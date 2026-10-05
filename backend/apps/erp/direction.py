from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db.models import Sum, F, OuterRef, Subquery, DecimalField, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from . import models as m, security


def total(queryset, field):
    return queryset.aggregate(value=Sum(field))['value'] or Decimal(0)


def summary(view, request):
    if view.member.role not in ('owner','admin','finance','viewer') or not view.enabled('invoices'):
        return None
    org=view.org
    zone=ZoneInfo(org.timezone)
    today=timezone.localdate(timezone=zone)
    try:
        start=date.fromisoformat(request.query_params.get('start',str(today-timedelta(days=29))))
        end=date.fromisoformat(request.query_params.get('end',str(today)))
    except (ValueError,TypeError):
        raise ValidationError('Les dates doivent être au format AAAA-MM-JJ.')
    length=(end-start).days+1
    if not 1<=length<=366:
        raise ValidationError('Choisissez une période de 1 à 366 jours.')

    def enabled(resource):
        return view.enabled(resource) and security.allowed(view.member.role,resource)

    def period(first,last):
        invoices=m.Invoice.objects.filter(organization=org,date__range=(first,last))
        sales=total(invoices.filter(kind='invoice',status__in=['issued','paid']),'subtotal')
        credits=total(invoices.filter(kind='credit',status='issued'),'subtotal')
        result={'revenue_ht':format(sales-credits,'.2f')}
        result['receipts']=format(total(m.Payment.objects.filter(organization=org,date__range=(first,last)),'amount'),'.2f') if enabled('payments') else None
        result['approved_expenses']=format(total(m.Expense.objects.filter(organization=org,date__range=(first,last),status='approved'),'amount'),'.2f') if enabled('expenses') else None
        if enabled('missions'):
            lower=datetime.combine(first,time.min,zone)
            upper=datetime.combine(last+timedelta(days=1),time.min,zone)
            result['completed_missions']=m.Mission.objects.filter(organization=org,status='completed',completed_at__gte=lower,completed_at__lt=upper).count()
        else:result['completed_missions']=None
        result['commercial_margin']=None
        if enabled('orders') and enabled('expenses') and enabled('subcontracts'):
            amount=DecimalField(max_digits=18,decimal_places=2)
            costs=m.Expense.objects.filter(organization=org,mission__order_id=OuterRef('pk'),status='approved').values('mission__order_id').annotate(amount=Sum('amount')).values('amount')
            subcontract=m.Subcontract.objects.filter(organization=org,mission__order_id=OuterRef('pk'),status='completed').values('mission__order_id').annotate(amount=Sum('agreed_amount')).values('amount')
            orders=m.TransportOrder.objects.filter(organization=org,planned_date__range=(first,last),status__in=['confirmed','completed']).annotate(direct_cost=Coalesce(Subquery(costs,output_field=amount),Value(Decimal(0)),output_field=amount),external_cost=Coalesce(Subquery(subcontract,output_field=amount),Value(Decimal(0)),output_field=amount))
            margin=orders.aggregate(value=Sum(F('amount')-F('direct_cost')-F('external_cost')))['value'] or Decimal(0)
            result['commercial_margin']=format(margin,'.2f')
        return result

    from .crm_services import invoice_balances
    unpaid=invoice_balances(m.Invoice.objects.filter(organization=org,kind='invoice',status='issued')).filter(remaining__gt=0)
    current=period(start,end)
    previous=period(start-timedelta(days=length),start-timedelta(days=1))
    return {'start':str(start),'end':str(end),'previous_start':str(start-timedelta(days=length)),
        'previous_end':str(start-timedelta(days=1)),'timezone':org.timezone,'today':str(today),
        'current':current,'previous':previous,
        'changes':{key:format(Decimal(value)-Decimal(previous[key]),'.2f') if value is not None else None for key,value in current.items()},
        'receivable_now':format(total(unpaid,'remaining'),'.2f'),
        'overdue_now':format(total(unpaid.filter(due_date__lt=today),'remaining'),'.2f'),
        'definitions':{'revenue_ht':'Factures émises ou soldées moins avoirs émis, HT, selon leur date.',
            'receipts':'Règlements clients enregistrés selon leur date de paiement.',
            'approved_expenses':'Dépenses validées selon leur date, sans addition des factures fournisseurs.',
            'completed_missions':'Missions terminées pendant la période dans le fuseau de l’entreprise.',
            'commercial_margin':'Prix HT des commandes confirmées ou réalisées prévues sur la période, moins leurs dépenses validées et sous-traitances réalisées ; hors charges indirectes.',
            'receivable_now':'Soldes positifs actuels des factures émises après paiements et avoirs ; hors créances soldées et crédits clients.'}}

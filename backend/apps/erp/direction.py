from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db.models import Sum, Count, Q, F, OuterRef, Subquery, DecimalField, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from . import models as m, security


def total(queryset, field):
    return queryset.aggregate(value=Sum(field))['value'] or Decimal(0)


def percentage(numerator, denominator):
    return format(Decimal(numerator)*100/Decimal(denominator),'.2f') if denominator else None


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

    try:
        previous_start=start-timedelta(days=length)
        previous_end=start-timedelta(days=1)
        end+timedelta(days=1)
    except OverflowError:
        raise ValidationError('Cette période dépasse les dates prises en charge.')

    def enabled(resource):
        return view.enabled(resource) and security.allowed(view.member.role,resource)

    def period(first,last):
        lower=datetime.combine(first,time.min,zone)
        upper=datetime.combine(last+timedelta(days=1),time.min,zone)
        invoices=m.Invoice.objects.filter(organization=org,date__range=(first,last))
        sales=total(invoices.filter(kind='invoice',status__in=['issued','paid']),'subtotal')
        credits=total(invoices.filter(kind='credit',status='issued'),'subtotal')
        result={'revenue_ht':format(sales-credits,'.2f')}
        result['receipts']=format(total(m.Payment.objects.filter(organization=org,date__range=(first,last)),'amount'),'.2f') if enabled('payments') else None
        result['approved_expenses']=format(total(m.Expense.objects.filter(organization=org,date__range=(first,last),status='approved'),'amount'),'.2f') if enabled('expenses') else None
        result.update(quotes_sent=None,quotes_accepted=None,quote_acceptance_rate=None)
        if 'commercial' in view.active_applications:
            quotes=m.QuoteLink.objects.filter(organization=org,quote__organization=org,quote__kind='quote',sent_at__gte=lower,sent_at__lt=upper).aggregate(sent=Count('pk'),accepted=Count('pk',filter=Q(quote__quote_status__in=['accepted','converted'])))
            result.update(quotes_sent=quotes['sent'],quotes_accepted=quotes['accepted'],quote_acceptance_rate=percentage(quotes['accepted'],quotes['sent']))
        result['orders']=m.TransportOrder.objects.filter(organization=org,planned_date__range=(first,last)).exclude(status='cancelled').count() if enabled('orders') else None
        result.update(missions=None,completion_rate=None,late_missions=None,vehicles_used=None)
        if enabled('missions'):
            result['completed_missions']=m.Mission.objects.filter(organization=org,status='completed',completed_at__gte=lower,completed_at__lt=upper).count()
            from .operations_rules import late_query
            trips=m.Mission.objects.filter(organization=org,departure__gte=lower,departure__lt=upper).exclude(status='cancelled')
            cohort=trips.aggregate(total=Count('pk'),completed=Count('pk',filter=Q(status='completed')),late=Count('pk',filter=late_query(timezone.now())|Q(status='completed',completed_at__gt=F('arrival'))))
            result.update(missions=cohort['total'],completion_rate=percentage(cohort['completed'],cohort['total']),late_missions=cohort['late'])
            if enabled('vehicles'):result['vehicles_used']=trips.values('vehicle_id').distinct().count()
        else:result['completed_missions']=None
        result['incidents']=m.Incident.objects.filter(organization=org,occurred_at__gte=lower,occurred_at__lt=upper,status__in=['reported','resolved']).count() if enabled('incidents') else None
        result['maintenance']=m.Maintenance.objects.filter(organization=org,due_date__range=(first,last)).exclude(status='cancelled').count() if enabled('maintenance') else None
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
    previous=period(previous_start,previous_end)
    clients=[]
    if enabled('partners'):
        sales=m.Invoice.objects.filter(organization=org,date__range=(start,end),status__in=['issued','paid'],kind__in=['invoice','credit'])
        for row in sales.values('customer_id','customer__name').annotate(invoiced=Sum('subtotal',filter=Q(kind='invoice')),credited=Sum('subtotal',filter=Q(kind='credit'))).annotate(net=Coalesce(F('invoiced'),Value(Decimal(0)))-Coalesce(F('credited'),Value(Decimal(0)))).order_by('-net','customer_id')[:5]:
            clients.append({'name':row['customer__name'],'revenue_ht':format(row['net'],'.2f')})
    fleet_now=None
    if enabled('vehicles') and enabled('missions'):
        from .operations_rules import availability,AVAILABILITY_MINUTES
        now=timezone.now()
        _,_,vehicles,_=availability(org,now,now+timedelta(minutes=AVAILABILITY_MINUTES))
        fleet_now={'available':vehicles.count(),'window_minutes':AVAILABILITY_MINUTES}
    return {'start':str(start),'end':str(end),'previous_start':str(previous_start),
        'previous_end':str(previous_end),'timezone':org.timezone,'today':str(today),
        'current':current,'previous':previous,
        'changes':{key:format(Decimal(value)-Decimal(previous[key]),'.2f') if value is not None and previous[key] is not None else None for key,value in current.items()},
        'units':{key:'percent' if key in ('quote_acceptance_rate','completion_rate') else 'count' if key in ('quotes_sent','quotes_accepted','orders','missions','completed_missions','late_missions','vehicles_used','incidents','maintenance') else 'money' for key in current},
        'top_clients':clients,'fleet_now':fleet_now,
        'receivable_now':format(total(unpaid,'remaining'),'.2f'),
        'overdue_now':format(total(unpaid.filter(due_date__lt=today),'remaining'),'.2f'),
        'definitions':{'revenue_ht':'Factures émises ou soldées moins avoirs émis, HT, selon leur date.',
            'quotes_sent':'Devis avec un envoi électronique réussi dont la dernière date d’envoi appartient à la période. Un renvoi compte une seule fois.',
            'quotes_accepted':'Parmi ces devis envoyés, ceux acceptés ou convertis à la date de consultation.',
            'quote_acceptance_rate':'Devis acceptés ou convertis parmi les devis envoyés dans la période ; indisponible si aucun envoi. Les écarts de taux sont en points de pourcentage.',
            'orders':'Commandes non annulées prévues sur la période, brouillons inclus.',
            'missions':'Missions non annulées dont le départ prévu appartient aux journées locales de la période.',
            'completion_rate':'Missions actuellement terminées parmi les missions non annulées au départ prévu dans la période ; indisponible sans mission.',
            'late_missions':'Dans cette cohorte, missions en retard selon les règles du Centre, ou terminées après l’arrivée prévue. La situation des missions ouvertes est celle de la consultation.',
            'vehicles_used':'Véhicules distincts affectés aux missions non annulées au départ prévu dans la période ; ce nombre ne mesure pas un taux horaire d’utilisation.',
            'incidents':'Incidents signalés ou résolus survenus dans les journées locales de la période ; brouillons exclus.',
            'maintenance':'Interventions non annulées dont la date prévue appartient à la période.',
            'receipts':'Règlements clients enregistrés selon leur date de paiement.',
            'approved_expenses':'Dépenses validées selon leur date, sans addition des factures fournisseurs.',
            'completed_missions':'Missions terminées pendant la période dans le fuseau de l’entreprise.',
            'commercial_margin':'Prix HT des commandes confirmées ou réalisées prévues sur la période, moins leurs dépenses validées et sous-traitances réalisées ; hors charges indirectes.',
            'receivable_now':'Soldes positifs actuels des factures émises après paiements et avoirs ; hors créances soldées et crédits clients.'}}

from datetime import date
from decimal import Decimal

from django.db.models import Sum
from rest_framework.exceptions import ValidationError

from . import models as m, security


def summary(view, request):
    view.ensure('journal')
    dates={}
    for key in ('start','end'):
        raw=request.query_params.get(key)
        if raw:
            try:dates[key]=date.fromisoformat(raw)
            except (ValueError,TypeError):raise ValidationError('Les dates doivent être au format AAAA-MM-JJ.')
    if len(dates)==2 and not 1<=(dates['end']-dates['start']).days+1<=366:
        raise ValidationError('Choisissez une période de 1 à 366 jours.')
    entries=m.JournalEntry.objects.filter(organization=view.org,status='posted')
    if 'start' in dates:entries=entries.filter(date__gte=dates['start'])
    if 'end' in dates:entries=entries.filter(date__lte=dates['end'])
    balances={a.code:{'code':a.code,'name':a.name,'debit':Decimal(0),'credit':Decimal(0)} for a in m.Account.objects.filter(organization=view.org).order_by('code')}
    for entry in entries.only('lines').iterator(chunk_size=500):
        for line in entry.lines:
            row=balances[line['account']];row['debit']+=Decimal(line['debit']);row['credit']+=Decimal(line['credit'])
    for row in balances.values():
        row['balance']=row['debit']-row['credit']
        for field in ('debit','credit','balance'):row[field]=format(row[field],'.2f')
    permitted=all(view.enabled(resource) and security.allowed(view.member.role,resource) for resource in ('orders','expenses','subcontracts'))
    result={'trial_balance':list(balances.values()),'profitability':[], 'profitability_available':permitted,'currency':view.org.currency,
        'start':str(dates['start']) if 'start' in dates else None,'end':str(dates['end']) if 'end' in dates else None,
        'profitability_count':0,'profitability_page':1,'profitability_pages':1,
        'note':'Rentabilité commerciale : prix convenu moins dépenses de mission validées et sous-traitances réalisées, hors charges indirectes.'}
    if not permitted:return result
    orders=view.queryset('orders').order_by('planned_date','reference','id')
    if 'start' in dates:orders=orders.filter(planned_date__gte=dates['start'])
    if 'end' in dates:orders=orders.filter(planned_date__lte=dates['end'])
    if request.query_params.get('status'):orders=orders.filter(status=request.query_params['status'])
    if request.query_params.get('customer'):
        try:orders=orders.filter(customer_id=request.query_params['customer'])
        except (ValueError,TypeError):raise ValidationError('Le client sélectionné est invalide.')
    from .views import Page
    paginator=Page();page=paginator.paginate_queryset(orders,request,view=view)
    identities=[order.pk for order in page]
    costs=dict(m.Expense.objects.filter(organization=view.org,status='approved',mission__order_id__in=identities).values('mission__order_id').annotate(total=Sum('amount')).values_list('mission__order_id','total'))
    subcontract_costs=dict(m.Subcontract.objects.filter(organization=view.org,status='completed',mission__order_id__in=identities).values('mission__order_id').annotate(total=Sum('agreed_amount')).values_list('mission__order_id','total'))
    for order in page:
        cost=costs.get(order.pk,Decimal(0))+subcontract_costs.get(order.pk,Decimal(0))
        result['profitability'].append({'reference':order.reference,'customer':order.customer.name,'revenue':format(order.amount,'.2f'),'cost':format(cost,'.2f'),'margin':format(order.amount-cost,'.2f')})
    result.update(profitability_count=paginator.page.paginator.count,profitability_page=paginator.page.number,profitability_pages=paginator.page.paginator.num_pages)
    return result

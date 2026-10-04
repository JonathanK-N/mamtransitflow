from datetime import timedelta
from decimal import Decimal
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from . import models as m, services


def invoice_balances(queryset):
    from django.db.models import OuterRef, Subquery, Sum, F, DecimalField, Value
    from django.db.models.functions import Coalesce
    credits=m.Invoice.objects.filter(organization_id=OuterRef('organization_id'),original_id=OuterRef('pk'),kind='credit',status='issued').values('original_id').annotate(amount=Sum('total')).values('amount')
    amount=DecimalField(max_digits=18,decimal_places=2)
    return queryset.annotate(credited_amount=Coalesce(Subquery(credits,output_field=amount),Value(Decimal(0)),output_field=amount)).annotate(remaining=F('total')-F('paid')-F('credited_amount'))


def payment_state(invoice):
    return 'partial' if invoice.kind=='invoice' and invoice.status=='issued' and invoice.paid>0 and getattr(invoice,'remaining',invoice.total-invoice.paid)>0 else invoice.status


def active_customer(customer):
    if customer.archived_at or customer.kind not in ('customer', 'both'):
        raise ValidationError('Sélectionnez un client actif.')


def allocate_bases(lines,amount,subtotal):
    cents=int(amount*100)
    shares=[services.rounded(services.decimal(line['quantity'])*services.decimal(line['price']))*cents/subtotal for line in lines]
    allocations=[int(share) for share in shares]
    remainder=cents-sum(allocations)
    priorities=sorted(range(len(lines)),key=lambda index:shares[index]-allocations[index],reverse=True)
    for index in priorities[:remainder]:allocations[index]+=1
    return [Decimal(value)/100 for value in allocations]


def commercial_notification(org,obj,event,title,resource):
    from .notifications import notify
    from .security import allowed
    from .applications import resource_enabled
    if not resource_enabled(org,resource):return
    for member in m.Membership.objects.filter(organization=org,active=True,user__is_active=True):
        if allowed(member.role,resource,True):
            notify(org,member.user_id,f'commercial:{obj.pk}:{event}','operations',title,'Consultez le dossier commercial.',{'module':resource,'id':str(obj.pk)})


@transaction.atomic
def quote_action(org, actor, quote, action, data):
    m.Organization.objects.select_for_update().get(pk=org.pk)
    quote = get_object_or_404(m.Invoice.objects.select_for_update(), organization=org, pk=quote.pk, kind='quote')
    if action == 'convert':
        existing = m.TransportOrder.objects.filter(organization=org, source_quote=quote).first()
        if existing:
            return existing
        if quote.quote_status != 'accepted':
            raise ValidationError('Acceptez le devis avant de créer la commande.')
        active_customer(quote.customer)
        if not quote.origin or not quote.destination:
            raise ValidationError('Le départ et la destination sont requis.')
        try:
            from datetime import date
            planned = date.fromisoformat(data.get('planned_date', str(timezone.localdate())))
        except (TypeError, ValueError):
            raise ValidationError('Date prévue invalide.')
        quantity=sum((services.decimal(x['quantity']) for x in quote.lines),Decimal(0))
        if quantity>=Decimal('1000000000000') or quantity!=quantity.quantize(Decimal('.001')):
            raise ValidationError('Les quantités de transport doivent tenir sur 12 chiffres et 3 décimales.')
        order = m.TransportOrder(organization=org, source_quote=quote,
            reference=services.sequence(org, 'CMD'), customer=quote.customer,
            origin=quote.origin, destination=quote.destination, activity=quote.activity,
            planned_date=planned, quantity=quantity.quantize(Decimal('.001')),
            unit=quote.unit, amount=quote.subtotal,
            product=' / '.join(x['description'] for x in quote.lines)[:180], notes=quote.notes)
        order.full_clean();order.save()
        services.audit(org, actor, 'quote-convert', order, quote=str(quote.pk))
        commercial_notification(org,order,'created','Commande à confirmer et planifier','orders')
        return order
    old = quote.quote_status
    if action == 'send' and old == 'draft' and quote.status == 'draft':
        if quote.due_date < timezone.localdate():
            raise ValidationError('La date de validité du devis est dépassée.')
        return services.transition(org, actor, m.Invoice, quote.pk, 'issue')
    elif action in ('accept', 'refuse', 'expire') and old == 'sent':
        expired = quote.due_date < timezone.localdate()
        if action == 'accept' and expired:
            raise ValidationError('Le devis a expiré.')
        if action == 'expire' and not expired:
            raise ValidationError('La date de validité n’est pas dépassée.')
        quote.quote_status = {'accept':'accepted', 'refuse':'refused', 'expire':'expired'}[action]
    else:
        raise ValidationError('Transition de devis impossible.')
    quote.save(update_fields=['quote_status','updated_at'])
    services.audit(org, actor, 'quote-'+action, quote, previous=old)
    if action=='accept':commercial_notification(org,quote,'accepted','Devis accepté','invoices')
    return quote


@transaction.atomic
def invoice_from_mission(org, actor, mission):
    m.Organization.objects.select_for_update().get(pk=org.pk)
    mission = get_object_or_404(m.Mission.objects.select_related('order__customer','order__source_quote'), organization=org, pk=mission.pk)
    if mission.status != 'completed' or not mission.order_id:
        raise ValidationError('Une mission terminée liée à une commande est requise.')
    order = mission.order
    existing = m.Invoice.objects.filter(organization=org, mission=mission, kind='invoice').exclude(status='cancelled').first()
    if existing:
        return existing
    quantity = mission.delivered_quantity or order.quantity or Decimal(1)
    price = services.rounded(order.amount / quantity)
    # Preserve the agreed amount when unit-price rounding would change the total.
    if services.rounded(price * quantity) != order.amount:
        quantity, price = Decimal(1), order.amount
    source=order.source_quote
    tax_rate=source.lines[0].get('tax_rate','0') if source and len(source.lines)==1 else '0'
    proposed=[dict(description=order.product or f'Transport {order.origin} → {order.destination}',quantity=str(quantity),price=str(price),tax_rate=tax_rate)]
    if source and len(source.lines)>1 and source.subtotal>0:
        proposed=[]
        for line,base in zip(source.lines,allocate_bases(source.lines,order.amount,source.subtotal)):
            proposed.append(dict(description=line['description'],quantity=line['quantity'],price=str(base/services.decimal(line['quantity'])),tax_rate=line['tax_rate']))
    lines, subtotal, tax, total = services.invoice_totals(proposed)
    today = timezone.localdate()
    invoice = m.Invoice.objects.create(organization=org, customer=order.customer, order=order,
        mission=mission, date=today, due_date=today+timedelta(days=order.customer.payment_days),
        lines=lines, subtotal=subtotal, tax=tax, total=total,unit=order.unit,notes=source.notes if source else '')
    services.audit(org, actor, 'invoice-draft-delivery', invoice, mission=str(mission.pk))
    return invoice

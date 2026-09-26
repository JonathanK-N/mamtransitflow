"""Transitions transactionnelles. Auteur : Jonathan Kakesa (JonathanK-N)."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from . import models as m


def decimal(value):
    try:
        result = Decimal(str(value))
        if not result.is_finite() or abs(result) >= Decimal('1000000000000000'):
            raise ValueError()
        return result
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError('Montant ou quantité invalide.')


def rounded(value): return decimal(value).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)


def audit(org, actor, action, obj, **detail):
    m.AuditEvent.objects.create(organization=org, actor=actor, action=action,
        resource=obj._meta.model_name, object_id=str(obj.pk), detail=detail)


def sequence(org, prefix):
    # Parent lock also serializes the first creation of a counter.
    m.Organization.objects.select_for_update().get(pk=org.pk)
    key = f'{prefix}-{timezone.now().year}'
    seq, _ = m.Sequence.objects.get_or_create(organization=org, key=key)
    seq.value += 1
    seq.save(update_fields=['value'])
    return f'{key}-{seq.value:05d}'


def invoice_totals(lines):
    if not isinstance(lines, list) or not 1 <= len(lines) <= 200:
        raise ValidationError({'lines': 'Saisissez entre 1 et 200 lignes.'})
    normalized, subtotal, taxes = [], Decimal(0), Decimal(0)
    for line in lines:
        if not isinstance(line, dict): raise ValidationError('Ligne invalide.')
        label = str(line.get('description', '')).strip()
        quantity, price, rate = decimal(line.get('quantity',1)), decimal(line.get('price',0)), decimal(line.get('tax_rate',0))
        if not label or len(label)>250 or quantity<=0 or price<0 or not 0<=rate<=100:
            raise ValidationError({'lines': 'Description, quantité positive, prix et taux entre 0 et 100 requis.'})
        base = rounded(quantity*price)
        tax = rounded(base*rate/100)
        subtotal += base; taxes += tax
        normalized.append({'description':label,'quantity':str(quantity),'price':str(price),'tax_rate':str(rate),'total':str(base+tax)})
    if subtotal+taxes >= Decimal('1000000000000000'): raise ValidationError('Total trop élevé.')
    return normalized, subtotal, taxes, subtotal+taxes


def journal_lines(org, lines):
    if not isinstance(lines,list) or not 2<=len(lines)<=200: raise ValidationError('Au moins deux lignes sont requises.')
    accounts=set(m.Account.objects.filter(organization=org).values_list('code',flat=True))
    normalized=[]; debit=credit=Decimal(0)
    for line in lines:
        if not isinstance(line,dict): raise ValidationError('Ligne invalide.')
        d,c=rounded(line.get('debit',0)),rounded(line.get('credit',0))
        code=str(line.get('account',''))
        if code not in accounts or d<0 or c<0 or (d>0)==(c>0):
            raise ValidationError('Chaque ligne exige un compte de cette entreprise et un débit OU un crédit positif.')
        debit+=d;credit+=c
        normalized.append({'account':code,'debit':str(d),'credit':str(c)})
    if debit!=credit: raise ValidationError(f'Écriture déséquilibrée : débit {debit}, crédit {credit}.')
    return normalized


def auto_journal(org, actor, reference, date, description, lines):
    entry=m.JournalEntry.objects.create(organization=org,reference=reference,date=date,
        description=description,lines=journal_lines(org,lines),status='posted')
    audit(org,actor,'post',entry)
    return entry


def setup_accounts(org):
    # Operational chart only; statutory localization requires country validation.
    for code,name in [('411','Clients'),('401','Fournisseurs'),('706','Prestations de transport'),
                      ('443','Taxes collectées'),('521','Banque et trésorerie'),('601','Achats et charges')]:
        m.Account.objects.get_or_create(organization=org,code=code,defaults={'name':name})


@transaction.atomic
def transition(org,actor,model,pk,action,data=None):
    data=data or {}
    # A consistent organization lock prevents opposing module lock orders.
    m.Organization.objects.select_for_update().get(pk=org.pk)
    obj=model.objects.select_for_update().get(pk=pk,organization=org)
    old=obj.status
    if model is m.Mission:
        if action=='start' and old=='planned':
            vehicle=m.Vehicle.objects.select_for_update().get(pk=obj.vehicle_id,organization=org)
            driver=m.Employee.objects.select_for_update().get(pk=obj.driver_id,organization=org)
            if vehicle.status!='available' or not driver.active or driver.job!='driver':
                raise ValidationError('Le véhicule ou le chauffeur est indisponible.')
            if driver.license_expiry and driver.license_expiry < timezone.localdate():
                raise ValidationError('Le permis du chauffeur est expiré.')
            if m.Mission.objects.filter(organization=org,status='active').filter(m.Q(vehicle=vehicle)|m.Q(driver=driver)).exists():
                raise ValidationError('Le véhicule ou le chauffeur effectue déjà une mission.')
            obj.status='active';obj.started_at=timezone.now()
        elif action=='complete' and old=='active':
            loaded=decimal(data.get('loaded_quantity',obj.loaded_quantity))
            delivered=decimal(data.get('delivered_quantity',obj.delivered_quantity))
            if loaded<0 or delivered<0 or delivered>loaded: raise ValidationError('Les quantités livrées doivent être comprises entre zéro et le chargement.')
            if obj.order_id and obj.order.unit==obj.vehicle.capacity_unit and loaded>obj.vehicle.capacity:
                raise ValidationError('Chargement supérieur à la capacité du véhicule.')
            obj.loaded_quantity=loaded;obj.delivered_quantity=delivered
            obj.delivery_note=str(data.get('delivery_note',obj.delivery_note))[:10000]
            obj.status='completed';obj.completed_at=timezone.now()
            if obj.order_id:
                obj.order.status='completed';obj.order.save(update_fields=['status','updated_at'])
        elif action=='cancel' and old=='planned':
            if m.Booking.objects.filter(mission=obj).exclude(status='cancelled').exists():
                raise ValidationError('Annulez les réservations avant cette mission.')
            obj.status='cancelled'
        else: raise ValidationError('Transition de mission impossible.')
    elif model is m.Maintenance:
        vehicle=m.Vehicle.objects.select_for_update().get(pk=obj.vehicle_id,organization=org)
        if action=='start' and old=='planned':
            if m.Mission.objects.filter(vehicle=vehicle,status='active').exists(): raise ValidationError('Véhicule en mission.')
            if vehicle.status=='retired': raise ValidationError('Véhicule hors service.')
            obj.status='active';vehicle.status='maintenance'
        elif action in ('complete','cancel') and old in ('planned','active'):
            obj.status='completed' if action=='complete' else 'cancelled'
            if not m.Maintenance.objects.filter(vehicle=vehicle,status='active').exclude(pk=obj.pk).exists() and vehicle.status=='maintenance':
                vehicle.status='available'
        else: raise ValidationError('Transition atelier impossible.')
        vehicle.save(update_fields=['status','updated_at'])
    elif model is m.TransportOrder:
        if action=='confirm' and old=='draft': obj.status='confirmed'
        elif action=='cancel' and old in ('draft','confirmed'):
            if m.Mission.objects.filter(order=obj).exclude(status='cancelled').exists(): raise ValidationError('Des missions sont liées à cette commande.')
            obj.status='cancelled'
        else: raise ValidationError('Transition de commande impossible.')
    elif model is m.Invoice:
        if action=='issue' and old=='draft':
            obj.lines,obj.subtotal,obj.tax,obj.total=invoice_totals(obj.lines)
            if obj.total<=0: raise ValidationError('Le total doit être positif.')
            obj.number=sequence(org,{'quote':'DEV','invoice':'FAC','credit':'AVO'}[obj.kind]);obj.status='issued'
            if obj.kind=='credit':
                if not obj.original_id or obj.original.kind!='invoice' or obj.original.status not in ('issued','paid') or obj.original.customer_id!=obj.customer_id:
                    raise ValidationError("Une facture d'origine émise pour ce client est requise.")
                credited=m.Invoice.objects.filter(original=obj.original,status='issued',kind='credit').aggregate(s=Sum('total'))['s'] or 0
                if credited+obj.total>obj.original.total: raise ValidationError("L'avoir dépasse le montant restant à créditer.")
            if obj.kind!='quote':
                lines=[{'account':'411','debit':str(obj.total),'credit':'0'}, {'account':'706','debit':'0','credit':str(obj.subtotal)}]
                if obj.tax: lines.append({'account':'443','debit':'0','credit':str(obj.tax)})
                if obj.kind=='credit': lines=[dict(x,debit=x['credit'],credit=x['debit']) for x in lines]
                auto_journal(org,actor,obj.number,obj.date,f'{obj.number} - {obj.customer.name}',lines)
        elif action=='cancel' and old=='draft': obj.status='cancelled'
        else: raise ValidationError('Seul un brouillon peut être émis ou annulé ; utilisez un avoir pour corriger une facture émise.')
    elif model is m.JournalEntry:
        if action!='post' or old!='draft': raise ValidationError('Cette écriture ne peut pas être comptabilisée.')
        obj.lines=journal_lines(org,obj.lines);obj.status='posted'
    elif model is m.Expense:
        if action!='approve' or old!='draft' or obj.amount<=0: raise ValidationError('Dépense non validable.')
        obj.status='approved'
        auto_journal(org,actor,f'DEP-{obj.pk}',obj.date,obj.title,[{'account':'601','debit':str(obj.amount)}, {'account':'521','credit':str(obj.amount)}])
    elif model is m.Booking:
        if action=='board' and old=='confirmed' and obj.mission.status in ('planned','active'): obj.status='boarded'
        elif action=='cancel' and old=='confirmed': obj.status='cancelled'
        else: raise ValidationError('Transition de réservation impossible.')
    elif model is m.Purchase:
        if action=='order' and old=='draft':
            obj.lines,obj.total=purchase_lines(org,obj.lines);obj.status='ordered'
        elif action=='receive' and old=='ordered':
            for line in obj.lines:
                stock_move(org,actor,{'item':m.StockItem.objects.get(pk=line['item'],organization=org),
                    'quantity':decimal(line['quantity']),'reason':f'Réception {obj.reference}', 'reference':f'{obj.pk}-{line["item"]}'})
            obj.status='received'
            if obj.total:
                auto_journal(org,actor,f'ACH-{obj.reference}',obj.date,f'Achat {obj.reference}',[{'account':'601','debit':str(obj.total)},{'account':'401','credit':str(obj.total)}])
        elif action=='cancel' and old in ('draft','ordered'):obj.status='cancelled'
        else: raise ValidationError('Transition achat impossible.')
    else: raise ValidationError('Action inconnue.')
    obj.full_clean();obj.save();audit(org,actor,action,obj,previous=old,status=obj.status)
    return obj


def purchase_lines(org,lines):
    if not isinstance(lines,list) or not 1<=len(lines)<=200: raise ValidationError('Articles requis.')
    out=[];total=Decimal(0);seen=set()
    for line in lines:
        if not isinstance(line,dict): raise ValidationError('Article invalide.')
        try: item=m.StockItem.objects.get(pk=line.get('item'),organization=org)
        except (m.StockItem.DoesNotExist, ValueError, TypeError): raise ValidationError('Article introuvable dans cette entreprise.')
        if str(item.pk) in seen: raise ValidationError('Regroupez les quantités du même article.')
        seen.add(str(item.pk));q=decimal(line.get('quantity',0));price=decimal(line.get('price',0))
        if q<=0 or price<0: raise ValidationError('Quantité positive et prix positif ou nul requis.')
        total+=rounded(q*price);out.append({'item':str(item.pk),'quantity':str(q),'price':str(price)})
    return out,total


@transaction.atomic
def stock_move(org,actor,data):
    item=m.StockItem.objects.select_for_update().get(pk=data['item'].pk,organization=org)
    q=decimal(data['quantity'])
    if q==0 or item.quantity+q<0: raise ValidationError('Mouvement nul ou stock insuffisant.')
    obj=m.StockMovement.objects.create(organization=org,**data)
    item.quantity+=q;item.save(update_fields=['quantity','updated_at']);audit(org,actor,'stock',obj)
    return obj


@transaction.atomic
def payment(org,actor,data):
    m.Organization.objects.select_for_update().get(pk=org.pk)
    inv=m.Invoice.objects.select_for_update().get(pk=data['invoice'].pk,organization=org)
    credit=m.Invoice.objects.filter(original=inv,kind='credit',status='issued').aggregate(s=Sum('total'))['s'] or 0
    amount=decimal(data['amount'])
    if inv.kind!='invoice' or inv.status!='issued' or amount<=0 or inv.paid+amount>inv.total-credit:
        raise ValidationError('Facture non payable ou montant supérieur au solde après avoirs.')
    obj=m.Payment.objects.create(organization=org,**data)
    inv.paid+=amount
    if inv.paid==inv.total-credit:inv.status='paid'
    inv.save(update_fields=['paid','status','updated_at'])
    auto_journal(org,actor,f'REG-{obj.pk}',obj.date,f'Règlement {inv.number}',[{'account':'521','debit':str(amount)},{'account':'411','credit':str(amount)}])
    audit(org,actor,'payment',obj)
    return obj


@transaction.atomic
def booking(org,actor,data):
    mission=m.Mission.objects.select_for_update().get(pk=data['mission'].pk,organization=org)
    if not mission.route_id or not mission.route.active or mission.status!='planned':raise ValidationError('Choisissez un départ voyageurs ouvert.')
    occupied=m.Booking.objects.filter(mission=mission).exclude(status='cancelled').aggregate(s=Sum('seats'))['s'] or 0
    if occupied+data['seats']>mission.vehicle.seats:raise ValidationError('Nombre de places disponibles insuffisant.')
    data['amount']=rounded(mission.route.fare*data['seats'])
    obj=m.Booking.objects.create(organization=org,**data);audit(org,actor,'book',obj)
    return obj

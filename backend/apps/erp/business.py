"""Services commerciaux et fournisseurs. Auteur : Jonathan Kakesa (JonathanK-N)."""
from calendar import monthrange
from datetime import timedelta,date
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from . import models as m,services

MODELS=(m.TransportContract,m.Subcontract,m.Incident,m.SupplierBill)


def validate(model,candidate,data):
    if model is m.TransportContract:
        if candidate.end_date<candidate.start_date:raise ValidationError('La fin du contrat doit suivre son début.')
        if candidate.next_date and not candidate.start_date<=candidate.next_date<=candidate.end_date:raise ValidationError('La prochaine prestation doit se situer dans le contrat.')
    if model is m.PricingRule and candidate.valid_until<candidate.valid_from:raise ValidationError('Période tarifaire invalide.')
    if model is m.Incident and candidate.mission_id and candidate.mission.vehicle_id!=candidate.vehicle_id:raise ValidationError('La mission et le véhicule ne correspondent pas.')
    if model is m.SupplierBill:
        if candidate.due_date<candidate.date:raise ValidationError('Échéance antérieure à la facture.')
        if candidate.purchase_id and candidate.purchase.supplier_id!=candidate.supplier_id:raise ValidationError('La commande appartient à un autre fournisseur.')
        if candidate.subcontract_id and candidate.subcontract.supplier_id!=candidate.supplier_id:raise ValidationError('La sous-traitance appartient à un autre fournisseur.')
        if candidate.purchase_id and candidate.subcontract_id:raise ValidationError('Choisissez un achat ou une sous-traitance.')
        data['lines'],data['subtotal'],data['tax'],data['total']=services.invoice_totals(candidate.lines)
    return data


def transition(org,actor,obj,action,data):
    old=obj.status
    if isinstance(obj,m.TransportContract):
        if action=='activate' and old in ('draft','paused'):
            obj.status='active';obj.next_date=obj.next_date or obj.start_date
        elif action=='pause' and old=='active':obj.status='paused'
        elif action=='close' and old in ('draft','active','paused'):obj.status='closed'
        elif action=='generate' and old=='active':
            if not obj.next_date or obj.next_date>obj.end_date:raise ValidationError('Toutes les prestations prévues ont déjà été générées.')
            reference=f'{obj.reference[:60]}-{obj.next_date.isoformat()}'
            if m.TransportOrder.objects.filter(organization=org,reference=reference).exists():raise ValidationError('La commande de cette échéance existe déjà.')
            order=m.TransportOrder.objects.create(organization=org,reference=reference,customer=obj.customer,activity=obj.activity,
                origin=obj.origin,destination=obj.destination,product=obj.description[:180],quantity=obj.quantity,unit=obj.unit,
                amount=obj.amount,planned_date=obj.next_date,notes=f'Contrat {obj.reference}')
            services.audit(org,actor,'contract-order',order,contract=str(obj.pk))
            if obj.recurrence=='once':obj.next_date=None;obj.status='closed'
            elif obj.recurrence=='weekly':obj.next_date+=timedelta(days=7)
            else:
                month=obj.next_date.month%12+1;year=obj.next_date.year+(obj.next_date.month==12)
                obj.next_date=date(year,month,min(obj.start_date.day,monthrange(year,month)[1]))
            if obj.next_date and obj.next_date>obj.end_date:obj.next_date=None;obj.status='closed'
        else:raise ValidationError('Action impossible pour ce contrat.')
    elif isinstance(obj,m.Subcontract):
        if action=='approve' and old=='draft':
            if obj.agreed_amount<=0 or obj.mission.status=='cancelled':raise ValidationError('Montant ou mission invalide.')
            obj.status='approved'
        elif action=='complete' and old=='approved':
            obj.completion_note=str(data.get('completion_note','')).strip()[:10000]
            if not obj.completion_note:raise ValidationError('Un bilan de prestation est requis.')
            obj.status='completed'
        elif action=='cancel' and old in ('draft','approved'):obj.status='cancelled'
        else:raise ValidationError('Action impossible pour cette sous-traitance.')
    elif isinstance(obj,m.Incident):
        if action=='report' and old=='draft':obj.status='reported'
        elif action=='resolve' and old=='reported':
            obj.resolution=str(data.get('resolution','')).strip()[:10000]
            if not obj.resolution:raise ValidationError('Décrivez les mesures prises avant la clôture.')
            obj.status='resolved';obj.resolved_at=timezone.now()
        else:raise ValidationError('Action impossible pour cet incident.')
    elif isinstance(obj,m.SupplierBill):
        if action=='post' and old=='draft':
            if obj.total<=0:raise ValidationError('La facture doit être positive.')
            if obj.purchase_id and obj.purchase.status!='received':raise ValidationError('Réceptionnez la commande avant de comptabiliser sa facture.')
            if obj.subcontract_id and obj.subcontract.status!='completed':raise ValidationError('La prestation sous-traitée doit être réalisée.')
            # Received purchases already recognized the net liability. Only the difference is posted here.
            accrued=obj.purchase.total if obj.purchase_id else 0
            difference=obj.total-accrued
            if difference:
                lines=[{'account':'601','debit':str(abs(difference))},{'account':'401','credit':str(abs(difference))}]
                if difference<0:lines=[{'account':x['account'],'debit':x.get('credit','0'),'credit':x.get('debit','0')} for x in lines]
                services.auto_journal(org,actor,'FOU-'+str(obj.pk),obj.date,'Facture fournisseur '+obj.reference,lines)
            obj.status='posted'
        elif action=='cancel' and old=='draft':obj.status='cancelled'
        else:raise ValidationError('Facture verrouillée ; cette action est impossible.')
    obj.full_clean();obj.save();services.audit(org,actor,action,obj,previous=old,status=obj.status)
    return obj


@transaction.atomic
def supplier_payment(org,actor,data):
    m.Organization.objects.select_for_update().get(pk=org.pk)
    bill=m.SupplierBill.objects.select_for_update().get(pk=data['bill'].pk,organization=org)
    amount=services.decimal(data['amount'])
    if bill.status!='posted' or amount<=0 or bill.paid+amount>bill.total:raise ValidationError('Montant supérieur au solde ou facture non payable.')
    obj=m.SupplierPayment.objects.create(organization=org,**data)
    bill.paid+=amount
    if bill.paid==bill.total:bill.status='paid'
    bill.save(update_fields=['paid','status','updated_at'])
    services.auto_journal(org,actor,'FOU-REG-'+str(obj.pk),obj.date,'Règlement fournisseur '+bill.reference,
        [{'account':'401','debit':str(amount)},{'account':'521','credit':str(amount)}])
    services.audit(org,actor,'supplier-payment',obj)
    return obj

"""Contrats et validation. Auteur : Jonathan Kakesa (JonathanK-N)."""
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from django.db import models
from django.core.exceptions import ValidationError as DjangoValidation
from rest_framework import serializers
from apps.comptes.models import Utilisateur
from . import models as m, services

RESOURCES = {
    'partners':m.Partner,'employees':m.Employee,'vehicles':m.Vehicle,'orders':m.TransportOrder,
    'routes':m.Route,'missions':m.Mission,'bookings':m.Booking,'maintenance':m.Maintenance,
    'expenses':m.Expense,'invoices':m.Invoice,'payments':m.Payment,'accounts':m.Account,
    'journal':m.JournalEntry,'stock':m.StockItem,'movements':m.StockMovement,'purchases':m.Purchase,
    'documents':m.Document,'audit':m.AuditEvent,
}
PROTECTED = {
    m.Mission:['status','started_at','completed_at'],m.TransportOrder:['status'],m.Maintenance:['status'],
    m.Booking:['status','amount'],m.Expense:['status'],m.Invoice:['status','number','subtotal','tax','total','paid'],
    m.JournalEntry:['status'],m.Purchase:['status','total'],m.StockItem:['quantity'],
}


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model=m.Organization
        fields=['id','name','slug','country','currency','timezone','activities','address','phone','email','registration','tax_number']
        read_only_fields=['id','slug']
    def validate_timezone(self,value):
        try:ZoneInfo(value)
        except (ZoneInfoNotFoundError,ValueError):raise serializers.ValidationError('Fuseau horaire inconnu.')
        return value
    def validate_activities(self,value):
        if not isinstance(value,list) or not value or any(x not in dict(m.ACTIVITIES) for x in value):
            raise serializers.ValidationError('Choisissez au moins une activité connue.')
        return list(dict.fromkeys(value))


class ScopedSerializer(serializers.ModelSerializer):
    label=serializers.SerializerMethodField()
    relations=serializers.SerializerMethodField()
    def get_label(self,obj):return str(obj)
    def get_relations(self,obj):
        return {f.name:str(getattr(obj,f.name)) for f in obj._meta.fields
                if isinstance(f,models.ForeignKey) and f.name not in ('organization','actor','user') and getattr(obj,f.attname)}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        org=self.context.get('organization')
        for name,field in self.fields.items():
            if isinstance(field,serializers.PrimaryKeyRelatedField) and not field.read_only:
                related=self.Meta.model._meta.get_field(name).related_model
                if related is Utilisateur:
                    field.queryset=Utilisateur.objects.filter(membership__organization=org,membership__active=True) if org else Utilisateur.objects.none()
                else:field.queryset=related.objects.filter(organization=org) if org else related.objects.none()
    def validate(self,data):
        org=self.context['organization'];model=self.Meta.model
        current=self.instance
        if current and hasattr(current,'status') and model not in (m.Vehicle,) and current.status not in ('draft','planned'):
            raise serializers.ValidationError('Ce document est verrouillé par son état ; utilisez les actions métier.')
        if model in (m.Payment,m.StockMovement,m.Booking) and current:
            raise serializers.ValidationError('Enregistrement immuable ; utilisez une action de correction.')
        if model is m.Account and current and data.get('code',current.code)!=current.code:
            raise serializers.ValidationError('Le numéro de compte est permanent. Créez un autre compte.')
        if model is m.Vehicle and current:
            status=data.get('status',current.status)
            if status=='maintenance' and status!=current.status:raise serializers.ValidationError('Démarrez une intervention pour immobiliser le véhicule.')
            if status!=current.status and (m.Mission.objects.filter(vehicle=current,status='active').exists() or m.Maintenance.objects.filter(vehicle=current,status='active').exists()):
                raise serializers.ValidationError('Le véhicule a une mission ou une intervention en cours.')
            if data.get('mileage',current.mileage)<current.mileage:raise serializers.ValidationError('Le compteur ne peut pas reculer.')
        if model is m.Employee and current and data.get('active') is False and m.Mission.objects.filter(driver=current,status='active').exists():
            raise serializers.ValidationError('Ce chauffeur a une mission en cours.')
        candidate=model(organization=org)
        if current:
            for f in model._meta.fields:setattr(candidate,f.attname,getattr(current,f.attname))
        for k,v in data.items():setattr(candidate,k,v)
        if model is m.Mission:
            if candidate.arrival<=candidate.departure:raise serializers.ValidationError('L’arrivée doit suivre le départ.')
            if candidate.driver.job!='driver':raise serializers.ValidationError('Sélectionnez un chauffeur.')
            if candidate.order_id and candidate.order.status not in ('confirmed',):raise serializers.ValidationError('Confirmez la commande avant sa mission.')
            if candidate.order_id and candidate.route_id:raise serializers.ValidationError('Choisissez une commande ou une ligne voyageurs.')
            if candidate.route_id and candidate.vehicle.seats<=0:raise serializers.ValidationError('Le véhicule doit disposer de places voyageurs.')
            if candidate.order_id and candidate.order.unit==candidate.vehicle.capacity_unit and candidate.loaded_quantity>candidate.vehicle.capacity:
                raise serializers.ValidationError('Chargement supérieur à la capacité du véhicule.')
            overlaps=m.Mission.objects.filter(organization=org,status__in=['planned','active'],departure__lt=candidate.arrival,arrival__gt=candidate.departure).filter(m.Q(vehicle=candidate.vehicle)|m.Q(driver=candidate.driver))
            if current:overlaps=overlaps.exclude(pk=current.pk)
            if overlaps.exists():raise serializers.ValidationError('Chevauchement de planning pour ce véhicule ou ce chauffeur.')
        if model is m.Invoice:
            if candidate.due_date<candidate.date:raise serializers.ValidationError('L’échéance ne peut pas précéder la date.')
            if candidate.order_id and candidate.order.customer_id!=candidate.customer_id:
                raise serializers.ValidationError('La commande appartient à un autre client.')
            data['lines'],data['subtotal'],data['tax'],data['total']=services.invoice_totals(candidate.lines)
            if candidate.original_id and (candidate.original.customer_id!=candidate.customer_id or candidate.original.kind!='invoice'):
                raise serializers.ValidationError("La facture d'origine doit appartenir au même client.")
        if model is m.JournalEntry:data['lines']=services.journal_lines(org,candidate.lines)
        if model is m.Purchase:data['lines'],data['total']=services.purchase_lines(org,candidate.lines)
        if model is m.Vehicle:
            parts=candidate.compartments
            if not isinstance(parts,list) or len(parts)>30:raise serializers.ValidationError('Compartiments invalides.')
            capacities=[]
            for item in parts:
                if not isinstance(item,dict) or not item.get('name'):raise serializers.ValidationError('Nom et capacité de chaque compartiment requis.')
                capacity=services.decimal(item.get('capacity',0))
                if capacity<=0:raise serializers.ValidationError('Capacité du compartiment positive requise.')
                capacities.append(capacity)
            if sum(capacities)>candidate.capacity:raise serializers.ValidationError('Les compartiments dépassent la capacité totale.')
        try:candidate.clean()
        except DjangoValidation as exc:raise serializers.ValidationError(exc.message_dict)
        return data
    def validate_file(self,value):
        from pathlib import Path
        extension=Path(value.name).suffix.lower()
        if value.size>10*1024*1024:raise serializers.ValidationError('Fichier limité à 10 Mo.')
        signatures={'.pdf':b'%PDF-', '.png':b'\x89PNG\r\n\x1a\n', '.jpg':b'\xff\xd8\xff', '.jpeg':b'\xff\xd8\xff'}
        start=value.read(16);value.seek(0)
        if extension not in signatures or not start.startswith(signatures[extension]):
            raise serializers.ValidationError('Seuls les fichiers PDF, PNG et JPEG valides sont acceptés.')
        return value


def serializer_for(model):
    excluded=['organization']
    if model is m.Document:pass
    class Meta:
        exclude=excluded
        read_only_fields=['id','created_at','updated_at']+PROTECTED.get(model,[])
        validators=[]
    Meta.model=model
    return type(f'{model.__name__}Serializer',(ScopedSerializer,),{'Meta':Meta})

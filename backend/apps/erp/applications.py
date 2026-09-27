"""Applications installables et studio. Auteur : Jonathan Kakesa (JonathanK-N)."""
import re
from datetime import date
from decimal import Decimal,InvalidOperation
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError,PermissionDenied,APIException
from . import models as m,services
from .views import ScopedView,Page


APPLICATIONS={
 'people':dict(name='Congés & avances',category='Gestion',description='Demandes de congés, indisponibilités et avances enregistrées du personnel.',icon='file',resources=['leave','advances'],depends=['finance'],default=True),
 'treasury':dict(name='Trésorerie & clôtures',category='Gestion',description='Relevés manuels, rapprochement des écritures et verrouillage des périodes.',icon='wallet',resources=['periods','statements'],depends=['finance'],default=True),
 'commercial':dict(name='Contrats & tarification',category='Gestion',description='Contrats récurrents, commandes par échéance et grilles tarifaires.',icon='file',resources=['contracts','pricing'],depends=['dispatch'],default=True),
 'subcontracting':dict(name='Sous-traitance',category='Exploitation',description='Prestataires, engagements et suivi des prestations externalisées.',icon='truck',resources=['subcontracts'],depends=['dispatch'],default=True),
 'incidents':dict(name='Incidents & sinistres',category='Exploitation',description='Signalement, dossiers assurance et résolution des incidents.',icon='wrench',resources=['incidents'],depends=['fleet'],default=True),
 'payables':dict(name='Comptes fournisseurs',category='Gestion',description='Factures fournisseurs, échéances, dettes et règlements enregistrés.',icon='wallet',resources=['supplier-bills','supplier-payments'],depends=['finance'],default=True),
 'fleet':dict(name='Flotte',category='Exploitation',description='Véhicules, capacités et échéances de votre parc.',icon='truck',resources=['vehicles'],depends=[],default=True),
 'dispatch':dict(name='Transport & missions',category='Exploitation',description='Commandes, planification, affectations et livraisons.',icon='route',resources=['orders','missions'],depends=['fleet'],default=True),
 'passengers':dict(name='Voyageurs & navettes',category='Exploitation',description='Lignes, circuits, départs et réservations de places.',icon='bus',resources=['routes','bookings'],depends=['dispatch'],default=True),
 'workshop':dict(name='Atelier',category='Exploitation',description='Interventions, immobilisations et entretien de la flotte.',icon='wrench',resources=['maintenance'],depends=['fleet'],default=True),
 'inventory':dict(name='Achats & stocks',category='Gestion',description='Pièces, commandes fournisseurs et mouvements de stock.',icon='package',resources=['stock','movements','purchases'],depends=[],default=True),
 'finance':dict(name='Facturation & comptabilité',category='Gestion',description='Devis, factures, règlements enregistrés et écritures comptables.',icon='wallet',resources=['invoices','payments','expenses','accounts','journal'],depends=[],default=True),
 'documents':dict(name='Documents',category='Collaboration',description='Justificatifs privés et documents de vos opérations.',icon='file',resources=['documents'],depends=[],default=True),
 'payment-connectors':dict(name='Paiements connectés',category='Connexions',description='Futurs connecteurs bancaires et Mobile Money. APIs partenaires en attente.',icon='credit-card',resources=[],depends=['finance'],default=False,pending=True),
}


def active_keys(org):
    keys={key for key,value in APPLICATIONS.items() if value['default']}
    for row in m.InstalledApplication.objects.filter(organization=org):
        if row.enabled:keys.add(row.key)
        else:keys.discard(row.key)
    return keys


def resource_enabled(org,resource,active=None):
    key=next((k for k,v in APPLICATIONS.items() if resource in v['resources']),None)
    return key is None or key in (active if active is not None else active_keys(org))


def can_use(app,role,write=False):
    return app.enabled and (role in ('owner','admin') or role in (app.write_roles if write else app.read_roles))


def app_data(app,role):
    return dict(id=str(app.pk),name=app.name,slug=app.slug,description=app.description,icon=app.icon,
        color=app.color,fields=app.fields,read_roles=app.read_roles,write_roles=app.write_roles,
        enabled=app.enabled,writable=can_use(app,role,True))


def validate_fields(fields):
    if not isinstance(fields,list) or not 1<=len(fields)<=30:raise ValidationError('Une application contient de 1 à 30 champs.')
    output=[];keys=set()
    for field in fields:
        if not isinstance(field,dict):raise ValidationError('Champ invalide.')
        key=str(field.get('key',''));label=str(field.get('label','')).strip();kind=field.get('type','text')
        if not re.fullmatch('[a-z][a-z0-9_]{0,39}',key) or key in keys:raise ValidationError('Les identifiants des champs doivent être uniques et alphanumériques.')
        if not label or len(label)>80 or kind not in ('text','textarea','number','date','checkbox','select','email'):
            raise ValidationError('Libellé ou type de champ invalide.')
        if type(field.get('required',False)) is not bool:raise ValidationError('Indicateur obligatoire invalide.')
        options=field.get('options',[]) if kind=='select' else []
        if kind=='select' and (not isinstance(options,list) or not 1<=len(options)<=40 or any(not isinstance(x,str) or not x.strip() or len(x)>80 for x in options) or len(set(options))!=len(options)):
            raise ValidationError('Choisissez de 1 à 40 options distinctes.')
        keys.add(key);output.append(dict(key=key,label=label,type=kind,required=field.get('required',False),options=options))
    return output


def validate_values(fields,data):
    if not isinstance(data,dict):raise ValidationError('Fiche invalide.')
    if set(data)-{f['key'] for f in fields}:raise ValidationError('Cette fiche contient un champ inconnu.')
    result={}
    for field in fields:
        key=field['key'];value=data.get(key);kind=field['type']
        if value is None or value=='':
            if field['required']:raise ValidationError({key:'Ce champ est obligatoire.'})
            result[key]=None;continue
        if kind=='checkbox':
            if type(value) is not bool:raise ValidationError({key:'Valeur oui/non requise.'})
        elif kind=='number':
            try:
                number=Decimal(str(value))
                if not number.is_finite() or abs(number)>=Decimal('1e15') or number.as_tuple().exponent < -6:raise ValueError()
                value=str(number)
            except (InvalidOperation,ValueError):raise ValidationError({key:'Nombre invalide (six décimales maximum).'})
        elif kind=='date':
            try:value=date.fromisoformat(str(value)).isoformat()
            except ValueError:raise ValidationError({key:'Date invalide.'})
        else:
            if not isinstance(value,str) or len(value)>(5000 if kind=='textarea' else 500):raise ValidationError({key:'Texte trop long ou invalide.'})
            if kind=='select' and value not in field['options']:raise ValidationError({key:'Option inconnue.'})
            if kind=='email':
                from rest_framework.serializers import EmailField
                value=EmailField().run_validation(value)
        result[key]=value
    return result


class ApplicationStoreView(ScopedView):
    def get(self,request):
        keys=active_keys(self.org);admin=self.member.role in ('owner','admin')
        custom=m.CustomApplication.objects.filter(organization=self.org)
        return Response({'applications':[dict(value,key=key,installed=key in keys,status='pending' if value.get('pending') else 'available') for key,value in APPLICATIONS.items()],
            'custom':[app_data(x,self.member.role) for x in custom if admin or can_use(x,self.member.role)],'admin':admin})
    def post(self,request):
        if self.member.role not in ('owner','admin'):raise PermissionDenied('Administration requise.')
        m.Organization.objects.select_for_update().get(pk=self.org.pk)
        key=request.data.get('key');enabled=request.data.get('enabled')
        if not isinstance(key,str) or key not in APPLICATIONS or type(enabled) is not bool:raise ValidationError('Application ou état invalide.')
        keys=active_keys(self.org)
        if not enabled:
            dependants=[v['name'] for k,v in APPLICATIONS.items() if k in keys and key in v['depends']]
            if dependants:raise ValidationError('Désactivez d’abord : '+', '.join(dependants))
        def enable(target):
            for dependency in APPLICATIONS[target]['depends']:enable(dependency)
            row,_=m.InstalledApplication.objects.update_or_create(organization=self.org,key=target,defaults={'enabled':True})
            services.audit(self.org,request.user,'app-enable',row)
        if enabled:enable(key)
        else:
            row,_=m.InstalledApplication.objects.update_or_create(organization=self.org,key=key,defaults={'enabled':False})
            services.audit(self.org,request.user,'app-disable',row)
        return self.get(request)


class CustomApplicationView(ScopedView):
    def save(self,request,pk=None):
        if self.member.role not in ('owner','admin'):raise PermissionDenied('Administration requise.')
        m.Organization.objects.select_for_update().get(pk=self.org.pk)
        app=get_object_or_404(m.CustomApplication.objects.select_for_update(),pk=pk,organization=self.org) if pk else m.CustomApplication(organization=self.org)
        name=str(request.data.get('name',app.name)).strip()
        description=str(request.data.get('description',app.description)).strip()
        if not name or len(name)>80 or len(description)>500:raise ValidationError('Nom ou description invalide.')
        fields=validate_fields(request.data.get('fields',app.fields))
        roles=set(dict(m.ROLES))
        read=request.data.get('read_roles',app.read_roles);write=request.data.get('write_roles',app.write_roles)
        if not isinstance(read,list) or not isinstance(write,list) or any(not isinstance(x,str) or x not in roles for x in read+write) or 'viewer' in write or not set(write)<=set(read):
            raise ValidationError('Droits incohérents : tout rôle autorisé à modifier doit pouvoir lire ; le rôle lecture seule ne peut pas modifier.')
        if pk and app.records.exists():
            proposed={f['key']:f for f in fields};old_keys={f['key'] for f in app.fields}
            for old in app.fields:
                new=proposed.get(old['key'])
                if not new or any(new[k]!=old[k] for k in ('type','required','options')):
                    raise ValidationError('Des fiches existent : conservez les champs, leurs types et contraintes. Vous pouvez renommer les libellés ou ajouter des champs facultatifs.')
            if any(f['required'] and f['key'] not in old_keys for f in fields):raise ValidationError('Un nouveau champ doit rester facultatif pour les fiches existantes.')
        enabled=request.data.get('enabled',app.enabled)
        if type(enabled) is not bool:raise ValidationError('État invalide.')
        icon=request.data.get('icon',app.icon);color=request.data.get('color',app.color)
        if icon not in ('folder','truck','users','file','package','calendar','wrench','wallet') or color not in ('green','blue','purple','orange'):
            raise ValidationError('Icône ou couleur invalide.')
        app.name=name;app.description=description;app.fields=fields;app.read_roles=read;app.write_roles=write;app.enabled=enabled;app.icon=icon;app.color=color
        if not pk:app.slug=(slugify(name)[:55] or 'application')+'-'+str(app.pk)[:8]
        app.save();services.audit(self.org,request.user,'app-configure' if pk else 'app-create',app)
        return Response(app_data(app,self.member.role),status=200 if pk else 201)
    def post(self,request):return self.save(request)
    def patch(self,request,pk):return self.save(request,pk)


class RecordConflict(APIException):
    status_code=409
    default_detail='Cette fiche a changé depuis son ouverture. Actualisez avant de réessayer.'


class CustomRecordsView(ScopedView):
    def application(self,pk,write=False):
        app=get_object_or_404(m.CustomApplication,pk=pk,organization=self.org)
        if not can_use(app,self.member.role,write):raise PermissionDenied('Application inactive ou accès insuffisant.')
        return app
    def output(self,obj):return dict(id=str(obj.pk),title=obj.title,data=obj.data,revision=obj.revision,created_at=obj.created_at,updated_at=obj.updated_at)
    def get(self,request,app_id,pk=None):
        app=self.application(app_id);qs=app.records.filter(organization=self.org)
        if pk:return Response(self.output(get_object_or_404(qs,pk=pk)))
        if request.query_params.get('q'):qs=qs.filter(title__icontains=request.query_params['q'][:150])
        paginator=Page();page=paginator.paginate_queryset(qs,request)
        return paginator.get_paginated_response([self.output(x) for x in page])
    def save(self,request,app_id,pk=None):
        m.Organization.objects.select_for_update().get(pk=self.org.pk)
        app=self.application(app_id,True)
        obj=get_object_or_404(m.CustomRecord.objects.select_for_update(),organization=self.org,application=app,pk=pk) if pk else m.CustomRecord(organization=self.org,application=app,created_by=request.user)
        if pk and request.data.get('revision')!=obj.revision:raise RecordConflict()
        values=validate_values(app.fields,request.data.get('data',{}))
        obj.data=values;obj.title=next((str(values[f['key']])[:200] for f in app.fields if values.get(f['key']) not in (None,'') and f['type'] in ('text','email','select')),app.name)
        if pk:obj.revision+=1
        obj.full_clean();obj.save();services.audit(self.org,request.user,'record-update' if pk else 'record-create',obj,application=str(app.pk))
        return Response(self.output(obj),status=200 if pk else 201)
    def post(self,request,app_id):return self.save(request,app_id)
    def patch(self,request,app_id,pk):return self.save(request,app_id,pk)
    def delete(self,request,app_id,pk):
        app=self.application(app_id,True)
        obj=get_object_or_404(m.CustomRecord.objects.select_for_update(),organization=self.org,application=app,pk=pk)
        if request.data.get('revision')!=obj.revision:raise RecordConflict()
        services.audit(self.org,request.user,'record-delete',obj,application=str(app.pk));obj.delete()
        return Response(status=204)

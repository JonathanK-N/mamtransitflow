"""Parcours terrain. Auteur : Jonathan Kakesa (JonathanK-N)."""
import hashlib
from datetime import timedelta
from pathlib import Path
from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from . import models as m, services
from .views import ScopedView, Page
from .serializers import serializer_for

CHECKS={'brakes':'Freins','tires':'Pneus','lights':'Éclairage','fluids':'Niveaux et fuites','equipment':'Équipements de sécurité','documents':'Documents du véhicule'}


class ReportInput(serializers.Serializer):
    mission=serializers.UUIDField()
    kind=serializers.ChoiceField(choices=['incident','request','check','mileage'])
    title=serializers.CharField(max_length=180)
    description=serializers.CharField(max_length=10000,required=False,allow_blank=True,default='')
    mileage=serializers.IntegerField(min_value=0,max_value=2147483647,required=False)
    severity=serializers.ChoiceField(choices=['minor','major','critical'],default='minor')
    category=serializers.ChoiceField(choices=['breakdown','accident','cargo','delay','other'],default='breakdown')
    occurred_at=serializers.DateTimeField(required=False)
    checks=serializers.JSONField(required=False,default=dict)


class FieldView(ScopedView):
    def check(self):
        if self.member.role not in ('owner','admin','operations','workshop','driver'):raise PermissionDenied()
        if not self.enabled('missions'):raise PermissionDenied('L’application transport est désactivée.')
    def trips(self):
        qs=m.Mission.objects.filter(organization=self.org)
        if self.member.role=='driver':qs=qs.filter(driver__user=self.request.user)
        return qs
    def reports(self):
        qs=m.FieldReport.objects.filter(organization=self.org)
        if self.member.role=='driver':qs=qs.filter(actor=self.request.user,mission__driver__user=self.request.user)
        return qs.select_related('mission','incident','maintenance','actor').prefetch_related('attachments')
    def get(self,request,pk=None):
        self.check()
        if pk:
            attachment=get_object_or_404(m.FieldAttachment,organization=self.org,pk=pk,report__in=self.reports())
            services.audit(self.org,request.user,'field-download',attachment)
            response=FileResponse(attachment.file.open('rb'),as_attachment=True,filename=attachment.title+Path(attachment.file.name).suffix)
            response['X-Content-Type-Options']='nosniff'
            return response
        def item(x):
            return dict(id=str(x.pk),mission=x.mission.reference,kind=x.kind,title=x.title,description=x.description,
                mileage=x.mileage,checks=x.checks,created_at=x.created_at,author=x.actor.nom,
                status=x.incident.status if x.incident_id else x.maintenance.status if x.maintenance_id else 'recorded',
                response=x.incident.resolution if x.incident_id else x.maintenance.notes if x.maintenance_id else '',
                incident=str(x.incident_id) if x.incident_id else None,maintenance=str(x.maintenance_id) if x.maintenance_id else None,
                attachments=[dict(id=str(a.pk),title=a.title) for a in x.attachments.all()])
        paginator=Page();rows=paginator.paginate_queryset(self.reports(),request)
        return paginator.get_paginated_response([item(x) for x in rows])
    def post(self,request,pk=None):
        self.check()
        if self.member.role=='workshop':raise PermissionDenied('Utilisez les interventions atelier pour le traitement.')
        m.Organization.objects.select_for_update().get(pk=self.org.pk)
        if pk:
            report=get_object_or_404(self.reports(),pk=pk)
            upload=serializers.FileField().run_validation(request.data.get('file'))
            serializer_for(m.Document)(context=self.context()).validate_file(upload)
            title=serializers.CharField(max_length=180).run_validation(request.data.get('title'))
            row=m.FieldAttachment.objects.create(organization=self.org,report=report,file=upload,title=title)
            services.audit(self.org,request.user,'field-attachment',row)
            return Response({'id':str(row.pk)},status=201)
        serializer=ReportInput(data=request.data);serializer.is_valid(raise_exception=True);data=serializer.validated_data
        trip=get_object_or_404(self.trips(),pk=data['mission'])
        if trip.status=='cancelled':raise ValidationError('Cette mission est annulée.')
        kind=data['kind'];mileage=data.get('mileage');checks=data['checks'];description=data['description']
        if kind in ('check','mileage') and mileage is None:raise ValidationError('Le relevé kilométrique est requis.')
        if kind=='check':
            if trip.status!='planned':raise ValidationError('Le contrôle avant départ concerne une mission planifiée.')
            if not isinstance(checks,dict) or set(checks)!=set(CHECKS) or any(type(v) is not bool for v in checks.values()):
                raise ValidationError('Renseignez chacun des six points de contrôle.')
            if not all(checks.values()) and not description:raise ValidationError('Décrivez les anomalies du contrôle.')
        elif checks:raise ValidationError('Les points de contrôle sont réservés au contrôle avant départ.')
        if kind in ('incident','request') and not description:raise ValidationError('Décrivez les faits ou les travaux demandés.')
        if kind=='incident' and not self.enabled('incidents'):raise PermissionDenied('L’application incidents est désactivée.')
        if kind=='request' and not self.enabled('maintenance'):raise PermissionDenied('L’application entretien est désactivée.')
        if mileage is not None:
            vehicle=m.Vehicle.objects.select_for_update().get(pk=trip.vehicle_id,organization=self.org)
            if mileage<vehicle.mileage:raise ValidationError('Le compteur ne peut pas diminuer. Contactez l’administration pour une correction.')
            vehicle.mileage=mileage;vehicle.save(update_fields=['mileage','updated_at'])
        row=m.FieldReport(organization=self.org,mission=trip,actor=request.user,kind=kind,title=data['title'],description=description,mileage=mileage,checks=checks)
        if kind=='incident':
            occurred=data.get('occurred_at',timezone.now())
            if occurred>timezone.now():raise ValidationError('La date de l’incident ne peut pas être future.')
            row.incident=m.Incident.objects.create(organization=self.org,reference='TER-'+str(row.pk),title=row.title,
                mission=trip,vehicle=trip.vehicle,occurred_at=occurred,severity=data['severity'],category=data['category'],description=description,status='reported')
        if kind=='request' or kind=='check' and not all(checks.values()):
            if not self.enabled('maintenance'):raise PermissionDenied('Activez Entretien pour transmettre les anomalies à l’atelier.')
            row.maintenance=m.Maintenance.objects.create(organization=self.org,vehicle=trip.vehicle,title=row.title,notes=description,due_date=timezone.localdate())
        row.full_clean();row.save();services.audit(self.org,request.user,'field-report',row,kind=kind)
        return Response({'id':str(row.pk)},status=201)


class FieldContextView(FieldView):
    def get(self,request):
        self.check()
        qs=self.trips().filter(status__in=['planned','active','completed']).select_related('vehicle')
        q=request.query_params.get('q','').strip()
        if q:qs=qs.filter(Q(reference__icontains=q)|Q(vehicle__plate__icontains=q))
        paginator=Page();rows=paginator.paginate_queryset(qs,request)
        return paginator.get_paginated_response([dict(id=str(x.pk),reference=x.reference,vehicle=x.vehicle.plate,mileage=x.vehicle.mileage,status=x.status) for x in rows])


class NotificationsView(FieldView):
    def notifications(self):
        self.check();items=[];today=timezone.localdate()
        trips=self.trips();vehicles=m.Vehicle.objects.filter(organization=self.org)
        if self.member.role=='driver':vehicles=vehicles.filter(mission__in=trips.filter(status__in=['planned','active'])).distinct()
        def add(identity,version,title,body,severity='info'):
            key=hashlib.sha256(f'{identity}:{version}'.encode()).hexdigest()
            items.append(dict(key=key,title=title,body=body,severity=severity,identity=str(identity),version=str(version)))
        for x in trips.filter(status__in=['planned','active']).select_related('vehicle').order_by('departure'):
            add(x.pk,x.updated_at,f'Mission {x.reference}',f'{x.origin} → {x.destination} · {x.vehicle.plate} · {x.get_status_display()}')
        if self.enabled('maintenance'):
            for x in m.Maintenance.objects.filter(organization=self.org,vehicle__in=vehicles).exclude(status='cancelled').select_related('vehicle'):
                overdue=x.status not in ('completed',) and (x.due_date is not None and x.due_date<=today or x.due_mileage is not None and x.vehicle.mileage>=x.due_mileage)
                soon=x.due_date is not None and x.due_date<=today+timedelta(days=7) or x.due_mileage is not None and x.vehicle.mileage>=x.due_mileage-500
                add(x.pk,f'{x.updated_at}:{overdue}:{soon}',f'Entretien · {x.vehicle.plate}',f'{x.title} · {x.get_status_display()}'+(f' · échéance {x.due_date}' if x.due_date else '')+(f' · {x.due_mileage} km' if x.due_mileage is not None else ''),'urgent' if overdue else 'warning' if soon and x.status!='completed' else 'info')
        for x in vehicles:
            for field,label in [('insurance_expiry','Assurance'),('inspection_expiry','Visite technique')]:
                expiry=getattr(x,field)
                if expiry and expiry<=today+timedelta(days=30):add(f'{x.pk}:{field}',f'{expiry}:{expiry<today}',f'{label} · {x.plate}',f'Échéance : {expiry}','urgent' if expiry<today else 'warning')
        for x in self.reports().filter(kind__in=['incident','request','check']):
            linked=x.incident if x.incident_id else x.maintenance
            if linked:add(x.pk,linked.updated_at,x.title,linked.get_status_display(),'warning' if getattr(linked,'severity','')=='critical' and linked.status!='resolved' else 'info')
        read=set(m.NotificationRead.objects.filter(organization=self.org,user=self.request.user).values_list('key',flat=True))
        for item in items:item['read']=item['key'] in read
        items.sort(key=lambda x:(x['read'],{'urgent':0,'warning':1,'info':2}[x['severity']]))
        return items
    def get(self,request):
        items=self.notifications();paginator=Page();rows=paginator.paginate_queryset(items,request)
        response=paginator.get_paginated_response(rows);response.data['unread']=sum(not x['read'] for x in items)
        return response
    def post(self,request):
        key=serializers.CharField(max_length=64).run_validation(request.data.get('key'))
        if key not in {x['key'] for x in self.notifications()}:raise ValidationError('Notification inaccessible ou actualisée.')
        m.NotificationRead.objects.get_or_create(organization=self.org,user=request.user,key=key)
        from django.db import transaction
        from .realtime import publish
        transaction.on_commit(lambda:publish(self.org.pk,[request.user.pk],'notification'))
        return Response({'ok':True})

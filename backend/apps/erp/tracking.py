import math
import os
from datetime import timedelta
from uuid import UUID
from django.db import transaction
from django.db.models import OuterRef, Subquery, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from . import models as m, services
from .views import ScopedView

CONFIG=dict(sample_seconds=10, stationary_seconds=30, movement_metres=10, max_accuracy=1000, online_seconds=45, lost_seconds=180, max_future_seconds=120)
FIELDS=('timestamp','latitude','longitude','accuracy','speed','heading','client_id')


def authorized(view):
    if view.member.role not in ('owner','admin','operations','driver'):raise PermissionDenied('Suivi réservé à exploitation et au chauffeur assigné.')
    return view.queryset('missions')


def broadcast(mission,event="tracking"):
    from .realtime import publish
    users=list(m.Membership.objects.filter(organization_id=mission.organization_id,active=True,user__is_active=True,role__in=['owner','admin','operations']).values_list('user_id',flat=True))
    driver_user=m.Employee.objects.filter(pk=mission.driver_id,organization_id=mission.organization_id).values_list('user_id',flat=True).first()
    if driver_user:users.append(driver_user)
    transaction.on_commit(lambda:publish(mission.organization_id,set(users),event,mission=mission.pk))


def status(mission,last,now):
    if mission.status!='active':return 'ended'
    if mission.tracking_status in ('permission_required','unavailable'):return mission.tracking_status
    age=(now-(last or mission.started_at or now)).total_seconds()
    if age>=CONFIG['lost_seconds']:return 'lost'
    if not last:return 'waiting'
    return 'online' if age<=CONFIG['online_seconds'] else 'recent'


def inspect_signal(mission,last,now):
    state=status(mission,last,now)
    interrupted=state in ('lost','permission_required','unavailable')
    if interrupted and not mission.tracking_lost_at:
        mission.tracking_lost_at=now
        m.Mission.objects.filter(pk=mission.pk,organization_id=mission.organization_id).update(tracking_lost_at=now)
        from .notifications import notify
        title='Permission localisation requise' if state=='permission_required' else 'GPS indisponible' if state=='unavailable' else 'Signal GPS perdu'
        body=f'Le véhicule {mission.vehicle.plate} ne transmet plus de position exploitable. Mission {mission.reference}.'
        users=m.Membership.objects.filter(organization_id=mission.organization_id,active=True,role__in=['owner','admin','operations']).values_list('user_id',flat=True)
        for user in users:notify(mission.organization,user,f'gps:{mission.pk}:{now.isoformat()}','missions',title,body,{'module':'missions','id':str(mission.pk)})
        broadcast(mission)
    elif state=='online' and mission.tracking_lost_at:
        m.Mission.objects.filter(pk=mission.pk,organization_id=mission.organization_id).update(tracking_lost_at=None)
        mission.tracking_lost_at=None
        broadcast(mission)
    return state


def active_rows(qs):
    latest=m.Position.objects.filter(organization_id=OuterRef('organization_id'),mission_id=OuterRef('pk')).order_by('-timestamp')
    return qs.filter(status='active').annotate(**{'gps_'+field:Subquery(latest.values(field)[:1]) for field in FIELDS})


def check_signals(organization=None):
    now=timezone.now()
    orgs=m.Organization.objects.filter(pk=organization) if organization else m.Organization.objects.filter(mission__status='active').distinct()
    for org in orgs:
        with transaction.atomic():
            m.Organization.objects.select_for_update().get(pk=org.pk)
            for mission in active_rows(m.Mission.objects.filter(organization=org).select_related('vehicle','organization')):
                inspect_signal(mission,mission.gps_timestamp,now)


class TrackingView(ScopedView):
    def get(self,request,pk=None):
        qs=authorized(self)
        if pk:
            mission=get_object_or_404(qs,pk=pk)
            return Response({'started_at':mission.started_at,'completed_at':mission.completed_at,'state':status(mission,m.Position.objects.filter(organization=self.org,mission=mission).order_by('-timestamp').values_list('timestamp',flat=True).first(),timezone.now())})
        own=request.query_params.get('assigned')=='1'
        if own:qs=qs.filter(driver__user=request.user)
        if not own and self.member.role in ('owner','admin','operations'):check_signals(self.org.pk)
        now=timezone.now()
        rows=[]
        for mission in active_rows(qs):
            last={f:getattr(mission,'gps_'+f) for f in FIELDS} if mission.gps_timestamp else None
            rows.append(dict(id=str(mission.pk),reference=mission.reference,vehicle=mission.vehicle.name,plate=mission.vehicle.plate,driver=mission.driver.name,driver_user=mission.driver.user_id,origin=mission.origin,destination=mission.destination,started_at=mission.started_at,state=status(mission,mission.gps_timestamp,now),last=last))
        return Response({'missions':rows,'config':CONFIG,'server_time':now,'tiles':{'url':os.environ.get('TF_MAP_TILE_URL','https://tile.openstreetmap.org/{z}/{x}/{y}.png'),'attribution':os.environ.get('TF_MAP_TILE_ATTRIBUTION','© OpenStreetMap contributors'),'attribution_url':os.environ.get('TF_MAP_TILE_ATTRIBUTION_URL','https://www.openstreetmap.org/copyright')}})

    def post(self,request,pk):
        mission=get_object_or_404(authorized(self),pk=pk)
        if mission.driver.user_id!=request.user.pk:raise PermissionDenied('Seul le chauffeur assigné peut signaler la permission de son appareil.')
        if mission.status!='active':raise ValidationError('Mission inactive.')
        state=request.data.get('state')
        if state not in ('permission_required','unavailable','capturing'):raise ValidationError('État GPS invalide.')
        if mission.tracking_status==state:return Response({'state':state})
        mission.tracking_status=state;mission.save(update_fields=['tracking_status'])
        last=m.Position.objects.filter(organization=self.org,mission=mission).order_by('-timestamp').values_list('timestamp',flat=True).first()
        inspect_signal(mission,last,timezone.now());broadcast(mission)
        return Response({'state':status(mission,last,timezone.now())})


class PositionsView(ScopedView):
    def get(self,request,pk):
        mission=get_object_or_404(authorized(self),pk=pk)
        qs=m.Position.objects.filter(organization=self.org,mission=mission).order_by('timestamp')
        latest=qs.order_by('-timestamp').values_list('timestamp',flat=True).first()
        after=request.query_params.get('after')
        if after:qs=qs.filter(timestamp__gt=serializers.DateTimeField().run_validation(after))
        points=list(qs.values(*FIELDS)[:2001]);more=len(points)>2000;points=points[:2000]
        return Response({'positions':points,'next':points[-1]['timestamp'] if more else None,'state':status(mission,latest,timezone.now())})

    def post(self,request,pk):
        mission=get_object_or_404(authorized(self),pk=pk)
        points=request.data.get('positions')
        if not isinstance(points,list) or not 1<=len(points)<=200:raise ValidationError('Entre 1 et 200 positions requises.')
        now=timezone.now()
        if not mission.started_at or mission.status not in ('active','completed','cancelled') or mission.completed_at and now>mission.completed_at+timedelta(hours=24):raise ValidationError('Fenêtre de synchronisation fermée.')
        new=[]
        for point in points:
            if not isinstance(point,dict):raise ValidationError('Position invalide.')
            timestamp=serializers.DateTimeField().run_validation(point.get('timestamp'))
            lat=services.decimal(point.get('latitude'));lng=services.decimal(point.get('longitude'))
            end=mission.completed_at or now+timedelta(seconds=CONFIG["max_future_seconds"])
            if not -90<=lat<=90 or not -180<=lng<=180 or not mission.started_at<=timestamp<=end:raise ValidationError('Position hors limites du trajet.')
            values={}
            for field,maximum in [('accuracy',1000),('speed',150),('heading',360)]:
                value=point.get(field)
                if value is not None:
                    try:value=float(value)
                    except (ValueError,TypeError):raise ValidationError('Mesure GPS invalide.')
                    if not math.isfinite(value) or not 0<=value<=maximum:raise ValidationError('Mesure GPS hors limites.')
                values[field]=value
            client=point.get('client_id')
            try:client=UUID(str(client)) if client else None
            except ValueError:raise ValidationError('Identifiant du point invalide.')
            new.append(m.Position(organization=self.org,mission=mission,timestamp=timestamp,latitude=lat,longitude=lng,client_id=client,**values))
        existing=list(m.Position.objects.filter(organization=self.org,mission=mission).filter(Q(timestamp__in=[p.timestamp for p in new])|Q(client_id__in=[p.client_id for p in new if p.client_id])).values_list('timestamp','client_id'))
        timestamps={p[0] for p in existing};identities={p[1] for p in existing if p[1]};fresh=[]
        for point in new:
            if point.timestamp in timestamps or point.client_id and point.client_id in identities:continue
            fresh.append(point);timestamps.add(point.timestamp)
            if point.client_id:identities.add(point.client_id)
        m.Position.objects.bulk_create(fresh,ignore_conflicts=True)
        if fresh and mission.status=='active':
            if mission.tracking_status!='permission_required':
                mission.tracking_status='capturing'
                mission.save(update_fields=['tracking_status'])
            latest=m.Position.objects.filter(organization=self.org,mission=mission).order_by('-timestamp').values_list('timestamp',flat=True).first()
            inspect_signal(mission,latest,now)
        if fresh:broadcast(mission)
        return Response({'accepted':len(new),'created':len(fresh)})

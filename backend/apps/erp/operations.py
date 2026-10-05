from datetime import date,datetime,time,timedelta
from zoneinfo import ZoneInfo
from types import SimpleNamespace
from uuid import UUID
from django.db.models import Q, Count, Exists, OuterRef, Subquery, F, Value, Case, When, IntegerField, CharField, DateTimeField
from django.db.models.functions import Cast, TruncDate
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError, APIException
from rest_framework.response import Response
from . import models as m,services
from .views import ScopedView,Page
from .serializers import serializer_for
from .operations_rules import availability,late_query,RISK_HOURS,AVAILABILITY_MINUTES
from .tracking import status as gps_status,CONFIG


class Conflict(APIException):
    status_code=409
    default_detail='Cette affectation a changé. Actualisez la mission avant de réessayer.'


def scope(view):
    view.ensure('missions')
    if view.member.role not in ('owner','admin','operations'):raise PermissionDenied('Centre réservé à l’exploitation.')


def risk_rows(org,now):
    zone=ZoneInfo(org.timezone)
    latest=m.Position.objects.filter(organization=org,mission_id=OuterRef('pk')).order_by('-timestamp')
    leaves=m.LeaveRequest.objects.filter(organization=org,employee_id=OuterRef('driver_id'),status='approved',start_date__lte=OuterRef('arrival_day'),end_date__gte=OuterRef('departure_day'))
    maintenance=m.Maintenance.objects.filter(organization=org,vehicle_id=OuterRef('vehicle_id'),status='active')
    return m.Mission.objects.filter(organization=org).annotate(departure_day=TruncDate('departure',tzinfo=zone),arrival_day=TruncDate('arrival',tzinfo=zone)).annotate(
        gps_timestamp=Subquery(latest.values('timestamp')[:1]),on_leave=Exists(leaves),in_workshop=Exists(maintenance))


def resource_risk():
    return Q(driver__active=False)|~Q(vehicle__status='available')|Q(in_workshop=True)|Q(on_leave=True)|Q(driver__license_expiry__lt=F('departure_day'))


def lost_query(now):
    return Q(status='active')&(Q(gps_timestamp__lte=now-timedelta(seconds=CONFIG['lost_seconds']))|Q(gps_timestamp__isnull=True,started_at__lte=now-timedelta(seconds=CONFIG['lost_seconds'])))&~Q(tracking_status__in=['permission_required','unavailable'])


def problems_query(now):
    imminent=Q(status='active')|Q(status='planned',departure__lte=now+timedelta(hours=RISK_HOURS))
    return late_query(now)|lost_query(now)|Q(status='active',tracking_status__in=['permission_required','unavailable'])|(imminent&resource_risk())|Q(status='completed',delivered_quantity__lt=F('loaded_quantity'))|Q(status='completed')&~Q(delivery_note='')


def serialize_mission(row,now):
    return dict(id=str(row.pk),resource='missions',reference=row.reference,customer_id=str(row.order.customer_id) if row.order_id else None,customer=row.order.customer.name if row.order_id else None,order_id=str(row.order_id) if row.order_id else None,order_reference=row.order.reference if row.order_id else None,
        origin=row.origin,destination=row.destination,departure=row.departure,arrival=row.arrival,driver_id=str(row.driver_id),driver=row.driver.name,vehicle_id=str(row.vehicle_id),plate=row.vehicle.plate,vehicle=row.vehicle.name,status=row.status,updated_at=row.updated_at,
        gps=gps_status(row,row.gps_timestamp,now),last_position_at=row.gps_timestamp,late=row.status=='planned' and row.departure<now or row.status=='active' and row.arrival<now,
        resource_problem=row.status in ('planned','active') and (not row.driver.active or row.vehicle.status!='available' or row.in_workshop or row.on_leave or row.driver.license_expiry is not None and row.driver.license_expiry<row.departure_day),
        delivery_problem=row.status=='completed' and (row.delivered_quantity<row.loaded_quantity or bool(row.delivery_note)))


def unassigned(org,selected):
    trips=m.Mission.objects.filter(organization=org,order_id=OuterRef('pk')).exclude(status='cancelled')
    return m.TransportOrder.objects.filter(organization=org,status='confirmed',planned_date__lte=selected).annotate(has_mission=Exists(trips)).filter(has_mission=False)


def alert_rows(view,now,selected):
    missions=risk_rows(view.org,now).filter(problems_query(now)).filter(Q(status='active')|Q(status='planned',departure__lte=now+timedelta(hours=RISK_HOURS))|Q(status='completed',completed_at__gte=now-timedelta(days=1)))
    gps=lost_query(now)|Q(status='active',tracking_status__in=['permission_required','unavailable'])
    critical=gps|Q(status='active')&resource_risk()
    shape=['object_id','resource','label','kind','severity_rank','due_sort','created_at']
    def shape_rows(qs,resource,label,kind,severity,due):
        return qs.order_by().annotate(object_id=Cast('id',CharField()),resource=Value(resource),label=label,kind=kind,severity_rank=severity,due_sort=due).values(*shape)
    results=shape_rows(missions,'missions',F('reference'),Case(When(gps,then=Value('gps')),When(resource_risk(),then=Value('resource')),When(late_query(now),then=Value('late')),default=Value('delivery')),Case(When(critical,then=Value(0)),default=Value(1),output_field=IntegerField()),F('departure'))
    orders=unassigned(view.org,selected)
    results=results.union(shape_rows(orders,'orders',F('reference'),Value('unassigned'),Case(When(planned_date__lt=timezone.localtime(now,ZoneInfo(view.org.timezone)).date(),then=Value(0)),default=Value(1),output_field=IntegerField()),Cast('planned_date',DateTimeField())),all=True)
    if view.enabled('incidents'):
        incidents=m.Incident.objects.filter(organization=view.org,status='reported')
        results=results.union(shape_rows(incidents,'incidents',F('title'),Value('incident'),Case(When(severity='critical',then=Value(0)),default=Value(1),output_field=IntegerField()),F('occurred_at')),all=True)
    if view.enabled('maintenance'):
        workshop=m.Maintenance.objects.filter(organization=view.org,status='active')
        results=results.union(shape_rows(workshop,'maintenance',F('title'),Value('maintenance'),Value(2,output_field=IntegerField()),F('created_at')),all=True)
    return results.order_by('severity_rank','due_sort','-created_at','resource','object_id')


class OperationsCenterView(ScopedView):
    def get(self,request):
        scope(self)
        now=timezone.now();zone=ZoneInfo(self.org.timezone);today=timezone.localtime(now,zone).date()
        try:selected=date.fromisoformat(request.query_params.get('date',str(today)))
        except (TypeError,ValueError):raise ValidationError('Date d’exploitation invalide.')
        start=datetime.combine(selected,time.min,zone);end=datetime.combine(selected+timedelta(days=1),time.min,zone)
        current=selected==today
        missions=risk_rows(self.org,now)
        day=missions.filter(Q(departure__lt=end,arrival__gt=start)|Q(completed_at__gte=start,completed_at__lt=end)|(Q(status='active') if current else Q(pk__isnull=True)))
        pending=unassigned(self.org,selected)
        q=request.query_params.get('q','').strip()[:150]
        rows=day
        if q:rows=rows.filter(Q(reference__icontains=q)|Q(vehicle__plate__icontains=q)|Q(driver__name__icontains=q)|Q(order__customer__name__icontains=q)|Q(order__reference__icontains=q)|Q(origin__icontains=q)|Q(destination__icontains=q))
        mode=request.query_params.get('filter','all')
        filters={'all':Q(),'planned':Q(status='planned'),'upcoming':Q(status='planned',departure__gte=now),'active':Q(status='active'),'late':late_query(now),'completed':Q(status='completed'),'problems':problems_query(now)}
        if mode not in (*filters,'unassigned'):raise ValidationError('Filtre mission invalide.')
        pager=Page()
        if mode=='unassigned':
            rows=pending.select_related('customer')
            if q:rows=rows.filter(Q(reference__icontains=q)|Q(customer__name__icontains=q)|Q(origin__icontains=q)|Q(destination__icontains=q))
            page=pager.paginate_queryset(rows.order_by('planned_date','id'),request)
            output=[dict(id=str(x.pk),resource='orders',reference=x.reference,customer_id=str(x.customer_id),customer=x.customer.name,origin=x.origin,destination=x.destination,planned_date=x.planned_date,updated_at=x.updated_at,status=x.status) for x in page]
        else:
            page=pager.paginate_queryset(rows.filter(filters[mode]).select_related('order__customer','driver','vehicle').order_by('departure','id'),request)
            output=[serialize_mission(x,now) for x in page]
        summary=day.exclude(status='cancelled').aggregate(total=Count('id'),planned=Count('id',filter=Q(status='planned')),active=Count('id',filter=Q(status='active')),completed=Count('id',filter=Q(status='completed')),late=Count('id',filter=late_query(now)))
        vehicles,drivers,free_vehicles,free_drivers=availability(self.org,now,now+timedelta(minutes=AVAILABILITY_MINUTES))
        summary.update(unassigned=pending.count(),incidents=m.Incident.objects.filter(organization=self.org,status='reported').count() if self.enabled('incidents') else None,gps_lost=missions.filter(lost_query(now)).count() if current else None,available_vehicles=free_vehicles.count(),available_drivers=free_drivers.count())
        alerts=alert_rows(self,now,selected)
        alert_page=Page();alert_page.page_query_param='alert_page'
        alert_items=alert_page.paginate_queryset(alerts,request)
        for item in alert_items:item['object_id']=str(UUID(item['object_id']))
        labels={'gps':'Signal GPS interrompu','resource':'Ressource indisponible','late':'Horaire prévu dépassé','delivery':'Livraison à vérifier','unassigned':'Affectation requise','incident':'Incident ouvert','maintenance':'Intervention en cours'}
        alert_output=[dict(x,key=x['resource']+':'+x['object_id']+':'+x['kind'],title=labels[x['kind']],severity=['critical','attention','information'][x['severity_rank']]) for x in alert_items]
        resources={'mission':'missions','transportorder':'orders','employee':'employees','vehicle':'vehicles','incident':'incidents','maintenance':'maintenance','deliveryreceipt':'missions'}
        allowed=[name for name,key in resources.items() if self.enabled(key)]
        activity=m.AuditEvent.objects.filter(organization=self.org,resource__in=allowed).order_by('-created_at')[:15]
        action_labels={'create':'Création','update':'Modification','start':'Démarrage','complete':'Fin','confirm':'Confirmation','cancel':'Annulation','report':'Signalement','resolve':'Résolution','operations-assign':'Affectation','operations-reassign':'Réaffectation','receipt-sign':'Signature livraison'}
        return Response(dict(date=selected,today=today,timezone=self.org.timezone,server_time=now,current=current,kpi=summary,
            missions=dict(results=output,count=pager.page.paginator.count,page=pager.page.number,pages=pager.page.paginator.num_pages),
            alerts=dict(results=alert_output,count=alert_page.page.paginator.count,page=alert_page.page.number,pages=alert_page.page.paginator.num_pages),
            modules={key:self.enabled(key) for key in ('missions','orders','vehicles','employees','maintenance','incidents','partners')},
            activity=[dict(id=str(x.pk),resource=resources[x.resource],object_id=x.detail.get('mission') if x.resource=='deliveryreceipt' else x.object_id,label=action_labels.get(x.action,x.action),reference=x.detail.get('reference',''),created_at=x.created_at) for x in activity],risk_hours=RISK_HOURS,availability_minutes=AVAILABILITY_MINUTES))


class OperationsResourcesView(ScopedView):
    def get(self,request):
        scope(self)
        now=timezone.now()
        start=serializers.DateTimeField().run_validation(request.query_params['departure']) if request.query_params.get('departure') else now
        end=serializers.DateTimeField().run_validation(request.query_params['arrival']) if request.query_params.get('arrival') else start+timedelta(minutes=AVAILABILITY_MINUTES)
        if end<=start:raise ValidationError('L’arrivée doit suivre le départ.')
        exclude=None
        if request.query_params.get('mission'):
            target=get_object_or_404(self.queryset('missions'),pk=request.query_params['mission'])
            if target.status=='planned':exclude=target.pk
        vehicles,drivers,free_vehicles,free_drivers=availability(self.org,start,end,exclude)
        kind=request.query_params.get('kind','vehicles');only=request.query_params.get('available')=='1';q=request.query_params.get('q','')[:150]
        if kind=='vehicles':
            rows=free_vehicles if only else vehicles
            if q:rows=rows.filter(Q(plate__icontains=q)|Q(name__icontains=q))
            rows=rows.order_by('plate','id')
        elif kind=='drivers':
            rows=free_drivers if only else drivers
            if q:rows=rows.filter(name__icontains=q)
            rows=rows.order_by('name','id')
        else:raise ValidationError('Type de ressources invalide.')
        pager=Page();page=pager.paginate_queryset(rows,request)
        first=timezone.localtime(start,ZoneInfo(self.org.timezone)).date()
        output=[]
        for x in page:
            if kind=='vehicles':state='maintenance' if x.in_workshop or x.status=='maintenance' else 'unavailable' if x.status!='available' else 'in_mission' if x.current_mission else 'booked' if x.busy else 'available'
            else:state='unavailable' if not x.active else 'leave' if x.on_leave else 'license' if x.license_expiry and x.license_expiry<first else 'in_mission' if x.current_mission else 'booked' if x.busy else 'available'
            output.append(dict(id=str(x.pk),label=str(x),name=x.name,plate=x.plate if kind=='vehicles' else None,state=state,current_mission=str(x.current_mission) if x.current_mission else None,current_reference=x.current_reference,current_driver=x.current_driver if kind=='vehicles' else None,current_vehicle=x.current_vehicle if kind=='drivers' else None,next_mission=str(x.next_mission) if x.next_mission else None,next_reference=x.next_reference,next_departure=x.next_departure if kind=='drivers' else None,intervention=str(x.intervention_id) if kind=='vehicles' and x.intervention_id else None))
            if kind=='vehicles':
                output[-1].update(gps=gps_status(SimpleNamespace(status='active',tracking_status=x.current_tracking_status,started_at=x.current_started_at),x.last_position_at,now) if x.current_mission else 'ended',last_position_at=x.last_position_at)
        summary=rows.aggregate(total=Count('id'),in_mission=Count('id',filter=Q(current_mission__isnull=False)),available=Count('id',filter=Q(id__in=(free_vehicles if kind=='vehicles' else free_drivers).values('id'))))
        if kind=='vehicles':summary.update(rows.aggregate(maintenance=Count('id',filter=Q(in_workshop=True)|Q(status='maintenance')),unavailable=Count('id',filter=Q(status='retired'))))
        else:summary.update(rows.aggregate(leave=Count('id',filter=Q(on_leave=True)),license=Count('id',filter=Q(license_expiry__lt=first)),unavailable=Count('id',filter=Q(active=False))))
        response=pager.get_paginated_response(output);response.data['summary']=summary
        return response


class OperationsMissionView(ScopedView):
    def get(self,request,pk):
        scope(self)
        now=timezone.now()
        row=get_object_or_404(risk_rows(self.org,now).select_related('order__customer','driver','vehicle'),pk=pk)
        return Response(serialize_mission(row,now))


class AssignmentInput(serializers.Serializer):
    mission=serializers.UUIDField(required=False)
    order=serializers.UUIDField(required=False)
    expected_updated_at=serializers.DateTimeField()
    fields=serializers.DictField()


class OperationsAssignmentView(ScopedView):
    def post(self,request):
        scope(self);self.ensure('missions',True)
        data=AssignmentInput(data=request.data);data.is_valid(raise_exception=True);data=data.validated_data
        if ('mission' in data)==('order' in data):raise ValidationError('Choisissez une mission ou une commande à affecter.')
        current=None
        if 'mission' in data:
            current=get_object_or_404(self.queryset('missions').select_for_update(),pk=data['mission'])
            if current.updated_at!=data['expected_updated_at']:raise Conflict()
            if current.status!='planned':raise ValidationError('Seule une mission planifiée peut être réaffectée. Le GPS actif et les livraisons restent verrouillés.')
            fields=data['fields']
        else:
            self.ensure('orders',True)
            order=get_object_or_404(self.queryset('orders').select_for_update(),pk=data['order'])
            if order.updated_at!=data['expected_updated_at'] or order.status!='confirmed' or m.Mission.objects.filter(organization=self.org,order=order).exclude(status='cancelled').exists():raise Conflict()
            fields=dict(data['fields'],order=str(order.pk))
            fields.setdefault('origin',order.origin);fields.setdefault('destination',order.destination)
        permitted={'driver','vehicle','departure','arrival','origin','destination','loaded_quantity','notes','order','route'}
        if set(fields)-permitted:raise ValidationError('Champs d’affectation invalides.')
        if current and ('order' in fields and str(fields['order'])!=str(current.order_id) or 'route' in fields and str(fields['route'])!=str(current.route_id)):
            raise ValidationError('Le rattachement de la mission ne peut pas changer pendant une réaffectation.')
        serializer=serializer_for(m.Mission)(current,data=fields,partial=current is not None,context=self.context());serializer.is_valid(raise_exception=True)
        obj=serializer.save(organization=self.org,**({} if current else {'reference':services.sequence(self.org,'MIS')}))
        services.audit(self.org,request.user,'operations-reassign' if current else 'operations-assign',obj)
        return Response(serializer_for(m.Mission)(obj,context=self.context()).data,status=200 if current else 201)

from datetime import timedelta
from django.db.models import Q, Exists, OuterRef, Subquery
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from . import models as m
from .management import local_dates

RISK_HOURS=24
AVAILABILITY_MINUTES=60


def late_query(now):
    return Q(status='planned',departure__lt=now)|Q(status='active',arrival__lt=now)


def overlap_query(start,end):
    conflict=Q(status__in=['planned','active'],departure__lt=end,arrival__gt=start)
    if start<=timezone.now():conflict|=Q(status='active',departure__lt=end)
    return conflict


def availability(org,start,end,exclude=None):
    first,last=local_dates(org,start,end)
    bookings=m.Mission.objects.filter(organization=org).filter(overlap_query(start,end))
    if exclude:bookings=bookings.exclude(pk=exclude)
    current=m.Mission.objects.filter(organization=org,status='active')
    upcoming=m.Mission.objects.filter(organization=org,status='planned',departure__gte=start).order_by('departure','id')
    intervention=m.Maintenance.objects.filter(organization=org,status='active',vehicle_id=OuterRef('pk'))
    vehicles=m.Vehicle.objects.filter(organization=org).annotate(
        busy=Exists(bookings.filter(vehicle_id=OuterRef('pk'))),in_workshop=Exists(intervention),
        intervention_id=Subquery(intervention.values('id')[:1]),
        current_mission=Subquery(current.filter(vehicle_id=OuterRef('pk')).values('id')[:1]),
        current_reference=Subquery(current.filter(vehicle_id=OuterRef('pk')).values('reference')[:1]),
        current_driver=Subquery(current.filter(vehicle_id=OuterRef('pk')).values('driver__name')[:1]),
        current_tracking_status=Subquery(current.filter(vehicle_id=OuterRef('pk')).values('tracking_status')[:1]),
        current_started_at=Subquery(current.filter(vehicle_id=OuterRef('pk')).values('started_at')[:1]),
        next_mission=Subquery(upcoming.filter(vehicle_id=OuterRef('pk')).values('id')[:1]),
        next_reference=Subquery(upcoming.filter(vehicle_id=OuterRef('pk')).values('reference')[:1]))
    leaves=m.LeaveRequest.objects.filter(organization=org,employee_id=OuterRef('pk'),status='approved',start_date__lte=last,end_date__gte=first)
    drivers=m.Employee.objects.filter(organization=org,job='driver').annotate(
        busy=Exists(bookings.filter(driver_id=OuterRef('pk'))),on_leave=Exists(leaves),
        current_mission=Subquery(current.filter(driver_id=OuterRef('pk')).values('id')[:1]),
        current_reference=Subquery(current.filter(driver_id=OuterRef('pk')).values('reference')[:1]),
        current_vehicle=Subquery(current.filter(driver_id=OuterRef('pk')).values('vehicle__plate')[:1]),
        next_mission=Subquery(upcoming.filter(driver_id=OuterRef('pk')).values('id')[:1]),
        next_reference=Subquery(upcoming.filter(driver_id=OuterRef('pk')).values('reference')[:1]),
        next_departure=Subquery(upcoming.filter(driver_id=OuterRef('pk')).values('departure')[:1]))
    last=m.Position.objects.filter(organization=org,mission_id=OuterRef('current_mission')).order_by('-timestamp')
    vehicles=vehicles.annotate(last_position_at=Subquery(last.values('timestamp')[:1]))
    available_vehicles=vehicles.filter(status='available',busy=False,in_workshop=False)
    available_drivers=drivers.filter(active=True,busy=False,on_leave=False).filter(Q(license_expiry__isnull=True)|Q(license_expiry__gte=first))
    return vehicles,drivers,available_vehicles,available_drivers


def validate_assignment(org,candidate,current=None):
    if not candidate.driver.active:raise ValidationError('Ce chauffeur a quitté l’entreprise.')
    if candidate.driver.job!='driver':raise ValidationError('Sélectionnez un chauffeur.')
    if candidate.vehicle.status!='available' or m.Maintenance.objects.filter(organization=org,vehicle=candidate.vehicle,status='active').exists():
        raise ValidationError('Ce véhicule est indisponible ou en maintenance.')
    first,_=local_dates(org,candidate.departure,candidate.arrival)
    if candidate.driver.license_expiry and candidate.driver.license_expiry<first:
        raise ValidationError('Le permis du chauffeur sera expiré au départ.')
    conflicts=m.Mission.objects.filter(organization=org).filter(overlap_query(candidate.departure,candidate.arrival)).filter(Q(vehicle=candidate.vehicle)|Q(driver=candidate.driver))
    if current:conflicts=conflicts.exclude(pk=current.pk)
    conflict=conflicts.select_related('driver','vehicle').order_by('departure').first()
    if conflict:
        resource=conflict.vehicle.plate if conflict.vehicle_id==candidate.vehicle_id else conflict.driver.name
        raise ValidationError(f'Chevauchement : {resource} est déjà affecté à {conflict.reference} sur cette période ou a une mission encore active.')

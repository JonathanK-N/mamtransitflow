from datetime import timedelta
import pytest
from django.utils import timezone
from apps.erp import models as m
from .test_workflows import env,mission,create,act

pytestmark=pytest.mark.django_db


def test_center_and_resources_smoke(env):
    trip=mission(env)
    response=env['client'].get('/api/v2/operations/center')
    assert response.status_code==200,response.data
    assert response.data['kpi']['planned']==1
    assert response.data['missions']['results'][0]['id']==trip['id']
    for kind in ('vehicles','drivers'):
        response=env['client'].get('/api/v2/operations/resources',{'kind':kind})
        assert response.status_code==200,response.data
        assert response.data['count']==1


def test_assignment_order_and_stale_revision(env):
    order=create(env,'orders',dict(customer=str(env['partner'].pk),origin='A',destination='B',planned_date=str(timezone.localdate())))
    order=act(env,'orders',order['id'],'confirm')
    row=m.TransportOrder.objects.get(pk=order['id'])
    now=timezone.now()+timedelta(hours=1)
    body=dict(order=str(row.pk),expected_updated_at=row.updated_at.isoformat(),fields=dict(driver=str(env['driver'].pk),vehicle=str(env['vehicle'].pk),departure=now.isoformat(),arrival=(now+timedelta(hours=2)).isoformat()))
    result=env['client'].post('/api/v2/operations/assign',body,format='json')
    assert result.status_code==201,result.data
    assert env['client'].post('/api/v2/operations/assign',body,format='json').status_code==409
    assert m.Mission.objects.filter(order=row).count()==1
    assert env['client'].get('/api/v2/operations/center',{'filter':'unassigned'}).data['missions']['count']==0


def test_alerts_union_and_gps_loss(env):
    trip=mission(env)
    m.Mission.objects.filter(pk=trip['id']).update(status='active',started_at=timezone.now()-timedelta(minutes=5))
    order=create(env,'orders',dict(customer=str(env['partner'].pk),origin='A',destination='B',planned_date=str(timezone.localdate())))
    act(env,'orders',order['id'],'confirm')
    m.Incident.objects.create(organization=env['org'],vehicle=env['vehicle'],title='TEST incident',severity='critical',status='reported',occurred_at=timezone.now())
    response=env['client'].get('/api/v2/operations/center')
    assert response.status_code==200,response.data
    assert response.data['kpi']['gps_lost']==1
    assert {x['kind'] for x in response.data['alerts']['results']}=={'gps','unassigned','incident'}


@pytest.mark.parametrize('role',['driver','client','finance','workshop','viewer'])
def test_center_roles_denied(env,role):
    env['member'].role=role;env['member'].save()
    for path in ('center','resources','missions/'+str(env['vehicle'].pk)):
        assert env['client'].get('/api/v2/operations/'+path).status_code==403


def test_foreign_resources_and_mission_denied(env):
    foreign=m.Vehicle.objects.create(organization=env['other'],plate='SECRET')
    assert env['client'].get('/api/v2/operations/resources',{'q':'SECRET'}).data['count']==0
    assert env['client'].get('/api/v2/operations/missions/'+str(foreign.pk)).status_code==404


def test_availability_respects_overlap_leave_license_maintenance_and_tenant(env):
    from zoneinfo import ZoneInfo
    now=timezone.now();end=now+timedelta(hours=2)
    today=timezone.localtime(now,ZoneInfo(env['org'].timezone)).date()
    blocked=m.Vehicle.objects.create(organization=env['org'],plate='WORKSHOP')
    m.Maintenance.objects.create(organization=env['org'],vehicle=blocked,title='TEST',status='active')
    expired=m.Employee.objects.create(organization=env['org'],name='Expired',license_expiry=today-timedelta(days=1))
    leave=m.Employee.objects.create(organization=env['org'],name='Leave')
    m.LeaveRequest.objects.create(organization=env['org'],employee=leave,start_date=today,end_date=today,status='approved')
    trip=mission(env)
    params={'available':'1','departure':now.isoformat(),'arrival':end.isoformat()}
    for kind in ('vehicles','drivers'):
        response=env['client'].get('/api/v2/operations/resources',dict(params,kind=kind))
        assert response.status_code==200,response.data
        assert response.data['count']==0
        response=env['client'].get('/api/v2/operations/resources',dict(params,kind=kind,mission=trip['id']))
        assert response.data['count']==1
    m.Mission.objects.filter(pk=trip['id']).update(status='active',departure=now-timedelta(hours=2),arrival=now-timedelta(hours=1))
    assert env['client'].get('/api/v2/operations/resources',dict(params,kind='vehicles')).data['count']==0


def test_reassignment_revision_and_active_lock(env):
    trip=mission(env)
    vehicle=m.Vehicle.objects.create(organization=env['org'],plate='REPLACE')
    body=dict(mission=trip['id'],expected_updated_at=trip['updated_at'],fields=dict(vehicle=str(vehicle.pk)))
    response=env['client'].post('/api/v2/operations/assign',body,format='json')
    assert response.status_code==200,response.data
    assert str(response.data['vehicle'])==str(vehicle.pk)
    assert env['client'].post('/api/v2/operations/assign',body,format='json').status_code==409
    act(env,'missions',trip['id'],'start')
    row=m.Mission.objects.get(pk=trip['id']);body['expected_updated_at']=row.updated_at.isoformat()
    assert env['client'].post('/api/v2/operations/assign',body,format='json').status_code==400
    assert m.Mission.objects.get(pk=trip['id']).vehicle_id==vehicle.pk


def test_org_date_and_historical_view(env):
    from unittest.mock import patch
    from datetime import datetime,timezone as utc
    env['org'].timezone='America/Toronto';env['org'].save()
    instant=datetime(2026,10,5,1,0,tzinfo=utc.utc)
    m.Mission.objects.create(organization=env['org'],reference='LOCAL-DAY',driver=env['driver'],vehicle=env['vehicle'],origin='A',destination='B',departure=instant,arrival=instant+timedelta(hours=1))
    with patch('apps.erp.operations.timezone.now',return_value=instant):
        response=env['client'].get('/api/v2/operations/center')
        assert str(response.data['date'])=='2026-10-04'
        assert response.data['kpi']['total']==1
        historical=env['client'].get('/api/v2/operations/center',{'date':'2026-10-03'})
        assert historical.data['current'] is False
        assert historical.data['kpi']['gps_lost'] is None
    assert env['client'].get('/api/v2/operations/center',{'date':'invalid'}).status_code==400


def test_volume_query_count_and_pagination(env,record_property):
    import time
    from datetime import datetime,time as clock
    from zoneinfo import ZoneInfo
    from unittest.mock import patch
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    vehicles=m.Vehicle.objects.bulk_create([m.Vehicle(organization=env['org'],plate=f'VOLUME-{n:03}') for n in range(100)])
    drivers=m.Employee.objects.bulk_create([m.Employee(organization=env['org'],name=f'Driver {n:03}') for n in range(100)])
    zone=ZoneInfo(env['org'].timezone)
    now=datetime.combine(timezone.localtime(timezone.now(),zone).date(),clock(12),zone)
    trips=m.Mission.objects.bulk_create([m.Mission(organization=env['org'],reference=f'VOLUME-{n:03}-{j}',driver=drivers[n],vehicle=vehicles[n],origin='A',destination='B',status='active' if j==0 else 'planned',started_at=now-timedelta(minutes=10) if j==0 else None,departure=now+timedelta(hours=j*3),arrival=now+timedelta(hours=j*3+1)) for n in range(100) for j in range(2)])
    m.Position.objects.bulk_create([m.Position(organization=env['org'],mission=row,timestamp=now,latitude='9.537',longitude='-13.678') for row in trips if row.status=='active' and int(row.reference.split('-')[1])<50])
    started=time.perf_counter()
    with patch('apps.erp.operations.timezone.now',return_value=now),CaptureQueriesContext(connection) as queries:
        response=env['client'].get('/api/v2/operations/center',{'page_size':25})
    elapsed=(time.perf_counter()-started)*1000
    assert len(queries)<=20
    record_property('volume','100 vehicles / 100 drivers / 200 missions / 50 positions')
    record_property('center_sql_queries',len(queries));record_property('center_ms',round(elapsed,1))
    assert response.status_code==200,response.data
    assert response.data['missions']['count']==200
    assert len(response.data['missions']['results'])==25
    assert response.data['alerts']['count']==50
    with patch('apps.erp.operations.timezone.now',return_value=now),CaptureQueriesContext(connection) as queries:
        response=env['client'].get('/api/v2/operations/resources',{'kind':'drivers','page_size':25})
    assert len(queries)<=10
    record_property('drivers_sql_queries',len(queries))
    assert response.data['count']==101


def test_operations_contact_reuses_direct_and_cannot_remove(env):
    from apps.comptes.models import Utilisateur
    user=Utilisateur.objects.create_user(courriel='driver-center@example.test',mot_de_passe='Driver-test-938!',nom='Driver')
    m.Membership.objects.create(organization=env['org'],user=user,role='driver')
    env['driver'].user=user;env['driver'].save()
    env['member'].role='operations';env['member'].save()
    url='/api/v2/employees/'+str(env['driver'].pk)
    first=env['client'].post(url+'/contact',{},format='json');second=env['client'].post(url+'/contact',{},format='json')
    assert first.status_code==201,first.data
    assert second.status_code==200 and second.data['id']==first.data['id']
    assert env['client'].post(url+'/remove',{},format='json').status_code==403


@pytest.mark.parametrize('role',['owner','admin','operations'])
def test_operational_roles_can_read_center(env,role):
    env['member'].role=role;env['member'].save()
    assert env['client'].get('/api/v2/operations/center').status_code==200


def test_assignment_foreign_order_and_driver_refused(env):
    foreign_customer=m.Partner.objects.create(organization=env['other'],name='SECRET')
    foreign_order=m.TransportOrder.objects.create(organization=env['other'],customer=foreign_customer,reference='SECRET',origin='A',destination='B',planned_date=timezone.localdate(),status='confirmed')
    foreign_driver=m.Employee.objects.create(organization=env['other'],name='SECRET')
    now=timezone.now()+timedelta(hours=1)
    fields=dict(driver=str(env['driver'].pk),vehicle=str(env['vehicle'].pk),departure=now.isoformat(),arrival=(now+timedelta(hours=1)).isoformat())
    response=env['client'].post('/api/v2/operations/assign',dict(order=str(foreign_order.pk),expected_updated_at=foreign_order.updated_at.isoformat(),fields=fields),format='json')
    assert response.status_code==404
    order=m.TransportOrder.objects.create(organization=env['org'],customer=env['partner'],reference='LOCAL',origin='A',destination='B',planned_date=timezone.localdate(),status='confirmed')
    fields['driver']=str(foreign_driver.pk)
    assert env['client'].post('/api/v2/operations/assign',dict(order=str(order.pk),expected_updated_at=order.updated_at.isoformat(),fields=fields),format='json').status_code==400
    assert not m.Mission.objects.exists()


def test_late_risk_and_alert_reads_do_not_notify_again(env):
    from unittest.mock import patch
    from uuid import UUID
    now=timezone.now()
    trip=mission(env)
    m.Mission.objects.filter(pk=trip['id']).update(departure=now-timedelta(minutes=5),arrival=now+timedelta(hours=1))
    env['driver'].license_expiry=now.date()-timedelta(days=1);env['driver'].save()
    count=m.GlobalNotification.objects.count()
    with patch('apps.erp.operations.timezone.now',return_value=now):
        first=env['client'].get('/api/v2/operations/center',{'filter':'problems'}).data
        second=env['client'].get('/api/v2/operations/center').data
    assert first['kpi']['late']==1
    assert first['missions']['count']==1
    assert first['missions']['results'][0]['resource_problem'] is True
    assert len(first['alerts']['results'])==1
    assert first['alerts']['results'][0]['kind']=='resource'
    assert first['alerts']['results'][0]['key']==second['alerts']['results'][0]['key']
    assert str(UUID(first['alerts']['results'][0]['object_id']))==trip['id']
    assert m.GlobalNotification.objects.count()==count


def test_gps_boundary_matches_tracking_state(env):
    from unittest.mock import patch
    now=timezone.now();trip=mission(env)
    m.Mission.objects.filter(pk=trip['id']).update(status='active',started_at=now-timedelta(minutes=10))
    m.Position.objects.create(organization=env['org'],mission_id=trip['id'],timestamp=now-timedelta(seconds=180),latitude=9,longitude=1)
    with patch('apps.erp.operations.timezone.now',return_value=now):
        data=env['client'].get('/api/v2/operations/center').data
    assert data['kpi']['gps_lost']==1
    assert data['missions']['results'][0]['gps']=='lost'
    assert data['alerts']['results'][0]['severity']=='critical'

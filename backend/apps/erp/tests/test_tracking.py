from datetime import timedelta
from uuid import uuid4
import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from apps.comptes.models import Utilisateur
from apps.erp import models as m, services
from apps.erp.tracking import check_signals
from .test_workflows import env, mission, act

pytestmark=pytest.mark.django_db

@pytest.fixture
def gps_env(env):
    user=Utilisateur.objects.create_user(courriel='driver-gps@example.test',mot_de_passe='Gps-password-938!',nom='Chauffeur GPS')
    m.Membership.objects.create(organization=env['org'],user=user,role='driver')
    env['driver'].user=user;env['driver'].save()
    trip=mission(env);act(env,'missions',trip['id'],'start')
    row=m.Mission.objects.get(pk=trip['id']);row.started_at=timezone.now()-timedelta(minutes=10);row.save(update_fields=['started_at'])
    client=APIClient();client.force_authenticate(user);client.credentials(HTTP_X_ORGANIZATION=str(env['org'].pk))
    return dict(**env,trip=row,driver_client=client)

def point(**extra):return dict(timestamp=timezone.now().isoformat(),latitude=45.4042,longitude=-71.8929,accuracy=12,speed=17.5,heading=90,client_id=str(uuid4()),**extra)
def post(e,points,client=None):return (client or e['driver_client']).post(f"/api/v2/missions/{e['trip'].pk}/positions",{'positions':points},format='json')

def test_idempotent_batch_and_optional_measurements(gps_env):
    e=gps_env;p=point();assert post(e,[p]).status_code==200;assert post(e,[p]).status_code==200
    assert m.Position.objects.count()==1
    result=e['driver_client'].get(f"/api/v2/missions/{e['trip'].pk}/positions").data['positions'][0]
    assert result['accuracy']==12 and result['speed']==17.5 and result['heading']==90
    p2={**p,'timestamp':(timezone.now()+timedelta(seconds=1)).isoformat()};assert post(e,[p2]).status_code==200;assert m.Position.objects.count()==1

@pytest.mark.parametrize('field,value',[('latitude',91),('longitude',181),('accuracy',1001),('accuracy',-1),('speed',151),('speed',-1),('heading',361),('heading',-1),('client_id','wrong')])
def test_invalid_points_rollback_whole_batch(gps_env,field,value):
    bad=point();bad[field]=value;assert post(gps_env,[point(),bad]).status_code==400;assert not m.Position.objects.exists()

@pytest.mark.parametrize('state',['permission_required','unavailable'])
def test_permission_loss_retains_last_point_and_deduplicates_alerts(gps_env,state):
    e=gps_env;assert post(e,[point()]).status_code==200
    url=f"/api/v2/missions/{e['trip'].pk}/tracking"
    assert e['driver_client'].post(url,{'state':state},format='json').status_code==200
    count=m.GlobalNotification.objects.filter(key__startswith='gps:').count();assert count==1
    assert e['driver_client'].post(url,{'state':state},format='json').status_code==200
    check_signals(e['org'].pk);assert m.GlobalNotification.objects.filter(key__startswith='gps:').count()==count
    assert m.Position.objects.count()==1
    assert e['client'].get('/api/v2/tracking').data['missions'][0]['state']==state
    assert post(e,[point()]).status_code==200
    assert e['client'].get('/api/v2/tracking').data['missions'][0]['state']=='online'


def test_offline_old_upload_is_not_online_then_restores(gps_env):
    e=gps_env;p=point();p['timestamp']=(timezone.now()-timedelta(minutes=4)).isoformat()
    assert post(e,[p]).status_code==200
    assert e['client'].get('/api/v2/tracking').data['missions'][0]['state']=='lost'
    check_signals(e['org'].pk);check_signals(e['org'].pk)
    assert m.GlobalNotification.objects.filter(key__startswith='gps:').count()==1
    assert post(e,[point()]).status_code==200
    assert e['client'].get('/api/v2/tracking').data['missions'][0]['state']=='online'
    e['trip'].refresh_from_db();assert e['trip'].tracking_lost_at is None

@pytest.mark.parametrize('action',['complete','cancel'])
def test_lifecycle_ends_tracking_and_rejects_later_points(gps_env,action):
    e=gps_env;p=point();assert post(e,[p]).status_code==200
    act(e,'missions',str(e['trip'].pk),action)
    e['trip'].refresh_from_db();assert e['trip'].tracking_status=='ended' and e['trip'].tracking_ended_at
    assert post(e,[point()]).status_code==400
    assert post(e,[p]).status_code==200
    assert not e['driver_client'].get('/api/v2/tracking').data['missions']
    assert e['driver_client'].get(f"/api/v2/missions/{e['trip'].pk}/positions").data['positions']


def test_outside_active_window_and_fake_stop_rejected(gps_env):
    e=gps_env;p=point();p['timestamp']=(e['trip'].started_at-timedelta(seconds=1)).isoformat()
    assert post(e,[p]).status_code==400
    for state in ['paused','ended','stopped']:
        assert e['driver_client'].post(f"/api/v2/missions/{e['trip'].pk}/tracking",{'state':state},format='json').status_code==400
    assert e['driver_client'].post(f"/api/v2/missions/{e['trip'].pk}/actions/cancel",{},format='json').status_code==403


def test_cross_tenant_history_state_and_positions(gps_env):
    e=gps_env;other=m.Mission.objects.create(organization=e['other'],reference='FOREIGN',vehicle=m.Vehicle.objects.create(organization=e['other'],plate='FOREIGN'),driver=m.Employee.objects.create(organization=e['other'],name='Foreign'),origin='A',destination='B',departure=timezone.now(),arrival=timezone.now()+timedelta(hours=1))
    for suffix in ['positions','tracking']:
        url=f'/api/v2/missions/{other.pk}/{suffix}'
        assert e['driver_client'].get(url).status_code==404
        assert e['driver_client'].post(url,{'positions':[point()],'state':'capturing'},format='json').status_code==404

@pytest.mark.parametrize('role',['viewer','finance','workshop','client'])
def test_fleet_and_history_roles(gps_env,role):
    e=gps_env;e['member'].role=role;e['member'].save()
    assert e['client'].get('/api/v2/tracking').status_code==403
    assert e['client'].get(f"/api/v2/missions/{e['trip'].pk}/positions").status_code==403


def test_many_active_vehicles_use_bounded_queries(gps_env,django_assert_max_num_queries):
    e=gps_env
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    with CaptureQueriesContext(connection) as baseline:e['client'].get('/api/v2/tracking')
    for i in range(12):
        driver=m.Employee.objects.create(organization=e['org'],name=f'Driver {i}')
        vehicle=m.Vehicle.objects.create(organization=e['org'],plate=f'TEST-{i}')
        m.Mission.objects.create(organization=e['org'],reference=f'FLEET-{i}',vehicle=vehicle,driver=driver,origin='A',destination='B',status='active',started_at=timezone.now(),departure=timezone.now(),arrival=timezone.now()+timedelta(hours=1))
    with django_assert_max_num_queries(len(baseline)):
        result=e['client'].get('/api/v2/tracking');assert result.status_code==200;assert len(result.data['missions'])==13
    assert len(e['driver_client'].get('/api/v2/tracking').data['missions'])==1


def test_history_pagination_does_not_truncate(gps_env):
    e=gps_env;start=e['trip'].started_at
    m.Position.objects.bulk_create([m.Position(organization=e['org'],mission=e['trip'],timestamp=start+timedelta(milliseconds=i),latitude=45,longitude=-71) for i in range(2002)])
    response=e['driver_client'].get(f"/api/v2/missions/{e['trip'].pk}/positions").data
    assert len(response['positions'])==2000 and response['next']
    response=e['driver_client'].get(f"/api/v2/missions/{e['trip'].pk}/positions",{'after':response['next'].isoformat()}).data
    assert len(response['positions'])==2 and not response['next']

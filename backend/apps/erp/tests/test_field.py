"""Recette terrain. Auteur : Jonathan Kakesa (JonathanK-N)."""
import pytest
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.erp import models as m
from apps.erp.field import CHECKS
from .test_workflows import env,mission,act

pytestmark=pytest.mark.django_db

def driver(env):
    trip=mission(env)
    env['driver'].user=env['user'];env['driver'].save()
    env['member'].role='driver';env['member'].save()
    return trip

def report(env,trip,kind='incident',**extra):
    return env['client'].post('/api/v2/field/reports',dict(mission=trip['id'],kind=kind,title='Contrôle terrain',description='Fuite constatée',**extra),format='json')

def test_driver_incident_and_workshop_resolution_are_linked(env):
    trip=driver(env);response=report(env,trip,severity='critical')
    assert response.status_code==201,response.data
    row=m.FieldReport.objects.get(pk=response.data['id'])
    assert row.incident.status=='reported' and row.incident.vehicle==env['vehicle']
    assert env['client'].get('/api/v2/incidents').status_code==403
    env['member'].role='workshop';env['member'].save()
    act(env,'incidents',row.incident_id,'resolve',{'resolution':'Durite remplacée'})
    env['member'].role='driver';env['member'].save()
    data=env['client'].get('/api/v2/field/reports').data['results'][0]
    assert data['status']=='resolved' and data['response']=='Durite remplacée'

def test_foreign_or_unassigned_mission_is_not_available(env):
    trip=mission(env);env['member'].role='driver';env['member'].save()
    assert report(env,trip).status_code==404
    assert env['client'].get('/api/v2/field/context').data['count']==0
    env['client'].credentials(HTTP_X_ORGANIZATION=str(env['other'].pk))
    assert env['client'].get('/api/v2/field/reports').status_code==403

def test_inspection_blocks_start_until_new_conforming_check(env):
    trip=driver(env);checks=dict.fromkeys(CHECKS,True);checks['brakes']=False
    response=report(env,trip,'check',checks=checks,mileage=300)
    assert response.status_code==201,response.data
    assert m.Maintenance.objects.count()==1
    act(env,'missions',trip['id'],'start',expected=400)
    checks['brakes']=True
    assert report(env,trip,'check',checks=checks,mileage=300).status_code==201
    act(env,'missions',trip['id'],'start')
    assert report(env,trip,'check',checks=checks,mileage=300).status_code==400

@pytest.mark.parametrize('extra',[{'mileage':-1},{'mileage':'bad'},{'mileage':True},{'checks':{'brakes':True}}])
def test_invalid_field_reports_are_rejected(env,extra):
    trip=driver(env)
    assert report(env,trip,'check',**extra).status_code==400
    assert not m.FieldReport.objects.exists()

def test_mileage_monotonic_and_notification_read_changes_with_state(env):
    trip=driver(env)
    maintenance=m.Maintenance.objects.create(organization=env['org'],vehicle=env['vehicle'],title='Vidange',due_mileage=1000)
    assert report(env,trip,'mileage',mileage=1000).status_code==201
    assert report(env,trip,'mileage',mileage=999).status_code==400
    env['vehicle'].refresh_from_db();assert env['vehicle'].mileage==1000
    alerts=env['client'].get('/api/v2/field/notifications').data
    item=next(x for x in alerts['results'] if 'Vidange' in x['body']);assert item['severity']=='urgent'
    assert env['client'].post('/api/v2/field/notifications',{'key':item['key']},format='json').status_code==200
    assert next(x for x in env['client'].get('/api/v2/field/notifications').data['results'] if x['key']==item['key'])['read']
    maintenance.status='completed';maintenance.save()
    changed=next(x for x in env['client'].get('/api/v2/field/notifications').data['results'] if 'Vidange' in x['body'])
    assert not changed['read'] and changed['key']!=item['key'] and changed['severity']=='info'

@pytest.mark.django_db(transaction=True)
def test_private_attachment_access_and_mime_validation(env,settings,tmp_path):
    settings.MEDIA_ROOT=tmp_path;trip=driver(env);row=report(env,trip).data
    path='/api/v2/field/reports/'+row['id']+'/attachments'
    assert env['client'].post(path,{'title':'Photo','file':SimpleUploadedFile('bad.png',b'<script>bad</script>')},format='multipart').status_code==400
    response=env['client'].post(path,{'title':'Bon','file':SimpleUploadedFile('bon.pdf',b'%PDF-1.4\nrecette')},format='multipart')
    assert response.status_code==201
    url='/api/v2/field/attachments/'+response.data['id']
    download=env['client'].get(url);assert download.status_code==200;download.close()
    env['driver'].user=None;env['driver'].save()
    assert env['client'].get(url).status_code==404

def test_request_creates_planned_maintenance_and_disabled_module_denies(env):
    trip=driver(env)
    assert report(env,trip,'request').status_code==201
    assert m.FieldReport.objects.get().maintenance.status=='planned'
    env['member'].role='owner';env['member'].save()
    assert env['client'].post('/api/v2/applications',{'key':'workshop','enabled':False},format='json').status_code==200
    env['member'].role='driver';env['member'].save()
    assert report(env,trip,'request').status_code==403

def test_viewer_cannot_access_field_data(env):
    env['member'].role='viewer';env['member'].save()
    for path in ('reports','context','notifications'):
        assert env['client'].get('/api/v2/field/'+path).status_code==403

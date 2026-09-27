"""Recette des applications par entreprise. Auteur : Jonathan Kakesa (JonathanK-N)."""
import pytest
from apps.erp import models as m
from .test_workflows import env

pytestmark=pytest.mark.django_db


def custom(env,**extra):
    payload=dict(name='Contrôles de chargement',fields=[{'key':'title','label':'Référence','type':'text','required':True},
        {'key':'weight','label':'Poids','type':'number','required':False}],read_roles=['operations','viewer'],write_roles=['operations'])
    payload.update(extra)
    response=env['client'].post('/api/v2/applications/custom',payload,format='json')
    assert response.status_code==201,response.data
    return response.data


def test_disable_is_tenant_scoped_and_api_enforced(env):
    response=env['client'].post('/api/v2/applications',{'key':'inventory','enabled':False},format='json')
    assert response.status_code==200,response.data
    assert env['client'].get('/api/v2/stock').status_code==403
    assert 'stock' not in [x['key'] for x in env['client'].get('/api/v2/catalog').data['resources']]
    assert env['client'].get('/api/v2/dashboard').status_code==200
    m.Membership.objects.create(organization=env['other'],user=env['user'],role='owner')
    env['client'].credentials(HTTP_X_ORGANIZATION=str(env['other'].pk))
    assert env['client'].get('/api/v2/stock').status_code==200


def test_dependencies_prevent_breakage_and_reinstall_automatically(env):
    client=env['client']
    assert client.post('/api/v2/applications',{'key':'fleet','enabled':False},format='json').status_code==400
    for key in ('passengers','commercial','subcontracting','incidents','dispatch','workshop','fleet'):
        assert client.post('/api/v2/applications',{'key':key,'enabled':False},format='json').status_code==200
    assert client.get('/api/v2/vehicles').status_code==403
    assert client.post('/api/v2/applications',{'key':'passengers','enabled':True},format='json').status_code==200
    assert client.get('/api/v2/vehicles').status_code==200
    assert m.Vehicle.objects.filter(organization=env['org']).count()==1


def test_payment_connectors_stay_pending(env):
    response=env['client'].post('/api/v2/applications',{'key':'payment-connectors','enabled':True},format='json')
    entry=next(a for a in response.data['applications'] if a['key']=='payment-connectors')
    assert entry['installed'] and entry['status']=='pending'
    assert env['client'].post('/api/v2/payment-connectors/transfer',{'amount':100},format='json').status_code==404


def test_custom_record_isolation_and_revision_conflict(env):
    app=custom(env);url=f"/api/v2/applications/custom/{app['id']}/records"
    response=env['client'].post(url,{'data':{'title':'BL-001','weight':'125.50'}},format='json')
    assert response.status_code==201,response.data
    row=response.data;detail=url+'/'+row['id']
    payload={'revision':1,'data':{'title':'BL-002','weight':'130'}}
    assert env['client'].patch(detail,payload,format='json').status_code==200
    assert env['client'].patch(detail,payload,format='json').status_code==409
    m.Membership.objects.create(organization=env['other'],user=env['user'],role='owner')
    env['client'].credentials(HTTP_X_ORGANIZATION=str(env['other'].pk))
    assert env['client'].get(url).status_code==404
    assert env['client'].get(detail).status_code==404
    assert env['client'].patch(detail,payload,format='json').status_code==404


def test_schema_and_permissions_remain_server_controlled(env):
    app=custom(env);url=f"/api/v2/applications/custom/{app['id']}/records"
    assert env['client'].post(url,{'data':{'title':'Bon','weight':'NaN'}},format='json').status_code==400
    assert env['client'].post(url,{'data':{'title':'Bon','unknown':'value'}},format='json').status_code==400
    env['member'].role='viewer';env['member'].save()
    assert env['client'].get(url).status_code==200
    assert env['client'].post(url,{'data':{'title':'Bon'}},format='json').status_code==403
    assert env['client'].post('/api/v2/applications',{'key':'finance','enabled':False},format='json').status_code==403
    assert env['client'].post('/api/v2/applications/custom',{},format='json').status_code==403


def test_existing_records_protect_field_schema(env):
    app=custom(env);url='/api/v2/applications/custom/'+app['id']
    assert env['client'].post(url+'/records',{'data':{'title':'Bon'}},format='json').status_code==201
    assert env['client'].patch(url,{'fields':[{'key':'title','label':'Poids','type':'number','required':True}]},format='json').status_code==400
    fields=app['fields'];fields[0]['label']='Nouvelle référence'
    fields.append({'key':'comment','label':'Commentaire','type':'text','required':False})
    assert env['client'].patch(url,{'fields':fields},format='json').status_code==200
    assert env['client'].patch(url,{'enabled':False},format='json').status_code==200
    assert env['client'].get(url+'/records').status_code==403
    assert m.CustomRecord.objects.count()==1

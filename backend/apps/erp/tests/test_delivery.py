"""Recette des livraisons signées. Auteur : Jonathan Kakesa (JonathanK-N)."""
import hashlib,json
import pytest
from apps.erp import models as m
from django.core.files.uploadedfile import SimpleUploadedFile
from .test_workflows import env,mission,act

pytestmark=pytest.mark.django_db


def completed(env):
    trip=mission(env)
    act(env,'missions',trip['id'],'start')
    return act(env,'missions',trip['id'],'complete',{'loaded_quantity':0,'delivered_quantity':0,'delivery_note':'Réception effectuée.'})


def payload(**extra):
    data=dict(recipient_name='Mamadou Diallo',reservations='Colis contrôlés.',consent=True,signature=[[[10,100],[80,40],[160,130],[230,80]]])
    data.update(extra)
    return data


def test_signed_receipt_freezes_data_and_downloads_private_pdf(env):
    trip=completed(env);url='/api/v2/missions/'+trip['id']+'/receipt'
    response=env['client'].post(url,payload(),format='json')
    assert response.status_code==201,response.data
    receipt=response.data['receipt']
    expected=hashlib.sha256(json.dumps(receipt['snapshot'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    assert receipt['digest']==expected
    env['vehicle'].plate='NOUVELLE-PLAQUE';env['vehicle'].save()
    assert env['client'].get(url).data['receipt']['snapshot']['vehicle']=='RC-001'
    assert env['client'].post(url,payload(),format='json').status_code==409
    assert env['client'].patch(url,payload(recipient_name='Modification'),format='json').status_code==405
    pdf=env['client'].get(url+'/pdf')
    assert pdf.status_code==200 and pdf.content.startswith(b'%PDF-')
    assert pdf['Content-Type']=='application/pdf' and pdf['Cache-Control']=='no-store'
    assert m.AuditEvent.objects.filter(action='receipt-sign').exists()
    m.Membership.objects.create(organization=env['other'],user=env['user'],role='owner')
    env['client'].credentials(HTTP_X_ORGANIZATION=str(env['other'].pk))
    assert env['client'].get(url).status_code==404
    assert env['client'].get(url+'/pdf').status_code==404


@pytest.mark.parametrize('invalid',[
    {'consent':False},{'consent':'true'},{'signature':[]},{'signature':[[[1,2]]]},
    {'signature':[[[0,0],[999,100]]]},{'signature':[[[0,0],[True,100]]]},
    {'signature':[[[0,0],[1,1]]]},{'recipient_name':''},
])
def test_signature_requires_valid_strokes_identity_and_consent(env,invalid):
    trip=completed(env)
    response=env['client'].post('/api/v2/missions/'+trip['id']+'/receipt',payload(**invalid),format='json')
    assert response.status_code==400,response.data
    assert not m.DeliveryReceipt.objects.exists()


def test_driver_can_only_sign_own_completed_mission(env):
    trip=completed(env)
    env['member'].role='driver';env['member'].save()
    url='/api/v2/missions/'+trip['id']+'/receipt'
    assert env['client'].post(url,payload(),format='json').status_code==404
    env['driver'].user=env['user'];env['driver'].save()
    assert env['client'].post(url,payload(),format='json').status_code==201
    assert env['client'].get(url+'/pdf').status_code==200


def test_cannot_sign_before_completion_or_with_readonly_role(env):
    trip=mission(env);url='/api/v2/missions/'+trip['id']+'/receipt'
    assert env['client'].post(url,payload(),format='json').status_code==400
    assert env['client'].get(url).data['receipt'] is None
    env['member'].role='viewer';env['member'].save()
    assert env['client'].post(url,payload(),format='json').status_code==403


def test_driver_uploads_delivery_evidence_only_for_own_mission(env,settings,tmp_path):
    settings.MEDIA_ROOT=tmp_path
    trip=completed(env)
    env['member'].role='driver';env['member'].save()
    url='/api/v2/missions/'+trip['id']+'/delivery-documents'
    def upload():return env['client'].post(url,{'title':'Bon de réception','file':SimpleUploadedFile('bon.pdf',b'%PDF-1.4\nrecette')},format='multipart')
    assert upload().status_code==404
    env['driver'].user=env['user'];env['driver'].save()
    response=upload()
    assert response.status_code==201,response.data
    assert not response.data['shared_with_customer']
    assert m.Document.objects.get(pk=response.data['id']).mission_id==m.Mission.objects.get(pk=trip['id']).pk
    assert env['client'].get(url).data['count']==1

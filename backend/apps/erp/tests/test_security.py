"""Sessions, invitations et fichiers privés. Auteur : Jonathan Kakesa (JonathanK-N)."""
import hashlib
from datetime import timedelta
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient
from apps.erp import models as m
from .test_workflows import env

pytestmark=pytest.mark.django_db


def test_refresh_requires_csrf_rotates_and_logout_revokes(env):
    client=APIClient(enforce_csrf_checks=True)
    result=client.post('/api/v2/auth/login',{'email':'direction@example.test','password':'Long-password-938!'},format='json')
    assert result.status_code==200
    original=client.cookies['tf_refresh'].value
    assert client.cookies['tf_refresh']['httponly']
    assert client.post('/api/v2/auth/refresh',{},format='json').status_code==403
    csrf=client.get('/api/v2/auth/csrf').data['csrf']
    assert client.post('/api/v2/auth/refresh',{},format='json',HTTP_X_CSRFTOKEN=csrf).status_code==200
    rotated=client.cookies['tf_refresh'].value
    assert original!=rotated
    client.cookies['tf_refresh']=original
    assert client.post('/api/v2/auth/refresh',{},format='json',HTTP_X_CSRFTOKEN=csrf).status_code==401
    client.cookies['tf_refresh']=rotated
    assert client.post('/api/v2/auth/logout',{},format='json',HTTP_X_CSRFTOKEN=csrf).status_code==200
    client.cookies['tf_refresh']=rotated
    assert client.post('/api/v2/auth/refresh',{},format='json',HTTP_X_CSRFTOKEN=csrf).status_code==401


def test_invited_signup_does_not_create_company(env):
    token='invitation-recette-secrete'
    m.TeamInvitation.objects.create(organization=env['org'],email='colleague@example.test',role='operations',
        digest=hashlib.sha256(token.encode()).hexdigest(),expires_at=timezone.now()+timedelta(days=1))
    client=APIClient()
    result=client.post('/api/v2/auth/register',{'name':'Collaborateur','email':'colleague@example.test',
        'password':'Independent-password-839!','invitation':token},format='json')
    assert result.status_code==201,result.data
    assert m.Organization.objects.count()==2
    assert len(result.data['organizations'])==1
    assert result.data['organizations'][0]['role']=='operations'
    assert m.TeamInvitation.objects.get().used_at is not None
    again=client.post('/api/v2/auth/register',{'name':'Autre','email':'other@example.test','password':'Independent-password-839!','invitation':token},format='json')
    assert again.status_code==400


def test_private_document_isolation_and_file_validation(env,tmp_path,settings):
    settings.MEDIA_ROOT=tmp_path
    client=env['client']
    document=SimpleUploadedFile('preuve.pdf',b'%PDF-1.4\nrecette',content_type='application/pdf')
    result=client.post('/api/v2/documents',{'title':'Preuve','file':document},format='multipart')
    assert result.status_code==201,result.data
    pk=result.data['id']
    url=f'/api/v2/documents/{pk}/download'
    response=client.get(url);assert response.status_code==200
    assert b'%PDF' in b''.join(response.streaming_content)
    assert APIClient().get(url).status_code==401
    m.Membership.objects.create(organization=env['other'],user=env['user'],role='owner')
    client.credentials(HTTP_X_ORGANIZATION=str(env['other'].pk))
    assert client.get(url).status_code==404
    spoof=SimpleUploadedFile('malicious.pdf',b'<script>alert(1)</script>')
    assert client.post('/api/v2/documents',{'title':'Faux PDF','file':spoof},format='multipart').status_code==400


def test_login_throttle_does_not_disclose_accounts():
    client=APIClient()
    for _ in range(15):assert client.post('/api/v2/auth/login',{'email':'missing@example.test','password':'incorrect'},format='json').status_code==401
    assert client.post('/api/v2/auth/login',{'email':'missing@example.test','password':'incorrect'},format='json').status_code==429


def test_last_owner_cannot_be_disabled(env):
    result=env['client'].patch('/api/v2/team',{'id':env['member'].pk,'active':False},format='json')
    assert result.status_code==400
    env['member'].refresh_from_db();assert env['member'].active


def test_legacy_api_is_not_available_in_saas(env):
    assert env['client'].get('/api/vehicules').status_code==404


def test_password_reset_single_use_and_revokes_access(env):
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.http import urlsafe_base64_encode
    from django.utils.encoding import force_bytes
    from rest_framework_simplejwt.tokens import RefreshToken
    old_access=str(RefreshToken.for_user(env['user']).access_token)
    token=urlsafe_base64_encode(force_bytes(env['user'].pk))+':'+default_token_generator.make_token(env['user'])
    client=APIClient()
    data={'token':token,'password':'Changed-and-private-643!'}
    assert client.post('/api/v2/auth/password/reset',data,format='json').status_code==200
    assert client.post('/api/v2/auth/password/reset',data,format='json').status_code==400
    client.credentials(HTTP_AUTHORIZATION='Bearer '+old_access)
    assert client.get('/api/v2/auth/me').status_code==401


def test_password_request_response_does_not_reveal_user(env,monkeypatch):
    monkeypatch.setattr('apps.comptes.invitations.envoyer',lambda *a,**kw:True)
    client=APIClient()
    known=client.post('/api/v2/auth/password/request',{'email':'direction@example.test'},format='json')
    unknown=client.post('/api/v2/auth/password/request',{'email':'absent@example.test'},format='json')
    assert known.status_code==unknown.status_code==200
    assert known.data==unknown.data


def test_database_rejects_cross_company_relation_even_without_serializer(env):
    from django.db import connection,transaction,IntegrityError
    if connection.vendor!='postgresql':pytest.skip('Contrainte PostgreSQL')
    with pytest.raises(IntegrityError),transaction.atomic():
        m.Invoice.objects.create(organization=env['other'],customer=env['partner'],date='2026-09-26',due_date='2026-10-26')


def test_driver_can_only_operate_assigned_mission_and_sync_late_points(env):
    from .test_workflows import mission,act
    trip=mission(env)
    env['driver'].user=env['user'];env['driver'].save()
    env['member'].role='driver';env['member'].save()
    act(env,'missions',trip['id'],'start')
    point={'timestamp':timezone.now().isoformat(),'latitude':'9.641200','longitude':'-13.578400'}
    act(env,'missions',trip['id'],'complete')
    url=f"/api/v2/missions/{trip['id']}/positions"
    assert env['client'].post(url,{'positions':[point]},format='json').status_code==200
    assert env['client'].post(url,{'positions':[point]},format='json').status_code==200
    assert m.Position.objects.count()==1
    env['driver'].user=None;env['driver'].save()
    assert env['client'].get(url).status_code==404
    assert env['client'].post(url,{'positions':[point]},format='json').status_code==404

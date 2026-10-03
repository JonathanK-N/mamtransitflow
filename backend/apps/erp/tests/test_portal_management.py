from datetime import timedelta
from urllib.parse import urlparse,parse_qs
import pytest
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient
from apps.erp import models as m
from apps.comptes.models import Utilisateur
from .test_workflows import env

pytestmark=pytest.mark.django_db

@pytest.fixture(autouse=True)
def delivery(settings):
    settings.TF_COURRIEL_CONFIGURE=True
    settings.TF_RESEND_CLE=''
    settings.EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'

def new(env,**extra):
    return env['client'].post('/api/v2/portal-access',dict(mode='new',name='Client TEST Émeraude',email='customer@example.test',contact_name='Renée',phone='+224 12345',**extra),format='json')

def token(response):return parse_qs(urlparse(response.data['link']).query)['invitation'][0]

def test_new_customer_and_invitation_use_existing_model_branded_email_and_pending_list(env):
    response=new(env);assert response.status_code==201,response.data
    partner=m.Partner.objects.get(pk=response.data['customer']['id'])
    assert partner.kind=='customer' and partner.organization==env['org'] and partner.contact_name=='Renée'
    assert response.data['sent'] and response.data['company']==env['org'].name
    email=mail.outbox[-1];assert env['org'].name in email.subject
    assert 'Bonjour Renée,' in email.body and 'portail client' in email.body
    html=email.alternatives[0].content
    assert 'votre espace client TransitFlow' in html and 'transitflow-logo.png' in html
    assert response.data['link'] in html and response.data['link'] in email.body
    assert env['client'].get('/api/v2/partners/'+str(partner.pk)).status_code==200
    pending=env['client'].get('/api/v2/portal-access/invitations').data
    assert pending['count']==1 and pending['results'][0]['status']=='pending'
    assert env['client'].get('/api/v2/portal-access').data['count']==0
    assert not Utilisateur.objects.filter(courriel=partner.email).exists()

@pytest.mark.parametrize('data,field',[(dict(mode='new',name='Test'),'email'),(dict(mode='new',name='Test',email=''),'email'),(dict(mode='new',name='Test',email='incorrect'),'email'),(dict(mode='new',email='valid@example.test'),'name'),(dict(email='valid@example.test'),'partner')])
def test_required_fields_are_french_and_no_partial_customer_or_invitation(env,data,field):
    before=m.Partner.objects.count()
    response=env['client'].post('/api/v2/portal-access',data,format='json')
    assert response.status_code==400 and field in response.data
    assert m.Partner.objects.count()==before and not m.TeamInvitation.objects.exists()
    assert not mail.outbox

def test_existing_customer_email_completed_without_overwriting_business_data(env):
    partner=env['partner'];partner.address='Adresse métier';partner.notes='Conditions privées';partner.payment_days=60;partner.save()
    response=env['client'].post('/api/v2/portal-access',{'partner':str(partner.pk),'email':' NEW@EXAMPLE.TEST ','name':'Ne pas remplacer'},format='json')
    assert response.status_code==201,response.data
    partner.refresh_from_db();assert partner.email=='new@example.test'
    assert partner.name=='Client Conakry' and partner.address=='Adresse métier' and partner.notes=='Conditions privées' and partner.payment_days==60
    assert m.Partner.objects.filter(organization=env['org']).count()==1

def test_duplicate_email_case_insensitive_returns_scoped_customer_without_creation(env):
    partner=env['partner'];partner.email='CUSTOMER@example.test';partner.save()
    response=new(env);assert response.status_code==409
    assert response.data['code']=='duplicate_customer' and response.data['customer']['id']==str(partner.pk)
    assert m.Partner.objects.filter(organization=env['org']).count()==1 and not m.TeamInvitation.objects.exists()
    response=env['client'].post('/api/v2/portal-access',{'partner':str(partner.pk),'email':'customer@example.test'},format='json');assert response.status_code==201
    assert new(env).status_code==409
    assert m.TeamInvitation.objects.count()==1 and len(mail.outbox)==1

@pytest.mark.parametrize('query',['Émeraude','CUSTOMER@','12345','Renée'])
def test_search_name_email_phone_contact_is_scoped_and_excludes_suppliers(env,query):
    own=m.Partner.objects.create(organization=env['org'],name='Émeraude',email='customer@example.test',phone='12345',contact_name='Renée')
    m.Partner.objects.create(organization=env['other'],name='Émeraude',email='customer@example.test',phone='12345',contact_name='Renée')
    m.Partner.objects.create(organization=env['org'],name='Émeraude fournisseur',kind='supplier',email='customer@example.test',phone='12345',contact_name='Renée')
    rows=env['client'].get('/api/v2/portal-access/customers',{'q':query}).data['results']
    assert [row['id'] for row in rows]==[str(own.pk)]

def test_same_email_in_another_organization_does_not_reveal_or_block_customer(env):
    m.Partner.objects.create(organization=env['other'],name='Confidentiel',email='customer@example.test')
    response=new(env);assert response.status_code==201 and 'Confidentiel' not in str(response.data)

def test_identical_pending_invitation_is_not_duplicated(env):
    first=new(env);partner=first.data['customer']['id']
    response=env['client'].post('/api/v2/portal-access',{'partner':partner,'email':'customer@example.test'},format='json')
    assert response.status_code==409 and response.data['code']=='pending_invitation'
    assert m.TeamInvitation.objects.count()==1 and len(mail.outbox)==1

def test_resend_rotates_token_cancel_invalidates_it_and_states_are_visible(env):
    first=new(env);pk=first.data['invitation']['id'];old=token(first)
    resent=env['client'].post(f'/api/v2/portal-access/invitations/{pk}/resend',{},format='json')
    assert resent.status_code==201 and token(resent)!=old
    assert m.TeamInvitation.objects.filter(canceled_at__isnull=True,used_at__isnull=True,expires_at__gt=timezone.now()).count()==1
    account=Utilisateur.objects.create_user(courriel='customer@example.test',nom='Client',mot_de_passe='Portal-test-password-839!')
    client=APIClient();client.force_authenticate(account)
    assert client.post('/api/v2/invitation/accept',{'token':old},format='json').status_code==400
    second=resent.data['invitation']['id']
    assert env['client'].post(f'/api/v2/portal-access/invitations/{second}/cancel',{},format='json').status_code==200
    assert client.post('/api/v2/invitation/accept',{'token':token(resent)},format='json').status_code==400
    assert env['client'].post(f'/api/v2/portal-access/invitations/{second}/resend',{},format='json').status_code==400
    assert {x['status'] for x in env['client'].get('/api/v2/portal-access/invitations').data['results']}=={'canceled'}
    assert not m.PortalAccess.objects.exists()

def test_expired_invitation_can_be_renewed(env):
    first=new(env);invite=m.TeamInvitation.objects.get(pk=first.data['invitation']['id']);invite.expires_at=timezone.now()-timedelta(seconds=1);invite.save()
    assert env['client'].get('/api/v2/portal-access/invitations').data['results'][0]['status']=='expired'
    assert env['client'].post(f'/api/v2/portal-access/invitations/{invite.pk}/resend',{},format='json').status_code==201

def test_new_customer_accepts_registers_no_membership_employee_and_only_own_portal(env):
    first=new(env);client=APIClient();response=client.post('/api/v2/auth/register',{'email':'customer@example.test','name':'Client TEST','password':'Portal-test-password-839!','invitation':token(first)},format='json')
    assert response.status_code==201,response.data
    user=Utilisateur.objects.get(courriel='customer@example.test')
    assert not m.Membership.objects.filter(user=user).exists() and not m.Employee.objects.filter(user=user).exists()
    client.credentials(HTTP_AUTHORIZATION='Bearer '+response.data['access'],HTTP_X_ORGANIZATION=str(env['org'].pk))
    own=m.PortalAccess.objects.get(user=user).partner
    for partner,reference in [(own,'OWN'),(env['partner'],'OTHER')]:
        m.TransportOrder.objects.create(organization=env['org'],customer=partner,reference=reference,origin='A',destination='B',planned_date='2026-10-03',status='confirmed')
    assert [x['reference'] for x in client.get('/api/v2/portal/orders').data['results']]==['OWN']
    for path in ['employees','team','settings','messaging/conversations','portal-access/customers','portal-access/invitations']:
        assert client.get('/api/v2/'+path).status_code in [403,404]
    assert client.get('/api/v2/portal/orders/'+str(env['partner'].pk)).status_code==404
    assert env['client'].get('/api/v2/portal-access/invitations').data['results'][0]['status']=='accepted'
    assert env['client'].get('/api/v2/portal-access').data['count']==1
    assert client.post('/api/v2/invitation/accept',{'token':token(first)},format='json').status_code==400

def test_foreign_customer_invitation_actions_and_internal_invites_are_isolated(env):
    foreign=m.Partner.objects.create(organization=env['other'],name='Confidentiel')
    invite=m.TeamInvitation.objects.create(organization=env['other'],partner=foreign,role='client',email='customer@example.test',digest='1'*64,expires_at=timezone.now()+timedelta(days=7))
    for action in ['resend','cancel']:
        assert env['client'].post(f'/api/v2/portal-access/invitations/{invite.pk}/{action}',{},format='json').status_code==404
    assert env['client'].post('/api/v2/portal-access',{'partner':str(foreign.pk),'email':'customer@example.test'},format='json').status_code==404
    staff=m.TeamInvitation.objects.create(organization=env['org'],role='driver',email='customer@example.test',digest='2'*64,expires_at=timezone.now()+timedelta(days=7))
    portal=new(env);assert portal.status_code==201
    assert all(x['role']!='client' for x in env['client'].get('/api/v2/team').data['invitations'])
    assert env['client'].post('/api/v2/team',{'email':'customer@example.test','role':'driver'},format='json').status_code==201
    client_invite=m.TeamInvitation.objects.get(pk=portal.data['invitation']['id']);assert client_invite.expires_at>timezone.now() and not client_invite.canceled_at
    staff.refresh_from_db();assert not staff.canceled_at
    assert env['client'].post(f'/api/v2/portal-access/invitations/{staff.pk}/cancel',{},format='json').status_code==404

@pytest.mark.parametrize('role',['operations','finance','workshop','driver','viewer'])
def test_only_admins_can_manage_portal_clients(env,role):
    env['member'].role=role;env['member'].save()
    for path in ['portal-access','portal-access/customers','portal-access/invitations']:
        assert env['client'].get('/api/v2/'+path).status_code==403
    assert new(env).status_code==403

def test_failed_email_keeps_customer_and_invitation_with_honest_result(env,monkeypatch):
    monkeypatch.setattr('apps.comptes.invitations.envoyer',lambda *a,**k:False)
    response=new(env);assert response.status_code==201 and response.data['sent'] is False
    assert m.Partner.objects.filter(pk=response.data['customer']['id']).exists()
    assert m.TeamInvitation.objects.filter(pk=response.data['invitation']['id']).exists()

@pytest.mark.django_db(transaction=True)
def test_concurrent_new_customer_invites_create_one_customer_and_one_pending_invite(env):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from django.db import connection,connections,close_old_connections
    if connection.vendor!='postgresql':pytest.skip('Verrouillage vérifié sur PostgreSQL uniquement')
    gate=Barrier(2)
    def worker(index):
        close_old_connections()
        try:
            client=APIClient();client.force_authenticate(env['user']);client.credentials(HTTP_X_ORGANIZATION=str(env['org'].pk))
            gate.wait(timeout=10)
            return client.post('/api/v2/portal-access',{'mode':'new','name':'Concurrence','email':'race-customer@example.test'},format='json').status_code
        finally:connections.close_all()
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(worker,[0,1]))
    assert sorted(results)==[201,409]
    assert m.Partner.objects.filter(organization=env['org'],email='race-customer@example.test').count()==1
    assert m.TeamInvitation.objects.filter(organization=env['org'],email='race-customer@example.test').count()==1

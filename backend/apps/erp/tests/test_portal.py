"""Isolation du portail client. Auteur : Jonathan Kakesa (JonathanK-N)."""
from urllib.parse import urlparse,parse_qs
from datetime import timedelta
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient
import pytest
from apps.erp import models as m
from apps.comptes.models import Utilisateur
from .test_workflows import env,create,act,mission,invoice
from .test_delivery import payload

pytestmark=pytest.mark.django_db


def access(env,monkeypatch):
    monkeypatch.setattr('apps.comptes.invitations.envoyer',lambda *a,**kw:False)
    response=env['client'].post('/api/v2/portal-access',{'email':'client@example.test','partner':str(env['partner'].pk)},format='json')
    assert response.status_code==201,response.data
    token=parse_qs(urlparse(response.data['link']).query)['invitation'][0]
    client=APIClient()
    response=client.post('/api/v2/auth/register',{'name':'Client externe','email':'client@example.test','password':'Client-Recette-456!','invitation':token},format='json')
    assert response.status_code==201,response.data
    assert response.data['organizations'][0]['role']=='client'
    client.credentials(HTTP_AUTHORIZATION='Bearer '+response.data['access'],HTTP_X_ORGANIZATION=str(env['org'].pk))
    assert not m.Membership.objects.filter(user__courriel='client@example.test').exists()
    return client


def test_portal_hides_other_clients_drafts_and_internal_apis(env,monkeypatch):
    customer=access(env,monkeypatch)
    own=create(env,'orders',dict(reference='CLIENT-001',customer=str(env['partner'].pk),origin='Conakry',destination='Kindia',planned_date='2026-09-27'))
    act(env,'orders',own['id'],'confirm')
    create(env,'orders',dict(reference='BROUILLON-PRIVE',customer=str(env['partner'].pk),origin='A',destination='B',planned_date='2026-09-27'))
    other=m.Partner.objects.create(organization=env['org'],name='Client concurrent')
    m.TransportOrder.objects.create(organization=env['org'],reference='AUTRE-CLIENT',customer=other,origin='A',destination='B',planned_date='2026-09-27',status='confirmed')
    result=customer.get('/api/v2/portal/orders')
    assert result.status_code==200 and result.data['count']==1
    assert result.data['results'][0]['reference']=='CLIENT-001'
    for resource in ('orders','partners','employees','journal','dashboard','catalog','applications','team','portal-access'):
        assert customer.get('/api/v2/'+resource).status_code==403
    assert customer.post('/api/v2/portal/orders',{},format='json').status_code==405
    draft=invoice(env)
    assert customer.get('/api/v2/portal/invoices').data['count']==0
    act(env,'invoices',draft['id'],'issue')
    assert customer.get('/api/v2/portal/invoices').data['count']==1
    customer.credentials(HTTP_AUTHORIZATION=customer._credentials['HTTP_AUTHORIZATION'],HTTP_X_ORGANIZATION=str(env['other'].pk))
    assert customer.get('/api/v2/portal/orders').status_code==404


@pytest.mark.django_db(transaction=True)
def test_portal_shared_documents_and_signed_receipts_require_own_customer(env,monkeypatch,settings,tmp_path):
    settings.MEDIA_ROOT=tmp_path
    customer=access(env,monkeypatch)
    own=create(env,'orders',dict(reference='CLIENT-001',customer=str(env['partner'].pk),origin='A',destination='B',planned_date='2026-09-27'))
    act(env,'orders',own['id'],'confirm')
    trip=mission(env,order=own['id'])
    act(env,'missions',trip['id'],'start');act(env,'missions',trip['id'],'complete')
    assert env['client'].post('/api/v2/missions/'+trip['id']+'/receipt',payload(),format='json').status_code==201
    assert customer.get('/api/v2/portal/receipt/'+trip['id']).content.startswith(b'%PDF-')
    shared=m.Document.objects.create(organization=env['org'],mission_id=trip['id'],category='delivery',shared_with_customer=True,title='Bon de livraison',file=SimpleUploadedFile('bon.pdf',b'%PDF-1.4\nrecette'))
    private=m.Document.objects.create(organization=env['org'],mission_id=trip['id'],category='delivery',title='Note interne',file=SimpleUploadedFile('interne.pdf',b'%PDF-1.4\nprive'))
    result=customer.get('/api/v2/portal/documents')
    assert result.data['count']==1
    assert customer.get('/api/v2/portal/document/'+str(private.pk)).status_code==404
    response=customer.get('/api/v2/portal/document/'+str(shared.pk))
    assert response.status_code==200
    response.close()
    unrelated=m.Partner.objects.create(organization=env['org'],name='Autre client')
    row=m.PortalAccess.objects.get(user__courriel='client@example.test');row.partner=unrelated;row.save()
    assert customer.get('/api/v2/portal/receipt/'+trip['id']).status_code==404
    assert customer.get('/api/v2/portal/document/'+str(shared.pk)).status_code==404


def test_portal_revocation_and_module_disable_take_effect_immediately(env,monkeypatch):
    customer=access(env,monkeypatch)
    row=m.PortalAccess.objects.get(user__courriel='client@example.test')
    assert env['client'].patch('/api/v2/portal-access',{'id':str(row.pk),'active':False},format='json').status_code==200
    assert customer.get('/api/v2/portal/orders').status_code==404
    assert env['client'].patch('/api/v2/portal-access',{'id':str(row.pk),'active':True},format='json').status_code==200
    assert customer.get('/api/v2/portal/orders').status_code==200
    assert env['client'].post('/api/v2/applications',{'key':'customer-portal','enabled':False},format='json').status_code==200
    assert customer.get('/api/v2/portal/orders').status_code==403


def test_portal_invitation_rejects_foreign_partner_and_internal_account(env,monkeypatch):
    monkeypatch.setattr('apps.comptes.invitations.envoyer',lambda *a,**kw:False)
    foreign=m.Partner.objects.create(organization=env['other'],name='Autre entreprise')
    assert env['client'].post('/api/v2/portal-access',{'email':'client@example.test','partner':str(foreign.pk)},format='json').status_code==404
    assert env['client'].post('/api/v2/portal-access',{'email':env['user'].courriel,'partner':str(env['partner'].pk)},format='json').status_code==400
    assert env['client'].post('/api/v2/portal-access',{'email':'client@example.test','partner':[]},format='json').status_code==400


def test_portal_invoice_print_data_contains_only_customer_facing_fields(env,monkeypatch):
    customer=access(env,monkeypatch)
    env['partner'].address='Adresse client';env['partner'].tax_number='TAX-TEST';env['partner'].notes='PRIVATE-CUSTOMER-NOTES';env['partner'].save()
    draft=invoice(env);act(env,'invoices',draft['id'],'issue')
    item=m.Invoice.objects.get(pk=draft['id'])
    item.lines[0]['internal_cost']='PRIVATE-COST';item.save(update_fields=['lines'])
    response=customer.get('/api/v2/portal/invoices')
    assert response.status_code==200,response.data
    row=response.data['results'][0]
    assert row['customer_details']=={'name':env['partner'].name,'address':'Adresse client','email':env['partner'].email,'tax_number':'TAX-TEST'}
    assert set(row['lines'][0])=={'description','quantity','price','tax_rate','total'}
    assert 'PRIVATE' not in str(response.data)

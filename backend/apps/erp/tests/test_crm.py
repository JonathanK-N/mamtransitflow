from datetime import timedelta
from decimal import Decimal
import pytest
from django.utils import timezone
from apps.erp import models as m
from .test_workflows import env, create, act, mission

pytestmark=pytest.mark.django_db


def quote(env):
    today=timezone.localdate()
    return create(env,'invoices',dict(kind='quote',customer=str(env['partner'].pk),date=str(today),due_date=str(today+timedelta(days=30)),origin='Conakry',destination='Kindia',lines=[dict(description='Transport',quantity='2',price='100',tax_rate='0')]))


def commercial(env,pk,action,expected=200):
    response=env['client'].post(f'/api/v2/commercial/{pk}/{action}',{},format='json')
    assert response.status_code==expected,response.data
    return response.data


def test_quote_conversion_preserves_snapshot_and_is_idempotent(env):
    bill=quote(env)
    commercial(env,bill['id'],'convert',400)
    commercial(env,bill['id'],'send')
    commercial(env,bill['id'],'accept')
    order=commercial(env,bill['id'],'convert')
    assert order['amount']=='200.00'
    assert order['reference'].startswith('CMD-')
    assert str(order['source_quote'])==bill['id']
    assert commercial(env,bill['id'],'convert')['id']==order['id']
    assert m.TransportOrder.objects.count()==1
    assert env['client'].patch('/api/v2/invoices/'+bill['id'],{'origin':'Changed'},format='json').status_code==400
    env['client'].patch('/api/v2/orders/'+order['id'],{'origin':'Changed'},format='json')
    assert m.Invoice.objects.get(pk=bill['id']).origin=='Conakry'


def test_delivery_invoice_partial_and_full_payment_client_stats(env):
    bill=quote(env)
    commercial(env,bill['id'],'send');commercial(env,bill['id'],'accept')
    order=commercial(env,bill['id'],'convert')
    act(env,'orders',order['id'],'confirm')
    trip=mission(env,order=order['id'])
    act(env,'missions',trip['id'],'start')
    act(env,'missions',trip['id'],'complete',dict(loaded_quantity='2',delivered_quantity='2'))
    invoice=commercial(env,trip['id'],'invoice')
    assert invoice['status']=='draft'
    assert commercial(env,trip['id'],'invoice')['id']==invoice['id']
    act(env,'invoices',invoice['id'],'issue')
    for amount,reference in [('75','PARTIAL'),('125','FINAL')]:
        create(env,'payments',dict(invoice=invoice['id'],amount=amount,date=str(timezone.localdate()),reference=reference))
    assert m.Invoice.objects.get(pk=invoice['id']).status=='paid'
    response=env['client'].get(f"/api/v2/clients/{env['partner'].pk}")
    assert response.status_code==200,response.data
    assert Decimal(response.data['stats']['balance'])==0
    assert response.data['stats']['completed_missions']==1
    assert response.data['stats']['invoices']==1
    assert response.data['stats']['late']==0


def test_archive_preserves_history_excludes_selector_and_restores(env):
    bill=quote(env)
    url=f"/api/v2/clients/{env['partner'].pk}"
    assert env['client'].post(url+'/archive',{},format='json').status_code==200
    assert env['client'].get('/api/v2/partners').data['count']==0
    assert env['client'].get('/api/v2/clients?archived=true').data['count']==1
    assert m.Invoice.objects.filter(pk=bill['id']).exists()
    response=env['client'].post('/api/v2/orders',dict(customer=str(env['partner'].pk),origin='A',destination='B',planned_date=str(timezone.localdate())),format='json')
    assert response.status_code==400
    assert env['client'].delete('/api/v2/partners/'+str(env['partner'].pk)).status_code==403
    assert env['client'].post(url+'/restore',{},format='json').status_code==200
    assert env['client'].get('/api/v2/partners').data['count']==1


def test_cross_tenant_client_and_commercial_denied(env):
    foreign=m.Partner.objects.create(organization=env['other'],name='Secret')
    for suffix in ('','/activity'):
        assert env['client'].get(f'/api/v2/clients/{foreign.pk}'+suffix).status_code==404
    assert env['client'].post(f'/api/v2/clients/{foreign.pk}/archive',{},format='json').status_code==404
    response=env['client'].post('/api/v2/contacts',dict(customer=str(foreign.pk),name='Secret'),format='json')
    assert response.status_code==400


def test_operations_cannot_view_financial_client_totals(env):
    env['member'].role='operations';env['member'].save()
    response=env['client'].get(f"/api/v2/clients/{env['partner'].pk}")
    assert response.status_code==200
    assert 'balance' not in response.data['stats']
    assert 'invoices' not in response.data['tabs']


def test_server_generates_order_and_mission_references(env):
    order=create(env,'orders',dict(customer=str(env['partner'].pk),origin='A',destination='B',planned_date=str(timezone.localdate())))
    assert order['reference'].startswith('CMD-')
    now=timezone.now()+timedelta(days=1)
    trip=create(env,'missions',dict(vehicle=str(env['vehicle'].pk),driver=str(env['driver'].pk),origin='A',destination='B',departure=str(now),arrival=str(now+timedelta(hours=1))))
    assert trip['reference'].startswith('MIS-')


def test_client_activity_is_paginated_and_contains_related_document(env):
    bill=quote(env)
    response=env['client'].get(f"/api/v2/clients/{env['partner'].pk}/activity")
    assert response.status_code==200,response.data
    assert any(x['object_id']==bill['id'] for x in response.data['results'])


def test_external_discussion_isolated_from_internal_and_other_clients(env):
    import uuid
    from apps.comptes.models import Utilisateur
    from rest_framework.test import APIClient
    user=Utilisateur.objects.create_user(courriel='portal-crm@example.test',mot_de_passe='Portal-test-938!',nom='Client')
    access=m.PortalAccess.objects.create(organization=env['org'],user=user,partner=env['partner'])
    url=f"/api/v2/clients/{env['partner'].pk}"
    assert env['client'].post(url+'/conversation',{},format='json').status_code==200
    message=dict(body='Votre livraison est confirmée.',client_id=str(uuid.uuid4()))
    assert env['client'].post(url+'/messages',message,format='json').status_code==201
    assert env['client'].post(url+'/messages',message,format='json').status_code==200
    portal=APIClient();portal.force_authenticate(user);portal.credentials(HTTP_X_ORGANIZATION=str(env['org'].pk))
    response=portal.get('/api/v2/portal/messages')
    assert response.status_code==200,response.data
    assert response.data['count']==1
    assert 'sender' not in response.data['results'][0]
    assert portal.get('/api/v2/messaging/conversations').status_code==403
    other_user=Utilisateur.objects.create_user(courriel='other-portal-crm@example.test',mot_de_passe='Portal-test-938!',nom='Autre client')
    other_partner=m.Partner.objects.create(organization=env['org'],name='Autre client')
    m.PortalAccess.objects.create(organization=env['org'],user=other_user,partner=other_partner)
    portal.force_authenticate(other_user)
    assert portal.get('/api/v2/portal/messages').status_code==404
    portal.force_authenticate(user)
    access.active=False;access.save()
    assert portal.get('/api/v2/portal/messages').status_code==404
    assert portal.post('/api/v2/portal/messages',dict(body='Refusé',client_id=str(uuid.uuid4())),format='json').status_code==404
    assert m.ClientMessage.objects.count()==1


def test_customer_directory_and_totals_keep_bounded_queries_at_volume(env):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    m.Partner.objects.bulk_create([m.Partner(organization=env['org'],name=f'TEST Client {n:04d}') for n in range(500)])
    today=timezone.localdate()
    m.Invoice.objects.bulk_create([m.Invoice(organization=env['org'],customer=env['partner'],date=today,due_date=today-timedelta(days=1),total=Decimal('100.25'),paid=Decimal('40.10'),status='issued',number=f'TEST-VOLUME-{n}') for n in range(1000)])
    with CaptureQueriesContext(connection) as queries:
        response=env['client'].get('/api/v2/clients?q=TEST')
    assert response.status_code==200
    assert response.data['count']==500
    assert len(response.data['results'])==25
    assert len(queries)<=12
    with CaptureQueriesContext(connection) as queries:
        response=env['client'].get(f"/api/v2/clients/{env['partner'].pk}")
    assert response.status_code==200,response.data
    assert Decimal(response.data['stats']['billed'])==Decimal('100250.00')
    assert Decimal(response.data['stats']['paid'])==Decimal('40100.00')
    assert Decimal(response.data['stats']['balance'])==Decimal('60150.00')
    assert response.data['stats']['late']==1000
    assert len(queries)<=24


@pytest.mark.parametrize('rates,amount,total',[(['18'],'200','236'),(['18','0'],'200','218'),(['18','0'],'150','163.50')])
def test_invoice_from_delivery_preserves_quote_tax_rates(env,rates,amount,total):
    bill=quote(env)
    lines=[dict(description='Prestation '+str(n),quantity='1',price='100' if len(rates)>1 else '200',tax_rate=rate) for n,rate in enumerate(rates)]
    response=env['client'].patch('/api/v2/invoices/'+bill['id'],{'lines':lines},format='json');assert response.status_code==200,response.data
    commercial(env,bill['id'],'send');commercial(env,bill['id'],'accept')
    order=commercial(env,bill['id'],'convert')
    env['client'].patch('/api/v2/orders/'+order['id'],{'amount':amount},format='json')
    act(env,'orders',order['id'],'confirm')
    trip=mission(env,order=order['id']);act(env,'missions',trip['id'],'start')
    act(env,'missions',trip['id'],'complete',dict(loaded_quantity='2',delivered_quantity='2'))
    invoice=commercial(env,trip['id'],'invoice')
    assert Decimal(invoice['subtotal'])==Decimal(amount)
    assert Decimal(invoice['total'])==Decimal(total)
    assert [x['tax_rate'] for x in invoice['lines']]==rates


def test_small_amount_allocation_never_produces_negative_line_prices():
    from apps.erp.crm_services import allocate_bases
    lines=[dict(quantity='1',price='.01') for _ in range(100)]
    bases=allocate_bases(lines,Decimal('.50'),Decimal('1'))
    assert len(bases)==100 and min(bases)>=0
    assert sum(bases)==Decimal('.50')


def test_refused_and_expired_quotes_cannot_be_converted(env):
    bill=quote(env);commercial(env,bill['id'],'send');commercial(env,bill['id'],'refuse')
    commercial(env,bill['id'],'accept',400);commercial(env,bill['id'],'convert',400)
    second=quote(env);commercial(env,second['id'],'send')
    m.Invoice.objects.filter(pk=second['id']).update(due_date=timezone.localdate()-timedelta(days=1))
    commercial(env,second['id'],'accept',400);commercial(env,second['id'],'expire')
    commercial(env,second['id'],'convert',400)
    assert not m.TransportOrder.objects.exists()


def test_customer_documents_require_explicit_sharing_and_stay_isolated(env):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from apps.comptes.models import Utilisateur
    from rest_framework.test import APIClient
    user=Utilisateur.objects.create_user(courriel='documents-crm@example.test',mot_de_passe='Portal-test-938!',nom='Client')
    m.PortalAccess.objects.create(organization=env['org'],user=user,partner=env['partner'])
    other=m.Partner.objects.create(organization=env['org'],name='Autre client')
    documents=[]
    for customer,shared,title in [(env['partner'],False,'INTERNE TEST'),(env['partner'],True,'PARTAGE TEST'),(other,True,'AUTRE CLIENT TEST')]:
        response=env['client'].post('/api/v2/documents',{'customer':str(customer.pk),'title':title,'category':'other','shared_with_customer':shared,'file':SimpleUploadedFile('test.pdf',b'%PDF-1.4\n%%EOF',content_type='application/pdf')},format='multipart')
        assert response.status_code==201,response.data
        documents.append(response.data['id'])
    portal=APIClient();portal.force_authenticate(user);portal.credentials(HTTP_X_ORGANIZATION=str(env['org'].pk))
    response=portal.get('/api/v2/portal/documents')
    assert response.status_code==200,response.data
    assert [x['id'] for x in response.data['results']]==[documents[1]]
    assert portal.get('/api/v2/portal/document/'+documents[0]).status_code==404
    assert portal.get('/api/v2/portal/document/'+documents[2]).status_code==404


@pytest.mark.parametrize('relation',['contact_customer','document_customer','quote_order','invoice_mission','conversation_access','message_conversation'])
def test_database_rejects_cross_company_commercial_relations(env,relation):
    from django.db import connection,transaction,IntegrityError
    from uuid import uuid4
    if connection.vendor!='postgresql':pytest.skip('Contrainte composite PostgreSQL')
    own,other,customer,user=env['org'],env['other'],env['partner'],env['user']
    bill=m.Invoice.objects.create(organization=own,customer=customer,date=timezone.localdate(),due_date=timezone.localdate())
    trip=mission(env)
    access=m.PortalAccess.objects.create(organization=own,user=user,partner=customer)
    conversation=m.ClientConversation.objects.create(organization=own,access=access,creator=user)
    foreign_customer=m.Partner.objects.create(organization=other,name='TEST Client étranger')
    constructors={
        'contact_customer':lambda:m.PartnerContact.objects.create(organization=other,customer=customer,name='Contact'),
        'document_customer':lambda:m.Document.objects.create(organization=other,customer=customer,title='TEST Document',file='test.txt'),
        'quote_order':lambda:m.TransportOrder.objects.create(organization=other,customer=foreign_customer,source_quote=bill,reference='TEST',origin='A',destination='B',planned_date=timezone.localdate()),
        'invoice_mission':lambda:m.Invoice.objects.create(organization=other,customer=foreign_customer,mission_id=trip['id'],date=timezone.localdate(),due_date=timezone.localdate()),
        'conversation_access':lambda:m.ClientConversation.objects.create(organization=other,access=access,creator=user),
        'message_conversation':lambda:m.ClientMessage.objects.create(organization=other,conversation=conversation,sender=user,body='TEST',client_id=uuid4()),
    }
    if relation=='conversation_access':conversation.delete()
    with pytest.raises(IntegrityError),transaction.atomic():constructors[relation]()


def test_portal_billing_excludes_sent_quotes_and_draft_invoices(env):
    from apps.comptes.models import Utilisateur
    from rest_framework.test import APIClient
    user=Utilisateur.objects.create_user(courriel='portal-finance-test@example.test',mot_de_passe='Portal-test-938!',nom='Client TEST')
    m.PortalAccess.objects.create(organization=env['org'],user=user,partner=env['partner'])
    sent=quote(env);commercial(env,sent['id'],'send')
    draft=create(env,'invoices',dict(kind='invoice',customer=str(env['partner'].pk),date=str(timezone.localdate()),due_date=str(timezone.localdate()),lines=[dict(description='TEST',quantity='1',price='100',tax_rate='0')]))
    portal=APIClient();portal.force_authenticate(user);portal.credentials(HTTP_X_ORGANIZATION=str(env['org'].pk))
    response=portal.get('/api/v2/portal/invoices');assert response.status_code==200,response.data
    assert response.data['count']==0
    act(env,'invoices',draft['id'],'issue')
    response=portal.get('/api/v2/portal/invoices');assert response.data['count']==1
    assert response.data['results'][0]['id']==draft['id']

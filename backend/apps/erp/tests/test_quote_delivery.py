import re
from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.erp import models as m
from apps.erp.quote_delivery import digest
from .test_workflows import env, create

pytestmark = pytest.mark.django_db


def prepare(env, monkeypatch, success=True):
    env['partner'].email='customer@example.test'
    env['partner'].save(update_fields=['email'])
    transport=Mock(return_value=success)
    monkeypatch.setattr('apps.comptes.invitations.envoyer',transport)
    today=timezone.localdate()
    quote=create(env,'invoices',dict(kind='quote',customer=str(env['partner'].pk),date=str(today),
        due_date=str(today+timedelta(days=1)),origin='A',destination='B',
        lines=[dict(description='Transport TEST',quantity='1',price='100',tax_rate='18')]))
    return quote,transport


def send(env, quote):
    return env['client'].post(f"/api/v2/commercial/{quote['id']}/send",{},format='json')


def public(token, action='preview', **data):
    return APIClient().post('/api/v2/public/quotes/'+action,{'token':token,**data},format='json')


def test_send_delivers_minimal_public_quote_and_only_stores_hash(env,monkeypatch):
    quote,transport=prepare(env,monkeypatch)
    response=send(env,quote)
    assert response.status_code==200,response.data
    assert response.data['quote_status']=='sent'
    transport.assert_called_once()
    recipient,subject,text,html=transport.call_args.args
    assert recipient=='customer@example.test' and env['org'].name in subject
    assert 'Logo TransitFlow' in html and '/erp/email/transitflow-logo.png' in html
    token=re.search(r'/devis#([\w-]+)',text).group(1)
    link=m.QuoteLink.objects.get(quote_id=quote['id'])
    assert link.token_hash==digest(token) and token not in str(link.__dict__)
    m.Invoice.objects.filter(pk=quote['id']).update(lines=[dict(description='Transport TEST',quantity='1',price='100',tax_rate='18',internal_cost='PRIVATE')])
    result=public(token)
    assert result.status_code==200 and result.data['total']=='118.00'
    assert set(result.data)=={'company','customer','number','date','valid_until','origin','destination','lines','subtotal','tax','total','currency','state'}
    assert set(result.data['lines'][0])=={'description','quantity','price','tax_rate'}
    assert result['Cache-Control']=='no-store'
    assert public('x'*43).status_code==404
    assert public(token+'x').status_code==404
    assert m.TransportOrder.objects.count()==0


@pytest.mark.parametrize('decision,target',[('accept','accepted'),('refuse','refused')])
def test_customer_response_is_explicit_idempotent_and_audited(env,monkeypatch,decision,target):
    quote,transport=prepare(env,monkeypatch)
    assert send(env,quote).status_code==200
    token=re.search(r'/devis#([\w-]+)',transport.call_args.args[2]).group(1)
    assert public(token,'respond',decision='unknown').status_code==400
    result=public(token,'respond',decision=decision)
    assert result.status_code==200 and result.data['state']==target
    assert public(token,'respond',decision=decision).status_code==200
    assert public(token,'respond',decision='refuse' if decision=='accept' else 'accept').status_code==409
    assert m.QuoteLink.objects.get(quote_id=quote['id']).responded_at
    assert m.AuditEvent.objects.filter(action='quote-customer-response').count()==1
    assert m.GlobalNotification.objects.filter(title='Devis accepté' if decision=='accept' else 'Devis refusé').exists()
    assert not m.TransportOrder.objects.exists()


def test_failed_send_rolls_back_issue_number_and_link(env,monkeypatch):
    quote,_=prepare(env,monkeypatch,False)
    assert send(env,quote).status_code==400
    bill=m.Invoice.objects.get(pk=quote['id'])
    assert bill.status=='draft' and bill.quote_status=='draft' and bill.number==''
    assert not m.QuoteLink.objects.exists()
    assert not m.AuditEvent.objects.filter(action='quote-send-email').exists()


def test_missing_email_and_generic_issue_cannot_mark_quote_sent(env,monkeypatch):
    quote,transport=prepare(env,monkeypatch)
    env['partner'].email='';env['partner'].save(update_fields=['email'])
    assert send(env,quote).status_code==400
    assert env['client'].post(f"/api/v2/invoices/{quote['id']}/actions/issue",{},format='json').status_code==400
    transport.assert_not_called()


def test_expired_and_archived_link_cannot_be_used(env,monkeypatch):
    quote,transport=prepare(env,monkeypatch)
    assert send(env,quote).status_code==200
    token=re.search(r'/devis#([\w-]+)',transport.call_args.args[2]).group(1)
    link=m.QuoteLink.objects.get(quote_id=quote['id'])
    link.expires_at=timezone.now()-timedelta(seconds=1);link.save()
    assert public(token).status_code==410
    assert public(token,'respond',decision='accept').status_code==410
    link.expires_at=timezone.now()+timedelta(days=1);link.save()
    env['partner'].archived_at=timezone.now();env['partner'].save()
    assert public(token).status_code==410
    assert m.Invoice.objects.get(pk=quote['id']).quote_status=='sent'


def test_cross_tenant_send_and_public_rate_limit(env,monkeypatch):
    quote,transport=prepare(env,monkeypatch)
    env['client'].credentials(HTTP_X_ORGANIZATION=str(env['other'].pk))
    assert send(env,quote).status_code==403
    transport.assert_not_called()
    client=APIClient()
    for _ in range(60):
        assert client.post('/api/v2/public/quotes/preview',{'token':'x'*43},format='json').status_code==404
    assert client.post('/api/v2/public/quotes/preview',{'token':'x'*43},format='json').status_code==429


def test_resend_revokes_previous_token_and_failed_resend_preserves_link(env,monkeypatch):
    quote,transport=prepare(env,monkeypatch)
    assert send(env,quote).status_code==200
    first=re.search(r'/devis#([\w-]+)',transport.call_args.args[2]).group(1)
    url=f"/api/v2/commercial/{quote['id']}/resend"
    transport.return_value=False
    assert env['client'].post(url,{},format='json').status_code==400
    assert public(first).status_code==200
    transport.return_value=True
    assert env['client'].post(url,{},format='json').status_code==200
    second=re.search(r'/devis#([\w-]+)',transport.call_args.args[2]).group(1)
    assert first!=second and m.QuoteLink.objects.count()==1
    assert public(first).status_code==404 and public(second).status_code==200
    assert env['client'].post(f"/api/v2/commercial/{quote['id']}/revoke-link",{},format='json').status_code==200
    assert public(second).status_code==410


def test_quote_link_database_rejects_cross_tenant_relation(env,monkeypatch):
    from django.db import connection,transaction,IntegrityError
    if connection.vendor!='postgresql':pytest.skip('Contrainte composite vérifiée sur PostgreSQL uniquement')
    quote,_=prepare(env,monkeypatch)
    with pytest.raises(IntegrityError),transaction.atomic():
        m.QuoteLink.objects.create(organization=env['other'],quote_id=quote['id'],token_hash='a'*64,recipient='customer@example.test',expires_at=timezone.now()+timedelta(days=1))


def test_quote_expiration_boundary_does_not_send_or_issue(env,monkeypatch):
    from datetime import date
    quote,transport=prepare(env,monkeypatch)
    m.Invoice.objects.filter(pk=quote['id']).update(due_date=date.max)
    response=send(env,quote)
    assert response.status_code==400
    transport.assert_not_called()
    item=m.Invoice.objects.get(pk=quote['id'])
    assert item.status=='draft' and item.quote_status=='draft'
    assert not m.QuoteLink.objects.filter(quote=item).exists()

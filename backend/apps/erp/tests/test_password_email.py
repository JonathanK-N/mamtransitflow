import re
from html import escape
import pytest
from django.core import mail
from rest_framework.test import APIClient
from .test_workflows import env

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('name', ['<Renée & Jean>', ''])
def test_password_reset_email_branding_and_secure_link(env,settings,name):
    settings.TF_COURRIEL_CONFIGURE = False
    settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    settings.PASSWORD_RESET_TIMEOUT = 1800
    env['user'].nom=name;env['user'].save(update_fields=['nom'])
    client=APIClient()
    response=client.post('/api/v2/auth/password/request',{'email':env['user'].courriel},format='json',secure=True)
    assert response.status_code==200
    email=mail.outbox[-1]
    html=email.alternatives[0].content
    assert email.subject=='TransitFlow — réinitialisation de votre mot de passe'
    assert email.alternatives[0].mimetype=='text/html'
    assert 'https://testserver/static/erp/email/transitflow-logo.png' in html
    assert 'Réinitialiser mon mot de passe' in html
    assert '30 minutes' in html and '30 minutes' in email.body
    assert env['user'].courriel in html and env['user'].courriel in email.body
    assert 'Votre mot de passe reste inchangé' in html
    greeting=f'Bonjour {name},' if name else 'Bonjour,'
    assert greeting in email.body
    assert escape(greeting) in html
    link=re.search(r'https://testserver/connexion\?reset=([^\s]+)',email.body)
    assert link
    assert html.count(link.group(0))>=3
    token=link.group(1)
    payload={'token':token,'password':'Changed-and-private-643!'}
    assert client.post('/api/v2/auth/password/reset',payload,format='json').status_code==200
    assert client.post('/api/v2/auth/password/reset',payload,format='json').status_code==400


def test_password_request_does_not_send_or_disclose_unknown_account(env,settings):
    settings.TF_COURRIEL_CONFIGURE = False
    settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    client=APIClient()
    known=client.post('/api/v2/auth/password/request',{'email':env['user'].courriel},format='json')
    assert len(mail.outbox)==1
    unknown=client.post('/api/v2/auth/password/request',{'email':'unknown@example.test'},format='json')
    assert unknown.status_code==known.status_code==200
    assert unknown.data==known.data
    assert len(mail.outbox)==1

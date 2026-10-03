from datetime import timedelta
from html import escape
from zoneinfo import ZoneInfo
from urllib.parse import parse_qs, urlparse

import pytest
from django.contrib.staticfiles import finders
from django.core import mail
from django.utils import timezone
from apps.comptes.models import Utilisateur
from apps.erp import models as m
from .test_workflows import env

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('role,label', [('driver','Chauffeur'),('operations','Exploitation'),('workshop','Atelier'),('finance','Finance'),('admin','Administrateur'),('viewer','Lecture seule')])
def test_team_invitation_email_contains_identity_role_and_original_link(env,settings,role,label):
    settings.TF_COURRIEL_CONFIGURE = False
    settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    env['org'].name = 'Transport Émeraude & Fils'
    env['org'].save()
    response = env['client'].post('/api/v2/team', {'email':'new@example.test','role':role}, format='json', secure=True)
    assert response.status_code == 201, response.data
    invitation = m.TeamInvitation.objects.get(email='new@example.test')
    email = mail.outbox[-1]
    html = email.alternatives[0].content
    assert email.alternatives[0].mimetype == 'text/html'
    assert email.subject == 'Invitation à rejoindre Transport Émeraude & Fils sur TransitFlow'
    assert 'Transport Émeraude & Fils' in email.body
    assert 'Transport Émeraude &amp; Fils' in html
    assert label in html and label in email.body
    assert 'Bonjour,' in html and 'Bonjour,' in email.body
    link = response.data['link']
    assert f'href="{escape(link, quote=True)}"' in html
    assert link in email.body
    assert html.count(escape(link, quote=True)) >= 3
    assert 'Accepter l’invitation' in html
    assert 'https://testserver/static/erp/email/transitflow-logo.png' in html
    assert finders.find('erp/email/transitflow-logo.png')
    assert '<table role="presentation"' in html
    assert 'new@example.test' in html and 'new@example.test' in email.body
    expiration = timezone.localtime(invitation.expires_at, ZoneInfo(env['org'].timezone))
    assert expiration.strftime('%d/%m/%Y à %H:%M') in html
    assert env['org'].timezone in html
    token = parse_qs(urlparse(link).query)['invitation'][0]
    result = env['client'].post('/api/v2/invitation/accept', {'token':token}, format='json')
    assert result.status_code == 403
    assert invitation.used_at is None


def test_existing_recipient_name_is_escaped_and_actual_expiration_used(env,settings):
    from rest_framework.test import APIRequestFactory
    from apps.erp.invitation_email import send_invitation
    settings.TF_COURRIEL_CONFIGURE = False
    settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    user = Utilisateur.objects.create_user(courriel='known@example.test',nom='<Renée & Jean>',mot_de_passe='Known-recipient-938!')
    invitation = m.TeamInvitation(organization=env['org'],email=user.courriel,role='driver',expires_at=timezone.now()+timedelta(hours=3))
    request = APIRequestFactory().get('/api/v2/team', secure=True)
    send_invitation(request,invitation,'https://testserver/app?invitation=original-token')
    email = mail.outbox[-1]
    assert 'Bonjour <Renée & Jean>,' in email.body
    assert 'Bonjour &lt;Renée &amp; Jean&gt;,' in email.alternatives[0].content
    assert '<Renée' not in email.alternatives[0].content
    assert '7 jours' not in email.body


def test_client_invitation_uses_portal_wording_and_preserves_access_flow(env,settings):
    from rest_framework.test import APIClient
    settings.TF_COURRIEL_CONFIGURE = False
    settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    response = env['client'].post('/api/v2/portal-access',{'email':'customer@example.test','partner':str(env['partner'].pk)},format='json',secure=True)
    assert response.status_code == 201,response.data
    email = mail.outbox[-1]
    assert 'portail client' in email.body
    assert 'Client' in email.alternatives[0].content
    assert env['org'].name in email.subject
    token = parse_qs(urlparse(response.data['link']).query)['invitation'][0]
    response = APIClient().post('/api/v2/auth/register',{'name':'Client','email':'customer@example.test','password':'Customer-password-839!','invitation':token},format='json')
    assert response.status_code == 201,response.data
    assert m.PortalAccess.objects.filter(user__courriel='customer@example.test').exists()
    assert not m.Employee.objects.filter(email='customer@example.test').exists()


def test_recipient_employee_name_is_scoped_to_inviting_company(env,settings):
    from rest_framework.test import APIRequestFactory
    from apps.erp.invitation_email import send_invitation
    settings.TF_COURRIEL_CONFIGURE = False
    settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    m.Employee.objects.create(organization=env['other'],email='staff@example.test',name='Nom autre entreprise')
    invitation = m.TeamInvitation(organization=env['org'],email='staff@example.test',role='driver',expires_at=timezone.now()+timedelta(days=2))
    request = APIRequestFactory().get('/api/v2/team',secure=True)
    send_invitation(request,invitation,'https://testserver/app?invitation=original-token')
    assert 'Bonjour,' in mail.outbox[-1].body
    assert 'Nom autre entreprise' not in mail.outbox[-1].body
    m.Employee.objects.create(organization=env['org'],email='staff@example.test',name='Aminata Diallo')
    send_invitation(request,invitation,'https://testserver/app?invitation=original-token')
    assert 'Bonjour Aminata Diallo,' in mail.outbox[-1].body

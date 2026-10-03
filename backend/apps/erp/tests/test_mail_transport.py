"""Auteur : Jonathan Kakesa Nayaba, CPI_CEO Cognito Inc."""
import json
import urllib.error
from apps.comptes import invitations


def test_resend_identifies_transitflow_and_sends_invitation(monkeypatch, settings):
    settings.TF_COURRIEL_CONFIGURE = True
    settings.TF_RESEND_CLE = 'recette-sans-cle-reelle'
    settings.TF_EMAIL_EXPEDITEUR = 'TransitFlow <noreply@example.test>'
    received = []
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
    def send(request, timeout):
        received.append(request)
        assert timeout == 15
        assert request.full_url == 'https://api.resend.com/emails'
        assert request.get_method() == 'POST'
        assert request.get_header('User-agent') == 'TransitFlow/1.0'
        assert request.get_header('Authorization') == 'Bearer recette-sans-cle-reelle'
        return Response()
    monkeypatch.setattr(invitations.urllib.request, 'urlopen', send)
    assert invitations.envoyer('personnel@example.test','Invitation','Rejoignez votre entreprise','<p>Invitation</p>')
    assert len(received) == 1
    payload = json.loads(received[0].data)
    assert payload['to'] == ['personnel@example.test']
    assert payload['from'] == settings.TF_EMAIL_EXPEDITEUR
    assert payload['text'] == 'Rejoignez votre entreprise'
    assert payload['html'] == '<p>Invitation</p>'


def test_resend_refusal_does_not_claim_email_sent(monkeypatch, settings):
    settings.TF_COURRIEL_CONFIGURE = True
    settings.TF_RESEND_CLE = 'recette-sans-cle-reelle'
    def refuse(*args, **kwargs):
        raise urllib.error.HTTPError('https://api.resend.com/emails',403,'Forbidden',{},None)
    monkeypatch.setattr(invitations.urllib.request, 'urlopen', refuse)
    assert invitations.envoyer('personnel@example.test','Invitation','Lien','') is False

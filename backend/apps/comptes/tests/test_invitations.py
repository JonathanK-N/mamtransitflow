"""TransitFlow — Invitations des chauffeurs et mot de passe oublie
   Auteur : Jonathan K-N"""

import re
from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone

from apps.comptes.models import Invitation, Utilisateur
from apps.societe.models import Entreprise
from conftest import CHAUFFEUR_VALIDE, entete_auth

MOT_DE_PASSE = 'Navette-Estrie-2026'


def creer_et_inviter(client, jeton_admin, **champs):
    donnees = dict(CHAUFFEUR_VALIDE, inviter=True, **champs)
    r = client.post('/api/chauffeurs', donnees, format='json', **entete_auth(jeton_admin))
    assert r.status_code == 201, r.data
    return r.json()


def jeton_du_lien(lien):
    return re.search(r'jeton=([\w-]+)', lien).group(1)


def test_creation_avec_invitation_envoie_le_courriel(client, jeton_admin):
    Entreprise.objects.update_or_create(pk=1, defaults={'nom': 'Navettes Estrie'})
    r = creer_et_inviter(client, jeton_admin)
    assert r['chauffeur']['acces']['etat'] == 'invite'
    assert '/invitation.html?jeton=' in r['invitation']['lien']
    # Pas de fournisseur configure dans les tests : le courriel passe par le backend local, non "envoye".
    assert r['invitation']['courrielEnvoye'] is False
    assert len(mail.outbox) == 1
    courriel = mail.outbox[0]
    assert courriel.subject == 'Rejoignez Navettes Estrie sur TransitFlow'
    assert courriel.to == ['a.diallo@transitflow.ca']
    assert r['invitation']['lien'] in courriel.body
    # Le jeton n est jamais stocke en clair.
    jeton = jeton_du_lien(r['invitation']['lien'])
    assert not Invitation.objects.filter(empreinte=jeton).exists()


def test_parcours_complet_du_chauffeur(client, jeton_admin):
    r = creer_et_inviter(client, jeton_admin)
    jeton = jeton_du_lien(r['invitation']['lien'])

    page = client.get(f'/api/invitations/{jeton}').json()
    assert page['valide'] and page['prenom'] == 'Aminata' and page['courriel'] == 'a.diallo@transitflow.ca'

    r = client.post(f'/api/invitations/{jeton}', {'motDePasse': MOT_DE_PASSE, 'confirmation': MOT_DE_PASSE},
                    format='json')
    assert r.status_code == 200, r.data
    session = r.json()
    assert session['session']['role'] == 'chauffeur' and session['accueil'] == 'chauffeur/mes-trajets.html'
    assert session['jeton']

    # Le lien ne sert qu une fois.
    assert client.get(f'/api/invitations/{jeton}').status_code == 410
    assert client.post(f'/api/invitations/{jeton}', {'motDePasse': MOT_DE_PASSE, 'confirmation': MOT_DE_PASSE},
                       format='json').status_code == 410

    # Connexion normale ensuite ; la fiche indique un acces actif.
    assert client.post('/api/auth/connexion', {'courriel': 'a.diallo@transitflow.ca', 'motDePasse': MOT_DE_PASSE},
                       format='json').status_code == 200
    fiche = client.get(f"/api/chauffeurs/{r.json()['session']['chauffeurId']}", **entete_auth(jeton_admin)).json()
    assert fiche['chauffeur']['acces']['etat'] == 'actif'


@pytest.mark.parametrize('mdp, confirmation, message', [
    ('court', 'court', 'trop court'),
    (MOT_DE_PASSE, 'Autre-chose-2026', 'pas identiques'),
    ('12345678901', '12345678901', 'entierement numerique'),
])
def test_mot_de_passe_refuse(client, jeton_admin, mdp, confirmation, message):
    jeton = jeton_du_lien(creer_et_inviter(client, jeton_admin)['invitation']['lien'])
    r = client.post(f'/api/invitations/{jeton}', {'motDePasse': mdp, 'confirmation': confirmation}, format='json')
    assert r.status_code == 400
    assert message in r.json()['message'].lower().replace('é', 'e').replace('è', 'e')
    assert client.get(f'/api/invitations/{jeton}').status_code == 200  # toujours utilisable


def test_renvoyer_remplace_l_ancien_lien(client, jeton_admin):
    r = creer_et_inviter(client, jeton_admin)
    ancien = jeton_du_lien(r['invitation']['lien'])
    code = r['chauffeur']['id']
    r2 = client.post(f'/api/chauffeurs/{code}/invitation', **entete_auth(jeton_admin))
    assert r2.status_code == 201
    assert client.get(f'/api/invitations/{ancien}').status_code == 410
    assert client.get(f"/api/invitations/{jeton_du_lien(r2.json()['lien'])}").status_code == 200


def test_revoquer_et_expiration(client, jeton_admin):
    r = creer_et_inviter(client, jeton_admin)
    jeton, code = jeton_du_lien(r['invitation']['lien']), r['chauffeur']['id']
    Invitation.objects.update(expire_le=timezone.now() - timedelta(minutes=1))
    assert client.get(f'/api/invitations/{jeton}').status_code == 410
    fiche = client.get(f'/api/chauffeurs/{code}', **entete_auth(jeton_admin)).json()['chauffeur']
    assert fiche['acces']['etat'] == 'expire'

    r2 = client.post(f'/api/chauffeurs/{code}/invitation', **entete_auth(jeton_admin)).json()
    assert client.delete(f'/api/chauffeurs/{code}/invitation', **entete_auth(jeton_admin)).status_code == 200
    assert client.get(f"/api/invitations/{jeton_du_lien(r2['lien'])}").status_code == 410


def test_invitation_refusee_si_compte_actif(client, jeton_admin):
    r = creer_et_inviter(client, jeton_admin)
    jeton, code = jeton_du_lien(r['invitation']['lien']), r['chauffeur']['id']
    client.post(f'/api/invitations/{jeton}', {'motDePasse': MOT_DE_PASSE, 'confirmation': MOT_DE_PASSE},
                format='json')
    assert client.post(f'/api/chauffeurs/{code}/invitation', **entete_auth(jeton_admin)).status_code == 409


def test_desactiver_l_acces_bloque_la_connexion(client, jeton_admin):
    r = creer_et_inviter(client, jeton_admin)
    jeton, code = jeton_du_lien(r['invitation']['lien']), r['chauffeur']['id']
    session = client.post(f'/api/invitations/{jeton}', {'motDePasse': MOT_DE_PASSE, 'confirmation': MOT_DE_PASSE},
                          format='json').json()
    r = client.post(f'/api/chauffeurs/{code}/acces', {'actif': False}, format='json', **entete_auth(jeton_admin))
    assert r.json()['chauffeur']['acces']['etat'] == 'desactive'
    assert client.post('/api/auth/connexion', {'courriel': 'a.diallo@transitflow.ca', 'motDePasse': MOT_DE_PASSE},
                       format='json').status_code == 401
    assert client.post('/api/auth/rafraichir', {'rafraichissement': session['rafraichissement']},
                       format='json').status_code == 401
    client.post(f'/api/chauffeurs/{code}/acces', {'actif': True}, format='json', **entete_auth(jeton_admin))
    assert client.post('/api/auth/connexion', {'courriel': 'a.diallo@transitflow.ca', 'motDePasse': MOT_DE_PASSE},
                       format='json').status_code == 200


def test_actions_d_invitation_reservees_a_l_admin(client, jeton_admin):
    r = creer_et_inviter(client, jeton_admin)
    code = r['chauffeur']['id']
    assert client.post(f'/api/chauffeurs/{code}/invitation').status_code == 401
    session = client.post(f"/api/invitations/{jeton_du_lien(r['invitation']['lien'])}",
                          {'motDePasse': MOT_DE_PASSE, 'confirmation': MOT_DE_PASSE}, format='json').json()
    assert client.post(f'/api/chauffeurs/{code}/acces', {'actif': False}, format='json',
                       **entete_auth(session['jeton'])).status_code == 403


def test_jeton_inconnu(client):
    assert client.get('/api/invitations/nimporte-quoi').status_code == 410


def test_mot_de_passe_oublie(client, compte_admin):
    r = client.post('/api/auth/mot-de-passe-oublie', {'courriel': 'inconnu@exemple.ca'}, format='json')
    assert r.status_code == 200 and len(mail.outbox) == 0  # meme reponse, rien d envoye

    r = client.post('/api/auth/mot-de-passe-oublie', {'courriel': 'ADMIN@transitflow.ca'}, format='json')
    assert r.status_code == 200 and len(mail.outbox) == 1
    jeton = jeton_du_lien(mail.outbox[0].body)
    assert client.get(f'/api/invitations/{jeton}').json()['type'] == 'reinitialisation'
    r = client.post(f'/api/invitations/{jeton}', {'motDePasse': MOT_DE_PASSE, 'confirmation': MOT_DE_PASSE},
                    format='json')
    assert r.status_code == 200 and r.json()['session']['role'] == 'admin'
    compte_admin.refresh_from_db()
    assert compte_admin.check_password(MOT_DE_PASSE)


def test_mot_de_passe_oublie_limite(client):
    for _ in range(5):
        client.post('/api/auth/mot-de-passe-oublie', {'courriel': 'x@exemple.ca'}, format='json')
    assert client.post('/api/auth/mot-de-passe-oublie', {'courriel': 'x@exemple.ca'},
                       format='json').status_code == 429


def test_changer_son_mot_de_passe(client, compte_admin, jeton_admin):
    r = client.post('/api/auth/mot-de-passe', {'actuel': 'mauvais', 'nouveau': MOT_DE_PASSE,
                                               'confirmation': MOT_DE_PASSE}, format='json', **entete_auth(jeton_admin))
    assert r.status_code == 400
    r = client.post('/api/auth/mot-de-passe', {'actuel': 'motdepasse123', 'nouveau': MOT_DE_PASSE,
                                               'confirmation': MOT_DE_PASSE}, format='json', **entete_auth(jeton_admin))
    assert r.status_code == 200
    compte_admin.refresh_from_db()
    assert compte_admin.check_password(MOT_DE_PASSE)
    assert Utilisateur.objects.count() == 1

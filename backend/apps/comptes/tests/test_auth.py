"""
TransitFlow — Tests de connexion (app comptes)
Auteur : Jonathan K-N

Verifie apps/comptes : connexion avec mot de passe hache, jeton JWT
valide sur /api/auth/session, et creation de comptes de connexion
(reservee a 'fleet.admin').
"""

from conftest import creer_chauffeur_avec_compte, entete_auth


def test_connexion_admin_ok(client, compte_admin):
    r = client.post('/api/auth/connexion', {'courriel': 'admin@transitflow.ca', 'motDePasse': 'motdepasse123'},
                     format='json')
    assert r.status_code == 200
    data = r.json()
    assert data['ok'] is True
    assert data['session']['role'] == 'admin'
    assert 'jeton' in data


def test_connexion_mauvais_mot_de_passe(client, compte_admin):
    r = client.post('/api/auth/connexion', {'courriel': 'admin@transitflow.ca', 'motDePasse': 'faux'},
                     format='json')
    assert r.status_code == 401


def test_connexion_courriel_inconnu(client):
    r = client.post('/api/auth/connexion', {'courriel': 'inconnu@transitflow.ca', 'motDePasse': 'x'},
                     format='json')
    assert r.status_code == 401


def test_session_necessite_jeton(client):
    r = client.get('/api/auth/session')
    assert r.status_code == 401


def test_session_avec_jeton_valide(client, compte_admin, jeton_admin):
    r = client.get('/api/auth/session', **entete_auth(jeton_admin))
    assert r.status_code == 200
    assert r.json()['session']['courriel'] == 'admin@transitflow.ca'


def test_creation_compte_reservee_admin(client, jeton_admin):
    _, jeton_chauffeur = creer_chauffeur_avec_compte(client, jeton_admin)
    r = client.post('/api/auth/comptes', {'courriel': 'x@transitflow.ca', 'motDePasse': 'x', 'groupes': []},
                     format='json', **entete_auth(jeton_chauffeur))
    assert r.status_code == 403


def test_creation_compte_lie_a_un_chauffeur(client, jeton_admin):
    fiche, jeton_chauffeur = creer_chauffeur_avec_compte(client, jeton_admin)
    r = client.get('/api/auth/session', **entete_auth(jeton_chauffeur))
    assert r.status_code == 200
    assert r.json()['session']['chauffeurId'] == fiche['id']
    assert r.json()['session']['role'] == 'chauffeur'


def test_creation_compte_groupe_inconnu(client, jeton_admin):
    r = client.post('/api/auth/comptes', {'courriel': 'x@transitflow.ca', 'motDePasse': 'x',
                                            'groupes': ['groupe-qui-n-existe-pas']},
                     format='json', **entete_auth(jeton_admin))
    assert r.status_code == 400


def test_creation_compte_courriel_deja_utilise(client, jeton_admin):
    creer_chauffeur_avec_compte(client, jeton_admin)
    r = client.post('/api/auth/comptes', {'courriel': 'a.diallo@transitflow.ca', 'motDePasse': 'x',
                                            'groupes': ['fleet.driver']}, format='json', **entete_auth(jeton_admin))
    assert r.status_code == 400

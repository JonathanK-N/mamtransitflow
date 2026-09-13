"""
TransitFlow — Tests d authentification (backend v2)
Auteur : Jonathan K-N

Verifie backend/apps/auth : connexion avec mot de passe hache (plus de mot
de passe unique 'demo'), jeton JWT valide sur /api/auth/moi, et la
creation de comptes de connexion (reservee a 'fleet.admin').
"""

from conftest import creer_admin, creer_chauffeur_avec_compte, entete_auth, jeton_pour


def test_connexion_admin_ok(client, db_session):
    creer_admin(db_session)
    r = client.post('/api/auth/connexion', json={'courriel': 'admin@transitflow.ca', 'mot_de_passe': 'motdepasse123'})
    assert r.status_code == 200
    data = r.json()
    assert data['ok'] is True
    assert data['compte']['groupes'] == ['fleet.admin']
    assert 'jeton' in data


def test_connexion_mauvais_mot_de_passe(client, db_session):
    creer_admin(db_session)
    r = client.post('/api/auth/connexion', json={'courriel': 'admin@transitflow.ca', 'mot_de_passe': 'faux'})
    assert r.status_code == 401


def test_connexion_courriel_inconnu(client):
    r = client.post('/api/auth/connexion', json={'courriel': 'inconnu@transitflow.ca', 'mot_de_passe': 'x'})
    assert r.status_code == 401


def test_moi_necessite_jeton(client):
    r = client.get('/api/auth/moi')
    assert r.status_code == 401


def test_moi_avec_jeton_valide(client, db_session):
    creer_admin(db_session)
    jeton = jeton_pour(client, 'admin@transitflow.ca')
    r = client.get('/api/auth/moi', headers=entete_auth(jeton))
    assert r.status_code == 200
    assert r.json()['courriel'] == 'admin@transitflow.ca'


def test_creation_compte_reservee_admin(client, db_session):
    _, jeton_chauffeur = creer_chauffeur_avec_compte(client, jeton_pour_admin_bootstrap(client, db_session))
    r = client.post('/api/auth/comptes', json={'courriel': 'x@transitflow.ca', 'mot_de_passe': 'x', 'groupes': []},
                     headers=entete_auth(jeton_chauffeur))
    assert r.status_code == 403


def test_creation_compte_lie_a_un_chauffeur(client, db_session):
    jeton_admin = jeton_pour_admin_bootstrap(client, db_session)
    fiche, jeton_chauffeur = creer_chauffeur_avec_compte(client, jeton_admin)
    r = client.get('/api/auth/moi', headers=entete_auth(jeton_chauffeur))
    assert r.status_code == 200
    assert r.json()['chauffeur_id'] == fiche['id']
    assert r.json()['groupes'] == ['fleet.driver']


def test_creation_compte_groupe_inconnu(client, db_session):
    jeton_admin = jeton_pour_admin_bootstrap(client, db_session)
    r = client.post('/api/auth/comptes', json={'courriel': 'x@transitflow.ca', 'mot_de_passe': 'x',
                                                 'groupes': ['groupe-qui-n-existe-pas']},
                     headers=entete_auth(jeton_admin))
    assert r.status_code == 400


def test_creation_compte_courriel_deja_utilise(client, db_session):
    jeton_admin = jeton_pour_admin_bootstrap(client, db_session)
    creer_chauffeur_avec_compte(client, jeton_admin)
    r = client.post('/api/auth/comptes', json={'courriel': 'a.diallo@transitflow.ca', 'mot_de_passe': 'x',
                                                 'groupes': ['fleet.driver']}, headers=entete_auth(jeton_admin))
    assert r.status_code == 400


def jeton_pour_admin_bootstrap(client, db_session):
    creer_admin(db_session)
    return jeton_pour(client, 'admin@transitflow.ca')

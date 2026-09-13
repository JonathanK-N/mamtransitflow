"""
TransitFlow — Tests de connexion / session
Auteur : Jonathan K-N

Verifie backend/auth.py et backend/routes/auth_routes.py : connexion
reussie (admin et chauffeur), refus (mauvais mot de passe, mauvais
role, courriel inconnu), et validite du jeton renvoye (une route
protegee doit l accepter tant qu on ne s est pas deconnecte).
"""

from conftest import connecter, creer_chauffeur, entete_auth, jeton_admin, jeton_pour


def test_connexion_admin_ok(client):
    r = connecter(client, 'a.tremblay@transitflow.ca')
    assert r.status_code == 200
    data = r.get_json()
    assert data['ok'] is True
    assert data['session']['role'] == 'admin'
    assert 'jeton' in data


def test_connexion_chauffeur_sans_fiche_associee(client):
    # Le compte existe (voir COMPTES dans backend/auth.py) mais aucune fiche
    # chauffeur d id 'c1' n a encore ete creee : le nom retombe sur "Inconnu".
    r = connecter(client, 'a.diallo@transitflow.ca', role='chauffeur')
    data = r.get_json()
    assert data['ok'] is True
    assert data['session']['nom'] == 'Inconnu'
    assert data['session']['initiales'] == '??'


def test_connexion_chauffeur_recupere_nom_depuis_la_fiche(client):
    # Le premier chauffeur cree recoit toujours l id 'c1' (voir Store.ajouter_chauffeur),
    # qui correspond justement au chauffeurId du compte 'a.diallo@transitflow.ca'.
    creer_chauffeur(client, jeton_admin(client))
    r = connecter(client, 'a.diallo@transitflow.ca', role='chauffeur')
    data = r.get_json()
    assert data['session']['nom'] == 'Aminata Diallo'
    assert data['session']['initiales'] == 'AD'


def test_connexion_mauvais_mot_de_passe(client):
    r = connecter(client, 'a.tremblay@transitflow.ca', mot_de_passe='faux')
    assert r.status_code == 401
    assert r.get_json()['ok'] is False


def test_connexion_role_incorrect(client):
    r = connecter(client, 'a.diallo@transitflow.ca', role='admin')
    assert r.status_code == 401


def test_connexion_courriel_inconnu(client):
    r = connecter(client, 'inconnu@transitflow.ca')
    assert r.status_code == 401


def test_session_necessite_jeton(client):
    r = client.get('/api/auth/session')
    assert r.status_code == 401


def test_session_valide(client):
    jeton = jeton_pour(client, 'a.tremblay@transitflow.ca')
    r = client.get('/api/auth/session', headers=entete_auth(jeton))
    assert r.status_code == 200
    assert r.get_json()['session']['courriel'] == 'a.tremblay@transitflow.ca'


def test_deconnexion_invalide_le_jeton(client):
    jeton = jeton_pour(client, 'a.tremblay@transitflow.ca')
    client.post('/api/auth/deconnexion', headers=entete_auth(jeton))
    r = client.get('/api/auth/session', headers=entete_auth(jeton))
    assert r.status_code == 401

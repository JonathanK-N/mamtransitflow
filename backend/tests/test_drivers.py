"""
TransitFlow — Tests de l app drivers (chauffeurs)
Auteur : Jonathan K-N
"""

from conftest import CHAUFFEUR_VALIDE, creer_admin, entete_auth, jeton_pour


def jeton_admin(client, db_session):
    creer_admin(db_session)
    return jeton_pour(client, 'admin@transitflow.ca')


def test_liste_necessite_authentification(client):
    r = client.get('/api/chauffeurs')
    assert r.status_code == 401


def test_creation_chauffeur(client, db_session):
    jeton = jeton_admin(client, db_session)
    r = client.post('/api/chauffeurs', json=CHAUFFEUR_VALIDE, headers=entete_auth(jeton))
    assert r.status_code == 201
    fiche = r.json()
    assert fiche['id'] == 1
    assert fiche['statut'] == 'disponible'
    assert 'cree_le' in fiche


def test_creation_champs_manquants(client, db_session):
    jeton = jeton_admin(client, db_session)
    r = client.post('/api/chauffeurs', json={'prenom': 'Julie'}, headers=entete_auth(jeton))
    assert r.status_code == 422  # erreur de validation Pydantic


def test_filtre_par_statut(client, db_session):
    jeton = jeton_admin(client, db_session)
    client.post('/api/chauffeurs', json=CHAUFFEUR_VALIDE, headers=entete_auth(jeton))
    client.post('/api/chauffeurs', json=dict(CHAUFFEUR_VALIDE, prenom='Moussa', nom='Traore',
                                              courriel='m.traore@transitflow.ca', statut='hors-service'),
                 headers=entete_auth(jeton))
    r = client.get('/api/chauffeurs?statut=hors-service', headers=entete_auth(jeton))
    data = r.json()
    assert len(data) == 1
    assert data[0]['nom'] == 'Traore'


def test_recherche_texte(client, db_session):
    jeton = jeton_admin(client, db_session)
    client.post('/api/chauffeurs', json=CHAUFFEUR_VALIDE, headers=entete_auth(jeton))
    client.post('/api/chauffeurs', json=dict(CHAUFFEUR_VALIDE, prenom='Moussa', nom='Traore',
                                              courriel='m.traore@transitflow.ca'), headers=entete_auth(jeton))
    r = client.get('/api/chauffeurs?recherche=diallo', headers=entete_auth(jeton))
    data = r.json()
    assert len(data) == 1
    assert data[0]['nom'] == 'Diallo'


def test_obtenir_chauffeur_inexistant(client, db_session):
    jeton = jeton_admin(client, db_session)
    r = client.get('/api/chauffeurs/999', headers=entete_auth(jeton))
    assert r.status_code == 404


def test_maj_partielle(client, db_session):
    jeton = jeton_admin(client, db_session)
    fiche = client.post('/api/chauffeurs', json=CHAUFFEUR_VALIDE, headers=entete_auth(jeton)).json()
    r = client.patch(f"/api/chauffeurs/{fiche['id']}", json={'statut': 'hors-service'}, headers=entete_auth(jeton))
    assert r.status_code == 200
    assert r.json()['statut'] == 'hors-service'
    assert r.json()['prenom'] == 'Aminata'  # les autres champs ne bougent pas

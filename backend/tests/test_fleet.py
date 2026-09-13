"""
TransitFlow — Tests de l app fleet (vehicules)
Auteur : Jonathan K-N
"""

from conftest import creer_admin, entete_auth, jeton_pour


def test_liste_necessite_authentification(client):
    r = client.get('/api/vehicules')
    assert r.status_code == 401


def test_liste_vide_au_depart(client, db_session):
    creer_admin(db_session)
    jeton = jeton_pour(client, 'admin@transitflow.ca')
    r = client.get('/api/vehicules', headers=entete_auth(jeton))
    assert r.status_code == 200
    assert r.json() == []


def test_creation_reservee_admin(client, db_session):
    creer_admin(db_session)
    jeton = jeton_pour(client, 'admin@transitflow.ca')
    r = client.post('/api/vehicules', json={'plaque': 'QC-4821', 'modele': 'Ford Transit 2023'},
                     headers=entete_auth(jeton))
    assert r.status_code == 201
    assert r.json()['plaque'] == 'QC-4821'


def test_creation_plaque_deja_existante(client, db_session):
    creer_admin(db_session)
    jeton = jeton_pour(client, 'admin@transitflow.ca')
    client.post('/api/vehicules', json={'plaque': 'QC-4821', 'modele': 'Ford Transit'}, headers=entete_auth(jeton))
    r = client.post('/api/vehicules', json={'plaque': 'QC-4821', 'modele': 'Autre'}, headers=entete_auth(jeton))
    assert r.status_code == 400

"""
TransitFlow — Tests de l app fleet (vehicules)
Auteur : Jonathan K-N
"""

from conftest import entete_auth


def test_liste_necessite_authentification(client):
    r = client.get('/api/vehicules')
    assert r.status_code == 401


def test_liste_vide_au_depart(client, jeton_admin):
    r = client.get('/api/vehicules', **entete_auth(jeton_admin))
    assert r.status_code == 200
    assert r.json()['vehicules'] == []


def test_creation_reservee_admin(client, jeton_admin):
    from conftest import creer_chauffeur_avec_compte
    _, jeton_chauffeur = creer_chauffeur_avec_compte(client, jeton_admin)
    r = client.post('/api/vehicules', {'plaque': 'QC-4821', 'modele': 'Ford Transit'}, format='json',
                     **entete_auth(jeton_chauffeur))
    assert r.status_code == 403


def test_creation_vehicule(client, jeton_admin):
    r = client.post('/api/vehicules', {'plaque': 'QC-4821', 'modele': 'Ford Transit 2023'}, format='json',
                     **entete_auth(jeton_admin))
    assert r.status_code == 201
    assert r.json()['vehicule']['plaque'] == 'QC-4821'


def test_creation_plaque_deja_existante(client, jeton_admin):
    client.post('/api/vehicules', {'plaque': 'QC-4821', 'modele': 'Ford Transit'}, format='json',
                **entete_auth(jeton_admin))
    r = client.post('/api/vehicules', {'plaque': 'QC-4821', 'modele': 'Autre'}, format='json',
                     **entete_auth(jeton_admin))
    assert r.status_code == 400

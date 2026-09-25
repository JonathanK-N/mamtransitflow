"""
TransitFlow — Tests de l app dispatch (trajets, arrets)
Auteur : Jonathan K-N
"""

import re

import pytest

from apps.fleet.models import Vehicule
from conftest import creer_chauffeur_avec_compte, entete_auth

TRAJET_VALIDE = {'plaque': 'QC-4821', 'depart': 'Sherbrooke', 'arrivee': 'Magog',
                  'debut': '2026-09-12T07:30:00Z', 'finPrevue': '2026-09-12T08:45:00Z'}


@pytest.fixture(autouse=True)
def _vehicule(db):
    """La plaque d un trajet doit correspondre a un vehicule de la flotte."""
    Vehicule.objects.create(plaque='QC-4821', modele='Ford Transit 2023')


def _deux_chauffeurs(client, jeton_admin):
    fiche1, jeton1 = creer_chauffeur_avec_compte(client, jeton_admin)
    fiche2, jeton2 = creer_chauffeur_avec_compte(client, jeton_admin, courriel='m.traore@transitflow.ca',
                                                  prenom='Moussa', nom='Traore')
    return (fiche1, jeton1), (fiche2, jeton2)


def test_creation_reservee_chauffeur(client, jeton_admin):
    r = client.post('/api/trajets', TRAJET_VALIDE, format='json', **entete_auth(jeton_admin))
    assert r.status_code == 403


def test_creation_trajet_et_maj_chauffeur(client, jeton_admin):
    fiche, jeton = creer_chauffeur_avec_compte(client, jeton_admin)

    r = client.post('/api/trajets', TRAJET_VALIDE, format='json', **entete_auth(jeton))
    assert r.status_code == 201
    trajet = r.json()['trajet']
    assert re.fullmatch(r'T-\d+', trajet['id'])
    assert trajet['statut'] == 'en-cours'
    assert trajet['chauffeurId'] == fiche['id']
    assert trajet['arrets'] == []

    r = client.get(f"/api/chauffeurs/{fiche['id']}", **entete_auth(jeton_admin))
    assert r.json()['chauffeur']['statut'] == 'en-trajet'


def test_un_seul_trajet_en_cours(client, jeton_admin):
    _, jeton = creer_chauffeur_avec_compte(client, jeton_admin)
    assert client.post('/api/trajets', TRAJET_VALIDE, format='json', **entete_auth(jeton)).status_code == 201
    assert client.post('/api/trajets', TRAJET_VALIDE, format='json', **entete_auth(jeton)).status_code == 409


def test_creation_plaque_inconnue(client, jeton_admin):
    _, jeton = creer_chauffeur_avec_compte(client, jeton_admin)
    r = client.post('/api/trajets', dict(TRAJET_VALIDE, plaque='QC-0000'), format='json', **entete_auth(jeton))
    assert r.status_code == 400


def test_creation_arrivee_avant_depart(client, jeton_admin):
    _, jeton = creer_chauffeur_avec_compte(client, jeton_admin)
    r = client.post('/api/trajets', dict(TRAJET_VALIDE, finPrevue='2026-09-12T07:00:00Z'), format='json',
                     **entete_auth(jeton))
    assert r.status_code == 400


def test_ajouter_arret_puis_terminer(client, jeton_admin):
    fiche, jeton = creer_chauffeur_avec_compte(client, jeton_admin)
    trajet = client.post('/api/trajets', TRAJET_VALIDE, format='json', **entete_auth(jeton)).json()['trajet']

    r = client.post(f"/api/trajets/{trajet['id']}/arrets", {'lieu': 'Rock Forest', 'heure': '07:52', 'note': ''},
                     format='json', **entete_auth(jeton))
    assert r.status_code == 200
    assert len(r.json()['trajet']['arrets']) == 1
    assert r.json()['trajet']['arrets'][0]['heure'] == '07:52'

    r = client.post(f"/api/trajets/{trajet['id']}/terminer", **entete_auth(jeton))
    assert r.status_code == 200
    assert r.json()['trajet']['statut'] == 'termine'
    assert r.json()['trajet']['fin'] is not None

    r = client.get(f"/api/chauffeurs/{fiche['id']}", **entete_auth(jeton_admin))
    assert r.json()['chauffeur']['statut'] == 'disponible'

    # Un trajet termine ne se termine pas deux fois et n accepte plus d arret.
    assert client.post(f"/api/trajets/{trajet['id']}/terminer", **entete_auth(jeton)).status_code == 400
    r = client.post(f"/api/trajets/{trajet['id']}/arrets", {'lieu': 'x', 'heure': '09:00'}, format='json',
                     **entete_auth(jeton))
    assert r.status_code == 400


def test_arret_heure_invalide(client, jeton_admin):
    _, jeton = creer_chauffeur_avec_compte(client, jeton_admin)
    trajet = client.post('/api/trajets', TRAJET_VALIDE, format='json', **entete_auth(jeton)).json()['trajet']
    r = client.post(f"/api/trajets/{trajet['id']}/arrets", {'lieu': 'x', 'heure': '7h52'}, format='json',
                     **entete_auth(jeton))
    assert r.status_code == 400


def test_admin_peut_terminer_un_trajet(client, jeton_admin):
    _, jeton = creer_chauffeur_avec_compte(client, jeton_admin)
    trajet = client.post('/api/trajets', TRAJET_VALIDE, format='json', **entete_auth(jeton)).json()['trajet']
    r = client.post(f"/api/trajets/{trajet['id']}/terminer", **entete_auth(jeton_admin))
    assert r.status_code == 200


def test_arret_refuse_pour_autre_chauffeur(client, jeton_admin):
    (_, jeton1), (_, jeton2) = _deux_chauffeurs(client, jeton_admin)
    trajet = client.post('/api/trajets', TRAJET_VALIDE, format='json', **entete_auth(jeton1)).json()['trajet']
    r = client.post(f"/api/trajets/{trajet['id']}/arrets", {'lieu': 'x', 'heure': '08:00'}, format='json',
                     **entete_auth(jeton2))
    assert r.status_code == 403
    assert client.post(f"/api/trajets/{trajet['id']}/terminer", **entete_auth(jeton2)).status_code == 403


def test_chauffeur_ne_voit_que_ses_trajets(client, jeton_admin):
    (fiche1, jeton1), (_, jeton2) = _deux_chauffeurs(client, jeton_admin)
    trajet = client.post('/api/trajets', TRAJET_VALIDE, format='json', **entete_auth(jeton1)).json()['trajet']

    assert client.get('/api/trajets', **entete_auth(jeton2)).json()['trajets'] == []
    assert client.get(f"/api/trajets/{trajet['id']}", **entete_auth(jeton2)).status_code == 404
    assert client.get(f"/api/trajets/en-cours/{fiche1['id']}", **entete_auth(jeton2)).json()['trajet'] is None
    assert len(client.get('/api/trajets', **entete_auth(jeton1)).json()['trajets']) == 1


def test_trajet_en_cours(client, jeton_admin):
    fiche, jeton = creer_chauffeur_avec_compte(client, jeton_admin)
    assert client.get(f"/api/trajets/en-cours/{fiche['id']}", **entete_auth(jeton_admin)).json()['trajet'] is None
    trajet = client.post('/api/trajets', TRAJET_VALIDE, format='json', **entete_auth(jeton)).json()['trajet']
    r = client.get(f"/api/trajets/en-cours/{fiche['id']}", **entete_auth(jeton_admin))
    assert r.json()['trajet']['id'] == trajet['id']


def test_liste_filtre_par_chauffeur(client, jeton_admin):
    fiche, jeton = creer_chauffeur_avec_compte(client, jeton_admin)
    client.post('/api/trajets', TRAJET_VALIDE, format='json', **entete_auth(jeton))
    r = client.get(f"/api/trajets?chauffeurId={fiche['id']}", **entete_auth(jeton_admin))
    assert len(r.json()['trajets']) == 1

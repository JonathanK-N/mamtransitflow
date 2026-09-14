"""
TransitFlow — Tests de l app dispatch (trajets, arrets)
Auteur : Jonathan K-N
"""

from conftest import creer_chauffeur_avec_compte, entete_auth

TRAJET_VALIDE = {'plaque': 'QC-4821', 'depart': 'Sherbrooke', 'arrivee': 'Magog',
                  'debut': '2026-09-12T07:30:00Z', 'finPrevue': '2026-09-12T08:45:00Z'}


def test_creation_reservee_chauffeur(client, jeton_admin):
    r = client.post('/api/trajets', TRAJET_VALIDE, format='json', **entete_auth(jeton_admin))
    assert r.status_code == 403


def test_creation_trajet_et_maj_chauffeur(client, jeton_admin):
    fiche, jeton = creer_chauffeur_avec_compte(client, jeton_admin)

    r = client.post('/api/trajets', TRAJET_VALIDE, format='json', **entete_auth(jeton))
    assert r.status_code == 201
    trajet = r.json()['trajet']
    assert trajet['id'] == 'T-1'
    assert trajet['statut'] == 'en-cours'
    assert trajet['chauffeurId'] == fiche['id']
    assert trajet['arrets'] == []

    r = client.get(f"/api/chauffeurs/{fiche['id']}", **entete_auth(jeton_admin))
    assert r.json()['chauffeur']['statut'] == 'en-trajet'


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


def test_arret_refuse_pour_autre_chauffeur(client, jeton_admin):
    _, jeton1 = creer_chauffeur_avec_compte(client, jeton_admin)
    trajet = client.post('/api/trajets', TRAJET_VALIDE, format='json', **entete_auth(jeton1)).json()['trajet']

    _, jeton2 = creer_chauffeur_avec_compte(client, jeton_admin, courriel='m.traore@transitflow.ca',
                                              prenom='Moussa', nom='Traore')
    r = client.post(f"/api/trajets/{trajet['id']}/arrets", {'lieu': 'x', 'heure': '08:00'}, format='json',
                     **entete_auth(jeton2))
    assert r.status_code == 403


def test_trajet_en_cours(client, jeton_admin):
    fiche, jeton = creer_chauffeur_avec_compte(client, jeton_admin)
    assert client.get(f"/api/trajets/en-cours/{fiche['id']}", **entete_auth(jeton_admin)).json()['trajet'] is None
    client.post('/api/trajets', TRAJET_VALIDE, format='json', **entete_auth(jeton))
    r = client.get(f"/api/trajets/en-cours/{fiche['id']}", **entete_auth(jeton_admin))
    assert r.json()['trajet']['id'] == 'T-1'


def test_liste_filtre_par_chauffeur(client, jeton_admin):
    fiche, jeton = creer_chauffeur_avec_compte(client, jeton_admin)
    client.post('/api/trajets', TRAJET_VALIDE, format='json', **entete_auth(jeton))
    r = client.get(f"/api/trajets?chauffeurId={fiche['id']}", **entete_auth(jeton_admin))
    assert len(r.json()['trajets']) == 1

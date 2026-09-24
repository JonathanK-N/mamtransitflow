"""
TransitFlow — Tests de l app maintenance (incidents)
Auteur : Jonathan K-N
"""

from conftest import creer_chauffeur_avec_compte, entete_auth

INCIDENT_VALIDE = {'type': 'technique', 'titre': 'Panne', 'description': 'x', 'lieu': 'x', 'heure': '09:00'}


def test_creation_reservee_chauffeur(client, jeton_admin):
    r = client.post('/api/incidents', INCIDENT_VALIDE, format='json', **entete_auth(jeton_admin))
    assert r.status_code == 403


def test_creation_incident_sans_trajet(client, jeton_admin):
    fiche, jeton = creer_chauffeur_avec_compte(client, jeton_admin)
    r = client.post('/api/incidents', INCIDENT_VALIDE, format='json', **entete_auth(jeton))
    assert r.status_code == 201
    incident = r.json()['incident']
    assert incident['statut'] == 'ouvert'
    assert incident['chauffeurId'] == fiche['id']
    assert incident['trajetId'] is None


def test_creation_incident_type_invalide(client, jeton_admin):
    _, jeton = creer_chauffeur_avec_compte(client, jeton_admin)
    r = client.post('/api/incidents', dict(INCIDENT_VALIDE, type='autre'), format='json', **entete_auth(jeton))
    assert r.status_code == 400


def test_creation_incident_trajet_inexistant(client, jeton_admin):
    _, jeton = creer_chauffeur_avec_compte(client, jeton_admin)
    r = client.post('/api/incidents', dict(INCIDENT_VALIDE, trajetId='T-999'), format='json',
                     **entete_auth(jeton))
    assert r.status_code == 404


def test_traiter_reserve_admin(client, jeton_admin):
    _, jeton = creer_chauffeur_avec_compte(client, jeton_admin)
    incident = client.post('/api/incidents', INCIDENT_VALIDE, format='json', **entete_auth(jeton)).json()['incident']
    r = client.post(f"/api/incidents/{incident['id']}/traiter", **entete_auth(jeton))
    assert r.status_code == 403


def test_traiter_incident(client, jeton_admin):
    _, jeton = creer_chauffeur_avec_compte(client, jeton_admin)
    incident = client.post('/api/incidents', INCIDENT_VALIDE, format='json', **entete_auth(jeton)).json()['incident']
    r = client.post(f"/api/incidents/{incident['id']}/traiter", **entete_auth(jeton_admin))
    assert r.status_code == 200
    assert r.json()['incident']['statut'] == 'traite'


def test_filtre_par_statut(client, jeton_admin):
    _, jeton = creer_chauffeur_avec_compte(client, jeton_admin)
    incident = client.post('/api/incidents', INCIDENT_VALIDE, format='json', **entete_auth(jeton)).json()['incident']
    client.post(f"/api/incidents/{incident['id']}/traiter", **entete_auth(jeton_admin))

    assert client.get('/api/incidents?statut=ouvert', **entete_auth(jeton_admin)).json()['incidents'] == []
    assert len(client.get('/api/incidents?statut=traite', **entete_auth(jeton_admin)).json()['incidents']) == 1


def test_creation_heure_invalide(client, jeton_admin):
    _, jeton = creer_chauffeur_avec_compte(client, jeton_admin)
    r = client.post('/api/incidents', dict(INCIDENT_VALIDE, heure='25:00'), format='json', **entete_auth(jeton))
    assert r.status_code == 400


def test_cloisonnement_entre_chauffeurs(client, jeton_admin):
    from apps.fleet.models import Vehicule

    Vehicule.objects.create(plaque='QC-4821', modele='Ford Transit 2023')
    _, jeton1 = creer_chauffeur_avec_compte(client, jeton_admin)
    _, jeton2 = creer_chauffeur_avec_compte(client, jeton_admin, courriel='m.traore@transitflow.ca',
                                              prenom='Moussa', nom='Traore')
    trajet = client.post('/api/trajets', {'plaque': 'QC-4821', 'depart': 'A', 'arrivee': 'B',
                                          'debut': '2026-09-12T07:30:00Z', 'finPrevue': '2026-09-12T08:45:00Z'},
                         format='json', **entete_auth(jeton1)).json()['trajet']
    incident = client.post('/api/incidents', INCIDENT_VALIDE, format='json', **entete_auth(jeton1)).json()['incident']

    # Le chauffeur 2 ne voit pas l incident du chauffeur 1...
    assert client.get('/api/incidents', **entete_auth(jeton2)).json()['incidents'] == []
    assert client.get(f"/api/incidents/{incident['id']}", **entete_auth(jeton2)).status_code == 404
    # ... et ne peut pas rattacher un incident au trajet d un autre.
    r = client.post('/api/incidents', dict(INCIDENT_VALIDE, trajetId=trajet['id']), format='json',
                     **entete_auth(jeton2))
    assert r.status_code == 404
    # L administrateur voit tout.
    assert len(client.get('/api/incidents', **entete_auth(jeton_admin)).json()['incidents']) == 1

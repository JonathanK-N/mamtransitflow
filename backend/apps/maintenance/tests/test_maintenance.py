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

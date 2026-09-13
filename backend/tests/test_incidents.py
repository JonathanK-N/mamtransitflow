from conftest import entete_auth, jeton_pour


def test_liste_incidents_filtre_statut(client):
    jeton = jeton_pour(client, 'a.tremblay@transitflow.ca')
    r = client.get('/api/incidents?statut=ouvert', headers=entete_auth(jeton))
    data = r.get_json()['incidents']
    assert len(data) == 1
    assert all(i['statut'] == 'ouvert' for i in data)


def test_obtenir_incident_inexistant(client):
    jeton = jeton_pour(client, 'a.tremblay@transitflow.ca')
    r = client.get('/api/incidents/I-999', headers=entete_auth(jeton))
    assert r.status_code == 404


def test_creation_incident_par_chauffeur(client):
    jeton = jeton_pour(client, 's.fortin@transitflow.ca', role='chauffeur')
    payload = {'trajetId': 'T-2093', 'type': 'route', 'titre': 'Embouteillage',
               'description': 'Circulation ralentie.', 'lieu': 'Autoroute 10', 'heure': '09:40'}
    r = client.post('/api/incidents', json=payload, headers=entete_auth(jeton))
    assert r.status_code == 201
    incident = r.get_json()['incident']
    assert incident['id'] == 'I-3'
    assert incident['statut'] == 'ouvert'
    assert incident['chauffeurId'] == 'c3'
    assert incident['date'] == '2026-09-12'


def test_creation_incident_type_invalide(client):
    jeton = jeton_pour(client, 's.fortin@transitflow.ca', role='chauffeur')
    payload = {'type': 'autre', 'titre': 'x', 'description': 'x', 'lieu': 'x', 'heure': '09:00'}
    r = client.post('/api/incidents', json=payload, headers=entete_auth(jeton))
    assert r.status_code == 400


def test_creation_incident_trajet_inexistant(client):
    jeton = jeton_pour(client, 's.fortin@transitflow.ca', role='chauffeur')
    payload = {'trajetId': 'T-9999', 'type': 'route', 'titre': 'x',
               'description': 'x', 'lieu': 'x', 'heure': '09:00'}
    r = client.post('/api/incidents', json=payload, headers=entete_auth(jeton))
    assert r.status_code == 404


def test_traiter_incident_reserve_admin(client):
    jeton = jeton_pour(client, 's.fortin@transitflow.ca', role='chauffeur')
    r = client.post('/api/incidents/I-1/traiter', headers=entete_auth(jeton))
    assert r.status_code == 403


def test_traiter_incident(client):
    jeton = jeton_pour(client, 'a.tremblay@transitflow.ca')
    r = client.post('/api/incidents/I-1/traiter', headers=entete_auth(jeton))
    assert r.status_code == 200
    assert r.get_json()['incident']['statut'] == 'traite'


def test_traiter_incident_inexistant(client):
    jeton = jeton_pour(client, 'a.tremblay@transitflow.ca')
    r = client.post('/api/incidents/I-999/traiter', headers=entete_auth(jeton))
    assert r.status_code == 404

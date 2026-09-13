"""
TransitFlow — Tests des routes incidents
Auteur : Jonathan K-N

Verifie backend/routes/incidents_routes.py : signalement d un incident
par un chauffeur (avec ou sans trajet associe, validation du type),
et le fait de le marquer "traite" est reserve a l administrateur.
"""

from conftest import creer_chauffeur, entete_auth, jeton_admin, jeton_pour

TRAJET_VALIDE = {'plaque': 'QC-4821', 'depart': 'Sherbrooke', 'arrivee': 'Magog',
                  'debut': '2026-09-12T07:30', 'finPrevue': '2026-09-12T08:45'}


def _chauffeur_et_jeton(client, **champs):
    """Cree un chauffeur (admin requis) puis se connecte avec son compte : renvoie (chauffeur, jeton)."""
    admin = jeton_admin(client)
    chauffeur = creer_chauffeur(client, admin, **champs)
    jeton = jeton_pour(client, chauffeur['courriel'], role='chauffeur')
    return chauffeur, jeton


def test_liste_vide_au_depart(client):
    jeton = jeton_admin(client)
    r = client.get('/api/incidents', headers=entete_auth(jeton))
    assert r.get_json()['incidents'] == []


def test_obtenir_incident_inexistant(client):
    jeton = jeton_admin(client)
    r = client.get('/api/incidents/I-999', headers=entete_auth(jeton))
    assert r.status_code == 404


def test_creation_reservee_chauffeur(client):
    jeton = jeton_admin(client)
    r = client.post('/api/incidents', json={'type': 'route', 'titre': 'x', 'description': 'x',
                                              'lieu': 'x', 'heure': '09:00'}, headers=entete_auth(jeton))
    assert r.status_code == 403


def test_creation_incident_par_chauffeur(client):
    chauffeur, jeton = _chauffeur_et_jeton(client)
    trajet = client.post('/api/trajets', json=TRAJET_VALIDE, headers=entete_auth(jeton)).get_json()['trajet']

    payload = {'trajetId': trajet['id'], 'type': 'route', 'titre': 'Embouteillage',
               'description': 'Circulation ralentie.', 'lieu': 'Autoroute 10', 'heure': '09:40'}
    r = client.post('/api/incidents', json=payload, headers=entete_auth(jeton))
    assert r.status_code == 201
    incident = r.get_json()['incident']
    assert incident['id'] == 'I-1'
    assert incident['statut'] == 'ouvert'
    assert incident['chauffeurId'] == chauffeur['id']
    assert incident['date'] == '2026-09-12'


def test_creation_incident_sans_trajet(client):
    _, jeton = _chauffeur_et_jeton(client)
    payload = {'type': 'technique', 'titre': 'Panne', 'description': 'x', 'lieu': 'x', 'heure': '09:00'}
    r = client.post('/api/incidents', json=payload, headers=entete_auth(jeton))
    assert r.status_code == 201
    assert r.get_json()['incident']['trajetId'] is None


def test_creation_incident_type_invalide(client):
    _, jeton = _chauffeur_et_jeton(client)
    payload = {'type': 'autre', 'titre': 'x', 'description': 'x', 'lieu': 'x', 'heure': '09:00'}
    r = client.post('/api/incidents', json=payload, headers=entete_auth(jeton))
    assert r.status_code == 400


def test_creation_incident_trajet_inexistant(client):
    _, jeton = _chauffeur_et_jeton(client)
    payload = {'trajetId': 'T-9999', 'type': 'route', 'titre': 'x', 'description': 'x',
               'lieu': 'x', 'heure': '09:00'}
    r = client.post('/api/incidents', json=payload, headers=entete_auth(jeton))
    assert r.status_code == 404


def test_traiter_incident_reserve_admin(client):
    _, jeton = _chauffeur_et_jeton(client)
    r = client.post('/api/incidents/I-1/traiter', headers=entete_auth(jeton))
    assert r.status_code == 403


def test_traiter_incident(client):
    _, jeton = _chauffeur_et_jeton(client)
    payload = {'type': 'technique', 'titre': 'Panne', 'description': 'x', 'lieu': 'x', 'heure': '09:00'}
    incident = client.post('/api/incidents', json=payload, headers=entete_auth(jeton)).get_json()['incident']

    admin = jeton_admin(client)
    r = client.post('/api/incidents/' + incident['id'] + '/traiter', headers=entete_auth(admin))
    assert r.status_code == 200
    assert r.get_json()['incident']['statut'] == 'traite'


def test_traiter_incident_inexistant(client):
    jeton = jeton_admin(client)
    r = client.post('/api/incidents/I-999/traiter', headers=entete_auth(jeton))
    assert r.status_code == 404


def test_filtre_par_statut(client):
    _, jeton = _chauffeur_et_jeton(client)
    payload = {'type': 'technique', 'titre': 'Panne', 'description': 'x', 'lieu': 'x', 'heure': '09:00'}
    incident = client.post('/api/incidents', json=payload, headers=entete_auth(jeton)).get_json()['incident']
    admin = jeton_admin(client)
    client.post('/api/incidents/' + incident['id'] + '/traiter', headers=entete_auth(admin))

    r = client.get('/api/incidents?statut=ouvert', headers=entete_auth(admin))
    assert r.get_json()['incidents'] == []
    r = client.get('/api/incidents?statut=traite', headers=entete_auth(admin))
    assert len(r.get_json()['incidents']) == 1

"""
TransitFlow — Tests de l app maintenance (incidents)
Auteur : Jonathan K-N
"""

from conftest import creer_admin, creer_chauffeur_avec_compte, entete_auth, jeton_pour

INCIDENT_VALIDE = {'type': 'technique', 'titre': 'Panne', 'description': 'x', 'lieu': 'x',
                    'horodatage': '2026-09-12T09:00:00Z'}


def jeton_admin(client, db_session):
    creer_admin(db_session)
    return jeton_pour(client, 'admin@transitflow.ca')


def test_creation_reservee_chauffeur(client, db_session):
    jeton = jeton_admin(client, db_session)
    r = client.post('/api/incidents', json=INCIDENT_VALIDE, headers=entete_auth(jeton))
    assert r.status_code == 403


def test_creation_incident_sans_trajet(client, db_session):
    admin = jeton_admin(client, db_session)
    fiche, jeton = creer_chauffeur_avec_compte(client, admin)
    r = client.post('/api/incidents', json=INCIDENT_VALIDE, headers=entete_auth(jeton))
    assert r.status_code == 201
    incident = r.json()
    assert incident['statut'] == 'ouvert'
    assert incident['chauffeur_id'] == fiche['id']
    assert incident['trajet_id'] is None


def test_creation_incident_type_invalide(client, db_session):
    admin = jeton_admin(client, db_session)
    _, jeton = creer_chauffeur_avec_compte(client, admin)
    r = client.post('/api/incidents', json=dict(INCIDENT_VALIDE, type='autre'), headers=entete_auth(jeton))
    assert r.status_code == 422


def test_creation_incident_trajet_inexistant(client, db_session):
    admin = jeton_admin(client, db_session)
    _, jeton = creer_chauffeur_avec_compte(client, admin)
    r = client.post('/api/incidents', json=dict(INCIDENT_VALIDE, trajet_id=999), headers=entete_auth(jeton))
    assert r.status_code == 404


def test_traiter_reserve_admin(client, db_session):
    admin = jeton_admin(client, db_session)
    _, jeton = creer_chauffeur_avec_compte(client, admin)
    incident = client.post('/api/incidents', json=INCIDENT_VALIDE, headers=entete_auth(jeton)).json()
    r = client.post(f"/api/incidents/{incident['id']}/traiter", headers=entete_auth(jeton))
    assert r.status_code == 403


def test_traiter_incident(client, db_session):
    admin = jeton_admin(client, db_session)
    _, jeton = creer_chauffeur_avec_compte(client, admin)
    incident = client.post('/api/incidents', json=INCIDENT_VALIDE, headers=entete_auth(jeton)).json()
    r = client.post(f"/api/incidents/{incident['id']}/traiter", headers=entete_auth(admin))
    assert r.status_code == 200
    assert r.json()['statut'] == 'traite'


def test_filtre_par_statut(client, db_session):
    admin = jeton_admin(client, db_session)
    _, jeton = creer_chauffeur_avec_compte(client, admin)
    incident = client.post('/api/incidents', json=INCIDENT_VALIDE, headers=entete_auth(jeton)).json()
    client.post(f"/api/incidents/{incident['id']}/traiter", headers=entete_auth(admin))

    assert client.get('/api/incidents?statut=ouvert', headers=entete_auth(admin)).json() == []
    assert len(client.get('/api/incidents?statut=traite', headers=entete_auth(admin)).json()) == 1

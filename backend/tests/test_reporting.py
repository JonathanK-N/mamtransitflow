"""
TransitFlow — Tests de l app reporting (indicateurs)
Auteur : Jonathan K-N
"""

from conftest import creer_admin, creer_chauffeur_avec_compte, entete_auth, jeton_pour


def jeton_admin(client, db_session):
    creer_admin(db_session)
    return jeton_pour(client, 'admin@transitflow.ca')


def test_indicateurs_reserve_admin(client, db_session):
    admin = jeton_admin(client, db_session)
    _, jeton = creer_chauffeur_avec_compte(client, admin)
    r = client.get('/api/indicateurs', headers=entete_auth(jeton))
    assert r.status_code == 403


def test_indicateurs_valeurs(client, db_session):
    admin = jeton_admin(client, db_session)
    fiche1, jeton1 = creer_chauffeur_avec_compte(client, admin, permis_expiration='2026-10-05')
    creer_chauffeur_avec_compte(client, admin, courriel='m.traore@transitflow.ca', prenom='Moussa', nom='Traore',
                                 permis_expiration='2028-01-01', statut='hors-service')

    trajet = client.post('/api/trajets', json={
        'plaque': 'QC-4821', 'depart': 'Sherbrooke', 'arrivee': 'Magog',
        'debut': '2026-09-12T07:30:00Z', 'fin_prevue': '2026-09-12T08:45:00Z'
    }, headers=entete_auth(jeton1)).json()
    client.post('/api/incidents', json={
        'trajet_id': trajet['id'], 'type': 'route', 'titre': 'x', 'description': 'x', 'lieu': 'x',
        'horodatage': '2026-09-12T09:00:00Z'
    }, headers=entete_auth(jeton1))

    r = client.get('/api/indicateurs', headers=entete_auth(admin))
    assert r.status_code == 200
    k = r.json()
    assert k['chauffeurs_actifs'] == 1  # le 2e est 'hors-service'
    assert k['trajets_en_cours'] == 1
    assert k['incidents_ouverts'] == 1
    assert k['permis_a_expirer'] == 1  # 2026-10-05 est dans les 60 jours, 2028-01-01 non


def test_sante(client):
    r = client.get('/api/sante')
    assert r.status_code == 200
    assert r.json()['ok'] is True

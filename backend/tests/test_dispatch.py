"""
TransitFlow — Tests de l app dispatch (trajets, arrets)
Auteur : Jonathan K-N
"""

from conftest import creer_admin, creer_chauffeur_avec_compte, entete_auth, jeton_pour

TRAJET_VALIDE = {'plaque': 'QC-4821', 'depart': 'Sherbrooke', 'arrivee': 'Magog',
                  'debut': '2026-09-12T07:30:00Z', 'fin_prevue': '2026-09-12T08:45:00Z'}


def jeton_admin(client, db_session):
    creer_admin(db_session)
    return jeton_pour(client, 'admin@transitflow.ca')


def test_creation_reservee_chauffeur(client, db_session):
    jeton = jeton_admin(client, db_session)
    r = client.post('/api/trajets', json=TRAJET_VALIDE, headers=entete_auth(jeton))
    assert r.status_code == 403


def test_creation_trajet_et_maj_chauffeur(client, db_session):
    admin = jeton_admin(client, db_session)
    fiche, jeton = creer_chauffeur_avec_compte(client, admin)

    r = client.post('/api/trajets', json=TRAJET_VALIDE, headers=entete_auth(jeton))
    assert r.status_code == 201
    trajet = r.json()
    assert trajet['code'] == 'T-1'
    assert trajet['statut'] == 'en-cours'
    assert trajet['chauffeur_id'] == fiche['id']
    assert trajet['arrets'] == []

    r = client.get(f"/api/chauffeurs/{fiche['id']}", headers=entete_auth(admin))
    assert r.json()['statut'] == 'en-trajet'


def test_ajouter_arret_puis_terminer(client, db_session):
    admin = jeton_admin(client, db_session)
    fiche, jeton = creer_chauffeur_avec_compte(client, admin)
    trajet = client.post('/api/trajets', json=TRAJET_VALIDE, headers=entete_auth(jeton)).json()

    r = client.post(f"/api/trajets/{trajet['id']}/arrets",
                     json={'lieu': 'Rock Forest', 'heure': '2026-09-12T07:52:00Z', 'note': ''},
                     headers=entete_auth(jeton))
    assert r.status_code == 200
    assert len(r.json()['arrets']) == 1

    r = client.post(f"/api/trajets/{trajet['id']}/terminer", headers=entete_auth(jeton))
    assert r.status_code == 200
    assert r.json()['statut'] == 'termine'
    assert r.json()['fin'] is not None

    r = client.get(f"/api/chauffeurs/{fiche['id']}", headers=entete_auth(admin))
    assert r.json()['statut'] == 'disponible'


def test_arret_refuse_pour_autre_chauffeur(client, db_session):
    admin = jeton_admin(client, db_session)
    _, jeton1 = creer_chauffeur_avec_compte(client, admin)
    trajet = client.post('/api/trajets', json=TRAJET_VALIDE, headers=entete_auth(jeton1)).json()

    _, jeton2 = creer_chauffeur_avec_compte(client, admin, courriel='m.traore@transitflow.ca',
                                             prenom='Moussa', nom='Traore')
    r = client.post(f"/api/trajets/{trajet['id']}/arrets", json={'lieu': 'x', 'heure': '2026-09-12T08:00:00Z'},
                     headers=entete_auth(jeton2))
    assert r.status_code == 403


def test_trajet_en_cours(client, db_session):
    admin = jeton_admin(client, db_session)
    fiche, jeton = creer_chauffeur_avec_compte(client, admin)
    assert client.get(f"/api/trajets/en-cours/{fiche['id']}", headers=entete_auth(admin)).json() is None
    client.post('/api/trajets', json=TRAJET_VALIDE, headers=entete_auth(jeton))
    r = client.get(f"/api/trajets/en-cours/{fiche['id']}", headers=entete_auth(admin))
    assert r.json()['code'] == 'T-1'

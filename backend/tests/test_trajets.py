from conftest import entete_auth, jeton_pour


def test_liste_trajets_tri_desc(client):
    jeton = jeton_pour(client, 'a.tremblay@transitflow.ca')
    r = client.get('/api/trajets', headers=entete_auth(jeton))
    debuts = [t['debut'] for t in r.get_json()['trajets']]
    assert debuts == sorted(debuts, reverse=True)


def test_trajet_en_cours(client):
    jeton = jeton_pour(client, 'a.tremblay@transitflow.ca')
    r = client.get('/api/trajets/en-cours/c2', headers=entete_auth(jeton))
    assert r.get_json()['trajet']['id'] == 'T-2091'


def test_trajet_en_cours_absent(client):
    jeton = jeton_pour(client, 'a.tremblay@transitflow.ca')
    r = client.get('/api/trajets/en-cours/c3', headers=entete_auth(jeton))
    assert r.get_json()['trajet'] is None


def test_obtenir_trajet_inexistant(client):
    jeton = jeton_pour(client, 'a.tremblay@transitflow.ca')
    r = client.get('/api/trajets/T-9999', headers=entete_auth(jeton))
    assert r.status_code == 404


def test_creation_reservee_chauffeur(client):
    jeton = jeton_pour(client, 'a.tremblay@transitflow.ca')
    r = client.post('/api/trajets', json={}, headers=entete_auth(jeton))
    assert r.status_code == 403


def test_creation_trajet_incremente_id_et_met_a_jour_chauffeur(client):
    jeton = jeton_pour(client, 's.fortin@transitflow.ca', role='chauffeur')
    payload = {'plaque': 'L9M 356', 'depart': 'Sherbrooke', 'arrivee': 'Lennoxville',
               'debut': '2026-09-12T10:00', 'finPrevue': '2026-09-12T10:30'}
    r = client.post('/api/trajets', json=payload, headers=entete_auth(jeton))
    assert r.status_code == 201
    trajet = r.get_json()['trajet']
    assert trajet['id'] == 'T-2094'
    assert trajet['statut'] == 'en-cours'
    assert trajet['arrets'] == []
    assert trajet['fin'] is None

    jeton_admin = jeton_pour(client, 'a.tremblay@transitflow.ca')
    chauffeur = client.get('/api/chauffeurs/c3', headers=entete_auth(jeton_admin)).get_json()['chauffeur']
    assert chauffeur['statut'] == 'en-trajet'


def test_creation_trajet_champ_manquant(client):
    jeton = jeton_pour(client, 's.fortin@transitflow.ca', role='chauffeur')
    r = client.post('/api/trajets', json={'plaque': 'L9M 356'}, headers=entete_auth(jeton))
    assert r.status_code == 400


def test_ajouter_arret(client):
    jeton = jeton_pour(client, 'm.traore@transitflow.ca', role='chauffeur')
    r = client.post('/api/trajets/T-2091/arrets', json={'lieu': 'Ascot', 'heure': '08:05', 'note': ''},
                     headers=entete_auth(jeton))
    assert r.status_code == 200
    assert len(r.get_json()['trajet']['arrets']) == 2


def test_ajouter_arret_refuse_pour_autre_chauffeur(client):
    jeton = jeton_pour(client, 'a.diallo@transitflow.ca', role='chauffeur')
    r = client.post('/api/trajets/T-2091/arrets', json={'lieu': 'Ascot', 'heure': '08:05'},
                     headers=entete_auth(jeton))
    assert r.status_code == 403


def test_terminer_trajet_libere_le_chauffeur(client):
    jeton = jeton_pour(client, 'm.traore@transitflow.ca', role='chauffeur')
    r = client.post('/api/trajets/T-2091/terminer', headers=entete_auth(jeton))
    assert r.status_code == 200
    trajet = r.get_json()['trajet']
    assert trajet['statut'] == 'termine'
    assert trajet['fin'] is not None

    jeton_admin = jeton_pour(client, 'a.tremblay@transitflow.ca')
    chauffeur = client.get('/api/chauffeurs/c2', headers=entete_auth(jeton_admin)).get_json()['chauffeur']
    assert chauffeur['statut'] == 'disponible'


def test_terminer_trajet_refuse_pour_autre_chauffeur(client):
    jeton = jeton_pour(client, 'a.diallo@transitflow.ca', role='chauffeur')
    r = client.post('/api/trajets/T-2091/terminer', headers=entete_auth(jeton))
    assert r.status_code == 403

from conftest import entete_auth, jeton_pour

PAYLOAD_VALIDE = {
    'prenom': 'Julie', 'nom': 'Roy', 'age': 31, 'telephone': '819-555-0300',
    'courriel': 'j.roy@transitflow.ca', 'adresse': '1 rue Principale',
    'permisNumero': 'D9999-000000-09', 'permisExpiration': '2029-01-01',
    'plaqueHabituelle': 'F7X 213'
}


def test_liste_necessite_authentification(client):
    r = client.get('/api/chauffeurs')
    assert r.status_code == 401


def test_liste_chauffeurs(client):
    jeton = jeton_pour(client, 'a.tremblay@transitflow.ca')
    r = client.get('/api/chauffeurs', headers=entete_auth(jeton))
    assert r.status_code == 200
    assert len(r.get_json()['chauffeurs']) == 4


def test_filtre_par_statut(client):
    jeton = jeton_pour(client, 'a.tremblay@transitflow.ca')
    r = client.get('/api/chauffeurs?statut=hors-service', headers=entete_auth(jeton))
    data = r.get_json()['chauffeurs']
    assert len(data) == 1
    assert all(c['statut'] == 'hors-service' for c in data)


def test_recherche_texte(client):
    jeton = jeton_pour(client, 'a.tremblay@transitflow.ca')
    r = client.get('/api/chauffeurs?recherche=diallo', headers=entete_auth(jeton))
    data = r.get_json()['chauffeurs']
    assert len(data) == 1
    assert data[0]['id'] == 'c1'


def test_obtenir_chauffeur_inexistant(client):
    jeton = jeton_pour(client, 'a.tremblay@transitflow.ca')
    r = client.get('/api/chauffeurs/c999', headers=entete_auth(jeton))
    assert r.status_code == 404


def test_creation_reservee_admin(client):
    jeton = jeton_pour(client, 'a.diallo@transitflow.ca', role='chauffeur')
    r = client.post('/api/chauffeurs', json=PAYLOAD_VALIDE, headers=entete_auth(jeton))
    assert r.status_code == 403


def test_creation_chauffeur(client):
    jeton = jeton_pour(client, 'a.tremblay@transitflow.ca')
    r = client.post('/api/chauffeurs', json=PAYLOAD_VALIDE, headers=entete_auth(jeton))
    assert r.status_code == 201
    chauffeur = r.get_json()['chauffeur']
    assert chauffeur['id'] == 'c5'
    assert chauffeur['statut'] == 'disponible'
    assert 'creeLe' in chauffeur


def test_creation_champs_manquants(client):
    jeton = jeton_pour(client, 'a.tremblay@transitflow.ca')
    r = client.post('/api/chauffeurs', json={'prenom': 'Julie'}, headers=entete_auth(jeton))
    assert r.status_code == 400


def test_maj_chauffeur(client):
    jeton = jeton_pour(client, 'a.tremblay@transitflow.ca')
    r = client.patch('/api/chauffeurs/c1', json={'statut': 'hors-service'}, headers=entete_auth(jeton))
    assert r.status_code == 200
    assert r.get_json()['chauffeur']['statut'] == 'hors-service'


def test_maj_chauffeur_inexistant(client):
    jeton = jeton_pour(client, 'a.tremblay@transitflow.ca')
    r = client.patch('/api/chauffeurs/c999', json={'statut': 'hors-service'}, headers=entete_auth(jeton))
    assert r.status_code == 404

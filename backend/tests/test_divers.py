from conftest import entete_auth, jeton_pour


def test_vehicules(client):
    jeton = jeton_pour(client, 'a.diallo@transitflow.ca', role='chauffeur')
    r = client.get('/api/vehicules', headers=entete_auth(jeton))
    assert r.status_code == 200
    assert len(r.get_json()['vehicules']) == 4


def test_indicateurs_reserve_admin(client):
    jeton = jeton_pour(client, 'a.diallo@transitflow.ca', role='chauffeur')
    r = client.get('/api/indicateurs', headers=entete_auth(jeton))
    assert r.status_code == 403


def test_indicateurs_valeurs(client):
    jeton = jeton_pour(client, 'a.tremblay@transitflow.ca')
    r = client.get('/api/indicateurs', headers=entete_auth(jeton))
    k = r.get_json()['indicateurs']
    assert k['chauffeursActifs'] == 3
    assert k['trajetsEnCours'] == 1
    assert k['trajetsDuJour'] == 1
    assert k['incidentsOuverts'] == 1
    assert k['permisAExpirer'] == 1


def test_sante(client):
    r = client.get('/api/sante')
    assert r.status_code == 200
    assert r.get_json()['ok'] is True

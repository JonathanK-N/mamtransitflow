from conftest import CHAUFFEUR_VALIDE, creer_chauffeur, entete_auth, jeton_admin, jeton_pour


def test_liste_necessite_authentification(client):
    r = client.get('/api/chauffeurs')
    assert r.status_code == 401


def test_liste_vide_au_depart(client):
    jeton = jeton_admin(client)
    r = client.get('/api/chauffeurs', headers=entete_auth(jeton))
    assert r.status_code == 200
    assert r.get_json()['chauffeurs'] == []


def test_creation_reservee_admin(client):
    jeton = jeton_pour(client, 's.fortin@transitflow.ca', role='chauffeur')
    r = client.post('/api/chauffeurs', json=CHAUFFEUR_VALIDE, headers=entete_auth(jeton))
    assert r.status_code == 403


def test_creation_chauffeur(client):
    jeton = jeton_admin(client)
    r = client.post('/api/chauffeurs', json=CHAUFFEUR_VALIDE, headers=entete_auth(jeton))
    assert r.status_code == 201
    chauffeur = r.get_json()['chauffeur']
    assert chauffeur['id'] == 'c1'
    assert chauffeur['statut'] == 'disponible'
    assert 'creeLe' in chauffeur


def test_creation_champs_manquants(client):
    jeton = jeton_admin(client)
    r = client.post('/api/chauffeurs', json={'prenom': 'Julie'}, headers=entete_auth(jeton))
    assert r.status_code == 400


def test_filtre_par_statut(client):
    jeton = jeton_admin(client)
    creer_chauffeur(client, jeton, courriel='a.diallo@transitflow.ca')
    creer_chauffeur(client, jeton, prenom='Moussa', nom='Traore', courriel='m.traore@transitflow.ca',
                     statut='hors-service')
    r = client.get('/api/chauffeurs?statut=hors-service', headers=entete_auth(jeton))
    data = r.get_json()['chauffeurs']
    assert len(data) == 1
    assert data[0]['nom'] == 'Traore'


def test_recherche_texte(client):
    jeton = jeton_admin(client)
    creer_chauffeur(client, jeton, courriel='a.diallo@transitflow.ca')
    creer_chauffeur(client, jeton, prenom='Moussa', nom='Traore', courriel='m.traore@transitflow.ca')
    r = client.get('/api/chauffeurs?recherche=diallo', headers=entete_auth(jeton))
    data = r.get_json()['chauffeurs']
    assert len(data) == 1
    assert data[0]['nom'] == 'Diallo'


def test_obtenir_chauffeur_inexistant(client):
    jeton = jeton_admin(client)
    r = client.get('/api/chauffeurs/c999', headers=entete_auth(jeton))
    assert r.status_code == 404


def test_maj_chauffeur(client):
    jeton = jeton_admin(client)
    chauffeur = creer_chauffeur(client, jeton)
    r = client.patch('/api/chauffeurs/' + chauffeur['id'], json={'statut': 'hors-service'},
                      headers=entete_auth(jeton))
    assert r.status_code == 200
    assert r.get_json()['chauffeur']['statut'] == 'hors-service'


def test_maj_chauffeur_inexistant(client):
    jeton = jeton_admin(client)
    r = client.patch('/api/chauffeurs/c999', json={'statut': 'hors-service'}, headers=entete_auth(jeton))
    assert r.status_code == 404

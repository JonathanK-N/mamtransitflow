from conftest import creer_chauffeur, entete_auth, jeton_admin, jeton_pour

TRAJET_VALIDE = {'plaque': 'QC-4821', 'depart': 'Sherbrooke', 'arrivee': 'Magog',
                  'debut': '2026-09-12T07:30', 'finPrevue': '2026-09-12T08:45'}


def _chauffeur_et_jeton(client, **champs):
    admin = jeton_admin(client)
    chauffeur = creer_chauffeur(client, admin, **champs)
    jeton = jeton_pour(client, chauffeur['courriel'], role='chauffeur')
    return chauffeur, jeton


def test_liste_vide_au_depart(client):
    jeton = jeton_admin(client)
    r = client.get('/api/trajets', headers=entete_auth(jeton))
    assert r.get_json()['trajets'] == []


def test_trajet_en_cours_absent(client):
    jeton = jeton_admin(client)
    r = client.get('/api/trajets/en-cours/c1', headers=entete_auth(jeton))
    assert r.get_json()['trajet'] is None


def test_obtenir_trajet_inexistant(client):
    jeton = jeton_admin(client)
    r = client.get('/api/trajets/T-9999', headers=entete_auth(jeton))
    assert r.status_code == 404


def test_creation_reservee_chauffeur(client):
    jeton = jeton_admin(client)
    r = client.post('/api/trajets', json=TRAJET_VALIDE, headers=entete_auth(jeton))
    assert r.status_code == 403


def test_creation_trajet_premier_id_et_maj_chauffeur(client):
    chauffeur, jeton = _chauffeur_et_jeton(client)
    r = client.post('/api/trajets', json=TRAJET_VALIDE, headers=entete_auth(jeton))
    assert r.status_code == 201
    trajet = r.get_json()['trajet']
    assert trajet['id'] == 'T-1'
    assert trajet['statut'] == 'en-cours'
    assert trajet['chauffeurId'] == chauffeur['id']
    assert trajet['arrets'] == []
    assert trajet['fin'] is None

    admin = jeton_admin(client)
    fiche = client.get('/api/chauffeurs/' + chauffeur['id'], headers=entete_auth(admin)).get_json()['chauffeur']
    assert fiche['statut'] == 'en-trajet'


def test_creation_trajet_incremente_id(client):
    _, jeton = _chauffeur_et_jeton(client)
    client.post('/api/trajets', json=TRAJET_VALIDE, headers=entete_auth(jeton))
    r = client.post('/api/trajets', json=TRAJET_VALIDE, headers=entete_auth(jeton))
    assert r.get_json()['trajet']['id'] == 'T-2'


def test_creation_trajet_champ_manquant(client):
    _, jeton = _chauffeur_et_jeton(client)
    r = client.post('/api/trajets', json={'plaque': 'QC-4821'}, headers=entete_auth(jeton))
    assert r.status_code == 400


def test_liste_trajets_tri_desc(client):
    _, jeton = _chauffeur_et_jeton(client)
    client.post('/api/trajets', json=TRAJET_VALIDE, headers=entete_auth(jeton))
    client.post('/api/trajets', json=dict(TRAJET_VALIDE, debut='2026-09-13T07:30', finPrevue='2026-09-13T08:45'),
                 headers=entete_auth(jeton))
    admin = jeton_admin(client)
    debuts = [t['debut'] for t in client.get('/api/trajets', headers=entete_auth(admin)).get_json()['trajets']]
    assert debuts == sorted(debuts, reverse=True)


def test_ajouter_arret(client):
    chauffeur, jeton = _chauffeur_et_jeton(client)
    trajet = client.post('/api/trajets', json=TRAJET_VALIDE, headers=entete_auth(jeton)).get_json()['trajet']
    r = client.post('/api/trajets/' + trajet['id'] + '/arrets',
                     json={'lieu': 'Ascot', 'heure': '08:05', 'note': ''}, headers=entete_auth(jeton))
    assert r.status_code == 200
    assert len(r.get_json()['trajet']['arrets']) == 1


def test_ajouter_arret_refuse_pour_autre_chauffeur(client):
    admin = jeton_admin(client)
    _, jeton1 = _chauffeur_et_jeton(client)
    trajet = client.post('/api/trajets', json=TRAJET_VALIDE, headers=entete_auth(jeton1)).get_json()['trajet']
    autre = creer_chauffeur(client, admin, prenom='Moussa', nom='Traore', courriel='m.traore@transitflow.ca')
    jeton2 = jeton_pour(client, autre['courriel'], role='chauffeur')
    r = client.post('/api/trajets/' + trajet['id'] + '/arrets', json={'lieu': 'Ascot', 'heure': '08:05'},
                     headers=entete_auth(jeton2))
    assert r.status_code == 403


def test_terminer_trajet_libere_le_chauffeur(client):
    chauffeur, jeton = _chauffeur_et_jeton(client)
    trajet = client.post('/api/trajets', json=TRAJET_VALIDE, headers=entete_auth(jeton)).get_json()['trajet']
    r = client.post('/api/trajets/' + trajet['id'] + '/terminer', headers=entete_auth(jeton))
    assert r.status_code == 200
    termine = r.get_json()['trajet']
    assert termine['statut'] == 'termine'
    assert termine['fin'] is not None

    admin = jeton_admin(client)
    fiche = client.get('/api/chauffeurs/' + chauffeur['id'], headers=entete_auth(admin)).get_json()['chauffeur']
    assert fiche['statut'] == 'disponible'

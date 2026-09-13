from conftest import creer_chauffeur, entete_auth, jeton_admin, jeton_pour

TRAJET_VALIDE = {'plaque': 'QC-4821', 'depart': 'Sherbrooke', 'arrivee': 'Magog',
                  'debut': '2026-09-12T07:30', 'finPrevue': '2026-09-12T08:45'}


def test_vehicules_vide_au_depart(client):
    jeton = jeton_admin(client)
    r = client.get('/api/vehicules', headers=entete_auth(jeton))
    assert r.status_code == 200
    assert r.get_json()['vehicules'] == []


def test_indicateurs_reserve_admin(client):
    admin = jeton_admin(client)
    creer_chauffeur(client, admin)
    jeton = jeton_pour(client, 'a.diallo@transitflow.ca', role='chauffeur')
    r = client.get('/api/indicateurs', headers=entete_auth(jeton))
    assert r.status_code == 403


def test_indicateurs_valeurs(client):
    admin = jeton_admin(client)
    chauffeur = creer_chauffeur(client, admin, permisExpiration='2026-10-05')
    creer_chauffeur(client, admin, prenom='Moussa', nom='Traore', courriel='m.traore@transitflow.ca',
                     permisExpiration='2028-01-01', statut='hors-service')

    jeton = jeton_pour(client, chauffeur['courriel'], role='chauffeur')
    trajet = client.post('/api/trajets', json=TRAJET_VALIDE, headers=entete_auth(jeton)).get_json()['trajet']
    client.post('/api/incidents', json={'trajetId': trajet['id'], 'type': 'route', 'titre': 'x',
                                          'description': 'x', 'lieu': 'x', 'heure': '09:00'},
                headers=entete_auth(jeton))

    r = client.get('/api/indicateurs', headers=entete_auth(admin))
    k = r.get_json()['indicateurs']
    assert k['chauffeursActifs'] == 1
    assert k['trajetsEnCours'] == 1
    assert k['trajetsDuJour'] == 1
    assert k['incidentsOuverts'] == 1
    assert k['incidentsDuJour'] == 1
    assert k['permisAExpirer'] == 1


def test_sante(client):
    r = client.get('/api/sante')
    assert r.status_code == 200
    assert r.get_json()['ok'] is True

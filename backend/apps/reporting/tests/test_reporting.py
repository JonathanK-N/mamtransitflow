"""
TransitFlow — Tests de l app reporting (indicateurs)
Auteur : Jonathan K-N
"""

from conftest import creer_chauffeur_avec_compte, entete_auth


def test_indicateurs_reserve_admin(client, jeton_admin):
    _, jeton = creer_chauffeur_avec_compte(client, jeton_admin)
    r = client.get('/api/indicateurs', **entete_auth(jeton))
    assert r.status_code == 403


def test_indicateurs_valeurs(client, jeton_admin):
    fiche1, jeton1 = creer_chauffeur_avec_compte(client, jeton_admin, permisExpiration='2026-10-05')
    creer_chauffeur_avec_compte(client, jeton_admin, courriel='m.traore@transitflow.ca', prenom='Moussa',
                                 nom='Traore', permisExpiration='2028-01-01', statut='hors-service')

    trajet = client.post('/api/trajets', {
        'plaque': 'QC-4821', 'depart': 'Sherbrooke', 'arrivee': 'Magog',
        'debut': '2026-09-12T07:30:00Z', 'finPrevue': '2026-09-12T08:45:00Z'
    }, format='json', **entete_auth(jeton1)).json()['trajet']
    client.post('/api/incidents', {
        'trajetId': trajet['id'], 'type': 'route', 'titre': 'x', 'description': 'x', 'lieu': 'x', 'heure': '09:00'
    }, format='json', **entete_auth(jeton1))

    r = client.get('/api/indicateurs', **entete_auth(jeton_admin))
    assert r.status_code == 200
    k = r.json()['indicateurs']
    assert k['chauffeursActifs'] == 1  # le 2e est 'hors-service'
    assert k['trajetsEnCours'] == 1
    assert k['incidentsOuverts'] == 1
    assert k['permisAExpirer'] == 1  # 2026-10-05 est dans les 60 jours, 2028-01-01 non


def test_sante(client):
    r = client.get('/api/sante')
    assert r.status_code == 200
    assert r.json()['ok'] is True

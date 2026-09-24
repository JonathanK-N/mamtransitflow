"""
TransitFlow — Tests de l app drivers (chauffeurs)
Auteur : Jonathan K-N
"""

from conftest import CHAUFFEUR_VALIDE, creer_chauffeur_avec_compte, entete_auth


def test_liste_necessite_authentification(client):
    r = client.get('/api/chauffeurs')
    assert r.status_code == 401


def test_creation_chauffeur(client, jeton_admin):
    r = client.post('/api/chauffeurs', CHAUFFEUR_VALIDE, format='json', **entete_auth(jeton_admin))
    assert r.status_code == 201
    fiche = r.json()['chauffeur']
    assert fiche['id'] == 'c1'
    assert fiche['statut'] == 'disponible'
    assert fiche['aUnCompte'] is False
    assert 'creeLe' in fiche


def test_creation_champs_manquants(client, jeton_admin):
    r = client.post('/api/chauffeurs', {'prenom': 'Julie'}, format='json', **entete_auth(jeton_admin))
    assert r.status_code == 400


def test_creation_reservee_admin(client, jeton_admin):
    _, jeton = creer_chauffeur_avec_compte(client, jeton_admin)
    r = client.post('/api/chauffeurs', dict(CHAUFFEUR_VALIDE, courriel='x@transitflow.ca'), format='json',
                     **entete_auth(jeton))
    assert r.status_code == 403


def test_creation_courriel_deja_utilise(client, jeton_admin):
    client.post('/api/chauffeurs', CHAUFFEUR_VALIDE, format='json', **entete_auth(jeton_admin))
    r = client.post('/api/chauffeurs', dict(CHAUFFEUR_VALIDE, courriel='A.Diallo@TransitFlow.ca'), format='json',
                     **entete_auth(jeton_admin))
    assert r.status_code == 400


def test_creation_avec_compte_et_mot_de_passe_genere(client, jeton_admin):
    """La fiche et le compte de connexion sont crees en une seule fois ; le chauffeur peut se connecter."""
    r = client.post('/api/chauffeurs', dict(CHAUFFEUR_VALIDE, creerCompte=True), format='json',
                     **entete_auth(jeton_admin))
    assert r.status_code == 201
    data = r.json()
    assert data['chauffeur']['aUnCompte'] is True
    mot_de_passe = data['motDePasseInitial']
    assert len(mot_de_passe) >= 12

    r = client.post('/api/auth/connexion', {'courriel': CHAUFFEUR_VALIDE['courriel'], 'motDePasse': mot_de_passe,
                                             'role': 'chauffeur'}, format='json')
    assert r.status_code == 200
    assert r.json()['session']['chauffeurId'] == data['chauffeur']['id']


def test_creation_avec_mot_de_passe_choisi(client, jeton_admin):
    r = client.post('/api/chauffeurs', dict(CHAUFFEUR_VALIDE, motDePasse='Navette-Sherbrooke-26'), format='json',
                     **entete_auth(jeton_admin))
    assert r.status_code == 201
    assert 'motDePasseInitial' not in r.json()
    r = client.post('/api/auth/connexion', {'courriel': CHAUFFEUR_VALIDE['courriel'],
                                             'motDePasse': 'Navette-Sherbrooke-26'}, format='json')
    assert r.status_code == 200


def test_creation_mot_de_passe_trop_faible(client, jeton_admin):
    r = client.post('/api/chauffeurs', dict(CHAUFFEUR_VALIDE, motDePasse='1234'), format='json',
                     **entete_auth(jeton_admin))
    assert r.status_code == 400


def test_creation_plaque_vide_ou_inconnue(client, jeton_admin):
    r = client.post('/api/chauffeurs', dict(CHAUFFEUR_VALIDE, plaqueHabituelle=''), format='json',
                     **entete_auth(jeton_admin))
    assert r.status_code == 201
    assert r.json()['chauffeur']['plaqueHabituelle'] is None

    r = client.post('/api/chauffeurs', dict(CHAUFFEUR_VALIDE, courriel='b@transitflow.ca', plaqueHabituelle='QC-0000'),
                     format='json', **entete_auth(jeton_admin))
    assert r.status_code == 400


def test_filtre_par_statut(client, jeton_admin):
    client.post('/api/chauffeurs', CHAUFFEUR_VALIDE, format='json', **entete_auth(jeton_admin))
    client.post('/api/chauffeurs', dict(CHAUFFEUR_VALIDE, prenom='Moussa', nom='Traore',
                                          courriel='m.traore@transitflow.ca', statut='hors-service'),
                format='json', **entete_auth(jeton_admin))
    r = client.get('/api/chauffeurs?statut=hors-service', **entete_auth(jeton_admin))
    data = r.json()['chauffeurs']
    assert len(data) == 1
    assert data[0]['nom'] == 'Traore'


def test_recherche_texte(client, jeton_admin):
    client.post('/api/chauffeurs', CHAUFFEUR_VALIDE, format='json', **entete_auth(jeton_admin))
    client.post('/api/chauffeurs', dict(CHAUFFEUR_VALIDE, prenom='Moussa', nom='Traore',
                                          courriel='m.traore@transitflow.ca'), format='json',
                **entete_auth(jeton_admin))
    r = client.get('/api/chauffeurs?recherche=diallo', **entete_auth(jeton_admin))
    data = r.json()['chauffeurs']
    assert len(data) == 1
    assert data[0]['nom'] == 'Diallo'


def test_obtenir_chauffeur_inexistant(client, jeton_admin):
    r = client.get('/api/chauffeurs/c999', **entete_auth(jeton_admin))
    assert r.status_code == 404


def test_chauffeur_ne_voit_que_sa_fiche(client, jeton_admin):
    fiche1, jeton1 = creer_chauffeur_avec_compte(client, jeton_admin)
    fiche2, _ = creer_chauffeur_avec_compte(client, jeton_admin, courriel='m.traore@transitflow.ca',
                                              prenom='Moussa', nom='Traore')
    liste = client.get('/api/chauffeurs', **entete_auth(jeton1)).json()['chauffeurs']
    assert [c['id'] for c in liste] == [fiche1['id']]
    assert client.get(f"/api/chauffeurs/{fiche1['id']}", **entete_auth(jeton1)).status_code == 200
    assert client.get(f"/api/chauffeurs/{fiche2['id']}", **entete_auth(jeton1)).status_code == 404


def test_maj_par_admin(client, jeton_admin):
    fiche, _ = creer_chauffeur_avec_compte(client, jeton_admin)
    r = client.patch(f"/api/chauffeurs/{fiche['id']}", {'statut': 'hors-service'}, format='json',
                      **entete_auth(jeton_admin))
    assert r.status_code == 200
    assert r.json()['chauffeur']['statut'] == 'hors-service'


def test_maj_courriel_suit_le_compte(client, jeton_admin):
    fiche, _ = creer_chauffeur_avec_compte(client, jeton_admin)
    r = client.patch(f"/api/chauffeurs/{fiche['id']}", {'courriel': 'nouveau@transitflow.ca'}, format='json',
                      **entete_auth(jeton_admin))
    assert r.status_code == 200
    r = client.post('/api/auth/connexion', {'courriel': 'nouveau@transitflow.ca', 'motDePasse': 'chauffeur123'},
                     format='json')
    assert r.status_code == 200


def test_maj_par_le_chauffeur_lui_meme(client, jeton_admin):
    """Un chauffeur peut mettre a jour ses coordonnees sur SA PROPRE fiche."""
    fiche, jeton_chauffeur = creer_chauffeur_avec_compte(client, jeton_admin)
    r = client.patch(f"/api/chauffeurs/{fiche['id']}", {'telephone': '819-555-0000'}, format='json',
                      **entete_auth(jeton_chauffeur))
    assert r.status_code == 200
    assert r.json()['chauffeur']['telephone'] == '819-555-0000'


def test_maj_champs_reserves_refusee_au_chauffeur(client, jeton_admin):
    fiche, jeton_chauffeur = creer_chauffeur_avec_compte(client, jeton_admin)
    for champs in ({'statut': 'hors-service'}, {'permisExpiration': '2030-01-01'}):
        r = client.patch(f"/api/chauffeurs/{fiche['id']}", champs, format='json', **entete_auth(jeton_chauffeur))
        assert r.status_code == 403


def test_maj_refusee_pour_un_autre_chauffeur(client, jeton_admin):
    fiche1, _ = creer_chauffeur_avec_compte(client, jeton_admin)
    _, jeton2 = creer_chauffeur_avec_compte(client, jeton_admin, courriel='m.traore@transitflow.ca',
                                              prenom='Moussa', nom='Traore')
    r = client.patch(f"/api/chauffeurs/{fiche1['id']}", {'telephone': '000'}, format='json',
                      **entete_auth(jeton2))
    assert r.status_code == 404

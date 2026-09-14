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
    assert 'creeLe' in fiche


def test_creation_champs_manquants(client, jeton_admin):
    r = client.post('/api/chauffeurs', {'prenom': 'Julie'}, format='json', **entete_auth(jeton_admin))
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


def test_maj_par_admin(client, jeton_admin):
    fiche, _ = creer_chauffeur_avec_compte(client, jeton_admin)
    r = client.patch(f"/api/chauffeurs/{fiche['id']}", {'statut': 'hors-service'}, format='json',
                      **entete_auth(jeton_admin))
    assert r.status_code == 200
    assert r.json()['chauffeur']['statut'] == 'hors-service'


def test_maj_par_le_chauffeur_lui_meme(client, jeton_admin):
    """Un chauffeur peut mettre a jour SA PROPRE fiche (ex. son statut apres avoir demarre un trajet)."""
    fiche, jeton_chauffeur = creer_chauffeur_avec_compte(client, jeton_admin)
    r = client.patch(f"/api/chauffeurs/{fiche['id']}", {'statut': 'en-trajet'}, format='json',
                      **entete_auth(jeton_chauffeur))
    assert r.status_code == 200
    assert r.json()['chauffeur']['statut'] == 'en-trajet'


def test_maj_refusee_pour_un_autre_chauffeur(client, jeton_admin):
    fiche1, _ = creer_chauffeur_avec_compte(client, jeton_admin)
    _, jeton2 = creer_chauffeur_avec_compte(client, jeton_admin, courriel='m.traore@transitflow.ca',
                                              prenom='Moussa', nom='Traore')
    r = client.patch(f"/api/chauffeurs/{fiche1['id']}", {'statut': 'hors-service'}, format='json',
                      **entete_auth(jeton2))
    assert r.status_code == 403

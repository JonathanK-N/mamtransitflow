"""
TransitFlow — Fixtures et petits utilitaires partages par les tests
Auteur : Jonathan K-N

Pytest charge automatiquement ce fichier (conftest.py) avant les tests
et rend ses fixtures ('app', 'client') disponibles partout, sans import.
Les autres fonctions (connecter, jeton_pour, entete_auth, jeton_admin,
creer_chauffeur) sont de simples raccourcis pour eviter de repeter le
meme code dans chaque test_*.py : on les importe explicitement
(`from conftest import ...`) en haut de chaque fichier de test.
"""

import pytest

from backend import auth, config
from backend.app import create_app


@pytest.fixture
def app(tmp_path, monkeypatch):
    """
    Application Flask isolee pour un seul test :
    - le fichier de donnees pointe vers un dossier temporaire (tmp_path)
      propre a ce test, pour ne jamais toucher au vrai backend/data/db.json
      ni melanger les donnees d un test a l autre ;
    - les jetons de connexion (_SESSIONS) sont vides au debut et a la
      fin de chaque test, pour repartir a zero a chaque fois.
    """
    monkeypatch.setattr(config, 'DATA_FILE', str(tmp_path / 'db.json'))
    auth._SESSIONS.clear()
    application = create_app()
    application.config.update(TESTING=True)
    yield application
    auth._SESSIONS.clear()


@pytest.fixture
def client(app):
    """Client de test Flask : permet d appeler les routes (client.get/post/...) sans vrai serveur HTTP."""
    return app.test_client()


def connecter(client, courriel, mot_de_passe='demo', role=None):
    """Appelle POST /api/auth/connexion et renvoie la reponse brute (utile pour tester les echecs)."""
    payload = {'courriel': courriel, 'motDePasse': mot_de_passe}
    if role:
        payload['role'] = role
    return client.post('/api/auth/connexion', json=payload)


def jeton_pour(client, courriel, role=None):
    """Se connecte et renvoie directement le jeton (utile quand on sait que la connexion va reussir)."""
    return connecter(client, courriel, role=role).get_json()['jeton']


def entete_auth(jeton):
    """Construit l entete Authorization a passer a client.get/post(..., headers=...)."""
    return {'Authorization': 'Bearer ' + jeton}


def jeton_admin(client):
    """Raccourci : connexion avec le compte administrateur de demonstration."""
    return jeton_pour(client, 'a.tremblay@transitflow.ca')


# Donnees minimales valides pour creer un chauffeur (voir CHAMPS_REQUIS
# dans backend/routes/chauffeurs_routes.py). Le courriel correspond au
# compte 'a.diallo@transitflow.ca' de backend/auth.py, ce qui permet de
# tester la connexion chauffeur juste apres avoir cree sa fiche.
CHAUFFEUR_VALIDE = {
    'prenom': 'Aminata', 'nom': 'Diallo', 'age': 34, 'telephone': '819-555-0142',
    'courriel': 'a.diallo@transitflow.ca', 'adresse': '12 rue King Ouest, Sherbrooke, QC',
    'permisNumero': 'D1234-560912-01', 'permisExpiration': '2027-03-15',
    'plaqueHabituelle': 'QC-4821'
}


def creer_chauffeur(client, jeton_admin_, **champs):
    """Cree un chauffeur via l API (avec CHAUFFEUR_VALIDE comme base, ecrasee par **champs) et le renvoie."""
    payload = dict(CHAUFFEUR_VALIDE)
    payload.update(champs)
    r = client.post('/api/chauffeurs', json=payload, headers=entete_auth(jeton_admin_))
    assert r.status_code == 201, r.get_json()
    return r.get_json()['chauffeur']

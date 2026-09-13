import pytest

from backend import auth, config
from backend.app import create_app


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DATA_FILE', str(tmp_path / 'db.json'))
    auth._SESSIONS.clear()
    application = create_app()
    application.config.update(TESTING=True)
    yield application
    auth._SESSIONS.clear()


@pytest.fixture
def client(app):
    return app.test_client()


def connecter(client, courriel, mot_de_passe='demo', role=None):
    payload = {'courriel': courriel, 'motDePasse': mot_de_passe}
    if role:
        payload['role'] = role
    return client.post('/api/auth/connexion', json=payload)


def jeton_pour(client, courriel, role=None):
    return connecter(client, courriel, role=role).get_json()['jeton']


def entete_auth(jeton):
    return {'Authorization': 'Bearer ' + jeton}


def jeton_admin(client):
    return jeton_pour(client, 'a.tremblay@transitflow.ca')


CHAUFFEUR_VALIDE = {
    'prenom': 'Aminata', 'nom': 'Diallo', 'age': 34, 'telephone': '819-555-0142',
    'courriel': 'a.diallo@transitflow.ca', 'adresse': '12 rue King Ouest, Sherbrooke, QC',
    'permisNumero': 'D1234-560912-01', 'permisExpiration': '2027-03-15',
    'plaqueHabituelle': 'QC-4821'
}


def creer_chauffeur(client, jeton_admin_, **champs):
    payload = dict(CHAUFFEUR_VALIDE)
    payload.update(champs)
    r = client.post('/api/chauffeurs', json=payload, headers=entete_auth(jeton_admin_))
    assert r.status_code == 201, r.get_json()
    return r.get_json()['chauffeur']

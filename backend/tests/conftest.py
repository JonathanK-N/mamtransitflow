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

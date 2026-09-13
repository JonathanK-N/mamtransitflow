"""
TransitFlow — Fixtures partagees par les tests (backend v2, FastAPI)
Auteur : Jonathan K-N

Chaque test recoit sa propre base de donnees SQLite en memoire, creee de
zero (toutes les tables, aucune donnee), et un client de test FastAPI
branche dessus via `app.dependency_overrides` -- la meme API que le vrai
serveur, mais isolee d un test a l autre.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.apps.auth.models import Groupe
from backend.apps.auth.security import hacher_mot_de_passe
from backend.database import get_db
from backend.main import create_app
from backend.models_registry import Base

GROUPES_DE_BASE = ['fleet.admin', 'fleet.driver']


@pytest.fixture
def db_session():
    """Une base SQLite en memoire, fraiche pour chaque test."""
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    SessionTest = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionTest()
    for code in GROUPES_DE_BASE:
        session.add(Groupe(code=code, nom=code))
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    """Client de test FastAPI branche sur db_session au lieu de la vraie base."""
    app = create_app()

    def _get_db_test():
        yield db_session

    app.dependency_overrides[get_db] = _get_db_test
    return TestClient(app)


def entete_auth(jeton):
    return {'Authorization': 'Bearer ' + jeton}


def jeton_pour(client, courriel, mot_de_passe='motdepasse123'):
    r = client.post('/api/auth/connexion', json={'courriel': courriel, 'mot_de_passe': mot_de_passe})
    assert r.status_code == 200, r.text
    return r.json()['jeton']


def creer_admin(db_session, courriel='admin@transitflow.ca', mot_de_passe='motdepasse123'):
    """Insere directement un compte admin en base (raccourci pour les tests)."""
    from backend.apps.auth.models import Compte
    groupe = db_session.query(Groupe).filter(Groupe.code == 'fleet.admin').first()
    compte = Compte(courriel=courriel, nom='Admin Test', mot_de_passe_hache=hacher_mot_de_passe(mot_de_passe))
    compte.groupes.append(groupe)
    db_session.add(compte)
    db_session.commit()
    return compte


CHAUFFEUR_VALIDE = {
    'prenom': 'Aminata', 'nom': 'Diallo', 'age': 34, 'telephone': '819-555-0142',
    'courriel': 'a.diallo@transitflow.ca', 'adresse': '12 rue King Ouest',
    'permis_numero': 'D1234', 'permis_expiration': '2027-03-15', 'plaque_habituelle': None
}


def creer_chauffeur_avec_compte(client, jeton_admin, mot_de_passe='chauffeur123', **champs):
    """Cree une fiche chauffeur PUIS son compte de connexion, comme le ferait l admin. Renvoie (fiche, jeton)."""
    payload = dict(CHAUFFEUR_VALIDE)
    payload.update(champs)
    r = client.post('/api/chauffeurs', json=payload, headers=entete_auth(jeton_admin))
    assert r.status_code == 201, r.text
    fiche = r.json()

    r = client.post('/api/auth/comptes', json={
        'courriel': fiche['courriel'], 'mot_de_passe': mot_de_passe, 'nom': f"{fiche['prenom']} {fiche['nom']}",
        'chauffeur_id': fiche['id'], 'groupes': ['fleet.driver']
    }, headers=entete_auth(jeton_admin))
    assert r.status_code == 201, r.text

    jeton = jeton_pour(client, fiche['courriel'], mot_de_passe)
    return fiche, jeton

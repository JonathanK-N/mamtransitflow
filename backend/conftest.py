"""
TransitFlow — Fixtures partagees par tous les tests (pytest-django)
Auteur : Jonathan K-N

pytest-django cree automatiquement une base de donnees de test et
l efface a chaque test (via la fixture `db`). Ce fichier ajoute par-dessus
des raccourcis specifiques a TransitFlow : les groupes de permission de
base, un client DRF, un compte admin pret a l emploi, et un raccourci pour
creer un chauffeur + son compte de connexion (comme le ferait un vrai
administrateur depuis l interface).
"""

import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.comptes.models import Utilisateur

GROUPES_DE_BASE = ['fleet.admin', 'fleet.driver']


@pytest.fixture(autouse=True)
def _cache_vide():
    """Le compteur de limitation de debit (apps/suivi) vit dans le cache : chaque test repart de zero."""
    from django.core.cache import cache
    cache.clear()


@pytest.fixture(autouse=True)
def _groupes_de_base(db):
    """Cree les groupes de permission de base avant chaque test (comme le fait la commande bootstrap)."""
    for code in GROUPES_DE_BASE:
        Group.objects.get_or_create(name=code)


@pytest.fixture
def client():
    """Remplace le client Django par defaut par celui de DRF (reponses .json() plus pratiques)."""
    return APIClient()


def jeton_pour(utilisateur: Utilisateur) -> str:
    return str(AccessToken.for_user(utilisateur))


def entete_auth(jeton: str) -> dict:
    return {'HTTP_AUTHORIZATION': 'Bearer ' + jeton}


@pytest.fixture
def compte_admin(db):
    utilisateur = Utilisateur.objects.create_user(courriel='admin@transitflow.ca', mot_de_passe='motdepasse123',
                                                   nom='Admin Test')
    utilisateur.groups.add(Group.objects.get(name='fleet.admin'))
    return utilisateur


@pytest.fixture
def jeton_admin(compte_admin):
    return jeton_pour(compte_admin)


CHAUFFEUR_VALIDE = {
    'prenom': 'Aminata', 'nom': 'Diallo', 'age': 34, 'telephone': '819-555-0142',
    'courriel': 'a.diallo@transitflow.ca', 'adresse': '12 rue King Ouest',
    'permisNumero': 'D1234', 'permisExpiration': '2027-03-15', 'plaqueHabituelle': None
}


def creer_chauffeur_avec_compte(client, jeton_admin_, mot_de_passe='chauffeur123', **champs):
    """Cree une fiche chauffeur PUIS son compte de connexion, comme le ferait l admin. Renvoie (fiche, jeton)."""
    payload = dict(CHAUFFEUR_VALIDE)
    payload.update(champs)
    r = client.post('/api/chauffeurs', payload, format='json', **entete_auth(jeton_admin_))
    assert r.status_code == 201, r.data
    fiche = r.json()['chauffeur']

    r = client.post('/api/auth/comptes', {
        'courriel': fiche['courriel'], 'motDePasse': mot_de_passe, 'nom': f"{fiche['prenom']} {fiche['nom']}",
        'chauffeurId': fiche['id'], 'groupes': ['fleet.driver']
    }, format='json', **entete_auth(jeton_admin_))
    assert r.status_code == 201, r.data

    r = client.post('/api/auth/connexion', {'courriel': fiche['courriel'], 'motDePasse': mot_de_passe},
                     format='json')
    assert r.status_code == 200, r.data
    return fiche, r.json()['jeton']

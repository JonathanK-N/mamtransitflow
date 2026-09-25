"""
TransitFlow — Tests des commandes d initialisation (bootstrap, seed_demo)
Auteur : Jonathan K-N
"""

import pytest
from django.core.management import CommandError, call_command

from apps.comptes.models import Utilisateur
from apps.dispatch.models import Trajet
from apps.drivers.models import Chauffeur


def test_bootstrap_depuis_env(monkeypatch):
    monkeypatch.setenv('TF_ADMIN_COURRIEL', 'Patron@Exemple.com')
    monkeypatch.setenv('TF_ADMIN_MOT_DE_PASSE', 'Un-Mot-De-Passe-Solide')
    monkeypatch.setenv('TF_ADMIN_NOM', 'Le Patron')
    call_command('bootstrap', '--depuis-env')
    call_command('bootstrap', '--depuis-env')  # redeploiement : ne fait rien de plus
    admin = Utilisateur.objects.get()
    assert admin.courriel == 'patron@exemple.com'
    assert admin.a_groupe('fleet.admin')


def test_bootstrap_depuis_env_sans_variables(monkeypatch):
    monkeypatch.delenv('TF_ADMIN_COURRIEL', raising=False)
    monkeypatch.delenv('TF_ADMIN_MOT_DE_PASSE', raising=False)
    call_command('bootstrap', '--depuis-env')
    assert not Utilisateur.objects.exists()


def test_bootstrap_arguments_obligatoires():
    with pytest.raises(CommandError):
        call_command('bootstrap')


def test_seed_demo_puis_connexion(client, settings):
    settings.DEBUG = True
    call_command('seed_demo')
    call_command('seed_demo')  # idempotent
    assert Chauffeur.objects.count() == 4
    assert Trajet.objects.filter(statut='en-cours').count() == 1

    r = client.post('/api/auth/connexion', {'courriel': 'a.diallo@transitflow.ca', 'motDePasse': 'Transit-Demo-2026',
                                             'role': 'chauffeur'}, format='json')
    assert r.status_code == 200

    call_command('seed_demo', '--reset')
    assert Chauffeur.objects.count() == 4


def test_seed_demo_refuse_en_production(settings):
    settings.DEBUG = False
    with pytest.raises(CommandError):
        call_command('seed_demo')


def test_preparer_deploiement(monkeypatch):
    monkeypatch.setenv('TF_ADMIN_COURRIEL', 'admin@exemple.com')
    monkeypatch.setenv('TF_ADMIN_MOT_DE_PASSE', 'Un-Mot-De-Passe-Solide')
    call_command('preparer_deploiement')
    call_command('preparer_deploiement')  # redeploiement : sans effet de bord
    assert Utilisateur.objects.get().a_groupe('fleet.admin')

"""
TransitFlow — Tests des commandes d initialisation (bootstrap, seed_demo)
Auteur : Jonathan K-N
"""

import pytest
from django.utils import timezone
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


def _connexion(courriel, mot_de_passe):
    from rest_framework.test import APIClient
    return APIClient().post('/api/auth/connexion', {'courriel': courriel, 'motDePasse': mot_de_passe,
                                                   'role': 'admin'}, format='json')


def test_bootstrap_ignore_les_espaces_des_variables(monkeypatch):
    monkeypatch.setenv('TF_ADMIN_COURRIEL', '  patron@exemple.com ')
    monkeypatch.setenv('TF_ADMIN_MOT_DE_PASSE', ' Un-Mot-De-Passe-Solide \n')
    call_command('bootstrap', '--depuis-env')
    assert Utilisateur.objects.get().courriel == 'patron@exemple.com'
    assert _connexion('patron@exemple.com', 'Un-Mot-De-Passe-Solide').status_code == 200


def test_bootstrap_ne_change_pas_un_compte_existant_par_defaut(monkeypatch):
    monkeypatch.setenv('TF_ADMIN_COURRIEL', 'patron@exemple.com')
    monkeypatch.setenv('TF_ADMIN_MOT_DE_PASSE', 'Ancien-Mot-De-Passe-1')
    call_command('bootstrap', '--depuis-env')
    monkeypatch.setenv('TF_ADMIN_MOT_DE_PASSE', 'Nouveau-Mot-De-Passe-2')
    call_command('bootstrap', '--depuis-env')
    assert _connexion('patron@exemple.com', 'Ancien-Mot-De-Passe-1').status_code == 200
    assert _connexion('patron@exemple.com', 'Nouveau-Mot-De-Passe-2').status_code == 401


def test_bootstrap_reinitialise_le_mot_de_passe_sur_demande(monkeypatch):
    from django.contrib.auth.models import Group

    monkeypatch.setenv('TF_ADMIN_COURRIEL', 'patron@exemple.com')
    monkeypatch.setenv('TF_ADMIN_MOT_DE_PASSE', 'Ancien-Mot-De-Passe-1')
    call_command('bootstrap', '--depuis-env')
    admin = Utilisateur.objects.get()
    admin.is_active = False
    admin.save()
    admin.groups.remove(Group.objects.get(name='fleet.admin'))

    monkeypatch.setenv('TF_ADMIN_MOT_DE_PASSE', 'Nouveau-Mot-De-Passe-2')
    monkeypatch.setenv('TF_ADMIN_REINITIALISER', '1')
    call_command('bootstrap', '--depuis-env')
    assert _connexion('patron@exemple.com', 'Ancien-Mot-De-Passe-1').status_code == 401
    r = _connexion('patron@exemple.com', 'Nouveau-Mot-De-Passe-2')
    assert r.status_code == 200 and r.json()['session']['role'] == 'admin'
    assert Utilisateur.objects.count() == 1


def test_connexion_mot_de_passe_compare_tel_quel(monkeypatch):
    from django.contrib.auth.models import Group

    compte = Utilisateur.objects.create_user(courriel='a@exemple.com', mot_de_passe=' espace-avant-et-apres ')
    compte.groups.add(Group.objects.get(name='fleet.admin'))
    assert _connexion('a@exemple.com', ' espace-avant-et-apres ').status_code == 200
    assert _connexion('a@exemple.com', 'espace-avant-et-apres').status_code == 401


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


def test_seed_demo_entretien(settings):
    from apps.entretien.models import BonTravail, PlanEntretien
    from apps.fleet.models import Vehicule

    settings.DEBUG = True
    call_command('seed_demo')
    call_command('seed_demo')  # idempotent : pas de doublons de plans ni de bons
    assert PlanEntretien.objects.count() == 5 * 4
    assert BonTravail.objects.filter(statut='termine').count() == 3
    assert BonTravail.objects.filter(statut='en-cours').count() == 1
    assert BonTravail.objects.filter(incident__isnull=False).count() == 1
    assert Vehicule.objects.get(plaque='QC-2287').statut == 'maintenance'
    assert all(v.releves.exists() for v in Vehicule.objects.all())
    from apps.suivi.models import PositionGPS
    en_cours = Trajet.objects.get(statut='en-cours')
    assert en_cours.positions.count() > 30
    assert (timezone.now() - en_cours.positions.last().horodatage).total_seconds() < 60
    call_command('seed_demo', '--reset')  # les bons (PROTECT) ne bloquent pas la remise a zero
    assert BonTravail.objects.filter(statut='en-cours').count() == 1


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

"""
TransitFlow — Initialisation d une nouvelle installation
Auteur : Jonathan K-N

Il n y a pas de comptes de demonstration codes en dur : chaque client a
ses propres comptes, avec de vrais mots de passe. Cette commande cree :
1. les deux groupes de permission de base ('fleet.admin', 'fleet.driver') ;
2. un premier compte administrateur, pour pouvoir se connecter une
   premiere fois et creer les autres comptes depuis l interface.

Usage (depuis backend/) :
  python manage.py bootstrap admin@exemple.com "mot-de-passe-sur" "Prenom Nom"

Au deploiement (Railway, voir railway.json), la commande est lancee sans
argument avec --depuis-env : elle cree les groupes, puis le compte decrit
par TF_ADMIN_COURRIEL / TF_ADMIN_MOT_DE_PASSE / TF_ADMIN_NOM s il n existe
pas encore. Elle ne fait rien de plus a chaque redeploiement.

Mot de passe perdu ou modifie apres coup : definir TF_ADMIN_REINITIALISER=1
puis redeployer. Le compte TF_ADMIN_COURRIEL reprend alors le mot de passe
TF_ADMIN_MOT_DE_PASSE, est reactive et remis dans le groupe 'fleet.admin'.
Retirer ensuite la variable (sinon chaque redemarrage recommence).

Les espaces en debut et fin des variables (copier-coller) sont ignores.
"""

import os

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError

from apps.comptes.models import Utilisateur

GROUPES_DE_BASE = ['fleet.admin', 'fleet.driver']


class Command(BaseCommand):
    help = "Cree les groupes de permission de base et le premier compte administrateur."

    def add_arguments(self, parser):
        parser.add_argument('courriel', nargs='?')
        parser.add_argument('mot_de_passe', nargs='?')
        parser.add_argument('nom', nargs='?', default='')
        parser.add_argument(
            '--depuis-env', action='store_true',
            help="Lit le compte dans TF_ADMIN_COURRIEL/TF_ADMIN_MOT_DE_PASSE/TF_ADMIN_NOM ; "
                 "ne fait rien si le compte existe deja ou si les variables sont absentes.",
        )

    def handle(self, *args, **options):
        for code in GROUPES_DE_BASE:
            Group.objects.get_or_create(name=code)

        if options['depuis_env']:
            courriel = os.environ.get('TF_ADMIN_COURRIEL', '').strip()
            mot_de_passe = os.environ.get('TF_ADMIN_MOT_DE_PASSE', '').strip()
            nom = os.environ.get('TF_ADMIN_NOM', '').strip()
            if not (courriel and mot_de_passe):
                self.stdout.write('Groupes de base prets (TF_ADMIN_COURRIEL/TF_ADMIN_MOT_DE_PASSE absents : '
                                  'aucun compte administrateur cree).')
                return
            existant = Utilisateur.objects.filter(courriel__iexact=courriel).first()
            if existant:
                if os.environ.get('TF_ADMIN_REINITIALISER', '').strip() == '1':
                    self._reinitialiser(existant, mot_de_passe)
                    return
                self.stdout.write(f'Groupes de base prets ; le compte {existant.courriel} existe deja '
                                  '(TF_ADMIN_REINITIALISER=1 pour lui redonner TF_ADMIN_MOT_DE_PASSE).')
                return
        else:
            courriel, mot_de_passe, nom = options['courriel'], options['mot_de_passe'], options['nom']
            if not (courriel and mot_de_passe):
                raise CommandError('Usage : bootstrap <courriel> <mot_de_passe> [nom]  (ou --depuis-env)')
            if Utilisateur.objects.filter(courriel__iexact=courriel).exists():
                raise CommandError(f'Le compte {courriel.lower()} existe deja.')

        utilisateur = Utilisateur.objects.create_superuser(courriel=courriel, mot_de_passe=mot_de_passe, nom=nom)
        utilisateur.groups.add(Group.objects.get(name='fleet.admin'))
        self.stdout.write(self.style.SUCCESS(f'Compte administrateur cree : {utilisateur.courriel}'))

    def _reinitialiser(self, utilisateur, mot_de_passe):
        utilisateur.set_password(mot_de_passe)
        utilisateur.is_active = True
        utilisateur.is_staff = True
        utilisateur.is_superuser = True
        utilisateur.save(update_fields=['password', 'is_active', 'is_staff', 'is_superuser'])
        utilisateur.groups.add(Group.objects.get(name='fleet.admin'))
        self.stdout.write(self.style.WARNING(
            f'Compte administrateur {utilisateur.courriel} reinitialise avec TF_ADMIN_MOT_DE_PASSE. '
            'Retirez TF_ADMIN_REINITIALISER des variables du service.'))

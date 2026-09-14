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
"""

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError

from apps.comptes.models import Utilisateur

GROUPES_DE_BASE = ['fleet.admin', 'fleet.driver']


class Command(BaseCommand):
    help = "Cree les groupes de permission de base et le premier compte administrateur."

    def add_arguments(self, parser):
        parser.add_argument('courriel')
        parser.add_argument('mot_de_passe')
        parser.add_argument('nom')

    def handle(self, *args, **options):
        for code in GROUPES_DE_BASE:
            Group.objects.get_or_create(name=code)

        courriel = options['courriel'].lower()
        if Utilisateur.objects.filter(courriel=courriel).exists():
            raise CommandError(f'Le compte {courriel} existe deja.')

        utilisateur = Utilisateur.objects.create_superuser(
            courriel=courriel, mot_de_passe=options['mot_de_passe'], nom=options['nom']
        )
        utilisateur.groups.add(Group.objects.get(name='fleet.admin'))
        self.stdout.write(self.style.SUCCESS(f'Compte administrateur cree : {courriel}'))

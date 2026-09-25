"""
TransitFlow — Purge des anciennes positions GPS
Auteur : Jonathan K-N

Les positions sont des donnees personnelles (deplacements des chauffeurs) :
on ne les garde que le temps utile. Supprime les points des trajets
TERMINES depuis plus de N jours (90 par defaut, ou TF_GPS_RETENTION_JOURS).
Les trajets eux-memes, leurs arrets et incidents sont conserves.

Usage (depuis backend/) :
  python manage.py purger_positions               # 90 jours
  python manage.py purger_positions --jours 30
  python manage.py purger_positions --simulation  # affiche sans supprimer
Lancee aussi a chaque demarrage du conteneur (preparer_deploiement).
"""

import os
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.suivi.models import PositionGPS


class Command(BaseCommand):
    help = 'Supprime les positions GPS des trajets termines depuis plus de N jours.'

    def add_arguments(self, parser):
        parser.add_argument('--jours', type=int, default=None)
        parser.add_argument('--simulation', action='store_true', help='Compte sans supprimer.')

    def handle(self, *args, **options):
        jours = options['jours']
        if jours is None:
            jours = int(os.environ.get('TF_GPS_RETENTION_JOURS', '90') or 90)
        if jours < 1:
            raise CommandError('La duree de conservation doit etre d au moins 1 jour.')
        limite = timezone.now() - timedelta(days=jours)
        anciennes = PositionGPS.objects.filter(trajet__statut='termine', trajet__fin__lt=limite)
        nombre = anciennes.count()
        if options['simulation']:
            self.stdout.write(f'{nombre} position(s) GPS de plus de {jours} jours seraient supprimees.')
            return
        anciennes.delete()
        self.stdout.write(f'Positions GPS : {nombre} point(s) de plus de {jours} jours supprime(s).')

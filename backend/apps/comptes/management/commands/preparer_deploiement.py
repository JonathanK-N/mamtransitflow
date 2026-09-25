"""
TransitFlow — Preparation d un deploiement
Auteur : Jonathan K-N

Commande unique lancee au demarrage du conteneur Railway, juste avant
gunicorn (deploy.startCommand dans railway.json) :
1. applique les migrations (tables a jour) ;
2. cree les groupes de base et, si TF_ADMIN_COURRIEL / TF_ADMIN_MOT_DE_PASSE
   sont definis, le premier administrateur (bootstrap --depuis-env) ;
3. supprime les positions GPS trop anciennes (purger_positions).

Elle etait d abord declaree en commande de pre-deploiement, mais Railway
ne semblait pas l executer : les tables n etaient pas creees et la connexion
repondait 500. La commande de demarrage, elle, passe toujours par un
shell. Elle est sans effet de bord a chaque redemarrage.

Usage (depuis la racine du projet) :
  python backend/manage.py preparer_deploiement
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Applique les migrations puis cree les groupes et le premier administrateur (deploiement).'

    def handle(self, *args, **options):
        self.stdout.write('Migrations...')
        call_command('migrate', interactive=False, verbosity=1, stdout=self.stdout, stderr=self.stderr)
        self.stdout.write('Comptes de base...')
        call_command('bootstrap', depuis_env=True, stdout=self.stdout, stderr=self.stderr)
        call_command('purger_positions', stdout=self.stdout, stderr=self.stderr)
        self.stdout.write(self.style.SUCCESS('Deploiement pret.'))

from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from apps.erp.models import Organization
from apps.erp.personnel import reconcile_personnel


class Command(BaseCommand):
    help = 'Audite le Personnel des membres internes ; --apply applique les rapprochements sûrs.'

    def add_arguments(self, parser):
        parser.add_argument('--apply',action='store_true')
        parser.add_argument('--organization',type=str)

    def handle(self,*args,**options):
        organization_id=options['organization']
        if organization_id:
            try:exists=Organization.objects.filter(pk=organization_id).exists()
            except (ValueError,TypeError,ValidationError):raise CommandError('Identifiant entreprise invalide.')
            if not exists:raise CommandError('Entreprise introuvable.')
        audit=reconcile_personnel(organization_id=organization_id,dry_run=True)
        self.stdout.write('Personnel audit: '+', '.join(f'{key}={value}' for key,value in audit.items()))
        if options['apply']:
            result=reconcile_personnel(organization_id=organization_id,dry_run=False)
            self.stdout.write('Personnel applied: '+', '.join(f'{key}={value}' for key,value in result.items()))
            if result['conflicts'] or result['external']:
                self.stderr.write('Personnel: rapprochements ambigus ou accès externes conservés sans modification.')
        else:self.stdout.write('Simulation uniquement ; aucune modification de données.')

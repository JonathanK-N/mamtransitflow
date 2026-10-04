from django.core.management.base import BaseCommand
from apps.erp.tracking import check_signals

class Command(BaseCommand):
    help="Détecter les interruptions GPS des missions actives."
    def handle(self,*args,**options):check_signals()

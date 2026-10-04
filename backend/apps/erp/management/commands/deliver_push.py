import time
from django.core.management.base import BaseCommand
from django.db import close_old_connections
from apps.erp.push import process_pending


class Command(BaseCommand):
    help='Traiter la file persistante de notifications push.'
    def add_arguments(self,parser):parser.add_argument('--once',action='store_true')
    def handle(self,*args,**options):
        checked=0
        while True:
            close_old_connections()
            from apps.erp.tracking import check_signals
            if time.monotonic()-checked>=30:
                check_signals();checked=time.monotonic()
            process_pending()
            if options['once']:return
            time.sleep(5)

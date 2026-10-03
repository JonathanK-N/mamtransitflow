import time
from django.core.management.base import BaseCommand
from django.db import close_old_connections
from apps.erp.push import process_pending


class Command(BaseCommand):
    help='Traiter la file persistante de notifications push.'
    def add_arguments(self,parser):parser.add_argument('--once',action='store_true')
    def handle(self,*args,**options):
        while True:
            close_old_connections()
            process_pending()
            if options['once']:return
            time.sleep(5)

"""
TransitFlow — Donnees de demonstration
Auteur : Jonathan K-N

Recree un jeu de donnees realiste (vehicules, un administrateur, quatre
chauffeurs avec leur compte, trajets, arrets, incidents) equivalent au
TF_SEED du prototype front-end, qui n a jamais ete commite. Les dates sont
calculees a partir d aujourd hui : le tableau de bord reste coherent quel
que soit le jour de la demonstration.

Usage (depuis backend/) :
  python manage.py seed_demo                      # mot de passe : Transit-Demo-2026
  python manage.py seed_demo --mot-de-passe XXX
  python manage.py seed_demo --reset              # vide les donnees metier avant

Refuse de s executer quand TF_DEBUG=0 (production), sauf avec --force.
"""

from datetime import date, datetime, timedelta

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.comptes.models import Utilisateur
from apps.dispatch.models import Arret, Trajet
from apps.drivers.models import Chauffeur
from apps.fleet.models import Vehicule
from apps.maintenance.models import Incident

MOT_DE_PASSE_PAR_DEFAUT = 'Transit-Demo-2026'
ADMIN = ('a.tremblay@transitflow.ca', 'Alex Tremblay')

VEHICULES = [
    ('QC-4821', 'Ford Transit 2023'),
    ('QC-1094', 'Mercedes Sprinter 2022'),
    ('QC-7733', 'Ford Transit 2024'),
    ('QC-2287', 'Nissan NV200 2021'),
    ('QC-5512', 'Ford Transit 2022'),
]

# (courriel, prenom, nom, age, telephone, adresse, permis, expiration dans N jours, statut, plaque)
CHAUFFEURS = [
    ('a.diallo@transitflow.ca', 'Aminata', 'Diallo', 34, '819-555-0142', '12 rue King Ouest, Sherbrooke',
     'D1234-560101-02', 40, 'en-trajet', 'QC-4821'),
    ('m.traore@transitflow.ca', 'Moussa', 'Traore', 41, '819-555-0187', '455 boul. Jacques-Cartier, Sherbrooke',
     'T5678-410602-14', 540, 'disponible', 'QC-1094'),
    ('s.fortin@transitflow.ca', 'Sophie', 'Fortin', 29, '418-555-0103', '8 rue Saint-Jean, Quebec',
     'F9012-290815-09', 300, 'disponible', 'QC-7733'),
    ('m.barry@transitflow.ca', 'Mamadou', 'Barry', 27, '819-555-0104', "2500 boul. de l Universite, Sherbrooke",
     'B3456-270210-21', 20, 'hors-service', 'QC-2287'),
]


class Command(BaseCommand):
    help = 'Cree les comptes et donnees de demonstration TransitFlow.'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true',
                            help='Supprime vehicules, chauffeurs, trajets, incidents et comptes non administrateurs.')
        parser.add_argument('--mot-de-passe', default=MOT_DE_PASSE_PAR_DEFAUT,
                            help='Mot de passe de tous les comptes de demonstration.')
        parser.add_argument('--force', action='store_true', help='Autorise l execution en production.')

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG and not options['force']:
            raise CommandError('TF_DEBUG=0 : ajoutez --force pour creer des donnees de demonstration en production.')
        mot_de_passe = options['mot_de_passe']

        if options['reset']:
            Incident.objects.all().delete()
            Trajet.objects.all().delete()
            Utilisateur.objects.filter(chauffeur__isnull=False).delete()
            Chauffeur.objects.all().delete()
            Vehicule.objects.all().delete()

        groupe_admin, _ = Group.objects.get_or_create(name='fleet.admin')
        groupe_chauffeur, _ = Group.objects.get_or_create(name='fleet.driver')

        for plaque, modele in VEHICULES:
            Vehicule.objects.get_or_create(plaque=plaque, defaults={'modele': modele})

        courriel_admin, nom_admin = ADMIN
        if not Utilisateur.objects.filter(courriel=courriel_admin).exists():
            admin = Utilisateur.objects.create_user(courriel=courriel_admin, mot_de_passe=mot_de_passe,
                                                    nom=nom_admin)
            admin.groups.add(groupe_admin)

        aujourdhui = timezone.localdate()
        chauffeurs = {}
        for (courriel, prenom, nom, age, telephone, adresse, permis, jours_permis,
             statut, plaque) in CHAUFFEURS:
            chauffeur, cree = Chauffeur.objects.get_or_create(courriel=courriel, defaults=dict(
                prenom=prenom, nom=nom, age=age, telephone=telephone, adresse=adresse, permis_numero=permis,
                permis_expiration=aujourdhui + timedelta(days=jours_permis), statut=statut,
                plaque_habituelle_id=plaque,
            ))
            chauffeurs[courriel] = chauffeur
            if not Utilisateur.objects.filter(courriel=courriel).exists():
                compte = Utilisateur.objects.create_user(courriel=courriel, mot_de_passe=mot_de_passe,
                                                         nom=chauffeur.nom_complet, chauffeur=chauffeur)
                compte.groups.add(groupe_chauffeur)

        def a(jours, heure):
            h, m = map(int, heure.split(':'))
            jour = aujourdhui + timedelta(days=jours)
            return timezone.make_aware(datetime.combine(jour, datetime.min.time()) + timedelta(hours=h, minutes=m))

        if not Trajet.objects.exists():
            self._creer_trajets(chauffeurs, aujourdhui, a)

        self.stdout.write(self.style.SUCCESS(
            'Donnees de demonstration pretes.\n'
            f'  Administrateur : {courriel_admin}\n'
            f'  Chauffeurs     : {", ".join(c[0] for c in CHAUFFEURS)}\n'
            f'  Mot de passe   : {mot_de_passe}'
        ))

    def _creer_trajets(self, chauffeurs, aujourdhui: date, a):
        diallo = chauffeurs['a.diallo@transitflow.ca']
        traore = chauffeurs['m.traore@transitflow.ca']
        fortin = chauffeurs['s.fortin@transitflow.ca']

        # Historique (trajets termines).
        historiques = [
            (traore, 'QC-1094', 'Sherbrooke', 'Montreal', -1, '07:00', '09:15', '09:05'),
            (fortin, 'QC-7733', 'Quebec', 'Levis', -2, '13:10', '13:50', '13:48'),
            (diallo, 'QC-4821', 'Sherbrooke', 'Magog', -3, '07:30', '08:15', '08:20'),
        ]
        for chauffeur, plaque, depart, arrivee, jours, h_debut, h_prevue, h_fin in historiques:
            trajet = Trajet.objects.create(
                chauffeur=chauffeur, plaque=plaque, depart=depart, arrivee=arrivee,
                depart_adresse=f'Terminus {depart}', debut=a(jours, h_debut), fin_prevue=a(jours, h_prevue),
                fin=a(jours, h_fin), statut='termine',
            )
            Arret.objects.create(trajet=trajet, lieu='Halte routiere', heure=h_debut[:3] + '30', note='Arret regulier')

        traite = Trajet.objects.filter(chauffeur=traore).first()
        Incident.objects.create(
            trajet=traite, chauffeur=traore, type='route', titre='Bouchon sur l autoroute 10',
            description='Accident sur la voie de gauche, 20 minutes de retard.', lieu='A-10, sortie 90',
            date=aujourdhui - timedelta(days=1), heure='07:40', statut='traite',
        )

        # Trajet en cours pour Aminata Diallo, commence il y a 40 minutes.
        maintenant = timezone.localtime()
        debut = maintenant - timedelta(minutes=40)
        en_cours = Trajet.objects.create(
            chauffeur=diallo, plaque='QC-4821', depart='Sherbrooke', arrivee='Granby',
            depart_adresse='Terminus Sherbrooke, 60 rue Depot', debut=debut,
            fin_prevue=debut + timedelta(minutes=75), statut='en-cours',
        )
        Arret.objects.create(trajet=en_cours, lieu='Orford', heure=(debut + timedelta(minutes=20)).strftime('%H:%M'),
                             note='Deux passagers descendus')
        Incident.objects.create(
            trajet=en_cours, chauffeur=diallo, type='technique', titre='Voyant moteur allume',
            description='Voyant moteur orange apres l arret d Orford, vehicule toujours roulant.',
            lieu='Autoroute 10, sortie 115', date=aujourdhui,
            heure=(debut + timedelta(minutes=30)).strftime('%H:%M'), statut='ouvert',
        )

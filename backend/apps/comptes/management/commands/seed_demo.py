"""
TransitFlow — Donnees de demonstration
Auteur : Jonathan K-N

Recree un jeu de donnees realiste (vehicules et leur compteur, un
administrateur, quatre chauffeurs avec leur compte, trajets, arrets,
incidents, plans d entretien preventif et bons de travail) equivalent au
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
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.comptes.models import Utilisateur
from apps.dispatch.models import Arret, Trajet
from apps.drivers.models import Chauffeur
from apps.entretien.models import BonTravail, PlanEntretien
from apps.entretien import services as entretien
from apps.fleet.models import ReleveKilometrage, Vehicule
from apps.fleet.services import enregistrer_kilometrage
from apps.maintenance.models import Incident
from apps.suivi.models import PositionGPS

MOT_DE_PASSE_PAR_DEFAUT = 'Transit-Demo-2026'
ADMIN = ('a.tremblay@transitflow.ca', 'Alex Tremblay')

# (plaque, modele, annee, kilometrage actuel, mise en service il y a N jours)
VEHICULES = [
    ('QC-4821', 'Ford Transit', 2023, 48210, 820),
    ('QC-1094', 'Mercedes-Benz Sprinter', 2022, 91540, 1180),
    ('QC-7733', 'Ford Transit', 2024, 17350, 310),
    ('QC-2287', 'Nissan NV200', 2021, 126800, 1560),
    ('QC-5512', 'Ford Transit', 2022, 73020, 1050),
]

# Programme preventif type d une navette : (type, libelle, intervalle km, intervalle jours)
PROGRAMME_PREVENTIF = [
    ('vidange', 'Vidange moteur et filtre a huile', 8000, 180),
    ('inspection', 'Inspection mecanique obligatoire', None, 365),
    ('freins', 'Controle des freins', 30000, None),
    ('pneus', 'Permutation des pneus', 10000, None),
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
            BonTravail.objects.all().delete()
            PlanEntretien.objects.all().delete()
            Incident.objects.all().delete()
            Trajet.objects.all().delete()
            Utilisateur.objects.filter(chauffeur__isnull=False).delete()
            Chauffeur.objects.all().delete()
            Vehicule.objects.all().delete()

        groupe_admin, _ = Group.objects.get_or_create(name='fleet.admin')
        groupe_chauffeur, _ = Group.objects.get_or_create(name='fleet.driver')

        aujourdhui = timezone.localdate()
        for plaque, modele, annee, kilometrage, jours_service in VEHICULES:
            vehicule, cree = Vehicule.objects.get_or_create(plaque=plaque, defaults={
                'modele': modele, 'annee': annee,
                'mise_en_service': aujourdhui - timedelta(days=jours_service),
            })
            if cree or not vehicule.releves.exists():
                # Historique : un releve il y a 120 jours (~100 km/jour), pour que le
                # cout au km de la demonstration porte sur une distance realiste.
                ancien = enregistrer_kilometrage(vehicule, max(0, kilometrage - 12000), source='initial',
                                                 note='Donnees de demonstration')
                ReleveKilometrage.objects.filter(pk=ancien.pk).update(
                    releve_le=timezone.now() - timedelta(days=120))
                enregistrer_kilometrage(vehicule, kilometrage, source='manuel', note='Donnees de demonstration')

        courriel_admin, nom_admin = ADMIN
        if not Utilisateur.objects.filter(courriel=courriel_admin).exists():
            admin = Utilisateur.objects.create_user(courriel=courriel_admin, mot_de_passe=mot_de_passe,
                                                    nom=nom_admin)
            admin.groups.add(groupe_admin)

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
        if not PlanEntretien.objects.exists():
            self._creer_entretien(aujourdhui)

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
        self._creer_trace_gps(en_cours, maintenant)
        Incident.objects.create(
            trajet=en_cours, chauffeur=diallo, type='technique', titre='Voyant moteur allume',
            description='Voyant moteur orange apres l arret d Orford, vehicule toujours roulant.',
            lieu='Autoroute 10, sortie 115', date=aujourdhui,
            heure=(debut + timedelta(minutes=30)).strftime('%H:%M'), statut='ouvert',
        )

    def _creer_entretien(self, aujourdhui: date):
        """
        Un programme preventif par vehicule, avec des echeances variees pour
        que le tableau de bord montre des retards, des alertes proches et
        des entretiens a jour ; plus quelques bons de travail (termines avec
        leurs couts, en cours, planifies, et un correctif issu d un incident).
        """
        admin = Utilisateur.objects.filter(courriel=ADMIN[0]).first()
        # Decalage du dernier entretien par vehicule : (km parcourus depuis, jours ecoules depuis).
        decalages = {
            'QC-4821': (7400, 150),   # vidange imminente
            'QC-1094': (8600, 200),   # vidange en retard
            'QC-7733': (2100, 40),    # tout est a jour
            'QC-2287': (5200, 350),   # inspection annuelle imminente
            'QC-5512': (3900, 90),
        }
        plans = {}
        for vehicule in Vehicule.objects.all():
            km_depuis, jours_depuis = decalages.get(vehicule.plaque, (1000, 30))
            for type_, libelle, intervalle_km, intervalle_jours in PROGRAMME_PREVENTIF:
                plans[(vehicule.plaque, type_)] = PlanEntretien.objects.create(
                    vehicule=vehicule, type=type_, libelle=libelle, intervalle_km=intervalle_km,
                    intervalle_jours=intervalle_jours,
                    dernier_km=max(0, vehicule.kilometrage - km_depuis),
                    derniere_date=aujourdhui - timedelta(days=jours_depuis),
                )

        def bon(plaque, jours, **champs):
            vehicule = Vehicule.objects.get(plaque=plaque)
            return BonTravail.objects.create(vehicule=vehicule, cree_par=admin,
                                             date_prevue=aujourdhui + timedelta(days=jours), **champs)

        # Historique : interventions terminees avec leurs couts.
        historique = [
            ('QC-1094', -60, 'correctif', 'freins', 'Remplacement des plaquettes avant', 'Garage Sherbrooke Auto',
             '248.60', '180.00'),
            ('QC-2287', -35, 'correctif', 'electrique', 'Batterie remplacee', 'Canadian Tire Sherbrooke',
             '219.99', '45.00'),
            ('QC-5512', -20, 'correctif', 'pneus', 'Reparation crevaison arriere gauche', 'Pneus Estrie',
             '35.00', '40.00'),
        ]
        for plaque, jours, categorie, type_, titre, fournisseur, pieces, main_oeuvre in historique:
            b = bon(plaque, jours, categorie=categorie, type=type_, titre=titre, fournisseur=fournisseur)
            entretien.terminer(b, auteur=admin, date_fin=aujourdhui + timedelta(days=jours),
                               cout_pieces=Decimal(pieces), cout_main_oeuvre=Decimal(main_oeuvre))

        # Vidange en retard du Sprinter : planifiee demain.
        bon('QC-1094', 1, categorie='preventif', type='vidange', titre=plans[('QC-1094', 'vidange')].libelle,
            plan=plans[('QC-1094', 'vidange')], priorite='haute', fournisseur='Garage Sherbrooke Auto',
            cout_pieces=Decimal('89.00'), cout_main_oeuvre=Decimal('60.00'))

        # Le NV200 est au garage (bon en cours -> vehicule en maintenance).
        en_cours = bon('QC-2287', 0, categorie='correctif', type='climatisation',
                       titre='Climatisation ne refroidit plus',
                       description='Recharge de gaz et recherche de fuite.', fournisseur='Clim Auto Estrie')
        entretien.demarrer(en_cours)

        # Correctif a planifier a partir de l incident "voyant moteur" du trajet en cours.
        incident = Incident.objects.filter(type='technique', statut='ouvert').first()
        if incident and incident.trajet_id:
            bon(incident.trajet.plaque, 2, categorie='correctif', type='reparation', titre=incident.titre,
                description=incident.description, incident=incident, priorite='urgente')

    def _creer_trace_gps(self, trajet, maintenant):
        """
        Trace GPS du trajet en cours (Sherbrooke -> Magog par l autoroute 10),
        un point par minute, le dernier il y a 20 s : le vehicule apparait
        "en ligne" sur la carte en direct des le chargement de la demo.
        """
        jalons = [(45.4042, -71.8929), (45.3905, -71.9480), (45.3610, -72.0105), (45.3250, -72.0740),
                  (45.2950, -72.1180), (45.2667, -72.1486)]
        minutes = int((maintenant - trajet.debut).total_seconds() // 60)
        total = 75  # duree prevue du trajet, en minutes
        points = []
        for m in range(minutes + 1):
            avancement = min(m / total, 1) * (len(jalons) - 1)
            i = min(int(avancement), len(jalons) - 2)
            f = avancement - i
            lat = jalons[i][0] + (jalons[i + 1][0] - jalons[i][0]) * f
            lng = jalons[i][1] + (jalons[i + 1][1] - jalons[i][1]) * f
            instant = maintenant - timedelta(seconds=20) - timedelta(minutes=minutes - m)
            points.append(PositionGPS(trajet=trajet, chauffeur=trajet.chauffeur, plaque=trajet.plaque,
                                      latitude=round(lat, 6), longitude=round(lng, 6), precision_m=8,
                                      vitesse_kmh=0 if m in (20, 21) else 92, cap=240, horodatage=instant))
        PositionGPS.objects.bulk_create(points)

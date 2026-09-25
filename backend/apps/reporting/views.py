"""
TransitFlow — Indicateurs du tableau de bord
Auteur : Jonathan K-N

Equivalent de Store.indicateurs() dans les versions precedentes. Utilise
l heure reelle (timezone.now()) plutot qu une date figee en dur, pour
fonctionner correctement quel que soit le fuseau horaire du client.
"""

from datetime import timedelta

from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.comptes.permissions import DansGroupe
from apps.dispatch.models import Trajet
from apps.drivers.models import Chauffeur
from apps.entretien.models import BonTravail, PlanEntretien
from apps.fleet.models import Vehicule
from apps.maintenance.models import Incident

# Un permis est considere "a renouveler bientot" s il expire dans les 60 jours.
FENETRE_PERMIS_JOURS = 60


class IndicateursView(APIView):
    permission_classes = [DansGroupe('fleet.admin')]

    def get(self, request):
        aujourdhui = timezone.localdate()
        limite_permis = aujourdhui + timedelta(days=FENETRE_PERMIS_JOURS)

        indicateurs = {
            'chauffeursActifs': Chauffeur.objects.exclude(statut='hors-service').count(),
            'trajetsEnCours': Trajet.objects.filter(statut='en-cours').count(),
            'trajetsDuJour': Trajet.objects.filter(debut__date=aujourdhui).count(),
            'incidentsOuverts': Incident.objects.filter(statut='ouvert').count(),
            'incidentsDuJour': Incident.objects.filter(date=aujourdhui).count(),
            'permisAExpirer': Chauffeur.objects.filter(permis_expiration__lt=limite_permis).count(),
            **_indicateurs_entretien(aujourdhui),
        }
        return Response({'ok': True, 'indicateurs': indicateurs})


def _indicateurs_entretien(aujourdhui):
    """Etat de la flotte vu par l atelier (voir apps/entretien)."""
    etats = {'en-retard': 0, 'bientot': 0, 'a-jour': 0}
    plans = PlanEntretien.objects.filter(actif=True, vehicule__statut__in=['actif', 'maintenance']) \
        .select_related('vehicule')
    for plan in plans:
        etats[plan.echeance(aujourdhui)['etat']] += 1
    return {
        'vehiculesDisponibles': Vehicule.objects.filter(statut='actif').count(),
        'vehiculesEnMaintenance': Vehicule.objects.filter(statut='maintenance').count(),
        'entretiensEnRetard': etats['en-retard'],
        'entretiensBientot': etats['bientot'],
        'bonsOuverts': BonTravail.objects.filter(statut__in=BonTravail.STATUTS_OUVERTS).count(),
    }

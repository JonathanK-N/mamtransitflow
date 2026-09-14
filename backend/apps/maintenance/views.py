"""
TransitFlow — Routes incidents
Auteur : Jonathan K-N

  GET  /api/incidents               -> liste (filtres type/statut/chauffeurId)
  GET  /api/incidents/<code>        -> detail
  POST /api/incidents               -> signaler (reserve a 'fleet.driver')
  POST /api/incidents/<code>/traiter -> marquer traite (reserve a 'fleet.admin')
"""

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.comptes.permissions import DansGroupe, EstConnecte
from apps.dispatch.models import Trajet
from apps.drivers.models import Chauffeur
from .models import Incident
from .serializers import IncidentEntreeSerializer, IncidentSerializer


class IncidentsView(APIView):
    def get_permissions(self):
        classe = EstConnecte if self.request.method == 'GET' else DansGroupe('fleet.driver')
        return [classe()]

    def get(self, request):
        incidents = Incident.objects.select_related('trajet', 'chauffeur')
        type_ = request.query_params.get('type')
        if type_ and type_ != 'tous':
            incidents = incidents.filter(type=type_)
        statut = request.query_params.get('statut')
        if statut and statut != 'tous':
            incidents = incidents.filter(statut=statut)
        chauffeur_id = request.query_params.get('chauffeurId')
        if chauffeur_id:
            chauffeur = Chauffeur.depuis_code(chauffeur_id)
            incidents = incidents.filter(chauffeur=chauffeur) if chauffeur else incidents.none()
        return Response({'ok': True, 'incidents': IncidentSerializer(incidents, many=True).data})

    def post(self, request):
        if not request.user.chauffeur:
            return Response({'ok': False, 'message': 'Ce compte n est associe a aucune fiche chauffeur.'},
                             status=status.HTTP_403_FORBIDDEN)

        entree = IncidentEntreeSerializer(data=request.data)
        entree.is_valid(raise_exception=True)
        donnees = entree.validated_data

        trajet = None
        if donnees.get('trajetId'):
            trajet = Trajet.depuis_code(donnees['trajetId'])
            if not trajet:
                return Response({'ok': False, 'message': 'Trajet introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        incident = Incident.objects.create(
            trajet=trajet, chauffeur=request.user.chauffeur, type=donnees['type'], titre=donnees['titre'],
            description=donnees['description'], lieu=donnees['lieu'],
            date=donnees.get('date') or timezone.localdate(), heure=donnees['heure']
        )
        return Response({'ok': True, 'incident': IncidentSerializer(incident).data}, status=status.HTTP_201_CREATED)


class IncidentDetailView(APIView):
    permission_classes = [EstConnecte]

    def get(self, request, code):
        incident = Incident.depuis_code(code)
        if not incident:
            return Response({'ok': False, 'message': 'Incident introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'ok': True, 'incident': IncidentSerializer(incident).data})


class TraiterIncidentView(APIView):
    permission_classes = [DansGroupe('fleet.admin')]

    def post(self, request, code):
        incident = Incident.depuis_code(code)
        if not incident:
            return Response({'ok': False, 'message': 'Incident introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        incident.statut = 'traite'
        incident.save(update_fields=['statut'])
        return Response({'ok': True, 'incident': IncidentSerializer(incident).data})

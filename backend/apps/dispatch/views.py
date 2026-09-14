"""
TransitFlow — Routes trajets
Auteur : Jonathan K-N

  GET  /api/trajets                 -> liste (filtres statut/chauffeurId)
  GET  /api/trajets/en-cours/<code> -> trajet en cours d un chauffeur
  GET  /api/trajets/<code>          -> detail
  POST /api/trajets                 -> demarrer un trajet (reserve a 'fleet.driver')
  POST /api/trajets/<code>/arrets   -> ajouter un arret (chauffeur proprietaire seulement)
  POST /api/trajets/<code>/terminer -> terminer (chauffeur proprietaire seulement)

Le chauffeur d un trajet vient toujours du compte connecte
(request.user.chauffeur), jamais d une valeur envoyee par le client.
"""

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.comptes.permissions import DansGroupe, EstConnecte
from apps.drivers.models import Chauffeur
from .models import Arret, Trajet
from .serializers import ArretSerializer, TrajetSerializer


def _chauffeur_ou_403(request):
    if not request.user.chauffeur:
        return None
    return request.user.chauffeur


class TrajetsView(APIView):
    def get_permissions(self):
        classe = EstConnecte if self.request.method == 'GET' else DansGroupe('fleet.driver')
        return [classe()]

    def get(self, request):
        trajets = Trajet.objects.select_related('chauffeur').prefetch_related('arrets')
        statut = request.query_params.get('statut')
        if statut and statut != 'tous':
            trajets = trajets.filter(statut=statut)
        chauffeur_id = request.query_params.get('chauffeurId')
        if chauffeur_id:
            chauffeur = Chauffeur.depuis_code(chauffeur_id)
            trajets = trajets.filter(chauffeur=chauffeur) if chauffeur else trajets.none()
        return Response({'ok': True, 'trajets': TrajetSerializer(trajets, many=True).data})

    def post(self, request):
        chauffeur = _chauffeur_ou_403(request)
        if not chauffeur:
            return Response({'ok': False, 'message': 'Ce compte n est associe a aucune fiche chauffeur.'},
                             status=status.HTTP_403_FORBIDDEN)
        serializer = TrajetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        trajet = Trajet.objects.create(chauffeur=chauffeur, statut='en-cours', **{
            'plaque': serializer.validated_data['plaque'],
            'depart': serializer.validated_data['depart'],
            'depart_adresse': serializer.validated_data.get('depart_adresse'),
            'arrivee': serializer.validated_data['arrivee'],
            'debut': serializer.validated_data['debut'],
            'fin_prevue': serializer.validated_data['fin_prevue']
        })
        chauffeur.statut = 'en-trajet'
        chauffeur.save(update_fields=['statut'])
        return Response({'ok': True, 'trajet': TrajetSerializer(trajet).data}, status=status.HTTP_201_CREATED)


class TrajetEnCoursView(APIView):
    permission_classes = [EstConnecte]

    def get(self, request, code):
        chauffeur = Chauffeur.depuis_code(code)
        if not chauffeur:
            return Response({'ok': True, 'trajet': None})
        trajet = Trajet.objects.filter(chauffeur=chauffeur, statut='en-cours').first()
        return Response({'ok': True, 'trajet': TrajetSerializer(trajet).data if trajet else None})


class TrajetDetailView(APIView):
    permission_classes = [EstConnecte]

    def get(self, request, code):
        trajet = Trajet.depuis_code(code)
        if not trajet:
            return Response({'ok': False, 'message': 'Trajet introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'ok': True, 'trajet': TrajetSerializer(trajet).data})


class AjouterArretView(APIView):
    permission_classes = [DansGroupe('fleet.driver')]

    def post(self, request, code):
        trajet = Trajet.depuis_code(code)
        if not trajet:
            return Response({'ok': False, 'message': 'Trajet introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        if trajet.chauffeur_id != request.user.chauffeur_id:
            return Response({'ok': False, 'message': 'Acces refuse.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = ArretSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        Arret.objects.create(trajet=trajet, **serializer.validated_data)
        return Response({'ok': True, 'trajet': TrajetSerializer(trajet).data})


class TerminerTrajetView(APIView):
    permission_classes = [DansGroupe('fleet.driver')]

    def post(self, request, code):
        trajet = Trajet.depuis_code(code)
        if not trajet:
            return Response({'ok': False, 'message': 'Trajet introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        if trajet.chauffeur_id != request.user.chauffeur_id:
            return Response({'ok': False, 'message': 'Acces refuse.'}, status=status.HTTP_403_FORBIDDEN)

        trajet.statut = 'termine'
        trajet.fin = timezone.now()
        trajet.save(update_fields=['statut', 'fin'])
        trajet.chauffeur.statut = 'disponible'
        trajet.chauffeur.save(update_fields=['statut'])
        return Response({'ok': True, 'trajet': TrajetSerializer(trajet).data})

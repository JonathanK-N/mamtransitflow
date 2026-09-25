"""
TransitFlow — Routes du suivi GPS
Auteur : Jonathan K-N

  POST /api/trajets/<T-1>/positions -> lot de positions du chauffeur (trajet en cours, le sien)
  GET  /api/trajets/<T-1>/parcours  -> parcours complet + distance et vitesses (admin, ou chauffeur du trajet)
  GET  /api/suivi/en-direct         -> dernier point de chaque trajet en cours (admin)

Le temps reel repose sur des requetes HTTP courtes : le telephone envoie
ses points toutes les ~10 s, la carte de l administrateur se rafraichit
toutes les ~5 s. Ce choix fonctionne tel quel sur l hebergement actuel
(gunicorn, sans serveur Redis ni WebSocket a exploiter) et supporte
plusieurs dizaines de vehicules ; voir README (Suivi GPS).
"""

from django.db.models import OuterRef, Subquery
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.comptes.permissions import DansGroupe, voit_tout
from apps.dispatch.models import Trajet
from . import services
from .models import PositionGPS
from .serializers import LotPositionsSerializer, PositionSerializer


def _erreur(message, code):
    return Response({'ok': False, 'message': message}, status=code)


class PositionsView(APIView):
    permission_classes = [DansGroupe('fleet.driver')]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'positions'

    def post(self, request, code):
        trajet = Trajet.depuis_code(code)
        # Un chauffeur ne peut alimenter que son propre trajet : celui d un
        # autre repond 404 comme s il n existait pas.
        if not trajet or trajet.chauffeur_id != request.user.chauffeur_id:
            return _erreur('Trajet introuvable.', status.HTTP_404_NOT_FOUND)
        if trajet.statut != 'en-cours':
            return _erreur('Ce trajet est termine : le suivi GPS est arrete.', status.HTTP_409_CONFLICT)
        entree = LotPositionsSerializer(data=request.data)
        entree.is_valid(raise_exception=True)
        resultat = services.enregistrer_positions(trajet, entree.validated_data['positions'])
        return Response({'ok': True, **resultat})


class ParcoursView(APIView):
    def get(self, request, code):
        trajet = Trajet.depuis_code(code)
        if not trajet or not voit_tout(request.user, trajet.chauffeur):
            return _erreur('Trajet introuvable.', status.HTTP_404_NOT_FOUND)
        positions = list(trajet.positions.all())
        stats = services.statistiques(positions) if positions else {
            'distanceM': 0, 'dureeS': 0, 'vitesseMoyenneKmh': None, 'vitesseMaxKmh': None}
        derniere = positions[-1] if positions else None
        return Response({
            'ok': True,
            'trajetId': trajet.code,
            'statut': trajet.statut,
            'nombrePoints': len(positions),
            'positions': PositionSerializer(services.alleger(positions), many=True).data,
            'statistiques': stats,
            'liaison': services.etat_liaison(derniere, timezone.now()) if trajet.statut == 'en-cours' else None,
        })


class EnDirectView(APIView):
    permission_classes = [DansGroupe('fleet.admin')]

    def get(self, request):
        maintenant = timezone.now()
        derniere = PositionGPS.objects.filter(trajet=OuterRef('pk')).order_by('-horodatage')
        trajets = (Trajet.objects.filter(statut='en-cours').select_related('chauffeur')
                   .annotate(derniere_id=Subquery(derniere.values('pk')[:1])).order_by('debut'))
        positions = PositionGPS.objects.in_bulk([t.derniere_id for t in trajets if t.derniere_id])

        vehicules = []
        for t in trajets:
            p = positions.get(t.derniere_id)
            vehicules.append({
                'trajetId': t.code,
                'chauffeurId': t.chauffeur.code,
                'chauffeur': t.chauffeur.nom_complet,
                'telephone': t.chauffeur.telephone,
                'plaque': t.plaque,
                'depart': t.depart,
                'arrivee': t.arrivee,
                'debut': t.debut,
                'finPrevue': t.fin_prevue,
                'liaison': services.etat_liaison(p, maintenant),
                'position': PositionSerializer(p).data if p else None,
                'ageSecondes': round((maintenant - p.horodatage).total_seconds()) if p else None,
            })
        return Response({'ok': True, 'horodatage': maintenant, 'vehicules': vehicules})

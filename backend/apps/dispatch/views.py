"""
TransitFlow — Routes trajets
Auteur : Jonathan K-N

  GET  /api/trajets                 -> liste (filtres statut/chauffeurId)
  GET  /api/trajets/en-cours/<code> -> trajet en cours d un chauffeur
  GET  /api/trajets/<code>          -> detail
  POST /api/trajets                 -> demarrer un trajet (reserve a 'fleet.driver')
  POST /api/trajets/<code>/arrets   -> ajouter un arret (chauffeur proprietaire seulement)
  POST /api/trajets/<code>/terminer -> terminer (chauffeur proprietaire, ou administrateur) ;
                                       {kilometrage} facultatif = compteur du vehicule a l arrivee

Le chauffeur d un trajet vient toujours du compte connecte
(request.user.chauffeur), jamais d une valeur envoyee par le client.
Cloisonnement : un chauffeur ne voit que ses propres trajets ; ceux des
autres repondent 404 comme s ils n existaient pas.

Un trajet ne demarre qu avec un vehicule 'actif' : un vehicule en
maintenance (bon de travail en cours) ou hors service est refuse (409).
"""

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.comptes.permissions import DansGroupe, EstConnecte, est_admin, voit_tout
from apps.drivers.models import Chauffeur
from apps.fleet.models import Vehicule
from apps.fleet.services import enregistrer_kilometrage
from .models import Arret, Trajet
from .serializers import ArretSerializer, TerminerTrajetSerializer, TrajetSerializer


def _erreur(message, code):
    return Response({'ok': False, 'message': message}, status=code)


def _trajet_visible(request, code):
    """Le trajet demande s il existe ET que le compte connecte a le droit de le voir, sinon None."""
    trajet = Trajet.depuis_code(code)
    if not trajet or not voit_tout(request.user, trajet.chauffeur):
        return None
    return trajet


class TrajetsView(APIView):
    def get_permissions(self):
        classe = EstConnecte if self.request.method == 'GET' else DansGroupe('fleet.driver')
        return [classe()]

    def get(self, request):
        trajets = Trajet.objects.select_related('chauffeur').prefetch_related('arrets')
        if not est_admin(request.user):
            trajets = trajets.filter(chauffeur_id=request.user.chauffeur_id)
        statut = request.query_params.get('statut')
        if statut and statut != 'tous':
            trajets = trajets.filter(statut=statut)
        chauffeur_id = request.query_params.get('chauffeurId')
        if chauffeur_id:
            chauffeur = Chauffeur.depuis_code(chauffeur_id)
            trajets = trajets.filter(chauffeur=chauffeur) if chauffeur else trajets.none()
        return Response({'ok': True, 'trajets': TrajetSerializer(trajets, many=True).data})

    def post(self, request):
        if not request.user.chauffeur_id:
            return _erreur('Ce compte n est associe a aucune fiche chauffeur.', status.HTTP_403_FORBIDDEN)
        serializer = TrajetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        donnees = serializer.validated_data

        vehicule = Vehicule.objects.filter(plaque=donnees['plaque']).first()
        if not vehicule:
            return _erreur('Vehicule introuvable pour cette plaque.', status.HTTP_400_BAD_REQUEST)
        if not vehicule.disponible:
            return _erreur(f'Le vehicule {vehicule.plaque} est {vehicule.get_statut_display().lower()} : '
                           'choisissez un autre vehicule.', status.HTTP_409_CONFLICT)
        if donnees['fin_prevue'] <= donnees['debut']:
            return _erreur('L arrivee prevue doit etre posterieure au depart.', status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # Verrou sur la fiche : deux demarrages simultanes ne peuvent pas
            # creer deux trajets en cours pour le meme chauffeur.
            chauffeur = Chauffeur.objects.select_for_update().get(pk=request.user.chauffeur_id)
            if Trajet.objects.filter(chauffeur=chauffeur, statut='en-cours').exists():
                return _erreur('Un trajet est deja en cours : terminez-le avant d en demarrer un autre.',
                               status.HTTP_409_CONFLICT)
            # Verrou sur le vehicule : un bon de travail ne peut pas le passer
            # en maintenance pendant ce demarrage (voir apps/entretien/services.py).
            vehicule = Vehicule.objects.select_for_update().get(pk=vehicule.pk)
            if not vehicule.disponible:
                return _erreur(f'Le vehicule {vehicule.plaque} vient de passer '
                               f'{vehicule.get_statut_display().lower()}.', status.HTTP_409_CONFLICT)
            trajet = Trajet.objects.create(
                chauffeur=chauffeur, statut='en-cours', plaque=donnees['plaque'], depart=donnees['depart'],
                depart_adresse=donnees.get('depart_adresse'), arrivee=donnees['arrivee'],
                debut=donnees['debut'], fin_prevue=donnees['fin_prevue']
            )
            chauffeur.statut = 'en-trajet'
            chauffeur.save(update_fields=['statut'])
        return Response({'ok': True, 'trajet': TrajetSerializer(trajet).data}, status=status.HTTP_201_CREATED)


class TrajetEnCoursView(APIView):
    permission_classes = [EstConnecte]

    def get(self, request, code):
        chauffeur = Chauffeur.depuis_code(code)
        if not chauffeur or not voit_tout(request.user, chauffeur):
            return Response({'ok': True, 'trajet': None})
        trajet = Trajet.objects.filter(chauffeur=chauffeur, statut='en-cours').first()
        return Response({'ok': True, 'trajet': TrajetSerializer(trajet).data if trajet else None})


class TrajetDetailView(APIView):
    permission_classes = [EstConnecte]

    def get(self, request, code):
        trajet = _trajet_visible(request, code)
        if not trajet:
            return _erreur('Trajet introuvable.', status.HTTP_404_NOT_FOUND)
        return Response({'ok': True, 'trajet': TrajetSerializer(trajet).data})


class AjouterArretView(APIView):
    permission_classes = [DansGroupe('fleet.driver')]

    def post(self, request, code):
        trajet = Trajet.depuis_code(code)
        if not trajet:
            return _erreur('Trajet introuvable.', status.HTTP_404_NOT_FOUND)
        if trajet.chauffeur_id != request.user.chauffeur_id:
            return _erreur('Acces refuse.', status.HTTP_403_FORBIDDEN)
        if trajet.statut != 'en-cours':
            return _erreur('Ce trajet est termine : impossible d y ajouter un arret.', status.HTTP_400_BAD_REQUEST)

        serializer = ArretSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        Arret.objects.create(trajet=trajet, **serializer.validated_data)
        return Response({'ok': True, 'trajet': TrajetSerializer(trajet).data})


class TerminerTrajetView(APIView):
    """Le chauffeur termine son trajet ; l administrateur peut aussi en cloturer un (oubli, panne...)."""
    permission_classes = [EstConnecte]

    def post(self, request, code):
        trajet = Trajet.depuis_code(code)
        if not trajet:
            return _erreur('Trajet introuvable.', status.HTTP_404_NOT_FOUND)
        if not (est_admin(request.user) or trajet.chauffeur_id == request.user.chauffeur_id):
            return _erreur('Acces refuse.', status.HTTP_403_FORBIDDEN)
        if trajet.statut == 'termine':
            return _erreur('Ce trajet est deja termine.', status.HTTP_400_BAD_REQUEST)
        entree = TerminerTrajetSerializer(data=request.data)
        entree.is_valid(raise_exception=True)
        kilometrage = entree.validated_data.get('kilometrage')

        with transaction.atomic():
            # Compteur saisi a l arrivee (facultatif) : alimente le suivi
            # kilometrique et les echeances d entretien du vehicule. Une
            # valeur incoherente annule toute la cloture (reponse 400).
            if kilometrage is not None:
                vehicule = Vehicule.objects.filter(plaque=trajet.plaque).first()
                if vehicule:
                    enregistrer_kilometrage(vehicule, kilometrage, source='trajet', auteur=request.user,
                                            note=f'{trajet.code} — {trajet.depart} -> {trajet.arrivee}')
            trajet.statut = 'termine'
            trajet.fin = timezone.now()
            trajet.save(update_fields=['statut', 'fin'])
            trajet.chauffeur.statut = 'disponible'
            trajet.chauffeur.save(update_fields=['statut'])
        return Response({'ok': True, 'trajet': TrajetSerializer(trajet).data})

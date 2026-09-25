"""
TransitFlow — Routes vehicules
Auteur : Jonathan K-N

  GET   /api/vehicules                      -> liste (filtre ?statut=, ?disponible=1)
  POST  /api/vehicules                      -> ajout (reserve a 'fleet.admin')
  GET   /api/vehicules/<plaque>             -> fiche + derniers releves kilometriques
  PATCH /api/vehicules/<plaque>             -> mise a jour (admin) ; plaque et compteur exclus
  GET   /api/vehicules/<plaque>/kilometrage -> historique des releves (admin)
  POST  /api/vehicules/<plaque>/kilometrage -> nouveau releve (admin)

Les chauffeurs lisent la liste (pour choisir leur vehicule au depart
d un trajet) mais seuls les administrateurs voient la fiche detaillee et
modifient la flotte.
"""

from django.apps import apps
from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.comptes.permissions import DansGroupe, EstConnecte
from .models import Vehicule
from .serializers import (ReleveEntreeSerializer, ReleveKilometrageSerializer, VehiculeMajSerializer,
                          VehiculeSerializer)
from .services import enregistrer_kilometrage

NOMBRE_RELEVES_FICHE = 20


def _introuvable():
    return Response({'ok': False, 'message': 'Vehicule introuvable.'}, status=status.HTTP_404_NOT_FOUND)


def _vehicule(plaque):
    return Vehicule.objects.filter(plaque__iexact=(plaque or '').strip()).first()


class VehiculesView(APIView):
    def get_permissions(self):
        classe = EstConnecte if self.request.method == 'GET' else DansGroupe('fleet.admin')
        return [classe()]

    def get(self, request):
        vehicules = Vehicule.objects.all()
        statut = request.query_params.get('statut')
        if statut and statut != 'tous':
            vehicules = vehicules.filter(statut=statut)
        if request.query_params.get('disponible') in ('1', 'true'):
            vehicules = vehicules.filter(statut='actif')
        return Response({'ok': True, 'vehicules': VehiculeSerializer(vehicules, many=True).data})

    def post(self, request):
        serializer = VehiculeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            kilometrage = serializer.validated_data.pop('kilometrage', 0)
            vehicule = serializer.save(kilometrage=0)
            # Toujours un premier releve : l historique part de la valeur a l achat.
            enregistrer_kilometrage(vehicule, kilometrage, source='initial', auteur=request.user,
                                    note='Mise en flotte')
        return Response({'ok': True, 'vehicule': VehiculeSerializer(vehicule).data},
                        status=status.HTTP_201_CREATED)


class VehiculeDetailView(APIView):
    permission_classes = [DansGroupe('fleet.admin')]

    def get(self, request, plaque):
        vehicule = _vehicule(plaque)
        if not vehicule:
            return _introuvable()
        releves = vehicule.releves.select_related('auteur')[:NOMBRE_RELEVES_FICHE]
        chauffeurs = vehicule.chauffeurs.all()
        return Response({
            'ok': True,
            'vehicule': VehiculeSerializer(vehicule).data,
            'releves': ReleveKilometrageSerializer(releves, many=True).data,
            'chauffeursHabituels': [{'id': c.code, 'prenom': c.prenom, 'nom': c.nom} for c in chauffeurs],
        })

    def patch(self, request, plaque):
        vehicule = _vehicule(plaque)
        if not vehicule:
            return _introuvable()
        serializer = VehiculeMajSerializer(vehicule, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        nouveau_statut = serializer.validated_data.get('statut')
        if nouveau_statut and nouveau_statut != vehicule.statut:
            probleme = _probleme_changement_statut(vehicule, nouveau_statut)
            if probleme:
                return Response({'ok': False, 'message': probleme}, status=status.HTTP_409_CONFLICT)
        serializer.save()
        return Response({'ok': True, 'vehicule': VehiculeSerializer(vehicule).data})


def _probleme_changement_statut(vehicule: Vehicule, nouveau_statut: str) -> str:
    """Message d erreur si le changement de statut contredit l etat reel de la flotte, sinon ''."""
    Trajet = apps.get_model('dispatch', 'Trajet')
    BonTravail = apps.get_model('entretien', 'BonTravail')
    if nouveau_statut == 'hors-service' and Trajet.objects.filter(plaque=vehicule.plaque,
                                                                  statut='en-cours').exists():
        return 'Un trajet est en cours avec ce vehicule : terminez-le avant de le mettre hors service.'
    if nouveau_statut == 'actif' and BonTravail.objects.filter(vehicule=vehicule, statut='en-cours').exists():
        return 'Un bon de travail est en cours sur ce vehicule : terminez-le pour le remettre en service.'
    return ''


class KilometrageView(APIView):
    permission_classes = [DansGroupe('fleet.admin')]

    def get(self, request, plaque):
        vehicule = _vehicule(plaque)
        if not vehicule:
            return _introuvable()
        releves = vehicule.releves.select_related('auteur')
        return Response({'ok': True, 'releves': ReleveKilometrageSerializer(releves, many=True).data})

    def post(self, request, plaque):
        vehicule = _vehicule(plaque)
        if not vehicule:
            return _introuvable()
        entree = ReleveEntreeSerializer(data=request.data)
        entree.is_valid(raise_exception=True)
        releve = enregistrer_kilometrage(vehicule, entree.validated_data['kilometrage'], source='manuel',
                                         auteur=request.user, note=entree.validated_data['note'])
        return Response({
            'ok': True,
            'vehicule': VehiculeSerializer(vehicule).data,
            'releve': ReleveKilometrageSerializer(releve).data if releve else None,
        }, status=status.HTTP_201_CREATED if releve else status.HTTP_200_OK)

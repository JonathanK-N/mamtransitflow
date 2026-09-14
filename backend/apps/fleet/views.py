"""
TransitFlow — Routes vehicules
Auteur : Jonathan K-N

  GET  /api/vehicules -> liste des vehicules de la flotte
  POST /api/vehicules -> ajoute un vehicule (reserve a 'fleet.admin')
"""

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.comptes.permissions import DansGroupe, EstConnecte
from .models import Vehicule
from .serializers import VehiculeSerializer


class VehiculesView(APIView):
    def get_permissions(self):
        classe = EstConnecte if self.request.method == 'GET' else DansGroupe('fleet.admin')
        return [classe()]

    def get(self, request):
        vehicules = Vehicule.objects.all()
        return Response({'ok': True, 'vehicules': VehiculeSerializer(vehicules, many=True).data})

    def post(self, request):
        if Vehicule.objects.filter(plaque=request.data.get('plaque')).exists():
            return Response({'ok': False, 'message': 'Cette plaque existe deja.'},
                             status=status.HTTP_400_BAD_REQUEST)
        serializer = VehiculeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vehicule = serializer.save()
        return Response({'ok': True, 'vehicule': VehiculeSerializer(vehicule).data},
                         status=status.HTTP_201_CREATED)

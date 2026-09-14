"""TransitFlow — Schemas de l app fleet (vehicules)
   Auteur : Jonathan K-N"""

from rest_framework import serializers

from .models import Vehicule


class VehiculeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicule
        fields = ['plaque', 'modele']

"""TransitFlow — Schemas de l app suivi (positions GPS)
   Auteur : Jonathan K-N"""

from rest_framework import serializers

from .models import PositionGPS

TAILLE_MAXIMALE_LOT = 200


class PositionEntreeSerializer(serializers.Serializer):
    """Un point tel que l envoie assets/js/gps.js (champs de l API Geolocation du navigateur)."""
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lng = serializers.FloatField(min_value=-180, max_value=180)
    precision = serializers.FloatField(required=False, allow_null=True, min_value=0)
    vitesse = serializers.FloatField(required=False, allow_null=True, min_value=0, max_value=400)  # km/h
    cap = serializers.FloatField(required=False, allow_null=True, min_value=0, max_value=360)
    horodatage = serializers.DateTimeField()

    def validate(self, donnees):
        # (0, 0) est la valeur renvoyee par certains appareils quand le GPS n a pas encore de signal.
        if abs(donnees['lat']) < 1e-6 and abs(donnees['lng']) < 1e-6:
            raise serializers.ValidationError('Position invalide (0, 0).')
        return donnees


class LotPositionsSerializer(serializers.Serializer):
    positions = PositionEntreeSerializer(many=True, allow_empty=False, max_length=TAILLE_MAXIMALE_LOT)


class PositionSerializer(serializers.ModelSerializer):
    lat = serializers.FloatField(source='latitude')
    lng = serializers.FloatField(source='longitude')
    precision = serializers.FloatField(source='precision_m')
    vitesse = serializers.FloatField(source='vitesse_kmh')

    class Meta:
        model = PositionGPS
        fields = ['lat', 'lng', 'precision', 'vitesse', 'cap', 'horodatage']

"""TransitFlow — Schemas de l app maintenance (incidents)
   Auteur : Jonathan K-N"""

from rest_framework import serializers

from apps.dispatch.serializers import valider_heure
from .models import Incident

TYPES_VALIDES = {'technique', 'route'}


class IncidentSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source='code', read_only=True)
    trajetId = serializers.CharField(source='trajet.code', read_only=True, default=None)
    chauffeurId = serializers.CharField(source='chauffeur.code', read_only=True)

    class Meta:
        model = Incident
        fields = ['id', 'trajetId', 'chauffeurId', 'type', 'titre', 'description', 'lieu', 'date', 'heure', 'statut']
        read_only_fields = ['statut']

    def validate_type(self, valeur):
        if valeur not in TYPES_VALIDES:
            raise serializers.ValidationError('Type d incident invalide.')
        return valeur


class IncidentEntreeSerializer(serializers.Serializer):
    """Ce que le front-end envoie pour signaler un incident (voir chauffeur/incident-nouveau.html)."""
    trajetId = serializers.CharField(required=False, allow_null=True, default=None)
    type = serializers.ChoiceField(choices=list(TYPES_VALIDES))
    titre = serializers.CharField()
    description = serializers.CharField()
    lieu = serializers.CharField()
    date = serializers.DateField(required=False)
    heure = serializers.CharField(validators=[valider_heure])

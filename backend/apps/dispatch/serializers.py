"""TransitFlow — Schemas de l app dispatch (trajets, arrets)
   Auteur : Jonathan K-N"""

from rest_framework import serializers

from .models import Arret, Trajet


class ArretSerializer(serializers.ModelSerializer):
    class Meta:
        model = Arret
        fields = ['lieu', 'heure', 'note']


class TrajetSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source='code', read_only=True)
    chauffeurId = serializers.SerializerMethodField()
    departAdresse = serializers.CharField(source='depart_adresse', required=False, allow_null=True)
    finPrevue = serializers.DateTimeField(source='fin_prevue')
    arrets = ArretSerializer(many=True, read_only=True)

    class Meta:
        model = Trajet
        fields = ['id', 'chauffeurId', 'plaque', 'depart', 'departAdresse', 'arrivee',
                  'debut', 'finPrevue', 'fin', 'statut', 'arrets']
        read_only_fields = ['fin', 'statut']

    def get_chauffeurId(self, obj):
        return obj.chauffeur.code

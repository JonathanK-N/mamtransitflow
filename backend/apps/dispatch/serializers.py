"""TransitFlow — Schemas de l app dispatch (trajets, arrets)
   Auteur : Jonathan K-N"""

import re

from rest_framework import serializers

from .models import Arret, Trajet


def valider_heure(valeur: str) -> str:
    """Heure "HH:MM" sur 24 h : la frise du front-end trie ces heures comme du texte."""
    if not re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d', valeur or ''):
        raise serializers.ValidationError('Heure invalide (format attendu HH:MM).')
    return valeur


class ArretSerializer(serializers.ModelSerializer):
    heure = serializers.CharField(validators=[valider_heure])

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


class TerminerTrajetSerializer(serializers.Serializer):
    """Corps (facultatif) de POST /api/trajets/<code>/terminer."""
    kilometrage = serializers.IntegerField(required=False, allow_null=True, min_value=0, max_value=5_000_000)

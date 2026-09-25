"""TransitFlow — Schemas de l app fleet (vehicules, releves kilometriques)
   Auteur : Jonathan K-N

   Noms de champs en camelCase (numeroSerie, miseEnService...) comme dans
   le reste de l API, colonnes en snake_case en base (via `source=`)."""

import re

from django.utils import timezone
from rest_framework import serializers

from .models import ReleveKilometrage, Vehicule

ANNEE_MINIMALE = 1980
# NIV (numero d identification du vehicule) : 17 caracteres, sans I, O ni Q.
_FORMAT_NIV = re.compile(r'[A-HJ-NPR-Z0-9]{17}')


class VehiculeSerializer(serializers.ModelSerializer):
    numeroSerie = serializers.CharField(source='numero_serie', required=False, allow_blank=True, max_length=17)
    miseEnService = serializers.DateField(source='mise_en_service', required=False, allow_null=True)
    kilometrage = serializers.IntegerField(required=False, min_value=0, max_value=5_000_000)
    disponible = serializers.BooleanField(read_only=True)

    class Meta:
        model = Vehicule
        fields = ['plaque', 'modele', 'annee', 'numeroSerie', 'kilometrage', 'statut', 'miseEnService',
                  'disponible']
        read_only_fields = ['statut']
        # L unicite de la plaque est verifiee dans validate_plaque (message en francais, insensible a la casse).
        extra_kwargs = {'plaque': {'validators': []}}

    def validate_plaque(self, valeur):
        valeur = re.sub(r'\s+', ' ', valeur.strip().upper())
        if not valeur:
            raise serializers.ValidationError('La plaque est obligatoire.')
        if not re.fullmatch(r'[A-Z0-9][A-Z0-9 -]*', valeur):
            raise serializers.ValidationError('Plaque invalide (lettres, chiffres, espaces et tirets seulement).')
        if Vehicule.objects.filter(plaque__iexact=valeur).exists():
            raise serializers.ValidationError('Cette plaque existe deja.')
        return valeur

    def validate_modele(self, valeur):
        valeur = valeur.strip()
        if not valeur:
            raise serializers.ValidationError('Le modele est obligatoire.')
        return valeur

    def validate_annee(self, valeur):
        if valeur is None:
            return None
        maximum = timezone.localdate().year + 1
        if not ANNEE_MINIMALE <= valeur <= maximum:
            raise serializers.ValidationError(f'Annee invalide (entre {ANNEE_MINIMALE} et {maximum}).')
        return valeur

    def validate_numeroSerie(self, valeur):
        valeur = (valeur or '').strip().upper()
        if valeur and not _FORMAT_NIV.fullmatch(valeur):
            raise serializers.ValidationError('NIV invalide : 17 caracteres, lettres (sauf I, O, Q) et chiffres.')
        return valeur

    def validate_miseEnService(self, valeur):
        if valeur and valeur > timezone.localdate():
            raise serializers.ValidationError('La date de mise en service ne peut pas etre dans le futur.')
        return valeur


class VehiculeMajSerializer(VehiculeSerializer):
    """
    PATCH d un vehicule. La plaque est l identifiant (reprise telle quelle
    dans les trajets et les fiches chauffeurs) : elle ne se modifie pas. Le
    compteur passe par POST /api/vehicules/<plaque>/kilometrage (historique).
    Le statut se modifie ici, avec les regles de VehiculeDetailView.patch.
    """
    statut = serializers.ChoiceField(choices=['actif', 'hors-service'], required=False)
    kilometrage = serializers.IntegerField(read_only=True)

    class Meta(VehiculeSerializer.Meta):
        read_only_fields = ['plaque', 'kilometrage']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for champ in self.fields.values():
            champ.required = False


class ReleveKilometrageSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)
    auteur = serializers.SerializerMethodField()
    releveLe = serializers.DateTimeField(source='releve_le', read_only=True)

    class Meta:
        model = ReleveKilometrage
        fields = ['id', 'kilometrage', 'source', 'note', 'auteur', 'releveLe']

    def get_auteur(self, obj):
        if not obj.auteur:
            return None
        return obj.auteur.nom or obj.auteur.courriel


class ReleveEntreeSerializer(serializers.Serializer):
    kilometrage = serializers.IntegerField(min_value=0, max_value=5_000_000)
    note = serializers.CharField(required=False, allow_blank=True, max_length=255, default='')

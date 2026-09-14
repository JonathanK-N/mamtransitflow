"""
TransitFlow — Schemas de l app drivers (chauffeurs)
Auteur : Jonathan K-N

Les noms de champs (permisNumero, permisExpiration, plaqueHabituelle,
creeLe...) reprennent exactement ceux attendus par assets/js/admin.js et
assets/js/chauffeur.js, meme si les colonnes en base sont en snake_case
(permis_numero, ...) -- c est le role du `source=` de chaque champ.
"""

from rest_framework import serializers

from .models import Chauffeur


class ChauffeurSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source='code', read_only=True)
    permisNumero = serializers.CharField(source='permis_numero')
    permisExpiration = serializers.DateField(source='permis_expiration')
    plaqueHabituelle = serializers.CharField(source='plaque_habituelle_id', required=False, allow_null=True)
    creeLe = serializers.DateTimeField(source='cree_le', read_only=True)

    class Meta:
        model = Chauffeur
        fields = ['id', 'prenom', 'nom', 'age', 'telephone', 'courriel', 'adresse',
                  'permisNumero', 'permisExpiration', 'statut', 'plaqueHabituelle', 'creeLe']

    def validate_plaqueHabituelle(self, valeur):
        if valeur is None:
            return None
        from apps.fleet.models import Vehicule
        if not Vehicule.objects.filter(plaque=valeur).exists():
            raise serializers.ValidationError('Vehicule introuvable pour cette plaque.')
        return valeur


class ChauffeurMajSerializer(ChauffeurSerializer):
    """Meme schema, mais tous les champs deviennent facultatifs (utilise pour PATCH)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for champ in self.fields.values():
            champ.required = False

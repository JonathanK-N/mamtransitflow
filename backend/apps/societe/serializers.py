"""TransitFlow — Schemas de l app societe (noms de champs en camelCase pour le front-end)
   Auteur : Jonathan K-N"""

from rest_framework import serializers

from .models import Entreprise

CHAMPS = {
    'nom': 'nom', 'courriel': 'courriel', 'telephone': 'telephone', 'adresse': 'adresse', 'ville': 'ville',
    'province': 'province', 'codePostal': 'code_postal', 'neq': 'neq',
}
MODULES = {'entretien': 'module_entretien', 'suivi': 'module_suivi', 'paie': 'module_paie'}
PORTAIL = {'trajets': 'portail_trajets', 'incidents': 'portail_incidents', 'vehicule': 'portail_vehicule',
           'paie': 'portail_paie', 'profil': 'portail_profil'}


def entreprise_en_json(e: Entreprise) -> dict:
    return {
        **{cle: getattr(e, champ) for cle, champ in CHAMPS.items()},
        'modules': {cle: getattr(e, champ) for cle, champ in MODULES.items()},
        # Ce que le portail chauffeur affiche vraiment (tient compte des modules).
        'portail': {cle: e.portail_autorise(cle) for cle in PORTAIL},
        # Les cases cochees par l administrateur, meme si le module est desactive.
        'portailReglages': {cle: getattr(e, champ) for cle, champ in PORTAIL.items()},
    }


class EntrepriseMajSerializer(serializers.Serializer):
    nom = serializers.CharField(max_length=150, required=False)
    courriel = serializers.EmailField(required=False, allow_blank=True)
    telephone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    adresse = serializers.CharField(max_length=255, required=False, allow_blank=True)
    ville = serializers.CharField(max_length=100, required=False, allow_blank=True)
    province = serializers.CharField(max_length=50, required=False, allow_blank=True)
    codePostal = serializers.CharField(max_length=10, required=False, allow_blank=True)
    neq = serializers.CharField(max_length=20, required=False, allow_blank=True)
    modules = serializers.DictField(child=serializers.BooleanField(), required=False)
    portail = serializers.DictField(child=serializers.BooleanField(), required=False)

    def validate_nom(self, valeur):
        if not valeur.strip():
            raise serializers.ValidationError('Le nom de l entreprise est obligatoire.')
        return valeur.strip()

    def validate_modules(self, valeur):
        inconnus = set(valeur) - set(MODULES)
        if inconnus:
            raise serializers.ValidationError(f'Module inconnu : {", ".join(sorted(inconnus))}.')
        return valeur

    def validate_portail(self, valeur):
        inconnus = set(valeur) - set(PORTAIL)
        if inconnus:
            raise serializers.ValidationError(f'Droit de portail inconnu : {", ".join(sorted(inconnus))}.')
        return valeur

    def appliquer(self, entreprise: Entreprise) -> Entreprise:
        d = self.validated_data
        for cle, champ in CHAMPS.items():
            if cle in d:
                setattr(entreprise, champ, d[cle])
        for cle, actif in d.get('modules', {}).items():
            setattr(entreprise, MODULES[cle], actif)
        for cle, actif in d.get('portail', {}).items():
            setattr(entreprise, PORTAIL[cle], actif)
        entreprise.save()
        return entreprise

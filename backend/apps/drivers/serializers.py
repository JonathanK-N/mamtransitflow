"""
TransitFlow — Schemas de l app drivers (chauffeurs)
Auteur : Jonathan K-N

Les noms de champs (permisNumero, permisExpiration, plaqueHabituelle,
creeLe...) reprennent exactement ceux attendus par assets/js/admin.js et
assets/js/chauffeur.js, meme si les colonnes en base sont en snake_case
(permis_numero, ...) -- c est le role du `source=` de chaque champ.
"""

from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils.crypto import get_random_string
from rest_framework import serializers

from .models import Chauffeur


class ChauffeurSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source='code', read_only=True)
    permisNumero = serializers.CharField(source='permis_numero')
    permisExpiration = serializers.DateField(source='permis_expiration')
    plaqueHabituelle = serializers.CharField(source='plaque_habituelle_id', required=False, allow_null=True,
                                             allow_blank=True)
    creeLe = serializers.DateTimeField(source='cree_le', read_only=True)
    aUnCompte = serializers.SerializerMethodField()
    acces = serializers.SerializerMethodField()

    class Meta:
        model = Chauffeur
        fields = ['id', 'prenom', 'nom', 'age', 'telephone', 'courriel', 'adresse',
                  'permisNumero', 'permisExpiration', 'statut', 'plaqueHabituelle', 'creeLe', 'aUnCompte', 'acces']

    def get_aUnCompte(self, obj) -> bool:
        return hasattr(obj, 'compte')

    def get_acces(self, obj) -> dict:
        """Acces au portail : aucun, invite (lien en attente), expire, actif ou desactive."""
        from apps.comptes.invitations import statut_acces
        return statut_acces(obj)

    def validate_plaqueHabituelle(self, valeur):
        # Le formulaire envoie '' quand "Aucun vehicule" est choisi.
        if not valeur:
            return None
        from apps.fleet.models import Vehicule
        if not Vehicule.objects.filter(plaque=valeur).exists():
            raise serializers.ValidationError('Vehicule introuvable pour cette plaque.')
        return valeur

    def validate_courriel(self, valeur):
        valeur = valeur.strip().lower()
        autres = Chauffeur.objects.filter(courriel__iexact=valeur)
        if self.instance is not None:
            autres = autres.exclude(pk=self.instance.pk)
        if autres.exists():
            raise serializers.ValidationError('Un chauffeur utilise deja ce courriel.')
        return valeur


class ChauffeurCreationSerializer(ChauffeurSerializer):
    """
    Creation d une fiche chauffeur par l administrateur. Si `creerCompte`
    est vrai (c est le cas depuis admin/chauffeur-nouveau.html), le compte
    de connexion du chauffeur est cree dans la meme transaction, dans le
    groupe 'fleet.driver' : sans cela, le chauffeur ne pouvait pas se
    connecter. Si aucun mot de passe n est fourni, le serveur en genere un,
    renvoye une seule fois dans la reponse (motDePasseInitial).
    """
    creerCompte = serializers.BooleanField(write_only=True, required=False, default=False)
    # Envoie l invitation a rejoindre l entreprise des la creation (voir la vue).
    inviter = serializers.BooleanField(write_only=True, required=False, default=False)
    motDePasse = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta(ChauffeurSerializer.Meta):
        fields = ChauffeurSerializer.Meta.fields + ['creerCompte', 'motDePasse', 'inviter']

    def validate(self, donnees):
        from apps.comptes.models import Utilisateur

        donnees = super().validate(donnees)
        if donnees.get('motDePasse'):
            donnees['creerCompte'] = True
        if donnees.get('creerCompte'):
            if Utilisateur.objects.filter(courriel__iexact=donnees['courriel']).exists():
                raise serializers.ValidationError({'courriel': 'Un compte de connexion existe deja avec ce courriel.'})
            if donnees.get('motDePasse'):
                validate_password(donnees['motDePasse'])
        return donnees

    @transaction.atomic
    def create(self, donnees):
        from apps.comptes.models import Utilisateur

        creer_compte = donnees.pop('creerCompte', False)
        donnees.pop('inviter', None)
        mot_de_passe = donnees.pop('motDePasse', '') or None
        chauffeur = Chauffeur.objects.create(**donnees)

        if creer_compte:
            genere = mot_de_passe is None
            if genere:
                mot_de_passe = get_random_string(12)
            utilisateur = Utilisateur.objects.create_user(
                courriel=chauffeur.courriel, mot_de_passe=mot_de_passe, nom=chauffeur.nom_complet,
                chauffeur=chauffeur,
            )
            groupe, _ = Group.objects.get_or_create(name='fleet.driver')
            utilisateur.groups.add(groupe)
            if genere:
                chauffeur.mot_de_passe_genere = mot_de_passe
        return chauffeur


class ChauffeurMajSerializer(ChauffeurSerializer):
    """Meme schema, mais tous les champs deviennent facultatifs (utilise pour PATCH)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for champ in self.fields.values():
            champ.required = False

    def validate_courriel(self, valeur):
        from apps.comptes.models import Utilisateur

        valeur = super().validate_courriel(valeur)
        compte = getattr(self.instance, 'compte', None)
        if compte and Utilisateur.objects.filter(courriel__iexact=valeur).exclude(pk=compte.pk).exists():
            raise serializers.ValidationError('Un compte de connexion existe deja avec ce courriel.')
        return valeur

    @transaction.atomic
    def update(self, chauffeur, donnees):
        chauffeur = super().update(chauffeur, donnees)
        # Le courriel de connexion suit celui de la fiche.
        compte = getattr(chauffeur, 'compte', None)
        if compte and 'courriel' in donnees and compte.courriel != chauffeur.courriel:
            compte.courriel = chauffeur.courriel
            compte.save(update_fields=['courriel'])
        return chauffeur

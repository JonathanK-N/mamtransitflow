"""
TransitFlow — Schemas de l app comptes
Auteur : Jonathan K-N

Les noms de champs en sortie (`role`, `chauffeurId`, `initiales`...) sont
volontairement identiques a ceux que le front-end existant
(assets/js/auth.js) attend deja, pour que les pages HTML deja ecrites par
Mamadou continuent de fonctionner sans modification.
"""

from rest_framework import serializers

from .models import Utilisateur


def _role_depuis_groupes(utilisateur: Utilisateur) -> str:
    """Le front-end attend un seul 'role' (admin/chauffeur) ; on le deduit des groupes Django."""
    if utilisateur.a_groupe('fleet.admin'):
        return 'admin'
    if utilisateur.a_groupe('fleet.driver'):
        return 'chauffeur'
    return 'inconnu'


def _initiales(utilisateur: Utilisateur) -> str:
    if utilisateur.chauffeur:
        return (utilisateur.chauffeur.prenom[0] + utilisateur.chauffeur.nom[0]).upper()
    morceaux = utilisateur.nom.split()
    return ''.join(m[0] for m in morceaux[:2]).upper() or '??'


class SessionSerializer(serializers.Serializer):
    """La 'session' renvoyee a la connexion, telle qu attendue par Auth.connecter() cote front-end."""
    courriel = serializers.EmailField()
    role = serializers.SerializerMethodField()
    nom = serializers.SerializerMethodField()
    initiales = serializers.SerializerMethodField()
    chauffeurId = serializers.SerializerMethodField()

    def get_role(self, obj):
        return _role_depuis_groupes(obj)

    def get_nom(self, obj):
        return obj.chauffeur.nom_complet if obj.chauffeur else obj.nom

    def get_initiales(self, obj):
        return _initiales(obj)

    def get_chauffeurId(self, obj):
        return obj.chauffeur.code if obj.chauffeur else None


class ConnexionSerializer(serializers.Serializer):
    courriel = serializers.EmailField()
    # Mot de passe compare tel quel : DRF retire par defaut les espaces en
    # debut et fin de chaine, ce qui rendait inutilisable tout mot de passe
    # enregistre avec un espace (copier-coller dans une variable Railway).
    motDePasse = serializers.CharField(write_only=True, trim_whitespace=False)
    role = serializers.CharField(required=False, allow_blank=True)


class CompteEntreeSerializer(serializers.Serializer):
    """Cree un compte de connexion (route reservee a 'fleet.admin', voir views.py)."""
    courriel = serializers.EmailField()
    motDePasse = serializers.CharField(trim_whitespace=False)
    nom = serializers.CharField(required=False, allow_blank=True, default='')
    chauffeurId = serializers.CharField(required=False, allow_null=True, default=None)
    groupes = serializers.ListField(child=serializers.CharField(), default=['fleet.driver'])

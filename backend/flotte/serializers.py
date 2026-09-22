from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils.crypto import get_random_string
from rest_framework import serializers

from .models import Arret, Chauffeur, Incident, Profil, Trajet, Vehicule

User = get_user_model()


class VehiculeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicule
        fields = ["id", "plaque", "modele"]


class MoiSerializer(serializers.Serializer):
    """Représente l'utilisateur courant, façon `Auth.session()` du prototype JS.

    S'utilise avec un objet `User` (avec ses relations `profil` / `chauffeur`
    éventuelles) comme instance.
    """

    id = serializers.IntegerField()
    role = serializers.SerializerMethodField()
    nom = serializers.SerializerMethodField()
    initiales = serializers.SerializerMethodField()
    courriel = serializers.EmailField(source="email")
    chauffeur_id = serializers.SerializerMethodField()

    def get_role(self, user):
        return user.profil.role if hasattr(user, "profil") else None

    def get_nom(self, user):
        if hasattr(user, "chauffeur"):
            return user.chauffeur.nom_complet
        return user.get_full_name() or user.username

    def get_initiales(self, user):
        if hasattr(user, "chauffeur"):
            c = user.chauffeur
            return (c.prenom[:1] + c.nom[:1]).upper()
        return (user.first_name[:1] + user.last_name[:1]).upper() or user.username[:2].upper()

    def get_chauffeur_id(self, user):
        return user.chauffeur.id if hasattr(user, "chauffeur") else None


class ChauffeurSerializer(serializers.ModelSerializer):
    nom_complet = serializers.CharField(read_only=True)
    plaque_habituelle = serializers.SlugRelatedField(
        slug_field="plaque", queryset=Vehicule.objects.all(), required=False, allow_null=True
    )
    trajets_count = serializers.IntegerField(source="trajets.count", read_only=True)
    incidents_count = serializers.IntegerField(source="incidents.count", read_only=True)
    courriel_compte = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Chauffeur
        fields = [
            "id", "prenom", "nom", "nom_complet", "age", "telephone", "courriel",
            "adresse", "permis_numero", "permis_expiration", "statut",
            "plaque_habituelle", "cree_le", "trajets_count", "incidents_count",
            "courriel_compte",
        ]
        read_only_fields = ["cree_le"]


class ChauffeurCreationSerializer(serializers.ModelSerializer):
    """
    Création d'un chauffeur = création du compte Django (User + Profil) associé,
    comme le fait la page admin/chauffeur-nouveau.html. Le mot de passe initial
    est renvoyé une seule fois dans la réponse pour être communiqué au chauffeur.
    """

    plaque_habituelle = serializers.SlugRelatedField(
        slug_field="plaque", queryset=Vehicule.objects.all(), required=False, allow_null=True
    )
    mot_de_passe = serializers.CharField(write_only=True, required=False, validators=[validate_password])

    class Meta:
        model = Chauffeur
        fields = [
            "id", "prenom", "nom", "age", "telephone", "courriel", "adresse",
            "permis_numero", "permis_expiration", "statut", "plaque_habituelle",
            "mot_de_passe",
        ]

    def validate_courriel(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Un compte existe déjà avec ce courriel.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        mot_de_passe = validated_data.pop("mot_de_passe", None) or get_random_string(12)
        courriel = validated_data["courriel"]
        user = User.objects.create_user(
            username=courriel, email=courriel,
            first_name=validated_data["prenom"], last_name=validated_data["nom"],
            password=mot_de_passe,
        )
        Profil.objects.create(user=user, role=Profil.Role.CHAUFFEUR)
        chauffeur = Chauffeur.objects.create(user=user, **validated_data)
        chauffeur.mot_de_passe_genere = mot_de_passe
        return chauffeur

    def to_representation(self, instance):
        data = ChauffeurSerializer(instance, context=self.context).data
        genere = getattr(instance, "mot_de_passe_genere", None)
        if genere:
            data["mot_de_passe_initial"] = genere
        return data


class ArretSerializer(serializers.ModelSerializer):
    class Meta:
        model = Arret
        fields = ["id", "trajet", "lieu", "heure", "note"]
        read_only_fields = ["trajet"]


class IncidentSerializer(serializers.ModelSerializer):
    chauffeur_nom = serializers.CharField(source="chauffeur.nom_complet", read_only=True)
    # Le trajet associé est référencé par son code affiché (ex. "T-2093"),
    # comme le fait le front-end (i.trajetId == t.id), plutôt que par la clé
    # primaire interne — cohérent avec TrajetViewSet.lookup_field = "code".
    trajet = serializers.SlugRelatedField(
        slug_field="code", queryset=Trajet.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Incident
        fields = [
            "id", "code", "trajet", "chauffeur", "chauffeur_nom", "type", "titre",
            "description", "lieu", "date", "heure", "statut",
        ]
        read_only_fields = ["code", "chauffeur", "statut"]


class TrajetSerializer(serializers.ModelSerializer):
    arrets = ArretSerializer(many=True, read_only=True)
    chauffeur_nom = serializers.CharField(source="chauffeur.nom_complet", read_only=True)
    incidents_count = serializers.IntegerField(source="incidents.count", read_only=True)
    progression = serializers.SerializerMethodField()

    class Meta:
        model = Trajet
        fields = [
            "id", "code", "chauffeur", "chauffeur_nom", "vehicule", "plaque",
            "depart", "depart_adresse", "arrivee", "debut", "fin_prevue", "fin",
            "statut", "arrets", "incidents_count", "progression",
        ]
        read_only_fields = ["code", "statut", "fin"]

    def get_progression(self, trajet):
        from django.utils import timezone

        if trajet.statut == Trajet.Statut.TERMINE:
            return 100
        if trajet.statut == Trajet.Statut.PLANIFIE:
            return 0
        t0, t1, tn = trajet.debut.timestamp(), trajet.fin_prevue.timestamp(), timezone.now().timestamp()
        if t1 <= t0:
            return 0
        return max(0, min(100, round((tn - t0) / (t1 - t0) * 100)))


class TrajetCreationSerializer(serializers.ModelSerializer):
    """Un chauffeur démarre son propre trajet (chauffeur déduit de la requête)."""

    class Meta:
        model = Trajet
        fields = ["id", "code", "vehicule", "plaque", "depart", "depart_adresse", "arrivee", "debut", "fin_prevue"]
        read_only_fields = ["code"]


class IndicateursSerializer(serializers.Serializer):
    chauffeurs_actifs = serializers.IntegerField()
    trajets_en_cours = serializers.IntegerField()
    trajets_du_jour = serializers.IntegerField()
    incidents_ouverts = serializers.IntegerField()
    incidents_du_jour = serializers.IntegerField()
    permis_a_expirer = serializers.IntegerField()
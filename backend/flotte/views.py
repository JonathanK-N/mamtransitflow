from django.shortcuts import render

# Create your views here.
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import Arret, Chauffeur, Incident, Trajet, Vehicule
from .permissions import EstAdmin, EstAdminOuLectureSeule, EstProprietaireOuAdmin, est_admin
from .serializers import (
    ArretSerializer, ChauffeurCreationSerializer, ChauffeurSerializer,
    IncidentSerializer, IndicateursSerializer, MoiSerializer, TrajetCreationSerializer,
    TrajetSerializer, VehiculeSerializer,
)

User = get_user_model()


# --- Authentification -----------------------------------------------------

class ConnexionSerializer(TokenObtainPairSerializer):
    """Login par courriel (comme le prototype) plutôt que par username."""

    username_field = User.USERNAME_FIELD

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields[self.username_field].required = False

    def validate(self, attrs):
        courriel = self.initial_data.get("courriel") or attrs.get(self.username_field)
        try:
            utilisateur = User.objects.get(email__iexact=courriel)
        except User.DoesNotExist:
            raise ValidationError("Aucun compte ne correspond à ce courriel.")
        attrs[self.username_field] = utilisateur.get_username()
        data = super().validate(attrs)
        data["moi"] = MoiSerializer(self.user).data
        return data


class ConnexionView(TokenObtainPairView):
    serializer_class = ConnexionSerializer


class MoiView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(MoiSerializer(request.user).data)


# --- Chauffeurs -------------------------------------------------------------

class ChauffeurViewSet(viewsets.ModelViewSet):
    queryset = Chauffeur.objects.select_related("user", "plaque_habituelle").all()
    permission_classes = [IsAuthenticated, EstProprietaireOuAdmin]

    def get_serializer_class(self):
        if self.action == "create":
            return ChauffeurCreationSerializer
        return ChauffeurSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if est_admin(self.request.user):
            recherche = self.request.query_params.get("recherche")
            statut = self.request.query_params.get("statut")
            if recherche:
                qs = qs.filter(
                    prenom__icontains=recherche
                ) | qs.filter(nom__icontains=recherche) | qs.filter(courriel__icontains=recherche)
            if statut and statut != "tous":
                qs = qs.filter(statut=statut)
            return qs
        # Un chauffeur ne voit que sa propre fiche.
        return qs.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        if not est_admin(request.user):
            raise PermissionDenied("Seul un administrateur peut créer un compte chauffeur.")
        return super().create(request, *args, **kwargs)


# --- Véhicules ---------------------------------------------------------------

class VehiculeViewSet(viewsets.ModelViewSet):
    queryset = Vehicule.objects.all()
    serializer_class = VehiculeSerializer
    permission_classes = [IsAuthenticated, EstAdminOuLectureSeule]


# --- Trajets ------------------------------------------------------------------

class TrajetViewSet(viewsets.ModelViewSet):
    queryset = Trajet.objects.select_related("chauffeur", "vehicule").prefetch_related("arrets")
    permission_classes = [IsAuthenticated, EstProprietaireOuAdmin]
    # Les trajets sont adressés par leur code affiché (ex. "T-2093"), comme
    # le front-end (t.id), plutôt que par la clé primaire interne.
    lookup_field = "code"
    lookup_value_regex = "[^/]+"

    def get_serializer_class(self):
        if self.action == "create":
            return TrajetCreationSerializer
        return TrajetSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if not est_admin(self.request.user):
            chauffeur = getattr(self.request.user, "chauffeur", None)
            qs = qs.filter(chauffeur=chauffeur) if chauffeur else qs.none()
        statut = self.request.query_params.get("statut")
        if statut and statut != "tous":
            qs = qs.filter(statut=statut)
        chauffeur_id = self.request.query_params.get("chauffeur")
        if chauffeur_id:
            qs = qs.filter(chauffeur_id=chauffeur_id)
        return qs

    def perform_create(self, serializer):
        chauffeur = getattr(self.request.user, "chauffeur", None)
        if chauffeur is None:
            raise PermissionDenied("Seul un compte chauffeur peut démarrer un trajet.")
        if Trajet.objects.filter(chauffeur=chauffeur, statut=Trajet.Statut.EN_COURS).exists():
            raise ValidationError("Un trajet est déjà en cours pour ce chauffeur.")
        trajet = serializer.save(chauffeur=chauffeur, statut=Trajet.Statut.EN_COURS)
        chauffeur.statut = Chauffeur.Statut.EN_TRAJET
        chauffeur.save(update_fields=["statut"])
        return trajet

    @action(detail=False, methods=["get"], url_path="en-cours")
    def en_cours_pour_chauffeur(self, request):
        """GET /api/trajets/en-cours/ — trajet en cours du chauffeur connecté (ou filtré par ?chauffeur=)."""
        return self.list(request)

    @action(detail=True, methods=["post"], url_path="ajouter-arret")
    def ajouter_arret(self, request, code=None):
        trajet = self.get_object()
        serializer = ArretSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(trajet=trajet)
        trajet.refresh_from_db()  # vide le cache prefetch_related("arrets") du get_object()
        return Response(TrajetSerializer(trajet).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def terminer(self, request, code=None):
        trajet = self.get_object()
        if trajet.statut == Trajet.Statut.TERMINE:
            raise ValidationError("Ce trajet est déjà terminé.")
        trajet.terminer()
        return Response(TrajetSerializer(trajet).data)


# --- Incidents ------------------------------------------------------------------

class IncidentViewSet(viewsets.ModelViewSet):
    queryset = Incident.objects.select_related("chauffeur", "trajet")
    serializer_class = IncidentSerializer
    permission_classes = [IsAuthenticated, EstProprietaireOuAdmin]
    # Même logique que TrajetViewSet : adressé par le code affiché (ex. "I-1001").
    lookup_field = "code"
    lookup_value_regex = "[^/]+"

    def get_queryset(self):
        qs = super().get_queryset()
        if not est_admin(self.request.user):
            chauffeur = getattr(self.request.user, "chauffeur", None)
            qs = qs.filter(chauffeur=chauffeur) if chauffeur else qs.none()
        type_ = self.request.query_params.get("type")
        if type_ and type_ != "tous":
            qs = qs.filter(type=type_)
        statut = self.request.query_params.get("statut")
        if statut and statut != "tous":
            qs = qs.filter(statut=statut)
        chauffeur_id = self.request.query_params.get("chauffeur")
        if chauffeur_id:
            qs = qs.filter(chauffeur_id=chauffeur_id)
        return qs

    def perform_create(self, serializer):
        chauffeur = getattr(self.request.user, "chauffeur", None)
        if chauffeur is None:
            raise PermissionDenied("Seul un compte chauffeur peut signaler un incident.")
        serializer.save(chauffeur=chauffeur, statut=Incident.Statut.OUVERT)

    @action(detail=True, methods=["post"])
    def traiter(self, request, code=None):
        if not est_admin(request.user):
            raise PermissionDenied("Seul un administrateur peut marquer un incident comme traité.")
        incident = self.get_object()
        incident.traiter()
        return Response(IncidentSerializer(incident).data)


# --- Tableau de bord ---------------------------------------------------------

class IndicateursView(APIView):
    permission_classes = [IsAuthenticated, EstAdmin]

    def get(self, request):
        aujourdhui = timezone.localdate()
        limite = aujourdhui + timedelta(days=60)
        donnees = {
            "chauffeurs_actifs": Chauffeur.objects.exclude(statut=Chauffeur.Statut.HORS_SERVICE).count(),
            "trajets_en_cours": Trajet.objects.filter(statut=Trajet.Statut.EN_COURS).count(),
            "trajets_du_jour": Trajet.objects.filter(debut__date=aujourdhui).count(),
            "incidents_ouverts": Incident.objects.filter(statut=Incident.Statut.OUVERT).count(),
            "incidents_du_jour": Incident.objects.filter(date=aujourdhui).count(),
            "permis_a_expirer": Chauffeur.objects.filter(permis_expiration__lt=limite).count(),
        }
        return Response(IndicateursSerializer(donnees).data)
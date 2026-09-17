"""
Modèles TransitFlow.

Chauffeur, Vehicule, Trajet, Arret, Incident. Chaque chauffeur possède un
compte Django (User) ; le rôle (admin/chauffeur) est porté par `Profil`.
"""
from django.conf import settings
from django.db import models


def _prochain_numero(modele, base):
    """Numérote T-xxxx / I-xxxx en reprenant le plus grand suffixe existant (comme
    le faisait Store.ajouterTrajet/ajouterIncident côté JS), plutôt que le pk."""
    plus_grand = base
    for (code,) in modele.objects.values_list("code"):
        try:
            plus_grand = max(plus_grand, int(code.split("-")[1]))
        except (IndexError, ValueError):
            continue
    return plus_grand + 1


class Profil(models.Model):
    """Étend le User Django avec un rôle métier (admin ou chauffeur)."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Administrateur"
        CHAUFFEUR = "chauffeur", "Chauffeur"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profil"
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CHAUFFEUR)

    def __str__(self):
        return f"{self.user.get_username()} ({self.role})"


class Vehicule(models.Model):
    plaque = models.CharField(max_length=20, unique=True)
    modele = models.CharField(max_length=100)

    class Meta:
        ordering = ["plaque"]

    def __str__(self):
        return f"{self.plaque} — {self.modele}"


class Chauffeur(models.Model):
    class Statut(models.TextChoices):
        DISPONIBLE = "disponible", "Disponible"
        EN_TRAJET = "en-trajet", "En trajet"
        HORS_SERVICE = "hors-service", "Hors service"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chauffeur"
    )
    prenom = models.CharField(max_length=100)
    nom = models.CharField(max_length=100)
    age = models.PositiveSmallIntegerField()
    telephone = models.CharField(max_length=30)
    courriel = models.EmailField(unique=True)
    adresse = models.CharField(max_length=255)
    permis_numero = models.CharField(max_length=50)
    permis_expiration = models.DateField()
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.DISPONIBLE)
    plaque_habituelle = models.ForeignKey(
        Vehicule, on_delete=models.SET_NULL, null=True, blank=True, related_name="chauffeurs_habituels"
    )
    cree_le = models.DateField(auto_now_add=True)

    class Meta:
        ordering = ["nom", "prenom"]

    def __str__(self):
        return f"{self.prenom} {self.nom}"

    @property
    def nom_complet(self):
        return f"{self.prenom} {self.nom}"


class Trajet(models.Model):
    class Statut(models.TextChoices):
        PLANIFIE = "planifie", "Planifié"
        EN_COURS = "en-cours", "En cours"
        TERMINE = "termine", "Terminé"

    code = models.CharField(max_length=20, unique=True, editable=False, blank=True)
    chauffeur = models.ForeignKey(Chauffeur, on_delete=models.CASCADE, related_name="trajets")
    vehicule = models.ForeignKey(
        Vehicule, on_delete=models.SET_NULL, null=True, related_name="trajets"
    )
    plaque = models.CharField(max_length=20)
    depart = models.CharField(max_length=150)
    depart_adresse = models.CharField(max_length=255)
    arrivee = models.CharField(max_length=150)
    debut = models.DateTimeField()
    fin_prevue = models.DateTimeField()
    fin = models.DateTimeField(null=True)
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.EN_COURS)

    class Meta:
        ordering = ["-debut"]

    def __str__(self):
        return f"{self.code} — {self.depart} → {self.arrivee}"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = f"T-{_prochain_numero(Trajet, 2092)}"
        super().save(*args, **kwargs)

    def terminer(self):
        from django.utils import timezone

        self.statut = self.Statut.TERMINE
        self.fin = timezone.now()
        self.save(update_fields=["statut", "fin"])
        self.chauffeur.statut = Chauffeur.Statut.DISPONIBLE
        self.chauffeur.save(update_fields=["statut"])


class Arret(models.Model):
    trajet = models.ForeignKey(Trajet, on_delete=models.CASCADE, related_name="arrets")
    lieu = models.CharField(max_length=150)
    heure = models.CharField(max_length=5, help_text="Format HH:MM")
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["heure"]

    def __str__(self):
        return f"{self.lieu} ({self.heure})"


class Incident(models.Model):
    class Type(models.TextChoices):
        TECHNIQUE = "technique", "Technique"
        ROUTE = "route", "Route"

    class Statut(models.TextChoices):
        OUVERT = "ouvert", "Ouvert"
        TRAITE = "traite", "Traité"

    code = models.CharField(max_length=20, unique=True, editable=False, blank=True)
    trajet = models.ForeignKey(
        Trajet, on_delete=models.SET_NULL, null=True, blank=True, related_name="incidents"
    )
    chauffeur = models.ForeignKey(Chauffeur, on_delete=models.CASCADE, related_name="incidents")
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.ROUTE)
    titre = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    lieu = models.CharField(max_length=150)
    date = models.DateField()
    heure = models.CharField(max_length=5, help_text="Format HH:MM")
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.OUVERT)

    class Meta:
        ordering = ["-date", "-heure"]

    def __str__(self):
        return f"{self.code} — {self.titre}"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = f"I-{_prochain_numero(Incident, 1000)}"
        super().save(*args, **kwargs)

    def traiter(self):
        self.statut = self.Statut.TRAITE
        self.save(update_fields=["statut"])
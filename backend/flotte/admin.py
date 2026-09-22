from django.contrib import admin

from .models import Arret, Chauffeur, Incident, Profil, Trajet, Vehicule


@admin.register(Profil)
class ProfilAdmin(admin.ModelAdmin):
    list_display = ["user", "role"]
    list_filter = ["role"]


@admin.register(Vehicule)
class VehiculeAdmin(admin.ModelAdmin):
    list_display = ["plaque", "modele"]
    search_fields = ["plaque", "modele"]


@admin.register(Chauffeur)
class ChauffeurAdmin(admin.ModelAdmin):
    list_display = ["nom_complet", "courriel", "statut", "permis_expiration"]
    list_filter = ["statut"]
    search_fields = ["prenom", "nom", "courriel", "telephone"]


class ArretInline(admin.TabularInline):
    model = Arret
    extra = 0


@admin.register(Trajet)
class TrajetAdmin(admin.ModelAdmin):
    list_display = ["code", "chauffeur", "depart", "arrivee", "statut", "debut"]
    list_filter = ["statut"]
    inlines = [ArretInline]


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ["code", "chauffeur", "type", "titre", "statut", "date"]
    list_filter = ["type", "statut"]
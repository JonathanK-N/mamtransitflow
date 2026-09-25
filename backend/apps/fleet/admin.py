from django.contrib import admin

from .models import ReleveKilometrage, Vehicule


class ReleveEnLigne(admin.TabularInline):
    model = ReleveKilometrage
    extra = 0
    readonly_fields = ['kilometrage', 'source', 'note', 'auteur', 'releve_le']
    can_delete = False


@admin.register(Vehicule)
class VehiculeAdmin(admin.ModelAdmin):
    list_display = ['plaque', 'modele', 'annee', 'kilometrage', 'statut']
    list_filter = ['statut']
    search_fields = ['plaque', 'modele', 'numero_serie']
    inlines = [ReleveEnLigne]


@admin.register(ReleveKilometrage)
class ReleveKilometrageAdmin(admin.ModelAdmin):
    list_display = ['vehicule', 'kilometrage', 'source', 'auteur', 'releve_le']
    list_filter = ['source']
    search_fields = ['vehicule__plaque']

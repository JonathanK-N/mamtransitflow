from django.contrib import admin

from .models import BonTravail, PlanEntretien


@admin.register(PlanEntretien)
class PlanEntretienAdmin(admin.ModelAdmin):
    list_display = ['code', 'vehicule', 'type', 'libelle', 'intervalle_km', 'intervalle_jours', 'dernier_km',
                    'derniere_date', 'actif']
    list_filter = ['type', 'actif']
    search_fields = ['libelle', 'vehicule__plaque']


@admin.register(BonTravail)
class BonTravailAdmin(admin.ModelAdmin):
    list_display = ['code', 'vehicule', 'titre', 'categorie', 'type', 'priorite', 'statut', 'date_prevue',
                    'cout_pieces', 'cout_main_oeuvre']
    list_filter = ['statut', 'categorie', 'type', 'priorite']
    search_fields = ['titre', 'description', 'fournisseur', 'vehicule__plaque']
    date_hierarchy = 'date_prevue'
    raw_id_fields = ['plan', 'incident']

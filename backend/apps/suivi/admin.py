from django.contrib import admin

from .models import PositionGPS


@admin.register(PositionGPS)
class PositionGPSAdmin(admin.ModelAdmin):
    list_display = ['trajet', 'plaque', 'latitude', 'longitude', 'precision_m', 'vitesse_kmh', 'horodatage']
    list_filter = ['plaque']
    date_hierarchy = 'horodatage'
    raw_id_fields = ['trajet', 'chauffeur']

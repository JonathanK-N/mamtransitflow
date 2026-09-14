from django.contrib import admin

from .models import Arret, Trajet

admin.site.register(Trajet)
admin.site.register(Arret)

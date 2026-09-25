from django.contrib import admin

from .models import BulletinPaie, ParametresPaie, PeriodePaie, ProfilPaie, Retenue

for modele in (ParametresPaie, Retenue, ProfilPaie, PeriodePaie, BulletinPaie):
    admin.site.register(modele)

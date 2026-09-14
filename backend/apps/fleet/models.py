"""TransitFlow — Modele : vehicules de la flotte
   Auteur : Jonathan K-N"""

from django.db import models


class Vehicule(models.Model):
    plaque = models.CharField(max_length=20, unique=True)
    modele = models.CharField(max_length=100)

    class Meta:
        ordering = ['plaque']

    def __str__(self):
        return f'{self.plaque} ({self.modele})'

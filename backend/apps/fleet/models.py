"""
TransitFlow — Modeles : vehicules de la flotte et releves kilometriques
Auteur : Jonathan K-N

Le compteur kilometrique courant (Vehicule.kilometrage) est la base du
module d entretien (apps/entretien) : les echeances preventives se
calculent a partir de lui. Chaque changement passe par un
ReleveKilometrage (voir apps/fleet/services.py) pour garder l historique
et savoir d ou vient la valeur (saisie manuelle, fin de trajet, garage).

Statut du vehicule :
  - 'actif'        : disponible pour un trajet ;
  - 'maintenance'  : immobilise par un bon de travail en cours (gere
                     automatiquement par apps/entretien) ;
  - 'hors-service' : retire de la circulation par l administrateur.
Un trajet ne peut demarrer qu avec un vehicule 'actif'.
"""

from django.conf import settings
from django.db import models


class Vehicule(models.Model):
    STATUTS = [('actif', 'Actif'), ('maintenance', 'En maintenance'), ('hors-service', 'Hors service')]

    plaque = models.CharField(max_length=20, unique=True)
    modele = models.CharField(max_length=100)
    annee = models.PositiveSmallIntegerField(null=True, blank=True)
    numero_serie = models.CharField(max_length=17, blank=True, default='')  # NIV / VIN
    kilometrage = models.PositiveIntegerField(default=0)
    statut = models.CharField(max_length=20, choices=STATUTS, default='actif')
    mise_en_service = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['plaque']

    def __str__(self):
        return f'{self.plaque} ({self.modele})'

    @property
    def disponible(self) -> bool:
        return self.statut == 'actif'


class ReleveKilometrage(models.Model):
    SOURCES = [
        ('initial', 'Valeur initiale'),
        ('manuel', 'Saisie manuelle'),
        ('trajet', 'Fin de trajet'),
        ('entretien', 'Bon de travail'),
    ]

    vehicule = models.ForeignKey(Vehicule, on_delete=models.CASCADE, related_name='releves')
    kilometrage = models.PositiveIntegerField()
    source = models.CharField(max_length=20, choices=SOURCES, default='manuel')
    note = models.CharField(max_length=255, blank=True, default='')
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name='releves_kilometrage')
    releve_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-releve_le', '-id']
        indexes = [models.Index(fields=['vehicule', '-releve_le'])]

    def __str__(self):
        return f'{self.vehicule.plaque} : {self.kilometrage} km ({self.source})'

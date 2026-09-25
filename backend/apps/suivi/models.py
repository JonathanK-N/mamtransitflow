"""
TransitFlow — Modele : positions GPS des trajets
Auteur : Jonathan K-N

Pendant un trajet en cours, la page du chauffeur (chauffeur/trajet-en-cours.html)
lit la position du telephone (API de geolocalisation du navigateur) et
l envoie par petits lots. Chaque point est rattache au trajet : la carte
en direct de l administrateur affiche le dernier point de chaque trajet
en cours, et la fiche d un trajet redessine tout son parcours.

`horodatage` est l instant de la mesure donne par le telephone (et non
l instant de reception) : un lot envoye en retard, apres une coupure de
reseau, se replace donc au bon endroit du parcours. Un meme point envoye
deux fois (nouvel essai apres une erreur reseau) est ignore grace a la
contrainte d unicite (trajet, horodatage).
"""

import math

from django.db import models


class PositionGPS(models.Model):
    trajet = models.ForeignKey('dispatch.Trajet', on_delete=models.CASCADE, related_name='positions')
    chauffeur = models.ForeignKey('drivers.Chauffeur', on_delete=models.CASCADE, related_name='positions')
    plaque = models.CharField(max_length=20)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    precision_m = models.FloatField(null=True, blank=True)   # rayon d incertitude, en metres
    vitesse_kmh = models.FloatField(null=True, blank=True)
    cap = models.FloatField(null=True, blank=True)           # direction, en degres (0 = nord)
    horodatage = models.DateTimeField()
    recu_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['horodatage']
        constraints = [
            models.UniqueConstraint(fields=['trajet', 'horodatage'], name='position_unique_par_instant'),
        ]
        indexes = [
            models.Index(fields=['trajet', '-horodatage']),
            models.Index(fields=['horodatage']),
        ]

    def __str__(self):
        return f'{self.plaque} {self.latitude},{self.longitude} @ {self.horodatage:%Y-%m-%d %H:%M:%S}'


RAYON_TERRE_M = 6_371_000


def distance_m(lat1, lon1, lat2, lon2) -> float:
    """Distance a vol d oiseau entre deux points (formule de haversine), en metres."""
    p1, p2 = math.radians(float(lat1)), math.radians(float(lat2))
    dp = p2 - p1
    dl = math.radians(float(lon2) - float(lon1))
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * RAYON_TERRE_M * math.asin(min(1.0, math.sqrt(a)))

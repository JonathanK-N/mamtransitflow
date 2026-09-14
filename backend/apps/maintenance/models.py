"""
TransitFlow — Modele : incidents
Auteur : Jonathan K-N

Comme pour Arret.heure (voir apps/dispatch/models.py), `date` et `heure`
restent deux champs simples plutot qu un DateTimeField combine : c est le
format que le front-end existant envoie et affiche directement
(Format.jourHeure(i.date + 'T' + i.heure) dans assets/js/format.js).
"""

import re

from django.db import models


class Incident(models.Model):
    TYPES = [('technique', 'Technique'), ('route', 'Route')]
    STATUTS = [('ouvert', 'Ouvert'), ('traite', 'Traite')]

    trajet = models.ForeignKey('dispatch.Trajet', null=True, blank=True,
                                on_delete=models.SET_NULL, related_name='incidents')
    chauffeur = models.ForeignKey('drivers.Chauffeur', on_delete=models.CASCADE, related_name='incidents')
    type = models.CharField(max_length=20, choices=TYPES)
    titre = models.CharField(max_length=150)
    description = models.TextField()
    lieu = models.CharField(max_length=150)
    date = models.DateField()
    heure = models.CharField(max_length=5)  # format "HH:MM"
    statut = models.CharField(max_length=20, choices=STATUTS, default='ouvert')

    class Meta:
        ordering = ['-date', '-heure']

    def __str__(self):
        return f'{self.code} : {self.titre}'

    @property
    def code(self) -> str:
        return f'I-{self.id}'

    @classmethod
    def depuis_code(cls, code: str):
        correspondance = re.fullmatch(r'I-(\d+)', str(code or ''))
        if not correspondance:
            return None
        return cls.objects.filter(pk=int(correspondance.group(1))).first()

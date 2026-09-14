"""
TransitFlow — Modeles : trajets et arrets
Auteur : Jonathan K-N

Le champ Arret.heure est une simple chaine "HH:MM" (pas un DateTimeField) :
c est deliberement ce que fait le front-end existant (assets/js/chauffeur.js,
formulaire avec <input type="time">) et Format.js s attend a pouvoir trier
et comparer ces heures comme du texte simple (localeCompare) sur toute la
frise d un trajet (arrets + incidents melanges). Introduire un vrai type
"heure" ici casserait ce tri sans rien apporter.
"""

import re

from django.db import models


class Trajet(models.Model):
    STATUTS = [('en-cours', 'En cours'), ('termine', 'Termine')]

    chauffeur = models.ForeignKey('drivers.Chauffeur', on_delete=models.CASCADE, related_name='trajets')
    plaque = models.CharField(max_length=20)
    depart = models.CharField(max_length=150)
    depart_adresse = models.CharField(max_length=255, blank=True, null=True)
    arrivee = models.CharField(max_length=150)
    debut = models.DateTimeField()
    fin_prevue = models.DateTimeField()
    fin = models.DateTimeField(null=True, blank=True)
    statut = models.CharField(max_length=20, choices=STATUTS, default='en-cours')

    class Meta:
        ordering = ['-debut']

    def __str__(self):
        return f'{self.code} : {self.depart} -> {self.arrivee}'

    @property
    def code(self) -> str:
        return f'T-{self.id}'

    @classmethod
    def depuis_code(cls, code: str):
        correspondance = re.fullmatch(r'T-(\d+)', str(code or ''))
        if not correspondance:
            return None
        return cls.objects.filter(pk=int(correspondance.group(1))).first()


class Arret(models.Model):
    trajet = models.ForeignKey(Trajet, on_delete=models.CASCADE, related_name='arrets')
    lieu = models.CharField(max_length=150)
    heure = models.CharField(max_length=5)  # format "HH:MM", voir la note en tete de fichier
    note = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        ordering = ['heure']

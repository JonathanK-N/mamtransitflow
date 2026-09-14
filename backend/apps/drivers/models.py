"""
TransitFlow — Modele : chauffeurs
Auteur : Jonathan K-N

Django utilise un entier auto-incremente comme cle primaire (`id`), mais
le front-end existant affiche et manipule des identifiants du style 'c1'
(voir assets/js/*.js). La propriete `code` et la methode `depuis_code`
font le pont entre les deux, pour que l API renvoie et accepte ce meme
format sans que le front-end ait besoin de changer.
"""

import re

from django.db import models


class Chauffeur(models.Model):
    STATUTS = [
        ('disponible', 'Disponible'),
        ('en-trajet', 'En trajet'),
        ('hors-service', 'Hors service')
    ]

    prenom = models.CharField(max_length=100)
    nom = models.CharField(max_length=100)
    age = models.PositiveSmallIntegerField()
    telephone = models.CharField(max_length=30)
    courriel = models.EmailField()
    adresse = models.CharField(max_length=255)
    permis_numero = models.CharField(max_length=50)
    permis_expiration = models.DateField()
    statut = models.CharField(max_length=20, choices=STATUTS, default='disponible')
    plaque_habituelle = models.ForeignKey('fleet.Vehicule', to_field='plaque', db_column='plaque_habituelle',
                                           null=True, blank=True, on_delete=models.SET_NULL,
                                           related_name='chauffeurs')
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.nom_complet

    @property
    def code(self) -> str:
        """Identifiant lisible style ancien front-end (ex. 'c1'), pour l affichage et les URLs."""
        return f'c{self.id}'

    @property
    def nom_complet(self) -> str:
        return f'{self.prenom} {self.nom}'

    @classmethod
    def depuis_code(cls, code: str):
        """Retrouve un chauffeur a partir de son code affiche ('c1' -> pk=1). None si invalide/introuvable."""
        correspondance = re.fullmatch(r'c(\d+)', str(code or ''))
        if not correspondance:
            return None
        return cls.objects.filter(pk=int(correspondance.group(1))).first()

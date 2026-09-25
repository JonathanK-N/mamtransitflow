"""
TransitFlow — Modeles : entretien de la flotte
Auteur : Jonathan K-N

Deux notions, comme dans un module de maintenance d ERP :

- PlanEntretien (programme preventif) : "vidange tous les 8 000 km ou
  6 mois" pour un vehicule donne. L echeance suivante se calcule a partir
  du dernier entretien realise (dernier_km / derniere_date) ; la premiere
  limite atteinte (kilometres OU jours) declenche l echeance.

- BonTravail (ordre de travail) : une intervention concrete sur un
  vehicule, preventive (issue d un plan) ou corrective (panne, incident
  technique signale par un chauffeur). Cycle de vie :
      planifie -> en-cours -> termine
          \\-----------\\-----> annule
  Les transitions et leurs effets (statut du vehicule, compteur, plan,
  incident) sont centralises dans apps/entretien/services.py.

Identifiants affiches : 'P-12' pour un plan, 'BT-34' pour un bon de
travail (meme principe que 'c1', 'T-1', 'I-1' ailleurs dans l API).
"""

import re
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

TYPES_ENTRETIEN = [
    ('vidange', 'Vidange et filtres'),
    ('pneus', 'Pneus'),
    ('freins', 'Freins'),
    ('inspection', 'Inspection mecanique'),
    ('courroie', 'Courroie de distribution'),
    ('climatisation', 'Climatisation'),
    ('carrosserie', 'Carrosserie'),
    ('electrique', 'Systeme electrique'),
    ('reparation', 'Reparation mecanique'),
    ('autre', 'Autre'),
]

# Une echeance passe a "bientot" quand il reste moins de 20 % de
# l intervalle, plafonne a 1 000 km et 30 jours (une vidange tous les
# 8 000 km s annonce a 1 000 km, un controle tous les 90 jours a 18 jours).
PART_ALERTE = 5            # 1/5 = 20 %
SEUIL_KM_MAXIMAL = 1000
SEUIL_JOURS_MAXIMAL = 30


def _depuis_code(modele, prefixe: str, code: str):
    correspondance = re.fullmatch(prefixe + r'-(\d+)', str(code or '').strip(), flags=re.IGNORECASE)
    if not correspondance:
        return None
    return modele.objects.filter(pk=int(correspondance.group(1))).first()


class PlanEntretien(models.Model):
    vehicule = models.ForeignKey('fleet.Vehicule', on_delete=models.CASCADE, related_name='plans_entretien')
    type = models.CharField(max_length=20, choices=TYPES_ENTRETIEN)
    libelle = models.CharField(max_length=150)
    intervalle_km = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    intervalle_jours = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    dernier_km = models.PositiveIntegerField(default=0)
    derniere_date = models.DateField()
    actif = models.BooleanField(default=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['vehicule__plaque', 'type', 'id']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(intervalle_km__isnull=False) | models.Q(intervalle_jours__isnull=False),
                name='plan_entretien_intervalle_requis',
            ),
        ]

    def __str__(self):
        return f'{self.code} : {self.libelle} ({self.vehicule.plaque})'

    @property
    def code(self) -> str:
        return f'P-{self.id}'

    @classmethod
    def depuis_code(cls, code: str):
        return _depuis_code(cls, 'P', code)

    @property
    def prochain_km(self) -> int | None:
        return self.dernier_km + self.intervalle_km if self.intervalle_km else None

    @property
    def prochaine_date(self) -> date | None:
        return self.derniere_date + timedelta(days=self.intervalle_jours) if self.intervalle_jours else None

    def echeance(self, aujourdhui: date, kilometrage: int | None = None) -> dict:
        """
        Etat de l echeance a une date donnee : 'en-retard', 'bientot' ou
        'a-jour', avec les kilometres et jours restants (negatifs = depasses).
        `kilometrage` vaut par defaut le compteur actuel du vehicule.
        """
        if kilometrage is None:
            kilometrage = self.vehicule.kilometrage
        km_restants = self.prochain_km - kilometrage if self.intervalle_km else None
        jours_restants = (self.prochaine_date - aujourdhui).days if self.intervalle_jours else None

        en_retard = (km_restants is not None and km_restants <= 0) or \
                    (jours_restants is not None and jours_restants <= 0)
        bientot = (km_restants is not None and km_restants <= min(SEUIL_KM_MAXIMAL,
                                                                  self.intervalle_km // PART_ALERTE)) or \
                  (jours_restants is not None and jours_restants <= min(SEUIL_JOURS_MAXIMAL,
                                                                        self.intervalle_jours // PART_ALERTE))
        etat = 'en-retard' if en_retard else ('bientot' if bientot else 'a-jour')
        return {'etat': etat, 'kmRestants': km_restants, 'joursRestants': jours_restants}


class BonTravail(models.Model):
    CATEGORIES = [('preventif', 'Preventif'), ('correctif', 'Correctif')]
    STATUTS = [('planifie', 'Planifie'), ('en-cours', 'En cours'), ('termine', 'Termine'), ('annule', 'Annule')]
    PRIORITES = [('basse', 'Basse'), ('normale', 'Normale'), ('haute', 'Haute'), ('urgente', 'Urgente')]
    STATUTS_OUVERTS = ('planifie', 'en-cours')

    vehicule = models.ForeignKey('fleet.Vehicule', on_delete=models.PROTECT, related_name='bons_travail')
    plan = models.ForeignKey(PlanEntretien, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name='bons_travail')
    incident = models.OneToOneField('maintenance.Incident', null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='bon_travail')
    categorie = models.CharField(max_length=20, choices=CATEGORIES, default='correctif')
    type = models.CharField(max_length=20, choices=TYPES_ENTRETIEN)
    titre = models.CharField(max_length=150)
    description = models.TextField(blank=True, default='')
    priorite = models.CharField(max_length=20, choices=PRIORITES, default='normale')
    statut = models.CharField(max_length=20, choices=STATUTS, default='planifie')
    date_prevue = models.DateField()
    debut = models.DateTimeField(null=True, blank=True)
    fin = models.DateTimeField(null=True, blank=True)
    kilometrage = models.PositiveIntegerField(null=True, blank=True)
    fournisseur = models.CharField(max_length=150, blank=True, default='')
    cout_pieces = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'),
                                      validators=[MinValueValidator(Decimal('0'))])
    cout_main_oeuvre = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'),
                                           validators=[MinValueValidator(Decimal('0'))])
    notes_cloture = models.TextField(blank=True, default='')
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name='bons_travail_crees')
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_prevue', '-id']
        indexes = [
            models.Index(fields=['statut', 'date_prevue']),
            models.Index(fields=['vehicule', 'statut']),
        ]

    def __str__(self):
        return f'{self.code} : {self.titre} ({self.vehicule.plaque})'

    @property
    def code(self) -> str:
        return f'BT-{self.id}'

    @classmethod
    def depuis_code(cls, code: str):
        return _depuis_code(cls, 'BT', code)

    @property
    def cout_total(self) -> Decimal:
        return (self.cout_pieces or Decimal('0')) + (self.cout_main_oeuvre or Decimal('0'))

    @property
    def ouvert(self) -> bool:
        return self.statut in self.STATUTS_OUVERTS

    def en_retard(self, aujourdhui: date) -> bool:
        return self.statut == 'planifie' and self.date_prevue < aujourdhui

"""
TransitFlow — Modeles : paie des chauffeurs
Auteur : Jonathan K-N

  ParametresPaie  : frequence des paies, heures supplementaires, vacances (fiche unique)
  Retenue         : une cotisation ou retenue (RRQ, AE, RQAP, impot...) et sa part employeur
  ProfilPaie      : comment un chauffeur est paye (a l heure, au trajet, salaire fixe)
  PeriodePaie     : une paie (du ... au ..., versee le ...) : brouillon -> validee -> payee
  BulletinPaie    : le bulletin d un chauffeur pour une periode
  LigneBulletin   : une ligne du bulletin (gain, retenue salarie, cotisation employeur)

Les heures viennent des trajets termines (apps/dispatch) : pas de double saisie.
"""

import re
from decimal import Decimal

from django.db import models

ZERO = Decimal('0')


def _depuis_code(modele, prefixe, code):
    trouve = re.fullmatch(prefixe + r'-(\d+)', str(code or ''))
    return modele.objects.filter(pk=int(trouve.group(1))).first() if trouve else None


class ParametresPaie(models.Model):
    FREQUENCES = [('hebdomadaire', 'Chaque semaine'), ('deux-semaines', 'Aux deux semaines'),
                  ('bimensuelle', 'Deux fois par mois'), ('mensuelle', 'Chaque mois')]
    PERIODES_PAR_AN = {'hebdomadaire': 52, 'deux-semaines': 26, 'bimensuelle': 24, 'mensuelle': 12}

    frequence = models.CharField(max_length=20, choices=FREQUENCES, default='deux-semaines')
    seuil_heures_sup = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('40'))
    majoration_heures_sup = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal('1.50'))
    # Indemnite de vacances versee a chaque paie (%), 0 si elle est versee au moment des vacances.
    taux_vacances = models.DecimalField(max_digits=5, decimal_places=2, default=ZERO)

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def courants(cls) -> 'ParametresPaie':
        return cls.objects.get_or_create(pk=1)[0]

    @property
    def periodes_par_an(self) -> int:
        return self.PERIODES_PAR_AN[self.frequence]


class Retenue(models.Model):
    """
    Cotisation calculee sur les gains imposables. Sur l annee, seule la part
    des gains cumules comprise entre plancher_annuel et plafond_annuel est
    cotisable ; exemption_annuelle est repartie sur les paies de l annee.
    """
    code = models.CharField(max_length=20, unique=True)
    libelle = models.CharField(max_length=120)
    taux_salarie = models.DecimalField(max_digits=6, decimal_places=3, default=ZERO)
    taux_employeur = models.DecimalField(max_digits=6, decimal_places=3, default=ZERO)
    plancher_annuel = models.DecimalField(max_digits=10, decimal_places=2, default=ZERO)
    plafond_annuel = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    exemption_annuelle = models.DecimalField(max_digits=10, decimal_places=2, default=ZERO)
    note = models.CharField(max_length=255, blank=True, default='')
    actif = models.BooleanField(default=True)
    ordre = models.PositiveSmallIntegerField(default=10)

    class Meta:
        ordering = ['ordre', 'id']

    def __str__(self):
        return self.libelle


class ProfilPaie(models.Model):
    MODES = [('horaire', 'A l heure'), ('trajet', 'Au trajet'), ('fixe', 'Salaire fixe par paie')]

    chauffeur = models.OneToOneField('drivers.Chauffeur', on_delete=models.CASCADE, related_name='profil_paie')
    mode = models.CharField(max_length=10, choices=MODES, default='horaire')
    taux_horaire = models.DecimalField(max_digits=8, decimal_places=2, default=ZERO)
    taux_trajet = models.DecimalField(max_digits=8, decimal_places=2, default=ZERO)
    salaire_periode = models.DecimalField(max_digits=10, decimal_places=2, default=ZERO)
    actif = models.BooleanField(default=True)


class PeriodePaie(models.Model):
    STATUTS = [('brouillon', 'Brouillon'), ('validee', 'Validee'), ('payee', 'Payee')]

    debut = models.DateField()
    fin = models.DateField()
    date_paiement = models.DateField()
    statut = models.CharField(max_length=10, choices=STATUTS, default='brouillon')
    calculee_le = models.DateTimeField(null=True, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-debut', '-id']

    @property
    def code(self) -> str:
        return f'PP-{self.id}'

    @classmethod
    def depuis_code(cls, code):
        return _depuis_code(cls, 'PP', code)


class BulletinPaie(models.Model):
    periode = models.ForeignKey(PeriodePaie, on_delete=models.CASCADE, related_name='bulletins')
    chauffeur = models.ForeignKey('drivers.Chauffeur', on_delete=models.PROTECT, related_name='bulletins_paie')
    mode = models.CharField(max_length=10, default='horaire')
    nombre_trajets = models.PositiveIntegerField(default=0)
    heures_regulieres = models.DecimalField(max_digits=7, decimal_places=2, default=ZERO)
    heures_sup = models.DecimalField(max_digits=7, decimal_places=2, default=ZERO)
    brut = models.DecimalField(max_digits=10, decimal_places=2, default=ZERO)
    brut_imposable = models.DecimalField(max_digits=10, decimal_places=2, default=ZERO)
    retenues = models.DecimalField(max_digits=10, decimal_places=2, default=ZERO)
    net = models.DecimalField(max_digits=10, decimal_places=2, default=ZERO)
    cotisations_employeur = models.DecimalField(max_digits=10, decimal_places=2, default=ZERO)

    class Meta:
        ordering = ['chauffeur__nom', 'chauffeur__prenom']
        constraints = [models.UniqueConstraint(fields=['periode', 'chauffeur'], name='un_bulletin_par_periode')]

    @property
    def code(self) -> str:
        return f'BP-{self.id}'

    @classmethod
    def depuis_code(cls, code):
        return _depuis_code(cls, 'BP', code)

    @property
    def cout_employeur(self) -> Decimal:
        return self.brut + self.cotisations_employeur


class LigneBulletin(models.Model):
    GENRES = [('gain', 'Gain'), ('retenue', 'Retenue'), ('employeur', 'Cotisation employeur')]

    bulletin = models.ForeignKey(BulletinPaie, on_delete=models.CASCADE, related_name='lignes')
    genre = models.CharField(max_length=10, choices=GENRES)
    code = models.CharField(max_length=20)
    libelle = models.CharField(max_length=150)
    quantite = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    taux = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    # Un remboursement de depenses n est pas un revenu : il ne subit aucune retenue.
    imposable = models.BooleanField(default=True)
    manuelle = models.BooleanField(default=False)
    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['ordre', 'id']

"""
TransitFlow — Modele : l entreprise qui utilise TransitFlow
Auteur : Jonathan K-N

Une seule fiche (pk=1), comme la fiche Societe d un ERP : son nom apparait
dans l interface, dans les courriels d invitation ("Rejoignez <nom> sur
TransitFlow") et sur les bulletins de paie.

Elle porte aussi les deux reglages qui font de TransitFlow un ERP modulaire :
- modules_* : les applications activees (entretien, suivi GPS, paie). Un
  module desactive disparait des menus et son API refuse les requetes ;
- portail_* : ce que l administrateur autorise dans le portail chauffeur.
"""

from django.db import models


class Entreprise(models.Model):
    nom = models.CharField(max_length=150, default='Mon entreprise de transport')
    courriel = models.EmailField(blank=True, default='')
    telephone = models.CharField(max_length=30, blank=True, default='')
    adresse = models.CharField(max_length=255, blank=True, default='')
    ville = models.CharField(max_length=100, blank=True, default='')
    province = models.CharField(max_length=50, blank=True, default='QC')
    code_postal = models.CharField(max_length=10, blank=True, default='')
    neq = models.CharField('NEQ', max_length=20, blank=True, default='')

    # ---- Modules (applications) actives -------------------------------
    module_entretien = models.BooleanField(default=True)
    module_suivi = models.BooleanField(default=True)
    module_paie = models.BooleanField(default=True)

    # ---- Portail chauffeur : ce que l administrateur autorise ---------
    portail_trajets = models.BooleanField(default=True)       # demarrer / terminer ses trajets
    portail_incidents = models.BooleanField(default=True)     # signaler un incident
    portail_vehicule = models.BooleanField(default=True)      # fiche et entretiens de son vehicule
    portail_paie = models.BooleanField(default=False)         # consulter ses bulletins de paie
    portail_profil = models.BooleanField(default=True)        # modifier telephone / adresse

    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Entreprise'

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        self.pk = 1  # fiche unique
        super().save(*args, **kwargs)

    @classmethod
    def courante(cls) -> 'Entreprise':
        entreprise, _ = cls.objects.get_or_create(pk=1)
        return entreprise

    def portail_autorise(self, droit: str) -> bool:
        """droit : 'trajets', 'incidents', 'vehicule', 'paie' ou 'profil'. La paie exige aussi le module."""
        if droit == 'paie' and not self.module_paie:
            return False
        if droit == 'vehicule' and not self.module_entretien:
            return False
        return bool(getattr(self, 'portail_' + droit))

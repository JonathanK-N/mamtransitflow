"""
TransitFlow — Regles metier de l entretien
Auteur : Jonathan K-N

Toutes les transitions d un bon de travail passent par ces fonctions,
qui gardent la flotte coherente :

  demarrer  : le vehicule passe 'maintenance' (sauf s il est hors service)
              et ne peut plus partir en trajet ; refuse si un trajet est
              en cours avec ce vehicule.
  terminer  : enregistre le compteur (releve 'entretien'), les couts,
              recale le plan preventif (dernier_km / derniere_date),
              marque l incident d origine comme traite et remet le
              vehicule 'actif' s il n a plus d autre bon en cours.
  annuler   : libere le vehicule de la meme facon.

Chaque fonction verrouille le bon (select_for_update) : deux clics
simultanes sur "Terminer" ne peuvent pas appliquer deux fois les effets.
"""

from datetime import datetime, time

from django.db import transaction
from django.utils import timezone

from apps.fleet.models import Vehicule
from apps.fleet.services import enregistrer_kilometrage
from .models import BonTravail


class ConflitMetier(Exception):
    """Transition refusee par une regle metier (repondue en HTTP 409 par les vues)."""


def _verrouiller(bon: BonTravail) -> BonTravail:
    # of=('self',) : seul le bon est verrouille. PostgreSQL refuse FOR UPDATE
    # sur les jointures externes (plan et incident sont facultatifs).
    return BonTravail.objects.select_for_update(of=('self',)) \
        .select_related('vehicule', 'plan', 'incident').get(pk=bon.pk)


def _liberer_vehicule(vehicule_id: int, sauf_bon_id: int):
    """Remet le vehicule 'actif' s il etait en maintenance et qu aucun autre bon n est en cours."""
    vehicule = Vehicule.objects.select_for_update().get(pk=vehicule_id)
    if vehicule.statut != 'maintenance':
        return
    autres = BonTravail.objects.filter(vehicule_id=vehicule_id, statut='en-cours').exclude(pk=sauf_bon_id)
    if not autres.exists():
        vehicule.statut = 'actif'
        vehicule.save(update_fields=['statut'])


def demarrer(bon: BonTravail) -> BonTravail:
    from apps.dispatch.models import Trajet

    with transaction.atomic():
        bon = _verrouiller(bon)
        if bon.statut != 'planifie':
            raise ConflitMetier('Seul un bon de travail planifie peut etre demarre.')
        vehicule = Vehicule.objects.select_for_update().get(pk=bon.vehicule_id)
        if Trajet.objects.filter(plaque=vehicule.plaque, statut='en-cours').exists():
            raise ConflitMetier(f'Le vehicule {vehicule.plaque} est actuellement en trajet : '
                                'attendez son retour pour demarrer l intervention.')
        bon.statut = 'en-cours'
        bon.debut = timezone.now()
        bon.save(update_fields=['statut', 'debut', 'modifie_le'])
        if vehicule.statut == 'actif':
            vehicule.statut = 'maintenance'
            vehicule.save(update_fields=['statut'])
    return bon


def terminer(bon: BonTravail, *, auteur=None, kilometrage=None, date_fin=None, cout_pieces=None,
             cout_main_oeuvre=None, fournisseur=None, notes=None) -> BonTravail:
    """
    Cloture un bon planifie ou en cours. Un bon encore 'planifie' peut etre
    termine directement : c est le cas d une intervention deja realisee
    qu on saisit apres coup (facture du garage recue).
    """
    maintenant = timezone.now()
    with transaction.atomic():
        bon = _verrouiller(bon)
        if not bon.ouvert:
            raise ConflitMetier('Ce bon de travail est deja clos.')

        if date_fin:
            fin = timezone.make_aware(datetime.combine(date_fin, time(12, 0)))
            if timezone.localdate(maintenant) == date_fin:
                fin = maintenant
        else:
            fin = maintenant
        debut = bon.debut or fin
        if fin < debut and timezone.localdate(fin) < timezone.localdate(debut):
            raise ConflitMetier('La date de fin ne peut pas preceder le debut de l intervention.')

        vehicule = bon.vehicule
        if kilometrage is not None:
            enregistrer_kilometrage(vehicule, kilometrage, source='entretien', auteur=auteur,
                                    note=f'{bon.code} — {bon.titre}')
        vehicule.refresh_from_db(fields=['kilometrage'])

        bon.statut = 'termine'
        bon.debut = min(debut, fin)
        bon.fin = fin
        bon.kilometrage = kilometrage if kilometrage is not None else vehicule.kilometrage
        if cout_pieces is not None:
            bon.cout_pieces = cout_pieces
        if cout_main_oeuvre is not None:
            bon.cout_main_oeuvre = cout_main_oeuvre
        if fournisseur is not None:
            bon.fournisseur = fournisseur
        if notes is not None:
            bon.notes_cloture = notes
        bon.save()

        # Le prochain entretien preventif se recalcule a partir de celui-ci
        # (sauf si le plan a deja ete recale par une intervention plus recente).
        plan = bon.plan
        date_realisation = timezone.localdate(fin)
        if plan and date_realisation >= plan.derniere_date:
            plan.dernier_km = max(plan.dernier_km, bon.kilometrage)
            plan.derniere_date = date_realisation
            plan.save(update_fields=['dernier_km', 'derniere_date'])

        incident = bon.incident
        if incident and incident.statut != 'traite':
            incident.statut = 'traite'
            incident.save(update_fields=['statut'])

        _liberer_vehicule(bon.vehicule_id, bon.pk)
    return bon


def annuler(bon: BonTravail, motif: str = '') -> BonTravail:
    with transaction.atomic():
        bon = _verrouiller(bon)
        if not bon.ouvert:
            raise ConflitMetier('Ce bon de travail est deja clos.')
        etait_en_cours = bon.statut == 'en-cours'
        bon.statut = 'annule'
        bon.fin = timezone.now()
        if motif:
            bon.notes_cloture = motif
        bon.save(update_fields=['statut', 'fin', 'notes_cloture', 'modifie_le'])
        if etait_en_cours:
            _liberer_vehicule(bon.vehicule_id, bon.pk)
    return bon

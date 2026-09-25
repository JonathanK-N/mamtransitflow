"""
TransitFlow — Calcul de la paie
Auteur : Jonathan K-N

Pour chaque chauffeur qui a un profil de paie actif :
1. gains automatiques, tires des trajets TERMINES commences dans la periode :
   - a l heure : heures reelles (debut -> fin du trajet). Au-dela du seuil
     hebdomadaire (40 h par defaut, Loi sur les normes du travail), les
     heures sont majorees (150 % par defaut). Les semaines sont les semaines
     ISO (lundi-dimanche) ; une semaine a cheval sur deux paies est comptee
     dans chacune pour la part qui lui revient ;
   - au trajet : nombre de trajets x taux ;
   - salaire fixe : montant par paie ;
2. lignes manuelles de l administrateur (prime, remboursement, avance...),
   conservees a chaque recalcul ;
3. indemnite de vacances si elle est versee a chaque paie ;
4. retenues : pour chaque cotisation active, part des gains imposables
   cumules sur l annee civile (date de paiement) comprise entre le plancher
   et le plafond annuels, moins l exemption repartie sur les paies de l annee.

Ce calcul donne une paie juste pour les cotisations a taux fixe (RRQ, AE,
RQAP). Les retenues d impot ne suivent pas les tables officielles (TP-1015.F,
T4127) : elles s appliquent comme un taux forfaitaire fixe par l entreprise.
"""

from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.dispatch.models import Trajet
from .models import ZERO, BulletinPaie, LigneBulletin, ParametresPaie, PeriodePaie, ProfilPaie, Retenue

CENT = Decimal('0.01')


def arrondi(valeur) -> Decimal:
    return Decimal(valeur).quantize(CENT, rounding=ROUND_HALF_UP)


class ErreurPaie(Exception):
    pass


def _heures(trajet) -> Decimal:
    return Decimal((trajet.fin - trajet.debut).total_seconds()) / Decimal(3600)


def heures_de_la_periode(chauffeur, periode, parametres):
    """(nombre de trajets, heures regulieres, heures supplementaires) du chauffeur sur la periode."""
    trajets = Trajet.objects.filter(chauffeur=chauffeur, statut='termine', fin__isnull=False)
    trajets = [t for t in trajets.filter(debut__date__gte=periode.debut - timezone.timedelta(days=1),
                                          debut__date__lte=periode.fin + timezone.timedelta(days=1))
               if periode.debut <= timezone.localtime(t.debut).date() <= periode.fin and t.fin > t.debut]
    par_semaine = defaultdict(Decimal)
    for t in trajets:
        par_semaine[timezone.localtime(t.debut).date().isocalendar()[:2]] += _heures(t)
    # Heures de la meme semaine deja payees dans la periode precedente (semaine a cheval).
    deja = _heures_semaine_avant(chauffeur, periode)
    regulieres = sup = ZERO
    for semaine, heures in par_semaine.items():
        avant = deja.get(semaine, ZERO)
        seuil_restant = max(ZERO, parametres.seuil_heures_sup - avant)
        regulieres += min(heures, seuil_restant)
        sup += max(ZERO, heures - seuil_restant)
    return len(trajets), arrondi(regulieres), arrondi(sup)


def _heures_semaine_avant(chauffeur, periode):
    """Heures de la semaine ISO du premier jour de la periode, faites avant ce jour."""
    lundi = periode.debut - timezone.timedelta(days=periode.debut.weekday())
    if lundi == periode.debut:
        return {}
    heures = defaultdict(Decimal)
    for t in Trajet.objects.filter(chauffeur=chauffeur, statut='termine', fin__isnull=False,
                                   debut__date__gte=lundi - timezone.timedelta(days=1),
                                   debut__date__lt=periode.debut + timezone.timedelta(days=1)):
        jour = timezone.localtime(t.debut).date()
        if lundi <= jour < periode.debut and t.fin > t.debut:
            heures[jour.isocalendar()[:2]] += _heures(t)
    return heures


def _cumul_imposable_avant(bulletin) -> Decimal:
    """Gains imposables deja verses au chauffeur cette annee, avant cette paie."""
    periode = bulletin.periode
    autres = BulletinPaie.objects.filter(
        chauffeur=bulletin.chauffeur, periode__date_paiement__year=periode.date_paiement.year,
    ).exclude(periode=periode).exclude(periode__statut='brouillon').filter(
        periode__date_paiement__lte=periode.date_paiement)
    return autres.aggregate(t=Sum('brut_imposable'))['t'] or ZERO


def _partie_cotisable(cumul_avant, base, plancher, plafond) -> Decimal:
    """Part de l intervalle [cumul_avant, cumul_avant + base] comprise entre plancher et plafond."""
    debut, fin = cumul_avant, cumul_avant + base
    bas = max(debut, plancher)
    haut = fin if plafond is None else min(fin, plafond)
    return max(ZERO, haut - bas)


def calculer_bulletin(bulletin, profil, parametres, retenues):
    """Recalcule les lignes automatiques d un bulletin (les lignes manuelles sont gardees)."""
    bulletin.lignes.filter(manuelle=False).delete()
    nb, regulieres, sup = heures_de_la_periode(bulletin.chauffeur, bulletin.periode, parametres)
    bulletin.mode, bulletin.nombre_trajets = profil.mode, nb
    bulletin.heures_regulieres, bulletin.heures_sup = (regulieres, sup) if profil.mode == 'horaire' else (ZERO, ZERO)
    ordre = 0
    nouvelles = []

    def ajouter(genre, code, libelle, montant, quantite=None, taux=None, imposable=True):
        nonlocal ordre
        ordre += 1
        nouvelles.append(LigneBulletin(bulletin=bulletin, genre=genre, code=code, libelle=libelle,
                                       quantite=quantite, taux=taux, montant=arrondi(montant),
                                       imposable=imposable, ordre=ordre))

    if profil.mode == 'horaire':
        ajouter('gain', 'REG', 'Heures regulieres', regulieres * profil.taux_horaire, regulieres, profil.taux_horaire)
        if sup:
            taux_sup = arrondi(profil.taux_horaire * parametres.majoration_heures_sup)
            ajouter('gain', 'HS', 'Heures supplementaires', sup * taux_sup, sup, taux_sup)
    elif profil.mode == 'trajet':
        ajouter('gain', 'TRJ', 'Trajets effectues', Decimal(nb) * profil.taux_trajet, Decimal(nb), profil.taux_trajet)
    else:
        ajouter('gain', 'SAL', 'Salaire de la periode', profil.salaire_periode)

    manuelles = list(bulletin.lignes.filter(manuelle=True))
    gains_imposables = sum((l.montant for l in nouvelles if l.genre == 'gain'), ZERO) + \
        sum((l.montant for l in manuelles if l.genre == 'gain' and l.imposable), ZERO)
    if parametres.taux_vacances > 0:
        vacances = gains_imposables * parametres.taux_vacances / 100
        ajouter('gain', 'VAC', 'Indemnite de vacances', vacances, gains_imposables, parametres.taux_vacances)
        gains_imposables += arrondi(vacances)

    bulletin.brut_imposable = arrondi(gains_imposables)
    cumul = _cumul_imposable_avant(bulletin)
    exemption_divisee = parametres.periodes_par_an or 1
    for r in retenues:
        cotisable = _partie_cotisable(cumul, bulletin.brut_imposable, r.plancher_annuel, r.plafond_annuel)
        cotisable = arrondi(max(ZERO, cotisable - r.exemption_annuelle / exemption_divisee))
        if not cotisable:
            continue  # sous le plancher, plafond atteint : pas de ligne a 0 $ sur le bulletin
        if r.taux_salarie:
            ajouter('retenue', r.code, r.libelle, cotisable * r.taux_salarie / 100, cotisable, r.taux_salarie)
        if r.taux_employeur:
            ajouter('employeur', r.code, r.libelle + ' (employeur)', cotisable * r.taux_employeur / 100,
                    cotisable, r.taux_employeur)
    LigneBulletin.objects.bulk_create(nouvelles)
    totaliser(bulletin)


def totaliser(bulletin):
    lignes = list(bulletin.lignes.all())
    gains = sum((l.montant for l in lignes if l.genre == 'gain'), ZERO)
    retenues = sum((l.montant for l in lignes if l.genre == 'retenue'), ZERO)
    bulletin.brut = arrondi(gains)
    bulletin.retenues = arrondi(retenues)
    bulletin.net = arrondi(gains - retenues)
    bulletin.cotisations_employeur = arrondi(sum((l.montant for l in lignes if l.genre == 'employeur'), ZERO))
    bulletin.save()


@transaction.atomic
def calculer_periode(periode: PeriodePaie) -> PeriodePaie:
    periode = PeriodePaie.objects.select_for_update().get(pk=periode.pk)
    if periode.statut != 'brouillon':
        raise ErreurPaie('Seule une paie en brouillon peut etre recalculee.')
    parametres = ParametresPaie.courants()
    retenues = list(Retenue.objects.filter(actif=True))
    profils = {p.chauffeur_id: p for p in ProfilPaie.objects.filter(actif=True).select_related('chauffeur')}
    # Un chauffeur sans profil actif sort de la paie, sauf s il a des lignes manuelles.
    for b in periode.bulletins.exclude(chauffeur_id__in=profils):
        if not b.lignes.filter(manuelle=True).exists():
            b.delete()
    for chauffeur_id, profil in profils.items():
        bulletin, _ = BulletinPaie.objects.get_or_create(periode=periode, chauffeur_id=chauffeur_id)
        calculer_bulletin(bulletin, profil, parametres, retenues)
    periode.calculee_le = timezone.now()
    periode.save(update_fields=['calculee_le'])
    return periode


def recalculer_bulletin(bulletin):
    """Apres l ajout ou le retrait d une ligne manuelle."""
    profil = ProfilPaie.objects.filter(chauffeur=bulletin.chauffeur).first()
    if profil:
        calculer_bulletin(bulletin, profil, ParametresPaie.courants(), list(Retenue.objects.filter(actif=True)))
    else:
        totaliser(bulletin)


TRANSITIONS = {
    'valider': ('brouillon', 'validee'),
    'payer': ('validee', 'payee'),
    'rouvrir': ('validee', 'brouillon'),
}


@transaction.atomic
def changer_statut(periode: PeriodePaie, action: str) -> PeriodePaie:
    periode = PeriodePaie.objects.select_for_update().get(pk=periode.pk)
    depart, arrivee = TRANSITIONS[action]
    if periode.statut != depart:
        raise ErreurPaie(f'Action impossible : la paie est {periode.get_statut_display().lower()}.')
    if action == 'valider' and not periode.bulletins.exists():
        raise ErreurPaie('Calculez la paie avant de la valider : aucun bulletin.')
    periode.statut = arrivee
    periode.save(update_fields=['statut'])
    return periode

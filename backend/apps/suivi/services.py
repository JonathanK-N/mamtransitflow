"""
TransitFlow — Regles metier du suivi GPS
Auteur : Jonathan K-N
"""

from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import PositionGPS, distance_m

# Au-dela, la mesure est trop imprecise pour etre utile (triangulation par antennes).
PRECISION_MAXIMALE_M = 1000
# Points acceptes autour du trajet : un peu avant le depart (horloge du
# telephone en avance) et jusqu a 2 minutes dans le futur (decalage d horloge).
MARGE_AVANT_DEPART = timedelta(minutes=10)
MARGE_FUTUR = timedelta(minutes=2)

# Etat de la liaison d un trajet en cours, d apres l age de son dernier point.
DELAI_EN_LIGNE = timedelta(seconds=60)
DELAI_INTERMITTENT = timedelta(minutes=5)

# Calcul de distance : on ignore les points peu precis et les sauts
# physiquement impossibles (reflet GPS entre deux immeubles, par exemple).
PRECISION_POUR_DISTANCE_M = 100
VITESSE_IMPOSSIBLE_KMH = 250
POINTS_MAXIMUM_PARCOURS = 2000

_SIX_DECIMALES = Decimal('0.000001')


def _coordonnee(valeur: float) -> Decimal:
    return Decimal(str(valeur)).quantize(_SIX_DECIMALES, rounding=ROUND_HALF_UP)


def enregistrer_positions(trajet, points: list[dict]) -> dict:
    """
    Enregistre un lot de points valides pour un trajet en cours. Renvoie
    {'recues', 'enregistrees', 'ignorees'} : un point est ignore s il est
    trop imprecis, hors de la fenetre du trajet, ou deja recu (renvoi).
    """
    maintenant = timezone.now()
    borne_basse = trajet.debut - MARGE_AVANT_DEPART
    borne_haute = maintenant + MARGE_FUTUR
    a_creer = {}
    for point in points:
        if point.get('precision') is not None and point['precision'] > PRECISION_MAXIMALE_M:
            continue
        if not borne_basse <= point['horodatage'] <= borne_haute:
            continue
        a_creer[point['horodatage']] = PositionGPS(
            trajet=trajet, chauffeur_id=trajet.chauffeur_id, plaque=trajet.plaque,
            latitude=_coordonnee(point['lat']), longitude=_coordonnee(point['lng']),
            precision_m=point.get('precision'), vitesse_kmh=point.get('vitesse'), cap=point.get('cap'),
            horodatage=point['horodatage'],
        )

    deja_recus = set(PositionGPS.objects.filter(trajet=trajet, horodatage__in=list(a_creer))
                     .values_list('horodatage', flat=True))
    nouveaux = [p for instant, p in a_creer.items() if instant not in deja_recus]
    try:
        with transaction.atomic():
            PositionGPS.objects.bulk_create(nouveaux)
    except IntegrityError:
        # Deux envois simultanes du meme lot : on insere point par point en ignorant les doublons.
        enregistres = 0
        for position in nouveaux:
            try:
                with transaction.atomic():
                    position.save()
                enregistres += 1
            except IntegrityError:
                pass
        return {'recues': len(points), 'enregistrees': enregistres, 'ignorees': len(points) - enregistres}
    return {'recues': len(points), 'enregistrees': len(nouveaux), 'ignorees': len(points) - len(nouveaux)}


def etat_liaison(derniere, maintenant) -> str:
    if derniere is None:
        return 'aucune'
    age = maintenant - derniere.horodatage
    if age <= DELAI_EN_LIGNE:
        return 'en-ligne'
    if age <= DELAI_INTERMITTENT:
        return 'intermittent'
    return 'perdue'


def _vitesse_kmh(a, b):
    secondes = (b.horodatage - a.horodatage).total_seconds()
    if secondes <= 0:
        return None, 0.0
    troncon = distance_m(a.latitude, a.longitude, b.latitude, b.longitude)
    return troncon / secondes * 3.6, troncon


def statistiques(positions: list) -> dict:
    """
    Distance parcourue (m), duree suivie (s), vitesses moyenne et maximale (km/h).

    Un point qui impliquerait un saut physiquement impossible (> 250 km/h)
    est ecarte. Si le point suivant confirme la nouvelle position (saut
    plausible entre les deux), c est la reference precedente qui etait
    fausse : on repart de la nouvelle position sans compter le saut. Un
    premier point aberrant ne bloque donc pas tout le calcul.

    La vitesse maximale vient du telephone quand il la fournit ; sinon elle
    est estimee sur des troncons d au moins 10 s (en dessous, l imprecision
    du GPS gonfle artificiellement les vitesses).
    """
    distance = 0.0
    vitesses_appareil = [p.vitesse_kmh for p in positions if p.vitesse_kmh is not None]
    vitesses_estimees = []
    precedent = candidat = None
    for p in positions:
        if p.precision_m is not None and p.precision_m > PRECISION_POUR_DISTANCE_M:
            continue
        if precedent is None:
            precedent = p
            continue
        vitesse, troncon = _vitesse_kmh(precedent, p)
        if vitesse is None:
            continue
        if vitesse > VITESSE_IMPOSSIBLE_KMH:
            confirme = candidat is not None and (_vitesse_kmh(candidat, p)[0] or 0) <= VITESSE_IMPOSSIBLE_KMH
            if confirme:
                vitesse, troncon = _vitesse_kmh(candidat, p)
                precedent = candidat  # l ancienne reference etait le point aberrant
            else:
                candidat = p
                continue
        candidat = None
        if (p.horodatage - precedent.horodatage).total_seconds() >= 10:
            vitesses_estimees.append(vitesse)
        distance += troncon
        precedent = p
    duree = (positions[-1].horodatage - positions[0].horodatage).total_seconds() if len(positions) > 1 else 0
    moyenne = distance / duree * 3.6 if duree > 0 else None
    # La vitesse maximale ne peut pas etre inferieure a la moyenne (cas d un
    # trajet court dont les troncons sont tous trop brefs pour etre estimes).
    vitesse_max = max(vitesses_appareil or vitesses_estimees or [0])
    if moyenne and not vitesses_appareil:
        vitesse_max = max(vitesse_max, moyenne)
    return {
        'distanceM': round(distance),
        'dureeS': round(duree),
        'vitesseMoyenneKmh': round(moyenne, 1) if moyenne else None,
        'vitesseMaxKmh': round(vitesse_max, 1) if vitesse_max else None,
    }


def alleger(positions: list, maximum: int = POINTS_MAXIMUM_PARCOURS) -> list:
    """Reduit un tres long parcours a `maximum` points repartis regulierement (premier et dernier conserves)."""
    if len(positions) <= maximum:
        return positions
    pas = (len(positions) - 1) / (maximum - 1)
    return [positions[round(i * pas)] for i in range(maximum)]

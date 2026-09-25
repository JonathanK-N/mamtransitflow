"""
TransitFlow — Regles metier de la flotte
Auteur : Jonathan K-N

Point d entree unique pour faire avancer le compteur d un vehicule : la
saisie manuelle (admin), la fin d un trajet (apps/dispatch) et la cloture
d un bon de travail (apps/entretien) passent toutes par ici.
"""

from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import ReleveKilometrage, Vehicule

# Garde-fou contre les fautes de frappe (un zero de trop) : un vehicule de
# navette ne parcourt pas plus que ca entre deux releves.
ECART_MAXIMAL_KM = 20000


def enregistrer_kilometrage(vehicule: Vehicule, kilometrage: int, source: str = 'manuel', auteur=None,
                            note: str = '', champ: str = 'kilometrage') -> ReleveKilometrage | None:
    """
    Enregistre un releve et met a jour le compteur du vehicule.

    - un compteur ne recule jamais : une valeur inferieure au compteur
      actuel est refusee (ValidationError, donc HTTP 400 dans une vue DRF) ;
    - une valeur egale au compteur actuel n ajoute pas de releve (None) ;
    - un saut de plus de ECART_MAXIMAL_KM est refuse (faute de frappe probable).

    Le vehicule est verrouille (select_for_update) le temps de l ecriture :
    deux releves simultanes ne peuvent pas se croiser.
    """
    if kilometrage is None:
        return None
    kilometrage = int(kilometrage)
    if kilometrage < 0:
        raise ValidationError({champ: ['Le kilometrage ne peut pas etre negatif.']})

    with transaction.atomic():
        verrouille = Vehicule.objects.select_for_update().get(pk=vehicule.pk)
        if kilometrage < verrouille.kilometrage:
            raise ValidationError({champ: [(
                f'Le compteur de {verrouille.plaque} indique deja {verrouille.kilometrage} km : '
                'un releve ne peut pas etre inferieur.')]})
        if kilometrage - verrouille.kilometrage > ECART_MAXIMAL_KM and verrouille.releves.exists():
            raise ValidationError({champ: [(
                f'Ecart de plus de {ECART_MAXIMAL_KM} km depuis le dernier releve : verifiez la saisie.')]})
        if kilometrage == verrouille.kilometrage and verrouille.releves.exists():
            return None

        releve = ReleveKilometrage.objects.create(vehicule=verrouille, kilometrage=kilometrage, source=source,
                                                  auteur=auteur, note=note[:255])
        verrouille.kilometrage = kilometrage
        verrouille.save(update_fields=['kilometrage'])
    vehicule.kilometrage = kilometrage
    return releve

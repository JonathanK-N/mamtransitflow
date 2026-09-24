"""
TransitFlow — Permissions par groupe (DRF)
Auteur : Jonathan K-N

Equivalent du decorateur `exiger()` des versions precedentes (Flask puis
FastAPI), mais construit sur le systeme de Groupes deja integre a Django :

  class MaVue(APIView):
      permission_classes = [DansGroupe('fleet.admin')]

`EstConnecte` (sans argument) demande juste d etre authentifie, peu
importe le groupe -- c est la permission par defaut de toutes les routes
de l API (voir DEFAULT_PERMISSION_CLASSES dans settings.py).
"""

from rest_framework.permissions import BasePermission


def est_admin(utilisateur) -> bool:
    """Vrai si le compte connecte appartient au groupe 'fleet.admin'."""
    return bool(utilisateur and utilisateur.is_authenticated and utilisateur.a_groupe('fleet.admin'))


def voit_tout(utilisateur, chauffeur) -> bool:
    """
    Regle de cloisonnement commune a toutes les apps : un administrateur
    voit toutes les donnees, un chauffeur uniquement celles qui le
    concernent (sa fiche, ses trajets, ses incidents).
    """
    return est_admin(utilisateur) or (chauffeur is not None and utilisateur.chauffeur_id == chauffeur.id)


class EstConnecte(BasePermission):
    message = 'Authentification requise.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


def DansGroupe(nom_groupe: str):
    """Fabrique une classe de permission DRF qui verifie en plus l appartenance a un groupe."""

    class _DansGroupe(EstConnecte):
        message = 'Acces refuse.'

        def has_permission(self, request, view):
            return super().has_permission(request, view) and request.user.a_groupe(nom_groupe)

    return _DansGroupe

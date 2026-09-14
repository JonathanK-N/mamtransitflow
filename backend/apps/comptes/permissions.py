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

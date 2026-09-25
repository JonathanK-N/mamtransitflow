"""TransitFlow — Permissions liees aux modules et au portail chauffeur
   Auteur : Jonathan K-N

   ModuleActif('paie')     : l API d un module desactive repond 403.
   PortailAutorise('paie') : un chauffeur n accede a la fonction que si
                             l administrateur l a ouverte dans le portail
                             (un administrateur passe toujours)."""

from rest_framework.permissions import BasePermission

from apps.comptes.permissions import est_admin
from .models import Entreprise


def ModuleActif(module: str):
    class _ModuleActif(BasePermission):
        message = f'Le module {module} est desactive pour cette entreprise.'

        def has_permission(self, request, view):
            return bool(getattr(Entreprise.courante(), 'module_' + module))

    return _ModuleActif


def PortailAutorise(droit: str):
    class _PortailAutorise(BasePermission):
        message = 'Cette fonction n est pas ouverte dans le portail chauffeur.'

        def has_permission(self, request, view):
            if est_admin(request.user):
                return True
            return Entreprise.courante().portail_autorise(droit)

    return _PortailAutorise

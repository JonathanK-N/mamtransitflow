"""Permissions basées sur le rôle métier (Profil.role), pas seulement is_staff."""
from rest_framework.permissions import BasePermission, SAFE_METHODS


def est_admin(user):
    return bool(
        user and user.is_authenticated
        and hasattr(user, "profil") and user.profil.role == "admin"
    )


def est_chauffeur(user):
    return bool(
        user and user.is_authenticated
        and hasattr(user, "profil") and user.profil.role == "chauffeur"
    )


class EstAdmin(BasePermission):
    """Accès réservé aux comptes administrateur."""

    message = "Réservé aux administrateurs."

    def has_permission(self, request, view):
        return est_admin(request.user)


class EstAdminOuLectureSeule(BasePermission):
    """Lecture pour tout utilisateur authentifié, écriture réservée à l'admin."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return est_admin(request.user)


class EstProprietaireOuAdmin(BasePermission):
    """
    Un chauffeur ne voit/modifie que ses propres ressources (trajets, incidents,
    sa propre fiche) ; l'administrateur a accès à tout.
    """

    def has_object_permission(self, request, view, obj):
        if est_admin(request.user):
            return True
        chauffeur = getattr(request.user, "chauffeur", None)
        if chauffeur is None:
            return False
        cible = obj if obj.__class__.__name__ == "Chauffeur" else getattr(obj, "chauffeur", None)
        return cible == chauffeur
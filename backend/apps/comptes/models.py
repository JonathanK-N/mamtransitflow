"""
TransitFlow — Modele : comptes de connexion
Auteur : Jonathan K-N

Utilisateur remplace le User par defaut de Django : on se connecte avec un
courriel (pas un nom d utilisateur), et un compte peut etre lie a une
fiche chauffeur (backend/apps/drivers). Les groupes de permission
('fleet.admin', 'fleet.driver', ...) utilisent le systeme de Groupes deja
integre a Django (django.contrib.auth.models.Group) -- pas besoin de le
reinventer, Django le fait deja tres bien.

Voir backend/transitflow/settings.py : AUTH_USER_MODEL = 'comptes.Utilisateur'.
"""

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models


class UtilisateurManager(BaseUserManager):
    """Django a besoin d un manager personnalise des qu on remplace 'username' par 'courriel'."""

    def create_user(self, courriel, mot_de_passe=None, **champs_supplementaires):
        if not courriel:
            raise ValueError('Un courriel est requis.')
        # Courriel entierement en minuscules : la connexion ne depend pas de
        # la casse saisie (voir apps/comptes/views.py).
        utilisateur = self.model(courriel=courriel.strip().lower(), **champs_supplementaires)
        utilisateur.set_password(mot_de_passe)
        utilisateur.save(using=self._db)
        return utilisateur

    def create_superuser(self, courriel, mot_de_passe=None, **champs_supplementaires):
        champs_supplementaires.setdefault('is_staff', True)
        champs_supplementaires.setdefault('is_superuser', True)
        return self.create_user(courriel, mot_de_passe, **champs_supplementaires)


class Utilisateur(AbstractBaseUser, PermissionsMixin):
    """
    Un compte de connexion. PermissionsMixin apporte gratuitement les
    champs `groups` (groupes de permission) et `user_permissions`,
    utilises par apps/comptes/permissions.py pour proteger les routes.
    """
    courriel = models.EmailField(unique=True)
    nom = models.CharField(max_length=150, blank=True)
    # Lien optionnel vers une fiche chauffeur (backend/apps/drivers/models.py) :
    # seuls les comptes du groupe 'fleet.driver' en ont un.
    chauffeur = models.OneToOneField('drivers.Chauffeur', null=True, blank=True,
                                      on_delete=models.SET_NULL, related_name='compte')
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    cree_le = models.DateTimeField(auto_now_add=True)

    objects = UtilisateurManager()

    USERNAME_FIELD = 'courriel'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.courriel

    def a_groupe(self, nom_groupe: str) -> bool:
        """Vrai si ce compte appartient au groupe de permission indique (ex. 'fleet.admin')."""
        return self.groups.filter(name=nom_groupe).exists()

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profil


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def creer_profil_admin_pour_superutilisateur(sender, instance, created, **kwargs):
    """
    Un compte créé via `createsuperuser` n'a pas de Profil : on lui en attribue
    un avec le rôle admin.
    """
    if instance.is_superuser and not hasattr(instance, "profil"):
        Profil.objects.create(user=instance, role=Profil.Role.ADMIN)
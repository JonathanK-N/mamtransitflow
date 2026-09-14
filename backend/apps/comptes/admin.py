from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Utilisateur


class UtilisateurAdmin(UserAdmin):
    model = Utilisateur
    ordering = ['courriel']
    list_display = ['courriel', 'nom', 'chauffeur', 'is_staff', 'is_active']
    fieldsets = (
        (None, {'fields': ('courriel', 'password')}),
        ('Informations', {'fields': ('nom', 'chauffeur')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')})
    )
    add_fieldsets = (
        (None, {'classes': ('wide',), 'fields': ('courriel', 'password1', 'password2')}),
    )
    search_fields = ['courriel', 'nom']


admin.site.register(Utilisateur, UtilisateurAdmin)

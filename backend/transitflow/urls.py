"""
TransitFlow — Routage principal
Auteur : Jonathan K-N

Assemble les URLs de chaque app (comptes, drivers, fleet, dispatch,
maintenance, entretien, suivi, reporting) sous /api/, et sert toujours les pages du
front-end (index.html, admin/, chauffeur/, assets/) depuis ce meme
serveur Django -- comme le faisait backend/app.py (FastAPI) avant lui --
pour eviter tout probleme de CORS en developpement.

Le site d administration integre de Django (django.contrib.admin) est
deplace sur /django-admin/ : /admin/ est deja pris par les pages HTML de
l espace administrateur du front-end (admin/tableau-de-bord.html, etc.).
"""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path, re_path
from django.views.static import serve

from .settings import RACINE_PROJET


def sante(request):
    """Petite route de verification pour confirmer que le serveur repond bien."""
    return JsonResponse({'ok': True, 'service': 'transitflow-api'})


def page_accueil(request):
    return serve(request, path='index.html', document_root=RACINE_PROJET)


urlpatterns = [
    path('django-admin/', admin.site.urls),

    # Chaque app declare ses propres chemins complets (voir apps/*/urls.py) :
    # pas de prefixe ajoute ici, pour garder un controle exact sur les barres
    # obliques finales et rester identique a ce que le front-end appelle.
    path('', include('apps.comptes.urls')),
    path('', include('apps.drivers.urls')),
    path('', include('apps.fleet.urls')),
    path('', include('apps.dispatch.urls')),
    path('', include('apps.maintenance.urls')),
    path('', include('apps.entretien.urls')),
    path('', include('apps.suivi.urls')),
    path('', include('apps.reporting.urls')),
    path('api/sante', sante),

    # ---- Pages statiques du front-end -----------------------------------
    # On n expose pas tout le dossier racine (ca donnerait acces au code du
    # backend) : seulement les dossiers/fichiers dont le front-end a besoin.
    path('', page_accueil),
    path('index.html', page_accueil),
    re_path(r'^assets/(?P<path>.*)$', serve, {'document_root': RACINE_PROJET / 'assets'}),
    re_path(r'^admin/(?P<path>.*)$', serve, {'document_root': RACINE_PROJET / 'admin'}),
    re_path(r'^chauffeur/(?P<path>.*)$', serve, {'document_root': RACINE_PROJET / 'chauffeur'}),
]

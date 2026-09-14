"""TransitFlow — URLs de l app comptes
   Auteur : Jonathan K-N

   Chemins complets (pas de prefixe ajoute par le urls.py principal) pour
   garder un controle exact sur la presence ou non d une barre oblique
   finale -- le front-end existant (assets/js/*.js) appelle ces routes
   sans barre finale (ex. '/api/auth/connexion', pas '/api/auth/connexion/')."""

from django.urls import path

from .views import ConnexionView, CreerCompteView, SessionView

urlpatterns = [
    path('api/auth/connexion', ConnexionView.as_view()),
    path('api/auth/session', SessionView.as_view()),
    path('api/auth/comptes', CreerCompteView.as_view())
]

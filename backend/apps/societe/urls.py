"""TransitFlow — URLs de l app societe
   Auteur : Jonathan K-N (chemins complets, voir apps/comptes/urls.py)"""

from django.urls import path

from .views import EntreprisePubliqueView, EntrepriseView

urlpatterns = [
    path('api/entreprise/publique', EntreprisePubliqueView.as_view()),
    path('api/entreprise', EntrepriseView.as_view()),
]

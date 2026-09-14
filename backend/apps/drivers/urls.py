"""TransitFlow — URLs de l app drivers
   Auteur : Jonathan K-N (chemins complets, voir apps/comptes/urls.py)"""

from django.urls import path

from .views import ChauffeurDetailView, ChauffeursView

urlpatterns = [
    path('api/chauffeurs', ChauffeursView.as_view()),
    path('api/chauffeurs/<str:code>', ChauffeurDetailView.as_view())
]

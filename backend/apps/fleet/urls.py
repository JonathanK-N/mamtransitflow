"""TransitFlow — URLs de l app fleet
   Auteur : Jonathan K-N (chemins complets, voir apps/comptes/urls.py)"""

from django.urls import path

from .views import VehiculesView

urlpatterns = [path('api/vehicules', VehiculesView.as_view())]

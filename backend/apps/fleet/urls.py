"""TransitFlow — URLs de l app fleet
   Auteur : Jonathan K-N (chemins complets, voir apps/comptes/urls.py)"""

from django.urls import path

from .views import KilometrageView, VehiculeDetailView, VehiculesView

urlpatterns = [
    path('api/vehicules', VehiculesView.as_view()),
    path('api/vehicules/<str:plaque>/kilometrage', KilometrageView.as_view()),
    path('api/vehicules/<str:plaque>', VehiculeDetailView.as_view()),
]

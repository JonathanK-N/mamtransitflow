"""TransitFlow — URLs de l app reporting
   Auteur : Jonathan K-N (chemins complets, voir apps/comptes/urls.py)"""

from django.urls import path

from .views import IndicateursView

urlpatterns = [path('api/indicateurs', IndicateursView.as_view())]

"""TransitFlow — URLs de l app suivi
   Auteur : Jonathan K-N (chemins complets, voir apps/comptes/urls.py)"""

from django.urls import path

from .views import EnDirectView, ParcoursView, PositionsView

urlpatterns = [
    path('api/trajets/<str:code>/positions', PositionsView.as_view()),
    path('api/trajets/<str:code>/parcours', ParcoursView.as_view()),
    path('api/suivi/en-direct', EnDirectView.as_view()),
]

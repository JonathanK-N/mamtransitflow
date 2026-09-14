"""TransitFlow — URLs de l app maintenance
   Auteur : Jonathan K-N (chemins complets, voir apps/comptes/urls.py)"""

from django.urls import path

from .views import IncidentDetailView, IncidentsView, TraiterIncidentView

urlpatterns = [
    path('api/incidents', IncidentsView.as_view()),
    path('api/incidents/<str:code>/traiter', TraiterIncidentView.as_view()),
    path('api/incidents/<str:code>', IncidentDetailView.as_view())
]

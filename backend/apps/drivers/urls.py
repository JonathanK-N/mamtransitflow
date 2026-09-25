"""TransitFlow — URLs de l app drivers
   Auteur : Jonathan K-N (chemins complets, voir apps/comptes/urls.py)"""

from django.urls import path

from .views import AccesChauffeurView, ChauffeurDetailView, ChauffeursView, InvitationChauffeurView

urlpatterns = [
    path('api/chauffeurs', ChauffeursView.as_view()),
    path('api/chauffeurs/<str:code>/invitation', InvitationChauffeurView.as_view()),
    path('api/chauffeurs/<str:code>/acces', AccesChauffeurView.as_view()),
    path('api/chauffeurs/<str:code>', ChauffeurDetailView.as_view()),
]

"""TransitFlow — URLs de l app dispatch
   Auteur : Jonathan K-N (chemins complets, voir apps/comptes/urls.py)

   L ordre compte : les motifs plus specifiques (en-cours/<code>, <code>/arrets,
   <code>/terminer) doivent etre declares avant le motif generique <code>,
   sinon Django essaierait de le faire correspondre en premier."""

from django.urls import path

from .views import AjouterArretView, TerminerTrajetView, TrajetDetailView, TrajetEnCoursView, TrajetsView

urlpatterns = [
    path('api/trajets', TrajetsView.as_view()),
    path('api/trajets/en-cours/<str:code>', TrajetEnCoursView.as_view()),
    path('api/trajets/<str:code>/arrets', AjouterArretView.as_view()),
    path('api/trajets/<str:code>/terminer', TerminerTrajetView.as_view()),
    path('api/trajets/<str:code>', TrajetDetailView.as_view())
]

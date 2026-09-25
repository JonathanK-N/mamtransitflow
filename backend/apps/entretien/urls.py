"""TransitFlow — URLs de l app entretien
   Auteur : Jonathan K-N (chemins complets, voir apps/comptes/urls.py)"""

from django.urls import path

from .views import (AnnulerBonView, BonDetailView, BonsView, CoutsView, DemarrerBonView, EcheancesView,
                    ExportBonsView, PlanDetailView, PlansView, TerminerBonView)

urlpatterns = [
    path('api/entretien/plans', PlansView.as_view()),
    path('api/entretien/plans/<str:code>', PlanDetailView.as_view()),
    path('api/entretien/echeances', EcheancesView.as_view()),
    path('api/entretien/bons', BonsView.as_view()),
    path('api/entretien/bons/<str:code>/demarrer', DemarrerBonView.as_view()),
    path('api/entretien/bons/<str:code>/terminer', TerminerBonView.as_view()),
    path('api/entretien/bons/<str:code>/annuler', AnnulerBonView.as_view()),
    path('api/entretien/bons/<str:code>', BonDetailView.as_view()),
    path('api/entretien/couts', CoutsView.as_view()),
    path('api/entretien/export.csv', ExportBonsView.as_view()),
]

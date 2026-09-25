"""TransitFlow — URLs de l app paie
   Auteur : Jonathan K-N (chemins complets, voir apps/comptes/urls.py)"""

from django.urls import path

from . import views as v

urlpatterns = [
    path('api/paie/parametres', v.ParametresView.as_view()),
    path('api/paie/retenues', v.RetenuesView.as_view()),
    path('api/paie/retenues/<int:pk>', v.RetenueDetailView.as_view()),
    path('api/paie/profils', v.ProfilsView.as_view()),
    path('api/paie/profils/<str:code>', v.ProfilDetailView.as_view()),
    path('api/paie/periodes', v.PeriodesView.as_view()),
    path('api/paie/periodes/<str:code>/export.csv', v.ExportPeriodeView.as_view()),
    path('api/paie/periodes/<str:code>/<str:action>', v.PeriodeActionView.as_view()),
    path('api/paie/periodes/<str:code>', v.PeriodeDetailView.as_view()),
    path('api/paie/mes-bulletins', v.MesBulletinsView.as_view()),
    path('api/paie/bulletins/<str:code>/lignes', v.LignesBulletinView.as_view()),
    path('api/paie/bulletins/<str:code>', v.BulletinDetailView.as_view()),
    path('api/paie/lignes/<int:pk>', v.LigneDetailView.as_view()),
]

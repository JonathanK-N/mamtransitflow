from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

router = DefaultRouter()
router.register("chauffeurs", views.ChauffeurViewSet, basename="chauffeur")
router.register("vehicules", views.VehiculeViewSet, basename="vehicule")
router.register("trajets", views.TrajetViewSet, basename="trajet")
router.register("incidents", views.IncidentViewSet, basename="incident")

urlpatterns = [
    path("auth/connexion/", views.ConnexionView.as_view(), name="auth-connexion"),
    path("auth/rafraichir/", TokenRefreshView.as_view(), name="auth-rafraichir"),
    path("auth/moi/", views.MoiView.as_view(), name="auth-moi"),
    path("indicateurs/", views.IndicateursView.as_view(), name="indicateurs"),
    path("", include(router.urls)),
]
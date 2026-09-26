"""Auteur : Jonathan Kakesa (JonathanK-N)."""
from django.urls import path
from . import views as v, auth as a

urlpatterns=[
    path('auth/csrf',a.CsrfView.as_view()),path('auth/register',a.RegisterView.as_view()),
    path('auth/login',a.LoginView.as_view()),path('auth/refresh',a.RefreshView.as_view()),
    path('auth/logout',a.LogoutView.as_view()),path('auth/me',a.MeView.as_view()),
    path('auth/password/request',a.PasswordRequestView.as_view()),path('auth/password/reset',a.PasswordResetView.as_view()),
    path('invitation/accept',v.AcceptInvitationView.as_view()),
    path('catalog',v.CatalogView.as_view()),path('organization',v.OrganizationView.as_view()),
    path('dashboard',v.DashboardView.as_view()),path('reports',v.ReportsView.as_view()),
    path('team',v.TeamView.as_view()),
    path('documents/<uuid:pk>/download',v.DownloadView.as_view()),
    path('missions/<uuid:pk>/positions',v.PositionsView.as_view()),
    path('<str:resource>/export',v.ExportView.as_view()),
    path('<str:resource>/<uuid:pk>/actions/<str:action>',v.ActionView.as_view()),
    path('<str:resource>/<uuid:pk>',v.ResourceView.as_view()),
    path('<str:resource>',v.ResourceView.as_view()),
]

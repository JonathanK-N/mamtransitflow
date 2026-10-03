"""Auteur : Jonathan Kakesa (JonathanK-N)."""
from django.urls import path
from . import views as v, auth as a
from . import applications as apps
from .delivery import ReceiptView,DeliveryDocumentsView
from .portal import PortalAdminView,PortalView
from .field import FieldView,FieldContextView,NotificationsView
from .messaging import MessagingView, CollaboratorsView, MessagesView, MessageReadView, MessageAttachmentView
from .notifications import GlobalNotificationsView, PreferencesView
from .push import PushSubscriptionsView

from .personnel_actions import EmployeeActionView

urlpatterns=[
    path('employees/<uuid:pk>/contact',EmployeeActionView.as_view(http_method_names=['post','options']),{'action':'contact'}),
    path('employees/<uuid:pk>/remove',EmployeeActionView.as_view(http_method_names=['post','options']),{'action':'remove'}),
    path('messaging/collaborators',CollaboratorsView.as_view()),
    path('messaging/conversations',MessagingView.as_view(http_method_names=['get','post','head','options'])),
    path('messaging/conversations/<uuid:pk>',MessagingView.as_view(http_method_names=['get','patch','head','options'])),
    path('messaging/conversations/<uuid:pk>/messages',MessagesView.as_view(http_method_names=['get','post','head','options'])),
    path('messaging/conversations/<uuid:pk>/read',MessageReadView.as_view(http_method_names=['post','options'])),
    path('messaging/attachments/<uuid:pk>',MessageAttachmentView.as_view(http_method_names=['get','head','options'])),
    path('notifications',GlobalNotificationsView.as_view()),
    path('notifications/preferences',PreferencesView.as_view()),
    path('notifications/subscriptions',PushSubscriptionsView.as_view()),
    path('field/context',FieldContextView.as_view()),
    path('field/reports',FieldView.as_view()),
    path('field/reports/<uuid:pk>/attachments',FieldView.as_view()),
    path('field/attachments/<uuid:pk>',FieldView.as_view()),
    path('field/notifications',NotificationsView.as_view()),
    path('missions/<uuid:pk>/delivery-documents',DeliveryDocumentsView.as_view()),
    path('portal-access',PortalAdminView.as_view()),
    path('portal/<str:resource>/<uuid:pk>',PortalView.as_view()),
    path('portal/<str:resource>',PortalView.as_view()),
    path('missions/<uuid:pk>/receipt',ReceiptView.as_view()),
    path('missions/<uuid:pk>/receipt/pdf',ReceiptView.as_view(),{'pdf':True}),
    path('applications',apps.ApplicationStoreView.as_view()),
    path('applications/custom',apps.CustomApplicationView.as_view()),
    path('applications/custom/<uuid:pk>',apps.CustomApplicationView.as_view()),
    path('applications/custom/<uuid:app_id>/records',apps.CustomRecordsView.as_view()),
    path('applications/custom/<uuid:app_id>/records/<uuid:pk>',apps.CustomRecordsView.as_view()),
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

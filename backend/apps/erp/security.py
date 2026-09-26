"""Contexte et permissions. Auteur : Jonathan Kakesa (JonathanK-N)."""
from django.db import connection
from django.core.exceptions import ValidationError as DjangoValidation
from rest_framework.exceptions import PermissionDenied,ValidationError
from .models import Membership

OPERATIONAL={'partners','employees','vehicles','orders','routes','missions','bookings','expenses','documents'}
FINANCIAL={'partners','invoices','payments','accounts','journal','expenses','documents'}
WORKSHOP={'vehicles','maintenance','partners','stock','movements','purchases','documents'}


def set_scope(organization_id):
    if connection.vendor=='postgresql':
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('transitflow.organization', %s, true)",[str(organization_id)])


def membership(request):
    org=request.headers.get('X-Organization','')
    if not org:raise ValidationError('Sélectionnez une entreprise.')
    try:member=Membership.objects.select_related('organization').get(organization_id=org,user=request.user,active=True)
    except (Membership.DoesNotExist,ValueError,TypeError,DjangoValidation):raise PermissionDenied('Entreprise inaccessible.')
    set_scope(member.organization_id)
    return member


def allowed(role,resource,write=False):
    if role in ('owner','admin'):return True
    if role=='viewer':return not write
    if role=='operations':return resource in OPERATIONAL
    if role=='finance':return resource in FINANCIAL
    if role=='workshop':return resource in WORKSHOP
    if role=='driver':return resource in {'missions','documents'} and not write
    return False

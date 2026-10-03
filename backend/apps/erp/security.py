"""Contexte et permissions. Auteur : Jonathan Kakesa (JonathanK-N)."""
from django.db import connection, transaction
from django.core.exceptions import ValidationError as DjangoValidation
from rest_framework.exceptions import PermissionDenied,ValidationError
from .models import Membership

OPERATIONAL={'partners','employees','vehicles','orders','routes','missions','bookings','expenses','documents','contracts','pricing','subcontracts','incidents'}
FINANCIAL={'partners','invoices','payments','accounts','journal','expenses','documents','contracts','pricing','supplier-bills','supplier-payments','periods','statements'}
WORKSHOP={'vehicles','maintenance','partners','stock','movements','purchases','documents','incidents'}


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
    if resource=='employees' and role=='finance':return not write
    if resource in {'leave','advances'}:return role=='finance'
    if role=='viewer':return not write
    if role=='operations':return resource in OPERATIONAL
    if role=='finance':return resource in FINANCIAL
    if role=='workshop':return resource in WORKSHOP
    if role=='driver':return resource in {'missions','documents'} and not write
    return False


@transaction.atomic
def grant_invitation(invite,user):
    from . import models as m
    set_scope(invite.organization_id)
    m.Organization.objects.select_for_update().get(pk=invite.organization_id)
    if m.Membership.objects.filter(organization=invite.organization,user=user).exists():
        raise ValidationError('Ce compte dispose déjà d’un accès interne à cette entreprise.')
    if invite.role=='client':
        if not invite.partner_id or invite.partner.organization_id!=invite.organization_id or invite.partner.kind not in ('customer','both'):
            raise ValidationError('Le client lié à cette invitation est invalide.')
        access=m.PortalAccess.objects.filter(organization=invite.organization,user=user).first()
        if access and access.active and access.partner_id!=invite.partner_id:
            raise ValidationError('Révoquez l’ancien accès client avant de changer son rattachement.')
        m.PortalAccess.objects.update_or_create(organization=invite.organization,user=user,defaults={'partner':invite.partner,'active':True})
    else:
        if invite.role not in dict(m.ROLES):
            raise ValidationError('Rôle interne invalide.')
        if m.PortalAccess.objects.filter(organization=invite.organization,user=user,active=True).exists():
            raise ValidationError('Révoquez l’accès client avant de donner un accès interne.')
        email=user.courriel.strip().lower()
        employees=m.Employee.objects.select_for_update().filter(organization=invite.organization)
        employee=employees.filter(user=user).order_by('created_at','pk').first()
        if employee is None:
            matches=list(employees.filter(email__iexact=email).order_by('created_at','pk'))
            if len(matches)>1 or any(x.user_id not in (None,user.pk) for x in matches):
                raise ValidationError('Le courriel est déjà rattaché à une fiche Personnel ambiguë ou à un autre compte.')
            employee=matches[0] if matches else None
        if employee is None:
            m.Employee.objects.create(organization=invite.organization,user=user,email=email,
                name=user.nom.strip() or email,
                job={'driver':'driver','operations':'dispatcher','workshop':'mechanic'}.get(invite.role,'office'))
        else:
            changes=[]
            if employee.user_id is None:employee.user=user;changes.append('user')
            if not employee.email.strip():employee.email=email;changes.append('email')
            if not employee.name.strip():employee.name=user.nom.strip() or email;changes.append('name')
            if changes:employee.save(update_fields=changes+['updated_at'])
        m.Membership.objects.create(organization=invite.organization,user=user,role=invite.role)

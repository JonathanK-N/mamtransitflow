import logging
from django.db import transaction
from rest_framework.exceptions import ValidationError
from . import models as m

INTERNAL_JOBS = {'driver':'driver','operations':'dispatcher','workshop':'mechanic',
                 'finance':'office','admin':'office','owner':'office','viewer':'office'}


@transaction.atomic
def sync_employee(organization, user, role, *, active=True, dry_run=False):
    from .security import set_scope
    if role not in INTERNAL_JOBS:
        raise ValidationError('Rôle interne invalide.')
    set_scope(organization.pk)
    m.Organization.objects.select_for_update().get(pk=organization.pk)
    email = user.courriel.strip().lower()
    employees = m.Employee.objects.select_for_update().filter(organization=organization)
    matches = list(employees.filter(user=user).order_by('created_at','pk'))
    if len(matches) > 1:
        raise ValidationError('Plusieurs fiches Personnel sont liées à ce compte.')
    employee = matches[0] if matches else None
    if employee is None:
        matches = list(employees.filter(email__iexact=email).order_by('created_at','pk'))
        if len(matches) > 1 or any(x.user_id not in (None,user.pk) for x in matches):
            raise ValidationError('Le courriel est déjà rattaché à une fiche Personnel ambiguë ou à un autre compte.')
        employee = matches[0] if matches else None
    if employee is None:
        employee = m.Employee(organization=organization,user=user,email=email,
            name=user.nom.strip() or email,job=INTERNAL_JOBS[role],active=active)
        if not dry_run:employee.save()
        return employee,'created'
    changes = []
    linked = employee.user_id is None
    if linked:employee.user=user;changes.append('user')
    if not employee.email.strip():employee.email=email;changes.append('email')
    if not employee.name.strip():employee.name=user.nom.strip() or email;changes.append('name')
    if changes and not dry_run:employee.save(update_fields=changes+['updated_at'])
    return employee,'linked' if linked else 'updated' if changes else 'unchanged'


def reconcile_personnel(*, organization_id=None, dry_run=True):
    from .security import set_scope
    counts = dict(members=0,created=0,linked=0,updated=0,unchanged=0,conflicts=0,external=0)
    organizations = m.Organization.objects.order_by('pk')
    if organization_id:organizations=organizations.filter(pk=organization_id)
    for organization in organizations.iterator():
        with transaction.atomic():
            set_scope(organization.pk)
            m.Organization.objects.select_for_update().get(pk=organization.pk)
            members = m.Membership.objects.filter(organization=organization,role__in=INTERNAL_JOBS).select_related('user').order_by('pk')
            for member in members:
                counts['members']+=1
                if m.PortalAccess.objects.filter(organization=organization,user=member.user,active=True).exists():
                    counts['external']+=1
                    continue
                try:
                    _,outcome=sync_employee(organization,member.user,member.role,active=member.active,dry_run=dry_run)
                except ValidationError:
                    counts['conflicts']+=1
                    logging.getLogger(__name__).warning('Personnel conflict: organization=%s membership=%s',organization.pk,member.pk)
                    continue
                counts[outcome]+=1
    return counts

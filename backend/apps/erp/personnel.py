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


@transaction.atomic
def remove_employee(organization, actor, employee):
    from django.utils import timezone
    from rest_framework.exceptions import PermissionDenied
    from . import services
    from .realtime import publish
    m.Organization.objects.select_for_update().get(pk=organization.pk)
    actor=m.Membership.objects.get(pk=actor.pk,organization=organization,active=True)
    if actor.role not in ('owner','admin'):raise PermissionDenied('Administration requise.')
    employee=m.Employee.objects.select_for_update().get(pk=employee.pk,organization=organization)
    member=m.Membership.objects.select_for_update().filter(organization=organization,user_id=employee.user_id).first() if employee.user_id else None
    if member:
        if member.role=='owner' and member.active and m.Membership.objects.filter(organization=organization,active=True,role='owner').count()<=1:
            raise ValidationError('Conservez au moins un propriétaire actif.')
        if member.user_id==actor.user_id:raise ValidationError('Vous ne pouvez pas vous retirer depuis Personnel.')
        if member.role in ('owner','admin') and actor.role!='owner':raise PermissionDenied('Seul un propriétaire peut retirer un administrateur ou un propriétaire.')
    employees=m.Employee.objects.filter(organization=organization)
    employees=employees.filter(user_id=employee.user_id) if employee.user_id else employees.filter(pk=employee.pk)
    if m.Mission.objects.filter(organization=organization,driver__in=employees,status__in=['planned','active']).exists():
        raise ValidationError('Réaffectez ou annulez les missions planifiées et en cours avant de retirer cette personne.')
    employees.update(active=False,updated_at=timezone.now())
    if member:
        member.active=False;member.save(update_fields=['active'])
        m.ConversationParticipant.objects.filter(organization=organization,membership=member).update(active=False)
        m.GlobalNotification.objects.filter(organization=organization,user_id=member.user_id).update(push_pending=False)
        m.PushSubscription.objects.filter(organization=organization,user_id=member.user_id).delete()
        m.TeamInvitation.objects.filter(organization=organization,email__iexact=member.user.courriel,used_at__isnull=True).update(expires_at=timezone.now())
        transaction.on_commit(lambda:publish(organization.pk,[member.user_id],'access_revoked'))
        from .messaging import changed
        for conversation in m.Conversation.objects.filter(organization=organization,participants__membership=member):changed(conversation)
    services.audit(organization,actor.user,'employee-remove',employee,membership=member.pk if member else None)
    return employee

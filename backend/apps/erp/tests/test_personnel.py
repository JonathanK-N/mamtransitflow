from io import StringIO
import pytest
from django.core.management import call_command
from rest_framework.exceptions import ValidationError
from apps.comptes.models import Utilisateur
from apps.erp import models as m
from apps.erp.personnel import reconcile_personnel, sync_employee
from .test_workflows import env

pytestmark=pytest.mark.django_db


def account(email='staff@example.test'):
    return Utilisateur.objects.create_user(courriel=email,mot_de_passe='Personnel-recette-938!',nom='Jean Tshibangu')


@pytest.mark.parametrize('role,job',[('driver','driver'),('operations','dispatcher'),('workshop','mechanic'),('finance','office'),('admin','office'),('owner','office'),('viewer','office')])
def test_reconciliation_repairs_old_members_without_changing_access(env,role,job):
    user=account()
    member=m.Membership.objects.create(organization=env['org'],user=user,role=role)
    first=reconcile_personnel(organization_id=env['org'].pk,dry_run=False)
    assert first['created']==2
    employee=m.Employee.objects.get(organization=env['org'],user=user)
    assert employee.job==job and employee.name==user.nom and employee.email==user.courriel
    second=reconcile_personnel(organization_id=env['org'].pk,dry_run=False)
    assert second['created']==second['linked']==second['updated']==0
    assert m.Employee.objects.filter(organization=env['org'],user=user).count()==1
    member.refresh_from_db();assert member.role==role and member.active
    result=env['client'].get('/api/v2/employees')
    assert result.status_code==200
    assert str(employee.pk) in [row['id'] for row in result.data['results']]


def test_reconciliation_reuses_email_and_preserves_business_fields_and_inactive_state(env):
    user=account()
    m.Membership.objects.create(organization=env['org'],user=user,role='driver')
    employee=m.Employee.objects.create(organization=env['org'],email=user.courriel.upper(),name='Nom métier',
        job='mechanic',phone='123456',license_number='Permis conservé',notes='Notes métier',active=False)
    count=m.Employee.objects.count()
    preview=reconcile_personnel(organization_id=env['org'].pk)
    assert preview['linked']==1 and preview['created']==1
    employee.refresh_from_db();assert employee.user_id is None
    assert m.Employee.objects.count()==count
    result=reconcile_personnel(organization_id=env['org'].pk,dry_run=False)
    assert result['linked']==1
    employee.refresh_from_db()
    assert employee.user_id==user.pk
    assert (employee.name,employee.job,employee.phone,employee.license_number,employee.notes,employee.active)==('Nom métier','mechanic','123456','Permis conservé','Notes métier',False)
    rows=env['client'].get('/api/v2/employees').data['results']
    assert any(row['id']==str(employee.pk) and row['user']==user.pk and row['active'] is False for row in rows)


def test_reconciliation_strictly_separates_organizations(env):
    user=account()
    foreign=m.Employee.objects.create(organization=env['other'],user=user,email=user.courriel,name='Autre entreprise')
    m.Membership.objects.create(organization=env['org'],user=user,role='driver')
    reconcile_personnel(organization_id=env['org'].pk,dry_run=False)
    own=m.Employee.objects.get(organization=env['org'],user=user)
    assert own.pk!=foreign.pk
    m.Membership.objects.create(organization=env['other'],user=env['user'],role='owner')
    rows=env['client'].get('/api/v2/employees').data['results']
    assert str(own.pk) in [x['id'] for x in rows]
    assert str(foreign.pk) not in [x['id'] for x in rows]
    env['client'].credentials(HTTP_X_ORGANIZATION=str(env['other'].pk))
    rows=env['client'].get('/api/v2/employees').data['results']
    assert str(foreign.pk) in [x['id'] for x in rows]
    assert str(own.pk) not in [x['id'] for x in rows]


@pytest.mark.parametrize('conflict',['duplicate_email','duplicate_user','other_user'])
def test_reconciliation_leaves_ambiguous_records_untouched(env,conflict):
    user=account()
    m.Membership.objects.create(organization=env['org'],user=user,role='driver')
    m.Employee.objects.create(organization=env['org'],name='Premier',email=user.courriel,
        user=user if conflict=='duplicate_user' else env['user'] if conflict=='other_user' else None)
    if conflict!='other_user':
        m.Employee.objects.create(organization=env['org'],name='Deuxième',email=user.courriel.upper(),user=user if conflict=='duplicate_user' else None)
    before=list(m.Employee.objects.values('id','user_id','name','email','job'))
    with pytest.raises(ValidationError):sync_employee(env['org'],user,'driver')
    assert list(m.Employee.objects.values('id','user_id','name','email','job'))==before
    result=reconcile_personnel(organization_id=env['org'].pk,dry_run=False)
    assert result['conflicts']>=1
    assert m.Employee.objects.filter(organization=env['org'],email__iexact=user.courriel).count()==len([x for x in before if x['email'].lower()==user.courriel])


def test_external_access_is_not_reconciled_into_personnel(env):
    user=account('customer@example.test')
    m.PortalAccess.objects.create(organization=env['org'],user=user,partner=env['partner'])
    reconcile_personnel(organization_id=env['org'].pk,dry_run=False)
    assert not m.Employee.objects.filter(organization=env['org'],user=user).exists()
    m.Membership.objects.create(organization=env['org'],user=user,role='viewer')
    result=reconcile_personnel(organization_id=env['org'].pk,dry_run=False)
    assert result['external']==1
    assert not m.Employee.objects.filter(organization=env['org'],user=user).exists()


def test_command_defaults_to_audit_and_apply_is_idempotent(env):
    user=account()
    m.Membership.objects.create(organization=env['org'],user=user,role='driver',active=False)
    before=m.Employee.objects.count()
    output=StringIO()
    call_command('reconcile_personnel',organization=str(env['org'].pk),stdout=output)
    assert m.Employee.objects.count()==before
    assert 'created=2' in output.getvalue()
    call_command('reconcile_personnel',organization=str(env['org'].pk),apply=True,stdout=StringIO())
    assert m.Employee.objects.count()==before+2
    assert m.Employee.objects.get(organization=env['org'],user=user).active is False
    call_command('reconcile_personnel',organization=str(env['org'].pk),apply=True,stdout=StringIO())
    assert m.Employee.objects.count()==before+2

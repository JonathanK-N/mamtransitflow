"""Concurrence sur PostgreSQL réel. Auteur : Jonathan Kakesa (JonathanK-N)."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import timedelta
from decimal import Decimal
import pytest
from django.db import connection,connections,close_old_connections
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.comptes.models import Utilisateur
from apps.erp import models as m,services

pytestmark=pytest.mark.django_db(transaction=True)


def concurrent(call):
    gate=Barrier(2)
    def worker(index):
        close_old_connections()
        try:
            gate.wait(timeout=10)
            call(index)
            return 'accepted'
        except ValidationError:return 'rejected'
        finally:connections.close_all()
    with ThreadPoolExecutor(max_workers=2) as pool:return list(pool.map(worker,[0,1]))


def test_simultaneous_payments_do_not_overpay():
    if connection.vendor!='postgresql':pytest.skip('Verrouillage vérifié sur PostgreSQL uniquement')
    org=m.Organization.objects.create(name='Concurrence',slug='concurrence')
    user=Utilisateur.objects.create_user(courriel='race@example.test',mot_de_passe='Race-test-934!',nom='Finance')
    services.setup_accounts(org)
    customer=m.Partner.objects.create(organization=org,name='Client')
    invoice=m.Invoice.objects.create(organization=org,customer=customer,date='2026-09-26',due_date='2026-10-26',status='issued',total=100,number='FAC-RACE')
    results=concurrent(lambda n:services.payment(org,user,dict(invoice=invoice,amount=Decimal('75'),date='2026-09-26',reference=f'RACE-{n}')))
    assert sorted(results)==['accepted','rejected']
    invoice.refresh_from_db();assert invoice.paid==75
    assert m.Payment.objects.count()==1


def test_simultaneous_bookings_do_not_oversell():
    if connection.vendor!='postgresql':pytest.skip('Verrouillage vérifié sur PostgreSQL uniquement')
    org=m.Organization.objects.create(name='Voyageurs',slug='voyageurs')
    user=Utilisateur.objects.create_user(courriel='bus@example.test',mot_de_passe='Race-test-934!',nom='Guichet')
    vehicle=m.Vehicle.objects.create(organization=org,plate='BUS',name='Bus',seats=1)
    driver=m.Employee.objects.create(organization=org,name='Chauffeur')
    route=m.Route.objects.create(organization=org,name='Ligne',origin='A',destination='B',fare=500)
    trip=m.Mission.objects.create(organization=org,reference='M1',vehicle=vehicle,driver=driver,route=route,origin='A',destination='B',departure=timezone.now(),arrival=timezone.now()+timedelta(hours=1))
    results=concurrent(lambda n:services.booking(org,user,dict(mission=trip,passenger=f'Voyageur {n}',phone='600000000',seats=1)))
    assert sorted(results)==['accepted','rejected']
    assert m.Booking.objects.count()==1


def test_simultaneous_internal_invitations_do_not_duplicate_employee():
    if connection.vendor!='postgresql':pytest.skip('Verrouillage vérifié sur PostgreSQL uniquement')
    from apps.erp.security import grant_invitation
    org=m.Organization.objects.create(name='Personnel',slug='personnel-race')
    user=Utilisateur.objects.create_user(courriel='staff-race@example.test',mot_de_passe='Race-test-934!',nom='Chauffeur')
    invitations=[m.TeamInvitation.objects.create(organization=org,email=user.courriel,role='driver',
        digest=str(n)*64,expires_at=timezone.now()+timedelta(days=1)) for n in range(2)]
    results=concurrent(lambda n:grant_invitation(invitations[n],user))
    assert sorted(results)==['accepted','rejected']
    assert m.Membership.objects.filter(organization=org,user=user).count()==1
    assert m.Employee.objects.filter(organization=org,user=user).count()==1


def crm_environment():
    org=m.Organization.objects.create(name='TEST CRM concurrence',slug='crm-race')
    user=Utilisateur.objects.create_user(courriel='crm-race@example.test',mot_de_passe='Race-test-934!',nom='Direction')
    m.Membership.objects.create(organization=org,user=user,role='owner')
    customer=m.Partner.objects.create(organization=org,name='TEST Client concurrence')
    return org,user,customer


def test_simultaneous_quote_conversions_create_one_order():
    if connection.vendor!='postgresql':pytest.skip('Verrouillage vérifié sur PostgreSQL uniquement')
    from apps.erp.crm_services import quote_action
    org,user,customer=crm_environment()
    quote=m.Invoice.objects.create(organization=org,customer=customer,kind='quote',status='issued',quote_status='accepted',date=timezone.localdate(),due_date=timezone.localdate(),origin='A',destination='B',subtotal=100,total=100,lines=[dict(description='Transport',quantity='1',price='100',tax_rate='0')])
    assert concurrent(lambda n:quote_action(org,user,quote,'convert',{}))==['accepted','accepted']
    assert m.TransportOrder.objects.filter(source_quote=quote).count()==1


def test_simultaneous_server_references_are_unique():
    if connection.vendor!='postgresql':pytest.skip('Verrouillage vérifié sur PostgreSQL uniquement')
    org,user,customer=crm_environment()
    def create_order(n):
        from rest_framework.test import APIClient
        api=APIClient();api.force_authenticate(user);api.credentials(HTTP_X_ORGANIZATION=str(org.pk))
        response=api.post('/api/v2/orders',dict(customer=str(customer.pk),origin='A',destination='B',planned_date=str(timezone.localdate())),format='json')
        assert response.status_code==201,response.data
    assert concurrent(create_order)==['accepted','accepted']
    assert m.TransportOrder.objects.values('reference').distinct().count()==2


def test_simultaneous_planning_cannot_book_same_resources():
    if connection.vendor!='postgresql':pytest.skip('Verrouillage vérifié sur PostgreSQL uniquement')
    org,user,customer=crm_environment()
    vehicle=m.Vehicle.objects.create(organization=org,name='Camion',plate='CRM-RACE')
    driver=m.Employee.objects.create(organization=org,name='Chauffeur')
    now=timezone.now()+timedelta(days=1)
    def plan(n):
        from rest_framework.test import APIClient
        api=APIClient();api.force_authenticate(user);api.credentials(HTTP_X_ORGANIZATION=str(org.pk))
        response=api.post('/api/v2/missions',dict(vehicle=str(vehicle.pk),driver=str(driver.pk),origin='A',destination='B',departure=str(now),arrival=str(now+timedelta(hours=1))),format='json')
        if response.status_code==400:raise ValidationError('Conflit attendu')
        assert response.status_code==201,response.data
    assert sorted(concurrent(plan))==['accepted','rejected']
    assert m.Mission.objects.count()==1


def test_simultaneous_portal_invitations_create_one_pending(monkeypatch):
    if connection.vendor!='postgresql':pytest.skip('Verrouillage vérifié sur PostgreSQL uniquement')
    org,user,customer=crm_environment()
    monkeypatch.setattr('apps.erp.invitation_email.send_invitation',lambda *args:False)
    def invite(n):
        from rest_framework.test import APIClient
        api=APIClient();api.force_authenticate(user);api.credentials(HTTP_X_ORGANIZATION=str(org.pk))
        response=api.post('/api/v2/portal-access',dict(mode='existing',partner=str(customer.pk),email='portal-race@example.test'),format='json')
        if response.status_code==409:raise ValidationError('Invitation déjà en attente')
        assert response.status_code==201,response.data
    assert sorted(concurrent(invite))==['accepted','rejected']
    assert m.TeamInvitation.objects.count()==1

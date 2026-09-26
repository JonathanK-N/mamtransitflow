"""Concurrence sur PostgreSQL réel. Auteur : Jonathan Kakesa (JonathanK-N)."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import timedelta
from decimal import Decimal
import pytest
from django.db import connection,close_old_connections
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
        finally:close_old_connections()
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

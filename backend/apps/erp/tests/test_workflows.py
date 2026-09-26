"""Recette API multi-entreprises. Auteur : Jonathan Kakesa (JonathanK-N)."""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from apps.comptes.models import Utilisateur
from apps.erp import models as m, services
from apps.erp.serializers import RESOURCES

pytestmark = pytest.mark.django_db


@pytest.fixture
def env():
    user = Utilisateur.objects.create_user(courriel='direction@example.test', mot_de_passe='Long-password-938!', nom='Direction')
    org = m.Organization.objects.create(name='Transport Guinée', slug='guinee', activities=['freight','passengers'])
    other = m.Organization.objects.create(name='Transport Cameroun', slug='cameroun', country='CM', currency='XAF')
    membership = m.Membership.objects.create(organization=org, user=user, role='owner')
    services.setup_accounts(org)
    client = APIClient(); client.force_authenticate(user)
    client.credentials(HTTP_X_ORGANIZATION=str(org.pk))
    partner = m.Partner.objects.create(organization=org, name='Client Conakry')
    vehicle = m.Vehicle.objects.create(organization=org, plate='RC-001', name='Camion', seats=3)
    driver = m.Employee.objects.create(organization=org, name='Chauffeur')
    return dict(client=client,user=user,org=org,other=other,member=membership,partner=partner,vehicle=vehicle,driver=driver)


def create(env, resource, data):
    response=env['client'].post('/api/v2/'+resource,data,format='json')
    assert response.status_code==201, response.data
    return response.data


def act(env, resource, pk, action, data=None, expected=200):
    response=env['client'].post(f'/api/v2/{resource}/{pk}/actions/{action}',data or {},format='json')
    assert response.status_code==expected,response.data
    return response.data


def mission(env, **extra):
    now=timezone.now()+timedelta(hours=1)
    return create(env,'missions',dict(reference='M-001',vehicle=str(env['vehicle'].pk),driver=str(env['driver'].pk),
        origin='Conakry',destination='Kindia',departure=now.isoformat(),arrival=(now+timedelta(hours=4)).isoformat(),**extra))


def invoice(env, **extra):
    return create(env,'invoices',dict(customer=str(env['partner'].pk),date='2026-09-26',due_date='2026-10-26',
        lines=[dict(description='Transport',quantity='2',price='100',tax_rate='18')],**extra))


@pytest.mark.parametrize('resource',list(RESOURCES))
def test_every_module_requires_membership(env,resource):
    env['client'].credentials(HTTP_X_ORGANIZATION=str(env['other'].pk))
    assert env['client'].get('/api/v2/'+resource).status_code==403


def test_foreign_detail_update_delete_export_and_relation(env):
    foreign=m.Partner.objects.create(organization=env['other'],name='Confidentiel Cameroun')
    client=env['client'];url=f'/api/v2/partners/{foreign.pk}'
    assert client.get(url).status_code==404
    assert client.patch(url,{'name':'Pirate'},format='json').status_code==404
    assert client.delete(url).status_code==404
    assert b'Confidentiel' not in client.get('/api/v2/partners/export').content
    response=client.post('/api/v2/invoices',dict(customer=str(foreign.pk),date='2026-09-26',due_date='2026-10-26',lines=[]),format='json')
    assert response.status_code==400
    assert not m.Invoice.objects.exists()


def test_freight_delivery_and_immutable_finance(env):
    order=create(env,'orders',dict(reference='CMD-001',customer=str(env['partner'].pk),origin='Conakry',destination='Kindia',planned_date='2026-09-26',amount='200'))
    act(env,'orders',order['id'],'confirm')
    trip=mission(env,order=order['id'])
    act(env,'missions',trip['id'],'start')
    act(env,'missions',trip['id'],'complete',dict(loaded_quantity='100',delivered_quantity='101'),400)
    act(env,'missions',trip['id'],'complete',dict(loaded_quantity='100',delivered_quantity='98',delivery_note='Deux colis refusés'))
    assert m.TransportOrder.objects.get(pk=order['id']).status=='completed'
    bill=invoice(env,order=order['id'])
    issued=act(env,'invoices',bill['id'],'issue')
    assert Decimal(issued['total'])==Decimal('236')
    assert issued['number'].startswith('FAC-')
    assert env['client'].patch('/api/v2/invoices/'+bill['id'],{'notes':'Modification'},format='json').status_code==400
    create(env,'payments',dict(invoice=bill['id'],amount='100',date='2026-09-26',reference='BANK-1'))
    response=env['client'].post('/api/v2/payments',dict(invoice=bill['id'],amount='137',date='2026-09-26',reference='BANK-2'),format='json')
    assert response.status_code==400
    create(env,'payments',dict(invoice=bill['id'],amount='136',date='2026-09-26',reference='BANK-2'))
    assert m.Invoice.objects.get(pk=bill['id']).status=='paid'
    report=env['client'].get('/api/v2/reports').data
    assert sum(Decimal(x['debit']) for x in report['trial_balance'])==sum(Decimal(x['credit']) for x in report['trial_balance'])


def test_passenger_capacity_cancel_releases_seat(env):
    route=create(env,'routes',dict(name='Conakry-Kindia',origin='Conakry',destination='Kindia',fare='25000'))
    trip=mission(env,route=route['id'])
    booking=create(env,'bookings',dict(mission=trip['id'],passenger='Famille Diallo',phone='600000000',seats=3))
    assert Decimal(booking['amount'])==75000
    response=env['client'].post('/api/v2/bookings',dict(mission=trip['id'],passenger='Autre',phone='600000001',seats=1),format='json')
    assert response.status_code==400
    act(env,'missions',trip['id'],'cancel',expected=400)
    act(env,'bookings',booking['id'],'cancel')
    create(env,'bookings',dict(mission=trip['id'],passenger='Nouveau',phone='600000001',seats=1))


def test_stock_purchase_reception_once_and_no_negative(env):
    item=create(env,'stock',dict(code='PNEU',name='Pneu',minimum='2'))
    purchase=create(env,'purchases',dict(reference='ACH-1',supplier=str(env['partner'].pk),date='2026-09-26',lines=[dict(item=item['id'],quantity='4',price='120')]))
    act(env,'purchases',purchase['id'],'order')
    act(env,'purchases',purchase['id'],'receive')
    act(env,'purchases',purchase['id'],'receive',expected=400)
    assert m.StockItem.objects.get(pk=item['id']).quantity==4
    response=env['client'].post('/api/v2/movements',dict(item=item['id'],quantity='-5',reference='SORTIE-1',reason='Atelier'),format='json')
    assert response.status_code==400
    assert m.StockItem.objects.get(pk=item['id']).quantity==4
    create(env,'movements',dict(item=item['id'],quantity='-2',reference='SORTIE-1',reason='Atelier'))
    assert m.StockItem.objects.get(pk=item['id']).quantity==2


def test_vehicle_workshop_and_dispatch_conflict(env):
    trip=mission(env)
    work=create(env,'maintenance',dict(vehicle=str(env['vehicle'].pk),title='Vidange'))
    act(env,'maintenance',work['id'],'start')
    act(env,'missions',trip['id'],'start',expected=400)
    act(env,'maintenance',work['id'],'complete')
    act(env,'missions',trip['id'],'start')
    work2=create(env,'maintenance',dict(vehicle=str(env['vehicle'].pk),title='Freins'))
    act(env,'maintenance',work2['id'],'start',expected=400)


@pytest.mark.parametrize('role,allowed,denied',[('operations','missions','invoices'),('finance','invoices','stock'),('workshop','maintenance','invoices'),('driver','missions','partners')])
def test_role_permissions(env,role,allowed,denied):
    env['member'].role=role;env['member'].save()
    assert env['client'].get('/api/v2/'+allowed).status_code==200
    assert env['client'].get('/api/v2/'+denied).status_code==403
    assert env['client'].get('/api/v2/audit').status_code==403


def test_viewer_cannot_write_or_promote_self(env):
    env['member'].role='viewer';env['member'].save()
    assert env['client'].post('/api/v2/partners',{'name':'Forbidden'},format='json').status_code==403
    assert env['client'].patch('/api/v2/team',{'id':env['member'].pk,'role':'owner'},format='json').status_code==403


def test_csv_formula_escaped(env):
    m.Partner.objects.create(organization=env['org'],name='=HYPERLINK("bad")')
    data=env['client'].get('/api/v2/partners/export').content.decode('utf-8-sig')
    assert "'=HYPERLINK" in data


def test_disabled_membership_immediately_revoked(env):
    env['member'].active=False;env['member'].save()
    assert env['client'].get('/api/v2/dashboard').status_code==403

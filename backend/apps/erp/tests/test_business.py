"""Recette commerciale et fournisseurs. Auteur : Jonathan Kakesa (JonathanK-N)."""
from decimal import Decimal
from django.utils import timezone
import pytest
from apps.erp import models as m
from .test_workflows import env,create,act,mission

pytestmark=pytest.mark.django_db


def test_recurring_contract_keeps_month_anchor_and_generates_once(env):
    contract=create(env,'contracts',dict(reference='CON-001',customer=str(env['partner'].pk),origin='Conakry',destination='Kindia',amount='100',start_date='2026-01-31',end_date='2026-03-31',recurrence='monthly'))
    act(env,'contracts',contract['id'],'activate')
    first=act(env,'contracts',contract['id'],'generate')
    assert first['next_date']=='2026-02-28'
    second=act(env,'contracts',contract['id'],'generate')
    assert second['next_date']=='2026-03-31'
    final=act(env,'contracts',contract['id'],'generate')
    assert final['status']=='closed'
    act(env,'contracts',contract['id'],'generate',expected=400)
    assert m.TransportOrder.objects.count()==3


def test_tariff_matches_units_route_and_validity(env):
    rule=create(env,'pricing',dict(name='Tarif Conakry Kindia',origin='Conakry',destination='Kindia',unit='t',unit_price='50',minimum='80',valid_from='2026-01-01',valid_until='2026-12-31'))
    order=create(env,'orders',dict(reference='CMD-TARIF',customer=str(env['partner'].pk),origin='Conakry',destination='Kindia',planned_date='2026-09-26',quantity='3',unit='t'))
    result=act(env,'orders',order['id'],'price',{'pricing_rule':rule['id']})
    assert Decimal(result['amount'])==150
    assert env['client'].patch('/api/v2/orders/'+order['id'],{'destination':'Mamou'},format='json').status_code==200
    act(env,'orders',order['id'],'price',{'pricing_rule':rule['id']},expected=400)


def test_incident_requires_resolution_and_matching_vehicle(env):
    trip=mission(env)
    incident=create(env,'incidents',dict(reference='INC-001',title='Panne moteur',vehicle=str(env['vehicle'].pk),mission=trip['id'],occurred_at=timezone.now().isoformat(),description='Arrêt moteur sur la route.'))
    act(env,'incidents',incident['id'],'report')
    act(env,'incidents',incident['id'],'resolve',expected=400)
    closed=act(env,'incidents',incident['id'],'resolve',{'resolution':'Réparation et contrôle de sécurité effectués.'})
    assert closed['status']=='resolved' and closed['resolved_at']


def test_subcontract_supplier_bill_and_payment(env):
    trip=mission(env)
    subcontract=create(env,'subcontracts',dict(reference='ST-001',mission=trip['id'],supplier=str(env['partner'].pk),agreed_amount='300',due_date='2026-10-26'))
    act(env,'subcontracts',subcontract['id'],'approve')
    act(env,'subcontracts',subcontract['id'],'complete',{'completion_note':'Prestation réalisée, bon reçu.'})
    bill=create(env,'supplier-bills',dict(reference='FOU-001',supplier=str(env['partner'].pk),subcontract=subcontract['id'],date='2026-09-26',due_date='2026-10-26',lines=[{'description':'Transport sous-traité','quantity':1,'price':'300','tax_rate':0}]))
    act(env,'supplier-bills',bill['id'],'post')
    payment=create(env,'supplier-payments',dict(bill=bill['id'],reference='VIR-001',date='2026-09-26',amount='300'))
    assert m.SupplierBill.objects.get(pk=bill['id']).status=='paid'
    assert env['client'].patch('/api/v2/supplier-payments/'+payment['id'],{'amount':1},format='json').status_code==400
    report=env['client'].get('/api/v2/reports').data['trial_balance']
    assert sum(Decimal(x['debit']) for x in report)==sum(Decimal(x['credit']) for x in report)


def test_received_purchase_is_not_expensed_twice(env):
    item=create(env,'stock',dict(code='FILTRE',name='Filtre'))
    purchase=create(env,'purchases',dict(reference='ACH-FILTRE',supplier=str(env['partner'].pk),date='2026-09-26',lines=[{'item':item['id'],'quantity':2,'price':50}]))
    act(env,'purchases',purchase['id'],'order');act(env,'purchases',purchase['id'],'receive')
    bill=create(env,'supplier-bills',dict(reference='FOU-FILTRE',supplier=str(env['partner'].pk),purchase=purchase['id'],date='2026-09-26',due_date='2026-10-26',lines=[{'description':'Filtres','quantity':2,'price':50,'tax_rate':0}]))
    act(env,'supplier-bills',bill['id'],'post')
    balance=env['client'].get('/api/v2/reports').data['trial_balance']
    assert next(x for x in balance if x['code']=='601')['debit']==100
    duplicate=env['client'].post('/api/v2/supplier-bills',dict(reference='FOU-FILTRE-2',supplier=str(env['partner'].pk),purchase=purchase['id'],date='2026-09-26',due_date='2026-10-26',lines=[{'description':'Filtres','quantity':2,'price':50,'tax_rate':0}]),format='json')
    assert duplicate.status_code==400

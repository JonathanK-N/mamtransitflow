from datetime import date
from decimal import Decimal
import csv
import io

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.erp import models as m
from .test_workflows import env

pytestmark=pytest.mark.django_db


def order(env,reference,**fields):
    return m.TransportOrder.objects.create(organization=env['org'],customer=env['partner'],reference=reference,origin='A',destination='B',planned_date=date(2026,10,5),amount=Decimal('100.01'),**fields)


@pytest.mark.parametrize('role,expected,visible',[('owner',200,True),('admin',200,True),('viewer',200,True),('finance',200,False),('operations',403,False),('workshop',403,False),('driver',403,False),('client',403,False)])
def test_reports_never_bypass_resource_permissions(env,role,expected,visible):
    order(env,'PRIVATE-ORDER')
    env['member'].role=role;env['member'].save()
    response=env['client'].get('/api/v2/reports')
    assert response.status_code==expected
    if expected==200:
        assert response.data['profitability_available'] is visible
        assert bool(response.data['profitability']) is visible
        if not visible:assert 'PRIVATE-ORDER' not in str(response.data)


@pytest.mark.parametrize('query',['start=bad','end=2026-99-01','start=2026-10-06&end=2026-10-05','start=2020-01-01&end=2026-10-05'])
def test_reports_reject_invalid_periods(env,query):
    assert env['client'].get('/api/v2/reports?'+query).status_code==400


def test_reports_paginate_and_filter_without_cross_tenant_data(env,record_property):
    m.TransportOrder.objects.bulk_create([m.TransportOrder(organization=env['org'],customer=env['partner'],reference=f'ORDER-{n:04}',origin='A',destination='B',planned_date=date(2026,10,5),amount=Decimal('100.01'),status='confirmed') for n in range(1000)])
    foreign=m.Partner.objects.create(organization=env['other'],name='FOREIGN-SECRET')
    m.TransportOrder.objects.create(organization=env['other'],customer=foreign,reference='FOREIGN-ORDER',origin='A',destination='B',planned_date=date(2026,10,5),amount=999)
    with CaptureQueriesContext(connection) as captured:
        response=env['client'].get('/api/v2/reports?start=2026-10-05&end=2026-10-05&status=confirmed&page=2')
    assert response.status_code==200,response.data
    assert response.data['profitability_count']==1000
    assert response.data['profitability_page']==2
    assert len(response.data['profitability'])==25
    assert response.data['profitability'][0]['reference']=='ORDER-0025'
    assert response.data['profitability'][0]['margin']=='100.01'
    assert 'FOREIGN' not in str(response.data)
    assert len(captured)<=25
    record_property('reports_1000_orders_queries',len(captured))
    assert env['client'].get('/api/v2/reports?customer='+str(foreign.pk)).data['profitability']==[]
    assert env['client'].get('/api/v2/reports?start=2026-10-06&end=2026-10-06').data['profitability_count']==0


def test_csv_preserves_zero_and_false(env):
    m.StockItem.objects.create(organization=env['org'],code='ZERO',name='Zero',quantity=0,minimum=0,unit_cost=0)
    response=env['client'].get('/api/v2/stock/export')
    assert response.status_code==200
    rows=list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig')),delimiter=';'))
    row=next(row for row in rows if row['code']=='ZERO')
    assert Decimal(row['quantity'])==0
    assert Decimal(row['unit_cost'])==0

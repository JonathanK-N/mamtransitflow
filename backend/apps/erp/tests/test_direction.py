from datetime import datetime, date, timedelta, timezone as dt_timezone
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.erp import models as m
from .test_workflows import env

pytestmark=pytest.mark.django_db


def invoice(env, number, **fields):
    return m.Invoice.objects.create(organization=env['org'],customer=env['partner'],number=number,
        date=fields.pop('date',date(2026,10,5)),due_date=date(2026,10,6),**fields)


def test_direction_decimal_comparison_excludes_drafts_quotes_cancelled_and_foreign(env):
    invoice(env,'FAC-1',kind='invoice',status='issued',subtotal=Decimal('100.10'),total=Decimal('118.12'),paid=Decimal('20.00'))
    invoice(env,'AVO-1',kind='credit',status='issued',subtotal=Decimal('10.05'),total=Decimal('11.86'))
    invoice(env,'FAC-PREV',date=date(2026,10,4),kind='invoice',status='paid',subtotal=Decimal('30.00'),total=Decimal('30.00'),paid=Decimal('30.00'))
    for index,(kind,status) in enumerate([('quote','issued'),('invoice','draft'),('invoice','cancelled')]):
        invoice(env,f'EXCLUDED-{index}',kind=kind,status=status,subtotal=999,total=999)
    foreign=m.Partner.objects.create(organization=env['other'],name='Foreign')
    m.Invoice.objects.create(organization=env['other'],customer=foreign,number='SECRET',date=date(2026,10,5),due_date=date(2026,10,6),status='issued',subtotal=999,total=999)
    result=env['client'].get('/api/v2/dashboard?start=2026-10-05&end=2026-10-05')
    assert result.status_code==200,result.data
    data=result.data['direction']
    assert data['current']['revenue_ht']=='90.05'
    assert data['previous']['revenue_ht']=='30.00'
    assert data['changes']['revenue_ht']=='60.05'
    assert data['previous_start']=='2026-10-04'
    assert data['receivable_now']=='98.12'


@pytest.mark.parametrize('role,visible',[('owner',True),('admin',True),('finance',True),('viewer',True),('operations',False),('workshop',False),('driver',False)])
def test_direction_role_matrix(env,role,visible):
    env['member'].role=role;env['member'].save()
    result=env['client'].get('/api/v2/dashboard')
    assert result.status_code==200
    assert bool(result.data['direction']) is visible
    if not visible:assert result.data['receivable'] is None


@pytest.mark.parametrize('parameters',['start=bad&end=2026-10-05','start=2026-10-06&end=2026-10-05','start=2020-01-01&end=2026-10-05'])
def test_direction_rejects_invalid_periods(env,parameters):
    assert env['client'].get('/api/v2/dashboard?'+parameters).status_code==400


def test_direction_mission_period_respects_dst_and_company_timezone(env):
    env['org'].timezone='America/Toronto';env['org'].save()
    for index,completed in enumerate([datetime(2026,11,1,4,30,tzinfo=dt_timezone.utc),datetime(2026,11,2,4,30,tzinfo=dt_timezone.utc),datetime(2026,11,2,5,30,tzinfo=dt_timezone.utc)]):
        m.Mission.objects.create(organization=env['org'],reference=f'DST-{index}',vehicle=env['vehicle'],driver=env['driver'],origin='A',destination='B',departure=completed-timedelta(hours=1),arrival=completed,status='completed',completed_at=completed)
    result=env['client'].get('/api/v2/dashboard?start=2026-11-01&end=2026-11-01')
    assert result.status_code==200,result.data
    assert result.data['direction']['current']['completed_missions']==2


def test_direction_queries_remain_bounded_at_5000_invoices(env,record_property):
    def query():
        with CaptureQueriesContext(connection) as captured:
            response=env['client'].get('/api/v2/dashboard?start=2026-10-05&end=2026-10-05')
        assert response.status_code==200,response.data
        return response,len(captured)
    _,before=query()
    m.Invoice.objects.bulk_create([m.Invoice(organization=env['org'],customer=env['partner'],number=f'VOLUME-{n}',date=date(2026,10,5),due_date=date(2026,10,6),kind='invoice',status='issued',subtotal=Decimal('100.01'),total=Decimal('100.01')) for n in range(5000)])
    result,after=query()
    assert result.data['direction']['current']['revenue_ht']=='500050.00'
    assert after==before and after<=40
    record_property('invoice_volume',5000)
    record_property('dashboard_sql_queries',after)


def test_direction_commercial_margin_and_receipts_use_actual_validated_costs(env):
    day=date(2026,10,5)
    bill=invoice(env,'FAC-COSTS',kind='invoice',status='issued',total=100,subtotal=100)
    m.Payment.objects.create(organization=env['org'],invoice=bill,amount=Decimal('25.03'),date=day,reference='PAY-TEST')
    order=m.TransportOrder.objects.create(organization=env['org'],customer=env['partner'],reference='CMD-COST',origin='A',destination='B',planned_date=day,amount=Decimal('100.01'),status='confirmed')
    departure=datetime(2026,10,5,10,tzinfo=dt_timezone.utc)
    trip=m.Mission.objects.create(organization=env['org'],order=order,reference='MIS-COST',vehicle=env['vehicle'],driver=env['driver'],origin='A',destination='B',departure=departure,arrival=departure+timedelta(hours=1),status='completed',completed_at=departure+timedelta(hours=1))
    m.Expense.objects.create(organization=env['org'],mission=trip,title='Coût validé',date=day,amount=Decimal('10.02'),status='approved')
    m.Expense.objects.create(organization=env['org'],mission=trip,title='Brouillon exclu',date=day,amount=99,status='draft')
    supplier=m.Partner.objects.create(organization=env['org'],name='Prestataire',kind='supplier')
    m.Subcontract.objects.create(organization=env['org'],mission=trip,supplier=supplier,reference='SUB-TEST',due_date=day,agreed_amount=Decimal('5.03'),status='completed')
    result=env['client'].get('/api/v2/dashboard?start=2026-10-05&end=2026-10-05')
    assert result.status_code==200,result.data
    current=result.data['direction']['current']
    assert current['receipts']=='25.03'
    assert current['approved_expenses']=='10.02'
    assert current['commercial_margin']=='84.96'
    assert current['completed_missions']==1


def test_currency_change_does_not_relabel_existing_money(env):
    response=env['client'].patch('/api/v2/organization',{'currency':'USD'},format='json')
    assert response.status_code==200,response.data
    env['org'].refresh_from_db()
    invoice(env,'FAC-CURRENCY',kind='invoice',status='issued',subtotal=100,total=100)
    response=env['client'].patch('/api/v2/organization',{'currency':'EUR'},format='json')
    assert response.status_code==400
    env['org'].refresh_from_db()
    assert env['org'].currency=='USD'
    assert env['client'].patch('/api/v2/organization',{'name':'Updated company','currency':'USD'},format='json').status_code==200


def test_invoice_overdue_days_use_company_day(env,monkeypatch):
    from django.utils import timezone
    env['org'].timezone='America/Toronto';env['org'].save()
    monkeypatch.setattr(timezone,'now',lambda:datetime(2026,10,6,1,30,tzinfo=dt_timezone.utc))
    item=invoice(env,'FAC-TZ',kind='invoice',status='issued',subtotal=100,total=100)
    item.due_date=date(2026,10,5);item.save()
    response=env['client'].get('/api/v2/invoices/'+str(item.pk))
    assert response.status_code==200,response.data
    assert response.data['overdue_days']==0


@pytest.mark.parametrize('parameters',['start=0001-01-01&end=0001-01-01','start=9999-12-31&end=9999-12-31'])
def test_direction_date_boundaries_return_validation_error(env,parameters):
    assert env['client'].get('/api/v2/dashboard?'+parameters).status_code==400


def test_document_number_year_uses_company_timezone(env,monkeypatch):
    from django.utils import timezone
    from django.db import transaction
    from apps.erp.services import sequence
    env['org'].timezone='America/Toronto';env['org'].save()
    monkeypatch.setattr(timezone,'now',lambda:datetime(2027,1,1,1,30,tzinfo=dt_timezone.utc))
    with transaction.atomic():
        assert sequence(env['org'],'FAC')=='FAC-2026-00001'
    env['org'].timezone='Asia/Tokyo';env['org'].save()
    with transaction.atomic():
        assert sequence(env['org'],'FAC')=='FAC-2027-00001'

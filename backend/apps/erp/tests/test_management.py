"""Recette personnel et trésorerie. Auteur : Jonathan Kakesa (JonathanK-N)."""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.utils import timezone
from apps.erp import models as m
from .test_workflows import env, create, act, mission, invoice

pytestmark=pytest.mark.django_db


def test_finance_can_select_staff_without_editing_employee_profiles(env):
    env['member'].role='finance';env['member'].save()
    assert env['client'].get('/api/v2/employees').status_code==200
    assert env['client'].patch('/api/v2/employees/'+str(env['driver'].pk),{'name':'Modification interdite'},format='json').status_code==403
    catalog=env['client'].get('/api/v2/catalog').data['resources']
    assert not next(x for x in catalog if x['key']=='employees')['writable']
    assert 'close' not in next(x for x in catalog if x['key']=='periods')['actions']['draft']


def test_leave_blocks_assignment_and_overlapping_requests(env):
    day=timezone.localdate()
    payload=dict(employee=str(env['driver'].pk),start_date=str(day),end_date=str(day+timedelta(days=2)))
    leave=create(env,'leave',payload)
    act(env,'leave',leave['id'],'submit');act(env,'leave',leave['id'],'approve')
    now=timezone.now()+timedelta(hours=1)
    response=env['client'].post('/api/v2/missions',dict(reference='ABSENT',driver=str(env['driver'].pk),vehicle=str(env['vehicle'].pk),origin='A',destination='B',departure=now.isoformat(),arrival=(now+timedelta(hours=4)).isoformat()),format='json')
    assert response.status_code==400
    second=create(env,'leave',payload)
    act(env,'leave',second['id'],'submit');act(env,'leave',second['id'],'approve',expected=400)
    env['member'].role='viewer';env['member'].save()
    assert env['client'].get('/api/v2/leave').status_code==403
    assert env['client'].get('/api/v2/leave/export').status_code==403


def test_leave_cannot_interrupt_existing_mission(env):
    trip=mission(env)
    day=timezone.localdate()
    leave=create(env,'leave',dict(employee=str(env['driver'].pk),start_date=str(day),end_date=str(day+timedelta(days=2))))
    act(env,'leave',leave['id'],'submit');act(env,'leave',leave['id'],'approve',expected=400)
    assert m.Mission.objects.get(pk=trip['id']).status=='planned'


def test_advance_records_actual_movements_once(env):
    day=str(timezone.localdate())
    advance=create(env,'advances',dict(reference='AV-001',employee=str(env['driver'].pk),date=day,amount='100',reason='Avance demandée'))
    act(env,'advances',advance['id'],'approve')
    act(env,'advances',advance['id'],'disburse',expected=400)
    paid=act(env,'advances',advance['id'],'disburse',dict(date=day,reference='Pièce 001'))
    assert paid['status']=='disbursed'
    act(env,'advances',advance['id'],'disburse',dict(date=day,reference='Doublon'),expected=400)
    act(env,'advances',advance['id'],'settle',dict(date=day,reference='Reçu 002'))
    entries=list(m.JournalEntry.objects.filter(reference__startswith='AV-'))
    assert len(entries)==2
    balance=sum(Decimal(line['debit'])-Decimal(line['credit']) for entry in entries for line in entry.lines if line['account']=='425')
    assert balance==0


def test_closing_locks_manual_and_automatic_posting_atomically(env):
    period=create(env,'periods',dict(name='Exercice antérieur',start_date='2020-01-01',end_date='2020-12-31'))
    act(env,'periods',period['id'],'close',dict(closing_note='Soldes contrôlés'))
    expense=create(env,'expenses',dict(title='Tentative antidatée',amount='20',date='2020-06-01'))
    act(env,'expenses',expense['id'],'approve',expected=400)
    assert m.Expense.objects.get(pk=expense['id']).status=='draft'
    assert not m.JournalEntry.objects.exists()
    entry=create(env,'journal',dict(reference='J-2020',date='2020-06-01',description='Antidatée',lines=[{'account':'601','debit':20},{'account':'521','credit':20}]))
    act(env,'journal',entry['id'],'post',expected=400)
    assert env['client'].patch('/api/v2/periods/'+period['id'],{'end_date':'2019-01-01'},format='json').status_code==400


def test_closing_requires_draft_resolution_and_admin(env):
    period=create(env,'periods',dict(name='Ancienne période',start_date='2020-01-01',end_date='2020-12-31'))
    expense=create(env,'expenses',dict(title='Brouillon',amount='20',date='2020-06-01'))
    act(env,'periods',period['id'],'close',dict(closing_note='Trop tôt'),expected=400)
    act(env,'expenses',expense['id'],'approve')
    env['member'].role='finance';env['member'].save()
    act(env,'periods',period['id'],'close',dict(closing_note='Non autorisé'),expected=403)
    env['member'].role='owner';env['member'].save()
    act(env,'periods',period['id'],'close',dict(closing_note='Terminé'))


def test_reconciliation_amount_uniqueness_and_audited_correction(env):
    entry=create(env,'journal',dict(reference='BANQUE',date='2020-06-01',description='Encaissement',lines=[{'account':'521','debit':100},{'account':'411','credit':100}]))
    act(env,'journal',entry['id'],'post')
    bank=m.Account.objects.get(organization=env['org'],code='521')
    payload=dict(reference='RELEVE-1',account=str(bank.pk),date='2020-06-02',description='Virement',amount='100')
    line=create(env,'statements',payload)
    act(env,'statements',line['id'],'match',dict(journal=entry['id'],note='Montant confirmé'))
    second=create(env,'statements',dict(payload,reference='RELEVE-2'))
    act(env,'statements',second['id'],'match',dict(journal=entry['id'],note='Doublon'),expected=400)
    assert m.BankStatementLine.objects.get(pk=second['id']).status=='draft'
    act(env,'statements',line['id'],'unmatch',dict(note='Mauvaise référence de relevé'))
    assert m.AuditEvent.objects.filter(action='previous-match').exists()
    act(env,'statements',second['id'],'match',dict(journal=entry['id'],note='Bonne référence'))
    wrong=create(env,'statements',dict(payload,reference='RELEVE-3',amount='-100'))
    act(env,'statements',wrong['id'],'match',dict(journal=entry['id'],note='Mauvais sens'),expected=400)

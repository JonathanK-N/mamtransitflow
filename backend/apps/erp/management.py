"""Personnel et contrôle comptable. Auteur : Jonathan Kakesa (JonathanK-N)."""
from datetime import date
from zoneinfo import ZoneInfo
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from . import models as m, services

MODELS = (m.LeaveRequest, m.EmployeeAdvance, m.FiscalPeriod, m.BankStatementLine)


def ensure_open_date(org, value):
    if m.FiscalPeriod.objects.filter(organization=org, status='closed', start_date__lte=value, end_date__gte=value).exists():
        raise ValidationError('Cette date appartient à une période clôturée. Utilisez une période ouverte pour la correction.')


def local_dates(org, start, end):
    zone = ZoneInfo(org.timezone)
    return timezone.localtime(start, zone).date(), timezone.localtime(end, zone).date()


def ensure_driver_available(org, driver, start, end):
    first, last = local_dates(org, start, end)
    if m.LeaveRequest.objects.filter(organization=org, employee=driver, status='approved', start_date__lte=last, end_date__gte=first).exists():
        raise ValidationError('Le chauffeur est en congé sur cette période.')


def validate(model, obj, data):
    if model in (m.LeaveRequest, m.FiscalPeriod):
        if obj.end_date < obj.start_date:
            raise ValidationError('La fin ne peut pas précéder le début.')
    if model is m.FiscalPeriod:
        if m.FiscalPeriod.objects.filter(organization=obj.organization, start_date__lte=obj.end_date, end_date__gte=obj.start_date).exclude(pk=obj.pk).exists():
            raise ValidationError('Cette période chevauche une période existante.')
    if model is m.EmployeeAdvance and (obj.amount <= 0 or not obj.employee.active):
        raise ValidationError('Une avance positive et un salarié actif sont requis.')
    if model is m.BankStatementLine:
        if not obj.amount or not obj.account.code.startswith('5'):
            raise ValidationError('Choisissez un compte de trésorerie et un montant non nul.')
        ensure_open_date(obj.organization, obj.date)
    if model is m.Mission:
        ensure_driver_available(obj.organization, obj.driver, obj.departure, obj.arrival)
    return data


def required_text(data, key, limit=10000):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise ValidationError('Un justificatif ou un motif valide est requis.')
    return value.strip()


def movement_date(data):
    try:
        value = date.fromisoformat(data.get('date', ''))
    except (TypeError, ValueError):
        raise ValidationError('La date réelle du mouvement est requise.')
    if value > timezone.localdate():
        raise ValidationError('Un mouvement réalisé ne peut pas être daté dans le futur.')
    return value


def transition(org, actor, obj, action, data):
    old = obj.status
    if isinstance(obj, m.LeaveRequest):
        if action == 'submit' and old == 'draft':
            if not obj.employee.active:
                raise ValidationError('Le salarié est inactif.')
            obj.status = 'submitted'
        elif action == 'approve' and old == 'submitted':
            if not obj.employee.active:
                raise ValidationError('Le salarié est inactif.')
            overlaps = m.LeaveRequest.objects.filter(organization=org, employee=obj.employee, status='approved', start_date__lte=obj.end_date, end_date__gte=obj.start_date).exclude(pk=obj.pk)
            if overlaps.exists():
                raise ValidationError('Un congé approuvé couvre déjà ces dates.')
            for trip in m.Mission.objects.filter(organization=org, driver=obj.employee, status__in=['planned', 'active']):
                start, end = local_dates(org, trip.departure, trip.arrival)
                if start <= obj.end_date and end >= obj.start_date:
                    raise ValidationError('Réaffectez les missions du chauffeur avant de valider ce congé.')
            obj.status = 'approved'
        elif action == 'reject' and old == 'submitted':
            obj.decision_note = required_text(data, 'decision_note')
            obj.status = 'rejected'
        elif action == 'cancel' and old in ('draft', 'submitted', 'approved'):
            if old == 'approved' and obj.start_date <= timezone.localdate():
                raise ValidationError('Un congé commencé reste dans l’historique.')
            obj.status = 'cancelled'
        else:
            raise ValidationError('Action impossible pour cette demande de congé.')
    elif isinstance(obj, m.EmployeeAdvance):
        if action == 'approve' and old == 'draft':
            validate(type(obj), obj, {})
            obj.status = 'approved'
        elif action == 'cancel' and old in ('draft', 'approved'):
            obj.status = 'cancelled'
        elif (action, old) in (('disburse', 'approved'), ('settle', 'disbursed')):
            day, reference = movement_date(data), required_text(data, 'reference', 120)
            if action == 'settle' and day < obj.payment_date:
                raise ValidationError('Le remboursement ne peut pas précéder le versement.')
            ensure_open_date(org, day)
            m.Account.objects.get_or_create(organization=org, code='425', defaults={'name':'Personnel — avances'})
            outgoing = action == 'disburse'
            debit, credit = ('425', '521') if outgoing else ('521', '425')
            services.auto_journal(org, actor, f'AV-{action}-{obj.pk}', day, f'Avance {obj.reference}',
                [{'account':debit, 'debit':str(obj.amount)}, {'account':credit, 'credit':str(obj.amount)}])
            if outgoing:
                obj.payment_date, obj.payment_reference, obj.status = day, reference, 'disbursed'
            else:
                obj.settlement_date, obj.settlement_reference, obj.status = day, reference, 'settled'
        else:
            raise ValidationError('Action impossible pour cette avance.')
    elif isinstance(obj, m.FiscalPeriod):
        if action != 'close' or old != 'draft':
            raise ValidationError('Cette période ne peut plus être modifiée.')
        if obj.end_date >= timezone.localdate():
            raise ValidationError('La période doit être entièrement écoulée avant sa clôture.')
        for model in (m.JournalEntry, m.Invoice, m.SupplierBill, m.Expense, m.Purchase):
            if model.objects.filter(organization=org, date__gte=obj.start_date, date__lte=obj.end_date, status='draft').exists():
                raise ValidationError('Traitez les brouillons financiers de cette période avant de la clôturer.')
        if m.BankStatementLine.objects.filter(organization=org, date__gte=obj.start_date, date__lte=obj.end_date, status='draft').exists():
            raise ValidationError('Rapprochez les opérations du relevé avant la clôture.')
        obj.closing_note = required_text(data, 'closing_note')
        obj.closed_at, obj.status = timezone.now(), 'closed'
    elif isinstance(obj, m.BankStatementLine):
        ensure_open_date(org, obj.date)
        note = required_text(data, 'note')
        if action == 'match' and old == 'draft':
            entry = get_object_or_404(m.JournalEntry, organization=org, pk=data.get('journal'))
            if entry.status != 'posted':
                raise ValidationError('Choisissez une écriture comptabilisée.')
            ensure_open_date(org, entry.date)
            amount = sum((services.decimal(line.get('debit', 0)) - services.decimal(line.get('credit', 0)) for line in entry.lines if line['account'] == obj.account.code), services.decimal(0))
            if amount != obj.amount:
                raise ValidationError('Le montant et le sens de l’écriture doivent correspondre au relevé.')
            obj.journal, obj.status = entry, 'matched'
        elif action == 'unmatch' and old == 'matched':
            ensure_open_date(org, obj.journal.date)
            services.audit(org, actor, 'previous-match', obj, journal=str(obj.journal_id), note=note)
            obj.journal, obj.status = None, 'draft'
        else:
            raise ValidationError('Action impossible pour cette opération bancaire.')
        obj.reconciliation_note = note
    obj.full_clean()
    obj.save()
    services.audit(org, actor, action, obj, previous=old, status=obj.status)
    return obj

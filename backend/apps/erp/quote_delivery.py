import hashlib
import secrets
from collections.abc import Mapping
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidation
from django.db import transaction
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import models as m, services
from .auth import limit


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def send_quote(request, org, actor, quote):
    from apps.comptes.invitations import envoyer

    recipient = quote.customer.email.strip().lower()
    try:
        validate_email(recipient)
    except DjangoValidation:
        raise ValidationError('Renseignez une adresse courriel valide pour ce client.')
    zone = ZoneInfo(org.timezone)
    expires = datetime.combine(quote.due_date + timedelta(days=1), time.min, zone)
    if expires <= timezone.now():
        raise ValidationError('La date de validité du devis est dépassée.')
    if quote.quote_status == 'draft' and quote.status == 'draft':
        services.transition(org, actor, m.Invoice, quote.pk, 'issue')
        quote.refresh_from_db()
    elif quote.quote_status != 'sent' or quote.status != 'issued':
        raise ValidationError('Ce devis n’est plus ouvert à une réponse.')
    token = secrets.token_urlsafe(32)
    link, _ = m.QuoteLink.objects.update_or_create(quote=quote, defaults={'organization':org,
        'token_hash':digest(token), 'recipient':recipient, 'expires_at':expires,
        'sent_at':None, 'responded_at':None})
    url = request.build_absolute_uri('/devis') + '#' + token
    context = {'company_name': org.name, 'customer_name': quote.customer.contact_name or quote.customer.name,
        'number': quote.number, 'amount': str(quote.total), 'currency': org.currency,
        'due_date': quote.due_date.strftime('%d/%m/%Y'), 'link': url,
        'logo_url':request.build_absolute_uri('/'+static('erp/email/transitflow-logo.png').lstrip('/'))}
    sent = envoyer(recipient, f'{org.name} : votre devis {quote.number}',
        render_to_string('erp/email/quote.txt', context), render_to_string('erp/email/quote.html', context))
    if not sent:
        raise ValidationError('Le courriel n’a pas pu être transmis. Le devis reste en brouillon ; réessayez plus tard.')
    link.sent_at = timezone.now()
    link.save(update_fields=['sent_at', 'updated_at'])
    services.audit(org, actor, 'quote-send-email', quote, recipient=recipient)
    return quote


class PublicQuoteView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, action):
        if action not in ('preview', 'respond'):
            raise NotFound()
        limit(request, 'public-quote', maximum=60)
        if not isinstance(request.data, Mapping):
            raise ValidationError('Le corps de la requête doit être un objet JSON.')
        token = request.data.get('token')
        if not isinstance(token, str) or not 32 <= len(token) <= 100:
            raise NotFound('Ce lien de devis est invalide ou indisponible.')
        identity = m.QuoteLink.objects.filter(token_hash=digest(token), sent_at__isnull=False).values('organization_id').first()
        if not identity:
            raise NotFound('Ce lien de devis est invalide ou indisponible.')
        with transaction.atomic():
            from .security import set_scope
            set_scope(identity['organization_id'])
            m.Organization.objects.select_for_update().get(pk=identity['organization_id'])
            link = m.QuoteLink.objects.select_for_update(of=('self',)).select_related('quote__organization', 'quote__customer').get(token_hash=digest(token))
            quote = link.quote
            if quote.kind != 'quote' or quote.status != 'issued' or quote.customer.archived_at or link.expires_at <= timezone.now():
                response = Response({'detail': 'Ce lien de devis a expiré ou a été retiré.'}, status=410)
            elif action == 'preview':
                response = Response({'company': quote.organization.name, 'customer': quote.customer.name,
                    'number': quote.number, 'date': str(quote.date), 'valid_until': str(quote.due_date),
                    'origin': quote.origin, 'destination': quote.destination,
                    'lines': [{key:line.get(key,'') for key in ('description','quantity','price','tax_rate')} for line in quote.lines],
                    'subtotal': str(quote.subtotal), 'tax': str(quote.tax), 'total': str(quote.total),
                    'currency': quote.organization.currency, 'state': quote.quote_status})
            else:
                decision = request.data.get('decision')
                if decision not in ('accept', 'refuse'):
                    raise ValidationError('Choisissez Accepter ou Refuser.')
                target = {'accept': 'accepted', 'refuse': 'refused'}[decision]
                if quote.quote_status != 'sent':
                    response = Response({'state': quote.quote_status}, status=200 if quote.quote_status == target else 409)
                else:
                    from .crm_services import quote_action
                    quote_action(quote.organization, None, quote, decision, {})
                    link.responded_at = timezone.now()
                    link.save(update_fields=['responded_at', 'updated_at'])
                    services.audit(quote.organization, None, 'quote-customer-response', quote, decision=target)
                    response = Response({'state': target})
        response['Cache-Control'] = 'no-store'
        response['Referrer-Policy'] = 'no-referrer'
        return response

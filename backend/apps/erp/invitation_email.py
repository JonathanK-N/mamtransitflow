from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.template.loader import render_to_string
from django.templatetags.static import static
from django.utils import timezone

from apps.comptes.models import Utilisateur
from .models import Employee, ROLES


def send_invitation(request, invitation, link):
    from apps.comptes.invitations import envoyer

    organization = invitation.organization
    recipient = Utilisateur.objects.filter(courriel__iexact=invitation.email).first()
    name = recipient.nom.strip() if recipient and recipient.nom else ''
    if not name:
        employee = Employee.objects.filter(organization=organization, email__iexact=invitation.email).first()
        name = employee.name.strip() if employee else ''
    try:
        zone = ZoneInfo(organization.timezone)
    except ZoneInfoNotFoundError:
        zone = timezone.get_default_timezone()
    expiration = timezone.localtime(invitation.expires_at, zone)
    context = {
        'company_name': organization.name,
        'greeting': f'Bonjour {name},' if name else 'Bonjour,',
        'recipient_email': invitation.email,
        'role_name': dict(ROLES).get(invitation.role, 'Client'),
        'is_client': invitation.role == 'client',
        'expires_at': expiration.strftime('%d/%m/%Y à %H:%M'),
        'expiration_zone': str(zone),
        'link': link,
        'logo_url': request.build_absolute_uri('/' + static('erp/email/transitflow-logo.png').lstrip('/')),
    }
    subject = f'Invitation à rejoindre {organization.name} sur TransitFlow'
    text = render_to_string('erp/email/invitation.txt', context)
    html = render_to_string('erp/email/invitation.html', context)
    return envoyer(invitation.email, subject, text, html)

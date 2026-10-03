from django.conf import settings
from django.template.loader import render_to_string
from django.templatetags.static import static


def send_password_reset(request, user, link):
    from apps.comptes.invitations import envoyer

    seconds = settings.PASSWORD_RESET_TIMEOUT
    duration = f'{seconds // 60} minutes' if seconds % 60 == 0 else f'{seconds} secondes'
    name = user.nom.strip() if user.nom else ''
    context = {
        'greeting': f'Bonjour {name},' if name else 'Bonjour,',
        'recipient_email': user.courriel,
        'duration': duration,
        'link': link,
        'logo_url': request.build_absolute_uri('/' + static('erp/email/transitflow-logo.png').lstrip('/')),
    }
    return envoyer(user.courriel, 'TransitFlow — réinitialisation de votre mot de passe',
        render_to_string('erp/email/password_reset.txt', context),
        render_to_string('erp/email/password_reset.html', context))

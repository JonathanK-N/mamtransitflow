"""
TransitFlow — Invitations et reinitialisation de mot de passe
Auteur : Jonathan K-N

Parcours d un chauffeur, comme dans un ERP (Odoo, etc.) :
1. l administrateur cree la fiche du chauffeur, puis l invite ;
2. le chauffeur recoit un courriel "Rejoignez <entreprise> sur TransitFlow" ;
3. il ouvre le lien (invitation.html?jeton=...), choisit son mot de passe,
   et arrive directement dans son portail.
L administrateur ne connait jamais le mot de passe du chauffeur.
"""

import hashlib
import json
import logging
import secrets
import urllib.request
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.utils import timezone
from django.utils.html import escape

from .models import Invitation, Utilisateur

journal = logging.getLogger(__name__)


def empreinte(jeton: str) -> str:
    return hashlib.sha256(jeton.encode()).hexdigest()


def trouver(jeton: str):
    """Invitation correspondant au jeton (valide ou non), ou None."""
    if not jeton or len(jeton) > 200:
        return None
    return Invitation.objects.select_related('chauffeur', 'utilisateur').filter(empreinte=empreinte(jeton)).first()


def lien(request, jeton: str) -> str:
    return request.build_absolute_uri('/invitation.html') + '?jeton=' + jeton


def _creer(type_, courriel, *, chauffeur=None, utilisateur=None, auteur=None):
    """Revoque les liens encore ouverts du meme type pour ce courriel, puis en cree un nouveau."""
    jeton = secrets.token_urlsafe(32)
    with transaction.atomic():
        Invitation.objects.filter(type=type_, courriel__iexact=courriel, utilisee_le__isnull=True,
                                  revoquee=False).update(revoquee=True)
        invitation = Invitation.objects.create(
            type=type_, courriel=courriel.strip().lower(), chauffeur=chauffeur, utilisateur=utilisateur,
            empreinte=empreinte(jeton), cree_par=auteur,
            expire_le=timezone.now() + timedelta(days=settings.TF_INVITATION_JOURS))
    return invitation, jeton


def inviter_chauffeur(request, chauffeur, auteur):
    """Cree l invitation d un chauffeur et tente l envoi du courriel. Renvoie (invitation, lien)."""
    from apps.societe.models import Entreprise

    invitation, jeton = _creer('invitation', chauffeur.courriel, chauffeur=chauffeur, auteur=auteur)
    url = lien(request, jeton)
    nom_entreprise = Entreprise.courante().nom
    sujet = f'Rejoignez {nom_entreprise} sur TransitFlow'
    texte = (f'Bonjour {chauffeur.prenom},\n\n'
             f'{nom_entreprise} vous invite a rejoindre son espace chauffeur sur TransitFlow : vos trajets, '
             f'vos incidents et vos informations au meme endroit.\n\n'
             f'Pour activer votre compte et choisir votre mot de passe, ouvrez ce lien :\n{url}\n\n'
             f'Ce lien est personnel et expire dans {settings.TF_INVITATION_JOURS} jours.\n\n'
             f'— {nom_entreprise}')
    html = _gabarit(nom_entreprise, f'Bonjour {escape(chauffeur.prenom)},',
                    f'<strong>{escape(nom_entreprise)}</strong> vous invite a rejoindre son espace chauffeur '
                    'sur TransitFlow : vos trajets, vos incidents et vos informations au meme endroit.',
                    'Activer mon compte', url)
    invitation.courriel_envoye = envoyer(chauffeur.courriel, sujet, texte, html)
    invitation.save(update_fields=['courriel_envoye'])
    return invitation, url


def demander_reinitialisation(request, courriel: str) -> None:
    """Mot de passe oublie : envoie un lien si un compte actif existe (ne revele rien sinon)."""
    from apps.societe.models import Entreprise

    utilisateur = Utilisateur.objects.filter(courriel__iexact=courriel.strip(), is_active=True).first()
    if not utilisateur:
        return
    invitation, jeton = _creer('reinitialisation', utilisateur.courriel, utilisateur=utilisateur,
                               chauffeur=utilisateur.chauffeur)
    url = lien(request, jeton)
    nom_entreprise = Entreprise.courante().nom
    texte = (f'Bonjour,\n\nUne demande de nouveau mot de passe a ete faite pour votre compte TransitFlow '
             f'({nom_entreprise}).\n\nPour choisir un nouveau mot de passe : {url}\n\n'
             f'Si vous n etes pas a l origine de cette demande, ignorez ce message.')
    html = _gabarit(nom_entreprise, 'Bonjour,',
                    'Une demande de nouveau mot de passe a ete faite pour votre compte. '
                    'Si vous n etes pas a l origine de cette demande, ignorez ce message.',
                    'Choisir un nouveau mot de passe', url)
    invitation.courriel_envoye = envoyer(utilisateur.courriel, f'{nom_entreprise} — nouveau mot de passe',
                                         texte, html)
    invitation.save(update_fields=['courriel_envoye'])


@transaction.atomic
def accepter(invitation: Invitation, mot_de_passe: str) -> Utilisateur:
    """Cree le compte du chauffeur (invitation) ou change le mot de passe (reinitialisation)."""
    invitation = Invitation.objects.select_for_update().get(pk=invitation.pk)
    if not invitation.valide:
        raise ValueError('Ce lien n est plus valide. Demandez un nouveau lien a votre administrateur.')

    if invitation.type == 'reinitialisation':
        utilisateur = invitation.utilisateur
    else:
        utilisateur = Utilisateur.objects.filter(courriel__iexact=invitation.courriel).first()
        if utilisateur and utilisateur.chauffeur_id not in (None, invitation.chauffeur_id):
            raise ValueError('Ce courriel est deja utilise par un autre compte.')
        if not utilisateur:
            utilisateur = Utilisateur(courriel=invitation.courriel)
        chauffeur = invitation.chauffeur
        utilisateur.chauffeur = chauffeur
        utilisateur.nom = chauffeur.nom_complet if chauffeur else utilisateur.nom
        utilisateur.is_active = True
    utilisateur.set_password(mot_de_passe)
    utilisateur.save()
    if invitation.type == 'invitation':
        utilisateur.groups.add(Group.objects.get_or_create(name='fleet.driver')[0])

    invitation.utilisee_le = timezone.now()
    invitation.save(update_fields=['utilisee_le'])
    return utilisateur


def statut_acces(chauffeur) -> dict:
    """Etat de l acces au portail d un chauffeur, pour sa fiche et la liste."""
    compte = getattr(chauffeur, 'compte', None)
    derniere = chauffeur.invitations.filter(type='invitation').first()
    if compte and compte.is_active and compte.has_usable_password():
        return {'etat': 'actif', 'depuis': compte.cree_le.isoformat()}
    if compte and not compte.is_active:
        return {'etat': 'desactive'}
    if derniere and derniere.valide:
        return {'etat': 'invite', 'envoyeeLe': derniere.cree_le.isoformat(), 'expireLe': derniere.expire_le.isoformat(),
                'courrielEnvoye': derniere.courriel_envoye}
    if derniere and not derniere.revoquee and derniere.utilisee_le is None:
        return {'etat': 'expire', 'envoyeeLe': derniere.cree_le.isoformat()}
    return {'etat': 'aucun'}


# ---- Envoi -----------------------------------------------------------------

def envoyer(destinataire: str, sujet: str, texte: str, html: str) -> bool:
    """Envoie un courriel ; renvoie False (sans lever) si l envoi est impossible ou non configure."""
    if not settings.TF_COURRIEL_CONFIGURE:
        # Les tests lisent mail.outbox : on passe quand meme par le backend (locmem).
        _envoyer_django(destinataire, sujet, texte, html)
        return False
    try:
        if settings.TF_RESEND_CLE:
            _envoyer_resend(destinataire, sujet, texte, html)
        else:
            _envoyer_django(destinataire, sujet, texte, html)
        return True
    except Exception:  # un courriel rate ne doit pas faire echouer l invitation
        journal.exception('Envoi du courriel a %s impossible', destinataire)
        return False


def _envoyer_django(destinataire, sujet, texte, html):
    message = EmailMultiAlternatives(sujet, texte, settings.TF_EMAIL_EXPEDITEUR, [destinataire])
    message.attach_alternative(html, 'text/html')
    message.send()


def _envoyer_resend(destinataire, sujet, texte, html):
    requete = urllib.request.Request(
        'https://api.resend.com/emails', method='POST',
        data=json.dumps({'from': settings.TF_EMAIL_EXPEDITEUR, 'to': [destinataire], 'subject': sujet,
                         'text': texte, 'html': html}).encode(),
        headers={'Authorization': 'Bearer ' + settings.TF_RESEND_CLE, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(requete, timeout=15) as reponse:
        if reponse.status >= 300:
            raise RuntimeError(f'Resend a repondu {reponse.status}')


def _gabarit(entreprise, salutation, paragraphe, bouton, url):
    return f'''<!doctype html><html><body style="margin:0;background:#f6f3ee;font-family:Arial,sans-serif;color:#2b2622">
<table width="100%" cellpadding="0" cellspacing="0" style="padding:32px 12px"><tr><td align="center">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;background:#fff;border-radius:14px;padding:32px">
<tr><td style="font-size:18px;font-weight:bold;padding-bottom:4px">Transit<span style="color:#c2571a">Flow</span></td></tr>
<tr><td style="font-size:13px;color:#8a8178;padding-bottom:24px">{escape(entreprise)}</td></tr>
<tr><td style="font-size:15px;line-height:1.5;padding-bottom:12px">{salutation}</td></tr>
<tr><td style="font-size:15px;line-height:1.5;padding-bottom:24px">{paragraphe}</td></tr>
<tr><td style="padding-bottom:24px"><a href="{escape(url)}" style="display:inline-block;background:#c2571a;color:#fff;
text-decoration:none;padding:12px 22px;border-radius:10px;font-weight:bold">{escape(bouton)}</a></td></tr>
<tr><td style="font-size:12px;color:#8a8178;line-height:1.5">Ce lien est personnel et expire dans
{settings.TF_INVITATION_JOURS} jours. Si le bouton ne fonctionne pas, copiez cette adresse :<br>
<span style="word-break:break-all">{escape(url)}</span></td></tr>
</table></td></tr></table></body></html>'''

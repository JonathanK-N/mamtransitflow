"""TransitFlow — comptes et sessions (equivalent de assets/js/auth.js)"""

import secrets
import threading

from . import config
from .store import Store

COMPTES = [
    {'courriel': 'a.tremblay@transitflow.ca', 'role': 'admin', 'nom': 'Alex Tremblay', 'initiales': 'AT'},
    {'courriel': 'a.diallo@transitflow.ca', 'role': 'chauffeur', 'chauffeurId': 'c1'},
    {'courriel': 'm.traore@transitflow.ca', 'role': 'chauffeur', 'chauffeurId': 'c2'},
    {'courriel': 's.fortin@transitflow.ca', 'role': 'chauffeur', 'chauffeurId': 'c3'},
    {'courriel': 'm.barry@transitflow.ca', 'role': 'chauffeur', 'chauffeurId': 'c4'},
    {'courriel': 'Mamadou.Barry@USherbrooke.ca', 'role': 'admin', 'chauffeurId': 'c5',
     'nom': 'Mamadou Barry', 'initiales': 'MB'}
]

_verrou = threading.Lock()
_SESSIONS = {}


def _initiales(chauffeur):
    if not chauffeur:
        return '??'
    return (chauffeur['prenom'][0] + chauffeur['nom'][0]).upper()


def _nom_complet(chauffeur):
    return f"{chauffeur['prenom']} {chauffeur['nom']}" if chauffeur else 'Inconnu'


def connecter(courriel, mot_de_passe, role=None):
    compte = next((c for c in COMPTES
                   if c['courriel'].lower() == str(courriel or '').strip().lower()), None)
    if not compte:
        return {'ok': False, 'message': 'Aucun compte ne correspond a ce courriel.'}
    if mot_de_passe != config.MOT_DE_PASSE_DEMO:
        return {'ok': False, 'message': 'Mot de passe incorrect.'}
    if role and compte['role'] != role:
        return {'ok': False, 'message': 'Ce compte n est pas un compte ' + role + '.'}

    session = dict(compte)
    if compte['role'] == 'chauffeur':
        c = Store.chauffeur(compte['chauffeurId'])
        session['nom'] = _nom_complet(c)
        session['initiales'] = _initiales(c)
    return {'ok': True, 'session': session}


def creer_jeton(session):
    jeton = secrets.token_hex(16)
    with _verrou:
        _SESSIONS[jeton] = session
    return jeton


def obtenir_session(jeton):
    with _verrou:
        return _SESSIONS.get(jeton)


def supprimer_jeton(jeton):
    with _verrou:
        _SESSIONS.pop(jeton, None)


def accueil(session):
    return 'admin/tableau-de-bord.html' if session['role'] == 'admin' else 'chauffeur/mes-trajets.html'

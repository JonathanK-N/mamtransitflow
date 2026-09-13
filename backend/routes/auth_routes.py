"""TransitFlow — routes de connexion / session"""

from flask import Blueprint, jsonify, request

from .. import auth
from . import exiger, utilisateur_courant

bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@bp.post('/connexion')
def connexion():
    payload = request.get_json(silent=True) or {}
    resultat = auth.connecter(payload.get('courriel'), payload.get('motDePasse'), payload.get('role'))
    if not resultat['ok']:
        return jsonify(resultat), 401
    jeton = auth.creer_jeton(resultat['session'])
    return jsonify({'ok': True, 'session': resultat['session'], 'jeton': jeton,
                     'accueil': auth.accueil(resultat['session'])})


@bp.post('/deconnexion')
def deconnexion():
    entete = request.headers.get('Authorization', '')
    jeton = entete[7:] if entete.startswith('Bearer ') else None
    if jeton:
        auth.supprimer_jeton(jeton)
    return jsonify({'ok': True})


@bp.get('/session')
@exiger()
def session_active():
    return jsonify({'ok': True, 'session': utilisateur_courant()})

"""
TransitFlow — Routes de connexion / session
Auteur : Jonathan K-N

Ces routes sont utilisees par la page de connexion (index.html) et par
assets/js/auth.js :
  POST /api/auth/connexion   -> verifie courriel/mot de passe/role, renvoie un jeton
  POST /api/auth/deconnexion -> invalide le jeton
  GET  /api/auth/session     -> renvoie la session actuelle (sert a verifier qu un jeton est toujours valide)
"""

from flask import Blueprint, jsonify, request

from .. import auth
from . import exiger, utilisateur_courant

bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@bp.post('/connexion')
def connexion():
    """
    Recoit {courriel, motDePasse, role} en JSON.
    Si les identifiants sont valides, cree un jeton de session et le
    renvoie au front-end (qui le gardera en sessionStorage et le
    renverra dans l entete Authorization de chaque requete suivante).
    """
    payload = request.get_json(silent=True) or {}
    resultat = auth.connecter(payload.get('courriel'), payload.get('motDePasse'), payload.get('role'))
    if not resultat['ok']:
        return jsonify(resultat), 401
    jeton = auth.creer_jeton(resultat['session'])
    return jsonify({'ok': True, 'session': resultat['session'], 'jeton': jeton,
                     'accueil': auth.accueil(resultat['session'])})


@bp.post('/deconnexion')
def deconnexion():
    """Invalide le jeton envoye (le front-end efface ensuite sa session locale)."""
    entete = request.headers.get('Authorization', '')
    jeton = entete[7:] if entete.startswith('Bearer ') else None
    if jeton:
        auth.supprimer_jeton(jeton)
    return jsonify({'ok': True})


@bp.get('/session')
@exiger()
def session_active():
    """Renvoie la session actuelle si le jeton est encore valide (sinon 401, voir @exiger())."""
    return jsonify({'ok': True, 'session': utilisateur_courant()})

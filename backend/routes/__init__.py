"""TransitFlow — routes de l API"""

from functools import wraps

from flask import Blueprint, jsonify, request

from .. import auth


def utilisateur_courant():
    entete = request.headers.get('Authorization', '')
    jeton = entete[7:] if entete.startswith('Bearer ') else None
    return auth.obtenir_session(jeton) if jeton else None


def exiger(role=None):
    """Protege une route : session valide, et role precis si fourni."""
    def decorateur(fn):
        @wraps(fn)
        def enveloppe(*args, **kwargs):
            session = utilisateur_courant()
            if not session:
                return jsonify({'ok': False, 'message': 'Authentification requise.'}), 401
            if role and session.get('role') != role:
                return jsonify({'ok': False, 'message': 'Acces refuse.'}), 403
            request.session = session
            return fn(*args, **kwargs)
        return enveloppe
    return decorateur


__all__ = ['Blueprint', 'jsonify', 'request', 'exiger', 'utilisateur_courant']

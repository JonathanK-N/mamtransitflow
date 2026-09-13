"""
TransitFlow — Outils communs aux routes de l API
Auteur : Jonathan K-N

Ce fichier contient ce qui est partage par toutes les routes (auth_routes.py,
chauffeurs_routes.py, trajets_routes.py, incidents_routes.py, divers_routes.py) :
- utilisateur_courant() : retrouve la session a partir du jeton envoye
  par le front-end dans l entete "Authorization: Bearer <jeton>" ;
- exiger(role) : un decorateur qu on place au-dessus d une route pour
  la proteger. Sans argument, exiger() demande juste d etre connecte ;
  avec exiger('admin') ou exiger('chauffeur'), il verifie en plus que
  la session a bien ce role.

C est le meme principe que Auth.exiger(...) cote front-end (assets/js/auth.js),
mais ici c est la veritable barriere de securite puisque c est le
serveur qui decide d accepter ou refuser chaque requete.
"""

from functools import wraps

from flask import Blueprint, jsonify, request

from .. import auth


def utilisateur_courant():
    """Lit l entete Authorization et renvoie la session correspondante (ou None)."""
    entete = request.headers.get('Authorization', '')
    jeton = entete[7:] if entete.startswith('Bearer ') else None  # on retire le prefixe "Bearer "
    return auth.obtenir_session(jeton) if jeton else None


def exiger(role=None):
    """
    Decorateur a placer sur une route Flask pour la proteger :
      @bp.get('/exemple')
      @exiger('admin')          # ou juste @exiger() pour "connecte, peu importe le role"
      def exemple():
          ...

    Si la session est absente -> 401 (non authentifie).
    Si la session existe mais n a pas le bon role -> 403 (acces refuse).
    Sinon, la session est deposee dans request.session pour que la
    route puisse s en servir (ex. connaitre le chauffeurId courant).
    """
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

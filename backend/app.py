"""
TransitFlow — Point d entree de l API Flask
Auteur : Jonathan K-N

C est le fichier qui demarre le serveur. Il fait deux choses :
1. Il assemble l API (dossier routes/) : chaque groupe de routes est
   un "blueprint" Flask (auth, chauffeurs, trajets, incidents, divers)
   qu on enregistre ici.
2. Il sert aussi les pages du front-end (index.html, admin/, chauffeur/,
   assets/) directement depuis ce meme serveur Flask. Ainsi, le
   front-end et l API tournent sur la meme adresse (ex. localhost:5000)
   et les appels fetch('/api/...') du front-end fonctionnent sans avoir
   a configurer de serveur separe ni de CORS.

Pour lancer le serveur : `python -m backend.app`, puis ouvrir
http://127.0.0.1:5000/ dans un navigateur.
"""

import os

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

from .routes import auth_routes, chauffeurs_routes, divers_routes, incidents_routes, trajets_routes

# Dossier racine du projet (un niveau au-dessus de backend/), la ou se
# trouvent index.html, admin/, chauffeur/ et assets/.
RACINE_FRONTEND = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def create_app():
    """Construit et configure l application Flask (routes API + pages statiques)."""
    app = Flask(__name__)
    CORS(app)  # autorise les appels depuis une autre origine si jamais le front-end est servi ailleurs

    # Chaque blueprint regroupe les routes d une meme famille (voir backend/routes/).
    app.register_blueprint(auth_routes.bp)
    app.register_blueprint(chauffeurs_routes.bp)
    app.register_blueprint(trajets_routes.bp)
    app.register_blueprint(incidents_routes.bp)
    app.register_blueprint(divers_routes.bp)

    @app.get('/api/sante')
    def sante():
        """Petite route de verification pour confirmer que le serveur repond bien."""
        return jsonify({'ok': True, 'service': 'transitflow-api'})

    # ---- Pages statiques du front-end (index.html, admin/, chauffeur/, assets/) ----
    # On ne sert pas tout le dossier racine "tel quel" (ca exposerait le
    # code du backend et le fichier de donnees) : on ouvre seulement les
    # dossiers/fichiers dont le front-end a besoin.

    @app.get('/')
    def page_accueil():
        """Page de connexion, ouverte automatiquement sur l adresse racine du site."""
        return send_from_directory(RACINE_FRONTEND, 'index.html')

    @app.get('/index.html')
    def page_index():
        return send_from_directory(RACINE_FRONTEND, 'index.html')

    @app.get('/assets/<path:chemin>')
    def fichiers_assets(chemin):
        """CSS, JS et images (assets/css, assets/js, assets/img)."""
        return send_from_directory(os.path.join(RACINE_FRONTEND, 'assets'), chemin)

    @app.get('/admin/<path:chemin>')
    def pages_admin(chemin):
        """Ecrans de l espace administrateur."""
        return send_from_directory(os.path.join(RACINE_FRONTEND, 'admin'), chemin)

    @app.get('/chauffeur/<path:chemin>')
    def pages_chauffeur(chemin):
        """Ecrans de l espace chauffeur."""
        return send_from_directory(os.path.join(RACINE_FRONTEND, 'chauffeur'), chemin)

    return app


# Instance de l application, utilisee par Flask (ex. `flask --app backend.app run`)
# et par les tests (backend/tests/conftest.py appelle create_app() directement).
app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5000)

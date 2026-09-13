"""TransitFlow — point d entree de l API Flask"""

import os

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

from .routes import auth_routes, chauffeurs_routes, divers_routes, incidents_routes, trajets_routes

RACINE_FRONTEND = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def create_app():
    app = Flask(__name__)
    CORS(app)

    app.register_blueprint(auth_routes.bp)
    app.register_blueprint(chauffeurs_routes.bp)
    app.register_blueprint(trajets_routes.bp)
    app.register_blueprint(incidents_routes.bp)
    app.register_blueprint(divers_routes.bp)

    @app.get('/api/sante')
    def sante():
        return jsonify({'ok': True, 'service': 'transitflow-api'})

    # ---- Pages statiques du front-end (index.html, admin/, chauffeur/, assets/) ----
    @app.get('/')
    def page_accueil():
        return send_from_directory(RACINE_FRONTEND, 'index.html')

    @app.get('/index.html')
    def page_index():
        return send_from_directory(RACINE_FRONTEND, 'index.html')

    @app.get('/assets/<path:chemin>')
    def fichiers_assets(chemin):
        return send_from_directory(os.path.join(RACINE_FRONTEND, 'assets'), chemin)

    @app.get('/admin/<path:chemin>')
    def pages_admin(chemin):
        return send_from_directory(os.path.join(RACINE_FRONTEND, 'admin'), chemin)

    @app.get('/chauffeur/<path:chemin>')
    def pages_chauffeur(chemin):
        return send_from_directory(os.path.join(RACINE_FRONTEND, 'chauffeur'), chemin)

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5000)

"""TransitFlow — point d entree de l API Flask"""

from flask import Flask, jsonify
from flask_cors import CORS

from .routes import auth_routes, chauffeurs_routes, divers_routes, incidents_routes, trajets_routes


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

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5000)

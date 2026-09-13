"""
TransitFlow — Point d entree de l API FastAPI
Auteur : Jonathan K-N

Remplace l ancien backend/app.py (Flask). Assemble les routeurs de chaque
app (auth, drivers, fleet, dispatch, maintenance, reporting) et sert
toujours les pages du front-end (index.html, admin/, chauffeur/, assets/)
depuis ce meme serveur, pour eviter tout probleme de CORS en developpement.

Pour lancer le serveur : `uvicorn backend.main:app --reload --port 5000`,
puis ouvrir http://127.0.0.1:5000/
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import models_registry  # noqa: F401  (garantit que tous les modeles sont enregistres)
from .apps.auth.router import router as auth_router
from .apps.dispatch.router import router as dispatch_router
from .apps.drivers.router import router as drivers_router
from .apps.fleet.router import router as fleet_router
from .apps.maintenance.router import router as maintenance_router
from .apps.reporting.router import router as reporting_router
from .database import Base, engine

RACINE_FRONTEND = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def create_app(creer_tables: bool = True) -> FastAPI:
    """
    Construit et configure l application FastAPI (routes API + pages statiques).

    `creer_tables=False` sert uniquement aux tests (voir backend/tests/conftest.py) :
    ils branchent leur propre base SQLite en memoire via `app.dependency_overrides[get_db]`
    et n ont pas besoin -- ni envie -- que cette fonction cree aussi les tables
    sur la base par defaut (settings.database_url).
    """
    app = FastAPI(title='TransitFlow API', version='2.0.0')

    app.add_middleware(
        CORSMiddleware,
        allow_origins=['*'],
        allow_methods=['*'],
        allow_headers=['*']
    )

    if creer_tables:
        # En developpement, cree les tables si elles n existent pas encore.
        # En production, on utilise plutot les migrations Alembic (voir backend/alembic/)
        # pour faire evoluer un schema qui contient deja des donnees reelles.
        Base.metadata.create_all(bind=engine)

    for routeur in (auth_router, drivers_router, fleet_router, dispatch_router,
                     maintenance_router, reporting_router):
        app.include_router(routeur)

    @app.get('/api/sante')
    def sante():
        """Petite route de verification pour confirmer que le serveur repond bien."""
        return {'ok': True, 'service': 'transitflow-api'}

    # ---- Pages statiques du front-end -----------------------------------
    # On n expose pas tout le dossier racine (ca donnerait acces au code du
    # backend) : seulement les dossiers dont le front-end a besoin.
    app.mount('/assets', StaticFiles(directory=os.path.join(RACINE_FRONTEND, 'assets')), name='assets')
    app.mount('/admin', StaticFiles(directory=os.path.join(RACINE_FRONTEND, 'admin'), html=True), name='admin')
    app.mount('/chauffeur', StaticFiles(directory=os.path.join(RACINE_FRONTEND, 'chauffeur'), html=True),
              name='chauffeur')

    @app.get('/')
    @app.get('/index.html')
    def page_accueil():
        return FileResponse(os.path.join(RACINE_FRONTEND, 'index.html'))

    return app


app = create_app()

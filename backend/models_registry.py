"""
TransitFlow — Registre des modeles
Auteur : Jonathan K-N

Chaque app (backend/apps/*/models.py) declare ses tables independamment,
sans s importer les unes les autres, pour eviter les imports circulaires
(ex. Chauffeur reference Trajet par son nom en texte, pas par import
Python direct -- voir les `relationship('Trajet', ...)`).

Ce fichier est le seul endroit qui importe tous les modeles ensemble, pour
que SQLAlchemy connaisse la structure complete de la base de donnees avant
de creer les tables (create_all) ou de generer une migration Alembic.
Il doit etre importe avant tout create_all()/autogenerate.
"""

from .apps.auth import models as _auth_models  # noqa: F401
from .apps.dispatch import models as _dispatch_models  # noqa: F401
from .apps.drivers import models as _drivers_models  # noqa: F401
from .apps.fleet import models as _fleet_models  # noqa: F401
from .apps.maintenance import models as _maintenance_models  # noqa: F401
from .database import Base

__all__ = ['Base']

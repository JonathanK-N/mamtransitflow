"""
TransitFlow — Connexion a la base de donnees
Auteur : Jonathan K-N

Remplace l ancien backend/store.py (fichier JSON) par une vraie base de
donnees relationnelle via SQLAlchemy. Toutes les "apps" (backend/apps/*)
importent `Base` pour declarer leurs modeles, et `get_db` comme dependance
FastAPI pour obtenir une session le temps d une requete.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .settings import settings

# SQLite a besoin de cette option pour etre utilisable depuis plusieurs
# threads (ce que fait un serveur web) ; Postgres n en a pas besoin.
_connect_args = {'check_same_thread': False} if settings.database_url.startswith('sqlite') else {}

engine = create_engine(settings.database_url, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Classe de base commune a tous les modeles (voir backend/apps/*/models.py)."""
    pass


def get_db():
    """
    Dependance FastAPI : ouvre une session pour la duree d une requete et
    la ferme automatiquement ensuite (meme en cas d erreur), en l injectant
    dans les fonctions de route via `db: Session = Depends(get_db)`.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

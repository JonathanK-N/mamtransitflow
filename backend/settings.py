"""
TransitFlow — Configuration du serveur (v2, FastAPI)
Auteur : Jonathan K-N

Remplace l ancien backend/config.py (Flask). Les valeurs viennent des
variables d environnement (fichier .env a la racine, voir .env.example) au
lieu d etre codees en dur, pour pouvoir deployer le meme code chez
n importe quel client (chaque client a son propre secret JWT, sa propre
base de donnees) sans toucher au code.

Contrairement a la version Flask, il n y a plus d "horloge figee"
(AUJOURD_HUI codee en dur) : le serveur utilise l heure reelle, en UTC,
partout (voir backend/apps/*/service.py) pour fonctionner correctement
peu importe le fuseau horaire du client.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='TF_', env_file='.env', extra='ignore')

    # Base de donnees. Par defaut un fichier SQLite local (pratique pour
    # developper/tester sans Docker) ; en developpement/production, on
    # pointe vers Postgres via docker-compose (voir .env.example) :
    # TF_DATABASE_URL=postgresql+psycopg://transitflow:transitflow@localhost:5432/transitflow
    database_url: str = 'sqlite:///./backend/data/transitflow.db'

    # Jeton JWT (connexion). A changer obligatoirement en production
    # (TF_JWT_SECRET dans l environnement du serveur, jamais dans le code).
    jwt_secret: str = 'change-moi-en-production'
    jwt_algorithm: str = 'HS256'
    access_token_minutes: int = 30
    refresh_token_days: int = 14


settings = Settings()

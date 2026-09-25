"""
TransitFlow — Configuration du projet Django
Auteur : Jonathan K-N

Genere par `django-admin startproject`, puis adapte pour TransitFlow :
- lecture de la configuration depuis l environnement (et depuis un fichier
  .env a la racine du projet en developpement, voir .env.example) plutot
  que des valeurs codees en dur, pour pouvoir deployer chez n importe quel
  client (ou sur Railway) sans toucher au code ;
- base de donnees donnee par une URL (TF_DATABASE_URL, ou DATABASE_URL
  fournie automatiquement par Railway) ; SQLite local sinon ;
- ajout des apps metier (backend/apps/*) et de Django REST Framework +
  djangorestframework-simplejwt pour l API JSON consommee par le
  front-end (assets/js/*.js) ;
- mots de passe haches avec Argon2 plutot que l algorithme par defaut
  de Django (PBKDF2), plus robuste ;
- le site d administration integre de Django est deplace sur
  /django-admin/ (voir transitflow/urls.py) car /admin/ est deja pris
  par les pages de l espace administrateur du front-end (admin/*.html) ;
- reglages de securite HTTPS actives automatiquement quand DEBUG est
  desactive (production).
"""

import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
RACINE_PROJET = BASE_DIR.parent  # dossier contenant index.html, admin/, chauffeur/, assets/

# En developpement, les variables sont lues depuis le fichier .env a la
# racine du projet (jamais commite). En production (Railway), elles sont
# definies dans le tableau de bord du service : load_dotenv ne remplace
# jamais une variable deja presente dans l environnement.
load_dotenv(RACINE_PROJET / '.env')


def _liste(valeur: str) -> list:
    return [morceau.strip() for morceau in valeur.split(',') if morceau.strip()]


DEBUG = os.environ.get('TF_DEBUG', '1') == '1'

SECRET_KEY = os.environ.get('TF_SECRET_KEY', '')
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured('TF_SECRET_KEY doit etre defini en production (TF_DEBUG=0).')
    SECRET_KEY = 'django-insecure-cle-de-developpement-a-changer'

ALLOWED_HOSTS = _liste(os.environ.get('TF_ALLOWED_HOSTS', 'localhost,127.0.0.1'))
CSRF_TRUSTED_ORIGINS = _liste(os.environ.get('TF_CSRF_TRUSTED_ORIGINS', ''))

# Railway fournit le domaine public du service : on l autorise
# automatiquement pour ne pas avoir a le recopier a la main.
_domaine_railway = os.environ.get('RAILWAY_PUBLIC_DOMAIN')
if _domaine_railway:
    ALLOWED_HOSTS.append(_domaine_railway)
    CSRF_TRUSTED_ORIGINS.append(f'https://{_domaine_railway}')
if os.environ.get('RAILWAY_ENVIRONMENT_NAME'):
    # Les sondes de sante de Railway (healthcheckPath) arrivent avec cet hote.
    ALLOWED_HOSTS.append('healthcheck.railway.app')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',

    'apps.comptes',
    'apps.drivers',
    'apps.fleet',
    'apps.dispatch',
    'apps.maintenance',
    'apps.reporting',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # Sert les fichiers statiques de l admin Django (collectstatic) en production.
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'transitflow.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'transitflow.wsgi.application'

# Base de donnees. TF_DATABASE_URL (ou DATABASE_URL, fournie par Railway
# quand un service Postgres est relie) ; sinon un fichier SQLite local,
# pratique pour developper/tester sans Docker.
_url_bd = os.environ.get('TF_DATABASE_URL') or os.environ.get('DATABASE_URL') or ''
if _url_bd:
    # Accepte aussi la forme SQLAlchemy 'postgresql+psycopg://' des anciennes
    # versions du fichier .env.example.
    _url_bd = _url_bd.replace('postgresql+psycopg://', 'postgresql://', 1)
    DATABASES = {'default': dj_database_url.parse(_url_bd, conn_max_age=600, conn_health_checks=True)}
else:
    _dossier_sqlite = BASE_DIR / 'data'
    _dossier_sqlite.mkdir(exist_ok=True)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': _dossier_sqlite / 'transitflow.db',
        }
    }

AUTH_USER_MODEL = 'comptes.Utilisateur'

# Argon2 en premier -> devient l algorithme utilise pour les nouveaux mots
# de passe (Django sait quand meme relire d anciens hachages PBKDF2 grace
# aux autres entrees de la liste, utile si on migre une base existante).
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework_simplejwt.authentication.JWTAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['apps.comptes.permissions.EstConnecte'],
}

SIMPLE_JWT = {
    # Jeton d acces court + jeton de rafraichissement plus long : le
    # front-end (assets/js/store.js) redemande un jeton d acces de facon
    # transparente quand il expire. A la deconnexion, le jeton de
    # rafraichissement est mis sur liste noire (token_blacklist).
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=int(os.environ.get('TF_JETON_MINUTES', '60'))),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}

LANGUAGE_CODE = 'fr-ca'
TIME_ZONE = 'America/Toronto'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {
        'BACKEND': ('django.contrib.staticfiles.storage.StaticFilesStorage' if DEBUG
                    else 'whitenoise.storage.CompressedManifestStaticFilesStorage'),
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---- Production (TF_DEBUG=0) ---------------------------------------------
if not DEBUG:
    # Railway termine le HTTPS devant l application et transmet l information
    # dans l entete X-Forwarded-Proto.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = os.environ.get('TF_SSL_REDIRECT', '1') == '1'
    # La route de sante doit rester joignable en HTTP par la sonde de Railway.
    SECURE_REDIRECT_EXEMPT = [r'^api/sante$']
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get('TF_HSTS_SECONDS', '3600'))
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = 'same-origin'
    # HSTS reste limite au domaine du service : on ne peut pas l imposer a
    # tous les sous-domaines de up.railway.app ni l inscrire a la liste de
    # prechargement des navigateurs.
    SILENCED_SYSTEM_CHECKS = ['security.W005', 'security.W021']

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': os.environ.get('TF_LOG_LEVEL', 'INFO')},
}

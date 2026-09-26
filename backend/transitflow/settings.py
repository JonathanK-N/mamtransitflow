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
import sys
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


# Variables injectees automatiquement par Railway dans chaque service.
SUR_RAILWAY = bool(os.environ.get('RAILWAY_ENVIRONMENT_NAME'))
RAILWAY_PRODUCTION = os.environ.get('RAILWAY_ENVIRONMENT_NAME') == 'production'
# `collectstatic` (etape de build) ne fait que copier des fichiers : il n a
# besoin ni de la vraie cle secrete ni de la base de donnees.
_COLLECTSTATIC = 'collectstatic' in sys.argv

# Hors Railway, le mode developpement est actif par defaut ; sur Railway, il
# faut le demander explicitement (TF_DEBUG=1), et il reste interdit dans
# l environnement "production" : la page de debug de Django expose la
# configuration a n importe quel visiteur.
DEBUG = os.environ.get('TF_DEBUG', '0' if SUR_RAILWAY else '1') == '1'
if DEBUG and RAILWAY_PRODUCTION:
    print('TransitFlow : TF_DEBUG=1 ignore dans l environnement Railway "production".', file=sys.stderr)
    DEBUG = False

# Valeurs d exemple (.env.example) qui ne doivent jamais servir en production.
_CLES_D_EXEMPLE = {'change-moi-en-production', 'django-insecure-cle-de-developpement-a-changer'}

SECRET_KEY = os.environ.get('TF_SECRET_KEY', '').strip()
if not DEBUG and not _COLLECTSTATIC:
    # Le message dit pourquoi la cle est refusee, sans jamais l afficher.
    if not SECRET_KEY:
        _probleme = 'la variable TF_SECRET_KEY est absente ou vide dans ce service'
    elif SECRET_KEY in _CLES_D_EXEMPLE:
        _probleme = 'TF_SECRET_KEY contient encore la valeur d exemple de .env.example'
    elif len(SECRET_KEY) < 32:
        _probleme = f'TF_SECRET_KEY est trop courte ({len(SECRET_KEY)} caracteres, 32 minimum)'
    else:
        _probleme = ''
    if _probleme:
        raise ImproperlyConfigured(
            f'Cle secrete refusee : {_probleme}. Generez une valeur aleatoire, par exemple avec : '
            'python -c "import secrets; print(secrets.token_urlsafe(50))"'
        )
if not SECRET_KEY:
    SECRET_KEY = 'django-insecure-cle-de-developpement-a-changer'

ALLOWED_HOSTS = _liste(os.environ.get('TF_ALLOWED_HOSTS', 'localhost,127.0.0.1'))
CSRF_TRUSTED_ORIGINS = _liste(os.environ.get('TF_CSRF_TRUSTED_ORIGINS', ''))

if SUR_RAILWAY:
    # Domaines publics generes par Railway (*.up.railway.app). RAILWAY_PUBLIC_DOMAIN
    # n est injecte qu aux deploiements lances apres la creation du domaine :
    # on accepte donc le suffixe, le routage de Railway ne transmettant a ce
    # service que les requetes qui lui sont destinees.
    ALLOWED_HOSTS.append('.up.railway.app')
    CSRF_TRUSTED_ORIGINS.append('https://*.up.railway.app')
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
    'apps.entretien',
    'apps.suivi',
    'apps.reporting',
    'apps.societe',
    'apps.paie',
    'apps.erp',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'apps.erp.middleware.SecurityHeaders',
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

# Base de donnees. DATABASE_URL (reference au service Postgres de Railway)
# est prioritaire ; sinon TF_DATABASE_URL (developpement avec docker-compose) ;
# sinon un fichier SQLite local, pratique pour developper/tester sans Docker.
_url_bd = os.environ.get('DATABASE_URL') or os.environ.get('TF_DATABASE_URL') or ''
if SUR_RAILWAY and not _COLLECTSTATIC:
    # Sur Railway, le disque du conteneur est efface a chaque deploiement : une
    # base SQLite y perdrait toutes les donnees, et "localhost" n y designe
    # aucun serveur PostgreSQL.
    if not _url_bd:
        raise ImproperlyConfigured(
            'Aucune base de donnees : ajoutez la variable DATABASE_URL=${{Postgres.DATABASE_URL}} au service.')
    if '@localhost' in _url_bd or '@127.0.0.1' in _url_bd:
        raise ImproperlyConfigured(
            'La base de donnees pointe vers localhost (valeur de .env.example) : supprimez TF_DATABASE_URL '
            'et ajoutez DATABASE_URL=${{Postgres.DATABASE_URL}} au service.')
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
    # Envoi des positions GPS (apps/suivi) : un telephone envoie un lot
    # toutes les ~10 s ; au-dela de cette limite, la requete repond 429.
    'DEFAULT_THROTTLE_RATES': {'positions': os.environ.get('TF_GPS_LIMITE', '30/min')},
}

SIMPLE_JWT = {
    'CHECK_REVOKE_TOKEN': True,
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

# Auteur : Jonathan Kakesa (JonathanK-N). Isolation des routes historiques.
TF_LEGACY_ENABLED = os.environ.get('TF_LEGACY_ENABLED', '0') == '1'
PASSWORD_RESET_TIMEOUT = 3600
MEDIA_ROOT = Path(os.environ.get('TF_PRIVATE_STORAGE', str(BASE_DIR / 'privatefiles')))
WHITENOISE_ROOT = None if TF_LEGACY_ENABLED else RACINE_PROJET / 'frontend' / 'dist'
DATA_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024

# ---- Courriels (invitations, reinitialisation de mot de passe) -----------
# Deux facons d envoyer, au choix :
# - SMTP : TF_EMAIL_HOST (+ TF_EMAIL_PORT, TF_EMAIL_UTILISATEUR,
#   TF_EMAIL_MOT_DE_PASSE, TF_EMAIL_TLS=1) ;
# - Resend (API HTTPS, utile quand l hebergeur bloque le port SMTP) :
#   TF_RESEND_CLE.
# TF_EMAIL_EXPEDITEUR : adresse d envoi (ex. "TransitFlow <noreply@exemple.ca>").
# Sans configuration, rien n est envoye : l administrateur copie le lien
# d invitation affiche dans l interface et le transmet lui-meme.
TF_EMAIL_EXPEDITEUR = os.environ.get('TF_EMAIL_EXPEDITEUR', 'TransitFlow <noreply@transitflow.local>')
TF_RESEND_CLE = os.environ.get('TF_RESEND_CLE', '')
DEFAULT_FROM_EMAIL = TF_EMAIL_EXPEDITEUR
if os.environ.get('TF_EMAIL_HOST'):
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.environ['TF_EMAIL_HOST']
    EMAIL_PORT = int(os.environ.get('TF_EMAIL_PORT', '587'))
    EMAIL_HOST_USER = os.environ.get('TF_EMAIL_UTILISATEUR', '')
    EMAIL_HOST_PASSWORD = os.environ.get('TF_EMAIL_MOT_DE_PASSE', '')
    EMAIL_USE_TLS = os.environ.get('TF_EMAIL_TLS', '1') == '1'
    EMAIL_TIMEOUT = 15
else:
    EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
TF_COURRIEL_CONFIGURE = bool(os.environ.get('TF_EMAIL_HOST') or TF_RESEND_CLE)
# Duree de validite d un lien d invitation ou de reinitialisation.
TF_INVITATION_JOURS = int(os.environ.get('TF_INVITATION_JOURS', '7'))

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

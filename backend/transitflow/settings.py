"""
TransitFlow — Configuration du projet Django
Auteur : Jonathan K-N

Genere par `django-admin startproject`, puis adapte pour TransitFlow :
- lecture de la base de donnees et du secret depuis l environnement
  (voir .env.example a la racine du projet) plutot que des valeurs codees
  en dur, pour pouvoir deployer chez n importe quel client sans toucher
  au code ;
- ajout des apps metier (backend/apps/*) et de Django REST Framework +
  djangorestframework-simplejwt pour l API JSON consommee par le
  front-end (assets/js/*.js) ;
- mots de passe haches avec Argon2 plutot que l algorithme par defaut
  de Django (PBKDF2), plus robuste ;
- le site d administration integre de Django est deplace sur
  /django-admin/ (voir transitflow/urls.py) car /admin/ est deja pris
  par les pages de l espace administrateur du front-end (admin/*.html).
"""

import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RACINE_PROJET = BASE_DIR.parent  # dossier contenant index.html, admin/, chauffeur/, assets/

SECRET_KEY = os.environ.get('TF_SECRET_KEY', 'django-insecure-cle-de-developpement-a-changer')
DEBUG = os.environ.get('TF_DEBUG', '1') == '1'
ALLOWED_HOSTS = os.environ.get('TF_ALLOWED_HOSTS', '*').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',

    'apps.comptes',
    'apps.drivers',
    'apps.fleet',
    'apps.dispatch',
    'apps.maintenance',
    'apps.reporting',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
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

# Base de donnees. Par defaut, un fichier SQLite local (pratique pour
# developper/tester sans Docker) ; en developpement/production, TF_DATABASE_URL
# pointe vers Postgres (voir docker-compose.yml et .env.example a la racine).
_url_bd = os.environ.get('TF_DATABASE_URL', '')
if _url_bd.startswith('postgresql'):
    import re as _re
    _correspondance = _re.match(
        r'postgresql(?:\+\w+)?://(?P<user>[^:]+):(?P<password>[^@]+)@(?P<host>[^:/]+):(?P<port>\d+)/(?P<name>.+)',
        _url_bd
    )
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': _correspondance['name'],
            'USER': _correspondance['user'],
            'PASSWORD': _correspondance['password'],
            'HOST': _correspondance['host'],
            'PORT': _correspondance['port'],
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'data' / 'transitflow.db',
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
    # Jeton unique (pas d access/refresh comme le ferait un vrai flux OAuth) pour
    # rester compatible avec assets/js/auth.js, qui ne garde qu un seul jeton.
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=12),
}

LANGUAGE_CODE = 'fr-ca'
TIME_ZONE = 'America/Toronto'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

"""
TransitFlow — Tests de la configuration (settings.py) selon l environnement
Auteur : Jonathan K-N

Chaque cas demarre Django dans un processus separe avec ses propres
variables d environnement, comme le ferait Railway.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
CLE = 'une-vraie-cle-aleatoire-de-plus-de-trente-deux-caracteres-0123'
POSTGRES_RAILWAY = 'postgresql://postgres:secret@postgres.railway.internal:5432/railway'
LECTURE = ('from django.conf import settings as s; import json; '
           'print(json.dumps({"debug": s.DEBUG, "hosts": s.ALLOWED_HOSTS, "db_host": s.DATABASES["default"].get("HOST"), '
           '"ssl": getattr(s, "SECURE_SSL_REDIRECT", False)}))')


def _django(variables, commande=('shell', '-c', LECTURE)):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(('TF_', 'RAILWAY_')) and k != 'DATABASE_URL'}
    env.update(variables)
    return subprocess.run([sys.executable, 'manage.py', *commande], cwd=BACKEND, env=env,
                          capture_output=True, text=True, timeout=120)


def _reglages(variables):
    resultat = _django(variables)
    assert resultat.returncode == 0, resultat.stderr
    return json.loads(resultat.stdout.strip().splitlines()[-1])


RAILWAY = {'RAILWAY_ENVIRONMENT_NAME': 'production', 'DATABASE_URL': POSTGRES_RAILWAY, 'TF_SECRET_KEY': CLE}


def test_railway_correctement_configure():
    r = _reglages(RAILWAY)
    assert r['debug'] is False
    assert r['db_host'] == 'postgres.railway.internal'
    assert '.up.railway.app' in r['hosts'] and 'healthcheck.railway.app' in r['hosts']
    assert r['ssl'] is True


def test_railway_variables_de_env_example_importees():
    """Le cas rencontre en production : les valeurs de developpement importees depuis .env.example."""
    variables = dict(RAILWAY, TF_DEBUG='1', TF_ALLOWED_HOSTS='localhost,127.0.0.1',
                     TF_DATABASE_URL='postgresql://transitflow:transitflow@localhost:5433/transitflow')
    r = _reglages(variables)
    assert r['debug'] is False                       # jamais de page de debug en production
    assert r['db_host'] == 'postgres.railway.internal'  # DATABASE_URL l emporte
    assert '.up.railway.app' in r['hosts']


@pytest.mark.parametrize('cle', ['change-moi-en-production', 'trop-courte', ''])
def test_railway_cle_secrete_d_exemple_refusee(cle):
    resultat = _django(dict(RAILWAY, TF_SECRET_KEY=cle))
    assert resultat.returncode != 0
    assert 'TF_SECRET_KEY' in resultat.stderr


def test_railway_base_localhost_refusee():
    variables = dict(RAILWAY, DATABASE_URL='postgresql://transitflow:transitflow@localhost:5433/transitflow')
    resultat = _django(variables)
    assert resultat.returncode != 0
    assert 'localhost' in resultat.stderr


def test_railway_sans_base_refusee():
    variables = {k: v for k, v in RAILWAY.items() if k != 'DATABASE_URL'}
    resultat = _django(variables)
    assert resultat.returncode != 0
    assert 'DATABASE_URL' in resultat.stderr


def test_railway_collectstatic_sans_cle_ni_base(tmp_path):
    """L etape de build n a encore ni cle secrete ni base de donnees."""
    resultat = _django({'RAILWAY_ENVIRONMENT_NAME': 'production'},
                       ('collectstatic', '--noinput', '--dry-run'))
    assert resultat.returncode == 0, resultat.stderr


def test_developpement_local_par_defaut():
    r = _reglages({})
    assert r['debug'] is True
    assert r['hosts'] == ['localhost', '127.0.0.1']

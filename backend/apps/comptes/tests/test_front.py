"""TransitFlow — service des pages du front-end par Django
   Auteur : Jonathan K-N"""

import pytest

PAGES = ['/', '/index.html', '/admin/tableau-de-bord.html', '/chauffeur/mes-trajets.html',
         '/assets/js/admin-flotte.js', '/assets/css/transitflow.css']


@pytest.mark.parametrize('chemin', PAGES)
def test_front_revalide_apres_deploiement(client, chemin):
    """Sans Cache-Control, le navigateur gardait l ancien JavaScript apres
    un deploiement : chaque fichier du front doit etre revalide."""
    r = client.get(chemin)
    assert r.status_code == 200
    assert r['Cache-Control'] == 'no-cache'
    assert r.has_header('Last-Modified')


def test_front_fichier_inchange_renvoie_304(client):
    r = client.get('/assets/js/admin-flotte.js')
    r2 = client.get('/assets/js/admin-flotte.js', HTTP_IF_MODIFIED_SINCE=r['Last-Modified'])
    assert r2.status_code == 304


def test_front_code_du_backend_non_expose(client):
    client.raise_request_exception = False
    # Remontee de dossier refusee par Django (SuspiciousFileOperation -> 400).
    assert client.get('/admin/../backend/manage.py').status_code == 400
    assert client.get('/backend/manage.py').status_code == 404

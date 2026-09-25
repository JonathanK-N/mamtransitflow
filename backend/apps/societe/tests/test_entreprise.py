"""TransitFlow — Fiche entreprise, modules et portail chauffeur
   Auteur : Jonathan K-N"""

from apps.societe.models import Entreprise
from conftest import creer_chauffeur_avec_compte, entete_auth


def test_nom_public_et_modification(client, jeton_admin):
    assert client.get('/api/entreprise/publique').json()['nom'] == 'Mon entreprise de transport'
    r = client.patch('/api/entreprise', {'nom': 'Navettes Estrie', 'ville': 'Sherbrooke',
                                         'modules': {'paie': False}, 'portail': {'incidents': False}},
                     format='json', **entete_auth(jeton_admin))
    assert r.status_code == 200, r.data
    e = r.json()['entreprise']
    assert e['nom'] == 'Navettes Estrie' and e['ville'] == 'Sherbrooke'
    assert e['modules']['paie'] is False and e['portail']['incidents'] is False
    assert 'courrielConfigure' in e
    assert client.get('/api/entreprise/publique').json()['nom'] == 'Navettes Estrie'


def test_validation(client, jeton_admin):
    assert client.patch('/api/entreprise', {'nom': '  '}, format='json',
                        **entete_auth(jeton_admin)).status_code == 400
    assert client.patch('/api/entreprise', {'modules': {'compta': True}}, format='json',
                        **entete_auth(jeton_admin)).status_code == 400


def test_chauffeur_lit_mais_ne_modifie_pas(client, jeton_admin):
    _, jeton = creer_chauffeur_avec_compte(client, jeton_admin)
    r = client.get('/api/entreprise', **entete_auth(jeton)).json()['entreprise']
    assert 'courrielConfigure' not in r and r['portail']['trajets'] is True
    assert client.patch('/api/entreprise', {'nom': 'Pirate'}, format='json',
                        **entete_auth(jeton)).status_code == 403


def test_portail_paie_depend_du_module(db):
    e = Entreprise.courante()
    e.portail_paie, e.module_paie = True, False
    e.save()
    assert e.portail_autorise('paie') is False


def test_portail_ferme_bloque_l_api_du_chauffeur(client, jeton_admin):
    fiche, jeton = creer_chauffeur_avec_compte(client, jeton_admin)
    client.patch('/api/entreprise', {'portail': {'profil': False, 'incidents': False, 'trajets': False}},
                 format='json', **entete_auth(jeton_admin))
    assert client.patch(f"/api/chauffeurs/{fiche['id']}", {'telephone': '819-555-0000'}, format='json',
                        **entete_auth(jeton)).status_code == 403
    assert client.post('/api/incidents', {}, format='json', **entete_auth(jeton)).status_code == 403
    assert client.post('/api/trajets', {}, format='json', **entete_auth(jeton)).status_code == 403
    # L administrateur n est pas concerne par le portail.
    assert client.patch(f"/api/chauffeurs/{fiche['id']}", {'telephone': '819-555-0000'}, format='json',
                        **entete_auth(jeton_admin)).status_code == 200


def test_module_desactive_bloque_son_api(client, jeton_admin):
    client.patch('/api/entreprise', {'modules': {'entretien': False, 'suivi': False, 'paie': False}},
                 format='json', **entete_auth(jeton_admin))
    for url in ('/api/entretien/bons', '/api/suivi/en-direct', '/api/paie/periodes'):
        assert client.get(url, **entete_auth(jeton_admin)).status_code == 403, url

"""
TransitFlow — Tests du suivi GPS (envoi des positions, carte en direct, parcours, purge)
Auteur : Jonathan K-N
"""

from datetime import timedelta

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone

from apps.dispatch.models import Trajet
from apps.fleet.models import Vehicule
from apps.suivi import services
from apps.suivi.models import PositionGPS, distance_m
from conftest import creer_chauffeur_avec_compte, entete_auth

# Sherbrooke -> Magog, le long de l autoroute 10
SHERBROOKE = (45.4042, -71.8929)
MAGOG = (45.2667, -72.1486)


@pytest.fixture(autouse=True)
def _vehicule(db):
    Vehicule.objects.create(plaque='QC-4821', modele='Ford Transit')


def demarrer(client, jeton_admin, **champs_chauffeur):
    fiche, jeton = creer_chauffeur_avec_compte(client, jeton_admin, **champs_chauffeur)
    debut = timezone.now() - timedelta(minutes=30)
    r = client.post('/api/trajets', {'plaque': 'QC-4821', 'depart': 'Sherbrooke', 'arrivee': 'Magog',
                                     'debut': debut.isoformat(), 'finPrevue': (debut + timedelta(hours=1)).isoformat()},
                    format='json', **entete_auth(jeton))
    assert r.status_code == 201, r.data
    return r.json()['trajet'], jeton, fiche


def point(lat, lng, il_y_a_s=0, **extra):
    donnees = {'lat': lat, 'lng': lng, 'horodatage': (timezone.now() - timedelta(seconds=il_y_a_s)).isoformat()}
    donnees.update(extra)
    return donnees


def envoyer(client, jeton, trajet_id, points):
    return client.post(f'/api/trajets/{trajet_id}/positions', {'positions': points}, format='json',
                       **entete_auth(jeton))


# ---- Calculs -----------------------------------------------------------------

def test_distance_haversine():
    assert distance_m(*SHERBROOKE, *SHERBROOKE) == 0
    d = distance_m(*SHERBROOKE, *MAGOG)
    assert 24_000 < d < 25_500  # ~24,7 km a vol d oiseau


def test_alleger_garde_premier_et_dernier():
    points = list(range(10_000))
    allege = services.alleger(points, 2000)
    assert len(allege) == 2000 and allege[0] == 0 and allege[-1] == 9_999
    assert services.alleger([1, 2, 3], 2000) == [1, 2, 3]


# ---- Envoi des positions -----------------------------------------------------

def test_envoi_d_un_lot(client, jeton_admin):
    trajet, jeton, _ = demarrer(client, jeton_admin)
    r = envoyer(client, jeton, trajet['id'], [
        point(*SHERBROOKE, 20, precision=8, vitesse=0, cap=0),
        point(45.3900, -71.9200, 10, precision=12, vitesse=95.5, cap=230),
    ])
    assert r.status_code == 200, r.data
    assert r.json() == {'ok': True, 'recues': 2, 'enregistrees': 2, 'ignorees': 0}
    p = PositionGPS.objects.order_by('horodatage').last()
    assert p.plaque == 'QC-4821' and float(p.latitude) == 45.39 and p.vitesse_kmh == 95.5


def test_renvoi_du_meme_lot_ignore(client, jeton_admin):
    trajet, jeton, _ = demarrer(client, jeton_admin)
    lot = [point(*SHERBROOKE, 20), point(45.39, -71.92, 10)]
    envoyer(client, jeton, trajet['id'], lot)
    r = envoyer(client, jeton, trajet['id'], lot + [point(45.38, -71.95, 0)])
    assert r.json()['enregistrees'] == 1 and r.json()['ignorees'] == 2
    assert PositionGPS.objects.count() == 3


def test_points_hors_fenetre_ou_imprecis_ignores(client, jeton_admin):
    trajet, jeton, _ = demarrer(client, jeton_admin)
    r = envoyer(client, jeton, trajet['id'], [
        point(*SHERBROOKE, 60 * 60 * 3),          # bien avant le depart du trajet
        point(*SHERBROOKE, -60 * 10),             # 10 minutes dans le futur
        point(*SHERBROOKE, 5, precision=2500),    # triangulation grossiere
        point(*SHERBROOKE, 1, precision=15),      # seul point retenu
    ])
    assert r.json() == {'ok': True, 'recues': 4, 'enregistrees': 1, 'ignorees': 3}


@pytest.mark.parametrize('points', [
    [],
    [{'lat': 95, 'lng': 0, 'horodatage': '2026-09-25T10:00:00Z'}],
    [{'lat': 45, 'lng': -200, 'horodatage': '2026-09-25T10:00:00Z'}],
    [{'lat': 0, 'lng': 0, 'horodatage': '2026-09-25T10:00:00Z'}],
    [{'lat': 45, 'lng': -71}],
    [{'lat': 45, 'lng': -71, 'horodatage': 'hier'}],
    [{'lat': 45, 'lng': -71, 'horodatage': '2026-09-25T10:00:00Z', 'vitesse': -3}],
])
def test_lot_invalide(client, jeton_admin, points):
    trajet, jeton, _ = demarrer(client, jeton_admin)
    assert envoyer(client, jeton, trajet['id'], points).status_code == 400
    assert not PositionGPS.objects.exists()


def test_lot_trop_gros(client, jeton_admin):
    trajet, jeton, _ = demarrer(client, jeton_admin)
    lot = [point(45.40 + i / 10000, -71.89, 300 - i) for i in range(201)]
    assert envoyer(client, jeton, trajet['id'], lot).status_code == 400


def test_envoi_reserve_au_chauffeur_du_trajet(client, jeton_admin):
    trajet, _, _ = demarrer(client, jeton_admin)
    _, autre = creer_chauffeur_avec_compte(client, jeton_admin, courriel='m.traore@transitflow.ca', prenom='Moussa',
                                           nom='Traore')
    assert envoyer(client, autre, trajet['id'], [point(*SHERBROOKE)]).status_code == 404
    assert envoyer(client, jeton_admin, trajet['id'], [point(*SHERBROOKE)]).status_code == 403
    assert client.post(f"/api/trajets/{trajet['id']}/positions", {'positions': [point(*SHERBROOKE)]},
                       format='json').status_code == 401
    assert envoyer(client, autre, 'T-999', [point(*SHERBROOKE)]).status_code == 404


def test_envoi_refuse_apres_la_fin_du_trajet(client, jeton_admin):
    trajet, jeton, _ = demarrer(client, jeton_admin)
    client.post(f"/api/trajets/{trajet['id']}/terminer", **entete_auth(jeton))
    r = envoyer(client, jeton, trajet['id'], [point(*SHERBROOKE)])
    assert r.status_code == 409


def test_limitation_de_debit(client, jeton_admin, settings):
    from rest_framework.throttling import ScopedRateThrottle
    trajet, jeton, _ = demarrer(client, jeton_admin)
    ancien = ScopedRateThrottle.THROTTLE_RATES
    ScopedRateThrottle.THROTTLE_RATES = {'positions': '3/min'}
    try:
        codes = [envoyer(client, jeton, trajet['id'], [point(*SHERBROOKE, 30 - i)]).status_code for i in range(4)]
    finally:
        ScopedRateThrottle.THROTTLE_RATES = ancien
    assert codes == [200, 200, 200, 429]


# ---- Carte en direct -----------------------------------------------------------

def test_en_direct(client, jeton_admin):
    trajet, jeton, fiche = demarrer(client, jeton_admin)
    envoyer(client, jeton, trajet['id'], [point(*SHERBROOKE, 40), point(45.39, -71.92, 5, vitesse=88)])
    # Un second trajet en cours, sans aucune position recue.
    Vehicule.objects.create(plaque='QC-1094', modele='Sprinter')
    _, jeton2 = creer_chauffeur_avec_compte(client, jeton_admin, courriel='m.traore@transitflow.ca',
                                               prenom='Moussa', nom='Traore')
    client.post('/api/trajets', {'plaque': 'QC-1094', 'depart': 'Quebec', 'arrivee': 'Levis',
                                 'debut': timezone.now().isoformat(),
                                 'finPrevue': (timezone.now() + timedelta(hours=1)).isoformat()},
                format='json', **entete_auth(jeton2))

    r = client.get('/api/suivi/en-direct', **entete_auth(jeton_admin))
    assert r.status_code == 200
    vehicules = {v['plaque']: v for v in r.json()['vehicules']}
    assert set(vehicules) == {'QC-4821', 'QC-1094'}
    v = vehicules['QC-4821']
    assert v['trajetId'] == trajet['id'] and v['chauffeur'] == 'Aminata Diallo'
    assert v['liaison'] == 'en-ligne' and v['position']['vitesse'] == 88 and 3 <= v['ageSecondes'] <= 60
    assert vehicules['QC-1094']['liaison'] == 'aucune' and vehicules['QC-1094']['position'] is None


def test_en_direct_exclut_les_trajets_termines(client, jeton_admin):
    trajet, jeton, _ = demarrer(client, jeton_admin)
    envoyer(client, jeton, trajet['id'], [point(*SHERBROOKE)])
    client.post(f"/api/trajets/{trajet['id']}/terminer", **entete_auth(jeton))
    assert client.get('/api/suivi/en-direct', **entete_auth(jeton_admin)).json()['vehicules'] == []


def test_en_direct_reserve_admin(client, jeton_admin):
    _, jeton, _ = demarrer(client, jeton_admin)
    assert client.get('/api/suivi/en-direct', **entete_auth(jeton)).status_code == 403


@pytest.mark.parametrize('age, etat', [(10, 'en-ligne'), (120, 'intermittent'), (900, 'perdue')])
def test_etat_de_la_liaison(age, etat):
    maintenant = timezone.now()
    assert services.etat_liaison(PositionGPS(horodatage=maintenant - timedelta(seconds=age)), maintenant) == etat
    assert services.etat_liaison(None, maintenant) == 'aucune'


# ---- Parcours ------------------------------------------------------------------

def test_parcours_et_statistiques(client, jeton_admin):
    trajet, jeton, _ = demarrer(client, jeton_admin)
    # 3 points a 60 s d intervalle, ~1,7 km chacun, plus un point aberrant (saut de 100 km).
    envoyer(client, jeton, trajet['id'], [
        point(45.4000, -71.9000, 240, precision=10),
        point(45.4150, -71.9000, 180, precision=10),
        point(46.3000, -71.9000, 150, precision=10),   # aberrant : ignore dans la distance
        point(45.4300, -71.9000, 120, precision=10),
        point(45.4400, -71.9000, 60, precision=900),   # imprecis : ignore dans la distance
    ])
    r = client.get(f"/api/trajets/{trajet['id']}/parcours", **entete_auth(jeton_admin))
    assert r.status_code == 200
    corps = r.json()
    assert corps['nombrePoints'] == 5 and len(corps['positions']) == 5
    assert corps['liaison'] == 'intermittent'
    s = corps['statistiques']
    assert 3300 < s['distanceM'] < 3400      # 2 troncons valides de ~1 668 m
    assert s['dureeS'] == 180
    assert 80 < s['vitesseMaxKmh'] < 120     # estimee (aucune vitesse fournie par l appareil)
    assert corps['positions'][0]['lat'] == 45.4


def test_parcours_vide(client, jeton_admin):
    trajet, jeton, _ = demarrer(client, jeton_admin)
    corps = client.get(f"/api/trajets/{trajet['id']}/parcours", **entete_auth(jeton)).json()
    assert corps['positions'] == [] and corps['statistiques']['distanceM'] == 0 and corps['liaison'] == 'aucune'


def test_parcours_cloisonne(client, jeton_admin):
    trajet, _, _ = demarrer(client, jeton_admin)
    _, autre = creer_chauffeur_avec_compte(client, jeton_admin, courriel='m.traore@transitflow.ca', prenom='Moussa',
                                           nom='Traore')
    assert client.get(f"/api/trajets/{trajet['id']}/parcours", **entete_auth(autre)).status_code == 404
    assert client.get('/api/trajets/T-999/parcours', **entete_auth(jeton_admin)).status_code == 404


# ---- Purge ---------------------------------------------------------------------

def test_purge_des_positions(client, jeton_admin):
    trajet, jeton, _ = demarrer(client, jeton_admin)
    envoyer(client, jeton, trajet['id'], [point(*SHERBROOKE, 10)])
    client.post(f"/api/trajets/{trajet['id']}/terminer", **entete_auth(jeton))

    call_command('purger_positions', '--jours', '30')
    assert PositionGPS.objects.count() == 1  # trajet termine aujourd hui : conserve

    Trajet.objects.update(fin=timezone.now() - timedelta(days=31))
    call_command('purger_positions', '--jours', '30', '--simulation')
    assert PositionGPS.objects.count() == 1
    call_command('purger_positions', '--jours', '30')
    assert PositionGPS.objects.count() == 0
    assert Trajet.objects.count() == 1


def test_purge_ne_touche_pas_aux_trajets_en_cours(client, jeton_admin):
    trajet, jeton, _ = demarrer(client, jeton_admin)
    envoyer(client, jeton, trajet['id'], [point(*SHERBROOKE, 10)])
    call_command('purger_positions', '--jours', '1')
    assert PositionGPS.objects.count() == 1


def test_purge_duree_invalide(db):
    with pytest.raises(CommandError):
        call_command('purger_positions', '--jours', '0')


def test_premier_point_aberrant_ne_bloque_pas_la_distance():
    from apps.suivi.models import PositionGPS as P
    t0 = timezone.now()

    def pos(lat, s):
        return P(latitude=lat, longitude=-71.9, precision_m=10, vitesse_kmh=None, horodatage=t0 + timedelta(seconds=s))

    # Premier point a 100 km (erreur de premiere mesure), puis trajet regulier de ~1,1 km par minute.
    points = [pos(46.3, 0), pos(45.40, 60), pos(45.41, 120), pos(45.42, 180), pos(45.43, 240)]
    s = services.statistiques(points)
    assert 3300 < s['distanceM'] < 3400  # 3 troncons de ~1 112 m ; le saut initial n est pas compte


def test_point_aberrant_isole_ignore():
    from apps.suivi.models import PositionGPS as P
    t0 = timezone.now()
    lats = [45.40, 45.41, 47.00, 45.42, 45.43]
    points = [P(latitude=l, longitude=-71.9, precision_m=10, horodatage=t0 + timedelta(seconds=60 * i))
              for i, l in enumerate(lats)]
    assert 3300 < services.statistiques(points)['distanceM'] < 3400


def test_vitesse_max_jamais_inferieure_a_la_moyenne():
    from apps.suivi.models import PositionGPS as P
    t0 = timezone.now()
    # Points rapproches (2 s) : aucun troncon assez long pour estimer une vitesse de pointe.
    points = [P(latitude=45.40, longitude=-71.9 - i * 0.0004, precision_m=8, horodatage=t0 + timedelta(seconds=2 * i))
              for i in range(5)]
    s = services.statistiques(points)
    assert s['vitesseMaxKmh'] >= s['vitesseMoyenneKmh'] > 0

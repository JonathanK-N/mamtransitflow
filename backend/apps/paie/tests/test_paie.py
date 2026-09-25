"""TransitFlow — Paie : calcul, retenues, cycle de vie, portail chauffeur
   Auteur : Jonathan K-N

Montants verifies a la main (parametres 2026, paie aux deux semaines) :
45 h la meme semaine a 25 $/h -> 40 h x 25 + 5 h x 37,50 = 1 187,50 $ brut
  RRQ  : (1 187,50 - 3 500 / 26) x 6,3 %  = 66,33 $
  AE   : 1 187,50 x 1,30 %               = 15,44 $  (employeur 1,82 % = 21,61 $)
  RQAP : 1 187,50 x 0,430 %              =  5,11 $  (employeur 0,602 % = 7,15 $)
"""

import csv
import io
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.dispatch.models import Trajet
from apps.drivers.models import Chauffeur
from apps.paie.models import BulletinPaie, PeriodePaie, ProfilPaie
from conftest import creer_chauffeur_avec_compte, entete_auth

LUNDI = date(2026, 9, 7)  # semaine ISO du 7 au 13 septembre 2026


def trajet(chauffeur, jour, heures, statut='termine'):
    debut = timezone.make_aware(datetime.combine(jour, datetime.min.time()) + timedelta(hours=6))
    return Trajet.objects.create(chauffeur=chauffeur, plaque='QC-1', depart='Sherbrooke', arrivee='Montreal',
                                 debut=debut, fin_prevue=debut + timedelta(hours=heures),
                                 fin=debut + timedelta(hours=heures) if statut == 'termine' else None, statut=statut)


@pytest.fixture
def chauffeur_et_jeton(client, jeton_admin):
    fiche, jeton = creer_chauffeur_avec_compte(client, jeton_admin)
    return Chauffeur.depuis_code(fiche['id']), jeton


def creer_periode(client, jeton_admin, debut=LUNDI, fin=LUNDI + timedelta(days=13), paiement=None):
    r = client.post('/api/paie/periodes', {'debut': debut.isoformat(), 'fin': fin.isoformat(),
                                           'datePaiement': (paiement or fin + timedelta(days=5)).isoformat()},
                    format='json', **entete_auth(jeton_admin))
    assert r.status_code == 201, r.data
    return r.json()['periode']


def lignes(bulletin):
    return {l['code'] + ('-emp' if l['genre'] == 'employeur' else ''): l for l in bulletin['lignes']}


def bulletin_de(client, jeton_admin, periode_id):
    b = client.get(f'/api/paie/periodes/{periode_id}', **entete_auth(jeton_admin)).json()['bulletins'][0]
    return client.get(f"/api/paie/bulletins/{b['id']}", **entete_auth(jeton_admin)).json()['bulletin']


def test_retenues_2026_par_defaut(client, jeton_admin):
    r = client.get('/api/paie/parametres', **entete_auth(jeton_admin)).json()
    par_code = {x['code']: x for x in r['retenues']}
    assert par_code['RRQ']['tauxSalarie'] == 6.3 and par_code['RRQ']['plafondAnnuel'] == 74600
    assert par_code['AE']['tauxEmployeur'] == 1.82 and par_code['RQAP']['tauxSalarie'] == 0.43
    assert par_code['IMP-QC']['actif'] is False
    assert r['parametres']['periodesParAn'] == 26


def test_calcul_horaire_avec_heures_sup(client, jeton_admin, chauffeur_et_jeton):
    chauffeur, _ = chauffeur_et_jeton
    ProfilPaie.objects.create(chauffeur=chauffeur, mode='horaire', taux_horaire=Decimal('25'))
    for i in range(5):
        trajet(chauffeur, LUNDI + timedelta(days=i), 9)  # 45 h la meme semaine
    trajet(chauffeur, LUNDI + timedelta(days=2), 3, statut='en-cours')  # non termine : ignore
    trajet(chauffeur, LUNDI - timedelta(days=1), 8)  # avant la periode : ignore

    periode = creer_periode(client, jeton_admin)
    b = bulletin_de(client, jeton_admin, periode['id'])
    l = lignes(b)
    assert b['nombreTrajets'] == 5 and b['heuresRegulieres'] == 40 and b['heuresSup'] == 5
    assert l['REG']['montant'] == 1000 and l['HS']['montant'] == 187.5 and l['HS']['taux'] == 37.5
    assert b['brut'] == 1187.5
    assert l['RRQ']['montant'] == 66.33 and l['AE']['montant'] == 15.44 and l['RQAP']['montant'] == 5.11
    assert 'RRQ2' not in l  # sous le plancher de 74 600 $ : ligne a 0 $
    assert l['AE-emp']['montant'] == 21.61 and l['RQAP-emp']['montant'] == 7.15
    assert b['retenues'] == round(66.33 + 15.44 + 5.11, 2)
    assert b['net'] == round(1187.5 - b['retenues'], 2)
    assert b['coutEmployeur'] == round(1187.5 + b['cotisationsEmployeur'], 2)


def test_heures_sup_semaine_a_cheval(client, jeton_admin, chauffeur_et_jeton):
    """30 h en debut de semaine (paie precedente) + 15 h ensuite : 10 h regulieres, 5 h sup."""
    chauffeur, _ = chauffeur_et_jeton
    ProfilPaie.objects.create(chauffeur=chauffeur, mode='horaire', taux_horaire=Decimal('20'))
    for i in range(3):
        trajet(chauffeur, LUNDI + timedelta(days=i), 10)
    for i in range(3, 6):
        trajet(chauffeur, LUNDI + timedelta(days=i), 5)
    periode = creer_periode(client, jeton_admin, debut=LUNDI + timedelta(days=3), fin=LUNDI + timedelta(days=16))
    b = bulletin_de(client, jeton_admin, periode['id'])
    assert b['heuresRegulieres'] == 10 and b['heuresSup'] == 5


def test_plafond_annuel_de_l_assurance_emploi(client, jeton_admin, chauffeur_et_jeton):
    chauffeur, _ = chauffeur_et_jeton
    ProfilPaie.objects.create(chauffeur=chauffeur, mode='fixe', salaire_periode=Decimal('2000'))
    ancienne = PeriodePaie.objects.create(debut=date(2026, 1, 1), fin=date(2026, 1, 14),
                                          date_paiement=date(2026, 1, 20), statut='payee')
    BulletinPaie.objects.create(periode=ancienne, chauffeur=chauffeur, brut_imposable=Decimal('68500'))
    b = bulletin_de(client, jeton_admin, creer_periode(client, jeton_admin)['id'])
    l = lignes(b)
    assert l['SAL']['montant'] == 2000
    assert l['AE']['quantite'] == 400 and l['AE']['montant'] == 5.2  # seuls 400 $ restent assurables
    assert l['RQAP']['quantite'] == 2000


def test_modes_trajet_et_sans_profil(client, jeton_admin, chauffeur_et_jeton):
    chauffeur, _ = chauffeur_et_jeton
    for i in range(3):
        trajet(chauffeur, LUNDI + timedelta(days=i), 2)
    periode = creer_periode(client, jeton_admin)
    assert periode['totaux']['bulletins'] == 0  # pas de profil : pas de bulletin
    r = client.put(f'/api/paie/profils/{chauffeur.code}', {'mode': 'trajet', 'tauxTrajet': '85'}, format='json',
                   **entete_auth(jeton_admin))
    assert r.status_code == 200, r.data
    client.post(f"/api/paie/periodes/{periode['id']}/calculer", **entete_auth(jeton_admin))
    b = bulletin_de(client, jeton_admin, periode['id'])
    assert lignes(b)['TRJ']['montant'] == 255 and b['nombreTrajets'] == 3
    assert client.put(f'/api/paie/profils/{chauffeur.code}', {'mode': 'horaire'}, format='json',
                      **entete_auth(jeton_admin)).status_code == 400  # taux manquant


def test_lignes_manuelles(client, jeton_admin, chauffeur_et_jeton):
    chauffeur, _ = chauffeur_et_jeton
    ProfilPaie.objects.create(chauffeur=chauffeur, mode='fixe', salaire_periode=Decimal('1000'))
    periode = creer_periode(client, jeton_admin)
    b = bulletin_de(client, jeton_admin, periode['id'])
    url = f"/api/paie/bulletins/{b['id']}/lignes"
    client.post(url, {'genre': 'gain', 'libelle': 'Prime de nuit', 'montant': '100'}, format='json',
                **entete_auth(jeton_admin))
    client.post(url, {'genre': 'gain', 'libelle': 'Remboursement repas', 'montant': '50', 'imposable': False},
                format='json', **entete_auth(jeton_admin))
    r = client.post(url, {'genre': 'retenue', 'libelle': 'Avance', 'montant': '200'}, format='json',
                    **entete_auth(jeton_admin))
    b = r.json()['bulletin']
    assert b['brut'] == 1150 and b['brutImposable'] == 1100
    assert lignes(b)['AE']['quantite'] == 1100  # le remboursement n est pas cotisable
    # Un recalcul complet garde les lignes manuelles.
    client.post(f"/api/paie/periodes/{periode['id']}/calculer", **entete_auth(jeton_admin))
    b = bulletin_de(client, jeton_admin, periode['id'])
    assert sum(1 for l in b['lignes'] if l['manuelle']) == 3
    avance = next(l for l in b['lignes'] if l['libelle'] == 'Avance')
    b = client.delete(f"/api/paie/lignes/{avance['id']}", **entete_auth(jeton_admin)).json()['bulletin']
    assert b['net'] == round(1150 - b['retenues'], 2)


def test_cycle_de_vie_et_portail_chauffeur(client, jeton_admin, chauffeur_et_jeton):
    chauffeur, jeton_chauffeur = chauffeur_et_jeton
    ProfilPaie.objects.create(chauffeur=chauffeur, mode='fixe', salaire_periode=Decimal('1500'))
    periode = creer_periode(client, jeton_admin)
    pid = periode['id']
    bid = bulletin_de(client, jeton_admin, pid)['id']

    # Portail paie ferme par defaut.
    assert client.get('/api/paie/mes-bulletins', **entete_auth(jeton_chauffeur)).status_code == 403
    client.patch('/api/entreprise', {'portail': {'paie': True}}, format='json', **entete_auth(jeton_admin))
    # Brouillon : invisible pour le chauffeur.
    assert client.get('/api/paie/mes-bulletins', **entete_auth(jeton_chauffeur)).json()['bulletins'] == []
    assert client.get(f'/api/paie/bulletins/{bid}', **entete_auth(jeton_chauffeur)).status_code == 404

    assert client.post(f'/api/paie/periodes/{pid}/payer', **entete_auth(jeton_admin)).status_code == 409
    assert client.post(f'/api/paie/periodes/{pid}/valider', **entete_auth(jeton_admin)).status_code == 200
    assert client.post(f'/api/paie/periodes/{pid}/calculer', **entete_auth(jeton_admin)).status_code == 409
    assert client.post(f'/api/paie/bulletins/{bid}/lignes', {'genre': 'gain', 'libelle': 'x', 'montant': '1'},
                       format='json', **entete_auth(jeton_admin)).status_code == 409
    assert client.delete(f'/api/paie/periodes/{pid}', **entete_auth(jeton_admin)).status_code == 409

    mes = client.get('/api/paie/mes-bulletins', **entete_auth(jeton_chauffeur)).json()['bulletins']
    assert [b['id'] for b in mes] == [bid]
    detail = client.get(f'/api/paie/bulletins/{bid}', **entete_auth(jeton_chauffeur)).json()
    assert detail['bulletin']['brut'] == 1500 and detail['employeur']['nom']
    # Le chauffeur n accede pas a l administration de la paie.
    assert client.get('/api/paie/periodes', **entete_auth(jeton_chauffeur)).status_code == 403

    assert client.post(f'/api/paie/periodes/{pid}/payer', **entete_auth(jeton_admin)).json()['periode'][
        'statut'] == 'payee'
    assert client.post(f'/api/paie/periodes/{pid}/rouvrir', **entete_auth(jeton_admin)).status_code == 409


def test_bulletin_d_un_autre_chauffeur_invisible(client, jeton_admin, chauffeur_et_jeton):
    chauffeur, _ = chauffeur_et_jeton
    ProfilPaie.objects.create(chauffeur=chauffeur, mode='fixe', salaire_periode=Decimal('1500'))
    pid = creer_periode(client, jeton_admin)['id']
    bid = bulletin_de(client, jeton_admin, pid)['id']
    client.post(f'/api/paie/periodes/{pid}/valider', **entete_auth(jeton_admin))
    client.patch('/api/entreprise', {'portail': {'paie': True}}, format='json', **entete_auth(jeton_admin))
    _, autre = creer_chauffeur_avec_compte(client, jeton_admin, courriel='m.traore@transitflow.ca',
                                           prenom='Moussa', nom='Traore')
    assert client.get(f'/api/paie/bulletins/{bid}', **entete_auth(autre)).status_code == 404


def test_periodes_invalides(client, jeton_admin):
    creer_periode(client, jeton_admin)
    for debut, fin, paiement in [(LUNDI + timedelta(days=5), LUNDI + timedelta(days=18), LUNDI + timedelta(days=20)),
                                 (date(2026, 10, 10), date(2026, 10, 1), date(2026, 10, 15)),
                                 (date(2026, 11, 1), date(2026, 12, 31), date(2027, 1, 5)),
                                 (date(2026, 11, 1), date(2026, 11, 14), date(2026, 11, 10))]:
        r = client.post('/api/paie/periodes', {'debut': debut.isoformat(), 'fin': fin.isoformat(),
                                               'datePaiement': paiement.isoformat()},
                        format='json', **entete_auth(jeton_admin))
        assert r.status_code == 400, (debut, fin)


def test_export_csv(client, jeton_admin, chauffeur_et_jeton):
    chauffeur, _ = chauffeur_et_jeton
    ProfilPaie.objects.create(chauffeur=chauffeur, mode='fixe', salaire_periode=Decimal('1234.5'))
    pid = creer_periode(client, jeton_admin)['id']
    r = client.get(f'/api/paie/periodes/{pid}/export.csv', **entete_auth(jeton_admin))
    assert r.status_code == 200 and r['Content-Type'].startswith('text/csv')
    lignes_csv = list(csv.reader(io.StringIO(r.content.decode('utf-8').lstrip('\ufeff')), delimiter=';'))
    ligne = dict(zip(lignes_csv[0], lignes_csv[1]))
    assert ligne['Chauffeur'] == 'Aminata Diallo' and ligne['Brut'] == '1234,50' and 'Retenue RRQ' in ligne


def test_retenue_personnalisee(client, jeton_admin, chauffeur_et_jeton):
    chauffeur, _ = chauffeur_et_jeton
    ProfilPaie.objects.create(chauffeur=chauffeur, mode='fixe', salaire_periode=Decimal('1000'))
    r = client.post('/api/paie/retenues', {'code': 'SYND', 'libelle': 'Cotisation syndicale', 'tauxSalarie': '1.5'},
                    format='json', **entete_auth(jeton_admin))
    assert r.status_code == 201, r.data
    rid = r.json()['retenue']['id']
    assert client.patch(f'/api/paie/retenues/{rid}', {'plancherAnnuel': '100', 'plafondAnnuel': '50'},
                        format='json', **entete_auth(jeton_admin)).status_code == 400
    b = bulletin_de(client, jeton_admin, creer_periode(client, jeton_admin)['id'])
    assert lignes(b)['SYND']['montant'] == 15

"""
TransitFlow — Tests des plans d entretien preventif et des echeances
Auteur : Jonathan K-N
"""

from datetime import timedelta

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.entretien.models import BonTravail, PlanEntretien
from apps.fleet.models import Vehicule
from conftest import creer_chauffeur_avec_compte, entete_auth

AUJOURDHUI = timezone.localdate


@pytest.fixture
def vehicule(db):
    return Vehicule.objects.create(plaque='QC-4821', modele='Ford Transit', kilometrage=50000)


def creer_plan(vehicule, **champs):
    valeurs = dict(type='vidange', libelle='Vidange', intervalle_km=8000, intervalle_jours=180,
                   dernier_km=vehicule.kilometrage, derniere_date=AUJOURDHUI())
    valeurs.update(champs)
    return PlanEntretien.objects.create(vehicule=vehicule, **valeurs)


# ---- Calcul des echeances ------------------------------------------------

def test_plan_neuf_a_jour(vehicule):
    plan = creer_plan(vehicule)
    e = plan.echeance(AUJOURDHUI())
    assert e == {'etat': 'a-jour', 'kmRestants': 8000, 'joursRestants': 180}
    assert plan.prochain_km == 58000
    assert plan.prochaine_date == AUJOURDHUI() + timedelta(days=180)


def test_bientot_par_kilometres(vehicule):
    plan = creer_plan(vehicule, dernier_km=vehicule.kilometrage - 7100)
    assert plan.echeance(AUJOURDHUI())['etat'] == 'bientot'  # 900 km restants <= 1 000


def test_bientot_par_jours(vehicule):
    plan = creer_plan(vehicule, derniere_date=AUJOURDHUI() - timedelta(days=160))
    assert plan.echeance(AUJOURDHUI()) == {'etat': 'bientot', 'kmRestants': 8000, 'joursRestants': 20}


def test_seuil_proportionnel_aux_petits_intervalles(vehicule):
    # Controle tous les 90 jours : l alerte se declenche a 18 jours, pas a 30.
    plan = creer_plan(vehicule, intervalle_km=None, intervalle_jours=90,
                      derniere_date=AUJOURDHUI() - timedelta(days=65))
    assert plan.echeance(AUJOURDHUI())['etat'] == 'a-jour'  # 25 jours restants
    plan.derniere_date = AUJOURDHUI() - timedelta(days=75)
    assert plan.echeance(AUJOURDHUI())['etat'] == 'bientot'  # 15 jours restants


def test_en_retard_par_la_premiere_limite(vehicule):
    plan = creer_plan(vehicule, dernier_km=vehicule.kilometrage - 8200)
    e = plan.echeance(AUJOURDHUI())
    assert e['etat'] == 'en-retard' and e['kmRestants'] == -200 and e['joursRestants'] == 180


def test_en_retard_le_jour_meme(vehicule):
    plan = creer_plan(vehicule, intervalle_km=None, derniere_date=AUJOURDHUI() - timedelta(days=180))
    assert plan.echeance(AUJOURDHUI())['etat'] == 'en-retard'


def test_intervalle_obligatoire_en_base(vehicule):
    with pytest.raises(IntegrityError):
        creer_plan(vehicule, intervalle_km=None, intervalle_jours=None)


# ---- API : plans -----------------------------------------------------------

def test_creation_plan_part_du_compteur(client, jeton_admin, vehicule):
    r = client.post('/api/entretien/plans', {'vehicule': 'qc-4821', 'type': 'vidange', 'libelle': 'Vidange moteur',
                                             'intervalleKm': 8000, 'intervalleJours': 180},
                    format='json', **entete_auth(jeton_admin))
    assert r.status_code == 201, r.data
    p = r.json()['plan']
    assert p['id'].startswith('P-')
    assert p['vehicule'] == 'QC-4821'
    assert p['dernierKm'] == 50000 and p['prochainKm'] == 58000
    assert p['derniereDate'] == AUJOURDHUI().isoformat()
    assert p['echeance']['etat'] == 'a-jour'
    assert p['bonOuvert'] is None


def test_creation_plan_avec_historique(client, jeton_admin, vehicule):
    passe = (AUJOURDHUI() - timedelta(days=200)).isoformat()
    r = client.post('/api/entretien/plans', {'vehicule': 'QC-4821', 'type': 'vidange', 'libelle': 'Vidange',
                                             'intervalleKm': 8000, 'intervalleJours': 180, 'dernierKm': 41000,
                                             'derniereDate': passe},
                    format='json', **entete_auth(jeton_admin))
    assert r.status_code == 201
    assert r.json()['plan']['echeance']['etat'] == 'en-retard'


@pytest.mark.parametrize('champs, cle', [
    ({'intervalleKm': None, 'intervalleJours': None}, 'non_field_errors'),
    ({'intervalleKm': 50}, 'intervalleKm'),
    ({'dernierKm': 60000}, 'dernierKm'),
    ({'derniereDate': '2999-01-01'}, 'derniereDate'),
    ({'vehicule': 'INCONNU'}, 'vehicule'),
    ({'type': 'fusee'}, 'type'),
    ({'libelle': '  '}, 'libelle'),
])
def test_creation_plan_invalide(client, jeton_admin, vehicule, champs, cle):
    donnees = {'vehicule': 'QC-4821', 'type': 'vidange', 'libelle': 'Vidange', 'intervalleKm': 8000}
    donnees.update(champs)
    r = client.post('/api/entretien/plans', donnees, format='json', **entete_auth(jeton_admin))
    assert r.status_code == 400
    assert cle in r.json()


def test_un_seul_plan_actif_par_type(client, jeton_admin, vehicule):
    creer_plan(vehicule)
    r = client.post('/api/entretien/plans', {'vehicule': 'QC-4821', 'type': 'vidange', 'libelle': 'Encore',
                                             'intervalleKm': 5000}, format='json', **entete_auth(jeton_admin))
    assert r.status_code == 400 and 'type' in r.json()
    # Le type 'autre' peut avoir plusieurs plans.
    for libelle in ('Nettoyage', 'Controle extincteur'):
        r = client.post('/api/entretien/plans', {'vehicule': 'QC-4821', 'type': 'autre', 'libelle': libelle,
                                                 'intervalleJours': 30}, format='json', **entete_auth(jeton_admin))
        assert r.status_code == 201


def test_liste_plans_filtres(client, jeton_admin, vehicule):
    autre = Vehicule.objects.create(plaque='QC-1094', modele='Sprinter', kilometrage=1000)
    creer_plan(vehicule)
    creer_plan(autre, dernier_km=0, derniere_date=AUJOURDHUI() - timedelta(days=400))
    inactif = creer_plan(vehicule, type='pneus', libelle='Pneus', actif=False)

    tous = client.get('/api/entretien/plans', **entete_auth(jeton_admin)).json()['plans']
    assert len(tous) == 2
    r = client.get('/api/entretien/plans?vehicule=QC-1094', **entete_auth(jeton_admin))
    assert [p['vehicule'] for p in r.json()['plans']] == ['QC-1094']
    r = client.get('/api/entretien/plans?etat=en-retard', **entete_auth(jeton_admin))
    assert [p['vehicule'] for p in r.json()['plans']] == ['QC-1094']
    r = client.get('/api/entretien/plans?inactifs=1', **entete_auth(jeton_admin))
    assert inactif.code in [p['id'] for p in r.json()['plans']]


def test_modifier_et_desactiver_plan(client, jeton_admin, vehicule):
    plan = creer_plan(vehicule)
    r = client.patch(f'/api/entretien/plans/{plan.code}', {'intervalleKm': 10000, 'type': 'pneus'}, format='json',
                     **entete_auth(jeton_admin))
    assert r.status_code == 200
    assert r.json()['plan']['intervalleKm'] == 10000
    assert r.json()['plan']['type'] == 'vidange'  # le type ne change pas

    r = client.patch(f'/api/entretien/plans/{plan.code}', {'intervalleKm': None, 'intervalleJours': None},
                     format='json', **entete_auth(jeton_admin))
    assert r.status_code == 400

    r = client.delete(f'/api/entretien/plans/{plan.code}', **entete_auth(jeton_admin))
    assert r.status_code == 200 and r.json()['plan']['actif'] is False
    assert PlanEntretien.objects.filter(pk=plan.pk).exists()  # desactive, pas supprime


def test_reactivation_refusee_si_doublon(client, jeton_admin, vehicule):
    ancien = creer_plan(vehicule, actif=False)
    creer_plan(vehicule)
    r = client.patch(f'/api/entretien/plans/{ancien.code}', {'actif': True}, format='json',
                     **entete_auth(jeton_admin))
    assert r.status_code == 409


def test_plan_introuvable(client, jeton_admin):
    for methode in ('get', 'patch', 'delete'):
        r = getattr(client, methode)('/api/entretien/plans/P-999', **entete_auth(jeton_admin))
        assert r.status_code == 404
    assert client.get('/api/entretien/plans/n-importe-quoi', **entete_auth(jeton_admin)).status_code == 404


def test_plans_reserves_admin(client, jeton_admin, vehicule):
    _, jeton = creer_chauffeur_avec_compte(client, jeton_admin)
    assert client.get('/api/entretien/plans', **entete_auth(jeton)).status_code == 403
    assert client.get('/api/entretien/echeances', **entete_auth(jeton)).status_code == 403
    assert client.get('/api/entretien/plans').status_code == 401


# ---- API : echeances -----------------------------------------------------

def test_echeances_triees_par_urgence(client, jeton_admin, vehicule):
    creer_plan(vehicule, type='pneus', libelle='Pneus', intervalle_km=10000, intervalle_jours=None)  # a jour
    bientot = creer_plan(vehicule, type='freins', libelle='Freins', intervalle_km=None, intervalle_jours=365,
                         derniere_date=AUJOURDHUI() - timedelta(days=350))
    retard = creer_plan(vehicule, dernier_km=vehicule.kilometrage - 9000)
    hors_service = Vehicule.objects.create(plaque='QC-HS', modele='X', statut='hors-service')
    creer_plan(hors_service, dernier_km=0, derniere_date=AUJOURDHUI() - timedelta(days=999))

    r = client.get('/api/entretien/echeances', **entete_auth(jeton_admin))
    assert r.status_code == 200
    corps = r.json()
    assert [e['id'] for e in corps['echeances']] == [retard.code, bientot.code]
    assert corps['resume'] == {'enRetard': 1, 'bientot': 1, 'aJour': 1}

    r = client.get('/api/entretien/echeances?tous=1', **entete_auth(jeton_admin))
    assert len(r.json()['echeances']) == 3


def test_echeance_signale_le_bon_ouvert(client, jeton_admin, vehicule):
    plan = creer_plan(vehicule, dernier_km=vehicule.kilometrage - 9000)
    bon = BonTravail.objects.create(vehicule=vehicule, plan=plan, categorie='preventif', type='vidange',
                                    titre='Vidange', date_prevue=AUJOURDHUI())
    r = client.get('/api/entretien/echeances', **entete_auth(jeton_admin))
    assert r.json()['echeances'][0]['bonOuvert'] == bon.code

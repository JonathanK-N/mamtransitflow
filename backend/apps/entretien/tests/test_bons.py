"""
TransitFlow — Tests des bons de travail (cycle de vie, effets sur la flotte, couts, export)
Auteur : Jonathan K-N
"""

import csv
import io
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.entretien import services
from apps.entretien.models import BonTravail, PlanEntretien
from apps.fleet.models import ReleveKilometrage, Vehicule
from apps.maintenance.models import Incident
from conftest import creer_chauffeur_avec_compte, entete_auth

AUJOURDHUI = timezone.localdate


@pytest.fixture
def vehicule(db):
    return Vehicule.objects.create(plaque='QC-4821', modele='Ford Transit', kilometrage=50000)


@pytest.fixture
def plan(vehicule):
    return PlanEntretien.objects.create(vehicule=vehicule, type='vidange', libelle='Vidange moteur',
                                        intervalle_km=8000, intervalle_jours=180, dernier_km=41000,
                                        derniere_date=AUJOURDHUI() - timedelta(days=200))


def creer_bon(client, jeton, **donnees):
    corps = {'vehicule': 'QC-4821', 'type': 'freins', 'titre': 'Plaquettes avant'}
    corps.update(donnees)
    r = client.post('/api/entretien/bons', corps, format='json', **entete_auth(jeton))
    assert r.status_code == 201, r.data
    return r.json()['bon']


def action(client, jeton, bon_id, verbe, **donnees):
    return client.post(f'/api/entretien/bons/{bon_id}/{verbe}', donnees, format='json', **entete_auth(jeton))


def trajet_en_cours(client, jeton_admin, plaque='QC-4821'):
    _, jeton = creer_chauffeur_avec_compte(client, jeton_admin)
    r = client.post('/api/trajets', {'plaque': plaque, 'depart': 'Sherbrooke', 'arrivee': 'Magog',
                                     'debut': '2026-09-12T07:30:00Z', 'finPrevue': '2026-09-12T08:45:00Z'},
                    format='json', **entete_auth(jeton))
    assert r.status_code == 201, r.data
    return r.json()['trajet'], jeton


# ---- Creation --------------------------------------------------------------

def test_creation_libre(client, jeton_admin, vehicule):
    bon = creer_bon(client, jeton_admin, fournisseur='Garage Estrie', coutPieces='120.50', priorite='haute')
    assert bon['id'].startswith('BT-')
    assert bon['categorie'] == 'correctif' and bon['statut'] == 'planifie'
    assert bon['datePrevue'] == AUJOURDHUI().isoformat()
    assert bon['coutPieces'] == 120.5 and bon['coutTotal'] == 120.5
    assert bon['creePar'] == 'Admin Test'
    assert bon['enRetard'] is False


def test_creation_depuis_un_plan(client, jeton_admin, plan):
    bon = creer_bon(client, jeton_admin, vehicule='', type=None, titre='', planId=plan.code)
    assert bon['categorie'] == 'preventif'
    assert bon['type'] == 'vidange' and bon['titre'] == 'Vidange moteur'
    assert bon['planId'] == plan.code and bon['vehicule'] == 'QC-4821'


def test_creation_depuis_plan_vehicule_incoherent(client, jeton_admin, plan):
    Vehicule.objects.create(plaque='QC-1094', modele='X')
    r = client.post('/api/entretien/bons', {'planId': plan.code, 'vehicule': 'QC-1094'}, format='json',
                    **entete_auth(jeton_admin))
    assert r.status_code == 400 and 'vehicule' in r.json()


def test_creation_depuis_plan_desactive(client, jeton_admin, plan):
    plan.actif = False
    plan.save()
    r = client.post('/api/entretien/bons', {'planId': plan.code}, format='json', **entete_auth(jeton_admin))
    assert r.status_code == 400 and 'planId' in r.json()


def test_creation_depuis_un_incident_technique(client, jeton_admin, vehicule):
    trajet, jeton_chauffeur = trajet_en_cours(client, jeton_admin)
    incident = client.post('/api/incidents', {'trajetId': trajet['id'], 'type': 'technique',
                                              'titre': 'Voyant moteur', 'description': 'Voyant orange allume',
                                              'lieu': 'A-10', 'heure': '08:00'},
                           format='json', **entete_auth(jeton_chauffeur)).json()['incident']
    r = client.post('/api/entretien/bons', {'incidentId': incident['id']}, format='json',
                    **entete_auth(jeton_admin))
    assert r.status_code == 201, r.data
    bon = r.json()['bon']
    assert bon['vehicule'] == 'QC-4821'  # deduit du trajet de l incident
    assert bon['titre'] == 'Voyant moteur' and bon['description'] == 'Voyant orange allume'
    assert bon['type'] == 'reparation' and bon['priorite'] == 'haute'
    assert bon['incidentId'] == incident['id']

    # Un seul bon par incident.
    r = client.post('/api/entretien/bons', {'incidentId': incident['id']}, format='json',
                    **entete_auth(jeton_admin))
    assert r.status_code == 400 and 'incidentId' in r.json()


def test_creation_depuis_incident_route_refusee(client, jeton_admin, vehicule):
    trajet, jeton_chauffeur = trajet_en_cours(client, jeton_admin)
    incident = client.post('/api/incidents', {'trajetId': trajet['id'], 'type': 'route', 'titre': 'Bouchon',
                                              'description': 'x', 'lieu': 'x', 'heure': '08:00'},
                           format='json', **entete_auth(jeton_chauffeur)).json()['incident']
    r = client.post('/api/entretien/bons', {'incidentId': incident['id']}, format='json',
                    **entete_auth(jeton_admin))
    assert r.status_code == 400


def test_creation_depuis_incident_sans_trajet_exige_un_vehicule(client, jeton_admin, vehicule):
    fiche, jeton_chauffeur = creer_chauffeur_avec_compte(client, jeton_admin)
    incident = client.post('/api/incidents', {'type': 'technique', 'titre': 'Pneu', 'description': 'x',
                                              'lieu': 'Depot', 'heure': '08:00'},
                           format='json', **entete_auth(jeton_chauffeur)).json()['incident']
    r = client.post('/api/entretien/bons', {'incidentId': incident['id']}, format='json',
                    **entete_auth(jeton_admin))
    assert r.status_code == 400 and 'vehicule' in r.json()
    r = client.post('/api/entretien/bons', {'incidentId': incident['id'], 'vehicule': 'QC-4821'}, format='json',
                    **entete_auth(jeton_admin))
    assert r.status_code == 201


@pytest.mark.parametrize('donnees, cle', [
    ({'vehicule': ''}, 'vehicule'),
    ({'vehicule': 'INCONNU'}, 'vehicule'),
    ({'type': None}, 'type'),
    ({'titre': ''}, 'titre'),
    ({'coutPieces': '-1'}, 'coutPieces'),
    ({'priorite': 'critique'}, 'priorite'),
    ({'planId': 'P-999'}, 'planId'),
    ({'incidentId': 'I-999'}, 'incidentId'),
])
def test_creation_invalide(client, jeton_admin, vehicule, donnees, cle):
    corps = {'vehicule': 'QC-4821', 'type': 'freins', 'titre': 'Freins'}
    corps.update(donnees)
    corps = {k: v for k, v in corps.items() if v is not None}
    r = client.post('/api/entretien/bons', corps, format='json', **entete_auth(jeton_admin))
    assert r.status_code == 400
    assert cle in r.json()


def test_bons_reserves_admin(client, jeton_admin, vehicule):
    _, jeton = creer_chauffeur_avec_compte(client, jeton_admin)
    assert client.get('/api/entretien/bons', **entete_auth(jeton)).status_code == 403
    r = client.post('/api/entretien/bons', {'vehicule': 'QC-4821', 'type': 'freins', 'titre': 'x'}, format='json',
                    **entete_auth(jeton))
    assert r.status_code == 403
    assert client.get('/api/entretien/couts', **entete_auth(jeton)).status_code == 403
    assert client.get('/api/entretien/export.csv', **entete_auth(jeton)).status_code == 403


# ---- Cycle de vie ------------------------------------------------------------

def test_cycle_complet_preventif(client, jeton_admin, plan):
    bon = creer_bon(client, jeton_admin, planId=plan.code)

    r = action(client, jeton_admin, bon['id'], 'demarrer')
    assert r.status_code == 200
    assert r.json()['bon']['statut'] == 'en-cours' and r.json()['bon']['debut']
    assert Vehicule.objects.get(plaque='QC-4821').statut == 'maintenance'

    r = action(client, jeton_admin, bon['id'], 'terminer', kilometrage=50120, coutPieces='89.90',
               coutMainOeuvre='60', fournisseur='Garage Estrie', notes='Huile 5W30')
    assert r.status_code == 200, r.data
    fini = r.json()['bon']
    assert fini['statut'] == 'termine' and fini['fin']
    assert fini['kilometrage'] == 50120
    assert fini['coutTotal'] == 149.9
    assert fini['notesCloture'] == 'Huile 5W30'

    v = Vehicule.objects.get(plaque='QC-4821')
    assert v.statut == 'actif' and v.kilometrage == 50120
    assert v.releves.first().source == 'entretien'
    plan.refresh_from_db()
    assert plan.dernier_km == 50120 and plan.derniere_date == AUJOURDHUI()
    assert plan.echeance(AUJOURDHUI())['etat'] == 'a-jour'


def test_terminer_directement_un_bon_planifie(client, jeton_admin, vehicule):
    bon = creer_bon(client, jeton_admin)
    hier = (AUJOURDHUI() - timedelta(days=1)).isoformat()
    r = action(client, jeton_admin, bon['id'], 'terminer', dateFin=hier, coutPieces='10')
    assert r.status_code == 200
    fini = r.json()['bon']
    assert fini['statut'] == 'termine'
    assert fini['kilometrage'] == 50000  # compteur actuel par defaut
    assert timezone.localtime(BonTravail.objects.get().fin).date().isoformat() == hier
    assert Vehicule.objects.get().statut == 'actif'


def test_terminer_date_future_refusee(client, jeton_admin, vehicule):
    bon = creer_bon(client, jeton_admin)
    demain = (AUJOURDHUI() + timedelta(days=1)).isoformat()
    r = action(client, jeton_admin, bon['id'], 'terminer', dateFin=demain)
    assert r.status_code == 400


def test_terminer_avant_le_debut_refuse(client, jeton_admin, vehicule):
    bon = creer_bon(client, jeton_admin)
    action(client, jeton_admin, bon['id'], 'demarrer')
    avant = (AUJOURDHUI() - timedelta(days=3)).isoformat()
    r = action(client, jeton_admin, bon['id'], 'terminer', dateFin=avant)
    assert r.status_code == 409
    assert BonTravail.objects.get().statut == 'en-cours'


def test_terminer_compteur_incoherent_annule_tout(client, jeton_admin, plan):
    bon = creer_bon(client, jeton_admin, planId=plan.code)
    action(client, jeton_admin, bon['id'], 'demarrer')
    r = action(client, jeton_admin, bon['id'], 'terminer', kilometrage=1000)
    assert r.status_code == 400
    b = BonTravail.objects.get()
    assert b.statut == 'en-cours'
    assert Vehicule.objects.get().statut == 'maintenance'
    plan.refresh_from_db()
    assert plan.dernier_km == 41000


def test_terminer_ferme_l_incident(client, jeton_admin, vehicule):
    trajet, jeton_chauffeur = trajet_en_cours(client, jeton_admin)
    incident = client.post('/api/incidents', {'trajetId': trajet['id'], 'type': 'technique', 'titre': 'Voyant',
                                              'description': 'x', 'lieu': 'x', 'heure': '08:00'},
                           format='json', **entete_auth(jeton_chauffeur)).json()['incident']
    bon = creer_bon(client, jeton_admin, incidentId=incident['id'])
    r = action(client, jeton_admin, bon['id'], 'terminer')
    assert r.status_code == 200
    assert Incident.objects.get().statut == 'traite'


def test_demarrer_refuse_si_vehicule_en_trajet(client, jeton_admin, vehicule):
    trajet_en_cours(client, jeton_admin)
    bon = creer_bon(client, jeton_admin)
    r = action(client, jeton_admin, bon['id'], 'demarrer')
    assert r.status_code == 409
    assert 'en trajet' in r.json()['message']
    assert Vehicule.objects.get().statut == 'actif'


def test_transitions_interdites(client, jeton_admin, vehicule):
    bon = creer_bon(client, jeton_admin)
    action(client, jeton_admin, bon['id'], 'demarrer')
    assert action(client, jeton_admin, bon['id'], 'demarrer').status_code == 409
    action(client, jeton_admin, bon['id'], 'terminer')
    assert action(client, jeton_admin, bon['id'], 'terminer').status_code == 409
    assert action(client, jeton_admin, bon['id'], 'annuler').status_code == 409
    assert action(client, jeton_admin, bon['id'], 'demarrer').status_code == 409


def test_annuler_un_bon_en_cours_libere_le_vehicule(client, jeton_admin, vehicule):
    bon = creer_bon(client, jeton_admin)
    action(client, jeton_admin, bon['id'], 'demarrer')
    r = action(client, jeton_admin, bon['id'], 'annuler', motif='Piece indisponible')
    assert r.status_code == 200
    assert r.json()['bon']['statut'] == 'annule'
    assert r.json()['bon']['notesCloture'] == 'Piece indisponible'
    assert Vehicule.objects.get().statut == 'actif'


def test_vehicule_reste_en_maintenance_tant_qu_un_bon_est_en_cours(client, jeton_admin, vehicule):
    premier = creer_bon(client, jeton_admin)
    second = creer_bon(client, jeton_admin, type='pneus', titre='Pneus hiver')
    action(client, jeton_admin, premier['id'], 'demarrer')
    action(client, jeton_admin, second['id'], 'demarrer')
    action(client, jeton_admin, premier['id'], 'terminer')
    assert Vehicule.objects.get().statut == 'maintenance'
    action(client, jeton_admin, second['id'], 'terminer')
    assert Vehicule.objects.get().statut == 'actif'


def test_vehicule_hors_service_reste_hors_service(client, jeton_admin, vehicule):
    vehicule.statut = 'hors-service'
    vehicule.save()
    bon = creer_bon(client, jeton_admin)
    action(client, jeton_admin, bon['id'], 'demarrer')
    assert Vehicule.objects.get().statut == 'hors-service'
    action(client, jeton_admin, bon['id'], 'terminer')
    assert Vehicule.objects.get().statut == 'hors-service'


def test_vehicule_en_maintenance_ne_peut_pas_partir(client, jeton_admin, vehicule):
    bon = creer_bon(client, jeton_admin)
    action(client, jeton_admin, bon['id'], 'demarrer')
    _, jeton = creer_chauffeur_avec_compte(client, jeton_admin)
    r = client.post('/api/trajets', {'plaque': 'QC-4821', 'depart': 'A', 'arrivee': 'B',
                                     'debut': '2026-09-12T07:30:00Z', 'finPrevue': '2026-09-12T08:45:00Z'},
                    format='json', **entete_auth(jeton))
    assert r.status_code == 409
    assert 'maintenance' in r.json()['message']


def test_plan_non_recale_par_une_intervention_plus_ancienne(vehicule, plan):
    plan.dernier_km, plan.derniere_date = 49000, AUJOURDHUI() - timedelta(days=5)
    plan.save()
    bon = BonTravail.objects.create(vehicule=vehicule, plan=plan, categorie='preventif', type='vidange',
                                    titre='Saisie tardive', date_prevue=AUJOURDHUI() - timedelta(days=30))
    services.terminer(bon, date_fin=AUJOURDHUI() - timedelta(days=30))
    plan.refresh_from_db()
    assert plan.derniere_date == AUJOURDHUI() - timedelta(days=5)


def test_transition_bon_introuvable(client, jeton_admin):
    for verbe in ('demarrer', 'terminer', 'annuler'):
        assert action(client, jeton_admin, 'BT-404', verbe).status_code == 404


# ---- Modification, liste, detail -------------------------------------------

def test_modifier_un_bon_ouvert(client, jeton_admin, vehicule):
    bon = creer_bon(client, jeton_admin)
    demain = (AUJOURDHUI() + timedelta(days=1)).isoformat()
    r = client.patch(f"/api/entretien/bons/{bon['id']}", {'datePrevue': demain, 'fournisseur': 'Pneus Estrie',
                                                         'coutMainOeuvre': 75, 'statut': 'termine'},
                     format='json', **entete_auth(jeton_admin))
    assert r.status_code == 200
    b = r.json()['bon']
    assert b['datePrevue'] == demain and b['fournisseur'] == 'Pneus Estrie' and b['coutMainOeuvre'] == 75
    assert b['statut'] == 'planifie'  # le statut ne se change que par les actions


def test_bon_clos_non_modifiable(client, jeton_admin, vehicule):
    bon = creer_bon(client, jeton_admin)
    action(client, jeton_admin, bon['id'], 'annuler')
    r = client.patch(f"/api/entretien/bons/{bon['id']}", {'titre': 'x'}, format='json', **entete_auth(jeton_admin))
    assert r.status_code == 409


def test_detail_bon(client, jeton_admin, vehicule):
    bon = creer_bon(client, jeton_admin)
    r = client.get(f"/api/entretien/bons/{bon['id'].lower()}", **entete_auth(jeton_admin))
    assert r.status_code == 200 and r.json()['bon']['id'] == bon['id']
    assert client.get('/api/entretien/bons/BT-999', **entete_auth(jeton_admin)).status_code == 404


def test_liste_bons_filtres(client, jeton_admin, vehicule, plan):
    autre = Vehicule.objects.create(plaque='QC-1094', modele='Sprinter')
    passe = (AUJOURDHUI() - timedelta(days=10)).isoformat()
    en_retard = creer_bon(client, jeton_admin, datePrevue=passe, fournisseur='Garage Estrie')
    preventif = creer_bon(client, jeton_admin, planId=plan.code)
    termine = creer_bon(client, jeton_admin, vehicule='QC-1094', type='pneus', titre='Pneus')
    action(client, jeton_admin, termine['id'], 'terminer')
    annule = creer_bon(client, jeton_admin, titre='Annule')
    action(client, jeton_admin, annule['id'], 'annuler')

    def ids(requete):
        r = client.get('/api/entretien/bons' + requete, **entete_auth(jeton_admin))
        assert r.status_code == 200
        return {b['id'] for b in r.json()['bons']}

    assert ids('') == {en_retard['id'], preventif['id'], termine['id'], annule['id']}
    assert ids('?statut=ouverts') == {en_retard['id'], preventif['id']}
    assert ids('?statut=en-retard') == {en_retard['id']}
    assert ids('?statut=termine') == {termine['id']}
    assert ids('?vehicule=qc-1094') == {termine['id']}
    assert ids('?categorie=preventif') == {preventif['id']}
    assert ids('?type=pneus') == {termine['id']}
    assert ids(f'?debut={AUJOURDHUI().isoformat()}') == {preventif['id'], termine['id'], annule['id']}
    assert ids(f'?fin={passe}') == {en_retard['id']}
    assert ids('?recherche=estrie') == {en_retard['id']}
    assert ids(f"?recherche={termine['id']}") == {termine['id']}
    assert autre.bons_travail.count() == 1

    r = client.get('/api/entretien/bons?debut=pas-une-date', **entete_auth(jeton_admin))
    assert r.status_code == 400

    liste = client.get('/api/entretien/bons', **entete_auth(jeton_admin)).json()['bons']
    assert next(b for b in liste if b['id'] == en_retard['id'])['enRetard'] is True


# ---- Couts et export ---------------------------------------------------------

def test_couts_par_periode(client, jeton_admin, vehicule, plan):
    ReleveKilometrage.objects.create(vehicule=vehicule, kilometrage=50000, source='initial')
    autre = Vehicule.objects.create(plaque='QC-1094', modele='Sprinter', kilometrage=1000)
    b1 = creer_bon(client, jeton_admin, planId=plan.code, coutPieces='100', coutMainOeuvre='50')
    action(client, jeton_admin, b1['id'], 'terminer', kilometrage=50500)
    b2 = creer_bon(client, jeton_admin, vehicule='QC-1094', type='pneus', titre='Pneus', coutPieces='400')
    action(client, jeton_admin, b2['id'], 'terminer')
    creer_bon(client, jeton_admin, coutPieces='9999')  # ouvert : non compte
    ancien = BonTravail.objects.create(vehicule=autre, type='freins', titre='Ancien', statut='termine',
                                       date_prevue=AUJOURDHUI() - timedelta(days=800), cout_pieces=Decimal('1000'),
                                       fin=timezone.now() - timedelta(days=800))

    r = client.get('/api/entretien/couts', **entete_auth(jeton_admin))
    assert r.status_code == 200, r.data
    c = r.json()
    assert c['total'] == {'nombre': 2, 'pieces': 500.0, 'mainOeuvre': 50.0, 'total': 550.0}
    assert c['parCategorie']['preventif'] == {'nombre': 1, 'total': 150.0}
    assert c['parCategorie']['correctif'] == {'nombre': 1, 'total': 400.0}
    assert [t['type'] for t in c['parType']] == ['pneus', 'vidange']
    assert c['parType'][0]['libelle'] == 'Pneus'
    transit = next(v for v in c['parVehicule'] if v['vehicule'] == 'QC-4821')
    assert transit['total'] == 150.0 and transit['kmParcourus'] == 500 and transit['coutParKm'] == 0.3

    debut = (AUJOURDHUI() - timedelta(days=900)).isoformat()
    r = client.get(f'/api/entretien/couts?debut={debut}', **entete_auth(jeton_admin))
    assert r.json()['total']['nombre'] == 3
    assert ancien.pk


def test_couts_periode_invalide(client, jeton_admin):
    assert client.get('/api/entretien/couts?debut=2026-12-01&fin=2026-01-01',
                      **entete_auth(jeton_admin)).status_code == 400
    assert client.get('/api/entretien/couts?debut=hier', **entete_auth(jeton_admin)).status_code == 400


def test_export_csv(client, jeton_admin, vehicule):
    creer_bon(client, jeton_admin, titre='=HYPERLINK("http://x")', coutPieces='12.5', fournisseur='Garage Élite')
    r = client.get('/api/entretien/export.csv?statut=tous', **entete_auth(jeton_admin))
    assert r.status_code == 200
    assert r['Content-Type'].startswith('text/csv')
    assert 'attachment' in r['Content-Disposition']
    texte = r.content.decode('utf-8')
    assert texte.startswith('﻿')
    lignes = list(csv.reader(io.StringIO(texte.lstrip('﻿')), delimiter=';'))
    assert lignes[0][0] == 'Bon' and len(lignes) == 2
    ligne = dict(zip(lignes[0], lignes[1]))
    assert ligne['Titre'].startswith("'=")  # formule neutralisee
    assert ligne['Pieces'] == '12,50' and ligne['Fournisseur'] == 'Garage Élite'


def test_km_parcourus_depuis_le_releve_precedant_la_periode(vehicule):
    from apps.entretien.views import _km_parcourus

    ancien = ReleveKilometrage.objects.create(vehicule=vehicule, kilometrage=40000, source='initial')
    ReleveKilometrage.objects.filter(pk=ancien.pk).update(releve_le=timezone.now() - timedelta(days=60))
    ReleveKilometrage.objects.create(vehicule=vehicule, kilometrage=52000, source='trajet')
    debut = AUJOURDHUI() - timedelta(days=30)
    assert _km_parcourus(vehicule.pk, debut, AUJOURDHUI()) == 12000
    assert _km_parcourus(vehicule.pk, debut - timedelta(days=365), debut - timedelta(days=100)) == 0



def test_cout_par_km_non_calcule_si_releves_posterieurs_aux_couts(client, jeton_admin, vehicule):
    """Cas vu en production : bons clotures il y a 30 jours, premier releve
    aujourd hui. 577 $ / 176 km donnait 3,282 $/km : on n affiche rien."""
    BonTravail.objects.create(vehicule=vehicule, type='freins', titre='Freins', statut='termine',
                              date_prevue=AUJOURDHUI() - timedelta(days=30), cout_pieces=Decimal('577.60'),
                              fin=timezone.now() - timedelta(days=30))
    ReleveKilometrage.objects.create(vehicule=vehicule, kilometrage=91540, source='initial')
    ReleveKilometrage.objects.create(vehicule=vehicule, kilometrage=91716, source='trajet')

    ligne = client.get('/api/entretien/couts', **entete_auth(jeton_admin)).json()['parVehicule'][0]
    assert ligne['total'] == 577.6
    assert ligne['kmParcourus'] is None and ligne['coutParKm'] is None
    assert ligne['historiqueKmSuffisant'] is False

    # Un releve anterieur aux couts rend le calcul possible.
    ancien = ReleveKilometrage.objects.create(vehicule=vehicule, kilometrage=79540, source='initial')
    ReleveKilometrage.objects.filter(pk=ancien.pk).update(releve_le=timezone.now() - timedelta(days=45))
    ligne = client.get('/api/entretien/couts', **entete_auth(jeton_admin)).json()['parVehicule'][0]
    assert ligne['kmParcourus'] == 12176 and ligne['coutParKm'] == round(577.6 / 12176, 3)
    assert ligne['historiqueKmSuffisant'] is True

def test_incident_indique_son_bon_de_travail(client, jeton_admin, vehicule):
    trajet, jeton_chauffeur = trajet_en_cours(client, jeton_admin)
    incident = client.post('/api/incidents', {'trajetId': trajet['id'], 'type': 'technique', 'titre': 'Voyant',
                                              'description': 'x', 'lieu': 'x', 'heure': '08:00'},
                           format='json', **entete_auth(jeton_chauffeur)).json()['incident']
    assert incident['bonTravailId'] is None
    bon = creer_bon(client, jeton_admin, incidentId=incident['id'])
    liste = client.get('/api/incidents', **entete_auth(jeton_admin)).json()['incidents']
    assert liste[0]['bonTravailId'] == bon['id']
    detail = client.get(f"/api/incidents/{incident['id']}", **entete_auth(jeton_admin)).json()['incident']
    assert detail['bonTravailId'] == bon['id']

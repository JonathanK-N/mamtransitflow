"""
TransitFlow — Tests du suivi des vehicules (fiche, statut, releves kilometriques)
Auteur : Jonathan K-N
"""

import pytest
from django.utils import timezone

from apps.entretien.models import BonTravail
from apps.fleet.models import ReleveKilometrage, Vehicule
from apps.fleet.services import ECART_MAXIMAL_KM, enregistrer_kilometrage
from conftest import creer_chauffeur_avec_compte, entete_auth


@pytest.fixture
def vehicule(client, jeton_admin):
    r = client.post('/api/vehicules', {'plaque': 'QC-4821', 'modele': 'Ford Transit 2023', 'annee': 2023,
                                       'kilometrage': 48000}, format='json', **entete_auth(jeton_admin))
    assert r.status_code == 201, r.data
    return Vehicule.objects.get(plaque='QC-4821')


# ---- Creation -------------------------------------------------------------

def test_creation_avec_suivi_complet(client, jeton_admin):
    r = client.post('/api/vehicules', {
        'plaque': ' qc-1094 ', 'modele': 'Mercedes Sprinter', 'annee': 2022, 'numeroSerie': 'wdb9066351s123456',
        'kilometrage': 91540, 'miseEnService': '2022-03-01',
    }, format='json', **entete_auth(jeton_admin))
    assert r.status_code == 201, r.data
    v = r.json()['vehicule']
    assert v['plaque'] == 'QC-1094'
    assert v['numeroSerie'] == 'WDB9066351S123456'
    assert v['kilometrage'] == 91540
    assert v['statut'] == 'actif' and v['disponible'] is True
    releve = ReleveKilometrage.objects.get()
    assert releve.source == 'initial' and releve.kilometrage == 91540


def test_creation_minimale_reste_compatible(client, jeton_admin):
    r = client.post('/api/vehicules', {'plaque': 'QC-1', 'modele': 'Ford'}, format='json',
                    **entete_auth(jeton_admin))
    assert r.status_code == 201
    assert r.json()['vehicule']['kilometrage'] == 0


def test_plaque_unique_insensible_a_la_casse(client, jeton_admin, vehicule):
    r = client.post('/api/vehicules', {'plaque': 'qc-4821', 'modele': 'X'}, format='json',
                    **entete_auth(jeton_admin))
    assert r.status_code == 400
    assert 'existe deja' in str(r.json()['plaque'])


@pytest.mark.parametrize('champs, champ_en_erreur', [
    ({'annee': 1950}, 'annee'),
    ({'annee': timezone.localdate().year + 2}, 'annee'),
    ({'numeroSerie': 'COURT'}, 'numeroSerie'),
    ({'numeroSerie': 'IOQ12345678901234'}, 'numeroSerie'),
    ({'kilometrage': -5}, 'kilometrage'),
    ({'miseEnService': '2999-01-01'}, 'miseEnService'),
    ({'plaque': 'QC/48'}, 'plaque'),
    ({'modele': '   '}, 'modele'),
])
def test_creation_refuse_valeurs_invalides(client, jeton_admin, champs, champ_en_erreur):
    donnees = {'plaque': 'QC-9999', 'modele': 'Ford Transit'}
    donnees.update(champs)
    r = client.post('/api/vehicules', donnees, format='json', **entete_auth(jeton_admin))
    assert r.status_code == 400
    assert champ_en_erreur in r.json()


def test_statut_non_modifiable_a_la_creation(client, jeton_admin):
    r = client.post('/api/vehicules', {'plaque': 'QC-2', 'modele': 'X', 'statut': 'maintenance'}, format='json',
                    **entete_auth(jeton_admin))
    assert r.status_code == 201
    assert r.json()['vehicule']['statut'] == 'actif'


# ---- Liste et fiche ------------------------------------------------------

def test_liste_filtre_disponibles(client, jeton_admin, vehicule):
    Vehicule.objects.create(plaque='QC-2', modele='X', statut='hors-service')
    r = client.get('/api/vehicules?disponible=1', **entete_auth(jeton_admin))
    assert [v['plaque'] for v in r.json()['vehicules']] == ['QC-4821']
    r = client.get('/api/vehicules?statut=hors-service', **entete_auth(jeton_admin))
    assert [v['plaque'] for v in r.json()['vehicules']] == ['QC-2']


def test_fiche_vehicule(client, jeton_admin, vehicule):
    creer_chauffeur_avec_compte(client, jeton_admin, plaqueHabituelle='QC-4821')
    r = client.get('/api/vehicules/qc-4821', **entete_auth(jeton_admin))
    assert r.status_code == 200
    corps = r.json()
    assert corps['vehicule']['plaque'] == 'QC-4821'
    assert corps['releves'][0]['kilometrage'] == 48000
    assert corps['chauffeursHabituels'][0]['nom'] == 'Diallo'


def test_fiche_reservee_admin(client, jeton_admin, vehicule):
    _, jeton = creer_chauffeur_avec_compte(client, jeton_admin)
    assert client.get('/api/vehicules/QC-4821', **entete_auth(jeton)).status_code == 403
    assert client.get('/api/vehicules', **entete_auth(jeton)).status_code == 200


def test_fiche_introuvable(client, jeton_admin):
    assert client.get('/api/vehicules/ZZ-0', **entete_auth(jeton_admin)).status_code == 404


# ---- Modification --------------------------------------------------------

def test_patch_informations(client, jeton_admin, vehicule):
    r = client.patch('/api/vehicules/QC-4821', {'modele': 'Ford Transit 350', 'annee': 2024}, format='json',
                     **entete_auth(jeton_admin))
    assert r.status_code == 200
    assert r.json()['vehicule']['modele'] == 'Ford Transit 350'


def test_patch_ignore_plaque_et_compteur(client, jeton_admin, vehicule):
    r = client.patch('/api/vehicules/QC-4821', {'plaque': 'AUTRE', 'kilometrage': 1}, format='json',
                     **entete_auth(jeton_admin))
    assert r.status_code == 200
    vehicule.refresh_from_db()
    assert vehicule.plaque == 'QC-4821' and vehicule.kilometrage == 48000


def test_patch_hors_service_puis_actif(client, jeton_admin, vehicule):
    r = client.patch('/api/vehicules/QC-4821', {'statut': 'hors-service'}, format='json', **entete_auth(jeton_admin))
    assert r.json()['vehicule']['statut'] == 'hors-service'
    r = client.patch('/api/vehicules/QC-4821', {'statut': 'actif'}, format='json', **entete_auth(jeton_admin))
    assert r.json()['vehicule']['statut'] == 'actif'


def test_patch_statut_maintenance_manuel_refuse(client, jeton_admin, vehicule):
    r = client.patch('/api/vehicules/QC-4821', {'statut': 'maintenance'}, format='json', **entete_auth(jeton_admin))
    assert r.status_code == 400


def test_hors_service_refuse_pendant_un_trajet(client, jeton_admin, vehicule):
    _, jeton = creer_chauffeur_avec_compte(client, jeton_admin)
    r = client.post('/api/trajets', {'plaque': 'QC-4821', 'depart': 'A', 'arrivee': 'B',
                                     'debut': '2026-09-12T07:30:00Z', 'finPrevue': '2026-09-12T08:45:00Z'},
                    format='json', **entete_auth(jeton))
    assert r.status_code == 201
    r = client.patch('/api/vehicules/QC-4821', {'statut': 'hors-service'}, format='json', **entete_auth(jeton_admin))
    assert r.status_code == 409


def test_remise_en_service_refusee_si_bon_en_cours(client, jeton_admin, vehicule):
    BonTravail.objects.create(vehicule=vehicule, type='freins', titre='Freins', date_prevue=timezone.localdate(),
                              statut='en-cours')
    vehicule.statut = 'maintenance'
    vehicule.save()
    r = client.patch('/api/vehicules/QC-4821', {'statut': 'actif'}, format='json', **entete_auth(jeton_admin))
    assert r.status_code == 409


def test_patch_reserve_admin(client, jeton_admin, vehicule):
    _, jeton = creer_chauffeur_avec_compte(client, jeton_admin)
    r = client.patch('/api/vehicules/QC-4821', {'modele': 'X'}, format='json', **entete_auth(jeton))
    assert r.status_code == 403


# ---- Releves kilometriques -----------------------------------------------

def test_releve_manuel(client, jeton_admin, vehicule):
    r = client.post('/api/vehicules/QC-4821/kilometrage', {'kilometrage': 48500, 'note': 'Plein'}, format='json',
                    **entete_auth(jeton_admin))
    assert r.status_code == 201
    assert r.json()['vehicule']['kilometrage'] == 48500
    assert r.json()['releve']['source'] == 'manuel'
    assert r.json()['releve']['auteur'] == 'Admin Test'
    historique = client.get('/api/vehicules/QC-4821/kilometrage', **entete_auth(jeton_admin)).json()['releves']
    assert [h['kilometrage'] for h in historique] == [48500, 48000]


def test_releve_inferieur_refuse(client, jeton_admin, vehicule):
    r = client.post('/api/vehicules/QC-4821/kilometrage', {'kilometrage': 47000}, format='json',
                    **entete_auth(jeton_admin))
    assert r.status_code == 400
    assert 'inferieur' in r.json()['kilometrage'][0]
    vehicule.refresh_from_db()
    assert vehicule.kilometrage == 48000


def test_releve_identique_ne_cree_rien(client, jeton_admin, vehicule):
    r = client.post('/api/vehicules/QC-4821/kilometrage', {'kilometrage': 48000}, format='json',
                    **entete_auth(jeton_admin))
    assert r.status_code == 200 and r.json()['releve'] is None
    assert vehicule.releves.count() == 1


def test_releve_saut_improbable_refuse(client, jeton_admin, vehicule):
    r = client.post('/api/vehicules/QC-4821/kilometrage', {'kilometrage': 48000 + ECART_MAXIMAL_KM + 1},
                    format='json', **entete_auth(jeton_admin))
    assert r.status_code == 400


def test_premier_releve_sans_limite_d_ecart(db):
    v = Vehicule.objects.create(plaque='QC-X', modele='X')
    enregistrer_kilometrage(v, 250000, source='manuel')
    v.refresh_from_db()
    assert v.kilometrage == 250000


def test_releve_reserve_admin(client, jeton_admin, vehicule):
    _, jeton = creer_chauffeur_avec_compte(client, jeton_admin)
    r = client.post('/api/vehicules/QC-4821/kilometrage', {'kilometrage': 49000}, format='json',
                    **entete_auth(jeton))
    assert r.status_code == 403

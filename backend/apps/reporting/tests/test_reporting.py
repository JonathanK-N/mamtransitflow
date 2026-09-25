"""
TransitFlow — Tests de l app reporting (indicateurs)
Auteur : Jonathan K-N
"""

from datetime import timedelta

from django.utils import timezone

from apps.fleet.models import Vehicule
from conftest import creer_chauffeur_avec_compte, entete_auth


def test_indicateurs_reserve_admin(client, jeton_admin):
    _, jeton = creer_chauffeur_avec_compte(client, jeton_admin)
    r = client.get('/api/indicateurs', **entete_auth(jeton))
    assert r.status_code == 403


def test_indicateurs_valeurs(client, jeton_admin):
    Vehicule.objects.create(plaque='QC-4821', modele='Ford Transit 2023')
    aujourdhui = timezone.localdate()
    bientot = (aujourdhui + timedelta(days=30)).isoformat()
    plus_tard = (aujourdhui + timedelta(days=400)).isoformat()
    fiche1, jeton1 = creer_chauffeur_avec_compte(client, jeton_admin, permisExpiration=bientot)
    creer_chauffeur_avec_compte(client, jeton_admin, courriel='m.traore@transitflow.ca', prenom='Moussa',
                                 nom='Traore', permisExpiration=plus_tard, statut='hors-service')

    trajet = client.post('/api/trajets', {
        'plaque': 'QC-4821', 'depart': 'Sherbrooke', 'arrivee': 'Magog',
        'debut': '2026-09-12T07:30:00Z', 'finPrevue': '2026-09-12T08:45:00Z'
    }, format='json', **entete_auth(jeton1)).json()['trajet']
    client.post('/api/incidents', {
        'trajetId': trajet['id'], 'type': 'route', 'titre': 'x', 'description': 'x', 'lieu': 'x', 'heure': '09:00'
    }, format='json', **entete_auth(jeton1))

    r = client.get('/api/indicateurs', **entete_auth(jeton_admin))
    assert r.status_code == 200
    k = r.json()['indicateurs']
    assert k['chauffeursActifs'] == 1  # le 2e est 'hors-service'
    assert k['trajetsEnCours'] == 1
    assert k['incidentsOuverts'] == 1
    assert k['permisAExpirer'] == 1  # dans 30 jours : oui ; dans 400 jours : non


def test_sante(client):
    r = client.get('/api/sante')
    assert r.status_code == 200
    assert r.json()['ok'] is True


def test_indicateurs_entretien(client, jeton_admin):
    from apps.entretien.models import BonTravail, PlanEntretien

    aujourdhui = timezone.localdate()
    actif = Vehicule.objects.create(plaque='QC-1', modele='X', kilometrage=10000)
    atelier = Vehicule.objects.create(plaque='QC-2', modele='X', statut='maintenance')
    retire = Vehicule.objects.create(plaque='QC-3', modele='X', statut='hors-service')
    PlanEntretien.objects.create(vehicule=actif, type='vidange', libelle='V', intervalle_km=5000,
                                 dernier_km=4000, derniere_date=aujourdhui)                       # en retard
    PlanEntretien.objects.create(vehicule=atelier, type='inspection', libelle='I', intervalle_jours=365,
                                 derniere_date=aujourdhui - timedelta(days=350))                  # bientot
    PlanEntretien.objects.create(vehicule=retire, type='vidange', libelle='V', intervalle_jours=10,
                                 derniere_date=aujourdhui - timedelta(days=100))                  # ignore
    BonTravail.objects.create(vehicule=atelier, type='freins', titre='F', date_prevue=aujourdhui, statut='en-cours')
    BonTravail.objects.create(vehicule=actif, type='freins', titre='F', date_prevue=aujourdhui, statut='termine')

    k = client.get('/api/indicateurs', **entete_auth(jeton_admin)).json()['indicateurs']
    assert k['vehiculesDisponibles'] == 1
    assert k['vehiculesEnMaintenance'] == 1
    assert k['entretiensEnRetard'] == 1
    assert k['entretiensBientot'] == 1
    assert k['bonsOuverts'] == 1

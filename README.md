# TransitFlow

Logiciel de gestion de flotte pour une entreprise de transport par navette
(trajets interurbains) : chauffeurs, vehicules, trajets, arrets, incidents,
entretien de la flotte (plans preventifs, bons de travail, couts) et
suivi GPS en direct sur une carte (Leaflet / OpenStreetMap).

Backend : Django + Django REST Framework, organise en apps independantes
(comme les modules d un ERP). Front-end (a venir : Vue.js) actuellement en
HTML/CSS/JS, servi par ce meme serveur Django.

## Demarrage (developpement)

1. **Base de donnees** — rien a faire : une base SQLite locale est creee
   automatiquement dans `backend/data/`. Pour travailler sur PostgreSQL
   comme en production :
   ```
   docker compose up -d
   cp .env.example .env
   ```
   (`.env` est lu automatiquement par Django.)

2. **Dependances Python** (3.12) :
   ```
   pip install -r backend/requirements-dev.txt
   ```

3. **Migrations** (cree les tables), depuis `backend/` :
   ```
   python manage.py migrate
   ```

4. **Donnees** — au choix :
   - un jeu de demonstration complet (vehicules, chauffeurs, trajets,
     incidents ; mot de passe `Transit-Demo-2026`) :
     ```
     python manage.py seed_demo
     ```
     Administrateur : `a.tremblay@transitflow.ca` ; chauffeurs :
     `a.diallo@`, `m.traore@`, `s.fortin@`, `m.barry@transitflow.ca`.
   - ou seulement un premier compte administrateur :
     ```
     python manage.py bootstrap admin@exemple.com "mot-de-passe-sur" "Prenom Nom"
     ```

5. **Lancer le serveur** :
   ```
   python manage.py runserver 5000
   ```
   Puis ouvrir http://127.0.0.1:5000/ — le front-end et l API sont servis
   par le meme serveur. Le site d administration integre de Django est sur
   http://127.0.0.1:5000/django-admin/ (pas `/admin/`, deja pris par les
   pages HTML de l espace administrateur).

## Tests

Depuis `backend/` :
```
python -m pytest -q
```
Les memes tests tournent sur GitHub Actions a chaque push, sur PostgreSQL
(`.github/workflows/tests.yml`).

Test de bout en bout dans un vrai navigateur (module d entretien, cote
administrateur et chauffeur, y compris l affichage mobile) : voir l en-tete
de [`e2e/parcours_entretien.py`](e2e/parcours_entretien.py). Il se lance
sur une base de demonstration neuve (`seed_demo`) avec le serveur demarre.

## Deploiement

Sur Railway : voir [DEPLOIEMENT.md](DEPLOIEMENT.md).

## API

Toutes les routes sont sous `/api/` et, sauf connexion et sante, exigent
l entete `Authorization: Bearer <jeton>`. Un administrateur (groupe
`fleet.admin`) voit toutes les donnees ; un chauffeur (groupe
`fleet.driver`) uniquement sa fiche, ses trajets et ses incidents.

| Route | Role |
|---|---|
| `POST auth/connexion` | `{courriel, motDePasse, role}` → `{session, jeton, rafraichissement}` |
| `POST auth/rafraichir` | `{rafraichissement}` → nouveau `jeton` |
| `POST auth/deconnexion` | invalide le jeton de rafraichissement |
| `GET auth/session` | session du jeton envoye |
| `POST auth/comptes` | cree un compte de connexion (admin) |
| `GET/POST chauffeurs` | liste (`?statut=`, `?recherche=`) / creation avec compte (admin) |
| `GET/PATCH chauffeurs/<c1>` | fiche ; un chauffeur ne modifie que telephone et adresse |
| `GET/POST vehicules` | flotte (`?statut=`, `?disponible=1`) / ajout avec compteur initial (admin) |
| `GET/PATCH vehicules/<plaque>` | fiche + releves / modification, mise hors service (admin) |
| `GET/POST vehicules/<plaque>/kilometrage` | historique / nouveau releve du compteur (admin) |
| `GET/POST trajets` | liste (`?statut=`, `?chauffeurId=`) / demarrage (chauffeur, un seul en cours) |
| `GET trajets/<T-1>` · `trajets/en-cours/<c1>` | detail / trajet en cours d un chauffeur |
| `POST trajets/<T-1>/arrets` · `trajets/<T-1>/terminer` | ajout d arret / cloture (chauffeur ou admin), `{kilometrage}` facultatif |
| `GET/POST incidents` | liste (`?type=`, `?statut=`, `?chauffeurId=`) / signalement (chauffeur) |
| `GET incidents/<I-1>` · `POST incidents/<I-1>/traiter` | detail / traitement (admin) |
| `GET/POST entretien/plans` | plans preventifs (`?vehicule=`, `?etat=`) / creation (admin) |
| `GET/PATCH/DELETE entretien/plans/<P-1>` | detail / modification / retrait (admin) |
| `GET entretien/echeances` | entretiens en retard ou proches, les plus urgents d abord (admin) |
| `GET/POST entretien/bons` | bons de travail (`?statut=`, `?vehicule=`, `?categorie=`, `?type=`, `?debut=`, `?fin=`, `?recherche=`) / creation libre, depuis un plan (`planId`) ou un incident technique (`incidentId`) (admin) |
| `GET/PATCH entretien/bons/<BT-1>` | detail / modification d un bon ouvert (admin) |
| `POST entretien/bons/<BT-1>/demarrer` · `terminer` · `annuler` | cycle de vie du bon (admin) |
| `GET entretien/couts` | couts des bons termines par vehicule, type et categorie (`?debut=`, `?fin=`) (admin) |
| `GET entretien/export.csv` | export CSV (Excel) des bons, memes filtres que la liste (admin) |
| `POST trajets/<T-1>/positions` | lot de positions GPS `{positions: [{lat, lng, precision, vitesse, cap, horodatage}]}` (chauffeur du trajet en cours ; 200 points max, 30 envois/min) |
| `GET trajets/<T-1>/parcours` | trace GPS du trajet, distance, vitesses moyenne et maximale (admin, ou chauffeur du trajet) |
| `GET suivi/en-direct` | dernier point et etat du signal de chaque trajet en cours (admin) |
| `GET indicateurs` | indicateurs du tableau de bord (admin) |
| `GET sante` | verification que le serveur repond |

## Entretien de la flotte

- **Compteur** : chaque vehicule a un compteur kilometrique historise
  (saisie de l administrateur, arrivee d un chauffeur, sortie d atelier).
  Il ne recule jamais ; un saut de plus de 20 000 km est refuse.
- **Plans preventifs** : "vidange tous les 8 000 km ou 180 jours". La
  premiere limite atteinte declenche l echeance ; l alerte "bientot" part a
  20 % de l intervalle restant (au plus 1 000 km / 30 jours).
- **Bons de travail** : preventifs (depuis un plan) ou correctifs (libres
  ou depuis un incident technique). `planifie -> en-cours -> termine`, ou
  `annule`. Pendant l intervention le vehicule passe "en maintenance" et
  ne peut plus partir en trajet ; a la cloture, le compteur, le plan et
  l incident d origine sont mis a jour et le vehicule redevient actif.
- **Couts** : pieces et main-d oeuvre par bon, synthese par periode,
  vehicule (avec cout au kilometre) et type d intervention, export CSV.

## Suivi GPS en direct

- **Chauffeur** : sur la page *Trajet en cours*, le telephone partage sa
  position (API de geolocalisation du navigateur, HTTPS obligatoire). Les
  points sont envoyes par lots toutes les 10 s ; en cas de coupure de
  reseau ils sont gardes et renvoyes au retour du signal (le serveur
  ignore les doublons). L ecran est maintenu allume quand le navigateur le
  permet. Le partage s arrete a l arrivee.
- **Limite a connaitre** : une page web ne peut pas localiser un telephone
  dont l ecran est eteint ou le navigateur en arriere-plan. Pour un suivi
  en arriere-plan, il faudra une application mobile (etape ulterieure) ;
  l API actuelle est deja prete a la recevoir.
- **Administrateur** : *Carte* affiche tous les vehicules en route
  (rafraichie toutes les 5 s, mise en pause quand l onglet est cache), avec
  l etat du signal (en ligne < 1 min, faible < 5 min, perdu au-dela) et la
  trace du vehicule selectionne. La fiche d un trajet montre son parcours,
  la distance et les vitesses.
- **Donnees personnelles** : les positions des trajets termines depuis
  plus de 90 jours sont supprimees a chaque demarrage du serveur
  (`python manage.py purger_positions`, duree reglable par
  `TF_GPS_RETENTION_JOURS`).
- **Choix technique** : des requetes HTTP courtes plutot que des
  WebSockets. Le fonctionnement reste identique sur l hebergement actuel
  (gunicorn, sans Redis) et supporte plusieurs dizaines de vehicules ; le
  passage a Django Channels ne changerait que le transport.

Test de bout en bout : [`e2e/parcours_gps.py`](e2e/parcours_gps.py)
(position du telephone simulee, coupure de reseau, localisation refusee).

## Structure

```
backend/
  manage.py
  transitflow/    configuration du projet Django (settings, urls)
  apps/           un dossier par module metier (comptes, drivers, fleet,
                  dispatch, maintenance [incidents], entretien, suivi [GPS],
                  reporting) — chacun a ses modeles,
                  serializers et routes, independamment des autres ; les
                  tests de chaque app vivent dans son propre dossier tests/
admin/            pages de l espace administrateur
chauffeur/        pages de l espace chauffeur
assets/           CSS, JS et images du front-end
e2e/              test de bout en bout dans un navigateur (Playwright)
railway.json      configuration du deploiement Railway
```

Voir le plan de developpement pour la suite (suivi GPS en direct via
Django Channels, migration du front-end vers Vue.js, etc.).

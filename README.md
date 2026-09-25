# TransitFlow

Logiciel de gestion de flotte pour une entreprise de transport par navette
(trajets interurbains) : chauffeurs, vehicules, trajets, arrets, incidents,
et (a venir) suivi GPS en direct sur une carte.

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
| `GET/POST vehicules` | flotte / ajout (admin) |
| `GET/POST trajets` | liste (`?statut=`, `?chauffeurId=`) / demarrage (chauffeur, un seul en cours) |
| `GET trajets/<T-1>` · `trajets/en-cours/<c1>` | detail / trajet en cours d un chauffeur |
| `POST trajets/<T-1>/arrets` · `trajets/<T-1>/terminer` | ajout d arret / cloture (chauffeur ou admin) |
| `GET/POST incidents` | liste (`?type=`, `?statut=`, `?chauffeurId=`) / signalement (chauffeur) |
| `GET incidents/<I-1>` · `POST incidents/<I-1>/traiter` | detail / traitement (admin) |
| `GET indicateurs` | indicateurs du tableau de bord (admin) |
| `GET sante` | verification que le serveur repond |

## Structure

```
backend/
  manage.py
  transitflow/    configuration du projet Django (settings, urls)
  apps/           un dossier par module metier (comptes, drivers, fleet,
                  dispatch, maintenance, reporting) — chacun a ses modeles,
                  serializers et routes, independamment des autres ; les
                  tests de chaque app vivent dans son propre dossier tests/
admin/            pages de l espace administrateur
chauffeur/        pages de l espace chauffeur
assets/           CSS, JS et images du front-end
railway.json      configuration du deploiement Railway
```

Voir le plan de developpement pour la suite (suivi GPS en direct via
Django Channels, migration du front-end vers Vue.js, etc.).

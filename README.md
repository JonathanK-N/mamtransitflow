# TransitFlow

Logiciel de gestion de flotte pour une entreprise de transport par navette
(trajets interurbains) : chauffeurs, vehicules, trajets, incidents, et
(a venir) suivi GPS en direct sur une carte.

## Demarrage (developpement)

1. **Base de donnees** — Postgres via Docker (recommande) :
   ```
   docker compose up -d
   cp .env.example .env
   ```
   Ou sans Docker : ne rien faire, une base SQLite locale est utilisee par
   defaut (voir `backend/settings.py`).

2. **Dependances Python** :
   ```
   pip install -r backend/requirements.txt
   ```

3. **Migrations** (cree les tables) :
   ```
   python -m alembic -c backend/alembic.ini upgrade head
   ```

4. **Premier compte administrateur** (une seule fois par installation) :
   ```
   python -m backend.scripts.bootstrap admin@exemple.com "mot-de-passe-sur" "Prenom Nom"
   ```

5. **Lancer le serveur** :
   ```
   python -m uvicorn backend.main:app --reload --port 5000
   ```
   Puis ouvrir http://127.0.0.1:5000/ — le front-end et l API sont servis
   par le meme serveur.

## Tests

```
python -m pytest backend/tests -q
```

## Structure

```
backend/
  apps/         un dossier par module metier (auth, drivers, fleet,
                dispatch, maintenance, reporting) — chacun a ses modeles,
                schemas et routes, independamment des autres
  alembic/      migrations de la base de donnees
  scripts/      outils d exploitation (ex. bootstrap.py)
  tests/        tests automatises (pytest)
admin/          pages de l espace administrateur
chauffeur/      pages de l espace chauffeur
assets/         CSS, JS et images du front-end
```

Voir le plan de developpement pour la suite (suivi GPS en direct, migration
du front-end vers Vue.js, etc.).

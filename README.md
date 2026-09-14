# TransitFlow

Logiciel de gestion de flotte pour une entreprise de transport par navette
(trajets interurbains) : chauffeurs, vehicules, trajets, incidents, et
(a venir) suivi GPS en direct sur une carte.

Backend : Django + Django REST Framework, organise en apps independantes
(comme les modules d un ERP). Front-end (a venir : Vue.js) actuellement en
HTML/CSS/JS, servi par ce meme serveur Django.

## Demarrage (developpement)

1. **Base de donnees** — Postgres via Docker (recommande) :
   ```
   docker compose up -d
   cp .env.example .env
   ```
   Ou sans Docker : ne rien faire, une base SQLite locale est utilisee par
   defaut (voir `backend/transitflow/settings.py`).

2. **Dependances Python** :
   ```
   pip install -r backend/requirements.txt
   ```

3. **Migrations** (cree les tables), depuis `backend/` :
   ```
   python manage.py migrate
   ```

4. **Premier compte administrateur** (une seule fois par installation) :
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
```

Voir le plan de developpement pour la suite (suivi GPS en direct via
Django Channels, migration du front-end vers Vue.js, etc.).

# Deploiement sur Railway

TransitFlow se deploie comme **un seul service Railway** (Django sert l API
et les pages du front-end) relie a **une base PostgreSQL Railway**.

## Fichiers utilises par Railway

| Fichier | Role |
|---|---|
| `railway.json` | Build, commande de demarrage (migrations incluses), sonde de sante |
| `requirements.txt` | Dependances de production (a la racine : Railpack ne copie que ce fichier avant l installation) |
| `.python-version` | Version de Python (3.12) |
| `.github/workflows/tests.yml` | Tests automatiques (option "Wait for CI") |

Ce que fait `railway.json` a chaque deploiement :

1. **Build** : installation des dependances, puis `collectstatic` (fichiers
   CSS/JS de `/django-admin/`, servis par WhiteNoise).
2. **Au demarrage du conteneur**, avant gunicorn (`manage.py preparer_deploiement`) :
   `migrate` (tables a jour), puis
   `bootstrap --depuis-env` (groupes de permission + premier
   administrateur s il n existe pas encore).
3. **Demarrage** : `gunicorn` sur le port fourni par Railway.
4. **Sonde de sante** : `GET /api/sante` doit repondre 200 avant que le
   trafic ne bascule sur la nouvelle version.

## Mise en place (une seule fois)

1. Sur [railway.com](https://railway.com), **New Project → Deploy from
   GitHub repo** et choisir `barm2734/mamtransitflow`.
2. Dans le service cree, **Settings → Source → Branch** : choisir la
   branche a deployer (`erp`, puis `main` une fois fusionnee).
3. Dans le projet, **+ New → Database → PostgreSQL**.
4. Dans le service de l application, onglet **Variables**, ajouter :

   | Variable | Valeur |
   |---|---|
   | `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (reference au service Postgres) |
   | `TF_DEBUG` | `0` |
   | `TF_SECRET_KEY` | une valeur aleatoire, voir ci-dessous |
   | `TF_ADMIN_COURRIEL` | courriel du premier administrateur |
   | `TF_ADMIN_MOT_DE_PASSE` | son mot de passe (12 caracteres ou plus) |
   | `TF_ADMIN_NOM` | son nom affiche (ex. `Alex Tremblay`) |

   **N importez pas les variables suggerees par Railway depuis
   `.env.example`** : ce sont des valeurs de developpement (base sur
   `localhost`, mode debug). Si c est deja fait, supprimez `TF_DATABASE_URL`,
   `TF_ALLOWED_HOSTS` et `TF_DEBUG`, et remplacez `TF_SECRET_KEY`. Par
   securite, l application refuse de demarrer avec une base `localhost` ou
   une cle d exemple, et ignore `TF_DEBUG=1` dans l environnement
   `production`.

   Generer la cle secrete :
   ```
   python -c "import secrets; print(secrets.token_urlsafe(50))"
   ```

5. **Settings → Networking → Generate Domain** pour obtenir une adresse
   publique `xxx.up.railway.app`. Elle est autorisee automatiquement par
   Django (`RAILWAY_PUBLIC_DOMAIN`), rien a recopier.
6. Facultatif : **Settings → Deploy → Wait for CI** pour ne deployer que
   si les tests GitHub Actions passent.

Le premier deploiement se lance tout seul. Ouvrir ensuite l adresse
publique et se connecter avec `TF_ADMIN_COURRIEL` / `TF_ADMIN_MOT_DE_PASSE`
(onglet **Administrateur**).

## Apres le premier deploiement

- **Vehicules** : les ajouter depuis l ecran *Vehicules* (la flotte demarre vide).
- **Chauffeurs** : *Chauffeurs → + Nouveau chauffeur*. Le compte de connexion
  est cree en meme temps ; sans mot de passe saisi, un mot de passe est
  genere et affiche **une seule fois**, a transmettre au chauffeur.
- **Mot de passe administrateur** : `TF_ADMIN_MOT_DE_PASSE` ne sert qu a la
  creation du compte ; le changer ensuite dans `/django-admin/` n est pas
  ecrase par les deploiements suivants. Le journal de demarrage indique
  toujours le compte concerne (`Compte administrateur cree : ...` ou
  `le compte ... existe deja`) : verifier son orthographe en cas d echec
  de connexion.
- **Connexion administrateur impossible** (mot de passe perdu, ou
  `TF_ADMIN_MOT_DE_PASSE` modifie apres la creation du compte) : ajouter
  `TF_ADMIN_REINITIALISER=1` aux variables du service et redeployer. Le
  compte `TF_ADMIN_COURRIEL` reprend le mot de passe `TF_ADMIN_MOT_DE_PASSE`
  et est reactive (le journal affiche `Compte administrateur ... reinitialise`).
  **Retirer ensuite la variable.** Les espaces en debut et fin de ces
  variables sont ignores.
- **Donnees de demonstration** (environnement de test uniquement) :
  ```
  railway run python backend/manage.py seed_demo --force
  ```
  (mot de passe de tous les comptes : `Transit-Demo-2026`, modifiable avec
  `--mot-de-passe`).

## Variables facultatives

| Variable | Defaut | Effet |
|---|---|---|
| `TF_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Domaines supplementaires (ex. domaine personnalise) |
| `TF_CSRF_TRUSTED_ORIGINS` | — | Origines HTTPS supplementaires pour `/django-admin/` |
| `TF_JETON_MINUTES` | `60` | Duree du jeton d acces (le jeton de rafraichissement dure 7 jours) |
| `TF_HSTS_SECONDS` | `3600` | Duree HSTS ; augmenter (ex. `31536000`) une fois le domaine stable |
| `WEB_CONCURRENCY` | `2` | Nombre de processus gunicorn |
| `TF_LOG_LEVEL` | `INFO` | Niveau des journaux |

## Domaine personnalise

**Settings → Networking → Custom Domain**, puis ajouter le domaine a
`TF_ALLOWED_HOSTS` et `https://<domaine>` a `TF_CSRF_TRUSTED_ORIGINS`.

## Depannage

- **Le deploiement echoue a la sonde de sante** : consulter les journaux de
  deploiement ; le plus souvent `TF_SECRET_KEY` est absente alors que
  `TF_DEBUG=0` (Django refuse alors de demarrer, volontairement).
- **Erreur de base de donnees au demarrage** (ou erreur 500 a la connexion) : verifier que
  `DATABASE_URL` reference bien le service Postgres du meme projet.
- **Page `/django-admin/` sans style** : le build n a pas execute
  `collectstatic` ; verifier `railway.json`.

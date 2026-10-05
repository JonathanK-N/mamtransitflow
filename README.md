# TransitFlow ERP

TransitFlow est un ERP multi-entreprise pour le transport de marchandises, voyageurs, navettes et activités spécialisées. La version SaaS utilise Django/DRF, PostgreSQL, Vue 3, une PWA et un canal temps réel ASGI/Redis.

## Architecture actuelle

- `backend/apps/erp` : organisations, adhésions, permissions, personnel, flotte, commandes, missions, GPS, clients/CRM, devis, facturation, règlements, comptabilité, atelier, stocks, documents, portail, messagerie et notifications.
- `frontend/src` : application Vue/PWA, espace entreprise, Centre d’exploitation, espace chauffeur et portail client.
- API `/api/v2/`, canal `/ws/activity`, santé `/api/sante`.
- Django sert l’interface compilée. Les fichiers privés sont téléchargés par les routes autorisées, pas depuis un dossier public.
- Chaque objet métier appartient à une organisation. Les API contrôlent l’adhésion active, le rôle et les applications activées ; les références interentreprises sont également contrôlées par PostgreSQL.
- Montants en Decimal, séquences serveur, actions sensibles transactionnelles. Les modules historiques hors `apps/erp` restent présents pour compatibilité ; `TF_LEGACY_ENABLED=0` désactive leurs routes globales dans le SaaS.

## Développement

Python 3.12, Node 22 et pnpm 11.25.0 sont les versions de recette CI. PostgreSQL et Redis sont nécessaires pour vérifier la concurrence et le temps réel comme en production. SQLite est utile localement mais ne prouve pas les verrous PostgreSQL.

```sh
python -m venv .venv
# Activer .venv selon le système.
pip install -r requirements-dev.txt
npm install --global pnpm@11.25.0
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend build
python backend/manage.py migrate
python backend/manage.py collectstatic --noinput
python -m uvicorn transitflow.asgi:application --app-dir backend --host 127.0.0.1 --port 8000
```

Définir `DATABASE_URL`, `TF_REDIS_URL` et les variables locales décrites dans `.env.example`. Pour créer une entreprise vide et son propriétaire, ouvrir `/commencer`. Pour rejoindre une entreprise existante, accepter son invitation ; ne pas créer une seconde entreprise.

## Tests et livraison

```sh
python backend/manage.py check
python backend/manage.py makemigrations --check --dry-run
cd backend
python -m pytest apps/erp/tests -q
cd ../frontend
pnpm exec playwright install chromium webkit
pnpm exec playwright test
```

Les tests navigateur nécessitent le serveur de recette, les données isolées et `TF_TEST_URL` si son URL diffère de `http://127.0.0.1:8000`. Ne pas lancer toute la suite sur des données clients réelles. Les tests de courriel simulent le transport.

La CI générale et la recette ERP sont dans `.github/workflows`. La recette utilise PostgreSQL/Redis, deux workers ASGI et cinq profils navigateur, puis contrôle l’image de production et le stockage privé. Les résultats effectivement exécutés figurent dans les rapports ; un module existant n’est pas automatiquement un module validé.

Railway déploie actuellement la branche `transitflow-tests` du dépôt `JonathanK-N/mamtransitflow`. `transitflow-erp` est la branche d’intégration. Le service utilise une base PostgreSQL persistante et un volume `/data` pour les fichiers privés. Vérifier la version déployée, les migrations, `/api/sante` et les logs après chaque livraison. La persistance d’un volume ne prouve pas qu’une sauvegarde restaurable est configurée.

## Documentation

- [Architecture et sécurité](docs/ARCHITECTURE_ERP.md)
- [Installation, configuration et exploitation](docs/EXPLOITATION_ERP.md)
- [Centre d’exploitation](docs/Centre-exploitation.md)
- [CRM et flux commercial](docs/CRM-commercial.md)
- [Transmission et réponse aux devis](docs/Devis-client.md)
- [GPS et limites mobiles](docs/GPS.md)
- [Portail et livraison](docs/PORTAIL_ET_LIVRAISON.md)
- [Audit de production et vérifications restantes](docs/Audit-production.md)

Les documents historiques de paie et les anciens portails ne décrivent pas les fonctionnalités garanties du SaaS actuel. La paie réglementaire, les déclarations fiscales et les intégrations financières externes nécessitent un périmètre et une validation spécifiques.
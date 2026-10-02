# TransitFlow — Explorateur du modèle relationnel

Jonathan Kakesa Nayaba, CPI_CEO Cognito Inc. — développeur principal et auteur du Projet TransitFlow ERP.

Service statique autonome du projet Railway TransitFlow, branche `transitflow-schema`.
Le schéma décrit les migrations de `transitflow-erp` à la révision `b51ce1638be67af030f961a42f07ba74e6baf348` (migration ERP 0013).
Il ne contient aucun enregistrement métier ni identifiant de démonstration.

## Exécution

Node.js 22 : `node server.mjs`. Le port est fourni par `PORT`, ou vaut 8080.
Contrôle de disponibilité : `/health`. Aucun accès à PostgreSQL, aucun volume ni secret requis.
Le conteneur s’exécute avec l’utilisateur non privilégié `node`.

## Contenu

`public/index.html` : explorateur autonome avec recherche, filtres, zoom, détails et exports.
`public/schema.json`, `public/TransitFlow.dbml` et `public/MRL_TransitFlow.md` : formats documentaires complémentaires.
La documentation est une photographie de la version indiquée, pas une introspection automatique de la production.

## Vérification

`node --test server.test.mjs` vérifie les routes autorisées, les réponses HTTP et le schéma publié.

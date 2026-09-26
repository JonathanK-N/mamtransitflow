# TransitFlow : ERP multi-entreprise

Auteur : Jonathan Kakesa (JonathanK-N)

## Périmètre

Un même service accueille des entreprises indépendantes de transport de
marchandises, voyageurs, navettes, scolaire et transport spécialisé. Le carburant
est une spécialisation ; il ne définit pas le modèle commun.

## Frontières de sécurité

- L'utilisateur est global ; ses adhésions et rôles sont propres aux entreprises.
- Chaque objet métier possède une organisation obligatoire et un identifiant UUID.
- L'API exige une adhésion active pour l'en-tête X-Organization ; aucun identifiant
  fourni dans le corps ne peut changer l'entreprise propriétaire.
- Les relations sont validées dans la même organisation, les collections filtrées
  avant recherche, pagination, agrégation et export.
- PostgreSQL vérifie aussi les clés étrangères composites organisation/objet,
  y compris lors d’une écriture qui contournerait les sérialiseurs applicatifs.
- Les anciennes routes mono-entreprise sont désactivées par défaut. Le mode
  TF_LEGACY_ENABLED est réservé aux installations historiques isolées.
- Aucun accès implicite de super-administrateur aux données du client par l'API.
- Les documents sont servis par une route authentifiée, jamais un dossier public.

## Domaines

Organisation et adhésions ; partenaires ; véhicules et personnel ; commandes et
missions ; voyageurs et réservations ; entretien ; achats et stocks ; facturation
et règlements ; écritures comptables ; documents et audit.

Les états sensibles changent uniquement dans des services transactionnels. Les
montants utilisent Decimal ; les documents financiers validés sont immuables.
Une devise par organisation, sans conversion implicite entre GNF, XAF, XOF, CDF,
EUR ou USD. Les taux sont saisis explicitement : aucun taux fiscal prétendument
universel n'est fourni. La paie et les déclarations réglementaires par pays
exigent un périmètre localisé et une validation indépendante.

## Compatibilité et migration

Les tables historiques restent intactes. L'import historique doit être explicite,
transactionnel, reproductible et rattaché à une organisation choisie. Une sauvegarde
restaurable est nécessaire avant toute migration d'une base d'exploitation.

## Livraison

Branche de développement : transitflow-erp. Branche de recette : transitflow-tests.
La recette utilise une base et des comptes jetables. Les résultats exécutés et
les limites sont consignés dans docs/RECETTE.md, sans présenter une simulation
comme une validation d'intégration externe ou une homologation réglementaire.

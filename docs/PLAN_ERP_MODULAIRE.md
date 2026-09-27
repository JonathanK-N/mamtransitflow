# Extension de TransitFlow en ERP modulaire

Auteur : Jonathan Kakesa (JonathanK-N)

## Périmètre autorisé

- Applications installables et désactivables indépendamment pour chaque entreprise.
- Création d’applications internes par l’administrateur : champs, droits et fiches,
  sans exécution de code arbitraire fourni depuis le navigateur.
- Module de connexion aux paiements réservé dans le catalogue. Aucun appel bancaire
  ou Mobile Money tant que les API contractuelles ne sont pas disponibles.
- Extension métier : contrats, tarification, sous-traitance, incidents, livraison,
  ressources humaines, trésorerie, dettes fournisseurs et clôtures.
- Localisations par pays fondées sur des sources vérifiables ; aucun taux fiscal
  ou social supposé. Priorité confirmée : Guinée, puis Cameroun et Congo.
- Animation discrète, navigation accessible et préférence de réduction des mouvements.
- Recette, sécurité, sauvegarde/restauration, charge, exploitation et documentation.

## Ordre d’intégration

1. Catalogue, dépendances et droits des applications ; studio de formulaires.
2. Parcours commerciaux et transport avancés.
3. Ressources humaines et finance de gestion.
4. Paramétrage pays et circuits d’approbation.
5. Exploitation, reprise des données, recette et validation de mise en service.

Les livraisons sont versionnées sur `transitflow-erp` et vérifiées sur
`transitflow-tests`. Les paiements externes restent explicitement en attente.

## Avancement au 27 septembre 2026

- Livré et testé : catalogue, dépendances, studio, droits et fiches internes.
- Livré et testé : contrats, tarifs, sous-traitance, incidents et dettes fournisseurs.
- Livré et testé : congés avec indisponibilités, avances à remboursement intégral,
  rapprochement manuel et verrouillage des périodes comptables.
- Livré et testé : animations discrètes et prise en compte des mouvements réduits.
- Vérifié localement : restauration PostgreSQL avec comparaison des contenus.
- En cours de préparation : paie et fiscalité guinéennes, puis Cameroun et Congo.
- À réaliser : portail client, signature de livraison, imports, paie réglementaire,
  reprise historique, charge et mise en production.

Les détails et les limites sont consignés dans `RECETTE_MODULAIRE.md`.

# Recette de l’extension modulaire — 27 septembre 2026

Auteur : Jonathan Kakesa (JonathanK-N)

Révision applicative : `853952e`. Branche de recette : `transitflow-tests`.

## Vérifications locales exécutées

| Vérification | Résultat |
| --- | --- |
| API ERP sur PostgreSQL, applications et nouveaux circuits | 70 tests réussis |
| Compatibilité avec les fonctionnalités historiques | 250 tests réussis |
| Parcours réels Chromium | 5 scénarios réussis |
| TypeScript et compilation Vue de production | Réussis |
| Migrations Django et vérification système | Aucun changement manquant, aucune erreur |
| Contrôle visuel du catalogue des applications | Capture inspectée, disposition lisible |
| Sauvegarde PostgreSQL locale puis restauration isolée | 66 tables, 624 lignes ; empreintes de contenu identiques |

La suite ERP a initialement signalé deux connexions de threads encore ouvertes à
la suppression de la base de test. Le nettoyage ferme désormais explicitement
ces connexions ; les deux tests de concurrence ont été rejoués avec création et
suppression de base, sans cet avertissement.

La restauration a utilisé `pg_dump` au format custom et `pg_restore --exit-on-error`
sur une **nouvelle base locale**. Les nombres de lignes et les empreintes des
lignes de chaque table ont été comparés. Les fichiers privés, les sauvegardes
distantes, la rétention et la restauration d’un service public restent hors de
ce contrôle local.

## Scénarios ajoutés

- Activation et désactivation des applications par entreprise, contrôle serveur
  et résolution des dépendances sans suppression des données.
- Studio : droits de lecture/écriture, validation des types, isolation des fiches,
  conflits de révision et conservation du schéma contenant déjà des données.
- Contrats mensuels : conservation du jour d’ancrage et absence de doublons.
- Tarifs : contrôle du trajet, de la période de validité et des unités.
- Sous-traitance, incident résolu, facture fournisseur et règlement ; absence
  de double comptabilisation d’un achat déjà réceptionné.
- Congés : conflits avec les missions et les congés existants ; données non
  accessibles au rôle lecture seule. La finance peut sélectionner un salarié
  sans modifier sa fiche.
- Avances : justificatifs, dates réelles, remboursement et interdiction de rejouer
  le versement.
- Clôture : résolution préalable des brouillons, autorisation administrative,
  blocage atomique des écritures antidatées.
- Rapprochement manuel : montant, sens, unicité et correction auditée.
- Navigateur : création d’une application et de ses fiches, puis création,
  soumission et approbation d’un congé, avec persistance après rechargement.

## Périmètre restant

La paie légale automatisée, les déclarations par pays, les soldes de congés,
les remboursements partiels d’avances, les imports bancaires, le portail client,
la signature de livraison et la reprise historique complète restent à intégrer.
La recette de forte charge et le déploiement public ne sont pas réalisés.
Les connexions bancaires et Mobile Money restent en attente des API partenaires,
conformément à la demande. Aucune transaction externe n’est exécutée.

Voir [Localisations](LOCALISATIONS.md) pour l’ordre Guinée, Cameroun, Congo et
les sources officielles repérées. Les résultats locaux ne certifient pas une
conformité fiscale ni une équivalence à l’ensemble des applications d’Odoo.

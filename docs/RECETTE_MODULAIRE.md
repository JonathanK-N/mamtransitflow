# Recette de l’extension modulaire — 27 septembre 2026

Auteur : Jonathan Kakesa (JonathanK-N)

Révision applicative : `5b64a2e8ab8fde996c2c8881c828a18a24e937b0`.
Branche de recette : `transitflow-tests`.

## Vérifications exécutées (local et intégration continue)

| Vérification | Résultat |
| --- | --- |
| API ERP sur PostgreSQL, applications et nouveaux circuits | 73 tests réussis en CI ; 70 puis 9 tests ciblés en local |
| Compatibilité avec les fonctionnalités historiques | 250 tests réussis |
| Parcours réels Chromium | 5 scénarios réussis |
| TypeScript et compilation Vue de production | Réussis |
| Migrations Django et vérification système | Aucun changement manquant, aucune erreur |
| Contrôle visuel du catalogue des applications | Capture inspectée, disposition lisible |
| Sauvegarde PostgreSQL locale puis restauration isolée | 66 tables, 624 lignes ; empreintes de contenu identiques |
| Requêtes concurrentes locales, deux entreprises | 120 requêtes, concurrence 8, aucune réponse inattendue |
| Construction Docker Linux en CI | Réussie |

Preuves : [Recette ERP et Docker](https://github.com/JonathanK-N/mamtransitflow/actions/runs/36301754458)
et [Compatibilité historique](https://github.com/JonathanK-N/mamtransitflow/actions/runs/36301754485).
Les captures et traces de la recette navigateur sont conservées dans les artefacts
du workflow ERP.

Le contrôle concurrent local a duré 15,13 secondes : médiane 908 ms, percentile 95
à 1 706 ms, maximum 2 671 ms. Il porte sur des lectures de catalogue, tableau de
bord et partenaires, et des refus d’accès interentreprises. Le serveur Django de
développement et ce petit volume ne permettent pas d’en déduire une capacité de
production ; une recette de charge sur l’hébergement cible reste nécessaire.

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
- Refus des corps JSON et identifiants de module mal formés sans erreur serveur.
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

## Complément : portail et livraison

La livraison suivante ajoute le portail client, les accès révocables, les pièces
partagées explicitement et les justificatifs signés téléchargeables en PDF.
Sa recette locale PostgreSQL compte **89 tests API réussis** ; les **6 parcours
Chromium passent**, dont la signature par un chauffeur puis le téléchargement par
le client. La compilation Vue/TypeScript et le contrôle des migrations passent.
Le PDF et les captures du portail ont été inspectés visuellement.

La révision `f233dc6a07cd8ae56f873bc7fe61683606d84bd3` a ensuite passé la
[recette ERP, navigateur et Docker sous Linux](https://github.com/JonathanK-N/mamtransitflow/actions/runs/36337156280)
et les [tests de compatibilité historique](https://github.com/JonathanK-N/mamtransitflow/actions/runs/36337156249).

Les limites d’inscription ont été conservées : les compteurs de la seule base
locale ont été réinitialisés avant la recette complète après plusieurs essais.
Aucune limite du service public n’a été modifiée. Voir le
[guide du portail et des livraisons](PORTAIL_ET_LIVRAISON.md).

## Périmètre restant après ce complément

La paie légale automatisée, les déclarations par pays, les soldes de congés,
les remboursements partiels d’avances, les imports bancaires et la reprise
historique complète restent à intégrer. La recette de forte charge reste à faire.
Le site Railway est accessible et les comptes de démonstration administrateur et
chauffeur ont été vérifiés ; la persistance des fichiers, les sauvegardes et la
messagerie de cet hébergement restent à confirmer.
Les connexions bancaires et Mobile Money restent en attente des API partenaires,
conformément à la demande. Aucune transaction externe n’est exécutée.

Voir [Localisations](LOCALISATIONS.md) pour l’ordre Guinée, Cameroun, Congo et
les sources officielles repérées. Les résultats locaux ne certifient pas une
conformité fiscale ni une équivalence à l’ensemble des applications d’Odoo.

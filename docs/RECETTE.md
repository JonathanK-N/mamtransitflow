# Recette TransitFlow ERP — 26 septembre 2026

Auteur : Jonathan Kakesa (JonathanK-N)

Révision applicative vérifiée : `12e68ce1a9ec000f3cfe3c5ffcc8f36866f44a95`.
Branche dédiée : `transitflow-tests`. Les corrections validées sont intégrées
à `transitflow-erp` sans modifier la branche historique `erp`.

## Résultats exécutés

| Vérification | Résultat |
| --- | --- |
| API ERP, isolation, sessions et concurrence PostgreSQL | 42 tests réussis |
| Compatibilité historique sur une base PostgreSQL neuve | 250 tests réussis |
| Parcours réels Chromium avec API et PostgreSQL | 3 scénarios réussis |
| Vérification TypeScript et compilation Vue | Réussies |
| Cohérence des migrations Django | Aucun changement manquant |
| Vérification Django en configuration de production | Réussie ; les deux exclusions HSTS historiques sont conservées |
| Installation Python | Aucune incompatibilité signalée par pip check |
| Dépendances front utilisées en production | Aucune vulnérabilité connue signalée par pnpm audit --prod lors de cette recette |
| Construction Docker Linux en intégration continue | Réussie |

Preuves GitHub : [Recette ERP](https://github.com/JonathanK-N/mamtransitflow/actions/runs/36269568387)
et [Tests historiques](https://github.com/JonathanK-N/mamtransitflow/actions/runs/36269568336).
Le workflow ERP conserve captures et traces dans son artefact `recette-navigateur`.

## Scénarios vérifiés

- L’utilisateur ne peut consulter, modifier, supprimer, exporter ni associer une
  référence d’une autre entreprise. Les rôles finance, exploitation, atelier,
  chauffeur et lecture seule sont contrôlés côté serveur.
- PostgreSQL refuse directement une facture liée au client d’une autre entreprise.
- Deux règlements concurrents ne dépassent pas le solde d’une facture ; deux
  réservations concurrentes ne vendent pas la même dernière place.
- La confirmation d’une commande permet la mission ; la livraison contrôle les
  quantités et termine la commande. L’atelier empêche un départ incompatible.
- La réception d’un achat ne peut être rejouée ; une sortie de stock insuffisant
  est refusée. Les écritures comptables restent équilibrées.
- Les documents privés exigent une session autorisée ; un fichier dont le contenu
  ne correspond pas au type annoncé est refusé.
- Le renouvellement de session exige un jeton CSRF, révoque l’ancien jeton de
  renouvellement et cesse de fonctionner après déconnexion.
- Une invitation crée un membre de l’entreprise visée, sans nouvelle entreprise.
  La réinitialisation de mot de passe est à usage unique et invalide l’ancien accès.
- Un chauffeur n’accède qu’à ses missions. Les positions prises avant la clôture
  peuvent être synchronisées après, pendant une fenêtre limitée, sans doublon.
- Dans Chromium : accueil, photographie, inscription, création de véhicule,
  rechargement du module, déconnexion, affichage mobile, création et émission
  d’une facture puis refus de lecture depuis une entreprise indépendante.

## Conditions de reproductibilité

Les tests de concurrence utilisent de vraies connexions PostgreSQL. Ils ne
constituent pas un test de charge à grande échelle. Les scénarios navigateur
utilisent l’application compilée, sans remplacer les API par des réponses simulées.

Exécuter les suites SaaS et historique dans des processus séparés. Après des tests
transactionnels, une base réutilisée peut avoir perdu les données insérées par les
migrations historiques. Recréer cette base de test (`--create-db`) avant la recette
historique ; ne jamais exécuter cette option contre une base d’exploitation.

## Ce qui n’est pas validé par ces résultats

Pas de déploiement public effectué dans cette livraison. Les envois SMTP réels,
les transferts bancaires/Mobile Money, les boîtiers GPS, les restaurations de
sauvegardes en exploitation et les fortes charges ne sont pas homologués ici.

Le GPS navigateur nécessite une autorisation explicite et la fiche ouverte ; il
ne remplace pas un boîtier embarqué ni un service de localisation en arrière-plan.
Les localisations fiscales, la paie africaine par pays, les états réglementaires
et la reprise complète des données historiques restent à réaliser et à valider.
Ces résultats ne doivent pas être présentés comme une équivalence fonctionnelle
à tous les modules d’Odoo ou comme une certification comptable.

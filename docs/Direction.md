# Pilotage Direction

La vue d'ensemble existante affiche une synthèse de gestion pour les rôles propriétaire, administrateur, finance et lecture seule lorsque Facturation est activée. Le Centre d'exploitation conserve les opérations courantes et la carte ; il ne fournit pas les finances aux rôles exploitation, atelier ou chauffeur.

Le serveur accepte `dashboard?start=AAAA-MM-JJ&end=AAAA-MM-JJ`, avec une période inclusive de 1 à 366 jours. Par défaut : les 30 derniers jours selon le fuseau de l'entreprise. La comparaison utilise la période immédiatement précédente, de même longueur. Les écarts sont des différences absolues calculées en Decimal ; aucun pourcentage trompeur n'est calculé avec un dénominateur nul.

| Indicateur | Définition |
|---|---|
| Chiffre d'affaires HT | Factures émises ou soldées moins avoirs émis, selon leur date ; devis et brouillons exclus. |
| Encaissements | Paiements clients enregistrés selon leur date effective. |
| Dépenses validées | Dépenses approuvées selon leur date ; les factures fournisseurs ne sont pas additionnées afin de ne pas prétendre à un résultat comptable consolidé. |
| Missions terminées | Date de fin effective comprise dans les journées locales sélectionnées, y compris les changements d'heure. |
| Marge commerciale | Commandes confirmées ou réalisées prévues sur la période : prix HT moins dépenses de leurs missions validées et sous-traitances réalisées, hors charges indirectes. |
| À encaisser / retard | Soldes positifs actuels des factures émises après paiements et avoirs liés. Ces indicateurs sont indépendants de la période. Les crédits clients et factures soldées ne sont pas additionnés aux créances. |

Un module désactivé ou inaccessible produit un indicateur indisponible, jamais un zéro présenté comme mesuré. Chaque agrégat est filtré par organisation. Les montants sont calculés en SQL/Decimal puis formatés à l'affichage ; le navigateur ne recalcule pas les soldes.

Les tests vérifient le périmètre financier, la matrice de rôles, les dates invalides, les limites de journée avec changement d'heure, les coûts réellement validés et une charge de 5000 factures. Une autre recette de volume ajoute 1000 clients, 5000 commandes, 5000 missions, 100 véhicules et 200 chauffeurs dans une base de test et consigne les requêtes et temps dans JUnit. Les temps mesurés dans cette base ne sont pas des garanties de latence de production.


## Indicateurs commerciaux et opérationnels

Les devis envoyés reposent sur un envoi électronique réussi et sa dernière date d'envoi dans les journées locales de la période. Un renvoi ne crée pas un second devis. Le nombre accepté et le taux d'acceptation décrivent l'état actuel de cette cohorte ; les devis convertis restent acceptés. Sans envoi, le taux est indisponible. Un taux de zéro n'est affiché que si un dénominateur existe.

Les commandes comprennent les commandes non annulées prévues pendant la période, brouillons inclus. Les missions prévues, leur taux de réalisation et leurs retards utilisent la cohorte des départs prévus dans la période, hors annulations. Les missions terminées utilisent séparément leur date de fin effective. Les retards reprennent les règles du Centre pour les missions ouvertes, plus les missions achevées après l'arrivée prévue.

Les véhicules mobilisés sont un nombre distinct de véhicules affectés à cette cohorte, pas une mesure horaire de télématique. La disponibilité actuelle réutilise les règles existantes de planning et d'atelier pour les 60 prochaines minutes ; elle n'est pas présentée comme un historique. Les interventions sont classées par date prévue, les incidents signalés/résolus par date de survenue.

Les cinq principaux clients sont classés selon les factures et avoirs HT émis datés de la période ; devis et brouillons sont exclus. Les modules inaccessibles restent indisponibles, en particulier les données d'exploitation pour Finance. Les écarts des pourcentages sont exprimés en points et ne sont pas assimilés à des montants.

Les montants transmis comme chaînes décimales sont formatés directement par Intl, sans conversion intermédiaire en Number qui pourrait perdre des centimes sur de très grands montants.

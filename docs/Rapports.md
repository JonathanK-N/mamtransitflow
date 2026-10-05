# Rapports et devise

La balance comptable utilise les écritures comptabilisées de l'entreprise active. Les dates filtrent la date comptable. Sans dates, tout l'historique est pris en compte ; les écritures sont lues par blocs de 500 sans charger la liste complète en mémoire. Une période avec début et fin ne peut pas dépasser 366 jours.

La rentabilité commerciale est accessible seulement si les modules Commandes, Dépenses et Sous-traitance sont actifs et que le rôle autorise leur lecture. Le rôle Finance conserve la balance mais ne reçoit pas les commandes qu'il n'a pas le droit de consulter. Les coûts et la marge ne contournent pas ces permissions.

Les commandes sont paginées par 25, au maximum 100 via l'API. Les filtrès `start`, `end`, `customer` et `status` concernent les commandes ; leur période repose sur la date prévue. Les coûts directs regroupent les dépenses validées et les sous-traitances réalisées des missions liées aux commandes de la page. La marge est le prix convenu HT moins ces coûts, hors charges indirectes, et n'est pas un résultat comptable. Les montants sont calculés avec Decimal au serveur.

Les exports CSV existants utilisent le même périmètre de lecture que les listes, filtrent l'entreprise, protègent les cellules commençant par une formule et conservent les valeurs zéro. Ils sont actuellement construits dans la réponse HTTP ; les très gros fichiers restent une limite à mesurer avant d'introduire un export asynchrone.

TransitFlow utilise une devise unique par entreprise, sans conversion FX. La devise peut être choisie avant la création de données monétaires. Elle ne peut plus être changée ensuite, car un changement d'étiquette ne convertirait ni les documents ni les paiements historiques. Les coordonnées et autrès parametrès restent modifiables. Les échéances et les dates générées de facture utilisent le fuseau de l'entreprise.

Validation ajoutée : matrice de huit rôles, périodes invalides, pagination sur 1000 commandes, isolation entre entreprises, calcul Decimal, préservation des zéros CSV, refus du changement de devise historique et échéance autour de minuit. Une validation locale ne remplace pas la CI PostgreSQL ni la recette de production.

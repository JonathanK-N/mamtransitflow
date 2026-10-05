# Audit de production TransitFlow

## État au 5 octobre 2026

Cet audit distingue les preuves obtenues des vérifications restantes. Aucun module n'est déclaré validé uniquement parce que son code existe.

| Priorité | Constat vérifié | Suite |
|---|---|---|
| P1 corrigé | Un retour rapide du contact chauffeur pouvait être suivi d'une navigation tardive vers Messages. | d46c78b : CI complète verte, déploiement Railway d01fb326 confirmé, recette de production réussie, santé 200, nettoyage TEST vérifié, zéro 5xx dans la fenêtre de logs. |
| P1 corrigé en branche | L'envoi du devis ne transmettait aucun courriel. | SMTP local et acceptation publique réussissent dans la recette commerciale complète ; migration et CI PostgreSQL puis déploiement encore requis. |
| P1 à vérifier | Sauvegardes PostgreSQL et fichiers persistants : fréquence, rétention et restauration non encore prouvées. | Lire la configuration accessible, conserver les preuves et tester une restauration dans une base temporaire si possible. |
| P1 à vérifier | Audit global des permissions, finances, exports, volume, sessions PWA et parcours intermodules. | Réutiliser les suites existantes, compléter uniquement les lacunes démontrées. |
| P1 en correction | L'ancienne vue d'ensemble ne permet pas de comparer une période de gestion à la précédente et utilise la date serveur. | Synthèse Direction en cours : Decimal, périodes locales, définitions et permissions, tests de changement d'heure et de volume. |
| P1 corrigé en branche | Les routes publiques d'authentification utilisaient `.get` sans vérifier la forme JSON et pouvaient produire une erreur serveur pour une liste. | Validation commune du corps JSON ; 12 cas malformés et la rotation CSRF/refresh existante réussissent localement. CI et déploiement encore requis. |

## Centre d'exploitation

La version finale du Centre d46c78b est déployée sur transitflow-tests et synchronisée sur transitflow-erp. Ses suites CI comportent 250 tests généraux, 318 tests ERP et 58 tests navigateur distincts, tous réussis. La recette de production réussit avec deux sessions, affectation concurrente, positions GPS simulées dans le navigateur, alertes, conversation réutilisée et nettoyage TEST vérifié indépendamment. Les fenêtres contrôlées ne montrent ni erreur runtime ni réponse 5xx. Les premières tentatives échouées restent distinguées des réussites ; les réexécutions ne sont pas additionnées au nombre de tests distincts.

Les essais navigateur ne prouvent pas la capture GPS physique en arrière-plan sur téléphone. Les vérifications de volumes, connexions PostgreSQL, accessibilité clavier, logs et déploiement sont détaillées dans le rapport du Centre.

## Sauvegardes : preuve accessible et limite actuelle

L'inventaire Railway confirme un volume PostgreSQL de 50000 Mo à `/var/lib/postgresql/data` et un volume applicatif de 1024 Mo à `/data`. Il ne donne aucune fréquence ni rétention des sauvegardes. Le navigateur a atteint la connexion GitHub de Railway ; aucune session authentifiée n'était disponible. La connexion a été demandée à l'utilisateur pendant la poursuite des travaux indépendants. Une sauvegarde et une restauration ne sont donc pas encore validées.

## Méthode

Pour chaque lot : diagnostic du code et de la configuration réelle, correction minimale, tests représentatifs, revue du diff, déploiement après réussite, santé et logs, recette TEST puis réaudit. Les envois mail automatiques des tests utilisent un transport simulé. Aucune restauration ne doit écraser la base de production.

## Lot de sécurité, rapports et devise en branche

La CI a8fb374 a échoué sur le retour Messages vers Centre sur iPad. Le détail d'une conversation pouvait réécrire le fragment pendant une navigation. La sélection vérifie maintenant la route avant et après la requête ; le parcours iPad avec réponse retardée passe localement. L'affectation locale utilise le mode séquentiel car SQLite ne prouve pas les verrous PostgreSQL. Les essais locaux simultanés ont rencontré `database is locked` ; ces échecs ne sont pas déclarés comme réussites.

Les rapports ne renvoient plus la rentabilité des commandes au rôle Finance qui ne peut pas consulter les commandes. La pagination de 1000 commandes et la matrice de huit rôles passent dans 14 nouveaux tests. Le navigateur a validé Direction et Rapports à 320 pixels. Le changement de devise avec données monétaires existantes est refusé, et les échéances et dates générées utilisent le jour de l'entreprise. Les suites Direction/CRM passent : 32 réussites et 6 essais PostgreSQL non exécutables sur SQLite, a exécuter obligatoirement en CI PostgreSQL. Ces lots ne sont pas encore déclarés déployés.

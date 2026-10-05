# Audit de production TransitFlow

## État au 5 octobre 2026

Cet audit distingue les preuves obtenues des vérifications restantes. Aucun module n'est déclaré validé uniquement parce que son code existe.

| Priorité | Constat vérifié | Suite |
|---|---|---|
| P1 corrigé | Un retour rapide du contact chauffeur pouvait être suivi d'une navigation tardive vers Messages. | d46c78b : CI complète verte, déploiement Railway d01fb326 confirmé, recette de production réussie, santé 200, nettoyage TEST vérifié, zéro 5xx dans la fenêtre de logs. |
| P1 | crm_services.quote_action(send) émet le devis mais ne transmet aucun courriel. Aucun parcours public de réponse au devis n'existe dans les routes inspectées. | Étendre le devis existant : transmission vérifiable, lien temporaire révocable, réponse explicite, expiration par fuseau entreprise et audit. |
| P1 à vérifier | Sauvegardes PostgreSQL et fichiers persistants : fréquence, rétention et restauration non encore prouvées. | Lire la configuration accessible, conserver les preuves et tester une restauration dans une base temporaire si possible. |
| P1 à vérifier | Audit global des permissions, finances, exports, volume, sessions PWA et parcours intermodules. | Réutiliser les suites existantes, compléter uniquement les lacunes démontrées. |
| P1 en correction | L'ancienne vue d'ensemble ne permet pas de comparer une période de gestion à la précédente et utilise la date serveur. | Synthèse Direction en cours : Decimal, périodes locales, définitions et permissions, tests de changement d'heure et de volume. |

## Centre d'exploitation

La version finale du Centre d46c78b est déployée sur transitflow-tests et synchronisée sur transitflow-erp. Ses suites CI comportent 250 tests généraux, 318 tests ERP et 58 tests navigateur distincts, tous réussis. La recette de production réussit avec deux sessions, affectation concurrente, positions GPS simulées dans le navigateur, alertes, conversation réutilisée et nettoyage TEST vérifié indépendamment. Les fenêtres contrôlées ne montrent ni erreur runtime ni réponse 5xx. Les premières tentatives échouées restent distinguées des réussites ; les réexécutions ne sont pas additionnées au nombre de tests distincts.

Les essais navigateur ne prouvent pas la capture GPS physique en arrière-plan sur téléphone. Les vérifications de volumes, connexions PostgreSQL, accessibilité clavier, logs et déploiement sont détaillées dans le rapport du Centre.

## Sauvegardes : preuve accessible et limite actuelle

L'inventaire Railway confirme un volume PostgreSQL de 50000 Mo à `/var/lib/postgresql/data` et un volume applicatif de 1024 Mo à `/data`. Il ne donne aucune fréquence ni rétention des sauvegardes. Le navigateur a atteint la connexion GitHub de Railway ; aucune session authentifiée n'était disponible. La connexion a été demandée à l'utilisateur pendant la poursuite des travaux indépendants. Une sauvegarde et une restauration ne sont donc pas encore validées.

## Méthode

Pour chaque lot : diagnostic du code et de la configuration réelle, correction minimale, tests représentatifs, revue du diff, déploiement après réussite, santé et logs, recette TEST puis réaudit. Les envois mail automatiques des tests utilisent un transport simulé. Aucune restauration ne doit écraser la base de production.

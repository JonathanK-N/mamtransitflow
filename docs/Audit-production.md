# Audit de production TransitFlow

## État au 5 octobre 2026

Cet audit distingue les preuves obtenues des vérifications restantes. Aucun module n'est déclaré validé uniquement parce que son code existe.

| Priorité | Constat vérifié | Suite |
|---|---|---|
| P1 | Un retour rapide du contact chauffeur peut être suivi d'une navigation tardive vers Messages. | Garde de cycle de vie ajoutée, recette en cours sur operations-center. |
| P1 | crm_services.quote_action(send) émet le devis mais ne transmet aucun courriel. Aucun parcours public de réponse au devis n'existe dans les routes inspectées. | Étendre le devis existant : transmission vérifiable, lien temporaire révocable, réponse explicite, expiration par fuseau entreprise et audit. |
| P1 à vérifier | Sauvegardes PostgreSQL et fichiers persistants : fréquence, rétention et restauration non encore prouvées. | Lire la configuration accessible, conserver les preuves et tester une restauration dans une base temporaire si possible. |
| P1 à vérifier | Audit global des permissions, finances, exports, volume, sessions PWA et parcours intermodules. | Réutiliser les suites existantes, compléter uniquement les lacunes démontrées. |

## Centre d'exploitation

La version 95ea697 est déployée. Ses suites CI comportent 250 tests généraux, 318 tests ERP et 58 tests navigateur distincts, tous réussis. La recette de production précédente sur 7d5cbe6 a réussi avec deux sessions, affectation concurrente, positions GPS simulées dans le navigateur et nettoyage des données TEST. La recette initiale sur 95ea697 a échoué au retour depuis Messages ; les données TEST ont été nettoyées. Elle ne constitue pas une validation complète de cette version.

Les essais navigateur ne prouvent pas la capture GPS physique en arrière-plan sur téléphone. Les vérifications de volumes, connexions PostgreSQL, accessibilité clavier, logs et déploiement sont détaillées dans le rapport du Centre.

## Méthode

Pour chaque lot : diagnostic du code et de la configuration réelle, correction minimale, tests représentatifs, revue du diff, déploiement après réussite, santé et logs, recette TEST puis réaudit. Les envois mail automatiques des tests utilisent un transport simulé. Aucune restauration ne doit écraser la base de production.

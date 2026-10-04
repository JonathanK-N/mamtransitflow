# Suivi GPS des missions

Le frontend officiel est Vue/PWA. `frontend/src/gps.ts` possède la capture, la file IndexedDB et la synchronisation ; `App.vue` le rattache à la session et `DriverTracking.vue` affiche son état, indépendamment des fiches Missions ou Terrain et des changements d’entreprise. Chaque requête conserve explicitement le tenant de sa mission. `MissionTracking.vue` affiche désormais le parcours enregistré ; `LiveTracking.vue` affiche la flotte autorisée sur `TrackingMap.vue`.

Les anciens `assets/js/gps.js`, les pages HTML et `apps/suivi` restent des références compatibles avec les autres modules historiques. Ils ne sont pas chargés en production lorsque `TF_LEGACY_ENABLED=0`. Le scénario `e2e/parcours_gps.py` appelle les tests Vue/PWA `gps.spec.ts`. Aucun troisième modèle de positions ni canal GPS séparé n’a été ajouté : `erp.Position`, PostgreSQL et `/ws/activity` restent les sources officielles.

## Cycle professionnel obligatoire

Seules les missions actives assignées au compte chauffeur déclenchent la capture. La permission déjà accordée lance `watchPosition` ; une permission inconnue ou refusée affiche un bouton Autoriser la localisation et l’exigence obligatoire. Aucun bouton d’arrêt, pause ou désactivation du GPS n’est fourni. La fin normale essaie un dernier point, synchronise la file puis la transition métier ferme le suivi. L’annulation autorisée, le retrait d’accès, l’invalidation de session arrêtent la capture et libèrent Wake Lock. Le chauffeur ne peut pas annuler une mission par l’API.

Une révocation distante ne peut être reçue pendant une coupure réseau : l’application utilise sa dernière affectation active connue jusqu’à resynchronisation. Changer d’entreprise ne permet pas de couper une mission active : le suivi continue dans son tenant autorisé, identifié dans le bandeau. Après une ouverture hors connexion, elle ne relance pas une capture sans pouvoir vérifier l’affectation auprès du serveur ; les positions déjà conservées restent dans IndexedDB.

## Mesures et fréquence

Le serveur fournit la configuration centrale : intervalle minimal 10 s, déplacement minimal 10 m, point stationnaire après 30 s, précision maximale 1 000 m, En ligne jusqu’à 45 s, Position récente jusqu’à 180 s, puis Signal perdu. `watchPosition` demande une haute précision, un cache maximal de 5 s et un délai de 30 s. Une lecture ponctuelle prend le relais pour le battement stationnaire si le navigateur n’émet pas de nouvelle mesure. Aucune fréquence de réception GPS physique n’est garantie.

Précision en mètres, vitesse en m/s (affichée en km/h) et cap en degrés sont facultatifs. Les points non finis, hors limites et hors de la fenêtre started_at/completed_at sont rejetés. Les coordonnées sont conservées à six décimales. Les statistiques du parcours donnent sa durée, la distance approximative reliant les points GPS et, si disponibles, les vitesses mesurées moyenne et maximale. Elles ne constituent pas une distance routière certifiée. Aucun itinéraire ou point de destination n’est inventé à partir d’une adresse textuelle.

## File et temps réel

IndexedDB `transitflow-mission-gps` stocke chaque point avec compte, entreprise, mission et UUID. Les anciennes files locales compatibles sont migrées après persistance. Aucune limite arbitraire ne supprime les points anciens. Des lots de 200 sont renvoyés automatiquement ; mission/timestamp et mission/client_id empêchent les doublons. Seuls les points acquittés sont retirés. Les points enregistrés pendant la mission peuvent être synchronisés dans les 24 h après sa fin, avec timestamp antérieur à cette fin. Un stockage refusé affiche une alerte et conserve une file en mémoire, qui ne peut survivre à la fermeture du navigateur.

API authentifiée → validation → `Position` PostgreSQL → événement de métadonnées Redis/Channels → API autorisée → marqueur Leaflet existant. Les coordonnées ne sont pas diffusées dans les événements WebSocket. Après reconnexion, l’API recharge la source de vérité. La carte effectue un appel global regroupé, limité à un par seconde ; aucun polling par véhicule. Le mécanisme existant de resynchronisation assure un secours toutes les 60 s. Les timestamps des points, et non leur heure d’upload, déterminent leur fraîcheur. La carte utilise l’heure serveur et le temps monotone écoulé ; une horloge exploitant décalée ne transforme pas un ancien point en véhicule en ligne. La première acquisition ponctuelle fonctionne aussi lorsque watchPosition n’a pas encore délivré de mesure valide.

La boucle de durée de vie ASGI vérifie les interruptions toutes les 30 s, même sans carte ouverte. Elle réutilise les notifications existantes et un verrou d’entreprise pour dédupliquer les alertes entre les processus. La commande `python backend/manage.py check_tracking` permet une vérification ponctuelle ; `deliver_push` vérifie aussi les signaux. Les positions ne créent pas d’événement du journal administratif.

## Carte et permissions

Leaflet 1.9.4 est installé par npm/pnpm et compilé avec Vite. Le fournisseur par défaut est `https://tile.openstreetmap.org/{z}/{x}/{y}.png` avec attribution visible. Pour remplacer le fournisseur, définir `TF_MAP_TILE_URL` (HTTPS) et `TF_MAP_TILE_ATTRIBUTION` / `TF_MAP_TILE_ATTRIBUTION_URL`, avec attribution conforme aux droits du fournisseur. La politique CSP autorise l’origine HTTPS configurée. Les tests interceptent les tuiles ; le Service Worker ne les précharge pas et n’enregistre aucune réponse privée GPS.

Politique OSM : https://operations.osmfoundation.org/policies/tiles/ . Le service public offre une disponibilité au mieux ; utiliser un fournisseur dédié avec quotas et engagement de service avant un déploiement à grande échelle. Leaflet : https://leafletjs.com/download.html .

Owner, admin et operations consultent la flotte ; les chauffeurs consultent uniquement leurs missions. Finance, atelier, lecture seule et clients n’accèdent pas aux positions. API, historique, état et événement WebSocket revalident l’entreprise et les droits ; la base garde ses contraintes de références tenant. Les marqueurs changent de position sans recréer la carte. Le cadrage initial et la sélection sont explicites ; les nouveaux points ne recentrent pas une exploration manuelle.

## Limites PWA

Android/iOS peuvent suspendre une PWA, restreindre le GPS en arrière-plan, lors du verrouillage ou pour économiser la batterie. Wake Lock est demandé au premier plan et réacquis quand la page redevient visible, lorsqu’il est disponible. Le navigateur reste maître de ses permissions. Aucun Service Worker n’essaie de maintenir une géolocalisation permanente. Le fonctionnement garanti par l’application concerne le premier plan autorisé ; l’exploitation conserve la dernière mesure et reçoit les états d’interruption.

## Recette

Backend : `python -m pytest backend/apps/erp/tests/test_tracking.py backend/apps/erp/tests/test_tracking_realtime.py -q`.
Navigateurs Vue/PWA : `pnpm --dir frontend exec playwright test gps.spec.ts`, ou `python e2e/parcours_gps.py`.
Le scénario utilise deux sessions contrôlées, une géolocalisation native simulée pour les déplacements et une injection des erreurs de permission. Les profils couvrent desktop Chromium, Android, iPhone/WebKit, iPad/WebKit et smartphone 320/360 px. Les comptes et missions sont préfixés TEST ; aucun trajet réel n’est simulé comme preuve physique.

La lecture de flotte calcule la fraîcheur sans mutation ni verrou d’entreprise. Le contrôle automatique prend un verrou non bloquant (`skip_locked`) et reprend les entreprises occupées au prochain passage : deux workers ne produisent pas deux alertes et une opération métier ne bloque pas la consultation de carte.

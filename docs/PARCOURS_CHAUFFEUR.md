# Terrain et notifications

Auteur : Jonathan Kakesa (JonathanK-N)

## Accès et utilisation

Le menu **Terrain & notifications** et la cloche ouvrent le suivi terrain.
Le chauffeur choisit uniquement une mission qui lui est affectée. L’administration,
l’exploitation et l’atelier consultent les déclarations de leur entreprise.
L’atelier traite les dossiers depuis les modules Incidents et Entretien.

**Nouvelle déclaration** propose quatre formulaires :

- Incident : panne, accident, marchandise, retard ou autre événement, avec gravité,
  description et compteur facultatif. Le dossier est immédiatement signalé dans
  Incidents. Sa résolution et le retour saisi deviennent visibles au chauffeur.
- Demande d’intervention : crée une intervention planifiée dans Entretien ; le
  chauffeur suit son avancement et le compte rendu de l’atelier.
- Contrôle avant départ : freins, pneus, éclairage, niveaux/fuites, équipements de
  sécurité et documents du véhicule. Tous les points doivent être renseignés.
  Une anomalie exige une description, crée une demande atelier et bloque le départ
  jusqu’à un nouveau contrôle conforme. Les contrôles précédents restent conservés.
- Relevé kilométrique : met à jour le compteur du véhicule avec un historique daté
  et attribué à son auteur. Un compteur inférieur au précédent est refusé.

Les contrôles sont proposés pour les missions planifiées. Ils ne sont pas imposés
rétroactivement aux missions existantes sans contrôle ; dès qu’un contrôle existe,
le dernier résultat conditionne le démarrage. Les anomalies doivent être traitées
avant que le chauffeur atteste un nouveau contrôle conforme.

Après enregistrement, joindre les photos ou justificatifs PDF/JPEG/PNG, chacun
limité à 10 Mo. Ces pièces restent privées au circuit terrain et ne sont pas
publiées dans le portail client. Le chauffeur ne peut ni résoudre lui-même un
incident ni modifier les coûts et décisions d’atelier.

## Notifications

Le centre affiche les missions planifiées/en cours, leurs changements, les
interventions et les retours liés aux déclarations. Il affiche aussi les échéances
d’assurance et de visite technique des véhicules affectés à des missions ouvertes.

Les entretiens sont prioritaires à la date d’échéance ou au kilométrage prévu.
Ils sont signalés à l’approche de sept jours ou de 500 km. Les échéances de documents
sont signalées à trente jours. Les valeurs proviennent des fiches saisies par
l’entreprise ; aucun programme constructeur n’est déduit automatiquement.

**Marquer comme lu** conserve l’état pour l’utilisateur et l’entreprise. Un
changement de statut ou le passage d’un seuil produit un nouvel état non lu.
Les notifications prioritaires puis non lues sont présentées en premier.
Le suivi se rafraîchit chaque minute tant que cet écran est ouvert et visible ;
le bouton Actualiser permet une vérification immédiate.

Il s’agit de notifications dans l’application. Aucun SMS, message WhatsApp,
courriel ou push lorsque le navigateur est fermé n’est envoyé par ce module.
Les déclarations et pièces jointes nécessitent une connexion au serveur.

## Isolation et déploiement

Les accès sont vérifiés côté serveur, y compris les pièces jointes, et les
références entre entreprises sont contraintes dans PostgreSQL. Un chauffeur
réaffecté ne conserve pas l’accès aux missions de son remplaçant. Les dossiers
restent accessibles à l’administration de leur entreprise.

Appliquer les migrations 0012 et 0013, puis reconstruire l’interface. Comme pour
les autres documents privés, sauvegarder le volume des fichiers en plus de la
base PostgreSQL. Aucun nouveau compte ni mot de passe n’est inclus dans ces
migrations.

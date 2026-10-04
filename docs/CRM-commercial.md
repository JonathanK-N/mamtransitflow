# Clients et workflow commercial

Le module Clients réutilise Partner (customer/both), Invoice (kind=quote/invoice/credit), TransportOrder, Mission, DeliveryReceipt, Payment et Document. Aucun deuxième référentiel client n’est créé.

## Parcours

Créer un client et ses contacts, puis un devis depuis sa fiche. Le bouton « Marquer comme envoyé » attribue le numéro DEV et fige le devis ; il ne déclenche pas un email de devis. Accepter, refuser ou constater son expiration. La conversion d’un devis accepté crée une seule commande, conservant le lien et les conditions du devis. Confirmer puis planifier la mission, avec le chauffeur et le véhicule disponibles. Les références CMD/MIS sont attribuées automatiquement si elles ne sont pas fournies.

Démarrer la mission utilise le suivi GPS existant. Terminer puis signer la livraison utilise les composants existants, sans modifier les snapshots signés. « Créer la facture » produit un brouillon lié à la mission et à sa commande, reprend les taxes du devis et les délais de paiement du client. L’émission reste explicite. Enregistrer des paiements partiels puis le solde utilise les écritures comptables existantes. Les avoirs émis réduisent le solde ; les devis et brouillons ne gonflent pas les indicateurs financiers.

## Fiche client

Recherche et pagination serveur, tri, contacts, coordonnées, notes internes, avertissement de doublons, compteurs et montants agrégés, devis, commandes, missions/livraisons, factures, paiements, documents et activité. L’archivage exclut le client des nouvelles prestations sans supprimer son historique ; la restauration est possible. La suppression physique par l’API est interdite.

## Portail et messages

Seul un administrateur peut inviter, renvoyer, annuler, suspendre ou réactiver un accès. Le portail montre les commandes et livraisons du client, les factures émises/soldées et les documents explicitement partagés. Les brouillons, devis, notes internes, personnel, GPS brut, autres clients et conversations internes restent inaccessibles. Les commandes présentent leur étape commerciale actuelle.

Les messages externes utilisent ClientConversation/ClientMessage, rattachés à un PortalAccess, indépendamment des conversations internes. Texte uniquement, pagination, rafraîchissement visible toutes les quinze secondes, identifiant de tentative pour éviter les doubles envois. Une suspension interdit l’accès. Plusieurs accès client sont pris en charge par l’API via access ; la fiche utilise le dernier accès par défaut. La messagerie interne conserve son fonctionnement temps réel.

## Rôles

| Rôle | Clients | Commercial et finance | Opérations | Portail |
|---|---|---|---|---|
| Propriétaire/administrateur | Lecture/écriture | Lecture/écriture | Lecture/écriture | Gestion et messages |
| Exploitation | Lecture/écriture | Masqués | Selon les permissions existantes | Messages externes |
| Finance | Lecture/écriture | Lecture/écriture | Lecture selon les permissions existantes, conversion en commande réservée aux rôles autorisés | Messages externes |
| Atelier | Référentiel partenaires selon les permissions existantes | Masqués | Atelier selon les permissions existantes | Aucune gestion |
| Observateur | Lecture | Lecture selon les modules autorisés | Lecture | Aucune gestion |
| Chauffeur | Pas de CRM | Masqués | Missions attribuées et GPS existants | Aucun portail interne |
| Client | Son portail exclusivement | Ses factures publiées | Ses prestations publiées | Ses messages externes |

Les modules activés limitent également chaque onglet, action et notification. Les contrôles sont exécutés côté serveur.

## Données et intégrité

Migrations additives 0018–0023 : adresse/archivage Partner, PartnerContact, lien du devis vers sa commande, champs commerciaux Invoice/TransportOrder, lien Invoice.mission, Document.customer, Payment.notes, conversations externes, index et reprise des états des devis existants. Les contraintes composites PostgreSQL imposent l’organisation identique sur les nouvelles relations. Les créations et conversions sensibles verrouillent l’organisation dans une transaction ; la conversion et la facture de mission sont idempotentes. Les noms et emails partagés entre clients ne sont pas soumis à une unicité artificielle.

Les indicateurs utilisent agrégations Decimal et sous-requêtes de crédits, la pagination est limitée à cent éléments, l’activité filtre les objets liés en SQL et respecte les permissions. Index sur répertoire clients, commandes clients, factures clients et audit. Un test de volume couvre 500 clients et 1 000 factures avec plafonds de requêtes pour la liste et la fiche.

## Vérification

La recette CI utilise PostgreSQL, Redis et deux workers ASGI : tests backend, contraintes, concurrence, puis navigateur desktop, Android, iPhone, iPad et petit écran. Le scénario CRM réalise le cycle jusqu’au solde, signe la livraison, reçoit une position du navigateur chauffeur et accepte le portail dans une deuxième session. Les scénarios GPS/PWA/messagerie/personnel/portail existants restent obligatoires. La géolocalisation des tests est simulée par le navigateur ; elle ne démontre pas la réception GPS d’un appareil physique en arrière-plan.

En production, utiliser uniquement une organisation et des utilisateurs TEST dédiés. Conserver les documents commerciaux comme preuves, archiver le client, suspendre le portail, retirer le chauffeur et retirer le véhicule après la recette. Aucun nettoyage des limites d’authentification de production.

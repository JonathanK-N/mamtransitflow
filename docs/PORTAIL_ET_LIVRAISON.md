# Portail client et justificatifs de livraison

Auteur : Jonathan Kakesa (JonathanK-N)

## Activer les accès clients

L’application **Portail client** dépend des applications transport, finance et
documents. Chaque entreprise garde ses propres activations et ses propres accès.
Dans l’administration du portail, sélectionner une fiche client, saisir son
courriel puis créer une invitation. Le lien expire après sept jours. La messagerie
doit être configurée pour envoyer le courriel ; sinon l’administrateur copie le
lien et le transmet au destinataire.

Le destinataire crée son compte depuis ce lien ou accepte l’invitation avec son
compte existant. Il accède uniquement aux commandes publiées, livraisons, factures
émises et documents explicitement partagés de sa fiche client. Il ne devient pas
un collaborateur interne. Les données du personnel, la comptabilité interne et
les autres clients restent inaccessibles. Révoquer un accès prend effet sur les
requêtes suivantes, même si le navigateur conserve une session ouverte.

## Faire signer une livraison

1. Terminer la mission et vérifier les quantités livrées et le bilan.
2. Ouvrir **Justificatif signé** dans les missions.
3. Renseigner le nom et les réserves du destinataire, recueillir sa signature
   dans le cadre et son accord, puis confirmer.
4. Télécharger le PDF. Le client concerné le retrouve dans **Mes livraisons**.

Le chauffeur travaille uniquement sur les missions qui lui sont affectées.
L’administration et l’exploitation peuvent également enregistrer une signature.
Une livraison déjà signée ne peut pas être signée à nouveau ou modifiée par ces
API. Les informations de livraison sont figées dans le justificatif avec une
empreinte SHA-256 et une date serveur UTC. Il s’agit d’une signature manuscrite
capturée, sans certification de l’identité du signataire ni signature électronique
qualifiée.

## Joindre les pièces complémentaires

Pendant une mission démarrée ou après sa clôture, ouvrir les documents de livraison
pour ajouter un PDF, JPEG ou PNG de 10 Mo maximum. Les pièces restent internes par
défaut. Cocher le partage uniquement si elles doivent apparaître dans le portail
du client lié à la commande. Ces pièces complémentaires ne font pas partie de
l’empreinte du justificatif signé.

Les fichiers sont téléchargés par des routes authentifiées ; aucun répertoire
public ne les expose. Leur persistance exige un volume privé durable ou un stockage
adapté, avec sauvegarde distincte de PostgreSQL. Voir [Exploitation](EXPLOITATION_ERP.md).

## Déploiement et vérifications

Installer les dépendances incluant ReportLab, appliquer les migrations 0008 à
0011 et reconstruire le frontend. Ces migrations ajoutent les justificatifs,
accès clients, indicateur de partage et contraintes de référence par entreprise.
Elles ne créent aucun compte de démonstration ni mot de passe.

Les tests couvrent la confidentialité entre entreprises et entre clients,
la révocation, la désactivation du module, les signatures invalides, la conservation
du justificatif et les droits du chauffeur. La recette Chromium traverse
l’inscription sur invitation, la signature, le téléchargement PDF et le portail.

# Documents financiers

Factures, devis et avoirs utilisent le même aperçu depuis leur fiche dans Facturation. Le portail client utilise ce même rendu pour ses factures accessibles. Le bouton « Imprimer / enregistrer en PDF » utilise l'impression du navigateur ; aucun second moteur de facturation ou service PDF n'est ajouté.

L'aperçu affiche l'entreprise, ses coordonnées et identifiants, le client, le numéro serveur, les dates, les références liées, les prestations, taxes et totaux calculés par le serveur. Un document non émis reste explicitement marqué BROUILLON. Les factures affichent les paiements et le solde. Les avoirs affichent la référence de leur facture d'origine.

Le portail reçoit uniquement les coordonnées publiques du client et les champs autorisés des lignes. Les notes internes du référentiel client et les métadonnées arbitraires d'une ligne ne sont pas transmises. Les droits existants du portail continuent de filtrer les factures par client et entreprise.

Le rendu est adapté aux petits écrans. L'impression A4 répète les en-têtes du tableau, évite de couper une prestation et masque les contrôles. Échap ferme uniquement l'aperçu ; le focus revient au bouton qui l'a ouvert. La fermeture reste disponible après le passage en mode impression.

Les recettes couvrent une facture de 200 lignes, les centimes et taxes, les caractères internationaux, un devis brouillon, un avoir lié, l'impression, le clavier, l'absence de débordement à 320 pixels et une seconde session client. Les profils Chromium, Android, iPhone, iPad et 320 pixels sont exécutés en CI. La variable de recette locale `TF_TEST_PRINT_PDF=1`, uniquement avec Chromium, conserve également l'impression PDF pour son inspection visuelle.

La pagination et le choix d'imprimante dépendent du navigateur. Une recette automatisée ne valide pas toutes les imprimantes physiques.

Les saisies numériques de l'éditeur sont transmises comme texte afin de préserver les centimes sans conversion JavaScript en flottants. Les calculs et validations restent côté serveur. La recette vérifie notamment le prix transmis de `99999999999999.99`, puis le total émis sur PostgreSQL et son rendu. SQLite ne garantit pas cette précision de stockage : `TF_TEST_SQLITE_PRECISION=1` est réservé à la recette locale, où seul le DTO de lecture de cette facture extrême est remplacé pour contrôler le rendu ; il n'est pas activé en CI PostgreSQL.

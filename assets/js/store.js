/* TransitFlow — client de l API backend
   Auteur original : Mamadou Barry (version localStorage)
   Modifie par : Jonathan K-N — remplace le localStorage par des appels
   fetch() vers l API Flask (dossier backend/). Les noms de methode de
   Store restent les memes qu avant (Store.chauffeurs(), Store.trajet(id),
   etc.), mais chacune renvoie maintenant une promesse : il faut donc
   utiliser "await Store.xxx(...)" partout ou Store est appele
   (voir admin.js et chauffeur.js). */

// Cle utilisee pour garder la session (avec son jeton de connexion)
// dans sessionStorage. Doit rester identique a SESSION_KEY dans auth.js
// puisque les deux fichiers lisent/ecrivent la meme entree.
const TF_SESSION_KEY = 'transitflow.session';

// Prefixe de toutes les routes de l API (voir backend/app.py et
// backend/routes/). Comme le front-end est servi par le meme serveur
// Flask que l API, un chemin relatif comme '/api' suffit : il n y a pas
// besoin de preciser un nom de domaine ou un port.
const API_BASE = '/api';

/*
 * Fonction centrale utilisee par toutes les methodes de Store pour
 * parler a l API :
 * 1. elle recupere le jeton de connexion dans sessionStorage et l ajoute
 *    a l entete "Authorization" (le serveur en a besoin pour savoir
 *    qui fait la demande, voir backend/routes/__init__.py) ;
 * 2. si le serveur repond 401 (jeton invalide/expire), on efface la
 *    session locale et on renvoie l utilisateur a la page de connexion ;
 * 3. sinon, si la reponse n est pas un succes, on transforme le message
 *    d erreur du serveur en exception JavaScript ;
 * 4. si tout va bien, on renvoie les donnees JSON de la reponse.
 */
async function tfRequete(chemin, options) {
  options = options || {};
  const entetes = Object.assign({ 'Content-Type': 'application/json' }, options.headers || {});
  let jeton = null;
  try {
    const brut = sessionStorage.getItem(TF_SESSION_KEY);
    jeton = brut ? JSON.parse(brut).jeton : null;
  } catch (e) { jeton = null; }
  if (jeton) entetes.Authorization = 'Bearer ' + jeton;

  const reponse = await fetch(API_BASE + chemin, Object.assign({}, options, { headers: entetes }));

  if (reponse.status === 401) {
    // Session expiree ou jeton invalide : on nettoie et on renvoie vers la connexion,
    // sauf si on est deja sur la page de connexion (pour eviter une boucle de redirections).
    sessionStorage.removeItem(TF_SESSION_KEY);
    if (!window.location.pathname.replace(/\/+/g, '/').endsWith('/index.html') && window.location.pathname !== '/') {
      window.location.href = '/index.html';
    }
    throw new Error('Session expiree ou invalide.');
  }

  const donnees = await reponse.json().catch(function () { return {}; });
  if (!reponse.ok) {
    throw new Error(donnees.message || 'Erreur de communication avec le serveur.');
  }
  return donnees;
}

/* Transforme un objet de filtres ({statut: 'ouvert', ...}) en chaine de
   requete ("?statut=ouvert"), en ignorant les valeurs vides/absentes. */
function tfParametres(filtre) {
  const params = new URLSearchParams();
  Object.keys(filtre || {}).forEach(function (cle) {
    if (filtre[cle]) params.set(cle, filtre[cle]);
  });
  const chaine = params.toString();
  return chaine ? '?' + chaine : '';
}

/*
 * Store expose les memes methodes qu avant (une par action possible :
 * lister, obtenir, ajouter, modifier...), mais chacune est maintenant
 * "async" et va chercher les donnees sur le serveur au lieu de les lire
 * dans le localStorage du navigateur. Quand une fiche n existe pas
 * (ex. Store.chauffeur('inconnu')), on attrape l erreur et on renvoie
 * null, exactement comme le faisait l ancienne version avec le
 * localStorage - le reste du code (admin.js, chauffeur.js) n a donc
 * pas besoin de changer sa facon de vérifier "si ca n existe pas".
 */
const Store = {
  /* Chauffeurs */
  async chauffeurs(filtre) {
    const donnees = await tfRequete('/chauffeurs' + tfParametres(filtre));
    return donnees.chauffeurs;
  },

  async chauffeur(id) {
    try {
      const donnees = await tfRequete('/chauffeurs/' + encodeURIComponent(id));
      return donnees.chauffeur;
    } catch (e) { return null; }
  },

  async ajouterChauffeur(chauffeur) {
    const donnees = await tfRequete('/chauffeurs', { method: 'POST', body: JSON.stringify(chauffeur) });
    return donnees.chauffeur;
  },

  async majChauffeur(id, champs) {
    try {
      const donnees = await tfRequete('/chauffeurs/' + encodeURIComponent(id),
        { method: 'PATCH', body: JSON.stringify(champs) });
      return donnees.chauffeur;
    } catch (e) { return null; }
  },

  /* Trajets */
  async trajets(filtre) {
    const donnees = await tfRequete('/trajets' + tfParametres(filtre));
    return donnees.trajets;
  },

  async trajet(id) {
    try {
      const donnees = await tfRequete('/trajets/' + encodeURIComponent(id));
      return donnees.trajet;
    } catch (e) { return null; }
  },

  async trajetEnCours(chauffeurId) {
    const donnees = await tfRequete('/trajets/en-cours/' + encodeURIComponent(chauffeurId));
    return donnees.trajet;
  },

  async ajouterTrajet(trajet) {
    // Le serveur ignore un chauffeurId envoye ici : il utilise toujours
    // celui de la session connectee (voir backend/routes/trajets_routes.py).
    const donnees = await tfRequete('/trajets', { method: 'POST', body: JSON.stringify(trajet) });
    return donnees.trajet;
  },

  async ajouterArret(trajetId, arret) {
    try {
      const donnees = await tfRequete('/trajets/' + encodeURIComponent(trajetId) + '/arrets',
        { method: 'POST', body: JSON.stringify(arret) });
      return donnees.trajet;
    } catch (e) { return null; }
  },

  async terminerTrajet(trajetId) {
    try {
      const donnees = await tfRequete('/trajets/' + encodeURIComponent(trajetId) + '/terminer',
        { method: 'POST' });
      return donnees.trajet;
    } catch (e) { return null; }
  },

  /* Incidents */
  async incidents(filtre) {
    const donnees = await tfRequete('/incidents' + tfParametres(filtre));
    return donnees.incidents;
  },

  async incident(id) {
    try {
      const donnees = await tfRequete('/incidents/' + encodeURIComponent(id));
      return donnees.incident;
    } catch (e) { return null; }
  },

  async ajouterIncident(incident) {
    const donnees = await tfRequete('/incidents', { method: 'POST', body: JSON.stringify(incident) });
    return donnees.incident;
  },

  async traiterIncident(id) {
    try {
      const donnees = await tfRequete('/incidents/' + encodeURIComponent(id) + '/traiter', { method: 'POST' });
      return donnees.incident;
    } catch (e) { return null; }
  },

  async vehicules() {
    const donnees = await tfRequete('/vehicules');
    return donnees.vehicules;
  },

  /* Indicateurs du tableau de bord */
  async indicateurs() {
    const donnees = await tfRequete('/indicateurs');
    return donnees.indicateurs;
  }
};

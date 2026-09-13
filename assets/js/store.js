/* TransitFlow — client de l API backend
   Auteur : Mamadou Barry */

const TF_SESSION_KEY = 'transitflow.session';
const API_BASE = '/api';

/* Construit une requete authentifiee vers l API et normalise la reponse. */
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

function tfParametres(filtre) {
  const params = new URLSearchParams();
  Object.keys(filtre || {}).forEach(function (cle) {
    if (filtre[cle]) params.set(cle, filtre[cle]);
  });
  const chaine = params.toString();
  return chaine ? '?' + chaine : '';
}

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

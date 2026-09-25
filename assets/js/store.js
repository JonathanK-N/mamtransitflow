/* TransitFlow — client de l API backend
   Auteur original : Mamadou Barry (version localStorage)
   Modifie par : Jonathan K-N — remplace le localStorage par des appels
   fetch() vers l API Django (dossier backend/). Les noms de methode de
   Store restent les memes qu avant (Store.chauffeurs(), Store.trajet(id),
   etc.), mais chacune renvoie une promesse : il faut donc utiliser
   "await Store.xxx(...)" partout ou Store est appele (voir admin.js et
   chauffeur.js). */

// Cle utilisee pour garder la session (jeton d acces + jeton de
// rafraichissement) dans sessionStorage. Doit rester identique a
// SESSION_KEY dans auth.js puisque les deux fichiers lisent/ecrivent la
// meme entree.
const TF_SESSION_KEY = 'transitflow.session';

// Prefixe de toutes les routes de l API (voir backend/apps/*/urls.py).
// Django sert le front-end et l API depuis le meme serveur : un chemin
// relatif suffit, quel que soit le domaine (local ou Railway).
const API_BASE = '/api';

function tfLireSession() {
  try { return JSON.parse(sessionStorage.getItem(TF_SESSION_KEY)); }
  catch (e) { return null; }
}

function tfEcrireSession(session) {
  sessionStorage.setItem(TF_SESSION_KEY, JSON.stringify(session));
}

/* Vrai des que le navigateur commence a quitter la page (voir tfRequete). */
let tfPageQuittee = false;
window.addEventListener('pagehide', function () { tfPageQuittee = true; });
window.addEventListener('pageshow', function () { tfPageQuittee = false; });

/* Renvoie a la page de connexion (sauf si on y est deja, pour eviter une boucle). */
function tfRetourConnexion() {
  sessionStorage.removeItem(TF_SESSION_KEY);
  const chemin = window.location.pathname.replace(/\/+/g, '/');
  if (!chemin.endsWith('/index.html') && chemin !== '/') {
    window.location.href = '/index.html';
  }
}

/* Affiche un message en bas de l ecran pendant quelques secondes (erreur ou confirmation). */
function tfNotifier(message, type) {
  let zone = document.querySelector('[data-tf-notifications]');
  if (!zone) {
    zone = document.createElement('div');
    zone.className = 'tf-toasts';
    zone.setAttribute('data-tf-notifications', '');
    zone.setAttribute('role', 'status');
    document.body.appendChild(zone);
  }
  const bulle = document.createElement('div');
  bulle.className = 'tf-toast ' + (type || 'erreur');
  bulle.textContent = message;
  zone.appendChild(bulle);
  setTimeout(function () { bulle.remove(); }, 6000);
}

/* Desactive le bouton d envoi pendant la requete (evite les doubles clics) et affiche l erreur eventuelle. */
async function tfEnvoyer(formulaire, action) {
  const bouton = formulaire.querySelector('[type=submit]');
  if (bouton) bouton.disabled = true;
  try {
    await action();
  } catch (e) {
    tfNotifier(e.message);
  } finally {
    if (bouton) bouton.disabled = false;
  }
}

/*
 * Echange le jeton de rafraichissement contre un nouveau jeton d acces
 * (POST /api/auth/rafraichir). Plusieurs requetes peuvent recevoir un 401
 * en meme temps : elles partagent alors la meme demande de renouvellement.
 */
let tfRenouvellementEnCours = null;
function tfRenouvelerJeton() {
  if (tfRenouvellementEnCours) return tfRenouvellementEnCours;
  tfRenouvellementEnCours = (async function () {
    const session = tfLireSession();
    if (!session || !session.rafraichissement) return false;
    try {
      const reponse = await fetch(API_BASE + '/auth/rafraichir', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rafraichissement: session.rafraichissement })
      });
      if (!reponse.ok) return false;
      const donnees = await reponse.json();
      session.jeton = donnees.jeton;
      session.rafraichissement = donnees.rafraichissement;
      tfEcrireSession(session);
      return true;
    } catch (e) {
      return false;
    }
  })();
  tfRenouvellementEnCours.finally(function () { tfRenouvellementEnCours = null; });
  return tfRenouvellementEnCours;
}

/* Premier message d erreur lisible d une reponse DRF ({message}, {detail} ou {champ: [erreurs]}). */
function tfMessageErreur(donnees) {
  if (!donnees) return 'Erreur de communication avec le serveur.';
  if (donnees.message) return donnees.message;
  if (donnees.detail) return donnees.detail;
  for (const cle of Object.keys(donnees)) {
    const valeur = donnees[cle];
    if (Array.isArray(valeur) && valeur.length) {
      return (cle === 'non_field_errors' ? '' : cle + ' : ') + valeur[0];
    }
    if (typeof valeur === 'string' && cle !== 'ok') return valeur;
  }
  return 'Erreur de communication avec le serveur.';
}

/*
 * Fonction centrale utilisee par toutes les methodes de Store pour
 * parler a l API (options.reponseBrute : renvoie la Response telle quelle,
 * pour un telechargement de fichier) :
 * 1. elle ajoute le jeton d acces a l entete "Authorization" ;
 * 2. si le serveur repond 401 (jeton expire), elle renouvelle le jeton
 *    une fois puis rejoue la requete ; si c est impossible, elle renvoie
 *    a la page de connexion ;
 * 3. si la reponse n est pas un succes, elle leve une Error avec le
 *    message du serveur ;
 * 4. sinon, elle renvoie les donnees JSON de la reponse.
 */
async function tfRequete(chemin, options, dejaRenouvele) {
  options = options || {};
  const entetes = Object.assign({ 'Content-Type': 'application/json' }, options.headers || {});
  const session = tfLireSession();
  if (session && session.jeton) entetes.Authorization = 'Bearer ' + session.jeton;

  let reponse;
  try {
    reponse = await fetch(API_BASE + chemin, Object.assign({}, options, { headers: entetes }));
  } catch (e) {
    // Requete interrompue parce que l utilisateur quitte la page (clic sur
    // un lien pendant le chargement) : ce n est pas une panne, on n affiche rien.
    if (tfPageQuittee) return new Promise(function () {});
    throw new Error('Impossible de joindre le serveur. Verifiez votre connexion.');
  }

  if (reponse.status === 401) {
    if (!dejaRenouvele && await tfRenouvelerJeton()) {
      return tfRequete(chemin, options, true);
    }
    tfRetourConnexion();
    throw new Error('Session expiree, veuillez vous reconnecter.');
  }

  if (options.reponseBrute && reponse.ok) return reponse;

  const donnees = await reponse.json().catch(function () { return {}; });
  if (!reponse.ok) {
    const erreur = new Error(tfMessageErreur(donnees));
    erreur.statut = reponse.status;
    throw erreur;
  }
  return donnees;
}

/* Comme tfRequete, mais renvoie null quand la ressource n existe pas (404). */
async function tfRequeteOuNull(chemin, options) {
  try {
    return await tfRequete(chemin, options);
  } catch (e) {
    if (e.statut === 404) return null;
    throw e;
  }
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
 * Store expose une methode par action possible (lister, obtenir,
 * ajouter, modifier...). Quand une fiche n existe pas (404), la methode
 * renvoie null, comme le faisait la version localStorage ; les autres
 * erreurs (droits, validation, reseau) sont levees pour etre affichees.
 */
const Store = {
  /* Chauffeurs */
  async chauffeurs(filtre) {
    const donnees = await tfRequete('/chauffeurs' + tfParametres(filtre));
    return donnees.chauffeurs;
  },

  /* Dictionnaire id -> chauffeur, pour afficher les noms dans les listes sans une requete par ligne. */
  async chauffeursParId() {
    const index = {};
    (await this.chauffeurs()).forEach(function (c) { index[c.id] = c; });
    return index;
  },

  async chauffeur(id) {
    if (!id) return null;
    const donnees = await tfRequeteOuNull('/chauffeurs/' + encodeURIComponent(id));
    return donnees ? donnees.chauffeur : null;
  },

  /* Renvoie {chauffeur, motDePasseInitial} : le mot de passe n est present que s il a ete genere. */
  async ajouterChauffeur(chauffeur) {
    const donnees = await tfRequete('/chauffeurs', { method: 'POST', body: JSON.stringify(chauffeur) });
    return { chauffeur: donnees.chauffeur, motDePasseInitial: donnees.motDePasseInitial || null };
  },

  async majChauffeur(id, champs) {
    const donnees = await tfRequete('/chauffeurs/' + encodeURIComponent(id),
      { method: 'PATCH', body: JSON.stringify(champs) });
    return donnees.chauffeur;
  },

  /* Trajets */
  async trajets(filtre) {
    const donnees = await tfRequete('/trajets' + tfParametres(filtre));
    return donnees.trajets;
  },

  async trajet(id) {
    if (!id) return null;
    const donnees = await tfRequeteOuNull('/trajets/' + encodeURIComponent(id));
    return donnees ? donnees.trajet : null;
  },

  async trajetEnCours(chauffeurId) {
    if (!chauffeurId) return null;
    const donnees = await tfRequete('/trajets/en-cours/' + encodeURIComponent(chauffeurId));
    return donnees.trajet;
  },

  async ajouterTrajet(trajet) {
    // Le chauffeur du trajet est toujours celui de la session connectee
    // (voir backend/apps/dispatch/views.py) : inutile de l envoyer.
    const donnees = await tfRequete('/trajets', { method: 'POST', body: JSON.stringify(trajet) });
    return donnees.trajet;
  },

  async ajouterArret(trajetId, arret) {
    const donnees = await tfRequete('/trajets/' + encodeURIComponent(trajetId) + '/arrets',
      { method: 'POST', body: JSON.stringify(arret) });
    return donnees.trajet;
  },

  /* kilometrage (facultatif) : compteur du vehicule a l arrivee, pour le suivi d entretien. */
  async terminerTrajet(trajetId, kilometrage) {
    const corps = (kilometrage === undefined || kilometrage === null || kilometrage === '')
      ? {} : { kilometrage: Number(kilometrage) };
    const donnees = await tfRequete('/trajets/' + encodeURIComponent(trajetId) + '/terminer',
      { method: 'POST', body: JSON.stringify(corps) });
    return donnees.trajet;
  },

  /* Incidents */
  async incidents(filtre) {
    const donnees = await tfRequete('/incidents' + tfParametres(filtre));
    return donnees.incidents;
  },

  async incident(id) {
    if (!id) return null;
    const donnees = await tfRequeteOuNull('/incidents/' + encodeURIComponent(id));
    return donnees ? donnees.incident : null;
  },

  async ajouterIncident(incident) {
    const donnees = await tfRequete('/incidents', { method: 'POST', body: JSON.stringify(incident) });
    return donnees.incident;
  },

  async traiterIncident(id) {
    const donnees = await tfRequete('/incidents/' + encodeURIComponent(id) + '/traiter', { method: 'POST' });
    return donnees.incident;
  },

  /* Vehicules */
  async vehicules(filtre) {
    const donnees = await tfRequete('/vehicules' + tfParametres(filtre));
    return donnees.vehicules;
  },

  async ajouterVehicule(vehicule) {
    const donnees = await tfRequete('/vehicules', { method: 'POST', body: JSON.stringify(vehicule) });
    return donnees.vehicule;
  },

  /* Fiche complete : {vehicule, releves, chauffeursHabituels}, ou null si la plaque n existe pas. */
  async vehicule(plaque) {
    if (!plaque) return null;
    return tfRequeteOuNull('/vehicules/' + encodeURIComponent(plaque));
  },

  async majVehicule(plaque, champs) {
    const donnees = await tfRequete('/vehicules/' + encodeURIComponent(plaque),
      { method: 'PATCH', body: JSON.stringify(champs) });
    return donnees.vehicule;
  },

  async releverKilometrage(plaque, kilometrage, note) {
    const donnees = await tfRequete('/vehicules/' + encodeURIComponent(plaque) + '/kilometrage',
      { method: 'POST', body: JSON.stringify({ kilometrage: Number(kilometrage), note: note || '' }) });
    return donnees.vehicule;
  },

  /* Entretien : plans preventifs */
  async plansEntretien(filtre) {
    const donnees = await tfRequete('/entretien/plans' + tfParametres(filtre));
    return donnees.plans;
  },

  async ajouterPlan(plan) {
    const donnees = await tfRequete('/entretien/plans', { method: 'POST', body: JSON.stringify(plan) });
    return donnees.plan;
  },

  async majPlan(id, champs) {
    const donnees = await tfRequete('/entretien/plans/' + encodeURIComponent(id),
      { method: 'PATCH', body: JSON.stringify(champs) });
    return donnees.plan;
  },

  async desactiverPlan(id) {
    const donnees = await tfRequete('/entretien/plans/' + encodeURIComponent(id), { method: 'DELETE' });
    return donnees.plan;
  },

  /* {echeances, resume} ; tous=true inclut les plans a jour. */
  async echeances(tous) {
    return tfRequete('/entretien/echeances' + (tous ? '?tous=1' : ''));
  },

  /* Entretien : bons de travail */
  async bonsTravail(filtre) {
    const donnees = await tfRequete('/entretien/bons' + tfParametres(filtre));
    return donnees.bons;
  },

  async bonTravail(id) {
    if (!id) return null;
    const donnees = await tfRequeteOuNull('/entretien/bons/' + encodeURIComponent(id));
    return donnees ? donnees.bon : null;
  },

  async ajouterBon(bon) {
    const donnees = await tfRequete('/entretien/bons', { method: 'POST', body: JSON.stringify(bon) });
    return donnees.bon;
  },

  async majBon(id, champs) {
    const donnees = await tfRequete('/entretien/bons/' + encodeURIComponent(id),
      { method: 'PATCH', body: JSON.stringify(champs) });
    return donnees.bon;
  },

  /* action : 'demarrer', 'terminer' ou 'annuler' ; corps selon l action (voir backend/apps/entretien/views.py). */
  async actionBon(id, action, corps) {
    const donnees = await tfRequete('/entretien/bons/' + encodeURIComponent(id) + '/' + action,
      { method: 'POST', body: JSON.stringify(corps || {}) });
    return donnees.bon;
  },

  async coutsEntretien(filtre) {
    return tfRequete('/entretien/couts' + tfParametres(filtre));
  },

  /* Telecharge l export CSV des bons (memes filtres que la liste). */
  async exporterBons(filtre) {
    const reponse = await tfRequete('/entretien/export.csv' + tfParametres(filtre), { reponseBrute: true });
    const fichier = await reponse.blob();
    const nom = (/filename="([^"]+)"/.exec(reponse.headers.get('Content-Disposition') || '') || [])[1] ||
      'bons-de-travail.csv';
    const lien = document.createElement('a');
    lien.href = URL.createObjectURL(fichier);
    lien.download = nom;
    document.body.appendChild(lien);
    lien.click();
    lien.remove();
    setTimeout(function () { URL.revokeObjectURL(lien.href); }, 1000);
  },

  /* Indicateurs du tableau de bord */
  async indicateurs() {
    const donnees = await tfRequete('/indicateurs');
    return donnees.indicateurs;
  }
};

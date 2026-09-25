/* TransitFlow — session et garde de page
   Auteur original : Mamadou Barry
   Modifie par : Jonathan K-N — Auth.connecter() et Auth.deconnecter()
   appellent l API Django (/api/auth/connexion et /api/auth/deconnexion)
   au lieu de valider les comptes dans le navigateur. La session gardee en
   sessionStorage contient en plus le jeton d acces et le jeton de
   rafraichissement recus du serveur, que store.js utilise a chaque
   requete. */

// Cle utilisee dans sessionStorage pour garder la session courante.
// Doit rester identique a TF_SESSION_KEY dans store.js.
const SESSION_KEY = 'transitflow.session';

const Auth = {
  /* Relit la session deja enregistree localement (ne contacte pas le serveur). */
  session() {
    try { return JSON.parse(sessionStorage.getItem(SESSION_KEY)); }
    catch (e) { return null; }
  },

  /*
   * Envoie courriel/mot de passe/role au serveur (POST /api/auth/connexion).
   * Le serveur repond soit par une erreur ({ok:false, message}), soit
   * par une session valide et ses jetons ({ok:true, session, jeton, rafraichissement}).
   */
  async connecter(courriel, motDePasse, role) {
    let reponse;
    try {
      reponse = await fetch('/api/auth/connexion', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ courriel: courriel, motDePasse: motDePasse, role: role })
      });
    } catch (e) {
      // Le serveur n est pas demarre, ou le reseau a coupe.
      return { ok: false, message: 'Impossible de joindre le serveur.' };
    }
    const donnees = await reponse.json().catch(function () { return {}; });
    if (!reponse.ok || !donnees.ok) {
      return { ok: false, message: donnees.message || 'Connexion refusee.' };
    }
    const session = Object.assign({}, donnees.session, {
      jeton: donnees.jeton,
      rafraichissement: donnees.rafraichissement
    });
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
    return { ok: true, session: session };
  },

  /* Invalide le jeton de rafraichissement cote serveur, puis nettoie la session locale et redirige. */
  async deconnecter(racine) {
    const session = this.session();
    if (session && session.rafraichissement) {
      try {
        await fetch('/api/auth/deconnexion', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ rafraichissement: session.rafraichissement })
        });
      } catch (e) { /* le serveur est peut-etre injoignable, on deconnecte quand meme */ }
    }
    sessionStorage.removeItem(SESSION_KEY);
    window.location.href = (racine || '../') + 'index.html';
  },

  /* Redirige vers la connexion si le role attendu n est pas celui de la session. */
  exiger(role, racine) {
    const s = this.session();
    if (!s || s.role !== role) {
      window.location.href = (racine || '../') + 'index.html';
      return null;
    }
    return s;
  },

  accueil(session) {
    return session.role === 'admin'
      ? 'admin/tableau-de-bord.html'
      : 'chauffeur/mes-trajets.html';
  }
};

/* Remplit la zone utilisateur de la barre de navigation et branche la deconnexion. */
function monterBarreUtilisateur(session, racine) {
  const zone = document.querySelector('[data-navbar-user]');
  if (!zone || !session) return;
  zone.innerHTML =
    '<span class="tf-avatar sm ' + (session.role === 'admin' ? 'on-dark' : '') + '">' +
      Format.echapper(session.initiales) + '</span>' +
    '<span>' + Format.echapper(session.nom) + '</span>' +
    '<button type="button" class="tf-btn tf-btn-outline-dark" ' +
      'style="height:34px;padding:0 14px;font-size:13px" data-deconnexion>Quitter</button>';
  zone.querySelector('[data-deconnexion]').addEventListener('click', function () {
    tfOublierEntreprise();
    Auth.deconnecter(racine);
  });
  // Les menus dependent de la configuration de l entreprise (voir tfMonterNavigation).
  window.tfNavigationPrete = tfMonterNavigation(session);
  window.tfNavigationPrete.catch(function () { /* page fermee : message deja affiche */ });
}

/* ---- Navigation generee selon l entreprise (modules et portail) ----------
   Auteur : Jonathan K-N

   Comme dans un ERP, les menus dependent de la configuration : un module
   desactive (entretien, suivi GPS, paie) disparait des menus de
   l administrateur, et le chauffeur ne voit que ce que l administrateur a
   ouvert dans son portail. Le serveur applique les memes regles (403) : le
   menu n est qu un reflet. La configuration est gardee 2 minutes en
   sessionStorage pour ne pas la redemander a chaque page. */

const TF_ENTREPRISE_CLE = 'transitflow.entreprise';

const TF_MENUS = {
  admin: [
    { href: 'tableau-de-bord.html', texte: 'Tableau de bord', pages: ['tableau-de-bord'] },
    { href: 'carte.html', texte: 'Carte', pages: ['carte'], module: 'suivi' },
    { href: 'trajets.html', texte: 'Trajets', pages: ['trajets', 'trajet'] },
    { href: 'incidents.html', texte: 'Incidents', pages: ['incidents'] },
    { href: 'chauffeurs.html', texte: 'Chauffeurs', pages: ['chauffeurs', 'chauffeur', 'chauffeur-nouveau'] },
    { href: 'paie.html', texte: 'Paie', pages: ['paie'], module: 'paie' },
    { href: 'vehicules.html', texte: 'Vehicules', pages: ['vehicules', 'vehicule'] },
    { href: 'entretiens.html', texte: 'Entretien', pages: ['entretiens'], module: 'entretien' },
    { href: 'parametres.html', texte: 'Parametres', pages: ['parametres'] }
  ],
  chauffeur: [
    { href: 'mes-trajets.html', texte: 'Mes trajets', pages: ['mes-trajets', 'trajet-en-cours'] },
    { href: 'trajet-nouveau.html', texte: 'Nouveau trajet', pages: ['trajet-nouveau'], portail: 'trajets' },
    { href: 'incident-nouveau.html', texte: 'Signaler un incident', pages: ['incident-nouveau'], portail: 'incidents' },
    { href: 'vehicule.html', texte: 'Mon vehicule', pages: ['vehicule'], portail: 'vehicule' },
    { href: 'paie.html', texte: 'Ma paie', pages: ['paie'], portail: 'paie' },
    { href: 'profil.html', texte: 'Mon profil', pages: ['profil'] }
  ]
};

/* Configuration de l entreprise (nom, modules, portail), depuis le cache ou l API. */
async function tfEntreprise(forcer) {
  if (!forcer) {
    try {
      const cache = JSON.parse(sessionStorage.getItem(TF_ENTREPRISE_CLE));
      if (cache && Date.now() - cache.le < 120000) return cache.entreprise;
    } catch (e) { /* cache illisible : on le redemande */ }
  }
  const donnees = await tfRequete('/entreprise');
  sessionStorage.setItem(TF_ENTREPRISE_CLE, JSON.stringify({ le: Date.now(), entreprise: donnees.entreprise }));
  return donnees.entreprise;
}

function tfOublierEntreprise() { sessionStorage.removeItem(TF_ENTREPRISE_CLE); }

function tfEntreeVisible(entree, entreprise) {
  if (entree.module && !entreprise.modules[entree.module]) return false;
  if (entree.portail && !entreprise.portail[entree.portail]) return false;
  return true;
}

/* Construit les liens de la barre et bloque une page fermee par la configuration. */
async function tfMonterNavigation(session) {
  const barre = document.querySelector('.tf-navbar');
  if (!barre || !session) return;
  const menu = TF_MENUS[session.role === 'admin' ? 'admin' : 'chauffeur'];
  const page = document.body.dataset.page;
  let entreprise;
  try { entreprise = await tfEntreprise(); } catch (e) { return; }

  barre.querySelectorAll('.tf-nav-link, [data-nav-entreprise]').forEach(function (l) { l.remove(); });
  const marque = barre.querySelector('.tf-brand');
  if (marque) {
    marque.href = menu[0].href;
    marque.insertAdjacentHTML('afterend', '<span class="tf-nav-entreprise" data-nav-entreprise title="' +
      Format.echapper(entreprise.nom) + '">' + Format.echapper(entreprise.nom) + '</span>');
  }
  const zoneUtilisateur = barre.querySelector('[data-navbar-user]');
  menu.filter(function (e) { return tfEntreeVisible(e, entreprise); }).forEach(function (e) {
    const lien = document.createElement('a');
    lien.className = 'tf-nav-link' + (e.pages.indexOf(page) >= 0 ? ' active' : '');
    lien.href = e.href;
    lien.textContent = e.texte;
    barre.insertBefore(lien, zoneUtilisateur);
  });
  const actif = barre.querySelector('.tf-nav-link.active');
  if (actif) actif.scrollIntoView({ block: 'nearest', inline: 'center' });

  const entreePage = menu.find(function (e) { return e.pages.indexOf(page) >= 0; });
  if (entreePage && !tfEntreeVisible(entreePage, entreprise)) {
    const principal = document.querySelector('main');
    if (principal) {
      principal.innerHTML = '<section class="tf-card p-4"><h1 class="tf-h2">Fonction non disponible</h1>' +
        '<p class="tf-meta mt-2 mb-3">' + (session.role === 'admin'
          ? 'Ce module est desactive. Vous pouvez l activer dans Parametres &gt; Applications.'
          : 'Votre entreprise n a pas ouvert cette fonction dans votre espace.') + '</p>' +
        '<a class="tf-btn tf-btn-primary" href="' + menu[0].href + '">Retour a l accueil</a></section>';
    }
    document.body.dataset.pret = '1';
    throw new Error('page-fermee');
  }
  return entreprise;
}

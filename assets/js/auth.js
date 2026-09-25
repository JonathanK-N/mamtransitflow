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
    Auth.deconnecter(racine);
  });
}

/* TransitFlow — session et garde de page
   Auteur : Mamadou Barry */

const SESSION_KEY = 'transitflow.session';
const MOT_DE_PASSE_DEMO = 'demo';

const COMPTES = [
  { courriel: 'a.tremblay@transitflow.ca', role: 'admin', nom: 'Alex Tremblay', initiales: 'AT' },
  { courriel: 'a.diallo@transitflow.ca', role: 'chauffeur', chauffeurId: 'c1' },
  { courriel: 'm.traore@transitflow.ca', role: 'chauffeur', chauffeurId: 'c2' },
  { courriel: 's.fortin@transitflow.ca', role: 'chauffeur', chauffeurId: 'c3' },
  { courriel: 'm.barry@transitflow.ca', role: 'chauffeur', chauffeurId: 'c4' },
  { courriel: 'Mamadou.Barry@USherbrooke.ca', role: 'admin', chauffeurId: 'c5', nom: 'Mamadou Barry', initiales: 'MB' }
];

const Auth = {
  session() {
    try { return JSON.parse(sessionStorage.getItem(SESSION_KEY)); }
    catch (e) { return null; }
  },

  connecter(courriel, motDePasse, role) {
    const compte = COMPTES.find(function (c) {
      return c.courriel.toLowerCase() === String(courriel).trim().toLowerCase();
    });
    if (!compte) return { ok: false, message: 'Aucun compte ne correspond a ce courriel.' };
    if (motDePasse !== MOT_DE_PASSE_DEMO) return { ok: false, message: 'Mot de passe incorrect.' };
    if (role && compte.role !== role) {
      return { ok: false, message: 'Ce compte n est pas un compte ' + role + '.' };
    }
    const session = Object.assign({}, compte);
    if (compte.role === 'chauffeur') {
      const c = Store.chauffeur(compte.chauffeurId);
      session.nom = Format.nomComplet(c);
      session.initiales = Format.initiales(c);
    }
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
    return { ok: true, session: session };
  },

  deconnecter(racine) {
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

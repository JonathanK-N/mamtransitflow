/* TransitFlow — ecrans chauffeur
   Auteur original : Mamadou Barry
   Modifie par : Jonathan K-N — meme principe que admin.js : chaque
   methode "pageXxx" est passee en async/await parce que les donnees
   viennent maintenant de l API (voir store.js) au lieu du localStorage. */

const Chauffeur = {
  /*
   * Point d entree, appele au chargement de chaque page chauffeur/*.html :
   * verifie la session, charge la fiche du chauffeur connecte (this.moi),
   * puis appelle la methode "pageXxx" correspondant a la page (via
   * l attribut data-page du <body>, comme dans admin.js).
   */
  async demarrer() {
    const session = Auth.exiger('chauffeur', '../');
    if (!session) return;
    monterBarreUtilisateur(session, '../');
    this.session = session;
    this.moi = await Store.chauffeur(session.chauffeurId);
    const page = document.body.dataset.page;
    const methode = 'page' + page.charAt(0).toUpperCase() + page.slice(1).replace(/-(.)/g, function (m, c) {
      return c.toUpperCase();
    });
    if (typeof this[methode] === 'function') await this[methode]();
  },

  /* Mes trajets */
  async pageMesTrajets() {
    const moi = this.moi;
    document.querySelector('[data-salutation]').textContent = 'Bonjour ' + moi.prenom;
    document.querySelector('[data-date]').textContent = Format.dateLongue('2026-09-12');

    const enCours = await Store.trajetEnCours(moi.id);
    const bloc = document.querySelector('[data-trajet-en-cours]');
    const vide = document.querySelector('[data-aucun-trajet]');

    if (enCours) {
      const p = Format.progression(enCours);
      bloc.classList.remove('tf-hidden');
      vide.classList.add('tf-hidden');
      bloc.querySelector('[data-titre]').textContent = enCours.depart + ' → ' + enCours.arrivee;
      bloc.querySelector('[data-meta]').textContent =
        enCours.plaque + ' · depart ' + Format.heure(enCours.debut);
      bloc.querySelector('[data-progression]').style.width = p + '%';
      bloc.querySelector('[data-ecoule]').textContent =
        Format.dureeDepuis(enCours.debut) + ' ecoulees · ' + enCours.arrets.length + ' arret' +
        (enCours.arrets.length > 1 ? 's' : '');
      bloc.querySelector('[data-prevue]').textContent = 'arrivee prevue ' + Format.heure(enCours.finPrevue);
      bloc.querySelector('[data-lien-suivi]').href =
        'trajet-en-cours.html?id=' + encodeURIComponent(enCours.id);
      bloc.querySelector('[data-lien-incident]').href =
        'incident-nouveau.html?trajet=' + encodeURIComponent(enCours.id);
      bloc.querySelector('[data-terminer]').addEventListener('click', async function () {
        await Store.terminerTrajet(enCours.id);
        window.location.reload();
      });
    } else {
      bloc.classList.add('tf-hidden');
      vide.classList.remove('tf-hidden');
    }

    // L API n a pas de route "mes trajets termines" toute faite : on
    // demande tous les trajets de ce chauffeur puis on filtre nous-memes
    // ceux qui sont 'termine'. Meme logique pour associer les incidents
    // a chaque trajet termine (on recupere tous les incidents une fois).
    const tousTrajets = await Store.trajets({ chauffeurId: moi.id });
    const passes = tousTrajets.filter(function (t) { return t.statut === 'termine'; });
    const tousIncidents = await Store.incidents();
    document.querySelector('[data-passes]').innerHTML = passes.map(function (t) {
      const incidents = tousIncidents.filter(function (i) { return i.trajetId === t.id; });
      return '<div class="col-12 col-md-4"><div class="tf-card tf-card-pad h-100 d-flex flex-column gap-2">' +
        '<div class="d-flex align-items-center justify-content-between">' +
        '<span class="tf-pill ok">Termine</span>' +
        '<span class="tf-mono tf-meta">' + Format.dateCourte(t.debut) + '</span></div>' +
        '<div style="font-size:16px;font-weight:500">' + Format.echapper(t.depart + ' → ' + t.arrivee) +
        '</div><div class="tf-meta">' + Format.duree(t.debut, t.fin) + ' · ' + t.arrets.length +
        ' arret' + (t.arrets.length > 1 ? 's' : '') + ' · ' +
        (incidents.length
          ? '<span class="tf-danger">' + incidents.length + ' incident' +
            (incidents.length > 1 ? 's' : '') + '</span>'
          : 'aucun incident') +
        '</div></div></div>';
    }).join('') || '<div class="col-12 tf-muted">Aucun trajet termine pour le moment.</div>';
  },

  /* Creer un trajet */
  async pageTrajetNouveau() {
    const moi = this.moi;
    const tuiles = document.querySelector('[data-vehicules]');
    let plaque = moi.plaqueHabituelle;

    const vehicules = await Store.vehicules();
    tuiles.innerHTML = vehicules.map(function (v) {
      return '<div class="col-6 col-md-4"><button type="button" class="tf-tile' +
        (v.plaque === plaque ? ' active' : '') + '" data-plaque="' + Format.echapper(v.plaque) + '">' +
        '<span class="tf-tile-mark"></span>' +
        '<span class="tf-mono" style="font-size:14px">' + Format.echapper(v.plaque) + '</span>' +
        '<span class="tf-tile-note">' + Format.echapper(v.modele) + '</span></button></div>';
    }).join('');

    tuiles.querySelectorAll('[data-plaque]').forEach(function (b) {
      b.addEventListener('click', function () {
        tuiles.querySelectorAll('[data-plaque]').forEach(function (x) { x.classList.remove('active'); });
        b.classList.add('active');
        plaque = b.dataset.plaque;
      });
    });

    if (await Store.trajetEnCours(moi.id)) {
      document.querySelector('[data-avertissement]').classList.remove('tf-hidden');
    }

    document.querySelector('[data-formulaire]').addEventListener('submit', async function (e) {
      e.preventDefault();
      const d = new FormData(e.target);
      // Le serveur ignore le chauffeurId envoye ici et prend toujours
      // celui de la session connectee (voir backend/routes/trajets_routes.py) ;
      // on le laisse quand meme dans l objet pour rester lisible.
      const trajet = await Store.ajouterTrajet({
        chauffeurId: moi.id,
        plaque: plaque,
        depart: d.get('depart').trim(),
        departAdresse: d.get('departAdresse').trim(),
        arrivee: d.get('arrivee').trim(),
        debut: '2026-09-12T' + d.get('heure'),
        finPrevue: '2026-09-12T' + d.get('heurePrevue')
      });
      await Store.majChauffeur(moi.id, { statut: 'en-trajet' });
      window.location.href = 'trajet-en-cours.html?id=' + encodeURIComponent(trajet.id);
    });
  },

  /* Trajet en cours : ajouter un arret, terminer */
  async pageTrajetEnCours() {
    const moi = this.moi;
    const id = new URLSearchParams(location.search).get('id');
    const t = id ? await Store.trajet(id) : await Store.trajetEnCours(moi.id);
    if (!t) {
      document.querySelector('[data-contenu]').innerHTML =
        '<p class="tf-muted">Aucun trajet en cours.</p>';
      return;
    }

    // Redessine le fil du trajet (appelee au chargement et apres l ajout
    // d un arret). On relit le trajet depuis l API a chaque fois plutot
    // que de reutiliser "t" tel quel, pour avoir les arrets a jour.
    async function dessiner() {
      const [courant, tousIncidents] = await Promise.all([Store.trajet(t.id), Store.incidents()]);
      const incidents = tousIncidents.filter(function (i) { return i.trajetId === courant.id; });
      document.querySelector('[data-titre]').textContent = courant.depart + ' → ' + courant.arrivee;
      document.querySelector('[data-meta]').textContent =
        courant.plaque + ' · ' + Format.dureeDepuis(courant.debut);

      const etapes = [{ heure: Format.heure(courant.debut), titre: 'Depart — ' + courant.depart,
        note: courant.departAdresse || courant.depart, classe: 'done' }];
      courant.arrets.forEach(function (a) {
        etapes.push({ heure: a.heure, titre: 'Arret — ' + a.lieu,
          note: a.note || 'Arret enregistre', classe: '' });
      });
      incidents.forEach(function (i) {
        etapes.push({ heure: i.heure, titre: 'Incident — ' + i.titre, note: i.lieu, classe: 'alert' });
      });
      etapes.sort(function (a, b) { return a.heure.localeCompare(b.heure); });
      etapes.push({ heure: Format.heure(courant.finPrevue), titre: 'Arrivee — ' + courant.arrivee,
        note: 'Heure prevue', classe: 'planned', futur: true });

      document.querySelector('[data-deroulement]').innerHTML = etapes.map(function (e, index) {
        return '<div class="tf-tl-time">' + e.heure + '</div>' +
          '<div class="tf-tl-body ' + e.classe + (index === etapes.length - 1 ? ' last' : '') + '">' +
          '<div class="tf-tl-title"' + (e.futur ? ' style="color:var(--tf-muted)"' : '') + '>' +
          Format.echapper(e.titre) + '</div>' +
          '<div class="tf-tl-note">' + Format.echapper(e.note) + '</div></div>';
      }).join('');

      document.querySelector('[data-lien-incident]').href =
        'incident-nouveau.html?trajet=' + encodeURIComponent(courant.id);
    }

    document.querySelector('[data-arret]').addEventListener('submit', async function (e) {
      e.preventDefault();
      const d = new FormData(e.target);
      await Store.ajouterArret(t.id, {
        lieu: d.get('lieu').trim(),
        heure: d.get('heure'),
        note: d.get('note').trim()
      });
      e.target.reset();
      await dessiner();
    });

    document.querySelector('[data-terminer]').addEventListener('click', async function () {
      await Store.terminerTrajet(t.id);
      window.location.href = 'mes-trajets.html';
    });

    await dessiner();
  },

  /* Signaler un incident */
  async pageIncidentNouveau() {
    const moi = this.moi;
    const params = new URLSearchParams(location.search);
    const trajetId = params.get('trajet');
    const trajet = trajetId ? await Store.trajet(trajetId) : await Store.trajetEnCours(moi.id);
    let type = 'technique';

    document.querySelector('[data-rattachement]').textContent = trajet
      ? 'Rattache au trajet ' + trajet.id + ' · ' + trajet.plaque
      : 'Aucun trajet en cours — l incident sera enregistre sans trajet.';

    document.querySelectorAll('[data-type]').forEach(function (tuile) {
      tuile.addEventListener('click', function () {
        document.querySelectorAll('[data-type]').forEach(function (x) { x.classList.remove('active'); });
        tuile.classList.add('active');
        type = tuile.dataset.type;
      });
    });

    document.querySelector('[data-formulaire]').addEventListener('submit', async function (e) {
      e.preventDefault();
      const d = new FormData(e.target);
      await Store.ajouterIncident({
        trajetId: trajet ? trajet.id : null,
        chauffeurId: moi.id,
        type: type,
        titre: d.get('titre').trim(),
        description: d.get('description').trim(),
        lieu: d.get('lieu').trim(),
        date: '2026-09-12',
        heure: d.get('heure')
      });
      window.location.href = trajet
        ? 'trajet-en-cours.html?id=' + encodeURIComponent(trajet.id)
        : 'mes-trajets.html';
    });
  }
};

// Chauffeur.demarrer() est asynchrone : on capture une eventuelle
// erreur (ex. serveur injoignable) pour la voir dans la console plutot
// que de la laisser disparaitre silencieusement.
document.addEventListener('DOMContentLoaded', function () {
  Chauffeur.demarrer().catch(function (e) { console.error('TransitFlow chauffeur :', e); });
});

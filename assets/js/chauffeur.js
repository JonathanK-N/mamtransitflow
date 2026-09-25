/* TransitFlow — ecrans chauffeur
   Auteur original : Mamadou Barry
   Modifie par : Jonathan K-N — meme principe que admin.js : chaque
   methode "pageXxx" est en async/await parce que les donnees viennent de
   l API (voir store.js). Les dates sont celles du jour reel et les
   erreurs du serveur sont affichees a l utilisateur (tfNotifier). A
   l arrivee, le chauffeur peut saisir le compteur du vehicule. */

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
    // Fonction fermee dans le portail : la navigation a remplace la page par un message.
    try { this.entreprise = await window.tfNavigationPrete; } catch (e) { return; }
    // Boutons vers des fonctions que l administrateur n a pas ouvertes dans le portail.
    const portail = (this.entreprise || {}).portail || {};
    [['trajet-nouveau.html', 'trajets'], ['incident-nouveau.html', 'incidents']].forEach(function (x) {
      if (portail[x[1]] === false) {
        document.querySelectorAll('a[href^="' + x[0] + '"]').forEach(function (a) { a.classList.add('tf-hidden'); });
      }
    });
    this.moi = await Store.chauffeur(session.chauffeurId);
    if (!this.moi) {
      document.querySelector('main').innerHTML =
        '<p class="tf-muted">Ce compte n est rattache a aucune fiche chauffeur. ' +
        'Contactez votre administrateur.</p>';
      return;
    }
    const page = document.body.dataset.page;
    const methode = 'page' + page.charAt(0).toUpperCase() + page.slice(1).replace(/-(.)/g, function (m, c) {
      return c.toUpperCase();
    });
    if (typeof this[methode] === 'function') await this[methode]();
    document.body.dataset.pret = '1';
  },

  /*
   * Fenetre "Marquer l arrivee" : le compteur du vehicule est demande (facultatif)
   * pour alimenter le suivi d entretien de la flotte. Renvoie true si le trajet est termine.
   */
  async marquerArrivee(trajet) {
    const vehicules = await Store.vehicules();
    const vehicule = vehicules.find(function (v) { return v.plaque === trajet.plaque; });
    const actuel = vehicule ? vehicule.kilometrage : 0;
    // Les derniers points GPS partent avant la cloture (le serveur les refuse ensuite).
    const suivi = Chauffeur.suivi || (typeof SuiviGPS === 'function' ? new SuiviGPS(trajet.id) : null);
    return tfModale({
      titre: 'Marquer l arrivee',
      sousTitre: trajet.depart + ' → ' + trajet.arrivee + ' · ' + trajet.plaque,
      corps: tfChamp('Compteur du vehicule (km)',
        '<input class="tf-input tf-mono" name="kilometrage" type="number" inputmode="numeric" min="' + actuel +
        '" step="1" placeholder="' + actuel + '">',
        'Facultatif — dernier releve : ' + Format.km(actuel) + '. Sert au suivi de l entretien.'),
      valider: 'Terminer le trajet',
      danger: true,
      async action(d) {
        if (suivi) await suivi.arreter();
        await Store.terminerTrajet(trajet.id, tfNombre(d, 'kilometrage'));
      }
    });
  },

  /* Partage de la position pendant le trajet (voir gps.js) et affichage de son etat. */
  partagerPosition(trajet) {
    const pastille = document.querySelector('[data-gps-statut]');
    const detail = document.querySelector('[data-gps-detail]');
    const relancer = document.querySelector('[data-gps-relancer]');
    const libelles = {
      actif: ['Actif', 'ok'], attente: ['Recherche', 'warn'], refuse: ['Refuse', 'danger'],
      indisponible: ['Indisponible', 'danger'], arrete: ['Arrete', '']
    };
    function afficher(etat) {
      const l = libelles[etat.statut] || [etat.statut, ''];
      pastille.className = 'tf-pill ms-auto ' + l[1];
      pastille.textContent = l[0];
      const morceaux = [];
      if (etat.message) morceaux.push(etat.message);
      if (etat.statut === 'actif' && etat.precision) morceaux.push('Precision ' + Math.round(etat.precision) + ' m');
      if (etat.dernierEnvoi) morceaux.push('envoye ' + Format.depuis((Date.now() - etat.dernierEnvoi) / 1000));
      if (etat.enAttente > 0) morceaux.push(etat.enAttente + ' point(s) en attente');
      detail.textContent = morceaux.join(' · ') || 'Demarrage...';
      relancer.classList.toggle('tf-hidden', etat.statut !== 'refuse');
    }
    this.suivi = new SuiviGPS(trajet.id, { rappel: afficher });
    const suivi = this.suivi;
    relancer.addEventListener('click', function () { suivi.arreter().then(function () { suivi.demarrer(); }); });
    // Rafraichit "envoye il y a ..." meme sans nouvelle position.
    setInterval(function () { afficher(suivi.etat); }, 5000);
    suivi.demarrer();
  },

  /* Mes trajets */
  async pageMesTrajets() {
    const moi = this.moi;
    document.querySelector('[data-salutation]').textContent = 'Bonjour ' + moi.prenom;
    document.querySelector('[data-date]').textContent = Format.dateLongue(Format.aujourdhui());

    // Le serveur ne renvoie que les trajets et incidents du chauffeur connecte.
    const [enCours, tousTrajets, tousIncidents] = await Promise.all([
      Store.trajetEnCours(moi.id), Store.trajets({ chauffeurId: moi.id }), Store.incidents()
    ]);
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
        try {
          if (await Chauffeur.marquerArrivee(enCours)) window.location.reload();
        } catch (e) { tfNotifier(e.message); }
      });
    } else {
      bloc.classList.add('tf-hidden');
      vide.classList.remove('tf-hidden');
    }

    const passes = tousTrajets.filter(function (t) { return t.statut === 'termine'; });
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
    const formulaire = document.querySelector('[data-formulaire]');
    formulaire.querySelector('[name=heure]').value = Format.heureActuelle();
    formulaire.querySelector('[name=heurePrevue]').value = Format.heureActuelle(60);

    const [vehicules, enCours] = await Promise.all([Store.vehicules(), Store.trajetEnCours(moi.id)]);
    // Seuls les vehicules 'actif' peuvent partir : ceux en maintenance ou
    // hors service sont affiches mais grises (le serveur les refuse aussi).
    const disponibles = vehicules.filter(function (v) { return v.disponible; });
    let plaque = disponibles.some(function (v) { return v.plaque === moi.plaqueHabituelle; })
      ? moi.plaqueHabituelle
      : (disponibles[0] ? disponibles[0].plaque : null);

    tuiles.innerHTML = vehicules.map(function (v) {
      return '<div class="col-6 col-md-4"><button type="button" class="tf-tile' +
        (v.plaque === plaque ? ' active' : '') + '" data-plaque="' + Format.echapper(v.plaque) + '"' +
        (v.disponible ? '' : ' disabled style="opacity:.55;cursor:not-allowed"') + '>' +
        '<span class="tf-tile-mark"></span>' +
        '<span class="tf-mono" style="font-size:14px">' + Format.echapper(v.plaque) + '</span>' +
        '<span class="tf-tile-note">' + Format.echapper(v.modele) +
        (v.disponible ? '' : ' · ' + Format.statutVehicule(v.statut).texte.toLowerCase()) + '</span></button></div>';
    }).join('') || '<div class="col-12 tf-muted">Aucun vehicule dans la flotte : ' +
      'demandez a votre administrateur d en ajouter un.</div>';

    tuiles.querySelectorAll('[data-plaque]:not([disabled])').forEach(function (b) {
      b.addEventListener('click', function () {
        tuiles.querySelectorAll('[data-plaque]').forEach(function (x) { x.classList.remove('active'); });
        b.classList.add('active');
        plaque = b.dataset.plaque;
      });
    });

    if (enCours) {
      document.querySelector('[data-avertissement]').classList.remove('tf-hidden');
    }

    formulaire.addEventListener('submit', function (e) {
      e.preventDefault();
      tfEnvoyer(formulaire, async function () {
        if (!plaque) throw new Error('Choisissez un vehicule.');
        const d = new FormData(formulaire);
        const debut = Format.instant(Format.aujourdhui(), d.get('heure'));
        // Une arrivee prevue "avant" le depart signifie un trajet qui passe minuit.
        let finPrevue = Format.instant(Format.aujourdhui(), d.get('heurePrevue'));
        if (finPrevue <= debut) finPrevue = Format.instant(Format.aujourdhui(1), d.get('heurePrevue'));
        const trajet = await Store.ajouterTrajet({
          plaque: plaque,
          depart: d.get('depart').trim(),
          departAdresse: d.get('departAdresse').trim(),
          arrivee: d.get('arrivee').trim(),
          debut: debut,
          finPrevue: finPrevue
        });
        window.location.href = 'trajet-en-cours.html?id=' + encodeURIComponent(trajet.id);
      });
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
    const formulaireArret = document.querySelector('[data-arret]');
    formulaireArret.querySelector('[name=heure]').value = Format.heureActuelle();
    if (t.statut === 'en-cours') this.partagerPosition(t);
    else document.querySelector('[data-gps]').classList.add('tf-hidden');

    // Redessine le fil du trajet (appelee au chargement et apres l ajout
    // d un arret). On relit le trajet depuis l API a chaque fois pour
    // avoir les arrets a jour.
    async function dessiner() {
      const [courant, tousIncidents] = await Promise.all([Store.trajet(t.id), Store.incidents()]);
      const incidents = tousIncidents.filter(function (i) { return i.trajetId === courant.id; });
      document.querySelector('[data-titre]').textContent = courant.depart + ' → ' + courant.arrivee;
      document.querySelector('[data-meta]').textContent =
        courant.plaque + ' · ' + (courant.statut === 'termine'
          ? 'termine en ' + Format.duree(courant.debut, courant.fin)
          : Format.dureeDepuis(courant.debut));

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
        return '<div class="tf-tl-time">' + Format.echapper(e.heure) + '</div>' +
          '<div class="tf-tl-body ' + e.classe + (index === etapes.length - 1 ? ' last' : '') + '">' +
          '<div class="tf-tl-title"' + (e.futur ? ' style="color:var(--tf-muted)"' : '') + '>' +
          Format.echapper(e.titre) + '</div>' +
          '<div class="tf-tl-note">' + Format.echapper(e.note) + '</div></div>';
      }).join('');

      document.querySelector('[data-lien-incident]').href =
        'incident-nouveau.html?trajet=' + encodeURIComponent(courant.id);
    }

    formulaireArret.addEventListener('submit', function (e) {
      e.preventDefault();
      tfEnvoyer(formulaireArret, async function () {
        const d = new FormData(formulaireArret);
        await Store.ajouterArret(t.id, {
          lieu: d.get('lieu').trim(),
          heure: d.get('heure'),
          note: d.get('note').trim()
        });
        formulaireArret.reset();
        formulaireArret.querySelector('[name=heure]').value = Format.heureActuelle();
        await dessiner();
      });
    });

    document.querySelector('[data-terminer]').addEventListener('click', async function () {
      try {
        if (await Chauffeur.marquerArrivee(t)) window.location.href = 'mes-trajets.html';
      } catch (e) { tfNotifier(e.message); }
    });

    await dessiner();
  },

  /* Signaler un incident */
  async pageIncidentNouveau() {
    const moi = this.moi;
    const params = new URLSearchParams(location.search);
    const trajetId = params.get('trajet');
    const trajet = trajetId ? await Store.trajet(trajetId) : await Store.trajetEnCours(moi.id);
    const formulaire = document.querySelector('[data-formulaire]');
    formulaire.querySelector('[name=heure]').value = Format.heureActuelle();
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

    formulaire.addEventListener('submit', function (e) {
      e.preventDefault();
      tfEnvoyer(formulaire, async function () {
        const d = new FormData(formulaire);
        await Store.ajouterIncident({
          trajetId: trajet ? trajet.id : null,
          type: type,
          titre: d.get('titre').trim(),
          description: d.get('description').trim(),
          lieu: d.get('lieu').trim(),
          date: Format.aujourdhui(),
          heure: d.get('heure')
        });
        window.location.href = trajet
          ? 'trajet-en-cours.html?id=' + encodeURIComponent(trajet.id)
          : 'mes-trajets.html';
      });
    });
  }
};

// Chauffeur.demarrer() est asynchrone : une erreur (ex. serveur injoignable)
// est affichee a l utilisateur plutot que de disparaitre dans la console.
document.addEventListener('DOMContentLoaded', function () {
  Chauffeur.demarrer().catch(function (e) {
    if (e && e.message === 'page-fermee') return;
    console.error('TransitFlow chauffeur :', e);
    tfNotifier(e.message);
  });
});

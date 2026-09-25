/* TransitFlow — ecrans administrateur de l ERP : parametres et paie
   Auteur : Jonathan K-N
   Complete l objet Admin (admin.js) avec les pages :
     - parametres.html : fiche entreprise, applications (modules), portail
                         chauffeur, parametres de paie et retenues, courriel ;
     - paie.html       : paies (periodes), bulletins, remuneration des chauffeurs.
   Charge APRES admin.js et admin-flotte.js (tfOnglets, tfPastille). */

const TF_APPLICATIONS = [
  { cle: null, icone: '👥', nom: 'Chauffeurs', texte: 'Fiches, permis, invitations et acces au portail.' },
  { cle: null, icone: '🧭', nom: 'Trajets et incidents', texte: 'Depart, arrets, arrivee et incidents de route.' },
  { cle: null, icone: '🚐', nom: 'Vehicules', texte: 'Flotte, compteurs et disponibilite.' },
  { cle: 'entretien', icone: '🔧', nom: 'Entretien', texte: 'Plans preventifs, bons de travail, echeances et couts.' },
  { cle: 'suivi', icone: '📍', nom: 'Suivi GPS', texte: 'Carte en direct et parcours des trajets.' },
  { cle: 'paie', icone: '💵', nom: 'Paie', texte: 'Heures tirees des trajets, cotisations du Quebec, bulletins.' }
];

const TF_PORTAIL = [
  { cle: 'trajets', nom: 'Demarrer et terminer ses trajets', texte: 'Sinon, le chauffeur consulte seulement ses trajets.' },
  { cle: 'incidents', nom: 'Signaler un incident', texte: 'Incident de route ou probleme technique pendant un trajet.' },
  { cle: 'vehicule', nom: 'Voir son vehicule', texte: 'Compteur, prochains entretiens et interventions en cours.',
    module: 'entretien' },
  { cle: 'paie', nom: 'Consulter ses bulletins de paie', texte: 'Bulletins des paies validees, imprimables en PDF.',
    module: 'paie' },
  { cle: 'profil', nom: 'Modifier son telephone et son adresse', texte: 'Le changement de mot de passe reste toujours possible.' }
];

function tfInterrupteur(attributs, coche, desactive) {
  return '<label class="tf-switch"><input type="checkbox" ' + attributs + (coche ? ' checked' : '') +
    (desactive ? ' disabled' : '') + '><span></span></label>';
}

function tfAnnee() { return new Date().getFullYear(); }

Object.assign(Admin, {
  /* ================================================================ Parametres */
  async pageParametres() {
    let entreprise = await tfEntreprise(true);
    const moi = this;
    const montrer = tfOnglets(document.querySelector('.tf-tabs').parentElement, function (nom) {
      if (nom === 'paie') moi.chargerParametresPaie().catch(function (e) { tfNotifier(e.message); });
      history.replaceState(null, '', '#' + nom);
    });
    const onglet = location.hash.slice(1);
    if (onglet && document.querySelector('[data-onglet="' + onglet + '"]')) montrer(onglet);

    // ---- Entreprise
    const formulaire = document.querySelector('[data-form-entreprise]');
    ['nom', 'neq', 'courriel', 'telephone', 'adresse', 'ville', 'province', 'codePostal'].forEach(function (cle) {
      formulaire.elements[cle].value = entreprise[cle] || '';
    });
    formulaire.addEventListener('submit', function (e) {
      e.preventDefault();
      if (!formulaire.reportValidity()) return;
      tfEnvoyer(formulaire, async function () {
        const d = new FormData(formulaire);
        const champs = {};
        ['nom', 'neq', 'courriel', 'telephone', 'adresse', 'ville', 'province', 'codePostal'].forEach(function (cle) {
          champs[cle] = String(d.get(cle) || '').trim();
        });
        entreprise = await Store.majEntreprise(champs);
        tfOublierEntreprise();
        document.querySelectorAll('[data-nav-entreprise]').forEach(function (n) { n.textContent = entreprise.nom; });
        tfNotifier('Informations de l entreprise enregistrees.', 'succes');
      });
    });

    // ---- Applications et portail : chaque interrupteur enregistre immediatement.
    function dessiner() {
      document.querySelector('[data-applications]').innerHTML = TF_APPLICATIONS.map(function (a) {
        const actif = a.cle ? entreprise.modules[a.cle] : true;
        return '<div class="tf-app' + (actif ? '' : ' inactive') + '">' +
          '<div class="d-flex align-items-center gap-3"><span class="tf-app-icone">' + a.icone + '</span>' +
          '<strong class="flex-fill">' + a.nom + '</strong>' +
          (a.cle ? tfInterrupteur('data-module="' + a.cle + '" aria-label="Activer ' + a.nom + '"', actif)
                 : '<span class="tf-pill ok">Inclus</span>') + '</div>' +
          '<p class="tf-meta mb-0">' + a.texte + '</p></div>';
      }).join('');
      document.querySelector('[data-portail]').innerHTML = TF_PORTAIL.map(function (p) {
        const moduleCoupe = p.module && !entreprise.modules[p.module];
        return '<div class="tf-reglage"><div class="flex-fill"><strong style="font-size:14.5px">' + p.nom + '</strong>' +
          '<div class="tf-meta">' + (moduleCoupe ? 'Activez d abord l application ' +
            TF_APPLICATIONS.find(function (a) { return a.cle === p.module; }).nom + '.' : p.texte) + '</div></div>' +
          tfInterrupteur('data-droit="' + p.cle + '" aria-label="' + p.nom + '"', entreprise.portailReglages[p.cle],
            moduleCoupe) + '</div>';
      }).join('');
      document.querySelector('[data-onglet-paie]').classList.toggle('tf-hidden', !entreprise.modules.paie);
    }
    dessiner();

    async function enregistrer(champs, interrupteur) {
      interrupteur.disabled = true;
      try {
        entreprise = await Store.majEntreprise(champs);
        tfOublierEntreprise();
        // Les menus changent avec les applications actives.
        await tfMonterNavigation(Auth.session()).catch(function () {});
        tfNotifier('Enregistre.', 'succes');
      } catch (e) {
        tfNotifier(e.message);
      }
      dessiner();
    }
    document.querySelector('[data-applications]').addEventListener('change', function (e) {
      const cle = e.target.dataset.module;
      if (cle) enregistrer({ modules: { [cle]: e.target.checked } }, e.target);
    });
    document.querySelector('[data-portail]').addEventListener('change', function (e) {
      const cle = e.target.dataset.droit;
      if (cle) enregistrer({ portail: { [cle]: e.target.checked } }, e.target);
    });

    // ---- Courriel
    const configure = entreprise.courrielConfigure;
    document.querySelector('[data-etat-courriel]').innerHTML = configure
      ? '<span class="tf-pill ok">Configure</span>' : '<span class="tf-pill warn">Non configure</span>';
    document.querySelector('[data-texte-courriel]').textContent = configure
      ? 'Les invitations et les liens « Mot de passe oublie » partent automatiquement par courriel.'
      : 'Aucun courriel ne part pour l instant. Les invitations restent possibles : a la creation d un chauffeur, ' +
        'TransitFlow affiche le lien d invitation a copier et a lui transmettre (texto, courriel personnel). ' +
        '« Mot de passe oublie » ne fonctionnera qu une fois l envoi configure.';

    // ---- Paie : formulaire des parametres
    const formPaie = document.querySelector('[data-form-paie]');
    formPaie.addEventListener('submit', function (e) {
      e.preventDefault();
      if (!formPaie.reportValidity()) return;
      tfEnvoyer(formPaie, async function () {
        const d = new FormData(formPaie);
        await Store.majParametresPaie({
          frequence: d.get('frequence'), seuilHeuresSup: tfNombre(d, 'seuilHeuresSup'),
          majorationHeuresSup: tfNombre(d, 'majorationHeuresSup'), tauxVacances: tfNombre(d, 'tauxVacances') || 0
        });
        tfNotifier('Parametres de paie enregistres.', 'succes');
      });
    });
    document.querySelector('[data-nouvelle-retenue]').addEventListener('click', function () {
      moi.modaleRetenue(null);
    });
  },

  async chargerParametresPaie() {
    const donnees = await Store.parametresPaie();
    const p = donnees.parametres;
    const formPaie = document.querySelector('[data-form-paie]');
    formPaie.elements.frequence.value = p.frequence;
    formPaie.elements.seuilHeuresSup.value = p.seuilHeuresSup;
    formPaie.elements.majorationHeuresSup.value = p.majorationHeuresSup;
    formPaie.elements.tauxVacances.value = p.tauxVacances;
    const moi = this;
    const pourcent = function (v) { return v ? TfPaieTexte.pourcent(v) : '—'; };
    const corps = document.querySelector('[data-retenues]');
    corps.innerHTML = donnees.retenues.map(function (r) {
      const tranche = r.plafondAnnuel === null
        ? (r.plancherAnnuel ? 'au-dela de ' + Format.montant(r.plancherAnnuel) : 'tous les gains')
        : (r.plancherAnnuel ? Format.montant(r.plancherAnnuel) + ' a ' : 'jusqu a ') + Format.montant(r.plafondAnnuel);
      const aConfigurer = !r.tauxSalarie && !r.tauxEmployeur;
      return '<tr data-ligne data-retenue="' + r.id + '"><td class="tf-mono">' + Format.echapper(r.code) + '</td>' +
        '<td><span style="font-weight:500">' + Format.echapper(r.libelle) + '</span>' +
          (r.note ? '<div class="tf-meta" style="font-size:12px">' + Format.echapper(r.note) + '</div>' : '') + '</td>' +
        '<td class="text-end tf-mono">' + pourcent(r.tauxSalarie) + '</td>' +
        '<td class="text-end tf-mono">' + pourcent(r.tauxEmployeur) + '</td>' +
        '<td class="text-end tf-mono" style="white-space:nowrap">' + tranche + '</td>' +
        '<td class="text-end tf-mono">' + (r.exemptionAnnuelle ? Format.montant(r.exemptionAnnuelle) : '—') + '</td>' +
        '<td>' + (r.actif ? '<span class="tf-pill ok">Active</span>'
          : '<span class="tf-pill ' + (aConfigurer ? 'warn">A configurer' : 'muted">Inactive') + '</span>') + '</td>' +
        '<td class="text-end"><span style="font-size:13px;color:var(--tf-accent-deep)">Modifier</span></td></tr>';
    }).join('') || '<tr><td colspan="8" class="tf-muted">Aucune retenue.</td></tr>';
    corps.querySelectorAll('[data-retenue]').forEach(function (tr) {
      tr.addEventListener('click', function () {
        moi.modaleRetenue(donnees.retenues.find(function (r) { return String(r.id) === tr.dataset.retenue; }));
      });
    });
  },

  async modaleRetenue(r) {
    const v = function (x) { return x === null || x === undefined ? '' : x; };
    const moi = this;
    const ok = await tfModale({
      titre: r ? 'Modifier la retenue ' + r.code : 'Nouvelle retenue',
      sousTitre: 'Calculee sur les gains imposables de chaque paie, avec cumul sur l annee civile.',
      corps:
        '<div class="row g-3">' +
          '<div class="col-4">' + tfChamp('Code', '<input class="tf-input" name="code" required maxlength="20" ' +
            'pattern="[A-Z0-9_\\-]+" value="' + Format.echapper(r ? r.code : '') + '" style="text-transform:uppercase">') + '</div>' +
          '<div class="col-8">' + tfChamp('Libelle', '<input class="tf-input" name="libelle" required maxlength="120" value="' +
            Format.echapper(r ? r.libelle : '') + '">') + '</div>' +
          '<div class="col-6">' + tfChamp('Taux salarie (%)', '<input class="tf-input" name="tauxSalarie" type="number" ' +
            'min="0" max="100" step="0.001" value="' + v(r && r.tauxSalarie) + '">') + '</div>' +
          '<div class="col-6">' + tfChamp('Taux employeur (%)', '<input class="tf-input" name="tauxEmployeur" type="number" ' +
            'min="0" max="100" step="0.001" value="' + v(r && r.tauxEmployeur) + '">') + '</div>' +
          '<div class="col-6">' + tfChamp('Gains annuels : a partir de ($)', '<input class="tf-input" name="plancherAnnuel" ' +
            'type="number" min="0" step="0.01" value="' + v(r ? r.plancherAnnuel : 0) + '">') + '</div>' +
          '<div class="col-6">' + tfChamp('Jusqu a ($, vide = sans plafond)', '<input class="tf-input" name="plafondAnnuel" ' +
            'type="number" min="0" step="0.01" value="' + v(r && r.plafondAnnuel) + '">') + '</div>' +
          '<div class="col-6">' + tfChamp('Exemption annuelle ($)', '<input class="tf-input" name="exemptionAnnuelle" ' +
            'type="number" min="0" step="0.01" value="' + v(r ? r.exemptionAnnuelle : 0) + '">',
            'Repartie sur les paies de l annee (RRQ : 3 500 $).') + '</div>' +
          '<div class="col-6 d-flex align-items-center"><label class="tf-check"><input type="checkbox" name="actif"' +
            (!r || r.actif ? ' checked' : '') + '><span>Appliquer cette retenue</span></label></div>' +
          '<div class="col-12">' + tfChamp('Note', '<input class="tf-input" name="note" maxlength="255" value="' +
            Format.echapper(r ? r.note : '') + '">') + '</div>' +
        '</div>' +
        (r ? '<button type="button" class="tf-btn tf-btn-danger align-self-start" style="height:36px;font-size:13px" ' +
          'data-supprimer-retenue>Supprimer cette retenue</button>' : ''),
      valider: r ? 'Enregistrer' : 'Ajouter',
      preparer: function (formulaire) {
        const bouton = formulaire.querySelector('[data-supprimer-retenue]');
        if (bouton) bouton.addEventListener('click', async function () {
          if (!window.confirm('Supprimer la retenue ' + r.code + ' ? Les paies deja validees ne changent pas.')) return;
          try {
            await Store.supprimerRetenue(r.id);
            formulaire.closest('.tf-modal-backdrop').remove();
            moi.chargerParametresPaie();
            tfNotifier('Retenue supprimee.', 'succes');
          } catch (e) { tfNotifier(e.message); }
        });
      },
      async action(d) {
        const champs = {
          code: tfTexte(d, 'code').toUpperCase(), libelle: tfTexte(d, 'libelle'),
          tauxSalarie: tfNombre(d, 'tauxSalarie') || 0, tauxEmployeur: tfNombre(d, 'tauxEmployeur') || 0,
          plancherAnnuel: tfNombre(d, 'plancherAnnuel') || 0, plafondAnnuel: tfNombre(d, 'plafondAnnuel'),
          exemptionAnnuelle: tfNombre(d, 'exemptionAnnuelle') || 0, note: tfTexte(d, 'note'), actif: d.get('actif') === 'on'
        };
        if (r) await Store.majRetenue(r.id, champs); else await Store.ajouterRetenue(champs);
      }
    });
    if (ok) {
      this.chargerParametresPaie();
      tfNotifier('Retenue enregistree. Elle s applique aux prochains calculs de paie.', 'succes');
    }
  },

  /* ====================================================================== Paie */
  async pagePaie() {
    const moi = this;
    this.paie = { selection: new URLSearchParams(location.search).get('periode') };
    tfOnglets(document.querySelector('.tf-tabs').parentElement, function (nom) {
      if (nom === 'remuneration') moi.dessinerProfils().catch(function (e) { tfNotifier(e.message); });
    });
    document.querySelector('[data-nouvelle-paie]').addEventListener('click', function () { moi.modaleNouvellePaie(); });
    await this.dessinerPeriodes();
    if (this.paie.selection) await this.ouvrirPeriode(this.paie.selection);
  },

  async dessinerPeriodes() {
    const [periodes, parametres] = await Promise.all([Store.periodesPaie(), Store.parametresPaie()]);
    this.paie.periodes = periodes;
    this.paie.parametres = parametres.parametres;
    const annee = String(tfAnnee());
    const cetteAnnee = periodes.filter(function (p) { return p.datePaiement.slice(0, 4) === annee && p.statut !== 'brouillon'; });
    const somme = function (cle) { return cetteAnnee.reduce(function (t, p) { return t + p.totaux[cle]; }, 0); };
    document.querySelector('[data-kpi="net"]').textContent = Format.montant(somme('net'));
    document.querySelector('[data-kpi-note="net"]').textContent = cetteAnnee.length + ' paie(s) validee(s) en ' + annee;
    document.querySelector('[data-kpi="cout"]').textContent = Format.montant(somme('coutEmployeur'));
    document.querySelector('[data-kpi="brouillons"]').textContent =
      periodes.filter(function (p) { return p.statut === 'brouillon'; }).length;
    const frequences = { hebdomadaire: 'chaque semaine', 'deux-semaines': 'aux deux semaines',
      bimensuelle: 'deux fois par mois', mensuelle: 'chaque mois' };
    document.querySelector('[data-sous-titre]').textContent = 'Paie ' + frequences[this.paie.parametres.frequence] +
      ' · heures tirees des trajets termines · cotisations du Quebec ' + annee;

    const profils = await Store.profilsPaie();
    this.paie.profils = profils;
    const actifs = profils.filter(function (p) { return p.profil && p.profil.actif; }).length;
    document.querySelector('[data-kpi="remuneres"]').textContent = actifs + ' / ' + profils.length;
    document.querySelector('[data-kpi-note="remuneres"]').textContent = actifs < profils.length
      ? (profils.length - actifs) + ' sans remuneration definie' : 'tous remuneres';

    const moi = this;
    const corps = document.querySelector('[data-periodes]');
    corps.innerHTML = periodes.map(function (p) {
      return '<tr data-ligne data-periode="' + p.id + '"' + (p.id === moi.paie.selection ? ' class="is-active"' : '') + '>' +
        '<td class="tf-mono">' + p.id + '</td><td>' + TfPaie.periode(p) + '</td>' +
        '<td>' + Format.dateCourte(p.datePaiement) + '</td><td>' + tfPastille(TfPaie.statut(p.statut)) + '</td>' +
        '<td class="text-end tf-mono">' + p.totaux.bulletins + '</td>' +
        '<td class="text-end tf-mono">' + Format.montant(p.totaux.brut) + '</td>' +
        '<td class="text-end tf-mono" style="font-weight:500">' + Format.montant(p.totaux.net) + '</td>' +
        '<td class="text-end tf-mono">' + Format.montant(p.totaux.coutEmployeur) + '</td></tr>';
    }).join('') || '<tr><td colspan="8" class="tf-muted">Aucune paie. ' + (actifs ? 'Creez la premiere avec « + Nouvelle paie ».'
      : 'Definissez d abord la remuneration des chauffeurs (onglet Remuneration).') + '</td></tr>';
    corps.querySelectorAll('[data-periode]').forEach(function (tr) {
      tr.addEventListener('click', function () { moi.ouvrirPeriode(tr.dataset.periode); });
    });
  },

  /* Dates proposees pour la prochaine paie, selon la frequence et la derniere paie. */
  datesProposees() {
    const iso = function (d) { return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10); };
    const plus = function (d, n) { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
    const frequence = this.paie.parametres.frequence;
    const derniere = this.paie.periodes[0];
    let debut;
    if (derniere) {
      debut = plus(new Date(derniere.fin + 'T12:00:00'), 1);
    } else {
      const aujourdhui = new Date();
      debut = frequence === 'mensuelle' || frequence === 'bimensuelle'
        ? new Date(aujourdhui.getFullYear(), aujourdhui.getMonth(), aujourdhui.getDate() > 15 && frequence === 'bimensuelle' ? 16 : 1, 12)
        : plus(aujourdhui, -((aujourdhui.getDay() + 6) % 7) - (frequence === 'deux-semaines' ? 7 : 0));
    }
    let fin;
    if (frequence === 'hebdomadaire') fin = plus(debut, 6);
    else if (frequence === 'deux-semaines') fin = plus(debut, 13);
    else if (frequence === 'mensuelle') fin = new Date(debut.getFullYear(), debut.getMonth() + 1, 0, 12);
    else fin = debut.getDate() <= 15 ? new Date(debut.getFullYear(), debut.getMonth(), 15, 12)
      : new Date(debut.getFullYear(), debut.getMonth() + 1, 0, 12);
    return { debut: iso(debut), fin: iso(fin), paiement: iso(plus(fin, 5)) };
  },

  async modaleNouvellePaie() {
    const dates = this.datesProposees();
    let creee = null;
    const ok = await tfModale({
      titre: 'Nouvelle paie',
      sousTitre: 'Les bulletins sont calcules des la creation, a partir des trajets termines de la periode.',
      corps: '<div class="row g-3">' +
        '<div class="col-6">' + tfChamp('Du', '<input class="tf-input" type="date" name="debut" required value="' + dates.debut + '">') + '</div>' +
        '<div class="col-6">' + tfChamp('Au', '<input class="tf-input" type="date" name="fin" required value="' + dates.fin + '">') + '</div>' +
        '<div class="col-12">' + tfChamp('Date de paiement', '<input class="tf-input" type="date" name="datePaiement" required value="' +
          dates.paiement + '">', 'Determine l annee des cumuls (plafonds RRQ, AE, RQAP).') + '</div></div>',
      valider: 'Creer et calculer',
      async action(d) {
        creee = await Store.ajouterPeriodePaie({ debut: d.get('debut'), fin: d.get('fin'), datePaiement: d.get('datePaiement') });
      }
    });
    if (ok && creee) {
      await this.dessinerPeriodes();
      await this.ouvrirPeriode(creee.id);
      tfNotifier('Paie ' + creee.id + ' creee : ' + creee.totaux.bulletins + ' bulletin(s) calcule(s).', 'succes');
    }
  },

  async ouvrirPeriode(id) {
    const donnees = await Store.periodePaie(id);
    const zone = document.querySelector('[data-detail]');
    document.querySelector('[data-bulletin]').classList.add('tf-hidden');
    if (!donnees) { zone.classList.add('tf-hidden'); return; }
    this.paie.selection = id;
    history.replaceState(null, '', 'paie.html?periode=' + encodeURIComponent(id));
    document.querySelectorAll('[data-periode]').forEach(function (tr) {
      tr.classList.toggle('is-active', tr.dataset.periode === id);
    });
    const p = donnees.periode;
    zone.querySelector('[data-detail-titre]').textContent = 'Paie ' + p.id;
    zone.querySelector('[data-detail-statut]').innerHTML = tfPastille(TfPaie.statut(p.statut));
    zone.querySelector('[data-detail-sous-titre]').textContent = 'Du ' + Format.dateLongue(p.debut) + ' au ' +
      Format.dateLongue(p.fin) + ' · versee le ' + Format.dateLongue(p.datePaiement) +
      (p.calculeeLe ? ' · calculee le ' + Format.jourHeure(p.calculeeLe) : '');
    const actions = {
      brouillon: [['calculer', 'Recalculer', 'tf-btn-ghost'], ['supprimer', 'Supprimer', 'tf-btn-danger'],
        ['exporter', 'Exporter (CSV)', 'tf-btn-ghost'], ['valider', 'Valider la paie', 'tf-btn-primary']],
      validee: [['rouvrir', 'Rouvrir', 'tf-btn-ghost'], ['exporter', 'Exporter (CSV)', 'tf-btn-ghost'],
        ['payer', 'Marquer comme payee', 'tf-btn-primary']],
      payee: [['exporter', 'Exporter (CSV)', 'tf-btn-ghost']]
    }[p.statut];
    const barre = zone.querySelector('[data-detail-actions]');
    barre.innerHTML = actions.map(function (a) {
      return '<button type="button" class="tf-btn ' + a[2] + '" style="height:40px;font-size:13.5px" data-action-paie="' +
        a[0] + '">' + a[1] + '</button>';
    }).join('');
    const moi = this;
    barre.querySelectorAll('[data-action-paie]').forEach(function (bouton) {
      bouton.addEventListener('click', function () { moi.actionPaie(p, bouton.dataset.actionPaie, bouton); });
    });
    const t = p.totaux;
    zone.querySelector('[data-detail-totaux]').innerHTML = [['Salaires bruts', t.brut], ['Retenues', t.retenues],
      ['Net a verser', t.net], ['Cotisations employeur', t.cotisationsEmployeur], ['Cout total', t.coutEmployeur]]
      .map(function (x, i) {
        return '<div class="col-6 col-md"><div class="tf-meta">' + x[0] + '</div><div class="tf-mono" style="font-size:' +
          (i === 2 ? '20px;font-weight:600' : '17px') + '">' + Format.montant(x[1]) + '</div></div>';
      }).join('');
    const corps = zone.querySelector('[data-bulletins]');
    corps.innerHTML = donnees.bulletins.map(function (b) {
      return '<tr data-ligne data-bulletin-id="' + b.id + '"><td class="tf-mono">' + b.id + '</td>' +
        '<td style="font-weight:500">' + Format.echapper(b.chauffeur) + '</td>' +
        '<td class="tf-meta">' + TfPaie.description(b) + '</td>' +
        '<td class="text-end tf-mono">' + Format.montant(b.brut) + '</td>' +
        '<td class="text-end tf-mono">' + Format.montant(b.retenues) + '</td>' +
        '<td class="text-end tf-mono" style="font-weight:500">' + Format.montant(b.net) + '</td>' +
        '<td class="text-end tf-mono">' + Format.montant(b.coutEmployeur) + '</td></tr>';
    }).join('') || '<tr><td colspan="7" class="tf-muted">Aucun bulletin : aucun chauffeur n a de remuneration active ' +
      '(onglet Remuneration des chauffeurs), puis « Recalculer ».</td></tr>';
    corps.querySelectorAll('[data-bulletin-id]').forEach(function (tr) {
      tr.addEventListener('click', function () { moi.ouvrirBulletin(tr.dataset.bulletinId); });
    });
    zone.classList.remove('tf-hidden');
  },

  async actionPaie(p, action, bouton) {
    const messages = {
      valider: 'Valider la paie ' + p.id + ' ? Les bulletins deviennent visibles par les chauffeurs (si le portail le permet) ' +
        'et ne peuvent plus etre modifies sans rouvrir la paie.',
      payer: 'Confirmer que les salaires de la paie ' + p.id + ' ont ete verses ? Une paie payee ne peut plus etre modifiee.',
      supprimer: 'Supprimer la paie ' + p.id + ' et ses bulletins ?',
      rouvrir: 'Rouvrir la paie ' + p.id + ' ? Elle repasse en brouillon et disparait du portail des chauffeurs.'
    };
    if (messages[action] && !window.confirm(messages[action])) return;
    bouton.disabled = true;
    try {
      if (action === 'exporter') {
        tfTelecharger(await Store.exporterPaie(p.id), 'paie-' + p.id + '-' + p.fin + '.csv');
      } else if (action === 'supprimer') {
        await Store.supprimerPeriodePaie(p.id);
        this.paie.selection = null;
        history.replaceState(null, '', 'paie.html');
        document.querySelector('[data-detail]').classList.add('tf-hidden');
        document.querySelector('[data-bulletin]').classList.add('tf-hidden');
        await this.dessinerPeriodes();
        tfNotifier('Paie supprimee.', 'succes');
        return;
      } else {
        await Store.actionPeriodePaie(p.id, action);
        await this.dessinerPeriodes();
        await this.ouvrirPeriode(p.id);
        tfNotifier({ calculer: 'Paie recalculee.', valider: 'Paie validee.', payer: 'Paie marquee comme payee.',
          rouvrir: 'Paie rouverte.' }[action], 'succes');
      }
    } catch (e) {
      tfNotifier(e.message);
    }
    bouton.disabled = false;
  },

  async ouvrirBulletin(id) {
    const donnees = await Store.bulletinPaie(id);
    if (!donnees) return;
    const zone = document.querySelector('[data-bulletin]');
    const brouillon = donnees.bulletin.periode.statut === 'brouillon';
    zone.innerHTML = '<div class="d-flex gap-2 flex-wrap mb-3 tf-no-print">' +
        (brouillon ? '<button type="button" class="tf-btn tf-btn-ghost" data-ajout="gain">+ Prime ou remboursement</button>' +
          '<button type="button" class="tf-btn tf-btn-ghost" data-ajout="retenue">+ Retenue (avance...)</button>' : '') +
        '<button type="button" class="tf-btn tf-btn-primary ms-auto" data-imprimer>Imprimer / PDF</button></div>' +
      tfRenduBulletin(donnees, { admin: true });
    zone.classList.remove('tf-hidden');
    zone.scrollIntoView({ behavior: 'smooth', block: 'start' });
    const moi = this;
    zone.querySelector('[data-imprimer]').addEventListener('click', function () { window.print(); });
    zone.querySelectorAll('[data-ajout]').forEach(function (b) {
      b.addEventListener('click', function () { moi.modaleLigne(donnees.bulletin, b.dataset.ajout); });
    });
    zone.querySelectorAll('[data-supprimer-ligne]').forEach(function (b) {
      b.addEventListener('click', async function () {
        b.disabled = true;
        try {
          await Store.supprimerLigneBulletin(b.dataset.supprimerLigne);
          await moi.apresModificationBulletin(donnees.bulletin);
        } catch (e) { tfNotifier(e.message); b.disabled = false; }
      });
    });
  },

  async modaleLigne(bulletin, genre) {
    const gain = genre === 'gain';
    const ok = await tfModale({
      titre: gain ? 'Ajouter un gain' : 'Ajouter une retenue',
      sousTitre: bulletin.chauffeur + ' · ' + bulletin.id,
      corps: tfChamp('Description', '<input class="tf-input" name="libelle" required maxlength="150" placeholder="' +
          (gain ? 'Prime de nuit, remboursement de repas...' : 'Avance sur salaire, uniforme...') + '">') +
        tfChamp('Montant ($)', '<input class="tf-input" name="montant" type="number" min="0.01" step="0.01" required>') +
        (gain ? '<label class="tf-check"><input type="checkbox" name="nonImposable"><span>Remboursement de depenses ' +
          '<span class="tf-meta">(non imposable : aucune cotisation)</span></span></label>' : ''),
      valider: 'Ajouter',
      async action(d) {
        await Store.ajouterLigneBulletin(bulletin.id, { genre: genre, libelle: tfTexte(d, 'libelle'),
          montant: tfNombre(d, 'montant'), imposable: d.get('nonImposable') !== 'on' });
      }
    });
    if (ok) await this.apresModificationBulletin(bulletin);
  },

  /* Apres un ajout ou un retrait de ligne : totaux de la paie a jour, bulletin rouvert. */
  async apresModificationBulletin(bulletin) {
    await this.dessinerPeriodes();
    await this.ouvrirPeriode(this.paie.selection);
    await this.ouvrirBulletin(bulletin.id);
  },

  async dessinerProfils() {
    const profils = await Store.profilsPaie();
    this.paie.profils = profils;
    const moi = this;
    const corps = document.querySelector('[data-profils]');
    corps.innerHTML = profils.map(function (x) {
      const p = x.profil;
      const taux = !p ? '—' : p.mode === 'horaire' ? Format.montant(p.tauxHoraire) + ' / h'
        : p.mode === 'trajet' ? Format.montant(p.tauxTrajet) + ' / trajet' : Format.montant(p.salairePeriode) + ' / paie';
      return '<tr data-ligne data-profil="' + x.chauffeurId + '"><td style="font-weight:500">' + Format.echapper(x.nom) + '</td>' +
        '<td>' + (p ? TfPaie.mode(p.mode) : '<span class="tf-muted">Non definie</span>') + '</td>' +
        '<td class="text-end tf-mono">' + taux + '</td>' +
        '<td>' + (p && p.actif ? '<span class="tf-pill ok">Dans la paie</span>' : '<span class="tf-pill muted">Hors paie</span>') + '</td>' +
        '<td class="text-end"><span style="font-size:13px;color:var(--tf-accent-deep)">' + (p ? 'Modifier' : 'Definir') + '</span></td></tr>';
    }).join('') || '<tr><td colspan="5" class="tf-muted">Aucun chauffeur.</td></tr>';
    corps.querySelectorAll('[data-profil]').forEach(function (tr) {
      tr.addEventListener('click', function () {
        moi.modaleProfil(profils.find(function (x) { return x.chauffeurId === tr.dataset.profil; }));
      });
    });
  },

  async modaleProfil(x) {
    const p = x.profil || { mode: 'horaire', tauxHoraire: '', tauxTrajet: '', salairePeriode: '', actif: true };
    const v = function (n) { return n ? n : ''; };
    const ok = await tfModale({
      titre: 'Remuneration de ' + x.nom,
      corps: tfChamp('Mode de remuneration', '<select class="tf-input" name="mode">' +
          [['horaire', 'A l heure (heures des trajets termines)'], ['trajet', 'Au trajet (montant par trajet termine)'],
           ['fixe', 'Salaire fixe par paie']].map(function (m) {
            return '<option value="' + m[0] + '"' + (p.mode === m[0] ? ' selected' : '') + '>' + m[1] + '</option>';
          }).join('') + '</select>') +
        '<div data-champ-mode="horaire">' + tfChamp('Taux horaire ($)', '<input class="tf-input" name="tauxHoraire" type="number" ' +
          'min="0" step="0.01" value="' + v(p.tauxHoraire) + '">', 'Salaire minimum au Quebec : 16,60 $ / h depuis le 1er mai 2026.') + '</div>' +
        '<div data-champ-mode="trajet">' + tfChamp('Montant par trajet ($)', '<input class="tf-input" name="tauxTrajet" type="number" ' +
          'min="0" step="0.01" value="' + v(p.tauxTrajet) + '">') + '</div>' +
        '<div data-champ-mode="fixe">' + tfChamp('Salaire brut par paie ($)', '<input class="tf-input" name="salairePeriode" ' +
          'type="number" min="0" step="0.01" value="' + v(p.salairePeriode) + '">') + '</div>' +
        '<label class="tf-check"><input type="checkbox" name="actif"' + (p.actif ? ' checked' : '') + '>' +
          '<span>Inclure ce chauffeur dans les paies</span></label>',
      valider: 'Enregistrer',
      preparer: function (formulaire) {
        const choix = formulaire.elements.mode;
        function montrer() {
          formulaire.querySelectorAll('[data-champ-mode]').forEach(function (z) {
            z.classList.toggle('tf-hidden', z.dataset.champMode !== choix.value);
          });
        }
        choix.addEventListener('change', montrer);
        montrer();
      },
      async action(d) {
        await Store.majProfilPaie(x.chauffeurId, { mode: d.get('mode'), tauxHoraire: tfNombre(d, 'tauxHoraire') || 0,
          tauxTrajet: tfNombre(d, 'tauxTrajet') || 0, salairePeriode: tfNombre(d, 'salairePeriode') || 0,
          actif: d.get('actif') === 'on' });
      }
    });
    if (ok) {
      await this.dessinerProfils();
      await this.dessinerPeriodes();
      tfNotifier('Remuneration enregistree. Recalculez les paies en brouillon pour l appliquer.', 'succes');
    }
  }
});

const TfPaieTexte = {
  pourcent(v) {
    return Number(v).toLocaleString('fr-CA', { minimumFractionDigits: 2, maximumFractionDigits: 3 }) + ' %';
  }
};

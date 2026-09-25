/* TransitFlow — ecrans administrateur de la flotte et de l entretien
   Auteur : Jonathan K-N

   Complete l objet Admin (admin.js) avec les pages :
     - vehicules.html   : liste de la flotte, etat d entretien, ajout ;
     - vehicule.html    : fiche d un vehicule (compteur, plans preventifs,
                          bons de travail, releves) ;
     - entretiens.html  : bons de travail, echeances, couts.
   Charge APRES admin.js : Admin.demarrer() (lance au DOMContentLoaded)
   trouve donc ces methodes comme les autres pages. Les fenetres de saisie
   utilisent tfModale (ui.js). */

/* ---- Morceaux d interface partages ------------------------------------ */

function tfPastille(etat) {
  return '<span class="tf-pill ' + etat.classe + '">' + Format.echapper(etat.texte) + '</span>';
}

/* Ordre de gravite des echeances, pour afficher la pire d un vehicule. */
const TF_GRAVITE = { 'en-retard': 0, 'bientot': 1, 'a-jour': 2 };

function tfPireEcheance(plans) {
  return plans.slice().sort(function (a, b) {
    return TF_GRAVITE[a.echeance.etat] - TF_GRAVITE[b.echeance.etat];
  })[0] || null;
}

function tfOptionsVehicules(vehicules, selection, vide) {
  return (vide !== undefined ? '<option value="">' + Format.echapper(vide) + '</option>' : '') +
    vehicules.map(function (v) {
      return '<option value="' + Format.echapper(v.plaque) + '"' + (v.plaque === selection ? ' selected' : '') + '>' +
        Format.echapper(v.plaque + ' — ' + v.modele) +
        (v.statut !== 'actif' ? ' (' + Format.statutVehicule(v.statut).texte.toLowerCase() + ')' : '') +
        '</option>';
    }).join('');
}

function tfOptionsPriorites(selection) {
  return ['basse', 'normale', 'haute', 'urgente'].map(function (p) {
    return '<option value="' + p + '"' + (p === (selection || 'normale') ? ' selected' : '') + '>' +
      Format.prioriteBon(p).texte + '</option>';
  }).join('');
}

function tfValeur(valeur) {
  return valeur === null || valeur === undefined ? '' : Format.echapper(valeur);
}

/* Active un groupe d onglets [data-onglet] / [data-volet] ; rappel(nom) a chaque changement. */
function tfOnglets(racine, rappel) {
  const onglets = racine.querySelectorAll('[data-onglet]');
  function montrer(nom) {
    onglets.forEach(function (o) { o.classList.toggle('active', o.dataset.onglet === nom); });
    racine.querySelectorAll('[data-volet]').forEach(function (v) {
      v.classList.toggle('tf-hidden', v.dataset.volet !== nom);
    });
    if (rappel) rappel(nom);
  }
  onglets.forEach(function (o) {
    o.addEventListener('click', function () { montrer(o.dataset.onglet); });
  });
  return montrer;
}

/* Active un groupe de puces de filtre : rappel(valeur) au clic. */
function tfPuces(selecteur, attribut, rappel) {
  const puces = document.querySelectorAll(selecteur);
  puces.forEach(function (b) {
    b.addEventListener('click', function () {
      puces.forEach(function (x) { x.classList.remove('active'); });
      b.classList.add('active');
      rappel(b.dataset[attribut]);
    });
  });
}

/* ---- Fenetres de saisie partagees ------------------------------------- */

const Fenetres = {
  /* Nouveau bon de travail. contexte : {vehicule, incident, plan, vehicules} */
  async nouveauBon(contexte) {
    // La liste de la page peut ne pas etre encore chargee : on la redemande si besoin.
    const vehicules = (contexte.vehicules && contexte.vehicules.length) ? contexte.vehicules : await Store.vehicules();
    const incident = contexte.incident || null;
    const plan = contexte.plan || null;
    let origine = '';
    if (plan) origine = 'Entretien preventif ' + plan.id + ' — ' + plan.libelle + ' (' + plan.vehicule + ')';
    if (incident) origine = 'A partir de l incident ' + incident.id + ' — ' + incident.titre;

    const corps = (plan ? '' :
      tfChamp('Vehicule', '<select class="tf-input" name="vehicule"' + (incident ? '' : ' required') + '>' +
        tfOptionsVehicules(vehicules, contexte.vehicule,
          incident ? 'Vehicule du trajet de l incident' : 'Choisir un vehicule') + '</select>') +
      '<div class="row g-3"><div class="col-12 col-sm-6">' +
        tfChamp('Type', '<select class="tf-input" name="type">' +
          Format.optionsTypesEntretien('reparation') + '</select>') +
      '</div><div class="col-12 col-sm-6">' +
        tfChamp('Priorite', '<select class="tf-input" name="priorite">' +
          tfOptionsPriorites(incident ? 'haute' : 'normale') + '</select>') +
      '</div></div>' +
      tfChamp('Titre', '<input class="tf-input" name="titre" maxlength="150" value="' +
        tfValeur(incident ? incident.titre : '') + '" required placeholder="Remplacement des plaquettes avant">') +
      tfChamp('Description', '<textarea class="tf-input" name="description" rows="3">' +
        tfValeur(incident ? incident.description : '') + '</textarea>')) +
      (plan ? tfChamp('Priorite', '<select class="tf-input" name="priorite">' +
        tfOptionsPriorites(plan.echeance.etat === 'en-retard' ? 'haute' : 'normale') + '</select>') : '') +
      '<div class="row g-3"><div class="col-12 col-sm-6">' +
        tfChamp('Date prevue', '<input class="tf-input" type="date" name="datePrevue" value="' +
          Format.aujourdhui() + '" required>') +
      '</div><div class="col-12 col-sm-6">' +
        tfChamp('Garage / fournisseur', '<input class="tf-input" name="fournisseur" maxlength="150">') +
      '</div></div>' +
      '<div class="row g-3"><div class="col-6">' +
        tfChamp('Pieces estimees ($)', '<input class="tf-input tf-mono" name="coutPieces" type="number" min="0" step="0.01">') +
      '</div><div class="col-6">' +
        tfChamp('Main-d oeuvre estimee ($)', '<input class="tf-input tf-mono" name="coutMainOeuvre" type="number" min="0" step="0.01">') +
      '</div></div>';

    let cree = null;
    await tfModale({
      titre: plan ? 'Planifier l entretien' : 'Nouveau bon de travail',
      sousTitre: origine,
      corps: corps,
      valider: 'Creer le bon',
      async action(d) {
        const bon = {
          priorite: tfTexte(d, 'priorite'),
          datePrevue: tfTexte(d, 'datePrevue'),
          fournisseur: tfTexte(d, 'fournisseur'),
          coutPieces: tfNombre(d, 'coutPieces') || 0,
          coutMainOeuvre: tfNombre(d, 'coutMainOeuvre') || 0
        };
        if (plan) {
          bon.planId = plan.id;
        } else {
          Object.assign(bon, {
            vehicule: tfTexte(d, 'vehicule'), type: tfTexte(d, 'type'), titre: tfTexte(d, 'titre'),
            description: tfTexte(d, 'description')
          });
        }
        if (incident) bon.incidentId = incident.id;
        cree = await Store.ajouterBon(bon);
      }
    });
    if (cree) tfNotifier('Bon ' + cree.id + ' cree.', 'succes');
    return cree;
  },

  async modifierBon(bon) {
    let resultat = null;
    await tfModale({
      titre: 'Modifier ' + bon.id,
      corps:
        tfChamp('Titre', '<input class="tf-input" name="titre" maxlength="150" required value="' +
          tfValeur(bon.titre) + '">') +
        tfChamp('Description', '<textarea class="tf-input" name="description" rows="3">' +
          tfValeur(bon.description) + '</textarea>') +
        '<div class="row g-3"><div class="col-12 col-sm-6">' +
          tfChamp('Priorite', '<select class="tf-input" name="priorite">' + tfOptionsPriorites(bon.priorite) +
            '</select>') +
        '</div><div class="col-12 col-sm-6">' +
          tfChamp('Date prevue', '<input class="tf-input" type="date" name="datePrevue" required value="' +
            tfValeur(bon.datePrevue) + '">') +
        '</div></div>' +
        tfChamp('Garage / fournisseur', '<input class="tf-input" name="fournisseur" maxlength="150" value="' +
          tfValeur(bon.fournisseur) + '">') +
        '<div class="row g-3"><div class="col-6">' +
          tfChamp('Pieces ($)', '<input class="tf-input tf-mono" name="coutPieces" type="number" min="0" step="0.01" value="' +
            tfValeur(bon.coutPieces) + '">') +
        '</div><div class="col-6">' +
          tfChamp('Main-d oeuvre ($)', '<input class="tf-input tf-mono" name="coutMainOeuvre" type="number" min="0" step="0.01" value="' +
            tfValeur(bon.coutMainOeuvre) + '">') +
        '</div></div>',
      async action(d) {
        resultat = await Store.majBon(bon.id, {
          titre: tfTexte(d, 'titre'), description: tfTexte(d, 'description'),
          priorite: tfTexte(d, 'priorite'), datePrevue: tfTexte(d, 'datePrevue'),
          fournisseur: tfTexte(d, 'fournisseur'),
          coutPieces: tfNombre(d, 'coutPieces') || 0, coutMainOeuvre: tfNombre(d, 'coutMainOeuvre') || 0
        });
      }
    });
    return resultat;
  },

  /* Cloture : compteur, date, couts reels, notes. compteurActuel : km du vehicule (indication). */
  async terminerBon(bon, compteurActuel) {
    let resultat = null;
    await tfModale({
      titre: 'Terminer ' + bon.id,
      sousTitre: bon.vehicule + ' · ' + bon.titre,
      corps:
        '<div class="row g-3"><div class="col-12 col-sm-6">' +
          tfChamp('Compteur a la sortie (km)', '<input class="tf-input tf-mono" name="kilometrage" type="number" min="' +
            (compteurActuel || 0) + '" step="1" placeholder="' + tfValeur(compteurActuel) + '">',
            compteurActuel !== undefined ? 'Actuel : ' + Format.km(compteurActuel) : '') +
        '</div><div class="col-12 col-sm-6">' +
          tfChamp('Termine le', '<input class="tf-input" type="date" name="dateFin" required max="' +
            Format.aujourdhui() + '" value="' + Format.aujourdhui() + '">') +
        '</div></div>' +
        tfChamp('Garage / fournisseur', '<input class="tf-input" name="fournisseur" maxlength="150" value="' +
          tfValeur(bon.fournisseur) + '">') +
        '<div class="row g-3"><div class="col-6">' +
          tfChamp('Pieces ($)', '<input class="tf-input tf-mono" name="coutPieces" type="number" min="0" step="0.01" value="' +
            tfValeur(bon.coutPieces) + '">') +
        '</div><div class="col-6">' +
          tfChamp('Main-d oeuvre ($)', '<input class="tf-input tf-mono" name="coutMainOeuvre" type="number" min="0" step="0.01" value="' +
            tfValeur(bon.coutMainOeuvre) + '">') +
        '</div></div>' +
        tfChamp('Travaux realises', '<textarea class="tf-input" name="notes" rows="3" ' +
          'placeholder="Pieces changees, observations, recommandations..."></textarea>'),
      valider: 'Terminer l intervention',
      danger: true,
      async action(d) {
        resultat = await Store.actionBon(bon.id, 'terminer', {
          kilometrage: tfNombre(d, 'kilometrage'),
          dateFin: tfTexte(d, 'dateFin'),
          fournisseur: tfTexte(d, 'fournisseur'),
          coutPieces: tfNombre(d, 'coutPieces') || 0,
          coutMainOeuvre: tfNombre(d, 'coutMainOeuvre') || 0,
          notes: tfTexte(d, 'notes')
        });
      }
    });
    if (resultat) tfNotifier('Bon ' + resultat.id + ' termine.', 'succes');
    return resultat;
  },

  async annulerBon(bon) {
    let resultat = null;
    await tfModale({
      titre: 'Annuler ' + bon.id,
      sousTitre: bon.vehicule + ' · ' + bon.titre,
      corps: tfChamp('Motif', '<textarea class="tf-input" name="motif" rows="3" required ' +
        'placeholder="Piece indisponible, intervention reportee..."></textarea>'),
      valider: 'Annuler le bon',
      danger: true,
      async action(d) {
        resultat = await Store.actionBon(bon.id, 'annuler', { motif: tfTexte(d, 'motif') });
      }
    });
    return resultat;
  },

  /* Ajout (plan absent) ou modification d un plan preventif. */
  async plan(vehicule, plan) {
    let resultat = null;
    await tfModale({
      titre: plan ? 'Modifier ' + plan.libelle : 'Nouveau plan d entretien',
      sousTitre: vehicule.plaque + ' · compteur ' + Format.km(vehicule.kilometrage),
      corps:
        (plan ? '' : tfChamp('Type', '<select class="tf-input" name="type" data-type-plan>' +
          Format.optionsTypesEntretien('vidange') + '</select>')) +
        tfChamp('Libelle', '<input class="tf-input" name="libelle" maxlength="150" required value="' +
          tfValeur(plan ? plan.libelle : 'Vidange et filtres') + '" data-libelle-plan>') +
        '<div class="row g-3"><div class="col-6">' +
          tfChamp('Tous les (km)', '<input class="tf-input tf-mono" name="intervalleKm" type="number" min="100" step="100" value="' +
            tfValeur(plan ? plan.intervalleKm : 8000) + '">') +
        '</div><div class="col-6">' +
          tfChamp('Ou tous les (jours)', '<input class="tf-input tf-mono" name="intervalleJours" type="number" min="1" value="' +
            tfValeur(plan ? plan.intervalleJours : 180) + '">') +
        '</div></div>' +
        '<p class="tf-meta mb-0">La premiere limite atteinte declenche l entretien. Laissez un champ vide pour ' +
          'ne suivre que l autre.</p>' +
        '<div class="row g-3"><div class="col-6">' +
          tfChamp('Dernier entretien (km)', '<input class="tf-input tf-mono" name="dernierKm" type="number" min="0" max="' +
            vehicule.kilometrage + '" value="' + tfValeur(plan ? plan.dernierKm : vehicule.kilometrage) + '">') +
        '</div><div class="col-6">' +
          tfChamp('Date du dernier entretien', '<input class="tf-input" type="date" name="derniereDate" max="' +
            Format.aujourdhui() + '" value="' + tfValeur(plan ? plan.derniereDate : Format.aujourdhui()) + '">') +
        '</div></div>',
      preparer(formulaire) {
        // Le libelle suit le type choisi tant que l utilisateur ne l a pas modifie.
        const type = formulaire.querySelector('[data-type-plan]');
        const libelle = formulaire.querySelector('[data-libelle-plan]');
        if (!type) return;
        let libelleModifie = false;
        libelle.addEventListener('input', function () { libelleModifie = true; });
        type.addEventListener('change', function () {
          if (!libelleModifie) libelle.value = Format.typeEntretien(type.value);
        });
      },
      async action(d) {
        const champs = {
          libelle: tfTexte(d, 'libelle'),
          intervalleKm: tfNombre(d, 'intervalleKm'),
          intervalleJours: tfNombre(d, 'intervalleJours'),
          dernierKm: tfNombre(d, 'dernierKm'),
          derniereDate: tfTexte(d, 'derniereDate') || null
        };
        if (champs.dernierKm === null) delete champs.dernierKm;
        if (!champs.derniereDate) delete champs.derniereDate;
        if (plan) {
          resultat = await Store.majPlan(plan.id, champs);
        } else {
          champs.vehicule = vehicule.plaque;
          champs.type = tfTexte(d, 'type');
          resultat = await Store.ajouterPlan(champs);
        }
      }
    });
    return resultat;
  }
};

/* ---- Pages ------------------------------------------------------------- */

Object.assign(Admin, {
  /* Liste de la flotte + ajout d un vehicule */
  async pageVehicules() {
    const corps = document.querySelector('[data-liste-vehicules]');
    const formulaire = document.querySelector('[data-formulaire]');
    const etat = { statut: 'tous' };
    formulaire.querySelector('[name=annee]').max = new Date().getFullYear() + 1;

    async function dessiner() {
      const [vehicules, tous, chauffeurs, plans] = await Promise.all([
        Store.vehicules(etat), Store.vehicules(), Store.chauffeurs(), Store.plansEntretien()
      ]);
      const disponibles = tous.filter(function (v) { return v.statut === 'actif'; }).length;
      document.querySelector('[data-compteur]').textContent =
        tous.length + ' vehicule' + (tous.length > 1 ? 's' : '') + ' · ' + disponibles + ' disponible' +
        (disponibles > 1 ? 's' : '');
      corps.innerHTML = vehicules.map(function (v) {
        const habituels = chauffeurs.filter(function (c) { return c.plaqueHabituelle === v.plaque; });
        const pire = tfPireEcheance(plans.filter(function (p) { return p.vehicule === v.plaque; }));
        const lien = 'vehicule.html?plaque=' + encodeURIComponent(v.plaque);
        return '<tr data-ligne="' + Format.echapper(lien) + '">' +
          '<td class="tf-mono">' + Format.echapper(v.plaque) + '</td>' +
          '<td>' + Format.echapper(v.modele) + (v.annee ? ' <span class="tf-meta">' + v.annee + '</span>' : '') + '</td>' +
          '<td class="tf-mono">' + Format.km(v.kilometrage) + '</td>' +
          '<td>' + tfPastille(Format.statutVehicule(v.statut)) + '</td>' +
          '<td>' + (pire
            ? tfPastille(Format.etatEcheance(pire.echeance.etat)) +
              (pire.echeance.etat !== 'a-jour'
                ? '<div class="tf-meta mt-1">' + Format.echapper(pire.libelle) + '</div>' : '')
            : '<span class="tf-meta">Aucun plan</span>') + '</td>' +
          '<td class="tf-muted">' + (habituels.map(function (c) {
            return Format.echapper(Format.nomCourt(c));
          }).join(', ') || '—') + '</td>' +
          '<td class="text-end"><a href="' + Format.echapper(lien) + '" style="font-size:13px">Ouvrir</a></td></tr>';
      }).join('') || '<tr><td colspan="7" class="tf-muted">' + (etat.statut === 'tous'
        ? 'Aucun vehicule. Ajoutez le premier ci-dessus.' : 'Aucun vehicule dans cet etat.') + '</td></tr>';
      corps.querySelectorAll('[data-ligne]').forEach(function (ligne) {
        ligne.addEventListener('click', function (e) {
          if (e.target.closest('a')) return;
          window.location.href = ligne.dataset.ligne;
        });
      });
    }

    tfPuces('[data-filtre-vehicule]', 'filtreVehicule', function (valeur) {
      etat.statut = valeur;
      dessiner().catch(function (e) { tfNotifier(e.message); });
    });

    formulaire.addEventListener('submit', function (e) {
      e.preventDefault();
      tfEnvoyer(formulaire, async function () {
        const d = new FormData(formulaire);
        const vehicule = await Store.ajouterVehicule({
          plaque: tfTexte(d, 'plaque').toUpperCase(),
          modele: tfTexte(d, 'modele'),
          annee: tfNombre(d, 'annee'),
          kilometrage: tfNombre(d, 'kilometrage') || 0
        });
        formulaire.reset();
        tfNotifier('Vehicule ' + vehicule.plaque + ' ajoute.', 'succes');
        await dessiner();
      });
    });
    return dessiner();
  },

  /* Fiche d un vehicule */
  async pageVehicule() {
    const plaque = new URLSearchParams(location.search).get('plaque');
    const contenu = document.querySelector('[data-contenu]');
    let fiche = await Store.vehicule(plaque);
    if (!fiche) {
      contenu.innerHTML = '<p class="tf-muted">Vehicule introuvable. <a href="vehicules.html">Retour a la flotte</a></p>';
      return;
    }
    let plans = [];
    let bons = [];
    const debutAnnee = new Date().getFullYear() + '-01-01';

    async function recharger() {
      [fiche, plans, bons] = await Promise.all([
        Store.vehicule(plaque),
        Store.plansEntretien({ vehicule: plaque }),
        Store.bonsTravail({ vehicule: plaque, statut: 'tous' })
      ]);
      dessiner();
    }

    function dessiner() {
      const v = fiche.vehicule;
      const s = Format.statutVehicule(v.statut);
      document.title = v.plaque + ' · TransitFlow';
      document.querySelector('[data-fil]').textContent = v.plaque;
      document.querySelector('[data-plaque]').textContent = v.plaque;
      const pastille = document.querySelector('[data-statut]');
      pastille.className = 'tf-pill ' + s.classe;
      pastille.textContent = s.texte;
      document.querySelector('[data-modele]').textContent = v.modele + (v.annee ? ' · ' + v.annee : '');
      document.querySelector('[data-compteur]').textContent = Format.km(v.kilometrage);
      document.querySelector('[data-nouveau-bon]').href =
        'entretiens.html?nouveau=1&vehicule=' + encodeURIComponent(v.plaque);

      const bascule = document.querySelector('[data-basculer-service]');
      bascule.textContent = v.statut === 'hors-service' ? 'Remettre en service' : 'Mettre hors service';
      bascule.disabled = v.statut === 'maintenance';
      bascule.title = v.statut === 'maintenance' ? 'Terminez le bon de travail en cours pour remettre ce vehicule en service' : '';

      const coutAnnee = bons.filter(function (b) {
        return b.statut === 'termine' && b.fin && b.fin.slice(0, 10) >= debutAnnee;
      }).reduce(function (total, b) { return total + b.coutTotal; }, 0);
      const infos = [
        ['NIV', v.numeroSerie || '—', true],
        ['Annee', v.annee || '—', true],
        ['Mise en service', v.miseEnService ? Format.dateLongue(v.miseEnService) : '—'],
        ['Entretien ' + new Date().getFullYear(), Format.montant(coutAnnee), true]
      ];
      document.querySelector('[data-informations]').innerHTML = infos.map(function (i) {
        return '<div><div class="tf-meta">' + i[0] + '</div><div class="tf-props-value' + (i[2] ? ' tf-mono' : '') +
          '" style="word-break:break-all">' + Format.echapper(i[1]) + '</div></div>';
      }).join('');

      document.querySelector('[data-chauffeurs]').innerHTML = fiche.chauffeursHabituels.map(function (c) {
        return '<a class="d-inline-flex align-items-center gap-2" href="chauffeur.html?id=' + encodeURIComponent(c.id) +
          '">' + tfCelluleChauffeur(c) + '</a>';
      }).join('') || '<span class="tf-meta">Aucun</span>';

      const sources = { initial: 'Mise en flotte', manuel: 'Saisie', trajet: 'Fin de trajet', entretien: 'Atelier' };
      document.querySelector('[data-releves]').innerHTML = fiche.releves.map(function (r) {
        return '<div class="d-flex align-items-baseline gap-3" style="font-size:13.5px">' +
          '<span class="tf-mono" style="min-width:92px">' + Format.km(r.kilometrage) + '</span>' +
          '<span class="tf-meta flex-fill">' + Format.echapper(sources[r.source] || r.source) +
          (r.note ? ' · ' + Format.echapper(r.note) : '') + '</span>' +
          '<span class="tf-meta tf-mono">' + Format.dateCourte(r.releveLe) + '</span></div>';
      }).join('') || '<span class="tf-meta">Aucun releve.</span>';

      // Plans preventifs
      const retard = plans.filter(function (p) { return p.echeance.etat === 'en-retard'; }).length;
      const proches = plans.filter(function (p) { return p.echeance.etat === 'bientot'; }).length;
      document.querySelector('[data-nb-plans]').textContent = plans.length ? '(' + plans.length + ')' : '';
      document.querySelector('[data-resume-plans]').textContent = plans.length
        ? retard + ' en retard · ' + proches + ' a prevoir · ' + (plans.length - retard - proches) + ' a jour'
        : 'Aucun programme preventif pour ce vehicule.';
      document.querySelector('[data-plans]').innerHTML = plans.map(function (p) {
        return '<tr>' +
          '<td><div style="font-weight:500">' + Format.echapper(p.libelle) + '</div>' +
            '<div class="tf-meta">' + Format.echapper(Format.intervalle(p)) + '</div></td>' +
          '<td class="tf-mono" style="font-size:13px;white-space:nowrap">' +
            (p.intervalleKm ? Format.km(p.dernierKm) + '<br>' : '') + Format.dateCourte(p.derniereDate) + '</td>' +
          '<td class="tf-mono" style="font-size:13px;white-space:nowrap">' +
            (p.prochainKm ? Format.km(p.prochainKm) + '<br>' : '') +
            (p.prochaineDate ? Format.dateCourte(p.prochaineDate) : '') + '</td>' +
          '<td>' + tfPastille(Format.etatEcheance(p.echeance.etat)) +
            '<div class="tf-meta mt-1">' + Format.echapper(Format.resteEcheance(p.echeance)) + '</div></td>' +
          '<td class="text-end" style="white-space:nowrap">' +
            (p.bonOuvert
              ? '<a class="tf-mono" style="font-size:13px" href="entretiens.html?bon=' + encodeURIComponent(p.bonOuvert) +
                '">' + Format.echapper(p.bonOuvert) + '</a>'
              : '<button type="button" class="tf-btn tf-btn-ghost sm" data-planifier="' + Format.echapper(p.id) +
                '">Planifier</button>') +
            ' <button type="button" class="tf-btn tf-btn-ghost sm" data-modifier-plan="' + Format.echapper(p.id) +
              '" aria-label="Modifier">Modifier</button>' +
            ' <button type="button" class="tf-btn tf-btn-danger sm" data-desactiver-plan="' + Format.echapper(p.id) +
              '" aria-label="Retirer">Retirer</button></td></tr>';
      }).join('') || '<tr><td colspan="5" class="tf-muted">Ajoutez un plan (vidange, inspection...) pour ' +
        'suivre les echeances de ce vehicule.</td></tr>';

      document.querySelectorAll('[data-planifier]').forEach(function (b) {
        b.addEventListener('click', async function () {
          const plan = plans.find(function (p) { return p.id === b.dataset.planifier; });
          try {
            const bon = await Fenetres.nouveauBon({ plan: plan });
            if (bon) await recharger();
          } catch (e) { tfNotifier(e.message); }
        });
      });
      document.querySelectorAll('[data-modifier-plan]').forEach(function (b) {
        b.addEventListener('click', async function () {
          const plan = plans.find(function (p) { return p.id === b.dataset.modifierPlan; });
          if (await Fenetres.plan(fiche.vehicule, plan)) await recharger();
        });
      });
      document.querySelectorAll('[data-desactiver-plan]').forEach(function (b) {
        b.addEventListener('click', async function () {
          const plan = plans.find(function (p) { return p.id === b.dataset.desactiverPlan; });
          if (!window.confirm('Retirer le plan « ' + plan.libelle + ' » ? L historique des bons est conserve.')) return;
          try {
            await Store.desactiverPlan(plan.id);
            tfNotifier('Plan retire.', 'succes');
            await recharger();
          } catch (e) { tfNotifier(e.message); }
        });
      });

      // Bons de travail
      document.querySelector('[data-nb-bons]').textContent = bons.length ? '(' + bons.length + ')' : '';
      document.querySelector('[data-bons]').innerHTML = bons.map(function (b) {
        return '<tr data-ligne="' + Format.echapper(b.id) + '">' +
          '<td class="tf-mono"><a href="entretiens.html?bon=' + encodeURIComponent(b.id) + '">' +
            Format.echapper(b.id) + '</a></td>' +
          '<td class="tf-mono" style="font-size:13px;white-space:nowrap">' + Format.dateCourte(b.fin || b.datePrevue) + '</td>' +
          '<td><div>' + Format.echapper(b.titre) + '</div><div class="tf-meta">' +
            Format.echapper(Format.typeEntretien(b.type)) + ' · ' + (b.categorie === 'preventif' ? 'preventif' : 'correctif') +
            '</div></td>' +
          '<td>' + tfPastille(Format.statutBon(b.statut)) + '</td>' +
          '<td class="tf-mono text-end">' + (b.coutTotal ? Format.montant(b.coutTotal) : '—') + '</td></tr>';
      }).join('') || '<tr><td colspan="5" class="tf-muted">Aucun bon de travail pour ce vehicule.</td></tr>';
      document.querySelectorAll('[data-bons] [data-ligne]').forEach(function (ligne) {
        ligne.addEventListener('click', function () {
          window.location.href = 'entretiens.html?bon=' + encodeURIComponent(ligne.dataset.ligne);
        });
      });
    }

    tfOnglets(document.querySelector('.tf-tabs').parentElement);

    document.querySelector('[data-relever]').addEventListener('click', async function () {
      const v = fiche.vehicule;
      const ok = await tfModale({
        titre: 'Relever le compteur',
        sousTitre: v.plaque + ' · actuel ' + Format.km(v.kilometrage),
        corps: tfChamp('Kilometrage', '<input class="tf-input tf-mono" name="kilometrage" type="number" required min="' +
            v.kilometrage + '" step="1" value="' + v.kilometrage + '">') +
          tfChamp('Note (facultatif)', '<input class="tf-input" name="note" maxlength="255" placeholder="Plein d essence">'),
        async action(d) { await Store.releverKilometrage(v.plaque, tfNombre(d, 'kilometrage'), tfTexte(d, 'note')); }
      });
      if (ok) { tfNotifier('Compteur mis a jour.', 'succes'); await recharger(); }
    });

    document.querySelector('[data-modifier]').addEventListener('click', async function () {
      const v = fiche.vehicule;
      const ok = await tfModale({
        titre: 'Modifier ' + v.plaque,
        corps: tfChamp('Modele', '<input class="tf-input" name="modele" maxlength="100" required value="' +
            tfValeur(v.modele) + '">') +
          '<div class="row g-3"><div class="col-6">' +
            tfChamp('Annee', '<input class="tf-input tf-mono" name="annee" type="number" min="1980" max="' +
              (new Date().getFullYear() + 1) + '" value="' + tfValeur(v.annee) + '">') +
          '</div><div class="col-6">' +
            tfChamp('Mise en service', '<input class="tf-input" name="miseEnService" type="date" max="' +
              Format.aujourdhui() + '" value="' + tfValeur(v.miseEnService) + '">') +
          '</div></div>' +
          tfChamp('NIV (numero de serie)', '<input class="tf-input tf-mono" name="numeroSerie" maxlength="17" ' +
            'style="text-transform:uppercase" value="' + tfValeur(v.numeroSerie) + '">', '17 caracteres, sans I, O ni Q'),
        async action(d) {
          await Store.majVehicule(v.plaque, {
            modele: tfTexte(d, 'modele'), annee: tfNombre(d, 'annee'),
            miseEnService: tfTexte(d, 'miseEnService') || null, numeroSerie: tfTexte(d, 'numeroSerie').toUpperCase()
          });
        }
      });
      if (ok) { tfNotifier('Fiche mise a jour.', 'succes'); await recharger(); }
    });

    document.querySelector('[data-basculer-service]').addEventListener('click', async function () {
      const v = fiche.vehicule;
      const vers = v.statut === 'hors-service' ? 'actif' : 'hors-service';
      if (vers === 'hors-service' &&
          !window.confirm('Mettre ' + v.plaque + ' hors service ? Il ne pourra plus etre choisi pour un trajet.')) return;
      try {
        await Store.majVehicule(v.plaque, { statut: vers });
        await recharger();
      } catch (e) { tfNotifier(e.message); }
    });

    document.querySelector('[data-ajouter-plan]').addEventListener('click', async function () {
      if (await Fenetres.plan(fiche.vehicule, null)) {
        tfNotifier('Plan ajoute.', 'succes');
        await recharger();
      }
    });

    await recharger();
  },

  /* Bons de travail, echeances et couts */
  async pageEntretiens() {
    const params = new URLSearchParams(location.search);
    const etat = { statut: 'ouverts', vehicule: '', recherche: '' };
    let selection = params.get('bon');
    let vehicules = [];
    let derniereDemande = 0;
    const corps = document.querySelector('[data-liste-bons]');
    const detail = document.querySelector('[data-detail-bon]');

    // Un lien direct vers un bon (depuis la fiche vehicule) doit le montrer quel que soit son statut.
    if (selection) {
      etat.statut = 'tous';
      document.querySelectorAll('[data-filtre-bon]').forEach(function (b) {
        b.classList.toggle('active', b.dataset.filtreBon === 'tous');
      });
    }

    async function indicateurs() {
      const annee = new Date().getFullYear();
      const [e, ouverts, couts] = await Promise.all([
        Store.echeances(), Store.bonsTravail({ statut: 'ouverts' }),
        Store.coutsEntretien({ debut: annee + '-01-01', fin: Format.aujourdhui() })
      ]);
      document.querySelector('[data-kpi="en-retard"]').textContent = e.resume.enRetard;
      document.querySelector('[data-kpi="bientot"]').textContent = e.resume.bientot;
      document.querySelector('[data-kpi="ouverts"]').textContent = ouverts.length;
      const enCours = ouverts.filter(function (b) { return b.statut === 'en-cours'; }).length;
      const enRetard = ouverts.filter(function (b) { return b.enRetard; }).length;
      document.querySelector('[data-kpi-note="ouverts"]').textContent =
        enCours + ' en cours' + (enRetard ? ' · ' + enRetard + ' en retard' : '');
      document.querySelector('[data-kpi="couts"]').textContent = Format.montant(couts.total.total);
      document.querySelector('[data-kpi-note="couts"]').textContent =
        couts.total.nombre + ' intervention' + (couts.total.nombre > 1 ? 's' : '') + ' terminee' +
        (couts.total.nombre > 1 ? 's' : '');
      document.querySelector('[data-nb-echeances]').textContent =
        (e.resume.enRetard + e.resume.bientot) ? '(' + (e.resume.enRetard + e.resume.bientot) + ')' : '';
      document.querySelector('[data-sous-titre]').textContent =
        Format.dateLongue(Format.aujourdhui()) + ' · ' + vehicules.filter(function (v) {
          return v.statut === 'maintenance';
        }).length + ' vehicule(s) a l atelier';
    }

    async function dessinerBons() {
      const numero = ++derniereDemande;
      const bons = await Store.bonsTravail(etat);
      if (numero !== derniereDemande) return;
      if (!selection || !bons.some(function (b) { return b.id === selection; })) {
        selection = bons[0] ? bons[0].id : null;
      }
      corps.innerHTML = bons.map(function (b) {
        const actif = b.id === selection;
        return '<tr data-ligne="' + Format.echapper(b.id) + '"' + (actif ? ' class="is-active is-open"' : '') + '>' +
          '<td class="tf-mono">' + Format.echapper(b.id) + '</td>' +
          '<td class="tf-mono">' + Format.echapper(b.vehicule) + '</td>' +
          '<td><div>' + Format.echapper(b.titre) + '</div><div class="tf-meta">' +
            Format.echapper(Format.typeEntretien(b.type)) +
            (b.priorite === 'haute' || b.priorite === 'urgente'
              ? ' · <span class="' + (b.priorite === 'urgente' ? 'tf-danger' : '') + '">priorite ' +
                Format.prioriteBon(b.priorite).texte.toLowerCase() + '</span>' : '') + '</div></td>' +
          '<td class="tf-mono' + (b.enRetard ? ' tf-danger' : '') + '" style="font-size:13px;white-space:nowrap">' +
            Format.dateCourte(b.datePrevue) + '</td>' +
          '<td>' + tfPastille(Format.statutBon(b.statut)) + '</td></tr>';
      }).join('') || '<tr><td colspan="5" class="tf-muted">Aucun bon de travail.</td></tr>';
      corps.querySelectorAll('[data-ligne]').forEach(function (ligne) {
        ligne.addEventListener('click', function () {
          selection = ligne.dataset.ligne;
          corps.querySelectorAll('[data-ligne]').forEach(function (l) {
            l.classList.toggle('is-active', l === ligne);
            l.classList.toggle('is-open', l === ligne);
          });
          dessinerDetail().catch(function (e) { tfNotifier(e.message); });
        });
      });
      await dessinerDetail();
    }

    async function dessinerDetail() {
      if (!selection) {
        detail.innerHTML = '<p class="tf-muted mb-0">Choisir un bon de travail dans la liste.</p>';
        return;
      }
      const b = await Store.bonTravail(selection);
      if (!b) { detail.innerHTML = '<p class="tf-muted mb-0">Bon de travail introuvable.</p>'; return; }
      const vehicule = vehicules.find(function (v) { return v.plaque === b.vehicule; });
      const proprietes = [
        ['Prevu le', Format.dateLongue(b.datePrevue), b.enRetard],
        ['Debut', b.debut ? Format.jourHeure(b.debut) : '—'],
        ['Fin', b.fin ? Format.jourHeure(b.fin) : '—'],
        ['Compteur', b.kilometrage !== null ? Format.km(b.kilometrage) : '—'],
        ['Garage', b.fournisseur || '—'],
        ['Categorie', b.categorie === 'preventif' ? 'Preventif' : 'Correctif']
      ];
      detail.innerHTML =
        '<div class="d-flex align-items-center gap-2 flex-wrap">' +
          tfPastille(Format.statutBon(b.statut)) + tfPastille(Format.prioriteBon(b.priorite)) +
          '<span class="tf-mono ms-auto tf-meta">' + Format.echapper(b.id) + '</span></div>' +
        '<div><h2 class="tf-h2" style="font-size:20px">' + Format.echapper(b.titre) + '</h2>' +
          '<div class="tf-meta mt-1">' + Format.echapper(Format.typeEntretien(b.type)) + '</div></div>' +
        '<a class="d-flex align-items-center gap-3 p-3" style="border-radius:12px;background:var(--tf-bg);color:inherit" ' +
          'href="vehicule.html?plaque=' + encodeURIComponent(b.vehicule) + '">' +
          '<span class="tf-mono" style="font-size:15px;font-weight:500">' + Format.echapper(b.vehicule) + '</span>' +
          '<span class="tf-meta">' + Format.echapper(b.modele) +
            (vehicule ? ' · ' + Format.km(vehicule.kilometrage) : '') + '</span>' +
          (vehicule ? '<span class="ms-auto">' + tfPastille(Format.statutVehicule(vehicule.statut)) + '</span>' : '') +
        '</a>' +
        (b.planId || b.incidentId ? '<div class="tf-meta">Origine : ' + (b.planId
          ? 'plan preventif <span class="tf-mono">' + Format.echapper(b.planId) + '</span>'
          : '<a href="incidents.html">incident <span class="tf-mono">' + Format.echapper(b.incidentId) + '</span></a>') +
          '</div>' : '') +
        (b.description ? '<div><div class="tf-meta mb-1">Description</div><p class="mb-0" ' +
          'style="font-size:14.5px;line-height:1.6;white-space:pre-line">' + Format.echapper(b.description) + '</p></div>' : '') +
        '<div class="tf-props">' + proprietes.map(function (p) {
          return '<div><div class="tf-meta">' + p[0] + '</div><div class="tf-props-value' + (p[2] ? ' tf-danger' : '') +
            '">' + Format.echapper(p[1]) + '</div></div>';
        }).join('') + '</div>' +
        '<div class="d-flex flex-column gap-2 p-3" style="border-radius:12px;border:1px solid var(--tf-line)">' +
          '<div class="d-flex"><span class="tf-meta">Pieces</span><span class="tf-mono ms-auto">' +
            Format.montant(b.coutPieces) + '</span></div>' +
          '<div class="d-flex"><span class="tf-meta">Main-d oeuvre</span><span class="tf-mono ms-auto">' +
            Format.montant(b.coutMainOeuvre) + '</span></div>' +
          '<div class="d-flex pt-2" style="border-top:1px solid var(--tf-line);font-weight:500">' +
            '<span>Total' + (b.statut === 'termine' ? '' : ' estime') + '</span><span class="tf-mono ms-auto">' +
            Format.montant(b.coutTotal) + '</span></div></div>' +
        (b.notesCloture ? '<div><div class="tf-meta mb-1">' + (b.statut === 'annule' ? 'Motif d annulation' :
          'Travaux realises') + '</div><p class="mb-0" style="font-size:14.5px;line-height:1.6;white-space:pre-line">' +
          Format.echapper(b.notesCloture) + '</p></div>' : '') +
        '<div class="tf-meta">Cree le ' + Format.dateLongue(b.creeLe) + (b.creePar ? ' par ' +
          Format.echapper(b.creePar) : '') + '</div>' +
        (b.statut === 'planifie' || b.statut === 'en-cours'
          ? '<div class="d-flex gap-2 flex-wrap pt-3" style="border-top:1px solid var(--tf-line)">' +
            (b.statut === 'planifie'
              ? '<button type="button" class="tf-btn tf-btn-primary flex-fill" data-action="demarrer">Demarrer</button>' : '') +
            '<button type="button" class="tf-btn tf-btn-dark flex-fill" data-action="terminer">Terminer</button>' +
            '<button type="button" class="tf-btn tf-btn-ghost" data-action="modifier">Modifier</button>' +
            '<button type="button" class="tf-btn tf-btn-danger" data-action="annuler">Annuler</button></div>'
          : '');

      detail.querySelectorAll('[data-action]').forEach(function (bouton) {
        bouton.addEventListener('click', async function () {
          try {
            let resultat = null;
            const action = bouton.dataset.action;
            if (action === 'demarrer') {
              bouton.disabled = true;
              resultat = await Store.actionBon(b.id, 'demarrer');
              tfNotifier(b.vehicule + ' est maintenant en maintenance.', 'succes');
            } else if (action === 'terminer') {
              resultat = await Fenetres.terminerBon(b, vehicule ? vehicule.kilometrage : undefined);
            } else if (action === 'annuler') {
              resultat = await Fenetres.annulerBon(b);
            } else if (action === 'modifier') {
              resultat = await Fenetres.modifierBon(b);
            }
            if (resultat) await toutRedessiner();
          } catch (e) {
            bouton.disabled = false;
            tfNotifier(e.message);
          }
        });
      });
    }

    let toutesEcheances = false;
    async function dessinerEcheances() {
      const e = await Store.echeances(toutesEcheances);
      document.querySelector('[data-resume-echeances]').textContent =
        e.resume.enRetard + ' en retard · ' + e.resume.bientot + ' a prevoir · ' + e.resume.aJour + ' a jour';
      const liste = document.querySelector('[data-liste-echeances]');
      liste.innerHTML = e.echeances.map(function (p) {
        return '<tr>' +
          '<td><a class="tf-mono" href="vehicule.html?plaque=' + encodeURIComponent(p.vehicule) + '">' +
            Format.echapper(p.vehicule) + '</a></td>' +
          '<td><div>' + Format.echapper(p.libelle) + '</div><div class="tf-meta">' +
            Format.echapper(Format.intervalle(p)) + '</div></td>' +
          '<td class="tf-mono" style="font-size:13px;white-space:nowrap">' +
            (p.prochainKm ? Format.km(p.prochainKm) + '<br>' : '') +
            (p.prochaineDate ? Format.dateCourte(p.prochaineDate) : '') + '</td>' +
          '<td class="tf-meta">' + Format.echapper(Format.resteEcheance(p.echeance)) + '</td>' +
          '<td>' + tfPastille(Format.etatEcheance(p.echeance.etat)) + '</td>' +
          '<td class="text-end">' + (p.bonOuvert
            ? '<a class="tf-mono" style="font-size:13px" href="?bon=' + encodeURIComponent(p.bonOuvert) + '">' +
              Format.echapper(p.bonOuvert) + '</a>'
            : '<button type="button" class="tf-btn tf-btn-ghost sm" data-planifier="' + Format.echapper(p.id) +
              '">Planifier</button>') + '</td></tr>';
      }).join('') || '<tr><td colspan="6" class="tf-muted">Aucune echeance proche : la flotte est a jour.</td></tr>';
      liste.querySelectorAll('[data-planifier]').forEach(function (bouton) {
        bouton.addEventListener('click', async function () {
          const plan = e.echeances.find(function (p) { return p.id === bouton.dataset.planifier; });
          try {
            const bon = await Fenetres.nouveauBon({ plan: plan });
            if (bon) { selection = bon.id; await toutRedessiner(); }
          } catch (err) { tfNotifier(err.message); }
        });
      });
    }

    const periode = document.querySelector('[data-periode]');
    function choisirPeriode(preset) {
      const aujourdhui = new Date();
      let debut;
      if (preset === 'mois') debut = Format.aujourdhui(1 - aujourdhui.getDate());
      else if (preset === '12mois') debut = Format.aujourdhui(-365);
      else debut = aujourdhui.getFullYear() + '-01-01';
      periode.debut.value = debut;
      periode.fin.value = Format.aujourdhui();
      document.querySelectorAll('[data-preset]').forEach(function (b) {
        b.classList.toggle('active', b.dataset.preset === preset);
      });
    }

    async function dessinerCouts() {
      const c = await Store.coutsEntretien({ debut: periode.debut.value, fin: periode.fin.value });
      const tuiles = [
        ['Total', Format.montant(c.total.total), c.total.nombre + ' intervention(s)'],
        ['Pieces', Format.montant(c.total.pieces), ''],
        ['Main-d oeuvre', Format.montant(c.total.mainOeuvre), ''],
        ['Preventif / correctif', Format.montant(c.parCategorie.preventif.total) + ' / ' +
          Format.montant(c.parCategorie.correctif.total),
          c.parCategorie.preventif.nombre + ' / ' + c.parCategorie.correctif.nombre + ' bon(s)']
      ];
      document.querySelector('[data-totaux]').innerHTML = tuiles.map(function (t) {
        return '<div class="col-6 col-lg-3"><div class="tf-stat h-100" style="padding:16px;border-radius:14px;' +
          'background:var(--tf-bg)"><span class="tf-stat-label">' + t[0] + '</span>' +
          '<span class="tf-mono" style="font-size:' + (t[1].length > 14 ? '16' : '22') + 'px;font-weight:500">' +
          Format.echapper(t[1]) + '</span><span class="tf-stat-note">' + (Format.echapper(t[2]) || '&nbsp;') + '</span></div></div>';
      }).join('');
      document.querySelector('[data-couts-vehicules]').innerHTML = c.parVehicule.map(function (v) {
        return '<tr><td><a class="tf-mono" href="vehicule.html?plaque=' + encodeURIComponent(v.vehicule) + '">' +
            Format.echapper(v.vehicule) + '</a><div class="tf-meta">' + Format.echapper(v.modele) + '</div></td>' +
          '<td class="tf-mono text-end">' + v.nombre + '</td>' +
          '<td class="tf-mono text-end">' + Format.montant(v.pieces) + '</td>' +
          '<td class="tf-mono text-end">' + Format.montant(v.mainOeuvre) + '</td>' +
          '<td class="tf-mono text-end" style="font-weight:500">' + Format.montant(v.total) + '</td>' +
          '<td class="tf-mono text-end tf-muted">' + (v.coutParKm !== null
            ? v.coutParKm.toLocaleString('fr-CA', { minimumFractionDigits: 3, maximumFractionDigits: 3 }) + ' $'
            : '—') + '</td></tr>';
      }).join('') || '<tr><td colspan="6" class="tf-muted">Aucune intervention terminee sur la periode.</td></tr>';
      const maximum = Math.max.apply(null, c.parType.map(function (t) { return t.total; }).concat([1]));
      document.querySelector('[data-couts-types]').innerHTML = c.parType.map(function (t) {
        return '<div class="tf-bar-row"><span>' + Format.echapper(t.libelle) + ' <span class="tf-meta">(' + t.nombre +
          ')</span></span><div class="tf-bar"><span style="width:' + Math.max(2, Math.round(t.total / maximum * 100)) +
          '%"></span></div><span class="tf-mono">' + Format.montant(t.total) + '</span></div>';
      }).join('') || '<p class="tf-meta mb-0">Aucune donnee sur la periode.</p>';
    }

    async function toutRedessiner() {
      vehicules = await Store.vehicules();
      await Promise.all([dessinerBons(), indicateurs(), dessinerEcheances()]);
    }

    function signaler(e) { tfNotifier(e.message); }

    const montrerOnglet = tfOnglets(document.querySelector('.tf-tabs').parentElement, function (nom) {
      if (nom === 'couts') dessinerCouts().catch(signaler);
    });

    tfPuces('[data-filtre-bon]', 'filtreBon', function (valeur) {
      etat.statut = valeur;
      dessinerBons().catch(signaler);
    });
    document.querySelector('[data-filtre-vehicule]').addEventListener('change', function (e) {
      etat.vehicule = e.target.value;
      dessinerBons().catch(signaler);
    });
    let minuterie = null;
    document.querySelector('[data-recherche]').addEventListener('input', function (e) {
      clearTimeout(minuterie);
      minuterie = setTimeout(function () {
        etat.recherche = e.target.value.trim();
        dessinerBons().catch(signaler);
      }, 250);
    });
    document.querySelector('[data-echeances-toutes]').addEventListener('change', function (e) {
      toutesEcheances = e.target.checked;
      dessinerEcheances().catch(signaler);
    });
    periode.addEventListener('submit', function (e) {
      e.preventDefault();
      document.querySelectorAll('[data-preset]').forEach(function (b) { b.classList.remove('active'); });
      dessinerCouts().catch(signaler);
    });
    document.querySelectorAll('[data-preset]').forEach(function (b) {
      b.addEventListener('click', function () {
        choisirPeriode(b.dataset.preset);
        dessinerCouts().catch(signaler);
      });
    });
    choisirPeriode('annee');

    document.querySelector('[data-exporter]').addEventListener('click', async function (e) {
      const bouton = e.currentTarget;
      bouton.disabled = true;
      try { await Store.exporterBons(etat); } catch (err) { tfNotifier(err.message); } finally { bouton.disabled = false; }
    });

    async function nouveauBon(contexte) {
      const bon = await Fenetres.nouveauBon(Object.assign({ vehicules: vehicules }, contexte));
      if (bon) {
        selection = bon.id;
        etat.statut = 'ouverts';
        document.querySelectorAll('[data-filtre-bon]').forEach(function (b) {
          b.classList.toggle('active', b.dataset.filtreBon === 'ouverts');
        });
        montrerOnglet('bons');
        await toutRedessiner();
      }
    }
    document.querySelector('[data-nouveau-bon]').addEventListener('click', function () {
      nouveauBon({ vehicule: etat.vehicule }).catch(signaler);
    });

    vehicules = await Store.vehicules();
    document.querySelector('[data-filtre-vehicule]').innerHTML =
      tfOptionsVehicules(vehicules, '', 'Tous les vehicules');
    if (params.get('onglet')) montrerOnglet(params.get('onglet'));
    await Promise.all([dessinerBons(), indicateurs(), dessinerEcheances()]);

    // Liens entrants : ?nouveau=1&vehicule=QC-1 (fiche vehicule), ?nouveau=1&incident=I-3 (incidents).
    if (params.get('nouveau')) {
      const contexte = { vehicule: params.get('vehicule') || '' };
      if (params.get('incident')) {
        contexte.incident = await Store.incident(params.get('incident'));
        if (!contexte.incident) tfNotifier('Incident introuvable.');
      }
      history.replaceState(null, '', location.pathname);
      await nouveauBon(contexte);
    }
  }
});

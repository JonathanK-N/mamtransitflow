/* TransitFlow — ecrans administrateur
   Auteur original : Mamadou Barry
   Modifie par : Jonathan K-N — chaque methode "pageXxx" est en
   async/await parce que les donnees viennent de l API (voir store.js).
   Les noms des chauffeurs sont resolus avec un seul appel
   (Store.chauffeursParId) plutot qu une requete par ligne de tableau, les
   dates sont celles du jour reel, et les erreurs du serveur sont
   affichees a l utilisateur (tfNotifier). Les pages de la flotte et de
   l entretien sont dans admin-flotte.js. */

/* Avatar + nom court d un chauffeur (ou "Inconnu" s il a ete supprime). */
function tfCelluleChauffeur(c) {
  return '<span class="d-inline-flex align-items-center gap-2">' +
    '<span class="tf-avatar sm ' + Format.tonAvatar(c ? c.id : '') + '">' + Format.initiales(c) + '</span>' +
    Format.echapper(Format.nomCourt(c)) + '</span>';
}

/* Panneau "invitation envoyee" : message selon que le courriel est parti ou non, et lien a copier. */
function tfAfficherInvitation(panneau, chauffeur, lien, courrielEnvoye) {
  panneau.querySelector('[data-message-invitation]').innerHTML = courrielEnvoye
    ? 'Un courriel d invitation a ete envoye a <strong>' + Format.echapper(chauffeur.courriel) + '</strong>.'
    : 'L envoi de courriels n est pas configure (Parametres &gt; Courriel) : copiez ce lien et transmettez-le a ' +
      '<strong>' + Format.echapper(chauffeur.prenom) + '</strong> par texto ou par courriel.';
  const champ = panneau.querySelector('[data-lien-invitation]');
  champ.value = lien;
  const bouton = panneau.querySelector('[data-copier]');
  bouton.onclick = async function () {
    try { await navigator.clipboard.writeText(lien); } catch (e) { champ.select(); document.execCommand('copy'); }
    bouton.textContent = 'Lien copie';
    setTimeout(function () { bouton.textContent = 'Copier le lien'; }, 2000);
  };
}

/* Pastille de l etat d acces au portail d un chauffeur. */
function tfPastilleAcces(acces) {
  const table = {
    actif: ['Actif', 'ok'], invite: ['Invite', 'warn'], expire: ['Invitation expiree', 'danger'],
    desactive: ['Desactive', 'muted'], aucun: ['Pas d acces', 'muted']
  };
  const t = table[(acces || {}).etat] || table.aucun;
  return '<span class="tf-pill ' + t[1] + '">' + t[0] + '</span>';
}

const Admin = {
  /*
   * Point d entree, appele au chargement de chaque page admin/*.html :
   * verifie la session, affiche le nom dans la barre du haut, puis
   * devine quelle methode "pageXxx" appeler a partir de l attribut
   * data-page du <body> (ex. data-page="tableau-de-bord" -> pageTableauDeBord).
   */
  async demarrer() {
    const session = Auth.exiger('admin', '../');
    if (!session) return;
    monterBarreUtilisateur(session, '../');
    // Module desactive : la navigation a remplace la page par un message.
    try { this.entreprise = await window.tfNavigationPrete; } catch (e) { return; }
    const page = document.body.dataset.page;
    const methode = 'page' + page.charAt(0).toUpperCase() + page.slice(1).replace(/-(.)/g, function (m, c) {
      return c.toUpperCase();
    });
    if (typeof this[methode] === 'function') await this[methode](session);
    document.body.dataset.pret = '1';
  },

  /* Tableau de bord */
  async pageTableauDeBord(session) {
    // Les appels ne dependent pas les uns des autres : Promise.all()
    // les lance tous en meme temps.
    const [k, trajetsEnCours, incidentsOuverts, chauffeurs, entretien] = await Promise.all([
      Store.indicateurs(),
      Store.trajets({ statut: 'en-cours' }),
      Store.incidents({ statut: 'ouvert' }),
      Store.chauffeurs(),
      Store.echeances()
    ]);
    const parId = {};
    chauffeurs.forEach(function (c) { parId[c.id] = c; });

    const prenom = session.nom.split(' ')[0];
    document.querySelector('[data-salutation]').textContent = 'Bonjour ' + prenom;
    document.querySelector('[data-sous-titre]').textContent =
      Format.dateLongue(Format.aujourdhui()) + ' · ' + k.trajetsEnCours + ' trajet' +
      (k.trajetsEnCours > 1 ? 's' : '') + ' actif' + (k.trajetsEnCours > 1 ? 's' : '');

    const valeurs = {
      'chauffeurs-actifs': k.chauffeursActifs,
      'trajets-en-cours': k.trajetsEnCours,
      'incidents-ouverts': k.incidentsOuverts,
      'permis-a-expirer': k.permisAExpirer
    };
    Object.keys(valeurs).forEach(function (cle) {
      const el = document.querySelector('[data-kpi="' + cle + '"]');
      if (el) el.textContent = valeurs[cle];
    });
    document.querySelector('[data-kpi-note="trajets"]').textContent = 'sur ' + k.trajetsDuJour + ' aujourd hui';

    document.querySelector('[data-trajets-en-cours]').innerHTML = trajetsEnCours.map(function (t) {
      const p = Format.progression(t);
      return '<tr>' +
        '<td>' + tfCelluleChauffeur(parId[t.chauffeurId]) + '</td>' +
        '<td class="tf-mono">' + Format.echapper(t.plaque) + '</td>' +
        '<td>' + Format.echapper(t.depart + ' → ' + t.arrivee) + '</td>' +
        '<td><div class="tf-progress sm"><span class="' + (p > 80 ? 'near' : '') +
          '" style="width:' + p + '%"></span></div>' +
          '<div class="tf-mono mt-1" style="font-size:11px;color:var(--tf-muted)">' + p + '% · ' +
          Format.dureeDepuis(t.debut) + '</div></td>' +
        '<td class="text-end"><a class="tf-mono" style="font-size:12.5px" href="trajet.html?id=' +
          encodeURIComponent(t.id) + '">Detail</a></td>' +
        '</tr>';
    }).join('') || '<tr><td colspan="5" class="tf-muted">Aucun trajet en cours.</td></tr>';

    const morceaux = incidentsOuverts.map(function (i) {
      return '<div class="tf-alert high"><div class="tf-alert-bar"></div><div>' +
        '<div style="font-size:13.5px;font-weight:500">Incident ' +
        Format.echapper(Format.typeIncident(i.type).texte.toLowerCase()) + ' non traite</div>' +
        '<div class="tf-meta mt-1">' + Format.echapper(Format.nomCourt(parId[i.chauffeurId]) + ' — ' + i.lieu) +
        ' · ' + Format.echapper(i.heure) + '</div></div></div>';
    });
    chauffeurs.filter(function (c) {
      return Format.permisBientotExpire(c.permisExpiration);
    }).forEach(function (c) {
      morceaux.push('<div class="tf-alert"><div class="tf-alert-bar"></div><div>' +
        '<div style="font-size:13.5px;font-weight:500">Permis expirant</div>' +
        '<div class="tf-meta mt-1">' + Format.echapper(Format.nomCourt(c)) + ' — ' +
        Format.dateLongue(c.permisExpiration) + '</div></div></div>');
    });
    // Entretien : echeances depassees ou proches (les plus urgentes d abord, voir /api/entretien/echeances).
    entretien.echeances.slice(0, 5).forEach(function (p) {
      const retard = p.echeance.etat === 'en-retard';
      morceaux.push('<a class="tf-alert' + (retard ? ' high' : '') + '" style="color:inherit" href="' +
        (p.bonOuvert ? 'entretiens.html?bon=' + encodeURIComponent(p.bonOuvert)
                     : 'vehicule.html?plaque=' + encodeURIComponent(p.vehicule)) + '">' +
        '<div class="tf-alert-bar"></div><div>' +
        '<div style="font-size:13.5px;font-weight:500">' + (retard ? 'Entretien en retard' : 'Entretien a prevoir') +
        ' — ' + Format.echapper(p.vehicule) + '</div>' +
        '<div class="tf-meta mt-1">' + Format.echapper(p.libelle) + ' · ' +
        Format.echapper(Format.resteEcheance(p.echeance)) +
        (p.bonOuvert ? ' · ' + Format.echapper(p.bonOuvert) + ' planifie' : '') + '</div></div></a>');
    });
    if (entretien.echeances.length > 5) {
      morceaux.push('<a class="tf-meta" href="entretiens.html?onglet=echeances">+ ' +
        (entretien.echeances.length - 5) + ' autre(s) echeance(s) d entretien</a>');
    }
    if (k.vehiculesEnMaintenance) {
      morceaux.push('<a class="tf-alert" style="color:inherit" href="vehicules.html"><div class="tf-alert-bar"></div><div>' +
        '<div style="font-size:13.5px;font-weight:500">' + k.vehiculesEnMaintenance + ' vehicule' +
        (k.vehiculesEnMaintenance > 1 ? 's' : '') + ' a l atelier</div>' +
        '<div class="tf-meta mt-1">' + k.vehiculesDisponibles + ' disponible' +
        (k.vehiculesDisponibles > 1 ? 's' : '') + ' pour les trajets</div></div></a>');
    }

    document.querySelector('[data-alertes]').innerHTML = morceaux.join('') ||
      '<div class="tf-meta">Aucune alerte en cours.</div>';
  },

  /* Liste des chauffeurs */
  pageChauffeurs() {
    // "etat" garde en memoire les filtres actifs (recherche + statut).
    // A chaque changement, dessiner() redemande la liste filtree a l API.
    const etat = { recherche: '', statut: 'tous' };
    const corps = document.querySelector('[data-liste-chauffeurs]');
    const compteur = document.querySelector('[data-compteur]');
    let derniereDemande = 0;

    async function dessiner() {
      // Ignore les reponses arrivees dans le desordre pendant la saisie.
      const numero = ++derniereDemande;
      const [liste, tous] = await Promise.all([Store.chauffeurs(etat), Store.chauffeurs()]);
      if (numero !== derniereDemande) return;
      compteur.textContent = liste.length + ' resultat' + (liste.length > 1 ? 's' : '') +
        ' sur ' + tous.length;
      corps.innerHTML = liste.map(function (c) {
        const s = Format.statutChauffeur(c.statut);
        const bientot = Format.permisBientotExpire(c.permisExpiration);
        return '<tr>' +
          '<td><span class="d-inline-flex align-items-center gap-3">' +
            '<span class="tf-avatar ' + Format.tonAvatar(c.id) + '">' + Format.initiales(c) + '</span>' +
            '<span><span class="d-block" style="font-weight:500">' +
              Format.echapper(Format.nomComplet(c)) + '</span>' +
            '<span class="tf-meta">' + Format.echapper(c.age) + ' ans</span></span></span></td>' +
          '<td class="tf-mono">' + Format.echapper(c.telephone) + '</td>' +
          '<td class="tf-muted">' + Format.echapper(c.courriel) + '</td>' +
          '<td class="tf-mono ' + (bientot ? 'tf-danger' : '') + '">' +
            Format.echapper(c.permisExpiration) + '</td>' +
          '<td><span class="tf-pill ' + s.classe + '">' + s.texte + '</span></td>' +
          '<td>' + tfPastilleAcces(c.acces) + '</td>' +
          '<td class="text-end"><a href="chauffeur.html?id=' + encodeURIComponent(c.id) +
            '" style="font-size:13px">Ouvrir</a></td>' +
          '</tr>';
      }).join('') || '<tr><td colspan="7" class="tf-muted">Aucun chauffeur ne correspond.</td></tr>';
    }

    function redessiner() {
      dessiner().catch(function (e) { tfNotifier(e.message); });
    }

    document.querySelector('[data-recherche]').addEventListener('input', function (e) {
      etat.recherche = e.target.value;
      redessiner();
    });
    document.querySelectorAll('[data-filtre-statut]').forEach(function (bouton) {
      bouton.addEventListener('click', function () {
        document.querySelectorAll('[data-filtre-statut]').forEach(function (b) {
          b.classList.remove('active');
        });
        bouton.classList.add('active');
        etat.statut = bouton.dataset.filtreStatut;
        redessiner();
      });
    });
    return dessiner();
  },

  /* Fiche chauffeur */
  /* Carte "Acces au portail" de la fiche chauffeur : inviter, renvoyer, suspendre, retablir. */
  dessinerAcces(c) {
    const carte = document.querySelector('[data-acces]');
    const acces = c.acces || { etat: 'aucun' };
    const date = function (iso) { return Format.dateLongue(iso); };
    const textes = {
      aucun: 'Ce chauffeur n a pas encore acces a son espace. Invitez-le : il recevra un courriel pour choisir ' +
        'son mot de passe.',
      invite: 'Invitation envoyee le ' + (acces.envoyeeLe ? date(acces.envoyeeLe) : '') + ', en attente. Le lien ' +
        'expire le ' + (acces.expireLe ? date(acces.expireLe) : '') + '.',
      expire: 'L invitation a expire sans etre utilisee. Renvoyez-en une nouvelle.',
      actif: 'Le chauffeur se connecte avec ' + c.courriel + '. En cas d oubli, il utilise « Mot de passe oublie ».',
      desactive: 'Acces suspendu : le chauffeur ne peut plus se connecter.'
    };
    carte.querySelector('[data-acces-pastille]').innerHTML = tfPastilleAcces(acces);
    carte.querySelector('[data-acces-texte]').textContent = textes[acces.etat] || '';
    const boutons = {
      aucun: [['inviter', 'Inviter le chauffeur', 'tf-btn-primary']],
      invite: [['inviter', 'Renvoyer l invitation', 'tf-btn-ghost'], ['annuler', 'Annuler l invitation', 'tf-btn-danger']],
      expire: [['inviter', 'Renvoyer l invitation', 'tf-btn-primary']],
      actif: [['suspendre', 'Suspendre l acces', 'tf-btn-danger']],
      desactive: [['retablir', 'Retablir l acces', 'tf-btn-primary']]
    }[acces.etat] || [];
    const zone = carte.querySelector('[data-acces-actions]');
    zone.innerHTML = boutons.map(function (b) {
      return '<button type="button" class="tf-btn ' + b[2] + '" style="height:38px;font-size:13.5px" data-action-acces="' +
        b[0] + '">' + b[1] + '</button>';
    }).join('');
    const moi = this;
    zone.querySelectorAll('[data-action-acces]').forEach(function (bouton) {
      bouton.addEventListener('click', async function () {
        const action = bouton.dataset.actionAcces;
        if (action === 'suspendre' && !window.confirm('Suspendre l acces de ' + Format.nomComplet(c) +
          ' ? Il sera deconnecte de tous ses appareils.')) return;
        bouton.disabled = true;
        try {
          let fiche;
          if (action === 'inviter') {
            const r = await Store.inviterChauffeur(c.id);
            fiche = r.chauffeur;
            carte.querySelector('[data-acces-lien]').classList.remove('tf-hidden');
            carte.querySelector('[data-message-invitation]').classList.remove('tf-hidden');
            tfAfficherInvitation(carte, fiche, r.lien, r.courrielEnvoye);
            tfNotifier(r.courrielEnvoye ? 'Invitation envoyee a ' + fiche.courriel + '.' : 'Lien d invitation cree.', 'succes');
          } else if (action === 'annuler') {
            fiche = await Store.annulerInvitation(c.id);
            carte.querySelector('[data-acces-lien]').classList.add('tf-hidden');
            carte.querySelector('[data-message-invitation]').classList.add('tf-hidden');
          } else {
            fiche = await Store.accesChauffeur(c.id, action === 'retablir');
          }
          moi.dessinerAcces(fiche);
        } catch (e) {
          tfNotifier(e.message);
          bouton.disabled = false;
        }
      });
    });
  },

  async pageChauffeur() {
    const id = new URLSearchParams(location.search).get('id');
    const c = await Store.chauffeur(id);
    if (!c) { document.querySelector('[data-fiche]').innerHTML =
      '<p class="tf-muted">Chauffeur introuvable.</p>'; return; }

    const s = Format.statutChauffeur(c.statut);
    // 3 appels independants lances en parallele.
    const [trajets, incidents, vehicules] = await Promise.all([
      Store.trajets({ chauffeurId: c.id }),
      Store.incidents({ chauffeurId: c.id }),
      Store.vehicules()
    ]);

    document.querySelector('[data-fil]').textContent = Format.nomComplet(c);
    document.querySelector('[data-avatar]').className = 'tf-avatar lg ' + Format.tonAvatar(c.id);
    document.querySelector('[data-avatar]').textContent = Format.initiales(c);
    document.querySelector('[data-nom]').textContent = Format.nomComplet(c);
    document.querySelector('[data-statut]').className = 'tf-pill ' + s.classe;
    document.querySelector('[data-statut]').textContent = s.texte;
    document.querySelector('[data-contact]').textContent =
      c.age + ' ans · ' + c.telephone + ' · ' + c.courriel;
    document.querySelector('[data-total-trajets]').textContent = trajets.length;
    document.querySelector('[data-total-incidents]').textContent = incidents.length;
    document.querySelector('[data-adresse]').textContent = c.adresse;
    document.querySelector('[data-permis]').textContent = c.permisNumero;
    document.querySelector('[data-permis-expiration]').textContent =
      'Valide jusqu au ' + Format.dateLongue(c.permisExpiration);
    document.querySelector('[data-cree-le]').textContent = Format.dateLongue(c.creeLe);
    document.querySelector('[data-plaque]').textContent = c.plaqueHabituelle || '—';
    this.dessinerAcces(c);
    const vehicule = vehicules.find(function (v) { return v.plaque === c.plaqueHabituelle; });
    document.querySelector('[data-vehicule]').textContent = vehicule ? vehicule.modele : '—';
    document.querySelector('[data-nb-incidents]').textContent = '(' + incidents.length + ')';

    document.querySelector('[data-historique]').innerHTML = trajets.map(function (t) {
      const st = Format.statutTrajet(t.statut);
      return '<tr' + (t.statut === 'en-cours' ? ' class="is-active"' : '') + '>' +
        '<td>' + Format.dateCourte(t.debut) + '</td>' +
        '<td style="font-weight:' + (t.statut === 'en-cours' ? '500' : '400') + '">' +
          Format.echapper(t.depart + ' → ' + t.arrivee) + '</td>' +
        '<td class="tf-mono tf-muted">' + Format.duree(t.debut, t.fin) + '</td>' +
        '<td><span class="tf-pill ' + st.classe + '">' + st.texte + '</span></td>' +
        '<td class="text-end"><a href="trajet.html?id=' + encodeURIComponent(t.id) +
          '" style="font-size:13px">Detail</a></td>' +
        '</tr>';
    }).join('') || '<tr><td colspan="5" class="tf-muted">Aucun trajet.</td></tr>';

    document.querySelector('[data-incidents-chauffeur]').innerHTML = incidents.map(function (i) {
      const st = Format.statutIncident(i.statut);
      const ty = Format.typeIncident(i.type);
      return '<tr><td class="tf-mono">' + Format.jourHeure(i.date + 'T' + i.heure) + '</td>' +
        '<td><span class="tf-pill ' + ty.classe + '">' + ty.texte + '</span></td>' +
        '<td>' + Format.echapper(i.titre) + '</td>' +
        '<td>' + Format.echapper(i.lieu) + '</td>' +
        '<td><span class="tf-pill ' + st.classe + '">' + st.texte + '</span></td></tr>';
    }).join('') || '<tr><td colspan="5" class="tf-muted">Aucun incident.</td></tr>';

    document.querySelectorAll('[data-onglet]').forEach(function (onglet) {
      onglet.addEventListener('click', function () {
        document.querySelectorAll('[data-onglet]').forEach(function (o) {
          o.classList.remove('active');
          o.style.borderBottom = '2.5px solid transparent';
          o.style.color = 'var(--tf-muted)';
        });
        onglet.classList.add('active');
        onglet.style.borderBottom = '2.5px solid var(--tf-accent)';
        onglet.style.color = 'var(--tf-ink)';
        document.querySelectorAll('[data-volet]').forEach(function (v) {
          v.classList.toggle('tf-hidden', v.dataset.volet !== onglet.dataset.onglet);
        });
      });
    });
  },

  /* Creation d un chauffeur et de son compte de connexion */
  async pageChauffeurNouveau() {
    const formulaire = document.querySelector('[data-formulaire]');
    const choixPlaque = formulaire.querySelector('[name=plaque]');

    // Les plaques proposees sont celles de la flotte reelle (voir vehicules.html).
    const vehicules = await Store.vehicules();
    choixPlaque.innerHTML = '<option value="">Aucun vehicule</option>' + vehicules.map(function (v) {
      return '<option value="' + Format.echapper(v.plaque) + '">' +
        Format.echapper(v.plaque + ' — ' + v.modele) + '</option>';
    }).join('');

    formulaire.addEventListener('submit', function (e) {
      e.preventDefault();
      tfEnvoyer(formulaire, async function () {
        const d = new FormData(formulaire);
        const resultat = await Store.ajouterChauffeur({
          prenom: d.get('prenom').trim(),
          nom: d.get('nom').trim(),
          age: Number(d.get('age')),
          telephone: d.get('telephone').trim(),
          courriel: d.get('courriel').trim(),
          adresse: d.get('adresse').trim(),
          permisNumero: d.get('permisNumero').trim(),
          permisExpiration: d.get('permisExpiration'),
          statut: d.get('statut'),
          plaqueHabituelle: d.get('plaque') || null,
          inviter: d.get('inviter') === 'on'
        });
        const lien = 'chauffeur.html?id=' + encodeURIComponent(resultat.chauffeur.id);
        if (!resultat.invitation) {
          window.location.href = lien;
          return;
        }
        const panneau = document.querySelector('[data-compte-cree]');
        tfAfficherInvitation(panneau, resultat.chauffeur, resultat.invitation.lien, resultat.invitation.courrielEnvoye);
        panneau.querySelector('[data-lien-fiche]').href = lien;
        formulaire.classList.add('tf-hidden');
        panneau.classList.remove('tf-hidden');
      });
    });
  },

  /* Vehicules, fiche vehicule et entretien : voir admin-flotte.js */

  /* Liste des trajets */
  pageTrajets() {
    const etat = { statut: 'tous' };
    const corps = document.querySelector('[data-liste-trajets]');

    async function dessiner() {
      const [trajets, parId] = await Promise.all([Store.trajets(etat), Store.chauffeursParId()]);
      corps.innerHTML = trajets.map(function (t) {
        const st = Format.statutTrajet(t.statut);
        return '<tr>' +
          '<td class="tf-mono">' + Format.echapper(t.id) + '</td>' +
          '<td>' + Format.dateCourte(t.debut) + '</td>' +
          '<td>' + tfCelluleChauffeur(parId[t.chauffeurId]) + '</td>' +
          '<td>' + Format.echapper(t.depart + ' → ' + t.arrivee) + '</td>' +
          '<td class="tf-mono">' + Format.echapper(t.plaque) + '</td>' +
          '<td class="tf-mono tf-muted">' + Format.duree(t.debut, t.fin) + '</td>' +
          '<td><span class="tf-pill ' + st.classe + '">' + st.texte + '</span></td>' +
          '<td class="text-end"><a href="trajet.html?id=' + encodeURIComponent(t.id) +
            '" style="font-size:13px">Detail</a></td>' +
          '</tr>';
      }).join('') || '<tr><td colspan="8" class="tf-muted">Aucun trajet.</td></tr>';
    }

    document.querySelectorAll('[data-filtre-trajet]').forEach(function (b) {
      b.addEventListener('click', function () {
        document.querySelectorAll('[data-filtre-trajet]').forEach(function (x) {
          x.classList.remove('active');
        });
        b.classList.add('active');
        etat.statut = b.dataset.filtreTrajet;
        dessiner().catch(function (e) { tfNotifier(e.message); });
      });
    });
    return dessiner();
  },

  /* Detail d un trajet */
  async pageTrajet() {
    const id = new URLSearchParams(location.search).get('id');
    const t = await Store.trajet(id);
    if (!t) { document.querySelector('[data-contenu]').innerHTML =
      '<p class="tf-muted">Trajet introuvable.</p>'; return; }

    const [c, tousIncidents] = await Promise.all([Store.chauffeur(t.chauffeurId), Store.incidents()]);
    const st = Format.statutTrajet(t.statut);
    const incidents = tousIncidents.filter(function (i) { return i.trajetId === t.id; });
    const p = Format.progression(t);

    document.querySelector('[data-fil]').textContent = t.id;
    document.querySelector('[data-titre]').textContent = t.depart + ' → ' + t.arrivee;
    const pastille = document.querySelector('[data-statut]');
    pastille.className = 'tf-pill ' + st.classe;
    pastille.textContent = st.texte;
    document.querySelector('[data-avatar]').className = 'tf-avatar ' + Format.tonAvatar(c ? c.id : '');
    document.querySelector('[data-avatar]').textContent = Format.initiales(c);
    document.querySelector('[data-chauffeur]').textContent = Format.nomComplet(c);
    document.querySelector('[data-telephone]').textContent = c ? c.telephone : '—';
    document.querySelector('[data-plaque]').textContent = t.plaque;
    document.querySelector('[data-duree]').textContent = t.statut === 'termine'
      ? Format.duree(t.debut, t.fin) : Format.dureeDepuis(t.debut);
    document.querySelector('[data-nb-arrets]').textContent = t.arrets.length;
    document.querySelector('[data-nb-incidents]').textContent = incidents.length;
    document.querySelector('[data-nb-incidents]').classList.toggle('tf-danger', incidents.length > 0);
    document.querySelector('[data-progression]').style.width = p + '%';
    document.querySelector('[data-progression-note]').textContent =
      p + '% · arrivee ' + (t.statut === 'termine' ? 'a ' : 'estimee ') + Format.heure(t.finPrevue);

    // L administrateur peut cloturer un trajet reste ouvert (oubli du chauffeur, panne...).
    if (t.statut === 'en-cours') {
      const bouton = document.createElement('button');
      bouton.type = 'button';
      bouton.className = 'tf-btn tf-btn-ghost';
      bouton.style.cssText = 'height:34px;padding:0 14px;font-size:13px;margin-left:12px';
      bouton.textContent = 'Cloturer le trajet';
      bouton.addEventListener('click', async function () {
        if (!window.confirm('Cloturer le trajet ' + t.id + ' maintenant ?')) return;
        try {
          await Store.terminerTrajet(t.id);
          window.location.reload();
        } catch (e) { tfNotifier(e.message); }
      });
      pastille.insertAdjacentElement('afterend', bouton);
    }

    const etapes = [];
    etapes.push({ heure: Format.heure(t.debut), titre: 'Depart — ' + t.depart,
      note: t.departAdresse || t.depart, classe: 'done' });
    t.arrets.forEach(function (a) {
      etapes.push({ heure: a.heure, titre: 'Arret — ' + a.lieu, note: a.note || 'Arret enregistre', classe: '' });
    });
    incidents.forEach(function (i) {
      const ty = Format.typeIncident(i.type);
      etapes.push({ heure: i.heure, classe: 'alert', incident: i, type: ty });
    });
    etapes.sort(function (a, b) { return a.heure.localeCompare(b.heure); });
    etapes.push({ heure: Format.heure(t.finPrevue), titre: 'Arrivee — ' + t.arrivee,
      note: t.statut === 'termine' ? 'Trajet termine' : 'Heure prevue',
      classe: t.statut === 'termine' ? 'done' : 'planned', futur: t.statut !== 'termine' });

    // Carte du parcours GPS (admin-carte.js), chargee sans bloquer le reste de la page.
    if (typeof tfCarteTrajet === 'function') {
      tfCarteTrajet(t).catch(function (e) { tfNotifier(e.message); });
    }

    document.querySelector('[data-deroulement]').innerHTML = etapes.map(function (e, index) {
      const dernier = index === etapes.length - 1 ? ' last' : '';
      let corps;
      if (e.incident) {
        const st2 = Format.statutIncident(e.incident.statut);
        corps = '<div class="tf-tl-alert">' +
          '<div class="d-flex align-items-center gap-2 mb-1">' +
          '<span class="tf-pill danger" style="font-size:11.5px">' + e.type.texte + '</span>' +
          '<span class="tf-meta">' + st2.texte.toLowerCase() + '</span></div>' +
          '<div style="font-size:14.5px;font-weight:500">' + Format.echapper(e.incident.titre) + '</div>' +
          '<div class="tf-tl-note">' + Format.echapper(e.incident.lieu) + ' — ' +
          Format.echapper(e.incident.description) + '</div></div>';
      } else {
        corps = '<div class="tf-tl-title"' + (e.futur ? ' style="color:var(--tf-muted)"' : '') + '>' +
          Format.echapper(e.titre) + '</div>' +
          '<div class="tf-tl-note">' + Format.echapper(e.note) + '</div>';
      }
      return '<div class="tf-tl-time' + (e.incident ? ' tf-danger' : '') + '">' + Format.echapper(e.heure) +
        '</div><div class="tf-tl-body ' + e.classe + dernier + '">' + corps + '</div>';
    }).join('');
  },

  /* Liste et detail des incidents */
  pageIncidents() {
    const etat = { type: 'tous', statut: 'tous' };
    const corps = document.querySelector('[data-liste-incidents]');
    let selection = null; // incident actuellement affiche dans le panneau de droite
    let parId = {};       // chauffeurs indexes par id, recharges a chaque dessin

    // Affiche le detail d un incident dans le panneau de droite.
    async function dessinerDetail(i) {
      const panneau = document.querySelector('[data-detail]');
      if (!i) { panneau.innerHTML = '<p class="tf-muted">Choisir un incident dans la liste.</p>'; return; }
      const c = parId[i.chauffeurId];
      const trajet = i.trajetId ? await Store.trajet(i.trajetId) : null;
      const st = Format.statutIncident(i.statut);
      const ty = Format.typeIncident(i.type);
      panneau.innerHTML =
        '<div class="d-flex align-items-center gap-2">' +
          '<span class="tf-pill ' + st.classe + '">' + st.texte + '</span>' +
          '<span class="tf-pill ' + ty.classe + '">' + ty.texte + '</span>' +
          '<span class="tf-mono ms-auto tf-meta">' + Format.jourHeure(i.date + 'T' + i.heure) + '</span>' +
        '</div>' +
        '<h2 class="tf-h2" style="font-size:20px">' + Format.echapper(i.titre) + '</h2>' +
        '<div class="d-flex align-items-center gap-3 p-3" style="border-radius:12px;background:var(--tf-bg)">' +
          '<span class="tf-avatar ' + Format.tonAvatar(c ? c.id : '') + '">' + Format.initiales(c) + '</span>' +
          '<span><span class="d-block" style="font-weight:500">' + Format.echapper(Format.nomComplet(c)) +
          '</span><span class="tf-meta">' + (i.trajetId
            ? 'Trajet ' + Format.echapper(i.trajetId) + ' · ' + Format.echapper(trajet ? trajet.plaque : '—')
            : 'Hors trajet') +
          '</span></span></div>' +
        '<div><div class="tf-meta mb-1">Description</div>' +
          '<p class="mb-0" style="font-size:14.5px;line-height:1.6">' +
          Format.echapper(i.description) + '</p></div>' +
        '<div class="row g-3"><div class="col-6"><div class="tf-meta mb-1">Lieu</div>' +
          '<div style="font-size:14.5px">' + Format.echapper(i.lieu) + '</div></div>' +
          '<div class="col-6"><div class="tf-meta mb-1">Signale a</div>' +
          '<div class="tf-mono" style="font-size:14.5px">' + Format.echapper(i.heure) + '</div></div></div>' +
        '<div class="d-flex gap-3 pt-3" style="border-top:1px solid var(--tf-line)">' +
          (c ? '<a class="tf-btn tf-btn-ghost flex-fill" href="tel:' + Format.echapper(c.telephone) +
            '">Contacter</a>' : '') +
          (i.statut === 'ouvert'
            ? '<button type="button" class="tf-btn tf-btn-dark flex-fill" data-traiter>Marquer comme traite</button>'
            : '<span class="tf-btn tf-btn-ghost flex-fill" style="cursor:default">Deja traite</span>') +
        '</div>' +
        // Un incident technique peut ouvrir un bon de travail (voir entretiens.html).
        (i.type === 'technique'
          ? (i.bonTravailId
            ? '<a class="tf-btn tf-btn-ghost" href="entretiens.html?bon=' + encodeURIComponent(i.bonTravailId) +
              '">Voir le bon de travail ' + Format.echapper(i.bonTravailId) + '</a>'
            : (i.statut === 'ouvert'
              ? '<a class="tf-btn tf-btn-primary" href="entretiens.html?nouveau=1&incident=' +
                encodeURIComponent(i.id) + '">Creer un bon de travail</a>' : ''))
          : '');
      const bouton = panneau.querySelector('[data-traiter]');
      if (bouton) bouton.addEventListener('click', async function () {
        try {
          selection = await Store.traiterIncident(i.id);
          await dessiner();
        } catch (e) { tfNotifier(e.message); }
      });
    }

    // Redessine la liste complete (au chargement, apres un filtre, un clic
    // sur une ligne, ou apres avoir marque un incident traite).
    async function dessiner() {
      const [liste, tous, chauffeurs] = await Promise.all([
        Store.incidents(etat), Store.incidents(), Store.chauffeursParId()
      ]);
      parId = chauffeurs;
      if (!selection || !liste.some(function (i) { return i.id === selection.id; })) {
        selection = liste[0] || null;
      }
      const ouverts = tous.filter(function (i) { return i.statut === 'ouvert'; }).length;
      document.querySelector('[data-resume]').textContent =
        ouverts + ' ouvert' + (ouverts > 1 ? 's' : '') + ' · ' + (tous.length - ouverts) + ' traite' +
        (tous.length - ouverts > 1 ? 's' : '');
      corps.innerHTML = liste.map(function (i) {
        const st = Format.statutIncident(i.statut);
        const ty = Format.typeIncident(i.type);
        const actif = selection && selection.id === i.id;
        return '<tr data-ligne="' + Format.echapper(i.id) + '" style="cursor:pointer"' +
          (actif ? ' class="is-active is-open"' : '') + '>' +
          '<td class="tf-mono" style="font-size:13px">' + Format.jourHeure(i.date + 'T' + i.heure) + '</td>' +
          '<td><span class="tf-pill ' + ty.classe + '">' + ty.texte + '</span></td>' +
          '<td>' + Format.echapper(Format.nomCourt(parId[i.chauffeurId])) + '</td>' +
          '<td>' + Format.echapper(i.lieu) + '</td>' +
          '<td><span class="tf-pill ' + st.classe + '">' + st.texte + '</span></td>' +
          '</tr>';
      }).join('') || '<tr><td colspan="5" class="tf-muted">Aucun incident.</td></tr>';

      corps.querySelectorAll('[data-ligne]').forEach(function (ligne) {
        ligne.addEventListener('click', function () {
          selection = liste.find(function (i) { return i.id === ligne.dataset.ligne; }) || null;
          dessiner().catch(function (e) { tfNotifier(e.message); });
        });
      });
      await dessinerDetail(selection);
    }

    document.querySelectorAll('[data-filtre-incident]').forEach(function (b) {
      b.addEventListener('click', function () {
        document.querySelectorAll('[data-filtre-incident]').forEach(function (x) {
          x.classList.remove('active');
        });
        b.classList.add('active');
        const v = b.dataset.filtreIncident;
        etat.type = (v === 'technique' || v === 'route') ? v : 'tous';
        etat.statut = (v === 'ouvert') ? 'ouvert' : 'tous';
        dessiner().catch(function (e) { tfNotifier(e.message); });
      });
    });
    return dessiner();
  }
};

// Admin.demarrer() est asynchrone : une erreur (ex. serveur injoignable)
// est affichee a l utilisateur plutot que de disparaitre dans la console.
document.addEventListener('DOMContentLoaded', function () {
  Admin.demarrer().catch(function (e) {
    if (e && e.message === 'page-fermee') return;
    console.error('TransitFlow admin :', e);
    tfNotifier(e.message);
  });
});

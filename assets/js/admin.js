/* TransitFlow — ecrans administrateur
   Auteur : Mamadou Barry */

const Admin = {
  demarrer() {
    const session = Auth.exiger('admin', '../');
    if (!session) return;
    monterBarreUtilisateur(session, '../');
    const page = document.body.dataset.page;
    const methode = 'page' + page.charAt(0).toUpperCase() + page.slice(1).replace(/-(.)/g, function (m, c) {
      return c.toUpperCase();
    });
    if (typeof this[methode] === 'function') this[methode](session);
  },

  /* Tableau de bord */
  pageTableauDeBord(session) {
    const k = Store.indicateurs();
    const prenom = session.nom.split(' ')[0];
    document.querySelector('[data-salutation]').textContent = 'Bonjour ' + prenom;
    document.querySelector('[data-sous-titre]').textContent =
      Format.dateLongue('2026-09-12') + ' · ' + k.trajetsEnCours + ' trajets actifs';

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

    const corps = document.querySelector('[data-trajets-en-cours]');
    corps.innerHTML = Store.trajets({ statut: 'en-cours' }).map(function (t) {
      const c = Store.chauffeur(t.chauffeurId);
      const p = Format.progression(t);
      return '<tr>' +
        '<td><span class="d-inline-flex align-items-center gap-2">' +
          '<span class="tf-avatar sm ' + Format.tonAvatar(c.id) + '">' + Format.initiales(c) + '</span>' +
          Format.echapper(Format.nomCourt(c)) + '</span></td>' +
        '<td class="tf-mono">' + Format.echapper(t.plaque) + '</td>' +
        '<td>' + Format.echapper(t.depart + ' → ' + t.arrivee) + '</td>' +
        '<td><div class="tf-progress sm"><span class="' + (p > 80 ? 'near' : '') +
          '" style="width:' + p + '%"></span></div>' +
          '<div class="tf-mono mt-1" style="font-size:11px;color:var(--tf-muted)">' + p + '% · ' +
          Format.dureeDepuis(t.debut) + '</div></td>' +
        '<td class="text-end"><a class="tf-mono" style="font-size:12.5px" href="trajet.html?id=' +
          encodeURIComponent(t.id) + '">Detail</a></td>' +
        '</tr>';
    }).join('');

    const alertes = document.querySelector('[data-alertes]');
    const morceaux = [];
    Store.incidents({ statut: 'ouvert' }).forEach(function (i) {
      const c = Store.chauffeur(i.chauffeurId);
      morceaux.push('<div class="tf-alert high"><div class="tf-alert-bar"></div><div>' +
        '<div style="font-size:13.5px;font-weight:500">Incident ' +
        Format.echapper(Format.typeIncident(i.type).texte.toLowerCase()) + ' non traite</div>' +
        '<div class="tf-meta mt-1">' + Format.echapper(Format.nomCourt(c) + ' — ' + i.lieu) +
        ' · ' + Format.echapper(i.heure) + '</div></div></div>');
    });
    Store.chauffeurs().filter(function (c) {
      return new Date(c.permisExpiration) < new Date('2026-11-11');
    }).forEach(function (c) {
      morceaux.push('<div class="tf-alert"><div class="tf-alert-bar"></div><div>' +
        '<div style="font-size:13.5px;font-weight:500">Permis expirant</div>' +
        '<div class="tf-meta mt-1">' + Format.echapper(Format.nomCourt(c)) + ' — ' +
        Format.dateLongue(c.permisExpiration) + '</div></div></div>');
    });
    alertes.innerHTML = morceaux.join('') ||
      '<div class="tf-meta">Aucune alerte en cours.</div>';
  },

  /* Liste des chauffeurs */
  pageChauffeurs() {
    const etat = { recherche: '', statut: 'tous' };
    const corps = document.querySelector('[data-liste-chauffeurs]');
    const compteur = document.querySelector('[data-compteur]');

    function dessiner() {
      const liste = Store.chauffeurs(etat);
      compteur.textContent = liste.length + ' resultat' + (liste.length > 1 ? 's' : '') +
        ' sur ' + Store.chauffeurs().length;
      corps.innerHTML = liste.map(function (c) {
        const s = Format.statutChauffeur(c.statut);
        const bientot = new Date(c.permisExpiration) < new Date('2026-11-11');
        return '<tr>' +
          '<td><span class="d-inline-flex align-items-center gap-3">' +
            '<span class="tf-avatar ' + Format.tonAvatar(c.id) + '">' + Format.initiales(c) + '</span>' +
            '<span><span class="d-block" style="font-weight:500">' +
              Format.echapper(Format.nomComplet(c)) + '</span>' +
            '<span class="tf-meta">' + c.age + ' ans</span></span></span></td>' +
          '<td class="tf-mono">' + Format.echapper(c.telephone) + '</td>' +
          '<td class="tf-muted">' + Format.echapper(c.courriel) + '</td>' +
          '<td class="tf-mono ' + (bientot ? 'tf-danger' : '') + '">' +
            Format.echapper(c.permisExpiration) + '</td>' +
          '<td><span class="tf-pill ' + s.classe + '">' + s.texte + '</span></td>' +
          '<td class="text-end"><a href="chauffeur.html?id=' + encodeURIComponent(c.id) +
            '" style="font-size:13px">Ouvrir</a></td>' +
          '</tr>';
      }).join('') || '<tr><td colspan="6" class="tf-muted">Aucun chauffeur ne correspond.</td></tr>';
    }

    document.querySelector('[data-recherche]').addEventListener('input', function (e) {
      etat.recherche = e.target.value;
      dessiner();
    });
    document.querySelectorAll('[data-filtre-statut]').forEach(function (bouton) {
      bouton.addEventListener('click', function () {
        document.querySelectorAll('[data-filtre-statut]').forEach(function (b) {
          b.classList.remove('active');
        });
        bouton.classList.add('active');
        etat.statut = bouton.dataset.filtreStatut;
        dessiner();
      });
    });
    dessiner();
  },

  /* Fiche chauffeur */
  pageChauffeur() {
    const id = new URLSearchParams(location.search).get('id') || 'c1';
    const c = Store.chauffeur(id);
    if (!c) { document.querySelector('[data-fiche]').innerHTML =
      '<p class="tf-muted">Chauffeur introuvable.</p>'; return; }

    const s = Format.statutChauffeur(c.statut);
    const trajets = Store.trajets({ chauffeurId: c.id });
    const incidents = Store.incidents({ chauffeurId: c.id });

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
    document.querySelector('[data-plaque]').textContent = c.plaqueHabituelle;
    const vehicule = Store.vehicules().find(function (v) { return v.plaque === c.plaqueHabituelle; });
    document.querySelector('[data-vehicule]').textContent = vehicule ? vehicule.modele : '—';
    document.querySelector('[data-nb-incidents]').textContent = '(' + incidents.length + ')';

    const corpsTrajets = document.querySelector('[data-historique]');
    corpsTrajets.innerHTML = trajets.map(function (t) {
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

    const corpsIncidents = document.querySelector('[data-incidents-chauffeur]');
    corpsIncidents.innerHTML = incidents.map(function (i) {
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

  /* Creation de compte chauffeur */
  pageChauffeurNouveau() {
    document.querySelector('[data-formulaire]').addEventListener('submit', function (e) {
      e.preventDefault();
      const d = new FormData(e.target);
      const chauffeur = Store.ajouterChauffeur({
        prenom: d.get('prenom').trim(),
        nom: d.get('nom').trim(),
        age: Number(d.get('age')),
        telephone: d.get('telephone').trim(),
        courriel: d.get('courriel').trim(),
        adresse: d.get('adresse').trim(),
        permisNumero: d.get('permisNumero').trim(),
        permisExpiration: d.get('permisExpiration'),
        statut: d.get('statut'),
        plaqueHabituelle: d.get('plaque')
      });
      window.location.href = 'chauffeur.html?id=' + encodeURIComponent(chauffeur.id);
    });
  },

  /* Liste des trajets */
  pageTrajets() {
    const etat = { statut: 'tous' };
    const corps = document.querySelector('[data-liste-trajets]');

    function dessiner() {
      corps.innerHTML = Store.trajets(etat).map(function (t) {
        const c = Store.chauffeur(t.chauffeurId);
        const st = Format.statutTrajet(t.statut);
        return '<tr>' +
          '<td class="tf-mono">' + Format.echapper(t.id) + '</td>' +
          '<td>' + Format.dateCourte(t.debut) + '</td>' +
          '<td><span class="d-inline-flex align-items-center gap-2">' +
            '<span class="tf-avatar sm ' + Format.tonAvatar(c.id) + '">' + Format.initiales(c) + '</span>' +
            Format.echapper(Format.nomCourt(c)) + '</span></td>' +
          '<td>' + Format.echapper(t.depart + ' → ' + t.arrivee) + '</td>' +
          '<td class="tf-mono">' + Format.echapper(t.plaque) + '</td>' +
          '<td class="tf-mono tf-muted">' + Format.duree(t.debut, t.fin) + '</td>' +
          '<td><span class="tf-pill ' + st.classe + '">' + st.texte + '</span></td>' +
          '<td class="text-end"><a href="trajet.html?id=' + encodeURIComponent(t.id) +
            '" style="font-size:13px">Detail</a></td>' +
          '</tr>';
      }).join('');
    }

    document.querySelectorAll('[data-filtre-trajet]').forEach(function (b) {
      b.addEventListener('click', function () {
        document.querySelectorAll('[data-filtre-trajet]').forEach(function (x) {
          x.classList.remove('active');
        });
        b.classList.add('active');
        etat.statut = b.dataset.filtreTrajet;
        dessiner();
      });
    });
    dessiner();
  },

  /* Detail d un trajet */
  pageTrajet() {
    const id = new URLSearchParams(location.search).get('id') || 'T-2093';
    const t = Store.trajet(id);
    if (!t) { document.querySelector('[data-contenu]').innerHTML =
      '<p class="tf-muted">Trajet introuvable.</p>'; return; }

    const c = Store.chauffeur(t.chauffeurId);
    const st = Format.statutTrajet(t.statut);
    const incidents = Store.incidents().filter(function (i) { return i.trajetId === t.id; });
    const p = Format.progression(t);

    document.querySelector('[data-fil]').textContent = t.id;
    document.querySelector('[data-titre]').textContent = t.depart + ' → ' + t.arrivee;
    document.querySelector('[data-statut]').className = 'tf-pill ' + st.classe;
    document.querySelector('[data-statut]').textContent = st.texte;
    document.querySelector('[data-avatar]').className = 'tf-avatar ' + Format.tonAvatar(c.id);
    document.querySelector('[data-avatar]').textContent = Format.initiales(c);
    document.querySelector('[data-chauffeur]').textContent = Format.nomComplet(c);
    document.querySelector('[data-telephone]').textContent = c.telephone;
    document.querySelector('[data-plaque]').textContent = t.plaque;
    document.querySelector('[data-duree]').textContent = t.statut === 'termine'
      ? Format.duree(t.debut, t.fin) : Format.dureeDepuis(t.debut);
    document.querySelector('[data-nb-arrets]').textContent = t.arrets.length;
    document.querySelector('[data-nb-incidents]').textContent = incidents.length;
    document.querySelector('[data-nb-incidents]').classList.toggle('tf-danger', incidents.length > 0);
    document.querySelector('[data-progression]').style.width = p + '%';
    document.querySelector('[data-progression-note]').textContent =
      p + '% · arrivee ' + (t.statut === 'termine' ? 'a ' : 'estimee ') + Format.heure(t.finPrevue);

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
      return '<div class="tf-tl-time' + (e.incident ? ' tf-danger' : '') + '">' + e.heure + '</div>' +
        '<div class="tf-tl-body ' + e.classe + dernier + '">' + corps + '</div>';
    }).join('');
  },

  /* Liste et detail des incidents */
  pageIncidents() {
    const etat = { type: 'tous', statut: 'tous' };
    const corps = document.querySelector('[data-liste-incidents]');
    let selection = null;

    function dessinerDetail(i) {
      const panneau = document.querySelector('[data-detail]');
      if (!i) { panneau.innerHTML = '<p class="tf-muted">Choisir un incident dans la liste.</p>'; return; }
      const c = Store.chauffeur(i.chauffeurId);
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
          '<span class="tf-avatar ' + Format.tonAvatar(c.id) + '">' + Format.initiales(c) + '</span>' +
          '<span><span class="d-block" style="font-weight:500">' + Format.echapper(Format.nomComplet(c)) +
          '</span><span class="tf-meta">Trajet ' + Format.echapper(i.trajetId) + ' · ' +
          Format.echapper(Store.trajet(i.trajetId) ? Store.trajet(i.trajetId).plaque : '—') +
          '</span></span></div>' +
        '<div><div class="tf-meta mb-1">Description</div>' +
          '<p class="mb-0" style="font-size:14.5px;line-height:1.6">' +
          Format.echapper(i.description) + '</p></div>' +
        '<div class="row g-3"><div class="col-6"><div class="tf-meta mb-1">Lieu</div>' +
          '<div style="font-size:14.5px">' + Format.echapper(i.lieu) + '</div></div>' +
          '<div class="col-6"><div class="tf-meta mb-1">Signale a</div>' +
          '<div class="tf-mono" style="font-size:14.5px">' + Format.echapper(i.heure) + '</div></div></div>' +
        '<div class="d-flex gap-3 pt-3" style="border-top:1px solid var(--tf-line)">' +
          '<a class="tf-btn tf-btn-ghost flex-fill" href="tel:' + Format.echapper(c.telephone) +
            '">Contacter</a>' +
          (i.statut === 'ouvert'
            ? '<button type="button" class="tf-btn tf-btn-dark flex-fill" data-traiter>Marquer comme traite</button>'
            : '<span class="tf-btn tf-btn-ghost flex-fill" style="cursor:default">Deja traite</span>') +
        '</div>';
      const bouton = panneau.querySelector('[data-traiter]');
      if (bouton) bouton.addEventListener('click', function () {
        Store.traiterIncident(i.id);
        selection = Store.incident(i.id);
        dessiner();
      });
    }

    function dessiner() {
      const liste = Store.incidents(etat);
      if (!selection || !liste.some(function (i) { return i.id === selection.id; })) {
        selection = liste[0] || null;
      }
      document.querySelector('[data-resume]').textContent =
        Store.incidents({ statut: 'ouvert' }).length + ' ouverts · ' +
        Store.incidents({ statut: 'traite' }).length + ' traites';
      corps.innerHTML = liste.map(function (i) {
        const c = Store.chauffeur(i.chauffeurId);
        const st = Format.statutIncident(i.statut);
        const ty = Format.typeIncident(i.type);
        const actif = selection && selection.id === i.id;
        return '<tr data-ligne="' + i.id + '" style="cursor:pointer"' +
          (actif ? ' class="is-active is-open"' : '') + '>' +
          '<td class="tf-mono" style="font-size:13px">' + Format.jourHeure(i.date + 'T' + i.heure) + '</td>' +
          '<td><span class="tf-pill ' + ty.classe + '">' + ty.texte + '</span></td>' +
          '<td>' + Format.echapper(Format.nomCourt(c)) + '</td>' +
          '<td>' + Format.echapper(i.lieu) + '</td>' +
          '<td><span class="tf-pill ' + st.classe + '">' + st.texte + '</span></td>' +
          '</tr>';
      }).join('') || '<tr><td colspan="5" class="tf-muted">Aucun incident.</td></tr>';

      corps.querySelectorAll('[data-ligne]').forEach(function (ligne) {
        ligne.addEventListener('click', function () {
          selection = Store.incident(ligne.dataset.ligne);
          dessiner();
        });
      });
      dessinerDetail(selection);
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
        dessiner();
      });
    });
    dessiner();
  }
};

document.addEventListener('DOMContentLoaded', function () { Admin.demarrer(); });

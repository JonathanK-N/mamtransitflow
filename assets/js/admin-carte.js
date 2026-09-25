/* TransitFlow — suivi GPS cote administrateur
   Auteur : Jonathan K-N

   - carte.html : carte en direct de tous les trajets en cours, rafraichie
     toutes les 5 s (mise en pause quand l onglet est cache), liste des
     vehicules a droite, trace du vehicule selectionne (suivi a l ecran) ;
   - trajet.html : parcours du trajet sur une carte, avec distance et
     vitesses (rafraichi toutes les 15 s tant que le trajet est en cours).
   Charge apres admin.js et carte.js. */

const TF_RAFRAICHISSEMENT_CARTE_MS = 5000;
const TF_RAFRAICHISSEMENT_TRACE_MS = 15000;

/* Appelle `tache` toutes les `intervalle` ms tant que l onglet est visible (et tout de suite au retour). */
function tfRepeter(tache, intervalle) {
  let minuterie = null;
  function planifier() {
    clearTimeout(minuterie);
    minuterie = setTimeout(async function () {
      if (document.visibilityState === 'visible') {
        try { await tache(); } catch (e) { /* erreur reseau passagere : nouvel essai au prochain tour */ }
      }
      planifier();
    }, intervalle);
  }
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'visible') { tache().catch(function () {}); planifier(); }
  });
  planifier();
}

Object.assign(Admin, {
  async pageCarte() {
    const liste = document.querySelector('[data-liste-suivi]');
    const resume = document.querySelector('[data-resume]');
    const vide = document.querySelector('[data-carte-vide]');
    const suivreAuto = document.querySelector('[data-suivre]');
    const carte = tfCreerCarte(document.querySelector('[data-carte]'));
    const marqueurs = {};      // trajetId -> L.Marker
    const trace = L.layerGroup().addTo(carte);
    let selection = new URLSearchParams(location.search).get('trajet');
    let vehicules = [];
    let premierCadrage = true;

    function cadrer() {
      const points = vehicules.filter(function (v) { return v.position; })
        .map(function (v) { return [v.position.lat, v.position.lng]; });
      if (points.length === 1) carte.setView(points[0], 13);
      else if (points.length > 1) carte.fitBounds(points, { padding: [60, 60], maxZoom: 13 });
    }

    async function dessinerTrace() {
      if (!selection) { trace.clearLayers(); return; }
      const p = await Store.parcours(selection);
      tfDessinerParcours(trace, p.positions, false);
    }

    function dessinerListe() {
      liste.innerHTML = vehicules.map(function (v) {
        const l = Format.liaison(v.liaison);
        return '<button type="button" data-trajet="' + Format.echapper(v.trajetId) + '"' +
          (v.trajetId === selection ? ' class="active"' : '') + '>' +
          '<span class="tf-voyant ' + Format.echapper(v.liaison) + '"></span>' +
          '<span class="flex-fill" style="min-width:0">' +
            '<span class="d-flex align-items-baseline gap-2"><span style="font-weight:500">' +
              Format.echapper(v.chauffeur) + '</span><span class="tf-mono tf-meta ms-auto">' +
              Format.echapper(v.plaque) + '</span></span>' +
            '<span class="d-block tf-meta">' + Format.echapper(v.depart + ' → ' + v.arrivee) + '</span>' +
            '<span class="d-block tf-meta">' + l.texte + ' · ' + Format.echapper(Format.depuis(v.ageSecondes)) +
              (v.position && v.position.vitesse !== null ? ' · ' + Format.vitesse(v.position.vitesse) : '') +
            '</span></span></button>';
      }).join('') || '<p class="tf-empty mb-0">Aucun trajet en cours.</p>';
      liste.querySelectorAll('[data-trajet]').forEach(function (b) {
        b.addEventListener('click', function () { choisir(b.dataset.trajet, true); });
      });
    }

    function dessinerMarqueurs() {
      const presents = {};
      vehicules.forEach(function (v) {
        if (!v.position) return;
        presents[v.trajetId] = true;
        const icone = tfIconeVehicule(v.plaque, v.liaison, v.position.cap, v.trajetId === selection);
        const position = [v.position.lat, v.position.lng];
        let m = marqueurs[v.trajetId];
        if (!m) {
          m = L.marker(position, { icon: icone, title: v.plaque, riseOnHover: true }).addTo(carte);
          m.on('click', function () { choisir(v.trajetId, false); });
          m.bindPopup('');
          marqueurs[v.trajetId] = m;
        } else {
          m.setLatLng(position);
          m.setIcon(icone);
        }
        m.setPopupContent(tfBulleVehicule(v));
        m.setZIndexOffset(v.trajetId === selection ? 1000 : 0);
      });
      Object.keys(marqueurs).forEach(function (id) {
        if (!presents[id]) { carte.removeLayer(marqueurs[id]); delete marqueurs[id]; }
      });
    }

    async function actualiser() {
      vehicules = await Store.enDirect();
      if (selection && !vehicules.some(function (v) { return v.trajetId === selection; })) {
        selection = null;
        trace.clearLayers();
      }
      const localises = vehicules.filter(function (v) { return v.position; }).length;
      resume.textContent = vehicules.length + ' trajet' + (vehicules.length > 1 ? 's' : '') + ' en cours · ' +
        localises + ' localise' + (localises > 1 ? 's' : '') + ' · mis a jour a ' + Format.heureActuelle() + ':' +
        String(new Date().getSeconds()).padStart(2, '0');
      vide.classList.toggle('tf-hidden', localises > 0);
      dessinerMarqueurs();
      dessinerListe();
      if (premierCadrage && localises) { cadrer(); premierCadrage = false; } else if (suivreAuto.checked) cadrer();
      else suivreSelection();
      // La trace du vehicule suivi avance au meme rythme que son marqueur.
      if (selection) await dessinerTrace();
    }

    /* Garde le vehicule selectionne a l ecran quand il approche du bord de la carte. */
    function suivreSelection() {
      const m = selection && marqueurs[selection];
      if (m && !carte.getBounds().pad(-0.15).contains(m.getLatLng())) carte.panTo(m.getLatLng());
    }

    async function choisir(trajetId, centrer) {
      selection = trajetId;
      dessinerListe();
      dessinerMarqueurs();
      const v = vehicules.find(function (x) { return x.trajetId === trajetId; });
      const m = marqueurs[trajetId];
      if (m && centrer) { carte.setView(m.getLatLng(), Math.max(carte.getZoom(), 13)); m.openPopup(); }
      else if (!m && v && centrer) tfNotifier('Aucune position recue pour ' + v.plaque + ' pour le moment.');
      await dessinerTrace();
    }

    document.querySelector('[data-recadrer]').addEventListener('click', cadrer);
    await actualiser();
    if (selection) await choisir(selection, true);
    tfRepeter(actualiser, TF_RAFRAICHISSEMENT_CARTE_MS);
  }
});

/* Carte du parcours sur la fiche d un trajet (appelee par Admin.pageTrajet). */
async function tfCarteTrajet(trajet) {
  const zone = document.querySelector('[data-carte-trajet]');
  if (!zone || typeof L === 'undefined') return;
  const carte = tfCreerCarte(zone, { scrollWheelZoom: false });
  const groupe = L.layerGroup().addTo(carte);
  const stats = document.querySelector('[data-stats-parcours]');
  const lienDirect = document.querySelector('[data-lien-direct]');
  let cadre = false;

  async function dessiner() {
    const p = await Store.parcours(trajet.id);
    const limites = tfDessinerParcours(groupe, p.positions, trajet.statut === 'termine');
    if (limites && !cadre) {
      carte.fitBounds(limites, { padding: [24, 24], maxZoom: 17 });
      cadre = true;
    }
    const s = p.statistiques;
    stats.innerHTML = p.nombrePoints
      ? [['Distance', Format.distance(s.distanceM)], ['Vitesse moy.', Format.vitesse(s.vitesseMoyenneKmh)],
         ['Vitesse max.', Format.vitesse(s.vitesseMaxKmh)], ['Points GPS', p.nombrePoints]]
        .map(function (x) {
          return '<div><div class="tf-meta">' + x[0] + '</div><div class="tf-mono" style="font-size:14px">' +
            Format.echapper(x[1]) + '</div></div>';
        }).join('')
      : '<p class="tf-meta mb-0" style="grid-column:1/-1">Aucune position GPS recue pour ce trajet' +
        (trajet.statut === 'en-cours' ? ' : le chauffeur doit garder la page du trajet ouverte.' : '.') + '</p>';
    if (lienDirect) {
      lienDirect.classList.toggle('tf-hidden', trajet.statut !== 'en-cours');
      lienDirect.href = 'carte.html?trajet=' + encodeURIComponent(trajet.id);
    }
  }

  await dessiner();
  if (trajet.statut === 'en-cours') tfRepeter(dessiner, TF_RAFRAICHISSEMENT_TRACE_MS);
}

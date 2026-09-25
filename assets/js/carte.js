/* TransitFlow — cartes Leaflet partagees (carte en direct, parcours d un trajet)
   Auteur : Jonathan K-N

   Fond de carte OpenStreetMap (attribution obligatoire, affichee en bas a
   droite). Les vehicules sont dessines avec des marqueurs HTML (divIcon) :
   couleur selon la fraicheur du signal, fleche selon le cap, plaque en
   etiquette. Leaflet (L) est charge par la page avant ce fichier. */

const TF_CARTE = {
  // Centre par defaut quand aucune position n est connue : Sherbrooke.
  centre: [45.4042, -71.8929],
  zoom: 9,
  // Adresse sans sous-domaine a/b/c, comme le recommande OpenStreetMap.
  tuiles: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
};

/* Cree une carte dans l element donne. */
function tfCreerCarte(element, options) {
  const carte = L.map(element, Object.assign({ zoomControl: true, attributionControl: true }, options || {}))
    .setView(TF_CARTE.centre, TF_CARTE.zoom);
  // Le serveur impose Referrer-Policy: same-origin, qui supprime l entete
  // Referer vers les autres sites. Or OpenStreetMap refuse les tuiles sans
  // Referer (image "Access blocked") : on envoie l origine du site, pour les
  // seules tuiles, sans affaiblir la politique du reste de l application.
  L.tileLayer(TF_CARTE.tuiles, {
    maxZoom: 19, attribution: TF_CARTE.attribution, referrerPolicy: 'strict-origin-when-cross-origin'
  }).addTo(carte);
  return carte;
}

/* Icone d un vehicule en route. liaison : 'en-ligne' | 'intermittent' | 'perdue'. */
function tfIconeVehicule(plaque, liaison, cap, selectionne) {
  const fleche = (cap === null || cap === undefined || isNaN(cap)) ? ''
    : '<span class="tf-marqueur-cap" style="transform:rotate(' + Math.round(cap) + 'deg)"></span>';
  return L.divIcon({
    className: '',
    iconSize: [0, 0],
    html: '<div class="tf-marqueur ' + Format.echapper(liaison) + (selectionne ? ' selection' : '') + '">' +
      fleche + '<span class="tf-marqueur-point"></span>' +
      '<span class="tf-marqueur-etiquette">' + Format.echapper(plaque) + '</span></div>'
  });
}

function tfIconeBorne(type) {
  return L.divIcon({ className: '', iconSize: [0, 0], html: '<div class="tf-marqueur-borne ' + type + '"></div>' });
}

/*
 * Dessine (ou redessine) le parcours d un trajet dans un groupe de calques :
 * trace, point de depart et dernier point connu. Renvoie les limites du
 * trace (L.LatLngBounds) ou null s il n y a aucun point.
 */
function tfDessinerParcours(groupe, positions, termine) {
  groupe.clearLayers();
  if (!positions.length) return null;
  const points = positions.map(function (p) { return [p.lat, p.lng]; });
  L.polyline(points, { color: '#D9702F', weight: 4, opacity: 0.85, lineJoin: 'round' }).addTo(groupe);
  L.marker(points[0], { icon: tfIconeBorne('depart'), title: 'Depart' }).addTo(groupe);
  if (termine && points.length > 1) {
    L.marker(points[points.length - 1], { icon: tfIconeBorne('arrivee'), title: 'Arrivee' }).addTo(groupe);
  }
  return L.latLngBounds(points);
}

/* Contenu de la bulle d un vehicule sur la carte en direct. */
function tfBulleVehicule(v) {
  const p = v.position;
  const l = Format.liaison(v.liaison);
  return '<div style="min-width:200px">' +
    '<div style="font-weight:600">' + Format.echapper(v.chauffeur) + '</div>' +
    '<div class="tf-mono" style="font-size:12.5px">' + Format.echapper(v.plaque) + '</div>' +
    '<div class="mt-1">' + Format.echapper(v.depart + ' → ' + v.arrivee) + '</div>' +
    '<div class="mt-2 d-flex gap-2 align-items-center"><span class="tf-pill ' + l.classe +
      '" style="padding:3px 9px;font-size:11.5px">' + l.texte + '</span>' +
      '<span class="tf-meta">' + Format.echapper(Format.depuis(v.ageSecondes)) + '</span></div>' +
    (p ? '<div class="tf-meta mt-1">' + [
      p.vitesse !== null && p.vitesse !== undefined ? Format.vitesse(p.vitesse) : '',
      p.precision ? 'precision ' + Math.round(p.precision) + ' m' : ''
    ].filter(Boolean).join(' · ') + '</div>' : '') +
    '<div class="mt-2 d-flex gap-3"><a href="trajet.html?id=' + encodeURIComponent(v.trajetId) + '">Voir le trajet</a>' +
      (v.telephone ? '<a href="tel:' + Format.echapper(v.telephone) + '">Appeler</a>' : '') + '</div></div>';
}

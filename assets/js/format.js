/* TransitFlow — formatage et libelles
   Auteur : Mamadou Barry
   Modifie par : Jonathan K-N — les dates et durees se calculent a partir
   de l heure reelle du navigateur (et non plus d un "aujourd hui" fige au
   12 septembre 2026) ; libelles de la flotte et de l entretien. */

const MOIS = ['janvier', 'fevrier', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'aout', 'septembre', 'octobre', 'novembre', 'decembre'];
const MOIS_COURT = ['janv.', 'fevr.', 'mars', 'avr.', 'mai', 'juin',
  'juil.', 'aout', 'sept.', 'oct.', 'nov.', 'dec.'];

const Format = {
  /* Date locale au format AAAA-MM-JJ (decalee de n jours si demande). */
  aujourdhui(decalageJours) {
    const d = new Date();
    if (decalageJours) d.setDate(d.getDate() + decalageJours);
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' +
      String(d.getDate()).padStart(2, '0');
  },

  /* Heure locale actuelle "HH:MM" (decalee de n minutes si demande), pour pre-remplir les formulaires. */
  heureActuelle(decalageMinutes) {
    const d = new Date(Date.now() + (decalageMinutes || 0) * 60000);
    return String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
  },

  /* Instant ISO (UTC) correspondant a une date "AAAA-MM-JJ" et une heure "HH:MM" locales. */
  instant(date, heure) {
    return new Date(date + 'T' + heure).toISOString();
  },

  /* Vrai si le permis expire dans les 60 prochains jours (meme fenetre que /api/indicateurs). */
  permisBientotExpire(expiration) {
    return Boolean(expiration) && expiration < this.aujourdhui(60);
  },

  dateLongue(iso) {
    if (!iso) return '—';
    const d = new Date(iso.slice(0, 10) + 'T00:00');
    return d.getDate() + ' ' + MOIS[d.getMonth()] + ' ' + d.getFullYear();
  },

  dateCourte(iso) {
    if (!iso) return '—';
    const d = new Date(iso.slice(0, 10) + 'T00:00');
    return d.getDate() + ' ' + MOIS_COURT[d.getMonth()] + ' ' + d.getFullYear();
  },

  jourHeure(iso) {
    if (!iso) return '—';
    return iso.slice(8, 10) + '/' + iso.slice(5, 7) + ' ' + (iso.slice(11, 16) || '');
  },

  heure(iso) { return iso ? iso.slice(11, 16) : '—'; },

  duree(debut, fin) {
    if (!debut || !fin) return '—';
    const ms = new Date(fin) - new Date(debut);
    if (isNaN(ms) || ms < 0) return '—';
    const minutes = Math.round(ms / 60000);
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    if (h === 0) return m + ' min';
    return h + ' h ' + String(m).padStart(2, '0');
  },

  dureeDepuis(debut, maintenant) {
    return this.duree(debut, maintenant || new Date().toISOString());
  },

  progression(trajet, maintenant) {
    if (trajet.statut === 'termine') return 100;
    if (trajet.statut === 'planifie') return 0;
    const t0 = new Date(trajet.debut).getTime();
    const t1 = new Date(trajet.finPrevue).getTime();
    const tn = maintenant ? new Date(maintenant).getTime() : Date.now();
    if (!t0 || !t1 || t1 <= t0) return 0;
    return Math.max(0, Math.min(100, Math.round(((tn - t0) / (t1 - t0)) * 100)));
  },

  initiales(chauffeur) {
    if (!chauffeur) return '??';
    return (chauffeur.prenom[0] + chauffeur.nom[0]).toUpperCase();
  },

  nomCourt(chauffeur) {
    if (!chauffeur) return 'Inconnu';
    return chauffeur.prenom[0] + '. ' + chauffeur.nom;
  },

  nomComplet(chauffeur) {
    return chauffeur ? chauffeur.prenom + ' ' + chauffeur.nom : 'Inconnu';
  },

  tonAvatar(id) {
    const tons = ['', 'tone-b', 'tone-c', 'tone-d'];
    const n = parseInt(String(id).replace(/\D/g, ''), 10) || 0;
    return tons[n % tons.length];
  },

  statutChauffeur(statut) {
    const table = {
      'en-trajet': { texte: 'En trajet', classe: 'warn' },
      'disponible': { texte: 'Disponible', classe: 'ok' },
      'hors-service': { texte: 'Hors service', classe: '' }
    };
    return table[statut] || { texte: statut, classe: '' };
  },

  statutTrajet(statut) {
    const table = {
      'en-cours': { texte: 'En cours', classe: 'warn' },
      'termine': { texte: 'Termine', classe: 'ok' },
      'planifie': { texte: 'Planifie', classe: '' }
    };
    return table[statut] || { texte: statut, classe: '' };
  },

  statutIncident(statut) {
    return statut === 'ouvert'
      ? { texte: 'Ouvert', classe: 'danger' }
      : { texte: 'Traite', classe: 'ok' };
  },

  typeIncident(type) {
    return type === 'technique'
      ? { texte: 'Technique', classe: 'type-tech' }
      : { texte: 'Route', classe: '' };
  },

  /* ---- Flotte et entretien ---- */

  /* 48210 -> "48 210 km" */
  km(valeur) {
    if (valeur === null || valeur === undefined || valeur === '') return '—';
    return Number(valeur).toLocaleString('fr-CA') + ' km';
  },

  /* 1234.5 -> "1 234,50 $" */
  montant(valeur) {
    return Number(valeur || 0).toLocaleString('fr-CA', { style: 'currency', currency: 'CAD' });
  },

  statutVehicule(statut) {
    const table = {
      'actif': { texte: 'Actif', classe: 'ok' },
      'maintenance': { texte: 'En maintenance', classe: 'warn' },
      'hors-service': { texte: 'Hors service', classe: '' }
    };
    return table[statut] || { texte: statut, classe: '' };
  },

  statutBon(statut) {
    const table = {
      'planifie': { texte: 'Planifie', classe: '' },
      'en-cours': { texte: 'En cours', classe: 'warn' },
      'termine': { texte: 'Termine', classe: 'ok' },
      'annule': { texte: 'Annule', classe: 'muted' }
    };
    return table[statut] || { texte: statut, classe: '' };
  },

  prioriteBon(priorite) {
    const table = {
      'basse': { texte: 'Basse', classe: '' },
      'normale': { texte: 'Normale', classe: '' },
      'haute': { texte: 'Haute', classe: 'warn' },
      'urgente': { texte: 'Urgente', classe: 'danger' }
    };
    return table[priorite] || { texte: priorite, classe: '' };
  },

  /* Meme liste que TYPES_ENTRETIEN dans backend/apps/entretien/models.py. */
  TYPES_ENTRETIEN: [
    ['vidange', 'Vidange et filtres'], ['pneus', 'Pneus'], ['freins', 'Freins'],
    ['inspection', 'Inspection mecanique'], ['courroie', 'Courroie de distribution'],
    ['climatisation', 'Climatisation'], ['carrosserie', 'Carrosserie'],
    ['electrique', 'Systeme electrique'], ['reparation', 'Reparation mecanique'], ['autre', 'Autre']
  ],

  typeEntretien(type) {
    const trouve = this.TYPES_ENTRETIEN.find(function (t) { return t[0] === type; });
    return trouve ? trouve[1] : type;
  },

  /* <option> de chaque type d entretien (pour les listes deroulantes). */
  optionsTypesEntretien(selection) {
    return this.TYPES_ENTRETIEN.map(function (t) {
      return '<option value="' + t[0] + '"' + (t[0] === selection ? ' selected' : '') + '>' + t[1] + '</option>';
    }).join('');
  },

  etatEcheance(etat) {
    const table = {
      'en-retard': { texte: 'En retard', classe: 'danger' },
      'bientot': { texte: 'Bientot', classe: 'warn' },
      'a-jour': { texte: 'A jour', classe: 'ok' }
    };
    return table[etat] || { texte: etat, classe: '' };
  },

  /* "tous les 8 000 km ou 180 jours" */
  intervalle(plan) {
    const morceaux = [];
    if (plan.intervalleKm) morceaux.push(this.km(plan.intervalleKm));
    if (plan.intervalleJours) morceaux.push(plan.intervalleJours + ' jours');
    return 'tous les ' + morceaux.join(' ou ');
  },

  /* Ce qui reste avant l echeance : "600 km restants · 30 j restants" / "depasse de 200 km · 180 j restants". */
  resteEcheance(echeance) {
    const morceaux = [];
    if (echeance.kmRestants !== null && echeance.kmRestants !== undefined) {
      morceaux.push(echeance.kmRestants > 0
        ? Number(echeance.kmRestants).toLocaleString('fr-CA') + ' km restants'
        : 'depasse de ' + Number(-echeance.kmRestants).toLocaleString('fr-CA') + ' km');
    }
    if (echeance.joursRestants !== null && echeance.joursRestants !== undefined) {
      morceaux.push(echeance.joursRestants > 0
        ? echeance.joursRestants + ' j restants'
        : (echeance.joursRestants === 0 ? 'aujourd hui' : 'depasse de ' + (-echeance.joursRestants) + ' j'));
    }
    return morceaux.join(' · ') || '—';
  },

  /* ---- Suivi GPS ---- */

  /* 12 -> "il y a 12 s", 190 -> "il y a 3 min", 7300 -> "il y a 2 h" */
  depuis(secondes) {
    if (secondes === null || secondes === undefined) return 'jamais';
    if (secondes < 5) return 'a l instant';
    if (secondes < 60) return 'il y a ' + Math.round(secondes) + ' s';
    if (secondes < 3600) return 'il y a ' + Math.floor(secondes / 60) + ' min';
    return 'il y a ' + Math.floor(secondes / 3600) + ' h';
  },

  /* 12430 -> "12,4 km", 830 -> "830 m" */
  distance(metres) {
    if (metres === null || metres === undefined) return '—';
    if (metres < 1000) return Math.round(metres) + ' m';
    return (metres / 1000).toLocaleString('fr-CA', { maximumFractionDigits: 1 }) + ' km';
  },

  vitesse(kmh) {
    return (kmh === null || kmh === undefined) ? '—' : Math.round(kmh) + ' km/h';
  },

  liaison(etat) {
    const table = {
      'en-ligne': { texte: 'En ligne', classe: 'ok' },
      'intermittent': { texte: 'Signal faible', classe: 'warn' },
      'perdue': { texte: 'Signal perdu', classe: '' },
      'aucune': { texte: 'Aucune position', classe: '' }
    };
    return table[etat] || { texte: etat, classe: '' };
  },

  echapper(valeur) {
    return String(valeur === null || valeur === undefined ? '' : valeur)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }
};

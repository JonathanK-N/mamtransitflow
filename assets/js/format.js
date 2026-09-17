/* TransitFlow — formatage et libelles
   Auteur : Mamadou Barry */

const MOIS = ['janvier', 'fevrier', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'aout', 'septembre', 'octobre', 'novembre', 'decembre'];
const MOIS_COURT = ['janv.', 'fevr.', 'mars', 'avr.', 'mai', 'juin',
  'juil.', 'aout', 'sept.', 'oct.', 'nov.', 'dec.'];

const Format = {
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
    return this.duree(debut, maintenant || '2026-09-12T09:02');
  },

  progression(trajet, maintenant) {
    if (trajet.statut === 'termine') return 100;
    if (trajet.statut === 'planifie') return 0;
    const t0 = new Date(trajet.debut).getTime();
    const t1 = new Date(trajet.finPrevue).getTime();
    const tn = new Date(maintenant || '2026-09-12T09:02').getTime();
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

  echapper(valeur) {
    return String(valeur === null || valeur === undefined ? '' : valeur)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }
};

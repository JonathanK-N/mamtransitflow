/* TransitFlow — donnees et persistance locale
   Auteur : Mamadou Barry */

const TF_KEY = 'transitflow.v1';


const Store = {
  load() {
    const raw = localStorage.getItem(TF_KEY);
    if (!raw) {
      const copie = JSON.parse(JSON.stringify(TF_SEED));
      localStorage.setItem(TF_KEY, JSON.stringify(copie));
      return copie;
    }
    try { return JSON.parse(raw); }
    catch (e) { localStorage.removeItem(TF_KEY); return this.load(); }
  },

  save(donnees) { localStorage.setItem(TF_KEY, JSON.stringify(donnees)); },

  reinitialiser() { localStorage.removeItem(TF_KEY); return this.load(); },

  /* Chauffeurs */
  chauffeurs(filtre) {
    const liste = this.load().chauffeurs;
    if (!filtre) return liste;
    const q = (filtre.recherche || '').trim().toLowerCase();
    return liste.filter(function (c) {
      const okStatut = !filtre.statut || filtre.statut === 'tous' || c.statut === filtre.statut;
      const texte = (c.prenom + ' ' + c.nom + ' ' + c.telephone + ' ' + c.courriel).toLowerCase();
      return okStatut && (!q || texte.indexOf(q) !== -1);
    });
  },

  chauffeur(id) {
    return this.load().chauffeurs.find(function (c) { return c.id === id; }) || null;
  },

  ajouterChauffeur(chauffeur) {
    const d = this.load();
    chauffeur.id = 'c' + (d.chauffeurs.length + 1);
    chauffeur.statut = chauffeur.statut || 'disponible';
    chauffeur.creeLe = new Date().toISOString().slice(0, 10);
    d.chauffeurs.push(chauffeur);
    this.save(d);
    return chauffeur;
  },

  majChauffeur(id, champs) {
    const d = this.load();
    const c = d.chauffeurs.find(function (x) { return x.id === id; });
    if (!c) return null;
    Object.assign(c, champs);
    this.save(d);
    return c;
  },

  /* Trajets */
  trajets(filtre) {
    const liste = this.load().trajets.slice().sort(function (a, b) {
      return (b.debut || '').localeCompare(a.debut || '');
    });
    if (!filtre) return liste;
    return liste.filter(function (t) {
      const okStatut = !filtre.statut || filtre.statut === 'tous' || t.statut === filtre.statut;
      const okChauffeur = !filtre.chauffeurId || t.chauffeurId === filtre.chauffeurId;
      return okStatut && okChauffeur;
    });
  },

  trajet(id) {
    return this.load().trajets.find(function (t) { return t.id === id; }) || null;
  },

  trajetEnCours(chauffeurId) {
    return this.load().trajets.find(function (t) {
      return t.chauffeurId === chauffeurId && t.statut === 'en-cours';
    }) || null;
  },

  ajouterTrajet(trajet) {
    const d = this.load();
    const numeros = d.trajets.map(function (t) { return parseInt(t.id.split('-')[1], 10) || 0; });
    trajet.id = 'T-' + (Math.max.apply(null, numeros) + 1);
    trajet.statut = 'en-cours';
    trajet.arrets = [];
    trajet.fin = null;
    d.trajets.push(trajet);
    this.save(d);
    return trajet;
  },

  ajouterArret(trajetId, arret) {
    const d = this.load();
    const t = d.trajets.find(function (x) { return x.id === trajetId; });
    if (!t) return null;
    t.arrets.push(arret);
    this.save(d);
    return t;
  },

  terminerTrajet(trajetId) {
    const d = this.load();
    const t = d.trajets.find(function (x) { return x.id === trajetId; });
    if (!t) return null;
    t.statut = 'termine';
    t.fin = new Date().toISOString().slice(0, 16);
    const c = d.chauffeurs.find(function (x) { return x.id === t.chauffeurId; });
    if (c) c.statut = 'disponible';
    this.save(d);
    return t;
  },

  /* Incidents */
  incidents(filtre) {
    const liste = this.load().incidents.slice().sort(function (a, b) {
      return (b.date + b.heure).localeCompare(a.date + a.heure);
    });
    if (!filtre) return liste;
    return liste.filter(function (i) {
      const okType = !filtre.type || filtre.type === 'tous' || i.type === filtre.type;
      const okStatut = !filtre.statut || filtre.statut === 'tous' || i.statut === filtre.statut;
      const okChauffeur = !filtre.chauffeurId || i.chauffeurId === filtre.chauffeurId;
      return okType && okStatut && okChauffeur;
    });
  },

  incident(id) {
    return this.load().incidents.find(function (i) { return i.id === id; }) || null;
  },

  ajouterIncident(incident) {
    const d = this.load();
    const numeros = d.incidents.map(function (i) { return parseInt(i.id.split('-')[1], 10) || 0; });
    incident.id = 'I-' + (Math.max.apply(null, numeros) + 1);
    incident.statut = 'ouvert';
    d.incidents.unshift(incident);
    this.save(d);
    return incident;
  },

  traiterIncident(id) {
    const d = this.load();
    const i = d.incidents.find(function (x) { return x.id === id; });
    if (!i) return null;
    i.statut = 'traite';
    this.save(d);
    return i;
  },

  vehicules() { return this.load().vehicules; },

  /* Indicateurs du tableau de bord */
  indicateurs() {
    const d = this.load();
    const aujourdhui = '2026-09-12';
    const limite = new Date('2026-11-11');
    return {
      chauffeursActifs: d.chauffeurs.filter(function (c) { return c.statut !== 'hors-service'; }).length,
      trajetsEnCours: d.trajets.filter(function (t) { return t.statut === 'en-cours'; }).length,
      trajetsDuJour: d.trajets.filter(function (t) { return (t.debut || '').slice(0, 10) === aujourdhui; }).length,
      incidentsOuverts: d.incidents.filter(function (i) { return i.statut === 'ouvert'; }).length,
      incidentsDuJour: d.incidents.filter(function (i) { return i.date === aujourdhui; }).length,
      permisAExpirer: d.chauffeurs.filter(function (c) { return new Date(c.permisExpiration) < limite; }).length
    };
  }
};

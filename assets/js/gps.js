/* TransitFlow — partage de position du chauffeur pendant un trajet
   Auteur : Jonathan K-N

   Utilise l API de geolocalisation du navigateur (watchPosition). Les
   points sont mis en file d attente puis envoyes par lots toutes les
   10 secondes a POST /api/trajets/<id>/positions :
   - une coupure de reseau ne perd rien : la file est gardee (y compris
     si la page est rechargee, via sessionStorage) et renvoyee au retour
     du reseau ; le serveur ignore les points deja recus ;
   - les mesures tres imprecises (> 1 km) et les micro-deplacements a
     l arret sont ecartes pour economiser batterie et donnees ;
   - l ecran est maintenu allume (Wake Lock) quand le navigateur le permet :
     un navigateur mobile suspend la geolocalisation d une page en
     arriere-plan ou ecran eteint.
   La geolocalisation exige HTTPS (ou localhost). */

class SuiviGPS {
  constructor(trajetId, options) {
    this.trajetId = trajetId;
    this.options = Object.assign({ intervalleEnvoi: 10000, rappel: function () {} }, options || {});
    this.cle = 'transitflow.gps.' + trajetId;
    this.file = this._lireFile();
    this.etat = { statut: 'arrete', precision: null, dernierEnvoi: null, enAttente: this.file.length, message: '' };
    this.dernierGarde = null;
    this.surveillance = null;
    this.minuterie = null;
    this.verrou = null;
    this.envoiEnCours = false;
    this.pause = 0;
    this._surVisibilite = this._surVisibilite.bind(this);
    this._surEnLigne = this.envoyer.bind(this);
  }

  static disponible() {
    return 'geolocation' in navigator;
  }

  demarrer() {
    if (!SuiviGPS.disponible()) {
      this._majEtat({ statut: 'indisponible', message: 'Ce navigateur ne permet pas la localisation.' });
      return;
    }
    if (this.surveillance !== null) return;
    this._majEtat({ statut: 'attente', message: 'Recherche du signal GPS...' });
    this.surveillance = navigator.geolocation.watchPosition(
      this._surPosition.bind(this), this._surErreur.bind(this),
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 30000 });
    this.minuterie = setInterval(this.envoyer.bind(this), this.options.intervalleEnvoi);
    document.addEventListener('visibilitychange', this._surVisibilite);
    window.addEventListener('online', this._surEnLigne);
    this._verrouillerEcran();
  }

  /* Arrete le suivi et envoie les derniers points (a appeler avant de terminer le trajet). */
  async arreter() {
    if (this.surveillance !== null) navigator.geolocation.clearWatch(this.surveillance);
    this.surveillance = null;
    clearInterval(this.minuterie);
    document.removeEventListener('visibilitychange', this._surVisibilite);
    window.removeEventListener('online', this._surEnLigne);
    if (this.verrou) { try { await this.verrou.release(); } catch (e) { /* deja libere */ } }
    this.verrou = null;
    await this.envoyer();
    this._majEtat({ statut: 'arrete', message: '' });
  }

  _surPosition(position) {
    const c = position.coords;
    this._majEtat({ statut: 'actif', precision: c.accuracy, message: '' });
    if (c.accuracy > 1000) return;
    // Ecarte les petits sauts a l arret : on garde un point s il s est
    // deplace d au moins 10 m, ou toutes les 30 s pour montrer qu il est en ligne.
    const maintenant = position.timestamp;
    if (this.dernierGarde) {
      const d = SuiviGPS.distance(this.dernierGarde.lat, this.dernierGarde.lng, c.latitude, c.longitude);
      if (d < 10 && maintenant - this.dernierGarde.instant < 30000) return;
    }
    this.dernierGarde = { lat: c.latitude, lng: c.longitude, instant: maintenant };
    this.file.push({
      lat: Math.round(c.latitude * 1e6) / 1e6,
      lng: Math.round(c.longitude * 1e6) / 1e6,
      precision: Math.round(c.accuracy * 10) / 10,
      vitesse: (c.speed === null || isNaN(c.speed)) ? null : Math.round(c.speed * 3.6 * 10) / 10,
      cap: (c.heading === null || isNaN(c.heading)) ? null : Math.round(c.heading),
      horodatage: new Date(maintenant).toISOString()
    });
    if (this.file.length > 2000) this.file.splice(0, this.file.length - 2000);
    this._ecrireFile();
    this._majEtat({ enAttente: this.file.length });
    // Premier point : envoye tout de suite pour apparaitre sur la carte sans attendre.
    if (!this.etat.dernierEnvoi) this.envoyer();
  }

  _surErreur(erreur) {
    if (erreur.code === 1) {
      this._majEtat({ statut: 'refuse', message: 'Localisation refusee : autorisez-la dans les reglages du navigateur.' });
    } else if (erreur.code === 3) {
      this._majEtat({ statut: 'attente', message: 'Signal GPS faible, nouvel essai...' });
    } else {
      this._majEtat({ statut: 'attente', message: 'Position indisponible pour le moment.' });
    }
  }

  async envoyer() {
    if (this.envoiEnCours || !this.file.length || Date.now() < this.pause) return;
    if (!navigator.onLine) { this._majEtat({ message: 'Hors ligne : les positions seront envoyees au retour du reseau.' }); return; }
    this.envoiEnCours = true;
    const lot = this.file.slice(0, 200);
    try {
      await Store.envoyerPositions(this.trajetId, lot);
      this.file.splice(0, lot.length);
      this._ecrireFile();
      this._majEtat({ dernierEnvoi: Date.now(), enAttente: this.file.length,
        message: this.etat.statut === 'actif' ? '' : this.etat.message });
      if (this.file.length) setTimeout(this.envoyer.bind(this), 500);
    } catch (e) {
      if (e.statut === 409 || e.statut === 404) {
        // Trajet termine (ou plus accessible) : inutile de continuer.
        this.file = [];
        this._ecrireFile();
        await this.arreter();
      } else if (e.statut === 429) {
        this.pause = Date.now() + 30000;
      } else if (e.statut === 400) {
        this.file.splice(0, lot.length);  // lot refuse par le serveur : on ne le renverra pas indefiniment
        this._ecrireFile();
      } else {
        this._majEtat({ message: 'Envoi en attente (reseau).' });
      }
    } finally {
      this.envoiEnCours = false;
    }
  }

  _surVisibilite() {
    if (document.visibilityState === 'visible') {
      this._verrouillerEcran();
      this.envoyer();
    }
  }

  async _verrouillerEcran() {
    if (!('wakeLock' in navigator) || this.verrou) return;
    try {
      this.verrou = await navigator.wakeLock.request('screen');
      const moi = this;
      this.verrou.addEventListener('release', function () { moi.verrou = null; });
    } catch (e) { /* refuse (economie d energie) : le suivi continue tant que l ecran reste allume */ }
  }

  _majEtat(changements) {
    Object.assign(this.etat, changements);
    try { this.options.rappel(Object.assign({}, this.etat)); } catch (e) { /* affichage seulement */ }
  }

  _lireFile() {
    try { return JSON.parse(sessionStorage.getItem(this.cle)) || []; } catch (e) { return []; }
  }

  _ecrireFile() {
    try {
      if (this.file.length) sessionStorage.setItem(this.cle, JSON.stringify(this.file));
      else sessionStorage.removeItem(this.cle);
    } catch (e) { /* stockage plein ou interdit : la file reste en memoire */ }
  }

  static distance(lat1, lng1, lat2, lng2) {
    const r = Math.PI / 180;
    const a = Math.sin((lat2 - lat1) * r / 2) ** 2 +
      Math.cos(lat1 * r) * Math.cos(lat2 * r) * Math.sin((lng2 - lng1) * r / 2) ** 2;
    return 12742000 * Math.asin(Math.min(1, Math.sqrt(a)));
  }
}

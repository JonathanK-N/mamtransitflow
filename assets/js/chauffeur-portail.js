/* TransitFlow — portail chauffeur : mon vehicule, ma paie, mon profil
   Auteur : Jonathan K-N
   Complete l objet Chauffeur (chauffeur.js). Chaque page n est accessible
   que si l administrateur l a ouverte dans Parametres > Portail chauffeur
   (la navigation de auth.js l a deja verifie, et le serveur refuse sinon). */

Object.assign(Chauffeur, {
  /* Mon vehicule */
  async pageVehicule() {
    const d = await Store.monVehicule();
    if (!d.vehicule) {
      document.querySelector('[data-aucun]').classList.remove('tf-hidden');
      return;
    }
    const v = d.vehicule;
    const s = Format.statutVehicule(v.statut);
    document.querySelector('[data-source]').textContent = d.source === 'trajet-en-cours'
      ? 'Vehicule de votre trajet en cours' : 'Votre vehicule habituel';
    document.querySelector('[data-plaque]').textContent = v.plaque;
    document.querySelector('[data-statut]').innerHTML = '<span class="tf-pill ' + s.classe + '">' + s.texte + '</span>';
    document.querySelector('[data-modele]').textContent = v.modele + (v.annee ? ' · ' + v.annee : '');
    document.querySelector('[data-compteur]').textContent = Format.km(v.kilometrage);
    document.querySelector('[data-vehicule]').classList.remove('tf-hidden');

    if (d.entretiens.length) {
      document.querySelector('[data-entretiens]').innerHTML = d.entretiens.map(function (e) {
        const etat = Format.etatEcheance(e.echeance.etat);
        return '<li><div class="flex-fill"><strong>' + Format.echapper(e.libelle) + '</strong>' +
          '<div class="tf-meta">' + Format.resteEcheance(e.echeance) + '</div></div>' +
          '<span class="tf-pill ' + etat.classe + '">' + etat.texte + '</span></li>';
      }).join('');
      document.querySelector('[data-bloc-entretiens]').classList.remove('tf-hidden');
    }
    if (d.interventions.length) {
      document.querySelector('[data-interventions]').innerHTML = d.interventions.map(function (b) {
        const st = Format.statutBon(b.statut);
        return '<li><div class="flex-fill"><strong>' + Format.echapper(b.titre) + '</strong>' +
          '<div class="tf-meta"><span class="tf-mono">' + Format.echapper(b.id) + '</span> · prevue le ' +
          Format.dateCourte(b.datePrevue) + '</div></div>' +
          '<span class="tf-pill ' + st.classe + '">' + st.texte + '</span></li>';
      }).join('');
      document.querySelector('[data-bloc-interventions]').classList.remove('tf-hidden');
    }
  },

  /* Ma paie */
  async pagePaie() {
    const bulletins = await Store.mesBulletins();
    const corps = document.querySelector('[data-bulletins]');
    corps.innerHTML = bulletins.map(function (b) {
      return '<tr data-ligne data-bulletin-id="' + b.id + '"><td>' + Format.dateLongue(b.periode.datePaiement) + '</td>' +
        '<td class="tf-meta">' + TfPaie.periode(b.periode) + '</td><td class="tf-meta">' + TfPaie.description(b) + '</td>' +
        '<td class="text-end tf-mono">' + Format.montant(b.brut) + '</td>' +
        '<td class="text-end tf-mono" style="font-weight:600">' + Format.montant(b.net) + '</td>' +
        '<td class="text-end"><span style="font-size:13px;color:var(--tf-accent-deep)">Voir</span></td></tr>';
    }).join('') || '<tr><td colspan="6" class="tf-muted">Aucun bulletin pour le moment. Ils apparaissent ici des que ' +
      'votre employeur valide une paie.</td></tr>';
    corps.querySelectorAll('[data-bulletin-id]').forEach(function (tr) {
      tr.addEventListener('click', async function () {
        const donnees = await Store.bulletinPaie(tr.dataset.bulletinId);
        if (!donnees) return;
        const zone = document.querySelector('[data-bulletin]');
        zone.innerHTML = '<div class="d-flex justify-content-end mb-3 tf-no-print">' +
          '<button type="button" class="tf-btn tf-btn-primary" data-imprimer>Imprimer / PDF</button></div>' +
          tfRenduBulletin(donnees, { admin: false });
        zone.classList.remove('tf-hidden');
        zone.querySelector('[data-imprimer]').addEventListener('click', function () { window.print(); });
        zone.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });
  },

  /* Mon profil */
  async pageProfil() {
    const moi = this.moi;
    const entreprise = this.entreprise || {};
    document.querySelector('[data-entreprise]').textContent = entreprise.nom ? 'Chauffeur · ' + entreprise.nom : '';
    document.querySelector('[data-nom]').textContent = Format.nomComplet(moi);
    document.querySelector('[data-courriel]').textContent = moi.courriel;
    document.querySelector('[data-permis]').textContent = moi.permisNumero;
    document.querySelector('[data-permis-expiration]').textContent = Format.dateLongue(moi.permisExpiration);

    const formulaire = document.querySelector('[data-form-profil]');
    formulaire.elements.telephone.value = moi.telephone;
    formulaire.elements.adresse.value = moi.adresse;
    const modifiable = !entreprise.portail || entreprise.portail.profil;
    if (!modifiable) {
      formulaire.querySelectorAll('input').forEach(function (i) { i.readOnly = true; });
      formulaire.querySelector('[type=submit]').classList.add('tf-hidden');
      formulaire.querySelector('[data-profil-verrouille]').classList.remove('tf-hidden');
    }
    formulaire.addEventListener('submit', function (e) {
      e.preventDefault();
      if (!modifiable || !formulaire.reportValidity()) return;
      tfEnvoyer(formulaire, async function () {
        const d = new FormData(formulaire);
        await Store.majChauffeur(moi.id, { telephone: tfTexte(d, 'telephone'), adresse: tfTexte(d, 'adresse') });
        tfNotifier('Coordonnees enregistrees.', 'succes');
      });
    });

    const formMdp = document.querySelector('[data-form-mdp]');
    formMdp.addEventListener('submit', function (e) {
      e.preventDefault();
      if (!formMdp.reportValidity()) return;
      tfEnvoyer(formMdp, async function () {
        const d = new FormData(formMdp);
        await Store.changerMotDePasse(d.get('actuel'), d.get('nouveau'), d.get('confirmation'));
        formMdp.reset();
        tfNotifier('Mot de passe modifie.', 'succes');
      });
    });
  }
});

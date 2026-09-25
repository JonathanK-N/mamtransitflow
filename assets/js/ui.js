/* TransitFlow — composants d interface partages (fenetre modale)
   Auteur : Jonathan K-N

   tfModale ouvre une fenetre contenant un formulaire et gere pour la page :
   la fermeture (bouton, clic hors de la fenetre, touche Echap), le bouton
   de validation desactive pendant l envoi, et l affichage de l erreur du
   serveur DANS la fenetre (le formulaire reste ouvert pour etre corrige).

   Utilisation :
     await tfModale({
       titre: 'Relever le compteur',
       corps: '<label class="tf-field">...<input name="kilometrage"></label>',
       valider: 'Enregistrer',
       async action(donnees, formulaire) { await Store.xxx(donnees.get('kilometrage')); }
     });
   La promesse renvoie true si l action a reussi, false si la fenetre a ete fermee. */

function tfModale(options) {
  return new Promise(function (resoudre) {
    const fond = document.createElement('div');
    fond.className = 'tf-modal-backdrop';
    fond.innerHTML =
      '<form class="tf-modal" role="dialog" aria-modal="true" novalidate>' +
        '<div class="d-flex align-items-start gap-3">' +
          '<div class="flex-fill"><h2 class="tf-h2" data-modale-titre></h2>' +
          (options.sousTitre ? '<p class="tf-meta mt-1 mb-0" data-modale-sous-titre></p>' : '') + '</div>' +
          '<button type="button" class="tf-modal-close" aria-label="Fermer" data-fermer>✕</button>' +
        '</div>' +
        '<div class="tf-form-error tf-hidden" data-modale-erreur role="alert"></div>' +
        '<div class="d-flex flex-column gap-3" data-modale-corps></div>' +
        '<div class="d-flex gap-3 justify-content-end flex-wrap">' +
          '<button type="button" class="tf-btn tf-btn-ghost" data-fermer>Annuler</button>' +
          '<button type="submit" class="tf-btn ' + (options.danger ? 'tf-btn-dark' : 'tf-btn-primary') + '"></button>' +
        '</div>' +
      '</form>';
    const formulaire = fond.querySelector('form');
    fond.querySelector('[data-modale-titre]').textContent = options.titre;
    if (options.sousTitre) fond.querySelector('[data-modale-sous-titre]').textContent = options.sousTitre;
    fond.querySelector('[data-modale-corps]').innerHTML = options.corps;
    const bouton = formulaire.querySelector('[type=submit]');
    bouton.textContent = options.valider || 'Enregistrer';
    const zoneErreur = fond.querySelector('[data-modale-erreur]');

    function fermer(resultat) {
      document.removeEventListener('keydown', surTouche);
      fond.remove();
      resoudre(resultat);
    }
    function surTouche(e) { if (e.key === 'Escape' && !bouton.disabled) fermer(false); }

    fond.querySelectorAll('[data-fermer]').forEach(function (b) {
      b.addEventListener('click', function () { fermer(false); });
    });
    fond.addEventListener('mousedown', function (e) { if (e.target === fond) fermer(false); });
    document.addEventListener('keydown', surTouche);

    formulaire.addEventListener('submit', async function (e) {
      e.preventDefault();
      if (!formulaire.reportValidity()) return;
      zoneErreur.classList.add('tf-hidden');
      bouton.disabled = true;
      try {
        await options.action(new FormData(formulaire), formulaire);
        fermer(true);
      } catch (erreur) {
        zoneErreur.textContent = erreur.message;
        zoneErreur.classList.remove('tf-hidden');
        bouton.disabled = false;
      }
    });

    document.body.appendChild(fond);
    if (options.preparer) options.preparer(formulaire);
    const premier = formulaire.querySelector('[data-modale-corps] input, [data-modale-corps] select, ' +
      '[data-modale-corps] textarea');
    if (premier) premier.focus();
  });
}

/* Petit raccourci pour les champs de formulaire des modales. */
function tfChamp(libelle, controle, note) {
  return '<label class="tf-field"><span class="tf-label">' + libelle + '</span>' + controle +
    (note ? '<span class="tf-meta">' + note + '</span>' : '') + '</label>';
}

/* Valeur texte nettoyee d un FormData ('' si absente). */
function tfTexte(donnees, nom) {
  return String(donnees.get(nom) || '').trim();
}

/* Nombre d un FormData, ou null si le champ est vide. */
function tfNombre(donnees, nom) {
  const valeur = tfTexte(donnees, nom).replace(/\s/g, '').replace(',', '.');
  return valeur === '' ? null : Number(valeur);
}

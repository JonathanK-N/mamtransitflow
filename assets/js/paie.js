/* TransitFlow — affichage de la paie, partage par l administrateur et le portail chauffeur
   Auteur : Jonathan K-N

   tfRenduBulletin() produit un bulletin de paie imprimable (bouton
   "Imprimer / PDF" : le navigateur enregistre en PDF). Le CSS d impression
   (transitflow.css, @media print) masque tout le reste de la page. */

const TfPaie = {
  statut(statut) {
    return {
      brouillon: { texte: 'Brouillon', classe: 'warn' },
      validee: { texte: 'Validee', classe: 'ok' },
      payee: { texte: 'Payee', classe: 'muted' }
    }[statut] || { texte: statut, classe: '' };
  },

  mode(mode) {
    return { horaire: 'A l heure', trajet: 'Au trajet', fixe: 'Salaire fixe' }[mode] || mode;
  },

  periode(p) {
    return Format.dateCourte(p.debut) + ' au ' + Format.dateCourte(p.fin);
  },

  nombre(valeur, decimales) {
    if (valeur === null || valeur === undefined) return '';
    return Number(valeur).toLocaleString('fr-CA', { minimumFractionDigits: decimales || 0,
      maximumFractionDigits: decimales === undefined ? 2 : decimales });
  },

  /* Mode et base d un bulletin : "A l heure · 40 h + 5 h sup.", "Au trajet · 12 trajets", "Salaire fixe". */
  description(b) {
    return b.mode === 'fixe' ? 'Salaire fixe' : TfPaie.mode(b.mode) + ' · ' + TfPaie.base(b);
  },

  /* Base de calcul d un bulletin : "40 h + 5 h sup.", "12 trajets", "Salaire fixe". */
  base(b) {
    if (b.mode === 'horaire') {
      return TfPaie.nombre(b.heuresRegulieres) + ' h' + (b.heuresSup ? ' + ' + TfPaie.nombre(b.heuresSup) + ' h sup.' : '');
    }
    if (b.mode === 'trajet') return b.nombreTrajets + ' trajet' + (b.nombreTrajets > 1 ? 's' : '');
    return 'Salaire fixe';
  }
};

/*
 * donnees : reponse de GET /api/paie/bulletins/<id> ({bulletin, employeur, employe}).
 * options.admin : affiche les cotisations employeur et, si la paie est en
 * brouillon, les boutons de suppression des lignes manuelles ([data-supprimer-ligne]).
 */
function tfRenduBulletin(donnees, options) {
  options = options || {};
  const b = donnees.bulletin;
  const e = donnees.employeur;
  const modifiable = options.admin && b.periode.statut === 'brouillon';
  const ligne = function (l) {
    return '<tr><td>' + Format.echapper(l.libelle) +
      (l.manuelle ? ' <span class="tf-meta">(ajout manuel' + (l.genre === 'gain' && !l.imposable ? ', non imposable' : '') +
        ')</span>' : '') + '</td>' +
      '<td class="text-end tf-mono">' + (l.quantite !== null && l.genre === 'gain' ? TfPaie.nombre(l.quantite) : '') + '</td>' +
      '<td class="text-end tf-mono">' + (l.taux !== null ? TfPaie.nombre(l.taux, l.genre === 'gain' ? 2 : 3) +
        (l.genre === 'gain' ? '' : ' %') : '') + '</td>' +
      '<td class="text-end tf-mono">' + Format.montant(l.montant) + '</td>' +
      (modifiable ? '<td class="text-end" style="width:40px">' + (l.manuelle
        ? '<button type="button" class="tf-lien-suppr" title="Retirer cette ligne" data-supprimer-ligne="' + l.id +
          '">✕</button>' : '') + '</td>' : '') + '</tr>';
  };
  const section = function (titre, genre) {
    const lignes = b.lignes.filter(function (l) { return l.genre === genre; });
    if (!lignes.length) return '';
    return '<tr class="tf-bulletin-section"><td colspan="' + (modifiable ? 5 : 4) + '">' + titre + '</td></tr>' +
      lignes.map(ligne).join('');
  };
  const adresse = [e.adresse, [e.ville, e.province, e.codePostal].filter(Boolean).join(' ')].filter(Boolean).join(', ');
  const statut = TfPaie.statut(b.periode.statut);
  return '<article class="tf-bulletin tf-card">' +
    '<header class="d-flex flex-wrap justify-content-between gap-3">' +
      '<div><div class="tf-bulletin-employeur">' + Format.echapper(e.nom) + '</div>' +
        '<div class="tf-meta">' + Format.echapper(adresse) + (e.neq ? ' · NEQ ' + Format.echapper(e.neq) : '') + '</div></div>' +
      '<div class="text-end"><div class="tf-h3">Bulletin de paie</div>' +
        '<div class="tf-meta tf-mono">' + Format.echapper(b.id) + ' · ' + Format.echapper(b.periode.id) + '</div>' +
        (b.periode.statut === 'brouillon' ? '<span class="tf-pill warn mt-1">Brouillon</span>' : '') + '</div>' +
    '</header>' +
    '<div class="row g-3 tf-bulletin-infos">' +
      '<div class="col-6 col-md-3"><div class="tf-meta">Employe</div><strong>' + Format.echapper(donnees.employe.nom) + '</strong></div>' +
      '<div class="col-6 col-md-3"><div class="tf-meta">Periode</div>' + TfPaie.periode(b.periode) + '</div>' +
      '<div class="col-6 col-md-3"><div class="tf-meta">Date de paiement</div>' + Format.dateLongue(b.periode.datePaiement) + '</div>' +
      '<div class="col-6 col-md-3"><div class="tf-meta">Base</div>' + TfPaie.description(b) + '</div>' +
    '</div>' +
    '<table class="tf-table tf-bulletin-table"><thead><tr><th>DESCRIPTION</th><th class="text-end">QUANTITE</th>' +
      '<th class="text-end">TAUX</th><th class="text-end">MONTANT</th>' + (modifiable ? '<th></th>' : '') + '</tr></thead><tbody>' +
      section('Gains', 'gain') + section('Retenues', 'retenue') +
      (options.admin ? section('Cotisations de l employeur (ne reduisent pas le salaire)', 'employeur') : '') +
    '</tbody></table>' +
    '<div class="tf-bulletin-totaux">' +
      '<div><span class="tf-meta">Salaire brut</span><span class="tf-mono">' + Format.montant(b.brut) + '</span></div>' +
      '<div><span class="tf-meta">Retenues</span><span class="tf-mono">− ' + Format.montant(b.retenues) + '</span></div>' +
      '<div class="net"><span>Net a payer</span><span class="tf-mono">' + Format.montant(b.net) + '</span></div>' +
      (options.admin ? '<div><span class="tf-meta">Cout pour l employeur</span><span class="tf-mono">' +
        Format.montant(b.coutEmployeur) + '</span></div>' : '') +
    '</div>' +
    '<p class="tf-meta mb-0" style="font-size:12px">Statut de la paie : ' + statut.texte.toLowerCase() +
      '. Document genere par TransitFlow.</p>' +
  '</article>';
}

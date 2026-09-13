"""
TransitFlow — Routes trajets
Auteur : Jonathan K-N

Equivalent des ecrans chauffeur/trajet-nouveau.html, chauffeur/trajet-en-cours.html,
chauffeur/mes-trajets.html et admin/trajet(s).html :
  GET  /api/trajets                  -> liste (avec filtres statut/chauffeurId)
  GET  /api/trajets/en-cours/<id>    -> trajet en cours d un chauffeur (ou aucun)
  GET  /api/trajets/<id>             -> detail d un trajet
  POST /api/trajets                  -> demarrer un trajet (reserve au chauffeur)
  POST /api/trajets/<id>/arrets      -> ajouter un arret (reserve au chauffeur proprietaire)
  POST /api/trajets/<id>/terminer    -> terminer le trajet (reserve au chauffeur proprietaire)

Pour les 3 dernieres routes, on verifie en plus que le trajet
appartient bien au chauffeur connecte (t['chauffeurId'] == session['chauffeurId']) :
un chauffeur ne doit pas pouvoir modifier le trajet d un collegue.
"""

from flask import Blueprint, jsonify, request

from ..store import Store
from . import exiger

bp = Blueprint('trajets', __name__, url_prefix='/api/trajets')


@bp.get('')
@exiger()
def lister():
    """Liste des trajets, du plus recent au plus ancien."""
    filtre = {'statut': request.args.get('statut', ''), 'chauffeurId': request.args.get('chauffeurId', '')}
    return jsonify({'ok': True, 'trajets': Store.trajets(filtre)})


@bp.get('/en-cours/<chauffeur_id>')
@exiger()
def en_cours(chauffeur_id):
    """Trajet actuellement en cours pour ce chauffeur (utilise par chauffeur/mes-trajets.html)."""
    return jsonify({'ok': True, 'trajet': Store.trajet_en_cours(chauffeur_id)})


@bp.get('/<id_>')
@exiger()
def obtenir(id_):
    """Detail d un trajet, ou 404 s il n existe pas."""
    t = Store.trajet(id_)
    if not t:
        return jsonify({'ok': False, 'message': 'Trajet introuvable.'}), 404
    return jsonify({'ok': True, 'trajet': t})


@bp.post('')
@exiger('chauffeur')
def creer():
    """
    Demarre un nouveau trajet pour le chauffeur connecte. Le chauffeurId
    vient toujours de la session (jamais du corps de la requete) pour
    qu un chauffeur ne puisse pas creer un trajet au nom d un autre.
    Une fois le trajet cree, le chauffeur passe automatiquement au
    statut 'en-trajet'.
    """
    session = request.session
    payload = request.get_json(silent=True) or {}
    for champ in ('plaque', 'depart', 'arrivee', 'debut', 'finPrevue'):
        if not str(payload.get(champ, '')).strip():
            return jsonify({'ok': False, 'message': 'Champ manquant : ' + champ}), 400

    trajet = {
        'chauffeurId': session['chauffeurId'],
        'plaque': payload['plaque'],
        'depart': payload['depart'].strip(),
        'departAdresse': (payload.get('departAdresse') or '').strip(),
        'arrivee': payload['arrivee'].strip(),
        'debut': payload['debut'],
        'finPrevue': payload['finPrevue']
    }
    trajet = Store.ajouter_trajet(trajet)
    Store.maj_chauffeur(session['chauffeurId'], {'statut': 'en-trajet'})
    return jsonify({'ok': True, 'trajet': trajet}), 201


@bp.post('/<id_>/arrets')
@exiger('chauffeur')
def ajouter_arret(id_):
    """Ajoute un arret au trajet, seulement si ce trajet appartient au chauffeur connecte."""
    session = request.session
    t = Store.trajet(id_)
    if not t:
        return jsonify({'ok': False, 'message': 'Trajet introuvable.'}), 404
    if t['chauffeurId'] != session['chauffeurId']:
        return jsonify({'ok': False, 'message': 'Acces refuse.'}), 403

    payload = request.get_json(silent=True) or {}
    if not str(payload.get('lieu', '')).strip() or not str(payload.get('heure', '')).strip():
        return jsonify({'ok': False, 'message': 'Lieu et heure requis.'}), 400

    arret = {'lieu': payload['lieu'].strip(), 'heure': payload['heure'],
              'note': (payload.get('note') or '').strip()}
    return jsonify({'ok': True, 'trajet': Store.ajouter_arret(id_, arret)})


@bp.post('/<id_>/terminer')
@exiger('chauffeur')
def terminer(id_):
    """Termine le trajet, seulement si ce trajet appartient au chauffeur connecte."""
    session = request.session
    t = Store.trajet(id_)
    if not t:
        return jsonify({'ok': False, 'message': 'Trajet introuvable.'}), 404
    if t['chauffeurId'] != session['chauffeurId']:
        return jsonify({'ok': False, 'message': 'Acces refuse.'}), 403
    return jsonify({'ok': True, 'trajet': Store.terminer_trajet(id_)})

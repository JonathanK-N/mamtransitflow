"""TransitFlow — routes trajets (equivalent des ecrans trajet*.html)"""

from flask import Blueprint, jsonify, request

from ..store import Store
from . import exiger

bp = Blueprint('trajets', __name__, url_prefix='/api/trajets')


@bp.get('')
@exiger()
def lister():
    filtre = {'statut': request.args.get('statut', ''), 'chauffeurId': request.args.get('chauffeurId', '')}
    return jsonify({'ok': True, 'trajets': Store.trajets(filtre)})


@bp.get('/en-cours/<chauffeur_id>')
@exiger()
def en_cours(chauffeur_id):
    return jsonify({'ok': True, 'trajet': Store.trajet_en_cours(chauffeur_id)})


@bp.get('/<id_>')
@exiger()
def obtenir(id_):
    t = Store.trajet(id_)
    if not t:
        return jsonify({'ok': False, 'message': 'Trajet introuvable.'}), 404
    return jsonify({'ok': True, 'trajet': t})


@bp.post('')
@exiger('chauffeur')
def creer():
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
    session = request.session
    t = Store.trajet(id_)
    if not t:
        return jsonify({'ok': False, 'message': 'Trajet introuvable.'}), 404
    if t['chauffeurId'] != session['chauffeurId']:
        return jsonify({'ok': False, 'message': 'Acces refuse.'}), 403
    return jsonify({'ok': True, 'trajet': Store.terminer_trajet(id_)})

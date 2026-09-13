"""TransitFlow — routes chauffeurs (equivalent des ecrans admin/chauffeur*.html)"""

from flask import Blueprint, jsonify, request

from ..store import Store
from . import exiger

bp = Blueprint('chauffeurs', __name__, url_prefix='/api/chauffeurs')

CHAMPS_REQUIS = ['prenom', 'nom', 'age', 'telephone', 'courriel', 'adresse',
                  'permisNumero', 'permisExpiration', 'plaqueHabituelle']


@bp.get('')
@exiger()
def lister():
    filtre = {'recherche': request.args.get('recherche', ''), 'statut': request.args.get('statut', '')}
    return jsonify({'ok': True, 'chauffeurs': Store.chauffeurs(filtre)})


@bp.get('/<id_>')
@exiger()
def obtenir(id_):
    c = Store.chauffeur(id_)
    if not c:
        return jsonify({'ok': False, 'message': 'Chauffeur introuvable.'}), 404
    return jsonify({'ok': True, 'chauffeur': c})


@bp.post('')
@exiger('admin')
def creer():
    payload = request.get_json(silent=True) or {}
    manquants = [champ for champ in CHAMPS_REQUIS if not str(payload.get(champ, '')).strip()]
    if manquants:
        return jsonify({'ok': False, 'message': 'Champs manquants : ' + ', '.join(manquants)}), 400

    chauffeur = {
        'prenom': payload['prenom'].strip(),
        'nom': payload['nom'].strip(),
        'age': int(payload['age']),
        'telephone': payload['telephone'].strip(),
        'courriel': payload['courriel'].strip(),
        'adresse': payload['adresse'].strip(),
        'permisNumero': payload['permisNumero'].strip(),
        'permisExpiration': payload['permisExpiration'],
        'statut': payload.get('statut') or 'disponible',
        'plaqueHabituelle': payload['plaqueHabituelle']
    }
    return jsonify({'ok': True, 'chauffeur': Store.ajouter_chauffeur(chauffeur)}), 201


@bp.patch('/<id_>')
@exiger('admin')
def modifier(id_):
    payload = request.get_json(silent=True) or {}
    chauffeur = Store.maj_chauffeur(id_, payload)
    if not chauffeur:
        return jsonify({'ok': False, 'message': 'Chauffeur introuvable.'}), 404
    return jsonify({'ok': True, 'chauffeur': chauffeur})

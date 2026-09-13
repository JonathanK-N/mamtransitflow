"""
TransitFlow — Routes incidents
Auteur : Jonathan K-N

Equivalent des ecrans chauffeur/incident-nouveau.html et admin/incidents.html :
  GET  /api/incidents             -> liste (avec filtres type/statut/chauffeurId)
  GET  /api/incidents/<id>        -> detail d un incident
  POST /api/incidents             -> signaler un incident (reserve au chauffeur)
  POST /api/incidents/<id>/traiter -> marquer comme traite (reserve a l administrateur)
"""

from flask import Blueprint, jsonify, request

from .. import config
from ..store import Store
from . import exiger

bp = Blueprint('incidents', __name__, url_prefix='/api/incidents')


@bp.get('')
@exiger()
def lister():
    """Liste des incidents, du plus recent au plus ancien."""
    filtre = {
        'type': request.args.get('type', ''),
        'statut': request.args.get('statut', ''),
        'chauffeurId': request.args.get('chauffeurId', '')
    }
    return jsonify({'ok': True, 'incidents': Store.incidents(filtre)})


@bp.get('/<id_>')
@exiger()
def obtenir(id_):
    """Detail d un incident, ou 404 s il n existe pas."""
    i = Store.incident(id_)
    if not i:
        return jsonify({'ok': False, 'message': 'Incident introuvable.'}), 404
    return jsonify({'ok': True, 'incident': i})


@bp.post('')
@exiger('chauffeur')
def creer():
    """
    Signale un nouvel incident pour le chauffeur connecte (chauffeurId
    vient toujours de la session, jamais du corps de la requete).
    Le trajet associe (trajetId) est facultatif -- un incident peut
    etre signale sans trajet en cours -- mais s il est fourni, on
    verifie qu il existe vraiment. La date, si absente, prend la date
    "figee" de la demo (config.AUJOURD_HUI).
    """
    session = request.session
    payload = request.get_json(silent=True) or {}
    for champ in ('type', 'titre', 'description', 'lieu', 'heure'):
        if not str(payload.get(champ, '')).strip():
            return jsonify({'ok': False, 'message': 'Champ manquant : ' + champ}), 400
    if payload['type'] not in ('technique', 'route'):
        return jsonify({'ok': False, 'message': 'Type d incident invalide.'}), 400

    trajet_id = payload.get('trajetId')
    if trajet_id and not Store.trajet(trajet_id):
        return jsonify({'ok': False, 'message': 'Trajet introuvable.'}), 404

    incident = {
        'trajetId': trajet_id,
        'chauffeurId': session['chauffeurId'],
        'type': payload['type'],
        'titre': payload['titre'].strip(),
        'description': payload['description'].strip(),
        'lieu': payload['lieu'].strip(),
        'date': payload.get('date') or config.AUJOURD_HUI,
        'heure': payload['heure']
    }
    return jsonify({'ok': True, 'incident': Store.ajouter_incident(incident)}), 201


@bp.post('/<id_>/traiter')
@exiger('admin')
def traiter(id_):
    """Marque un incident comme traite. Reserve a l administrateur."""
    incident = Store.traiter_incident(id_)
    if not incident:
        return jsonify({'ok': False, 'message': 'Incident introuvable.'}), 404
    return jsonify({'ok': True, 'incident': incident})

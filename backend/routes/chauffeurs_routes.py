"""
TransitFlow — Routes chauffeurs
Auteur : Jonathan K-N

Equivalent des ecrans admin/chauffeurs.html, admin/chauffeur.html et
admin/chauffeur-nouveau.html :
  GET   /api/chauffeurs        -> liste (avec filtres recherche/statut)
  GET   /api/chauffeurs/<id>   -> fiche d un chauffeur
  POST  /api/chauffeurs        -> creation (reserve a l administrateur)
  PATCH /api/chauffeurs/<id>   -> mise a jour partielle (reserve a l administrateur)
"""

from flask import Blueprint, jsonify, request

from ..store import Store
from . import exiger

bp = Blueprint('chauffeurs', __name__, url_prefix='/api/chauffeurs')

# Champs obligatoires pour creer un chauffeur (voir le formulaire de
# admin/chauffeur-nouveau.html).
CHAMPS_REQUIS = ['prenom', 'nom', 'age', 'telephone', 'courriel', 'adresse',
                  'permisNumero', 'permisExpiration', 'plaqueHabituelle']


@bp.get('')
@exiger()
def lister():
    """Liste des chauffeurs. Accessible a tout utilisateur connecte (admin ou chauffeur)."""
    filtre = {'recherche': request.args.get('recherche', ''), 'statut': request.args.get('statut', '')}
    return jsonify({'ok': True, 'chauffeurs': Store.chauffeurs(filtre)})


@bp.get('/<id_>')
@exiger()
def obtenir(id_):
    """Fiche d un chauffeur precis, ou 404 s il n existe pas."""
    c = Store.chauffeur(id_)
    if not c:
        return jsonify({'ok': False, 'message': 'Chauffeur introuvable.'}), 404
    return jsonify({'ok': True, 'chauffeur': c})


@bp.post('')
@exiger('admin')
def creer():
    """
    Cree un nouveau chauffeur. Reserve a l administrateur (@exiger('admin')).
    On verifie d abord que tous les champs obligatoires sont presents
    avant de construire l objet chauffeur transmis a Store.
    """
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
    """Met a jour un ou plusieurs champs d un chauffeur existant. Reserve a l administrateur."""
    payload = request.get_json(silent=True) or {}
    chauffeur = Store.maj_chauffeur(id_, payload)
    if not chauffeur:
        return jsonify({'ok': False, 'message': 'Chauffeur introuvable.'}), 404
    return jsonify({'ok': True, 'chauffeur': chauffeur})

"""
TransitFlow — Vehicules et indicateurs du tableau de bord
Auteur : Jonathan K-N

Deux petites routes qui ne meritaient pas chacune leur propre fichier :
  GET /api/vehicules    -> liste des vehicules de la flotte
  GET /api/indicateurs  -> chiffres du tableau de bord (reserve a l administrateur)
"""

from flask import Blueprint, jsonify

from ..store import Store
from . import exiger

bp = Blueprint('divers', __name__, url_prefix='/api')


@bp.get('/vehicules')
@exiger()
def vehicules():
    """Liste des vehicules (plaque + modele), utilisee par chauffeur/trajet-nouveau.html."""
    return jsonify({'ok': True, 'vehicules': Store.vehicules()})


@bp.get('/indicateurs')
@exiger('admin')
def indicateurs():
    """Chiffres du tableau de bord (admin/tableau-de-bord.html). Reserve a l administrateur."""
    return jsonify({'ok': True, 'indicateurs': Store.indicateurs()})

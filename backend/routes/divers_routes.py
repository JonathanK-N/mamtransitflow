"""TransitFlow — vehicules et indicateurs du tableau de bord"""

from flask import Blueprint, jsonify

from ..store import Store
from . import exiger

bp = Blueprint('divers', __name__, url_prefix='/api')


@bp.get('/vehicules')
@exiger()
def vehicules():
    return jsonify({'ok': True, 'vehicules': Store.vehicules()})


@bp.get('/indicateurs')
@exiger('admin')
def indicateurs():
    return jsonify({'ok': True, 'indicateurs': Store.indicateurs()})

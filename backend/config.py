"""TransitFlow — configuration du serveur"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'data', 'db.json')

MOT_DE_PASSE_DEMO = 'demo'

# Horloge figee pour la demo (memes valeurs que le front-end)
AUJOURD_HUI = '2026-09-12'
MAINTENANT = '2026-09-12T09:02'
LIMITE_PERMIS = '2026-11-11'

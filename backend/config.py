"""
TransitFlow — Configuration du serveur
Auteur : Jonathan K-N

Ce fichier regroupe les constantes utilisees par tout le backend :
- ou se trouve le fichier de donnees (notre "base de donnees" en JSON) ;
- le mot de passe de demonstration accepte pour tous les comptes ;
- l horloge figee utilisee pour les indicateurs, afin que les dates
  affichees restent coherentes avec celles utilisees cote front-end
  (assets/js/format.js utilise les memes valeurs).
"""

import os

# Dossier qui contient ce fichier (backend/), utilise pour calculer
# le chemin du fichier de donnees de maniere fiable peu importe d ou
# le serveur est lance.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Fichier JSON qui sert de "base de donnees" : Store (voir store.py)
# lit et ecrit dedans a chaque requete. Il est recree automatiquement
# s il n existe pas encore.
DATA_FILE = os.path.join(BASE_DIR, 'data', 'db.json')

# Mot de passe unique accepte pour tous les comptes de demonstration
# (voir COMPTES dans auth.py). Pas de vraie gestion de mot de passe
# ici puisque c est un projet de demonstration.
MOT_DE_PASSE_DEMO = 'demo'

# Horloge figee pour la demo (memes valeurs que le front-end) :
# plutot que d utiliser la date reelle du serveur, on fige "aujourd hui"
# a une date fixe pour que les indicateurs du tableau de bord restent
# previsibles et coherents avec les exemples utilises dans le front-end.
AUJOURD_HUI = '2026-09-12'
MAINTENANT = '2026-09-12T09:02'
LIMITE_PERMIS = '2026-11-11'

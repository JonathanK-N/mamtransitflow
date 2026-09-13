"""
TransitFlow — Comptes et sessions
Auteur : Jonathan K-N

Gere tout ce qui touche a l authentification cote serveur :
- la liste des comptes de demonstration (COMPTES) ;
- la verification du courriel / mot de passe / role a la connexion ;
- la creation d un "jeton" de session apres une connexion reussie,
  et sa verification a chaque requete protegee de l API.

C est l equivalent cote serveur de assets/js/auth.js, sauf qu ici la
"session" ne vit pas dans le navigateur : elle est gardee en memoire
sur le serveur (_SESSIONS) et retrouvee grace au jeton envoye par le
front-end dans l entete HTTP "Authorization: Bearer <jeton>".
"""

import secrets
import threading

from . import config
from .store import Store

# Comptes de demonstration : un seul mot de passe pour tous ('demo',
# voir config.MOT_DE_PASSE_DEMO). Les comptes 'chauffeur' pointent
# vers une fiche chauffeur (chauffeurId) creee via l API /api/chauffeurs ;
# tant qu aucune fiche ne porte cet id, la connexion fonctionne quand
# meme mais le nom affiche est "Inconnu" (voir _nom_complet plus bas).
COMPTES = [
    {'courriel': 'a.tremblay@transitflow.ca', 'role': 'admin', 'nom': 'Alex Tremblay', 'initiales': 'AT'},
    {'courriel': 'a.diallo@transitflow.ca', 'role': 'chauffeur', 'chauffeurId': 'c1'},
    {'courriel': 'm.traore@transitflow.ca', 'role': 'chauffeur', 'chauffeurId': 'c2'},
    {'courriel': 's.fortin@transitflow.ca', 'role': 'chauffeur', 'chauffeurId': 'c3'},
    {'courriel': 'm.barry@transitflow.ca', 'role': 'chauffeur', 'chauffeurId': 'c4'},
    {'courriel': 'Mamadou.Barry@USherbrooke.ca', 'role': 'admin', 'chauffeurId': 'c5',
     'nom': 'Mamadou Barry', 'initiales': 'MB'}
]

# Verrou pour proteger l acces a _SESSIONS quand plusieurs requetes
# arrivent en meme temps (meme logique que le verrou dans store.py).
_verrou = threading.Lock()

# Dictionnaire "jeton -> session" garde en memoire vive du serveur.
# Simple et suffisant pour une demo : si le serveur redemarre, tout le
# monde doit juste se reconnecter.
_SESSIONS = {}


def _initiales(chauffeur):
    """Renvoie les initiales (ex. 'AD' pour Aminata Diallo), ou '??' si le chauffeur est introuvable."""
    if not chauffeur:
        return '??'
    return (chauffeur['prenom'][0] + chauffeur['nom'][0]).upper()


def _nom_complet(chauffeur):
    """Renvoie 'Prenom Nom', ou 'Inconnu' si le chauffeur est introuvable."""
    return f"{chauffeur['prenom']} {chauffeur['nom']}" if chauffeur else 'Inconnu'


def connecter(courriel, mot_de_passe, role=None):
    """
    Verifie les identifiants et renvoie soit une erreur ({'ok': False, 'message': ...}),
    soit la session a creer ({'ok': True, 'session': {...}}).

    Etapes de verification, dans l ordre :
    1. le courriel doit correspondre a un compte de COMPTES ;
    2. le mot de passe doit etre celui de la demo ;
    3. si un role est demande (ex. le bouton "Chauffeur" a ete choisi
       sur la page de connexion), il doit correspondre au role du compte.

    Pour un compte chauffeur, on va chercher sa fiche dans le Store
    pour recuperer son vrai nom/initiales plutot que d afficher juste
    son courriel.
    """
    compte = next((c for c in COMPTES
                   if c['courriel'].lower() == str(courriel or '').strip().lower()), None)
    if not compte:
        return {'ok': False, 'message': 'Aucun compte ne correspond a ce courriel.'}
    if mot_de_passe != config.MOT_DE_PASSE_DEMO:
        return {'ok': False, 'message': 'Mot de passe incorrect.'}
    if role and compte['role'] != role:
        return {'ok': False, 'message': 'Ce compte n est pas un compte ' + role + '.'}

    session = dict(compte)
    if compte['role'] == 'chauffeur':
        c = Store.chauffeur(compte['chauffeurId'])
        session['nom'] = _nom_complet(c)
        session['initiales'] = _initiales(c)
    return {'ok': True, 'session': session}


def creer_jeton(session):
    """
    Genere un jeton aleatoire et l associe a la session en memoire.
    Ce jeton est renvoye au front-end, qui devra le renvoyer dans
    l entete Authorization de chaque requete pour prouver qui il est.
    """
    jeton = secrets.token_hex(16)
    with _verrou:
        _SESSIONS[jeton] = session
    return jeton


def obtenir_session(jeton):
    """Retrouve la session associee a un jeton, ou None si le jeton est invalide/expire."""
    with _verrou:
        return _SESSIONS.get(jeton)


def supprimer_jeton(jeton):
    """Invalide un jeton (utilise a la deconnexion)."""
    with _verrou:
        _SESSIONS.pop(jeton, None)


def accueil(session):
    """Page vers laquelle rediriger juste apres la connexion, selon le role."""
    return 'admin/tableau-de-bord.html' if session['role'] == 'admin' else 'chauffeur/mes-trajets.html'

"""
TransitFlow — Donnees et persistance serveur
Auteur : Jonathan K-N

Ce fichier est l equivalent cote serveur de assets/js/store.js : au
lieu d enregistrer les donnees dans le localStorage du navigateur, on
les enregistre dans un fichier JSON sur le serveur (voir DATA_FILE
dans config.py). Toutes les routes de l API (dossier routes/) passent
par la classe Store ci-dessous pour lire ou modifier les donnees.

La structure des donnees est toujours la meme :
{
  "chauffeurs": [...],
  "trajets": [...],
  "incidents": [...],
  "vehicules": [...]
}
"""

import json
import os
import threading
from datetime import datetime

from . import config

# Un verrou (lock) pour eviter que deux requetes arrivant en meme
# temps ne lisent/ecrivent le fichier JSON en meme temps et corrompent
# les donnees (Flask peut traiter plusieurs requetes en parallele).
_verrou = threading.Lock()


def _structure_vide():
    """Structure de depart quand il n y a encore aucune donnee (pas de seed)."""
    return {'chauffeurs': [], 'trajets': [], 'incidents': [], 'vehicules': []}


def _lire():
    """Lit le fichier JSON et le recree vide s il n existe pas ou est corrompu."""
    if not os.path.exists(config.DATA_FILE):
        donnees = _structure_vide()
        _ecrire(donnees)
        return donnees
    try:
        with open(config.DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        # Fichier illisible ou mal forme : on repart d une base vide
        # plutot que de faire planter le serveur.
        donnees = _structure_vide()
        _ecrire(donnees)
        return donnees


def _ecrire(donnees):
    """Ecrit la structure complete dans le fichier JSON (cree le dossier au besoin)."""
    os.makedirs(os.path.dirname(config.DATA_FILE), exist_ok=True)
    with open(config.DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(donnees, f, ensure_ascii=False, indent=2)


class Store:
    """
    Point d entree unique pour lire/ecrire les donnees.
    Toutes les methodes sont statiques/de classe : Store ne garde rien
    en memoire entre deux appels, tout est relu depuis le fichier a
    chaque fois (comme le ferait une vraie base de donnees).
    """

    @staticmethod
    def load():
        """Renvoie la structure complete (chauffeurs, trajets, incidents, vehicules)."""
        with _verrou:
            return _lire()

    @staticmethod
    def save(donnees):
        """Enregistre la structure complete sur disque."""
        with _verrou:
            _ecrire(donnees)

    @classmethod
    def reinitialiser(cls):
        """Supprime le fichier de donnees et repart d une base vide (utile en debogage)."""
        with _verrou:
            if os.path.exists(config.DATA_FILE):
                os.remove(config.DATA_FILE)
            return _lire()

    # ---- Chauffeurs ----------------------------------------------------
    @classmethod
    def chauffeurs(cls, filtre=None):
        """
        Liste des chauffeurs, avec filtre optionnel :
        - filtre['recherche'] : texte cherche dans prenom/nom/telephone/courriel
        - filtre['statut']    : 'disponible' / 'en-trajet' / 'hors-service' / 'tous'
        """
        liste = cls.load()['chauffeurs']
        if not filtre:
            return liste
        q = (filtre.get('recherche') or '').strip().lower()
        statut = filtre.get('statut')

        def correspond(c):
            ok_statut = not statut or statut == 'tous' or c['statut'] == statut
            texte = (c['prenom'] + ' ' + c['nom'] + ' ' + c['telephone'] + ' ' + c['courriel']).lower()
            return ok_statut and (not q or q in texte)

        return [c for c in liste if correspond(c)]

    @classmethod
    def chauffeur(cls, id_):
        """Renvoie un chauffeur par son id, ou None s il n existe pas."""
        return next((c for c in cls.load()['chauffeurs'] if c['id'] == id_), None)

    @classmethod
    def ajouter_chauffeur(cls, chauffeur):
        """
        Cree un nouveau chauffeur. L id est genere automatiquement
        (c1, c2, c3, ...) a partir du nombre de chauffeurs existants,
        et le statut par defaut est 'disponible'.
        """
        d = cls.load()
        chauffeur['id'] = 'c' + str(len(d['chauffeurs']) + 1)
        chauffeur['statut'] = chauffeur.get('statut') or 'disponible'
        chauffeur['creeLe'] = datetime.utcnow().strftime('%Y-%m-%d')
        d['chauffeurs'].append(chauffeur)
        cls.save(d)
        return chauffeur

    @classmethod
    def maj_chauffeur(cls, id_, champs):
        """Met a jour un ou plusieurs champs d un chauffeur existant (ex. son statut)."""
        d = cls.load()
        c = next((x for x in d['chauffeurs'] if x['id'] == id_), None)
        if not c:
            return None
        c.update(champs)
        cls.save(d)
        return c

    # ---- Trajets ---------------------------------------------------------
    @classmethod
    def trajets(cls, filtre=None):
        """
        Liste des trajets, du plus recent au plus ancien, avec filtre optionnel :
        - filtre['statut']      : 'en-cours' / 'termine' / 'planifie' / 'tous'
        - filtre['chauffeurId'] : ne garder que les trajets de ce chauffeur
        """
        liste = sorted(cls.load()['trajets'], key=lambda t: t.get('debut') or '', reverse=True)
        if not filtre:
            return liste
        statut = filtre.get('statut')
        chauffeur_id = filtre.get('chauffeurId')

        def correspond(t):
            ok_statut = not statut or statut == 'tous' or t['statut'] == statut
            ok_chauffeur = not chauffeur_id or t['chauffeurId'] == chauffeur_id
            return ok_statut and ok_chauffeur

        return [t for t in liste if correspond(t)]

    @classmethod
    def trajet(cls, id_):
        """Renvoie un trajet par son id, ou None s il n existe pas."""
        return next((t for t in cls.load()['trajets'] if t['id'] == id_), None)

    @classmethod
    def trajet_en_cours(cls, chauffeur_id):
        """Renvoie le trajet 'en-cours' d un chauffeur (un chauffeur n en a qu un a la fois)."""
        return next((t for t in cls.load()['trajets']
                     if t['chauffeurId'] == chauffeur_id and t['statut'] == 'en-cours'), None)

    @classmethod
    def ajouter_trajet(cls, trajet):
        """
        Demarre un nouveau trajet. L id est du type 'T-1', 'T-2', ... :
        on regarde le plus grand numero existant et on ajoute 1, plutot
        que de compter simplement le nombre de trajets (pour ne jamais
        reutiliser un id meme si de vieux trajets etaient supprimes).
        Le trajet demarre toujours avec le statut 'en-cours', sans
        arret enregistre et sans heure de fin.
        """
        d = cls.load()
        numeros = []
        for t in d['trajets']:
            try:
                numeros.append(int(t['id'].split('-')[1]))
            except (IndexError, ValueError):
                numeros.append(0)
        suivant = (max(numeros) if numeros else 0) + 1
        trajet['id'] = 'T-' + str(suivant)
        trajet['statut'] = 'en-cours'
        trajet['arrets'] = []
        trajet['fin'] = None
        d['trajets'].append(trajet)
        cls.save(d)
        return trajet

    @classmethod
    def ajouter_arret(cls, trajet_id, arret):
        """Ajoute un arret (lieu, heure, note) a la liste des arrets d un trajet."""
        d = cls.load()
        t = next((x for x in d['trajets'] if x['id'] == trajet_id), None)
        if not t:
            return None
        t['arrets'].append(arret)
        cls.save(d)
        return t

    @classmethod
    def terminer_trajet(cls, trajet_id):
        """
        Termine un trajet : marque son statut 'termine', enregistre l
        heure de fin, et remet automatiquement le chauffeur au statut
        'disponible' puisqu il n est plus occupe.
        """
        d = cls.load()
        t = next((x for x in d['trajets'] if x['id'] == trajet_id), None)
        if not t:
            return None
        t['statut'] = 'termine'
        t['fin'] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M')
        c = next((x for x in d['chauffeurs'] if x['id'] == t['chauffeurId']), None)
        if c:
            c['statut'] = 'disponible'
        cls.save(d)
        return t

    # ---- Incidents -------------------------------------------------------
    @classmethod
    def incidents(cls, filtre=None):
        """
        Liste des incidents, du plus recent au plus ancien, avec filtre optionnel :
        - filtre['type']        : 'technique' / 'route' / 'tous'
        - filtre['statut']      : 'ouvert' / 'traite' / 'tous'
        - filtre['chauffeurId'] : ne garder que les incidents de ce chauffeur
        """
        liste = sorted(cls.load()['incidents'],
                        key=lambda i: (i.get('date') or '') + (i.get('heure') or ''), reverse=True)
        if not filtre:
            return liste
        type_ = filtre.get('type')
        statut = filtre.get('statut')
        chauffeur_id = filtre.get('chauffeurId')

        def correspond(i):
            ok_type = not type_ or type_ == 'tous' or i['type'] == type_
            ok_statut = not statut or statut == 'tous' or i['statut'] == statut
            ok_chauffeur = not chauffeur_id or i['chauffeurId'] == chauffeur_id
            return ok_type and ok_statut and ok_chauffeur

        return [i for i in liste if correspond(i)]

    @classmethod
    def incident(cls, id_):
        """Renvoie un incident par son id, ou None s il n existe pas."""
        return next((i for i in cls.load()['incidents'] if i['id'] == id_), None)

    @classmethod
    def ajouter_incident(cls, incident):
        """
        Signale un nouvel incident. Meme logique d id que les trajets
        (I-1, I-2, ...). Le nouvel incident est place en tete de liste
        (insert(0, ...)) et commence toujours avec le statut 'ouvert'.
        """
        d = cls.load()
        numeros = []
        for i in d['incidents']:
            try:
                numeros.append(int(i['id'].split('-')[1]))
            except (IndexError, ValueError):
                numeros.append(0)
        suivant = (max(numeros) if numeros else 0) + 1
        incident['id'] = 'I-' + str(suivant)
        incident['statut'] = 'ouvert'
        d['incidents'].insert(0, incident)
        cls.save(d)
        return incident

    @classmethod
    def traiter_incident(cls, id_):
        """Marque un incident comme 'traite' (utilise par l administrateur)."""
        d = cls.load()
        i = next((x for x in d['incidents'] if x['id'] == id_), None)
        if not i:
            return None
        i['statut'] = 'traite'
        cls.save(d)
        return i

    # ---- Vehicules ---------------------------------------------------------
    @classmethod
    def vehicules(cls):
        """Liste des vehicules de la flotte (plaque + modele)."""
        return cls.load()['vehicules']

    # ---- Indicateurs du tableau de bord ------------------------------------
    @classmethod
    def indicateurs(cls):
        """
        Calcule les chiffres affiches sur le tableau de bord admin :
        nombre de chauffeurs actifs, trajets en cours, trajets du jour,
        incidents ouverts, incidents du jour, et permis qui expirent
        bientot (avant la date LIMITE_PERMIS definie dans config.py).
        """
        d = cls.load()
        aujourdhui = config.AUJOURD_HUI
        limite = datetime.fromisoformat(config.LIMITE_PERMIS)
        return {
            'chauffeursActifs': len([c for c in d['chauffeurs'] if c['statut'] != 'hors-service']),
            'trajetsEnCours': len([t for t in d['trajets'] if t['statut'] == 'en-cours']),
            'trajetsDuJour': len([t for t in d['trajets'] if (t.get('debut') or '')[:10] == aujourdhui]),
            'incidentsOuverts': len([i for i in d['incidents'] if i['statut'] == 'ouvert']),
            'incidentsDuJour': len([i for i in d['incidents'] if i['date'] == aujourdhui]),
            'permisAExpirer': len([c for c in d['chauffeurs']
                                    if datetime.fromisoformat(c['permisExpiration']) < limite])
        }

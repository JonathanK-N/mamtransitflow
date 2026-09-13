"""TransitFlow — donnees et persistance serveur (equivalent de assets/js/store.js)"""

import json
import os
import threading
from datetime import datetime

from . import config
from .seed import SEED

_verrou = threading.Lock()


def _copie_seed():
    return json.loads(json.dumps(SEED))


def _lire():
    if not os.path.exists(config.DATA_FILE):
        donnees = _copie_seed()
        _ecrire(donnees)
        return donnees
    try:
        with open(config.DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        donnees = _copie_seed()
        _ecrire(donnees)
        return donnees


def _ecrire(donnees):
    os.makedirs(os.path.dirname(config.DATA_FILE), exist_ok=True)
    with open(config.DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(donnees, f, ensure_ascii=False, indent=2)


class Store:
    @staticmethod
    def load():
        with _verrou:
            return _lire()

    @staticmethod
    def save(donnees):
        with _verrou:
            _ecrire(donnees)

    @classmethod
    def reinitialiser(cls):
        with _verrou:
            if os.path.exists(config.DATA_FILE):
                os.remove(config.DATA_FILE)
            return _lire()

    # ---- Chauffeurs ----------------------------------------------------
    @classmethod
    def chauffeurs(cls, filtre=None):
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
        return next((c for c in cls.load()['chauffeurs'] if c['id'] == id_), None)

    @classmethod
    def ajouter_chauffeur(cls, chauffeur):
        d = cls.load()
        chauffeur['id'] = 'c' + str(len(d['chauffeurs']) + 1)
        chauffeur['statut'] = chauffeur.get('statut') or 'disponible'
        chauffeur['creeLe'] = datetime.utcnow().strftime('%Y-%m-%d')
        d['chauffeurs'].append(chauffeur)
        cls.save(d)
        return chauffeur

    @classmethod
    def maj_chauffeur(cls, id_, champs):
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
        return next((t for t in cls.load()['trajets'] if t['id'] == id_), None)

    @classmethod
    def trajet_en_cours(cls, chauffeur_id):
        return next((t for t in cls.load()['trajets']
                     if t['chauffeurId'] == chauffeur_id and t['statut'] == 'en-cours'), None)

    @classmethod
    def ajouter_trajet(cls, trajet):
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
        d = cls.load()
        t = next((x for x in d['trajets'] if x['id'] == trajet_id), None)
        if not t:
            return None
        t['arrets'].append(arret)
        cls.save(d)
        return t

    @classmethod
    def terminer_trajet(cls, trajet_id):
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
        return next((i for i in cls.load()['incidents'] if i['id'] == id_), None)

    @classmethod
    def ajouter_incident(cls, incident):
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
        return cls.load()['vehicules']

    # ---- Indicateurs du tableau de bord ------------------------------------
    @classmethod
    def indicateurs(cls):
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

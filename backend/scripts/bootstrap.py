"""
TransitFlow — Initialisation d une nouvelle installation
Auteur : Jonathan K-N

Contrairement au prototype (Flask), il n y a plus de comptes de
demonstration codes en dur : chaque client doit avoir ses propres comptes,
avec de vrais mots de passe. Ce script cree :
1. les deux groupes de permission de base ('fleet.admin', 'fleet.driver') ;
2. un premier compte administrateur, pour pouvoir se connecter une
   premiere fois et creer les autres comptes depuis l interface.

A executer une seule fois par installation :
  python -m backend.scripts.bootstrap admin@exemple.com "mot-de-passe-sur" "Prenom Nom"
"""

import sys

from ..apps.auth.models import Compte, Groupe
from ..apps.auth.security import hacher_mot_de_passe
from ..database import SessionLocal, engine
from ..models_registry import Base

GROUPES_DE_BASE = [
    ('fleet.admin', 'Administration de la flotte'),
    ('fleet.driver', 'Chauffeur')
]


def executer(courriel: str, mot_de_passe: str, nom: str) -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for code, libelle in GROUPES_DE_BASE:
            if not db.query(Groupe).filter(Groupe.code == code).first():
                db.add(Groupe(code=code, nom=libelle))
        db.commit()

        if db.query(Compte).filter(Compte.courriel == courriel.lower()).first():
            print(f'Le compte {courriel} existe deja, rien a faire.')
            return

        groupe_admin = db.query(Groupe).filter(Groupe.code == 'fleet.admin').first()
        compte = Compte(courriel=courriel.lower(), nom=nom,
                         mot_de_passe_hache=hacher_mot_de_passe(mot_de_passe))
        compte.groupes.append(groupe_admin)
        db.add(compte)
        db.commit()
        print(f'Compte administrateur cree : {courriel}')
    finally:
        db.close()


if __name__ == '__main__':
    if len(sys.argv) != 4:
        print('Usage : python -m backend.scripts.bootstrap <courriel> <mot_de_passe> <nom>')
        sys.exit(1)
    executer(sys.argv[1], sys.argv[2], sys.argv[3])

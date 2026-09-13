"""
TransitFlow — Routes de connexion
Auteur : Jonathan K-N

  POST /api/auth/connexion -> verifie courriel/mot de passe, renvoie un jeton JWT
  GET  /api/auth/moi       -> renvoie le compte du jeton envoye (verifie qu il est valide)

Il n y a plus de route /deconnexion : un jeton JWT n est pas revocable
individuellement comme l etait l ancien dictionnaire _SESSIONS (Flask) --
il expire simplement tout seul (voir access_token_minutes dans settings.py).
Le front-end n a qu a oublier le jeton localement pour se deconnecter.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...database import get_db
from .deps import exiger
from .models import Compte, Groupe
from .schemas import CompteEntree, CompteSortie, ConnexionEntree, JetonSortie
from .security import creer_jeton, hacher_mot_de_passe, verifier_mot_de_passe

router = APIRouter(prefix='/api/auth', tags=['auth'])


@router.post('/connexion', response_model=JetonSortie)
def connexion(payload: ConnexionEntree, db: Session = Depends(get_db)):
    compte = db.query(Compte).filter(Compte.courriel == payload.courriel.lower()).first()
    if not compte or not compte.actif or not verifier_mot_de_passe(payload.mot_de_passe, compte.mot_de_passe_hache):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'Courriel ou mot de passe incorrect.')
    jeton = creer_jeton(compte.id)
    sortie = CompteSortie(id=compte.id, courriel=compte.courriel, nom=compte.nom,
                           chauffeur_id=compte.chauffeur_id, groupes=compte.codes_groupes)
    return JetonSortie(jeton=jeton, compte=sortie)


@router.get('/moi', response_model=CompteSortie)
def moi(compte: Compte = Depends(exiger())):
    return CompteSortie(id=compte.id, courriel=compte.courriel, nom=compte.nom,
                         chauffeur_id=compte.chauffeur_id, groupes=compte.codes_groupes)


@router.post('/comptes', response_model=CompteSortie, status_code=status.HTTP_201_CREATED)
def creer_compte(payload: CompteEntree, db: Session = Depends(get_db), _=Depends(exiger('fleet.admin'))):
    """Cree un compte de connexion (ex. pour donner acces a un chauffeur nouvellement embauche)."""
    if db.query(Compte).filter(Compte.courriel == payload.courriel.lower()).first():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Un compte existe deja avec ce courriel.')

    groupes = db.query(Groupe).filter(Groupe.code.in_(payload.groupes)).all()
    if len(groupes) != len(set(payload.groupes)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Groupe de permission inconnu.')

    compte = Compte(courriel=payload.courriel.lower(), nom=payload.nom,
                     chauffeur_id=payload.chauffeur_id,
                     mot_de_passe_hache=hacher_mot_de_passe(payload.mot_de_passe))
    compte.groupes = groupes
    db.add(compte)
    db.commit()
    db.refresh(compte)
    return CompteSortie(id=compte.id, courriel=compte.courriel, nom=compte.nom,
                         chauffeur_id=compte.chauffeur_id, groupes=compte.codes_groupes)

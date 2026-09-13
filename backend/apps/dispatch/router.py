"""
TransitFlow — Routes trajets
Auteur : Jonathan K-N

Meme comportement que l ancien backend/routes/trajets_routes.py (Flask) :
  GET  /api/trajets                 -> liste (filtres statut/chauffeur_id)
  GET  /api/trajets/en-cours/{id}   -> trajet en cours d un chauffeur
  GET  /api/trajets/{id}            -> detail
  POST /api/trajets                 -> demarrer un trajet (reserve a 'fleet.driver')
  POST /api/trajets/{id}/arrets     -> ajouter un arret (chauffeur proprietaire seulement)
  POST /api/trajets/{id}/terminer   -> terminer (chauffeur proprietaire seulement)

Le chauffeur_id d un trajet vient toujours du compte connecte
(compte.chauffeur_id), jamais d une valeur envoyee par le client : un
chauffeur ne peut pas demarrer un trajet au nom d un collegue.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...database import get_db
from ..auth.deps import exiger
from ..auth.models import Compte
from ..drivers.models import Chauffeur
from .models import Arret, Trajet
from .schemas import ArretEntree, TrajetEntree, TrajetSortie

router = APIRouter(prefix='/api/trajets', tags=['dispatch'])


@router.get('', response_model=list[TrajetSortie])
def lister(statut: str = '', chauffeur_id: int | None = None,
           db: Session = Depends(get_db), _=Depends(exiger())):
    requete = db.query(Trajet)
    if statut and statut != 'tous':
        requete = requete.filter(Trajet.statut == statut)
    if chauffeur_id:
        requete = requete.filter(Trajet.chauffeur_id == chauffeur_id)
    return requete.order_by(Trajet.debut.desc()).all()


@router.get('/en-cours/{chauffeur_id}', response_model=TrajetSortie | None)
def en_cours(chauffeur_id: int, db: Session = Depends(get_db), _=Depends(exiger())):
    return db.query(Trajet).filter(Trajet.chauffeur_id == chauffeur_id, Trajet.statut == 'en-cours').first()


@router.get('/{id_}', response_model=TrajetSortie)
def obtenir(id_: int, db: Session = Depends(get_db), _=Depends(exiger())):
    trajet = db.get(Trajet, id_)
    if not trajet:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Trajet introuvable.')
    return trajet


def _chauffeur_id_ou_403(compte: Compte) -> int:
    if not compte.chauffeur_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, 'Ce compte n est associe a aucune fiche chauffeur.')
    return compte.chauffeur_id


@router.post('', response_model=TrajetSortie, status_code=status.HTTP_201_CREATED)
def creer(payload: TrajetEntree, db: Session = Depends(get_db), compte: Compte = Depends(exiger('fleet.driver'))):
    chauffeur_id = _chauffeur_id_ou_403(compte)
    trajet = Trajet(chauffeur_id=chauffeur_id, statut='en-cours', **payload.model_dump())
    db.add(trajet)
    chauffeur = db.get(Chauffeur, chauffeur_id)
    chauffeur.statut = 'en-trajet'
    db.commit()
    db.refresh(trajet)
    return trajet


@router.post('/{id_}/arrets', response_model=TrajetSortie)
def ajouter_arret(id_: int, payload: ArretEntree, db: Session = Depends(get_db),
                   compte: Compte = Depends(exiger('fleet.driver'))):
    trajet = db.get(Trajet, id_)
    if not trajet:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Trajet introuvable.')
    if trajet.chauffeur_id != compte.chauffeur_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, 'Acces refuse.')
    db.add(Arret(trajet_id=id_, **payload.model_dump()))
    db.commit()
    db.refresh(trajet)
    return trajet


@router.post('/{id_}/terminer', response_model=TrajetSortie)
def terminer(id_: int, db: Session = Depends(get_db), compte: Compte = Depends(exiger('fleet.driver'))):
    trajet = db.get(Trajet, id_)
    if not trajet:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Trajet introuvable.')
    if trajet.chauffeur_id != compte.chauffeur_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, 'Acces refuse.')
    trajet.statut = 'termine'
    trajet.fin = datetime.now(timezone.utc)
    chauffeur = db.get(Chauffeur, trajet.chauffeur_id)
    chauffeur.statut = 'disponible'
    db.commit()
    db.refresh(trajet)
    return trajet

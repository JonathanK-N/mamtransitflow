"""
TransitFlow — Routes chauffeurs
Auteur : Jonathan K-N

Meme comportement que l ancien backend/routes/chauffeurs_routes.py (Flask),
porte sur une vraie base de donnees :
  GET   /api/chauffeurs        -> liste (avec filtres recherche/statut)
  GET   /api/chauffeurs/{id}   -> fiche d un chauffeur
  POST  /api/chauffeurs        -> creation (reserve a 'fleet.admin')
  PATCH /api/chauffeurs/{id}   -> mise a jour partielle (reserve a 'fleet.admin')
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ...database import get_db
from ..auth.deps import exiger
from .models import Chauffeur
from .schemas import ChauffeurEntree, ChauffeurMaj, ChauffeurSortie

router = APIRouter(prefix='/api/chauffeurs', tags=['drivers'])


@router.get('', response_model=list[ChauffeurSortie])
def lister(recherche: str = '', statut: str = '', db: Session = Depends(get_db), _=Depends(exiger())):
    requete = db.query(Chauffeur)
    if statut and statut != 'tous':
        requete = requete.filter(Chauffeur.statut == statut)
    if recherche:
        q = f'%{recherche}%'
        requete = requete.filter(or_(
            Chauffeur.prenom.ilike(q), Chauffeur.nom.ilike(q),
            Chauffeur.telephone.ilike(q), Chauffeur.courriel.ilike(q)
        ))
    return requete.order_by(Chauffeur.id).all()


@router.get('/{id_}', response_model=ChauffeurSortie)
def obtenir(id_: int, db: Session = Depends(get_db), _=Depends(exiger())):
    chauffeur = db.get(Chauffeur, id_)
    if not chauffeur:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Chauffeur introuvable.')
    return chauffeur


@router.post('', response_model=ChauffeurSortie, status_code=status.HTTP_201_CREATED)
def creer(payload: ChauffeurEntree, db: Session = Depends(get_db), _=Depends(exiger('fleet.admin'))):
    chauffeur = Chauffeur(**payload.model_dump())
    db.add(chauffeur)
    db.commit()
    db.refresh(chauffeur)
    return chauffeur


@router.patch('/{id_}', response_model=ChauffeurSortie)
def modifier(id_: int, payload: ChauffeurMaj, db: Session = Depends(get_db), _=Depends(exiger('fleet.admin'))):
    chauffeur = db.get(Chauffeur, id_)
    if not chauffeur:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Chauffeur introuvable.')
    for champ, valeur in payload.model_dump(exclude_unset=True).items():
        setattr(chauffeur, champ, valeur)
    db.commit()
    db.refresh(chauffeur)
    return chauffeur

"""
TransitFlow — Routes vehicules
Auteur : Jonathan K-N

  GET  /api/vehicules -> liste des vehicules de la flotte
  POST /api/vehicules -> ajoute un vehicule (reserve a 'fleet.admin')
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...database import get_db
from ..auth.deps import exiger
from .models import Vehicule
from .schemas import VehiculeEntree, VehiculeSortie

router = APIRouter(prefix='/api/vehicules', tags=['fleet'])


@router.get('', response_model=list[VehiculeSortie])
def lister(db: Session = Depends(get_db), _=Depends(exiger())):
    return db.query(Vehicule).order_by(Vehicule.plaque).all()


@router.post('', response_model=VehiculeSortie, status_code=status.HTTP_201_CREATED)
def creer(payload: VehiculeEntree, db: Session = Depends(get_db), _=Depends(exiger('fleet.admin'))):
    if db.query(Vehicule).filter(Vehicule.plaque == payload.plaque).first():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Cette plaque existe deja.')
    vehicule = Vehicule(plaque=payload.plaque, modele=payload.modele)
    db.add(vehicule)
    db.commit()
    db.refresh(vehicule)
    return vehicule

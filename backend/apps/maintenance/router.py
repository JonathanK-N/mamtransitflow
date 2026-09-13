"""
TransitFlow — Routes incidents
Auteur : Jonathan K-N

  GET  /api/incidents              -> liste (filtres type/statut/chauffeur_id)
  GET  /api/incidents/{id}         -> detail
  POST /api/incidents              -> signaler (reserve a 'fleet.driver')
  POST /api/incidents/{id}/traiter -> marquer traite (reserve a 'fleet.admin')
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...database import get_db
from ..auth.deps import exiger
from ..auth.models import Compte
from ..dispatch.models import Trajet
from .models import Incident
from .schemas import IncidentEntree, IncidentSortie

router = APIRouter(prefix='/api/incidents', tags=['maintenance'])


@router.get('', response_model=list[IncidentSortie])
def lister(type: str = '', statut: str = '', chauffeur_id: int | None = None,
           db: Session = Depends(get_db), _=Depends(exiger())):
    requete = db.query(Incident)
    if type and type != 'tous':
        requete = requete.filter(Incident.type == type)
    if statut and statut != 'tous':
        requete = requete.filter(Incident.statut == statut)
    if chauffeur_id:
        requete = requete.filter(Incident.chauffeur_id == chauffeur_id)
    return requete.order_by(Incident.horodatage.desc()).all()


@router.get('/{id_}', response_model=IncidentSortie)
def obtenir(id_: int, db: Session = Depends(get_db), _=Depends(exiger())):
    incident = db.get(Incident, id_)
    if not incident:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Incident introuvable.')
    return incident


@router.post('', response_model=IncidentSortie, status_code=status.HTTP_201_CREATED)
def creer(payload: IncidentEntree, db: Session = Depends(get_db),
          compte: Compte = Depends(exiger('fleet.driver'))):
    if not compte.chauffeur_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, 'Ce compte n est associe a aucune fiche chauffeur.')
    if payload.trajet_id and not db.get(Trajet, payload.trajet_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Trajet introuvable.')
    incident = Incident(chauffeur_id=compte.chauffeur_id, statut='ouvert', **payload.model_dump())
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return incident


@router.post('/{id_}/traiter', response_model=IncidentSortie)
def traiter(id_: int, db: Session = Depends(get_db), _=Depends(exiger('fleet.admin'))):
    incident = db.get(Incident, id_)
    if not incident:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Incident introuvable.')
    incident.statut = 'traite'
    db.commit()
    db.refresh(incident)
    return incident

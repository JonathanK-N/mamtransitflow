"""
TransitFlow — Indicateurs du tableau de bord
Auteur : Jonathan K-N

Version 1 (Phase 0) du module "reporting" : juste les chiffres du tableau
de bord admin, equivalent de Store.indicateurs() dans l ancien
backend/store.py. Contrairement a l ancienne version, on utilise l heure
reelle (datetime.now(timezone.utc)) au lieu d une date figee en dur --
important pour fonctionner correctement quel que soit le fuseau horaire
du client.

Les rapports plus complets (exports PDF/Excel, historique) sont prevus a
la Phase 4 du plan et viendront s ajouter ici sans toucher aux autres apps.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...database import get_db
from ..auth.deps import exiger
from ..dispatch.models import Trajet
from ..drivers.models import Chauffeur
from ..maintenance.models import Incident

router = APIRouter(prefix='/api/indicateurs', tags=['reporting'])

# Un permis est considere "a renouveler bientot" s il expire dans les 60 jours.
FENETRE_PERMIS_JOURS = 60


class Indicateurs(BaseModel):
    chauffeurs_actifs: int
    trajets_en_cours: int
    trajets_du_jour: int
    incidents_ouverts: int
    incidents_du_jour: int
    permis_a_expirer: int


@router.get('', response_model=Indicateurs)
def indicateurs(db: Session = Depends(get_db), _=Depends(exiger('fleet.admin'))):
    maintenant = datetime.now(timezone.utc)
    aujourdhui = maintenant.date()
    limite_permis = aujourdhui + timedelta(days=FENETRE_PERMIS_JOURS)

    return Indicateurs(
        chauffeurs_actifs=db.query(Chauffeur).filter(Chauffeur.statut != 'hors-service').count(),
        trajets_en_cours=db.query(Trajet).filter(Trajet.statut == 'en-cours').count(),
        trajets_du_jour=db.query(Trajet).filter(func.date(Trajet.debut) == aujourdhui).count(),
        incidents_ouverts=db.query(Incident).filter(Incident.statut == 'ouvert').count(),
        incidents_du_jour=db.query(Incident).filter(func.date(Incident.horodatage) == aujourdhui).count(),
        permis_a_expirer=db.query(Chauffeur).filter(Chauffeur.permis_expiration < limite_permis).count()
    )

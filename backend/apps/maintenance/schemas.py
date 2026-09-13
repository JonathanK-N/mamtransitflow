"""TransitFlow — Schemas de l app maintenance (incidents)
   Auteur : Jonathan K-N"""

from datetime import datetime

from pydantic import BaseModel, field_validator

TYPES_VALIDES = {'technique', 'route'}


class IncidentEntree(BaseModel):
    trajet_id: int | None = None
    type: str
    titre: str
    description: str
    lieu: str
    horodatage: datetime

    @field_validator('type')
    @classmethod
    def _type_valide(cls, valeur):
        if valeur not in TYPES_VALIDES:
            raise ValueError('Type d incident invalide.')
        return valeur


class IncidentSortie(BaseModel):
    id: int
    trajet_id: int | None
    chauffeur_id: int
    type: str
    titre: str
    description: str
    lieu: str
    horodatage: datetime
    statut: str

    model_config = {'from_attributes': True}

"""TransitFlow — Schemas de l app fleet (vehicules)
   Auteur : Jonathan K-N"""

from pydantic import BaseModel


class VehiculeEntree(BaseModel):
    plaque: str
    modele: str


class VehiculeSortie(BaseModel):
    id: int
    plaque: str
    modele: str

    model_config = {'from_attributes': True}

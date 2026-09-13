"""TransitFlow — Schemas de l app dispatch (trajets, arrets)
   Auteur : Jonathan K-N"""

from datetime import datetime

from pydantic import BaseModel


class TrajetEntree(BaseModel):
    plaque: str
    depart: str
    depart_adresse: str | None = None
    arrivee: str
    debut: datetime
    fin_prevue: datetime


class ArretEntree(BaseModel):
    lieu: str
    heure: datetime
    note: str | None = None


class ArretSortie(BaseModel):
    id: int
    lieu: str
    heure: datetime
    note: str | None

    model_config = {'from_attributes': True}


class TrajetSortie(BaseModel):
    id: int
    code: str
    chauffeur_id: int
    plaque: str
    depart: str
    depart_adresse: str | None
    arrivee: str
    debut: datetime
    fin_prevue: datetime
    fin: datetime | None
    statut: str
    arrets: list[ArretSortie]

    model_config = {'from_attributes': True}

"""TransitFlow — Schemas de l app drivers (chauffeurs)
   Auteur : Jonathan K-N"""

from datetime import date, datetime

from pydantic import BaseModel


class ChauffeurEntree(BaseModel):
    prenom: str
    nom: str
    age: int
    telephone: str
    courriel: str
    adresse: str
    permis_numero: str
    permis_expiration: date
    plaque_habituelle: str | None = None
    statut: str = 'disponible'


class ChauffeurMaj(BaseModel):
    """Tous les champs sont facultatifs : seuls ceux fournis sont modifies (PATCH)."""
    prenom: str | None = None
    nom: str | None = None
    age: int | None = None
    telephone: str | None = None
    courriel: str | None = None
    adresse: str | None = None
    permis_numero: str | None = None
    permis_expiration: date | None = None
    plaque_habituelle: str | None = None
    statut: str | None = None


class ChauffeurSortie(BaseModel):
    id: int
    prenom: str
    nom: str
    age: int
    telephone: str
    courriel: str
    adresse: str
    permis_numero: str
    permis_expiration: date
    statut: str
    plaque_habituelle: str | None
    cree_le: datetime

    model_config = {'from_attributes': True}

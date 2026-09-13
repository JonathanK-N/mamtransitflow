"""
TransitFlow — Modele : vehicules de la flotte
Auteur : Jonathan K-N
"""

from sqlalchemy import Column, Integer, String

from ...database import Base


class Vehicule(Base):
    __tablename__ = 'vehicules'

    id = Column(Integer, primary_key=True)
    plaque = Column(String, unique=True, nullable=False, index=True)
    modele = Column(String, nullable=False)

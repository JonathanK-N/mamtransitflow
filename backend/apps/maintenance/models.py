"""
TransitFlow — Modele : incidents
Auteur : Jonathan K-N
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ...database import Base


class Incident(Base):
    __tablename__ = 'incidents'

    id = Column(Integer, primary_key=True)
    trajet_id = Column(Integer, ForeignKey('trajets.id'), nullable=True)
    chauffeur_id = Column(Integer, ForeignKey('chauffeurs.id'), nullable=False)
    type = Column(String, nullable=False)  # technique / route
    titre = Column(String, nullable=False)
    description = Column(String, nullable=False)
    lieu = Column(String, nullable=False)
    horodatage = Column(DateTime(timezone=True), nullable=False)
    statut = Column(String, nullable=False, default='ouvert')  # ouvert / traite

    trajet = relationship('Trajet', back_populates='incidents')
    chauffeur = relationship('Chauffeur', back_populates='incidents')

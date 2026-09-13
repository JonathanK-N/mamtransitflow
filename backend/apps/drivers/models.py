"""
TransitFlow — Modele : chauffeurs
Auteur : Jonathan K-N

Reprend les memes champs que l ancien Store (backend/store.py, Flask),
mais dans une vraie table plutot qu un objet JSON. L id est maintenant un
entier auto-incremente par la base de donnees (plus besoin de le calculer
a la main comme 'c' + len(liste)).
"""

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from ...database import Base


class Chauffeur(Base):
    __tablename__ = 'chauffeurs'

    id = Column(Integer, primary_key=True)
    prenom = Column(String, nullable=False)
    nom = Column(String, nullable=False)
    age = Column(Integer, nullable=False)
    telephone = Column(String, nullable=False)
    courriel = Column(String, nullable=False)
    adresse = Column(String, nullable=False)
    permis_numero = Column(String, nullable=False)
    permis_expiration = Column(Date, nullable=False)
    statut = Column(String, nullable=False, default='disponible')  # disponible / en-trajet / hors-service
    plaque_habituelle = Column(String, ForeignKey('vehicules.plaque'), nullable=True)
    cree_le = Column(DateTime(timezone=True), server_default=func.now())

    trajets = relationship('Trajet', back_populates='chauffeur')
    incidents = relationship('Incident', back_populates='chauffeur')

    @property
    def nom_complet(self) -> str:
        return f'{self.prenom} {self.nom}'

    @property
    def initiales(self) -> str:
        return (self.prenom[0] + self.nom[0]).upper()

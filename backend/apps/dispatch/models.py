"""
TransitFlow — Modeles : trajets et arrets
Auteur : Jonathan K-N

Dans l ancienne version (backend/store.py, Flask), un trajet gardait ses
arrets dans une simple liste JSON imbriquee. Ici, Arret devient sa propre
table liee au trajet par une cle etrangere -- plus robuste (chaque arret a
son propre id, peut etre requete independamment) et c est ce que permet une
vraie base de donnees relationnelle.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ...database import Base


class Trajet(Base):
    __tablename__ = 'trajets'

    id = Column(Integer, primary_key=True)
    chauffeur_id = Column(Integer, ForeignKey('chauffeurs.id'), nullable=False)
    plaque = Column(String, nullable=False)
    depart = Column(String, nullable=False)
    depart_adresse = Column(String, nullable=True)
    arrivee = Column(String, nullable=False)
    debut = Column(DateTime(timezone=True), nullable=False)
    fin_prevue = Column(DateTime(timezone=True), nullable=False)
    fin = Column(DateTime(timezone=True), nullable=True)
    statut = Column(String, nullable=False, default='en-cours')  # en-cours / termine

    chauffeur = relationship('Chauffeur', back_populates='trajets')
    arrets = relationship('Arret', back_populates='trajet', cascade='all, delete-orphan',
                           order_by='Arret.heure')
    incidents = relationship('Incident', back_populates='trajet')

    @property
    def code(self) -> str:
        """Identifiant lisible style ancien front-end (ex. 'T-42'), pour l affichage seulement."""
        return f'T-{self.id}'


class Arret(Base):
    __tablename__ = 'arrets'

    id = Column(Integer, primary_key=True)
    trajet_id = Column(Integer, ForeignKey('trajets.id'), nullable=False)
    lieu = Column(String, nullable=False)
    heure = Column(DateTime(timezone=True), nullable=False)
    note = Column(String, nullable=True)

    trajet = relationship('Trajet', back_populates='arrets')

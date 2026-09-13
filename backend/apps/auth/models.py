"""
TransitFlow — Modeles : comptes et groupes de permission
Auteur : Jonathan K-N

Remplace la liste COMPTES codee en dur de l ancien backend/auth.py par de
vrais comptes en base de donnees, avec mot de passe hache et des groupes
de permission (a la Odoo) au lieu de deux roles fixes 'admin'/'chauffeur'.

Un compte peut appartenir a plusieurs groupes ; chaque groupe porte un
"code" (ex. 'fleet.admin') que les routes verifient via la dependance
`exiger` (voir deps.py). Ca permet d ajouter plus tard de nouveaux groupes
(ex. 'maintenance.tech') sans changer la structure de la table.
"""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table, func
from sqlalchemy.orm import relationship

from ...database import Base

# Table d association many-to-many entre comptes et groupes (un compte
# peut avoir plusieurs groupes, un groupe peut etre partage par plusieurs comptes).
comptes_groupes = Table(
    'comptes_groupes', Base.metadata,
    Column('compte_id', ForeignKey('comptes.id'), primary_key=True),
    Column('groupe_id', ForeignKey('groupes.id'), primary_key=True)
)


class Groupe(Base):
    """Un groupe de permission, ex. 'fleet.admin' ou 'fleet.driver'."""
    __tablename__ = 'groupes'

    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, nullable=False)
    nom = Column(String, nullable=False)


class Compte(Base):
    """Un compte de connexion (equivalent des entrees de COMPTES dans l ancien auth.py)."""
    __tablename__ = 'comptes'

    id = Column(Integer, primary_key=True)
    courriel = Column(String, unique=True, nullable=False, index=True)
    mot_de_passe_hache = Column(String, nullable=False)
    nom = Column(String, nullable=True)
    actif = Column(Boolean, nullable=False, default=True)
    # Lien optionnel vers une fiche chauffeur (backend/apps/drivers/models.py) :
    # seuls les comptes du groupe 'fleet.driver' en ont un.
    chauffeur_id = Column(Integer, ForeignKey('chauffeurs.id'), nullable=True, unique=True)
    cree_le = Column(DateTime(timezone=True), server_default=func.now())

    groupes = relationship('Groupe', secondary=comptes_groupes, backref='comptes')

    def a_permission(self, code: str) -> bool:
        """Vrai si ce compte appartient a un groupe portant ce code (ex. 'fleet.admin')."""
        return any(g.code == code for g in self.groupes)

    @property
    def codes_groupes(self):
        return [g.code for g in self.groupes]

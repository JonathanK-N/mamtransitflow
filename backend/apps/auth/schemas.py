"""
TransitFlow — Schemas (validation des donnees entrantes/sortantes)
Auteur : Jonathan K-N

Un "schema" Pydantic decrit la forme attendue d une requete ou d une
reponse. FastAPI valide automatiquement les donnees recues contre ces
schemas (ex. rejette une connexion si "courriel" est absent) : c est ce
qui remplace les verifications manuelles qu on faisait a la main dans
l ancien backend/routes/*.py (Flask).
"""

from pydantic import BaseModel, EmailStr


class ConnexionEntree(BaseModel):
    courriel: EmailStr
    mot_de_passe: str


class CompteSortie(BaseModel):
    id: int
    courriel: str
    nom: str | None
    chauffeur_id: int | None
    groupes: list[str]

    model_config = {'from_attributes': True}


class JetonSortie(BaseModel):
    ok: bool = True
    jeton: str
    compte: CompteSortie


class CompteEntree(BaseModel):
    """
    Cree un compte de connexion, separe de la fiche chauffeur elle-meme
    (backend/apps/drivers) : une fiche chauffeur est un dossier RH (permis,
    telephone...), un compte est ce qui permet de se connecter au systeme.
    Ca permet par exemple de creer une fiche chauffeur sans lui donner
    acces tout de suite, ou de creer plus tard des comptes pour d autres
    groupes (ex. 'maintenance.tech') sans toucher a ce schema.
    """
    courriel: EmailStr
    mot_de_passe: str
    nom: str | None = None
    chauffeur_id: int | None = None
    groupes: list[str] = ['fleet.driver']

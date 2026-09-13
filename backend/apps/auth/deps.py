"""
TransitFlow — Dependances FastAPI pour proteger les routes
Auteur : Jonathan K-N

Equivalent du decorateur `exiger()` de l ancien backend/routes/__init__.py
(Flask), mais sous forme de "dependances" FastAPI : on les declare dans la
signature d une route et FastAPI les execute avant d appeler la fonction.

  @router.get('/exemple')
  def exemple(compte: Compte = Depends(exiger('fleet.admin'))):
      ...

Sans argument, exiger() demande juste d etre connecte (peu importe le
groupe). Avec exiger('fleet.admin'), il faut en plus appartenir a ce
groupe de permission.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ...database import get_db
from .models import Compte
from .security import verifier_jeton

_schema_jeton = HTTPBearer(auto_error=False)


def utilisateur_courant(
    identifiants: HTTPAuthorizationCredentials | None = Depends(_schema_jeton),
    db: Session = Depends(get_db)
) -> Compte | None:
    """Retrouve le compte a partir du jeton envoye (entete Authorization: Bearer <jeton>)."""
    if not identifiants:
        return None
    compte_id = verifier_jeton(identifiants.credentials)
    if compte_id is None:
        return None
    compte = db.get(Compte, compte_id)
    return compte if (compte and compte.actif) else None


def exiger(permission: str | None = None):
    """Fabrique une dependance qui verifie la connexion, et le groupe de permission si fourni."""
    def dependance(compte: Compte | None = Depends(utilisateur_courant)) -> Compte:
        if not compte:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'Authentification requise.')
        if permission and not compte.a_permission(permission):
            raise HTTPException(status.HTTP_403_FORBIDDEN, 'Acces refuse.')
        return compte
    return dependance

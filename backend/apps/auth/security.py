"""
TransitFlow — Hachage des mots de passe et jetons JWT
Auteur : Jonathan K-N

Deux responsabilites bien separees :
1. Mots de passe : on ne stocke jamais un mot de passe en clair (contrairement
   a l ancien MOT_DE_PASSE_DEMO commun a tous les comptes) -- on stocke un
   "hachage" (argon2) qu il est impossible de retransformer en mot de passe.
2. Jetons JWT : a la connexion, on genere un jeton signe contenant l id du
   compte. Le front-end le renvoie a chaque requete (entete Authorization),
   et verifier_jeton() confirme qu il est valide et n a pas expire, sans
   avoir besoin de retenir les jetons actifs en memoire (contrairement a
   l ancien dictionnaire _SESSIONS de backend/auth.py).
"""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from ...settings import settings

_contexte_mdp = CryptContext(schemes=['argon2'], deprecated='auto')


def hacher_mot_de_passe(mot_de_passe: str) -> str:
    return _contexte_mdp.hash(mot_de_passe)


def verifier_mot_de_passe(mot_de_passe: str, hachage: str) -> bool:
    return _contexte_mdp.verify(mot_de_passe, hachage)


def creer_jeton(compte_id: int, duree: timedelta | None = None) -> str:
    """Cree un jeton JWT signe, valide pendant `duree` (par defaut : access_token_minutes)."""
    expiration = datetime.now(timezone.utc) + (duree or timedelta(minutes=settings.access_token_minutes))
    charge = {'sub': str(compte_id), 'exp': expiration}
    return jwt.encode(charge, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verifier_jeton(jeton: str) -> int | None:
    """Renvoie l id du compte si le jeton est valide et non expire, sinon None."""
    try:
        charge = jwt.decode(jeton, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return int(charge['sub'])
    except (JWTError, KeyError, ValueError):
        return None

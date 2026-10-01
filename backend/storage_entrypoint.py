"""Auteur : Jonathan Kakesa Nayaba. Initialisation du stockage persistant."""
import os
import pwd
import sys
import tempfile
from pathlib import Path


def main():
    account = pwd.getpwnam('transitflow')
    storage = Path(os.environ.get('TF_PRIVATE_STORAGE', '/data/privatefiles'))
    if not storage.is_absolute() or storage.is_symlink():
        raise RuntimeError('Le stockage doit etre un repertoire absolu sans lien symbolique.')
    if os.geteuid() == 0:
        # Seul le dossier prive du volume peut etre initialise avec ces privileges.
        if storage != Path('/data/privatefiles') or Path('/data').is_symlink():
            raise RuntimeError('Initialisation privilegiee autorisee uniquement dans /data/privatefiles.')
        storage.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(storage, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fchown(descriptor, account.pw_uid, account.pw_gid)
            os.fchmod(descriptor, 0o700)
        finally:
            os.close(descriptor)
        os.setgroups([])
        os.setgid(account.pw_gid)
        os.setuid(account.pw_uid)
    if os.geteuid() != account.pw_uid or os.getegid() != account.pw_gid:
        raise RuntimeError('Le processus doit utiliser le compte transitflow.')
    os.umask(0o077)
    storage.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryFile(dir=storage) as probe:
        probe.write(b'TransitFlow storage probe')
        probe.flush()
    if len(sys.argv) < 2:
        raise RuntimeError('Commande de lancement manquante.')
    os.environ['HOME'] = account.pw_dir
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == '__main__':
    main()

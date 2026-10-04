"""Recette GPS officielle Vue/PWA, exécutée par Playwright avec tuiles simulées."""
import os
import subprocess
from pathlib import Path

root=Path(__file__).resolve().parents[1]
environment=os.environ.copy()
if environment.get('TF_E2E_URL'):environment['TF_TEST_URL']=environment['TF_E2E_URL']
raise SystemExit(subprocess.call(['pnpm.cmd' if os.name=='nt' else 'pnpm','exec','playwright','test','gps.spec.ts'],cwd=root/'frontend',env=environment))

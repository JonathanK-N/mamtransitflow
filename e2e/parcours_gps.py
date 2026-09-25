"""
TransitFlow — Test de bout en bout du suivi GPS (navigateur reel, position simulee)
Auteur : Jonathan K-N

Un chauffeur (telephone simule, 390 px) partage sa position pendant son
trajet ; l administrateur suit le vehicule sur la carte en direct, voit
sa trace, puis le parcours complet sur la fiche du trajet. Couvre aussi
la coupure de reseau (points gardes puis renvoyes) et le refus de la
localisation.

Prerequis : pip install playwright && playwright install chromium
Execution, sur une base de demonstration neuve (depuis backend/) :
    rm -f data/transitflow.db && python manage.py migrate && python manage.py seed_demo
    python manage.py runserver 5000
puis, depuis la racine du depot :
    python e2e/parcours_gps.py

Variables facultatives :
  TF_E2E_URL        adresse du serveur (defaut http://127.0.0.1:5000)
  TF_E2E_BOOTSTRAP  chemin local de bootstrap.min.css, si le CDN n est pas joignable
  TF_E2E_LEAFLET    dossier local de leaflet/dist, si le CDN n est pas joignable
  TF_E2E_CAPTURES   dossier des captures d ecran (defaut : dossier temporaire)
Les tuiles OpenStreetMap sont remplacees par une image neutre : le test ne
depend pas du serveur de cartes.
"""
import asyncio
import base64
import os
import tempfile

from playwright.async_api import async_playwright, expect

BASE = os.environ.get('TF_E2E_URL', 'http://127.0.0.1:5000').rstrip('/')
MDP = 'Transit-Demo-2026'
DOSSIER = os.path.join(os.environ.get('TF_E2E_CAPTURES') or tempfile.mkdtemp(prefix='transitflow-gps-'), '')
BOOTSTRAP = os.environ.get('TF_E2E_BOOTSTRAP')
LEAFLET = os.environ.get('TF_E2E_LEAFLET')
TUILE = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/58BAwAI/AL+XJ/PAAAAAElFTkSuQmCC')

# Depart du terminus de Sherbrooke vers l ouest : pas de ~30 m, soit ~90 km/h
# au rythme ou le test deplace le telephone (une position toutes les ~1,2 s).
TRACE = [(45.4042, -71.8929 - i * 0.0004) for i in range(5)]
etapes = []


def ok(msg):
    etapes.append(msg)
    print('  OK', msg, flush=True)


async def preparer(contexte):
    async def cdn(route):
        url = route.request.url
        if 'leaflet' in url and LEAFLET:
            nom = url.rsplit('/', 1)[-1]
            await route.fulfill(path=os.path.join(LEAFLET, nom),
                                content_type='text/css' if nom.endswith('.css') else 'application/javascript',
                                headers={'Access-Control-Allow-Origin': '*'})
        elif 'bootstrap' in url and BOOTSTRAP:
            await route.fulfill(path=BOOTSTRAP, content_type='text/css')
        else:
            await route.continue_()
    await contexte.route('https://cdn.jsdelivr.net/**', cdn)
    await contexte.route('https://*.tile.openstreetmap.org/**',
                         lambda r: r.fulfill(body=TUILE, content_type='image/png'))
    if BOOTSTRAP:
        await contexte.route('https://fonts.googleapis.com/**', lambda r: r.fulfill(body='', content_type='text/css'))


def surveiller(pg):
    pg.erreurs = []
    pg.on('pageerror', lambda e: pg.erreurs.append(str(e)))
    pg.on('console', lambda m: pg.erreurs.append(m.text)
          if m.type == 'error' and 'status of 4' not in m.text else None)
    pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
    return pg


async def connexion(pg, courriel, role):
    await pg.goto(BASE + '/index.html')
    if role == 'chauffeur':
        await pg.click('[data-role=chauffeur]')
    await pg.fill('input[name=courriel]', courriel)
    await pg.fill('input[name=motDePasse]', MDP)
    await pg.click('button[type=submit]')
    await pg.wait_for_url('**/tableau-de-bord.html' if role == 'admin' else '**/mes-trajets.html')
    await pg.wait_for_load_state('networkidle')


async def points_recus(pg, trajet):
    return await pg.evaluate("async (t) => (await Store.parcours(t)).nombrePoints", trajet)


async def scenario(nav):
    # ---- Chauffeur : telephone avec localisation autorisee ----------------
    tel = await nav.new_context(viewport={'width': 390, 'height': 844}, geolocation={
        'latitude': TRACE[0][0], 'longitude': TRACE[0][1], 'accuracy': 8}, permissions=['geolocation'])
    await preparer(tel)
    ch = surveiller(await tel.new_page())
    await connexion(ch, 'a.diallo@transitflow.ca', 'chauffeur')
    await ch.click('[data-trajet-en-cours] [data-lien-suivi]')
    await ch.wait_for_url('**/trajet-en-cours.html?id=*')
    trajet = ch.url.split('id=')[1]
    # Le trajet de demonstration a deja une trace (seed_demo) : on mesure ce que le test y ajoute.
    distance_initiale = await ch.evaluate(f"async () => (await Store.parcours('{trajet}')).statistiques.distanceM")
    await expect(ch.locator('[data-gps-statut]')).to_have_text('Actif', timeout=15000)
    await expect(ch.locator('[data-gps-detail]')).to_contain_text('Precision 8 m')
    await expect(ch.locator('[data-gps-detail]')).to_contain_text('envoye', timeout=15000)
    ok(f'Chauffeur : partage GPS actif sur {trajet}, premier point envoye')

    for lat, lng in TRACE[1:3]:
        await tel.set_geolocation({'latitude': lat, 'longitude': lng, 'accuracy': 10})
        await ch.wait_for_timeout(1200)
    await ch.wait_for_function(f"async () => (await Store.parcours('{trajet}')).nombrePoints >= 3", timeout=25000)
    ok('Deplacement simule : points envoyes par lots')
    await ch.screenshot(path=DOSSIER + 'chauffeur-gps.png', full_page=True)

    # ---- Administrateur : carte en direct -----------------------------------
    bureau = await nav.new_context(viewport={'width': 1440, 'height': 900})
    await preparer(bureau)
    ad = surveiller(await bureau.new_page())
    await connexion(ad, 'a.tremblay@transitflow.ca', 'admin')
    await ad.click('.tf-navbar a[href="carte.html"]')
    await ad.wait_for_url('**/carte.html')
    await expect(ad.locator('.tf-marqueur-etiquette', has_text='QC-4821')).to_be_visible(timeout=10000)
    ligne = ad.locator('[data-liste-suivi] button', has_text='Aminata Diallo')
    await expect(ligne).to_contain_text('En ligne')
    await expect(ad.locator('[data-resume]')).to_contain_text('1 trajet en cours · 1 localise')
    await expect(ad.locator('[data-carte-vide]')).to_be_hidden()
    ok('Admin : vehicule QC-4821 sur la carte en direct, signal "En ligne"')

    await ligne.click()
    await expect(ligne).to_have_class('active')
    await expect(ad.locator('.leaflet-overlay-pane path')).to_have_count(1, timeout=10000)
    await expect(ad.locator('.leaflet-popup-content')).to_contain_text('Voir le trajet')
    ok('Admin : selection du vehicule, trace et bulle d informations')

    # Le vehicule avance : le marqueur suit sans recharger la page.
    avant = await ad.locator('.tf-marqueur-etiquette', has_text='QC-4821').bounding_box()
    await tel.set_geolocation({'latitude': TRACE[3][0], 'longitude': TRACE[3][1], 'accuracy': 9})
    await ad.wait_for_function(
        "(y) => { const e = [...document.querySelectorAll('.tf-marqueur-etiquette')].find(x => x.textContent === 'QC-4821');"
        " return e && Math.abs(e.getBoundingClientRect().x - y) > 3; }", arg=avant['x'], timeout=30000)
    ok('Admin : le marqueur se deplace en direct (rafraichissement automatique)')
    await ad.wait_for_timeout(1500)  # fin des animations de la carte avant la capture
    await ad.screenshot(path=DOSSIER + 'admin-carte.png')

    # ---- Coupure de reseau cote telephone ------------------------------------
    avant_coupure = await points_recus(ad, trajet)
    await tel.set_offline(True)
    await tel.set_geolocation({'latitude': TRACE[4][0], 'longitude': TRACE[4][1], 'accuracy': 9})
    await ch.wait_for_timeout(3000)
    await expect(ch.locator('[data-gps-detail]')).to_contain_text('en attente', timeout=15000)
    assert await points_recus(ad, trajet) == avant_coupure
    await tel.set_offline(False)
    await ad.wait_for_function(f"async () => (await Store.parcours('{trajet}')).nombrePoints > {avant_coupure}",
                               timeout=30000)
    ok('Coupure de reseau : point garde puis envoye au retour du reseau')

    # ---- Fiche du trajet ----------------------------------------------------
    await ad.goto(BASE + f'/admin/trajet.html?id={trajet}')
    stats = ad.locator('[data-stats-parcours]')
    await expect(stats).to_contain_text('Distance', timeout=10000)
    await expect(stats).to_contain_text('km')
    await expect(ad.locator('[data-carte-trajet] .leaflet-overlay-pane path')).to_have_count(1)
    await expect(ad.locator('[data-lien-direct]')).to_be_visible()
    ok('Fiche trajet : parcours dessine, distance et vitesses')

    # ---- Arrivee : derniers points envoyes, suivi arrete ---------------------
    await ch.click('[data-terminer]')
    m = ch.locator('.tf-modal')
    await m.locator('[type=submit]').click()
    await ch.wait_for_url('**/mes-trajets.html')
    await ad.goto(BASE + '/admin/carte.html')
    await expect(ad.locator('[data-liste-suivi]')).to_contain_text('Aucun trajet en cours')
    await expect(ad.locator('[data-carte-vide]')).to_be_visible()
    await ad.goto(BASE + f'/admin/trajet.html?id={trajet}')
    await expect(ad.locator('[data-stats-parcours]')).to_contain_text('Points GPS')
    await expect(ad.locator('[data-lien-direct]')).to_be_hidden()
    distance = await ad.evaluate(f"async () => (await Store.parcours('{trajet}')).statistiques.distanceM")
    # 4 pas de ~31 m ; le saut entre la fin de la trace de demo et le terminus est ecarte (> 250 km/h).
    assert 100 < distance - distance_initiale < 200, (distance, distance_initiale)
    await ad.wait_for_timeout(1500)
    await ad.screenshot(path=DOSSIER + 'admin-trajet.png', full_page=True)
    ok('Arrivee : trajet retire de la carte en direct, parcours conserve')

    # ---- Localisation refusee ----------------------------------------------
    refuse = await nav.new_context(viewport={'width': 390, 'height': 844})
    await preparer(refuse)
    r = surveiller(await refuse.new_page())
    await connexion(r, 'm.traore@transitflow.ca', 'chauffeur')
    await r.goto(BASE + '/chauffeur/trajet-nouveau.html')
    await expect(r.locator('[data-plaque].active')).to_be_visible()
    await r.fill('[name=depart]', 'Sherbrooke')
    await r.fill('[name=departAdresse]', 'Terminus Sherbrooke, 60 rue Depot')
    await r.fill('[name=arrivee]', 'Montreal')
    await r.click('[data-formulaire] [type=submit]')
    try:
        await r.wait_for_url('**/trajet-en-cours.html?id=*', timeout=10000)
    except Exception:
        await r.screenshot(path=DOSSIER + 'echec-refuse.png', full_page=True)
        print('TOASTS', await r.locator('.tf-toast').all_inner_texts(), r.url)
        raise
    await expect(r.locator('[data-gps-statut]')).to_have_text('Refuse', timeout=15000)
    await expect(r.locator('[data-gps-relancer]')).to_be_visible()
    ok('Localisation refusee : message clair et bouton pour reessayer')

    for page in (ch, ad, r):
        assert not page.erreurs, page.erreurs


async def main():
    async with async_playwright() as p:
        nav = await p.chromium.launch()
        try:
            await scenario(nav)
        finally:
            await nav.close()
    print(f'\n{len(etapes)} etapes reussies — captures : {DOSSIER}')


asyncio.run(main())

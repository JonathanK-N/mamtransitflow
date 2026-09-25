"""
TransitFlow — Test de bout en bout du module d entretien (navigateur reel)
Auteur : Jonathan K-N

Rejoue dans Chromium le parcours complet d un administrateur et d un
chauffeur : ajout d un vehicule, releve du compteur, plan preventif,
bon de travail (planifie -> en cours -> termine), annulation, incident,
export CSV, couts, arrivee d un chauffeur avec son compteur, affichage
mobile. Echoue au moindre ecart ou a la moindre erreur JavaScript.

Prerequis : pip install playwright && playwright install chromium
Execution, sur une base de demonstration neuve (depuis backend/) :
    rm -f data/transitflow.db && python manage.py migrate && python manage.py seed_demo
    python manage.py runserver 5000
puis, dans un autre terminal (depuis la racine du depot) :
    python e2e/parcours_entretien.py

Variables facultatives :
  TF_E2E_URL        adresse du serveur (defaut http://127.0.0.1:5000)
  TF_E2E_BOOTSTRAP  chemin local de bootstrap.min.css, si le CDN n est pas joignable
  TF_E2E_CAPTURES   dossier ou enregistrer les captures d ecran (defaut : dossier temporaire)
"""
import asyncio
import os
import tempfile

from playwright.async_api import async_playwright, expect

BASE = os.environ.get('TF_E2E_URL', 'http://127.0.0.1:5000').rstrip('/')
MDP = 'Transit-Demo-2026'
DOSSIER = os.path.join(os.environ.get('TF_E2E_CAPTURES') or tempfile.mkdtemp(prefix='transitflow-e2e-'), '')
BOOTSTRAP = os.environ.get('TF_E2E_BOOTSTRAP')
etapes = []


def ok(msg):
    etapes.append(msg)
    print('  OK', msg, flush=True)


async def nouvelle_page(navigateur, largeur=1440, hauteur=1000):
    pg = await navigateur.new_page(viewport={'width': largeur, 'height': hauteur}, accept_downloads=True)
    if BOOTSTRAP:
        await pg.route('https://cdn.jsdelivr.net/npm/bootstrap*/**',
                       lambda r: r.fulfill(path=BOOTSTRAP, content_type='text/css'))
        await pg.route('https://fonts.googleapis.com/**', lambda r: r.fulfill(body='', content_type='text/css'))
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


async def modale(pg):
    m = pg.locator('.tf-modal')
    await expect(m).to_be_visible()
    return m


async def main():
    async with async_playwright() as p:
        nav = await p.chromium.launch()
        pg = await nouvelle_page(nav)
        try:
            await scenario(nav, pg)
        except Exception:
            await pg.screenshot(path=DOSSIER + 'echec.png', full_page=True)
            print('ERREURS NAVIGATEUR', pg.erreurs)
            raise
    print(f'\n{len(etapes)} etapes reussies — captures : {DOSSIER}')


async def scenario(nav, pg):
    await connexion(pg, 'a.tremblay@transitflow.ca', 'admin')
    await expect(pg.locator('[data-alertes]')).to_contain_text('Entretien en retard')
    ok('Tableau de bord : alertes d entretien affichees')

    # 1. Ajout d un vehicule
    await pg.goto(BASE + '/admin/vehicules.html')
    f = pg.locator('[data-formulaire]')
    await f.locator('[name=plaque]').fill('qc-9001')
    await f.locator('[name=modele]').fill('Ford Transit Connect')
    await f.locator('[name=annee]').fill('2025')
    await f.locator('[name=kilometrage]').fill('1000')
    await f.locator('[type=submit]').click()
    ligne = pg.locator('[data-liste-vehicules] tr', has_text='QC-9001')
    await expect(ligne).to_contain_text('1 000 km')
    await expect(ligne).to_contain_text('Aucun plan')
    ok('Vehicule QC-9001 ajoute (plaque normalisee, compteur 1 000 km)')
    await pg.click('[data-filtre-vehicule=maintenance]')
    await expect(pg.locator('[data-liste-vehicules] tr')).to_have_count(1)
    await expect(pg.locator('[data-liste-vehicules]')).to_contain_text('QC-2287')
    await pg.click('[data-filtre-vehicule=tous]')
    ok('Filtre par statut de vehicule')

    # 2. Fiche vehicule : releve de compteur (erreur puis succes)
    await pg.locator('[data-liste-vehicules] tr', has_text='QC-9001').locator('td').first.click()
    await pg.wait_for_url('**/vehicule.html?plaque=QC-9001')
    await expect(pg.locator('[data-compteur]')).to_have_text('1 000 km')
    await pg.click('[data-relever]')
    m = await modale(pg)
    await m.locator('[name=kilometrage]').evaluate("e => e.removeAttribute('min')")
    await m.locator('[name=kilometrage]').fill('900')
    await m.locator('[type=submit]').click()
    await expect(m.locator('[data-modale-erreur]')).to_contain_text('ne peut pas etre inferieur')
    ok('Releve inferieur refuse, erreur affichee dans la fenetre')
    await m.locator('[name=kilometrage]').fill('1500')
    await m.locator('[name=note]').fill('Controle depart')
    await m.locator('[type=submit]').click()
    await expect(pg.locator('.tf-modal')).to_have_count(0)
    await expect(pg.locator('[data-compteur]')).to_have_text('1 500 km')
    await expect(pg.locator('[data-releves]')).to_contain_text('Controle depart')
    ok('Releve 1 500 km enregistre et historise')

    # 3. Modifier la fiche (NIV invalide puis valide)
    await pg.click('[data-modifier]')
    m = await modale(pg)
    await m.locator('[name=numeroSerie]').fill('ABC')
    await m.locator('[type=submit]').click()
    await expect(m.locator('[data-modale-erreur]')).to_contain_text('NIV')
    await m.locator('[name=numeroSerie]').fill('1ftbw3xm5nka12345')
    await m.locator('[type=submit]').click()
    await expect(pg.locator('[data-informations]')).to_contain_text('1FTBW3XM5NKA12345')
    ok('Fiche modifiee (NIV valide, en majuscules)')

    # 4. Plan preventif
    await pg.click('[data-ajouter-plan]')
    m = await modale(pg)
    await m.locator('[name=type]').select_option('vidange')
    await m.locator('[name=intervalleKm]').fill('5000')
    await m.locator('[name=intervalleJours]').fill('180')
    await m.locator('[type=submit]').click()
    await expect(pg.locator('[data-plans]')).to_contain_text('Vidange et filtres')
    await expect(pg.locator('[data-plans]')).to_contain_text('6 500 km')
    await expect(pg.locator('[data-plans]')).to_contain_text('A jour')
    ok('Plan de vidange cree (prochaine a 6 500 km)')

    # 5. Planifier depuis le plan
    await pg.locator('[data-plans] [data-planifier]').click()
    m = await modale(pg)
    await m.locator('[name=fournisseur]').fill('Garage Estrie')
    await m.locator('[name=coutPieces]').fill('80')
    await m.locator('[type=submit]').click()
    lien_bon = pg.locator('[data-plans] a', has_text='BT-')
    await expect(lien_bon).to_be_visible()
    bon = (await lien_bon.inner_text()).strip()
    ok(f'Bon {bon} planifie depuis le plan')

    # 6. Demarrer / terminer depuis la page Entretien
    await lien_bon.click()
    await pg.wait_for_url(f'**/entretiens.html?bon={bon}')
    detail = pg.locator('[data-detail-bon]')
    await expect(detail).to_contain_text('Vidange et filtres')
    await detail.locator('[data-action=demarrer]').click()
    await expect(detail.locator('.tf-pill').first).to_have_text('En cours')
    await expect(detail).to_contain_text('En maintenance')
    ok('Bon demarre : vehicule passe en maintenance')

    await detail.locator('[data-action=terminer]').click()
    m = await modale(pg)
    await m.locator('[name=kilometrage]').fill('1620')
    await m.locator('[name=coutMainOeuvre]').fill('55.5')
    await m.locator('[name=notes]').fill('Huile 5W30, filtre')
    await m.locator('[type=submit]').click()
    await expect(pg.locator('.tf-modal')).to_have_count(0)
    await expect(detail.locator('.tf-pill').first).to_have_text('Termine')
    await expect(detail).to_contain_text('135,50')
    await expect(detail).to_contain_text('Huile 5W30')
    await expect(detail).to_contain_text('Actif')
    ok('Bon termine : couts 135,50 $, vehicule remis actif')

    await pg.goto(BASE + '/admin/vehicule.html?plaque=QC-9001')
    await expect(pg.locator('[data-compteur]')).to_have_text('1 620 km')
    await expect(pg.locator('[data-plans]')).to_contain_text('6 620 km')
    await pg.click('[data-onglet=bons]')
    await expect(pg.locator('[data-bons]')).to_contain_text(bon)
    await pg.screenshot(path=DOSSIER + 'parcours-vehicule.png', full_page=True)
    ok('Plan recale sur l intervention (prochaine a 6 620 km)')

    # 7. Hors service puis remise en service
    await pg.click('[data-basculer-service]')
    await expect(pg.locator('[data-statut]')).to_have_text('Hors service')
    await pg.click('[data-basculer-service]')
    await expect(pg.locator('[data-statut]')).to_have_text('Actif')
    ok('Mise hors service / remise en service')

    # 8. Incident technique deja lie a un bon (demo) : doublon refuse
    await pg.goto(BASE + '/admin/incidents.html')
    await expect(pg.locator('[data-detail]')).to_contain_text('Voir le bon de travail')
    ok('Incident : lien vers son bon de travail')
    await pg.goto(BASE + '/admin/entretiens.html?nouveau=1&incident=I-2')
    m = await modale(pg)
    await expect(m).to_contain_text('A partir de l incident')
    await expect(m.locator('[name=titre]')).to_have_value('Voyant moteur allume')
    await m.locator('[type=submit]').click()
    await expect(m.locator('[data-modale-erreur]')).to_contain_text('existe deja')
    await m.locator('[data-fermer]').first.click()
    await expect(pg.locator('.tf-modal')).to_have_count(0)
    ok('Incident deja lie a un bon : doublon refuse avec message clair')

    # 9. Nouveau bon libre + annulation
    await pg.goto(BASE + '/admin/entretiens.html')
    await pg.click('[data-nouveau-bon]')
    m = await modale(pg)
    await m.locator('[name=vehicule]').select_option('QC-7733')
    await m.locator('[name=type]').select_option('carrosserie')
    await m.locator('[name=titre]').fill('Retouche pare-chocs arriere')
    await m.locator('[type=submit]').click()
    detail = pg.locator('[data-detail-bon]')
    await expect(detail).to_contain_text('Retouche pare-chocs arriere')
    await detail.locator('[data-action=annuler]').click()
    m = await modale(pg)
    await m.locator('[name=motif]').fill('Reporte au printemps')
    await m.locator('[type=submit]').click()
    await expect(pg.locator('[data-liste-bons]')).not_to_contain_text('Retouche pare-chocs')
    await pg.click('[data-filtre-bon=annule]')
    await expect(pg.locator('[data-liste-bons]')).to_contain_text('Retouche pare-chocs')
    await expect(detail).to_contain_text('Reporte au printemps')
    ok('Bon libre cree puis annule avec motif')

    # 10. Recherche et filtre vehicule
    await pg.click('[data-filtre-bon=tous]')
    await pg.fill('[data-recherche]', bon)
    await expect(pg.locator('[data-liste-bons] tr')).to_have_count(1)
    await pg.fill('[data-recherche]', '')
    await pg.select_option('[data-filtre-vehicule]', 'QC-2287')
    await expect(pg.locator('[data-liste-bons]')).not_to_contain_text('QC-1094')
    await expect(pg.locator('[data-liste-bons]')).to_contain_text('QC-2287')
    ok('Recherche par numero de bon et filtre par vehicule')

    # 11. Export CSV
    async with pg.expect_download() as tele:
        await pg.click('[data-exporter]')
    fichier = await (await tele.value).path()
    contenu = open(fichier, encoding='utf-8-sig').read()
    assert contenu.startswith('Bon;Vehicule'), contenu[:40]
    ok('Export CSV telecharge')

    # 12. Echeances -> planifier
    await pg.click('[data-onglet=echeances]')
    ligne = pg.locator('[data-liste-echeances] tr', has_text='QC-4821')
    await ligne.locator('[data-planifier]').click()
    m = await modale(pg)
    await m.locator('[type=submit]').click()
    lien = ligne.locator('a', has_text='BT-')
    await expect(lien).to_be_visible()
    await lien.click()
    await expect(pg.locator('[data-detail-bon]')).to_contain_text('Preventif')
    await expect(pg.locator('[data-detail-bon]')).to_contain_text('QC-4821')
    ok('Echeance planifiee depuis l onglet Echeances')

    # 13. Couts
    await pg.click('[data-onglet=couts]')
    await expect(pg.locator('[data-couts-vehicules]')).to_contain_text('QC-9001')
    await expect(pg.locator('[data-couts-types]')).to_contain_text('Vidange')
    await pg.screenshot(path=DOSSIER + 'parcours-couts.png', full_page=True)
    await pg.click('[data-preset=mois]')
    await expect(pg.locator('[data-totaux]')).to_contain_text('Total')
    ok('Onglet couts : par vehicule, par type, periodes')
    assert not pg.erreurs, pg.erreurs

    # 14. Chauffeur (mobile) : arrivee avec compteur, vehicule en maintenance grise
    ch = await nouvelle_page(nav, 390, 844)
    await connexion(ch, 'a.diallo@transitflow.ca', 'chauffeur')
    await ch.click('[data-trajet-en-cours] [data-terminer]')
    m = await modale(ch)
    await expect(m).to_contain_text('48 210 km')
    await m.locator('[name=kilometrage]').fill('48290')
    await ch.screenshot(path=DOSSIER + 'chauffeur-arrivee.png')
    await m.locator('[type=submit]').click()
    await expect(ch.locator('[data-aucun-trajet]')).to_be_visible()
    ok('Chauffeur : arrivee avec compteur 48 290 km (mobile)')
    await ch.goto(BASE + '/chauffeur/trajet-nouveau.html')
    tuile = ch.locator('[data-plaque="QC-2287"]')
    await expect(tuile).to_be_disabled()
    await expect(tuile).to_contain_text('en maintenance')
    await expect(ch.locator('[data-plaque].active')).to_have_attribute('data-plaque', 'QC-4821')
    ok('Chauffeur : vehicule en maintenance non selectionnable')
    assert not ch.erreurs, ch.erreurs

    await pg.goto(BASE + '/admin/vehicule.html?plaque=QC-4821')
    await expect(pg.locator('[data-compteur]')).to_have_text('48 290 km')
    await expect(pg.locator('[data-releves]')).to_contain_text('Fin de trajet')
    ok('Compteur du chauffeur visible sur la fiche vehicule')

    # 15. Mobile admin : pas de debordement horizontal
    mob = await nouvelle_page(nav, 390, 844)
    await connexion(mob, 'a.tremblay@transitflow.ca', 'admin')
    for nom in ['entretiens.html', 'vehicule.html?plaque=QC-1094', 'vehicules.html', 'tableau-de-bord.html']:
        await mob.goto(BASE + '/admin/' + nom)
        await mob.wait_for_timeout(900)
        largeur = await mob.evaluate('document.documentElement.scrollWidth')
        await mob.screenshot(path=DOSSIER + 'mobile-' + nom.split('?')[0].replace('.html', '') + '.png',
                             full_page=True)
        assert largeur <= 390, (nom, largeur)
    ok('Mobile : aucune page ne deborde horizontalement')
    assert not mob.erreurs, mob.erreurs
    await nav.close()


asyncio.run(main())

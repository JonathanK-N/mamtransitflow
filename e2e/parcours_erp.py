"""
TransitFlow — Test de bout en bout de l ERP (navigateur reel)
Auteur : Jonathan K-N

Rejoue dans Chromium :
  1. administrateur : menus selon les applications, fiche entreprise,
     activation / desactivation d une application ;
  2. invitation d un nouveau chauffeur (lien a copier, courriel non configure) ;
  3. le chauffeur ouvre le lien, choisit son mot de passe et arrive dans son portail ;
  4. paie : paie validee, paie en brouillon, bulletin, prime ajoutee, remuneration
     du nouveau chauffeur, recalcul, validation ;
  5. portail chauffeur : ma paie (bulletin), mon vehicule, mon profil, fermeture
     d une fonction par l administrateur ;
  6. mot de passe oublie, suspension d acces, affichage mobile.
Echoue au moindre ecart ou a la moindre erreur JavaScript.

Prerequis et execution : comme e2e/parcours_entretien.py (base de demonstration neuve).
"""
import asyncio
import os
import re
import tempfile

from playwright.async_api import async_playwright, expect

BASE = os.environ.get('TF_E2E_URL', 'http://127.0.0.1:5000').rstrip('/')
MDP = 'Transit-Demo-2026'
MDP_NOUVEAU = 'Estrie-Navette-2026'
DOSSIER = os.path.join(os.environ.get('TF_E2E_CAPTURES') or tempfile.mkdtemp(prefix='transitflow-erp-'), '')
BOOTSTRAP = os.environ.get('TF_E2E_BOOTSTRAP')
etapes = []


def ok(msg):
    etapes.append(msg)
    print('  OK', msg, flush=True)


async def nouvelle_page(navigateur, largeur=1440, hauteur=1000):
    contexte = await navigateur.new_context(viewport={'width': largeur, 'height': hauteur}, accept_downloads=True)
    pg = await contexte.new_page()
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


async def connexion(pg, courriel, role, mdp=MDP):
    await pg.goto(BASE + '/index.html')
    if role == 'chauffeur':
        await pg.click('[data-role=chauffeur]')
    await pg.fill('[data-connexion] input[name=courriel]', courriel)
    await pg.fill('[data-connexion] input[name=motDePasse]', mdp)
    await pg.click('[data-connexion] button[type=submit]')
    await pg.wait_for_url('**/tableau-de-bord.html' if role == 'admin' else '**/mes-trajets.html')
    await pret(pg)


async def menus(pg):
    await expect(pg.locator('.tf-nav-link').first).to_be_visible()
    return [t.strip() for t in await pg.locator('.tf-nav-link').all_inner_texts()]


async def modale(pg):
    m = pg.locator('.tf-modal')
    await expect(m).to_be_visible()
    return m


async def pret(pg):
    """Attend la fin de l initialisation de la page (donnees chargees, formulaires branches)."""
    await pg.wait_for_selector('body[data-pret]', state='attached')


async def aller(pg, chemin):
    await pg.goto(BASE + chemin)
    await pret(pg)


def verifier_console(*pages):
    for pg in pages:
        assert not pg.erreurs, f'Erreurs JavaScript : {pg.erreurs}'


async def main():
    async with async_playwright() as p:
        nav = await p.chromium.launch()
        ad = await nouvelle_page(nav)

        # ---- 1. Administrateur : menus, entreprise, applications -------------
        await connexion(ad, 'a.tremblay@transitflow.ca', 'admin')
        liens = await menus(ad)
        assert liens == ['Tableau de bord', 'Carte', 'Trajets', 'Incidents', 'Chauffeurs', 'Paie', 'Vehicules',
                         'Entretien', 'Parametres'], liens
        await expect(ad.locator('[data-nav-entreprise]')).to_have_text('Navettes Estrie (demo)')
        ok('menus administrateur complets, nom de l entreprise dans la barre')

        await aller(ad, '/admin/parametres.html')
        await expect(ad.locator('[data-form-entreprise] input[name=nom]')).to_have_value('Navettes Estrie (demo)')
        await ad.fill('[data-form-entreprise] input[name=nom]', 'Navettes Estrie')
        await ad.fill('[data-form-entreprise] input[name=neq]', '1170000000')
        await ad.click('[data-form-entreprise] button[type=submit]')
        await expect(ad.locator('.tf-toast')).to_contain_text('enregistrees')
        await expect(ad.locator('[data-nav-entreprise]')).to_have_text('Navettes Estrie')
        ok('fiche entreprise modifiee (nom, NEQ)')

        await ad.click('[data-onglet=applications]')
        await ad.locator('label.tf-switch:has([data-module=paie])').click()
        await expect(ad.locator('.tf-nav-link', has_text='Paie')).to_have_count(0)
        await expect(ad.locator('[data-onglet-paie]')).to_be_hidden()
        await aller(ad, '/admin/paie.html')
        await expect(ad.locator('main')).to_contain_text('Fonction non disponible')
        ok('application Paie desactivee : menu retire, page bloquee')
        await aller(ad, '/admin/parametres.html#applications')
        await ad.locator('label.tf-switch:has([data-module=paie])').click()
        await expect(ad.locator('.tf-nav-link', has_text='Paie')).to_have_count(1)
        ok('application Paie reactivee')

        await ad.click('[data-onglet=courriel]')
        await expect(ad.locator('[data-etat-courriel]')).to_contain_text('Non configure')
        await ad.click('[data-onglet=paie]')
        await expect(ad.locator('[data-retenues] tr')).to_have_count(6)
        await expect(ad.locator('[data-retenues]')).to_contain_text('6,30 %')
        await expect(ad.locator('[data-retenues]')).to_contain_text('A configurer')
        await ad.screenshot(path=DOSSIER + '01-parametres-paie.png', full_page=True)
        ok('parametres de paie : 6 retenues 2026, impots a configurer')

        # ---- 2. Invitation d un nouveau chauffeur ------------------------------
        await aller(ad, '/admin/chauffeur-nouveau.html')
        f = ad.locator('[data-formulaire]')
        for nom, valeur in {'prenom': 'Kevin', 'nom': 'Lavoie', 'age': '29', 'telephone': '819-555-0199',
                            'courriel': 'k.lavoie@transitflow.ca', 'adresse': '45 rue Wellington Nord',
                            'permisNumero': 'L4521', 'permisExpiration': '2029-06-30'}.items():
            await f.locator(f'[name={nom}]').fill(valeur)
        await expect(f.locator('[name=inviter]')).to_be_checked()
        await f.locator('button[type=submit]').click()
        panneau = ad.locator('[data-compte-cree]')
        await expect(panneau).to_be_visible()
        await expect(panneau.locator('[data-message-invitation]')).to_contain_text('copiez ce lien')
        lien = await panneau.locator('[data-lien-invitation]').input_value()
        assert re.search(r'/invitation\.html\?jeton=[\w-]{30,}$', lien), lien
        await ad.screenshot(path=DOSSIER + '02-invitation-creee.png', full_page=True)
        ok('chauffeur cree avec invitation : lien a copier affiche')

        await panneau.locator('[data-lien-fiche]').click()
        await pret(ad)
        await expect(ad.locator('[data-acces-pastille]')).to_contain_text('Invite')
        await expect(ad.locator('[data-acces-actions]')).to_contain_text('Renvoyer l invitation')
        ok('fiche : acces au portail « Invite »')

        # ---- 3. Le chauffeur accepte l invitation -------------------------------
        ch = await nouvelle_page(nav)
        await ch.goto(lien)
        await expect(ch.locator('[data-titre]')).to_have_text('Rejoindre Navettes Estrie')
        await expect(ch.locator('[data-sous-titre]')).to_contain_text('Bonjour Kevin')
        await expect(ch.locator('input[name=courriel]')).to_have_value('k.lavoie@transitflow.ca')
        assert 'jeton' not in ch.url, 'le jeton doit disparaitre de la barre d adresse'
        await ch.fill('input[name=motDePasse]', MDP_NOUVEAU)
        await ch.fill('input[name=confirmation]', 'Autre-Chose-2026')
        await ch.click('button[type=submit]')
        await expect(ch.locator('[data-erreur]')).to_contain_text('pas identiques')
        await ch.screenshot(path=DOSSIER + '03-invitation-chauffeur.png', full_page=True)
        await ch.fill('input[name=confirmation]', MDP_NOUVEAU)
        await ch.click('button[type=submit]')
        await ch.wait_for_url('**/chauffeur/mes-trajets.html')
        await pret(ch)
        liens = await menus(ch)
        assert liens == ['Mes trajets', 'Nouveau trajet', 'Signaler un incident', 'Mon vehicule', 'Ma paie',
                         'Mon profil'], liens
        ok('le chauffeur choisit son mot de passe et arrive dans son portail')

        await ch.goto(lien)
        await expect(ch.locator('[data-invalide]')).to_be_visible()
        ok('le lien d invitation ne sert qu une fois')

        await ad.reload()
        await pret(ad)
        await expect(ad.locator('[data-acces-pastille]')).to_contain_text('Actif')
        ok('fiche : acces « Actif » apres activation')

        # ---- 4. Paie ------------------------------------------------------------
        await aller(ad, '/admin/paie.html')
        await expect(ad.locator('[data-periodes] tr')).to_have_count(2)
        await expect(ad.locator('[data-periodes] tr').nth(1)).to_contain_text('Validee')
        await expect(ad.locator('[data-kpi="net"]')).not_to_have_text('—')
        await ad.locator('[data-periodes] tr').nth(1).click()
        await expect(ad.locator('[data-bulletins] tr')).to_have_count(4)
        await expect(ad.locator('[data-bulletins]')).to_contain_text('80 h + 10 h sup.')
        await expect(ad.locator('[data-detail-actions]')).to_contain_text('Marquer comme payee')
        ok('paie validee : 4 bulletins, heures supplementaires calculees')

        await ad.locator('[data-bulletins] tr', has_text='Diallo').click()
        bulletin = ad.locator('[data-bulletin] .tf-bulletin')
        await expect(bulletin).to_contain_text('Navettes Estrie')
        await expect(bulletin).to_contain_text('Regime de rentes du Quebec')
        await expect(bulletin).to_contain_text('2 149,08')
        await expect(ad.locator('[data-ajout]')).to_have_count(0)  # paie validee : non modifiable
        ok('bulletin d Aminata Diallo : net 2 149,08 $, lecture seule')

        # Remuneration du nouveau chauffeur, puis la paie en brouillon.
        await ad.click('[data-onglet=remuneration]')
        await ad.locator('[data-profils] tr', has_text='Kevin Lavoie').click()
        m = await modale(ad)
        await m.locator('[name=tauxHoraire]').fill('23.75')
        await m.locator('button[type=submit]').click()
        await expect(ad.locator('[data-profils] tr', has_text='Kevin Lavoie')).to_contain_text('23,75')
        ok('remuneration du nouveau chauffeur : 23,75 $ / h')

        await ad.click('[data-onglet=paies]')
        await ad.locator('[data-periodes] tr').first.click()
        await ad.locator('[data-action-paie=calculer]').click()
        await expect(ad.locator('.tf-toast', has_text='recalculee')).to_be_visible()
        await expect(ad.locator('[data-bulletins] tr')).to_have_count(5)
        await ad.locator('[data-bulletins] tr', has_text='Traore').click()
        net_avant = await ad.locator('.tf-bulletin-totaux .net .tf-mono').inner_text()
        await ad.locator('[data-ajout=gain]').click()
        m = await modale(ad)
        await m.locator('[name=libelle]').fill('Prime de nuit')
        await m.locator('[name=montant]').fill('100')
        await m.locator('button[type=submit]').click()
        await expect(ad.locator('[data-bulletin]')).to_contain_text('Prime de nuit')
        net_apres = await ad.locator('.tf-bulletin-totaux .net .tf-mono').inner_text()
        assert net_apres != net_avant, (net_avant, net_apres)
        await ad.screenshot(path=DOSSIER + '04-bulletin-admin.png', full_page=True)
        ok(f'prime de 100 $ ajoutee : net {net_avant} -> {net_apres}')

        await ad.locator('[data-supprimer-ligne]').click()
        await expect(ad.locator('[data-bulletin]')).not_to_contain_text('Prime de nuit')
        ok('ligne manuelle retiree')

        async with ad.expect_download() as telechargement:
            await ad.locator('[data-action-paie=exporter]').click()
        contenu = open(await (await telechargement.value).path(), encoding='utf-8-sig').read()
        assert contenu.startswith('Bulletin;Chauffeur') and 'Kevin Lavoie' in contenu, contenu[:200]
        ok('export CSV du journal de paie')

        await ad.locator('[data-action-paie=valider]').click()
        await expect(ad.locator('[data-detail-statut]')).to_contain_text('Validee')
        ok('paie en brouillon validee')

        # ---- 5. Portail chauffeur -------------------------------------------------
        di = await nouvelle_page(nav)
        await connexion(di, 'a.diallo@transitflow.ca', 'chauffeur')
        await aller(di, '/chauffeur/paie.html')
        await expect(di.locator('[data-bulletins] tr')).to_have_count(2)
        await di.locator('[data-bulletins] tr').last.click()
        await expect(di.locator('[data-bulletin]')).to_contain_text('2 149,08')
        await expect(di.locator('[data-bulletin]')).not_to_contain_text('employeur)')
        await di.screenshot(path=DOSSIER + '05-bulletin-chauffeur.png', full_page=True)
        ok('portail : Aminata voit ses 2 bulletins, sans les cotisations employeur')

        await aller(di, '/chauffeur/vehicule.html')
        await expect(di.locator('[data-plaque]')).to_have_text('QC-4821')
        await expect(di.locator('[data-source]')).to_contain_text('trajet en cours')
        await expect(di.locator('[data-entretiens] li').first).to_be_visible()
        ok('portail : mon vehicule (QC-4821, prochains entretiens)')

        await aller(ch, '/chauffeur/profil.html')
        await ch.fill('[data-form-profil] input[name=telephone]', '819-555-0100')
        await ch.click('[data-form-profil] button[type=submit]')
        await expect(ch.locator('.tf-toast').last).to_be_visible()
        messages = await ch.locator('.tf-toast').all_inner_texts()
        assert any('Coordonnees' in t for t in messages), messages
        ok('portail : le chauffeur modifie son telephone')

        # L administrateur ferme la paie et les incidents dans le portail.
        await aller(ad, '/admin/parametres.html#portail')
        await ad.locator('label.tf-switch:has([data-droit=paie])').click()
        await expect(ad.locator('.tf-toast', has_text='Enregistre')).to_be_visible()
        await ad.locator('label.tf-switch:has([data-droit=incidents])').click()
        await expect(ad.locator('[data-droit=incidents]')).not_to_be_checked()
        await di.evaluate("sessionStorage.removeItem('transitflow.entreprise')")
        await aller(di, '/chauffeur/mes-trajets.html')
        liens = await menus(di)
        assert 'Ma paie' not in liens and 'Signaler un incident' not in liens, liens
        await expect(di.locator('a[href^="incident-nouveau.html"]:visible')).to_have_count(0)
        await aller(di, '/chauffeur/paie.html')
        await expect(di.locator('main')).to_contain_text('Fonction non disponible')
        ok('portail ferme par l administrateur : menus, boutons et page bloques')

        # ---- 6. Mot de passe oublie, suspension, mobile ---------------------------
        anon = await nouvelle_page(nav)
        await anon.goto(BASE + '/index.html')
        await expect(anon.locator('[data-sous-titre]')).to_contain_text('Navettes Estrie')
        await anon.click('[data-oubli]')
        await anon.fill('[data-form-oubli] input[name=courriel]', 'k.lavoie@transitflow.ca')
        await anon.click('[data-form-oubli] button[type=submit]')
        await expect(anon.locator('[data-oubli-message]')).to_contain_text('Si un compte existe')
        ok('mot de passe oublie : reponse identique que le compte existe ou non')

        await aller(ad, '/admin/chauffeurs.html')
        await expect(ad.locator('[data-liste-chauffeurs] tr', has_text='Kevin Lavoie')).to_contain_text('Actif')
        await ad.locator('[data-liste-chauffeurs] tr', has_text='Kevin Lavoie').locator('a').click()
        await pret(ad)
        await ad.locator('[data-action-acces=suspendre]').click()
        await expect(ad.locator('[data-acces-pastille]')).to_contain_text('Desactive')
        await anon.goto(BASE + '/index.html')
        await anon.click('[data-role=chauffeur]')
        await anon.fill('[data-connexion] input[name=courriel]', 'k.lavoie@transitflow.ca')
        await anon.fill('[data-connexion] input[name=motDePasse]', MDP_NOUVEAU)
        await anon.click('[data-connexion] button[type=submit]')
        await expect(anon.locator('[data-erreur]')).to_be_visible()
        ok('acces suspendu : le chauffeur ne peut plus se connecter')

        mob = await nouvelle_page(nav, 390, 844)
        await connexion(mob, 'm.traore@transitflow.ca', 'chauffeur')
        for nom in ('mes-trajets', 'vehicule', 'profil'):
            await aller(mob, f'/chauffeur/{nom}.html')
            largeur = await mob.evaluate('document.documentElement.scrollWidth')
            assert largeur <= 390, f'{nom} deborde en largeur sur mobile ({largeur}px)'
            await mob.screenshot(path=DOSSIER + f'06-mobile-{nom}.png', full_page=True)
        mob_inv = await nouvelle_page(nav, 390, 844)
        await mob_inv.goto(BASE + '/invitation.html?jeton=inconnu')
        await expect(mob_inv.locator('[data-invalide]')).to_be_visible()
        assert await mob_inv.evaluate('document.documentElement.scrollWidth') <= 390
        await mob_inv.screenshot(path=DOSSIER + '06-mobile-invitation-invalide.png', full_page=True)
        ok('affichage mobile du portail et de la page d invitation sans debordement')

        verifier_console(ad, ch, di, anon, mob, mob_inv)
        ok('aucune erreur JavaScript')
        await nav.close()
    print(f'\n{len(etapes)} etapes reussies. Captures : {DOSSIER}')


if __name__ == '__main__':
    asyncio.run(main())

import {test,expect} from '@playwright/test'
test.use({actionTimeout:20000})

async function fits(page:any){const info=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,overflow:[...document.querySelectorAll('body *')].map(e=>({tag:e.tagName,cls:e.className,right:e.getBoundingClientRect().right})).filter(e=>e.right>innerWidth+1).slice(0,8)}));expect(info.scroll,JSON.stringify(info)).toBeLessThanOrEqual(info.width)}

test('Pages publiques, connexion, inscription et récupération sans débordement',async({page})=>{
 for(const path of ['/', '/connexion', '/commencer']){
  await page.goto(path);await expect(page.locator('main').first()).toBeVisible();await fits(page)
 }
 await page.goto('/connexion');await page.getByRole('button',{name:'Mot de passe oublié ?'}).click()
 await expect(page.getByLabel('Adresse courriel')).toBeVisible();await fits(page)
})

test('Manifest, cache statique, démarrage privé et reconnexion',async({page,context,request})=>{
 const manifest=await request.get('/manifest.webmanifest');expect(manifest.ok()).toBeTruthy()
 const data=await manifest.json();expect(data.name).toBe('TransitFlow');expect(data.display).toBe('standalone');expect(data.start_url).toBe('/app')
 for(const icon of data.icons){expect((await request.get(icon.src)).ok()).toBeTruthy()}
 await page.goto('/app');await expect(page.getByRole('button',{name:'Se connecter',exact:true})).toBeVisible()
 await page.evaluate(()=>navigator.serviceWorker.ready)
 await page.reload();await page.evaluate(()=>navigator.serviceWorker.ready)
 await expect.poll(()=>page.evaluate(()=>!!navigator.serviceWorker.controller)).toBeTruthy()
 if(['iphone','ipad'].includes(test.info().project.name)){
  await page.locator('.pwa-install summary').click()
  await expect(page.locator('.pwa-install p')).toContainText('Dans Safari')
 }
 if(test.info().project.name==='chromium'){
  const session=await context.newCDPSession(page)
  const checked=await session.send('Page.getAppManifest');expect(checked.errors).toEqual([])
  const installability=await session.send('Page.getInstallabilityErrors');expect(installability.installabilityErrors).toEqual([])
  await session.detach()
 }
 await context.setOffline(true);await page.reload().catch(error=>{if(!['iphone','ipad'].includes(test.info().project.name))throw error})
 await expect(page.getByText('Vous êtes hors connexion. Les données et enregistrements nécessitent Internet.')).toBeVisible()
 await page.getByLabel('Adresse courriel').fill('offline@example.test');await page.getByLabel('Mot de passe',{exact:true}).fill('Mot-de-passe-934!')
 await page.getByRole('button',{name:'Se connecter',exact:true}).click();await expect(page.getByRole('alert')).toContainText('hors connexion')
 const urls=await page.evaluate(async()=>{const entries=await Promise.all((await caches.keys()).map(async key=>(await (await caches.open(key)).keys()).map(r=>r.url)));return entries.flat()})
 expect(urls.length).toBeGreaterThan(0);expect(urls.some(url=>/\/api\/|token=|invitation=|reset=/.test(url))).toBeFalsy()
 await context.setOffline(false);await expect(page.getByText('Connexion rétablie')).toBeVisible();await fits(page)
})

test('Session, modules autorisés, cartes mobiles, formulaire et déconnexion',async({page,request})=>{
 const email=`responsive-${Date.now()}-${test.info().project.name}@example.test`,password='Responsive-Recette-934!'
 const registered=await request.post('/api/v2/auth/register',{data:{name:'Direction mobile',email,password,organization:{name:'Transport mobile',country:'GN',currency:'GNF',timezone:'Africa/Conakry',activities:['freight']}}})
 expect(registered.status()).toBe(201);const account=await registered.json()
 const headers={Authorization:'Bearer '+account.access,'X-Organization':account.organizations[0].id}
 const create=async(path:string,data:any)=>{const r=await request.post('/api/v2/'+path,{headers,data});expect(r.ok(),await r.text()).toBeTruthy();return await r.json()}
 const driverEmail='driver-'+email
 const driver=await create('employees',{name:'Chauffeur mobile',email:driverEmail,job:'driver',phone:'+224600000000'})
 const vehicle=await create('vehicles',{plate:'MOB-'+Date.now(),name:'Camion mobile',capacity:20,capacity_unit:'t'})
 await create('maintenance',{title:'Entretien mobile',vehicle:vehicle.id,due_date:new Date(Date.now()+86400000).toISOString().slice(0,10),cost:'100'})
 await create('incidents',{reference:'INC-'+Date.now(),title:'Incident mobile',vehicle:vehicle.id,occurred_at:new Date().toISOString(),description:'Constat de recette',estimated_cost:'0'})
 await create('missions',{reference:'MOBILE-'+Date.now(),vehicle:vehicle.id,driver:driver.id,origin:'Conakry',destination:'Kindia',departure:new Date(Date.now()+3600000).toISOString(),arrival:new Date(Date.now()+18000000).toISOString()})
 await page.goto('/connexion');await page.getByLabel('Adresse courriel').fill(email);await page.getByLabel('Mot de passe',{exact:true}).fill(password);await page.getByRole('button',{name:'Se connecter',exact:true}).click()
 await expect(page.locator('.workspace')).toBeVisible();await page.reload();await expect(page.locator('.workspace')).toBeVisible()
 const mobile=(page.viewportSize()?.width||1280)<=600
 async function nav(name:string){if((page.viewportSize()?.width||1280)<=900)await page.getByRole('button',{name:'Menu',exact:true}).click();await page.locator('.sidebar').getByRole('button',{name,exact:true}).click();await expect(page.locator('.loading-panel')).toHaveCount(0);await fits(page)}
 for(const name of ['Personnel','Missions','Flotte','Entretien','Incidents','Facturation','Paramètres','Applications','Terrain & notifications']){await nav(name);if(mobile&&['Personnel','Missions','Flotte','Entretien','Incidents'].includes(name))await expect(page.locator('.mobile-records')).toBeVisible()}
 await nav('Personnel');await expect(page.locator(mobile?'.mobile-records':'.resource-panel table').getByText('Chauffeur mobile',{exact:true})).toBeVisible()
 await page.locator(mobile?'.mobile-records':'.resource-panel table').getByRole('button',{name:'Chauffeur mobile',exact:true}).click();await expect(page.getByRole('dialog')).toBeVisible();await fits(page)
 await page.getByRole('dialog').locator('.editor-head').getByRole('button',{name:'Fermer',exact:true}).click()
 const invitation=await create('team',{email:driverEmail,role:'driver'})
 const joined=await request.post('/api/v2/auth/register',{data:{name:'Chauffeur mobile',email:driverEmail,password,invitation:new URL(invitation.link).searchParams.get('invitation')}})
 expect(joined.status()).toBe(201)
 await page.evaluate(()=>localStorage.setItem('transitflow.positions.test','[{"latitude":1}]'))
 if(mobile){await page.getByRole('navigation',{name:'Navigation mobile'}).getByRole('button',{name:'Missions',exact:true}).click();await expect(page.locator('.mobile-records')).toBeVisible();await page.getByRole('navigation',{name:'Navigation mobile'}).getByRole('button',{name:'Plus',exact:true}).click()}else if((page.viewportSize()?.width||1280)<=900)await page.getByRole('button',{name:'Menu',exact:true}).click()
 await page.getByRole('button',{name:'Se déconnecter'}).click();await expect(page.getByRole('button',{name:'Se connecter',exact:true})).toBeVisible();await page.reload();await expect(page.locator('.workspace')).toHaveCount(0)
 expect(await page.evaluate(()=>localStorage.getItem('transitflow.positions.test'))).toBeNull()
 await page.getByLabel('Adresse courriel').fill(driverEmail);await page.getByLabel('Mot de passe',{exact:true}).fill(password);await page.getByRole('button',{name:'Se connecter',exact:true}).click()
 await expect(page.locator('.workspace')).toBeVisible()
 if((page.viewportSize()?.width||1280)<=900)await page.getByRole('button',{name:'Menu',exact:true}).click()
 await expect(page.locator('.sidebar').getByRole('button',{name:'Personnel',exact:true})).toHaveCount(0)
 await expect(page.locator('.sidebar').getByRole('button',{name:'Missions',exact:true})).toBeVisible()
 if((page.viewportSize()?.width||1280)<=900)await page.getByRole('button',{name:'Fermer le menu',exact:true}).click()
 if(mobile){await expect(page.getByRole('navigation',{name:'Navigation mobile'}).getByRole('button',{name:'Terrain',exact:true})).toBeVisible();await page.getByRole('navigation',{name:'Navigation mobile'}).getByRole('button',{name:'Terrain',exact:true}).click()}else await nav('Terrain & notifications')
 await page.getByRole('button',{name:'Nouvelle déclaration',exact:true}).click()
 await page.getByRole('combobox',{name:'Mission',exact:true}).selectOption({index:1})
 await page.getByLabel('Type de déclaration').selectOption('check')
 await page.getByLabel('Objet',{exact:true}).fill('Contrôle mobile')
 await page.getByLabel('Compteur kilométrique').fill('12000')
 for(const name of ['Freins','Pneus','Éclairage','Niveaux et fuites','Équipements de sécurité','Documents du véhicule'])await page.getByRole('combobox',{name,exact:true}).selectOption('ok')
 await fits(page);await page.getByRole('button',{name:'Enregistrer la déclaration',exact:true}).click()
 await expect(page.getByRole('heading',{name:'Contrôle mobile',exact:true})).toBeVisible()
 await page.locator('.field-tabs').getByRole('button',{name:/^Notifications/}).click()
 await expect(page.locator('.field-help').filter({hasText:'actualisées toutes les minutes'})).toBeVisible()
 const read=page.getByRole('button',{name:'Marquer comme lu',exact:true})
 if(await read.count()){await read.first().click();await expect(page.locator('.field-card .status').filter({hasText:/^Lu$/}).first()).toBeVisible()}
 const cached=await page.evaluate(async()=>{const keys=await caches.keys();return (await Promise.all(keys.map(async key=>(await (await caches.open(key)).keys()).map(request=>request.url)))).flat()})
 expect(cached.some(url=>url.includes('/api/'))).toBeFalsy()
 await page.screenshot({path:`test-results/responsive-${test.info().project.name}.png`,fullPage:true})
})

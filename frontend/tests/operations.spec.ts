import {test,expect} from '@playwright/test'
import {mkdirSync,writeFileSync} from 'node:fs'
import {dirname} from 'node:path'

test('Centre : 100 marqueurs, carte conservée, tuiles indisponibles et aucun historique automatique',async({page,request},info)=>{
 test.setTimeout(120000)
 if(info.project.name==='small')await page.setViewportSize({width:360,height:740})
 const stamp=Date.now()+'-'+info.project.name,email='operations-volume-'+stamp+'@example.test',password='Operations-Test-938!'
 const response=await request.post('/api/v2/auth/register',{data:{name:'TEST Volume Exploitation',email,password,organization:{name:'TEST Exploitation Volume '+stamp,country:'GN',currency:'USD',timezone:'Africa/Conakry',activities:['freight']}}});expect(response.status()).toBe(201)
 const account=await response.json(),org=account.organizations[0].id,headers={Authorization:'Bearer '+account.access,'X-Organization':org}
 const live=await (await request.get('/api/v2/tracking',{headers})).json()
 let offset=0,calls=0,history=0
 await page.route('https://tile.openstreetmap.org/**',route=>route.abort())
 await page.route('**/api/v2/tracking',route=>{calls++;route.fulfill({json:{...live,server_time:new Date().toISOString(),missions:Array.from({length:100},(_,n)=>({id:'test-marker-'+n,organization:org,reference:'TEST-'+n,plate:'TEST-'+n,vehicle:'Camion TEST',driver:'Chauffeur TEST',origin:'A',destination:'B',started_at:new Date().toISOString(),state:'online',last:{timestamp:new Date().toISOString(),latitude:9.537+(n%10)*.002+offset,longitude:-13.678+Math.floor(n/10)*.002+offset,accuracy:5,speed:0}}))}})})
 page.on('request',req=>{if(/\/missions\/[^/]+\/positions/.test(req.url()))history++})
 await page.goto('/connexion');await page.getByLabel('Adresse courriel').fill(email);await page.getByLabel('Mot de passe',{exact:true}).fill(password);await page.getByRole('button',{name:'Se connecter',exact:true}).click()
 const started=Date.now(),center=page.locator('.operations-center'),markers=center.locator('.leaflet-interactive');await expect(markers).toHaveCount(100)
 const initialMs=Date.now()-started
 await page.evaluate(()=>{(window as any).__mapNode=document.querySelector('.leaflet-container');(window as any).__markerNode=document.querySelector('.leaflet-interactive')})
 await center.getByRole('button',{name:'Agrandir la carte',exact:true}).click();await center.locator('.leaflet-control-zoom-in').click();await page.waitForTimeout(350)
 const map=center.getByTestId('tracking-map'),box=await map.boundingBox();expect(box).not.toBeNull();await page.mouse.move(box!.x+box!.width*.3,box!.y+box!.height*.3);await page.mouse.down();await page.mouse.move(box!.x+box!.width*.3+60,box!.y+box!.height*.3+50,{steps:5});await page.mouse.up();await page.waitForTimeout(350)
 const transform=await center.locator('.leaflet-map-pane').getAttribute('style'),path=await markers.first().getAttribute('d'),before=calls
 offset=.001;const changed=Date.now();await page.evaluate(()=>document.dispatchEvent(new Event('visibilitychange')))
 await expect.poll(()=>calls).toBeGreaterThan(before);await expect.poll(()=>markers.first().getAttribute('d')).not.toBe(path)
 expect(await page.evaluate(()=>document.querySelector('.leaflet-container')===(window as any).__mapNode&&document.querySelector('.leaflet-interactive')===(window as any).__markerNode)).toBeTruthy()
 expect(await center.locator('.leaflet-map-pane').getAttribute('style')).toBe(transform);expect(history).toBe(0);expect(calls).toBeLessThanOrEqual(before+2)
 await page.getByRole('button',{name:'Fermer la carte',exact:true}).click();await center.getByRole('navigation',{name:'Vues de l’exploitation'}).getByRole('button',{name:'Missions',exact:true}).click();await expect(center.getByText('Aucune mission ou commande pour ce filtre.')).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy()
 const pathProof=info.outputPath('operations-volume.json');mkdirSync(dirname(pathProof),{recursive:true});writeFileSync(pathProof,JSON.stringify({profile:info.project.name,markers:100,initial_ms:initialMs,refresh_ms:Date.now()-changed,tracking_calls:calls,history_calls:history,map_preserved:true,markers_preserved:true,pan_zoom_preserved:true,tiles_failure_tolerated:true},null,2))
})

test('Centre : affectation, deux sessions GPS, conversation réutilisée, alertes et fin de mission',async({page,browser,request},info)=>{
 test.setTimeout(360000)
 if(info.project.name==='small')await page.setViewportSize({width:360,height:740})
 const stamp=Date.now()+'-'+info.project.name,password='Operations-Test-938!',email='operations-owner-'+stamp+'@example.test',driverEmail='operations-driver-'+stamp+'@example.test'
 const registration=await request.post('/api/v2/auth/register',{data:{name:'Direction TEST Exploitation',email,password,organization:{name:'TEST Exploitation '+stamp,country:'GN',currency:'USD',timezone:'Africa/Conakry',activities:['freight']}}})
 expect(registration.status()).toBe(201)
 const owner=await registration.json(),org=owner.organizations[0].id,headers={Authorization:'Bearer '+owner.access,'X-Organization':org}
 const proof:any={profile:info.project.name,organization:org,owner_email:email,status:'running'},proofPath=info.outputPath('operations-proof.json');mkdirSync(dirname(proofPath),{recursive:true});const save=(stage:string)=>{proof.stage=stage;writeFileSync(proofPath,JSON.stringify(proof,null,2))};save('registered')
 const post=async(path:string,data:any={},h=headers)=>{const r=await request.post('/api/v2/'+path,{headers:h,data});const detail=path+' '+(await r.text()).slice(0,600);expect(r.status(),detail).toBeGreaterThanOrEqual(200);expect(r.status(),detail).toBeLessThan(300);return r.json()}
 const get=async(path:string)=>{const r=await request.get('/api/v2/'+path,{headers});expect(r.status()).toBe(200);return r.json()}
 const vehicle=await post('vehicles',{plate:'OPS-'+stamp,name:'Camion TEST Exploitation',capacity:1000,capacity_unit:'kg'}),customer=await post('partners',{name:'Client TEST Exploitation '+stamp})
 const invite=await post('team',{email:driverEmail,role:'driver'})
 const joined=await request.post('/api/v2/auth/register',{data:{name:'Chauffeur TEST Exploitation',email:driverEmail,password,invitation:new URL(invite.link).searchParams.get('invitation')}});expect(joined.status()).toBe(201)
 const driverAccount=await joined.json(),driver=(await get('employees')).results.find((x:any)=>x.email===driverEmail),driverHeaders={Authorization:'Bearer '+driverAccount.access,'X-Organization':org}
 const extraVehicle=await post('vehicles',{plate:'OPS-PLAN-'+stamp,name:'Camion planifié TEST'}),workshopVehicle=await post('vehicles',{plate:'OPS-WORK-'+stamp,name:'Camion atelier TEST'}),extraDriver=await post('employees',{name:'Chauffeur planning TEST',job:'driver'}),otherCustomer=await post('partners',{name:'Client planning TEST '+stamp})
 const now=Date.now(),base={driver:extraDriver.id,vehicle:extraVehicle.id,origin:'TEST Dépôt',destination:'TEST Client'}
 const late=await post('missions',{...base,departure:new Date(now-1800000).toISOString(),arrival:new Date(now+1800000).toISOString()}),planned=await post('missions',{...base,departure:new Date(now+10800000).toISOString(),arrival:new Date(now+14400000).toISOString()})
 const workshop=await post('maintenance',{vehicle:workshopVehicle.id,title:'Intervention TEST Exploitation'});await post('maintenance/'+workshop.id+'/actions/start')
 const done=await post('missions',{driver:driver.id,vehicle:vehicle.id,origin:'TEST Départ livré',destination:'TEST Livraison',departure:new Date(now-7200000).toISOString(),arrival:new Date(now-3600000).toISOString()});await post('missions/'+done.id+'/actions/start');await post('missions/'+done.id+'/actions/complete',{loaded_quantity:'0',delivered_quantity:'0'})
 const order=await post('orders',{customer:customer.id,origin:'Conakry',destination:'Kindia',planned_date:(await get('operations/center')).today});await post('orders/'+order.id+'/actions/confirm')
 Object.assign(proof,{vehicle:vehicle.id,driver:driver.id,customer:customer.id,order:order.id});save('setup')
 const login=async(p:any,account:string)=>{await p.goto('/connexion');await p.getByLabel('Adresse courriel').fill(account);await p.getByLabel('Mot de passe',{exact:true}).fill(password);await p.getByRole('button',{name:'Se connecter',exact:true}).click();await expect(p.locator('.workspace')).toBeVisible()}
 let driverContext:any,trip:any
 try{
  await login(page,email);const center=page.locator('.operations-center');await expect(center).toBeVisible()
  await expect(center.locator('[data-operation="'+late.id+'"]')).toContainText('Horaire dépassé')
  await expect(center.locator('[data-operation="'+planned.id+'"]')).toContainText('Planifiée')
  await expect(center.locator('[data-operation="'+done.id+'"]')).toContainText('Terminée')
  await center.getByRole('navigation',{name:'Vues de l’exploitation'}).getByRole('button',{name:'Flotte',exact:true}).click();await expect(center.locator('.operations-resources')).toContainText('En maintenance');await center.getByRole('navigation',{name:'Vues de l’exploitation'}).getByRole('button',{name:'Missions',exact:true}).click()
  await center.getByRole('navigation',{name:'Filtres missions'}).getByRole('button',{name:'À affecter',exact:true}).click()
  let card=center.locator('[data-operation="'+order.id+'"]');await expect(card).toBeVisible();await card.getByRole('button',{name:'Affecter',exact:true}).click()
  const dialog=page.getByRole('dialog');await expect(dialog.getByLabel('Chauffeur',{exact:true})).toContainText(driver.name);await dialog.getByLabel('Chauffeur',{exact:true}).selectOption(driver.id);await dialog.getByLabel('Véhicule',{exact:true}).selectOption(vehicle.id);await dialog.getByRole('button',{name:/Enregistrer/}).click();await expect(dialog).toHaveCount(0);await expect(center.locator('[data-operation="'+order.id+'"]')).toHaveCount(0)
  trip=(await get('missions')).results.find((x:any)=>x.order===order.id);proof.mission=trip.id;save('assigned')
  await center.getByRole('navigation',{name:'Filtres missions'}).getByRole('button',{name:'Toutes',exact:true}).click();card=center.locator('[data-operation="'+trip.id+'"]');await expect(card).toBeVisible()
  await card.getByRole('button',{name:'Voir client',exact:true}).click();await expect(page.getByRole('heading',{name:customer.name,exact:true})).toBeVisible();await page.goto('/app#operations');await expect(center).toBeVisible()
  driverContext=await browser.newContext({...info.project.use,baseURL:process.env.TF_TEST_URL||'http://127.0.0.1:8000',permissions:['geolocation'],geolocation:{latitude:9.537,longitude:-13.678,accuracy:5}} as any)
  await driverContext.addInitScript(()=>{const geo=navigator.geolocation,normalize=(p:any)=>({coords:p.coords,timestamp:p.timestamp>Date.now()*10?p.timestamp/1000:p.timestamp});const watch=geo.watchPosition.bind(geo),current=geo.getCurrentPosition.bind(geo);geo.watchPosition=(ok,error,options)=>watch(p=>ok(normalize(p)),e=>{if(e.code!==2)error?.(e)},options);geo.getCurrentPosition=(ok,error,options)=>current(p=>ok(normalize(p)),error,options)})
  const driverPage=await driverContext.newPage();await login(driverPage,driverEmail);driverPage.on('dialog',d=>d.accept());await driverPage.getByRole('button',{name:'Démarrer',exact:true}).click()
  await expect(driverPage.getByTestId('driver-tracking')).toBeVisible();const authorize=driverPage.getByRole('button',{name:/Autoriser|Activer le GPS/});if(await authorize.count())await authorize.first().click()
  await driverContext.setGeolocation({latitude:9.5371,longitude:-13.6781,accuracy:5})
  await center.getByRole('navigation',{name:'Vues de l’exploitation'}).getByRole('button',{name:'Synthèse',exact:true}).click()
  await expect.poll(async()=> (await get('missions/'+trip.id+'/positions')).positions?.length||0,{timeout:60000}).toBeGreaterThan(0)
  await expect(center.locator('.leaflet-interactive')).toHaveCount(1)
  const marker=center.locator('.leaflet-interactive').first();const firstPath=await marker.getAttribute('d');await marker.evaluate(el=>{(window as any).__operationsMarker=el})
  await driverPage.waitForTimeout(11000)
  await driverContext.setGeolocation({latitude:9.541,longitude:-13.671,accuracy:5})
  await expect.poll(()=>marker.getAttribute('d'),{timeout:60000}).not.toBe(firstPath)
  expect(await marker.evaluate(el=>el===(window as any).__operationsMarker)).toBeTruthy();proof.marker_updated_in_place=true;save('gps')
  await center.getByRole('navigation',{name:'Vues de l’exploitation'}).getByRole('button',{name:'Missions',exact:true}).click();card=center.locator('[data-operation="'+trip.id+'"]');await expect(card).toContainText('En cours')
  await card.getByRole('button',{name:'Contacter chauffeur',exact:true}).click();await expect(page.locator('.messaging')).toBeVisible();const first=(await get('messaging/conversations')).results.find((x:any)=>x.kind==='direct');expect(first).toBeTruthy()
  await page.goto('/app#operations');await expect(center).toBeVisible();await center.locator('[data-operation="'+trip.id+'"]') .getByRole('button',{name:'Contacter chauffeur',exact:true}).click();expect((await get('messaging/conversations')).results.filter((x:any)=>x.kind==='direct')).toHaveLength(1);proof.conversation=first.id
  await page.goto('/app#operations');await expect(center).toBeVisible();await post('missions/'+trip.id+'/tracking',{state:'unavailable'},driverHeaders)
  await expect(center.locator('.operations-alerts')).toContainText('Signal GPS interrompu')
  const incident=await post('incidents',{reference:'INC-TEST-'+stamp,vehicle:vehicle.id,mission:trip.id,title:'Incident TEST Exploitation',occurred_at:new Date().toISOString(),severity:'minor'});await post('incidents/'+incident.id+'/actions/report');proof.incident=incident.id
  await expect(center.locator('.operations-alerts')).toContainText(incident.title)
  await post('missions/'+trip.id+'/actions/complete',{loaded_quantity:'0',delivered_quantity:'0'},driverHeaders)
  await expect(center.locator('[data-operation="'+trip.id+'"]')).toContainText('Terminée');await expect(center.locator('.leaflet-interactive')).toHaveCount(0);await post('incidents/'+incident.id+'/actions/resolve',{resolution:'Recette TEST terminée'});proof.real_time_completion=true;save('completed')
  await center.getByRole('navigation',{name:'Vues de l’exploitation'}).getByRole('button',{name:'Carte',exact:true}).click();await center.getByRole('button',{name:'Agrandir la carte',exact:true}).click();await expect(page.locator('.operations-fullscreen')).toBeVisible();await page.getByRole('button',{name:'Fermer la carte',exact:true}).click();await expect(page.locator('.operations-fullscreen')).toHaveCount(0)
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();await page.screenshot({path:info.outputPath('operations-complete.png'),fullPage:true})
  proof.status='passed';save('verified')
 }finally{
  await driverContext?.close()
  const missions=await get('missions');for(const item of missions.results)if(['planned','active'].includes(item.status))await post('missions/'+item.id+'/actions/cancel')
  const incidents=await get('incidents');for(const item of incidents.results)if(item.status==='reported')await post('incidents/'+item.id+'/actions/resolve',{resolution:'Nettoyage recette TEST'})
  const orders=await get('orders');for(const item of orders.results)if(['draft','confirmed'].includes(item.status))await post('orders/'+item.id+'/actions/cancel')
  await post('maintenance/'+workshop.id+'/actions/complete');for(const employee of [driver,extraDriver])await post('employees/'+employee.id+'/remove');for(const item of [vehicle,extraVehicle,workshopVehicle]){const retired=await request.patch('/api/v2/vehicles/'+item.id,{headers,data:{status:'retired'}});expect(retired.status()).toBe(200)}for(const item of [customer,otherCustomer])await post('clients/'+item.id+'/archive');proof.cleaned=true;save('cleaned')
 }
})

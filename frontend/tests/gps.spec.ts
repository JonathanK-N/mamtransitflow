import {test,expect} from '@playwright/test'

test('GPS obligatoire : deux sessions Leaflet, navigation, offline, permissions et fin de mission',async({browser,request},info)=>{
 test.setTimeout(240000)
 const stamp=Date.now()+'-'+info.project.name,password='Gps-Recette-938!',email='gps-owner-'+stamp+'@example.test',driverEmail='gps-driver-'+stamp+'@example.test'
 const register=async(address:string,invitation='')=>{const r=await request.post('/api/v2/auth/register',{data:{name:address===email?'Direction GPS TEST':'Chauffeur GPS TEST',email:address,password,invitation,organization:{name:'TEST GPS '+stamp,country:'CA',currency:'USD',timezone:'America/Toronto',activities:['freight']}}});expect(r.status(),await r.text()).toBe(201);return r.json()}
 const owner=await register(email),org=owner.organizations[0].id,headers={Authorization:'Bearer '+owner.access,'X-Organization':org}
 const post=async(path:string,data:any)=>{const r=await request.post('/api/v2/'+path,{headers,data});expect(r.ok(),await r.text()).toBeTruthy();return r.json()}
 const invitation=await post('team',{email:driverEmail,role:'driver'}),driver=await register(driverEmail,new URL(invitation.link).searchParams.get('invitation')!)
 const employee=(await (await request.get('/api/v2/employees',{headers})).json()).results.find((e:any)=>e.user===driver.user.id);expect(employee).toBeTruthy();await request.patch('/api/v2/employees/'+employee.id,{headers,data:{active:true}})
 const vehicle=await post('vehicles',{plate:'GPS-'+stamp,name:'Camion GPS TEST',capacity:20,capacity_unit:'t'})
 const mission=await post('missions',{reference:'GPS-'+stamp,vehicle:vehicle.id,driver:employee.id,origin:'Sherbrooke',destination:'Montréal',departure:new Date(Date.now()+60000).toISOString(),arrival:new Date(Date.now()+7200000).toISOString()})
 const baseURL=process.env.TF_TEST_URL||'http://127.0.0.1:8000',a=await browser.newContext({baseURL,viewport:{width:1360,height:900}}),b=await browser.newContext({...info.project.use,baseURL} as any),admin=await a.newPage(),phone=await b.newPage()
 const errors:string[]=[],events:any[]=[];for(const page of [admin,phone])page.on('pageerror',e=>errors.push(e.message))
 admin.on('websocket',ws=>ws.on('framereceived',e=>{try{events.push(JSON.parse(String(e.payload)))}catch{}}))
 await a.route('https://tile.openstreetmap.org/**',r=>r.fulfill({contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/58BAwAI/AL+XJ/PAAAAAElFTkSuQmCC','base64')}))
 await b.route('https://tile.openstreetmap.org/**',r=>r.fulfill({contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/58BAwAI/AL+XJ/PAAAAAElFTkSuQmCC','base64')}))
 await b.addInitScript(()=>{const w=window as any;w.gpsTest={watch:null,error:null,cleared:0,permission:{state:'granted',onchange:null}};Object.defineProperty(navigator,'geolocation',{value:{watchPosition:(success:any,error:any)=>{w.gpsTest.watch=success;w.gpsTest.error=error;return 42},clearWatch:()=>{w.gpsTest.watch=null;w.gpsTest.cleared++},getCurrentPosition:(success:any)=>{success({timestamp:Date.now(),coords:{latitude:45.405,longitude:-71.9,accuracy:12,speed:12,heading:270}})}}});Object.defineProperty(navigator,'permissions',{value:{query:async()=>w.gpsTest.permission}})})
 async function login(page:any,address:string){await page.goto('/connexion');await page.getByLabel('Adresse courriel').fill(address);await page.getByLabel('Mot de passe',{exact:true}).fill(password);await page.getByRole('button',{name:'Se connecter',exact:true}).click();await expect(page.locator('.workspace')).toBeVisible()}
 async function navigate(page:any,name:string){if((page.viewportSize()?.width||1280)<=600)await page.getByRole('navigation',{name:'Navigation mobile'}).getByRole('button',{name:'Plus',exact:true}).click();else if((page.viewportSize()?.width||1280)<=900)await page.getByRole('button',{name:'Menu',exact:true}).click();await page.locator('.sidebar').getByRole('button',{name,exact:true}).click()}
 async function emit(lng:number){await phone.evaluate(lng=>{const test=(window as any).gpsTest;test.watch?.({timestamp:Date.now(),coords:{latitude:45.4042,longitude:lng,accuracy:12,speed:17.5,heading:270}})},lng)}
 const positions=async()=> (await (await request.get('/api/v2/missions/'+mission.id+'/positions',{headers})).json()).positions
 try{
  await login(admin,email);await navigate(admin,'Suivi en direct');await expect(admin.getByTestId('tracking-map')).toBeVisible()
  await login(phone,driverEmail);expect(await phone.evaluate(()=>(window as any).gpsTest.watch)).toBeNull()
  await post('missions/'+mission.id+'/actions/start',{})
  await expect(phone.getByTestId('driver-tracking')).toContainText('Suivi GPS actif')
  await expect.poll(()=>phone.evaluate(()=>!!(window as any).gpsTest.watch)).toBe(true)
  expect(await phone.getByRole('button',{name:/arrêter|désactiver|pause/i}).count()).toBe(0)
  expect(await phone.locator('.sidebar').getByRole('button',{name:'Suivi en direct',exact:true}).count()).toBe(0)
  await emit(-71.8929);await expect.poll(async()=> (await positions()).length).toBe(1)
  const card=admin.locator(`[data-mission="${mission.id}"]`);await expect(card).toContainText('-71.892900');await expect(card.locator('[data-state]')).toHaveAttribute('data-state','online')
  await expect(admin.locator('.leaflet-control-attribution')).toContainText('OpenStreetMap');expect(events.some(e=>e.type==='tracking')).toBeTruthy()
  await admin.evaluate(()=>{(window as any).gpsMapElement=document.querySelector('.leaflet-container');(window as any).gpsMarkerElement=document.querySelector('.leaflet-overlay-pane path')})
  await navigate(phone,'Terrain & notifications');expect(await phone.evaluate(()=>!!(window as any).gpsTest.watch)).toBe(true)
  await phone.waitForTimeout(10500);await emit(-71.8939);await expect(card).toContainText('-71.893900')
  expect(await admin.evaluate(()=>document.querySelector('.leaflet-container')===(window as any).gpsMapElement)).toBe(true)
  expect(await admin.evaluate(()=>document.querySelector('.leaflet-overlay-pane path')===(window as any).gpsMarkerElement)).toBe(true)
  await b.setOffline(true);await phone.waitForTimeout(10500);await emit(-71.8949);await phone.waitForTimeout(10500);await emit(-71.8959)
  await expect(phone.getByTestId('driver-tracking')).toContainText('Hors connexion — suivi GPS actif');await expect(phone.getByTestId('driver-tracking')).toContainText('2 positions en attente')
  await expect(card).toContainText('-71.893900');await b.setOffline(false);await expect.poll(async()=> (await positions()).length).toBe(4);await expect(card).toContainText('-71.895900');await expect(phone.getByTestId('driver-tracking')).not.toContainText('positions en attente')
  await phone.evaluate(()=>{const t=(window as any).gpsTest;t.permission.state='denied';t.permission.onchange?.();t.error?.({code:1})})
  await expect(phone.getByTestId('driver-tracking')).toContainText('Suivi GPS interrompu');await expect(card.locator('[data-state]')).toHaveAttribute('data-state','permission_required');expect((await positions()).length).toBe(4);await expect(card).toContainText('-71.895900')
  await phone.evaluate(()=>{const t=(window as any).gpsTest;t.permission.state='granted';t.permission.onchange?.();document.dispatchEvent(new Event('visibilitychange'))});await expect.poll(()=>phone.evaluate(()=>!!(window as any).gpsTest.watch)).toBe(true)
  await phone.waitForTimeout(10500);await emit(-71.8969);await expect(card.locator('[data-state]')).toHaveAttribute('data-state','online')
  expect(await phone.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
  if(info.project.name==='small'){await phone.setViewportSize({width:360,height:740});expect(await phone.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)}
  await phone.screenshot({path:info.outputPath('gps-driver-'+info.project.name+'.png'),fullPage:true});await admin.screenshot({path:info.outputPath('gps-fleet-'+info.project.name+'.png')})
  await navigate(phone,'Missions');await phone.getByRole('button',{name:'Terminer',exact:true}).first().click();const dialog=phone.getByRole('dialog',{name:'Terminer la mission'});await dialog.getByRole('button',{name:'Clôturer la mission',exact:true}).click();await expect(dialog).toHaveCount(0)
  await expect(phone.getByTestId('driver-tracking')).toHaveCount(0);await expect.poll(()=>phone.evaluate(()=>(window as any).gpsTest.watch)).toBeNull();const finished=(await positions()).length;await emit(-71.99);await phone.waitForTimeout(1000);expect((await positions()).length).toBe(finished)
  await expect(card).toHaveCount(0)
  await navigate(admin,'Missions');await admin.locator('tbody tr').filter({hasText:mission.reference}).click();await expect(admin.getByRole('heading',{name:'Parcours GPS réel'})).toBeVisible();await expect(admin.locator('.tracking-panel .leaflet-overlay-pane path')).toHaveCount(3)
  expect(errors).toEqual([])
 }finally{await a.close();await b.close()}
})

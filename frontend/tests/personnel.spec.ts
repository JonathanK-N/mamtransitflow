import {test,expect} from '@playwright/test'
test.use({actionTimeout:20000})
test('Personnel contacte puis retire un compte TEST connecté sans perdre son autre entreprise',async({browser,request},info)=>{
 const stamp=Date.now()+'-'+info.project.name,password='Recette-Personnel-938!',email='personnel-'+stamp+'@example.test'
 const register=async(address:string,name:string,extra:any={})=>{const r=await request.post('/api/v2/auth/register',{data:{name,email:address,password,organization:{name:'TEST Personnel '+name+' '+stamp,country:'GN',currency:'GNF',timezone:'Africa/Conakry',activities:['freight']},...extra}});expect(r.status(),await r.text()).toBe(201);return r.json()}
 const owner=await register(email,'Direction'),org=owner.organizations[0].id,headers={Authorization:'Bearer '+owner.access,'X-Organization':org}
 const invite=await request.post('/api/v2/team',{headers,data:{email:'peer-'+email,role:'driver'}});expect(invite.status()).toBe(201)
 const peer=await register('peer-'+email,'Chauffeur TEST retrait',{invitation:new URL((await invite.json()).link).searchParams.get('invitation')})
 const other=await register('other-'+email,'Autre entreprise'),otherOrg=other.organizations[0].id,otherHeaders={Authorization:'Bearer '+other.access,'X-Organization':otherOrg}
 const secondInvite=await request.post('/api/v2/team',{headers:otherHeaders,data:{email:'peer-'+email,role:'driver'}});expect(secondInvite.status()).toBe(201)
 expect((await request.post('/api/v2/invitation/accept',{headers:{Authorization:'Bearer '+peer.access},data:{token:new URL((await secondInvite.json()).link).searchParams.get('invitation')}})).status()).toBe(200)
 const employee=(await (await request.get('/api/v2/employees',{headers})).json()).results.find((x:any)=>x.user===peer.user.id);expect(employee).toBeTruthy()
 expect((await request.post('/api/v2/employees/'+employee.id+'/contact',{headers:otherHeaders,data:{}})).status()).toBe(404)
 const config={...info.project.use,baseURL:process.env.TF_TEST_URL||'http://127.0.0.1:8000'}
 const a=await browser.newContext(config as any),b=await browser.newContext(config as any),pa=await a.newPage(),pb=await b.newPage()
 const received:string[]=[];let closed=false
 pb.on('websocket',ws=>{let tenant='';ws.on('framesent',e=>{try{const value=JSON.parse(String(e.payload));if(value.type==='authenticate')tenant=value.organization}catch{}});ws.on('framereceived',e=>{if(tenant===org)received.push(String(e.payload))});ws.on('close',()=>{if(tenant===org)closed=true})})
 async function login(page:any,address:string){await page.goto('/connexion');await page.getByLabel('Adresse courriel').fill(address);await page.getByLabel('Mot de passe',{exact:true}).fill(password);await page.getByRole('button',{name:'Se connecter',exact:true}).click();await expect(page.locator('.workspace')).toBeVisible()}
 async function navigate(page:any,name:string){if((page.viewportSize()?.width||1280)<=600)await page.getByRole('navigation',{name:'Navigation mobile'}).getByRole('button',{name:'Plus',exact:true}).click();else if((page.viewportSize()?.width||1280)<=900)await page.getByRole('button',{name:'Menu',exact:true}).click();await page.locator('.sidebar').getByRole('button',{name,exact:true}).click()}
 try{
  await login(pa,email);await login(pb,'peer-'+email);await navigate(pb,'Messages');await expect(pb.getByRole('status').filter({hasText:'En direct'})).toBeVisible()
  await navigate(pa,'Personnel');await pa.getByRole('button',{name:'Actions pour Chauffeur TEST retrait',exact:true}).click()
  await pa.getByRole('button',{name:'Contacter',exact:true}).click();await expect(pa.getByLabel('Votre message')).toBeVisible()
  const id=new URL(pa.url()).hash.split('conversation=')[1]
  await pa.getByLabel('Votre message').fill('Contact Personnel '+stamp);await pa.getByRole('button',{name:'Envoyer',exact:true}).click()
  await expect(pb.locator('.conversation-item')).toContainText('Contact Personnel '+stamp)
  const reuse=await request.post('/api/v2/employees/'+employee.id+'/contact',{headers,data:{}});expect((await reuse.json()).id).toBe(id)
  await navigate(pa,'Personnel');await pa.getByRole('button',{name:'Actions pour Chauffeur TEST retrait',exact:true}).click();await pa.getByRole('button',{name:'Retirer de l’entreprise',exact:true}).click()
  const dialog=pa.getByRole('dialog',{name:/Retirer Chauffeur TEST retrait/});await expect(dialog).toBeVisible();await expect(dialog).toContainText('Son historique professionnel sera conservé');expect(await dialog.evaluate(el=>el.contains(document.activeElement))).toBeTruthy();await pa.keyboard.press('Shift+Tab');expect(await dialog.evaluate(el=>el.contains(document.activeElement))).toBeTruthy()
  expect(await dialog.evaluate(el=>{const r=el.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight})).toBeTruthy()
  await dialog.getByRole('button',{name:'Annuler',exact:true}).click();expect((await (await request.get('/api/v2/employees/'+employee.id,{headers})).json()).active).toBe(true)
  if(info.project.name==='small')await pa.setViewportSize({width:360,height:740})
  await pa.getByRole('button',{name:'Actions pour Chauffeur TEST retrait',exact:true}).click();await pa.getByRole('button',{name:'Retirer de l’entreprise',exact:true}).click()
  await pa.screenshot({path:'test-results/personnel-confirmation-'+info.project.name+'.png'})
  await pa.getByRole('dialog').getByRole('button',{name:'Retirer de l’entreprise',exact:true}).click();await expect(pa.getByRole('dialog')).toHaveCount(0)
  await expect.poll(async()=> (await (await request.get('/api/v2/employees/'+employee.id,{headers})).json()).active).toBe(false)
  await expect.poll(()=>received.some(x=>JSON.parse(x).type==='access_revoked')).toBe(true);await expect.poll(()=>closed).toBe(true)
  await expect.poll(()=>pb.evaluate(()=>sessionStorage.getItem('transitflow.organization'))).toBe(otherOrg)
  await expect(pb.locator('.workspace')).toBeVisible();await expect(pb.locator('.message-stream')).toHaveCount(0)
  const removedHeaders={Authorization:'Bearer '+peer.access,'X-Organization':org}
  for(const path of ['missions','employees','notifications','messaging/conversations/'+id+'/messages'])expect((await request.get('/api/v2/'+path,{headers:removedHeaders})).status()).toBe(403)
  expect((await request.post('/api/v2/messaging/conversations/'+id+'/messages',{headers:removedHeaders,data:{body:'Interdit après retrait',client_id:crypto.randomUUID()}})).status()).toBe(403)
  expect((await request.get('/api/v2/missions',{headers:{Authorization:'Bearer '+peer.access,'X-Organization':otherOrg}})).status()).toBe(200)
  await navigate(pa,'Messages');await pa.locator('.conversation-item').filter({hasText:'ancien collaborateur'}).click();await expect(pa.locator('.message-stream')).toContainText('Contact Personnel '+stamp)
  for(const page of [pa,pb])expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy()
  await pa.screenshot({path:'test-results/personnel-history-'+info.project.name+'.png'})
  const remaining=(await (await request.get('/api/v2/employees',{headers:otherHeaders})).json()).results.find((x:any)=>x.user===peer.user.id)
  expect((await request.post('/api/v2/employees/'+remaining.id+'/remove',{headers:otherHeaders,data:{}})).status()).toBe(200)
  await expect(pb.getByRole('alert')).toContainText('Votre accès à cette entreprise a été retiré.')
  await pb.reload();await expect(pb.getByRole('alert')).toContainText('Vous ne disposez plus d’un accès actif à une entreprise.')
  expect((await (await request.get('/api/v2/auth/me',{headers:{Authorization:'Bearer '+peer.access}})).json()).user.id).toBe(peer.user.id)
 }finally{await a.close();await b.close()}
})

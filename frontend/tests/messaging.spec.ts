import {test,expect} from '@playwright/test'
test.use({actionTimeout:20000})

test('Deux collaborateurs échangent en direct, lecture, reconnexion et isolation tenant',async({browser,request},info)=>{
 const stamp=Date.now()+'-'+info.project.name,password='Recette-Messagerie-938!',email='chat-'+stamp+'@example.test'
 const register=async(email:string,name:string,extra:any={})=>{const r=await request.post('/api/v2/auth/register',{data:{name,email,password,organization:{name:'TEST Messagerie '+stamp,country:'GN',currency:'GNF',timezone:'Africa/Conakry',activities:['freight']},...extra}});expect(r.status(),await r.text()).toBe(201);return r.json()}
 const owner=await register(email,'Direction test'),org=owner.organizations[0].id,headers={Authorization:'Bearer '+owner.access,'X-Organization':org}
 const invite=await request.post('/api/v2/team',{headers,data:{email:'peer-'+email,role:'driver'}});expect(invite.status()).toBe(201)
 const invited=await invite.json();const peer=await register('peer-'+email,'Chauffeur test',{invitation:new URL(invited.link).searchParams.get('invitation')})
 const outsider=await register('other-'+email,'Organisation étrangère')
 const config=info.project.use
 const a=await browser.newContext({...config,baseURL:process.env.TF_TEST_URL||'http://127.0.0.1:8000'} as any)
 const b=await browser.newContext({...config,baseURL:process.env.TF_TEST_URL||'http://127.0.0.1:8000'} as any)
 const pa=await a.newPage(),pb=await b.newPage()
 async function login(page:any,address:string){await page.goto('/connexion');await page.getByLabel('Adresse courriel').fill(address);await page.getByLabel('Mot de passe',{exact:true}).fill(password);await page.getByRole('button',{name:'Se connecter',exact:true}).click();await expect(page.locator('.workspace')).toBeVisible();if((page.viewportSize()?.width||1280)<=600)await page.getByRole('navigation',{name:'Navigation mobile'}).getByRole('button',{name:'Messages',exact:true}).click();else{if((page.viewportSize()?.width||1280)<=900)await page.getByRole('button',{name:'Menu',exact:true}).click();await page.locator('.sidebar').getByRole('button',{name:'Messages',exact:true}).click()}await expect(page.getByRole('status').filter({hasText:'En direct'})).toBeVisible()}
 try{
  await login(pa,email);await login(pb,'peer-'+email)
  await pa.getByRole('button',{name:'Nouvelle discussion'}).click();await pa.getByRole('radio',{name:/Chauffeur test/}).check();await pa.getByRole('button',{name:'Créer la conversation'}).click()
  await pa.getByLabel('Votre message').fill('Bonjour exploitation '+stamp);await pa.getByRole('button',{name:'Envoyer',exact:true}).click()
  await expect(pb.locator('.conversation-item')).toContainText('Bonjour exploitation '+stamp)
  await expect(pb.locator('.conversation-item .unread-badge')).toHaveText('1')
  await pb.locator('.conversation-item').click();await expect(pb.locator('.message-stream')).toContainText('Bonjour exploitation '+stamp)
  await expect(pa.locator('.message-stream')).toContainText('Lu par Chauffeur test')
  await pb.getByLabel('Votre message').fill('Bien reçu '+stamp);await pb.getByRole('button',{name:'Envoyer',exact:true}).click();await expect(pa.locator('.message-stream')).toContainText('Bien reçu '+stamp)
  const identity=new URL(pa.url()).hash.split('conversation=')[1]
  const foreignHeaders={Authorization:'Bearer '+outsider.access,'X-Organization':outsider.organizations[0].id}
  expect((await request.get('/api/v2/messaging/conversations/'+identity+'/messages',{headers:foreignHeaders})).status()).toBe(404)
  const people=await request.get('/api/v2/messaging/collaborators',{headers:foreignHeaders});expect((await people.json()).results).toEqual([])
  const foreignMembers=await request.get('/api/v2/team',{headers:foreignHeaders});const foreignMember=(await foreignMembers.json()).members[0]
  const group=await request.post('/api/v2/messaging/conversations',{headers,data:{kind:'group',title:'Isolation recette',participants:[(await (await request.get('/api/v2/messaging/collaborators',{headers})).json()).results[0].id]}});expect(group.status()).toBe(201)
  expect((await request.patch('/api/v2/messaging/conversations/'+(await group.json()).id,{headers,data:{add:foreignMember.id}})).status()).toBe(404)
  const attachment=await request.post('/api/v2/messaging/conversations/'+identity+'/messages',{headers,multipart:{body:'Justificatif recette',client_id:crypto.randomUUID(),file:{name:'proof.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF-1.4\nproof')}}});expect(attachment.status()).toBe(201)
  const attachmentId=(await attachment.json()).attachments[0].id
  expect((await request.get('/api/v2/messaging/attachments/'+attachmentId,{headers:foreignHeaders})).status()).toBe(404)
  await b.setOffline(true);await pa.getByLabel('Votre message').fill('Pendant la coupure '+stamp);await pa.getByRole('button',{name:'Envoyer',exact:true}).click();await b.setOffline(false)
  await expect(pb.locator('.message-stream')).toContainText('Pendant la coupure '+stamp)
  await pb.reload();await expect(pb.locator('.message-stream')).toContainText('Bien reçu '+stamp)
  await expect(pb.locator('.conversation-item .unread-badge')).toHaveCount(0)
  for(const p of [pa,pb])expect(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy()
  await pb.screenshot({path:'test-results/messaging-'+info.project.name+'.png',fullPage:false})
 }finally{await a.close();await b.close()}
})

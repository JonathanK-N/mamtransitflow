import {test,expect} from '@playwright/test'
test('Portail client : création, recherche, doublons, renvoi, annulation et acceptation isolée',async({page,browser,request},info)=>{
 const stamp=Date.now()+'-'+info.project.name,password='Portail-Recette-839!',email='portal-'+stamp+'@example.test',customerEmail='customer-'+email,company='TEST Portail '+stamp,customer='TEST Client '+stamp
 const registered=await request.post('/api/v2/auth/register',{data:{name:'Direction TEST Portail',email,password,organization:{name:company,country:'GN',currency:'GNF',timezone:'Africa/Conakry',activities:['freight']}}});expect(registered.status(),await registered.text()).toBe(201)
 const owner=await registered.json(),headers={Authorization:'Bearer '+owner.access,'X-Organization':owner.organizations[0].id}
 await page.goto('/connexion');await page.getByLabel('Adresse courriel').fill(email);await page.getByLabel('Mot de passe',{exact:true}).fill(password);await page.getByRole('button',{name:'Se connecter',exact:true}).click();await expect(page.locator('.workspace')).toBeVisible()
 if((page.viewportSize()?.width||1280)<=600)await page.getByRole('navigation',{name:'Navigation mobile'}).getByRole('button',{name:'Plus',exact:true}).click();else if((page.viewportSize()?.width||1280)<=900)await page.getByRole('button',{name:'Menu',exact:true}).click();await page.locator('.sidebar').getByRole('button',{name:'Portail client',exact:true}).click();await expect(page).toHaveURL(/#portal-admin$/);await expect(page.getByRole('heading',{name:'Inviter un client dans son espace privé'})).toBeVisible()
 await page.getByRole('button',{name:'Nouveau client',exact:true}).click();await page.getByRole('button',{name:'Créer et inviter le client',exact:true}).click()
 await expect(page.getByText('Le nom du client est requis.',{exact:true})).toBeVisible();await expect(page.getByText('Le courriel est requis.',{exact:true})).toBeVisible();expect(await page.locator('select[required]').count()).toBe(0)
 await page.getByLabel('Nom / raison sociale du client').fill(customer);await page.getByLabel('Nom du contact (facultatif)').fill('Client TEST');await page.getByLabel('Courriel du client').fill(customerEmail);await page.getByLabel('Téléphone (facultatif)').fill('+224 123456')
 await page.getByRole('button',{name:'Créer et inviter le client',exact:true}).click();await expect(page.locator('.success-box')).toContainText(company)
 const pending=page.locator('.invite-row').filter({hasText:customerEmail});await expect(pending).toContainText('En attente')
 const initialLink=await page.locator('.invitation-link span').innerText()
 await pending.getByRole('button',{name:'Renvoyer l’invitation',exact:true}).click();await expect.poll(()=>page.locator('.invitation-link span').innerText()).not.toBe(initialLink)
 await page.locator('.invite-row').filter({hasText:customerEmail}).filter({hasText:'En attente'}).getByRole('button',{name:'Annuler l’invitation',exact:true}).click();await expect(page.locator('.success-box')).toContainText('Invitation annulée')
 const cancel=(await (await request.get('/api/v2/portal-access/invitations',{headers})).json()).results;expect(cancel.filter((x:any)=>x.status==='pending')).toHaveLength(0)
 await page.getByRole('button',{name:'Créer et inviter le client',exact:true}).click();await expect(page.getByRole('alert').filter({hasText:'Un client utilisant cette adresse existe déjà'})).toBeVisible();await page.getByRole('button',{name:'Utiliser '+customer,exact:true}).click()
 await expect(page.getByLabel('Courriel du client')).toHaveValue(customerEmail);await page.getByLabel('Rechercher un client').fill('123456');await expect(page.locator('.customer-result')).toHaveCount(1);await expect(page.locator('.customer-result')).toContainText(customer)
 await page.getByRole('button',{name:'Créer l’invitation client',exact:true}).click();await expect(page.locator('.success-box')).toContainText(company);const link=await page.locator('.invitation-link span').innerText()
 const partners=(await (await request.get('/api/v2/partners',{headers})).json()).results;expect(partners.filter((x:any)=>x.email===customerEmail)).toHaveLength(1);const partner=partners.find((x:any)=>x.email===customerEmail)
 const other=await request.post('/api/v2/partners',{headers,data:{name:'TEST Autre client '+stamp,kind:'customer',email:'other-'+customerEmail}});expect(other.status()).toBe(201);const otherPartner=await other.json()
 for(const [id,reference] of [[partner.id,'TEST-OWN-'+stamp],[otherPartner.id,'TEST-PRIVATE-'+stamp]]){
  const r=await request.post('/api/v2/orders',{headers,data:{customer:id,reference,origin:'Conakry',destination:'Kindia',planned_date:'2026-10-03'}});expect(r.status(),await r.text()).toBe(201);expect((await request.post('/api/v2/orders/'+(await r.json()).id+'/actions/confirm',{headers,data:{}})).status()).toBe(200)
 }
 if(info.project.name==='small')await page.setViewportSize({width:360,height:740})
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();await page.screenshot({path:'test-results/portal-admin-'+info.project.name+'.png',fullPage:true})
 const context=await browser.newContext({...info.project.use,baseURL:process.env.TF_TEST_URL||'http://127.0.0.1:8000'} as any);const client=await context.newPage()
 try{
  await client.goto('/app'+new URL(link).search);await client.getByLabel('Votre nom complet').fill('Client TEST');await client.getByLabel('Adresse courriel').fill(customerEmail);await client.getByLabel('Mot de passe',{exact:true}).fill(password);await client.getByRole('button',{name:'Rejoindre mon entreprise',exact:true}).click();await expect(client.locator('.client-portal')).toBeVisible()
  await expect(client.locator('.client-portal')).toContainText('TEST-OWN-'+stamp);await expect(client.locator('.client-portal')).not.toContainText('TEST-PRIVATE-'+stamp);await expect(client.getByRole('button',{name:'Personnel',exact:true})).toHaveCount(0)
  const login=await request.post('/api/v2/auth/login',{data:{email:customerEmail,password}});expect(login.status()).toBe(200);const account=await login.json(),clientHeaders={Authorization:'Bearer '+account.access,'X-Organization':owner.organizations[0].id}
  expect(account.organizations[0].role).toBe('client');for(const path of ['employees','team','journal','messaging/conversations','portal-access/customers'])expect((await request.get('/api/v2/'+path,{headers:clientHeaders})).status()).toBe(403)
  expect((await request.get('/api/v2/portal/orders/'+otherPartner.id,{headers:clientHeaders})).status()).toBe(404)
  await page.reload();await expect(page.getByRole('heading',{name:'Clients ayant accès au portail'})).toBeVisible();await expect(page.locator('.invite-row').filter({hasText:customerEmail}).filter({hasText:'Actif'})).toHaveCount(1)
  expect(await client.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();await client.screenshot({path:'test-results/portal-client-'+info.project.name+'.png',fullPage:true})
 }finally{await context.close()}
})

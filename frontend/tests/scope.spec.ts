import {test,expect} from '@playwright/test'

test.use({serviceWorkers:'block',actionTimeout:20000})
test('Entreprise : une réponse tardive ne repopule pas le module du nouveau tenant',async({page,request},info)=>{
 test.setTimeout(180000)
 const stamp=Date.now()+'-'+info.project.name,password='Scope-Test-938!',email='scope-'+stamp+'@example.test'
 const register=async(email:string,label:string)=>{const response=await request.post('/api/v2/auth/register',{data:{name:'Direction TEST '+label,email,password,organization:{name:'TEST Scope '+label+' '+stamp,country:'GN',currency:'USD',timezone:'Africa/Conakry',activities:['freight']}}});expect(response.status()).toBe(201);return response.json()}
 const a=await register(email,'A'),b=await register('other-'+email,'B')
 const headers=(account:any)=>({Authorization:'Bearer '+account.access,'X-Organization':account.organizations[0].id})
 const post=async(account:any,path:string,data:any)=>{const response=await request.post('/api/v2/'+path,{headers:headers(account),data});expect(response.ok(),(await response.text()).slice(0,300)).toBe(true);return response.json()}
 const invite=await post(b,'team',{email,role:'admin'});await post(a,'invitation/accept',{token:new URL(invite.link).searchParams.get('invitation')})
 for(const [account,label] of [[a,'A'],[b,'B']] as any){const customer=await post(account,'partners',{name:'TEST-PRIVATE-'+label+'-'+stamp});await post(account,'invoices',{customer:customer.id,date:'2026-10-05',due_date:'2026-10-06',lines:[{description:'Prestation '+label,quantity:'1',price:'1.01',tax_rate:'0'}]})}
 await page.goto('/connexion');await page.getByLabel('Adresse courriel').fill(email);await page.getByLabel('Mot de passe',{exact:true}).fill(password);await page.getByRole('button',{name:'Se connecter',exact:true}).click();await expect(page.locator('.operations-center')).toBeVisible()
 let releaseA!:()=>void,releaseB!:()=>void,aStarted=false,bStarted=false
 const gateA=new Promise<void>(resolve=>{releaseA=resolve}),gateB=new Promise<void>(resolve=>{releaseB=resolve})
 await page.route('**/api/v2/invoices?**',async route=>{const response=await route.fetch();if(route.request().headers()['x-organization']===a.organizations[0].id){aStarted=true;await gateA}else{bStarted=true;await gateB}await route.fulfill({response})})
 try{
  await page.evaluate(()=>{location.hash='invoices'});await expect.poll(()=>aStarted).toBe(true)
  if((page.viewportSize()?.width||1280)<=900)await page.getByRole('button',{name:'Menu',exact:true}).click()
  await page.getByLabel('Entreprise active',{exact:true}).selectOption(b.organizations[0].id);await expect(page.locator('.operations-center')).toBeVisible();await expect(page.getByLabel('Entreprise active',{exact:true})).toHaveValue(b.organizations[0].id)
  await page.evaluate(()=>{location.hash='invoices'});await expect.poll(()=>bStarted).toBe(true)
  const oldResponse=page.waitForEvent('requestfinished',{predicate:req=>req.url().includes('/api/v2/invoices?')&&req.headers()['x-organization']===a.organizations[0].id});releaseA();await oldResponse;await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))))
  await expect(page.locator('.workspace-content')).not.toContainText('TEST-PRIVATE-A-'+stamp);await expect(page.locator('.loading-panel')).toBeVisible()
  releaseB();await expect(page.locator('.workspace-content')).toContainText('TEST-PRIVATE-B-'+stamp);await expect(page.locator('.workspace-content')).not.toContainText('TEST-PRIVATE-A-'+stamp)
  await page.screenshot({path:info.outputPath('tenant-delayed-response.png'),fullPage:true})
 }finally{releaseA();releaseB();await page.unroute('**/api/v2/invoices?**')}
})

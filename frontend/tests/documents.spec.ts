import {test,expect} from '@playwright/test'

test.use({serviceWorkers:'block',actionTimeout:20000})

test('Documents : aperçu professionnel, 200 lignes, impression, clavier et portail',async({page,request,browser},info)=>{
 test.setTimeout(240000)
 const stamp=Date.now()+'-'+info.project.name,password='Documents-Test-938!',email='documents-'+stamp+'@example.test'
 const registered=await request.post('/api/v2/auth/register',{data:{name:'Direction TEST Documents',email,password,organization:{name:'TEST Documents '+stamp,country:'GN',currency:'USD',timezone:'America/Toronto',activities:['freight'],address:'123 Avenue du Transport',registration:'REG-TEST',tax_number:'TAX-COMPANY'}}});expect(registered.status()).toBe(201)
 const owner=await registered.json(),headers={Authorization:'Bearer '+owner.access,'X-Organization':owner.organizations[0].id}
 const post=async(path:string,data:any)=>{const response=await request.post('/api/v2/'+path,{headers,data});expect(response.ok(),(await response.text()).slice(0,300)).toBe(true);return response.json()}
 const customer=await post('partners',{name:'Client TEST Québec',address:'45 Rue de la Livraison',email:'documents-client-'+stamp+'@example.test',tax_number:'TAX-CLIENT',notes:'PRIVATE-CUSTOMER-NOTES'})
 const invoice=await post('invoices',{customer:customer.id,kind:'invoice',date:'2026-10-05',due_date:'2026-10-06',lines:Array.from({length:200},(_,index)=>({description:'Prestation TEST '+String(index+1).padStart(3,'0')+' - Café à Montréal',quantity:'1',price:'1.01',tax_rate:'18'})),notes:'Conditions de paiement TEST'})
 const issued=await post('invoices/'+invoice.id+'/actions/issue',{})
 const quote=await post('invoices',{customer:customer.id,kind:'quote',date:'2026-10-05',due_date:'2026-10-06',lines:[{description:'Devis TEST',quantity:'1',price:'5.01',tax_rate:'18'}]})
 const credit=await post('invoices',{customer:customer.id,kind:'credit',original:invoice.id,date:'2026-10-05',due_date:'2026-10-06',lines:[{description:'Avoir TEST',quantity:'1',price:'5.01',tax_rate:'18'}]})
 const login=async(p:any,email:string)=>{await p.goto('/connexion');await p.getByLabel('Adresse courriel').fill(email);await p.getByLabel('Mot de passe',{exact:true}).fill(password);await p.getByRole('button',{name:'Se connecter',exact:true}).click();await expect(p.locator('.workspace,.client-portal')).toBeVisible()}
 let releaseCatalog!:()=>void,catalogRequested=false;const catalogGate=new Promise<void>(resolve=>{releaseCatalog=resolve})
 await page.route('**/api/v2/catalog',async route=>{const response=await route.fetch();catalogRequested=true;await catalogGate;await route.fulfill({response})},{times:1})
 await login(page,email);await expect.poll(()=>catalogRequested).toBe(true);await page.evaluate(()=>{location.hash='invoices'});releaseCatalog();await page.getByRole('button',{name:issued.number,exact:true}).click();await page.getByRole('button',{name:'Aperçu du document',exact:true}).click()
 let preview=page.locator('.financial-preview'),paper=preview.locator('.financial-document')
 await expect(paper).toContainText('REG-TEST');await expect(paper).toContainText('TAX-CLIENT');await expect(paper).toContainText('Café à Montréal');await expect(paper.locator('tbody tr')).toHaveCount(200);await expect(paper).toContainText('238,00');await expect(paper).not.toContainText('PRIVATE-CUSTOMER-NOTES')
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
 await preview.screenshot({path:info.outputPath('financial-screen.png')})
 await page.emulateMedia({media:'print'});await expect(paper).toBeVisible();await expect(preview.locator('.financial-controls')).toBeHidden();expect(await paper.locator('thead').evaluate(el=>getComputedStyle(el).display)).toBe('table-header-group')
 await paper.screenshot({path:info.outputPath('financial-print.png')});if(process.env.TF_TEST_PRINT_PDF==='1')await page.pdf({path:info.outputPath('financial-200-lines.pdf'),preferCSSPageSize:true,printBackground:true});await page.emulateMedia({media:'screen'})
 await page.keyboard.press('Escape');await expect(preview).toHaveCount(0);await expect(page.getByRole('button',{name:'Aperçu du document',exact:true})).toBeFocused();await page.getByRole('dialog').getByLabel('Fermer',{exact:true}).click()
 await page.goto('/app#invoices?record='+quote.id);await page.getByRole('button',{name:'Aperçu du document',exact:true}).click();await expect(page.locator('.financial-document')).toContainText('BROUILLON');await expect(page.locator('.financial-document')).toContainText('Devis TEST');await page.keyboard.press('Escape');await page.getByRole('dialog').getByLabel('Fermer',{exact:true}).click()
 await page.goto('/app#invoices?record='+credit.id);await page.getByRole('button',{name:'Aperçu du document',exact:true}).click();await expect(page.locator('.financial-document')).toContainText('Avoir TEST');await expect(page.locator('.financial-document')).toContainText(issued.number);await page.keyboard.press('Escape');await page.getByRole('dialog').getByLabel('Fermer',{exact:true}).click()
 const invite=await post('portal-access',{mode:'existing',partner:customer.id,email:customer.email})
 const recipient=await request.post('/api/v2/auth/register',{data:{name:'Client TEST Documents',email:customer.email,password,invitation:new URL(invite.link).searchParams.get('invitation')}});expect(recipient.status()).toBe(201)
 const clientContext=await browser.newContext({...info.project.use,baseURL:process.env.TF_TEST_URL||'http://127.0.0.1:8000'} as any)
 try{const clientPage=await clientContext.newPage();await login(clientPage,customer.email);await clientPage.getByRole('button',{name:'Mes factures',exact:true}).click();await clientPage.getByRole('button',{name:'Facture '+issued.number,exact:true}).click();preview=clientPage.locator('.financial-preview');paper=preview.locator('.financial-document');await expect(paper).toContainText('123 Avenue du Transport');await expect(paper).toContainText('45 Rue de la Livraison');await expect(paper.locator('tbody tr')).toHaveCount(200);await expect(paper).not.toContainText('PRIVATE-CUSTOMER-NOTES');expect(await clientPage.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await clientPage.keyboard.press('Escape');await expect(preview).toHaveCount(0)}finally{await clientContext.close()}

})

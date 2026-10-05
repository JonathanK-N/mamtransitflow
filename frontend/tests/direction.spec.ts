import {test,expect} from '@playwright/test'

test('Direction : période, comparaison, créances et accès mobile au pilotage',async({page,request},info)=>{
 const stamp=Date.now()+'-'+info.project.name,email='direction-'+stamp+'@example.test',password='Direction-Test-938!'
 const registered=await request.post('/api/v2/auth/register',{data:{name:'Direction TEST',email,password,organization:{name:'TEST Direction '+stamp,country:'GN',currency:'USD',timezone:'Africa/Conakry',activities:['freight']}}});expect(registered.status()).toBe(201)
 const owner=await registered.json(),headers={Authorization:'Bearer '+owner.access,'X-Organization':owner.organizations[0].id}
 const post=async(path:string,data:any)=>{const r=await request.post('/api/v2/'+path,{headers,data});expect(r.ok(),await r.text()).toBeTruthy();return r.json()}
 const customer=await post('partners',{name:'TEST Client Direction'})
 const invoice=await post('invoices',{customer:customer.id,kind:'invoice',date:'2026-10-05',due_date:'2026-10-06',lines:[{description:'Transport TEST',quantity:'1',price:'100.01',tax_rate:'0'}]})
 await post('invoices/'+invoice.id+'/actions/issue',{})
 await post('payments',{invoice:invoice.id,date:'2026-10-05',reference:'TEST-PAY-'+stamp,amount:'25.00',method:'bank'})
 await page.goto('/connexion');await page.getByLabel('Adresse courriel').fill(email);await page.getByLabel('Mot de passe',{exact:true}).fill(password);await page.getByRole('button',{name:'Se connecter',exact:true}).click();await expect(page.locator('.workspace')).toBeVisible()
 await page.goto('/app#dashboard')
 const direction=page.getByRole('region',{name:'Tableau de bord Direction'})
 await expect(direction).toBeVisible()
 await direction.getByLabel('Début',{exact:true}).fill('2026-10-05');await direction.getByLabel('Fin',{exact:true}).fill('2026-10-05');await direction.getByRole('button',{name:'Appliquer la période',exact:true}).click()
 await expect(direction).toContainText('2026-10-04 → 2026-10-04')
 await expect(direction.locator('.stat-card').filter({hasText:'Chiffre d’affaires HT'})).toContainText('100,01')
 await expect(direction.locator('.stat-card').filter({hasText:'Encaissements clients'})).toContainText('25,00')
 await expect(direction.locator('.direction-balances')).toContainText('75,01')
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
 await page.screenshot({path:info.outputPath('direction-complete.png'),fullPage:true})
})

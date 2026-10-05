import {test,expect} from '@playwright/test'

test('Devis client : consultation sans compte, confirmation et aucune fuite du jeton dans les URL',async({page})=>{
 const token='test-quote-personal-token-with-sufficient-length'
 let responses=0
 await page.route('**/api/v2/public/quotes/*',async route=>{
  const request=route.request();expect(request.url()).not.toContain(token);expect(request.postDataJSON().token).toBe(token)
  expect(request.headers().authorization).toBeUndefined()
  if(request.url().endsWith('/respond')){responses++;expect(request.postDataJSON().decision).toBe('accept');await route.fulfill({json:{state:'accepted'}})}
  else await route.fulfill({json:{company:'TEST Transport',customer:'TEST Client',number:'DEV-TEST',date:'2026-10-05',valid_until:'2026-10-12',origin:'A',destination:'B',lines:[{description:'Transport TEST',quantity:'2',price:'100.00',tax_rate:'18'}],subtotal:'200.00',tax:'36.00',total:'236.00',currency:'USD',state:'sent'}})
 })
 await page.goto('/devis#'+token)
 await expect(page.getByRole('heading',{name:'TEST Transport',exact:true})).toBeVisible()
 await expect(page).toHaveURL(/\/devis$/)
 await expect(page.getByText('236.00 USD',{exact:true})).toBeVisible()
 await page.getByRole('button',{name:'Accepter le devis',exact:true}).click()
 expect(responses).toBe(0)
 await page.getByRole('button',{name:'Annuler',exact:true}).click()
 expect(responses).toBe(0)
 await page.getByRole('button',{name:'Accepter le devis',exact:true}).click()
 await page.getByRole('button',{name:'Confirmer l’acceptation',exact:true}).click()
 await expect(page.getByRole('status')).toContainText('Ce devis a été accepté.')
 expect(responses).toBe(1)
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
})

test('Devis client : lien expiré sans accès aux données',async({page})=>{
 await page.route('**/api/v2/public/quotes/preview',route=>route.fulfill({status:410,json:{detail:'Ce lien de devis a expiré ou a été retiré.'}}))
 await page.goto('/devis#test-expired-quote-token-with-sufficient-length')
 await expect(page.getByRole('alert')).toContainText('Ce lien de devis a expiré')
 await expect(page.getByRole('button',{name:'Accepter le devis'})).toHaveCount(0)
})

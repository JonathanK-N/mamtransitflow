import {test,expect} from '@playwright/test'
import {createServer} from 'node:http'
import {readFile} from 'node:fs/promises'
import {resolve,extname} from 'node:path'

test('Une mise à jour conserve la saisie jusqu’au choix explicite de recharger',async({page})=>{
 let version=1
 const root=resolve('dist')
 const server=createServer(async(req,res)=>{
  const url=new URL(req.url||'/', 'http://localhost')
  const pathname=['/','/app','/connexion'].includes(url.pathname)?'/index.html':url.pathname
  const file=resolve(root,'.'+pathname)
  if(!file.startsWith(root+'/')&&!file.startsWith(root+'\\')){res.writeHead(404).end();return}
  try{
   let content=await readFile(file)
   if(pathname==='/sw.js')content=Buffer.concat([content,Buffer.from(`\n// version ${version}\n`)])
   res.setHeader('Content-Type',({'.js':'application/javascript','.html':'text/html','.css':'text/css','.png':'image/png','.webmanifest':'application/manifest+json'} as any)[extname(file)]||'application/octet-stream')
   res.setHeader('Cache-Control','no-store');res.end(content)
  }catch{res.writeHead(404).end()}
 })
 await new Promise<void>(resolve=>server.listen(0,'127.0.0.1',resolve))
 try{
  const address=server.address() as any
  await page.goto(`http://127.0.0.1:${address.port}/connexion`)
  await page.evaluate(()=>navigator.serviceWorker.ready)
  await expect.poll(()=>page.evaluate(()=>!!navigator.serviceWorker.controller)).toBeTruthy()
  await page.getByLabel('Adresse courriel').fill('saisie@example.test')
  version=2
  await page.evaluate(async()=>{const registration=await navigator.serviceWorker.ready;await registration.update()})
  await expect(page.getByRole('button',{name:'Mettre à jour',exact:true})).toBeVisible()
  await expect(page.getByLabel('Adresse courriel')).toHaveValue('saisie@example.test')
  await page.getByRole('button',{name:'Mettre à jour',exact:true}).click()
  await expect(page.getByLabel('Adresse courriel')).toHaveValue('')
 }finally{await new Promise<void>((resolve,reject)=>server.close(error=>error?reject(error):resolve()))}
})

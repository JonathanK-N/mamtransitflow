// Auteur : Jonathan Kakesa (JonathanK-N).
let access = ''
let csrf = ''
let renewing: Promise<boolean> | null = null
export let organization = sessionStorage.getItem('transitflow.organization') || ''
export function setOrganization(id:string) { organization=id;sessionStorage.setItem('transitflow.organization',id) }
export function setAccess(token:string) { access=token }
function message(value:any):string {
  if(typeof value==='string')return value
  if(Array.isArray(value))return value.map(message).join(' ')
  if(value && typeof value==='object')return Object.entries(value).map(([k,v])=>`${k==='detail'?'':k+' : '}${message(v)}`).join(' ')
  return 'Une erreur est survenue.'
}
export async function refresh():Promise<boolean> {
  if(renewing)return renewing
  renewing=(async()=>{
    try {
      const c=await fetch('/api/v2/auth/csrf',{credentials:'same-origin'});csrf=(await c.json()).csrf
      const r=await fetch('/api/v2/auth/refresh',{method:'POST',credentials:'same-origin',headers:{'X-CSRFToken':csrf}})
      if(!r.ok)return false
      access=(await r.json()).access;return true
    }catch{return false}
  })()
  try{return await renewing}finally{renewing=null}
}
export async function api(path:string,method='GET',body?:any,retry=true):Promise<any> {
  const headers:Record<string,string>={}
  if(access)headers.Authorization='Bearer '+access
  if(organization)headers['X-Organization']=organization
  if(csrf)headers['X-CSRFToken']=csrf
  const multipart=body instanceof FormData
  if(body!==undefined&&!multipart)headers['Content-Type']='application/json'
  const response=await fetch('/api/v2/'+path,{method,headers,credentials:'same-origin',body:body===undefined?undefined:multipart?body:JSON.stringify(body)})
  if(response.status===401&&retry&&!path.startsWith('auth/')){
    if(await refresh())return api(path,method,body,false)
    window.dispatchEvent(new Event('session-expired'))
  }
  if(response.status===204)return null
  const data=await response.json().catch(()=>({detail:'Réponse serveur illisible.'}))
  if(!response.ok)throw new Error(message(data))
  if(data.access)access=data.access
  if(data.csrf)csrf=data.csrf
  return data
}
export async function download(path:string,name:string) {
  const response=await fetch('/api/v2/'+path,{headers:{Authorization:'Bearer '+access,'X-Organization':organization}})
  if(!response.ok)throw new Error('Téléchargement impossible. Vérifiez vos droits et votre session.')
  const url=URL.createObjectURL(await response.blob());const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),2000)
}
export function money(value:any,currency='GNF') { return new Intl.NumberFormat('fr-FR',{style:'currency',currency,maximumFractionDigits:['GNF','XAF','XOF'].includes(currency)?0:2}).format(Number(value||0)) }

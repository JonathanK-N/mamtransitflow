import {clientsClaim} from 'workbox-core'
import {cleanupOutdatedCaches, precacheAndRoute, createHandlerBoundToURL} from 'workbox-precaching'
import {NavigationRoute, registerRoute} from 'workbox-routing'

precacheAndRoute(self.__WB_MANIFEST)
cleanupOutdatedCaches()
registerRoute(new NavigationRoute(createHandlerBoundToURL('/index.html'), {
  allowlist: [/^\/$/, /^\/app(?:\/[^?]*)?(?:\?.*)?$/, /^\/(?:connexion|commencer)(?:\?.*)?$/],
  denylist: [/^\/api\//, /^\/django-admin/],
}))
self.addEventListener('message', event => {
  if (event.data?.type === 'SKIP_WAITING') self.skipWaiting()
})
clientsClaim()

function account(value) {
  return new Promise((resolve,reject)=>{
    const request=indexedDB.open('transitflow-push-account',1)
    request.onupgradeneeded=()=>request.result.createObjectStore('settings')
    request.onerror=()=>reject(request.error)
    request.onsuccess=()=>{const db=request.result,transaction=db.transaction('settings',value===undefined?'readonly':'readwrite'),store=transaction.objectStore('settings')
      const operation=value===undefined?store.get('account'):store.put(value,'account')
      operation.onsuccess=()=>{const result=operation.result;transaction.oncomplete=()=>{db.close();resolve(result)}}
      transaction.onerror=()=>{db.close();reject(transaction.error)}
    }
  })
}
self.addEventListener('message',event=>{
  if(event.data?.type==='PUSH_ACCOUNT')event.waitUntil((async()=>{
    const previous=await account(),next=event.data.user?{user:event.data.user,organization:event.data.organization}:null
    await account(next)
    if(!next||previous?.user!==next.user||previous?.organization!==next.organization){for(const n of await self.registration.getNotifications())n.close()}
  })())
})
self.addEventListener('push',event=>event.waitUntil((async()=>{
  let data;try{data=event.data?.json()}catch{return}
  const current=await account()
  if(!current||current.user!==data?.user||current.organization!==data.organization)return
  await self.registration.showNotification(typeof data.title==='string'?data.title:'TransitFlow',{
    body:typeof data.body==='string'?data.body:'Vous avez une nouvelle notification.',icon:'/icons/icon-192.png',
    tag:'transitflow-'+data.id,data:{id:data.id,context:data.context,organization:data.organization,user:data.user}})
})()))
self.addEventListener('notificationclick',event=>{
  event.notification.close();event.waitUntil((async()=>{
    const data=event.notification.data,current=await account()
    if(!current||current.user!==data?.user||current.organization!==data.organization)return
    const context=data.context||{},modules=['missions','incidents','maintenance','documents','field'],module=context.conversation?'messages':modules.includes(context.module)?context.module:'notifications'
    const params=new URLSearchParams({organization:data.organization})
    if(context.conversation)params.set('conversation',String(context.conversation))
    else if(context.id)params.set('record',String(context.id))
    const url='/app#'+module+'?'+params
    const windows=await self.clients.matchAll({type:'window',includeUncontrolled:true})
    const window=windows.find(w=>new URL(w.url).origin===self.location.origin&&new URL(w.url).pathname.startsWith('/app'))
    if(window){await window.navigate(url);await window.focus()}else await self.clients.openWindow(url)
  })())
})

import {ref} from 'vue'
import {api,organization,realtimeToken,refresh} from './api'
export const messageUnread=ref(0),notificationUnread=ref(0),connectionState=ref('Connexion…')
let socket:WebSocket|null=null,timer:ReturnType<typeof setTimeout>|undefined,heartbeat:ReturnType<typeof setInterval>|undefined,fallback:ReturnType<typeof setInterval>|undefined,stopped=true,retries=0,epoch=0
const handlers=new Set<(event:any)=>void>()
export function subscribeActivity(fn:(event:any)=>void){handlers.add(fn);return()=>handlers.delete(fn)}
function dispatch(event:any){handlers.forEach(fn=>fn(event))}
let counts:Promise<void>|null=null,countsAgain=false
export async function updateCounts(){
 if(counts){countsAgain=true;return counts}
 const selected=organization,generation=epoch
 counts=(async()=>{try{const [messages,notifications]=await Promise.all([api('messaging/conversations'),api('notifications')]);if(selected!==organization||generation!==epoch)return;messageUnread.value=messages.unread;notificationUnread.value=notifications.unread}catch{}})()
 try{await counts}finally{counts=null;if(countsAgain&&!stopped){countsAgain=false;updateCounts()}}
}
async function connect(generation:number){
 if(stopped||generation!==epoch||!navigator.onLine)return
 try{if(!realtimeToken()&&!await refresh())return;const token=realtimeToken();const tenant=organization
  const candidate=new WebSocket(`${location.protocol==='https:'?'wss:':'ws:'}//${location.host}/ws/activity`)
  socket=candidate
  candidate.onopen=()=>candidate.send(JSON.stringify({type:'authenticate',token,organization:tenant}))
  candidate.onmessage=event=>{let value;try{value=JSON.parse(event.data)}catch{return}
   if(generation!==epoch)return
   if(value.type==='ready'){retries=0;connectionState.value='En direct';ping();updateCounts();dispatch({type:'resync'})}
   else if(value.type==='access_revoked'){stopActivity();setPushAccount(null);window.dispatchEvent(new Event('organization-revoked'))}
   else if(value.type!=='pong'){if(!['typing','tracking','tracking_access'].includes(value.type))updateCounts();dispatch(value)}
  }
  candidate.onclose=event=>{if(stopped||generation!==epoch||socket!==candidate)return;connectionState.value='Reconnexion…';timer=setTimeout(async()=>{if(event.code===4403||event.code===4401)await refresh();connect(generation)},Math.min(30000,1000*2**Math.min(retries++,5))+Math.random()*500)}
  candidate.onerror=()=>candidate.close()
 }catch{connectionState.value='Reconnexion…';timer=setTimeout(()=>connect(generation),10000)}
}
function ping(){if(socket?.readyState===WebSocket.OPEN)socket.send(JSON.stringify({type:'ping',visible:document.visibilityState==='visible'}))}
function online(){if(stopped)return;clearTimeout(timer);const previous=socket;socket=null;previous?.close();connect(epoch);updateCounts();dispatch({type:'resync'})}
function visibility(){ping();if(document.visibilityState==='visible'){updateCounts();dispatch({type:'resync'})}}
export function startActivity(){stopActivity();stopped=false;const generation=epoch;messageUnread.value=0;notificationUnread.value=0;updateCounts();connect(generation);heartbeat=setInterval(ping,30000);fallback=setInterval(()=>{if(navigator.onLine&&document.visibilityState==='visible'){updateCounts();dispatch({type:'resync'})}},60000);window.addEventListener('online',online);document.addEventListener('visibilitychange',visibility)}
export function stopActivity(){stopped=true;epoch++;clearTimeout(timer);clearInterval(heartbeat);clearInterval(fallback);socket?.close();socket=null;window.removeEventListener('online',online);document.removeEventListener('visibilitychange',visibility);messageUnread.value=0;notificationUnread.value=0}
export function typing(conversation:string){if(socket?.readyState===WebSocket.OPEN)socket.send(JSON.stringify({type:'typing',conversation}))}

let pushAccount:{user:number|null,organization:string}={user:null,organization:''}
navigator.serviceWorker?.addEventListener('controllerchange',()=>{navigator.serviceWorker.controller?.postMessage({type:'PUSH_ACCOUNT',...pushAccount})})
export async function setPushAccount(user:number|null,tenant:string=''){
 pushAccount={user,organization:tenant}
 const registration=await navigator.serviceWorker?.getRegistration();registration?.active?.postMessage({type:'PUSH_ACCOUNT',user,organization:tenant})
}
export async function disableDevicePush(){
 const registration=await navigator.serviceWorker?.getRegistration();const subscription=await registration?.pushManager?.getSubscription()
 await setPushAccount(null)
 if(subscription){try{await api('notifications/subscriptions','DELETE',{endpoint:subscription.endpoint})}catch{}await subscription.unsubscribe()}
}

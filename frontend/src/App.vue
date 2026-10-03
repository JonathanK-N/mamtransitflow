<!-- Auteur : Jonathan Kakesa (JonathanK-N). -->
<script setup lang="ts">
import { onMounted, ref, defineAsyncComponent } from 'vue'
import PwaStatus from './PwaStatus.vue'
import {disableDevicePush,setPushAccount,stopActivity} from './activity'
import { ArrowRight, ArrowLeft, LoaderCircle, ShieldCheck } from 'lucide-vue-next'
import PublicSite from './PublicSite.vue'
const Workspace=defineAsyncComponent(()=>import('./Workspace.vue'))
import PasswordRecovery from './PasswordRecovery.vue'
import {api,refresh,setOrganization,organization,clearSession} from './api'
const screen=ref(location.pathname==='/commencer'?'register':location.pathname==='/connexion'?'login':location.pathname.startsWith('/app')?'loading':'public')
if(new URLSearchParams(location.search).has('reset'))screen.value='recovery'
const session=ref<any>(null),error=ref(''),busy=ref(false)
const form=ref({name:'',email:'',password:'',company:'',country:'GN',activity:'freight'})
const invitationToken=ref(new URLSearchParams(location.search).get('invitation')||sessionStorage.getItem('transitflow.invitation')||'')
if(new URLSearchParams(location.search).has('invitation')&&screen.value!=='recovery')screen.value='loading'
const countries=[['GN','Guinée','GNF','Africa/Conakry'],['CM','Cameroun','XAF','Africa/Douala'],['CG','Congo','XAF','Africa/Brazzaville'],['CD','RDC','CDF','Africa/Kinshasa'],['SN','Sénégal','XOF','Africa/Dakar'],['CI',"Côte d’Ivoire",'XOF','Africa/Abidjan'],['ML','Mali','XOF','Africa/Bamako'],['BJ','Bénin','XOF','Africa/Porto-Novo'],['BF','Burkina Faso','XOF','Africa/Ouagadougou'],['TG','Togo','XOF','Africa/Lome'],['GA','Gabon','XAF','Africa/Libreville'],['TD','Tchad','XAF','Africa/Ndjamena']]
function go(view:string){screen.value=view;error.value='';const path=view==='public'?'/':view==='register'?'/commencer':'/connexion';history.pushState({},'',path+(invitationToken.value&&view!=='public'?'?invitation='+encodeURIComponent(invitationToken.value):''))}
async function enter(data:any){
 session.value=data
 if(!data.organizations.some((x:any)=>x.id===organization))setOrganization(data.organizations[0]?.id||'')
 const invite=new URLSearchParams(location.search).get('invitation')||sessionStorage.getItem('transitflow.invitation')
 if(invite){try{const r=await api('invitation/accept','POST',{token:invite});setOrganization(r.organization);session.value=await api('auth/me');sessionStorage.removeItem('transitflow.invitation');invitationToken.value=''}catch(e:any){error.value=e.message}}
 const hash=location.pathname.startsWith('/app')?location.hash:''
 screen.value='workspace';history.replaceState({},'','/app'+hash)
}
async function submit(){
 busy.value=true;error.value=''
 try{
  let data
  if(screen.value==='register'){
   const country=countries.find(x=>x[0]===form.value.country)!
   data=await api('auth/register','POST',{name:form.value.name,email:form.value.email,password:form.value.password,invitation:invitationToken.value,organization:{name:form.value.company,country:country[0],currency:country[2],timezone:country[3],activities:[form.value.activity]}})
   if(invitationToken.value){sessionStorage.removeItem('transitflow.invitation');history.replaceState({},'','/commencer');invitationToken.value=''}
  }else data=await api('auth/login','POST',{email:form.value.email,password:form.value.password})
  await enter(data)
  form.value.password=''
 }catch(e:any){error.value=e.message}finally{busy.value=false}
}
let checkingAccess=false
async function revoked(){
 if(checkingAccess||!session.value)return
 checkingAccess=true;stopActivity();await setPushAccount(null)
 const old=organization;screen.value='loading'
 try{const fresh=await api('auth/me');session.value=fresh;setOrganization(fresh.organizations.find((x:any)=>x.id!==old)?.id||'');history.replaceState({},'','/app');screen.value=fresh.organizations.length?'workspace':'removed';error.value='Votre accès à cette entreprise a été retiré.'}catch{screen.value='removed';error.value='Votre accès à cette entreprise a été retiré.'}finally{checkingAccess=false}
}
async function logout(){try{await disableDevicePush();await api('auth/logout','POST');stopActivity();session.value=null;clearSession();form.value.password='';go('login')}catch(e:any){window.alert('Déconnexion non confirmée : '+e.message)}}
onMounted(async()=>{
 const invite=new URLSearchParams(location.search).get('invitation');if(invite)sessionStorage.setItem('transitflow.invitation',invite)
 window.addEventListener('organization-revoked',revoked)
 window.addEventListener('session-expired',()=>{stopActivity();setPushAccount(null);session.value=null;clearSession();form.value.password='';go('login');error.value='Votre session a expiré. Reconnectez-vous.'})
 window.addEventListener('popstate',()=>{
  if(location.pathname.startsWith('/app')){if(session.value)screen.value='workspace';else go('login')}
  else screen.value=location.pathname==='/commencer'?'register':location.pathname==='/connexion'?'login':'public'
 })
 if(screen.value==='loading'){if(await refresh()){try{await enter(await api('auth/me'));return}catch{}}go(invitationToken.value?'register':'login')}
})
</script>
<template>
 <PwaStatus/>
 <PublicSite v-if="screen==='public'" @login="go('login')" @register="go('register')"/>
 <div v-else-if="screen==='removed'" class="loading-screen"><p role="alert">{{error}}</p><button class="secondary" @click="logout">Se déconnecter</button></div>
 <Workspace v-else-if="screen==='workspace'&&session" :key="organization" :session="session" @logout="logout"/>
 <PasswordRecovery v-else-if="screen==='recovery'" @login="go('login')"/>
 <div v-else-if="screen==='loading'" class="loading-screen"><LoaderCircle class="spin"/> Ouverture de votre espace…</div>
 <main v-else class="auth-layout">
  <div class="auth-visual"><img src="/images/transport.jpg" alt="Camion sur la route"/><div class="auth-overlay"></div><a class="brand inverse" href="/" @click.prevent="go('public')"><img class="brand-mark" src="/icons/icon-192.png" width="36" height="36" alt=""/>TransitFlow</a><div class="auth-quote"><span class="eyebrow light">VOTRE PROCHAINE DESTINATION</span><h1>Une entreprise<br>qui avance.<br>Une gestion qui suit.</h1><p>Votre flotte, vos équipes et vos opérations.<br>Enfin au même endroit.</p></div></div>
  <div class="auth-panel"><button class="text-btn back" @click="go('public')"><ArrowLeft :size="17"/> Retour à l’accueil</button><div class="auth-form-wrap"><span class="eyebrow">BIENVENUE SUR TRANSITFLOW</span><h2>{{invitationToken?(screen==='register'?'Rejoignez votre entreprise.':'Acceptez votre invitation.'):(screen==='register'?'Créons votre espace.':'Heureux de vous retrouver.')}}</h2><p class="muted">{{invitationToken?(screen==='register'?'Créez votre compte avec le courriel invité et choisissez votre mot de passe. Vous rejoindrez l’entreprise qui vous invite.':'Connectez-vous avec le courriel invité et votre mot de passe habituel pour rejoindre cette entreprise.'):(screen==='register'?'Quelques informations pour organiser votre entreprise.':'Connectez-vous à votre entreprise pour reprendre la route.')}}</p>
   <div v-if="error" class="error-box" role="alert">{{error}}</div>
   <form @submit.prevent="submit">
    <label v-if="screen==='register'">Votre nom complet<input v-model="form.name" autocomplete="name" required maxlength="150" placeholder="Ex. Amadou Diallo"/></label>
    <label>Adresse courriel<input v-model="form.email" type="email" autocomplete="username" required placeholder="vous@entreprise.com"/></label>
    <label>Mot de passe<input v-model="form.password" type="password" :autocomplete="screen==='register'?'new-password':'current-password'" required :minlength="screen==='register'?10:1" :placeholder="screen==='register'?'Choisissez votre mot de passe':'Votre mot de passe'"/></label>
    <template v-if="screen==='register'&&!invitationToken"><label>Nom de l’entreprise<input v-model="form.company" required maxlength="150" placeholder="Ex. Transports Diallo"/></label><div class="form-row"><label>Pays<select v-model="form.country"><option v-for="c in countries" :value="c[0]">{{c[1]}}</option></select></label><label>Activité principale<select v-model="form.activity"><option value="freight">Marchandises</option><option value="passengers">Voyageurs</option><option value="shuttle">Navettes / scolaire</option><option value="fuel">Carburants</option><option value="cold">Frigorifique</option><option value="bulk">Vrac</option></select></label></div></template>
    <button class="primary full" :disabled="busy"><LoaderCircle v-if="busy" class="spin" :size="18"/>{{screen==='register'?(invitationToken?'Rejoindre mon entreprise':'Créer mon entreprise'):'Se connecter'}}<ArrowRight :size="18"/></button>
   </form><button v-if="screen==='login'" class="text-btn" @click="screen='recovery'">Mot de passe oublié ?</button><p class="auth-switch">{{screen==='register'?'Déjà un compte TransitFlow ?':invitationToken?'Première utilisation de TransitFlow ?':'Votre entreprise n’a pas encore d’espace ?'}} <button class="text-btn" @click="go(screen==='register'?'login':'register')">{{screen==='register'?'Se connecter':invitationToken?'Créer mon compte':'Commencer'}}</button></p><div class="auth-safe"><ShieldCheck :size="16"/> Votre espace entreprise est privé.</div>
  </div></div>
 </main>
</template>

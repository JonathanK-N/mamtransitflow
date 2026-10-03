<script setup lang="ts">
import {onMounted,onUnmounted,ref} from 'vue'
import {registerSW} from 'virtual:pwa-register'
const offline=ref(!navigator.onLine), restored=ref(false), update=ref(false), install=ref<any>(null), installing=ref(false), help=ref(false)
const standalone=ref(matchMedia('(display-mode: standalone)').matches || (navigator as any).standalone===true)
const ios=/iPad|iPhone|iPod/.test(navigator.userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1)
let timer:ReturnType<typeof setTimeout>|undefined, registration:ServiceWorkerRegistration|undefined
let updateRequested=false
function controlledReload(){if(updateRequested)location.reload();else update.value=true}
const applyUpdate=registerSW({onNeedRefresh(){update.value=true},onNeedReload:controlledReload,onRegisteredSW(_url,r){registration=r}})
async function updateApp(){updateRequested=true;if(registration?.waiting)await applyUpdate(true);else location.reload()}
function controllerChanged(){if(updateRequested)location.reload()}
function connection(){const previous=offline.value;offline.value=!navigator.onLine;if(previous&&!offline.value){restored.value=true;clearTimeout(timer);timer=setTimeout(()=>restored.value=false,5000);registration?.update().catch(()=>{})}}
function prompt(event:Event){event.preventDefault();install.value=event}
function installed(){standalone.value=true;install.value=null;help.value=false}
async function installApp(){installing.value=true;try{await install.value.prompt();await install.value.userChoice;install.value=null}finally{installing.value=false}}
function check(){if(navigator.onLine)registration?.update().catch(()=>{})}
onMounted(()=>{window.addEventListener('online',connection);window.addEventListener('offline',connection);window.addEventListener('beforeinstallprompt',prompt);window.addEventListener('appinstalled',installed);window.addEventListener('focus',check);navigator.serviceWorker?.addEventListener('controllerchange',controllerChanged)})
onUnmounted(()=>{clearTimeout(timer);window.removeEventListener('online',connection);window.removeEventListener('offline',connection);window.removeEventListener('beforeinstallprompt',prompt);window.removeEventListener('appinstalled',installed);window.removeEventListener('focus',check);navigator.serviceWorker?.removeEventListener('controllerchange',controllerChanged)})
</script>
<template>
 <aside class="pwa-status" aria-label="État de l’application">
  <p v-if="offline" class="connection-state" role="status">Vous êtes hors connexion. Les données et enregistrements nécessitent Internet.</p>
  <p v-else-if="restored" class="connection-state restored" role="status">Connexion rétablie</p>
  <div v-if="update" class="pwa-update" role="status"><span>Une nouvelle version de TransitFlow est disponible. Enregistrez votre travail avant de continuer.</span><button class="primary" @click="updateApp">Mettre à jour</button><button class="secondary" @click="update=false">Plus tard</button></div>
  <details v-if="!standalone&&(install||ios)" class="pwa-install" :open="help"><summary>Installer TransitFlow</summary><button v-if="install" class="primary" :disabled="installing" @click="installApp">Installer l’application</button><p v-else>Dans Safari, ouvrez Partager puis « Sur l’écran d’accueil » et activez « Ouvrir comme app » si proposé.</p></details>
 </aside>
</template>

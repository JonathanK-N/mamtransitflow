<!-- Auteur : Jonathan Kakesa (JonathanK-N). -->
<script setup lang="ts">
import {ref,onMounted,onUnmounted,computed} from 'vue'
import {api,organization} from './api'
const props=defineProps<{mission:any,canTrack:boolean,userId:number}>()
const key=`transitflow.positions.${props.userId}.${organization}.${props.mission.id}`
const points=ref<any[]>([]),queue=ref<any[]>([]),watching=ref(false),error=ref(''),sending=ref(false)
let watchId:number|undefined,timer:any,lastTime=0
try{queue.value=JSON.parse(localStorage.getItem(key)||'[]')}catch{error.value='La file locale ne peut pas être lue.'}
const latest=computed(()=>points.value[0])
function persist(){try{localStorage.setItem(key,JSON.stringify(queue.value))}catch{stop();error.value='Stockage du navigateur saturé. Les points en mémoire restent en attente.'}}
async function load(){try{points.value=(await api(`missions/${props.mission.id}/positions`)).positions}catch(e:any){error.value=e.message}}
async function sync(){
 if(sending.value||!queue.value.length||!navigator.onLine)return
 sending.value=true
 const batch=queue.value.slice(0,200)
 try{await api(`missions/${props.mission.id}/positions`,'POST',{positions:batch});queue.value.splice(0,batch.length);persist();await load()}catch(e:any){error.value=e.message}finally{sending.value=false}
}
function start(){
 if(!navigator.geolocation){error.value='La géolocalisation est indisponible.';return}
 error.value='';watching.value=true
 watchId=navigator.geolocation.watchPosition(position=>{
  if(position.timestamp-lastTime<10000)return
  if(queue.value.length>=5000){stop();error.value='File locale pleine. Synchronisez les positions avant de reprendre.';return}
  lastTime=position.timestamp
  queue.value.push({timestamp:new Date(position.timestamp).toISOString(),latitude:position.coords.latitude.toFixed(6),longitude:position.coords.longitude.toFixed(6)})
  persist();sync()
 },()=>{stop();error.value='Position indisponible. Vérifiez l’autorisation de localisation et le signal GPS.'},{enableHighAccuracy:true,maximumAge:10000,timeout:30000})
}
function stop(){if(watchId!==undefined)navigator.geolocation.clearWatch(watchId);watchId=undefined;watching.value=false}
onMounted(()=>{load();timer=setInterval(sync,15000);window.addEventListener('online',sync)})
onUnmounted(()=>{stop();clearInterval(timer);window.removeEventListener('online',sync)})
</script>
<template><section class="tracking-panel"><div class="line-heading"><h3>Suivi du trajet</h3><span class="status" :class="watching?'active':'planned'">{{watching?'Localisation active':'Localisation arrêtée'}}</span></div><p class="field-help">Le suivi utilise la position de cet appareil pendant que cette fiche reste ouverte. Les points non transmis restent dans ce navigateur ; fermer la fiche arrête la capture.</p><div v-if="error" class="error-box" role="alert">{{error}}</div><p v-if="latest">Dernier point : {{new Date(latest.timestamp).toLocaleString('fr-FR')}} · {{latest.latitude}}, {{latest.longitude}} <a class="text-btn" :href="`https://www.openstreetmap.org/?mlat=${latest.latitude}&mlon=${latest.longitude}#map=14/${latest.latitude}/${latest.longitude}`" target="_blank" rel="noopener noreferrer">Voir sur la carte</a></p><p v-else class="muted">Aucune position enregistrée.</p><div class="tracking-actions"><template v-if="canTrack"><button v-if="mission.status==='active'&&!watching" type="button" class="secondary small" @click="start">Activer le suivi de cet appareil</button><button v-if="watching" type="button" class="secondary small" @click="stop();sync()">Arrêter et synchroniser</button><button v-if="queue.length" type="button" class="primary small" :disabled="sending" @click="sync">Synchroniser {{queue.length}} point(s)</button></template><button type="button" class="text-btn" @click="load">Actualiser</button></div></section></template>

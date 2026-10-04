<script setup lang="ts">
import {ref,onMounted,onUnmounted} from 'vue'
import {api} from './api'
const props=defineProps<{customer?:string}>()
const rows=ref<any[]>([]),body=ref(''),error=ref(''),ready=ref(false),page=ref(1),count=ref(0),sending=ref(false)
const path=props.customer?`clients/${props.customer}/messages`:'portal/messages'
let timer:ReturnType<typeof setInterval>
let pendingId=''
async function load(){try{const r=await api(path+'?page='+page.value);rows.value=r.results;count.value=r.count;ready.value=true;error.value=''}catch(e:any){error.value=e.message}}
async function send(){if(sending.value)return;sending.value=true;try{pendingId=pendingId||crypto.randomUUID();await api(path,'POST',{body:body.value,client_id:pendingId});pendingId='';body.value='';page.value=1;await load()}catch(e:any){error.value=e.message}finally{sending.value=false}}
onMounted(async()=>{if(props.customer){try{await api(`clients/${props.customer}/conversation`,'POST',{})}catch(e:any){error.value=e.message;return}}await load();timer=setInterval(()=>{if(!document.hidden)load()},15000)})
onUnmounted(()=>clearInterval(timer))
</script>
<template><section class="client-discussion"><h3>Discussion client</h3><p>Cette discussion est séparée de la messagerie interne.</p><div v-if="error" class="error-box" role="alert">{{error}}</div><template v-if="ready"><form @submit.prevent="send"><label>Votre message<textarea v-model="body" required maxlength="5000" rows="3" @input="pendingId=''"/></label><button class="primary" :disabled="sending||!body.trim()">Envoyer le message</button></form><article v-for="row in rows" :key="row.id"><b>{{row.outgoing?'Vous':'Votre interlocuteur'}}</b><time>{{new Date(row.created_at).toLocaleString('fr-FR')}}</time><p>{{row.body}}</p></article><div class="table-pagination"><button class="secondary" :disabled="page===1" @click="page--;load()">Précédent</button><span>{{count}} messages</span><button class="secondary" :disabled="page*25>=count" @click="page++;load()">Suivant</button></div></template></section></template>
<style scoped>.client-discussion{padding:20px;max-width:800px}.client-discussion form{display:grid;gap:12px;margin:20px 0}.client-discussion article{padding:16px;margin:12px 0;border:1px solid #e5eaf0;border-radius:12px}.client-discussion p{white-space:pre-wrap;overflow-wrap:anywhere}.client-discussion time{display:block;font-size:12px;margin:8px 0}.client-discussion button{min-height:44px}</style>

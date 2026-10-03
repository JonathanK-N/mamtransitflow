<script setup lang="ts">
import {ref,nextTick,onUnmounted} from 'vue'
import {MoreHorizontal,MessageCircle,X} from 'lucide-vue-next'
import {api} from './api'
const props=defineProps<{employee:any,writable:boolean,admin:boolean,profile?:boolean}>()
const emit=defineEmits(['view','contact','removed'])
const mode=ref(''),busy=ref(false),error=ref(''),dialog=ref<HTMLElement|null>(null)
let previous:HTMLElement|null=null
async function show(value:string){previous=document.activeElement as HTMLElement;mode.value=value;error.value='';await nextTick();dialog.value?.querySelector<HTMLElement>('button')?.focus()}
function close(){if(busy.value)return;mode.value='';nextTick(()=>previous?.isConnected&&previous.focus())}
function keys(e:KeyboardEvent){if(e.key==='Escape'){e.preventDefault();close()}if(e.key==='Tab'){const controls=Array.from(dialog.value?.querySelectorAll<HTMLElement>('button:not(:disabled)')||[]),first=controls[0],last=controls.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus()}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus()}}}
async function contact(){busy.value=true;error.value='';try{const row=await api('employees/'+props.employee.id+'/contact','POST',{});mode.value='';emit('contact',row.id)}catch(e:any){error.value=e.message;if(!mode.value)await show('contact');error.value=e.message}finally{busy.value=false}}
async function remove(){busy.value=true;error.value='';try{await api('employees/'+props.employee.id+'/remove','POST',{});mode.value='';emit('removed')}catch(e:any){error.value=e.message}finally{busy.value=false}}
onUnmounted(()=>{mode.value=''})
</script>
<template>
 <button v-if="profile&&admin" type="button" class="secondary" @click="show('contact');contact()"><MessageCircle :size="18"/>Contacter</button>
 <button v-else-if="!profile" class="icon-btn" :aria-label="'Actions pour '+employee.name" aria-haspopup="dialog" :aria-expanded="!!mode" @click="show('menu')"><MoreHorizontal :size="22"/></button>
 <Teleport to="body"><div v-if="mode" class="modal-backdrop personnel-backdrop" @click.self="close"><section ref="dialog" class="personnel-dialog" role="dialog" aria-modal="true" :aria-label="mode==='remove'?'Retirer '+employee.name+' de l’entreprise ?':'Actions pour '+employee.name" @keydown="keys">
  <header><h2>{{mode==='remove'?'Retirer '+employee.name+' de l’entreprise ?':employee.name}}</h2><button class="icon-btn" aria-label="Fermer" :disabled="busy" @click="close"><X/></button></header>
  <div v-if="error" class="error-box" role="alert">{{error}}</div>
  <template v-if="mode==='menu'"><button class="secondary full" @click="close();emit('view')">{{writable?'Voir / Modifier':'Voir le profil'}}</button><button v-if="admin&&employee.active" class="secondary full" :disabled="busy" @click="contact"><MessageCircle :size="18"/>Contacter</button><button v-if="admin&&employee.active" class="secondary full danger-text" @click="mode='remove';error=''">Retirer de l’entreprise</button></template>
  <template v-else-if="mode==='remove'"><p>Cette personne perdra son accès à cette entreprise et ne pourra plus accéder à ses données, missions et conversations internes. Son historique professionnel sera conservé lorsque nécessaire.</p><footer><button class="secondary" :disabled="busy" @click="close">Annuler</button><button class="primary personnel-remove" :disabled="busy" @click="remove">{{busy?'Retrait en cours…':'Retirer de l’entreprise'}}</button></footer></template>
  <template v-else><p v-if="!error">Ouverture de la conversation…</p><button class="secondary" :disabled="busy" @click="close">Fermer</button></template>
 </section></div></Teleport>
</template>
<style scoped>
.personnel-backdrop{z-index:1200;padding: max(16px,env(safe-area-inset-top)) max(12px,env(safe-area-inset-right)) max(16px,env(safe-area-inset-bottom)) max(12px,env(safe-area-inset-left))}.personnel-dialog{background:white;border-radius:16px;padding:24px;width:100%;max-width:520px;max-height:calc(100dvh - 40px);overflow:auto;box-shadow:0 20px 70px #102a4340}.personnel-dialog header{display:flex;align-items:start;gap:12px;justify-content:space-between;margin-bottom:20px}.personnel-dialog h2{font-size:20px;line-height:1.4;overflow-wrap:anywhere;margin:0}.personnel-dialog p{line-height:1.65;margin:16px 0 24px}.personnel-dialog button{min-height:44px}.personnel-dialog .full{margin:10px 0;justify-content:flex-start}.personnel-dialog footer{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:12px}.personnel-remove{background:#b42318}.personnel-remove:hover{background:#912018}@media(max-width:600px){.personnel-dialog{padding:20px}.personnel-dialog footer button{width:100%;justify-content:center}}
</style>

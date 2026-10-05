<!-- Auteur : Jonathan Kakesa (JonathanK-N). -->
<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick,watch } from 'vue'
import { X, Plus, Trash2, Save, LoaderCircle, Download, Printer } from 'lucide-vue-next'
import { api,download,money } from './api'
import MissionTracking from './MissionTracking.vue'
import PersonnelActions from './PersonnelActions.vue'
const props=defineProps<{schema:any,record:any,currency:string,admin?:boolean,prefill?:any,assignment?:{mission?:string,order?:string,expected_updated_at:string},scope?:string,availableResources?:boolean}>()
const emit=defineEmits(['close','saved','contact','existing'])
const data=ref<Record<string,any>>({}),options=ref<Record<string,any[]>>({}),error=ref(''),saving=ref(false)
const initializing=ref(true),duplicates=ref<any[]>([]),duplicateConfirmed=ref(false)
const assignmentFields=['driver','vehicle','departure','arrival','origin','destination','loaded_quantity','notes']
const fields=computed(()=>props.schema.fields.filter((f:any)=>!f.readonly&&!(props.schema.key==='employees'&&props.record&&f.name==='active')&&(!props.assignment||assignmentFields.includes(f.name))))
const locked=computed(()=>!props.schema.writable||props.record&&['issued','paid','posted','approved','completed','active','cancelled','received','ordered','confirmed','boarded','paused','closed','reported','resolved','submitted','rejected','disbursed','settled','matched'].includes(props.record.status)||props.record&&['payments','supplier-payments','movements','bookings'].includes(props.schema.key))
const lineType=computed(()=>props.schema.key==='journal'?'journal':props.schema.key==='purchases'?'purchase':'invoice')
const lines=computed(()=>data.value.lines||[])
const availabilityBusy=ref(false);let availabilityGeneration=0,alive=true
const optionVersions:Record<string,number>={}
const scopedApi=(path:string,method='GET',body?:any)=>api(path,method,body,true,props.scope)
async function loadOptions(resource:string,query='') {
 if((props.assignment||props.availableResources)&&['employees','vehicles'].includes(resource)){await availableOptions(resource,query);return}
 try{options.value[resource]=(await scopedApi(resource+'?page_size=100&q='+encodeURIComponent(query))).results}catch{options.value[resource]=[]}
}
async function availableOptions(resource:string,query=''){
 const generation=availabilityGeneration
 const version=optionVersions[resource]=(optionVersions[resource]||0)+1
 if(!data.value.departure||!data.value.arrival){options.value[resource]=[];return}
 const params=new URLSearchParams({kind:resource==='employees'?'drivers':'vehicles',available:'1',page_size:'100',q:query,departure:new Date(data.value.departure).toISOString(),arrival:new Date(data.value.arrival).toISOString()})
 if(props.assignment?.mission)params.set('mission',props.assignment.mission)
 try{const result=await scopedApi('operations/resources?'+params);if(alive&&generation===availabilityGeneration&&version===optionVersions[resource]){options.value[resource]=result.results;const field=resource==='employees'?'driver':'vehicle';if(!query&&data.value[field]&&!result.results.some((row:any)=>row.id===data.value[field]))data.value[field]=''}}catch(e:any){if(alive&&generation===availabilityGeneration&&version===optionVersions[resource]){options.value[resource]=[];error.value=e.message}}
}
async function updateAvailability(){if(!(props.assignment||props.availableResources)||initializing.value)return;const generation=++availabilityGeneration;availabilityBusy.value=true;await Promise.all(['employees','vehicles'].map(resource=>availableOptions(resource)));if(generation===availabilityGeneration)availabilityBusy.value=false}
watch(()=>[data.value.departure,data.value.arrival],updateAvailability)
function addLine(){
 if(!data.value.lines)data.value.lines=[]
 data.value.lines.push(lineType.value==='journal'?{account:'',debit:0,credit:0}:lineType.value==='purchase'?{item:'',quantity:1,price:0}:{description:'',quantity:1,price:0,tax_rate:0})
}
function keydown(e:KeyboardEvent){if(e.key==='Escape')emit('close')}
onMounted(async()=>{
 const resources=new Set<string>()
 for(const f of fields.value){
  let value=props.record?.[f.name]??props.prefill?.[f.name]??f.default??(f.type==='checkbox'?false:f.type==='json'?[]:'')
  if(f.type==='datetime-local'&&value){const d=new Date(value);value=new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,16)}
  data.value[f.name]=Array.isArray(value)?JSON.parse(JSON.stringify(value)):value
  if(f.relation&&!locked.value)resources.add(f.relation)
 }
 if(['invoices','supplier-bills','purchases','journal'].includes(props.schema.key)&&!lines.value.length)addLine()
 if(props.schema.key==='journal'&&!locked.value)resources.add('accounts')
 if(props.schema.key==='purchases'&&!locked.value)resources.add('stock')
 await Promise.all([...resources].map(resource=>loadOptions(resource)))
 for(const f of fields.value){
  const value=data.value[f.name]
  if(f.relation&&value&&!locked.value&&!props.assignment&&!props.availableResources&&!options.value[f.relation]?.some((row:any)=>row.id===value)){
   try{const row=await scopedApi(f.relation+'/'+value);options.value[f.relation]=[row,...(options.value[f.relation]||[])]}catch{error.value='Une référence préremplie n’est plus accessible. Sélectionnez une fiche valide.'}
  }
 }
 initializing.value=false
 await nextTick()
 document.addEventListener('keydown',keydown)
 document.querySelector<HTMLInputElement>('.editor input')?.focus()
})
onUnmounted(()=>{alive=false;document.removeEventListener('keydown',keydown)})
async function save(){
 saving.value=true;error.value=''
 try{
  let body:Record<string,any>={}
  for(const f of fields.value){
   const value=data.value[f.name]
   if(f.type==='file'&&!(value instanceof File))continue
   if(value===''&&(f.name==='user'||f.type==='relation'||['date','datetime-local','number'].includes(f.type))){if(!f.required)body[f.name]=null;continue}
   body[f.name]=f.type==='datetime-local'&&value?new Date(value).toISOString():value
  }
  if(props.schema.key==='partners'&&!props.record&&!duplicateConfirmed.value){
   duplicates.value=await scopedApi('clients/duplicates','POST',body)
   if(duplicates.value.length)return
  }
  if(props.schema.key==='documents'){
   const multipart=new FormData();for(const [key,value] of Object.entries(body)){if(value!==null&&value!==undefined)multipart.append(key,value instanceof File?value:typeof value==='object'?JSON.stringify(value):String(value))}
   body=multipart
  }
  if(props.assignment)await scopedApi('operations/assign','POST',{...props.assignment,fields:body})
  else await scopedApi(props.schema.key+(props.record?'/'+props.record.id:''),props.record?'PATCH':'POST',body)
  emit('saved')
 }catch(e:any){error.value=e.message}finally{saving.value=false}
}
function print(){window.print()}
</script>
<template>
 <div class="modal-backdrop" @click.self="$emit('close')"><section class="editor" role="dialog" aria-modal="true" :aria-label="schema.label">
  <header class="editor-head"><div><span class="eyebrow">{{schema.label}}</span><h2>{{record?(record.label||'Détail'):'Nouvel enregistrement'}}</h2></div><button class="icon-btn" aria-label="Fermer" @click="$emit('close')"><X/></button></header>
  <div v-if="initializing" class="editor-body" role="status"><LoaderCircle class="spin"/> Chargement de la fiche…</div>
  <form v-else @submit.prevent="save" class="editor-body">
   <div v-if="error" class="error-box" role="alert">{{error}}</div>
   <div v-if="duplicates.length&&!duplicateConfirmed" class="info-box"><p>Un client similaire existe déjà.</p><p v-for="row in duplicates">{{row.name}} · {{row.email}} · {{row.phone}} <button type="button" class="secondary" @click="emit('existing',row)">Voir la fiche existante</button></p><button type="button" class="secondary" @click="duplicateConfirmed=true;save()">Créer quand même</button><button type="button" class="secondary" @click="emit('close')">Annuler</button></div>
   <div v-if="locked" class="info-box">Cet enregistrement est consultable. Son état ou vos permissions ne permettent pas de modifier ses valeurs.</div>
   <div v-if="assignment" class="info-box"><p>Seuls les chauffeurs et véhicules disponibles sur toute la période sont proposés. La disponibilité sera vérifiée à l’enregistrement.</p><p v-if="record">Chauffeur : {{record.relations?.driver}} → {{options.employees?.find((x:any)=>x.id===data.driver)?.label||"À choisir"}}<br/>Véhicule : {{record.relations?.vehicle}} → {{options.vehicles?.find((x:any)=>x.id===data.vehicle)?.label||"À choisir"}}</p><p v-if="availabilityBusy" role="status">Vérification des disponibilités…</p></div>
   <PersonnelActions v-if="record&&schema.key==='employees'&&record.active" :employee="record" :writable="schema.writable" :admin="!!admin" profile @contact="emit('contact',$event)"/>
   <div class="form-grid">
    <template v-for="f in fields" :key="f.name">
     <div v-if="f.name==='lines'" class="span-2 line-editor"><div class="line-heading"><h3>{{lineType==='journal'?'Écritures':lineType==='purchase'?'Articles commandés':'Prestations'}}</h3><button v-if="!locked" type="button" class="secondary small" @click="addLine"><Plus :size="15"/>Ajouter une ligne</button></div>
      <div v-for="(line,i) in lines" :key="i" class="line-row" :class="lineType">
       <template v-if="lineType==='journal'"><label>Compte<select v-model="line.account" :disabled="locked" required><option value="">Choisir</option><option v-if="locked" :value="line.account">{{line.account}}</option><option v-for="o in options.accounts||[]" :value="o.code">{{o.label}}</option></select></label><label>Débit<input v-model="line.debit" type="number" min="0" step=".01" :disabled="locked"/></label><label>Crédit<input v-model="line.credit" type="number" min="0" step=".01" :disabled="locked"/></label></template>
       <template v-else><label v-if="lineType==='purchase'">Article<select v-model="line.item" required :disabled="locked"><option value="">Choisir</option><option v-if="locked" :value="line.item">{{line.item}}</option><option v-for="o in options.stock||[]" :value="o.id">{{o.label}}</option></select></label><label v-else>Description<input v-model="line.description" required :disabled="locked" placeholder="Prestation de transport"/></label><label>Quantité<input v-model="line.quantity" type="number" step=".001" min=".001" required :disabled="locked"/></label><label>Prix unitaire<input v-model="line.price" type="number" min="0" step="any" required :disabled="locked"/></label><label v-if="lineType==='invoice'">Taxe (%)<input v-model="line.tax_rate" type="number" min="0" max="100" step=".01" :disabled="locked"/></label></template>
       <button v-if="!locked" class="icon-btn danger-text" type="button" aria-label="Supprimer cette ligne" @click="data.lines.splice(i,1)"><Trash2 :size="15"/></button>
      </div>
      <p v-if="lineType==='invoice'" class="field-help">Les taux sont ceux que votre entreprise applique. Faites valider votre paramétrage fiscal.</p>
     </div>
     <div v-else-if="f.name==='compartments'" class="span-2"><div class="line-heading"><h3>Compartiments (facultatif)</h3><button v-if="!locked" type="button" class="secondary small" @click="data.compartments.push({name:'',capacity:0})"><Plus :size="14"/>Ajouter</button></div><div v-for="(part,i) in data.compartments" class="line-row"><label>Nom<input v-model="part.name" :disabled="locked" required/></label><label>Capacité<input v-model="part.capacity" type="number" min=".001" step=".001" :disabled="locked" required/></label><button v-if="!locked" type="button" class="icon-btn" aria-label="Supprimer ce compartiment" @click="data.compartments.splice(i,1)"><Trash2 :size="15"/></button></div></div>
     <label v-else :class="{'span-2':f.type==='textarea','checkbox-label':f.type==='checkbox'}">{{f.label}}<span v-if="f.required" class="required">*</span>
      <textarea v-if="f.type==='textarea'" v-model="data[f.name]" :disabled="locked" :required="f.required" rows="3"></textarea>
      <template v-else-if="f.type==='relation'"><input v-if="!locked" type="search" :aria-label="'Rechercher '+f.label" placeholder="Filtrer les choix…" @input="loadOptions(f.relation,($event.target as HTMLInputElement).value)"/><select v-model="data[f.name]" :aria-label="f.label" :disabled="locked" :required="f.required"><option value="">Sélectionner</option><option v-if="locked" :value="data[f.name]">{{record?.relations?.[f.name]||data[f.name]}}</option><option v-for="option in options[f.relation]||[]" :value="option.id">{{option.label}}</option></select></template>
      <select v-else-if="f.type==='select'" v-model="data[f.name]" :disabled="locked" :required="f.required"><option v-for="o in f.options" :value="o.value">{{o.label}}</option></select>
      <input v-else-if="f.type==='checkbox'" v-model="data[f.name]" type="checkbox" :disabled="locked"/>
      <template v-else-if="f.type==='file'"><button v-if="record" type="button" class="secondary" @click="download('documents/'+record.id+'/download',record.title)"><Download :size="15"/>Télécharger le fichier</button><input v-if="!locked" type="file" accept="application/pdf,image/png,image/jpeg" :required="!record" @change="data[f.name]=($event.target as HTMLInputElement).files?.[0]"/></template>
      <pre v-else-if="f.type==='json'">{{JSON.stringify(data[f.name],null,2)}}</pre>
      <input v-else v-model="data[f.name]" :type="f.type" :step="f.type==='number'?'.001':undefined" :disabled="locked" :required="f.required"/>
      <small v-if="f.type==='datetime-local'" class="field-help">Heure locale de votre navigateur.</small>
     </label>
    </template>
   </div>
   <div v-if="record&&['invoices','supplier-bills'].includes(schema.key)" class="invoice-summary"><p>Total HT <strong>{{money(record.subtotal,currency)}}</strong></p><p>Taxes <strong>{{money(record.tax,currency)}}</strong></p><p>Total TTC <strong>{{money(record.total,currency)}}</strong></p><p>Réglé <strong>{{money(record.paid,currency)}}</strong></p></div>
   <MissionTracking v-if="record&&schema.key==='missions'&&['active','completed','cancelled'].includes(record.status)" :mission="record" :can-track="schema.canTrack" :user-id="schema.userId"/>
   <footer class="editor-footer"><button type="button" class="secondary" @click="$emit('close')">Fermer</button><button v-if="record" type="button" class="secondary" @click="print"><Printer :size="16"/>Imprimer</button><button v-if="!locked" class="primary" :disabled="saving||availabilityBusy"><LoaderCircle v-if="saving" class="spin" :size="16"/><Save v-else :size="16"/>Enregistrer</button></footer>
  </form>
 </section></div>
</template>

<!-- Auteur : Jonathan Kakesa (JonathanK-N). -->
<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { X, Plus, Trash2, Save, LoaderCircle, Download, Printer } from 'lucide-vue-next'
import { api,download,money } from './api'
import MissionTracking from './MissionTracking.vue'
const props=defineProps<{schema:any,record:any,currency:string}>()
const emit=defineEmits(['close','saved'])
const data=ref<Record<string,any>>({}),options=ref<Record<string,any[]>>({}),error=ref(''),saving=ref(false)
const fields=computed(()=>props.schema.fields.filter((f:any)=>!f.readonly))
const locked=computed(()=>!props.schema.writable||props.record&&['issued','paid','posted','approved','completed','active','cancelled','received','ordered','confirmed','boarded'].includes(props.record.status)||props.record&&['payments','movements','bookings'].includes(props.schema.key))
const lineType=computed(()=>props.schema.key==='journal'?'journal':props.schema.key==='purchases'?'purchase':'invoice')
const lines=computed(()=>data.value.lines||[])
async function loadOptions(resource:string,query='') {try{options.value[resource]=(await api(resource+'?page_size=100&q='+encodeURIComponent(query))).results}catch{options.value[resource]=[]}}
function addLine(){
 if(!data.value.lines)data.value.lines=[]
 data.value.lines.push(lineType.value==='journal'?{account:'',debit:0,credit:0}:lineType.value==='purchase'?{item:'',quantity:1,price:0}:{description:'',quantity:1,price:0,tax_rate:0})
}
function keydown(e:KeyboardEvent){if(e.key==='Escape')emit('close')}
onMounted(async()=>{
 for(const f of fields.value){
  let value=props.record?.[f.name]??f.default??(f.type==='checkbox'?false:f.type==='json'?[]:'')
  if(f.type==='datetime-local'&&value){const d=new Date(value);value=new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,16)}
  data.value[f.name]=Array.isArray(value)?JSON.parse(JSON.stringify(value)):value
  if(f.relation&&!locked.value)await loadOptions(f.relation)
 }
 if(['invoices','purchases','journal'].includes(props.schema.key)&&!lines.value.length)addLine()
 if(props.schema.key==='journal'&&!locked.value)await loadOptions('accounts')
 if(props.schema.key==='purchases'&&!locked.value)await loadOptions('stock')
 document.addEventListener('keydown',keydown)
 setTimeout(()=>document.querySelector<HTMLInputElement>('.editor input')?.focus(),50)
})
onUnmounted(()=>document.removeEventListener('keydown',keydown))
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
  if(props.schema.key==='documents'){
   const multipart=new FormData();for(const [key,value] of Object.entries(body)){if(value!==null&&value!==undefined)multipart.append(key,value instanceof File?value:typeof value==='object'?JSON.stringify(value):String(value))}
   body=multipart
  }
  await api(props.schema.key+(props.record?'/'+props.record.id:''),props.record?'PATCH':'POST',body)
  emit('saved')
 }catch(e:any){error.value=e.message}finally{saving.value=false}
}
function print(){window.print()}
</script>
<template>
 <div class="modal-backdrop" @click.self="$emit('close')"><section class="editor" role="dialog" aria-modal="true" :aria-label="schema.label">
  <header class="editor-head"><div><span class="eyebrow">{{schema.label}}</span><h2>{{record?(record.label||'Détail'):'Nouvel enregistrement'}}</h2></div><button class="icon-btn" aria-label="Fermer" @click="$emit('close')"><X/></button></header>
  <form @submit.prevent="save" class="editor-body">
   <div v-if="error" class="error-box" role="alert">{{error}}</div>
   <div v-if="locked" class="info-box">Cet enregistrement est consultable. Son état ou vos permissions ne permettent pas de modifier ses valeurs.</div>
   <div class="form-grid">
    <template v-for="f in fields" :key="f.name">
     <div v-if="f.name==='lines'" class="span-2 line-editor"><div class="line-heading"><h3>{{lineType==='journal'?'Écritures':lineType==='purchase'?'Articles commandés':'Prestations'}}</h3><button v-if="!locked" type="button" class="secondary small" @click="addLine"><Plus :size="15"/>Ajouter une ligne</button></div>
      <div v-for="(line,i) in lines" :key="i" class="line-row" :class="lineType">
       <template v-if="lineType==='journal'"><label>Compte<select v-model="line.account" :disabled="locked" required><option value="">Choisir</option><option v-if="locked" :value="line.account">{{line.account}}</option><option v-for="o in options.accounts||[]" :value="o.code">{{o.label}}</option></select></label><label>Débit<input v-model="line.debit" type="number" min="0" step=".01" :disabled="locked"/></label><label>Crédit<input v-model="line.credit" type="number" min="0" step=".01" :disabled="locked"/></label></template>
       <template v-else><label v-if="lineType==='purchase'">Article<select v-model="line.item" required :disabled="locked"><option value="">Choisir</option><option v-if="locked" :value="line.item">{{line.item}}</option><option v-for="o in options.stock||[]" :value="o.id">{{o.label}}</option></select></label><label v-else>Description<input v-model="line.description" required :disabled="locked" placeholder="Prestation de transport"/></label><label>Quantité<input v-model="line.quantity" type="number" step=".001" min=".001" required :disabled="locked"/></label><label>Prix unitaire<input v-model="line.price" type="number" min="0" step=".01" required :disabled="locked"/></label><label v-if="lineType==='invoice'">Taxe (%)<input v-model="line.tax_rate" type="number" min="0" max="100" step=".01" :disabled="locked"/></label></template>
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
   <div v-if="record&&schema.key==='invoices'" class="invoice-summary"><p>Total HT <strong>{{money(record.subtotal,currency)}}</strong></p><p>Taxes <strong>{{money(record.tax,currency)}}</strong></p><p>Total TTC <strong>{{money(record.total,currency)}}</strong></p><p>Réglé <strong>{{money(record.paid,currency)}}</strong></p></div>
   <MissionTracking v-if="record&&schema.key==='missions'&&['active','completed'].includes(record.status)" :mission="record" :can-track="schema.canTrack" :user-id="schema.userId"/>
   <footer class="editor-footer"><button type="button" class="secondary" @click="$emit('close')">Fermer</button><button v-if="record" type="button" class="secondary" @click="print"><Printer :size="16"/>Imprimer</button><button v-if="!locked" class="primary" :disabled="saving"><LoaderCircle v-if="saving" class="spin" :size="16"/><Save v-else :size="16"/>Enregistrer</button></footer>
  </form>
 </section></div>
</template>

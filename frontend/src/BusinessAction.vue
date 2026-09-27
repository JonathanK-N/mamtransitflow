<!-- Auteur : Jonathan Kakesa (JonathanK-N). -->
<script setup lang="ts">
import {ref,onMounted} from 'vue'
import {X,LoaderCircle} from 'lucide-vue-next'
import {api} from './api'
const props=defineProps<{resource:string,record:any,action:string,label:string,fields:any[]}>()
const emit=defineEmits(['close','saved'])
const data=ref<any>({}),options=ref<Record<string,any[]>>({}),busy=ref(false),loading=ref(true),error=ref('')
onMounted(async()=>{try{for(const field of props.fields){data.value[field.name]='';if(field.resource)options.value[field.name]=(await api(field.resource+'?page_size=100')).results}}catch(e:any){error.value=e.message}finally{loading.value=false}})
async function save(){busy.value=true;error.value='';try{await api(`${props.resource}/${props.record.id}/actions/${props.action}`,'POST',data.value);emit('saved')}catch(e:any){error.value=e.message}finally{busy.value=false}}
</script>
<template><div class="modal-backdrop" @click.self="emit('close')"><section class="editor" role="dialog" aria-modal="true" :aria-label="label"><header class="editor-head"><div><span class="eyebrow">{{record.label}}</span><h2>{{label}}</h2></div><button class="icon-btn" aria-label="Fermer" @click="emit('close')"><X/></button></header><form class="editor-body" @submit.prevent="save"><div v-if="error" class="error-box" role="alert">{{error}}</div><div v-if="loading" role="status"><LoaderCircle class="spin"/>Chargement…</div><div v-else class="form-grid"><label v-for="field in fields" class="span-2">{{field.label}}<textarea v-if="field.type==='textarea'" v-model="data[field.name]" :required="field.required" rows="6" maxlength="10000"></textarea><select v-else-if="field.type==='relation'" v-model="data[field.name]" :required="field.required"><option value="">Sélectionner</option><option v-for="option in options[field.name]||[]" :value="option.id">{{option.label}}</option></select><input v-else v-model="data[field.name]" :type="field.type" :required="field.required"/></label></div><footer class="editor-footer"><button class="secondary" type="button" @click="emit('close')">Annuler</button><button class="primary" :disabled="busy||loading">{{label}}</button></footer></form></section></div></template>

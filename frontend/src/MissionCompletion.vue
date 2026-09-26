<!-- Auteur : Jonathan Kakesa (JonathanK-N). -->
<script setup lang="ts">
import {ref} from 'vue'
import {api} from './api'
const props=defineProps<{mission:any}>(),emit=defineEmits(['close','saved'])
const form=ref({loaded_quantity:props.mission.loaded_quantity,delivered_quantity:props.mission.delivered_quantity,delivery_note:props.mission.delivery_note})
const error=ref(''),busy=ref(false)
async function save(){busy.value=true;error.value='';try{await api(`missions/${props.mission.id}/actions/complete`,'POST',form.value);emit('saved')}catch(e:any){error.value=e.message}finally{busy.value=false}}
</script>
<template><div class="modal-backdrop" @click.self="emit('close')"><section class="editor" role="dialog" aria-modal="true" aria-label="Terminer la mission"><header class="editor-head"><h2>Livraison · {{mission.reference}}</h2><button class="secondary" @click="emit('close')">Fermer</button></header><form class="editor-body" @submit.prevent="save"><p>Renseignez le bilan du trajet avant sa clôture.</p><div v-if="error" class="error-box" role="alert">{{error}}</div><div class="form-grid"><label>Quantité chargée<input v-model="form.loaded_quantity" type="number" min="0" step=".001" required/></label><label>Quantité livrée<input v-model="form.delivered_quantity" type="number" min="0" step=".001" required/></label><label class="span-2">Preuve et réserves de livraison<textarea v-model="form.delivery_note" rows="5" maxlength="10000" placeholder="Réceptionnaire, référence du bon, écarts constatés…"></textarea></label></div><p class="field-help">Pour un transport de voyageurs, conservez les quantités à zéro. Les justificatifs peuvent être ajoutés dans Documents.</p><footer class="editor-footer"><button class="secondary" type="button" @click="emit('close')">Annuler</button><button class="primary" :disabled="busy">Clôturer la mission</button></footer></form></section></div></template>

<script setup lang="ts">
import {ref,onUnmounted,watch} from 'vue'
import {api,money} from './api'
const props=defineProps<{initial:any,org:any}>()
const data=ref(props.initial),start=ref(''),end=ref(''),page=ref(1),busy=ref(false),error=ref('')
let alive=true,generation=0
watch(()=>props.initial,value=>{generation++;data.value=value;start.value='';end.value='';page.value=1;busy.value=false})
async function load(reset=false){if(reset)page.value=1;const version=++generation;busy.value=true;error.value='';const params=new URLSearchParams({page:String(page.value)});if(start.value)params.set('start',start.value);if(end.value)params.set('end',end.value)
 try{const result=await api('reports?'+params,'GET',undefined,true,props.org.id);if(alive&&version===generation)data.value=result}catch(e:any){if(alive&&version===generation)error.value=e.message}finally{if(alive&&version===generation)busy.value=false}}
onUnmounted(()=>{alive=false;generation++})
</script>
<template>
 <section class="reports-workspace">
  <form class="panel report-filters" @submit.prevent="load(true)"><label>Du<input v-model="start" type="date"/></label><label>Au<input v-model="end" type="date"/></label><button class="primary" :disabled="busy">Appliquer la période</button><p>Sans dates : tout l'historique. Une période complète est limitée à 366 jours.</p></form>
  <p v-if="error" class="error-box" role="alert">{{error}}</p><p v-if="busy" role="status">Chargement des rapports...</p>
  <section class="panel"><header class="panel-heading"><div><h2>Balance comptable</h2><p>Écritures comptabilisées selon leur date - {{data.currency}}</p></div></header><div class="table-wrap"><table><thead><tr><th>COMPTE</th><th>LIBELLÉ</th><th>DÉBIT</th><th>CRÉDIT</th><th>SOLDE</th></tr></thead><tbody><tr v-for="row in data.trial_balance" :key="row.code"><td data-label="Compte">{{row.code}}</td><td data-label="Libellé">{{row.name}}</td><td data-label="Débit">{{money(row.debit,org.currency)}}</td><td data-label="Crédit">{{money(row.credit,org.currency)}}</td><td data-label="Solde"><strong>{{money(row.balance,org.currency)}}</strong></td></tr></tbody></table></div></section>
  <section v-if="data.profitability_available" class="panel"><header class="panel-heading"><div><h2>Rentabilité des commandes</h2><p>{{data.note}} Période selon la date prévue de la commande.</p></div></header><p v-if="!data.profitability.length" class="empty-state">Aucune commande sur cette période.</p><div v-else class="table-wrap"><table><thead><tr><th>COMMANDE</th><th>CLIENT</th><th>PRIX CONVENU</th><th>COÛTS DIRECTS</th><th>MARGE</th></tr></thead><tbody><tr v-for="row in data.profitability" :key="row.reference"><td data-label="Commande">{{row.reference}}</td><td data-label="Client">{{row.customer}}</td><td data-label="Prix convenu">{{money(row.revenue,org.currency)}}</td><td data-label="Coûts directs">{{money(row.cost,org.currency)}}</td><td data-label="Marge">{{money(row.margin,org.currency)}}</td></tr></tbody></table></div><footer class="report-pages"><button class="secondary" :disabled="busy||page<=1" @click="page--;load()">Précédente</button><span>{{data.profitability_count}} commande(s) - {{data.profitability_page}} / {{data.profitability_pages}}</span><button class="secondary" :disabled="busy||page>=data.profitability_pages" @click="page++;load()">Suivante</button></footer></section>
 </section>
</template>
<style scoped>
.reports-workspace{display:grid;gap:20px}.report-filters{display:flex;flex-wrap:wrap;align-items:end;gap:16px;padding:20px}.report-filters label{display:grid;gap:8px}.report-filters input,.report-filters button,.report-pages button{min-height:44px}.report-filters p{flex-basis:100%;margin:0}.report-pages{display:flex;gap:12px;justify-content:space-between;align-items:center;padding:20px;flex-wrap:wrap}@media(max-width:600px){.report-filters label{flex:1;min-width:120px}.table-wrap{overflow:visible}table,tbody,tr,td{display:block;width:100%;min-width:0}thead{display:none}tr{padding:12px;border-bottom:1px solid #dce7df}td{display:flex;justify-content:space-between;gap:12px;overflow-wrap:anywhere;border:0;text-align:right}td::before{content:attr(data-label);font-weight:600;text-align:left}.report-pages{justify-content:center}}
</style>

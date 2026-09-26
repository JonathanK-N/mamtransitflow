<!-- Auteur : Jonathan Kakesa (JonathanK-N). -->
<script setup lang="ts">
import {ref} from 'vue'
import {api} from './api'
const emit=defineEmits(['login'])
const token=new URLSearchParams(location.search).get('reset')||''
const email=ref(''),password=ref(''),confirmation=ref(''),error=ref(''),message=ref(''),busy=ref(false)
async function submit(){
 error.value='';message.value=''
 if(token&&password.value!==confirmation.value){error.value='Les deux mots de passe doivent être identiques.';return}
 busy.value=true
 try{const r=await api('auth/password/'+(token?'reset':'request'),'POST',token?{token,password:password.value}:{email:email.value});message.value=r.detail}catch(e:any){error.value=e.message}finally{busy.value=false}
}
</script>
<template>
 <main class="recovery-page"><a href="/" class="brand"><span class="brand-mark">T</span>TransitFlow</a><section class="panel recovery-card"><span class="eyebrow">VOTRE COMPTE</span><h1>{{token?'Nouveau mot de passe':'Retrouver votre accès'}}</h1><p class="muted">{{token?'Choisissez un mot de passe personnel et unique.':'Indiquez le courriel associé à votre compte.'}}</p><div v-if="error" class="error-box" role="alert">{{error}}</div><div v-if="message" class="info-box" role="status">{{message}}</div><form v-if="!message" @submit.prevent="submit"><label v-if="!token">Adresse courriel<input type="email" v-model="email" required autocomplete="email"/></label><template v-else><label>Nouveau mot de passe<input v-model="password" type="password" required minlength="10" autocomplete="new-password"/></label><label>Confirmer le mot de passe<input v-model="confirmation" type="password" required minlength="10" autocomplete="new-password"/></label></template><button class="primary full" :disabled="busy">{{busy?'Traitement…':token?'Enregistrer le mot de passe':'Recevoir le lien'}}</button></form><button class="text-btn" @click="emit('login')">Retour à la connexion</button></section></main>
</template>

<!-- Auteur : Jonathan Kakesa (JonathanK-N). -->
<script setup lang="ts">
import { ref } from 'vue'
import { ArrowUpRight, ArrowRight, ChevronLeft, ChevronRight, Truck, Bus, ShieldCheck, Layers3, Route, Wrench, Wallet, Check, Menu, X } from 'lucide-vue-next'
defineEmits(['login','register'])
const menu=ref(false),slide=ref(0)
const slides=[
 {image:'/images/transport.jpg',title:'Les marchandises avancent. Votre entreprise aussi.',label:'MARCHANDISES & LOGISTIQUE',text:'De la commande à la livraison, reliez vos équipes, vos véhicules et vos clients.'},
 {image:'/images/voyageurs.jpg',title:'Chaque voyage commence par une bonne organisation.',label:'VOYAGEURS & NAVETTES',text:'Lignes, départs et réservations : une vision claire de votre activité de transport.'}
]
const features=[{icon:Truck,title:'Une flotte sous contrôle',text:'Véhicules, documents, disponibilités et échéances réunis dans une même vue.'},
 {icon:Route,title:'Des opérations fluides',text:'Planifiez vos missions, affectez vos chauffeurs et suivez les livraisons.'},
 {icon:Wallet,title:'Des finances lisibles',text:'Factures, règlements et dépenses reliés à vos opérations.'},
 {icon:Wrench,title:'Un atelier organisé',text:'Anticipez les interventions, gérez vos pièces et limitez les immobilisations.'}]
</script>
<template>
 <div class="marketing">
  <nav class="public-nav"><a href="/" class="brand"><span class="brand-mark">T</span>Transit<span>Flow</span></a>
   <button class="icon-btn mobile-only" aria-label="Ouvrir le menu" @click="menu=!menu"><Menu/></button>
   <div class="public-links" :class="{open:menu}"><a href="#solution" @click="menu=false">La solution</a><a href="#metiers" @click="menu=false">Vos métiers</a><a href="#entreprises" @click="menu=false">Votre entreprise</a></div>
   <div class="nav-actions"><button class="text-btn" @click="$emit('login')">Se connecter</button><button class="primary" @click="$emit('register')">Commencer <ArrowUpRight :size="16"/></button></div>
  </nav>
  <main>
   <section class="hero" aria-roledescription="carrousel" aria-label="Les métiers du transport">
    <img :key="slide" :src="slides[slide].image" :alt="slide===0?'Camion de transport routier':'Autobus pour le transport de voyageurs'" class="hero-photo" fetchpriority="high"/>
    <div class="hero-shade"></div><div class="hero-content"><div class="eyebrow light"><span></span> L’ERP DES ENTREPRISES DE TRANSPORT</div>
     <h1>Votre transport.<br>Votre entreprise.<br><em>Une seule plateforme.</em></h1>
     <p>Sur la route comme au bureau, gardez le cap.<br>TransitFlow relie votre flotte, vos opérations et vos finances, partout en Afrique francophone.</p>
     <div class="hero-buttons"><button class="primary bright" @click="$emit('register')">Créer mon espace entreprise <ArrowUpRight :size="19"/></button><a href="#solution" class="hero-link">Découvrir la solution <ArrowRight :size="18"/></a></div>
     <div class="hero-assurance"><ShieldCheck :size="17"/> Un espace privé pour chaque entreprise <span>•</span> Multi-activité</div>
    </div>
    <div class="hero-bottom"><div aria-live="polite"><small>{{slides[slide].label}}</small><p>{{slides[slide].title}}</p></div><div class="carousel-control"><span>0{{slide+1}} <i>/ 02</i></span><button aria-label="Photographie précédente" @click="slide=(slide+1)%2"><ChevronLeft/></button><button aria-label="Photographie suivante" @click="slide=(slide+1)%2"><ChevronRight/></button></div></div>
   </section>
   <div class="sector-strip"><span>PENSÉ POUR VOTRE MÉTIER</span><b>Marchandises</b><i>✦</i><b>Voyageurs</b><i>✦</i><b>Navettes & scolaire</b><i>✦</i><b>Transport spécialisé</b></div>
   <section class="public-section" id="solution"><div class="section-heading"><div><div class="eyebrow">UNE VISION D’ENSEMBLE</div><h2>Moins de dispersion.<br>Plus de maîtrise.</h2></div><p>Vos informations ne devraient pas voyager entre des cahiers, des fichiers et des messages. Rassemblez-les dans un outil conçu pour votre quotidien.</p></div>
    <div class="feature-grid"><article v-for="(f,i) in features" :key="f.title"><span class="feature-icon"><component :is="f.icon" :size="26"/></span><small>0{{i+1}}</small><h3>{{f.title}}</h3><p>{{f.text}}</p><button class="text-btn" @click="$emit('register')">Explorer le module <ArrowUpRight :size="17"/></button></article></div>
   </section>
   <section class="sectors public-section" id="metiers"><div class="eyebrow">UN SOCLE COMMUN, VOS SPÉCIALITÉS</div><h2>Tous les transports.<br>La même exigence.</h2><div class="sector-cards"><article><img src="/images/transport.jpg" alt="Transport routier de marchandises" loading="lazy"/><div><Truck/><h3>Marchandises & spécialisé</h3><p>Fret, carburants, vrac ou frigorifique : commandes, capacités et quantités livrées.</p></div></article><article><img src="/images/voyageurs.jpg" alt="Autobus voyageurs" loading="lazy"/><div><Bus/><h3>Voyageurs & circuits</h3><p>Lignes régulières, navettes d’entreprise et circuits scolaires : départs et réservations.</p></div></article></div></section>
   <section class="organization-section public-section" id="entreprises"><div class="organization-art"><Layers3 :size="65" stroke-width="1"/><div class="org-card"><ShieldCheck/> Votre entreprise <span>Espace privé</span></div><div class="org-line"></div><div class="org-mini"><span>Vos équipes</span><span>Vos données</span><span>Vos activités</span></div></div><div><div class="eyebrow">VOTRE ESPACE. VOS RÈGLES.</div><h2>Indépendants.<br>Même en partageant<br>la même plateforme.</h2><p>À Conakry, Douala, Dakar ou Kinshasa, chaque entreprise dispose de son organisation et de ses accès.</p><ul class="check-list"><li><Check/> Des droits adaptés à chaque membre</li><li><Check/> Une devise et des paramètres propres</li><li><Check/> Plusieurs activités au sein de votre entreprise</li></ul><button class="primary" @click="$emit('register')">Commencer avec mon entreprise <ArrowRight :size="17"/></button></div></section>
   <section class="public-cta"><span class="eyebrow light">LA PROCHAINE ÉTAPE EST ENTRE VOS MAINS</span><h2>Donnez une nouvelle direction<br>à votre gestion.</h2><button class="primary bright" @click="$emit('register')">Créer mon espace <ArrowUpRight :size="18"/></button></section>
  </main><footer class="public-footer"><a href="/" class="brand"><span class="brand-mark">T</span>Transit<span>Flow</span></a><span>L’entreprise de transport, unifiée.</span><a href="#solution">Fonctionnalités</a><button class="text-btn" @click="$emit('login')">Connexion</button><small>© {{new Date().getFullYear()}} TransitFlow</small></footer>
 </div>
</template>

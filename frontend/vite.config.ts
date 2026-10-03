import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import {VitePWA} from 'vite-plugin-pwa'
export default defineConfig({plugins:[vue(),VitePWA({
  strategies:'injectManifest',srcDir:'src',filename:'sw.js',registerType:'prompt',injectRegister:false,
  injectManifest:{globPatterns:['**/*.{js,css,html,png,svg,ico}'],globIgnores:['images/**'],maximumFileSizeToCacheInBytes:2000000},
  manifest:{id:'/app',name:'TransitFlow',short_name:'TransitFlow',description:'Votre flotte, vos équipes et vos opérations.',lang:'fr',start_url:'/app',scope:'/',display:'standalone',orientation:'any',theme_color:'#123c33',background_color:'#f5f8f5',icons:[
    {src:'/icons/icon-192.png',sizes:'192x192',type:'image/png',purpose:'any'},
    {src:'/icons/icon-512.png',sizes:'512x512',type:'image/png',purpose:'any'},
    {src:'/icons/maskable-192.png',sizes:'192x192',type:'image/png',purpose:'maskable'},
    {src:'/icons/maskable-512.png',sizes:'512x512',type:'image/png',purpose:'maskable'}
  ]}
})],build:{assetsDir:'web-assets'},server:{proxy:{'/api':'http://127.0.0.1:8000'}}})

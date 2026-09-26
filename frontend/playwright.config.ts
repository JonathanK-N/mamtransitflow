// Auteur : Jonathan Kakesa (JonathanK-N).
import {defineConfig,devices} from '@playwright/test'
export default defineConfig({
 testDir:'./tests',fullyParallel:false,workers:1,timeout:120000,expect:{timeout:20000},
 use:{baseURL:process.env.TF_TEST_URL||'http://127.0.0.1:8000',trace:'retain-on-failure',screenshot:'only-on-failure'},
 projects:[{name:'chromium',use:{...devices['Desktop Chrome']}}],
 reporter:[['list'],['html',{open:'never'}]]
})

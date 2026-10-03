// Auteur : Jonathan Kakesa (JonathanK-N).
import {defineConfig,devices} from '@playwright/test'
export default defineConfig({
 testDir:'./tests',fullyParallel:false,workers:1,timeout:120000,expect:{timeout:20000},
 use:{baseURL:process.env.TF_TEST_URL||'http://127.0.0.1:8000',trace:'retain-on-failure',screenshot:'only-on-failure'},
 projects:[{name:'chromium',use:{...devices['Desktop Chrome']}},
  {name:'android',testMatch:/responsive\.spec\.ts/,use:{...devices['Pixel 7']}},
  {name:'iphone',testMatch:/responsive\.spec\.ts/,use:{...devices['iPhone 13']}},
  {name:'ipad',testMatch:/responsive\.spec\.ts/,use:{...devices['iPad (gen 7)']}},
  {name:'small',testMatch:/responsive\.spec\.ts/,use:{...devices['Desktop Chrome'],viewport:{width:320,height:740}}}],
 reporter:[['list'],['html',{open:'never'}]]
})

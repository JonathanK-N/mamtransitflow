import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
test('Static service publishes only schema assets', async () => {
  const child = spawn(process.execPath, ['server.mjs'], { cwd: new URL('.', import.meta.url), env: { ...process.env, PORT: '18769' }, stdio: 'ignore' });
  const base = 'http://127.0.0.1:18769';
  try {
    let ready = false;
    for (let i = 0; i < 50; i++) { try { ready = (await fetch(base+'/health')).ok; } catch {} if (ready) break; await new Promise(r=>setTimeout(r,100)); }
    assert(ready);
    const html = await fetch(base); assert.equal(html.status,200); assert.match(await html.text(),/TransitFlow ERP/);
    assert.equal(html.headers.get('x-content-type-options'),'nosniff');
    const schema = await (await fetch(base+'/schema.json')).json(); assert.equal(schema.tables.length,71); assert.equal(schema.relations.length,120);
    for (const p of ['/index.html','/MRL_TransitFlow.md','/TransitFlow.dbml','/robots.txt']) assert.equal((await fetch(base+p)).status,200);
    for (const p of ['/.git/config','/server.mjs','/README.md','/missing','/public/../server.mjs']) assert.equal((await fetch(base+p)).status,404);
    assert.equal((await fetch(base,{method:'POST'})).status,405);
    assert.equal(await (await fetch(base,{method:'HEAD'})).text(),'');
  } finally { child.kill(); }
});

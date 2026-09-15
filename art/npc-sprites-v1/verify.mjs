import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
const here = path.dirname(fileURLToPath(import.meta.url)), game = path.resolve(here, '../../game');
const require = createRequire(path.join(game, 'package.json'));
const { chromium } = require('playwright-core');
const { createServer } = await import(pathToFileURL(path.join(game, 'node_modules/vite/dist/node/index.js')).href);
const original = (await fs.readFile(path.join(here, '../town-v2/preview-run.jsonl'), 'utf8')).trim().split('\n').map(JSON.parse);
const meta = structuredClone(original.find(x => x.kind === 'run_meta'));
meta.preview = true;
const level = structuredClone(original.find(x => x.kind === 'level'));
const added = [['떠돌이 모험자', 21, 17], ['견습 모험자', 24, 16], ['노점 상인', 27, 17]].map(([name,x,y], i) => ({id:100+i,type:'npc',name,x,y,concealed:false}));
level.features.push(...added, { id: 103, type: 'npc', name: '미등록 행인', x: 30, y: 17, concealed: false });
const lines = [meta, level];
let features = structuredClone(level.features);
for (let turn = 1; turn <= 7; turn++) {
  const [dx,dy] = [[1,0],[0,-1],[-1,0],[0,1],[0,0],[0,0],[0,0]][turn-1];
  features = features.map(f => f.id >=100 && f.id <=102 ? {...f,x:f.x+dx,y:f.y+dy,concealed:turn===6} : f);
  lines.push({kind:'tick',turn,decisions:{},events:[],bots:level.party,features:structuredClone(features),monsters:[],traps:[]});
}
// Visual-only fixture: controlled positions, no LLM decisions or new game outcome.
await fs.writeFile(path.join(here, 'preview-run.jsonl'), lines.map(x => JSON.stringify(x)).join('\n')+'\n');
const server=await createServer({root:game,configFile:path.join(game,'vite.config.ts'),server:{port:4217,strictPort:true,hmr:false,host:'127.0.0.1'}});
await server.listen();
let browser;
const errors=[], checks=[];
try {
  browser=await chromium.launch({headless:true,...(process.platform==='win32'?{channel:'msedge'}:{})});
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:4217/art/npc-sprites-v1/preview.html');
  await page.waitForFunction(()=>document.querySelectorAll('canvas').length===12 && Array.from(document.images).every(i=>i.complete));
  await page.waitForTimeout(300);
  await page.click('#idle');
  await page.screenshot({path:path.join(here,'preview.png'),fullPage:true});
  await page.click('#step');assert.match(await page.locator('#status').textContent(),/걷기/);
  await page.setViewportSize({width:390,height:844});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'mobile overflow');
  checks.push('Gallery loads 12 views; idle and frame controls; mobile width.');
  await page.setViewportSize({width:1600,height:1000});
  await page.goto('http://127.0.0.1:4217/game/?run=art/npc-sprites-v1/preview-run.jsonl&focus=1&t=0');
  await page.waitForFunction(()=>window.__wl?.scene?.frame?.turn===0,null,{timeout:60000});
  const sample=()=>page.evaluate(()=>{
    const a=window.__wl,scene=a.scene;
    return [100,101,102].map(id=>{const s=scene.children.getByName('npc-'+id);return s?{id,key:s.texture.key,frame:s.frame.name,dir:s.getData('dir'),playing:s.anims.isPlaying,x:s.x,y:s.y,depth:s.depth,tweens:scene.tweens.getTweensOf(s).length}:null});
  });
  const keys=['wl-npc-wanderer','wl-npc-apprentice','wl-npc-vendor'];
  assert.deepEqual((await sample()).map(s=>s.key),keys);
  const textureFrames=await page.evaluate(keys=>keys.map(k=>window.__wl.game.textures.get(k).frameTotal),keys);
  assert.deepEqual(textureFrames,[13,13,13]); // 12 + __BASE
  checks.push('All three bundled textures load with 12 frames and correct identities.');
  for(const [i,dir] of ['right','back','left','front'].entries()){
    await page.evaluate(()=>window.__wl.playback.step(1));
    const moving=await sample();assert(moving.every(s=>s.dir===dir && s.playing),'walk '+dir);
    await page.waitForFunction(()=>[100,101,102].every(id=>{const scene=window.__wl.scene,s=scene.children.getByName('npc-'+id);return s && !s.anims.isPlaying && scene.tweens.getTweensOf(s).length===0;}),null,{timeout:5000});
    const stopped=await sample();assert(stopped.every(s=>!s.playing && s.tweens===0),'stop '+dir);
    const position=await page.evaluate(()=>{const a=window.__wl;return a.playback.cur.features.filter(f=>f.id>=100&&f.id<=102).map(f=>({...a.scene.worldOf(f.x,f.y),depth:20+f.y*.01-.005}));});
    stopped.forEach((s,j)=>{assert.equal(s.x,position[j].x);assert.equal(s.y,position[j].y);assert.equal(s.depth,position[j].depth);assert.equal(Number(s.frame),['front','right','back','left'].indexOf(dir)*3);});
  }
  checks.push('Four walking directions, idle on arrival, exact destination and depth.');
  await page.evaluate(()=>window.__wl.playback.setIdx(2,'seek'));
  assert((await sample()).every(s=>s.dir==='front' && !s.playing && s.tweens===0),'seek resets');
  await page.evaluate(()=>{const p=window.__wl.playback;p.setSpeed(2);p.step(1);});
  await page.waitForFunction(()=>[100,101,102].every(id=>{const scene=window.__wl.scene,s=scene.children.getByName('npc-'+id);return s && !s.anims.isPlaying && scene.tweens.getTweensOf(s).length===0;}),null,{timeout:5000});
  assert((await sample()).every(s=>!s.playing && s.tweens===0),'16x arrival');
  await page.evaluate(()=>window.__wl.playback.setIdx(6,'seek'));assert((await sample()).every(s=>s===null),'concealed hidden');
  await page.evaluate(()=>window.__wl.playback.step(1));assert.deepEqual((await sample()).map(s=>s.key),keys);
  checks.push('Seeking, 16x playback, concealment and reappearance retain correct art.');
  const fixed=await page.evaluate(()=>{const scene=window.__wl.scene;return {fixed:[...scene.feats.values()].filter(s=>s.texture.key==='wl-town-npcs').length,fallback:scene.feats.get('npc#103')?.texture.key,head:scene.npcHeadOf('노점 상인')};});
  assert.equal(fixed.fixed,3);assert.equal(fixed.fallback,'tiny');assert(fixed.head);
  checks.push('Existing fixed NPCs, unknown NPC fallback, dialogue anchor unchanged.');
  await page.evaluate(()=>{const a=window.__wl;a.playback.setIdx(0,'seek');const c=a.scene.cameras.main;c.stopFollow();a.scene.setZoom(2);const p=a.scene.worldOf(24,17);c.centerOn(p.x,p.y);});
  await page.waitForTimeout(350);
  await page.screenshot({path:path.join(here,'in-game.png')});
  assert.deepEqual(errors,[]);
  await fs.writeFile(path.join(here,'verification.json'),JSON.stringify({passed:true,llmCalls:0,fixture:'controlled visual preview based on town-v2',checks,errors},null,2)+'\n');
  console.log('PASS',checks);
} finally { if(browser)await browser.close();await server.close(); }

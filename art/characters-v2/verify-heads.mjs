import fs from 'node:fs/promises';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
import {chromium} from '../../game/node_modules/playwright-core/index.mjs';
import {createServer} from '../../game/node_modules/vite/dist/node/index.js';
import {fileURLToPath} from 'node:url';
const here=new URL('./',import.meta.url),root=new URL('../../',here),game=new URL('game/',root);
const manifest=JSON.parse(await fs.readFile(new URL('manifest.json',here),'utf8'));
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
for(const b of Object.values(manifest.bodies))assert.equal(hash(await fs.readFile(new URL(b.sheet,here))),hash(await fs.readFile(new URL('head-review/before/'+b.sheet,here))),'Existing body bytes changed');
const server=await createServer({root:fileURLToPath(game),configFile:fileURLToPath(new URL('vite.config.ts',game)),server:{port:4233,strictPort:true,hmr:false,host:'127.0.0.1'}});await server.listen();
const browser=await chromium.launch({channel:'msedge',headless:true});
try{
 const page=await browser.newPage({viewport:{width:1120,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:4233/art/characters-v2/head-review/index.html');await page.evaluate(()=>window.reviewReady);
 await page.locator('#walk').uncheck();
 for(const dir of ['front','right','back','left']){await page.locator('#dir').selectOption(dir);await page.waitForTimeout(40);await page.screenshot({path:fileURLToPath(new URL(`head-review/${dir}.png`,here)),fullPage:true});}
 await page.locator('#dir').selectOption('right');await page.locator('#head').selectOption('braid');await page.waitForTimeout(40);await page.screenshot({path:fileURLToPath(new URL('head-review/braid.png',here)),fullPage:true});
 const motion=await page.evaluate(async()=>{
  const{current,drawCharacter}=await window.reviewReady;let sequences=0;const c=document.createElement('canvas');c.width=c.height=96;const g=c.getContext('2d');
  for(const b of Object.keys(current.manifest.bodies))for(const h of Object.keys(current.manifest.heads))for(const dir of current.manifest.directions){
   const frames=[];for(let col=1;col<5;col++){g.clearRect(0,0,96,96);drawCharacter(g,current,b,h,dir,col,{layer:'head'});frames.push(c.toDataURL());}
   if(new Set(frames).size<2)throw Error('Frozen walking head '+[b,h,dir]);sequences++;
  }return{movingHeadSequences:sequences};
 });assert.equal(motion.movingHeadSequences,448);
 await page.goto('http://127.0.0.1:4233/game/?run=art/characters-v2/preview-run.jsonl&focus=6&t=1');await page.waitForFunction(()=>window.__wl?.playback.cur?.turn===1);
 const actual=await page.evaluate(async()=>{
  const{loadAssets,drawCharacter}=await import('/art/character-bases-v1/modular-pilot/compose.js'),assets=await loadAssets(new URL('/art/characters-v2/',location.href));
  const c=document.createElement('canvas'),a=document.createElement('canvas');c.width=c.height=a.width=a.height=96;const g=c.getContext('2d',{willReadFrequently:true}),ag=a.getContext('2d',{willReadFrequently:true});let frames=0;
  for(const b of Object.keys(assets.manifest.bodies))for(const h of Object.keys(assets.manifest.heads)){
   const src=window.__wl.game.textures.get(`sd|sd-${b}|${h}`).getSourceImage();
   for(let row=0;row<4;row++)for(let col=0;col<5;col++){g.clearRect(0,0,96,96);ag.clearRect(0,0,96,96);drawCharacter(g,assets,b,h,assets.manifest.directions[row],col);ag.drawImage(src,col*96,row*96,96,96,0,0,96,96);const p=g.getImageData(0,0,96,96).data,q=ag.getImageData(0,0,96,96).data;if(!p.every((v,i)=>v===q[i]))throw Error('Runtime mismatch '+[b,h,row,col]);frames++;}
  }return{matchingGameFrames:frames};
 });assert.equal(actual.matchingGameFrames,2240);assert.deepEqual(errors,[]);
 const report={passed:true,unchangedBodySheets:8,...motion,...actual,errors};await fs.writeFile(new URL('head-review/verification.json',here),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
}finally{await browser.close();await server.close();}

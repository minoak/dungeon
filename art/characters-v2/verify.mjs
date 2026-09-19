import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {chromium} from '../../game/node_modules/playwright-core/index.mjs';
import {createServer} from '../../game/node_modules/vite/dist/node/index.js';
const here=path.dirname(fileURLToPath(import.meta.url)),root=path.resolve(here,'../..');
const catalog=JSON.parse(await fs.readFile(path.join(here,'catalog.json'),'utf8')),ids=Object.keys(catalog.bodies).map(id=>'sd-'+id);
const server=await createServer({root:path.join(root,'game'),configFile:path.join(root,'game/vite.config.ts'),server:{port:4232,strictPort:true,hmr:false,host:'127.0.0.1'}});
await server.listen();const browser=await chromium.launch({channel:'msedge',headless:true});let launcher;
try{
 const page=await browser.newPage({viewport:{width:1180,height:1080}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:4232/art/characters-v2/index.html');await page.evaluate(()=>window.wardrobeReady);
 await page.locator('#walking').uncheck();assert.equal(await page.locator('.card').count(),8);
 const first=page.locator('[data-head]').first();await first.selectOption('wavy-twintails');
 await page.locator('[data-body]').first().selectOption('mage-female');assert.equal(await first.inputValue(),'wavy-twintails');
 await page.locator('[data-body]').first().selectOption('warrior-male');await first.selectOption('tousled');
 const bodyChecks=await page.evaluate(async()=>{
  const {assets,drawCharacter}=await window.wardrobeReady;let checks=0;
  for(const body of Object.keys(assets.manifest.bodies))for(const dir of assets.manifest.directions)for(let col=0;col<5;col++){
   let reference;
   for(const head of Object.keys(assets.manifest.heads)){
    const c=document.createElement('canvas');c.width=c.height=96;const g=c.getContext('2d');drawCharacter(g,assets,body,head,dir,col,{layer:'body'});
    const pixels=g.getImageData(0,0,96,96).data;if(reference&&pixels.some((v,i)=>v!==reference[i]))throw Error('Hair changed body pixels');reference=pixels;
   }checks++;
  }return checks;
 });assert.equal(bodyChecks,160);
 for(const dir of ['front','right','back','left']){await page.locator(`[data-dir="${dir}"]`).click();await page.screenshot({path:path.join(here,`preview-${dir}.png`),fullPage:true});}
 await page.locator('[data-dir="front"]').click();await page.locator('#allHair').selectOption('wavy-twintails');await page.screenshot({path:path.join(here,'preview-shared-hair.png'),fullPage:true});
 await page.locator('#walking').check();const before=await page.locator('canvas').first().evaluate(c=>c.toDataURL());await page.waitForTimeout(180);assert.notEqual(await page.locator('canvas').first().evaluate(c=>c.toDataURL()),before);
 await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:path.join(here,'preview-mobile.png'),fullPage:true});
 // Check all production combinations in the actual Phaser texture manager.
 const game=await browser.newPage({viewport:{width:1500,height:980}});game.on('pageerror',e=>errors.push(e.message));
 await game.goto('http://127.0.0.1:4232/game/?run=art/characters-v2/preview-run.jsonl&focus=1&t=1');await game.waitForFunction(()=>window.__wl?.playback.cur?.turn===1);
 const runtime=await game.evaluate(({ids,hairs})=>{
  const a=window.__wl;let frames=0;
  for(const id of ids)for(const hair of hairs){const key=`sd|${id}|${hair}`,texture=a.game.textures.get(key);
   if(texture.key!==key||texture.source[0].scaleMode!==1)throw Error('Missing/pixel filter '+key);
   for(let i=0;i<20;i++){if(!texture.has(i))throw Error('Frame missing '+key);frames++;}
   for(const dir of ['front','right','back','left'])if(!a.game.anims.exists(key+'|walk|'+dir))throw Error('Animation missing');
  }
  const actors=ids.map((id,i)=>{const actor=a.scene.actorOf(String(i+1));if(!actor||!actor.key.includes(id))throw Error('Actor mismatch '+id);return{key:actor.key,height:actor.sprite.displayHeight,origin:actor.sprite.originY};});
  return{frames,actors};
 },{ids,hairs:Object.keys(catalog.heads)});assert.equal(runtime.frames,2240);assert(runtime.actors.every(a=>Math.abs(a.height-192)<.001));
 // Finish the initial focus pan before framing the group for size comparison.
 await game.waitForTimeout(400);
 for(const [name,zoom]of [['town-normal',.5],['town-close',1]]){await game.evaluate(z=>{const a=window.__wl,c=a.scene.cameras.main;c.panEffect.reset();c.stopFollow();a.scene.setZoom(z);const actors=Array.from({length:8},(_,i)=>a.scene.actorOf(String(i+1)).sprite);c.centerOn(actors.reduce((n,s)=>n+s.x,0)/8,actors.reduce((n,s)=>n+s.y,0)/8-60);},zoom);await game.waitForTimeout(120);await game.screenshot({path:path.join(here,name+'.png')});}
 await game.evaluate(()=>window.__wl.loadRun('runs/stream-20260909-203709.jsonl',{focus:'1',turn:5}));await game.waitForFunction(()=>window.__wl.playback.cur?.turn===5);
 assert.equal(await game.evaluate(()=>window.__wl.scene.actorOf('1').sprite.width),96);
 launcher=spawn('python',['art/sprites-v4/serve-preview.py','--port','8769'],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe']});
 await new Promise((resolve,reject)=>{const t=setTimeout(()=>reject(Error('Launcher startup timeout')),15000);launcher.once('error',reject);launcher.stdout.on('data',b=>{if(String(b).includes('http://')){clearTimeout(t);resolve();}});});
 const form=await browser.newPage({viewport:{width:1280,height:1000}});form.on('pageerror',e=>errors.push(e.message));await form.goto('http://127.0.0.1:8769/launcher/');await form.locator('#bNew').click();await form.waitForSelector('[data-art]');
 assert.deepEqual(await form.evaluate(()=>WLSprites.illustrations().map(p=>p.id).sort()),[...ids].sort());
 const card=form.locator('#cards [data-i="0"]'),body=card.locator('[data-art]'),hair=card.locator('[data-hairstyle]');
 await body.selectOption(ids[0]);await hair.selectOption('blunt-long');
 for(const id of ids){await body.selectOption(id);assert.equal(await hair.inputValue(),'blunt-long');assert.equal(await hair.locator('option').count(),14);assert.equal(await card.locator('.lookPrev').getAttribute('width'),'96');}
 // Default is an alias of a real shared style, not an extra selectable hairstyle.
 assert.equal(await form.evaluate(()=>WLSprites.defaultHair({sprite:'sd-mage-female'})),'wavy-twintails');
 await hair.selectOption('wavy-twintails');await card.locator('[data-k=name]').fill('공용 헤어 검토');await card.locator('[data-k=persona]').fill('주변을 신중하게 살피는 모험가.');
 const saved=form.waitForResponse(r=>r.url().endsWith('/api/characters')&&r.request().method()==='POST');await card.locator('[data-preset-save]').click();const response=await saved;assert.equal(response.status(),200);const preset=(await response.json()).preset;
 assert.equal(preset.slot.look.sprite,'sd-mage-female');assert.equal(preset.slot.look.hairstyle,'wavy-twintails');assert.equal(preset.slot.job,'전사');assert.equal(preset.slot.sex,'남');
 await body.selectOption('sd-archer-male');await hair.selectOption('tousled');await card.locator('[data-preset-load]').click();assert.equal(await form.locator('[data-art]').first().inputValue(),'sd-mage-female');assert.equal(await form.locator('[data-hairstyle]').first().inputValue(),'wavy-twintails');
 await form.screenshot({path:path.join(here,'launcher-preview.png'),fullPage:true});
 const legacy=await form.evaluate(()=>({old:WLSprites.cell({sprite:'sd-warrior',hairstyle:'long'},'front',-1)?.width,hd:WLSprites.cell({sprite:'sd-warrior-illustration'},'front',-1)?.width,selectedOld:WLSprites.illustrations({sprite:'sd-warrior'}).some(p=>p.id==='sd-warrior')}));assert.deepEqual(legacy,{old:96,hd:256,selectedOld:true});
 assert.deepEqual(errors,[]);
 const report={passed:true,bodies:8,hairs:14,combinations:112,frames:runtime.frames,unchangedBodyFrames:bodyChecks,launcherPreservesHair:true,launcherSaveLoad:true,appearanceDoesNotChangeJobOrSex:true,oldReplay:true,legacy,walking:true,mobileOverflow:false,llmCalls:0,errors};
 await fs.writeFile(path.join(here,'verification.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
}finally{if(launcher)launcher.kill();await browser.close();await server.close();}

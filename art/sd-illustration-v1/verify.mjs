import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {chromium} from '../../game/node_modules/playwright-core/index.mjs';
import {createServer} from '../../game/node_modules/vite/dist/node/index.js';
const here=path.dirname(fileURLToPath(import.meta.url)),root=path.resolve(here,'../..');
const server=await createServer({root:path.join(root,'game'),configFile:path.join(root,'game/vite.config.ts'),server:{port:4231,strictPort:true,hmr:false,host:'127.0.0.1'}});
await server.listen();
const browser=await chromium.launch({channel:'msedge',headless:true});
let launcher;
try{
 const page=await browser.newPage({viewport:{width:1500,height:980}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:4231/game/?run=art/sd-illustration-v1/preview-run.jsonl&focus=1&t=1');
 await page.waitForFunction(()=>window.__wl?.playback.cur?.turn===1);
 const metrics=await page.evaluate(()=>{
  const a=window.__wl,hd=a.scene.actorOf('1'),old=a.scene.actorOf('2');
  return {hd:{width:hd.sprite.width,height:hd.sprite.displayHeight,filter:hd.sprite.texture.source[0].scaleMode,origin:hd.sprite.originY,labelScale:hd.label.scaleY},
    old:{width:old.sprite.width,height:old.sprite.displayHeight,filter:old.sprite.texture.source[0].scaleMode,labelScale:old.label.scaleY},
    headDistance:hd.sprite.y-a.scene.headOf('1').y,portrait:a.scene.portrait('1').style.imageRendering,
    texture:hd.key};
 });
 assert.equal(metrics.hd.width,256);assert.equal(metrics.old.width,96);
 assert(Math.abs(metrics.hd.height-metrics.old.height)<0.001);assert.equal(metrics.hd.filter,0);assert.equal(metrics.old.filter,1);
 assert.equal(metrics.hd.labelScale,metrics.old.labelScale);assert.equal(metrics.portrait,'auto');assert(metrics.headDistance>120&&metrics.headDistance<145);
 // Check the packed source, including retained antialiased edges.
 const asset=await page.evaluate(()=>{
   const im=window.__wl.game.textures.get('sd|sd-warrior-illustration|default').getSourceImage();
   const c=document.createElement('canvas');c.width=im.width;c.height=im.height;const g=c.getContext('2d');g.drawImage(im,0,0);
   let partial=0;const bounds=[];
   for(let row=0;row<4;row++)for(let col=0;col<5;col++){
    const d=g.getImageData(col*256,row*256,256,256).data;let x0=256,x1=0,y0=256,y1=0,count=0;
    for(let y=0;y<256;y++)for(let x=0;x<256;x++){const a=d[(y*256+x)*4+3];if(a>0&&a<255)partial++;if(a>32){count++;x0=Math.min(x0,x);x1=Math.max(x1,x);y0=Math.min(y0,y);y1=Math.max(y1,y);}}
    if(count<5000||x0<2||x1>253||y0<2||y1>244||y1<240)throw Error('HD frame clipped/empty/misaligned '+JSON.stringify({row,col,x0,x1,y0,y1,count}));
    bounds.push([x0,y0,x1,y1]);
   }
   return {frames:bounds.length,partialAlphaPixels:partial,bounds};
 });assert(asset.partialAlphaPixels>1000);
 for(const [name,zoom]of [['town-normal',0.5],['town-close',1]]){
   await page.evaluate(z=>{const a=window.__wl,c=a.scene.cameras.main,s=a.scene.actorOf('1').sprite;c.stopFollow();a.scene.setZoom(z);c.centerOn(s.x-90,s.y-50);},zoom);
   await page.waitForTimeout(100);await page.screenshot({path:path.join(here,name+'.png')});
 }
 for(const dir of ['front','right','back','left']){
   await page.evaluate(dir=>{const a=window.__wl.scene.actorOf('1');a.sprite.play(a.key+'|walk|'+dir);},dir);
   await page.waitForTimeout(180);assert(await page.evaluate(()=>window.__wl.scene.actorOf('1').sprite.anims.isPlaying));
 }
 await page.evaluate(()=>window.__wl.loadRun('runs/stream-20260909-203709.jsonl',{focus:'1',turn:5}));
 await page.waitForFunction(()=>window.__wl.playback.cur?.turn===5);
 assert.equal(await page.evaluate(()=>window.__wl.scene.actorOf('1').sprite.width),96);
 // Real launcher UI on disposable storage: select and save the new appearance.
 launcher=spawn('python',['art/sprites-v4/serve-preview.py','--port','8768'],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe']});
 await new Promise((resolve,reject)=>{const t=setTimeout(()=>reject(Error('Preview launcher startup timeout')),15000);launcher.once('error',reject);launcher.stdout.on('data',b=>{if(String(b).includes('http://')){clearTimeout(t);resolve();}});});
 const form=await browser.newPage({viewport:{width:1280,height:1000}});form.on('pageerror',e=>errors.push(e.message));
 await form.goto('http://127.0.0.1:8768/launcher/');await form.locator('#bNew').click();await form.waitForSelector('[data-art]');
 await form.locator('[data-art]').first().selectOption('sd-warrior-illustration');
 assert.equal(await form.locator('.lookPrev').first().getAttribute('width'),'256');
 assert.equal(await form.locator('.lookPrev').first().evaluate(e=>getComputedStyle(e).imageRendering),'auto');
 assert.equal(await form.evaluate(()=>WLSprites.cell({sprite:'sd-warrior-illustration'},'back',2).width),256);
 assert.equal(await form.evaluate(()=>WLSprites.cell({sprite:'sd-warrior'},'front',-1).width),96);
 await form.screenshot({path:path.join(here,'launcher-preview.png'),fullPage:true});
 const card=form.locator('#cards [data-i="0"]');
 await card.locator('[data-k=name]').fill('SD 검토');
 await card.locator('[data-k=persona]').fill('신중하게 주변을 살피는 모험가.');
 const saved=form.waitForResponse(r=>r.url().endsWith('/api/characters')&&r.request().method()==='POST');
 await card.locator('[data-preset-save]').click();const response=await saved;assert.equal(response.status(),200);
 assert.equal((await response.json()).preset.slot.look.sprite,'sd-warrior-illustration');
 await card.locator('[data-art]').selectOption('sd-warrior');
 await card.locator('[data-preset-load]').click();
 assert.equal(await form.locator('[data-art]').first().inputValue(),'sd-warrior-illustration');
 assert.deepEqual(errors,[]);
 const report={passed:true,metrics,asset,oldReplay:true,walkingDirections:4,launcherPreview:true,launcherSave:true,llmCalls:0,errors};
 await fs.writeFile(path.join(here,'verification.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({passed:true,frames:asset.frames,matchedDisplaySize:true,oldReplay:true,launcherPreview:true,errors}));
}finally{if(launcher)launcher.kill();await browser.close();await server.close();}

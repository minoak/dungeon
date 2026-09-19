import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
import {chromium} from '../../../game/node_modules/playwright-core/index.mjs';
const here=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(here,'../../..');
const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript','.mjs':'text/javascript','.json':'application/json','.png':'image/png'};
const server=http.createServer(async(req,res)=>{
 try{let rel=decodeURIComponent(new URL(req.url,'http://localhost').pathname);if(rel.endsWith('/'))rel+='index.html';
  const file=path.resolve(root,'.'+rel);if(!file.startsWith(root+path.sep)){res.writeHead(403).end();return;}
  const bytes=await fs.readFile(file);res.writeHead(200,{'Content-Type':mime[path.extname(file)]||'application/octet-stream'}).end(bytes);
 }catch{res.writeHead(404).end();}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const base=process.env.WL_PILOT_URL||`http://127.0.0.1:${server.address().port}/art/character-bases-v1/modular-pilot/`;
let browser;
try{
 browser=await chromium.launch({channel:'msedge',headless:true});
 const page=await browser.newPage({viewport:{width:1120,height:890},deviceScaleFactor:1});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.goto(base);await page.evaluate(()=>window.pilotReady);
 await page.locator('#walking').uncheck();
 const report=await page.evaluate(async()=>{
   const {assets,drawCharacter}=await window.pilotReady;const {manifest}=assets;
   let frames=0;const sheets={},bodyChecks=[];
   const make=()=>{const c=document.createElement('canvas');c.width=c.height=96;return c;};
   const pixels=c=>c.getContext('2d').getImageData(0,0,96,96).data;
   for(const b of Object.keys(manifest.bodies)){
     for(const dir of manifest.directions)for(let col=0;col<5;col++){
       const layers=Object.keys(manifest.heads).map(h=>{const c=make();drawCharacter(c.getContext('2d'),assets,b,h,dir,col,{layer:'body'});return pixels(c);});
       if(layers[0].some((v,i)=>v!==layers[1][i]))throw Error('Hair choice altered body layer');
       bodyChecks.push([b,dir,col]);
     }
     for(const h of Object.keys(manifest.heads)){
       const sheet=document.createElement('canvas');sheet.width=480;sheet.height=384;const sg=sheet.getContext('2d');
       for(let row=0;row<4;row++)for(let col=0;col<5;col++){
         const c=make();drawCharacter(c.getContext('2d'),assets,b,h,manifest.directions[row],col);const d=pixels(c);
         let count=0,minX=96,maxX=-1,minY=96,maxY=-1;
         for(let y=0;y<96;y++)for(let x=0;x<96;x++){const a=d[(y*96+x)*4+3];if(a!==0&&a!==255)throw Error('Non-binary alpha');if(a){count++;minX=Math.min(minX,x);maxX=Math.max(maxX,x);minY=Math.min(minY,y);maxY=Math.max(maxY,y);}}
         if(count<500||minX<1||maxX>94||minY<1||maxY!==91)throw Error('Bounds or foot anchor '+JSON.stringify({b,h,row,col,count,minX,maxX,minY,maxY}));
         sg.drawImage(c,col*96,row*96);frames++;
       }
       sheets[b+'--'+h]=sheet.toDataURL('image/png').split(',')[1];
     }
   }
   return {frames,bodyChecks:bodyChecks.length,sheets};
 });
 assert.equal(report.frames,80);assert.equal(report.bodyChecks,40);
 // User interaction must retain the selected body and expose all hair on both bodies.
 const body=page.locator('[data-body]').first(),head=page.locator('[data-head]').first();
 const selected=await body.inputValue();await head.selectOption('long-head');assert.equal(await body.inputValue(),selected);
 await body.selectOption('archer-body');assert.equal(await head.inputValue(),'long-head');
 await body.selectOption(selected);await head.selectOption('short-head');
 for(const dir of ['front','right','back','left']){
   await page.locator(`[data-dir="${dir}"]`).click();
   await page.screenshot({path:path.join(here,`preview-${dir}.png`),fullPage:true});
 }
 await page.locator('#walking').check();
 const before=await page.locator('canvas').first().evaluate(c=>c.toDataURL());
 await page.waitForTimeout(180);
 const after=await page.locator('canvas').first().evaluate(c=>c.toDataURL());assert.notEqual(before,after,'Walking did not change image');
 await page.setViewportSize({width:390,height:844});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,'Mobile overflow');
 await page.screenshot({path:path.join(here,'preview-mobile.png'),fullPage:true});
 assert.deepEqual(errors,[]);
 for(const [id,png]of Object.entries(report.sheets))await fs.writeFile(path.join(here,'runtime',id+'.png'),Buffer.from(png,'base64'));
 const summary={frames:report.frames,unchangedBodyFrames:report.bodyChecks,directions:4,combinations:4,uiPreservesSelections:true,walkingChangesFrames:true,mobileOverflow:false,browserErrors:errors};
 await fs.writeFile(path.join(here,'verification.json'),JSON.stringify(summary,null,2)+'\n');console.log(JSON.stringify(summary));
}finally{if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));}

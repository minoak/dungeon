import fs from 'node:fs/promises';
import path from 'node:path';
import {createServer} from 'node:http';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
const here=path.dirname(fileURLToPath(import.meta.url)),root=path.resolve(here,'../..');
const require=createRequire(path.join(root,'game/package.json'));
const {chromium}=require('playwright-core');
const mime={'.html':'text/html; charset=utf-8','.json':'application/json; charset=utf-8','.png':'image/png'};
const server=createServer(async(req,res)=>{try{const p=path.resolve(root,'.'+decodeURIComponent(new URL(req.url,'http://x').pathname));if(!p.startsWith(root+path.sep))throw Error();const bytes=await fs.readFile(p);res.writeHead(200,{'Content-Type':mime[path.extname(p)]||'text/plain'});res.end(bytes)}catch{res.writeHead(404);res.end()}});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
try{
 const page=await browser.newPage({viewport:{width:1500,height:1250},deviceScaleFactor:1});const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto(`http://127.0.0.1:${server.address().port}/art/town-v2/preview.html`);
 await page.waitForFunction(()=>window.__townMap?.ready);
 const saveCanvas=async(name)=>{const raw=await page.locator('canvas').evaluate(c=>c.toDataURL().split(',')[1]);await fs.writeFile(path.join(here,name),Buffer.from(raw,'base64'))};
 await saveCanvas('map-overview.png');
 await page.screenshot({path:path.join(here,'preview-desktop.png'),fullPage:true});
 for(const option of ['temple_1','guild_1','tavern_1','gate_1','entry']){
  await page.locator('#route').selectOption(option);
  assert.match(await page.locator('#status').innerText(),/까지 \d+칸/);
 }
 await page.locator('#route').selectOption('');await page.locator('#collision').check();await page.locator('#grid').check();
 await saveCanvas('map-collision.png');
 await page.locator('#collision').uncheck();await page.locator('#grid').uncheck();await page.locator('#regions').check();
 await saveCanvas('map-regions.png');
 await page.setViewportSize({width:768,height:1000});
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 assert.deepEqual(errors,[]);
 console.log('PASS — 전체 지도·구역·충돌·목적지 5곳 경로·모바일 넘침·브라우저 오류');
}finally{await browser.close();await new Promise(r=>server.close(r))}

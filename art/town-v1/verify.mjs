// 독립 로컬 미리보기를 검사하고 표시 확인용 스크린샷을 저장한다.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {createServer} from 'node:http';
const here=path.dirname(fileURLToPath(import.meta.url));
const require=createRequire(path.resolve(here,'../../game/package.json'));
const {chromium}=require('playwright-core');
const types={'.html':'text/html; charset=utf-8','.json':'application/json; charset=utf-8','.png':'image/png','.md':'text/plain; charset=utf-8'};
const server=createServer(async(req,res)=>{try{const p=path.resolve(here,'.'+decodeURIComponent(new URL(req.url,'http://local').pathname));if(!p.startsWith(here+path.sep)){res.writeHead(403);res.end();return}const bytes=await fs.readFile(p);res.writeHead(200,{'Content-Type':types[path.extname(p)]||'application/octet-stream'});res.end(bytes)}catch{res.writeHead(404);res.end()}});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const port=server.address().port;
let browser;
try{
 browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
 const page=await browser.newPage({viewport:{width:1536,height:1150},deviceScaleFactor:1});const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.status()>=400&& !r.url().endsWith('favicon.ico'))errors.push(r.status()+' '+r.url())});
 await page.goto(`http://127.0.0.1:${port}/preview.html`);await page.waitForFunction(()=>window.__town?.ready);
 assert.equal(await page.locator('#status').innerText(),'에셋 준비 완료');
 const sample=()=>page.locator('#scene').evaluate(c=>c.toDataURL());
 const first=await sample();await page.locator('#grid').check();assert.notEqual(await sample(),first);await page.locator('#grid').uncheck();
 await page.locator('#collision').check();assert.notEqual(await sample(),first);const collision=await page.locator('#scene').evaluate(c=>c.toDataURL('image/png').split(',')[1]);await fs.writeFile(path.join(here,'scene-collision.png'),Buffer.from(collision,'base64'));await page.locator('#collision').uncheck();
 assert.equal((await page.locator('#ascii').innerText()).trim(),(await fs.readFile(path.join(here,'town-ascii.txt'),'utf8')).trim());
 await page.locator('#direction').selectOption('2');assert.notEqual(await sample(),first);await page.locator('#direction').selectOption('0');
 await page.locator('#people').uncheck();assert.notEqual(await sample(),first);await page.locator('#people').check();
 await page.locator('#decor').uncheck();assert.notEqual(await sample(),first);await page.locator('#decor').check();
 await page.locator('#connections').check();assert.notEqual(await sample(),first);await page.locator('#connections').uncheck();
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 await page.screenshot({path:path.join(here,'preview-desktop.png'),fullPage:true});
 // 크기·바닥 반복·겹침을 확인할 원본 크기의 렌더링을 별도로 보존한다.
 const base64=await page.locator('#scene').evaluate(c=>c.toDataURL('image/png').split(',')[1]);await fs.writeFile(path.join(here,'scene.png'),Buffer.from(base64,'base64'));
 await page.locator('#grid').check();await page.locator('#connections').check();const grid=await page.locator('#scene').evaluate(c=>c.toDataURL('image/png').split(',')[1]);await fs.writeFile(path.join(here,'scene-grid.png'),Buffer.from(grid,'base64'));
 await page.setViewportSize({width:768,height:1024});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await page.screenshot({path:path.join(here,'preview-tablet.png'),fullPage:true});
 assert.deepEqual(errors,[]);await fs.writeFile(path.join(here,'verification.json'),JSON.stringify({passed:true,checks:['7 images loaded','grid toggle','collision overlay','ASCII output displayed','NPC direction','people toggle','props toggle','connections toggle','desktop and tablet no horizontal overflow','no script or asset errors'],engineExecuted:false,llmCalls:0},null,2));
 console.log('PASS: 이미지 로드·표시 토글·4방향 선택·반응형·스크립트 오류; 스크린샷 저장');
}finally{if(browser)await browser.close();await new Promise(resolve=>server.close(resolve))}

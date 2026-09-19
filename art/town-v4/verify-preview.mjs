import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import assert from 'node:assert/strict';
const here=path.dirname(fileURLToPath(import.meta.url));
const require=createRequire(path.resolve(here,'../../game/package.json'));
const {chromium}=require('playwright-core');
const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
try{
 const page=await browser.newPage({viewport:{width:1600,height:1250}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:4217/art/town-v4/compare.html');
 await page.waitForFunction(()=>Object.keys(imgs).length===3);
 await page.screenshot({path:path.join(here,'comparison-preview.png'),fullPage:true});
 const click=async(x,y)=>{const b=await page.locator('canvas').boundingBox();await page.mouse.click(b.x+x/1536*b.width,b.y+y/1024*b.height)};
 await click(712,552);await click(1224,840);
 assert.match(await page.locator('#status').textContent(),/칸으로 이어지는 경로/);
 await page.locator('#walk').check();await page.locator('#zones').check();
 await page.locator('canvas').screenshot({path:path.join(here,'map-contract.png')});
 for(const mode of ['original','previous','overlay','current']){
   await page.locator(`[data-mode=${mode}]`).click();
   assert.equal(await page.locator(`[data-mode=${mode}]`).getAttribute('aria-pressed'),'true');
 }
 assert.deepEqual(errors,[]);console.log('PASS — original / previous / current / overlay, real navigation path, all images loaded');
}finally{await browser.close()}

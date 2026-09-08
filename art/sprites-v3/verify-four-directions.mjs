import {chromium} from 'file:///C:/Users/akals/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
const root='C:/Users/akals/Documents/GitHub/dungeon/art/sprites-v3';
const browser=await chromium.launch({headless:true,channel:'msedge'});
try {
 const page=await browser.newPage({viewport:{width:1080,height:1050}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto('file:///'+root+'/four-direction-walk.html');
 await page.waitForFunction(()=>ready===4);
 await page.locator('#play').click();
 for(let i=0;i<4;i++) {await page.locator('#frame').fill(String(i));assert.equal(await page.locator('#num').textContent(),(i+1)+' / 4');}
 const start=await page.evaluate(()=>phase);await page.waitForTimeout(350);assert.equal(await page.evaluate(()=>phase),start);
 await page.locator('#play').click();await page.waitForFunction(p=>phase!==p,start);
 await page.locator('#play').click();await page.locator('#frame').fill('0');
 assert.equal(await page.evaluate(()=>Object.values(DATA).every(s=>s.crops.length===4)),true);
 await page.screenshot({path:root+'/four-direction-walk-preview.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 assert.deepEqual(errors,[]);console.log('PASS: four strips, 4 frames, pause/resume, mobile width, no page errors');
} finally {await browser.close();}


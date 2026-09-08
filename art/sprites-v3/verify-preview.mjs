import {chromium} from 'file:///C:/Users/akals/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
const b=await chromium.launch({headless:true,channel:'msedge'}),p=await b.newPage();const errors=[];p.on('pageerror',e=>errors.push(e.message));
await p.goto('file:///C:/Users/akals/Documents/GitHub/dungeon/art/sprites-v3/front-walk-preview.html');await p.waitForFunction(()=>document.querySelector('#strip').naturalWidth>0);await p.locator('#play').click();
for(let i=0;i<4;i++){await p.locator('#frame').fill(String(i));assert.equal(await p.locator('#num').textContent(),(i+1)+' / 4');}
assert.deepEqual(errors,[]);await b.close();console.log('PASS: image loaded, four frames selectable, no page errors');

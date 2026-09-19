// Town-v3 browser QA. Opens the standalone file; no game/server/LLM runs.
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
const here=path.dirname(fileURLToPath(import.meta.url));
const require=createRequire(path.resolve(here,'../../game/package.json'));
const {chromium}=require('playwright-core');
const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
try {
  const page=await browser.newPage({viewport:{width:1580,height:1200},deviceScaleFactor:1});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(path.join(here,'preview.html')).href);
  await page.waitForFunction(()=>window.__townDraft?.ready);
  const routeIds=await page.locator('#route option').evaluateAll(es=>es.map(e=>e.value).filter(Boolean));
  for(const id of routeIds){await page.locator('#route').selectOption(id);const msg=await page.locator('#route-info').textContent();assert.match(msg,/\d+칸 · 도달 가능/);assert(!msg.includes('-1칸'),id)}
  await page.locator('#route').selectOption('anvil');
  assert.equal(await page.locator('#detail-name').textContent(),'모루');
  assert.match(await page.locator('#detail-text').textContent(),/미정/);
  await page.locator('#route').selectOption('');
  for(const id of ['regions','grid','collision','objects','names']){await page.locator('#'+id).check();await page.locator('#'+id).uncheck()}
  await page.locator('#objects').check();await page.locator('#names').check();
  await page.locator('[data-region="guild_district"]').click();
  assert(await page.locator('[data-region="guild_district"]').evaluate(e=>e.classList.contains('active')));
  await page.locator('[data-region="guild_district"]').click();
  // Pointer interaction uses an existing building's footprint.
  const box=await page.locator('#map').boundingBox();
  await page.mouse.click(box.x+((35+1)/66)*box.width,box.y+((8+1)/50)*box.height);
  assert.equal(await page.locator('#detail-name').textContent(),'모험가 길드');
  await page.locator('#route').selectOption('');
  const exportCanvas=async name=>{const data=await page.locator('#map').evaluate(c=>c.toDataURL().split(',')[1]);await fs.writeFile(path.join(here,name),Buffer.from(data,'base64'))};
  await exportCanvas('map-overview.png');
  await page.screenshot({path:path.join(here,'preview-desktop.png'),fullPage:true});
  await page.locator('#regions').check();await page.locator('#collision').check();await page.locator('#grid').check();
  await exportCanvas('map-contract.png');
  await page.setViewportSize({width:390,height:844});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'mobile overflow');
  assert.deepEqual(errors,[]);
  const report={status:'PASS',routes:routeIds.length,toggles:5,pointerSelection:true,regionSelection:true,mobileWidth:390,consoleErrors:errors,gameRuns:0,llmCalls:0};
  await fs.writeFile(path.join(here,'browser-validation.json'),JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify(report));
} finally {await browser.close()}

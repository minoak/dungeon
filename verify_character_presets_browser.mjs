// verify_character_presets.py의 임시 서버에서만 실행한다. 실제 사용자 저장소를 대상으로 하지 않는다.
import assert from 'node:assert/strict';
import path from 'node:path';
import os from 'node:os';
import {pathToFileURL} from 'node:url';
const origin=process.argv[2];
if(!origin)throw new Error('임시 검증 서버의 주소가 필요하다');
const {chromium}=await import('playwright').catch(()=>import(pathToFileURL(path.join(os.homedir(),
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs'))));
const browser=await chromium.launch({headless:true,...(process.platform==='win32'?{channel:'msedge'}:{})});
const errors=[];
try {
  const page=await browser.newPage({viewport:{width:1280,height:1000}});
  page.on('pageerror',e=>errors.push(e.message));
  page.on('dialog',d=>d.accept());
  const card=i=>page.locator(`#cards > .card`).nth(i);
  const library=async()=>await (await page.request.get(origin+'/api/characters')).json();
  const open=async()=>{
    await page.goto(origin+'/launcher/'); await page.locator('#bNew').click();
    await page.waitForFunction(()=>document.querySelector('#presetStatus').textContent.length>0);
  };
  await open();
  assert.deepEqual((await library()).presets,[]);
  await card(0).locator('[data-preset-save]').click();
  await card(0).locator('.presetMessage.error').waitFor();
  assert.deepEqual((await library()).presets,[]);
  await card(0).locator('[data-k=name]').fill('유나');
  await card(0).locator('[data-k=traits] label').filter({hasText:'신중한'}).click();
  await card(0).locator('[data-k=persona]').fill('친구에게 장난을 잘 친다.');
  await card(0).locator('[data-k=background]').fill('광산 마을에서 자랐다.');
  await card(0).locator('[data-hairstyle]').selectOption('long');
  await card(0).locator('[data-preset-label]').fill('유나 · 긴 머리');
  await card(0).locator('[data-preset-save]').click();
  await page.waitForFunction(()=>document.querySelector('#presetStatus').textContent.includes('1명'));
  const original=(await library()).presets[0];
  assert.equal(original.slot.persona,'친구에게 장난을 잘 친다.');
  assert.equal(original.slot.look.hairstyle,'long');
  assert.ok(!('goal' in original.slot));

  await open();
  assert.equal(await card(0).locator('[data-k=name]').inputValue(),'');
  await card(2).locator('[data-preset-select]').selectOption(original.id);
  await card(2).locator('[data-preset-load]').click();
  assert.equal(await card(2).locator('[data-k=name]').inputValue(),'유나');
  assert.equal(await card(2).locator('[data-k=persona]').inputValue(),original.slot.persona);
  assert.equal(await card(2).locator('[data-k=background]').inputValue(),original.slot.background);
  assert.equal(await card(2).locator('[data-k=job] .on input').inputValue(),'전사');
  assert.equal(await card(2).locator('[data-hairstyle]').inputValue(),'long');
  assert.equal(await card(2).locator('[data-k=traits] label.on').textContent(),'신중한');
  await card(2).locator('[data-hairstyle]').selectOption('twintails');
  assert.deepEqual((await library()).presets[0],original);
  await card(2).locator('[data-preset-label]').fill('유나 · 양갈래');
  await card(2).locator('[data-preset-update]').click();
  await card(2).locator('[data-preset-message]').filter({hasText:'수정 저장됨'}).waitFor();
  assert.equal((await library()).presets.length,1);
  assert.equal((await library()).presets[0].slot.look.hairstyle,'twintails');
  await card(2).locator('[data-preset-save]').click();
  await page.waitForFunction(()=>document.querySelector('#presetStatus').textContent.includes('2명'));
  assert.equal((await library()).presets.length,2);
  await card(2).locator('[data-preset-delete]').click();
  await page.waitForFunction(()=>document.querySelector('#presetStatus').textContent.includes('1명'));
  assert.equal((await library()).presets[0].id,original.id);
  assert.equal(await card(2).locator('[data-k=name]').inputValue(),'유나');

  await open();
  await card(1).locator('[data-preset-select]').selectOption(original.id);
  await card(1).locator('[data-preset-load]').click();
  assert.equal(await card(1).locator('[data-hairstyle]').inputValue(),'twintails');
  for(const [i,name] of [[0,'수나'],[2,'미나']]){
    await card(i).locator('[data-k=name]').fill(name);
    await card(i).locator('[data-k=persona]').fill('낯선 것을 보고 싶어 한다.');
  }
  if(process.argv[3])await page.screenshot({path:process.argv[3],fullPage:true});
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  const saved=page.waitForResponse(r=>r.url().endsWith('/api/party') && r.request().method()==='POST');
  await page.locator('#bNext').click();assert.equal((await saved).status(),200);
  await page.locator('#sOpts').waitFor({state:'visible'});
  assert.deepEqual(errors,[]);
  console.log('PASS: 프리셋 새 저장·재접속·다른 칸 복원·헤어/성격 유지·수정·별도 복사·삭제·파티 저장·모바일 표시');
} finally {await browser.close();}

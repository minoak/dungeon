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

  // D81(2026-09-17): 편집 카드는 1번 칸(내 캐릭터) 하나다 — 복원·수정·복사·삭제는 그 카드에서, 2·3번 칸은 동료를 고르기만 한다.
  await open();
  assert.equal(await page.locator('#cards > .card').count(),1);
  assert.equal(await page.locator('#mates .mate').count(),2);
  assert.equal(await card(0).locator('[data-k=name]').inputValue(),'');
  await card(0).locator('[data-preset-select]').selectOption(original.id);
  await card(0).locator('[data-preset-load]').click();
  assert.equal(await card(0).locator('[data-k=name]').inputValue(),'유나');
  assert.equal(await card(0).locator('[data-k=persona]').inputValue(),original.slot.persona);
  assert.equal(await card(0).locator('[data-k=background]').inputValue(),original.slot.background);
  assert.equal(await card(0).locator('[data-k=job] .on input').inputValue(),'전사');
  assert.equal(await card(0).locator('[data-hairstyle]').inputValue(),'long');
  assert.equal(await card(0).locator('[data-k=traits] label.on').textContent(),'신중한');
  await card(0).locator('[data-hairstyle]').selectOption('twintails');
  assert.deepEqual((await library()).presets[0],original);
  await card(0).locator('[data-preset-label]').fill('유나 · 양갈래');
  await card(0).locator('[data-preset-update]').click();
  await card(0).locator('[data-preset-message]').filter({hasText:'수정 저장됨'}).waitFor();
  assert.equal((await library()).presets.length,1);
  assert.equal((await library()).presets[0].slot.look.hairstyle,'twintails');
  await card(0).locator('[data-preset-save]').click();
  await page.waitForFunction(()=>document.querySelector('#presetStatus').textContent.includes('2명'));
  assert.equal((await library()).presets.length,2);
  await card(0).locator('[data-preset-delete]').click();
  await page.waitForFunction(()=>document.querySelector('#presetStatus').textContent.includes('1명'));
  assert.equal((await library()).presets[0].id,original.id);
  assert.equal(await card(0).locator('[data-k=name]').inputValue(),'유나');

  // 동료 칸: 다른 캐릭터를 하나 더 저장하고, 내 캐릭터로 유나를 불러온 뒤, 저장한 수나를 2번 칸 동료로 고른다(3번 칸은 준비된 동료 그대로).
  await open();
  await card(0).locator('[data-k=name]').fill('수나');
  await card(0).locator('[data-k=persona]').fill('낯선 것을 보고 싶어 한다.');
  await card(0).locator('[data-preset-save]').click();
  await page.waitForFunction(()=>document.querySelector('#presetStatus').textContent.includes('2명'));
  const suna=(await library()).presets.find(p=>p.slot.name==='수나');
  await card(0).locator('[data-preset-select]').selectOption(original.id);
  await card(0).locator('[data-preset-load]').click();
  assert.equal(await card(0).locator('[data-hairstyle]').inputValue(),'twintails');
  const mate=i=>page.locator('#mates .mate').nth(i);
  assert.equal(await mate(0).locator(`option[value="p:${original.id}"]`).count(),0); // 1번 칸에 선 저장본은 동료 후보가 아니다
  await mate(0).locator('[data-mate-select]').selectOption('p:'+suna.id);
  assert.ok((await mate(0).locator('.mateInfo').textContent()).includes('수나'));
  const third=await mate(1).locator('[data-mate-select]').inputValue();
  assert.ok(third.startsWith('c:')); // 준비된 동료(entities/companion)가 기본으로 채워져 있다
  if(process.argv[3])await page.screenshot({path:process.argv[3],fullPage:true});
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.route('**/api/start',route=>route.fulfill({status:400,json:{error:'검증용 중단(러너 0)'}})); // 출발 버튼이 파티를 저장한 뒤 판을 연다 — 판은 열지 않는다
  const saved=page.waitForResponse(r=>r.url().endsWith('/api/party') && r.request().method()==='POST');
  await page.locator('#bStart').click();
  const partyResponse=await saved;assert.equal(partyResponse.status(),200);
  const sent=partyResponse.request().postDataJSON();
  assert.deepEqual(sent.slots.map(s=>s.name||s.companion),['유나','수나',third.slice(2)]);
  assert.deepEqual(sent.preset_ids,[original.id,suna.id,'']);
  await page.waitForFunction(()=>document.querySelector('#err2').textContent.includes('검증용 중단'));
  assert.deepEqual(errors,[]);
  console.log('PASS: 프리셋 새 저장·재접속·복원·헤어/성격 유지·수정·별도 복사·삭제·저장 캐릭터를 동료로·준비된 동료·출발 버튼의 파티 저장·모바일 표시');
} finally {await browser.close();}

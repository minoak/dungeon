// 임시 공개 서버 전용. /api/start는 가로채므로 생성 API 호출은 0이다.
import assert from 'node:assert/strict';
import path from 'node:path';
import os from 'node:os';
import {pathToFileURL} from 'node:url';
const origin = process.argv[2];
if (!origin) throw new Error('임시 공개 서버 URL이 필요하다');
const {chromium} = await import('playwright').catch(() => import(pathToFileURL(path.join(os.homedir(),
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs'))));
const browser = await chromium.launch({headless: true, ...(process.platform === 'win32' ? {channel: 'msedge'} : {})});
try {
  const page = await browser.newPage({viewport: {width: 1280, height: 1000}});
  const errors = [], starts = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.route('**/api/status', route => route.fulfill({json: {running: false, seed: 42, resume: {
    run_id: 'browser-test', seed: 42, turn_last: 3, depth: 1, party: [], backend: 'gemini_api', provider: 'gemini_api', model: 'saved-custom-model'
  }}}));
  await page.route('**/api/start', route => {
    starts.push(route.request().postDataJSON());
    return route.fulfill({status: 400, json: {error: '검증용 중단(API 0콜)'}});
  });
  await page.goto(origin + '/launcher/');
  await page.locator('#loginProvider option').first().waitFor({state: 'attached'});
  assert.equal(await page.locator('#brain option').count(), 3);
  await page.waitForFunction(() => document.querySelector('#resumeModelCustom').value === 'saved-custom-model');
  assert.equal(await page.locator('#resumeModel').inputValue(), '__custom__');
  assert.equal(await page.locator('#resumeModelCustom').isVisible(), true);
  const key = 'fake-browser-key-12345678901234567890';
  await page.locator('#loginProvider').selectOption('anthropic_api');
  await page.locator('#loginKey').fill(key);
  await page.locator('#bLogin').click();
  await page.locator('#acctIn').waitFor({state: 'visible'});
  assert.equal(await page.locator('#brain').inputValue(), 'anthropic_api');
  assert.equal(await page.locator('#brainModel').inputValue(), 'claude-haiku-4-5-20251001');
  assert.equal(await page.locator('#brainModel option').count(), 5);
  assert.equal(await page.locator('#brainModelCustom').isVisible(), false);
  assert.equal(await page.locator('#apiKey').inputValue(), key);
  assert.equal(await page.locator('#resumeKey').inputValue(), ''); // Gemini 이어가기에는 Anthropic 키를 안 채운다
  await page.locator('#linkProvider').selectOption('openai_api');
  await page.locator('#linkKey').fill(key + '-openai');
  await page.locator('#bLink').click();
  await page.waitForFunction(() => document.querySelector('#acctKeys').textContent.includes('OpenAI'));
  await page.locator('#resumeProvider').selectOption('openai_api');
  assert.equal(await page.locator('#resumeModel').inputValue(), 'gpt-5.6-terra');
  await page.locator('#resumeKey').fill(key + '-resume');
  await page.locator('#resumeModel').selectOption('gpt-6-astra');
  await page.locator('#bResume').click();
  await page.waitForFunction(() => document.querySelector('#tStatus').textContent.includes('검증용 중단'));
  assert.deepEqual(starts.pop(), {resume: true, provider: 'openai_api', brain: 'openai_api', model: 'gpt-6-astra', key: key + '-resume'});
  // 상태 갱신이 사용자가 고른 모델을 저장 모델로 되돌리면 안 된다.
  await page.waitForResponse(r => r.url().endsWith('/api/status'));
  assert.equal(await page.locator('#resumeModel').inputValue(), 'gpt-6-astra');
  await page.locator('#resumeModel').selectOption('__custom__');
  await page.locator('#resumeModelCustom').fill('resume-model');
  await Promise.all([page.waitForResponse(r => r.url().endsWith('/api/start')), page.locator('#bResume').click()]);
  assert.equal(starts.pop().model, 'resume-model');
  await page.locator('#bNew').click();
  await page.locator('#partyMode label').filter({has: page.locator('input[value="default"]')}).click();
  await page.locator('#bNext').click();
  await page.locator('#brain').selectOption('openai_api');
  assert.equal(await page.locator('#apiKey').inputValue(), '');
  assert.equal(await page.locator('#brainModel').inputValue(), 'gpt-5.6-terra');
  await page.locator('#brainModel').selectOption('gpt-5.6-luna');
  assert.equal(await page.locator('#costRows tr').count(), 17);
  assert((await page.locator('#costEstimate').textContent()).includes('$0.00340'));
  await page.locator('#costChars').fill('20000');
  assert((await page.locator('#costEstimate').textContent()).includes('$0.00540'));
  await page.locator('#costChars').fill('10000');
  await page.locator('#brain').selectOption('anthropic_api');
  await page.locator('#brainModel').selectOption('claude-fable-5-1');
  assert((await page.locator('#costEstimate').textContent()).includes('$0.16500'));
  assert((await page.locator('#costEstimate').textContent()).includes('$16.50'));
  await page.locator('#brain').selectOption('openai_api');
  await page.locator('#brainModel').selectOption('gpt-5.6-luna');
  await page.locator('#apiKey').fill(key + '-start');
  await page.locator('#bStart').click();
  await page.waitForFunction(() => document.querySelector('#err2').textContent.includes('검증용 중단'));
  const start = starts.pop();
  assert.equal(start.provider, 'openai_api');
  assert.equal(start.model, 'gpt-5.6-luna');
  assert.equal(start.key, key + '-start');
  await page.locator('#brainModel').selectOption('__custom__');
  await page.locator('#brainModelCustom').fill('');
  await page.locator('#bStart').click();
  assert.equal(starts.length, 0); // 비어 있는 직접 입력은 기본 모델로 몰래 실행하지 않는다.
  await page.locator('#brainModelCustom').fill('org/my-model');
  assert((await page.locator('#costEstimate').textContent()).includes('미확인'));
  await Promise.all([page.waitForResponse(r => r.url().endsWith('/api/start')), page.locator('#bStart').click()]);
  assert.equal(starts.pop().model, 'org/my-model');
  await page.locator('#brain').selectOption('gemini_api');
  assert.equal(await page.locator('#brainModel option').count(), 10);
  assert.equal(await page.locator('#brainModelCustom').isVisible(), false);
  await page.locator('#brainModel').selectOption('gemini-3.1-pro-preview');
  await page.setViewportSize({width: 390, height: 844});
  await page.locator('#priceCard summary').filter({hasText:'같은 길이로 모델 가격 비교'}).click();
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  assert.equal(await page.evaluate(() => localStorage.length + sessionStorage.length), 0);
  assert.deepEqual(errors, []);
  if (process.argv[3]) await page.locator('#priceCard').screenshot({path: process.argv[3]});
  if (process.argv[4]) {
    const local = await browser.newPage({viewport: {width: 1280, height: 1000}});
    const localStarts = [];
    local.on('pageerror', e => errors.push(e.message));
    await local.route('**/api/status', route => route.fulfill({json: {running: false, resume: {
      run_id: 'local-resume', seed: 1, turn_last: 2, depth: 0, party: [], provider: 'gemini_api', model: 'gemini-3.8-flash'
    }}}));
    await local.route('**/api/start', route => {
      localStarts.push(route.request().postDataJSON());
      return route.fulfill({status: 400, json: {error: '검증용 중단(API 0콜)'}});
    });
    await local.goto(process.argv[4] + '/launcher/');
    await local.locator('#resumeKey').waitFor({state: 'visible'});
    await local.locator('#resumeKey').fill('fake-local-resume-key');
    await Promise.all([local.waitForResponse(r => r.url().endsWith('/api/start')), local.locator('#bResume').click()]);
    assert.equal(localStarts.pop().key, 'fake-local-resume-key');
    await local.locator('#bNew').click();
    await local.locator('#partyMode label').filter({has: local.locator('input[value="default"]')}).click();
    await local.locator('#bNext').click();
    await local.locator('#brain').selectOption('anthropic_api');
    assert(await local.locator('#apiKey').isVisible());
    await local.locator('#apiKey').fill('fake-local-start-key');
    await Promise.all([local.waitForResponse(r => r.url().endsWith('/api/start')), local.locator('#bStart').click()]);
    assert.equal(localStarts.pop().key, 'fake-local-start-key');
    await local.locator('#brain').selectOption('openai_api');
    assert.equal(await local.locator('#apiKey').inputValue(), '');
    await Promise.all([local.waitForResponse(r => r.url().endsWith('/api/start')), local.locator('#bStart').click()]);
    assert.equal(localStarts.pop().key, ''); // 로컬 빈 키는 기존 .env를 사용한다.
    await local.locator('#brain').selectOption('dummy');
    assert.equal(await local.locator('#keyCard').isVisible(), false);
    assert.equal(await local.locator('#priceCard').isVisible(), false);
    await local.locator('#brain').selectOption('gemini_api');
    await local.locator('#usePartySize').click();
    const config = await (await local.request.get(process.argv[4] + '/api/presets')).json();
    assert.equal(Number(await local.locator('#costChars').inputValue()), Math.max(...config.default_party.map(p => p.prompt_chars)));
    await local.setViewportSize({width:390,height:844});
    assert(await local.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    assert.equal(await local.evaluate(() => localStorage.length + sessionStorage.length), 0);
    assert.deepEqual(errors, []);
    // 새 화면을 읽었지만 Python 서버가 구버전이면 키를 보내지 않고 재시작을 안내한다.
    await local.route('**/api/presets', async route => {
      const response = await route.fetch(), json = await response.json();
      json.model_ui_version = 1;
      await route.fulfill({json});
    });
    await local.reload();
    await local.locator('#resumeKey').waitFor({state:'visible'});
    await local.locator('#resumeKey').fill('fake-old-server-key');
    await local.locator('#bResume').click();
    assert.equal(localStarts.length, 0);
    assert((await local.locator('#tStatus').textContent()).includes('이전 런처'));
    await local.locator('#bNew').click();
    assert((await local.locator('#tStatus').textContent()).includes('이전 런처'));
    console.log('ALL PASS local key entry: new/resume, blank env fallback, provider key clearing, no storage; prices: 17 rows, length scaling, Fable, unknown, party length, mobile');
  }
  console.log('ALL PASS browser model wiring: 17 choices, custom/saved models, preset/custom start/resume, empty guard, key isolation, mobile, no page errors');
} finally {
  await browser.close();
}

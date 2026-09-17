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
  await Promise.all([page.waitForResponse(r => r.url().endsWith('/api/start')), page.locator('#bStart').click()]);
  assert.equal(starts.pop().model, 'org/my-model');
  await page.locator('#brain').selectOption('gemini_api');
  assert.equal(await page.locator('#brainModel option').count(), 10);
  assert.equal(await page.locator('#brainModelCustom').isVisible(), false);
  await page.locator('#brainModel').selectOption('gemini-3.1-pro-preview');
  await page.setViewportSize({width: 390, height: 844});
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  assert.equal(await page.evaluate(() => localStorage.length + sessionStorage.length), 0);
  assert.deepEqual(errors, []);
  if (process.argv[3]) await page.screenshot({path: process.argv[3], fullPage: true});
  console.log('ALL PASS browser model wiring: 17 choices, custom/saved models, preset/custom start/resume, empty guard, key isolation, mobile, no page errors');
} finally {
  await browser.close();
}

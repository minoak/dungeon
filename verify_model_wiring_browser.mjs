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
    run_id: 'browser-test', seed: 42, turn_last: 3, depth: 1, party: [], backend: 'gemini_api', provider: 'gemini_api', model: 'gemini-3.8-flash'
  }}}));
  await page.route('**/api/start', route => {
    starts.push(route.request().postDataJSON());
    return route.fulfill({status: 400, json: {error: '검증용 중단(API 0콜)'}});
  });
  await page.goto(origin + '/launcher/');
  await page.locator('#loginProvider option').first().waitFor({state: 'attached'});
  assert.equal(await page.locator('#brain option').count(), 3);
  const key = 'fake-browser-key-12345678901234567890';
  await page.locator('#loginProvider').selectOption('anthropic_api');
  await page.locator('#loginKey').fill(key);
  await page.locator('#bLogin').click();
  await page.locator('#acctIn').waitFor({state: 'visible'});
  assert.equal(await page.locator('#brain').inputValue(), 'anthropic_api');
  assert.equal(await page.locator('#brainModel').inputValue(), 'claude-haiku-4-5-20251001');
  assert.equal(await page.locator('#apiKey').inputValue(), key);
  assert.equal(await page.locator('#resumeKey').inputValue(), ''); // Gemini 이어가기에는 Anthropic 키를 안 채운다
  await page.locator('#linkProvider').selectOption('openai_api');
  await page.locator('#linkKey').fill(key + '-openai');
  await page.locator('#bLink').click();
  await page.waitForFunction(() => document.querySelector('#acctKeys').textContent.includes('OpenAI'));
  await page.locator('#resumeProvider').selectOption('openai_api');
  assert.equal(await page.locator('#resumeModel').inputValue(), 'gpt-5.6-terra');
  await page.locator('#resumeKey').fill(key + '-resume');
  await page.locator('#resumeModel').fill('resume-model');
  await page.locator('#bResume').click();
  await page.waitForFunction(() => document.querySelector('#tStatus').textContent.includes('검증용 중단'));
  assert.deepEqual(starts.pop(), {resume: true, provider: 'openai_api', brain: 'openai_api', model: 'resume-model', key: key + '-resume'});
  await page.locator('#bNew').click();
  await page.locator('#partyMode label').filter({has: page.locator('input[value="default"]')}).click();
  await page.locator('#bNext').click();
  await page.locator('#brain').selectOption('openai_api');
  assert.equal(await page.locator('#apiKey').inputValue(), '');
  assert.equal(await page.locator('#brainModel').inputValue(), 'gpt-5.6-terra');
  await page.locator('#brainModel').fill('org/my-model');
  await page.locator('#apiKey').fill(key + '-start');
  await page.locator('#bStart').click();
  await page.waitForFunction(() => document.querySelector('#err2').textContent.includes('검증용 중단'));
  const start = starts.pop();
  assert.equal(start.provider, 'openai_api');
  assert.equal(start.model, 'org/my-model');
  assert.equal(start.key, key + '-start');
  assert.equal(await page.evaluate(() => localStorage.length + sessionStorage.length), 0);
  assert.deepEqual(errors, []);
  if (process.argv[3]) await page.screenshot({path: process.argv[3], fullPage: true});
  console.log('ALL PASS browser model wiring: login/link, provider defaults, key clearing, new run/resume payloads, no key storage, no page errors');
} finally {
  await browser.close();
}

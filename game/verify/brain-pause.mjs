// 실제 러너 + 고정 모델 응답으로 정지/재시도 화면을 검증한다. 사용자 원정·실제 LLM 무접촉.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'wl-brain-ui-'));
const out = path.join(root, 'game/verify/out');
fs.mkdirSync(out, { recursive: true });
const port = 4288, base = `http://127.0.0.1:${port}`;
const server = spawn('python', ['verify_brain_pause.py', '--serve', temp, String(port)], {
  cwd: root, env: { ...process.env, PYTHONUTF8: '1' }, stdio: 'ignore',
});
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const status = async () => (await fetch(base + '/api/status')).json();
let browser;
const errors = [];
let checks = 0;
function check(name, value) { assert.ok(value, name); checks++; console.log('PASS ' + name); }
try {
  let ready = false;
  for (let i = 0; i < 70; i++) {
    try { if ((await status()).brain_pause) { ready = true; break; } } catch {}
    await sleep(200);
  }
  assert.ok(ready, '격리 러너가 판단 오류로 정지');
  browser = await chromium.launch({ headless: true, ...(process.platform === 'win32' ? { channel: 'msedge' } : {}) });
  const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
  page.on('pageerror', e => errors.push(e.message));
  await page.goto(base + '/game/?run=state/stream.jsonl');
  await page.waitForSelector('#brainPause:not([hidden])');
  check('관전 화면에 판단 정지 사유와 재시도 버튼 표시',
    (await page.textContent('#brainPause')).includes('소지품에 없는 물건')
    && (await page.textContent('.live-hud')).includes('판단 정지') && await page.isEnabled('#brainRetry'));
  const first = (await status()).brain_pause.id;
  const stream = path.join(temp, 'state/stream.jsonl');
  const before = fs.readFileSync(stream, 'utf8');
  await sleep(1600);
  check('기다리는 동안 게임 기록과 모델 호출 수가 그대로', before === fs.readFileSync(stream, 'utf8')
    && fs.readFileSync(path.join(temp, 'state/calls-1'), 'utf8') === '2');
  await page.screenshot({ path: path.join(out, 'brain-pause.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  const box = await page.locator('#brainPause').boundingBox();
  check('좁은 화면에서도 정지 안내와 버튼이 화면 안에 배치', box.x >= 0 && box.x + box.width <= 390
    && box.y >= 0 && box.y + box.height <= 844);
  await page.screenshot({ path: path.join(out, 'brain-pause-mobile.png'), fullPage: true });
  await page.setViewportSize({ width: 1440, height: 960 });
  await page.reload();
  await page.waitForSelector('#brainPause:not([hidden])');
  check('새로고침해도 같은 정지 상태를 복원', (await status()).brain_pause.id === first);
  await page.click('#brainRetry');
  check('재시도 요청 중 중복 클릭 방지', await page.isDisabled('#brainRetry'));
  await page.waitForFunction(async id => {
    const s = await (await fetch('/api/status')).json();
    return s.brain_pause?.id && s.brain_pause.id !== id;
  }, first);
  await page.waitForFunction(() => !document.querySelector('#brainRetry').disabled);
  check('재시도도 실패하면 같은 틱에서 다시 정지', (await status()).brain_pause.turn === 1
    && fs.readFileSync(path.join(temp, 'state/calls-1'), 'utf8') === '4'
    && fs.readFileSync(path.join(temp, 'state/calls-2'), 'utf8') === '1');

  const title = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  title.on('pageerror', e => errors.push(e.message));
  await title.goto(base + '/launcher/');
  await title.waitForSelector('#brainPause:not([hidden])');
  check('런처에도 같은 정지 상태와 버튼 표시', (await title.textContent('#tStatus')).includes('일시정지'));
  const legacy = await browser.newPage();
  legacy.on('pageerror', e => errors.push(e.message));
  await legacy.goto(base + '/viewer/?run=state/stream.jsonl');
  await legacy.waitForSelector('#brainPause:not([hidden])');
  check('옛 뷰어에서도 정지 확인과 재시도 가능', await legacy.isEnabled('#brainRetry'));

  fs.writeFileSync(path.join(temp, 'state/allow-brain'), '');
  await title.click('#brainRetry');
  await page.waitForSelector('#brainPause', { state: 'hidden' });
  await title.waitForSelector('#brainPause', { state: 'hidden' });
  await page.waitForFunction(() => window.__wl?.run?.end);
  const records = fs.readFileSync(stream, 'utf8').trim().split('\n').map(JSON.parse);
  check('성공하면 정지 안내가 사라지고 같은 원정에서 1·2틱 실행',
    records.filter(r => r.kind === 'run_meta').length === 1
    && records.filter(r => r.kind === 'tick').map(r => r.turn).join(',') === '1,2'
    && records.filter(r => r.kind === 'tick').every(r => Object.values(r.decisions).every(d => d.src === 'haiku')));
  check('브라우저 실행 오류 없음', errors.length === 0);
  console.log(`ALL PASS — ${checks} browser checks; ${temp}`);
} finally {
  try { await fetch(base + '/api/stop', { method: 'POST', body: '{}' }); } catch {}
  await browser?.close();
  server.kill();
}

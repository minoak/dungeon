// 알파 시작 → 실제 dummy 러너 → 실시간 관전 → 결정론적 스킬 재생. LLM 호출·사용자 state 변경 없음.
// 실행: npm run build && node verify/alpha.mjs
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'wl-alpha-ui-'));
const out = path.join(root, 'game/verify/out');
fs.mkdirSync(out, { recursive: true });
const port = 4287, base = `http://127.0.0.1:${port}`;
const fixture = path.join(temp, 'fixture.jsonl');
const made = spawnSync('python', ['verify_skill_stream.py'], {
  cwd: root, env: { ...process.env, PYTHONUTF8: '1', WL_SKILL_FIXTURE: fixture }, encoding: 'utf8',
});
assert.equal(made.status, 0, made.stdout + made.stderr);
const server = spawn('python', ['verify_skill_launcher.py', '--serve', temp, String(port)], {
  cwd: root, env: { ...process.env, PYTHONUTF8: '1' }, stdio: 'ignore',
});
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
let browser;
const errors = [];
let checks = 0;
const check = (name, value) => { assert.ok(value, name); checks++; console.log('PASS ' + name); };
try {
  let ready = false;
  for (let i = 0; i < 60; i++) {
    try { if ((await fetch(base + '/api/presets')).ok) { ready = true; break; } } catch {}
    await sleep(200);
  }
  assert.ok(ready, '격리 런처 준비');
  browser = await chromium.launch({ headless: true, ...(process.platform === 'win32' ? { channel: 'msedge' } : {}) });
  const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
  page.on('pageerror', e => errors.push(e.message));
  page.on('response', r => { if (r.status() >= 400 && !r.url().includes('favicon')) errors.push(`${r.status()} ${r.url()}`); });
  await page.goto(base + '/launcher/');
  await page.click('#bNew');
  const first = page.locator('#cards > .card').first();
  const persona = '성'.repeat(1995) + '마지막성격', background = '배'.repeat(3995) + '마지막배경';
  await first.locator('[data-k=name]').fill('긴서술');
  await first.locator('[data-k=persona]').fill(persona);
  await first.locator('[data-k=background]').fill(background);
  check('성격 2000자 · 배경 4000자 입력과 글자 수 표시',
    (await first.locator('[data-cnt=pt]').textContent()) === '2000/2000'
    && (await first.locator('[data-cnt=bg]').textContent()) === '4000/4000');
  await first.locator('[data-preset-save]').click();
  await page.waitForFunction(() => document.querySelector('#presetStatus').textContent.includes('1명'));
  const library = await (await page.request.get(base + '/api/characters')).json();
  check('긴 시트를 서버에 끝까지 저장', library.presets[0].slot.persona === persona && library.presets[0].slot.background === background);
  await page.reload();
  await page.click('#bNew');
  await first.locator('[data-preset-select]').selectOption(library.presets[0].id);
  await first.locator('[data-preset-load]').click();
  check('페이지를 다시 열어도 긴 시트를 그대로 복원', await first.locator('[data-k=persona]').inputValue() === persona
    && await first.locator('[data-k=background]').inputValue() === background);
  const body = JSON.stringify({ slots: [1, 2, 3].map(i => ({ ...library.presets[0].slot, name: `서술${i}` })) })
    .replace(/[\u0080-\uffff]/g, c => '\\u' + c.charCodeAt(0).toString(16).padStart(4, '0'));
  const saved = await page.request.post(base + '/api/party', { data: body, headers: { 'Content-Type': 'application/json' } });
  const sheets = JSON.parse(fs.readFileSync(path.join(temp, 'party.json'), 'utf8'));
  check('유니코드를 이스케이프한 긴 3인 시트도 요청 크기 제한에 걸리지 않음', saved.ok() && body.length > 65536
    && sheets['3'].persona === persona && sheets['3'].background === background);
  await page.locator('#partyMode label').filter({ hasText: '기본 파티' }).click();
  await page.click('#bNext');
  await page.waitForSelector('#alphaPreview .wl-skill');
  check('기본 원정에 스킬 적용 · 시작 스킬 6개 미리보기 · 마을 비활성',
    await page.inputValue('#runMode') === 'standard' && await page.locator('#alphaPreview .wl-skill').count() === 6
    && await page.isDisabled('#town'));
  await page.screenshot({ path: path.join(out, 'alpha-launcher.png'), fullPage: true });
  await page.selectOption('#runMode', 'classic');
  check('이전 규칙 전환 시 스킬 설명 숨김 · 마을 복원', await page.isHidden('#alphaInfo') && !await page.isDisabled('#town'));
  await page.selectOption('#runMode', 'standard');
  await page.selectOption('#brain', 'dummy');
  check('규칙 두뇌의 스킬 미사용 안내', (await page.textContent('#alphaBrainHint')).includes('스킬을 선택하지 않아'));
  await page.getByText('고급: 시드 지정', { exact: true }).click();
  await page.fill('#seed', '7');
  await page.click('#bStart');
  await page.waitForURL('**/game/?run=state/stream.jsonl');
  await page.waitForFunction(() => window.__wl?.run?.meta?.alpha?.skills && window.__wl.playback.cur);
  check('실제 러너 설정: 5층 · 600틱 · 알파 3종 ON', await page.evaluate(() => {
    const m = window.__wl.run.meta;
    return m.ruleset === 'skills-v1' && m.depths === 5 && m.max_turns === 600 && m.alpha.skills && m.alpha.trpg_combat && m.alpha.random_skill_effective;
  }));
  await page.waitForSelector('.fc-skills .wl-skill');
  check('자동 관전 이동 · 알파 표식 · 캐릭터 스킬',
    (await page.textContent('#alphaLabel')).includes('3층 랜덤 획득') && await page.locator('.fc-skills .wl-skill').count() === 2);
  const count = await page.evaluate(() => window.__wl.run.frames.length);
  await page.waitForFunction(n => window.__wl.run.frames.length > n, count, { timeout: 10000 });
  check('진행 중인 알파 틱을 자동으로 수신', true);
  await page.screenshot({ path: path.join(out, 'alpha-live.png'), fullPage: true });
  await fetch(base + '/api/stop', { method: 'POST', body: '{}' });

  // 여기부터는 손으로 만든 엔진 검증 장면. LLM 플레이나 밸런스 증거가 아니다.
  const lines = fs.readFileSync(fixture, 'utf8').trimEnd().split('\n');
  const third = lines.findIndex(line => { const o = JSON.parse(line); return o.kind === 'level' && o.depth === 3; });
  const state = path.join(temp, 'state/stream.jsonl');
  fs.writeFileSync(state, lines.slice(0, third).join('\n') + '\n');
  await page.goto(base + '/game/?run=state/stream.jsonl');
  await page.waitForFunction(() => window.__wl?.run?.levels.length === 2);
  fs.writeFileSync(state, lines.join('\n') + '\n');
  await page.waitForFunction(() => window.__wl?.run?.levels.length === 5);
  check('폴링으로 3층 획득과 5층까지 새 기록 반영', true);
  await page.evaluate(() => {
    const a = window.__wl;
    a.playback.setIdx(a.run.frames.findIndex(f => f.kind === 'level' && f.level.depth === 3), 'seek');
  });
  check('획득 스킬 카드 · 층 진입 획득 기록', await page.locator('.fc-skills .wl-skill-new').count() === 1
    && (await page.textContent('#log')).includes('획득'));
  await page.screenshot({ path: path.join(out, 'alpha-acquisition.png'), fullPage: true });
  await page.evaluate(() => {
    const a = window.__wl;
    a.playback.setIdx(a.run.frames.findIndex(f => f.bots.some(b => b.char === '1' && Object.values(b.skill_cooldowns || {}).some(v => v > 0))), 'seek');
  });
  check('재생 위치에 맞는 재사용 대기 표시', (await page.textContent('.fc-skills')).includes('행동 후 재사용'));
  await page.evaluate(() => {
    const a = window.__wl;
    a.playback.setIdx(a.run.frames.findIndex(f => f.events.some(e => e.skill_roll)), 'seek');
  });
  check('명중 주사위와 기준값을 전투 기록에 표시', (await page.textContent('#log')).includes('주사위')
    && (await page.textContent('#log')).includes('기준'));
  await page.evaluate(() => window.__wl.playback.setIdx(0, 'seek'));
  check('과거로 되감으면 획득 스킬과 대기가 사라짐', await page.locator('.fc-skills .wl-skill-new').count() === 0
    && !(await page.textContent('.fc-skills')).includes('행동 후 재사용'));
  await page.goto(base + '/viewer/?run=state/stream.jsonl');
  await page.waitForSelector('#party .wl-skill');
  check('옛 뷰어에도 스킬 원정 표식과 스킬 카드', (await page.textContent('#runInfo')).includes('스킬 원정'));
  await page.click('#bEnd');
  check('옛 뷰어의 획득 스킬 및 주사위 기록', await page.locator('#party .wl-skill-new').count() === 2
    && (await page.textContent('#feed')).includes('주사위'));
  await page.goto(base + '/game/?run=runs/stream-20260909-203709.jsonl');
  await page.waitForFunction(() => window.__wl?.run?.frames.length > 0);
  check('기존 판에는 알파 표식·스킬 영역이 없음', await page.isHidden('#alphaLabel') && await page.isHidden('.fc-skill-section'));
  check('브라우저 오류 없음', errors.length === 0);
  console.log(`ALL PASS — ${checks} alpha UI checks. Screenshots: ${out}`);
} finally {
  await fetch(base + '/api/stop', { method: 'POST', body: '{}' }).catch(() => {});
  await browser?.close();
  server.kill();
  if (errors.length) console.error(errors);
  console.log('검증 기록: ' + temp);
}

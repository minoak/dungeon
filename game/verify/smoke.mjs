// 스모크 — 빌드 산출물을 vite preview 로 띄우고 헤드리스 Edge(playwright-core, channel msedge — 브라우저 다운로드 없음)로
// 대표 판(seed 257573)을 재생한다. LLM 0콜. 실행: cd game && npm run build && npm run smoke
//   WL_GAME_URL=http://127.0.0.1:8000/game/  → 론처(launcher.py) 상대로 검사(preview 안 띄움)
//   WL_RUN=runs/….jsonl                    → 다른 판
// Phase A(M1) 검사: 프레임 수·초점 기본값·칩 3개·칩 클릭 전환 ≤300ms·카메라가 초점을 봄·t176→t184 스텝·층 전이·
// 16× 전체 재생 프레임 정체·콘솔 오류 0. Phase B6 가 장면 재현(건네기 트윈·지문·말풍선·초점 카드·밝기) 검사를 덧붙인다.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { spawn, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const gameDir = path.resolve(here, '..');
const outDir = path.join(here, 'out');
fs.mkdirSync(outDir, { recursive: true });
const out = name => path.join(outDir, name);
const RUN = process.env.WL_RUN || 'runs/stream-20260909-203709.jsonl';
const PORT = Number(process.env.WL_PORT || 4199);
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function waitHttp(url, ms = 20000) {
  const t0 = Date.now();
  for (;;) {
    try { const r = await fetch(url); if (r.ok) return; } catch { /* 아직 */ }
    if (Date.now() - t0 > ms) throw new Error('서버가 안 뜬다: ' + url);
    await sleep(200);
  }
}

let base = process.env.WL_GAME_URL;
let server = null;
if (!base) {
  if (!fs.existsSync(path.join(gameDir, 'dist', 'index.html'))) {
    const b = spawnSync(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['run', 'build'], { cwd: gameDir, stdio: 'inherit', shell: process.platform === 'win32' });
    if (b.status !== 0) throw new Error('build 실패');
  }
  server = spawn(process.execPath, [path.join(gameDir, 'node_modules', 'vite', 'bin', 'vite.js'), 'preview',
    '--port', String(PORT), '--strictPort', '--host', '127.0.0.1'], { cwd: gameDir, stdio: ['ignore', 'pipe', 'pipe'] });
  server.stderr.on('data', d => process.stderr.write('[preview] ' + d));
  base = `http://127.0.0.1:${PORT}/game/`;
  await waitHttp(base);
}

const { chromium } = await import('playwright-core');
const browser = await chromium.launch({ headless: true, ...(process.platform === 'win32' ? { channel: 'msedge' } : {}) });
const errors = [];
let ok = false;
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
  page.on('response', r => { if (r.status() >= 400 && !/favicon/.test(r.url())) errors.push(`http ${r.status()} ${r.url()}`); });
  page.on('requestfailed', r => errors.push('requestfailed ' + r.url() + ' ' + (r.failure() && r.failure().errorText)));

  await page.goto(`${base}?run=${encodeURIComponent(RUN)}&focus=2&t=176`);
  await page.waitForFunction(() => window.__wl && window.__wl.run && window.__wl.playback.idx >= 0 && window.__wl.scene, null, { timeout: 40000 });
  await sleep(700);                                              // 팬·lerp 안정
  const info = await page.evaluate(() => {
    const a = window.__wl, f = a.playback.cur;
    return { frames: a.playback.frames.length, turn: f.turn, party: a.run.party.length, focus: a.focus.char,
             chips: document.querySelectorAll('.chip').length, levels: a.run.levels.length, end: a.run.end && a.run.end.outcome,
             renderer: a.game.renderer.type };
  });
  console.log('[smoke] 판', RUN, info);
  assert.equal(info.frames, 252, '프레임 수(level 2 + tick 250)');
  assert.equal(info.turn, 176); assert.equal(info.focus, '2'); assert.equal(info.chips, 3); assert.equal(info.levels, 2);

  const centered = async (char) => page.evaluate(c => {
    const a = window.__wl, p = a.scene.feetOf(c), s = a.scene.project(p.x, p.y);
    const w = a.dom.stage.clientWidth, h = a.dom.stage.clientHeight;
    return { x: s.x / w, y: s.y / h };
  }, char);
  let c = await centered('2');
  assert(c.x > 0.3 && c.x < 0.7 && c.y > 0.25 && c.y < 0.85, '초점(수나)이 화면 중앙 근처에 없다 ' + JSON.stringify(c));
  await page.screenshot({ path: out('m1-t176-focus2.png') });

  // 칩 클릭 → 초점 전환 ≤300ms(+여유) → 카메라가 유나로
  const t0 = Date.now();
  await page.click('.chip[data-char="1"]');
  await page.waitForFunction(() => window.__wl.focus.char === '1');
  const dt = Date.now() - t0;
  assert(dt <= 500, '칩 클릭 전환이 느리다 ' + dt + 'ms');
  await sleep(700);
  c = await centered('1');
  assert(c.x > 0.3 && c.x < 0.7 && c.y > 0.25 && c.y < 0.85, '초점(유나)이 화면 중앙 근처에 없다 ' + JSON.stringify(c));
  assert.equal(await page.evaluate(() => document.querySelector('.chip.focus')?.dataset.char), '1');
  await page.screenshot({ path: out('m1-t176-focus1.png') });
  await page.keyboard.press('2');                                // 숫자키 전환
  assert.equal(await page.evaluate(() => window.__wl.focus.char), '2');
  await sleep(400);

  // t177 → t184 스텝(트윈·걷기 애니 경로) — 장면 재현 검사는 B6 몫, 여기선 오류 0 + 스냅샷
  for (let t = 177; t <= 184; t++) {
    await page.evaluate(() => window.__wl.playback.step(1));
    await sleep(320);
    const cur = await page.evaluate(() => window.__wl.playback.cur.turn);
    assert.equal(cur, t);
    if (t === 179 || t === 182 || t === 184) await page.screenshot({ path: out(`m1-t${t}.png`) });
  }
  // 새로 보이는 몹 검사: t176 에 고블린 m0 이 수나 시야 안(계획 §7 "고블린 m0 등장")
  const mobVisible = await page.evaluate(() => {
    const a = window.__wl; a.playback.setIdx(a.frameOfTurn(176), 'seek');
    const f = a.playback.cur, v = a.scene.visibleSet('2'), m = f.monsters.find(m => m.id === 0);
    return v.has(m.x + ',' + m.y);
  });
  assert.equal(mobVisible, true, 't176 고블린 m0 이 수나 시야 안이어야 한다');

  // 층 전이: t14(마을) → level(1층) 프레임 → 무대 교체
  await page.evaluate(() => { const a = window.__wl; a.playback.setIdx(a.frameOfTurn(14), 'seek'); });
  await sleep(150);
  await page.evaluate(() => window.__wl.playback.step(1));
  await sleep(300);
  const lv = await page.evaluate(() => ({ kind: window.__wl.playback.cur.kind, depth: window.__wl.playback.cur.level.depth }));
  assert.deepEqual(lv, { kind: 'level', depth: 1 });
  await page.screenshot({ path: out('m1-level1-start.png') });
  await page.evaluate(() => window.__wl.playback.setIdx(0, 'seek'));
  await sleep(300);
  await page.screenshot({ path: out('m1-town-t0.png') });

  // 16× 전체 재생 — rAF 최장 간격으로 프레임 정체를 본다
  const perf = await page.evaluate(async () => {
    const a = window.__wl;
    a.playback.setIdx(0, 'seek'); a.playback.setSpeed(2);
    let frames = 0, worst = 0, last = performance.now(), stop = false;
    const loop = () => { const n = performance.now(); worst = Math.max(worst, n - last); last = n; frames++; if (!stop) requestAnimationFrame(loop); };
    requestAnimationFrame(loop);
    const t0 = performance.now();
    await new Promise(res => { const off = a.playback.on('play', p => { if (!p) { off(); res(); } }); a.playback.play(); });
    stop = true;
    return { ms: Math.round(performance.now() - t0), frames, worst: Math.round(worst), idx: a.playback.idx, fps: Math.round(frames / ((performance.now() - t0) / 1000)) };
  });
  console.log('[smoke] 16× 전체 재생', perf);
  assert.equal(perf.idx, 251, '끝까지 재생');
  assert(perf.worst < 400, '프레임 정체 ' + perf.worst + 'ms');
  await page.screenshot({ path: out('m1-end.png') });

  assert.deepEqual(errors, [], '브라우저 오류');
  ok = true;
} finally {
  await browser.close();
  if (server) server.kill();
}
if (!ok) process.exit(1);
console.log('SMOKE PASS (M1) — 스냅샷:', outDir);

// 스모크 — 빌드 산출물을 vite preview 로 띄우고 헤드리스 Edge(playwright-core, channel msedge — 브라우저 다운로드 없음)로
// 대표 판(seed 257573)을 재생한다. LLM 0콜. 실행: cd game && npm run build && npm run smoke
//   WL_GAME_URL=http://127.0.0.1:8000/game/  → 론처(launcher.py) 상대로 검사(preview 안 띄움). dev 서버(npx vite)도 같은 방식
//   WL_RUN=runs/….jsonl                    → 다른 판
//   WL_PORT=4199                           → preview 포트
//   WL_STATIC=1                            → 정적 배포 검사(2026-09-12): dist-static/ 을 `vite preview --mode static` 으로(론처·리포 서빙 없음,
//                                            판은 static-bundle.mjs 가 복사한 것만 — 기본 판이 목록에 있어야 한다). npm run smoke:static
//
// 검사 구조(B6): 검사 하나가 실패해도 멈추지 않고 다음 검사를 계속한다. 각 검사는 check('한글 이름', fn) 로 감싸고,
// 실패는 fails 목록에 모아 마지막에 한꺼번에 낸다 — 통합자가 "무엇이 남았는지" 한 번에 본다.
// 치명(페이지가 안 뜸·판이 안 열림)만 즉시 중단한다.
//
// Phase A(M1) 검사: 프레임 수·초점 기본값·칩 3개·칩 클릭 전환 ≤300ms(+여유)·카메라가 초점을 봄·t176→t184 스텝·층 전이·
// 16× 전체 재생 프레임 정체·콘솔 오류 0.
// Phase B6(M2/M3) 검사 — 계획 §7 장면 재현, 초점=수나(봇2). 훅 계약(README·카드 지시):
//   B1 초점 카드  #focusCard .fc[data-char] · .fc-hp("10/10") · .fc-bones
//   B2 말풍선·로그 #overlay .bubble[data-char](.proposal/.focus) · .stage-dir[data-char] · #log .grp[data-turn] 안 .say/.rsn/.ev/.dir/.give
//   B3 건네기     씬 오브젝트 setName("handoff") — give 프레임 뒤 400ms 존재
//   B4 밝기       setName("fog") · window.__wlFog = { level, focus, unknown, seen, visible, draws }
//   B5 라이브     #hud .live-hud · /api/status 의 game 필드(론처 상대일 때만)
//   (1) t176 seek: 유나 말풍선·수나 HP 10/10·안개 통계·안개 오브젝트  (2) t178→t179 step: 건네기 아이콘 100ms 안 등장·600ms 뒤 소멸·
//   로그 .give "가죽 갑옷"·수나 말풍선 "이거 입고"·.fc-bones "물건을 건넴"  (3) t181 "처치"  (4) t182 지문 "머리를 거칠게 쓰다듬으며"
//   (5) t184 수나 "동행"  (6) t1 .bubble.proposal  (7) 초점=미나 → .fc[data-char="3"]·__wlFog.focus  (8) 마을 t5 unknown===0
//   (9) 16× 전체 재생 worst<400ms·로그 그룹 ≤94  (10) 브라우저 오류 0. 스냅샷 verify/out/m1-*.png · m2-*.png
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

/* ───────────── 검사 장부 — 실패해도 계속, 마지막에 한꺼번에 ───────────── */
const passes = [], fails = [], skips = [];
async function check(name, fn) {
  try {
    const note = await fn();
    passes.push(name); console.log('[smoke] PASS', name, note ? '— ' + note : '');
  } catch (e) {
    const msg = (e && e.message || String(e)).split('\n')[0];
    fails.push(`${name}: ${msg}`); console.log('[smoke] FAIL', name, '—', msg);
  }
}
const skip = (name, why) => { skips.push(`${name}: ${why}`); console.log('[smoke] SKIP', name, '—', why); };

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
const STATIC = !!process.env.WL_STATIC;          // 정적 배포 검사 — dist-static/ · --mode static · 루트 서빙('/game/' 접두 없음)
if (!base) {
  if (!fs.existsSync(path.join(gameDir, STATIC ? 'dist-static' : 'dist', 'index.html'))) {
    const b = spawnSync(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['run', STATIC ? 'build:static' : 'build'], { cwd: gameDir, stdio: 'inherit', shell: process.platform === 'win32' });
    if (b.status !== 0) throw new Error('build 실패');
  }
  server = spawn(process.execPath, [path.join(gameDir, 'node_modules', 'vite', 'bin', 'vite.js'), 'preview', ...(STATIC ? ['--mode', 'static'] : []),
    '--port', String(PORT), '--strictPort', '--host', '127.0.0.1'], { cwd: gameDir, stdio: ['ignore', 'pipe', 'pipe'] });
  server.stderr.on('data', d => process.stderr.write('[preview] ' + d));
  base = `http://127.0.0.1:${PORT}/` + (STATIC ? '' : 'game/');
  await waitHttp(base);
}
if (!base.endsWith('/')) base += '/';

const { chromium } = await import('playwright-core');
const browser = await chromium.launch({ headless: true, ...(process.platform === 'win32' ? { channel: 'msedge' } : {}) });
const errors = [];
let fatal = null;
let navs = 0;                                                    // 메인 프레임 탐색 횟수(1 초과 = 도중 재로드, dev HMR 등)
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  page.on('framenavigated', f => { if (f === page.mainFrame()) navs++; });
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
  page.on('response', r => { if (r.status() >= 400 && !/favicon/.test(r.url())) errors.push(`http ${r.status()} ${r.url()}`); });
  page.on('requestfailed', r => errors.push('requestfailed ' + r.url() + ' ' + (r.failure() && r.failure().errorText)));

  /* ── 페이지 도우미 ── */
  const seekTurn = async (t, settle = 400) => {            // 임의 점프(seek = 스냅)
    await page.evaluate(t => { const a = window.__wl; a.playback.setIdx(a.frameOfTurn(t), 'seek'); }, t);
    await sleep(settle);
  };
  const stepTo = async (t, settle = 320) => {              // 한 틱 전진(step = 연출) 뒤 턴 확인
    await page.evaluate(() => window.__wl.playback.step(1));
    await sleep(settle);
    const cur = await page.evaluate(() => window.__wl.playback.cur.turn);
    assert.equal(cur, t, `step 뒤 턴이 ${t} 가 아니다(${cur})`);
  };
  const text = sel => page.evaluate(s => { const n = document.querySelector(s); return n ? (n.textContent || '').trim() : null; }, sel);
  const count = sel => page.evaluate(s => document.querySelectorAll(s).length, sel);
  const fog = () => page.evaluate(() => window.__wlFog ? { ...window.__wlFog } : null);
  const sceneHas = name => page.evaluate(n => !!(window.__wl.scene.children && window.__wl.scene.children.getByName(n)), name);
  const mustText = async (sel, needle, what) => {          // 셀렉터가 있고 텍스트에 needle 이 든다
    const s = await text(sel);
    assert.notEqual(s, null, `${what || sel} 없음`);
    assert(s.includes(needle), `${what || sel} 텍스트에 "${needle}" 없음: "${s.slice(0, 80)}"`);
    return s;
  };
  const centered = async (char) => page.evaluate(c => {
    const a = window.__wl, p = a.scene.feetOf(c), s = a.scene.project(p.x, p.y);
    const w = a.dom.stage.clientWidth, h = a.dom.stage.clientHeight;
    return { x: s.x / w, y: s.y / h };
  }, char);
  const inMiddle = c => c.x > 0.3 && c.x < 0.7 && c.y > 0.25 && c.y < 0.85;

  /* ── 치명: 판이 열려야 그 다음이 있다 ── */
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

  /* ═══════════════ M1(Phase A) ═══════════════ */
  await check('M1 판 기본(프레임 252·t176·초점 2·칩 3·층 2)', () => {
    assert.equal(info.frames, 252, '프레임 수(level 2 + tick 250)');
    assert.equal(info.turn, 176); assert.equal(info.focus, '2'); assert.equal(info.chips, 3); assert.equal(info.levels, 2);
  });
  await check('M1 카메라가 초점(수나)을 본다', async () => {
    const c = await centered('2');
    assert(inMiddle(c), '초점(수나)이 화면 중앙 근처에 없다 ' + JSON.stringify(c));
    await page.screenshot({ path: out('m1-t176-focus2.png') });
  });
  await check('M1 칩 클릭 전환 ≤300ms(+여유)·카메라 유나', async () => {
    const t0 = Date.now();
    await page.click('.chip[data-char="1"]');
    await page.waitForFunction(() => window.__wl.focus.char === '1', null, { timeout: 3000 });
    const dt = Date.now() - t0;
    assert(dt <= 500, '칩 클릭 전환이 느리다 ' + dt + 'ms');
    await sleep(700);
    const c = await centered('1');
    assert(inMiddle(c), '초점(유나)이 화면 중앙 근처에 없다 ' + JSON.stringify(c));
    assert.equal(await page.evaluate(() => document.querySelector('.chip.focus')?.dataset.char), '1');
    await page.screenshot({ path: out('m1-t176-focus1.png') });
    return dt + 'ms';
  });
  await check('M1 숫자키 초점 전환', async () => {
    await page.keyboard.press('2');
    assert.equal(await page.evaluate(() => window.__wl.focus.char), '2');
    await sleep(400);
  });
  await page.evaluate(() => window.__wl.focus.set('2'));      // 검사가 실패했어도 이후는 초점=수나로

  /* ═══════════════ M2 (1) t176 seek — 말풍선·초점 카드·안개 ═══════════════ */
  await seekTurn(176);
  await page.screenshot({ path: out('m2-t176.png') });
  await check('M2-1a t176 유나 말풍선(#overlay .bubble[data-char="1"])', async () => {
    assert(await count('#overlay .bubble[data-char="1"]') >= 1, '말풍선 없음');
  });
  await check('M2-1b t176 초점 카드 수나 HP "10/10"', async () => {
    await mustText('#focusCard .fc[data-char="2"] .fc-hp', '10/10', '.fc[data-char="2"] .fc-hp');
  });
  await check('M2-1c t176 안개 통계(__wlFog.unknown>0·draws≥1·focus 2)', async () => {
    const f = await fog();
    assert(f, 'window.__wlFog 없음');
    assert(f.unknown > 0, 'unknown 이 0 (1층인데 미지 칸이 없다) ' + JSON.stringify(f));
    assert(f.draws >= 1, 'draws < 1 ' + JSON.stringify(f));
    assert.equal(f.focus, '2', '__wlFog.focus');
    return `unknown ${f.unknown} seen ${f.seen} visible ${f.visible} draws ${f.draws}`;
  });
  await check('M2-1d t176 안개 그래픽(getByName("fog"))', async () => {
    assert(await sceneHas('fog'), '씬에 "fog" 오브젝트 없음');
  });

  /* ═══════════════ M1 t177→t184 스텝(트윈·걷기 애니 경로) ═══════════════ */
  await check('M1 t177→t184 스텝', async () => {
    for (let t = 177; t <= 184; t++) {
      await stepTo(t);
      if (t === 179 || t === 182 || t === 184) await page.screenshot({ path: out(`m1-t${t}.png`) });
    }
  });
  await check('M1 t176 고블린 m0 이 수나 시야 안', async () => {
    const mobVisible = await page.evaluate(() => {
      const a = window.__wl; a.playback.setIdx(a.frameOfTurn(176), 'seek');
      const f = a.playback.cur, v = a.scene.visibleSet('2'), m = f.monsters.find(m => m.id === 0);
      return !!(m && v && v.has(m.x + ',' + m.y));
    });
    assert.equal(mobVisible, true, 't176 고블린 m0 이 수나 시야 안이어야 한다');
  });

  /* ═══════════════ M2 (2) t178→t179 — 건네기 트윈·로그·말풍선·관계 뼈 ═══════════════ */
  await seekTurn(178);
  await check('M2-2a t179 건네기 아이콘 100ms 안 등장·600ms 뒤 소멸', async () => {
    const r = await page.evaluate(async () => {
      const a = window.__wl, has = () => !!(a.scene.children && a.scene.children.getByName('handoff'));
      const raf = () => new Promise(r => requestAnimationFrame(r));
      const t0 = performance.now();
      a.playback.step(1);
      let seenAt = has() ? 0 : -1;
      while (seenAt < 0 && performance.now() - t0 < 100) { await raf(); if (has()) seenAt = Math.round(performance.now() - t0); }
      await new Promise(r => setTimeout(r, Math.max(0, 300 - (performance.now() - t0))));
      const aliveAt300 = has();
      await new Promise(r => setTimeout(r, Math.max(0, 600 - (performance.now() - t0))));
      return { turn: a.playback.cur.turn, seenAt, aliveAt300, goneAt600: !has() };
    });
    assert.equal(r.turn, 179, 'step 뒤 턴');
    assert(r.seenAt >= 0, '100ms 안에 "handoff" 오브젝트가 안 나타남');
    assert(r.goneAt600, '600ms 뒤에도 "handoff" 오브젝트가 남아 있음');
    return `등장 ${r.seenAt}ms · 300ms 시점 ${r.aliveAt300 ? '있음' : '없음'} · 600ms 뒤 소멸`;
  });
  // 스냅샷용 두 번째 패스(위 검사는 타이밍만) — step 직후 찍어 날아가는 아이콘을 담는다
  await seekTurn(178);
  await page.evaluate(() => window.__wl.playback.step(1));
  await page.screenshot({ path: out('m2-t179-handoff.png') });
  await sleep(600);
  await page.screenshot({ path: out('m2-t179.png') });
  await check('M2-2b t179 로그 건네기 줄(.grp[data-turn="179"] .give "가죽 갑옷")', async () => {
    await mustText('#log .grp[data-turn="179"] .give', '가죽 갑옷');
  });
  await check('M2-2c t179 수나 말풍선 "이거 입고"', async () => {
    await mustText('#overlay .bubble[data-char="2"]', '이거 입고');
  });
  await check('M2-2d t179 초점 카드 관계 뼈 "물건을 건넴"', async () => {
    await mustText('#focusCard .fc[data-char="2"] .fc-bones', '물건을 건넴');
  });

  /* ═══════════════ M2 (3)(4)(5) t181 처치 · t182 지문 · t184 동행 ═══════════════ */
  await check('M2-3 t181 로그 "처치"', async () => {
    await stepTo(180); await stepTo(181);
    await page.screenshot({ path: out('m2-t181.png') });
    await mustText('#log .grp[data-turn="181"]', '처치');
  });
  await check('M2-4 t182 지문 "머리를 거칠게 쓰다듬으며"', async () => {
    const cur = await page.evaluate(() => window.__wl.playback.cur.turn);
    if (cur !== 182) { await seekTurn(181, 200); await stepTo(182); }
    await page.screenshot({ path: out('m2-t182.png') });
    const needle = '머리를 거칠게 쓰다듬으며';
    const a = await text('#overlay .stage-dir[data-char="1"]');
    const b = await text('#log .grp[data-turn="182"] .dir');
    assert((a && a.includes(needle)) || (b && b.includes(needle)),
      `지문 없음 — overlay: ${a === null ? '(없음)' : JSON.stringify(a.slice(0, 60))} · log .dir: ${b === null ? '(없음)' : JSON.stringify(b.slice(0, 60))}`);
    return a && a.includes(needle) ? 'overlay .stage-dir' + (b && b.includes(needle) ? ' + log .dir' : '') : 'log .dir';
  });
  await check('M2-5 t184 로그 수나 동행 줄("동행")', async () => {
    const cur = await page.evaluate(() => window.__wl.playback.cur.turn);
    if (cur !== 182) await seekTurn(182, 200);
    await stepTo(183); await stepTo(184);
    await page.screenshot({ path: out('m2-t184.png') });
    await mustText('#log .grp[data-turn="184"]', '동행');
  });

  /* ═══════════════ M2 (6)(7)(8) t1 제안 · 초점=미나 · 마을 t5 ═══════════════ */
  await check('M2-6 t1 제안 말풍선(.bubble.proposal — 유나)', async () => {
    await seekTurn(1);
    await page.screenshot({ path: out('m2-t1-proposal.png') });
    const who = await page.evaluate(() => [...document.querySelectorAll('#overlay .bubble.proposal')].map(n => n.dataset.char));
    assert(who.length >= 1, '.bubble.proposal 없음');
    return 'char ' + who.join(',');
  });
  await check('M2-7 초점=미나 → .fc[data-char="3"]·__wlFog.focus "3"', async () => {
    await page.keyboard.press('3');
    await page.waitForFunction(() => window.__wl.focus.char === '3', null, { timeout: 3000 });
    await sleep(500);
    await page.screenshot({ path: out('m2-focus3.png') });
    assert(await count('#focusCard .fc[data-char="3"]') >= 1, '.fc[data-char="3"] 없음');
    const f = await fog();
    assert(f, 'window.__wlFog 없음');
    assert.equal(f.focus, '3', '__wlFog.focus');
  });
  await page.evaluate(() => window.__wl.focus.set('2'));
  await sleep(300);
  await check('M2-8 마을 t5 — 안개 미지 칸 0', async () => {
    await seekTurn(5);
    await page.screenshot({ path: out('m2-town-t5.png') });
    const f = await fog();
    assert(f, 'window.__wlFog 없음');
    assert.equal(f.unknown, 0, '마을인데 unknown ≠ 0 ' + JSON.stringify(f));
    return `unknown ${f.unknown} seen ${f.seen} visible ${f.visible}`;
  });

  /* ═══════════════ M1 층 전이 ═══════════════ */
  await check('M1 층 전이 t14 → level(1층) 프레임', async () => {
    await seekTurn(14, 150);
    await page.evaluate(() => window.__wl.playback.step(1));
    await sleep(300);
    const lv = await page.evaluate(() => ({ kind: window.__wl.playback.cur.kind, depth: window.__wl.playback.cur.level.depth }));
    assert.deepEqual(lv, { kind: 'level', depth: 1 });
    await page.screenshot({ path: out('m1-level1-start.png') });
    await page.evaluate(() => window.__wl.playback.setIdx(0, 'seek'));
    await sleep(300);
    await page.screenshot({ path: out('m1-town-t0.png') });
  });

  await check('도트 에셋 로드 · 지형 변형 · 미등록 종류 폴백', async () => {
    const r = await page.evaluate(() => {
      const a = window.__wl, s = a.scene;
      a.playback.setIdx(a.frameOfTurn(176), 'seek');
      return { frames: ['wl-terrain', 'wl-goblin', 'wl-spider', 'wl-props', 'wl-traps'].map(k => s.textures.get(k).frameTotal - 1),
        tiles: [...new Set(s.ground.layer.data.flat().map(t => t.index).filter(n => n >= 0))],
        unknown: s.visualOf('mob:미등록'), known: s.visualOf('feat:chest'),
        goblin: s.children.getByName('mob-0')?.texture.key };
    });
    assert.deepEqual(r.frames, [8, 12, 12, 8, 4]);
    assert(r.tiles.filter(i => i < 4).length >= 3, '바닥 변형 부족');
    assert.equal(r.unknown.texture, 'tiny');
    assert.equal(r.known.texture, 'wl-props');
    assert.equal(r.goblin, 'wl-goblin');
  });
  await check('몬스터 두 종류 표시 · 숨은 몬스터/함정 비노출 · 이동 애니와 시킹 정지', async () => {
    const r = await page.evaluate(() => {
      const a = window.__wl, kinds = new Set(), leaks = [], movement = [];
      let spiderIdx = -1, spiderSpace = -1;
      for (let i = 1; i < a.run.frames.length; i++) {
        const f = a.run.frames[i], p = a.run.frames[i - 1];
        if (f.levelIdx !== p.levelIdx) continue;
        a.playback.setIdx(i - 1, 'seek'); a.playback.step(1);
        const vis = a.scene.visibleSet(a.focus.char);
        for (const m of f.monsters) {
          const sprite = a.scene.children.getByName('mob-' + m.id);
          if (m.alive && (m.concealed || (vis && !vis.has(m.x + ',' + m.y)))) {
            if (sprite) leaks.push([f.turn, m.id]);
          } else if (m.alive && sprite) {
            kinds.add(sprite.texture.key);
            if (sprite.texture.key === 'wl-spider') {
              const space = Math.min(...f.bots.filter(b => b.alive && !b.won).map(b => (b.x - m.x) ** 2 + (b.y - m.y) ** 2));
              if (space > spiderSpace && space <= 10) { spiderIdx = i; spiderSpace = space; }
            }
            const prev = p.monsters.find(v => v.id === m.id);
            if (prev && (prev.x !== m.x || prev.y !== m.y) && sprite.anims.isPlaying) movement.push(sprite.anims.currentAnim.key);
          }
        }
        for (const tr of f.traps) if (tr.hidden && a.scene.children.getByName(`trap-${tr.x},${tr.y}`)) {
          leaks.push([f.turn, 'hidden trap', tr.x, tr.y]);
        }
      }
      a.playback.setIdx(a.frameOfTurn(176), 'seek');
      const stopped = a.scene.children.list.filter(o => o.name?.startsWith('mob-')).every(o => !o.anims.isPlaying);
      return { kinds: [...kinds], leaks, movement: [...new Set(movement)], stopped, spiderIdx };
    });
    assert(r.kinds.includes('wl-goblin') && r.kinds.includes('wl-spider'), JSON.stringify(r.kinds));
    assert.deepEqual(r.leaks, []);
    assert(r.movement.length >= 2, '몬스터 걷기 애니 없음');
    assert(r.stopped, '시킹 뒤 걷기가 계속됨');
    await sleep(500);
    await page.screenshot({ path: out('world-combat.png') });
    if (r.spiderIdx >= 0) {
      await page.evaluate(i => window.__wl.playback.setIdx(i, 'seek'), r.spiderIdx);
      await sleep(500);
      await page.screenshot({ path: out('world-spider.png') });
    }
    return r.movement.join(', ');
  });

  /* ═══════════════ M1 + M2 (9) 16× 전체 재생 — 안개·말풍선·로그가 켜진 채로 ═══════════════ */
  let perf = null;
  await check('M1 16× 전체 재생 끝까지·프레임 정체 <400ms', async () => {
    perf = await page.evaluate(async () => {
      const a = window.__wl;
      a.playback.setIdx(0, 'seek'); a.playback.setSpeed(2);
      let frames = 0, worst = 0, last = performance.now(), stop = false;
      const loop = () => { const n = performance.now(); worst = Math.max(worst, n - last); last = n; frames++; if (!stop) requestAnimationFrame(loop); };
      requestAnimationFrame(loop);
      const t0 = performance.now();
      await new Promise(res => { const off = a.playback.on('play', p => { if (!p) { off(); res(); } }); a.playback.play(); });
      stop = true;
      return { ms: Math.round(performance.now() - t0), frames, worst: Math.round(worst), idx: a.playback.idx,
               fps: Math.round(frames / ((performance.now() - t0) / 1000)), logGroups: document.querySelectorAll('#log .grp').length,
               fog: window.__wlFog ? { ...window.__wlFog } : null };
    });
    console.log('[smoke] 16× 전체 재생', perf);
    await page.screenshot({ path: out('m1-end.png') });
    await page.screenshot({ path: out('m2-end.png') });
    assert.equal(perf.idx, 251, '끝까지 재생');
    assert(perf.worst < 400, '프레임 정체 ' + perf.worst + 'ms');
    return `worst ${perf.worst}ms · ${perf.fps}fps · ${perf.ms}ms`;
  });
  await check('M2-9 16× 재생 뒤 로그 그룹 수 ≤ 94', () => {
    assert(perf, '전체 재생이 안 돌았다(위 검사 참조)');
    assert(perf.logGroups >= 1, '로그 그룹(#log .grp)이 없다');
    assert(perf.logGroups <= 94, '로그 그룹이 너무 많다 ' + perf.logGroups);
    return perf.logGroups + '개';
  });

  /* ═══════════════ B5 라이브·배포 — 론처 상대일 때만 game 필드, 라이브일 때만 배지 ═══════════════ */
  if (STATIC) skip('B5 /api/status 응답', '정적 배포 — 론처 없음(/api/status 는 404 가 정상)');
  else await check('B5 /api/status 응답(론처면 game 필드)', async () => {
    const r = await fetch(new URL('/api/status', base));
    assert(r.ok, 'HTTP ' + r.status);
    const j = await r.json();
    if (j.dev) return 'dev 더미(론처 아님 — game 필드 검사 생략)';
    assert('game' in j, '/api/status 에 game 필드 없음: ' + JSON.stringify(j).slice(0, 120));
    return 'game=' + JSON.stringify(j.game).slice(0, 80);
  });
  const live = await page.evaluate(() => !!window.__wl.live);
  if (live) {
    await check('B5 라이브 배지(#hud .live-hud "LIVE · t…")', async () => { await mustText('#hud .live-hud', 'LIVE'); });
  } else skip('B5 라이브 배지(#hud .live-hud)', '리플레이 판(라이브 아님) — 론처 [L] 판에서만 검사 가능');

  /* ═══════════════ 관전 UI — 표시 필터가 기록을 지우지 않고, 배치 변경이 카메라를 깨지 않는다 ═══════════════ */
  await seekTurn(179);
  await check('UI 이야기/모든 기록 전환 · 원문 보존', async () => {
    const before = await page.locator('#log').textContent();
    assert.equal(await page.locator('#log').getAttribute('data-view'), 'story');
    assert.equal(await page.locator('#log .rsn').last().isVisible(), false);
    await page.locator('[data-log-view="all"]').click();
    assert.equal(await page.locator('#log .rsn').last().isVisible(), true);
    assert.equal(await page.locator('#log').textContent(), before);
    await page.locator('[data-log-view="story"]').click();
    assert.equal(await page.locator('#log').textContent(), before);
  });
  await check('UI 캐릭터 설정·관계 횟수 펼침 · 키보드 초점 선택', async () => {
    assert.equal(await page.locator('.fc-profile').getAttribute('open'), null);
    await page.locator('.fc-profile summary').click();
    assert.equal(await page.locator('.fc-sheet').isVisible(), true);
    await page.locator('.fc-profile summary').click();
    assert.equal(await page.locator('.fc-history').first().getAttribute('open'), null);
    await page.locator('.fc-history summary').first().click();
    assert.equal(await page.locator('.fc-bones').first().isVisible(), true);
    await page.locator('.fc-history summary').first().click();
    const wasPlaying = await page.evaluate(() => window.__wl.playback.playing);
    await page.locator('.chip[data-char="1"]').press('Space');
    assert.equal(await page.locator('.chip[data-char="1"]').getAttribute('aria-pressed'), 'true');
    assert.equal(await page.evaluate(() => window.__wl.playback.playing), wasPlaying);
  });
  await check('UI 기록 접기 · 캔버스 크기 동기화 · 390px 모바일', async () => {
    const height = () => page.locator('#stage').evaluate(e => e.clientHeight);
    const expanded = await height();
    await page.locator('#bLog').click();
    await page.waitForFunction(h => document.querySelector('#stage').clientHeight > h + 30, expanded);
    assert(await height() > expanded + 30);
    await page.waitForFunction(() => Math.abs(window.__wl.game.scale.height - document.querySelector('#stage').clientHeight) <= 1);
    assert.equal(await page.locator('#bLog').getAttribute('aria-expanded'), 'false');
    await page.screenshot({path: out('ui-stage-expanded.png')});
    await page.locator('#bLog').click();
    for (const width of [1024, 768, 390]) {
      await page.setViewportSize({width, height: 844});
      await page.waitForFunction(() => Math.abs(window.__wl.game.scale.width - document.querySelector('#stage').clientWidth) <= 1);
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${width}px 가로 넘침`);
      assert(await height() >= 240, `${width}px 무대가 너무 작음`);
      await page.waitForFunction(() => {
        const labels = ['#hud', '#sceneCaption'].map(s => document.querySelector(s).getBoundingClientRect());
        return [...document.querySelectorAll('#overlay .bubble')].every(e => {
          if (getComputedStyle(e).visibility === 'hidden') return true;
          const b = e.getBoundingClientRect();
          return labels.every(r => b.right <= r.left || b.left >= r.right || b.bottom <= r.top || b.top >= r.bottom);
        });
      });
      await page.screenshot({path: out(`ui-${width}.png`), fullPage: width <= 768});
    }
    await page.setViewportSize({width: 1280, height: 800});
    await page.waitForFunction(() => Math.abs(window.__wl.game.scale.width - document.querySelector('#stage').clientWidth) <= 1);
    await page.locator('#side').evaluate(e => { e.scrollTop = 0; });
    await page.screenshot({path: out('ui-desktop.png')});
  });

  /* ═══════════════ 도감·수첩 창(D63, 2026-09-13) — 별개 창, 재생 위치까지 쓴 것만 ═══════════════ */
  await check('도감·수첩 창 열기 · 도감 카드·캐릭터 줄 · 수첩 장(재생 위치 존중) · Esc', async () => {
    await page.locator('#codexBtn').click();
    await page.waitForFunction(() => document.querySelector('#codex')?.dataset.open === '1', null, { timeout: 3000 });
    const cards = await page.locator('#codex .cx-card').count();
    assert(cards >= 1, '도감 카드 0');
    assert((await page.locator('#codex .cx-row').count()) >= cards, '캐릭터 줄 없음');
    await page.locator('#codex .cx-tab[data-tab="notebook"]').click();
    await seekTurn(1);                                            // 아직 층을 안 떠남 → 장 0
    await page.waitForFunction(() => document.querySelectorAll('#codex .cx-page').length === 0, null, { timeout: 3000 });
    const hasNotebook = await page.evaluate(() => !!(window.__wl.run && window.__wl.run.meta && window.__wl.run.meta.notebook));
    let note = `카드 ${cards}`;
    if (hasNotebook) {
      await page.evaluate(() => { const a = window.__wl; a.playback.setIdx(a.playback.last, 'seek'); });   // 끝 → 층을 떠나며 쓴 장
      await page.waitForFunction(() => document.querySelectorAll('#codex .cx-page').length >= 1, null, { timeout: 3000 });
      note += ` · 수첩 장 ${await page.locator('#codex .cx-page').count()}`;
    } else note += ' · 옛 판(수첩 없음 — 장 0 확인)';
    await page.keyboard.press('Escape');
    await page.waitForFunction(() => document.querySelector('#codex')?.dataset.open === '0', null, { timeout: 3000 });
    return note;
  });

  /* ═══════════════ (10) 브라우저 오류 0 ═══════════════ */
  await check('브라우저 오류 0(pageerror·console.error·HTTP≥400·requestfailed)', () => {
    assert.deepEqual(errors, [], '브라우저 오류');
  });
} catch (e) {
  fatal = e;
} finally {
  await browser.close();
  if (server) server.kill();
}

/* ───────────── 결산 ───────────── */
if (navs > 1) fails.push(`페이지가 도중에 ${navs - 1}번 다시 로드됨(dev 서버 HMR 이 다른 편집에 반응했을 수 있다 — 결과 신뢰 불가, preview 나 hmr:false 로 다시)`);
console.log(`\n[smoke] 통과 ${passes.length} · 실패 ${fails.length} · 생략 ${skips.length} — 스냅샷: ${outDir}`);
if (fatal) { console.error('[smoke] 치명(검사 중단):', fatal && fatal.stack || fatal); }
if (fails.length) { console.error('[smoke] 실패 목록:'); for (const f of fails) console.error('  ✗ ' + f); }
if (errors.length) { console.error('[smoke] 브라우저 오류:'); for (const e of errors.slice(0, 20)) console.error('  ! ' + e); }
if (fatal || fails.length) process.exit(1);
console.log('SMOKE PASS (M1+M2)');

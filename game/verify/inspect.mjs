// 관전 클릭 창 화면 검사(p0512c) — 설계 .orch/drafts/viewer_click_design.md §6.2 관리자 확인 목록 1~12 중 자동화할 수 있는 것.
// smoke.mjs 와 같은 틀: 빌드 산출물을 vite preview 로 띄우고 헤드리스 Edge(playwright-core, channel msedge — 브라우저 다운로드 없음)로 본다.
// 검사 하나가 실패해도 다음으로 간다(check 장부) · 끝나면 브라우저와 서버를 닫는다(상주 없음). LLM 0콜.
// 실행: cd game && npm run build && npm run inspect
//   WL_GAME_URL=http://127.0.0.1:8000/game/ → 띄워 둔 서버 상대(preview 안 띄움) · WL_PORT=4198 → preview 포트
//
// 판: verify/fixtures/lore-click.jsonl — 인물 기록 0콜 판(verify/lore_click_fixture.py 가 verify_viewer_click 의 각본 판에서 만든다).
//     page.route 로 runs/lore-click.jsonl(녹화)·state/lore-click.jsonl(라이브 — 줄을 늘려 가며)에 대 준다. 리포의 runs/·state/ 는 안 건드린다.
//     기대값 = verify/fixtures/lore-click.scenes.json(파이썬 기준 접기 lorebook.fold_stream). 11번 옛 판 = runs/stream-20260909-203709.jsonl(스모크 판).
// 무대 클릭: 씬 공개 API(pickAt·project·worldOf·actorOf·headOf·feetOf)로 화면 안 칸 중앙의 후보를 찾고, 그 자리를 진짜 마우스로 누른다
//     (Phaser 입력 → 클릭 창). 게임 코드에 검사용 전역을 더하지 않았다 — window.__wl(이미 있는 스모크·디버그 훅)만 쓴다.
// 창 훅(Panel.ts 머리): #inspect[data-open] · .ins-chip[data-id] · .ins-call · .ins-real · .ins-facts · .ins-rec[data-key] · .ins-none · .ins-row[data-char] · .ins-cmp
// 눈으로 볼 것(점선 고리 모양·창 자리·건물 그림)은 SKIP 에 이유를 남기고 스냅샷을 verify/out/inspect-*.png 로 남긴다.
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
const FIX = fs.readFileSync(path.join(here, 'fixtures', 'lore-click.jsonl'), 'utf8');
const FIX_LINES = FIX.trimEnd().split('\n');
const SC = JSON.parse(fs.readFileSync(path.join(here, 'fixtures', 'lore-click.scenes.json'), 'utf8'));
const RUN = 'runs/lore-click.jsonl', LIVE = 'state/lore-click.jsonl', OLD_RUN = 'runs/stream-20260909-203709.jsonl';
const PORT = Number(process.env.WL_PORT || 4198);
const sleep = ms => new Promise(r => setTimeout(r, ms));
const TOWN = SC.levels.find(l => l.town), DUNGEON = SC.levels.find(l => !l.town);
/** 그 층의 틱 프레임 번호들(층 줄 프레임 다음부터 다음 층 줄 앞까지). */
const framesOf = lv => {
  const next = SC.levels.find(l => l.frame > lv.frame), end = next ? next.frame : SC.frames;
  return Array.from({ length: end - lv.frame - 1 }, (_, k) => lv.frame + 1 + k);
};

/* ───────────── 검사 장부 — 실패해도 계속, 마지막에 한꺼번에 ───────────── */
const passes = [], fails = [], skips = [];
async function check(name, fn) {
  try {
    const note = await fn();
    passes.push(name); console.log('[inspect] PASS', name, note ? '— ' + note : '');
  } catch (e) {
    const msg = (e && e.message || String(e)).split('\n')[0];
    fails.push(`${name}: ${msg}`); console.log('[inspect] FAIL', name, '—', msg);
  }
}
const skip = (name, why) => { skips.push(`${name}: ${why}`); console.log('[inspect] SKIP', name, '—', why); };
const nondecreasing = xs => xs.every((v, k) => k === 0 || xs[k - 1] <= v);

async function waitHttp(url, ms = 20000) {
  const t0 = Date.now();
  for (;;) {
    try { const r = await fetch(url); if (r.ok) return; } catch { /* 아직 */ }
    if (Date.now() - t0 > ms) throw new Error('서버가 안 뜬다: ' + url);
    await sleep(200);
  }
}

/* ───────────── 페이지 안 도우미(window.__it) — 씬 공개 API 만 쓴다 ───────────── */
function HELPERS() {
  const a = window.__wl, s = a.scene, canvas = a.game.canvas;
  const T = s.worldOf(1, 0).x - s.worldOf(0, 0).x;                       // 칸 크기(월드 px)
  const raf = () => new Promise(r => requestAnimationFrame(() => r()));
  const tid = t => t.t === 'bot' ? 'b' + t.char : t.t === 'mob' ? 'm' + t.id : t.t === 'feat' ? 'f' + t.id : t.t === 'trap' ? 't' + t.idx
    : t.t === 'exit' ? 'exit' : t.t === 'door' ? t.id : t.t === 'zone' ? 'zone:' + t.id : 'region:' + t.name;   // model.targetId
  const screenOf = (wx, wy) => {
    const p = s.project(wx, wy), r = canvas.getBoundingClientRect();
    return { x: r.left + p.x * r.width / a.game.scale.width, y: r.top + p.y * r.height / a.game.scale.height };
  };
  const onCanvas = p => {                                                  // 화면 안이고 그 점의 맨 위가 캔버스(창·도감 창에 덮이지 않음)
    const r = canvas.getBoundingClientRect();
    return p.x > r.left + 6 && p.y > r.top + 6 && p.x < r.right - 6 && p.y < r.bottom - 6 && document.elementFromPoint(p.x, p.y) === canvas;
  };
  const idsAt = (wx, wy) => s.pickAt(wx, wy).map(q => tid(q.target));
  const same = (u, v) => u.length === v.length && u.every((x, k) => x === v[k]);
  // p0512d: 누를 점이 그림 테두리 경계 위면 안 된다 — SD 그림 틀은 96px(옛 그림 2칸)이라 옆 칸 모험가의 테두리 끝이 이 칸 중앙과 딱 겹친다.
  //   검사가 계산한 점과 Phaser 포인터의 월드 점이 반올림(줌 1.5 = 2/3px 눈금)만큼 달라 그 모험가가 들고 나며 칩 ≠ 후보가 됐다.
  //   화면 3px 둘레(월드 = 3/줌, 최소 3)에서도 후보가 같은 점만 쓴다.
  const steady = (wx, wy, ids) => {
    const m = Math.max(3, 3 / s.cameras.main.zoom);
    return [[m, 0], [-m, 0], [0, m], [0, -m]].every(([dx, dy]) => same(idsAt(wx + dx, wy + dy), ids));
  };
  const at = (wx, wy) => { const p = screenOf(wx, wy), ids = idsAt(wx, wy); return { wx, wy, sx: p.x, sy: p.y, ok: onCanvas(p) && steady(wx, wy, ids), ids }; };
  const OFF = [[0, 0], [10, 0], [-10, 0], [0, 10], [0, -10], [10, 10], [-10, 10], [10, -10], [-10, -10]];
  /** 칸 (x, y) 안에서 누를 점 — 중앙부터 둘레로, 누를 수 있고(ok) 후보에 need 가 다 든 첫 점(없으면 중앙). */
  const pointIn = (x, y, need = []) => {
    for (const [dx, dy] of OFF) {
      const p = at((x + 0.5) * T + dx, (y + 0.5) * T + dy);
      if (p.ok && need.every(id => p.ids.includes(id))) return p;
    }
    return at((x + 0.5) * T, (y + 0.5) * T);
  };
  /** 화면 점(정수 px로 반올림) → 그 점의 월드 좌표에서 본 후보 — 마우스가 실제로 누르는 자리와 같게. */
  const atScreen = (x, y) => {
    const r = canvas.getBoundingClientRect(), cam = s.cameras.main, sx = Math.round(x), sy = Math.round(y);
    const wx = cam.worldView.x + (sx - r.left) * a.game.scale.width / r.width / cam.zoom;
    const wy = cam.worldView.y + (sy - r.top) * a.game.scale.height / r.height / cam.zoom;
    return { ...at(wx, wy), sx, sy };
  };
  /** 화면에 걸친 칸마다 누를 점 하나(pointIn — 중앙이 테두리 경계면 둘레로) · inGrid=false 면 층 밖 여백까지(빈 곳 찾기). */
  const tiles = (inGrid = true) => {
    const L = a.playback.cur.level, wv = s.cameras.main.worldView, outp = [];
    let x0 = Math.floor(wv.x / T), x1 = Math.floor((wv.x + wv.width) / T), y0 = Math.floor(wv.y / T), y1 = Math.floor((wv.y + wv.height) / T);
    if (inGrid) { x0 = Math.max(0, x0); y0 = Math.max(0, y0); x1 = Math.min(L.w - 1, x1); y1 = Math.min(L.h - 1, y1); }
    for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) outp.push({ x, y, ...pointIn(x, y) });
    return outp;
  };
  const settle = async () => { await raf(); await raf(); await raf(); };   // 카메라 worldView 는 렌더 때 갱신된다
  const kind = id => {
    const f = a.playback.cur;
    if (/^b\d+$/.test(id)) return 'bot';
    if (/^m\d+$/.test(id)) { const m = f.monsters.find(x => x.id === Number(id.slice(1))); return m && !m.alive ? 'corpse' : 'mob'; }
    if (/^f\d+$/.test(id)) {
      const ft = f.features.find(x => x.id === Number(id.slice(1))), ty = ft ? ft.type : '';
      return ty === 'npc' ? 'npc' : ty === 'building' ? 'threshold' : ['weapon', 'armor', 'potion', 'boon', 'treasure'].includes(ty) ? 'item' : 'fixture';
    }
    if (/^t\d+$/.test(id)) return 'trap';
    if (id === 'exit') return 'exit';
    if (/^d\d+$/.test(id)) return 'door';
    if (id.startsWith('zone:')) return id.startsWith('zone:c') ? 'corridor' : 'room';
    if (id.startsWith('region:')) return 'region';
    return '?';
  };
  /** 겹침 무리(설계 §1.3): 사람 0 > 몬스터 1(산 것 → 시체 1.5) > 물건·설비 2 > 함정 3 > 문·계단 4 > 장소 5. */
  const rank = id => ({ bot: 0, npc: 0, mob: 1, corpse: 1.5, item: 2, fixture: 2, threshold: 2, trap: 3, exit: 4, door: 4, room: 5, corridor: 5, region: 5 })[kind(id)] ?? 9;
  /** 시점·프레임으로 간다 — 초점이 바뀌면 카메라 팬(300ms)을 기다린다(팬 중엔 시킹이 카메라를 맞추지 않는다). */
  const go = async (i, c) => {
    if (c && a.focus.char !== c) { a.focus.set(c); await new Promise(r => setTimeout(r, 450)); }
    if (i !== null && i !== undefined) a.playback.setIdx(i, 'seek');
    await settle();
  };
  /** 지금 화면 안에서 그 대상을 누를 칸 — 첫째 후보로 잡히는 칸 먼저, 없으면 후보에 든 칸. */
  const spotOf = id => {
    const ts = tiles().filter(t => t.ok);
    return ts.find(t => t.ids[0] === id) || ts.find(t => t.ids.includes(id)) || null;
  };
  window.__it = { T, tid, at, atScreen, pointIn, tiles, settle, kind, rank, go, spotOf };
}

/* ───────────── 서버 ───────────── */
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
  try { await waitHttp(base); } catch (e) { server.kill(); throw e; }
}
if (!base.endsWith('/')) base += '/';

const errors = [];
let quiet = false;                                // 페이지를 닫는 동안 끊기는 요청(라이브 폴링)은 오류로 세지 않는다
let liveText = '';                                // state/lore-click.jsonl 자리에 대 줄 글(라이브 — 늘려 가며)
let browser = null;
let fatal = null;

async function openPage(query) {
  quiet = false;
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  const err = m => { if (!quiet) errors.push(m); };
  page.on('pageerror', e => err('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') err('console: ' + m.text()); });
  page.on('response', r => { if (r.status() >= 400 && !/favicon/.test(r.url())) err(`http ${r.status()} ${r.url()}`); });
  page.on('requestfailed', r => err('requestfailed ' + r.url() + ' ' + (r.failure() && r.failure().errorText)));
  await page.route('**/runs/lore-click.jsonl*', route => route.fulfill({ status: 200, contentType: 'application/x-ndjson; charset=utf-8', body: FIX }));
  await page.route('**/state/lore-click.jsonl*', route => route.fulfill({ status: 200, contentType: 'application/x-ndjson; charset=utf-8', body: liveText }));
  await page.goto(`${base}?${query}`);
  await page.waitForFunction(() => window.__wl && window.__wl.run && window.__wl.playback.idx >= 0 && window.__wl.scene, null, { timeout: 40000 });
  await page.evaluate(HELPERS);
  await sleep(500);
  return page;
}
async function closePage(page) { quiet = true; await page.close(); }   // 다음 openPage 가 다시 켠다(닫은 뒤 늦게 오는 이벤트도 무시)

/* ───────────── Node 쪽 도우미 ───────────── */
const go = (page, i, c) => page.evaluate(([i, c]) => window.__it.go(i, c), [i ?? null, c ?? null]);
const ranks = (page, ids) => page.evaluate(ids => ids.map(id => window.__it.rank(id)), ids);
/** 클릭 창의 지금 내용. */
const panel = page => page.evaluate(() => {
  const r = document.getElementById('inspect');
  if (!r) return { exists: false, open: false, chips: [], recs: [], rows: [], facts: [], secs: [], hist: [] };
  const q = sel => r.querySelector(sel), qa = sel => [...r.querySelectorAll(sel)], tx = n => (n ? (n.textContent || '').trim() : null);
  const on = q('.ins-chip.on'), pov = q('.ins-pov');
  return { exists: true, open: r.dataset.open === '1', chips: qa('.ins-chip').map(e => e.dataset.id), on: on ? on.dataset.id : null,
    call: tx(q('.ins-call')), sub: tx(q('.ins-sub')), real: tx(q('.ins-real')), gone: !!q('.ins-gone'),
    facts: qa('.ins-facts dt').map(e => [tx(e), tx(e.nextElementSibling)]), secs: qa('.ins-sec').map(tx),
    recs: qa('.ins-rec').map(e => [e.dataset.key, tx(e)]), none: tx(q('.ins-none')), hist: qa('.ins-rec summary').map(tx),
    rows: qa('.ins-row').map(e => [e.dataset.char, e.classList.contains('me'), tx(e)]), cmp: tx(q('.ins-cmp')), pov: pov ? pov.dataset.char : null };
});
const fact = (p, k) => (p.facts.find(f => f[0] === k) || [])[1] || '';
const waitOpen = (page, on = true) => page.waitForFunction(o => (document.getElementById('inspect')?.dataset.open === '1') === o, on, { timeout: 3000 });
async function closePanel(page) {
  if ((await panel(page)).open) { await page.keyboard.press('Escape'); await waitOpen(page, false); }
}
async function closeCodex(page) {
  if (await page.evaluate(() => document.querySelector('#codex')?.dataset.open === '1')) {
    await page.click('#codex .cx-close');
    await page.waitForFunction(() => document.querySelector('#codex')?.dataset.open === '0', null, { timeout: 3000 });
  }
}
/** 월드 좌표를 진짜 마우스로 누른다 — 화면 안이고 그 점의 맨 위가 캔버스여야 한다. 누르기 직전의 후보 목록을 돌려준다. */
async function clickWorld(page, wx, wy) {
  const p = await page.evaluate(([wx, wy]) => { const it = window.__it, q = it.at(wx, wy); return it.atScreen(q.sx, q.sy); }, [wx, wy]);
  assert(p.ok, `누를 자리가 화면 밖이거나 다른 요소에 덮였다 (${Math.round(p.sx)}, ${Math.round(p.sy)})`);
  await page.mouse.click(p.sx, p.sy);
  return p.ids;
}
/** 프레임·시점으로 가서 그 대상을 누른다(열린 창은 먼저 닫는다) — 첫째 후보가 아니면 머리 칩으로 고른다. */
async function openTarget(page, frame, focus, id) {
  await go(page, frame, focus);
  await closePanel(page);
  const sp = await page.evaluate(id => window.__it.spotOf(id), id);
  assert(sp, `프레임 ${frame} 초점 ${focus}: 화면 안에서 ${id} 를 누를 칸이 없다`);
  const ids = await clickWorld(page, sp.wx, sp.wy);
  await waitOpen(page);
  if ((await panel(page)).on !== id) await page.click(`#inspect .ins-chip[data-id="${id}"]`);
  const p = await panel(page);
  assert.equal(p.on, id, '고른 대상');
  return { ids, p, sp };
}
/** 화면 안 칸을 프레임·시점마다 훑어, 종류마다 누를 칸 하나(그 종류가 첫째 후보인 칸 먼저)를 찾는다. 다 찾으면 멈춘다. */
const scan = (page, frames, chars, want) => page.evaluate(async ([frames, chars, want]) => {
  const a = window.__wl, it = window.__it, found = {};
  for (const c of chars) {
    for (const i of frames) {
      await it.go(i, c);
      for (const t of it.tiles()) {
        if (!t.ok) continue;
        for (const id of t.ids) {
          const k = it.kind(id), first = id === t.ids[0];
          if (want.includes(k) && (!found[k] || (first && !found[k].first))) {
            found[k] = { kind: k, id, first, frame: i, turn: a.playback.cur.turn, focus: c, wx: t.wx, wy: t.wy, ids: t.ids };
          }
        }
      }
      if (want.every(k => found[k])) return found;
    }
  }
  return found;
}, [frames, chars, want]);
async function openRecords(page) {
  if (!(await page.evaluate(() => document.querySelector('#codex')?.dataset.open === '1'))) {
    await page.click('#codexBtn');
    await page.waitForFunction(() => document.querySelector('#codex')?.dataset.open === '1', null, { timeout: 3000 });
  }
  await page.click('#codex .cx-tab[data-tab="records"]');
}
/** '기록' 탭에서 그 사람을 골라 지금 프레임의 기록 열쇠들(정렬). */
async function recordKeys(page, c) {
  await page.click(`#codex .cx-char[data-char="${c}"]`);
  return page.evaluate(() => [...document.querySelectorAll('#codex .cx-rec')].map(e => e.dataset.key).sort());
}

const KINDS = [['mob', '몬스터'], ['corpse', '시체'], ['trap', '함정'], ['item', '바닥 물건'], ['door', '문'], ['exit', '계단'], ['room', '방'], ['corridor', '통로']];
const SUB = { mob: '몬스터', corpse: '몬스터', trap: '함정', door: '문', exit: '계단', room: '장소', corridor: '장소', npc: '마을 사람', threshold: '건물', region: '마을 구역' };

/** 1 — 던전의 종류마다 눌러 창이 뜨고, 칩이 누른 자리의 후보 그대로(무리 순서)이며 고른 것이 그 대상이다. 줌 1.5·1. */
async function dungeonClicks(page, tag, label) {
  const frames = framesOf(DUNGEON);
  let last = null;
  for (const z of [1.5, 1]) {
    await closePanel(page); await closeCodex(page);
    await go(page, frames[0], SC.party[0]);
    await page.evaluate(z => { window.__wl.scene.setZoom(z); }, z);
    await go(page, null, null);
    const found = await scan(page, frames, SC.party, KINDS.map(k => k[0]));
    last = found;
    for (const [k, word] of KINDS) {
      const f = found[k];
      await check(`1 던전 ${word} 클릭 → 창 (${label} · 줌 ${z})`, async () => {
        assert(f, `판 전체(초점 ${SC.party.join('·')})에서 화면 안에 누를 수 있는 ${word}이(가) 없다`);
        const { ids, p } = await openTarget(page, f.frame, f.focus, f.id);
        assert.equal(await page.evaluate(() => window.__wl.scene.zoom), z, '줌');
        assert.deepEqual(p.chips, ids, `칩 ${p.chips.join(' ')} ≠ 누른 자리의 후보(pickAt) ${ids.join(' ')}`);
        assert(nondecreasing(await ranks(page, p.chips)), '칩 순서가 무리 순서(사람 > 몬스터 > 물건 > 함정 > 문·계단 > 장소)가 아니다: ' + p.chips.join(' '));
        assert(p.call, '머리 이름이 비었다');
        assert(p.facts.length >= 1, '"무엇인가" 칸이 비었다');
        if (SUB[k]) assert(p.sub.includes(SUB[k]), `한 마디 "${p.sub}" 에 "${SUB[k]}" 없음`);
        if (k === 'corpse') assert.equal(fact(p, '상태'), '시체');
        if (k === 'mob') assert.notEqual(fact(p, '상태'), '시체');
        if (k === 'item') assert(fact(p, '설명'), '물건 설명(item_info)이 없다');
        await page.screenshot({ path: out(`inspect-1-${tag}-z${z}-${k}.png`) });
        return `t${f.turn} 초점 ${f.focus} · 칩 ${p.chips.join(' ')} · "${p.call}" ${p.sub}`;
      });
    }
  }
  return last;
}

/** 2 — SD 캐릭터의 머리(발 칸보다 위 줄)를 눌러도 그 사람이 첫째로 잡힌다. */
async function headClick(page, label) {
  await check(`2 SD 캐릭터 머리를 눌러도 그 사람 (${label})`, async () => {
    await closePanel(page);
    const h = await page.evaluate(async frames => {
      const a = window.__wl, s = a.scene, it = window.__it;
      for (const c of a.run.party.map(p => p.char)) {
        for (const i of frames) {
          await it.go(i, c);
          const act = s.actorOf(c), b = a.playback.cur.bots.find(x => x.char === c), hd = s.headOf(c), ft = s.feetOf(c);
          if (!act || !b || !b.alive || !act.sprite.visible || !hd || !ft) continue;
          const wx = ft.x, wy = hd.y + 0.2 * (ft.y - hd.y), p = it.at(wx, wy), row = Math.floor(wy / it.T);
          if (p.ok && row < b.y && p.ids[0] === 'b' + c) return { ...p, frame: i, turn: a.playback.cur.turn, focus: c, row, footRow: b.y };
        }
      }
      return null;
    }, framesOf(DUNGEON).slice(0, 30));
    assert(h, '발 칸보다 위(머리)를 눌러 그 사람이 첫째로 잡히는 장면이 없다 — 그림 맞음(getBounds)이 빠졌을 수 있다');
    await clickWorld(page, h.wx, h.wy);
    await waitOpen(page);
    const p = await panel(page);
    assert.equal(p.on, 'b' + h.focus, '머리를 눌러 고른 대상');
    return `t${h.turn} 초점 ${h.focus} — 발 칸 줄 ${h.footRow} · 누른 줄 ${h.row}`;
  });
}

try {
  const { chromium } = await import('playwright-core');
  browser = await chromium.launch({ headless: true, ...(process.platform === 'win32' ? { channel: 'msedge' } : {}) });

  /* ═══════════════ 인물 기록 판 · 옛 그림 렌더러 ═══════════════ */
  const page = await openPage(`run=${RUN}&focus=${SC.party[0]}&t=0&dungeonArt=off`);
  await check('준비: 픽스처 판이 열린다(프레임 수·파티·인물 기록 판·클릭 창 설치)', async () => {
    const r = await page.evaluate(() => {
      const a = window.__wl;
      return { frames: a.run.frames.length, party: a.run.party.map(p => p.char), people: !!(a.run.meta && (a.run.meta.strangers || a.run.meta.lore)),
               panel: !!document.getElementById('inspect'), open: document.getElementById('inspect')?.dataset.open };
    });
    assert.equal(r.frames, SC.frames, '프레임 수(scenes.json 과 같은 판인가)');
    assert.deepEqual(r.party, SC.party);
    assert(r.people, '인물 기록 판이 아니다');
    assert(r.panel && r.open === '0', '#inspect 가 없거나 처음부터 열려 있다');
    return `프레임 ${r.frames} · 파티 ${r.party.join(',')}`;
  });

  /* ── 8 마을(저작 마을, 줌 0.5): NPC·문턱·구역 ── */
  const TK = [['npc', 'NPC'], ['threshold', '건물 문턱'], ['region', '마을 구역']];
  const town = await scan(page, framesOf(TOWN), SC.party, TK.map(k => k[0]));
  for (const [k, word] of TK) {
    await check(`8 마을 ${word} 클릭 → 맞는 대상 (저작 마을)`, async () => {
      const f = town[k];
      assert(f, `마을 틱 전체에서 화면 안에 누를 수 있는 ${word}이(가) 없다`);
      const { p } = await openTarget(page, f.frame, f.focus, f.id);
      if (TOWN.art) assert.equal(await page.evaluate(() => window.__wl.scene.zoom), 0.5, '저작 마을 줌 0.5');
      assert(p.sub.includes(SUB[k]), `한 마디 "${p.sub}" 에 "${SUB[k]}" 없음`);
      if (k === 'region') assert.equal(p.call, f.id.slice('region:'.length), '구역 이름');
      assert(nondecreasing(await ranks(page, p.chips)), '칩 순서: ' + p.chips.join(' '));
      await page.screenshot({ path: out(`inspect-8-${k}.png`) });
      return `t${f.turn} 초점 ${f.focus} · 칩 ${p.chips.join(' ')} · "${p.call}" ${p.sub}`;
    });
  }
  skip('8 마을 건물 그림(문턱이 아닌 자리)', 'pickAt 은 건물 그림을 후보로 삼지 않는다 — 건물은 문턱 칸으로만 누른다(설계 §9). 그림 자리를 누르면 구역만 잡히는지 눈으로');

  /* ── 6 되감기 ── */
  await check('6 되감기 — 기록을 쓴 틱 앞은 \'모름\', 그 틱부터 글, 다시 앞으로 가면 글', async () => {
    const tried = [];
    for (const r of SC.rewind_none) {
      try { await openTarget(page, r.frame, r.viewer, r.target); } catch (e) { tried.push(`${r.target}@${r.frame}: ${String(e.message).split('\n')[0]}`); continue; }
      let p = await panel(page);
      const rec = p.recs.find(x => x[0] === r.key);
      assert(rec && rec[1].includes(r.text), `그 틱(프레임 ${r.frame})에 글 「${r.text}」 없음: ${JSON.stringify(p.recs)}`);
      await go(page, r.before, null);
      p = await panel(page);
      assert(p.open, '되감았는데 창이 닫혔다');
      assert(!p.recs.some(x => x[0] === r.key), '앞 프레임에 그 기록이 남아 있다');
      assert.equal(p.none, '모름', '앞 프레임은 \'모름\'');
      await go(page, r.frame, null);
      p = await panel(page);
      assert(p.recs.some(x => x[0] === r.key), '다시 앞으로 가면 글이 돌아와야 한다');
      return `${r.target} 초점 ${r.viewer} · 프레임 ${r.before} '모름' → ${r.frame} 「${r.text}」` + (tried.length ? ` (못 누른 후보 ${tried.length})` : '');
    }
    assert.fail('누를 수 있는 장면이 없다: ' + tried.join(' / '));
  });
  await check('6 되감기 — 고쳐 쓴 기록은 앞 프레임에 옛 글·옛 이름, 그 틱부터 새 글 + \'이전 글\'', async () => {
    const r = SC.rewind_edit[0];
    assert(r, 'scenes.json 에 고쳐 쓴 장면이 없다');
    await openTarget(page, r.frame, r.viewer, r.target);
    let p = await panel(page), rec = p.recs.find(x => x[0] === r.key);
    assert(rec && rec[1].includes(r.now.text), `새 글 「${r.now.text}」 없음: ${JSON.stringify(p.recs)}`);
    if (r.now.name) assert(rec[1].includes('이름: ' + r.now.name), '새 이름');
    assert(p.hist.some(h => h.startsWith('이전 글')), '\'이전 글\' 접힌 칸이 없다');
    if (r.target.startsWith('b')) assert.equal(p.call, r.now.name || '낯선 사람', '새 부르는 이름');
    await go(page, r.before, null);
    p = await panel(page); rec = p.recs.find(x => x[0] === r.key);
    assert(rec && rec[1].includes(r.prev.text), `앞 프레임에 옛 글 「${r.prev.text.slice(0, 20)}…」 없음`);
    if (r.prev.name) assert(rec[1].includes('이름: ' + r.prev.name), '옛 이름');
    if (r.target.startsWith('b')) assert.equal(p.call, r.prev.name || '낯선 사람', '옛 부르는 이름');
    return `${r.target} 초점 ${r.viewer} · 프레임 ${r.before} "${r.prev.name}" → ${r.frame} "${r.now.name}"`;
  });

  /* ── 7·12 도감·수첩 창 '기록' 탭 ── */
  const sw = SC.sweep;
  if (!sw) skip('7 쓸어냄 뒤 층 기록이 사라진다', 'scenes.json 에 틱 줄의 sweep 장면이 없다');
  else await check(`7 쓸어냄 뒤 층 기록(${sw.key})이 사라지고 사람·장소 기록은 남는다 — '기록' 탭 t${sw.turn} → 다음 틱`, async () => {
    await closePanel(page);
    await openRecords(page);
    for (const c of sw.gone_from) {
      await go(page, sw.frame, null);
      let keys = await recordKeys(page, c);
      assert(keys.includes(sw.key), `${c}: 쓸기 전 프레임에 ${sw.key} 없음`);
      for (const k of sw.kept[c]) assert(keys.includes(k), `${c}: 쓸기 전 ${k} 없음`);
      await go(page, sw.after, null);
      keys = await recordKeys(page, c);
      assert(!keys.includes(sw.key), `${c}: 쓸어낸 뒤에도 ${sw.key} 가 남았다`);
      for (const k of sw.kept[c]) assert(keys.includes(k), `${c}: 쓸어낸 뒤 ${k} 가 사라졌다`);
    }
    return `${sw.gone_from.join('·')} — 남은 것 ${Object.values(sw.kept).map(v => v.length).join('·')}개`;
  });
  if (!SC.levels.some(l => l.town && l.frame > DUNGEON.frame)) {
    skip('7 실제 원정 결산', '픽스처 판에 마을 귀환(원정 결산)이 없다 — 위 검사는 각본 쓸어냄(verify_viewer_click 의 obj:999)으로 같은 접기 길을 본다. 실제 결산은 원정을 마친 판으로 눈으로');
  }
  await check('12 도감·수첩 창 \'기록\' 탭 = 파이썬 접기(사람마다 · 몇 프레임)', async () => {
    await openRecords(page);
    const seen = [];
    for (const L of SC.ledgers) {
      await go(page, L.frame, null);
      for (const c of SC.party) {
        const keys = await recordKeys(page, c);
        assert.deepEqual(keys, [...L.by[c]].sort(), `t${L.turn} ${c} 의 기록 열쇠`);
      }
      seen.push(`t${L.turn}`);
    }
    await page.screenshot({ path: out('inspect-12-records.png') });
    return seen.join(' · ');
  });
  await closeCodex(page);

  /* ── 1·2·3 던전(옛 그림) ── */
  const oldFound = await dungeonClicks(page, 'old', '옛 그림');
  await headClick(page, '옛 그림');
  for (const o of SC.overlap) {
    await check(`3 겹친 칸 칩 순서 — ${o.want.join(' · ')} (t${o.turn} 초점 ${o.focus})`, async () => {
      await go(page, o.frame, o.focus);
      await closePanel(page);
      const pt = await page.evaluate(([x, y, need]) => window.__it.pointIn(x, y, need), [o.x, o.y, o.want]);
      assert(pt.ok, `칸 (${o.x}, ${o.y}) 안에 겹친 것을 다 잡는 누를 점이 없다 (중앙 후보 ${pt.ids.join(' ')})`);
      const ids = await clickWorld(page, pt.wx, pt.wy);
      await waitOpen(page);
      const p = await panel(page);
      assert.deepEqual(p.chips, ids, `칩 ${p.chips.join(' ')} ≠ 누른 자리의 후보 ${ids.join(' ')}`);
      const pos = o.want.map(id => p.chips.indexOf(id));
      assert(pos.every(n => n >= 0), `칩에 빠진 것: ${o.want.filter((id, k) => pos[k] < 0).join(' ')} (칩 ${p.chips.join(' ')})`);
      assert(nondecreasing(pos), '겹친 것들의 칩 순서: ' + p.chips.join(' '));
      assert(nondecreasing(await ranks(page, p.chips)), '무리 순서(사람 > 몬스터 > 물건 > 함정 > 문·계단 > 장소): ' + p.chips.join(' '));
      await page.screenshot({ path: out(`inspect-3-t${o.turn}.png`) });
      return p.chips.join(' > ');
    });
  }

  /* ── 4·5 초점 전환 · 모두 비교 ── */
  const cs = SC.calls[0];
  if (!cs) skip('4 초점 칩 전환 — 사람 부르는 이름', 'scenes.json 에 시점마다 이름이 갈리는 사람 장면이 없다');
  else {
    await check(`4 초점 칩을 바꾸면 부르는 이름·기록이 그 사람 것으로 (${cs.target} t${cs.turn})`, async () => {
      const self = cs.target.slice(1);
      const order = [cs.writer, ...SC.party.filter(c => c !== cs.writer && c !== self), ...(self !== cs.writer ? [self] : [])];
      await openTarget(page, cs.frame, order[0], cs.target);
      const seen = [];
      for (const [k, c] of order.entries()) {
        if (k > 0) {
          await page.click(`.chip[data-char="${c}"]`);
          await page.waitForFunction(c => window.__wl.focus.char === c, c, { timeout: 3000 });
          await sleep(150);
        }
        const p = await panel(page), want = cs.by[c];
        assert(p.open && p.on === cs.target, `초점 ${c}: 창이 닫혔거나 대상이 바뀌었다`);
        assert.equal(p.call, want.call, `초점 ${c} 의 부르는 이름`);
        if (want.call !== cs.real) assert(p.real && p.real.includes(cs.real), `초점 ${c}: 관전자 이름(${cs.real})이 나란히 없다`);
        if (want.recs === 'self') assert(p.none && p.none.includes('자기 자신'), `초점 ${c}(자기 자신): ${p.none}`);
        else {
          assert(p.secs.includes(`${SC.names[c]}에게는`), `"${SC.names[c]}에게는" 칸이 없다: ${p.secs.join(' / ')}`);
          const keys = Object.keys(want.recs);
          if (!keys.length) assert.equal(p.none, '모름', `초점 ${c}: 기록이 없으면 '모름'`);
          for (const key of keys) {
            const rec = p.recs.find(x => x[0] === key);
            assert(rec && rec[1].includes(want.recs[key]), `초점 ${c} 의 기록 ${key}: ${JSON.stringify(p.recs)}`);
          }
        }
        seen.push(`${c}→${p.call}`);
      }
      await page.screenshot({ path: out('inspect-4-calls.png') });
      return seen.join(' · ');
    });
    await check('5 [모두 비교] — 파티 전원 한 줄씩(파티 순서) · 시점 사람 줄 강조 · 닫았다 열어도 모드 기억 · 다시 누르면 시점 보기', async () => {
      let p = await panel(page);
      assert(p.open && p.on === cs.target, '4번 창이 열려 있지 않다');
      const focus = await page.evaluate(() => window.__wl.focus.char);
      await page.click('#inspect .ins-cmp');
      p = await panel(page);
      assert.deepEqual(p.rows.map(r => r[0]), SC.party, '줄 = 파티 순서 전원');
      assert.deepEqual(p.rows.filter(r => r[1]).map(r => r[0]), [focus], '강조 줄 = 시점 사람');
      assert.equal(p.call, cs.real, '비교 모드 머리 = 관전자 이름');
      for (const [c, , text] of p.rows) assert(text.includes(cs.by[c].call), `${c} 줄에 부르는 이름 ${cs.by[c].call} 없음`);
      await page.screenshot({ path: out('inspect-5-compare.png') });
      await closePanel(page);
      await openTarget(page, cs.frame, focus, cs.target);
      p = await panel(page);
      assert.equal(p.rows.length, SC.party.length, '닫았다 열면 비교 모드가 풀렸다');
      await page.click('#inspect .ins-cmp');
      p = await panel(page);
      assert.equal(p.rows.length, 0, '다시 누르면 시점 보기');
      assert(p.secs.some(s => s.endsWith('에게는')), '시점 보기의 "<이름>에게는" 칸');
      return p.cmp;
    });
  }
  if (SC.mob_split) {
    const ms = SC.mob_split;
    await check(`4 초점 칩을 바꾸면 몹 이름도 그 사람 것으로 (${ms.target} t${ms.turn})`, async () => {
      await openTarget(page, ms.frame, ms.writer, ms.target);
      const seen = [];
      for (const c of SC.party) {
        await page.click(`.chip[data-char="${c}"]`);
        await page.waitForFunction(c => window.__wl.focus.char === c, c, { timeout: 3000 });
        await sleep(150);
        const p = await panel(page);
        assert.equal(p.call, ms.by[c], `초점 ${c} 의 몹 이름`);
        seen.push(`${c}→${p.call}`);
      }
      return seen.join(' · ');
    });
  } else skip('4 초점 칩 전환 — 몹 이름(\'낯선 짐승\'↔종 이름)', '픽스처 판에 시점마다 종 앎이 갈리는 몹 장면이 없다(scenes.json mob_split = null) — 사람 호칭으로만 봤다');

  /* ── 10 닫기 · 빈 곳 ── */
  await check('10 Esc·× 로 닫기 · 빈 곳(벽·바깥) 클릭은 무시', async () => {
    const f = oldFound && (oldFound.room || oldFound.corridor || oldFound.door);
    assert(f, '1번 훑기에서 누를 장소를 못 찾았다');
    await openTarget(page, f.frame, f.focus, f.id);
    await page.keyboard.press('Escape');
    await waitOpen(page, false);
    await openTarget(page, f.frame, f.focus, f.id);
    await page.click('#inspect .ins-close');
    await waitOpen(page, false);
    await openTarget(page, f.frame, f.focus, f.id);
    const empty = await page.evaluate(() => {   // 층 밖 여백 먼저(그림 테두리에 걸릴 일이 없다), 없으면 벽 칸
      const L = window.__wl.playback.cur.level, ts = window.__it.tiles(false).filter(t => t.ok && !t.ids.length);
      return ts.find(t => t.x < 0 || t.y < 0 || t.x >= L.w || t.y >= L.h) || ts[0] || null;
    });
    assert(empty, '화면 안에 후보 없는 자리가 없다');
    assert.deepEqual(await clickWorld(page, empty.wx, empty.wy), [], '빈 곳의 후보');
    await sleep(250);
    const p = await panel(page);
    assert(p.open && p.on === f.id, '빈 곳을 눌렀더니 창이 닫혔거나 대상이 바뀌었다');
    return `빈 곳 칸 (${empty.x}, ${empty.y})`;
  });
  skip('1 점선 고리 모양·창 자리', '점선 고리(초점 고리와 다른 모양)·무대 왼쪽 아래 창 자리는 눈으로 — verify/out/inspect-*.png');
  await closePanel(page);
  await closePage(page);

  /* ═══════════════ 입체 렌더러(?dungeonArt=prototype) ═══════════════ */
  const page2 = await openPage(`run=${RUN}&focus=${SC.party[0]}&t=${(DUNGEON.turn || 0) + 1}&dungeonArt=prototype`);
  await check('준비: 입체 렌더러로 던전이 열린다', async () => {
    assert.equal(await page2.evaluate(() => window.__wl.scene.projectedDungeon), true, '입체 렌더러(projectedDungeon)가 아니다');
  });
  await dungeonClicks(page2, 'proj', '입체 렌더러');
  await headClick(page2, '입체 렌더러');
  await closePanel(page2);
  await closePage(page2);

  /* ═══════════════ 10 액자 모드 ═══════════════ */
  await check('10 액자 모드(?embed=1)엔 클릭 창이 없다(무대를 눌러도)', async () => {
    const pg = await openPage(`run=${RUN}&embed=1`);
    try {
      assert.equal(await pg.evaluate(() => !!document.getElementById('inspect')), false, '#inspect 가 있다');
      const c = await pg.evaluate(() => { const r = window.__wl.game.canvas.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; });
      await pg.mouse.click(c.x, c.y);
      await sleep(250);
      assert.equal(await pg.evaluate(() => !!document.getElementById('inspect')), false, '누른 뒤 #inspect 가 생겼다');
    } finally { await closePage(pg); }
  });

  /* ═══════════════ 9 라이브 꽁무니(state/ 자리에 줄을 늘려 대 준다 — 론처 폴링과 같은 길) ═══════════════ */
  const lv = SC.live;
  if (!lv) skip('9 라이브 꽁무니', 'scenes.json 에 HP 가 바뀌는 틱 쌍이 없다');
  else await check(`9 라이브 꽁무니 — 창을 연 채 새 틱이 붙으면 갱신되고 재생이 안 멈춘다 (t${lv.turn_cut} → t${lv.turn_grow})`, async () => {
    liveText = FIX_LINES.slice(0, lv.cut).join('\n') + '\n';
    const pg = await openPage(`run=${LIVE}&focus=${lv.focus}`);
    try {
      const st = await pg.evaluate(() => ({ live: window.__wl.live, turn: window.__wl.playback.cur.turn }));
      assert.equal(st.live, true, '라이브 판으로 열리지 않았다');
      assert.equal(st.turn, lv.turn_cut, '꽁무니 틱');
      const me = 'b' + lv.focus;
      await go(pg, null, null);
      const sp = await pg.evaluate(id => window.__it.spotOf(id), me);
      assert(sp, '시점 사람을 누를 칸이 없다');
      await clickWorld(pg, sp.wx, sp.wy);
      await waitOpen(pg);
      if ((await panel(pg)).on !== me) await pg.click(`#inspect .ins-chip[data-id="${me}"]`);
      let p = await panel(pg);
      assert(fact(p, 'HP').startsWith(lv.hp_cut), `HP ${fact(p, 'HP')} ≠ ${lv.hp_cut}`);
      await pg.evaluate(() => window.__wl.playback.play());
      liveText = FIX_LINES.slice(0, lv.grow).join('\n') + '\n';
      await pg.waitForFunction(t => window.__wl.playback.cur.turn === t, lv.turn_grow, { timeout: 10000 });
      await sleep(200);
      p = await panel(pg);
      assert.equal(await pg.evaluate(() => window.__wl.playback.playing), true, '창을 연 채 새 틱이 왔는데 재생이 멈췄다');
      assert(p.open && p.on === me, '새 틱에 창이 닫혔거나 대상이 바뀌었다');
      assert(fact(p, 'HP').startsWith(lv.hp_grow), `새 틱 HP ${lv.hp_grow} 로 갱신 안 됨: ${fact(p, 'HP')}`);
      await pg.screenshot({ path: out('inspect-9-live.png') });
      return `HP ${lv.hp_cut} → ${fact(p, 'HP')}`;
    } finally {                                   // 녹화 판으로 갈아 끼워 폴링을 멈춘 뒤 닫는다(loadRun 이 라이브 소스를 멈춘다)
      await pg.evaluate(() => { window.__wl.playback.pause(); return window.__wl.loadRun('runs/lore-click.jsonl'); }).catch(() => {});
      await closePage(pg);
    }
  });
  skip('9 론처 실판 라이브', '위 검사는 page.route 로 줄을 늘려 폴링 길을 흉내 낸다 — 론처에서 도는 실판의 꽁무니는 눈으로');

  /* ═══════════════ 11 옛 판(인물 기록 꺼짐) ═══════════════ */
  await check('11 옛 판(인물 기록 꺼짐) — 시스템 칸만 · \'기록 기능이 없던 판\' · 비교·기록 탭도 · 이름은 실명', async () => {
    const pg = await openPage(`run=${encodeURIComponent(OLD_RUN)}&focus=2&t=176&dungeonArt=off`);
    try {
      await go(pg, null, null);
      // 초점 자신은 옛 판에서도 '너'다(identity.call) — 다른 사람·몹을 누른다
      const sp = await pg.evaluate(() => window.__it.tiles().find(t => t.ok && /^[bm]\d+$/.test(t.ids[0] || '') && t.ids[0] !== 'b' + window.__wl.focus.char) || null);
      assert(sp, '옛 판 t176 화면 안에 누를 사람(초점 말고)·몹이 없다');
      await clickWorld(pg, sp.wx, sp.wy);
      await waitOpen(pg);
      let p = await panel(pg);
      assert(p.none && p.none.includes('기록 기능이 없던 판'), `기록 칸: ${p.none}`);
      assert(p.facts.length >= 2, '시스템 칸이 비었다');
      assert.equal(p.real, null, '옛 판은 부르는 이름 = 실명(관전자 이름을 따로 붙이지 않는다)');
      await pg.click('#inspect .ins-cmp');
      p = await panel(pg);
      assert(p.rows.length >= 1 && p.rows.every(r => r[2].includes('기록 기능이 없던 판')), '비교 줄마다 \'기록 기능이 없던 판\'');
      await pg.click('#inspect .ins-cmp');
      await pg.screenshot({ path: out('inspect-11-old.png') });
      await pg.keyboard.press('Escape');
      await pg.click('#codexBtn');
      await pg.waitForFunction(() => document.querySelector('#codex')?.dataset.open === '1', null, { timeout: 3000 });
      await pg.click('#codex .cx-tab[data-tab="records"]');
      const note = await pg.evaluate(() => document.querySelector('#codex .cx-body')?.textContent || '');
      assert(note.includes('기록 기능이 없던 판'), '\'기록\' 탭 안내 문구');
      return `${p.on || sp.ids[0]} · 칸 (${sp.x}, ${sp.y})`;
    } finally { await closePage(pg); }
  });

  await check('브라우저 오류 0(pageerror·console.error·HTTP≥400·requestfailed)', () => {
    assert.deepEqual(errors, [], '브라우저 오류');
  });
} catch (e) {
  fatal = e;
} finally {
  if (browser) await browser.close().catch(() => {});
  if (server) server.kill();
}

/* ───────────── 결산 ───────────── */
console.log(`\n[inspect] 통과 ${passes.length} · 실패 ${fails.length} · 생략 ${skips.length} — 스냅샷: ${outDir}`);
if (skips.length) { console.log('[inspect] 생략 목록:'); for (const s of skips) console.log('  - ' + s); }
if (fatal) console.error('[inspect] 치명(검사 중단):', fatal && fatal.stack || fatal);
if (fails.length) { console.error('[inspect] 실패 목록:'); for (const f of fails) console.error('  ✗ ' + f); }
if (errors.length) { console.error('[inspect] 브라우저 오류:'); for (const e of errors.slice(0, 20)) console.error('  ! ' + e); }
if (fatal || fails.length) process.exit(1);
console.log('INSPECT PASS (관전 클릭 창 §6.2)');

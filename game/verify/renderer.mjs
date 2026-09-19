// D88·D89·D90(2026-09-20) 렌더러 검사 — 빌드 산출물을 vite preview 로 띄우고 헤드리스 Edge(playwright-core, msedge 채널)로 본다. LLM 0콜.
// 실행: cd game && npm run build && npm run check:renderer      (WL_PORT=4198 · WL_LAB_PORT=4229 · WL_NO_LAB=1 = 실험실 구간 생략)
//   A 본편 URL + level.architecture 있는 층 = 입체 렌더러 · level.props 를 목록 그대로(kind 가 그림을 정한다)
//   B 문 칸에 선 캐릭터·몹 — 그 문 그림만 28% 로 옅어진다(나머지 문은 그대로)
//   C 한 세션에서 판 갈아타기(입체 → 옛 그림 → 입체 → 마을) — 텍스처 키 충돌·잔재 없음
//   D URL ?dungeonArt=prototype|flat|off 강제
//   E v4 저작 마을 — 던전 렌더러는 URL 로도 안 켜진다 · 그림 없는 피처 = 반짝임 표식(폴백 타일 0) · 이름표는 곁에 캐릭터가 있을 때만 · 그림 있는 피처는 전처럼
//   F 실험실(art/dungeon-v2/compare.html)이 계속 돈다 — 두 화면이 같은 스트림을 입체|평면으로, 옛 생성기 프로필도
// 자료 = verify/renderer_streams.py(실제 엔진 생성기의 정지 스냅샷 — 판을 돌리지 않는다). 판 파일은 리포에 두지 않고 요청을 가로채 건넨다.
// 스냅샷 verify/out/renderer-*.png. 마지막 줄 'ALL PASS' 가 판정.
import fs from 'node:fs';
import path from 'node:path';
import { spawn, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';

const here = path.dirname(fileURLToPath(import.meta.url)), gameDir = path.resolve(here, '..'), root = path.resolve(gameDir, '..');
const outDir = path.join(here, 'out');
fs.mkdirSync(outDir, { recursive: true });
const PORT = Number(process.env.WL_PORT || 4198), LAB_PORT = Number(process.env.WL_LAB_PORT || 4229);
const base = `http://127.0.0.1:${PORT}/game/`, PY = process.env.WL_PYTHON || 'python';
const pyEnv = { ...process.env, PYTHONUTF8: '1', DUNGEON_BRAIN_BACKEND: 'dummy' };
const sleep = ms => new Promise(r => setTimeout(r, ms));
let n = 0; const fails = [];
const check = (name, ok, detail = '') => { n++; if (ok) console.log('[renderer] PASS', name); else { fails.push(name); console.log('[renderer] FAIL', name, '—', detail); } };

if (!fs.existsSync(path.join(gameDir, 'dist', 'index.html'))) throw new Error('먼저 빌드: npm run build');
const made = spawnSync(PY, [path.join(here, 'renderer_streams.py'), outDir], { cwd: root, encoding: 'utf8', env: pyEnv });
if (made.status !== 0) throw new Error('자료 생성 실패: ' + made.stdout + made.stderr);
console.log('[renderer]', made.stdout.trim());

const servers = [spawn(process.execPath, [path.join(gameDir, 'node_modules', 'vite', 'bin', 'vite.js'), 'preview', '--port', String(PORT), '--strictPort', '--host', '127.0.0.1'],
  { cwd: gameDir, stdio: 'ignore' })];
const waitHttp = async url => { for (let i = 0; i < 150; i++) { try { if ((await fetch(url)).ok) return; } catch { /* 아직 */ } await sleep(200); } throw new Error('서버가 안 뜬다: ' + url); };
let browser;
try {
  await waitHttp(base);
  browser = await chromium.launch({ headless: true, ...(process.platform === 'win32' ? { channel: 'msedge' } : {}) });
  const errors = [];
  const watch = (page, allow404 = () => false) => {
    page.on('pageerror', e => errors.push('pageerror ' + e.message));
    page.on('console', m => { if (m.type() === 'error' && !/status of 404/.test(m.text())) errors.push('console ' + m.text()); });
    page.on('response', r => { if (r.status() >= 400 && !r.url().includes('favicon') && !allow404(r.url())) errors.push(`${r.status()} ${r.url()}`); });
  };
  const open = async query => {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    watch(page);
    await page.route(/\/runs\/__renderer_[a-z]+\.jsonl/, route => {
      const name = route.request().url().match(/__renderer_([a-z]+)\.jsonl/)[1];
      route.fulfill({ status: 200, contentType: 'application/x-ndjson; charset=utf-8', body: fs.readFileSync(path.join(outDir, `renderer_${name}.jsonl`)) });
    });
    await page.goto(base + '?' + query);
    await page.waitForFunction(() => window.__wl?.scene?.frame && window.__wl?.run?.meta, null, { timeout: 30000 });
    await sleep(500);
    return page;
  };
  const state = page => page.evaluate(() => {
    const s = window.__wl.scene, g = s.children.getByName('dungeon-v2-ground'), frames = k => s.textures.exists(k) ? s.textures.get(k).frameTotal : 0;
    return { ground: !!g, projected: s.projectedDungeon, groundIsProjected: g ? g.getData('projected') === true : null,
      oldGround: s.ground ? s.ground.visible : null, decorFrames: frames('dungeon-v2-decor'), flatWalls: frames('dungeon-v2-walls') };
  });
  const noFocus = page => page.evaluate(() => { const a = window.__wl; a.focus.char = null; a.focus.emit('change', { char: null, prev: null });
    a.scene.applyFrame({ prev: null, cur: a.playback.cur, mode: 'seek' }); });
  const load = async (page, name, wait = 700) => { await page.evaluate(p => window.__wl.loadRun(p, { turn: 1 }), `runs/__renderer_${name}.jsonl`); await sleep(wait); };

  // ── A
  let page = await open('run=runs/__renderer_concept.jsonl&t=1');
  let st = await state(page);
  check('A 본편 URL · architecture 있는 층 → 입체 렌더러(옛 타일맵은 숨김)', st.ground && st.projected && st.groundIsProjected && st.oldGround === false, JSON.stringify(st));
  check('A decor 는 시트로 실린다 · 평면 전용 그림은 안 싣는다', st.decorFrames >= 6 && st.flatWalls === 0, JSON.stringify(st));
  await noFocus(page);
  const furn = await page.evaluate(() => window.__wl.scene.children.list.filter(o => o.name === 'dungeon-furnishing' && !o.getData('dungeonWall'))
    .map(o => ({ cell: o.getData('dungeonCell'), tex: o.texture.key, frame: Number(o.frame.name), depth: o.depth })));
  const props = await page.evaluate(() => window.__wl.playback.cur.level.props);
  const want = { barrel: ['dungeon-v2-decor', 0], crate: ['dungeon-v2-decor', 1], jar: ['dungeon-v2-decor', 2], rubble: ['dungeon-v2-decor', 3],
    storage: ['dungeon-v3-architecture', 3], ruin: ['dungeon-v3-architecture', 2] };
  check('A level.props — 바닥 소품 = 엔진 목록 그대로(추첨 없음)', props.length > 0 && furn.length === props.length, `${furn.length} vs ${props.length}`);
  check('A level.props — kind 가 그림을 정한다 · blocks=false 는 선 이보다 뒤', props.every(p => {
    const o = furn.find(o => o.cell[0] === p.x && o.cell[1] === p.y);
    return o && o.tex === want[p.kind][0] && o.frame === want[p.kind][1]
      && (p.blocks ? o.depth > 20 + p.y * .01 - .005 : Math.abs(o.depth - (20 + p.y * .01 - .006)) < 1e-9);
  }), JSON.stringify(furn));
  await page.screenshot({ path: path.join(outDir, 'renderer-concept.png') });
  // ── B
  await page.evaluate(() => { const a = window.__wl; a.playback.setIdx(a.frameOfTurn(2), 'seek'); });
  await noFocus(page); await sleep(400);
  const dd = await page.evaluate(() => { const a = window.__wl, cur = a.playback.cur;
    return { bot: [cur.bots[0].x, cur.bots[0].y], mob: [cur.monsters[0].x, cur.monsters[0].y],
      doors: a.scene.children.list.filter(o => o.name === 'dungeon-door').map(o => ({ cell: o.getData('dungeonCell'), alpha: +o.alpha.toFixed(3) })) }; });
  const at = c => dd.doors.find(d => d.cell[0] === c[0] && d.cell[1] === c[1]);
  const rest = dd.doors.filter(d => d !== at(dd.bot) && d !== at(dd.mob));
  check('B 문 칸에 선 캐릭터 — 그 문 그림 28%', at(dd.bot)?.alpha === 0.28, JSON.stringify(at(dd.bot)));
  check('B 문 칸에 선 몹 — 그 문 그림 28%', at(dd.mob)?.alpha === 0.28, JSON.stringify(at(dd.mob)));
  check('B 나머지 문은 그대로', rest.length >= 1 && rest.every(d => d.alpha === 1), JSON.stringify(rest));
  await page.evaluate(() => { const s = window.__wl.scene, b = window.__wl.playback.cur.bots[0]; s.setZoom(2); s.cameras.main.stopFollow(); s.cameras.main.centerOn((b.x + .5) * 48, (b.y + .5) * 48); });
  await sleep(300); await page.screenshot({ path: path.join(outDir, 'renderer-door.png') });
  // ── C
  await load(page, 'original'); st = await state(page);
  check('C 같은 세션 · 옛 생성기 판 → 옛 그림', !st.ground && !st.projected && st.oldGround === true, JSON.stringify(st));
  await load(page, 'concept'); st = await state(page);
  check('C 같은 세션 · 다시 새 프로필 판 → 입체', st.ground && st.projected, JSON.stringify(st));
  await load(page, 'town', 1200); st = await state(page);
  check('C 같은 세션 · 마을 → 꺼짐', !st.ground && !st.projected, JSON.stringify(st));
  await page.close();
  // ── D
  for (const [q, run, ground, projected] of [['dungeonArt=prototype', 'original', true, true], ['dungeonArt=flat', 'concept', true, false],
    ['dungeonArt=flat', 'original', true, false], ['dungeonArt=off', 'concept', false, false], ['', 'original', false, false]]) {
    page = await open(`run=runs/__renderer_${run}.jsonl&t=1${q ? '&' + q : ''}`);
    st = await state(page);
    check(`D '${q || '(파라미터 없음)'}' + ${run} 판 → ${ground ? (projected ? '입체' : '평면') : '옛 그림'}`, st.ground === ground && st.projected === projected, JSON.stringify(st));
    await page.close();
  }
  // ── E
  for (const q of ['', '&dungeonArt=prototype']) {
    page = await open('run=runs/__renderer_town.jsonl&t=1' + q);
    const town = await page.evaluate(() => {
      const s = window.__wl.scene, by = name => s.children.getByName(name);
      const pick = o => o ? { tex: o.texture?.key, visible: o.visible, text: o.text, scale: o.scaleX, depth: o.depth } : null;
      return { ground: !!by('dungeon-v2-ground'), projected: s.projectedDungeon, m1: pick(by('feat-marker-901')), l1: pick(by('feat-label-901')),
        m2: pick(by('feat-marker-902')), l2: pick(by('feat-label-902')), m3: pick(by('feat-marker-903')),
        potion: pick(s.children.list.find(o => o.type === 'Sprite' && o.texture.key === 'wl-props' && Number(o.frame.name) === 5)),
        fallbackTiles: s.children.list.filter(o => o.type === 'Sprite' && o.texture.key === 'tiny').length };
    });
    const tag = q ? ' (+dungeonArt=prototype)' : '';
    check(`E 마을${tag} — 던전 렌더러 꺼짐`, !town.ground && !town.projected, JSON.stringify(town));
    check(`E 마을${tag} — 그림 없는 피처 = 반짝임 표식 · 폴백 타일 0`, town.m1?.tex === 'wl-spark' && town.m2?.tex === 'wl-spark' && town.fallbackTiles === 0, JSON.stringify(town));
    check(`E 마을${tag} — 이름표는 곁(2칸 안)에 캐릭터가 있을 때만`, town.l1?.visible === true && town.l1?.text === '우물' && town.l2?.visible === false, JSON.stringify(town));
    check(`E 마을${tag} — 제 그림이 있는 피처(물약)는 전처럼 스프라이트`, !town.m3 && town.potion?.tex === 'wl-props', JSON.stringify(town));
    if (!q) {
      await page.evaluate(() => { const s = window.__wl.scene, m = s.children.getByName('feat-marker-902'); document.getElementById('overlay').style.display = 'none';
        s.cameras.main.stopFollow(); s.cameras.main.centerOn(m.x, m.y); });
      await sleep(500); await page.screenshot({ path: path.join(outDir, 'renderer-town-marker.png') });
    }
    await page.close();
  }
  // ── F
  if (!process.env.WL_NO_LAB) {
    servers.push(spawn(PY, ['art/dungeon-v2/preview_server.py', '--port', String(LAB_PORT)], { cwd: root, stdio: 'ignore', env: pyEnv }));
    const lab = `http://127.0.0.1:${LAB_PORT}`;
    await waitHttp(lab + '/api/status');
    page = await browser.newPage({ viewport: { width: 1500, height: 950 } });
    watch(page, url => new URL(url).pathname === '/runs/');       // 실험실 서버는 판 목록(/runs/)을 서빙하지 않는다 — 전부터 404
    await page.goto(lab + '/art/dungeon-v2/compare.html?seed=7');
    await page.waitForFunction(() => window.dungeonLab?.ready, null, { timeout: 60000 });
    const read = () => page.evaluate(() => window.dungeonLab.apps.map(a => ({ ground: !!a.scene.children.getByName('dungeon-v2-ground'),
      projected: a.scene.projectedDungeon, arch: !!a.playback.cur.level.architecture })));
    let lv = await read();
    check('F 실험실 · concept — 왼쪽 입체 · 오른쪽 평면', lv[0].ground && lv[0].projected && lv[1].ground && !lv[1].projected && lv[0].arch, JSON.stringify(lv));
    await page.selectOption('#layout', 'original');
    await page.waitForFunction(() => window.dungeonLab?.profile === 'original' && window.dungeonLab.apps.every(a => a.run?.meta.art_profile === 'original'), null, { timeout: 60000 });
    await sleep(800); lv = await read();
    check('F 실험실 · original(architecture 없음) — URL 강제로 입체 · 평면', lv[0].ground && lv[0].projected && lv[1].ground && !lv[1].projected && !lv[0].arch, JSON.stringify(lv));
    const status = await page.evaluate(() => document.getElementById('status').textContent);
    check('F 실험실 상태 줄에 오류 없음', !status.startsWith('오류'), status);
    await page.screenshot({ path: path.join(outDir, 'renderer-lab.png') });
    await page.close();
  }
  check('브라우저 오류 0(pageerror · console.error · HTTP>=400)', errors.length === 0, errors.slice(0, 5).join(' | '));
} finally {
  await browser?.close();
  for (const s of servers) s.kill();
}
console.log(fails.length ? `[renderer] FAILED ${fails.length}/${n}: ${fails.join(' ; ')}` : `ALL PASS — game/verify/renderer.mjs (${n} checks · LLM 0콜)`);
process.exit(fails.length ? 1 : 0);

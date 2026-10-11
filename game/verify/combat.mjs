// 관리자 실행용: 고정 JSONL → 실제 파서·폴링·Phaser 검증. LLM 호출·스크린샷 없음.
// game/에서 npm run build 후 node verify/combat.mjs. 브라우저 금지 세션에서는 실행하지 않는다.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';
import { validateFixture } from './combat-fixture.mjs';

const game = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const fixture = fs.readFileSync(path.join(game, 'verify/fixtures/combat.jsonl'), 'utf8').trimEnd() + '\n';
validateFixture(fixture);
const lines = fixture.trimEnd().split('\n');
const port = 4293, base = process.env.WL_GAME_ORIGIN || `http://127.0.0.1:${port}`;
const server = process.env.WL_GAME_ORIGIN ? null : spawn(process.execPath, [path.join(game, 'node_modules/vite/bin/vite.js'), 'preview', '--port', String(port), '--strictPort'], { cwd: game, stdio: 'ignore' });
const sleep = ms => new Promise(r => setTimeout(r, ms));
let browser, checks = 0, observed = null;
const errors = [];
const failures = [];
const check = (name, ok) => {
  checks++;
  if (ok) console.log('  OK ' + name);
  else {
    failures.push(name);
    console.error('  FAIL ' + name + '\n관측값: ' + JSON.stringify(observed) + '\n콘솔: ' + JSON.stringify(errors));
  }
};
try {
  let ready = false;
  for (let i = 0; i < 80; i++) {
    try { if ((await fetch(base + '/game/')).ok) { ready = true; break; } } catch {}
    await sleep(150);
  }
  assert.ok(ready, '미리보기 서버 준비 실패');
  browser = process.env.WL_CDP ? await chromium.connectOverCDP(process.env.WL_CDP)
    : await chromium.launch({ headless: true, ...(process.platform === 'win32' ? { channel: 'msedge' } : {}) });
  const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
  page.on('pageerror', e => errors.push(e.message));
  // App의 Emitter가 잡아 콘솔로만 남기는 장면 생성 오류도 수집한다.
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('response', r => { if (r.status() >= 400 && !r.url().includes('favicon')) errors.push(`${r.status()} ${r.url()}`); });
  let liveText = lines.slice(0, 2).join('\n') + '\n';
  let polls = 0;
  await page.route('**/runs/combat.jsonl*', route => route.fulfill({ status: 200, contentType: 'application/x-ndjson', body: fixture }));
  await page.route('**/state/combat.jsonl*', route => { polls++; return route.fulfill({ status: 200, contentType: 'application/x-ndjson', body: liveText }); });
  await page.goto(base + '/game/?run=runs/combat.jsonl');
  await page.waitForFunction(() => window.__wl?.run?.frames.length === 12 && window.__wlCombat);
  // scene.pause()는 다음 게임 틱에 예약된다. sys.pause()는 즉시 멈추며 렌더는 유지한다.
  await page.evaluate(() => { const a = window.__wl; a.scene.sys.pause(); a.scene.cameras.main.setZoom(1.5); });
  const snapshot = async (stepTurn = null) => { observed = await page.evaluate(turn => {
    const a = window.__wl, s = window.__wlCombat;
    // 전진과 관측을 한 번의 작업에서 처리해 중간 렌더 틱의 영향을 없앤다.
    if (turn != null) { a.playback.setIdx(a.frameOfTurn(turn) - 1); a.playback.step(1); }
    const f = a.playback.cur;
    const sprites = [...(f?.bots ?? []).map(b => 'b' + b.char), ...(f?.monsters ?? []).map(m => 'm' + m.id)].map(id => {
      const sprite = a.scene.combatSprite(id);
      return { id, exists: !!sprite, visible: sprite?.visible, active: sprite?.active, flash: sprite?.tintFill === true };
    });
    const objects = a.scene.children.list.filter(o => o.name === 'combat-fx').map(o => ({ ...o.data.getAll(), depth: o.depth }));
    const popups = a.scene.children.list.filter(o => o.name === 'combat-popup').map(o => ({ ...o.data.getAll(), depth: o.depth }));
    const shake = a.scene.cameras.main.shakeEffect;
    return { active: s.active, created: s.created, suppressed: s.suppressed, kinds: s.kinds,
      objects, popups, popupCount: popups.length, projectileCount: objects.filter(o => o.projectile).length,
      sprites, tinted: sprites.filter(o => o.flash).length, shaking: shake.isRunning,
      shakeDuration: shake.duration, shakeIntensity: { x: shake.intensity.x, y: shake.intensity.y },
      turn: f?.turn, index: a.playback.idx, level: f?.levelIdx, sceneTurn: a.scene.frame?.turn,
      sceneMatches: a.scene.frame === f, paused: a.scene.sys.isPaused(), renderer: a.game.renderer.type };
  }, stepTurn); return observed; };
  const stepTo = turn => snapshot(turn);
  const age = ms => page.evaluate(dt => window.__wl.scene.events.emit('update', 0, dt), ms);
  let s = await snapshot();
  check('픽스처 층 생성·몹 스프라이트·즉시 정지', s.sceneMatches && s.paused && s.sprites.some(o => o.id === 'm0' && o.exists));
  s = await stepTo(1);
  check('원거리 치명타: 팝업·투사체·대상 플래시·약한 흔들림', s.active === 1 && s.popupCount === 1 && s.projectileCount === 1
    && s.objects[0]?.text === '-12!' && s.sprites.some(o => o.id === 'm0' && o.flash) && s.tinted === 1 && s.shaking
    && s.shakeDuration <= 110 && s.shakeIntensity.x <= 0.0012);
  check('숫자는 이름표 위, 공간 도형은 안개 아래', s.popups[0]?.depth > 70 && s.objects[0]?.depth < 60);
  await age(90);
  await age(700);
  s = await snapshot();
  check('수명 종료 시 도형·팝업·피격 색 복원', s.active === 0 && s.objects.length === 0 && s.popupCount === 0 && s.tinted === 0);
  s = await stepTo(2);
  check('응급처치·MISS, 비치명타 흔들림 없음', s.active === 2 && s.objects.some(o => o.kind === 'first_aid' && o.text === '+5') && s.objects.some(o => o.text === 'MISS') && !s.shaking);
  await age(80);
  s = await stepTo(3);
  check('밀어베기 도형', s.objects[0]?.kind === 'push_slash');
  await age(80);
  s = await stepTo(4);
  check('강타·처치 도형', s.objects[0]?.kind === 'heavy_strike' && s.objects[0]?.down);
  s = await stepTo(5);
  check('출혈베기 도형', s.objects[0]?.kind === 'bleeding_cut');
  s = await stepTo(6);
  check('함정·중독 부착·봇/몹 출혈', s.active === 3 && s.objects.filter(o => o.kind === 'status').length === 2 && s.objects.some(o => o.kind === 'trap'));
  s = await stepTo(7);
  check('시야 밖·은닉·회피 함정·없는 상태 이벤트 제외', s.active === 0 && s.objects.length === 0 && s.popupCount === 0);
  s = await stepTo(8);
  check('옛 필드 호환·물약 수신자', s.active === 2 && !s.objects[0]?.projectile && s.objects[1]?.target === 'b2');
  await page.evaluate(() => window.__wl.playback.step(1));
  check('층 전환 시 연출 정리', (await snapshot()).active === 0 && observed.popupCount === 0);
  s = await stepTo(10);
  check('봇 쓰러짐', s.objects.some(o => o.down && o.target === 'b2'));
  await stepTo(1);
  await page.evaluate(() => window.__wl.playback.setIdx(1));
  s = await snapshot();
  check('같은 층 시킹 시 도형·피격 색·흔들림 정리', s.active === 0 && s.popupCount === 0 && s.tinted === 0 && !s.shaking);
  await stepTo(1);
  const created = (await snapshot()).created;
  await page.evaluate(() => { const p = window.__wl.playback; p.emit('frame', { cur: p.cur, prev: p.frames[0], idx: p.idx, mode: 'step' }); });
  check('중복 프레임 알림 재생성 없음', (await snapshot()).created === created);
  await stepTo(1);
  await page.evaluate(() => window.__wl.playback.setSpeed(1));
  check('배속 변경 즉시 정리', (await snapshot()).active === 0 && observed.popupCount === 0 && observed.tinted === 0);
  await stepTo(1);
  await age(160);
  check('4배속 수명', (await snapshot()).active === 0);
  await page.evaluate(() => window.__wl.playback.setSpeed(0));
  await stepTo(1);
  await page.evaluate(() => window.__wl.focus.set('2'));
  check('초점 변경 정리', (await snapshot()).active === 0);
  await page.evaluate(() => { window.__wl.focus.set('1'); window.__wlCombat.setEnabled(false); });
  s = await stepTo(1);
  check('실행 중 끄기', s.active === 0 && !s.shaking);
  await page.evaluate(() => window.__wlCombat.setEnabled(true));
  await stepTo(1);
  await page.evaluate(() => window.__wl.loadRun('runs/combat.jsonl'));
  check('판 교체 정리', (await snapshot()).active === 0 && observed.tinted === 0);
  await page.evaluate(() => { const a = window.__wl; a.scene.sys.resume(); a.playback.setSpeed(2); a.playback.setIdx(0); a.playback.play(); });
  await page.waitForFunction(() => !window.__wl.playback.playing);
  await page.waitForFunction(() => window.__wlCombat.active === 0);
  await snapshot();
  check('실제 16배속 완주·잔여 연출 없음', await page.evaluate(() => window.__wl.playback.atEnd && !window.__wl.scene.children.list.some(o => o.name === 'combat-fx' || o.name === 'combat-popup')));
  await page.evaluate(() => { window.__wl.playback.setSpeed(0); window.__wl.scene.sys.pause(); });
  await page.evaluate(() => window.__wl.loadRun('state/combat.jsonl'));
  const liveStart = (await snapshot()).created;
  liveText = lines.slice(0, 3).join('\n') + '\n';
  await page.waitForFunction(() => window.__wl.playback.cur.turn === 1);
  s = await snapshot();
  check('실제 폴링 한 틱 추가', s.created === liveStart + 1 && s.active === 1);
  const pollCount = polls;
  for (let i = 0; polls <= pollCount && i < 50; i++) await sleep(100);
  check('같은 폴링 내용 재생성 없음', (await snapshot()).created === s.created && polls > pollCount);
  liveText = lines.slice(0, 6).join('\n') + '\n';
  await page.waitForFunction(() => window.__wl.playback.cur.turn === 4);
  check('다중 틱 점프는 중간·도착 연출 생략', (await snapshot()).active === 0 && observed.created === s.created);
  liveText = lines.slice(0, 7).join('\n') + '\n';
  await page.waitForFunction(() => window.__wl.playback.cur.turn === 5);
  check('점프 뒤 한 틱 연출 재개', (await snapshot()).created === s.created + 1);
  liveText = lines.slice(0, 2).join('\n') + '\n';
  await page.waitForFunction(() => window.__wl.playback.cur.turn === 0);
  check('라이브 파일 교체 정리', (await snapshot()).active === 0);
  await page.goto(base + '/game/?run=runs/combat.jsonl&combatFx=0');
  await page.waitForFunction(() => window.__wl?.playback.cur && window.__wlCombat);
  s = await stepTo(1);
  check('URL combatFx=0', s.created === 0 && s.active === 0);
  check('브라우저·이벤트 버스 오류 없음', errors.length === 0);
} catch (e) {
  failures.push('검증 준비 또는 진행 중단');
  console.error('중단: ' + e.stack + '\n마지막 관측값: ' + JSON.stringify(observed) + '\n콘솔: ' + JSON.stringify(errors));
} finally {
  await browser?.close(); server?.kill();
  if (errors.length) console.error(errors);
  console.log(`${failures.length ? 'FAILED' : 'ALL PASS'} — 전투 브라우저 검증: 검사 ${checks}, 실패 ${failures.length}`);
  if (failures.length) { console.error('실패 항목: ' + failures.join(', ')); process.exitCode = 1; }
}

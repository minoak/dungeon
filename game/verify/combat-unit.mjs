// 종료되는 Node 구성요소 검증. 실제 TS와 Phaser의 순수 Tint/Shake 부품을 사용한다.
// 브라우저·서버·자식 프로세스·Phaser 부팅·스크린샷 없음. 렌더 품질 검증은 아니다.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { EventEmitter } from 'node:events';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';
import { createRequire } from 'node:module';
import { validateFixture } from './combat-fixture.mjs';

const game = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(import.meta.url);
const Tint = require('phaser/src/gameobjects/components/Tint.js');
const Shake = require('phaser/src/cameras/2d/effects/Shake.js');
const win = { setTimeout, clearTimeout };
const errors = [];
const cache = new Map();
function load(file) {
  file = path.resolve(game, file);
  if (cache.has(file)) return cache.get(file);
  const mod = { exports: {} }; cache.set(file, mod.exports);
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  vm.runInNewContext(code, {
    exports: mod.exports, module: mod, URLSearchParams, location: { search: '' }, window: win,
    setTimeout, clearTimeout, console: { ...console, error: (...args) => errors.push(args) },
    require: name => name.endsWith('/DungeonScene') ? { DEPTH: { fx: 50, label: 70 } }
      : load(path.resolve(path.dirname(file), name + '.ts')),
  }, { filename: file });
  return mod.exports;
}
const { Emitter } = load('src/util/Emitter.ts');
const { Playback } = load('src/play/Playback.ts');
const { StreamParser } = load('src/stream/parse.ts');
const { installCombat } = load('src/fx/Combat.ts');
const fixture = fs.readFileSync(path.join(game, 'verify/fixtures/combat.jsonl'), 'utf8').trimEnd() + '\n';
const rows = validateFixture(fixture);
const broken = rows.map(r => r.kind === 'level' ? { ...r, exit: undefined } : r);
assert.throws(() => validateFixture(broken.map(JSON.stringify).join('\n')), /exit=/);
const parser = new StreamParser(); parser.feed(fixture);
const p = new Playback(); p.setFrames(parser.run.frames);
const bus = new Emitter(), focus = new Emitter(); focus.char = '1';
const events = new EventEmitter(), graphics = new Set(), sprites = new Map();
let pixels = 0, checks = 0;
const check = (name, value) => { assert.ok(value, name); checks++; console.log('  OK ' + name); };
for (const id of ['b1', 'b2', 'm0', 'm1', 'm2', 'm3']) sprites.set(id, {
  ...Tint,
  active: true, visible: true, tintFill: false,
  tintTopLeft: 0xffffff, tintTopRight: 0xffffff, tintBottomLeft: 0xffffff, tintBottomRight: 0xffffff,
});
const camera = { scene: {}, width: 1000, height: 700, zoom: 1, roundPixels: true, emit() {},
  shake(ms, intensity, force) { assert.ok(ms <= 110 && intensity <= 0.0012); this.shakeEffect.start(ms, intensity, force); } };
camera.shakeEffect = new Shake(camera);
const scene = {
  events, cameras: { main: camera },
  frame: null,
  worldOf: (x, y) => ({ x: (x + 0.5) * 48, y: (y + 1) * 48 - 4 }),
  visibleSet: c => p.cur.vis[c], combatSprite: id => sprites.get(id),
  add: { graphics() {
    const g = {
      data: {}, setDepth(d) { this.depth = d; return this; }, setName(n) { this.name = n; return this; }, setData(d) { this.data = d; return this; },
      clear() { return this; }, fillStyle() { return this; },
      fillRect(...coords) { assert.ok(coords.every(Number.isInteger), '정수 픽셀 좌표'); pixels++; return this; },
      destroy() { assert.ok(graphics.delete(this), '객체는 한 번만 소거'); },
    };
    graphics.add(g); return g;
  } },
};
const app = { playback: p, scene, run: parser.run, bus, focus };
let applyFrame = true;
p.on('frame', ({ cur }) => { if (applyFrame) scene.frame = cur; });
installCombat(app);
const stat = win.__wlCombat;
const step = turn => { const i = p.frames.findIndex(f => f.kind === 'tick' && f.turn === turn); p.setIdx(i - 1); p.step(1); };
const age = ms => events.emit('update', 0, ms);
const data = () => [...graphics].filter(g => g.name === 'combat-fx').map(g => g.data);
const clean = () => stat.active === 0 && graphics.size === 0 && [...sprites.values()].every(s => !s.tintFill);
step(1);
check('원거리 치명타: 한 이벤트·팝업·투사체·피격 색·흔들림',
  stat.active === 1 && data()[0].text === '-12!' && data()[0].projectile && sprites.get('m0').tintFill && camera.shakeEffect.isRunning);
check('숫자는 이름표 위, 도형은 안개 아래', [...graphics].some(g => g.name === 'combat-popup' && g.depth > 70)
  && [...graphics].some(g => g.name === 'combat-fx' && g.depth < 60));
camera.shakeEffect.update(0, 120);
check('실제 Phaser 흔들림 수명 종료', !camera.shakeEffect.isRunning);
age(90); check('수명 이전에는 연출 유지', stat.active === 1 && pixels > 0);
age(100); check('숫자보다 피격 색이 먼저 복원', !sprites.get('m0').tintFill && stat.active === 1);
age(600); check('수명 종료 시 도형·팝업 소거', clean());
step(2);
check('회복 수신자·MISS, 흔들림 없음', data().some(d => d.target === 'b2' && d.text === '+5')
  && data().some(d => d.text === 'MISS') && !camera.shakeEffect.isRunning);
for (const [turn, kind] of [[3, 'push_slash'], [4, 'heavy_strike'], [5, 'bleeding_cut']]) {
  step(turn); age(90); check(kind + ' 정수 픽셀 도형', data()[0].kind === kind && (turn !== 4 || data()[0].down));
}
step(6); age(90);
check('함정·중독 부착·봇/몹 출혈', stat.active === 3 && data().filter(d => d.kind === 'status').length === 2);
step(7); check('은닉·시야 밖·회피 함정·없는 상태 이벤트 제외', clean());
step(8); check('옛 필드 호환: 투사체 추측 없음·물약 수신자', stat.active === 2 && !data()[0].projectile && data()[1].target === 'b2');
p.step(1); check('층 전환 시 이전 연출 소거', clean());
step(10); check('봇 쓰러짐 연출', data()[0].down && data()[0].target === 'b2');
step(1); p.setIdx(1); check('같은 층 시킹 시 피격 색·흔들림·도형 정리', clean() && !camera.shakeEffect.isRunning);
step(1); const n = stat.created;
p.emit('frame', { cur: p.cur, prev: p.frames[0], idx: 1, mode: 'step' });
check('중복 프레임 재생성 없음', stat.created === n && clean());
step(1); p.setSpeed(1); check('배속 변경 시 이전 연출 소거', clean());
step(1); age(160); check('4배속 수명 제한', clean());
p.setSpeed(0); step(1); focus.emit('change', { char: '2', prev: '1' });
check('초점 변경 시 연출 정리', clean());
step(1); stat.setEnabled(false); step(2); check('끄기 옵션: 소거·생성 차단', clean());
stat.setEnabled(true); step(1); bus.emit('run', parser.run); check('판 교체 시 연출 정리', clean());
// 장면 생성 실패를 실제 상태로 재현: 대상 스프라이트가 없으면 피격 연출을 만들지 않는다.
const targetSprite = sprites.get('m0'); sprites.delete('m0'); step(1);
check('실제 대상 스프라이트가 없으면 생성 금지', clean()); sprites.set('m0', targetSprite);
p.setIdx(0); const current = p.frames[1]; scene.frame = null; applyFrame = false;
p.emit('frame', { cur: current, prev: p.frames[0], idx: 1, mode: 'step' });
check('장면 갱신 실패 시 남은 프레임으로 연출하지 않음', clean());
applyFrame = true;
const liveParser = new StreamParser(), lines = fixture.trimEnd().split('\n');
liveParser.feed(lines.slice(0, 2).join('\n') + '\n');
app.run = liveParser.run; p.setFrames(liveParser.run.frames); bus.emit('run', app.run); p.setIdx(0); p.setLive(true);
const grow = count => {
  const result = liveParser.feed(lines.slice(0, count).join('\n') + '\n');
  p.setFrames(liveParser.run.frames); p.grew(result.added);
};
let created = stat.created;
grow(3); check('라이브 한 틱 추가는 한 번 생성', stat.created === created + 1 && stat.active === 1);
created = stat.created; grow(3); check('같은 폴링 내용 재생 없음', stat.created === created);
grow(6); check('라이브 다중 틱 시킹은 중간·도착 연출 생략', clean() && stat.created === created);
grow(7); check('점프 뒤 한 틱 연출 재개', stat.active === 1 && stat.created === created + 1);
events.emit('shutdown'); check('씬 종료 시 전체 소거', clean());
check('이벤트 처리 중 숨겨진 오류 없음', errors.length === 0);
console.log(`ALL PASS — 전투 구성요소 ${checks}건 (${pixels}개 정수 픽셀 사각형, 렌더 미검증)`);

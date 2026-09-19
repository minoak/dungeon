// D88·D89·D90(2026-09-20) 관전 클라이언트의 순수 로직 검사 — 브라우저 없음 · LLM 0콜. 실행: cd game && node verify/props.mjs
//   ① 렌더러 고르기(dungeonArtFor): level.architecture 가 있으면 입체 · 없으면 옛 그림 · URL ?dungeonArt= 는 강제 · 마을 층은 늘 꺼짐
//   ② 엔진 소유 소품(level.props): 있으면 바닥 소품 추첨을 건너뛰고 그 목록 그대로 · 벽 부착물은 있든 없든 같은 자리 · 없으면 추첨 그대로
//   ③ 관전 로그 문장(evline): 새 interact.result 아홉 가지(뒤지기는 엔진의 got 이 먼저 · 이름은 name → what → target) · 모르는 result 는 옛 폴백 그대로 · 소품 대상(p<n>) 이름 풀기
// 층 자료는 실험실과 같은 길(art/dungeon-v2/preview_server.stream — 실제 엔진 생성기, 두뇌 미사용)로 만든다. 마지막 줄 'ALL PASS' 가 판정.
import assert from 'node:assert/strict';
import path from 'node:path';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { build } from 'esbuild';

const here = path.dirname(fileURLToPath(import.meta.url)), game = path.resolve(here, '..'), root = path.resolve(game, '..');
let checks = 0, serial = 0;
const check = (name, ok, detail = '') => { assert.ok(ok, name + (detail ? ' — ' + detail : '')); checks++; console.log('PASS ' + name); };

/** src 의 TS 모듈 하나를 묶어 그대로 import 한다(그림 import 는 빈 값 · phaser 는 타입뿐이라 지워진다). */
async function load(rel) {
  const out = await build({ entryPoints: [path.join(game, rel)], bundle: true, format: 'esm', write: false, platform: 'neutral',
    loader: { '.png': 'empty' }, logLevel: 'silent' });
  const text = out.outputFiles[0].text + `\n// ${++serial}`;   // 꼬리 주석 = 같은 모듈을 다른 URL 조건으로 다시 평가하기 위한 캐시 비키기
  return import('data:text/javascript;base64,' + Buffer.from(text).toString('base64'));
}

/* ───────────── ① 렌더러 고르기 ───────────── */
const plain = { grid: ['#'], w: 1, h: 1 }, arch = { ...plain, architecture: { version: 2 } }, town = { ...plain, architecture: { version: 2 }, visual: { schema: 'x' } };
for (const [search, want] of [
  ['', { plain: null, arch: 'projected' }],
  ['?dungeonArt=prototype', { plain: 'projected', arch: 'projected' }],
  ['?dungeonArt=flat', { plain: 'flat', arch: 'flat' }],
  ['?dungeonArt=off', { plain: null, arch: null }],
  ['?dungeonArt=nonsense', { plain: null, arch: 'projected' }],
]) {
  globalThis.location = { search };
  const { dungeonArtFor } = await load('src/scene/dungeonPrototype.ts');
  check(`① '${search || '(파라미터 없음)'}' — architecture 없는 층=${want.plain} · 있는 층=${want.arch}`,
    dungeonArtFor(plain, false) === want.plain && dungeonArtFor(arch, false) === want.arch);
  check(`① '${search || '(파라미터 없음)'}' — 마을 층(town · visual)에서는 꺼짐`,
    dungeonArtFor(arch, true) === null && dungeonArtFor(town, false) === null && dungeonArtFor(plain, true) === null);
}

/* ───────────── ② 엔진 소유 소품 ───────────── */
const { planDungeonDecor, PROP_KINDS } = await load('src/scene/dungeonDecor.ts');
const { planDungeonArchitecture } = await load('src/scene/dungeonArchitecture.ts');
const made = spawnSync(process.env.WL_PYTHON || 'python', ['-c',
  "import sys,json;sys.path.insert(0,'art/dungeon-v2');from preview_server import stream;print(json.dumps([json.loads(stream(i,p).decode().splitlines()[1]) for p in ('original','concept') for i in range(12)]))"],
  { cwd: root, encoding: 'utf8', maxBuffer: 8 * 1024 * 1024, env: { ...process.env, PYTHONUTF8: '1', DUNGEON_BRAIN_BACKEND: 'dummy' } });
assert.equal(made.status, 0, made.stderr);
// D92(09-20): 엔진이 concept 층에 제 소품(level.props)을 싣기 시작했다 — ② 는 '엔진 목록이 없을 때의 추첨'과
//   '있을 때의 그대로 받기'를 **둘 다** 보는 자리라, 입력에서 props 를 걷어 옛 조건을 되살린 뒤 아래에서 직접 얹는다
//   (renderer_streams.py 가 같은 이유로 덮어쓴다). 클라이언트 코드는 무접촉.
const levels = JSON.parse(made.stdout).map(({ props, ...L }) => L);
check('② kind 어휘 = barrel·crate·jar·rubble·storage·ruin', JSON.stringify(Object.keys(PROP_KINDS)) === JSON.stringify(['barrel', 'crate', 'jar', 'rubble', 'storage', 'ruin']));
const kinds = [...Object.keys(PROP_KINDS), 'mystery'];
let placed = 0, accents = 0, lottery = 0;
for (const L of levels) {
  const torches = planDungeonArchitecture(L).torches;
  const base = planDungeonDecor(L, torches);
  lottery += base.filter(o => o.surface === 'floor').length;
  assert.ok(base.every(o => o.kind === undefined && o.id === undefined), 'props 가 없으면 추첨 결과에 엔진 필드가 붙지 않는다');
  // 엔진이 보냈다고 치는 목록 — 방마다 안쪽 바닥 한 칸(추첨이 고르지 않을 한가운데도 그대로 받아야 한다)
  const props = L.rooms.map((r, i) => ({ id: i % 2 ? 'p' + i : i, kind: kinds[i % kinds.length], x: r.x + (r.w >> 1), y: r.y + (r.h >> 1),
    ...(i % 3 === 0 ? { blocks: false } : i % 3 === 1 ? { blocks: true } : {}) })).filter(p => L.grid[p.y][p.x] === '.');
  const withProps = { ...L, props }, before = JSON.stringify(withProps);
  const got = planDungeonDecor(withProps, torches);
  assert.equal(JSON.stringify(withProps), before, '입력 스냅샷을 고치지 않는다');
  assert.deepEqual(got, planDungeonDecor(withProps, torches), '같은 입력 = 같은 결과');
  const floor = got.filter(o => o.surface === 'floor'), wall = got.filter(o => o.surface === 'wall');
  assert.deepEqual(floor.map(o => [o.id, o.kind, o.x, o.y]), props.map(p => [p.id, p.kind, p.x, p.y]), '바닥 소품 = 엔진 목록 그대로(추첨 없음)');
  for (const [i, o] of floor.entries()) {
    assert.equal(o.frame, o.kind === 'mystery' ? 1 : PROP_KINDS[o.kind], 'kind → 프레임(모르는 kind 는 나무 상자)');
    assert.equal(o.blocks, props[i].blocks !== false, 'blocks 기본값은 막음');
    assert.ok(Math.abs(o.offsetX) <= 2 && Math.abs(o.offsetY) <= 2, '흔들림은 ±2px');
  }
  assert.deepEqual(wall, base.filter(o => o.surface === 'wall'), '벽 부착물은 props 가 있든 없든 같은 자리');
  assert.deepEqual(planDungeonDecor({ ...L, props: [] }, torches).filter(o => o.surface === 'floor'), [], '빈 목록도 엔진의 답이다 — 추첨하지 않는다');
  placed += floor.length; accents += wall.length;
}
check(`② level.props ${levels.length}층 — 바닥 소품 ${placed}개를 목록 그대로 · 벽 부착물 ${accents}개 불변 · props 없는 판의 추첨 ${lottery}개`, placed > 0 && accents > 0 && lottery > 0);

/* ───────────── ③ 관전 로그 문장 ───────────── */
const { evLine, resolveTarget } = await load('src/text/evline.ts');
const run = { names: { 1: '두란' }, colors: { 1: '#fff' } };
const f = { monsters: [], features: [{ id: 3, type: 'bookshelf', name: '낡은 책장', x: 1, y: 1 }],
  level: { props: [{ id: 'p2', kind: 'barrel', x: 2, y: 2, blocks: true }, { id: 5, kind: 'ruin', x: 3, y: 3 }] } };
const line = (e) => evLine({ type: 'interact', char: '1', target: 'f3', ...e }, f, run);
const has = (e, ...bits) => { const l = line(e); return !!l && bits.every(b => l.html.includes(b)); };
check('③ read — 이름 · 읽은 글', has({ result: 'read', text: '고블린 셋' }, '낡은 책장을 읽었다', '「고블린 셋」'));
check('③ read — text 없이도 한 줄', has({ result: 'read' }, '낡은 책장을 읽었다') && !line({ result: 'read' }).html.includes('「'));
check('③ sat · hp', has({ result: 'sat', name: '긴 의자', hp: 9 }, '긴 의자에 앉았다', '(HP 9)'));
check('③ drank', has({ result: 'drank', name: '우물' }, '우물에서 물을 마셨다'));
check('③ browsed · wares(문자열 · {name} 섞임)', has({ result: 'browsed', name: '노점', wares: ['밧줄', { name: '등불' }] }, '노점을 둘러봤다', '밧줄·등불'));
check('③ practiced', has({ result: 'practiced', name: '훈련대' }, '훈련대에서 연습했다'));
check('③ rummaged — found 있음(gold)', has({ result: 'rummaged', target: 'p2', found: '회복 물약' }, '통을 뒤졌다', '회복 물약 발견') && line({ result: 'rummaged', target: 'p2', found: '회복 물약' }).cls === 'gold');
check('③ rummaged — found 없음([] · false · 0 · 없음 = dim)', [[], false, 0, undefined, null].every(v =>
  has({ result: 'rummaged', target: 'p2', found: v }, '통을 뒤졌다', '아무것도 없다') && line({ result: 'rummaged', target: 'p2', found: v }).cls === 'dim'));
// 엔진(interactables.handle)이 실제로 보내는 꼴 — 나온 것은 got("potion"|"treasure"|"nothing"), 대상 이름은 what. found 만 읽으면 얻은 통도 빈손으로 찍힌다(09-20 수선)
const eng = { result: 'rummaged', what: '낡은 통', use_kind: 'rummage' };
check('③ rummaged — got:potion(gold · 소지 수)', has({ ...eng, got: 'potion', potions: 2 }, '낡은 통을 뒤졌다', '회복 물약 발견', '(소지 물약 2병)')
  && line({ ...eng, got: 'potion', potions: 2 }).cls === 'gold');
check('③ rummaged — got:treasure(gold · 소지 수 · 의뢰 진행)', has({ ...eng, got: 'treasure', bag: 1, quest: [{ title: '보물 셋', n: 1, need: 3 }] },
  '낡은 통을 뒤졌다', '보물 발견', '(모은 보물 1개)', '의뢰 「보물 셋」 1/3') && line({ ...eng, got: 'treasure', bag: 1 }).cls === 'gold');
check('③ rummaged — got:nothing(dim) · found 가 같이 실려도 got 이 먼저', [{}, { found: '회복 물약' }].every(x =>
  has({ ...eng, got: 'nothing', ...x }, '낡은 통을 뒤졌다', '아무것도 없다') && line({ ...eng, got: 'nothing', ...x }).cls === 'dim'));
check('③ rummaged — 모르는 got 은 원문 그대로(HTML 로 새지 않는다)', has({ ...eng, got: '<i>gem</i>' }, '&lt;i&gt;gem&lt;/i&gt; 발견'));
check('③ 대상 이름 — name 이 없으면 what(엔진의 칸) · 둘 다 없으면 target', has({ result: 'sat', what: '긴 의자' }, '긴 의자에 앉았다')
  && has({ result: 'sat', name: '돌 의자', what: '긴 의자' }, '돌 의자에 앉았다') && has({ result: 'sat' }, '낡은 책장에 앉았다'));
const oldViewer = readFileSync(path.join(root, 'viewer/index.html'), 'utf8');
check("③ 옛 뷰어(viewer/index.html)의 rummaged 꼬리말도 got 을 먼저 읽는다", oldViewer.includes("e.got != null ? e.got !== 'nothing'"));
check('③ lodged · warmed', has({ result: 'lodged', name: '여관', heal: 3, hp: 12 }, '여관에서 묵었다', 'HP +3', '(HP 12)') && has({ result: 'warmed', name: '화덕' }, '화덕 곁에서 불을 쬐었다'));
check('③ used_up', has({ result: 'used_up', target: 'p5' }, '부러진 기둥', '남은 것이 없다'));
check('③ 모르는 result 는 옛 폴백 그대로', has({ result: 'zzz_new' }, '상호작용 낡은 책장 — zzz_new') && line({ result: 'zzz_new' }).cls === 'dim');
check('③ 이름은 HTML 로 새지 않는다', has({ result: 'sat', name: '<b>x</b>' }, '&lt;b&gt;x&lt;/b&gt;에 앉았다'));
check("③ 소품 대상 — 'p2' · 숫자 id · 없는 id", resolveTarget('p2', f, run) === '통' && resolveTarget('p5', f, run) === '부러진 기둥' && resolveTarget('p9', f, run) === '소품');
check('③ 조합형 use(effect_type=interact)도 같은 문장', !!evLine({ type: 'use', effect_type: 'interact', char: '1', target: 'f3', result: 'read' }, f, run)?.html.includes('낡은 책장을 읽었다'));

console.log(`ALL PASS — game/verify/props.mjs (${checks} checks · LLM 0콜)`);

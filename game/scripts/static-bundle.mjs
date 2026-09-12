// 정적 배포 묶음(2026-09-12, 챔피언십 제출 — 메모 §3-2 "관전 페이지 정적 빌드"). `vite build --mode static` 뒤에 실행한다.
// dist-static/ 에 (1) viewer 에셋(tiles.json + 타일 시트 + SD 스프라이트·atlas) (2) 첨부 판(runs/*.jsonl)
// (3) runs/index.json(판 목록 — 첫 항목이 기본으로 열린다) (4) .nojekyll 을 넣는다. 이 폴더 하나가 론처 없이
// 정적 호스팅(GitHub Pages 등)에서 열리는 조건이다. LLM 0콜, 리포는 읽기만.
//   node scripts/static-bundle.mjs                      → game/static-runs.json 의 목록
//   node scripts/static-bundle.mjs runs/a.jsonl runs/b.jsonl   또는 WL_RUNS="runs/a.jsonl,runs/b.jsonl"  → 덮어씀
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const gameDir = path.resolve(here, '..');
const root = path.resolve(gameDir, '..');                  // dungeon/
const dist = path.join(gameDir, 'dist-static');

if (!fs.existsSync(path.join(dist, 'index.html'))) {
  console.error('dist-static/index.html 이 없다 — 먼저 `vite build --mode static` (npm run build:static 이 순서대로 한다)');
  process.exit(2);
}

const copies = [];
function copyFile(rel) {                                   // 리포 루트 기준 상대경로 → dist-static/ 같은 자리
  const src = path.join(root, rel), dst = path.join(dist, rel);
  if (!fs.existsSync(src)) throw new Error('없는 파일: ' + rel);
  fs.mkdirSync(path.dirname(dst), { recursive: true });
  fs.copyFileSync(src, dst);
  copies.push([rel, fs.statSync(src).size]);
}
function copyDir(rel) {
  for (const n of fs.readdirSync(path.join(root, rel))) {
    const r = rel + '/' + n;
    if (fs.statSync(path.join(root, r)).isFile()) copyFile(r);
  }
}

// (1) viewer 에셋 — 클라이언트가 fetch/Phaser 로 읽는 것(src/assets/tiles.ts·sd.ts·DungeonScene.preload). world.ts 의 그림은 Vite 가 번들에 넣는다.
copyFile('viewer/tiles.json');
const tiles = JSON.parse(fs.readFileSync(path.join(root, 'viewer/tiles.json'), 'utf8'));
const sheetDir = path.posix.dirname('viewer/' + tiles.tilesets[tiles.default].sheet);
copyDir(sheetDir);                                         // 타일 시트 + License.txt(CC0 표기도 같이 간다)
copyDir('viewer/assets/sprites/sd');                        // atlas.json + 프리셋×헤어 PNG

// (2) 첨부 판 + (3) 목록
const argRuns = process.argv.slice(2);
const envRuns = (process.env.WL_RUNS || '').split(',').map(s => s.trim()).filter(Boolean);
const listed = JSON.parse(fs.readFileSync(path.join(gameDir, 'static-runs.json'), 'utf8')).runs || [];
const runs = argRuns.length ? argRuns : envRuns.length ? envRuns : listed;
if (!runs.length) throw new Error('첨부할 판이 없다 — game/static-runs.json 또는 인자/WL_RUNS');

function labelOf(rel) {
  const first = fs.readFileSync(path.join(root, rel), 'utf8').split('\n')[0];
  let meta = null;
  try { meta = JSON.parse(first); } catch { /* 첫 줄이 run_meta 가 아니면 파일명만 */ }
  const stamp = rel.match(/stream-(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})\.jsonl$/);
  const when = stamp ? `${stamp[1]}.${stamp[2]}.${stamp[3]} · ${stamp[4]}:${stamp[5]}` : rel.replace(/^runs\//, '');
  const party = (meta?.party || []).map(p => p.name || p.job).filter(Boolean);
  const seed = meta?.seed ?? null;
  const label = when + (party.length ? ' · ' + party.join('·') : '') + (seed != null ? ` (seed ${seed})` : '');
  return { path: rel, label, seed, party };
}
const index = { runs: runs.map(r => { copyFile(r); return labelOf(r); }) };
fs.mkdirSync(path.join(dist, 'runs'), { recursive: true });
fs.writeFileSync(path.join(dist, 'runs', 'index.json'), JSON.stringify(index, null, 2) + '\n');
fs.writeFileSync(path.join(dist, '.nojekyll'), '');        // GitHub Pages: 밑줄 시작 경로도 그대로 서빙

// 확인 — 클라이언트가 읽는 파일이 전부 dist-static 안에 있는가
const must = ['index.html', 'viewer/tiles.json', 'viewer/' + tiles.tilesets[tiles.default].sheet,
              'viewer/assets/sprites/sd/atlas.json', 'runs/index.json', ...runs];
const missing = must.filter(m => !fs.existsSync(path.join(dist, m)));
if (missing.length) { console.error('빠진 파일:', missing); process.exit(1); }
const total = copies.reduce((a, [, s]) => a + s, 0);
console.log(`static-bundle: ${copies.length}개 복사(${(total / 1024 / 1024).toFixed(1)} MB) → ${path.relative(root, dist)}/`);
for (const r of index.runs) console.log('  판  ' + r.path + '  —  ' + r.label);

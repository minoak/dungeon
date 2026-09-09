// imagegen 원본 → 게임용 PNG. 원본은 보존하며 배경 키 추출·셀 분리·최근접 축소·발 정렬만 한다.
// 실행: node art/world-v1/build-runtime.mjs
// sharp가 프로젝트에 없으면 Codex 번들 런타임을 사용한다. 새 이미지를 그리는 스크립트가 아니다.
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
const require = createRequire(import.meta.url);
let sharp;
try { sharp = require('sharp'); } catch {
  sharp = require(path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp'));
}
const here = path.dirname(fileURLToPath(import.meta.url));
const output = path.resolve(here, '../../game/src/assets/world');
await fs.mkdir(output, { recursive: true });
const CELL = 96, FOOT = 92;
const report = {};

async function source(stem, key = false) {
  const { data, info } = await sharp(path.join(here, `${stem}-source.png`)).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  if (key) {
    for (let i = 0; i < data.length; i += 4) {
      const r = data[i], g = data[i + 1], b = data[i + 2];
      if (r > 95 && b > 85 && Math.min(r, b) - g > 65) data[i + 3] = 0;
    }
    // 배경과 섞인 키 색의 얇은 테두리도 알파로 제외한다. 내부 색은 건드리지 않는다.
    const original = Buffer.from(data);
    for (let y = 1; y < info.height - 1; y++) for (let x = 1; x < info.width - 1; x++) {
      const i = (y * info.width + x) * 4;
      if (!original[i + 3] || Math.min(original[i], original[i + 2]) - original[i + 1] < 35) continue;
      if ([-1, 1, -info.width, info.width].some(d => !original[i + d * 4 + 3])) data[i + 3] = 0;
    }
  }
  return { data, width: info.width, height: info.height };
}

function bounds(src, cols, rows, index) {
  const col = index % cols, row = Math.floor(index / cols);
  const cell = [Math.round(col * src.width / cols), Math.round(row * src.height / rows),
    Math.round((col + 1) * src.width / cols), Math.round((row + 1) * src.height / rows)];
  let left = cell[2], top = cell[3], right = cell[0], bottom = cell[1];
  for (let y = cell[1]; y < cell[3]; y++) for (let x = cell[0]; x < cell[2]; x++) {
    if (src.data[(y * src.width + x) * 4 + 3] < 128) continue;
    left = Math.min(left, x); top = Math.min(top, y); right = Math.max(right, x + 1); bottom = Math.max(bottom, y + 1);
  }
  assert(right > left && bottom > top, `빈 셀 ${index}`);
  assert(left > cell[0] + 1 && top > cell[1] + 1 && right < cell[2] - 1 && bottom < cell[3] - 1,
    `셀 ${index}가 경계에 닿는다. 배경이나 프레임 분리를 확인할 것: ${[left, top, right, bottom]}`);
  return { left, top, width: right - left, height: bottom - top };
}

async function pack(stem, cols, rows, dimensions) {
  const src = await source(stem, true);
  const boxes = Array.from({ length: cols * rows }, (_, i) => bounds(src, cols, rows, i));
  const pieces = [], frames = [];
  const commonScale = dimensions.length === 1 ? Math.min(dimensions[0][0] / Math.max(...boxes.map(b => b.width)),
    dimensions[0][1] / Math.max(...boxes.map(b => b.height))) : null;
  for (let i = 0; i < boxes.length; i++) {
    const b = boxes[i], limit = dimensions[i] || dimensions[0];
    const scale = commonScale ?? Math.min(limit[0] / b.width, limit[1] / b.height);
    const width = Math.round(b.width * scale), height = Math.round(b.height * scale);
    // 고블린은 귀·머리 중심을 기준으로 정렬한다. 아래쪽 칼이 움직여도 몸이 밀리지 않는다.
    let anchor = b.left + b.width / 2;
    if (stem === 'goblin') {
      let lo = b.left + b.width, hi = b.left;
      for (let y = b.top; y < b.top + b.height * 0.44; y++) for (let x = b.left; x < b.left + b.width; x++) {
        if (src.data[(y * src.width + x) * 4 + 3] < 128) continue;
        lo = Math.min(lo, x); hi = Math.max(hi, x + 1);
      }
      anchor = (lo + hi) / 2;
    }
    const dx = Math.round(CELL / 2 - (anchor - b.left) * scale), dy = FOOT - height;
    assert(dx >= 2 && dx + width <= CELL - 2 && dy >= 2, `${stem} ${i}: 런타임 잘림`);
    const png = await sharp(src.data, { raw: { width: src.width, height: src.height, channels: 4 } })
      .extract(b).resize(width, height, { kernel: 'nearest' }).png().toBuffer();
    pieces.push({ input: png, left: i % cols * CELL + dx, top: Math.floor(i / cols) * CELL + dy });
    frames.push({ source: b, anchor, scale, runtime: [dx, dy, width, height] });
  }
  await sharp({ create: { width: CELL * cols, height: CELL * rows, channels: 4, background: '#00000000' } })
    .composite(pieces).png().toFile(path.join(output, `${stem}.png`));
  report[stem] = { sourceSize: [src.width, src.height], size: [CELL * cols, CELL * rows], frames };
}

const terrain = await source('terrain');
assert.equal(terrain.width, terrain.height * 2, '지형 시트는 4×2 정사각 타일이어야 한다');
const ground = [];
for (let i = 0; i < 8; i++) {
  const col = i % 4, row = Math.floor(i / 4);
  const left = Math.round(col * terrain.width / 4), top = Math.round(row * terrain.height / 2);
  const width = Math.round((col + 1) * terrain.width / 4) - left;
  const height = Math.round((row + 1) * terrain.height / 2) - top;
  const input = await sharp(terrain.data, { raw: { width: terrain.width, height: terrain.height, channels: 4 } })
    .extract({ left, top, width, height }).resize(48, 48, { kernel: 'nearest' }).png().toBuffer();
  ground.push({ input, left: col * 48, top: row * 48 });
}
await sharp({ create: { width: 192, height: 96, channels: 4, background: '#00000000' } }).composite(ground)
  .png().toFile(path.join(output, 'terrain.png'));
report.terrain = { sourceSize: [terrain.width, terrain.height], size: [192, 96], frames: 8 };
await pack('goblin', 3, 4, [[78, 74]]);
await pack('spider', 3, 4, [[84, 60]]);
await pack('props', 4, 2, [[64, 82], [48, 44], [50, 42], [60, 60], [38, 28], [24, 30], [30, 40], [30, 38]]);
await pack('traps', 2, 2, [[44, 38], [44, 32], [42, 36], [38, 52]]);
await fs.writeFile(path.join(here, 'build-report.json'), JSON.stringify(report, null, 2) + '\n');
console.log('지형 8 · 몬스터 2종 × 12프레임 · 오브젝트 12 →', output);

// Packaging only: preserve generated pixels, crop cells, nearest-neighbour resize, align feet.
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
const require = createRequire(import.meta.url);
let sharp;
try { sharp = require('sharp'); } catch { sharp = require(path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp')); }
const here = path.dirname(fileURLToPath(import.meta.url));
const runtime = path.join(here, 'runtime');
const game = path.resolve(here, '../../game/src/assets/world');
await fs.mkdir(runtime, { recursive: true });
const CELL = 96, FOOT = 91;
const manifest = { cell: CELL, foot: FOOT, columns: 3, directions: ['front', 'right', 'back', 'left'], walk: [1, 0, 2, 0], frame_ms: 125, characters: [] };
const report = {};
const names = { wanderer: ['wandering_adventurer', '떠돌이 모험자'], apprentice: ['apprentice_adventurer', '견습 모험자'], vendor: ['street_vendor', '노점 상인'] };
for (const [key, [id, name]] of Object.entries(names)) {
  const { data, info } = await sharp(path.join(here, key + '-source.png')).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  const { width: W, height: H } = info;
  const opaque = (x, y) => data[(y * W + x) * 4 + 3] >= 128;
  const rows = Array.from({ length: H }, (_, y) => { let n = 0; for (let x = 0; x < W; x++) if (opaque(x, y)) n++; return n; });
  // Generation may trim exterior margins: choose transparent gutters near each nominal seam.
  const seam = (counts, at, radius) => {
    let best = Math.round(at);
    for (let p = Math.max(1, Math.floor(at - radius)); p < Math.min(counts.length - 1, at + radius); p++) {
      if (counts[p] < counts[best] || (counts[p] === counts[best] && Math.abs(p - at) < Math.abs(best - at))) best = p;
    }
    assert(counts[best] === 0, `${key}: no transparent gutter near ${at}`);
    return best;
  };
  const ys = [0, ...[1, 2, 3].map(i => seam(rows, H * i / 4, H * .06)), H];
  const boxes = [];
  for (let row = 0; row < 4; row++) {
    const columns = Array.from({ length: W }, (_, x) => { let n = 0; for (let y = ys[row]; y < ys[row + 1]; y++) if (opaque(x, y)) n++; return n; });
    const xs = [0, ...[1, 2].map(i => seam(columns, W * i / 3, W * .06)), W];
    for (let col = 0; col < 3; col++) {
      let left = W, top = H, right = -1, bottom = -1;
      for (let y = ys[row]; y < ys[row + 1]; y++) for (let x = xs[col]; x < xs[col + 1]; x++) if (opaque(x, y)) {
        left = Math.min(left, x); right = Math.max(right, x); top = Math.min(top, y); bottom = Math.max(bottom, y);
      }
      assert(right > left && bottom > top, `${key} empty frame ${row},${col}`);
      // Include a one-pixel fringe so semi-transparent edge pixels are retained.
      left = Math.max(xs[col], left - 1); top = Math.max(ys[row], top - 1);
      right = Math.min(xs[col + 1] - 1, right + 1); bottom = Math.min(ys[row + 1] - 1, bottom + 1);
      boxes.push({ left, top, width: right - left + 1, height: bottom - top + 1 });
    }
  }
  const scale = Math.min(84 / Math.max(...boxes.map(b => b.width)), 82 / Math.max(...boxes.map(b => b.height)));
  const pieces = [], frames = [];
  for (const [i, b] of boxes.entries()) {
    const width = Math.round(b.width * scale), height = Math.round(b.height * scale);
    const dx = Math.round((CELL - width) / 2), dy = FOOT - height;
    assert(dx >= 3 && dx + width <= CELL - 3 && dy >= 3, `${key} clipping frame ${i}`);
    const png = await sharp(data, { raw: { width: W, height: H, channels: 4 } }).extract(b).resize(width, height, { kernel: 'nearest' }).png().toBuffer();
    pieces.push({ input: png, left: (i % 3) * CELL + dx, top: Math.floor(i / 3) * CELL + dy });
    frames.push({ source: b, target: [dx, dy, width, height] });
  }
  const filename = `npc-${key}.png`;
  await sharp({ create: { width: CELL * 3, height: CELL * 4, channels: 4, background: '#00000000' } }).composite(pieces).png().toFile(path.join(runtime, filename));
  await fs.copyFile(path.join(runtime, filename), path.join(game, filename));
  manifest.characters.push({ id, name, key: `wl-npc-${key}`, sheet: filename });
  report[key] = { source: [W, H], output: [288, 384], scale, frames };
}
await fs.writeFile(path.join(runtime, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
await fs.writeFile(path.join(here, 'build-report.json'), JSON.stringify(report, null, 2) + '\n');
console.log('Packed three NPCs, 36 frames: 288x384 RGBA, 96px cells, foot y=91.');

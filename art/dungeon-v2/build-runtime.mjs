// Pack imagegen output; no hand-drawn replacement artwork. Originals stay intact.
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
const report = { generator: 'built-in imagegen', terrain: [], props: [] };
await fs.mkdir(path.join(here, 'runtime'), { recursive: true });
const terrain = sharp(path.join(here, 'source/terrain.png'));
const tm = await terrain.metadata();
assert(Math.abs(tm.width / tm.height - 2) < .02, 'Expected 4 by 2 terrain atlas');
const tiles = [];
for (let i = 0; i < 8; i++) {
  const x = Math.round(i % 4 * tm.width / 4), y = Math.round(Math.floor(i / 4) * tm.height / 2);
  const width = Math.round((i % 4 + 1) * tm.width / 4) - x;
  const height = Math.round((Math.floor(i / 4) + 1) * tm.height / 2) - y;
  // The generated atlas has separator strokes. Exclude them from floor crops.
  const inset = i < 4 ? 12 : 0;
  const box = { left: x + inset, top: y + inset, width: width - inset * 2, height: height - inset * 2 };
  tiles.push({ input: await terrain.clone().extract(box).resize(48, 48, { kernel: 'nearest' }).png().toBuffer(), left: i % 4 * 48, top: Math.floor(i / 4) * 48 });
  report.terrain.push(box);
}
await sharp({ create: { width: 192, height: 96, channels: 4, background: '#00000000' } }).composite(tiles).png().toFile(path.join(here, 'runtime/terrain.png'));
const { data, info } = await sharp(path.join(here, 'source/props.png')).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
assert(info.width === info.height, 'Props source must be square');
assert(data[3] === 0, 'Props need real transparency, not a painted background');
const dims = [[19, 43], [34, 62], [44, 36], [46, 46]], sprites = [];
for (let i = 0; i < 4; i++) {
  const x0 = i % 2 * info.width / 2, y0 = Math.floor(i / 2) * info.height / 2;
  let left = x0 + info.width / 2, top = y0 + info.height / 2, right = x0, bottom = y0;
  for (let y = y0; y < y0 + info.height / 2; y++) for (let x = x0; x < x0 + info.width / 2; x++) {
    if (data[(y * info.width + x) * 4 + 3] < 32) continue;
    left = Math.min(left, x); top = Math.min(top, y); right = Math.max(right, x + 1); bottom = Math.max(bottom, y + 1);
  }
  assert(right > left && bottom > top && left > x0 && top > y0 && right < x0 + info.width / 2 && bottom < y0 + info.height / 2, 'Missing or clipped sprite');
  const box = { left, top, width: right - left, height: bottom - top };
  const scale = Math.min(dims[i][0] / box.width, dims[i][1] / box.height);
  const w = Math.round(box.width * scale), h = Math.round(box.height * scale);
  const input = await sharp(data, { raw: info }).extract(box).resize(w, h, { kernel: 'nearest' }).png().toBuffer();
  sprites.push({ input, left: i % 2 * 96 + Math.floor((96 - w) / 2), top: Math.floor(i / 2) * 96 + 92 - h });
  report.props.push({ source: box, width: w, height: h, foot: 92 });
}
await sharp({ create: { width: 192, height: 192, channels: 4, background: '#00000000' } }).composite(sprites).png().toFile(path.join(here, 'runtime/props.png'));
// A continuous eight-tile floor patch preserves slab silhouettes across grid boundaries.
await sharp(path.join(here, 'source/floor.png')).resize(384, 384, { kernel: 'nearest' }).png()
  .toFile(path.join(here, 'runtime/floor.png'));
const decorSource = sharp(path.join(here, 'source/decor.png'));
const { data: dd, info: di } = await decorSource.ensureAlpha().raw().toBuffer({ resolveWithObject: true });
assert.equal(di.width / 3, di.height / 2, 'Decor must be 3 by 2 square cells');
assert.equal(dd[3], 0, 'Decor background must be genuinely transparent');
const decorPieces = [], decorReport = [];
const sizes = [[36, 33], [39, 36], [35, 27], [36, 24], [39, 39], [29, 42]];
const sourceCell = di.width / 3;
for (let i = 0; i < 6; i++) {
  const x0 = i % 3 * sourceCell, y0 = Math.floor(i / 3) * sourceCell;
  let left = x0 + sourceCell, top = y0 + sourceCell, right = x0, bottom = y0;
  for (let y = y0; y < y0 + sourceCell; y++) for (let x = x0; x < x0 + sourceCell; x++) {
    if (dd[(y * di.width + x) * 4 + 3] <= 32) continue;
    left = Math.min(left, x); right = Math.max(right, x + 1); top = Math.min(top, y); bottom = Math.max(bottom, y + 1);
  }
  assert(right > left && bottom > top && left > x0 && top > y0 && right < x0 + sourceCell && bottom < y0 + sourceCell, 'Clipped or empty decor');
  const box = { left, top, width: right - left, height: bottom - top };
  const scale = Math.min(sizes[i][0] / box.width, sizes[i][1] / box.height);
  const w = Math.round(box.width * scale), h = Math.round(box.height * scale);
  decorPieces.push({ input: await decorSource.clone().extract(box).resize(w, h, { kernel: 'nearest' }).png().toBuffer(),
    left: i % 3 * 96 + Math.floor((96 - w) / 2), top: Math.floor(i / 3) * 96 + 92 - h });
  decorReport.push({ source: box, width: w, height: h });
}
await sharp({ create: { width: 288, height: 192, channels: 4, background: '#00000000' } }).composite(decorPieces).png()
  .toFile(path.join(here, 'runtime/decor.png'));
report.floor = { source: 'source/floor.png', width: 384, height: 384, mode: 'continuous-world-pattern' };
report.decor = decorReport;
// Four square material cells: clean front, worn front, coping, attached pilaster.
const wallSource = sharp(path.join(here, 'source/walls.png'));
const wm = await wallSource.metadata();
assert.equal(wm.width, wm.height, 'Wall atlas must be square');
assert.equal(wm.width % 2, 0, 'Wall cells must divide evenly');
const wallCells = [], wallReport = [];
for (let i = 0; i < 4; i++) {
  const box = { left: i % 2 * wm.width / 2, top: Math.floor(i / 2) * wm.height / 2,
    width: wm.width / 2, height: wm.height / 2 };
  wallCells.push({ input: await wallSource.clone().extract(box).resize(48, 48, { kernel: 'nearest' }).png().toBuffer(),
    left: i % 2 * 48, top: Math.floor(i / 2) * 48 });
  wallReport.push(box);
}
await sharp({ create: { width: 96, height: 96, channels: 4, background: '#00000000' } })
  .composite(wallCells).png().toFile(path.join(here, 'runtime/walls.png'));
report.walls = wallReport;
await fs.writeFile(path.join(here, 'build-report.json'), JSON.stringify(report, null, 2) + '\n');
console.log('Packed 8 terrain tiles, continuous flagstones, 4 wall parts, 4 props and 6 furnishings.');

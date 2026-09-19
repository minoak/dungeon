// Test the actual pure renderer planner against production-generated maps; no browser or brain backend.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
const here = path.dirname(fileURLToPath(import.meta.url)), root = path.resolve(here, '../..');
const require = createRequire(path.join(root, 'game/package.json'));
const ts = require('typescript');
const source = await fs.readFile(path.join(root, 'game/src/scene/dungeonDecor.ts'), 'utf8');
const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
const { planDungeonDecor } = await import('data:text/javascript;base64,' + Buffer.from(js).toString('base64'));
const architectureSource = await fs.readFile(path.join(root, 'game/src/scene/dungeonArchitecture.ts'), 'utf8');
const architectureJs = ts.transpileModule(architectureSource, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
const { planDungeonArchitecture } = await import('data:text/javascript;base64,' + Buffer.from(architectureJs).toString('base64'));
const generated = spawnSync(process.env.WL_PYTHON || 'python', ['-c',
  "import sys,json;sys.path.insert(0,'art/dungeon-v2');from preview_server import stream;print(json.dumps([json.loads(stream(i,p).decode().splitlines()[1]) for p in ('original','concept') for i in range(100)]))"],
  { cwd: root, encoding: 'utf8', maxBuffer: 8 * 1024 * 1024 });
assert.equal(generated.status, 0, generated.stderr);
// D92(2026-09-20): the engine now ships its own props on concept levels; this file tests the client lottery,
// so strip level.props to restore the pre-D92 input (the engine-owned path is covered by game/verify/props.mjs).
const levels = JSON.parse(generated.stdout).map(({ props, ...L }) => L), frames = new Set();
let count = 0, floorCount = 0, attachedPiers = 0, previousRuleAttachedPiers = 0;
for (const L of levels) {
  const before = JSON.stringify(L);
  const architecture = planDungeonArchitecture(L);
  assert.deepEqual(architecture, planDungeonArchitecture(L), 'Architecture reproduces by seed');
  const reserved = architecture.torches;
  assert.equal(architecture.doors.length, L.grid.join('').split('+').length - 1, 'Every engine door gets a directional sprite');
  assert.equal(new Set(architecture.walls.map(p => `${p.x},${p.y}`)).size, architecture.walls.length, 'No duplicate wall sprites');
  for (const p of architecture.walls) assert.equal(L.grid[p.y][p.x], '#', 'Walls only occupy engine walls');
  const open = (x,y) => '.+'.includes(L.grid[y]?.[x] ?? '#');
  const fronts = new Map(architecture.walls.filter(p=>p.kind==='front').map(p=>[`${p.x},${p.y}`,p]));
  for (const p of fronts.values()) {
    const {x,y}=p, n=open(x,y-1), s=open(x,y+1);
    const end=(s&&(!open(x-1,y+1)||!open(x+1,y+1)))||(n&&(!open(x-1,y-1)||!open(x+1,y-1)));
    if(end||(x+(L.master_seed??0)%5)%5===0)previousRuleAttachedPiers++;
    if(!p.pier)continue;
    attachedPiers++;
    for(let dx=-4;dx<=4;dx++) {
      assert(fronts.has(`${x+dx},${y}`)&&open(x+dx,y-1)===n&&open(x+dx,y+1)===s,'Pier requires a long continuous face');
    }
    for(let dx=1;dx<8;dx++)assert(!fronts.get(`${x+dx},${y}`)?.pier,'Attached piers need eight cells of spacing');
  }
  for (const [x,y] of reserved) assert(architecture.walls.some(p => p.x === x && p.y === y), 'Torch has a supporting wall');
  const objects = planDungeonDecor(L, reserved);
  assert.deepEqual(objects, planDungeonDecor(L, reserved), 'Seed reproduction');
  assert.equal(JSON.stringify(L), before, 'Planner must not mutate source snapshots');
  assert.equal(new Set(objects.map(o => `${o.x},${o.y}`)).size, objects.length, 'No stacked furnishings');
  assert(objects.length > 0, 'Generated dungeon should contain furnishing candidates');
  for (const o of objects) {
    assert.equal(L.grid[o.y]?.[o.x], o.surface === 'floor' ? '.' : '#', 'Furniture surface matches tile');
    assert.equal(o.surface, o.frame < 4 ? 'floor' : 'wall', 'Storage belongs on floors; banners/webs on walls');
    assert(!reserved.some(([x, y]) => x === o.x && y === o.y), 'Reserved torch cells remain free');
    assert(!L.features.some(f => Math.abs(f.x - o.x) + Math.abs(f.y - o.y) <= 1), 'Feature access remains clear');
    assert(Math.abs(L.exit[0] - o.x) + Math.abs(L.exit[1] - o.y) > 1, 'Exit access remains clear');
    if (o.surface === 'floor') {
      floorCount++;
      assert(![...L.party, ...L.monsters].some(p => Math.max(Math.abs(p.x - o.x), Math.abs(p.y - o.y)) <= 1), 'Character and monster space remains clear');
      assert(!L.traps.some(t => t.x === o.x && t.y === o.y), 'No trap overlaps');
      const r = L.rooms.find(r => r.id === o.room);
      assert(o.x >= r.x && o.x < r.x + r.w && o.y >= r.y && o.y < r.y + r.h, 'Floor furniture inside room');
      for (const [x, y] of [[o.x-1,o.y],[o.x+1,o.y],[o.x,o.y-1],[o.x,o.y+1]]) {
        if (x < r.x || x >= r.x+r.w || y < r.y || y >= r.y+r.h) assert.notEqual(L.grid[y]?.[x], '.', 'Open corridor mouths remain clear');
      }
    }
    for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
      assert.notEqual(L.grid[o.y + dy]?.[o.x + dx], '+', 'Doorway approaches remain clear');
    }
    frames.add(o.frame); count++;
  }
  // Independently remove every furnished floor footprint and flood-fill what remains.
  const occupied = new Set(objects.filter(o => o.surface === 'floor').map(o => `${o.x},${o.y}`));
  const available = new Set(L.grid.flatMap((row, y) => [...row].flatMap((c, x) =>
    '.+'.includes(c) && !occupied.has(`${x},${y}`) ? [`${x},${y}`] : [])));
  const pending = [available.values().next().value], visited = new Set(pending);
  for (let i = 0; i < pending.length; i++) {
    const [x, y] = pending[i].split(',').map(Number);
    for (const p of [`${x-1},${y}`, `${x+1},${y}`, `${x},${y-1}`, `${x},${y+1}`]) {
      if (available.has(p) && !visited.has(p)) { visited.add(p); pending.push(p); }
    }
  }
  assert.equal(visited.size, available.size, 'All remaining floor cells connected with furniture treated as obstacles');
  assert(visited.has(L.exit.join(',')), 'Exit reachable with furniture treated as obstacles');
}
assert.equal(frames.size, 6, 'All six furnishing types can occur');
assert(attachedPiers>0&&attachedPiers<previousRuleAttachedPiers*.2,'Wall support density is substantially reduced');
const report = { passed: true, seeds: levels.length, profiles: ['original', 'concept'], seedsPerProfile: 100, placements: count, furnishingTypes: [...frames].sort(),
  attachedPiers, previousRuleAttachedPiers, unchangedEngineSnapshots: true, floorPlacements: floorCount, wallAccents: count - floorCount,
  connectedWithFurnitureAsObstacles: true, engineCollisionChanged: false, blockedDoorApproaches: 0,
  torchOverlaps: 0, duplicatePlacements: 0, deterministic: true, llmCalls: 0 };
await fs.writeFile(path.join(here, 'verification/decor.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report));

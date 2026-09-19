import type { LevelLine } from '../stream/types';

export interface DungeonDecor {
  x: number; y: number; frame: number; room: number;
  surface: 'floor' | 'wall'; offsetX: number; offsetY: number;
}

/** Static visual tiles. Floor footprints are tested as obstacles, but do not alter engine collision. */
export function planDungeonDecor(L: LevelLine, torches: [number, number][]): DungeonDecor[] {
  const result: DungeonDecor[] = [];
  const key = (x: number, y: number): string => `${x},${y}`;
  const occupied = new Set(torches.map(([x, y]) => key(x, y)));
  const blocked = new Set<string>();
  const floors: [number, number][] = [];
  for (let y = 0; y < L.h; y++) for (let x = 0; x < L.w; x++) {
    if (L.grid[y][x] === '.' || L.grid[y][x] === '+') floors.push([x, y]);
  }
  const hash = (x: number, y: number, salt: number): number => {
    let n = Math.imul(x + (L.master_seed ?? 0), 374761393) ^ Math.imul(y + salt, 668265263);
    n = Math.imul(n ^ (n >>> 13), 1274126177);
    return (n ^ (n >>> 16)) >>> 0;
  };
  const nearDoor = (x: number, y: number): boolean => {
    for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
      if (L.grid[y + dy]?.[x + dx] === '+') return true;
    }
    return false;
  };
  // Orthogonal connectivity is stronger than eight-way, no-corner-cut connectivity.
  const connected = (): boolean => {
    const start = floors.find(([x, y]) => !blocked.has(key(x, y)));
    if (!start) return false;
    const todo = [start], seen = new Set([key(...start)]);
    for (let i = 0; i < todo.length; i++) {
      const [x, y] = todo[i];
      for (const [xx, yy] of [[x - 1, y], [x + 1, y], [x, y - 1], [x, y + 1]]) {
        const k = key(xx, yy), cell = L.grid[yy]?.[xx];
        if ((cell === '.' || cell === '+') && !blocked.has(k) && !seen.has(k)) {
          seen.add(k); todo.push([xx, yy]);
        }
      }
    }
    return seen.size === floors.length - blocked.size;
  };
  const access = [...L.features, { x: L.exit[0], y: L.exit[1] }];
  const residents = [...(L.party ?? []), ...L.monsters];
  for (const r of L.rooms) {
    const seed = hash(r.x, r.y, r.id);
    const put = (x: number, y: number, frame: number, surface: 'floor' | 'wall'): boolean => {
      const k = key(x, y);
      if (L.grid[y]?.[x] !== (surface === 'floor' ? '.' : '#') || occupied.has(k) || nearDoor(x, y)) return false;
      if (access.some(f => Math.abs(f.x - x) + Math.abs(f.y - y) <= 1)) return false;
      if (surface === 'floor') {
        if (residents.some(f => Math.max(Math.abs(f.x - x), Math.abs(f.y - y)) <= 1)) return false;
        if (L.traps.some(t => t.x === x && t.y === y)) return false;
        // Protect corridor mouths even on maps without '+' doors.
        for (const [xx, yy] of [[x - 1, y], [x + 1, y], [x, y - 1], [x, y + 1]]) {
          if ((xx < r.x || xx >= r.x + r.w || yy < r.y || yy >= r.y + r.h)
            && L.grid[yy]?.[xx] === '.') return false;
        }
        blocked.add(k);
        if (!connected()) { blocked.delete(k); return false; }
      }
      occupied.add(k);
      result.push({ x, y, frame, room: r.id, surface,
        offsetX: surface === 'floor' ? hash(x, y, 1) % 5 - 2 : 0,
        offsetY: surface === 'floor' ? hash(x, y, 2) % 5 - 2 : 0 });
      return true;
    };
    // Only architectural accents remain attached to walls.
    if (seed % 3 !== 0 && !put(r.x, r.y - 1, 4, 'wall')) put(r.x + r.w - 1, r.y - 1, 4, 'wall');
    if (seed % 2 === 0) put(r.x + Math.floor(r.w / 2), r.y - 1, 5, 'wall');
    const spacious = r.w * r.h >= 60;
    if (!spacious && seed % 7 === 0) continue; // Some small rooms need breathing room.
    const corners = [[r.x, r.y], [r.x + r.w - 1, r.y],
      [r.x, r.y + r.h - 1], [r.x + r.w - 1, r.y + r.h - 1]];
    const [ax, ay] = corners[seed % 4];
    const [bx, by] = corners[(seed % 4) ^ 3];
    const candidates: [number, number][] = [];
    for (let y = r.y; y < r.y + r.h; y++) for (let x = r.x; x < r.x + r.w; x++) {
      // Furnish edges and corners; keep the centre open instead of scattering uniformly.
      const edge = Math.min(x - r.x, r.x + r.w - 1 - x, y - r.y, r.y + r.h - 1 - y);
      if (edge === 0 || spacious && edge === 1 && Math.min(Math.abs(x-ax)+Math.abs(y-ay),Math.abs(x-bx)+Math.abs(y-by)) <= 4) candidates.push([x, y]);
    }
    const score = ([x, y]: [number, number]): number => Math.min(Math.abs(x - ax) + Math.abs(y - ay),
      spacious ? Math.abs(x-bx)+Math.abs(y-by)+.8 : Infinity) + hash(x, y, 3) % 7 / 10;
    candidates.sort((a, b) => score(a) - score(b));
    const frames = seed % 3 === 0 ? [0, 1, 0, 2] : seed % 3 === 1 ? [2, 0, 2, 1] : [3, 3, 2, 3];
    const limit = spacious ? Math.min(12, Math.floor(r.w*r.h*.10)) : Math.min(4, Math.max(1, Math.floor(r.w * r.h * .16)));
    let n = 0;
    for (const [x, y] of candidates) {
      if (put(x, y, frames[n % frames.length], 'floor')) n++;
      if (n >= limit) break;
    }
  }
  return result;
}

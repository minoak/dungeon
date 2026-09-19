import type { LevelLine } from '../stream/types';

export interface DungeonDecor {
  x: number; y: number; frame: number; room: number;
  surface: 'floor' | 'wall'; offsetX: number; offsetY: number;
  // D89(09-20) 엔진 소유 소품(level.props)일 때만 — 그림은 kind 가 정한다(렌더러의 해시 변형 없음)
  kind?: string; id?: number | string; blocks?: boolean;
}

/** D89(09-20) 엔진 소유 바닥 소품의 kind 어휘 → decor 시트 프레임(0 통 둘 · 1 나무 상자 더미 · 2 항아리 둘 · 3 석재 잔해).
 *  이 파일의 추첨은 지금까지 프레임 번호(0~3)만 썼다 — 이름은 그림의 내용(art/dungeon-v2/decor-prompt.txt · architecture-prompt.txt)에서 붙였다.
 *  storage(통·상자·깨진 도기 더미) · ruin(부러진 기둥 밑동)은 입체 렌더러에 전용 그림(architecture 시트 3 · 2)이 있고, 여기 적힌 프레임은 평면 렌더러의 대역이다.
 *  모르는 kind 는 나무 상자(1)로 그린다 — 길을 막는 물체일 수 있으니 안 그리는 것보다 낫다. */
export const PROP_KINDS: Record<string, number> = { barrel: 0, crate: 1, jar: 2, rubble: 3, storage: 1, ruin: 3 };

/** Static visual tiles. Floor footprints are tested as obstacles, but do not alter engine collision.
 *  D89: level.props(엔진 소유 소품)가 있으면 바닥 소품 추첨(예약 칸·연결성 검사·모서리 후보)을 통째로 건너뛰고 그 목록을 그대로 돌려준다 —
 *  충돌을 아는 쪽(엔진)이 자리를 정한다. 벽 부착물(거미줄 4 · 깃발 5)은 어느 쪽이든 여기서 정한다(같은 입력 = 같은 자리). */
export function planDungeonDecor(L: LevelLine, torches: [number, number][]): DungeonDecor[] {
  const result: DungeonDecor[] = [];
  const owned = Array.isArray(L.props) ? L.props : null;
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
  if (owned) for (const p of owned) {             // D89 엔진이 정한 자리 그대로 — 클라이언트 몫은 그림 고르기와 ±2px 흔들림뿐
    if (!Number.isInteger(p?.x) || !Number.isInteger(p?.y)) continue;
    const room = L.rooms.find(r => p.x >= r.x && p.x < r.x + r.w && p.y >= r.y && p.y < r.y + r.h);
    const frame = PROP_KINDS[String(p.kind)];
    occupied.add(key(p.x, p.y));
    result.push({ x: p.x, y: p.y, frame: typeof frame === 'number' ? frame : 1, room: room ? room.id : -1, surface: 'floor',
      offsetX: hash(p.x, p.y, 1) % 5 - 2, offsetY: hash(p.x, p.y, 2) % 5 - 2,
      kind: String(p.kind), id: p.id, blocks: p.blocks !== false });
  }
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
    if (owned) continue;                          // D89 바닥 소품은 엔진 몫 — 아래 추첨은 level.props 가 없는 판(옛 스트림·실험실)만
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

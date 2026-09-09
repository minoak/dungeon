// 격자 시야(관전 근사) — 엔진과 픽셀 일치를 요구하지 않는다(GAME_CLIENT_PLAN §2).
// 규칙: 반경 run_meta.sight 의 원 안, 봇 칸에서 목표 칸까지 브레젠험 직선의 '중간 칸'에 '#'(벽)·'+'(문)이
// 있으면 안 보인다. 목표 칸 자체가 벽/문이면 그 칸은 보인다(벽면을 본다). 격자 밖은 막힌 것으로 친다.

export const cellKey = (x: number, y: number): string => x + ',' + y;

export function blocks(ch: string | undefined): boolean {
  return ch === undefined || ch === '#' || ch === '+';
}

/** (x0,y0) 에 선 봇이 반경 radius 안에서 보는 칸 집합("x,y"). */
export function lineOfSight(grid: string[], x0: number, y0: number, radius: number): Set<string> {
  const h = grid.length, w = h ? grid[0].length : 0;
  const out = new Set<string>();
  const r2 = (radius + 0.5) * (radius + 0.5);
  for (let y = y0 - radius; y <= y0 + radius; y++) {
    for (let x = x0 - radius; x <= x0 + radius; x++) {
      if (x < 0 || y < 0 || x >= w || y >= h) continue;
      const dx = x - x0, dy = y - y0;
      if (dx * dx + dy * dy > r2) continue;
      if (visibleAlong(grid, x0, y0, x, y)) out.add(cellKey(x, y));
    }
  }
  return out;
}

function visibleAlong(grid: string[], x0: number, y0: number, x1: number, y1: number): boolean {
  const dx = Math.abs(x1 - x0), dy = -Math.abs(y1 - y0);
  const sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1;
  let err = dx + dy, x = x0, y = y0;
  for (;;) {
    if (x === x1 && y === y1) return true;
    if (!(x === x0 && y === y0) && blocks(grid[y]?.[x])) return false;
    const e2 = 2 * err;
    if (e2 >= dy) { err += dy; x += sx; }
    if (e2 <= dx) { err += dx; y += sy; }
  }
}

/** 마을(전체 시야)용 — 격자의 모든 칸. */
export function allCells(w: number, h: number): Set<string> {
  const out = new Set<string>();
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) out.add(cellKey(x, y));
  return out;
}

export const EMPTY_SET: ReadonlySet<string> = new Set<string>();

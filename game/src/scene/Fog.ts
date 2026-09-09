// 밝기(fog) 레이어 — Phase B4. 화면은 초점 캐릭터 편에 선다(계획 §3):
//   지금 초점 캐릭터의 시야 = 밝게(안 칠함) · 가 본 곳 = 보통(검정 α 0.45) · 미지 = 어둡게(검정 α 0.88).
//   마을(run.levels[i].town)은 전부 밝음(안 그림). 초점이 없으면(null) 안 그린다(관전자 = 전부 보임).
//   초점 봇이 죽었거나 먼저 내려갔으면 시야가 빈 집합이라 본 곳만 반투명으로 남는다.
// 입력: app.playback('frame') · app.focus('change') · app.bus('run') · app.scene.visibleSet/seenSet · frame.level.grid.
// 갱신 규칙: 매 틱 다시 그리지 않는다. 서명(판 세대|층|초점|초점 봇 자리·생사|본 칸 수)이 같으면 건너뛴다 —
//   시야는 자리에만, 본 곳은 누적 수에만 의존하니 정확하다. 한 번 그릴 때는 가로로 이어진 같은 단계의 칸을
//   한 사각형으로 합쳐 fillRect 수를 줄인다(56×20 = 1120칸 → 보통 100~200개).
// 암반('#' 인데 바닥에 접하지 않은 칸)은 씬이 타일을 안 놓아 어차피 검정 — 칠하지 않고 셈에서도 뺀다.
// 디버그·스모크 훅: 그래픽 이름 'fog'(app.scene.children.getByName('fog')) · window.__wlFog(아래 FogStats).
import type Phaser from 'phaser';
import type { App } from '../app';
import type { Char, LevelLine } from '../stream/types';
import { TILE } from '../assets/tiles';
import { DEPTH } from './DungeonScene';
import { cellKey, EMPTY_SET } from '../world/Sight';

/** window.__wlFog — 마지막 갱신의 칸 수(암반 제외)·그린 횟수. */
export interface FogStats {
  level: number;                                 // 프레임의 levelIdx(-1 = 판 없음)
  depth: number;                                 // 그 층의 depth(마을 0)
  focus: Char | null;
  unknown: number;                               // 미지 칸 수(어둡게 칠한 칸)
  seen: number;                                  // 본 적 있으나 지금 안 보이는 칸 수(반투명)
  visible: number;                               // 지금 보이는 칸 수(안 칠함)
  total: number;                                 // 셈에 든 칸 수(바닥·문·바닥에 접한 벽) = unknown+seen+visible (마을·초점 없음이면 0)
  town: boolean;                                 // 마을 층(전부 밝음)
  draws: number;                                 // 실제로 다시 그린 횟수(누적)
}

declare global { interface Window { __wlFog?: FogStats } }

const NONE = 0, SEEN = 1, UNKNOWN = 2;           // 칸 단계
const ALPHA_SEEN = 0.45, ALPHA_UNKNOWN = 0.88;   // 검정 덮개의 불투명도

interface LevelCache { gen: number; levelIdx: number; w: number; h: number; rock: Uint8Array; total: number }

export function installFog(app: App): void {
  const scene = app.scene;
  const g: Phaser.GameObjects.Graphics = scene.add.graphics().setDepth(DEPTH.fog).setName('fog');
  const stats: FogStats = { level: -1, depth: 0, focus: null, unknown: 0, seen: 0, visible: 0, total: 0, town: false, draws: 0 };
  window.__wlFog = stats;

  let gen = 0;                                   // 판 세대 — 새 판이면 같은 층 번호라도 서명이 달라진다
  let sig = '';                                  // 마지막으로 그린 상태의 서명
  let cache: LevelCache | null = null;           // 층별 암반 마스크(층이 바뀔 때만 다시 만든다)
  let rowBuf = new Uint8Array(0);                // 한 행의 칸 단계 버퍼(재사용)

  /** 씬의 buildLevel 과 같은 판정: '.'/'+' 는 바닥, 바닥에 접한 '#' 만 벽, 나머지는 암반(타일 없음). */
  function levelCache(levelIdx: number, L: LevelLine): LevelCache {
    if (cache && cache.gen === gen && cache.levelIdx === levelIdx) return cache;
    const w = L.w, h = L.h;
    const isOpen = (x: number, y: number): boolean =>
      y >= 0 && y < h && x >= 0 && x < w && (L.grid[y][x] === '.' || L.grid[y][x] === '+');
    const rock = new Uint8Array(w * h);
    let total = 0;
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      if (isOpen(x, y)) { total++; continue; }
      let edge = false;
      for (let dy = -1; dy <= 1 && !edge; dy++) for (let dx = -1; dx <= 1 && !edge; dx++) if (isOpen(x + dx, y + dy)) edge = true;
      if (edge) total++; else rock[y * w + x] = 1;
    }
    cache = { gen, levelIdx, w, h, rock, total };
    return cache;
  }

  /** 층 전체를 칸 단계대로 칠한다(가로 런 병합). */
  function paint(levelIdx: number, L: LevelLine, focus: Char): void {
    const lc = levelCache(levelIdx, L);
    const vis = scene.visibleSet(focus) ?? EMPTY_SET;
    const seen = scene.seenSet(focus) ?? EMPTY_SET;
    const { w, h, rock } = lc;
    if (rowBuf.length < w) rowBuf = new Uint8Array(w);
    g.clear();
    let nU = 0, nS = 0, nV = 0, curAlpha = -1;
    for (let y = 0; y < h; y++) {
      const off = y * w;
      for (let x = 0; x < w; x++) {
        let lv = NONE;
        if (!rock[off + x]) {
          const k = cellKey(x, y);
          if (vis.has(k)) nV++;
          else if (seen.has(k)) { lv = SEEN; nS++; }
          else { lv = UNKNOWN; nU++; }
        }
        rowBuf[x] = lv;
      }
      for (let x = 0; x < w;) {                  // 같은 단계가 이어지는 구간 = 사각형 하나
        const lv = rowBuf[x];
        let x2 = x + 1;
        while (x2 < w && rowBuf[x2] === lv) x2++;
        if (lv !== NONE) {
          const a = lv === SEEN ? ALPHA_SEEN : ALPHA_UNKNOWN;
          if (a !== curAlpha) { g.fillStyle(0x000000, a); curAlpha = a; }
          g.fillRect(x * TILE, y * TILE, (x2 - x) * TILE, TILE);
        }
        x = x2;
      }
    }
    stats.level = levelIdx; stats.depth = L.depth; stats.focus = focus; stats.town = false;
    stats.unknown = nU; stats.seen = nS; stats.visible = nV; stats.total = lc.total;
    stats.draws++;
  }

  /** 안개 없음(마을·초점 없음·판 없음) — 한 번만 지운다. */
  function clearFog(levelIdx: number, depth: number, focus: Char | null, town: boolean, s: string): void {
    if (s === sig) return;
    sig = s;
    g.clear();
    stats.level = levelIdx; stats.depth = depth; stats.focus = focus; stats.town = town;
    stats.unknown = 0; stats.seen = 0; stats.visible = 0; stats.total = 0;
  }

  function redraw(): void {
    const run = app.run, f = scene.frame;
    const ls = run && f ? run.levels[f.levelIdx] : undefined;
    if (!run || !f || !ls) { clearFog(-1, 0, app.focus.char, false, `${gen}|none`); return; }
    const focus = app.focus.char;
    if (!focus) { clearFog(f.levelIdx, ls.line.depth, null, ls.town, `${gen}|${f.levelIdx}|nofocus`); return; }
    if (ls.town) { clearFog(f.levelIdx, ls.line.depth, focus, true, `${gen}|${f.levelIdx}|${focus}|town`); return; }
    const bot = f.bots.find(b => b.char === focus);
    const pos = bot ? bot.x + ',' + bot.y : '-';
    const alive = bot && bot.alive && !bot.won ? 1 : 0;
    const s = `${gen}|${f.levelIdx}|${focus}|${pos}|${alive}|${f.seen[focus] ?? 0}`;
    if (s === sig) return;
    sig = s;
    paint(f.levelIdx, ls.line, focus);
  }

  app.playback.on('frame', redraw);              // 씬이 먼저 구독했으니 scene.frame 은 이미 cur
  app.focus.on('change', redraw);
  app.bus.on('run', () => {                      // 새 판: 옛 층 덮개를 지우고 다음 'frame' 에서 새로 그린다
    gen++; cache = null; sig = '';
    g.clear();
    stats.level = -1; stats.focus = null; stats.unknown = 0; stats.seen = 0; stats.visible = 0; stats.total = 0; stats.town = false;
  });
  redraw();
}

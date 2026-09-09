// 타일·오브젝트 스프라이트 = viewer/tiles.json(Kenney Tiny Dungeon, CC0)의 글리프→타일 매핑 재사용.
// 표시 타일 48px(원본 16px ×3). SD 96px = 2타일 높이(RPG 만들기 비율). 뷰어 매핑에 없는 키만 EXTRA 로 보충.
export const TILE = 48;

export interface Tileset { label: string; license?: string; sheet: string; tile: number; map: Record<string, [number, number]> }
export interface TilesCfg { _readme?: string; default: string; tilesets: Record<string, Tileset> }

export const TILES_URL = '/viewer/tiles.json';

export async function fetchTiles(): Promise<TilesCfg> {
  const r = await fetch(TILES_URL, { cache: 'no-store' });
  if (!r.ok) throw new Error(`tiles.json ${r.status}`);
  return (await r.json()) as TilesCfg;
}

/** 뷰어 매핑에 없는 키 — Kenney 시트(12×11) [col,row]. 2026-09-09 접촉 시트로 고름. */
export const EXTRA: Record<string, [number, number]> = {
  'door': [10, 3],            // '+' 문 타일
  'exit': [6, 2],             // 계단(내려가는 출구) — 어두운 문간
  'feat:exit': [6, 2],
  'feat:stairs_up': [6, 2],   // 마을 판 상행 계단
  'feat:potion': [7, 9],      // 회복 물약(빨강)
  'feat:weapon': [7, 8],      // 검
  'feat:armor': [6, 8],       // 방패/갑옷
  'feat:npc': [2, 8],         // 마을 NPC
  'feat:grave': [7, 1],       // 묘(해골 비석)
  'item:potion': [7, 9], 'item:weapon': [7, 8], 'item:armor': [6, 8],   // 건네기 트윈 아이콘(B3)
};

/** key('feat:chest' 'mob:고블린' 'trap:spike' 'floor' 'wall' …) → [col,row]. '*' 폴백 → 제네릭. */
export function tilePos(ts: Tileset, key: string): [number, number] {
  if (ts.map[key]) return ts.map[key];
  if (EXTRA[key]) return EXTRA[key];
  const star = key.replace(/:.*$/, ':*');
  return ts.map[star] || EXTRA[star] || ts.map['feat:*'] || [6, 7];
}

/** 스프라이트시트 프레임 번호(행 우선). cols = 시트 폭 / 타일 크기. */
export function tileIndex(ts: Tileset, cols: number, key: string): number {
  const [c, r] = tilePos(ts, key);
  return r * cols + c;
}

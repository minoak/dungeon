// 원더랜드 전용 도트 에셋. 생성 원본·프레임 정렬 도구는 art/world-v1/에 보존한다.
// URL은 Vite가 해시를 붙여 dist로 복사하므로 임시 뷰어 경로에 의존하지 않는다.
import type Phaser from 'phaser';
import type { Dir } from '../stream/types';
import terrainUrl from './world/terrain.png';
import goblinUrl from './world/goblin.png';
import spiderUrl from './world/spider.png';
import propsUrl from './world/props.png';
import trapsUrl from './world/traps.png';

export const WORLD_CELL = 96;
export const WORLD_FOOT = 92;
export const TERRAIN_CELL = 48;
const DIRECTIONS: Dir[] = ['front', 'right', 'back', 'left'];
const MONSTERS: Record<string, string> = { '고블린': 'wl-goblin', '그림자거미': 'wl-spider' };
const PROPS: Record<string, number> = {
  door: 0, exit: 1, 'feat:exit': 1, 'feat:stairs_up': 1,
  'feat:chest': 2, 'feat:fountain': 3, 'feat:treasure': 4,
  'feat:potion': 5, 'feat:weapon': 6, 'feat:armor': 7,
  'item:potion': 5, 'item:weapon': 6, 'item:armor': 7,
};
const TRAPS: Record<string, number> = { 'trap:spike': 0, 'trap:dart': 1, 'trap:alarm': 2, 'feat:grave': 3 };

export interface WorldVisual { texture: string; frame: number }
export function worldVisual(key: string): WorldVisual | null {
  if (PROPS[key] !== undefined) return { texture: 'wl-props', frame: PROPS[key] };
  if (TRAPS[key] !== undefined) return { texture: 'wl-traps', frame: TRAPS[key] };
  const monster = key.startsWith('mob:') ? MONSTERS[key.slice(4)] : undefined;
  return monster ? { texture: monster, frame: 0 } : null;
}

export function queueWorld(load: Phaser.Loader.LoaderPlugin): void {
  load.spritesheet('wl-terrain', terrainUrl, { frameWidth: TERRAIN_CELL, frameHeight: TERRAIN_CELL });
  for (const [key, url] of [['wl-goblin', goblinUrl], ['wl-spider', spiderUrl], ['wl-props', propsUrl], ['wl-traps', trapsUrl]]) {
    load.spritesheet(key, url, { frameWidth: WORLD_CELL, frameHeight: WORLD_CELL });
  }
}

export function monsterFrame(dir: Dir): number { return DIRECTIONS.indexOf(dir) * 3; }
export function monsterWalk(texture: string, dir: Dir): string { return `${texture}-walk-${dir}`; }
export function registerWorldAnims(anims: Phaser.Animations.AnimationManager): void {
  for (const texture of Object.values(MONSTERS)) for (const dir of DIRECTIONS) {
    const key = monsterWalk(texture, dir), first = monsterFrame(dir);
    if (!anims.exists(key)) anims.create({ key, frames: [first + 1, first, first + 2, first].map(frame => ({ key: texture, frame })),
      frameRate: 8, repeat: -1 });
  }
}

/** 재생·시킹 때도 무늬가 바뀌지 않도록 칸 좌표로만 변형을 고른다. */
export function terrainFrame(grid: string[], x: number, y: number, town: boolean): number {
  const open = (xx: number, yy: number) => grid[yy]?.[xx] === '.' || grid[yy]?.[xx] === '+';
  // 하위 두 비트만 쓰면 4칸마다 체크무늬가 반복된다. 비트를 한 번 더 섞어 자연스럽게 흩뿌린다.
  let hash = Math.imul(x, 374761393) ^ Math.imul(y, 668265263);
  hash = Math.imul(hash ^ (hash >>> 13), 1274126177);
  hash = (hash ^ (hash >>> 16)) >>> 0;
  if (open(x, y)) return town ? 7 : hash % 4;
  if (open(x, y + 1)) return hash % 3 === 0 ? 6 : 4;
  for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) if (open(x + dx, y + dy)) return 5;
  return -1;
}

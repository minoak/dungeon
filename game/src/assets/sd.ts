// SD 캐릭터(viewer/assets/sprites/sd/atlas.json v3) → Phaser 스프라이트시트·애니메이션.
// 기본 셀 96px, 일러스트는 프리셋별 cell/footY/filter. 행 = directions 순서(front,right,back,left), 열 0 정지·1~4 걷기,
// frame_ms 160(기본 박자 — 실제 걸음 빠르기는 walkTimeScale 이 이동 시간에 맞춘다), 발 바닥 y=91 → origin (0.5, 91/96).
// 헤어별 PNG 는 전체 캐릭터 프레임(가발 레이어 아님).
// 선택값 = look.sprite + look.hairstyle. look.sprite 가 없는 옛 판 = 직업별 기본 SD 로 폴백(계획 §8 제안).
import Phaser from 'phaser';
import type { Dir, Look, PartyMember } from '../stream/types';
import { ROOT } from '../paths';

export const SD_DIR = ROOT + 'viewer/assets/sprites/sd/';   // 론처 '/viewer/…' · 정적 './viewer/…'(static-bundle.mjs 복사본)
export const SD_ATLAS_URL = SD_DIR + 'atlas.json';
export const FOOT_Y = 91;                        // 셀 안 발 바닥 y
/** 걷기 열 수(열 1~4). 기준: 한 칸 이동 = 걷기 한 주기 — 프레임 길이 = 한 칸 이동 시간 ÷ 이 수.
 *  예전엔 주기가 frame_ms×4 = 640ms 로 고정이라 1× 한 칸 560ms 보다 길어 발이 미끄러져 보였다(2026-10-12 c07 진단).
 *  걷기 상수 둘의 원천은 여기 — viewer/index.html 은 빌드 길이 달라 같은 값을 옮겨 두고, verify_walk_timing 이 같은지 본다. */
export const WALK_FRAMES = 4;
/** 한 칸(= 걷기 한 주기)의 최소 시간. 빠른 재생에서도 프레임이 40ms 보다 짧아지지 않는다(DungeonScene stepMs 하한). */
export const WALK_CYCLE_MIN_MS = 160;

export interface SdHairstyle { name: string; sheet: string }
export interface SdPreset { name: string; sheet: string; job: string; hairstyles?: Record<string, SdHairstyle>;
  cell?: number; footY?: number; filter?: 'nearest' | 'linear' }
export interface SdAtlas {
  version: number; cell: number; directions: Dir[]; columns: number; frame_ms: number; display_scale: number;
  presets: Record<string, SdPreset>;
}
export interface SdChoice { sprite: string; hairstyle: string }

export async function fetchAtlas(): Promise<SdAtlas> {
  const r = await fetch(SD_ATLAS_URL, { cache: 'no-store' });
  if (!r.ok) throw new Error(`SD atlas ${r.status}`);
  return (await r.json()) as SdAtlas;
}

/** 텍스처 키 — 프리셋×헤어 한 장. */
export const sheetKey = (c: SdChoice): string => `sd|${c.sprite}|${c.hairstyle}`;

/** Texture resolution is independent of the 96px world/display footprint. */
export function sdMetrics(atlas: SdAtlas, key: string): { cell: number; footY: number; scale: number; smooth: boolean } {
  const p = atlas.presets[key.split('|')[1]];
  const cell = p?.cell ?? atlas.cell;
  return { cell, footY: p?.footY ?? FOOT_Y * cell / atlas.cell, scale: atlas.cell / cell, smooth: p?.filter === 'linear' };
}

export function configureSdTextures(textures: Phaser.Textures.TextureManager, atlas: SdAtlas): void {
  for (const [id, p] of Object.entries(atlas.presets)) {
    for (const hairstyle of Object.keys(p.hairstyles || { default: {} })) {
      const key = sheetKey({ sprite: id, hairstyle });
      if (textures.exists(key)) textures.get(key).setFilter(p.filter === 'linear' ? Phaser.Textures.FilterMode.LINEAR : Phaser.Textures.FilterMode.NEAREST);
    }
  }
}

/** 로더에 시트 전부 등록(부팅 preload 에서). 헤어가 없는 프리셋은 default 한 장. */
export function queueSdSheets(load: Phaser.Loader.LoaderPlugin, atlas: SdAtlas): void {
  for (const [id, p] of Object.entries(atlas.presets)) {
    const hs = p.hairstyles && Object.keys(p.hairstyles).length ? p.hairstyles : { default: { name: '기본', sheet: p.sheet } };
    for (const [hid, h] of Object.entries(hs)) {
      load.spritesheet(sheetKey({ sprite: id, hairstyle: hid }), SD_DIR + h.sheet,
                       { frameWidth: p.cell ?? atlas.cell, frameHeight: p.cell ?? atlas.cell });
    }
  }
}

/** 시트의 look(+직업) → 실제로 그릴 프리셋·헤어. 없는 값은 직업으로, 그것도 없으면 첫 프리셋. */
export function resolveLook(look: Look | undefined, job: string | undefined, atlas: SdAtlas): SdChoice {
  const ids = Object.keys(atlas.presets);
  let sprite = look?.sprite && atlas.presets[look.sprite] ? look.sprite : '';
  if (!sprite) sprite = ids.find(id => atlas.presets[id].job === job) || ids[0];
  const p = atlas.presets[sprite];
  const hairstyle = look?.hairstyle && p.hairstyles && p.hairstyles[look.hairstyle] ? look.hairstyle : 'default';
  return { sprite, hairstyle: p.hairstyles && p.hairstyles[hairstyle] ? hairstyle : 'default' };
}

export function resolveMember(m: PartyMember | undefined, job: string | undefined, atlas: SdAtlas): SdChoice {
  return resolveLook(m?.look, m?.job || job, atlas);
}

/** 프레임 번호 — phase < 0 정지, 0..3 걷기. */
export function frameIndex(atlas: SdAtlas, dir: Dir, phase: number): number {
  const row = Math.max(0, atlas.directions.indexOf(dir));
  const col = phase < 0 ? 0 : 1 + (((Math.floor(phase) % WALK_FRAMES) + WALK_FRAMES) % WALK_FRAMES);
  return row * atlas.columns + col;
}

export const walkAnimKey = (key: string, dir: Dir): string => `${key}|walk|${dir}`;

/** 한 칸 이동(moveMs)에 걷기 한 주기가 꼭 맞는 애니 배속. 예: 1× 이동 560ms → 640/560 ≈ 1.14(프레임 140ms),
 *  빠른 재생 160ms → 4(프레임 40ms), 라이브 상한 1000ms → 0.64(프레임 250ms). */
export const walkTimeScale = (atlas: SdAtlas, moveMs: number): number => atlas.frame_ms * WALK_FRAMES / moveMs;

/** 시트마다 4방향 걷기 애니 등록(create 에서 한 번). */
export function registerAnims(anims: Phaser.Animations.AnimationManager, atlas: SdAtlas): void {
  for (const [id, p] of Object.entries(atlas.presets)) {
    const hs = p.hairstyles && Object.keys(p.hairstyles).length ? Object.keys(p.hairstyles) : ['default'];
    for (const hid of hs) {
      const key = sheetKey({ sprite: id, hairstyle: hid });
      for (const dir of atlas.directions) {
        const ak = walkAnimKey(key, dir);
        if (anims.exists(ak)) continue;
        const row = atlas.directions.indexOf(dir);
        anims.create({
          key: ak,
          frames: anims.generateFrameNumbers(key, { frames: Array.from({ length: WALK_FRAMES }, (_, i) => row * atlas.columns + 1 + i) }),
          frameRate: 1000 / atlas.frame_ms,
          repeat: -1,
        });
      }
    }
  }
}

/** 정면 얼굴·어깨 초상. 원본 해상도와 프리셋의 보간 방식을 함께 적용한다. */
export function portraitCanvas(textures: Phaser.Textures.TextureManager, atlas: SdAtlas, key: string,
                               size = 56): HTMLCanvasElement | null {
  if (!textures.exists(key)) return null;
  const img = textures.get(key).getSourceImage() as HTMLImageElement | HTMLCanvasElement;
  const c = document.createElement('canvas');
  c.width = c.height = size;
  const g = c.getContext('2d');
  if (!g) return null;
  const metrics = sdMetrics(atlas, key), ratio = metrics.cell / atlas.cell;
  g.imageSmoothingEnabled = metrics.smooth;
  g.imageSmoothingQuality = 'high';
  c.style.imageRendering = metrics.smooth ? 'auto' : 'pixelated';
  const row = Math.max(0, atlas.directions.indexOf('front'));
  // 셀 96 중 머리~어깨: x 20..76, y 4..60 (56×56) — 발은 초상에 안 넣는다
  g.drawImage(img, 20 * ratio, row * metrics.cell + 4 * ratio, 56 * ratio, 56 * ratio, 0, 0, size, size);
  return c;
}

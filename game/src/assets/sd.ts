// SD 도트 캐릭터(viewer/assets/sprites/sd/atlas.json v2) → Phaser 스프라이트시트·애니메이션.
// 규격(art/sprites-v4/README): 셀 96px, 행 = directions 순서(front,right,back,left), 열 0 정지·1~4 걷기,
// frame_ms 160, 발 바닥 y=91 → origin (0.5, 91/96). 헤어별 PNG 는 전체 캐릭터 프레임(가발 레이어 아님).
// 선택값 = look.sprite + look.hairstyle. look.sprite 가 없는 옛 판 = 직업별 기본 SD 로 폴백(계획 §8 제안).
import type Phaser from 'phaser';
import type { Dir, Look, PartyMember } from '../stream/types';

export const SD_DIR = '/viewer/assets/sprites/sd/';
export const SD_ATLAS_URL = SD_DIR + 'atlas.json';
export const FOOT_Y = 91;                        // 셀 안 발 바닥 y

export interface SdHairstyle { name: string; sheet: string }
export interface SdPreset { name: string; sheet: string; job: string; hairstyles?: Record<string, SdHairstyle> }
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

/** 로더에 시트 전부 등록(부팅 preload 에서). 헤어가 없는 프리셋은 default 한 장. */
export function queueSdSheets(load: Phaser.Loader.LoaderPlugin, atlas: SdAtlas): void {
  for (const [id, p] of Object.entries(atlas.presets)) {
    const hs = p.hairstyles && Object.keys(p.hairstyles).length ? p.hairstyles : { default: { name: '기본', sheet: p.sheet } };
    for (const [hid, h] of Object.entries(hs)) {
      load.spritesheet(sheetKey({ sprite: id, hairstyle: hid }), SD_DIR + h.sheet,
                       { frameWidth: atlas.cell, frameHeight: atlas.cell });
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
  const col = phase < 0 ? 0 : 1 + (((Math.floor(phase) % 4) + 4) % 4);
  return row * atlas.columns + col;
}

export const walkAnimKey = (key: string, dir: Dir): string => `${key}|walk|${dir}`;

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
          frames: anims.generateFrameNumbers(key, { frames: [1, 2, 3, 4].map(c => row * atlas.columns + c) }),
          frameRate: 1000 / atlas.frame_ms,
          repeat: -1,
        });
      }
    }
  }
}

/** 정면 정지 프레임에서 얼굴·어깨를 잘라 초상 캔버스로(칩용, 최근접 확대). */
export function portraitCanvas(textures: Phaser.Textures.TextureManager, atlas: SdAtlas, key: string,
                               size = 56): HTMLCanvasElement | null {
  if (!textures.exists(key)) return null;
  const img = textures.get(key).getSourceImage() as HTMLImageElement | HTMLCanvasElement;
  const c = document.createElement('canvas');
  c.width = c.height = size;
  const g = c.getContext('2d');
  if (!g) return null;
  g.imageSmoothingEnabled = false;
  const row = Math.max(0, atlas.directions.indexOf('front'));
  // 셀 96 중 머리~어깨: x 20..76, y 4..60 (56×56) — 발은 초상에 안 넣는다
  g.drawImage(img, 0 * atlas.cell + 20, row * atlas.cell + 4, 56, 56, 0, 0, size, size);
  return c;
}

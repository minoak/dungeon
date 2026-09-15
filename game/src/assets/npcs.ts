// D73 street NPCs: generated art/npc-sprites-v1 sheets, packaged by Vite.
import type Phaser from 'phaser';
import type { Dir } from '../stream/types';
import wanderer from '../../../entities/npc/wandering_adventurer.json';
import apprentice from '../../../entities/npc/apprentice_adventurer.json';
import vendor from '../../../entities/npc/street_vendor.json';
import wandererUrl from './world/npc-wanderer.png';
import apprenticeUrl from './world/npc-apprentice.png';
import vendorUrl from './world/npc-vendor.png';

export const NPC_CELL = 96, NPC_FOOT = 91;
const DIRECTIONS: Dir[] = ['front', 'right', 'back', 'left'];
const NPCS = [
  { name: wanderer.name, key: 'wl-npc-wanderer', url: wandererUrl },
  { name: apprentice.name, key: 'wl-npc-apprentice', url: apprenticeUrl },
  { name: vendor.name, key: 'wl-npc-vendor', url: vendorUrl },
];
// Current feature snapshots contain name + numeric instance id, not the entity definition id.
export function npcTexture(name: string): string | undefined { return NPCS.find(n => n.name === name)?.key; }
export function npcFrame(dir: Dir): number { return DIRECTIONS.indexOf(dir) * 3; }
export function npcWalk(key: string, dir: Dir): string { return `${key}-walk-${dir}`; }
export function queueNpcs(load: Phaser.Loader.LoaderPlugin): void {
  for (const n of NPCS) load.spritesheet(n.key, n.url, { frameWidth: NPC_CELL, frameHeight: NPC_CELL });
}
export function registerNpcAnims(anims: Phaser.Animations.AnimationManager): void {
  for (const n of NPCS) for (const dir of DIRECTIONS) {
    const key = npcWalk(n.key, dir), first = npcFrame(dir);
    if (!anims.exists(key)) anims.create({ key,
      frames: [first + 1, first, first + 2, first].map(frame => ({ key: n.key, frame })),
      frameRate: 8, repeat: -1 });
  }
}

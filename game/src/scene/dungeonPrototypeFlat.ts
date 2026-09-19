// Opt-in visual experiment: renderer only. Never changes the generated grid or engine RNG.
import type Phaser from 'phaser';
import type { LevelLine } from '../stream/types';
import { lineOfSight } from '../world/Sight';
import wallsUrl from '../../../art/dungeon-v2/runtime/walls.png';
import propsUrl from '../../../art/dungeon-v2/runtime/props.png';
import floorUrl from '../../../art/dungeon-v2/runtime/floor.png';
import decorUrl from '../../../art/dungeon-v2/runtime/decor.png';
import { planDungeonDecor } from './dungeonDecor';

export const dungeonPrototypeEnabled = new URLSearchParams(location.search).get('dungeonArt') === 'flat';
export function queueDungeonPrototype(load: Phaser.Loader.LoaderPlugin): void {
  if (!dungeonPrototypeEnabled) return;
  load.image('dungeon-v2-walls', wallsUrl);
  load.image('dungeon-v2-floor', floorUrl);
  load.image('dungeon-v2-decor', decorUrl);
  load.spritesheet('dungeon-v2-props', propsUrl, { frameWidth: 96, frameHeight: 96 });
}
export function dungeonPrototypeVisual(key: string): { texture: string; frame: number } | null {
  if (key === 'feat:chest') return { texture: 'dungeon-v2-props', frame: 2 };
  if (key === 'exit' || key === 'feat:exit') return { texture: 'dungeon-v2-props', frame: 3 };
  return null;
}

export function paintDungeonPrototype(scene: Phaser.Scene, L: LevelLine, tile: number): Phaser.GameObjects.Image {
  const key = 'dungeon-v2-level';
  // Level owner destroys the previous image before this function is called.
  if (scene.textures.exists(key)) scene.textures.remove(key);
  const texture = scene.textures.createCanvas(key, L.w * tile, L.h * tile)!;
  const ctx = texture.context;
  ctx.imageSmoothingEnabled = false;
  const masonry = scene.textures.get('dungeon-v2-walls').getSourceImage() as HTMLImageElement;
  const props = scene.textures.get('dungeon-v2-props').getSourceImage() as HTMLImageElement;
  const floor = scene.textures.get('dungeon-v2-floor').getSourceImage() as HTMLImageElement;
  const decor = scene.textures.get('dungeon-v2-decor').getSourceImage() as HTMLImageElement;
  const floorPattern = ctx.createPattern(floor, 'repeat')!;
  // Material scale is independent of the movement grid: smaller slabs make the room read larger.
  floorPattern.setTransform(new DOMMatrix().scale(.5));
  const open = (x: number, y: number): boolean => L.grid[y]?.[x] === '.' || L.grid[y]?.[x] === '+';
  const hash = (x: number, y: number): number => {
    let n = Math.imul(x + (L.master_seed ?? 0), 374761393) ^ Math.imul(y, 668265263);
    n = Math.imul(n ^ (n >>> 13), 1274126177);
    return (n ^ (n >>> 16)) >>> 0;
  };
  const draw = (f: number, x: number, y: number): void => {
    ctx.drawImage(masonry, f % 2 * 48, Math.floor(f / 2) * 48, 48, 48, x * tile, y * tile, tile, tile);
  };
  ctx.fillStyle = '#080c13'; ctx.fillRect(0, 0, texture.width, texture.height);
  const walls: [number, number][] = [];
  for (let y = 0; y < L.h; y++) for (let x = 0; x < L.w; x++) {
    if (open(x, y)) {
      ctx.fillStyle = floorPattern; ctx.fillRect(x * tile, y * tile, tile, tile);
      ctx.fillStyle = 'rgba(17,24,37,.10)'; ctx.fillRect(x * tile, y * tile, tile, tile);
    } else {
      let near = false;
      for (let yy = -1; yy <= 1; yy++) for (let xx = -1; xx <= 1; xx++) near ||= open(x + xx, y + yy);
      if (!near) continue; // Same rock boundary as normal fog; no undiscovered decorative objects outside it.
      walls.push([x, y]);
      const front = open(x, y + 1) || open(x, y - 1);
      draw(front ? (hash(x, y) % 4 === 0 ? 1 : 0) : 2, x, y);
      if (front) {
        // Separate the horizontal coping from the recessed vertical face.
        const faceShade = ctx.createLinearGradient(0, y * tile + 9, 0, (y + 1) * tile);
        faceShade.addColorStop(0, 'rgba(4,9,18,.36)');
        faceShade.addColorStop(.45, 'rgba(4,9,18,.14)');
        faceShade.addColorStop(1, 'rgba(4,9,18,.30)');
        ctx.fillStyle = faceShade; ctx.fillRect(x * tile, y * tile + 9, tile, tile - 9);
        ctx.drawImage(masonry, 0, 48, 48, 10, x * tile, y * tile, tile, 10);
        ctx.fillStyle = 'rgba(3,7,14,.55)'; ctx.fillRect(x * tile, y * tile + 10, tile, 2);
        // The foot course sits slightly proud of the wall face.
        ctx.drawImage(masonry, (hash(x, y) % 4 === 0 ? 1 : 0) * 48, 41, 48, 7,
          x * tile, y * tile + tile - 7, tile, 7);
      }
      if (!front) {
        ctx.fillStyle = 'rgba(6,10,20,.42)';
        if (open(x - 1, y)) ctx.fillRect(x * tile, y * tile, 6, tile);
        if (open(x + 1, y)) ctx.fillRect((x + 1) * tile - 6, y * tile, 6, tile);
        if (open(x, y - 1)) ctx.fillRect(x * tile, y * tile, tile, 5);
      }
    }
  }
  // Attached piers break up long masonry runs. Every pixel stays in the existing wall cell.
  const wallDetails: { x: number; y: number; kind: string }[] = [];
  const pier = (x: number, y: number, width: number): void => {
    const left = x * tile + (tile - width) / 2;
    ctx.fillStyle = 'rgba(3,7,13,.32)';
    ctx.fillRect(left + width - 1, y * tile + 9, 5, tile - 9);
    // Crop the surrounding wall out of the atlas's pilaster cell before placing it.
    ctx.drawImage(masonry, 55, 48, 34, 48, left, y * tile, width, tile);
  };
  for (const [x, y] of walls) {
    const north = open(x, y - 1), south = open(x, y + 1);
    const front = north || south;
    const doorway = L.grid[y]?.[x - 1] === '+' || L.grid[y]?.[x + 1] === '+';
    const corner = (south && (!open(x - 1, y + 1) || !open(x + 1, y + 1)))
      || (north && (!open(x - 1, y - 1) || !open(x + 1, y - 1)));
    const sideY = south ? y + 1 : y - 1;
    const longRun = front && [-2, -1, 1, 2].every(dx => open(x + dx, sideY));
    const rhythm = longRun && (x + ((L.master_seed ?? 0) % 5)) % 5 === 0;
    if (front && (corner || doorway || rhythm)) {
      pier(x, y, corner || doorway ? 36 : 30);
      wallDetails.push({ x, y, kind: doorway ? 'door-jamb' : corner ? 'corner' : 'pier' });
    }
  }
  // Contact shadows stay inside traversable tiles; walls never consume walkable cells.
  for (let y = 0; y < L.h; y++) for (let x = 0; x < L.w; x++) if (open(x, y)) {
    if (!open(x, y - 1)) {
      const shade = ctx.createLinearGradient(0, y * tile, 0, y * tile + 21);
      shade.addColorStop(0, 'rgba(3,8,17,.66)'); shade.addColorStop(1, 'rgba(3,8,17,0)');
      ctx.fillStyle = shade; ctx.fillRect(x * tile, y * tile, tile, 21);
    }
    ctx.fillStyle = 'rgba(4,9,18,.24)';
    if (!open(x - 1, y)) ctx.fillRect(x * tile, y * tile, 4, tile);
  }
  // Projected shadows from attached piers tie the architecture to its floor.
  for (const { x, y } of wallDetails) if (open(x, y + 1)) {
    ctx.save(); ctx.beginPath(); ctx.rect(x * tile, (y + 1) * tile, tile, tile); ctx.clip();
    ctx.fillStyle = 'rgba(3,8,17,.20)'; ctx.beginPath();
    ctx.moveTo(x * tile + 8, (y + 1) * tile);
    ctx.lineTo(x * tile + 39, (y + 1) * tile);
    ctx.lineTo(x * tile + 46, (y + 1) * tile + 20);
    ctx.lineTo(x * tile + 19, (y + 1) * tile + 20);
    ctx.closePath(); ctx.fill(); ctx.restore();
  }
  // Small, flat stone fragments along wall feet add wear without inventing obstacles.
  let stoneFragments = 0;
  for (let y = 0; y < L.h; y++) for (let x = 0; x < L.w; x++) {
    if (L.grid[y][x] !== '.' || hash(x, y) % 5 !== 0) continue;
    const north = L.grid[y - 1]?.[x] === '#', west = L.grid[y]?.[x - 1] === '#';
    if (!north && !west) continue;
    if (L.features.some(f => Math.abs(f.x - x) + Math.abs(f.y - y) <= 1)) continue;
    const size = 13 + hash(x + 1, y) % 8;
    const px = x * tile + (west ? 3 : 8 + hash(x, y + 1) % 18);
    const py = y * tile + (north ? 3 : 14 + hash(x, y + 2) % 13);
    ctx.save(); ctx.globalAlpha = .64;
    ctx.drawImage(decor, 30, 164, 36, 24, px, py, size, size * 2 / 3);
    ctx.restore(); stoneFragments++;
  }
  const torches: [number, number][] = [];
  for (const [x, y] of walls) {
    if (L.grid[y + 1]?.[x] !== '.' || L.grid[y]?.[x - 1] === '+' || L.grid[y]?.[x + 1] === '+') continue;
    if (L.features.some(f => f.x === x && f.y === y + 1)) continue;
    if (torches.some(([tx, ty]) => Math.abs(tx - x) + Math.abs(ty - y) < 5)) continue;
    if (hash(x, y) % 3 === 0 || !open(x - 1, y + 1)) torches.push([x, y]);
  }
  const decorations = planDungeonDecor(L, torches);
  for (const { x, y, frame, surface, offsetX, offsetY } of decorations) {
    if (surface === 'floor') {
      // Contact shadow grounds the object on the flagstones; no cut-out wall niche.
      ctx.fillStyle = frame === 3 ? 'rgba(3,7,12,.20)' : 'rgba(3,7,12,.40)';
      ctx.beginPath();
      ctx.ellipse(x * tile + 24 + offsetX, y * tile + 39 + offsetY, 18, 5, 0, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.drawImage(decor, frame % 3 * 96, Math.floor(frame / 3) * 96, 96, 96,
      x * tile - 24 + offsetX, y * tile - (surface === 'floor' ? 50 : 45) + offsetY, 96, 96);
  }
  for (const [x, y] of torches) {
    // Torch-bearing piers use the same masonry as the structural supports.
    if (!wallDetails.some(p => p.x === x && p.y === y)) {
      pier(x, y, 30);
      wallDetails.push({ x, y, kind: 'torch-pier' });
    }
    const lit = lineOfSight(L.grid, x, y + 1, 4);
    lit.add(`${x},${y}`);
    ctx.save(); ctx.beginPath();
    for (const cell of lit) { const [xx, yy] = cell.split(',').map(Number); ctx.rect(xx * tile, yy * tile, tile, tile); }
    ctx.clip();
    const cx = (x + .5) * tile, cy = (y + .65) * tile;
    const light = ctx.createRadialGradient(cx, cy, 2, cx, cy, tile * 2.9);
    light.addColorStop(0, 'rgba(255,180,62,.55)');
    light.addColorStop(.3, 'rgba(245,157,52,.24)');
    light.addColorStop(1, 'rgba(230,132,32,0)');
    ctx.fillStyle = light; ctx.fillRect(cx - tile * 4, cy - tile * 4, tile * 8, tile * 8);
    ctx.restore();
    ctx.drawImage(props, 0, 0, 96, 96, x * tile - 24, y * tile - 47, 96, 96);
  }
  texture.refresh();
  const image = scene.add.image(0, 0, key).setOrigin(0).setDepth(.5).setName('dungeon-v2-ground');
  image.setData('torches', torches);
  image.setData('decorations', decorations);
  image.setData('wallDetails', wallDetails);
  image.setData('materialScale', .5);
  image.setData('stoneFragments', stoneFragments);
  image.once('destroy', () => { if (scene.textures.exists(key)) scene.textures.remove(key); });
  return image;
}

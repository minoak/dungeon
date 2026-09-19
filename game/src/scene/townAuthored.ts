import type Phaser from 'phaser';
import type { TownVisual } from '../stream/types';

/** Authored background and foreground silhouettes share a single GPU texture.
 * Collision still comes exclusively from the server's traced layout grid.
 */
export function paintAuthoredTown(scene: Phaser.Scene, V: TownVisual, tile: number,
  groundDepth: number, standDepth: number): Phaser.GameObjects.GameObject[] {
  const art = V.art;
  if (!art) return [];
  const texture = 'wl-' + art.texture;
  const x = V.offset[0] * tile, y = V.offset[1] * tile;
  const sx = art.size[0] * tile / art.sourceSize[0];
  const sy = art.size[1] * tile / art.sourceSize[1];
  const objects: Phaser.GameObjects.GameObject[] = [];
  const plate = () => scene.add.image(x, y, texture).setOrigin(0).setScale(sx, sy);
  objects.push(plate().setDepth(groundDepth).setName('town-authored-background'));
  for (const o of art.occluders) {
    const points = o.polygon.map(([px, py]) => ({x: x + px * sx, y: y + py * sy}));
    const shape = scene.make.graphics({x: 0, y: 0}, false);
    shape.fillStyle(0xffffff).fillPoints(points, true);
    const mask = shape.createGeometryMask();
    const image = plate().setMask(mask)
      .setDepth(standDepth + ((y + o.footY * sy) / tile - 0.92) * 0.01)
      .setName('town-occluder-' + o.id);
    // Level rebuild destroys images; detach/destroy each mask and its invisible
    // graphics together so seeking and floor switches cannot retain stencils.
    image.once('destroy', () => { image.clearMask(); mask.destroy(); shape.destroy(); });
    objects.push(image);
  }
  for (const label of art.labels) {
    objects.push(scene.add.text(x + label.x * sx, y + label.y * sy, label.name, {
      fontFamily: 'sans-serif', fontSize: `${18 * sx}px`, color: '#f6eccb',
      backgroundColor: '#192127cc', padding: {x: 9 * sx, y: 3 * sy},
    }).setOrigin(0.5).setDepth(standDepth + 5).setName('town-area-label'));
  }
  return objects;
}

import type Phaser from 'phaser';
import type { TownVisual } from '../stream/types';

/** Low, walkable paving details. All coordinates belong to the visual layer. */
export function paintTownPaving(scene: Phaser.Scene, visual: TownVisual, tile: number, depth: number): Phaser.GameObjects.Graphics | null {
  const paving = visual.paving;
  if (!paving) return null;
  const g = scene.add.graphics().setDepth(depth), unit = tile / 48;
  const pos = (cell: [number, number]) => [(cell[0] + visual.offset[0]) * tile, (cell[1] + visual.offset[1]) * tile];
  for (const edge of paving.edges) {
    const [x,y] = pos(edge.cell);
    const horizontal = edge.side === 'n' || edge.side === 's';
    const far = edge.side === 's' || edge.side === 'e';
    const bx = x + (!horizontal && far ? tile - 6 * unit : 0);
    const by = y + (horizontal && far ? tile - 6 * unit : 0);
    g.fillStyle(0x514b40,.65).fillRect(bx,by,horizontal ? tile : 6*unit,horizontal ? 6*unit : tile);
    g.fillStyle(edge.material === 3 ? 0xaaa99a : 0xc4b392,.92)
      .fillRect(bx+unit,by+unit,horizontal ? tile-2*unit : 4*unit,horizontal ? 4*unit : tile-2*unit);
    g.lineStyle(unit,0xe6d5b5,.65);
    g.lineBetween(bx+unit,by+unit,horizontal ? bx+tile-unit : bx+unit,horizontal ? by+unit : by+tile-unit);
    g.lineStyle(unit,0x736958,.65);
    for(let i=12;i<48;i+=12) g.lineBetween(bx+(horizontal?i:0)*unit,by+(horizontal?0:i)*unit,bx+(horizontal?i:6)*unit,by+(horizontal?6:i)*unit);
    if(edge.soft && (edge.cell[0]*13+edge.cell[1]*7)%3===0){
      g.fillStyle(0x68754a,.6);
      g.fillRect(bx+(horizontal?17:2)*unit,by+(horizontal?2:17)*unit,horizontal?7*unit:2*unit,horizontal?2*unit:7*unit);
    }
  }
  for(const cell of paving.drains){
    const [x,y]=pos(cell),cx=x+tile*.5,cy=y+tile*.5;
    g.fillStyle(0x3c423c,.75).fillRect(cx-10*unit,cy-6*unit,20*unit,12*unit);
    g.lineStyle(2*unit,0x9b9581,.85).strokeRect(cx-10*unit,cy-6*unit,20*unit,12*unit);
    g.lineStyle(unit,0x8c8b75,.8);
    for(let i=-6;i<=6;i+=4)g.lineBetween(cx+i*unit,cy-5*unit,cx+i*unit,cy+5*unit);
  }
  for(const inset of paving.inlays){
    const [x,y]=pos(inset.cell),cx=x+tile*.5,cy=y+tile*.5,r=inset.radius*tile;
    g.lineStyle(3*unit,0x817055,.6).strokeCircle(cx,cy,r);
    g.lineStyle(unit,0xe5d4af,.8).strokeCircle(cx,cy,r-5*unit);
    const points=Array.from({length:16},(_,i)=>{
      const angle=i*Math.PI/8-Math.PI/2,rr=r*(i%2?.22:.68);
      return {x:cx+Math.cos(angle)*rr,y:cy+Math.sin(angle)*rr};
    });
    g.fillStyle(0xa58b60,.32).fillPoints(points,true);
    g.lineStyle(unit,0x8b7756,.65).strokePoints(points,true);
  }
  return g;
}

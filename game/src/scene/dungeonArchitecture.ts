import type { LevelLine } from '../stream/types';
export type WallKind = 'front' | 'west' | 'east' | 'both' | 'corner' | 'column';
export interface WallPiece { x: number; y: number; kind: WallKind; pier: boolean; height: number }
export interface DungeonArchitecture { walls: WallPiece[]; torches: [number, number][]; doors: {x:number;y:number;side:boolean;flip:boolean}[] }
export function artHash(seed: number, x: number, y: number): number {
  let n = Math.imul(x + seed, 374761393) ^ Math.imul(y, 668265263);
  n = Math.imul(n ^ (n >>> 13), 1274126177);
  return (n ^ (n >>> 16)) >>> 0;
}
export function planDungeonArchitecture(L: LevelLine): DungeonArchitecture {
  const open = (x: number, y: number) => L.grid[y]?.[x] === '.' || L.grid[y]?.[x] === '+';
  const walls: WallPiece[] = [], torches: [number, number][] = [], doors: DungeonArchitecture['doors'] = [];
  for (let y=0;y<L.h;y++) for(let x=0;x<L.w;x++) {
    if (L.grid[y][x] === '+') { doors.push({x,y,side:open(x-1,y)&&open(x+1,y),flip:!L.rooms.some(r=>x>r.x&&x<=r.x+r.w&&y>=r.y&&y<r.y+r.h)}); continue; }
    if (L.grid[y][x] !== '#') continue;
    const n=open(x,y-1),s=open(x,y+1),w=open(x-1,y),e=open(x+1,y);
    const adjacent=Number(n)+Number(s)+Number(w)+Number(e);
    const diagonal=[[-1,-1],[1,-1],[-1,1],[1,1]].some(([dx,dy])=>open(x+dx,y+dy));
    if(!adjacent&&!diagonal)continue;
    const kind:WallKind=adjacent===4?'column':n||s?'front':w&&e?'both':w?'west':e?'east':'corner';
    const end = (s&&(!open(x-1,y+1)||!open(x+1,y+1))) || (n&&(!open(x-1,y-1)||!open(x+1,y-1)));
    const pier=kind==='column'||kind==='corner';
    walls.push({x,y,kind,pier,height:kind==='column'?98:80});
    if ((kind==='front'&&s||kind==='column') && !L.features.some(f=>f.x===x&&f.y===y+1)
      && L.grid[y]?.[x-1]!=='+'&&L.grid[y]?.[x+1]!=='+'
      && !torches.some(([xx,yy])=>Math.abs(xx-x)+Math.abs(yy-y)<5)
      && (pier||end||(x+(L.master_seed??0)%5)%5===0||artHash(L.master_seed??0,x,y)%4===0)) torches.push([x,y]);
  }
  // Keep short walls plain. Long uninterrupted faces get sparse, centered supports.
  const fronts = new Map(walls.filter(p=>p.kind==='front').map(p=>[`${p.x},${p.y}`,p]));
  const exposure = (x:number,y:number) => Number(open(x,y-1))+2*Number(open(x,y+1));
  for (const p of fronts.values()) {
    if(fronts.has(`${p.x-1},${p.y}`)&&exposure(p.x-1,p.y)===exposure(p.x,p.y))continue;
    const span:WallPiece[]=[];
    for(let x=p.x;fronts.has(`${x},${p.y}`)&&exposure(x,p.y)===exposure(p.x,p.y);x++)span.push(fronts.get(`${x},${p.y}`)!);
    if(span.length<9)continue;
    const count=1+Math.floor((span.length-9)/8),start=Math.floor((span.length-1-(count-1)*8)/2);
    for(let i=0;i<count;i++)span[start+i*8].pier=true;
  }
  return {walls,torches,doors};
}

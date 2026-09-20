// Projected stone architecture. The map remains engine-owned; only the art profile changes geometry.
import type Phaser from 'phaser';
import type { LevelLine } from '../stream/types';
import { lineOfSight } from '../world/Sight';
import { planDungeonDecor } from './dungeonDecor';
import { artHash, planDungeonArchitecture } from './dungeonArchitecture';
import { queueDungeonPrototype as queueFlat, paintDungeonPrototype as paintFlat,
  dungeonPrototypeVisual as flatVisual } from './dungeonPrototypeFlat';
import frontUrl from '../../../art/dungeon-v2/runtime/concept-front.png';
import copingUrl from '../../../art/dungeon-v2/runtime/concept-coping.png';
import sideUrl from '../../../art/dungeon-v2/runtime/concept-side.png';
import capUrl from '../../../art/dungeon-v2/runtime/concept-cap.png';
import floorUrl from '../../../art/dungeon-v2/runtime/concept-floor.png';
import propsUrl from '../../../art/dungeon-v2/runtime/props.png';
import decorUrl from '../../../art/dungeon-v2/runtime/decor.png';
import architectureUrl from '../../../art/dungeon-v2/runtime/architecture.png';
import weatheringUrl from '../../../art/dungeon-v2/runtime/weathering.png';

// D88(2026-09-20) 렌더러는 층마다 고른다. 전에는 URL ?dungeonArt= 를 모듈 로드 때 한 번 읽어 판 전체에 고정했고, 본편 URL 에서는 늘 꺼져 있었다.
//   · 스트림의 level.architecture(새 던전 생성 프로필의 건축 기록)가 있는 층 = 입체(projected) · 없는 층 = 옛 그림(null).
//   · URL ?dungeonArt= 는 강제 덮어쓰기로 남는다: prototype = 입체 · flat = 평면 시제품 · off = 옛 그림.
//     실험실(art/dungeon-v2/compare.js)이 같은 스트림을 prototype|flat 두 화면에 나란히 놓고, 옛 생성기 판(architecture 없음)도 입체로 그려 본다.
//   · 마을 층(town · visual)에서는 URL 로도 켜지지 않는다 — 마을은 제 그림(저작 조감도·마을 타일)이 있다.
const artParam = new URLSearchParams(location.search).get('dungeonArt');
export type DungeonArt = 'projected' | 'flat';
export function dungeonArtFor(L: LevelLine, town: boolean): DungeonArt | null {
  if (town || L.visual) return null;
  if (artParam === 'prototype') return 'projected';
  if (artParam === 'flat') return 'flat';
  if (artParam === 'off') return null;
  return L.architecture ? 'projected' : null;
}
/** 씬의 preload 는 판 로드보다 먼저 돈다(main.ts: 씬 생성 → loadRun) — 스트림을 보고 고를 수 없으니 입체 에셋 9장(약 200KB)은 늘 싣는다.
 *  평면 시제품은 URL 로만 켜지므로 그때만 전용 2장을 더 싣는다(props·decor 시트는 두 렌더러가 같은 키로 같이 쓴다). */
export function queueDungeonPrototype(load: Phaser.Loader.LoaderPlugin): void {
  if (artParam === 'flat') queueFlat(load);
  for (const [name,url] of [['front',frontUrl],['coping',copingUrl],['side',sideUrl],['cap',capUrl],['floor',floorUrl]]) load.image('dungeon-v3-'+name,url);
  load.spritesheet('dungeon-v2-props',propsUrl,{frameWidth:96,frameHeight:96});
  load.spritesheet('dungeon-v2-decor',decorUrl,{frameWidth:96,frameHeight:96});
  load.spritesheet('dungeon-v3-architecture',architectureUrl,{frameWidth:128,frameHeight:128});
  load.spritesheet('dungeon-v3-weathering',weatheringUrl,{frameWidth:128,frameHeight:128});
}
export function dungeonPrototypeVisual(key: string): {texture:string;frame:number}|null {
  return flatVisual(key);
}
export { dungeonLifeVisual } from './dungeonPrototypeFlat';   // D92(09-20) 던전 살림 다섯의 그림 — 옛 그림 렌더러도 같이 쓴다(DungeonScene.visualOf)
interface Part {
  image: Phaser.GameObjects.Image; x:number; y:number; wall:boolean; foot:number;
  width:number; height:number; brightness:number; hidden:boolean; baseAlpha:number;
  door?:boolean;                                 // D88 문 그림 — 그 칸에 누가 서면 옅어진다(tickDungeonPrototype)
}
interface View { parts:Part[]; objects:Phaser.GameObjects.GameObject[]; tile:number; stats:{hidden:number;remembered:number;cutaway:number} }
const views = new WeakMap<Phaser.GameObjects.Image,View>();

export function paintDungeonPrototype(scene:Phaser.Scene,L:LevelLine,tile:number,art:DungeonArt='projected'):Phaser.GameObjects.Image {
  if (art === 'flat') return paintFlat(scene,L,tile);
  const layout=planDungeonArchitecture(L),decorations=planDungeonDecor(L,layout.torches);
  const prefix='dungeon-v3-', keys:string[]=[], objects:Phaser.GameObjects.GameObject[]=[], parts:Part[]=[];
  const tex=(name:string,w:number,h:number) => {
    const key=prefix+name; if(scene.textures.exists(key))scene.textures.remove(key);
    keys.push(key);const t=scene.textures.createCanvas(key,w,h)!;t.context.imageSmoothingEnabled=false;return t;
  };
  const source=(name:string)=>scene.textures.get(prefix+name).getSourceImage() as HTMLImageElement;
  const front=source('front'),coping=source('coping'),side=source('side'),cap=source('cap'),floor=source('floor');
  const props=scene.textures.get('dungeon-v2-props').getSourceImage() as HTMLImageElement;
  const decor=scene.textures.get('dungeon-v2-decor').getSourceImage() as HTMLImageElement;
  const weather=source('weathering');
  const hash=(x:number,y:number)=>artHash(L.master_seed??0,x,y);
  const open=(x:number,y:number)=>L.grid[y]?.[x]==='.'||L.grid[y]?.[x]==='+';
  // Mirrored material patch: exact source colours, with continuous edges and no four-cell seams.
  const patch=document.createElement('canvas');patch.width=288;patch.height=512;
  const pc=patch.getContext('2d')!;pc.imageSmoothingEnabled=false;
  for(let yy=0;yy<2;yy++)for(let xx=0;xx<2;xx++){
    pc.save();pc.translate(xx?288:0,yy?512:0);pc.scale(xx?-1:1,yy?-1:1);pc.drawImage(floor,0,0);pc.restore();
  }
  const groundTex=tex('level',L.w*tile,L.h*tile+96),g=groundTex.context;
  g.fillStyle='#080c14';g.fillRect(0,0,groundTex.width,groundTex.height);g.translate(0,96);
  const pattern=g.createPattern(patch,'repeat')!;pattern.setTransform(new DOMMatrix().scale(.85));
  let fragments=0,moss=0;
  for(let y=0;y<L.h;y++)for(let x=0;x<L.w;x++)if(open(x,y)){
    g.fillStyle=pattern;g.fillRect(x*tile,y*tile,tile,tile);
    g.fillStyle='rgba(18,24,31,.12)';g.fillRect(x*tile,y*tile,tile,tile);
    if(!open(x,y-1)){
      const shade=g.createLinearGradient(0,y*tile,0,y*tile+30);shade.addColorStop(0,'rgba(2,6,13,.65)');shade.addColorStop(1,'rgba(2,6,13,0)');
      g.fillStyle=shade;g.fillRect(x*tile,y*tile,tile,30);
    }
    if(!open(x-1,y)){g.fillStyle='rgba(2,6,13,.27)';g.fillRect(x*tile,y*tile,10,tile);}
    if(!open(x+1,y)){g.fillStyle='rgba(2,6,13,.16)';g.fillRect((x+1)*tile-7,y*tile,7,tile);}
    if(L.grid[y][x]==='.'&&hash(x,y)%3===0&&(!open(x,y-1)||!open(x-1,y))){
      const s=12+hash(x+1,y)%15;
      g.globalAlpha=.7;g.drawImage(decor,30,164,36,24,x*tile+4,y*tile+5,s,s*2/3);g.globalAlpha=1;fragments++;
    }
    if(L.grid[y][x]==='.'&&hash(x,y)%4===0&&(!open(x,y-1)||!open(x-1,y)||!open(x+1,y))){
      g.globalAlpha=.65;g.drawImage(weather,128,128,128,128,x*tile-40,y*tile-82,128,128);g.globalAlpha=1;moss++;
    }
  }
  // Pool light on traversable surfaces; visibility fog remains above this floor-only pass.
  for(const [x,y] of layout.torches){
    const lit=lineOfSight(L.grid,x,y+1,5);const cx=(x+.5)*tile,cy=(y+1)*tile+6;
    g.save();g.beginPath();for(const c of lit){const [xx,yy]=c.split(',').map(Number);if(open(xx,yy))g.rect(xx*tile,yy*tile,tile,tile);}g.clip();
    const light=g.createRadialGradient(cx,cy,0,cx,cy,tile*3.1);
    light.addColorStop(0,'rgba(255,179,62,.42)');light.addColorStop(.32,'rgba(240,159,54,.22)');light.addColorStop(1,'rgba(221,141,40,0)');
    g.fillStyle=light;g.fillRect(cx-tile*4,cy-tile*4,tile*8,tile*8);g.restore();
  }
  const wallTextures=new Map<string,string>();
  const makeWall=(kind:string,variant:number,lights:[number,number][]):string=>{
    const id=`wall-${kind}-${variant}-${lights.map(p=>p.join('_')).join('-')}`;if(wallTextures.has(id))return wallTextures.get(id)!;
    const t=tex(id,48,100),c=t.context,foot=100,top=20;
    const drawFront=()=>{
      c.drawImage(front,variant*48,0,48,52,0,top+13,48,67);
      c.drawImage(coping,variant*48,0,48,26,0,top,48,15);
      c.fillStyle='rgba(2,5,10,.55)';c.fillRect(0,top+15,48,3);
      c.drawImage(front,variant*48,34,48,10,0,foot-7,48,7);
    };
    if(kind==='front'||kind==='pier')drawFront();
    if(kind==='west'||kind==='east'||kind==='both'){
      const px=kind==='east'?22:0,w=kind==='both'?48:26;
      c.drawImage(side,0,variant*40,36,80,px,20,w,80);
      c.fillStyle='rgba(3,8,16,.48)';c.fillRect(kind==='west'?0:44,22,4,78);
      c.drawImage(cap,0,0,44,20,px,20,w,12);
    }
    if(kind==='column'||kind==='corner'||kind==='pier'){
      const h=kind==='column'?96:kind==='corner'?84:80,w=kind==='column'?42:kind==='corner'?38:26,left=(48-w)/2;
      c.fillStyle='rgba(0,2,6,.5)';c.fillRect(left+5,foot-h+8,w, h-8);
      c.drawImage(props,127,30,34,62,left,foot-h,w,h);
      c.drawImage(cap,0,0,44,28,left-2,foot-h,w+4,20);
    }
    // World-aligned falloff crosses tile boundaries without alternating warm/cold strips.
    c.globalCompositeOperation='source-atop';
    for(const [dx,dy] of lights){
      const light=c.createRadialGradient(24+dx*48,60+dy*48,0,24+dx*48,60+dy*48,148);
      light.addColorStop(0,'rgba(255,183,75,.40)');light.addColorStop(.36,'rgba(247,164,59,.25)');light.addColorStop(1,'rgba(243,160,58,0)');
      c.fillStyle=light;c.fillRect(0,0,48,100);
    }
    c.globalCompositeOperation='source-over';
    t.refresh();wallTextures.set(id,t.key);return t.key;
  };
  const add=(image:Phaser.GameObjects.Image,x:number,y:number,wall:boolean,foot:number,width:number,height:number,baseAlpha=1)=>{
    image.setDepth(20+(foot/tile-1)*.01+(wall?.003:0));objects.push(image);
    image.setData({dungeonCell:[x,y],dungeonWall:wall,dungeonBaseAlpha:baseAlpha});
    parts.push({image,x,y,wall,foot,width,height,brightness:1,hidden:false,baseAlpha});return image;
  };
  for(const p of layout.walls){
    const lights=layout.torches.filter(([x,y])=>Math.abs(x-p.x)<=3&&Math.abs(y-p.y)<=1).map(([x,y]):[number,number]=>[x-p.x,y-p.y]);
    const kind=p.kind==='front'&&p.pier?'pier':p.kind;
    const key=makeWall(kind,hash(p.x,p.y)%3,lights);
    add(scene.add.image(p.x*tile,(p.y+1)*tile,key).setOrigin(0,1).setName('dungeon-wall'),p.x,p.y,true,(p.y+1)*tile,48,p.height);
    // A narrow cast shadow falls in front of free-standing columns.
    if(p.kind==='column'){
      g.fillStyle='rgba(2,5,11,.35)';g.beginPath();g.moveTo(p.x*tile+5,(p.y+1)*tile-5);g.lineTo(p.x*tile+42,(p.y+1)*tile-5);g.lineTo(p.x*tile+62,(p.y+1)*tile+25);g.lineTo(p.x*tile+21,(p.y+1)*tile+25);g.closePath();g.fill();
    }
  }
  for(const d of layout.doors){
    const image=scene.add.image((d.x+.5)*tile,(d.y+1)*tile-2,'dungeon-v3-architecture',d.side?1:0).setOrigin(.5,120/128).setFlipX(d.side&&d.flip).setName('dungeon-door');
    add(image,d.x,d.y,true,(d.y+1)*tile-2,d.side?31:60,83);
    parts[parts.length-1].door=true;
  }
  for(const p of decorations){
    const floorObject=p.surface==='floor';
    const foot=(p.y+1)*tile-(floorObject?5:24)+p.offsetY;
    // D89 엔진 소유 소품(p.kind 있음)은 kind 가 그림을 정한다 — storage·ruin 만 전용 그림. 클라이언트 추첨(옛 스트림·실험실)일 때만 해시로 변형을 섞는다.
    const cluster=floorObject&&(p.kind?p.kind==='storage':(p.frame===0||p.frame===1)&&hash(p.x,p.y)%3===0);
    const ruin=floorObject&&(p.kind?p.kind==='ruin':p.frame===3&&hash(p.x,p.y)%2===0);
    const texture=cluster||ruin?'dungeon-v3-architecture':'dungeon-v2-decor',frame=cluster?3:ruin?2:p.frame;
    const scale=cluster?.78:ruin?.85:floorObject?1.15:1.2;
    const image=scene.add.image((p.x+.5)*tile+p.offsetX,foot,texture,frame).setOrigin(.5,cluster||ruin?120/128:92/96).setScale(scale).setName('dungeon-furnishing');
    add(image,p.x,p.y,!floorObject,floorObject?foot:(p.y+1)*tile,floorObject?43:36,floorObject?42:80);
    if(!floorObject)image.setDepth(20+p.y*.01+.004);
    // D89 통행을 막지 않는 소품(blocks=false)은 그 칸에 선 몹(−0.005)·캐릭터(0)보다 뒤에 — 밟고 선 이가 소품에 가리지 않게.
    if(floorObject&&p.blocks===false)image.setDepth(20+p.y*.01-.006);
    if(floorObject){g.fillStyle='rgba(1,5,11,.34)';g.beginPath();g.ellipse((p.x+.5)*tile+p.offsetX,foot-2,22,7,0,0,Math.PI*2);g.fill();}
  }
  for(const [x,y] of layout.torches){
    const column=layout.walls.find(p=>p.x===x&&p.y===y)?.kind==='column';
    const foot=(y+1)*tile-(column?24:12);
    const flame=scene.add.image((x+.5)*tile-(column?15:0),foot,'dungeon-v2-props',0).setOrigin(.5,92/96).setScale(.9).setName('dungeon-torch');
    add(flame,x,y,true,(y+1)*tile+1,42,column?98:80);
    // Flame attachment shares its support's order, independent of its own image anchor.
    flame.setDepth(20+y*.01+.004);
  }
  for(const p of layout.walls.filter(p=>p.kind==='column')){
    const banner=scene.add.image((p.x+.5)*tile+4,(p.y+1)*tile-7,'dungeon-v2-decor',5).setOrigin(.5,92/96).setScale(1.12).setName('dungeon-column-banner');
    add(banner,p.x,p.y,true,(p.y+1)*tile,42,98);banner.setDepth(20+p.y*.01+.005);
  }
  for(const p of layout.walls){
    if(p.kind==='column'||hash(p.x,p.y)%9!==0||decorations.some(d=>d.x===p.x&&d.y===p.y)||layout.torches.some(([x,y])=>x===p.x&&y===p.y))continue;
    const ivy=scene.add.image((p.x+.5)*tile,(p.y+1)*tile-7,'dungeon-v3-weathering',2).setOrigin(.5,120/128).setScale(1.3).setName('dungeon-ivy');
    add(ivy,p.x,p.y,true,(p.y+1)*tile,38,80);ivy.setDepth(20+p.y*.01+.004);moss++;
  }
  // Rubble beyond the wall silhouette comes from the same stone art, never a second room layer.
  const exterior=new Set<string>(),wallCells=new Set(layout.walls.map(p=>p.x+','+p.y));
  for(const p of layout.walls){
    if(hash(p.x,p.y)%3!==0)continue;
    const candidates=[[p.x-1,p.y],[p.x+1,p.y],[p.x,p.y+1],[p.x,p.y-1]];
    const outside=candidates.find(([x,y])=>L.grid[y]?.[x]==='#'&&!wallCells.has(x+','+y)&&!exterior.has(x+','+y)
      &&[-1,0,1].every(dx=>L.grid[y]?.[x+dx]==='#'));
    if(!outside)continue;const [x,y]=outside;
    exterior.add(x+','+y);
    const rock=scene.add.image((x+.5)*tile,(y+1)*tile,'dungeon-v3-weathering',hash(x,y)%2).setOrigin(.5,120/128).setTint(0x72839d).setScale(1.05).setFlipX(hash(x,y)%3===0).setName('dungeon-exterior-rock');
    add(rock,p.x,p.y,false,(y+1)*tile,96,64,.75);rock.setDepth(.6);
  }
  groundTex.refresh();
  const ground=scene.add.image(0,-96,groundTex.key).setOrigin(0).setDepth(.5).setName('dungeon-v2-ground');
  const stats={hidden:0,remembered:0,cutaway:0};views.set(ground,{parts,objects,tile,stats});
  ground.setData({projected:true,wallHeight:80,torches:layout.torches,decorations,wallDetails:layout.walls,stoneFragments:fragments,moss,exteriorRocks:exterior.size,visibility:stats});
  ground.once('destroy',()=>{for(const o of objects)o.destroy();for(const key of keys)if(scene.textures.exists(key))scene.textures.remove(key);views.delete(ground);});
  return ground;
}
export function syncDungeonPrototype(scene:Phaser.Scene,visible:Set<string>|null,seen:Set<string>|null):void {
  const ground=scene.children.getByName('dungeon-v2-ground') as Phaser.GameObjects.Image|null;
  const view=ground&&views.get(ground);if(!view)return;
  view.stats.hidden=0;view.stats.remembered=0;
  for(const p of view.parts){const key=p.x+','+p.y,isVisible=!visible||visible.has(key),known=isVisible||!!seen?.has(key);
    p.hidden=!known;p.brightness=isVisible?1:.45;p.image.setVisible(known).setAlpha(p.brightness*p.baseAlpha);
    if(!known)view.stats.hidden++;else if(!isVisible)view.stats.remembered++;
  }
}
/** actors = 벽 뒤에 서면 그 벽을 옅게 하는 이들(파티). others = 문 칸 판정에만 드는 이들(보이는 산 몹) — 발(월드 px) 좌표. */
export function tickDungeonPrototype(scene:Phaser.Scene,actors:{x:number;y:number}[],others:{x:number;y:number}[]=[]):void {
  const ground=scene.children.getByName('dungeon-v2-ground') as Phaser.GameObjects.Image|null;
  const view=ground&&views.get(ground);if(!view)return;let cutaway=0;
  const t=view.tile,everyone=others.length?actors.concat(others):actors;
  for(const p of view.parts){if(!p.wall||p.hidden)continue;
    let obscures=actors.some(a=>Math.abs(a.x-(p.x+.5)*t)<p.width/2+12&&a.y<p.foot-7&&a.y>p.foot-p.height-12);
    // D88 문 칸 가림: 문 그림의 깊이(같은 줄 +0.0026)는 그 칸에 선 캐릭터(+0)·몹(−0.005)보다 앞이고, 위의 '벽 뒤' 조건(발이 문 발치보다 7px 넘게 위)에도
    // 안 걸려서 문 칸에 선 이가 닫힌 문 그림에 통째로 가려졌다. 문 칸 안에 발이 있으면 같은 28% 로 옅게 — 열고 지나가는 문처럼 읽힌다.
    if(!obscures&&p.door)obscures=everyone.some(a=>Math.abs(a.x-(p.x+.5)*t)<t/2&&a.y>p.y*t&&a.y<=(p.y+1)*t);
    p.image.setAlpha(p.brightness*(obscures?.28:1));if(obscures)cutaway++;
  }
  view.stats.cutaway=cutaway;
}

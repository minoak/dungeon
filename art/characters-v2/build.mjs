// Deterministic packing of generated component artwork, then shared-head composition.
import fs from 'node:fs/promises';
import {chromium} from '../../game/node_modules/playwright-core/index.mjs';
const here=new URL('./',import.meta.url),dest=new URL('../../viewer/assets/sprites/sd/',here);
const catalog=JSON.parse(await fs.readFile(new URL('catalog.json',here),'utf8'));
const pilot=JSON.parse(await fs.readFile(new URL('../character-bases-v1/modular-pilot/manifest.json',here),'utf8'));
const inputs={};
for(const [id,b]of Object.entries(catalog.bodies))inputs[id]='data:image/png;base64,'+(await fs.readFile(new URL(b.source||`source/${id}.png`,here))).toString('base64');
for(const id of ['hair-brown','hair-gold','hair-purple'])inputs[id]='data:image/png;base64,'+(await fs.readFile(new URL(`source/${id}.png`,here))).toString('base64');
for(const [id,stem]of [['pilot-short','short-head'],['pilot-long','long-head']])inputs[id]='data:image/png;base64,'+(await fs.readFile(new URL(`../character-bases-v1/modular-pilot/runtime/${stem}.png`,here))).toString('base64');
await fs.mkdir(new URL('runtime/',here),{recursive:true});await fs.mkdir(new URL('shared/',dest),{recursive:true});
const browser=await chromium.launch({channel:'msedge',headless:true});
try{
 const page=await browser.newPage();
 const packed=await page.evaluate(async({inputs,catalog,pilot})=>{
  const make=(w,h)=>{const c=document.createElement('canvas');c.width=w;c.height=h;return c;};
  const parts={},source={};
  for(const [id,url]of Object.entries(inputs)){
   const im=new Image();im.src=url;await im.decode();const c=make(im.width,im.height),g=c.getContext('2d',{willReadFrequently:true});g.drawImage(im,0,0);
   if(id.startsWith('pilot-')){source[id]={canvas:c};continue;}
   const pixels=g.getImageData(0,0,c.width,c.height),d=pixels.data,W=c.width,H=c.height,labels=new Int32Array(W*H),queue=new Int32Array(W*H),components=[];
   let label=0;
   for(let p=0;p<W*H;p++)if(!labels[p]&&d[p*4+3]>128){
    label++;let read=0,write=1;queue[0]=p;labels[p]=label;let x0=W,y0=H,x1=0,y1=0;
    while(read<write){const cur=queue[read++],x=cur%W,y=Math.floor(cur/W);x0=Math.min(x0,x);x1=Math.max(x1,x+1);y0=Math.min(y0,y);y1=Math.max(y1,y+1);
     for(let dy=-1;dy<=1;dy++)for(let dx=-1;dx<=1;dx++){const nx=x+dx,ny=y+dy,n=ny*W+nx;if(nx>=0&&nx<W&&ny>=0&&ny<H&&!labels[n]&&d[n*4+3]>128){labels[n]=label;queue[write++]=n;}}
    }components.push({label,area:write,bounds:[x0,y0,x1,y1]});
   }
   const cols=id.startsWith('hair-')?4:5,count=4*cols;
   const selected=components.sort((a,b)=>b.area-a.area).slice(0,count);
   if(selected.length!==count||selected.some(c=>c.area<1000))throw Error('Missing silhouettes '+id);
   const keep=new Set(selected.map(c=>c.label));
   for(let p=0;p<W*H;p++)d[p*4+3]=keep.has(labels[p])?255:0;
   g.putImageData(pixels,0,0);
   selected.sort((a,b)=>(a.bounds[1]+a.bounds[3])-(b.bounds[1]+b.bounds[3]));const ordered=[];
   for(let row=0;row<4;row++)ordered.push(...selected.slice(row*cols,row*cols+cols).sort((a,b)=>a.bounds[0]-b.bounds[0]));
   source[id]={canvas:c,pixels:d,labels,frames:ordered,sourceSize:[W,H]};
  }
  const manifest={version:3,cell:96,columns:5,directions:['front','right','back','left'],frameMs:160,footY:91,headPlacement:catalog.headPlacement,bodies:{},heads:{}};
  for(const [id,spec]of Object.entries(catalog.bodies)){
   const src=source[id],out=make(480,384),g=out.getContext('2d');g.imageSmoothingEnabled=false;
   const scale=45/Math.max(...src.frames.map(f=>f.bounds[3]-f.bounds[1]));const frames=[];
   for(let i=0;i<20;i++){
    const f=src.frames[i],[x0,y0,x1,y1]=f.bounds;let sum=0,n=0;
    for(let y=y0;y<y0+8;y++)for(let x=x0;x<x1;x++)if(src.labels[y*src.canvas.width+x]===f.label){sum+=x;n++;}
    const ax=sum/n,w=Math.round((x1-x0)*scale),h=Math.round((y1-y0)*scale),dx=Math.round(48-(ax-x0)*scale),dy=92-h,row=Math.floor(i/5),col=i%5;
    if(dx<1||dx+w>95||dy<1)throw Error('Clipped body '+id);
    const tile=make(96,96),tg=tile.getContext('2d');tg.imageSmoothingEnabled=false;
    tg.drawImage(src.canvas,x0,y0,x1-x0,y1-y0,dx,dy,w,h);
    const td=tg.getImageData(0,0,96,96).data;let bottom=0;
    for(let p=0;p<96*96;p++)if(td[p*4+3])bottom=Math.max(bottom,Math.floor(p/96));
    const settle=91-bottom;g.drawImage(tile,col*96,row*96+settle);
    frames.push({row,col,bounds:f.bounds,anchor:[ax,y0],runtime:[dx,dy+settle,w,h],neck:[48,dy+settle+2]});
   }
   parts[id]=out;manifest.bodies[id]={...spec,sheet:`runtime/${id}.png`,frames,scale,sourceSize:src.sourceSize};
  }
  for(const [id,spec]of Object.entries(catalog.heads)){
   if(spec.source.startsWith('pilot-')){
    const old=pilot.heads[spec.source==='pilot-short'?'short-head':'long-head'];
    parts[id]=source[spec.source].canvas;manifest.heads[id]={...old,...spec,sheet:`runtime/${id}.png`};continue;
   }
   const src=source[spec.source],frames=src.frames.slice(spec.row*4,spec.row*4+4);
   // Art-directed neck attachment points. Blonde highlights are not a reliable
   // skin mask: the old detector picked ponytail/braid tips as necks.
   const anchors=spec.anchors;
   if(!Array.isArray(anchors)||anchors.length!==4||anchors.some(a=>a.length!==2||!a.every(Number.isFinite)))throw Error('Missing reviewed neck anchors '+id);
   const frontY=anchors[0][1];
   const scale=42/(frontY-frames[0].bounds[1]),out=make(96,384),g=out.getContext('2d');g.imageSmoothingEnabled=false;const packed=[];
   for(let row=0;row<4;row++){
    const [x0,y0,x1,y1]=frames[row].bounds,[ax,ay]=anchors[row],w=Math.round((x1-x0)*scale),h=Math.round((y1-y0)*scale),dx=Math.round(48-(ax-x0)*scale),dy=Math.round(48-(ay-y0)*scale);
    if(dx<1||dy<1||dx+w>95||dy+h>95)throw Error('Clipped head '+JSON.stringify({id,row,dx,dy,w,h,anchors}));
    g.drawImage(src.canvas,x0,y0,x1-x0,y1-y0,dx,row*96+dy,w,h);packed.push({row,bounds:frames[row].bounds,anchor:[ax,ay],runtime:[dx,dy,w,h]});
   }
   parts[id]=out;manifest.heads[id]={...spec,sheet:`runtime/${id}.png`,anchor:[48,48],frames:packed,scale,sourceSize:src.sourceSize};
  }
  return {manifest,parts:Object.fromEntries(Object.entries(parts).map(([id,c])=>[id,c.toDataURL('image/png').split(',')[1]]))};
 },{inputs,catalog,pilot});
 for(const [id,png]of Object.entries(packed.parts))await fs.writeFile(new URL(`runtime/${id}.png`,here),Buffer.from(png,'base64'));
 await fs.writeFile(new URL('manifest.json',here),JSON.stringify(packed.manifest,null,2)+'\n');
 // Use the same composer in preview and production exports.
 const composer=await fs.readFile(new URL('../character-bases-v1/modular-pilot/compose.js',here),'utf8');
 const compiled=await page.evaluate(async({packed,composer})=>{
  const module=await import(URL.createObjectURL(new Blob([composer],{type:'text/javascript'}))),images={};
  for(const [id,png]of Object.entries(packed.parts)){const im=new Image();im.src='data:image/png;base64,'+png;await im.decode();images[`runtime/${id}.png`]=im;}
  const assets={manifest:packed.manifest,images},sheets={},checks=[];
  for(const body of Object.keys(packed.manifest.bodies))for(const head of Object.keys(packed.manifest.heads)){
   const sheet=document.createElement('canvas');sheet.width=480;sheet.height=384;const g=sheet.getContext('2d',{willReadFrequently:true});
   for(let row=0;row<4;row++)for(let col=0;col<5;col++){
    g.save();g.translate(col*96,row*96);module.drawCharacter(g,assets,body,head,packed.manifest.directions[row],col);g.restore();
    const d=g.getImageData(col*96,row*96,96,96).data;let x0=96,y0=96,x1=-1,y1=-1,count=0;
    for(let y=0;y<96;y++)for(let x=0;x<96;x++){const a=d[(y*96+x)*4+3];if(a!==0&&a!==255)throw Error('Nonbinary alpha');if(a){count++;x0=Math.min(x0,x);y0=Math.min(y0,y);x1=Math.max(x1,x);y1=Math.max(y1,y);}}
    if(count<500||x0<1||x1>94||y0<1||y1!==91)throw Error('Bounds '+JSON.stringify({body,head,row,col,count,x0,y0,x1,y1}));
    checks.push({body,head,row,col,bounds:[x0,y0,x1,y1]});
   }sheets[body+'--'+head]=sheet.toDataURL('image/png').split(',')[1];
  }return {sheets,checks};
 },{packed,composer});
 for(const [id,png]of Object.entries(compiled.sheets))await fs.writeFile(new URL(`shared/${id}.png`,dest),Buffer.from(png,'base64'));
 const atlas=JSON.parse(await fs.readFile(new URL('atlas.json',dest),'utf8'));
 for(const id of ['sd-warrior','sd-rogue','sd-archer','sd-warrior-illustration'])if(atlas.presets[id])atlas.presets[id].selectable=false;
 for(const [id,b]of Object.entries(catalog.bodies)){
  // looks = 세계 안에서 보이는 모습 한 줄('낯선 사람' 판의 겉모습 문장 — sheetkit.looks_line 이 읽는다). name 은 고르는 목록용 분류 이름.
  const hairstyles=Object.fromEntries(Object.entries(catalog.heads).map(([h,v])=>[h,{name:v.name,...(v.looks?{looks:v.looks}:{}),sheet:`shared/${id}--${h}.png`}]));
  // The default alias is kept for old consumers; selectors show the 14 actual ids.
  atlas.presets['sd-'+id]={name:b.name,...(b.looks?{looks:b.looks}:{}),job:b.job,sex:b.sex,sharedHair:true,defaultHair:b.defaultHair,sheet:hairstyles[b.defaultHair].sheet,hairstyles:{default:hairstyles[b.defaultHair],...hairstyles}};
 }
 await fs.writeFile(new URL('atlas.json',dest),JSON.stringify(atlas,null,2)+'\n');
 const report={bodies:8,hairs:14,combinations:Object.keys(compiled.sheets).length,frames:compiled.checks.length,checks:compiled.checks};
 await fs.writeFile(new URL('build-report.json',here),JSON.stringify(report,null,2)+'\n');
 console.log(JSON.stringify({...report,checks:undefined}));
}finally{await browser.close();}

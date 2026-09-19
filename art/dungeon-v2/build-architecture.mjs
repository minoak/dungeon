import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const sharp=require(path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp'));
const here=path.dirname(fileURLToPath(import.meta.url));
const out=path.join(here,'runtime');
const report={referenceSamples:[],sprites:[]};
const reference=sharp(path.join(here,'concept.png'));
// Source rectangles from the approved composition; these are atlas samples, not replacement artwork.
const patches=[
 ['concept-floor',{left:687,top:367,width:144,height:256},144,256],
 ['concept-front',{left:1107,top:590,width:144,height:52},144,52],
 ['concept-coping',{left:1107,top:562,width:144,height:26},144,26],
 ['concept-side',{left:143,top:63,width:36,height:168},36,168],
 ['concept-cap',{left:484,top:28,width:44,height:28},44,28],
];
for(const [name,box,w,h] of patches){
 await reference.clone().extract(box).resize(w,h,{kernel:'nearest'}).png().toFile(path.join(out,name+'.png'));
 report.referenceSamples.push({name,source:box,width:w,height:h});
}
const input=sharp(path.join(here,'source/architecture.png'));
const {data,info}=await input.ensureAlpha().raw().toBuffer({resolveWithObject:true});
assert.equal(data[3],0,'Generated source must have real alpha');
const splitX=Math.floor(info.width/2),splitY=Math.floor(info.height*.60);
const areas=[[0,0,splitX,splitY],[splitX,0,info.width,splitY],[0,splitY,splitX,info.height],[splitX,splitY,info.width,info.height]];
const sizes=[[60,80],[31,83],[53,48],[61,48]];
const cells=[];
for(let i=0;i<4;i++){
 const [x0,y0,x1,y1]=areas[i];let l=x1,t=y1,r=x0,b=y0;
 for(let y=y0;y<y1;y++)for(let x=x0;x<x1;x++)if(data[(y*info.width+x)*4+3]>32){l=Math.min(l,x);t=Math.min(t,y);r=Math.max(r,x+1);b=Math.max(b,y+1);}
 assert(l>x0&&t>y0&&r<x1&&b<y1,'Object intersects crop boundary '+i);
 const box={left:l,top:t,width:r-l,height:b-t},scale=Math.min(sizes[i][0]/box.width,sizes[i][1]/box.height);
 const w=Math.round(box.width*scale),h=Math.round(box.height*scale);
 cells.push({input:await input.clone().extract(box).resize(w,h,{kernel:'nearest'}).png().toBuffer(),left:i%2*128+Math.floor((128-w)/2),top:Math.floor(i/2)*128+120-h});
 report.sprites.push({frame:i,source:box,width:w,height:h,cell:128,foot:120});
}
await sharp({create:{width:256,height:256,channels:4,background:'#00000000'}}).composite(cells).png().toFile(path.join(out,'architecture.png'));
// Weathering stays separate from architectural shapes, so density can vary by seed.
const weather=sharp(path.join(here,'source/weathering.png'));
const weatherPixels=await weather.ensureAlpha().raw().toBuffer({resolveWithObject:true});
assert.equal(weatherPixels.data[3],0,'Weathering source must have real alpha');
const ww=weatherPixels.info.width,wh=weatherPixels.info.height,weatherCells=[];
report.weathering=[];
const weatherSizes=[[94,64],[80,74],[27,79],[48,24]];
for(let i=0;i<4;i++){
 const x0=i%2*ww/2,y0=Math.floor(i/2)*wh/2,x1=x0+ww/2,y1=y0+wh/2;
 let l=x1,t=y1,r=x0,b=y0;
 for(let y=y0;y<y1;y++)for(let x=x0;x<x1;x++)if(weatherPixels.data[(y*ww+x)*4+3]>32){l=Math.min(l,x);t=Math.min(t,y);r=Math.max(r,x+1);b=Math.max(b,y+1);}
 assert(l>x0&&t>y0&&r<x1&&b<y1,'Weathering touches crop boundary '+i);
 const box={left:l,top:t,width:r-l,height:b-t},scale=Math.min(weatherSizes[i][0]/box.width,weatherSizes[i][1]/box.height);
 const w=Math.round(box.width*scale),h=Math.round(box.height*scale);
 weatherCells.push({input:await weather.clone().extract(box).resize(w,h,{kernel:'nearest'}).png().toBuffer(),left:i%2*128+Math.floor((128-w)/2),top:Math.floor(i/2)*128+120-h});
 report.weathering.push({frame:i,source:box,width:w,height:h,cell:128,foot:120});
}
await sharp({create:{width:256,height:256,channels:4,background:'#00000000'}}).composite(weatherCells).png().toFile(path.join(out,'weathering.png'));
await fs.writeFile(path.join(here,'architecture-build.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report));

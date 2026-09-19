// Append environment art without changing any of the existing 20 prop frames.
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
const require=createRequire(import.meta.url);
let sharp;try{sharp=require('sharp')}catch{sharp=require(path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp'))}
const here=path.dirname(fileURLToPath(import.meta.url));
const file=path.join(here,'source/details.png');
const {data,info}=await sharp(file).ensureAlpha().raw().toBuffer({resolveWithObject:true});
const ids=['tree','pine','hedge','flowers','stone_wall','stone_wall_vertical','fence','cliff','fountain','banner_lamp','market_red','market_blue','statue','crates','cart','stairs'];
const layers=[{input:await fs.readFile(path.join(here,'runtime/props.png')),left:0,top:0}];
for(let i=0;i<16;i++){
  const x0=Math.round(i%4*info.width/4),x1=Math.round((i%4+1)*info.width/4);
  const y0=Math.round(Math.floor(i/4)*info.height/4),y1=Math.round((Math.floor(i/4)+1)*info.height/4);
  let l=x1,r=x0,t=y1,b=y0;
  for(let y=y0;y<y1;y++)for(let x=x0;x<x1;x++)if(data[(y*info.width+x)*4+3]>32){l=Math.min(l,x);r=Math.max(r,x+1);t=Math.min(t,y);b=Math.max(b,y+1)}
  if(r<=l||b<=t)throw Error('Empty detail: '+ids[i]);
  const sprite=await sharp(file).extract({left:l,top:t,width:r-l,height:b-t}).resize(132,132,{fit:'inside',kernel:'nearest'}).png().toBuffer();
  const m=await sharp(sprite).metadata(),frame=i+20;
  layers.push({input:sprite,left:frame%4*144+Math.floor((144-m.width)/2),top:Math.floor(frame/4)*144+138-m.height});
}
const result=await sharp({create:{width:576,height:1296,channels:4,background:{r:0,g:0,b:0,alpha:0}}}).composite(layers).png().toBuffer();
await fs.writeFile(path.join(here,'runtime/props-detailed.png'),result);
await fs.writeFile(path.join(here,'../../game/src/assets/world/town-props.png'),result);
await fs.writeFile(path.join(here,'runtime/detail-manifest.json'),JSON.stringify(Object.fromEntries(ids.map((id,i)=>[id,{frame:i+20,cell:144,foot:138}])),null,2)+'\n');
console.log('Packed 16 environment sprites, preserving frames 0–19.');

// Slice generated atlases at transparent gutters, then alpha-trim and pack.
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
const require=createRequire(import.meta.url);
let sharp;try{sharp=require('sharp')}catch{sharp=require(path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp'))}
const here=path.dirname(fileURLToPath(import.meta.url)),root=path.resolve(here,'../..'),dest=path.join(root,'game/src/assets/world');
await fs.mkdir(path.join(here,'runtime'),{recursive:true});
async function slices(file,cols,rows){
 const {data,info}=await sharp(file).ensureAlpha().raw().toBuffer({resolveWithObject:true});
 const xsum=new Array(info.width).fill(0),ysum=new Array(info.height).fill(0);
 for(let y=0;y<info.height;y++)for(let x=0;x<info.width;x++)if(data[(y*info.width+x)*4+3]>64){xsum[x]++;ysum[y]++}
 if(!xsum.includes(0)||!ysum.includes(0))throw Error('Atlas needs transparent gutters: '+file);
 function cuts(hist,n){const out=[0];for(let k=1;k<n;k++){const ideal=hist.length*k/n,r=Math.floor(hist.length/n*.2);let best=Math.round(ideal);for(let p=Math.floor(ideal)-r;p<Math.ceil(ideal)+r;p++)if(hist[p]<hist[best]||(hist[p]===hist[best]&&Math.abs(p-ideal)<Math.abs(best-ideal)))best=p;if(hist[best]>3)throw Error('No safe atlas gutter: '+file);out.push(best)}return [...out,hist.length]}
 const xs=cuts(xsum,cols),ys=cuts(ysum,rows),out=[];
 for(let row=0;row<rows;row++)for(let col=0;col<cols;col++){
  let l=xs[col+1],r=xs[col],t=ys[row+1],b=ys[row];
  for(let y=ys[row];y<ys[row+1];y++)for(let x=xs[col];x<xs[col+1];x++)if(data[(y*info.width+x)*4+3]>32){l=Math.min(l,x);r=Math.max(r,x+1);t=Math.min(t,y);b=Math.max(b,y+1)}
  if(r<=l||b<=t)throw Error('Empty sprite');
  out.push(await sharp(file).extract({left:l,top:t,width:r-l,height:b-t}).png().toBuffer());
 }
 return out;
}
const ids=['general_store','blacksmith','craft_workshop','equipment_store','shared_lodging','small_home','ordinary_inn','garden_inn'];
const widths=[432,384,384,432,384,288,432,480];
const buildings=await slices(path.join(here,'source/buildings.png'),4,2),manifest={buildings:{},props:{}};
for(let i=0;i<ids.length;i++){
 const name=ids[i],filename=path.join(here,'runtime',name+'.png');
 await sharp(buildings[i]).resize({width:widths[i],kernel:'nearest'}).png().toFile(filename);
 await fs.copyFile(filename,path.join(dest,'town-'+name+'.png'));
 const m=await sharp(filename).metadata();manifest.buildings[name]={width:m.width,height:m.height,source:'source/buildings.png',cell:i};
}
const props=await slices(path.join(here,'source/props.png'),4,3);
const propIds=['anvil','workbench','rack','produce','goods','table','bench','board','stone','well','laundry','crate'];
const layers=[{input:await fs.readFile(path.join(root,'art/town-v1/runtime/props.png')),left:0,top:0}];
for(let i=0;i<props.length;i++){
 const sprite=await sharp(props[i]).resize(128,128,{fit:'inside',kernel:'nearest'}).png().toBuffer();
 const m=await sharp(sprite).metadata(),frame=i+8;
 layers.push({input:sprite,left:frame%4*144+Math.floor((144-m.width)/2),top:Math.floor(frame/4)*144+138-m.height});
 manifest.props[propIds[i]]={frame,foot:138,cell:144};
}
const propFile=path.join(here,'runtime/props.png');
await sharp({create:{width:576,height:720,channels:4,background:{r:0,g:0,b:0,alpha:0}}}).composite(layers).png().toFile(propFile);
await fs.copyFile(propFile,path.join(dest,'town-props.png'));
await fs.writeFile(path.join(here,'runtime/manifest.json'),JSON.stringify(manifest,null,2)+'\n');
console.log('Packed 8 buildings and 12 props; legacy prop frames 0-7 preserved.');
await import('./pack-details.mjs');
await import('./pack-paving.mjs');

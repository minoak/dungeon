// Preserve legacy terrain frames, then pack 2x2 material motifs at 48px per tile.
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
const require=createRequire(import.meta.url);
let sharp;try{sharp=require('sharp')}catch{sharp=require(path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp'))}
const here=path.dirname(fileURLToPath(import.meta.url)),file=path.join(here,'source/paving.png');
const m=await sharp(file).metadata();
const layers=[{input:await fs.readFile(path.join(here,'../town-v1/runtime/terrain.png')),left:0,top:0}];
for(let i=0;i<8;i++){
 const x0=Math.round(i%4*m.width/4),x1=Math.round((i%4+1)*m.width/4),y0=Math.round(Math.floor(i/4)*m.height/2),y1=Math.round((Math.floor(i/4)+1)*m.height/2);
 const motif=await sharp(file).extract({left:x0,top:y0,width:x1-x0,height:y1-y0}).resize(96,96,{kernel:'nearest'}).png().toBuffer();
 for(let part=0;part<4;part++){
   const frame=8+i*4+part,input=await sharp(motif).extract({left:part%2*48,top:Math.floor(part/2)*48,width:48,height:48}).png().toBuffer();
   layers.push({input,left:frame%4*48,top:Math.floor(frame/4)*48});
 }
}
const result=await sharp({create:{width:192,height:480,channels:4,background:{r:0,g:0,b:0,alpha:0}}}).composite(layers).png().toBuffer();
await fs.writeFile(path.join(here,'runtime/terrain-paved.png'),result);
await fs.writeFile(path.join(here,'../../game/src/assets/world/town-terrain.png'),result);
console.log('Paving atlas: original 8 frames preserved + 32 material frames.');

// 생성 원본 알파를 그대로 보존하고 여백만 제거해 게임 크기로 패킹한다.
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
const require=createRequire(import.meta.url);
let sharp;try{sharp=require('sharp')}catch{sharp=require(path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp'))}
const here=path.dirname(fileURLToPath(import.meta.url)),root=path.resolve(here,'../..');
const sources={temple:'exec-5e6049e7-1728-48ed-8ef2-f3307b817698.png',tavern:'exec-8cb4c1a9-b167-4ce2-9dd9-5b98e199d12a.png',gate:'exec-f5c820b1-1ac6-4084-afa2-edb1c951612d.png'};
await fs.mkdir(path.join(here,'source'),{recursive:true});await fs.mkdir(path.join(here,'runtime'),{recursive:true});
const manifest={};
for(const [id,name] of Object.entries(sources)){
 const source=path.join(here,'source',id+'.png');
 try{await fs.access(source)}catch{await fs.copyFile(path.join(os.homedir(),'.codex/generated_images/01a0906f-31d1-7903-be0c-a7ae23da4400',name),source)}
 const {data,info}=await sharp(source).ensureAlpha().raw().toBuffer({resolveWithObject:true});
 let l=info.width,t=info.height,r=0,b=0;
 for(let y=0;y<info.height;y++)for(let x=0;x<info.width;x++)if(data[(y*info.width+x)*4+3]>64){l=Math.min(l,x);r=Math.max(r,x+1);t=Math.min(t,y);b=Math.max(b,y+1)}
 const width={temple:480,tavern:576,gate:384}[id],height=Math.round((b-t)/(r-l)*width);
 const dst=path.join(here,'runtime',id+'.png');
 await sharp(source).extract({left:l,top:t,width:r-l,height:b-t}).resize(width,height,{kernel:'nearest'}).png().toFile(dst);
 await fs.copyFile(dst,path.join(root,'game/src/assets/world','town-'+id+'.png'));
 manifest[id]={width,height,source:'source/'+id+'.png',runtime:'runtime/'+id+'.png',alpha:true};
}
await fs.writeFile(path.join(here,'runtime/manifest.json'),JSON.stringify(manifest,null,2));
console.log(manifest);

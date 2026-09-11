// imagegen 원본의 키 배경을 알파로 변환하고 셀을 규격화한다. 그림 내용은 새로 그리지 않는다.
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
const require=createRequire(import.meta.url);
let sharp; try{sharp=require('sharp')}catch{sharp=require(path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp'))}
const here=path.dirname(fileURLToPath(import.meta.url)), out=path.join(here,'runtime');
await fs.mkdir(out,{recursive:true});
const report={};
async function read(name,key=false){
 const {data,info}=await sharp(path.join(here,'source',name)).ensureAlpha().raw().toBuffer({resolveWithObject:true});
 if(key)for(let i=0;i<data.length;i+=4){
  // 마젠타 배경과 그 위의 그림자만 제외한다. 물체의 갈색·붉은색·청록색은 유지한다.
  if(Math.min(data[i],data[i+2])-data[i+1]>55 && data[i]>100 && data[i+2]>90)data[i+3]=0;
 }
 return {data,width:info.width,height:info.height};
}
function cell(s,col,row,cols,rows){const l=Math.round(col*s.width/cols),t=Math.round(row*s.height/rows);return {left:l,top:t,width:Math.round((col+1)*s.width/cols)-l,height:Math.round((row+1)*s.height/rows)-t}}
function bounds(s,c){let l=c.left+c.width,t=c.top+c.height,r=c.left,b=c.top;
 for(let y=c.top;y<c.top+c.height;y++)for(let x=c.left;x<c.left+c.width;x++)if(s.data[(y*s.width+x)*4+3]>127){l=Math.min(l,x);t=Math.min(t,y);r=Math.max(r,x+1);b=Math.max(b,y+1)}
 assert(r>l&&b>t,'빈 프레임');assert(l>c.left&&t>c.top&&r<c.left+c.width&&b<c.top+c.height,'원본 프레임 경계 접촉');return {left:l,top:t,width:r-l,height:b-t};
}
const pipeline=s=>sharp(s.data,{raw:{width:s.width,height:s.height,channels:4}});
const blank=(w,h)=>sharp({create:{width:w,height:h,channels:4,background:'#00000000'}});
const terrain=await read('terrain.png'),tilePieces=[];
for(let i=0;i<8;i++){const b=cell(terrain,i%4,Math.floor(i/4),4,2);tilePieces.push({input:await pipeline(terrain).extract(b).resize(48,48,{kernel:'nearest'}).png().toBuffer(),left:i%4*48,top:Math.floor(i/4)*48})}
await blank(192,96).composite(tilePieces).png().toFile(path.join(out,'terrain.png'));
report.terrain={size:[192,96],cell:48,frames:8};
const guild=await read('guild-key.png',true),gb=bounds(guild,cell(guild,0,0,1,1));
const gh=Math.round(gb.height/gb.width*576);
await pipeline(guild).extract(gb).resize(576,gh,{kernel:'nearest'}).png().toFile(path.join(out,'guild.png'));
report.guild={size:[576,gh],source:gb,entrance:[282,gh-15]};
const props=await read('props-key.png',true),pieces=[],propFrames=[];
const limits=[[48,128],[118,118],[120,68],[74,74],[72,112],[140,76],[84,65],[128,85]];
for(let i=0;i<8;i++){
 const b=bounds(props,cell(props,i%4,Math.floor(i/4),4,2)),limit=limits[i],scale=Math.min(limit[0]/b.width,limit[1]/b.height);
 const w=Math.round(b.width*scale),h=Math.round(b.height*scale),x=Math.round((144-w)/2),y=138-h;
 assert(x>=2&&y>=2,'소품 잘림');pieces.push({input:await pipeline(props).extract(b).resize(w,h,{kernel:'nearest'}).png().toBuffer(),left:i%4*144+x,top:Math.floor(i/4)*144+y});propFrames.push({source:b,rect:[x,y,w,h]});
}
await blank(576,288).composite(pieces).png().toFile(path.join(out,'props.png'));
report.props={size:[576,288],cell:144,foot:138,frames:propFrames};
const npcs=await read('npcs-key.png',true),npcPieces=[],npcFrames=[];
for(let row=0;row<3;row++){
 const boxes=Array.from({length:4},(_,col)=>bounds(npcs,cell(npcs,col,row,4,3)));
 const scale=Math.min(78/Math.max(...boxes.map(b=>b.width)),82/Math.max(...boxes.map(b=>b.height)));
 for(let col=0;col<4;col++){
  const b=boxes[col],w=Math.round(b.width*scale),h=Math.round(b.height*scale),x=Math.round((96-w)/2),y=91-h;
  assert(x>=2&&y>=2&&x+w<=94,'NPC 잘림');npcPieces.push({input:await pipeline(npcs).extract(b).resize(w,h,{kernel:'nearest'}).png().toBuffer(),left:col*96+x,top:row*96+y});npcFrames.push({row,col,source:b,rect:[x,y,w,h],scale});
 }
}
await blank(384,288).composite(npcPieces).png().toFile(path.join(out,'npcs.png'));
report.npcs={size:[384,288],cell:96,foot:91,directions:['front','right','back','left'],frames:npcFrames};
// 프리뷰 폴더 하나만 서빙해도 기존 모험가와 비교할 수 있도록 원본 시트를 그대로 복사한다.
for(const name of ['warrior-twintails','rogue-ponytail','archer'])await fs.copyFile(path.resolve(here,'../../viewer/assets/sprites/sd',name+'.png'),path.join(out,name+'.png'));
for(const name of ['guild','props','npcs']){
 const {data}=await sharp(path.join(out,name+'.png')).ensureAlpha().raw().toBuffer({resolveWithObject:true});let opaque=0,transparent=0,key=0;
 for(let i=0;i<data.length;i+=4){if(data[i+3]===0)transparent++;else{opaque++;if(Math.min(data[i],data[i+2])-data[i+1]>55&&data[i]>100&&data[i+2]>90)key++}}
 assert(transparent>0&&opaque>0&&key===0,'알파/키 색 검사 실패: '+name);report[name].alphaCheck={opaque,transparent,keyPixels:key};
}
await fs.writeFile(path.join(here,'build-report.json'),JSON.stringify(report,null,2)+'\n');
console.log('PASS: 바닥 8종, 소품 8종, NPC 3종×4방향, 길드 외관; 잘림·빈 프레임·알파 검사');

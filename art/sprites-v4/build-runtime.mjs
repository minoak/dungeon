// 생성 원본을 보존하고, 크로마키 배경·프레임 여백을 런타임용 PNG로 정리한다.
// 실행: node art/sprites-v4/build-runtime.mjs (Playwright + Edge 또는 Chromium 필요)
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath, pathToFileURL} from 'node:url';
const here = path.dirname(fileURLToPath(import.meta.url));
const output = path.resolve(here, '../../viewer/assets/sprites/sd');
const playwright = await import('playwright').catch(() => import(pathToFileURL(path.join(
  os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs'))));
const browser = await playwright.chromium.launch({headless:true, ...(process.platform === 'win32' ? {channel:'msedge'} : {})});
const manifest = {version:2, cell:96, directions:['front','right','back','left'], columns:5,
  frame_ms:160, display_scale:1.5, presets:{}};
const hairStyles={
  warrior:[['default','헝클어진 머리'],['parted','가르마'],['halfup','반묶음'],['long','긴 머리'],['twintails','양갈래']],
  archer:[['default','포니테일'],['bob','단발'],['braid','땋은 머리']],
  rogue:[['default','단발 + 옆땋기'],['pixie','숏컷'],['ponytail','포니테일']],
};
const reports = {};
await fs.mkdir(output, {recursive:true});
try {
  const page = await browser.newPage();
  for (const [job,name] of [['warrior','SD 검사'],['archer','SD 궁수'],['rogue','SD 도적']]) {
    const preset=manifest.presets[`sd-${job}`]={name,sheet:`${job}.png`,job:{warrior:'전사',archer:'궁수',rogue:'도적'}[job],hairstyles:{}};
    for(const [style,hairName] of hairStyles[job]) {
    const stem=style==='default'?job:`${job}-${style}`;
    const source = await fs.readFile(path.join(here, style==='default'?`sd-${job}-source.png`:`hairstyles/${stem}-source.png`));
    const result = await page.evaluate(async ({url,size,reference}) => {
      const image = new Image(); image.src=url; await image.decode();
      const canvas = document.createElement('canvas');
      canvas.width=image.width; canvas.height=image.height;
      const ctx=canvas.getContext('2d', {willReadFrequently:true}); ctx.drawImage(image,0,0);
      const pixels=ctx.getImageData(0,0,canvas.width,canvas.height);
      // 자주색 옷의 낮은 채도는 남기고, 원본의 강한 분홍 배경과 경계 혼색만 제거한다.
      for(let i=0;i<pixels.data.length;i+=4){
        const [r,g,b]=pixels.data.slice(i,i+3);
        if(r>115 && b>90 && Math.min(r,b)-g>60) pixels.data[i+3]=0;
      }
      // 투명 배경과 맞닿은 픽셀의 분홍 혼색을 중화한다. 보라색 머리·의상의 내부 색은 보존한다.
      const rgba=pixels.data, width=canvas.width;
      for(let y=1;y<canvas.height-1;y++)for(let x=1;x<width-1;x++){
        const i=(y*width+x)*4;
        if(!rgba[i+3])continue;
        const excess=Math.min(rgba[i],rgba[i+2])-rgba[i+1];
        if(excess<=25)continue;
        let edge=false;
        for(let dy=-1;dy<=1;dy++)for(let dx=-1;dx<=1;dx++)
          if(!rgba[((y+dy)*width+x+dx)*4+3])edge=true;
        if(edge){rgba[i]-=excess;rgba[i+2]-=excess;}
      }
      ctx.putImageData(pixels,0,0);
      const frames=[];
      // 생성 시트는 행 간격이 정확한 등분이 아니다. 투명한 틈으로 행·열을 분리한다.
      const bands = values => {
        const out=[];
        for(let i=0;i<values.length;i++) if(values[i]) {
          const start=i; while(i+1<values.length && values[i+1]) i++;
          out.push([start,i+1]);
        }
        return out;
      };
      const rowCounts=Array(canvas.height).fill(0);
      for(let y=0;y<canvas.height;y++)for(let x=0;x<canvas.width;x++)
        if(pixels.data[(y*canvas.width+x)*4+3])rowCounts[y]++;
      const rows=bands(rowCounts);
      if(rows.length!==4)throw new Error('원본 행 분리 실패: '+JSON.stringify(rows));
      const columns=rows.map(([top,bottom])=>{
        const counts=Array(canvas.width).fill(0);
        for(let y=top;y<bottom;y++)for(let x=0;x<canvas.width;x++)
          if(pixels.data[(y*canvas.width+x)*4+3])counts[x]++;
        return bands(counts);
      });
      if(columns.some(c=>c.length!==5))throw new Error('원본 열 분리 실패');
      for(let row=0;row<4;row++) for(let col=0;col<5;col++){
        const cell=[columns[row][col][0]-1,rows[row][0]-1,columns[row][col][1]+1,rows[row][1]+1];
        let x0=cell[2], y0=cell[3], x1=0, y1=0;
        for(let y=cell[1];y<cell[3];y++)for(let x=cell[0];x<cell[2];x++){
          if(!pixels.data[(y*canvas.width+x)*4+3])continue;
          x0=Math.min(x0,x); y0=Math.min(y0,y); x1=Math.max(x1,x+1); y1=Math.max(y1,y+1);
        }
        if(x1<=x0 || y1<=y0) throw new Error('빈 프레임');
        if(x0<=cell[0] || y0<=cell[1] || x1>=cell[2] || y1>=cell[3]) throw new Error('원본 셀 경계에 닿는 프레임: '+JSON.stringify({row,col,cell,bounds:[x0,y0,x1,y1]}));
        // 머리의 중심을 기준으로 정렬한다. 무기나 망토가 흔들려도 몸이 좌우로 밀리지 않는다.
        let hx0=x1,hx1=x0;
        for(let y=y0;y<y0+(y1-y0)*.40;y++) for(let x=x0;x<x1;x++){
          if(pixels.data[(y*canvas.width+x)*4+3]){hx0=Math.min(hx0,x);hx1=Math.max(hx1,x+1);}
        }
        // 헤어의 부피가 달라져도 몸은 원래 머리 중심에 둔다.
        const anchor=reference ? reference.frames[row*5+col].anchor*image.width/reference.source_size[0] : (hx0+hx1)/2;
        frames.push({row,col,bounds:[x0,y0,x1,y1],anchor});
      }
      const heights=frames.map(f=>f.bounds[3]-f.bounds[1]).sort((a,b)=>a-b);
      // 모든 방향에 같은 배율을 사용한다. 프레임별 꽉 채우기는 캐릭터를 숨 쉬듯 늘였다 줄인다.
      // 짧은 머리를 골랐다고 몸까지 커지지 않도록 기본 외형의 배율을 재사용한다.
      const scale=reference ? reference.scale*reference.source_size[1]/image.height : (size-10)/heights.at(-1);
      const atlas=document.createElement('canvas'); atlas.width=size*5; atlas.height=size*4;
      const a=atlas.getContext('2d'); a.imageSmoothingEnabled=false;
      for(const frame of frames){
        const [x0,y0,x1,y1]=frame.bounds;
        const w=Math.round((x1-x0)*scale),h=Math.round((y1-y0)*scale);
        const dx=Math.round(size/2-(frame.anchor-x0)*scale),dy=size-4-h;
        if(dx<2 || dx+w>size-2 || dy<2)throw new Error('런타임 프레임 잘림');
        a.drawImage(canvas,x0,y0,x1-x0,y1-y0,frame.col*size+dx,frame.row*size+dy,w,h);
        frame.runtime=[dx,dy,w,h];
      }
      return {png:atlas.toDataURL('image/png').split(',')[1],frames,source_size:[image.width,image.height],scale};
    }, {url:'data:image/png;base64,'+source.toString('base64'),size:manifest.cell,reference:style==='default'?null:reports[job]});
    await fs.writeFile(path.join(output, `${stem}.png`),Buffer.from(result.png,'base64'));
    reports[stem]={...result,png:undefined};
    preset.hairstyles[style]={name:hairName,sheet:`${stem}.png`};
    }
  }
  await fs.writeFile(path.join(output,'atlas.json'),JSON.stringify(manifest,null,2)+'\n');
  await fs.writeFile(path.join(here,'build-report.json'),JSON.stringify(reports,null,2)+'\n');
  console.log(`SD 도트 외형 ${Object.keys(manifest.presets).length}종, 헤어 포함 ${Object.keys(reports).length}종 × 20 = ${Object.keys(reports).length*20}프레임 생성:`,output);
} finally {await browser.close();}

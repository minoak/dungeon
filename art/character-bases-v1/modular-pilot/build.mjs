// Pack generated transparent components; do not redraw the source artwork.
import fs from 'node:fs/promises';
import { chromium } from '../../../game/node_modules/playwright-core/index.mjs';
const here=new URL('./',import.meta.url);
const manifest={version:1,cell:96,columns:5,directions:['front','right','back','left'],frameMs:160,footY:91,
  bodies:{},heads:{}};
const sources={
  'warrior-body':{kind:'body',name:'전사 · 남성형'},
  'archer-body':{kind:'body',name:'궁수 · 여성형'},
  'short-head':{kind:'head',name:'레이어드 숏컷',scale:42/465,anchors:[[277,594],[776,594],[1271,594],[1747,594]]},
  'long-head':{kind:'head',name:'일자 앞머리 장발',scale:42/430,anchors:[[280,509],[844,509],[1350,509],[1860,509]]},
};
await fs.mkdir(new URL('runtime/',here),{recursive:true});
const browser=await chromium.launch({channel:'msedge',headless:true});
try {
  const page=await browser.newPage();
  for(const [id,spec] of Object.entries(sources)) {
    const bytes=await fs.readFile(new URL('source/'+id+'.png',here));
    const result=await page.evaluate(async ({url,spec})=>{
      const im=new Image();im.src=url;await im.decode();
      const src=document.createElement('canvas');src.width=im.width;src.height=im.height;
      const g=src.getContext('2d',{willReadFrequently:true});g.drawImage(im,0,0);
      const pixels=g.getImageData(0,0,src.width,src.height),d=pixels.data;
      // Generated alpha contains soft fringe: the game uses a binary pixel edge.
      for(let i=3;i<d.length;i+=4)d[i]=d[i]>128?255:0;
      g.putImageData(pixels,0,0);
      const bands=values=>{const out=[];for(let i=0;i<values.length;i++)if(values[i]){
        const start=i;while(i+1<values.length&&values[i+1])i++;out.push([start,i+1]);}return out;};
      const rowCounts=Array(src.height).fill(0);
      for(let y=0;y<src.height;y++)for(let x=0;x<src.width;x++)if(d[(y*src.width+x)*4+3])rowCounts[y]++;
      const rows=bands(rowCounts);
      const expectedRows=spec.kind==='body'?4:1,expectedCols=spec.kind==='body'?5:4;
      if(rows.length!==expectedRows)throw Error('Source row count '+rows.length);
      const frames=[];
      for(let row=0;row<rows.length;row++) {
        const [top,bottom]=rows[row],counts=Array(src.width).fill(0);
        for(let y=top;y<bottom;y++)for(let x=0;x<src.width;x++)if(d[(y*src.width+x)*4+3])counts[x]++;
        const cols=bands(counts);
        if(cols.length!==expectedCols)throw Error('Source column count '+cols.length);
        for(let col=0;col<cols.length;col++) {
          let [x0,x1]=cols[col],y0=bottom,y1=top;
          for(let y=top;y<bottom;y++)for(let x=x0;x<x1;x++)if(d[(y*src.width+x)*4+3]){y0=Math.min(y0,y);y1=Math.max(y1,y+1);}
          let neckX=0,neckN=0;
          for(let y=y0;y<y0+8;y++)for(let x=x0;x<x1;x++)if(d[(y*src.width+x)*4+3]){neckX+=x;neckN++;}
          frames.push({row,col,bounds:[x0,y0,x1,y1],anchor:spec.kind==='body'?[neckX/neckN,y0]:spec.anchors[col]});
        }
      }
      const scale=spec.scale||45/Math.max(...frames.map(f=>f.bounds[3]-f.bounds[1]));
      const out=document.createElement('canvas');out.width=96*(spec.kind==='body'?5:1);out.height=96*4;
      const a=out.getContext('2d');a.imageSmoothingEnabled=false;
      for(const f of frames) {
        const [x0,y0,x1,y1]=f.bounds,[ax,ay]=f.anchor;
        const w=Math.round((x1-x0)*scale),h=Math.round((y1-y0)*scale);
        const dx=Math.round(48-(ax-x0)*scale);
        const dy=spec.kind==='body'?92-h:Math.round(48-(ay-y0)*scale);
        if(dx<2||dx+w>94||dy<2||dy+h>94)throw Error('Clipped output '+JSON.stringify({f,dx,dy,w,h}));
        const row=spec.kind==='body'?f.row:f.col,col=spec.kind==='body'?f.col:0;
        a.drawImage(src,x0,y0,x1-x0,y1-y0,col*96+dx,row*96+dy,w,h);
        f.runtime=[dx,dy,w,h];f.neck=[48,spec.kind==='body'?dy+2:48];
      }
      return {png:out.toDataURL('image/png').split(',')[1],frames,scale,sourceSize:[im.width,im.height]};
    },{url:'data:image/png;base64,'+bytes.toString('base64'),spec});
    await fs.writeFile(new URL('runtime/'+id+'.png',here),Buffer.from(result.png,'base64'));
    const entry={name:spec.name,sheet:'runtime/'+id+'.png',frames:result.frames,scale:result.scale,sourceSize:result.sourceSize};
    if(spec.kind==='body')manifest.bodies[id]=entry;
    else manifest.heads[id]={...entry,anchor:[48,48],long:id==='long-head'};
  }
  await fs.writeFile(new URL('manifest.json',here),JSON.stringify(manifest,null,2)+'\n');
  console.log('Packed 2 bodies x 20 frames and 2 heads x 4 directions.');
}finally{await browser.close();}

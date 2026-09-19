// Pack modular illustration art with smooth alpha and high-resolution cells.
import fs from 'node:fs/promises';
import {chromium} from '../../game/node_modules/playwright-core/index.mjs';
const here=new URL('./',import.meta.url);
const browser=await chromium.launch({channel:'msedge',headless:true});
try{
 const page=await browser.newPage();
 const inputs={};
 for(const type of ['body','head'])inputs[type]='data:image/png;base64,'+(await fs.readFile(new URL('source/warrior-'+type+'.png',here))).toString('base64');
 const result=await page.evaluate(async inputs=>{
   const CELL=256,FOOT=243,parts={};
   for(const [type,url]of Object.entries(inputs)){
     const im=new Image();im.src=url;await im.decode();
     const source=document.createElement('canvas');source.width=im.width;source.height=im.height;
     const g=source.getContext('2d',{willReadFrequently:true});g.drawImage(im,0,0);
     const pixels=g.getImageData(0,0,im.width,im.height),d=pixels.data,W=im.width,H=im.height;
     // Identify disconnected alpha islands. Keep the main painted silhouettes,
     // plus their original soft edge; discard detached generation residue.
     const labels=new Int32Array(W*H),queue=new Int32Array(W*H),components=[];
     let label=0;
     for(let p=0;p<W*H;p++)if(!labels[p]&&d[p*4+3]>128){
       label++;let read=0,write=1;queue[0]=p;labels[p]=label;
       let x0=W,y0=H,x1=0,y1=0;
       while(read<write){const cur=queue[read++],x=cur%W,y=Math.floor(cur/W);x0=Math.min(x0,x);x1=Math.max(x1,x+1);y0=Math.min(y0,y);y1=Math.max(y1,y+1);
         for(let dy=-1;dy<=1;dy++)for(let dx=-1;dx<=1;dx++){const nx=x+dx,ny=y+dy,n=ny*W+nx;
           if(nx>=0&&nx<W&&ny>=0&&ny<H&&!labels[n]&&d[n*4+3]>128){labels[n]=label;queue[write++]=n;}}
       }
       components.push({label,area:write,bounds:[x0,y0,x1,y1]});
     }
     const count=type==='body'?20:4;
     const selected=components.sort((a,b)=>b.area-a.area).slice(0,count);
     if(selected.length!==count||selected.some(c=>c.area<3000))throw Error('Incomplete source components');
     const keep=new Set(selected.map(c=>c.label));
     const clean=new Uint8Array(W*H);
     for(let p=0;p<W*H;p++)if(keep.has(labels[p])){
       const x=p%W,y=Math.floor(p/W);
       for(let dy=-2;dy<=2;dy++)for(let dx=-2;dx<=2;dx++)if(x+dx>=0&&x+dx<W&&y+dy>=0&&y+dy<H)clean[(y+dy)*W+x+dx]=1;
     }
     for(let p=0;p<W*H;p++)if(!clean[p])d[p*4+3]=0;
     g.putImageData(pixels,0,0);
     let ordered;
     if(type==='body'){
       selected.sort((a,b)=>(a.bounds[1]+a.bounds[3])-(b.bounds[1]+b.bounds[3]));ordered=[];
       for(let r=0;r<4;r++)ordered.push(...selected.slice(r*5,r*5+5).sort((a,b)=>a.bounds[0]-b.bounds[0]));
     }else ordered=selected.sort((a,b)=>a.bounds[0]-b.bounds[0]);
     const scale=type==='body'?124/Math.max(...ordered.map(c=>c.bounds[3]-c.bounds[1])):112/490;
     const anchors=type==='head'?[[277,609],[827,609],[1352,609],[1905,609]]:null;
     const out=document.createElement('canvas');out.width=CELL*(type==='body'?5:1);out.height=CELL*4;const o=out.getContext('2d');o.imageSmoothingEnabled=true;o.imageSmoothingQuality='high';
     const frames=[];
     for(let i=0;i<ordered.length;i++){
       const c=ordered[i];let [x0,y0,x1,y1]=c.bounds;
       let ax=anchors?.[i][0],ay=anchors?.[i][1];
       if(type==='body'){
         let sum=0,n=0;for(let y=y0;y<y0+8;y++)for(let x=x0;x<x1;x++)if(labels[y*W+x]===c.label){sum+=x;n++;}
         ax=sum/n;ay=y0;
       }
       x0=Math.max(0,x0-2);y0=Math.max(0,y0-2);x1=Math.min(W,x1+2);y1=Math.min(H,y1+2);
       const w=(x1-x0)*scale,h=(y1-y0)*scale,dx=CELL/2-(ax-x0)*scale;
       const dy=type==='body'?FOOT+1-h:128-(ay-y0)*scale;
       const row=type==='body'?Math.floor(i/5):i,col=type==='body'?i%5:0;
       if(dx<2||dx+w>CELL-2||dy<2||dy+h>CELL-2)throw Error('Clipped packed component '+JSON.stringify({type,i,dx,dy,w,h}));
       o.drawImage(source,x0,y0,x1-x0,y1-y0,col*CELL+dx,row*CELL+dy,w,h);
       frames.push({row,col,source:[x0,y0,x1,y1],anchor:[ax,ay],neck:[128,dy+(ay-y0)*scale+3],runtime:[dx,dy,w,h]});
     }
     parts[type]={canvas:out,frames,scale,sourceSize:[W,H]};
   }
   const sheet=document.createElement('canvas');sheet.width=CELL*5;sheet.height=CELL*4;
   const g=sheet.getContext('2d');g.imageSmoothingEnabled=true;g.imageSmoothingQuality='high';
   for(const f of parts.body.frames){const {row,col}=f;
     g.save();g.translate(col*CELL,row*CELL);g.beginPath();g.rect(0,0,CELL,CELL);g.clip();
     g.drawImage(parts.body.canvas,col*CELL,row*CELL,CELL,CELL,0,0,CELL,CELL);
     g.drawImage(parts.head.canvas,0,row*CELL,CELL,CELL,f.neck[0]-128,f.neck[1]-128,CELL,CELL);g.restore();
   }
   const report={cell:CELL,footY:FOOT,body:{...parts.body,canvas:undefined},head:{...parts.head,canvas:undefined}};
   return {sheet:sheet.toDataURL('image/png').split(',')[1],body:parts.body.canvas.toDataURL('image/png').split(',')[1],head:parts.head.canvas.toDataURL('image/png').split(',')[1],report};
 },inputs);
 await fs.mkdir(new URL('runtime/',here),{recursive:true});
 for(const name of ['sheet','body','head'])await fs.writeFile(new URL('runtime/warrior-'+name+'.png',here),Buffer.from(result[name],'base64'));
 await fs.writeFile(new URL('build-report.json',here),JSON.stringify(result.report,null,2)+'\n');
 await fs.copyFile(new URL('runtime/warrior-sheet.png',here),new URL('../../viewer/assets/sprites/sd/warrior-illustration.png',here));
 console.log(JSON.stringify({cell:256,frames:20,sourceSizes:[result.report.body.sourceSize,result.report.head.sourceSize]}));
}finally{await browser.close();}

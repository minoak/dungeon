/** Pure frame composition. Body choice never depends on hair choice. */
export function drawCharacter(ctx,assets,bodyId,headId,direction,column,{layer='all'}={}) {
  const {manifest,images}=assets;
  const row=manifest.directions.indexOf(direction);
  const body=manifest.bodies[bodyId],head=manifest.heads[headId],size=manifest.cell;
  if(!body||!head||row<0||!Number.isInteger(column)||column<0||column>=manifest.columns)
    throw new Error('Unknown component or frame');
  const bodyImage=images[body.sheet],headImage=images[head.sheet];
  const neck=body.frames[row*manifest.columns+column].neck;
  const hx=neck[0]-head.anchor[0],hy=neck[1]-head.anchor[1];
  ctx.imageSmoothingEnabled=false;
  const drawHead=()=>ctx.drawImage(headImage,0,row*size,size,size,hx,hy,size,size);
  const drawBody=()=>ctx.drawImage(bodyImage,column*size,row*size,size,size,0,0,size,size);
  if(layer==='body'){drawBody();return;}
  if(layer==='head'){drawHead();return;}
  // Front/profile long tails behind shoulders. Back-facing hair covers the cape.
  if(head.long&&direction!=='back')drawHead();
  drawBody();
  ctx.save();
  if(head.long&&direction!=='back'){
    ctx.beginPath();ctx.rect(0,0,size,neck[1]);ctx.clip();
  }
  drawHead();ctx.restore();
}

export async function loadAssets(base=new URL('./',import.meta.url)) {
  const response=await fetch(new URL('manifest.json',base));
  if(!response.ok)throw new Error('Component manifest unavailable');
  const manifest=await response.json(),images={};
  await Promise.all([...Object.values(manifest.bodies),...Object.values(manifest.heads)].map(async entry=>{
    const im=new Image();im.src=new URL(entry.sheet,base);await im.decode();images[entry.sheet]=im;
  }));
  return {manifest,images};
}

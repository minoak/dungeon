/** Pure frame composition. Body choice never depends on hair choice. */
export function drawCharacter(ctx,assets,bodyId,headId,direction,column,{layer='all'}={}) {
  const {manifest,images}=assets;
  const row=manifest.directions.indexOf(direction);
  const body=manifest.bodies[bodyId],head=manifest.heads[headId],size=manifest.cell;
  if(!body||!head||row<0||!Number.isInteger(column)||column<0||column>=manifest.columns)
    throw new Error('Unknown component or frame');
  const bodyImage=images[body.sheet],headImage=images[head.sheet];
  const neck=body.frames[row*manifest.columns+column].neck;
  // Sink the attachment into the collar; a one-pixel passing-step dip keeps
  // heads from floating motionless above walking bodies. Legacy pilots opt out.
  const placement=manifest.headPlacement;
  const inset=placement?.neckInset??0,bob=placement?.walkBob?.[column]??0;
  // Generated body heights can move opposite to the bob and cancel it out.
  // Use the idle attachment as the head's stable baseline within each direction.
  const baseline=placement?body.frames[row*manifest.columns].neck:neck;
  const chin=head.chinY?.[row];
  const collar=baseline[1]+(placement?.collarOffset??inset);
  const hx=baseline[0]-head.anchor[0];
  // Neckless SD silhouette: the chin touches the collar, and the head's neck
  // stub is covered by clothing instead of being painted over the chest.
  const hy=chin==null?baseline[1]-head.anchor[1]+inset+bob:collar-chin+bob;
  ctx.imageSmoothingEnabled=false;
  const drawHead=()=>ctx.drawImage(headImage,0,row*size,size,size,hx,hy,size,size);
  const drawBody=()=>ctx.drawImage(bodyImage,column*size,row*size,size,size,0,0,size,size);
  if(layer==='body'){drawBody();return;}
  if(layer==='head'){drawHead();return;}
  // Front/profile long tails behind shoulders. Back-facing hair covers the cape.
  if(head.long&&direction!=='back')drawHead();
  drawBody();
  ctx.save();
  if(chin!=null&&!(head.long&&direction==='back')){
    ctx.beginPath();ctx.rect(0,0,size,Math.min(collar,neck[1]+(placement?.collarOffset??inset))+1);ctx.clip();
  }else if(head.long&&direction!=='back'){
    ctx.beginPath();ctx.rect(0,0,size,neck[1]+inset);ctx.clip();
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

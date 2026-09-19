import fs from 'node:fs/promises';
const here=new URL('./',import.meta.url),catalog=JSON.parse(await fs.readFile(new URL('catalog.json',here),'utf8'));
const records=(await fs.readFile(new URL('../town-v4/preview-run.jsonl',here),'utf8')).trim().split('\n').map(JSON.parse);
const bodies=Object.entries(catalog.bodies);
for(const record of records){
 const field=record.party?'party':record.bots?'bots':null;if(!field)continue;
 const original=record[field][0];
 record[field]=bodies.map(([id,b],i)=>{
  const member=structuredClone(original);member.char=String(i+1);member.name=b.name;member.job=b.job;member.sex=b.sex;
  if(record.kind==='run_meta')member.look={sprite:'sd-'+id,hairstyle:b.defaultHair};
  else{member.x=39+(i%4)*3;member.y=34+Math.floor(i/4)*3;}
  return member;
 });
}
await fs.writeFile(new URL('preview-run.jsonl',here),records.map(JSON.stringify).join('\n')+'\n');

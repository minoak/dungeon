import fs from 'node:fs/promises';
const records=(await fs.readFile(new URL('../town-v4/preview-run.jsonl',import.meta.url),'utf8')).trim().split('\n').map(JSON.parse);
for(const record of records){
 for(const member of record.party||record.bots||[]){
  if(member.char==='1'){member.name='일러스트 SD';member.job='전사';member.sex='남';if(record.kind==='run_meta')member.look={sprite:'sd-warrior-illustration',hairstyle:'default'};}
  if(member.char==='2'){member.name='기존 도트';member.job='전사';member.sex='남';if(record.kind==='run_meta')member.look={sprite:'sd-warrior',hairstyle:'default'};}
 }
}
await fs.writeFile(new URL('./preview-run.jsonl',import.meta.url),records.map(JSON.stringify).join('\n')+'\n');

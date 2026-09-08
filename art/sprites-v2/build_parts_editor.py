"""기존 픽셀 편집기에 전체 조합 선택과 묶음 저장 기능을 연결한다."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
data=json.loads((ROOT/'production/sprites.json').read_text(encoding='utf-8'))
html=(ROOT/'pixel-editor.html').read_text(encoding='utf-8')
approved=json.loads((ROOT/'approved-warrior-front.json').read_text(encoding='utf-8'))
html=html.replace('16픽셀 작업실','캐릭터 파츠 작업실')
html=html.replace('<h2>전사 · 정면</h2>','<h2>조합과 프레임 선택</h2><div class="toolbar"><label>머리 <select id="headPick"></select></label><label>직업 <select id="jobPick"></select></label><label>방향 <select id="dirPick"></select></label><label>동작 <select id="phasePick"><option value="-1">정지</option><option value="0">걷기 1</option><option value="1">걷기 2</option><option value="2">걷기 3</option><option value="3">걷기 4</option></select></label></div>')
start=html.index('const ORIGINAL=')
end=html.index('\nconst NAMES=',start)
html=html[:start]+'const ORIGINAL='+json.dumps(approved['rows'])+';\nconst PAL='+json.dumps(data['palette'])+';'+html[end:]
html=html.replace("'검날'];","'검날','상의 초록','상의 초록 그림자','상의 보라','상의 보라 그림자'];")
html=html.replace(",KEY='wonderland-pixel-workshop-v1';",";\nlet KEY='wonderland-parts-M1-warrior-front--1';")
html=html.replace("pixels=clone(ORIGINAL);commit(before)","pixels=clone(currentOriginal);commit(before)")
html=html.replace("download(b,'warrior-16-edited.png')","download(b,currentId()+'.png')")
html=html.replace("'warrior-16-work.json'","currentId()+'-work.json'")
html=html.replace('정면 기준형을 다듬는 독립 편집기입니다.','12종 머리 × 3종 직업 × 4방향 × 정지·걷기 4프레임의 초안입니다. 각 프레임 수정은 독립적으로 보관됩니다.')
html=html.replace('<h2>저장과 이어서 작업</h2>','<h2>선택 프레임 저장</h2>')
html=html.replace('<div id="status"','<div class="toolbar"><button id="sheet">현재 조합 시트 저장</button><button id="allSave">전체 수정 묶음 저장</button><label class="file">수정 묶음 열기<input id="allOpen" type="file" accept=".json"></label></div><p class="note">시트: 행은 정면·왼쪽·뒤·오른쪽, 열은 정지·걷기 1~4입니다. 머리를 고쳐도 다른 프레임에 자동 복제되지는 않습니다.</p><div id="status"')
extra=r"""
const PACK=__PACK__;
let currentOriginal=clone(ORIGINAL);
const selects=['headPick','jobPick','dirPick','phasePick'];
function option(id,value,label){const o=document.createElement('option');o.value=value;o.textContent=label;$('#'+id).append(o)}
Object.entries(PACK.heads).forEach(([id,h])=>option('headPick',id,id+' · '+h.name));
Object.entries(PACK.bodies).forEach(([id,b])=>option('jobPick',id,b.name));
PACK.directions.forEach((d,i)=>option('dirPick',d,['정면','왼쪽','뒤','오른쪽'][i]));
function currentId(){return selects.map(id=>$('#'+id).value).join('-')}
function original(h,j,d,p){const head=PACK.heads[h].frames[d],body=p<0?PACK.bodies[j].frames[d]:PACK.bodies[j].walk[d][p];return body.map((r,y)=>r.map((v,x)=>head.front[y][x]!=='.'?head.front[y][x]:v!=='.'?v:head.rear[y][x]))}
function readDraft(id){try{const d=JSON.parse(localStorage.getItem('wonderland-parts-'+id));return d&&valid(d.rows)&&valid(d.reference)?d:null}catch{return null}}
function selectFrame(){finish();const [h,j,d,p]=selects.map(id=>$('#'+id).value);KEY='wonderland-parts-'+currentId();currentOriginal=original(h,j,d,Number(p));const draft=readDraft(currentId());pixels=clone(draft?draft.rows:currentOriginal);reference=clone(draft?draft.reference:currentOriginal);past=[];future=[];render();message(draft?'이 프레임의 임시 작업을 복원했어요.':'기본 초안을 불러왔어요.')}
selects.forEach(id=>$('#'+id).onchange=selectFrame);
$('#sheet').onclick=()=>{finish();const h=$('#headPick').value,j=$('#jobPick').value,c=document.createElement('canvas');c.width=80;c.height=64;const g=c.getContext('2d');PACK.directions.forEach((d,y)=>[-1,0,1,2,3].forEach((p,x)=>{const id=[h,j,d,p].join('-'),draft=readDraft(id);g.drawImage(native(id===currentId()?pixels:draft?draft.rows:original(h,j,d,p)),x*16,y*16)}));c.toBlob(b=>download(b,h+'-'+j+'-sheet.png'))};
function ids(){return Object.keys(PACK.heads).flatMap(h=>Object.keys(PACK.bodies).flatMap(j=>PACK.directions.flatMap(d=>[-1,0,1,2,3].map(p=>[h,j,d,p].join('-')))))}
$('#allSave').onclick=()=>{finish();const edits={};ids().forEach(id=>{const d=readDraft(id);if(d)edits[id]=d});edits[currentId()]=pack();download(new Blob([JSON.stringify({version:1,kind:'wonderland-parts-edits',edits},null,2)],{type:'application/json'}),'wonderland-parts-edits.json')};
$('#allOpen').onchange=async e=>{const f=e.target.files[0];if(!f)return;try{if(f.size>5000000)throw Error();const all=JSON.parse(await f.text()),allowed=new Set(ids());if(all.version!==1||all.kind!=='wonderland-parts-edits'||!all.edits||typeof all.edits!=='object'||Array.isArray(all.edits))throw Error();const entries=Object.entries(all.edits);for(const [id,d] of entries){if(!allowed.has(id)||d.version!==1||d.size!==16||!valid(d.rows)||!valid(d.reference)||JSON.stringify(d.palette)!==JSON.stringify(PAL))throw Error()}finish();const backup=entries.map(([id])=>[id,localStorage.getItem('wonderland-parts-'+id)]);try{entries.forEach(([id,d])=>localStorage.setItem('wonderland-parts-'+id,JSON.stringify(d)))}catch(err){backup.forEach(([id,v])=>v===null?localStorage.removeItem('wonderland-parts-'+id):localStorage.setItem('wonderland-parts-'+id,v));throw err}selectFrame();message(entries.length+'개 프레임의 수정 내용을 불러왔어요.')}catch{message('수정 묶음을 불러오지 못했어요. 파일 형식이나 브라우저 저장 공간을 확인해 주세요.')}finally{e.target.value=''}};
selectFrame();
"""
html=html.replace('render();\n</script>',extra.replace('__PACK__',json.dumps(data,ensure_ascii=False))+'\nrender();\n</script>')
(ROOT/'parts-editor.html').write_text(html,encoding='utf-8')
print('Built parts-editor.html with 720 selectable frames')

gallery="""<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>원더랜드 캐릭터 전체 검토</title>
<style>body{margin:0;background:#20242c;color:#eee0cb;font:16px/1.6 system-ui}main{max-width:980px;margin:auto;padding:28px}h1{font-size:26px}button,select,a{font:inherit;color:inherit;background:#343d4c;padding:7px 12px;border-radius:6px;border:1px solid #657186}label{margin-right:12px}.row{display:flex;gap:16px;flex-wrap:wrap;margin:24px 0}.card{background:#292f39;border-radius:10px;padding:18px;flex:1;text-align:center}canvas{image-rendering:pixelated}p{color:#b5becc}.thumbs{display:flex;flex-wrap:wrap;gap:12px}.thumbs button{cursor:pointer}a{display:inline-block}input{vertical-align:middle}</style>
<main><h1>캐릭터 전체 검토 · 16×16</h1><p>승인한 전사 정면에서 확장한 초안입니다. 눈과 발 위치는 검사했으며, 머리 실루엣과 걷는 인상은 이 화면에서 검토할 수 있습니다.</p>
<label>머리 <select id="head"></select></label><label>직업 <select id="job"></select></label><label><input type="checkbox" id="walk" checked> 걷기</label><button id="pause">일시정지</button><label>프레임 <input type="range" id="phase" min="0" max="3" value="0"></label>
<div class="row" id="views"></div><p>위: 128px 확대 / 아래: 48px 표시. 걷기는 발을 번갈아 드는 4프레임이며 머리·팔·기본 무기는 고정입니다.</p><div class="thumbs" id="heads"></div><p><a href="../parts-editor.html">선택해서 픽셀 다듬기</a></p><p>편집기의 임시 수정은 이 기본 초안 검토 화면에 자동 반영되지 않습니다.</p></main><script>
const D=__DATA__,q=s=>document.querySelector(s);let tick=0,playing=true;
for(const [id,h] of Object.entries(D.heads)){const o=new Option(id+' · '+h.name,id);q('#head').add(o);const b=document.createElement('button');b.textContent=id;b.onclick=()=>{q('#head').value=id;render()};q('#heads').append(b)}
for(const [id,b] of Object.entries(D.bodies))q('#job').add(new Option(b.name,id));
D.directions.forEach((d,i)=>{const c=document.createElement('div');c.className='card';c.innerHTML='<div>'+['정면','왼쪽','뒤','오른쪽'][i]+'</div><canvas width="128" height="128"></canvas><div><canvas width="48" height="48"></canvas></div>';q('#views').append(c)});
function render(){const h=D.heads[q('#head').value],b=D.bodies[q('#job').value],phase=Number(q('#phase').value);D.directions.forEach((d,i)=>{const a=h.frames[d],body=q('#walk').checked?b.walk[d][phase]:b.frames[d],c=document.createElement('canvas');c.width=c.height=16;const g=c.getContext('2d');body.forEach((r,y)=>r.forEach((v,x)=>{const id=a.front[y][x]!=='.'?a.front[y][x]:v!=='.'?v:a.rear[y][x];if(id!=='.'){g.fillStyle=D.palette[id];g.fillRect(x,y,1,1)}}));q('#views').children[i].querySelectorAll('canvas').forEach(out=>{const ctx=out.getContext('2d');ctx.clearRect(0,0,out.width,out.height);ctx.imageSmoothingEnabled=false;ctx.drawImage(c,0,0,out.width,out.height)})})}
q('#pause').onclick=()=>{playing=!playing;q('#pause').textContent=playing?'일시정지':'재생'};q('#phase').oninput=()=>{playing=false;q('#pause').textContent='재생';render()};q('#head').onchange=q('#job').onchange=q('#walk').onchange=render;setInterval(()=>{if(playing&&q('#walk').checked){q('#phase').value=(Number(q('#phase').value)+1)%4;render()}},160);render();
</script></html>"""
(ROOT/'production/index.html').write_text(gallery.replace('__DATA__',json.dumps(data,ensure_ascii=False)),encoding='utf-8')

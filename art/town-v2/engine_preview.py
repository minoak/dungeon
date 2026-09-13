"""게임 클라이언트 표시 검사에 쓸 엔진 스냅샷. 실제 AI 플레이 기록은 아니다."""
import json
import os
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT))
os.environ['DUNGEON_BRAIN_BACKEND']='dummy'
os.environ['DUNGEON_BESTIARY_FILE']=''
import dungeon_gm as G
import show_runner
d, starts=show_runner.build_town()
bots=[]
for char,name,job,sprite in [('1','지도 검토 1','전사','sd-warrior'),('2','지도 검토 2','도적','sd-rogue'),('3','지도 검토 3','궁수','sd-archer')]:
    sheet={'name':name,'job':job,'sex':'여','persona':'','look':{'sprite':sprite},'hp':14,'str':3,'dex':1,'wdmg':4,'stealth':0,'search_r':1}
    b=G.spawn(d,char,bots,sheet=sheet)
    b['x'],b['y']=starts[char]
    bots.append(b)
party=[{**G.bot_snapshot(b),'name':b['name'],'look':b['look']} for b in bots]
rows=[{'kind':'run_meta','v':1,'seed':7,'town':True,'backend':'dummy','preview':True,'party':party},
      {'kind':'level','turn':0,**d.level_snapshot(),'party':party}]
rows.append({'kind':'tick','turn':1,'decisions':{},'events':[],'bots':party,'features':d.level_snapshot()['features'],'monsters':[],'traps':[]})
(HERE/'preview-run.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
print('엔진에서 지도 검토용 스냅샷 생성(LLM 0콜)')

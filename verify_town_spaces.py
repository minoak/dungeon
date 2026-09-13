"""공간 정의→엔진 격자 계약과 실패 조건. LLM 0콜."""
import json
from copy import deepcopy
from pathlib import Path
import entities
import town_layout
import town_spaces
import dungeon_gm as G

ROOT = Path(__file__).resolve().parent
layout = json.loads((ROOT/'art/town-v2/layout.json').read_text(encoding='utf-8'))
c = town_layout.compile_layout(layout)
assert len(c['spaces']['regions']) == 6 and len(c['spaces']['buildings']) == 4
assert len(c['spaces']['connections']) == 6
assert c['dungeon_entry'] == [41,30]
d, starts = G.Dungeon.from_layout(layout)
for char, start in starts.items():
    for target in [tuple(c['dungeon_entry']), *((n['x'],n['y']) for n in c['npcs']), *(tuple(e['cell']) for e in c['entrances'])]:
        assert d.path_to(*start,*target,[]), (char,target)
# 건물 크기가 바뀌면 충돌과 그림 너비도 함께 바뀐다.
defs = deepcopy(entities.load())
defs['temple']['comps']['building']['size'] = [11,7]
resolved = town_spaces.resolve(layout,defs)
temple = resolved['resolved_spaces']['buildings'][0]
assert temple['width'] == 11*48
assert next(b for b in resolved['blocked_rects'] if b['id']=='temple_1:footprint')['rect'][2] == 11

def rejects(modify):
    bad = deepcopy(layout)
    modify(bad)
    try: town_layout.compile_layout(bad)
    except ValueError: return
    raise AssertionError('잘못된 배치를 허용함')

rejects(lambda l:l['buildings'][0].update(entity='missing'))
rejects(lambda l:l['buildings'][0].update(cell=[48,0]))
rejects(lambda l:l['regions'][0]['rects'].append([25,0,1,1]))
rejects(lambda l:l['regions'].pop())
rejects(lambda l:l['connections'][0].update(cells=[[9,14],[12,15]]))
rejects(lambda l:l['connections'].pop(0))
rejects(lambda l:l['blocked_rects'].append({'id':'blocked-link','rect':[9,14,1,1]}))
# 예전 단일 길드 layout도 계속 읽는다.
old = json.loads((ROOT/'art/town-v1/layout.json').read_text(encoding='utf-8'))
assert town_layout.compile_layout(old)['size'] == [27,20]
print('ALL PASS — 공간 정의·경계·연결·건물 점유·전체 경로·v1 호환')

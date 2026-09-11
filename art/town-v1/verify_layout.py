"""배치 검증: 원본 불변, 잘못된 배치 거절, 엔진 격자·경로와의 일치. LLM 0콜."""
import copy
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
os.environ['DUNGEON_BRAIN_BACKEND'] = 'dummy'
from town_layout import compile_layout
import dungeon_gm as G

layout = json.loads((HERE/'layout.json').read_text(encoding='utf-8'))
before = copy.deepcopy(layout)
result = compile_layout(layout)
assert layout == before, '변환은 원본을 변경하면 안 된다'
assert result == compile_layout(layout), '같은 입력은 같은 격자'
assert result['map'] == json.loads((HERE/'town-candidate.json').read_text(encoding='utf-8'))['map']
assert '\n'.join(result['map'])+'\n' == (HERE/'town-ascii.txt').read_text(encoding='utf-8')

def reject(label, change):
    bad = copy.deepcopy(layout)
    change(bad)
    try:
        compile_layout(bad)
    except ValueError:
        return label
    raise AssertionError('잘못된 배치를 허용함: ' + label)

checks = [
    reject('벽 위 출발점', lambda d: d['starts'].update({'1':[7,6]})),
    reject('중복 NPC 자리', lambda d: d['npcs'][1].update(cell=d['npcs'][0]['cell'])),
    reject('맵 밖 사각형', lambda d: d['blocked_rects'].append({'id':'bad','rect':[24,17,2,1]})),
    reject('길드 문턱 없는 진짜 문', lambda d: d['entrances'][0].update(kind='door')),
    reject('샛길 입구 격리', lambda d: d['blocked_rects'].extend([
        {'id':'seal_above','rect':[22,16,1,1]},
        {'id':'seal_left','rect':[21,17,1,1]},
        {'id':'seal_right','rect':[23,17,1,1]}])),
]
engine, starts = G.Dungeon.from_ascii(result['map'], seed=1, depth=0)
assert {k:list(v) for k,v in starts.items()} == result['starts']
assert list(engine.exit) == result['dungeon_entry']
for y, row in enumerate(result['map']):
    for x, symbol in enumerate(row):
        assert (engine.grid[y][x] == G.WALL) == (symbol == '#'), (x,y,symbol)
targets = [result['dungeon_entry']] + [[n['x'],n['y']] for n in result['npcs']] + [e['cell'] for e in result['entrances']]
for char,(sx,sy) in starts.items():
    for tx,ty in targets:
        assert engine.path_to(sx,sy,tx,ty,[]), (char,tx,ty)
checks += ['원본 불변·결정론', '생성 파일과 일치', '엔진 벽·출발·입구 좌표 일치', '모든 출발점에서 목적지 경로']
known = {p.stem for p in (HERE.parent.parent/'entities/npc').glob('*.json')}
missing = [n['id'] for n in result['npcs'] if n['id'] not in known]
report = {'geometry_passed':True, 'checks':checks, 'missing_npc_definitions':missing,
          'live_town_changed':False, 'from_layout_integrated':False, 'llm_calls':0}
(HERE/'layout-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('PASS: 배치·거절 사례·엔진 격자·모든 출발점의 경로')
print('미등록 NPC: '+', '.join(missing))

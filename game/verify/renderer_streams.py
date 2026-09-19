"""verify/renderer.mjs 의 자료 — 실제 엔진 생성기로 지은 층의 정지 스냅샷 셋(두뇌 미사용 · LLM 0콜 · 판을 돌리지 않는다).
사용: python game/verify/renderer_streams.py <출력 폴더>      (출력은 ASCII 만)
  renderer_concept.jsonl  새 생성 프로필(level.architecture 있음) + level.props(방 한가운데 하나씩 — kind 여섯 가지 돌려 가며)
                          · t2 에 봇 1번이 정면 문 칸, 몹 0번이 측면 문 칸에 선다
  renderer_original.jsonl 옛 생성기(architecture 없음)
  renderer_town.jsonl     v4 저작 마을(art/town-v4/layout.json → Dungeon.from_layout) + 그림 없는 피처 둘(캐릭터 곁 · 먼 곳) + 그림 있는 피처(potion)
층 자료는 실험실과 같은 길(art/dungeon-v2/preview_server.stream)로 만든다 — 엔진이 level.props 를 내보내기 시작해도 여기서 덮어써 검사 입력을 고정한다.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(HERE, 'out')
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'art', 'dungeon-v2'))
import dungeon_gm as G  # noqa: E402
from preview_server import stream  # noqa: E402


def rows(seed, profile):
    return [json.loads(x) for x in stream(seed, profile).decode('utf-8').splitlines()]


def dump(name, data):
    with open(os.path.join(OUT, name), 'w', encoding='utf-8', newline='\n') as f:
        for r in data:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


os.makedirs(OUT, exist_ok=True)
KINDS = ['barrel', 'crate', 'jar', 'rubble', 'storage', 'ruin']

# -- 새 생성 프로필: 문 칸에 선 봇·몹 + 엔진 소유 소품
meta, level, tick = rows(7, 'concept')
grid = level['grid']
is_open = lambda x, y: grid[y][x] in '.+'
doors = [(x, y) for y, row in enumerate(grid) for x, c in enumerate(row) if c == '+']
front = [d for d in doors if is_open(d[0], d[1] - 1) and is_open(d[0], d[1] + 1)]     # 남북으로 지나는 문(정면 그림)
side = [d for d in doors if is_open(d[0] - 1, d[1]) and is_open(d[0] + 1, d[1])]      # 동서로 지나는 문(측면 그림)
assert front and side and len(doors) >= 3, (len(front), len(side), len(doors))
taken = {(e['x'], e['y']) for k in ('party', 'monsters', 'features', 'traps') for e in level[k]}
centres = [(r['x'] + r['w'] // 2, r['y'] + r['h'] // 2) for r in level['rooms']]
centres = [c for c in centres if grid[c[1]][c[0]] == '.' and c not in taken]
level['props'] = [dict(id='p%d' % i, kind=KINDS[i % len(KINDS)], x=x, y=y, blocks=(i % 2 == 0)) for i, (x, y) in enumerate(centres)]
t2 = json.loads(json.dumps(tick))
t2['turn'] = 2
t2['bots'][0]['x'], t2['bots'][0]['y'] = front[0]
t2['monsters'][0].update(x=side[0][0], y=side[0][1], alive=True, concealed=False)
dump('renderer_concept.jsonl', [meta, level, tick, t2])
original = rows(7, 'original')
original[1].pop('props', None)                      # 옛 길(클라이언트 추첨)을 본다
dump('renderer_original.jsonl', original)

# -- v4 저작 마을: 엔진이 layout 을 격자로 — 러너(show_runner)는 건드리지 않는다
with open(os.path.join(ROOT, 'art', 'town-v4', 'layout.json'), encoding='utf-8') as f:
    d, starts = G.Dungeon.from_layout(json.load(f))
bots = []
spots = [starts[k] for k in sorted(starts)]           # from_ascii 의 starts = {char: (x, y)}
assert len(spots) >= 2, 'layout needs two start cells'
for (char, name, job, sprite), (sx, sy) in zip([('1', 'probe 1', '전사', 'sd-warrior'), ('2', 'probe 2', '도적', 'sd-rogue')], spots):
    b = G.spawn(d, char, bots, sheet=dict(name=name, job=job, sex='여', persona='', look={'sprite': sprite},
                                          hp=14, str=3, dex=1, wdmg=4, stealth=0, search_r=1))
    b['x'], b['y'] = sx, sy
    bots.append(b)
party = [{**G.bot_snapshot(b), 'name': b['name'], 'look': b['look']} for b in bots]
town = d.level_snapshot()
assert town.get('visual', {}).get('art'), 'layout has no authored art'
g = town['grid']
b0 = party[0]
near = next((x, y) for y in range(b0['y'] - 2, b0['y'] + 3) for x in range(b0['x'] - 2, b0['x'] + 3)
            if g[y][x] == '.' and (x, y) != (b0['x'], b0['y']) and not any((p['x'], p['y']) == (x, y) for p in party))
fars = [(x, y) for y in range(len(g)) for x in range(len(g[0])) if g[y][x] == '.'
        and all(max(abs(p['x'] - x), abs(p['y'] - y)) > 6 for p in party)]
far, far2 = fars[len(fars) // 2], fars[len(fars) // 2 + 3]
town['features'] = list(town['features']) + [
    dict(id=901, type='well', name='우물', x=near[0], y=near[1], room_id=None, concealed=False),
    dict(id=902, type='bench', name='긴 의자', x=far[0], y=far[1], room_id=None, concealed=False),
    dict(id=903, type='potion', name='회복 물약', x=far2[0], y=far2[1], room_id=None, concealed=False)]
tmeta = dict(kind='run_meta', v=1, seed=7, started='renderer-probe', w=d.w, h=d.h, depths=1, sight=8, town=True,
             backend='dummy', preview=True, party=party)
dump('renderer_town.jsonl', [tmeta, dict(kind='level', turn=0, **town, party=party),
                             dict(kind='tick', turn=1, decisions={}, events=[], bots=party, features=town['features'],
                                  monsters=town['monsters'], traps=town['traps'])])
assert 'brains' not in sys.modules, 'probe data must not load brain backends'
print('ok doors=%d front=%s side=%s props=%d town=%dx%d near=%s far=%s' % (len(doors), front[0], side[0], len(level['props']), d.w, d.h, near, far))

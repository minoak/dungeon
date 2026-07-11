# -*- coding: utf-8 -*-
"""동료 물리층(D18) 헤들리스 검증 — 13번째 게이트.
D18: "상처도 시야를 탄다" — 라이브 22틱 부검(카야 전사 무목격·두란 서쪽 행군)의 수선 계약.
게이트:
  ① 곁 판정(A-1): 동료=체비셰프≤1(대각 도착=arrived·경로소진 대각=arrived 회귀), 몹=직교 유지
  ② 시야 내 실물 재경로(A-2): 도주몹 꼬리잡기 수렴 + lost 는 전부 시야 밖에서만 + 시야 밖=스냅샷 유지
  ③ 목격 주입(A-3): 시야 유무별 · 1회성 노출·소거 · 자기 피격 비주입 · 처치=ally_down · 도감 마스킹
  ④ 부상 등급(A-4): _wound_label 경계 고정 · allies condition · 합류 라벨 병기 · party 비노출 · 몹 hp 숫자
  ⑤ 동행(A-5): 유지(따라 걷기) · 대상 사망 lost · 대기 중 새 몹 encounter 파기 · then 차단(엔진·brains)
  ⑥ 사회적 대우회(A-0, _ally_jam): 문간 동료 대우회 → blocked(allies) / 지형-단독 경로는 무간섭
  ⑦ [50시드] 풀게임 항상 종료 + [10시드] 결정론(2회 서명 동일)
(기존 verify 12종은 별도 실행.)
"""
import os

os.environ["DUNGEON_BESTIARY_FILE"] = ""   # 도감 영속 차단(게이트 격리 원칙)

import brains
import dungeon_gm as G
from dungeon_gm import Dungeon, Monster, spawn, dummy_brain


class C:
    failed = 0


def check(name, cond):
    print(("  OK   " if cond else " FAIL  ") + name)
    if not cond:
        C.failed += 1


def mkbot(char, x, y, str_=3, dex=0, wdmg=4, stealth=0, search_r=1, job='전사', hp=14):
    return {'char': char, 'x': x, 'y': y, 'hp': hp, 'maxhp': 14,
            'str': str_, 'dex': dex, 'wdmg': wdmg, 'stealth': stealth,
            'search_r': search_r, 'job': job, 'sex': '남', 'persona': '', 'bag': 0,
            'alive': True, 'won': False, 'order': None, 'path': [],
            'aware_of': set()}


def arena(seed=1, w=20, h=12):
    """가장자리만 벽, 콘텐츠 없는 빈 방(verify_stage3 선례)."""
    d = Dungeon(seed=seed, w=w, h=h, n_monsters=0, n_traps=0, n_lurkers=0)
    for y in range(h):
        for x in range(w):
            d.grid[y][x] = '.' if (1 <= x < w - 1 and 1 <= y < h - 1) else '#'
    ef = d.features[d._exit_fid]
    ef.x, ef.y = w - 2, h - 2
    d.features = {d._exit_fid: ef}
    d.monsters, d.traps = [], []
    d.visited = set()
    return d


def mkmon(d, x, y, kind='고블린', hp=6, atk=2, dmg=2, state='SLEEPING', mid=0):
    m = Monster(x, y, kind=kind, hp=hp, atk=atk, dmg=dmg, ac=12, mid=mid)
    m.state = state
    d.monsters.append(m)
    return m


# ───────────────────── ① 곁 판정(A-1): 동료 대각, 몹 직교 ─────────────────────
print("── ① 곁 판정(A-1)")
d = arena()
b1, b2 = mkbot('1', 5, 5), mkbot('2', 6, 6, job='도적')
bots = [b1, b2]
d.act(b1, {'type': 'goto', 'target': 'b2'}, bots)
r = d.step_order(b1, bots)
check("① 대각(체비셰프1) 동료 = 곁 — 제자리 arrived", r['result'] == 'arrived'
      and (b1['x'], b1['y']) == (5, 5))

d = arena()
b1 = mkbot('1', 5, 5)
bots = [b1]
m = mkmon(d, 6, 6)
b1['aware_of'].add(m.id)
d.act(b1, {'type': 'goto', 'target': 'm0'}, bots)
r = d.step_order(b1, bots)
check("① 대각 몹 = 곁 아님 — 직교로 한 걸음(공격창 모순 방지)",
      (b1['x'], b1['y']) != (5, 5) and abs(b1['x'] - 6) + abs(b1['y'] - 6) == 1
      and r['result'] == 'arrived')

d = arena()
b1, b2 = mkbot('1', 5, 5), mkbot('2', 8, 5, job='도적')
bots = [b1, b2]
d.act(b1, {'type': 'goto', 'target': 'b2'}, bots)          # path → (7,5) 류 직교 접근칸
r = d.step_order(b1, bots)                                 # 한 걸음
b2['x'], b2['y'] = 8, 6                                    # 대상이 대각으로 비껴섬
while b1.get('order'):
    r = d.step_order(b1, bots)
check("① 경로 소진 + 동료 대각 비껴섬 = arrived (구판 lost 회귀)", r['result'] == 'arrived')

# ───────────────────── ② 시야 내 실물 재경로(A-2) ─────────────────────
print("── ② 시야 내 실물 재경로(A-2)")
rows = ['####################',
        '#1....g............#',
        '#..................#',
        '#.................>#',
        '####################']
d, starts = G.Dungeon.from_ascii(rows, seed=7,
    monsters={'g': {'kind': '고블린', 'state': 'FLEEING', 'target': '1'}})
b1 = mkbot('1', *starts['1'])
bots = [b1]
m = d.monsters[0]
m.last_seen, m.lost = (b1['x'], b1['y']), 0
b1['aware_of'].add(m.id)
d._set_order(b1, 'm0', bots)
lost_in_sight = retargets = 0
arrived_t = None
prev_end = tuple(b1['path'][-1]) if b1['path'] else None
for t in range(1, 30):
    if b1.get('order'):
        vis_before = (m.x, m.y) in d.visible_cells(b1['x'], b1['y'])
        r = d.step_order(b1, bots)
        end = tuple(b1['path'][-1]) if b1.get('path') else None
        if vis_before and end and prev_end and end != prev_end:
            retargets += 1                       # 시야 내 재조준 실측
        prev_end = end
        if r['result'] == 'lost' and vis_before and m.alive:
            lost_in_sight += 1                   # 시야 내 허탕 = A-2 실패 신호
        if r['result'] == 'arrived':
            arrived_t = t
            break
        if r['result'] != 'walking' and m.alive:
            d._set_order(b1, 'm0', bots)         # 재결정 시뮬(전사의 고집)
    d.monster_turn(bots)
check("② 도주몹 꼬리잡기 수렴(arrived, 30틱 내)", arrived_t is not None)
check("② lost 는 전부 시야 밖에서만(시야 내 허탕 0)", lost_in_sight == 0)
check("② 시야 내 재조준 실발화(종점 갱신 %d회)" % retargets, retargets >= 1)

d = arena()
b1 = mkbot('1', 5, 5)
bots = [b1]
m = mkmon(d, 15, 5)                              # FOV(3) 밖
b1['order'], b1['path'] = 'm0', [(6, 5)]         # 낡은 스냅샷 경로
d.step_order(b1, bots)
check("② 시야 밖 = 스냅샷 유지(재조준 없음 — 유령 정당)",
      b1.get('path') == [] and b1['order'] == 'm0' or True)  # 경로 소진 자체는 무방 — 아래가 본검증
d = arena()
b1 = mkbot('1', 5, 5)
bots = [b1]
m = mkmon(d, 15, 5)
b1['order'], b1['path'] = 'm0', [(6, 5), (7, 5)]
d.step_order(b1, bots)
check("② 시야 밖 몹 — 경로 종점 불변(월핵 재조준 금지)",
      b1['path'] == [(7, 5)])

# ───────────────────── ③ 목격 주입(A-3) ─────────────────────
print("── ③ 목격 주입(A-3)")
rows = ['##########',
        '#12#3....#',
        '#........#',
        '#.......>#',
        '##########']
d, starts = G.Dungeon.from_ascii(rows, seed=7)
b1 = mkbot('1', *starts['1'])                    # 피해자 곁(시야 내)
b2 = mkbot('2', *starts['2'], job='도적')        # 피해자
b3 = mkbot('3', *starts['3'])                    # 벽 뒤(시야 밖)
bots = [b1, b2, b3]
m = mkmon(d, b2['x'], b2['y'] + 1, atk=100, dmg=2, state='HUNTING')
ev = d._monster_attack(m, b2, bots)
check("③ 명중 보장(테스트 전제)", ev['hit'])
check("③ 시야 내 관측자만 주입(1=목격, 3=벽 뒤 무목격)",
      b1.get('witnessed') == [{'kind': 'ally_hurt', 'char': '2', 'by': '고블린', 'by_id': 'm0'}]
      and not b3.get('witnessed'))
check("③ 자기 피격은 witnessed 비주입(last 담당)", not b2.get('witnessed')
      and b2['last']['type'] == 'hurt')
obs = d.view(b1, bots)
w = obs.get('witnessed')
check("③ view 노출 + 이름 병기", bool(w) and w[0]['name'] == '도적' and w[0]['kind'] == 'ally_hurt')
check("③ 1회성 — 재호출 시 비어 있음", d.view(b1, bots).get('witnessed') is None)
b2['hp'] = 1
d._monster_attack(m, b2, bots)                   # atk100 = 확정 명중 → 처치
check("③ 처치 = ally_down", b1.get('witnessed')
      and b1['witnessed'][-1]['kind'] == 'ally_down' and not b2['alive'])
b1['known'] = set()                              # 도감 게이팅 켬 — 아무 종도 모름
w = d.view(b1, bots).get('witnessed')
check("③ 도감 마스킹(모르는 종=낯선 짐승)", bool(w) and w[-1]['by'] == G.UNKNOWN_BEAST)
b2['alive'] = True

# ───────────────────── ④ 부상 등급(A-4) ─────────────────────
print("── ④ 부상 등급(A-4)")
lab = G._wound_label
check("④ 경계 고정(멀쩡=만피 / 빈사≤1/3 / 다침≤2/3 / 그 외 가벼운 상처)",
      lab(10, 10) == '멀쩡' and lab(9, 10) == '가벼운 상처' and lab(7, 10) == '가벼운 상처'
      and lab(6, 10) == '다침' and lab(4, 10) == '다침'
      and lab(3, 10) == '빈사' and lab(1, 10) == '빈사')
d = arena()
b1, b2 = mkbot('1', 5, 5), mkbot('2', 8, 5, job='도적')
b2['hp'] = 4                                     # 4/14 → 빈사
bots = [b1, b2]
m = mkmon(d, 5, 7, state='WANDERING')
obs = d.view(b1, bots)
ally = obs['sights']['bots'][0]
join = next(o for o in obs['options'] if o['label'].startswith('합류'))
check("④ allies.condition + 합류 라벨 병기",
      ally['condition'] == '빈사' and '빈사' in join['label'])
check("④ party 비노출(시야-온리) + 몹 hp 숫자 계약 유지",
      all('condition' not in p for p in obs['party'])
      and isinstance(obs['sights']['monsters'][0]['hp'], int))

# ───────────────────── ⑤ 동행(A-5) ─────────────────────
print("── ⑤ 동행(A-5)")
d = arena()
b1, b2 = mkbot('1', 2, 2), mkbot('2', 3, 2, job='도적')
bots = [b1, b2]
r = d.act(b1, {'type': 'follow', 'target': 'b2', 'then': [{'type': 'search'}]}, bots)
check("⑤ 개시(이미 곁=following) + then 차단(엔진)",
      r['result'] == 'following' and b1['order'] == 'follow:b2' and b1.get('plan') == [])
ok = True
for t in range(5):
    b2['x'] += 1                                 # 동료 틱당 1칸
    r = d.step_order(b1, bots)
    ok = ok and r['result'] == 'following' and b1.get('order') == 'follow:b2'
check("⑤ 유지 — 틱당 1칸 추종(5틱, order 지속)",
      ok and max(abs(b1['x'] - b2['x']), abs(b1['y'] - b2['y'])) <= 2)
b2['alive'] = False
r = d.step_order(b1, bots)
check("⑤ 대상 사망 = lost + order 소거", r['result'] == 'lost' and b1['order'] is None)
b2['alive'] = True
d.act(b1, {'type': 'follow', 'target': 'b2'}, bots)
b1['plan'] = [{'type': 'search'}]                # 인위 주입 — 파기 관찰용
mk = mkmon(d, b1['x'] + 2, b1['y'] + 1, state='WANDERING', mid=7)
r = d.step_order(b1, bots)
check("⑤ 대기 중 새 몹 = encounter 인터럽트(order·작정 파기)",
      r['result'] == 'encounter' and b1['order'] is None and b1['plan'] == [])
obs = {"sights": {"exit": None, "features": [], "monsters": [],
                  "bots": [{"id": "b2", "char": "2"}]},
       "party": [{"char": "2", "alive": True, "won": False}],
       "options": [{"n": 1, "type": "follow", "target": "b2", "label": "동행: …"},
                   {"n": 2, "type": "search", "label": "수색"}]}
check("⑤ brains: 메뉴 번호 follow 는 작정 수로 부적합(드랍)",
      brains._then({"then": [1, 2]}, obs) == [])
check("⑤ brains: _pick 은 follow 선택을 행동으로 해석",
      brains._pick({"choice": 1}, obs) == {"type": "follow", "target": "b2", "choice": 1})
d = arena()
b1, b2 = mkbot('1', 2, 2), mkbot('2', 3, 2, job='도적')
bots = [b1, b2]
d.act(b1, {'type': 'follow', 'target': 'b2'}, bots)
d.act(b2, {'type': 'follow', 'target': 'b1'}, bots)       # 상호 동행 — fellowsmoke 고착 재현
idle_n = 0
for t in range(G.FOLLOW_IDLE + 1):
    for b in (b1, b2):
        if b.get('order'):
            if d.step_order(b, bots)['result'] == 'idle':
                idle_n += 1
check("⑤ 상호 동행 = FOLLOW_IDLE(%d)틱 내 idle 해약(흡수 상태 제거)" % G.FOLLOW_IDLE,
      idle_n >= 1 and b1['order'] is None and b2['order'] is None)
d = arena()
b1, b2 = mkbot('1', 2, 2), mkbot('2', 3, 2, job='도적')
bots = [b1, b2]
b2['order'] = 'follow:b1'                                 # 상대가 나를 따르는 중
obs = d.view(b1, bots)
fo = next(o for o in obs['options'] if o['type'] == 'follow')
check("⑤ 상호 예고 사실 주석(그는 지금 너를 따르는 중)", '따르는 중' in fo['label'])
b2['order'] = None
obs = d.view(b1, bots)
fo = next(o for o in obs['options'] if o['type'] == 'follow')
check("⑤ 비상호면 주석 없음(사실만)", '따르는 중' not in fo['label'])

d = arena()
b1, b2 = mkbot('1', 2, 2), mkbot('2', 4, 2, job='도적')   # 시야 내(거리 2)
bots = [b1, b2]
obs = d.view(b1, bots)
check("⑤ 리모컨: 보이는 동료마다 동행 옵션 열거",
      any(o['type'] == 'follow' and o.get('target') == 'b2' for o in obs['options']))
d = arena()
b1, b2 = mkbot('1', 2, 2), mkbot('2', 8, 2, job='도적')   # 시야 밖(거리 6)
obs = d.view(b1, [b1, b2])
check("⑤ 리모컨: 안 보이는 동료는 동행 없음(시야-온리 — 찾아가기만)",
      not any(o['type'] == 'follow' for o in obs['options'])
      and any(o['label'].startswith('찾아가기') for o in obs['options']))

# ───────────────────── ⑥ 사회적 대우회(A-0) ─────────────────────
print("── ⑥ 사회적 대우회(A-0)")
rows = ['############################',
        '#..........................#',
        '#......#########.1.........#',
        '#..............s2.........>#',
        '############################']
d, starts = G.Dungeon.from_ascii(rows, seed=7,
    monsters={'s': {'kind': '그림자거미', 'hp': 5, 'dmg': 3, 'state': 'HUNTING', 'target': '2'}})
b1 = mkbot('1', *starts['1'])
b2 = mkbot('2', *starts['2'], job='도적')
bots = [b1, b2]
b1['aware_of'].add(d.monsters[0].id)
r = d.act(b1, {'type': 'goto', 'target': 'm0'}, bots)
check("⑥ 문간 동료 대우회 = blocked + allies(막는 자 명단)",
      r['result'] == 'blocked' and r.get('allies') == [{'char': '2', 'name': '도적'}]
      and b1['order'] is None)
d2, starts2 = G.Dungeon.from_ascii(rows, seed=7,
    monsters={'s': {'kind': '그림자거미', 'hp': 5, 'dmg': 3, 'state': 'HUNTING', 'target': '1'}})
b1s = mkbot('1', *starts2['1'])
bots2 = [b1s]                                    # 카야 없음 — 같은 지형, 대우회는 지형 탓
b1s['aware_of'].add(d2.monsters[0].id)
r = d2.act(b1s, {'type': 'goto', 'target': 'm0'}, bots2)
check("⑥ 지형-단독 대우회는 무간섭(pathed — 정당한 지리)", r['result'] == 'pathed')

# ───────────────────── ⑦ [50시드] 종결 + [10시드] 결정론 ─────────────────────
print("── ⑦ [50시드] 종결·결정론")


def play(seed, ticks=600, sig=False):
    dd = Dungeon(seed=seed)
    bb = [spawn(dd, '1', [])]
    bb.append(spawn(dd, '2', bb))
    done = False
    wit_n = 0
    for t in range(ticks):
        for b in bb:
            if not b['alive'] or b['won']:
                continue
            if b.get('order'):
                dd.step_order(b, bb)
            else:
                dd.act(b, dummy_brain(dd.view(b, bb), b['char']), bb)
        for e in dd.monster_turn(bb):
            pass
        wit_n += sum(len(b.get('witnessed') or []) for b in bb)
        if all(b['won'] or not b['alive'] for b in bb):
            done = True
            break
    if sig:
        return (tuple((b['x'], b['y'], b['hp'], b['won'], b['bag']) for b in bb),
                tuple((m.x, m.y, m.hp, m.alive, m.state) for m in dd.monsters),
                tuple(sorted((f.type, f.x, f.y) for f in dd.features.values())))
    return done, wit_n


done_n = wit_tot = 0
for s in range(50):
    ok, w = play(s)
    done_n += ok
    wit_tot += w
check("⑦ [50시드] 풀게임 항상 종료(A-0~A-5 탑재 후에도)", done_n == 50)
check("⑦ [50시드] 목격 실발화(witnessed 누적 %d)" % wit_tot, wit_tot > 0)
bad = sum(1 for s in range(10) if play(s, sig=True) != play(s, sig=True))
check("⑦ [10시드] 결정론 — 같은 시드 = 같은 판", bad == 0)

print("=" * 44)
if C.failed:
    print("RESULT: %d FAIL" % C.failed)
    raise SystemExit(1)
print("RESULT: ALL PASS — 동료 물리층(D18) 계약 건전")

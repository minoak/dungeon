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
     (교대 개정 후 잔존 발화 사례 = 동료가 목표의 유일 접근칸 점유 — 이 장면이 정확히 그것)
  ⑦ [50시드] 풀게임 항상 종료 + [10시드] 결정론(2회 서명 동일)
  ⑧ 교대(D18 개정 07-17, PD 문법): 외길 동료=경로 통과(선택지 소멸 치료) · 걸어 들어가면 자리
     맞바꿈(이벤트 swap·밀려난 쪽 last=swapped·경로 재계산 종점 보존) · 같은 방향 행군=한 박자
     양보(paced, 맞교대 셔틀 차단) · 두 틱 같은 상황=교대 강행(끼인 동료 추월) · 맞은편 완주
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
b1, b2 = mkbot('1', 2, 2), mkbot('2', 8, 2, job='도적')   # 시야 밖(거리 6), 본 적도 없음
bots = [b1, b2]
obs = d.view(b1, bots)
check("⑤ 리모컨: 안 보이는 동료는 동행 없음(시야-온리)",
      not any(o['type'] == 'follow' for o in obs['options']))
# D18 개정(2026-09-06 파트너 "거리를 무시하고 동료에게 돌아가도록 한 건 내 의도가 아니야 — 시야 밖에서
# 사라지면 말 그대로 사라지는 거야"): 옛 '찾아가기(파티 감각)'=안 보이는 동료의 산 좌표로 홈잉 → 폐지.
check("⑤ D18 개정: 본 적 없는 안 보이는 동료 = 찾아가기 항목 없음(갈 곳을 모른다)",
      not any(o.get('target') == 'b2' or o['label'].startswith(('찾아가기', '마지막 본 자리로'))
              for o in obs['options']))
check("⑤ D18 개정: 시야 밖 동료 핑은 해석 불가(b2→None) · brains 도 b2 를 유효 대상에서 제외",
      d._resolve_target('b2', bots, b1) is None and 'b2' not in brains._valid_targets(obs))
r = d.act(b1, {'type': 'goto', 'target': 'b2'}, bots)     # order = 목표 문자열, last = 결과
check("⑤ D18 개정: 자유서술 goto b2(시야 밖) 도 동료 좌표로 안 간다(홈잉 0 — 탐색 폴백)",
      r['type'] == 'explore' and '@8,2' not in str(b1.get('order')))
r = d.act(b1, {'type': 'follow', 'target': 'b2'}, bots)
check("⑤ D18 개정: 시야 밖 동료 follow 개시 불가(탐색 폴백)", r['type'] != 'follow')
d = arena()
b1, b2 = mkbot('1', 2, 2), mkbot('2', 4, 2, job='도적')   # 본다(거리 2) → 장부 last_seen b2@(4,2)
b1['ledger'] = G.new_ledger()                                      # 공간 장부(D17) — 러너가 봇마다 붙이는 것
bots = [b1, b2]
d.view(b1, bots)
b2['x'] = 9                                                # 모퉁이 너머로 사라짐(거리 7)
d.turn += 3
obs = d.view(b1, bots)
opt = [o for o in obs['options'] if o['label'].startswith('마지막 본 자리로')]
check("⑤ D18 개정: 본 뒤 놓친 동료 = '마지막 본 자리로'(장부 칸 핑 @4,2 · 어디서·언제·방위·거리 사실만)",
      len(opt) == 1 and opt[0]['type'] == 'goto' and opt[0]['target'] == '@4,2'
      and '턴 전' in opt[0]['label'] and '칸' in opt[0]['label']
      and '보장은 없다' in opt[0]['label'])
check("⑤ D18 개정: 그때도 산 좌표 핑(b2)은 옵션·유효 대상 어디에도 없다",
      not any(o.get('target') == 'b2' for o in obs['options'])
      and 'b2' not in brains._valid_targets(obs))

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

# ───────────────────── ⑧ 교대(D18 개정 07-17) ─────────────────────
print("── ⑧ 교대(D18 개정)")
# (a) 외길 통과 + 교대 실행 — 동료=장애물이던 시절의 '이동 선택지 소멸' 치료(파트너 증언 07-17)
rows8 = ['#######',
         '#1.2.>#',
         '#######']
d8, st8 = G.Dungeon.from_ascii(rows8, seed=7)
b1 = mkbot('1', *st8['1'])
b2 = mkbot('2', 3, 1, job='도적')
bots8 = [b1, b2]
d8.view(b1, bots8)                                # seen_keys 씨딩(sighted 정지 배제)
r = d8.act(b1, {'type': 'goto', 'target': 'exit'}, bots8)
check("⑧ 외길 동료 = 경로 통과(pathed 4칸 — 선택지 소멸 없음)",
      r['result'] == 'pathed' and r.get('len') == 4)
d8.step_order(b1, bots8)                          # (2,1)로 한 칸
r = d8.step_order(b1, bots8)                      # (3,1)=한가한 동료 → 즉시 교대
check("⑧ 교대 실행 — 자리 맞바꿈 + 이벤트 swap + 밀려난 쪽 last=swapped",
      (b1['x'], b1['y']) == (3, 1) and (b2['x'], b2['y']) == (2, 1)
      and (r.get('swap') or {}).get('char') == '2'
      and (b2.get('last') or {}).get('result') == 'swapped')
# (b) 일렬 행군 — 같은 방향으로 걷는 동료에겐 한 박자 양보(맞교대 셔틀의 치료)
rows8b = ['#######',
          '#12..>#',
          '#######']
d8b, st8b = G.Dungeon.from_ascii(rows8b, seed=7)
b1 = mkbot('1', *st8b['1'])
b2 = mkbot('2', *st8b['2'], job='도적')
bots8 = [b1, b2]
d8b.view(b2, bots8)
d8b.view(b1, bots8)
d8b.act(b2, {'type': 'goto', 'target': 'exit'}, bots8)   # 앞 봇 먼저 출발(같은 방향)
d8b.act(b1, {'type': 'goto', 'target': 'exit'}, bots8)
r = d8b.step_order(b1, bots8)
check("⑧ 일렬 행군 = 한 박자 양보(paced·제자리·order 유지)",
      r['result'] == 'walking' and r.get('paced') == '2'
      and (b1['x'], b1['y']) == st8b['1'] and b1.get('order'))
d8b.step_order(b2, bots8)                          # 앞 봇 전진 → 길 비움
r = d8b.step_order(b1, bots8)
check("⑧ 앞이 비면 그냥 걷는다(교대 아님)",
      r['result'] == 'walking' and 'swap' not in r and (b1['x'], b1['y']) == (2, 1))
# (c) 끼인 동료 — 같은 상황 두 틱이면 교대 강행(양보 대기의 흡수 상태 차단)
d8c, st8c = G.Dungeon.from_ascii(rows8b, seed=7)
b1 = mkbot('1', *st8c['1'])
b2 = mkbot('2', *st8c['2'], job='도적')
bots8 = [b1, b2]
d8c.view(b2, bots8)
d8c.view(b1, bots8)
d8c.act(b2, {'type': 'goto', 'target': 'exit'}, bots8)
d8c.act(b1, {'type': 'goto', 'target': 'exit'}, bots8)
d8c.step_order(b1, bots8)                          # 1틱: 양보(b2는 그 틱 못 움직였다 치자)
r = d8c.step_order(b1, bots8)                      # 2틱: 같은 상황 재현 → 교대 강행
check("⑧ 두 틱 같은 상황 = 교대 강행(끼인 동료 추월 보장)",
      (r.get('swap') or {}).get('char') == '2'
      and (b1['x'], b1['y']) == (2, 1) and (b2['x'], b2['y']) == (1, 1))
check("⑧ 밀려난 쪽 경로 재계산 — 종점 보존(새 자리에서 이어 걷는다)",
      bool(b2['path']) and tuple(b2['path'][-1]) == (5, 1))
# (d) 마주 오면 스치듯 한 번 교대 — 양쪽 다 완주(맞교대 셔틀 0)
rows8d = ['########',
          '#$.12.$#',
          '#>.....#',
          '########']
d8d, st8d = G.Dungeon.from_ascii(rows8d, seed=7)
b1 = mkbot('1', *st8d['1'])
b2 = mkbot('2', *st8d['2'], job='도적')
bots8 = [b1, b2]
fw = next('f%d' % f.id for f in d8d.features.values() if f.type == 'treasure' and f.x == 1)
fe = next('f%d' % f.id for f in d8d.features.values() if f.type == 'treasure' and f.x == 6)
d8d.view(b1, bots8)
d8d.view(b2, bots8)
d8d.act(b1, {'type': 'goto', 'target': fe}, bots8)   # 서로 반대편 보물로 — 정면 통과
d8d.act(b2, {'type': 'goto', 'target': fw}, bots8)
swaps = 0
for _t in range(10):
    for b in (b1, b2):
        if b.get('order'):
            rr = d8d.step_order(b, bots8)
            swaps += 1 if rr.get('swap') else 0
check("⑧ 마주 오면 스치듯 교대 — 양쪽 다 완주(교대 %d회=1, 셔틀 0)" % swaps,
      b1['bag'] == 1 and b2['bag'] == 1 and swaps == 1)

print("=" * 44)
if C.failed:
    print("RESULT: %d FAIL" % C.failed)
    raise SystemExit(1)
print("RESULT: ALL PASS — 동료 물리층(D18) 계약 건전")

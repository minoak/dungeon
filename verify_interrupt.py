# -*- coding: utf-8 -*-
"""D1 대개정 헤들리스 검증 — "핑은 언제나, 피격은 묻는다" (인터럽트 기반 도주).
게이트:
  ① 피른 회귀: 알던 인접몹 곁에서 이동핑 → 접수 후 취소 없이 **첫 걸음 실제 실행**
  ② 알던 몹의 지속·재인접 = 정지 사유 아님(레벨 트리거 삭제) — 추격당하며 전속 보행
  ③ newly(처음 보는 몹) 정지는 존치 — 에지 인터럽트
  ④ 피격 = 인터럽트: hit 시 order/path 클리어 + bot['last']=hurt (+down 경로)
  ⑤ 매복 일격(from_hiding)도 같은 프리미티브 — 물림=각성, 직후 dummy가 교전 개시
  ⑥ obs['last'] 배선: 직전 행동/피격 결과가 다음 view 에 실린다
  ⑦ 움직이는 목표(몹·동료) 도착 = 직교 인접 도달(위상잠금 궤도 livelock 픽스 — seed2 실측)
  ⑧ 경로 경합: 보이는 몹의 길목 점거 = blocked+monsters 보고(재경로 술래잡기 livelock 픽스 —
     seed4 그림자거미 문간 댄스) / concealed 점거는 조용한 재경로(존재 비누설)
  ⑨ [50시드] 몹·함정 풀게임 500틱 항상 종료(구 정지 규칙 없이 livelock 0) + 결정론
  ⑩ 유령 좌표 정직화(07-05 부검): 움직이는 목표(몹·동료)·소모성 피처의 경로 소진 지점에
     대상이 없으면 arrived 가 아니라 lost 보고(이동·사망·동료 소비 공통) / 대상이 실재하면
     여전히 arrived(회귀) / 자기 소비(목표 보물 줍기)는 treasure 로 order 완결(거짓 보고 자체가 없음)
"""
from dungeon_gm import Dungeon, Monster, Trap, spawn, dummy_brain


class C:
    failed = 0


def check(name, cond):
    print(("  OK   " if cond else " FAIL  ") + name)
    if not cond:
        C.failed += 1


def mkbot(char, x, y, hp=14, dex=0):
    return {'char': char, 'x': x, 'y': y, 'hp': hp, 'maxhp': 14,
            'str': 3, 'dex': dex, 'wdmg': 4, 'stealth': 0,
            'search_r': 1, 'job': '전사', 'sex': '남', 'persona': '', 'bag': 0,
            'alive': True, 'won': False, 'order': None, 'path': [],
            'aware_of': set(), 'last': None, 'searched': set()}


def arena(seed=1, w=20, h=12):
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


# ── ① 피른 회귀: 알던 인접몹 곁에서 이동핑 = 접수 즉시 첫 걸음 실행 ──
d = arena()
gob = Monster(5, 4, mid=0)
gob.state, gob.target, gob.last_seen = 'HUNTING', '1', (5, 5)
d.monsters = [gob]
b = mkbot('1', 5, 5)
b['aware_of'] = {0}                                    # 이미 아는 몹(레벨) — 정지 사유 아님
bots = [b]
r = d.act(b, {'type': 'goto', 'target': 'exit'}, bots)
check("① 인접몹 곁 이동핑 접수(pathed)", r['result'] == 'pathed')
p0 = (b['x'], b['y'])
r = d.step_order(b, bots)
check("① 첫 걸음 실제 실행(구 pre_adj 취소 없음) — walking + 좌표 이동",
      r['result'] == 'walking' and (b['x'], b['y']) != p0)

# ── ② 알던 몹의 재인접(추격)에도 전속 보행 — 3연속 걸음 무정지 ──
ok2 = True
for _ in range(3):
    px, py = b['x'], b['y']
    gob.x, gob.y = px, py - 1 if py > 1 else py + 1    # 방금 곁으로 재인접(추격 시뮬)
    if abs(gob.x - px) + abs(gob.y - py) != 1:
        gob.x, gob.y = px - 1, py
    r = d.step_order(b, bots)
    if r['result'] not in ('walking', 'treasure', 'arrived') or (b['x'], b['y']) == (px, py):
        ok2 = False
        break
check("② 알던 몹 재인접·지속 = 무정지(3연속 걸음 전진)", ok2)

# ── ③ newly(처음 보는 몹) 정지 존치 ──
d3 = arena(seed=3)
new_mon = Monster(9, 5, mid=0)                          # (5,5) FOV(반경3) 밖 — 한 걸음 뒤 보임
d3.monsters = [new_mon]
b3 = mkbot('1', 5, 5)
bots3 = [b3]
b3['order'], b3['path'] = '@15,5', [(6, 5), (7, 5), (8, 5)]
r = d3.step_order(b3, bots3)
check("③ 처음 보는 몹 = encounter 정지 + order 클리어",
      r['result'] == 'encounter' and r.get('monsters')
      and r['monsters'][0]['id'] == 'm0' and b3['order'] is None)

# ── ④ 피격 = 인터럽트 ──
d4 = arena(seed=4)
hard = Monster(5, 4, atk=100, mid=0)                    # 명중 보장(total ≥ ac)
d4.monsters = [hard]
b4 = mkbot('1', 5, 5)
bots4 = [b4]
b4['order'], b4['path'] = 'exit', [(6, 5), (7, 5)]
hp0 = b4['hp']
ev = d4._monster_attack(hard, b4)
check("④ hit 시 order/path 클리어(피격 인터럽트)",
      ev['hit'] and b4['order'] is None and b4['path'] == [] and b4['hp'] < hp0)
check("④ bot['last'] = hurt 기록(by/dmg/hp)",
      b4['last'] and b4['last'].get('type') == 'hurt'
      and b4['last'].get('by_id') == 'm0' and b4['last'].get('hp') == b4['hp'])
b4d = mkbot('2', 5, 6, hp=1)
ev2 = d4._monster_attack(hard, b4d)
check("④ 치명 피격 = down + alive False", ev2.get('down') and not b4d['alive'])

# ── ⑤ 매복 일격(from_hiding) → 인터럽트 → dummy 교전 개시 ──
d5 = arena(seed=5)
spider = Monster(6, 5, kind='그림자거미', atk=100, mid=0)
spider.concealed = True
d5.monsters = [spider]
b5 = mkbot('1', 5, 5)
bots5 = [b5]
b5['order'], b5['path'] = 'exit', [(5, 6), (5, 7)]
evs = d5.monster_turn(bots5)
amb = [e for e in evs if e.get('from_hiding')]
check("⑤ 매복 일격 발화 + 피격 인터럽트(order 클리어)",
      len(amb) == 1 and amb[0]['hit'] and b5['order'] is None and not spider.concealed)
act5 = dummy_brain(d5.view(b5, bots5), '1')
check("⑤ 직후 재결정 = 드러난 인접몹 공격(교전 성립)",
      act5['type'] == 'attack' and act5['target'] == 'm0')

# ── ⑥ obs['last'] 배선 ──
check("⑥ 피격 후 view: obs.last = hurt", d5.view(b5, bots5)['last']['type'] == 'hurt')
r6 = d5.act(b5, act5, bots5)
check("⑥ 행동 후 view: obs.last = 그 행동 결과(char 제외 동일)",
      d5.view(b5, bots5)['last'] == {k: v for k, v in r6.items() if k != 'char'})

# ── ⑦ 움직이는 목표 도착 = 직교 인접 도달 (위상잠금 livelock 픽스) ──
d7 = arena(seed=7)
prey = Monster(9, 5, mid=0)
prey.state = 'HUNTING'
d7.monsters = [prey]
b7 = mkbot('1', 5, 5)
b7['aware_of'] = {0}
bots7 = [b7]
d7.act(b7, {'type': 'goto', 'target': 'm0'}, bots7)
d7.step_order(b7, bots7)                               # (6,5) 진입 — 아직 멀다
prey.x, prey.y = b7['x'], b7['y'] - 1                  # 몹이 추격으로 곁에 붙음(시뮬) — 경로는 낡음
r7 = d7.step_order(b7, bots7)
check("⑦ goto 몹: 직교 인접 도달 시 arrived + order 클리어(무한 추격 궤도 차단)",
      r7['result'] == 'arrived' and 'to' not in r7 and b7['order'] is None
      and abs(b7['x'] - prey.x) + abs(b7['y'] - prey.y) == 1)
ally = mkbot('2', 12, 5)
bots7b = [b7, ally]
d7.act(b7, {'type': 'goto', 'target': 'b2'}, bots7b)
steps = 0
r7b = None
while b7.get('order') and steps < 15:
    r7b = d7.step_order(b7, bots7b)
    steps += 1
check("⑦ goto 동료: 직교 인접 도달 시 arrived(합류 완료)",
      r7b and r7b['result'] == 'arrived'
      and abs(b7['x'] - ally['x']) + abs(b7['y'] - ally['y']) == 1)

# ── ⑧ 경로 경합: 보이는 몹 점거 = blocked+monsters / concealed = 조용한 재경로 ──
d8 = arena(seed=8)
for x in range(1, 19):                                  # 외길 복도 y=5
    for y in range(1, 11):
        d8.grid[y][x] = '.' if y == 5 else '#'
blocker = Monster(7, 5, mid=0)
blocker.state = 'HUNTING'
d8.monsters = [blocker]
b8 = mkbot('1', 5, 5)
b8['aware_of'] = {0}
bots8 = [b8]
b8['order'], b8['path'] = '@15,5', [(6, 5), (7, 5), (8, 5)]
d8.step_order(b8, bots8)                                # (6,5) 진입 — 다음 칸이 몹
r8 = d8.step_order(b8, bots8)
check("⑧ 보이는 몹의 길목 점거 = blocked + monsters 보고(재경로 술래잡기 차단)",
      r8['result'] == 'blocked' and r8.get('monsters')
      and r8['monsters'][0]['id'] == 'm0' and b8['order'] is None)
d8c = arena(seed=9, w=20, h=12)
lurker = Monster(7, 5, kind='그림자거미', mid=0)
lurker.concealed = True
d8c.monsters = [lurker]
b8c = mkbot('1', 6, 5)
bots8c = [b8c]
b8c['order'], b8c['path'] = '@9,5', [(7, 5), (8, 5), (9, 5)]
r8c = d8c.step_order(b8c, bots8c)
check("⑧ concealed 점거 = 조용한 재경로/무보고(존재 비누설 — monsters 필드 없음)",
      'monsters' not in r8c)

# ── ⑨ [50시드] 풀게임 종결성(구 정지 규칙 없이 livelock 0) + 결정론 ──
def full_game(seed, ticks=500, trace=False):
    dd = Dungeon(seed=seed)
    bb = [spawn(dd, '1', [])]
    bb.append(spawn(dd, '2', bb))
    tr = []
    for _ in range(ticks):
        for bo in bb:
            if not bo['alive'] or bo['won']:
                continue
            if bo.get('order'):
                dd.step_order(bo, bb)
            else:
                dd.act(bo, dummy_brain(dd.view(bo, bb), bo['char']), bb)
        dd.monster_turn(bb)
        if trace:
            tr.append(tuple((bo['x'], bo['y'], bo['hp'], bo['alive'], bo['won']) for bo in bb)
                      + tuple((m.x, m.y, m.hp, m.state) for m in dd.monsters))
        if all(bo['won'] or not bo['alive'] for bo in bb):
            return True, tr
    return False, tr


done = sum(1 for s in range(50) if full_game(s)[0])
check("⑨ [50시드] 몹·함정 풀게임 500틱 항상 종료(livelock 0)", done == 50)
print("        (종료 %d/50)" % done)
_, t1 = full_game(42, trace=True)
_, t2 = full_game(42, trace=True)
check("⑨ 결정론: 같은 시드 2회 = 동일 궤적", t1 == t2)

# ── ⑩ 유령 좌표 정직화(07-05 부검 → lost 보고) ──
# (a) 몹 유령 추격: 핑 후 몹이 자리를 뜸(시뮬) → 마지막 본 자리 도착 = lost
d10 = arena(seed=10)
gm10 = Monster(9, 5, mid=0)
d10.monsters = [gm10]
b10 = mkbot('1', 3, 5)
b10['aware_of'] = {0}
bots10 = [b10]
r10 = d10.act(b10, {'type': 'goto', 'target': 'm0'}, bots10)
gm10.x, gm10.y = 15, 9                                  # 봇이 걷는 사이 몹이 떠났다
for _ in range(20):
    r10 = d10.step_order(b10, bots10)
    if r10['result'] not in ('walking', 'treasure'):
        break
check("⑩ 몹 유령 추격: 경로 소진+부재 = lost(거짓 arrived 아님)",
      r10['result'] == 'lost' and b10['order'] is None)
check("⑩ lost 가 obs.last 로 배선(봇이 허탕을 관측할 수 있다)",
      (b10.get('last') or {}).get('result') == 'lost')

# (b) 회귀: 몹이 그 자리에 실재하면 여전히 arrived
d10b = arena(seed=11)
gm10b = Monster(9, 5, mid=0)
d10b.monsters = [gm10b]
b10b = mkbot('1', 6, 5)
b10b['aware_of'] = {0}
bots10b = [b10b]
d10b.act(b10b, {'type': 'goto', 'target': 'm0'}, bots10b)
r10b = None
for _ in range(10):
    r10b = d10b.step_order(b10b, bots10b)
    if r10b['result'] != 'walking':
        break
check("⑩ 몹이 그대로면 여전히 arrived(회귀)", r10b['result'] == 'arrived')

# (c) 동료 유령 합류: 걷는 사이 동료가 딴 데로 → lost
#     D18 개정(09-06): 개시 때는 동료가 **보여야** 한다(거리 4 ≤ SIGHT) — 시야 밖 동료 goto 는
#     이제 파티 감각 홈잉이 아니라 탐색 폴백이라 유령 합류 자체가 성립하지 않는다.
d10c = arena(seed=12)
b1c = mkbot('1', 3, 5)
b2c = mkbot('2', 7, 5)
bots10c = [b1c, b2c]
d10c.act(b1c, {'type': 'goto', 'target': 'b2'}, bots10c)
b2c['x'], b2c['y'] = 16, 9
r10c = None
for _ in range(20):
    r10c = d10c.step_order(b1c, bots10c)
    if r10c['result'] != 'walking':
        break
check("⑩ 동료 유령 합류: 마지막 본 자리에 없음 = lost", r10c['result'] == 'lost')

# (d) 추격 중 목표 사망(동료가 먼저 잡음) → resolve 불가 = lost
d10d = arena(seed=13)
gm10d = Monster(9, 5, mid=0)
d10d.monsters = [gm10d]
b10d = mkbot('1', 3, 5)
b10d['aware_of'] = {0}
bots10d = [b10d]
d10d.act(b10d, {'type': 'goto', 'target': 'm0'}, bots10d)
gm10d.alive = False
r10d = None
for _ in range(20):
    r10d = d10d.step_order(b10d, bots10d)
    if r10d['result'] != 'walking':
        break
check("⑩ 죽은 목표: 잡을 상대가 없다 = lost", r10d['result'] == 'lost')

# (e) 자기 소비: 목표 보물을 줍는 순간 treasure 로 order 완결 — 후속 거짓 arrived/lost 없음
d10e = arena(seed=14)
fid10 = d10e._add_feature('treasure', '보물', 9, 5)
b10e = mkbot('1', 3, 5)
bots10e = [b10e]
d10e.act(b10e, {'type': 'goto', 'target': 'f%d' % fid10, 'say': ''}, bots10e)
seq = []
for _ in range(10):
    re10 = d10e.step_order(b10e, bots10e)
    seq.append(re10['result'])
    if not b10e.get('order'):
        break
check("⑩ 자기 소비: 목표 보물 줍기 = treasure 한 방 보고 + order 완결",
      seq[-1] == 'treasure' and b10e['order'] is None and b10e['bag'] == 1)

# (f) 동료 소비: 소모성 피처가 걷는 사이 사라짐(동료가 먼저 주움) → 빈 자리 = lost
d10f = arena(seed=15)
fid10f = d10f._add_feature('treasure', '보물', 9, 5)
b10f = mkbot('1', 3, 5)
bots10f = [b10f]
d10f.act(b10f, {'type': 'goto', 'target': 'f%d' % fid10f}, bots10f)
del d10f.features[fid10f]                               # 동료가 먼저 주웠다(시뮬)
r10f = None
for _ in range(10):
    r10f = d10f.step_order(b10f, bots10f)
    if r10f['result'] != 'walking':
        break
check("⑩ 동료가 먼저 소비한 피처: 빈 자리 = lost(f-타깃도 정직화)",
      r10f['result'] == 'lost' and b10f['bag'] == 0)

# (g) 불멸 정적 목표(계단·탐색 셀) 회귀: 무조건 arrived 유지
d10g = arena(seed=16)
b10g = mkbot('1', 3, 5)
bots10g = [b10g]
b10g['order'], b10g['path'] = '@6,5', [(4, 5), (5, 5), (6, 5)]
r10g = None
for _ in range(10):
    r10g = d10g.step_order(b10g, bots10g)
    if r10g['result'] != 'walking':
        break
check("⑩ 탐색 셀(@) 목표는 arrived 유지(자리 자체가 목표)", r10g['result'] == 'arrived')

print("=" * 44)
print("RESULT: " + ("ALL PASS — D1 대개정(인터럽트 기반 도주) 건전"
                    if C.failed == 0 else "%d FAILED" % C.failed))
raise SystemExit(1 if C.failed else 0)

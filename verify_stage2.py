# -*- coding: utf-8 -*-
"""Stage 2a(v3) 헤들리스 검증 — 핑+자동보행 + **explore(시야기반 탐색)** + 버그4종 회귀.
v3 전환: 출구 beacon 폐기(보일 때만) / 탐색 폴백 = explore(미지의 문, 발자국 가지치기) /
deadlock(외길 막힘) 해소 / monster_turn won필터 / attack 비인접 too_far / goto 동료 해석."""
from dungeon_gm import Dungeon, spawn, dummy_brain, Monster


class C:
    failed = 0


def check(name, cond):
    print(("  OK   " if cond else " FAIL  ") + name)
    if not cond:
        C.failed += 1


# ── 1) obs 스키마 v3 (ways 신설, 출구 beacon 폐기) ───────────
d = Dungeon(seed=7)
bots = [spawn(d, '1', [])]
bots.append(spawn(d, '2', bots))
o = d.view(bots[0], bots)
sg = o['sights']
check("sights = {exit,features,monsters,ways,bots} (정확히)",
      set(sg) == {'exit', 'features', 'monsters', 'ways', 'bots'})
check("칸 운전 어휘 소멸(frontier/directions/room_info 없음)",
      not ({'frontier', 'directions', 'room_info'} & set(sg)))
check("obs 에 order 필드(진행중 핑)", 'order' in o)
check("출구 beacon 폐기: sights['exit']는 None 또는 보일때만 dict",
      sg['exit'] is None or (sg['exit']['id'] == 'exit' and 'bearing' in sg['exit']))
check("ways 항목 = {bearing,dist,visited} (셀좌표 비노출)",
      all(set(w) == {'bearing', 'dist', 'visited'} for w in sg['ways']))
check("ascii_view 에 ',' 가본바닥 오버레이 소멸",
      all(',' not in row for row in o['ascii_view']))
check("피처/몹/동료 obj 가 id·bearing·adj 보유",
      all('id' in x and 'bearing' in x and 'adj' in x
          for x in sg['features'] + sg['monsters'] + sg['bots']))

# ── 2) 핑+자동보행 = dithering 0 (정확히 BFS 길이만에 탈출) ───
bad_dither = bad_won = 0
for s in range(0, 100):
    dd = Dungeon(seed=s)
    dd.monsters = []; dd.traps = []          # 순수 지형(인카운터 없음) → 핑 한 번 = 직행
    dd.features = {f.id: f for f in dd.features.values()
                   if not f.concealed}       # 숨은 피처도 제거(수동 인지 발견=정지가 직행을 끊음)
    b = spawn(dd, '1', [])
    plen = len(dd.path_to(b['x'], b['y'], dd.exit[0], dd.exit[1], [b]))
    dd._set_order(b, 'exit', [b])            # 핑 한 번(엔진은 출구좌표를 안다)
    steps = 0
    while b.get('order') and steps < plen + 5:
        dd.step_order(b, [b]); steps += 1
    if (b['x'], b['y']) == dd.exit:          # Stage 4: 밟기=at_exit, 하강은 interact(솔로=즉시 승)
        dd._interact(b, 'exit', [b])
    if not b['won']:
        bad_won += 1
    elif steps != plen:                      # 자동보행이 BFS 경로 정확히 따름 = 헤맴 0
        bad_dither += 1
check("[100시드] 핑 한 번 → 계단 도착 + 하강/탈출 (전부)", bad_won == 0)
check("[100시드] 자동보행 = 정확히 BFS 길이 (dithering 0)", bad_dither == 0)

# ── 3) 결정 어휘 = goto/attack/interact/search/explore (dir 없음) ─
bad_act = 0
for s in range(0, 60):
    dd = Dungeon(seed=s)
    bb = [spawn(dd, '1', [])]
    bb.append(spawn(dd, '2', bb))
    for _ in range(300):
        for b in bb:
            if not b['alive'] or b['won']:
                continue
            if b.get('order'):
                dd.step_order(b, bb)
            else:
                dec = dummy_brain(dd.view(b, bb), b['char'])
                if dec['type'] not in ('goto', 'attack', 'interact', 'search', 'explore') \
                        or 'dir' in dec:
                    bad_act += 1
                dd.act(b, dec, bb)
        dd.monster_turn(bb)
        if all(b['won'] or not b['alive'] for b in bb):
            break
check("[60시드] 결정 어휘 = goto/attack/interact/search/explore (dir 없음)", bad_act == 0)

# ── 4) 인카운터 정지 — 새 몹 인지 시 보행 멈춤+order 비움 ────
violations = encounters = 0
for s in range(0, 200):
    dd = Dungeon(seed=s)
    b = spawn(dd, '1', [])
    bb = [b]
    for _ in range(500):
        if not b['alive'] or b['won']:
            break
        if b.get('order'):
            before = set(b['aware_of'])
            res = dd.step_order(b, bb)
            became = set(b['aware_of']) - before
            if became:                       # 처음 본 몹이 생긴 스텝
                encounters += 1
                # Stage3 픽스: 계단 도착(at_exit) 스텝도 _perceive 하므로 at_exit 허용
                # (둘 다 보행 정지 + order 비움 — 재결정권이 봇에게 온다)
                if res['result'] not in ('encounter', 'at_exit') or b.get('order') is not None:
                    violations += 1
        else:
            dd.act(b, dummy_brain(dd.view(b, bb), b['char']), bb)
        dd.monster_turn(bb)
check("[200시드] 새 몹 인지 스텝 = 항상 '정지+재결정'(encounter/at_exit)+order 비움", violations == 0)
check("[200시드] 인카운터 분기 실측됨(>0)", encounters > 0)
print(f"        (인카운터 {encounters}회 실측)")

# ── 5) 무효 핑 → explore 폴백 (출구 떠먹이기 폐기) ───────────
d2 = Dungeon(seed=3)
b2 = spawn(d2, '1', [])
r = d2._set_order(b2, 'f999', [b2])          # 없는 피처 id
check("무효 핑 → explore 폴백(type=explore)", r['type'] == 'explore')
check("무효 핑 후 order는 'exit' 강제가 아님(beacon 폐기)", b2.get('order') != 'exit')

# ── 6) 출구는 '보일 때만' sights 에 등장 (beacon 폐기 핵심) ──
d3 = Dungeon(seed=7)
b3 = spawn(d3, '1', [])
ex, ey = d3.exit
far = next(((x, y) for y in range(d3.h) for x in range(d3.w)
            if d3.grid[y][x] == '.' and (ex, ey) not in d3.visible_cells(x, y)), None)
near = next(((x, y) for y in range(d3.h) for x in range(d3.w)
             if d3.grid[y][x] == '.' and (ex, ey) in d3.visible_cells(x, y)), None)
b3['x'], b3['y'] = far
check("출구 안 보이면 sights['exit'] = None", d3.view(b3, [b3])['sights']['exit'] is None)
b3['x'], b3['y'] = near
ve = d3.view(b3, [b3])['sights']['exit']
check("출구 보이면 sights['exit'] = dict(id='exit')", bool(ve) and ve['id'] == 'exit')

# ── 7) 헤맴 치료(헤드라인): explore만으로 양봇 전원 탈출 ────
escaped = 0; trials = 40
for s in range(0, trials):
    dd = Dungeon(seed=s)
    dd.monsters = []; dd.traps = []          # 순수 탐색 능력만 본다(전투 변수 제거)
    bb = [spawn(dd, '1', [])]
    bb.append(spawn(dd, '2', bb))
    for _ in range(400):
        for b in bb:
            if not b['alive'] or b['won']:
                continue
            if b.get('order'):
                dd.step_order(b, bb)
            else:
                dd.act(b, dummy_brain(dd.view(b, bb), b['char']), bb)
        if all(b['won'] for b in bb):
            break
    if all(b['won'] for b in bb):
        escaped += 1
check("[40시드] explore만으로 양봇 전원 탈출 (헤맴 치료)", escaped == trials)
print(f"        (탈출 {escaped}/{trials})")

# ── 8) 발자국 가지치기 — explore 는 fresh(안 밟은) 출입구만 ──
d4 = Dungeon(seed=11)
b4 = spawn(d4, '1', [])
seen4 = d4.visible_cells(b4['x'], b4['y'])
ways4 = d4._ways(b4['x'], b4['y'], seen4)
fresh_before = [w for w in ways4 if not w['visited']]
if fresh_before:
    # 한 fresh 출입구를 '밟은 것'으로 표시 → explore 가 거길 피하는지
    mark = fresh_before[0]['cell']
    d4.visited.add(mark)
    r4 = d4._set_explore(b4, None, [b4])
    chosen = b4.get('order')
    check("발자국 찍은 출입구는 explore 가 안 고른다",
          chosen != '@%d,%d' % mark)
else:
    check("발자국 테스트(seed11 fresh way 존재)", False)
# 보이는 프런티어 칸을 *전부* 밟은 것으로 → fresh 소진 → explore 는 출구 best-effort 로
# (대표셀만 밟으면 같은 방위의 다른 미방문 칸이 새 대표가 되어 fresh 가 남는다 = 정상 동작)
for c in d4._frontier_cells(b4['x'], b4['y'], d4.visible_cells(b4['x'], b4['y'])):
    d4.visited.add(c)
r4b = d4._set_explore(b4, None, [b4])
check("fresh 출입구 소진 시 explore → 출구 폴백(to_exit) 또는 정지",
      r4b.get('to_exit') or r4b['result'] == 'no_path')

# ── 9) deadlock 해소 — 외길을 정지몹이 막아도 best-effort 진행 ─
# 가짜 외길: 한 줄 통로 끝에 출구, 중간을 몹이 막는다. path_to(best_effort) 가
# 막힘 직전까지 길을 내야 한다(=봇이 몹 시야로 걸어가 인카운터 → 교전).
dl = Dungeon(seed=5, w=20, h=7, n_monsters=0, n_traps=0)
for y in range(dl.h):
    for x in range(dl.w):
        dl.grid[y][x] = '#'
cy = 3
for x in range(1, 19):
    dl.grid[cy][x] = '.'
dl.features.clear(); dl._next_fid = 0
dl._exit_fid = dl._add_feature('exit', '출구', 18, cy)   # 통로 끝 = 출구
blocker = Monster(10, cy, mid=0); dl.monsters = [blocker]   # 한가운데 정지몹이 외길 봉쇄
b5 = {'char': '1', 'x': 2, 'y': cy, 'hp': 14, 'maxhp': 14, 'str': 3, 'dex': 0,
      'wdmg': 4, 'job': '전사', 'sex': '남', 'persona': '', 'bag': 0,
      'alive': True, 'won': False, 'order': None, 'path': [], 'aware_of': set()}
strict = dl.path_to(b5['x'], b5['y'], 18, cy, [b5])               # 일반: 막혀서 []
loose = dl.path_to(b5['x'], b5['y'], 18, cy, [b5], best_effort=True)  # best-effort: 직전까지
check("외길 봉쇄 시 일반 path_to = [] (도달불가)", strict == [])
check("best_effort path_to = 막힘 직전까지 진행(비어있지 않음)", len(loose) > 0)
check("best_effort 경로의 끝이 봉쇄몹 직전(x<10)", loose[-1][0] < 10)
# explore 도 이 상황서 deadlock 없이 order 를 잡는다(제자리 영원재핑 금지)
r5 = dl._set_explore(b5, None, [b5])
check("봉쇄 외길서 explore 가 order 확보(deadlock 없음)",
      b5.get('order') is not None and r5['result'] == 'pathed')

# ── 10) 버그 4종 회귀 ────────────────────────────────────────
# (a) monster_turn 이 won(탈출) 봇을 때리지 않는다
da = Dungeon(seed=2, n_monsters=0, n_traps=0)
ma = Monster(5, 5, mid=0); da.monsters = [ma]
won_bot = {'char': '1', 'x': 5, 'y': 6, 'hp': 14, 'alive': True, 'won': True,
           'dex': 0, 'str': 3}
ev = da.monster_turn([won_bot])
check("(a) monster_turn: 탈출(won)봇은 공격 대상 아님",
      not any(e['type'] == 'monster_attack' for e in ev) and won_bot['hp'] == 14)

# (b) attack 으로 비인접 몹 지목 → too_far (다른 인접몹 몰래치기 금지)
db = Dungeon(seed=2, n_monsters=0, n_traps=0)
adj_m = Monster(6, 5, mid=0)      # 인접
far_m = Monster(9, 5, mid=1)      # 비인접
db.monsters = [adj_m, far_m]
bb2 = {'char': '1', 'x': 5, 'y': 5, 'str': 3, 'wdmg': 4, 'bag': 0}
rb = db._attack(bb2, 'm1', [bb2])  # 비인접 far_m(m1) 지목
check("(b) 비인접 몹 지목 attack → too_far", rb['result'] == 'too_far')
check("(b) 인접몹(adj_m)은 몰래 안 맞음(HP 그대로)", adj_m.hp == 6)

# (c) goto 동료(b<char>) → 출구로 새지 않고 동료로 해석
dc = Dungeon(seed=2, n_monsters=0, n_traps=0)
c1 = spawn(dc, '1', [])
c2 = spawn(dc, '2', [c1])
rc = dc._set_order(c1, 'b2', [c1, c2])     # 동료 2 를 핑
check("(c) goto 동료 b2 → order 가 'exit' 아님(동료 해석)",
      c1.get('order') != 'exit' and rc['type'] == 'goto')
check("(c) goto 동료 b2 → 정상 경로/도착(no_path 아님)",
      rc['result'] in ('pathed', 'arrived'))

# ── 11) 리뷰 픽스 회귀 (F1 won동료 비가시 / F2 도달불가핑→explore / F4 방향 / 교착없음) ─
# (F1) 탈출(won) 동료는 sights['bots']에 안 뜬다(시야-온리·ascii_view와 일관)
df1 = Dungeon(seed=2, n_monsters=0, n_traps=0)
a1 = spawn(df1, '1', [])
a2 = spawn(df1, '2', [a1])
a2['won'] = True
a2['x'], a2['y'] = a1['x'], a1['y']           # 확실히 시야 안
check("(F1) 탈출(won) 동료는 sights['bots']에 안 보인다",
      all(o['id'] != 'b2' for o in df1.view(a1, [a1, a2])['sights']['bots']))

# (F2) 해석되나 도달불가(외길 봉쇄)한 핑 → explore 폴백(바보 재핑 no_path 아님)
dl2 = Dungeon(seed=5, w=20, h=7, n_monsters=0, n_traps=0)
for y in range(dl2.h):
    for x in range(dl2.w):
        dl2.grid[y][x] = '#'
cy2 = 3
for x in range(1, 19):
    dl2.grid[cy2][x] = '.'
dl2.features.clear(); dl2._next_fid = 0
dl2._exit_fid = dl2._add_feature('exit', '출구', 18, cy2)
dl2.monsters = [Monster(10, cy2, mid=0)]      # 외길 봉쇄
b6 = {'char': '1', 'x': 2, 'y': cy2, 'hp': 14, 'maxhp': 14, 'str': 3, 'dex': 0,
      'wdmg': 4, 'job': '전사', 'sex': '남', 'persona': '', 'bag': 0,
      'alive': True, 'won': False, 'order': None, 'path': [], 'aware_of': set()}
rf2 = dl2._set_order(b6, 'exit', [b6])         # 출구 valid 해석되나 도달불가
check("(F2) 도달불가 valid 핑 → explore 폴백(no_path 재핑 아님)",
      rf2['type'] == 'explore' and rf2['result'] != 'no_path' and b6.get('order') is not None)

# (F6) best_effort(지형거리): 몹이 외길 봉쇄 시 '봉쇄 직전'까지, 이미 직전이면 빈 경로(제자리)
dl3 = Dungeon(seed=5, w=20, h=7, n_monsters=0, n_traps=0)
for y in range(dl3.h):
    for x in range(dl3.w):
        dl3.grid[y][x] = '#'
cy3 = 3
for x in range(1, 19):
    dl3.grid[cy3][x] = '.'
dl3.features.clear(); dl3._next_fid = 0
dl3._exit_fid = dl3._add_feature('exit', '출구', 18, cy3)
dl3.monsters = [Monster(10, cy3, mid=0)]       # 몹이 외길 봉쇄(지형은 연결 → 봉쇄 직전으로 안내해야)
far_path = dl3.path_to(2, cy3, 18, cy3, [], best_effort=True)   # 멀리서 → 봉쇄몹 직전(9)까지
opt_path = dl3.path_to(9, cy3, 18, cy3, [], best_effort=True)   # 이미 몹 직전(최적) → []
check("(F6) best_effort: 먼 시작 → 봉쇄몹 직전(x=9)까지 진행",
      len(far_path) > 0 and far_path[-1] == (9, cy3))
check("(F6) best_effort: 시작이 이미 최적(봉쇄 직전)이면 빈 경로(제자리)", opt_path == [])
dl3.monsters = []
dl3.grid[cy3][10] = '#'                         # 이번엔 벽으로 진짜 단절
check("(F6b) best_effort: 벽으로 단절된 목표는 빈 경로(헛접근 안 함)",
      dl3.path_to(2, cy3, 18, cy3, [], best_effort=True) == [])

# (F4) explore 방향: 'N' 이 복합방위(NE/NW)의 N성분을 잡아 북쪽으로 (정확일치 무효 버그 회귀)
df4 = Dungeon(seed=7)
b7 = spawn(df4, '1', [])
seen7 = df4.visible_cells(b7['x'], b7['y'])
fresh7 = [w for w in df4._ways(b7['x'], b7['y'], seen7) if not w['visited']]
if any('N' in w['bearing'] for w in fresh7):
    df4._set_explore(b7, 'N', [b7])
    oy = int(b7['order'][1:].split(',')[1])
    check("(F4) explore 'N' → 북쪽(성분) 출입구 선택(oy < 봇 y)", oy < b7['y'])
else:
    check("(F4) seed7 에 북쪽 fresh way 존재", False)

# (교착없음) 몹·함정 *그대로* 둔 풀게임이 500틱 내 항상 종료(livelock 없음)
# (몹 대각셔틀·몹 외길봉쇄·벽단절을 모두 통과해야 — 과거 seed 24/28/30 교착 회귀 가드)
done = 0; trm = 50
for s in range(0, trm):
    dd = Dungeon(seed=s)
    bb = [spawn(dd, '1', [])]
    bb.append(spawn(dd, '2', bb))
    for _ in range(500):
        for b in bb:
            if not b['alive'] or b['won']:
                continue
            if b.get('order'):
                dd.step_order(b, bb)
            else:
                dd.act(b, dummy_brain(dd.view(b, bb), b['char']), bb)
        dd.monster_turn(bb)
        if all(b['won'] or not b['alive'] for b in bb):
            break
    if all(b['won'] or not b['alive'] for b in bb):
        done += 1
check("[50시드] 몹·함정 포함 풀게임 500틱 내 항상 종료(livelock 0)", done == trm)
print(f"        (종료 {done}/{trm})")

print("\n" + "=" * 44)
print("RESULT: " + ("ALL PASS" if C.failed == 0 else f"{C.failed} FAILED"))
import sys
sys.exit(1 if C.failed else 0)

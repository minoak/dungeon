# -*- coding: utf-8 -*-
"""스캐너·보고 이동(D19 정정판) 헤들리스 검증 — 16번째 게이트.
D19 정정(2026-07-15, 파트너 교정): "구조는 훤히"=과독 폐기 — 스캐너는 **시야에 들어온 격자의
번역기**다(전지성 제거: 구조 지식=지금 보이는 것+본 적 있는 것). 문(+)=격자의 실재 — 벽처럼
빛을 막고 바닥처럼 지나간다(개폐 상태 없는 항상 불투명 MVP). 정지 신호="새 오브젝트가 시야에
들어올 때"(벽·바닥 제외) 단일 원칙 — 처음 방 무조건 정지 폐지(다 본 방은 관통).
게이트:
  ① 기하 분류: 격자만 읽어 방(2×2 블록)/통로(폭1) 컴포넌트 — 출생기록 무관(from_ascii 다방 실증)
  ② 사전등록 미로 정합: 방3·문5·갈림길2·막다른곳3·공동 15×17·계단→공동 (EXP_D19_MAZE.md 의 지도)
  ③ 생성 맵 스윕: 전 바닥 구역 배정 · 문 타일 스탬프 실재·정합(측칸 직교 인접·구역 소속) ·
     scan=0 격자에 문 타일 전무(스위치 순수성) · 결정론(2회 스캔 동일)
  ④ 주소 어휘: '방 r0' 뭉개짐 치료(두 방=두 주소) · 장부(D17) 주소도 기하 구역 명의
  ⑤ 시야 제한 조회(전지성 제거): 다 못 본 방=크기·상대위치 없음(full=false+미답 방위) ·
     안 본 문 미등재 · 계단=내용물(07-12 정정 유지) — 확인 딱지 따라 수색→sighted→핑의 발견 서사
  ⑥ 문 핑 = 지나 들어서기: goto 문 → 반대쪽 칸(다음 공간) 도착 · 문 id는 goto 전용
  ⑦ 정지 신호 개정: 걷다 새 문/계단이 눈에 들면 sighted 정지(작정 파기) · 처음 방 진입은
     정지 사유 아님(entered 폐지) · 다 본 길은 끝까지 관통(무정지)
  ⑧ 탐색 종점: 종점=명사(아는 문·본 막다른 곳) · 빈 복도=끝까지 한 order ·
     개시 때 보이던 건 '새것' 아님(seen_keys 씨딩)
  ⑨ 시야-온리·출처 딱지: obs 에 좌표 무노출 · 미답 공간 한복판=문 어휘 없음 · 숨은 함정/매복 침묵
  ⑩ wire 전수성(그림≡문장): 8방위 슬롯 전부 발화(빈 방향='벽') · 실린 문·보이는 내용물이
     제 방위 슬롯 문장에 등장 — 다시드·전위치 스윕 · 문턱(문 위) 직렬화 무사고
  ⑪ 스위치: scan=False → obs·옵션·wire 구판 자구 그대로(D19 어휘 전무)
  ⑫ [30시드] scan-on 풀게임 항상 종료 + [8시드] 결정론(구역·목격 장부 서명 포함)
  ⑬ 문 광학: 문 너머 불가시 · 문 위=양쪽 가시 · 문턱에 올라서는 순간 sighted(다음 공간의 개시)
(기존 verify 15종은 별도 실행 — scan 기본 꺼짐이라 무수정 통과가 전제.)
"""
import json
import os

os.environ["DUNGEON_BESTIARY_FILE"] = ""   # 도감 영속 차단(게이트 격리 원칙)

import brains
import dungeon_gm as G
from dungeon_gm import Dungeon, spawn, dummy_brain, new_ledger

HERE = os.path.dirname(os.path.abspath(__file__))


class C:
    failed = 0


def check(name, cond):
    print(("  OK   " if cond else " FAIL  ") + name)
    if not cond:
        C.failed += 1


def mkbot(char, x, y, dex=0, search_r=1, job='전사', ledger=False):
    b = {'char': char, 'x': x, 'y': y, 'hp': 14, 'maxhp': 14,
         'str': 3, 'dex': dex, 'wdmg': 4, 'stealth': 0,
         'search_r': search_r, 'job': job, 'sex': '남', 'persona': '', 'bag': 0,
         'alive': True, 'won': False, 'order': None, 'path': [],
         'aware_of': set(), 'plan': []}
    if ledger:
        b['ledger'] = new_ledger()
    return b


def walk_out(d, b, bots, limit=60):
    r = None
    for _ in range(limit):
        if not b.get('order'):
            break
        r = d.step_order(b, bots)
    return r


def go_until(d, b, bots, target, want, limit=25):
    """핑을 거듭 던져 목표 결과까지 — 새 목격 sighted 정지가 끼어도 다시 잇는다(재결정 모사)."""
    last = None
    for _ in range(limit):
        d.view(b, bots)
        d.act(b, {'type': 'goto', 'target': target}, bots)
        last = walk_out(d, b, bots, limit=200)
        if last and last['result'] == want:
            return last
    return last


KR8 = {"N": "북쪽", "NE": "북동쪽", "E": "동쪽", "SE": "남동쪽",
       "S": "남쪽", "SW": "남서쪽", "W": "서쪽", "NW": "북서쪽"}

# ───────────────────── ① 기하 분류(격자만 읽는다) ─────────────────────
print("── ① 기하 분류(from_ascii 다방)")
rows = ['############',
        '#1..=..#.~.#',
        '#......#...#',
        '#.........>#',
        '############']
d, starts = G.Dungeon.from_ascii(rows, seed=7, scan=True)
rooms = [z for z in d.zones.values() if z.kind == '방']
corrs = [z for z in d.zones.values() if z.kind == '통로']
check("① 손그림 맵에서 방 2 + 통로 1 (출생기록은 단일 방이었다)",
      len(rooms) == 2 and len(corrs) == 1)
check("① 전 바닥 칸이 정확히 한 구역에 배정",
      len(d.zone_at) == sum(1 for y in range(d.h) for x in range(d.w)
                            if d.grid[y][x] == G.FLOOR))
check("① 통로=폭1 외길(2×2 블록 밖), 방=블록 소속",
      all(len(z.cells) >= 4 for z in rooms) and corrs[0].cells == frozenset({(7, 3)}))
chest = next(f for f in d.features.values() if f.type == 'chest')
fount = next(f for f in d.features.values() if f.type == 'fountain')
check("④ 두 방 = 두 주소(단일 r0 뭉개짐 치료)",
      d._zone_label(chest.x, chest.y) == '방 r0'
      and d._zone_label(fount.x, fount.y) == '방 r1'
      and d._zone_label(7, 3).startswith('통로 c'))

# ───────────────────── ② 사전등록 미로 정합 ─────────────────────
print("── ② 사전등록 미로(EXP_D19_MAZE.md)")
spec = json.load(open(os.path.join(HERE, 'scenarios', '미로탈출.json'), encoding='utf-8'))
dm, stm = G.Dungeon.from_ascii(spec['map'], seed=7, scan=True)
mrooms = [z for z in dm.zones.values() if z.kind == '방']
juncs = sum(len(z.junctions) for z in dm.zones.values())
deads = sum(len(z.deadends) for z in dm.zones.values())
cav = max(mrooms, key=lambda z: len(z.cells))
check("② 방 3 · 문 5 · 갈림길 2 · 막다른 곳 3",
      len(mrooms) == 3 and len(dm.doors) == 5 and juncs == 2 and deads == 3)
check("② 공동 = 15×17 (시야 5 보다 큰 방)", (cav.w, cav.h) == (15, 17))
check("② 계단은 공동 안(수색이 정복할 미지)", dm.zone_at[dm.exit] == cav.id)
small = next(z for z in mrooms if z is not cav and len(z.doors) == 3)
check("② 작은 방 = 문 3(사전등록 문구 그대로)", small is not None)

# ───────────────────── ③ 생성 맵 스윕 + 문 타일 + 결정론 ─────────────────────
print("── ③ 생성 맵 스윕(격자·문 타일 불변식)")
ok_cover = ok_door = ok_det = ok_pure = True
stamped = 0
for s in range(12):
    dz = Dungeon(seed=s, scan=True)
    floors = {(x, y) for y in range(dz.h) for x in range(dz.w)
              if dz.grid[y][x] == G.FLOOR}
    if set(dz.zone_at) != floors:
        ok_cover = False
    for door in dz.doors.values():
        if door.cell:                           # 문 타일: 격자 실재 + 측칸=문과 직교 인접·구역 정합
            stamped += 1
            px, py = door.cell
            if dz.grid[py][px] != G.DOOR:
                ok_door = False
            for zn, sc in door.sides.items():
                if abs(sc[0] - px) + abs(sc[1] - py) != 1 or dz.zone_at.get(sc) != zn:
                    ok_door = False
        else:                                   # 문 없는 트임: 문턱 쌍 직교 인접(지나기 성립)
            a, b = door.sides[door.zones[0]], door.sides[door.zones[1]]
            if abs(a[0] - b[0]) + abs(a[1] - b[1]) != 1:
                ok_door = False
            if (dz.zone_at[a] != door.zones[0] or dz.zone_at[b] != door.zones[1]):
                ok_door = False
    d0_ = Dungeon(seed=s)                       # 스위치 순수성 — scan=0 세계에 문 타일이 없다
    if any(d0_.grid[y][x] == G.DOOR for y in range(d0_.h) for x in range(d0_.w)):
        ok_pure = False
    dz2 = Dungeon(seed=s, scan=True)
    if ({z: sorted(dz.zones[z].cells) for z in dz.zones}
            != {z: sorted(dz2.zones[z].cells) for z in dz2.zones}
            or sorted(dz.doors) != sorted(dz2.doors)
            or {k: v.cell for k, v in dz.doors.items()}
            != {k: v.cell for k, v in dz2.doors.items()}):
        ok_det = False
check("③ [12시드] 전 바닥 배정(빠짐·중복 없음, 문 타일은 구역 밖)", ok_cover)
check("③ [12시드] 문 타일 스탬프 실재(%d개) + 측칸·트임 정합" % stamped,
      stamped > 0 and ok_door)
check("③ [12시드] scan=0 격자에 문 타일 전무(스위치 순수성)", ok_pure)
check("③ [12시드] 스캔 결정론(같은 격자=같은 구역·문·문 타일)", ok_det)

# ───────────────────── ④ 장부(D17) 주소 통합 ─────────────────────
print("── ④ 장부 주소 = 기하 구역 명의")
d4, st4 = G.Dungeon.from_ascii(rows, seed=7, scan=True)
d4.turn = 3
b4 = mkbot('1', *st4['1'], ledger=True)
d4.view(b4, [b4])
chest4 = next('f%d' % f.id for f in d4.features.values() if f.type == 'chest')
check("④ 보이는 상자 장부 등재 주소='방 r0'(기하)",
      b4['ledger']['statics'].get(chest4, {}).get('zone') == '방 r0')
check("④ 방문 구역 = 기하 id 열쇠", 'r0' in b4['ledger']['zones']
      and b4['ledger']['zones']['r0']['id'] == 'r0')

# ───────────────────── ⑤ 시야 제한 조회(전지성 제거) ─────────────────────
print("── ⑤ 시야 제한 조회 — 네 눈이 본 만큼이 네가 아는 만큼")
dm5, _ = G.Dungeon.from_ascii(spec['map'], seed=7, scan=True)
cav5 = max((z for z in dm5.zones.values() if z.kind == '방'), key=lambda z: len(z.cells))
west = dm5.doors['d3'].sides[cav5.id]           # 공동의 서쪽 입구 칸(문턱)
b5 = mkbot('1', *west)
obs5 = dm5.view(b5, [b5])
z5 = obs5['zone']
check("⑤ 다 못 본 방 = 크기·상대위치 없음 + full=false + 미답 방위(todo)",
      z5['kind'] == '방' and 'size' not in z5 and 'at' not in z5
      and z5['checked'].get('full') is False and z5['checked'].get('todo') in KR8)
check("⑤ 문 어휘 = 눈에 든 것만(doors_seen 명의 — 미목격 문 실증은 ⑨ 한복판 봇)",
      len(z5['doors']) >= 1
      and all(dr['id'] in b5['doors_seen'] for dr in z5['doors']))
check("⑤ 계단=내용물: 안 보이면 obs.zone·옵션·brains 타겟 어디에도 없다(07-12 정정 유지)",
      obs5['sights']['exit'] is None and 'exit' not in z5
      and not any(o.get('target') == 'exit' for o in obs5['options'])
      and 'exit' not in brains._valid_targets(obs5))
# 공동 치료의 몸통 = 근거 있는 수색: 확인 딱지의 미답 방위(todo)를 따라 훑는다 — 계단이
# '눈에 드는' 순간 sighted 로 멈추고, 그때부터 핑이 된다(발견의 순간이 살아남는다).
b5['zones_entered'].add('c1')                   # 서쪽 통로에서 걸어들어온 셈(들어온 문=가 본 곳)
sighted = False
guard = 0
while guard < 800 and not sighted:
    guard += 1
    if not b5.get('order'):
        ob = dm5.view(b5, [b5])
        todo = ((ob.get('zone') or {}).get('checked') or {}).get('todo')
        dm5.act(b5, {'type': 'explore', 'target': todo}, [b5])
        if not b5.get('order'):
            break
    w = dm5.step_order(b5, [b5])
    if (w and w['result'] == 'sighted'
            and any(x.get('kind') == 'exit' for x in w.get('seen', []))):
        sighted = True
check("⑤ 확인 딱지 따라 수색 → 계단이 시야에 들면 sighted 정지(발견의 순간)", sighted)
obs5b = dm5.view(b5, [b5])
check("⑤ 이제 보이는 계단 = sights·타겟에 등장(보일 때만 규칙 그대로)",
      obs5b['sights']['exit'] is not None and 'exit' in brains._valid_targets(obs5b))
w5 = go_until(dm5, b5, [b5], 'exit', 'at_exit')
check("⑤ 발견 후 핑 → 계단 앞(at_exit)", w5 is not None and w5['result'] == 'at_exit')

# ───────────────────── ⑥ 문 핑 = 지나 들어서기 ─────────────────────
print("── ⑥ 문 핑(지나 들어서기)")
d6, st6 = G.Dungeon.from_ascii(rows, seed=7, scan=True)
b6 = mkbot('1', *st6['1'])
obs6 = d6.view(b6, [b6])
door6 = next(o for o in obs6['options'] if o['type'] == 'goto'
             and str(o.get('target', '')).startswith('d'))
check("⑥ 아는 문이 이동 옵션에 있다(1:1 — 문 어휘의 리모컨 편입)", door6 is not None)
check("⑥ 문 id 는 _valid_targets(goto)에, interact 엔 없음",
      door6['target'] in brains._valid_targets(obs6)
      and door6['target'] not in brains._valid_targets(obs6, verb='interact'))
w6 = None                                       # 위치 기준 루프 — 도중 sighted 정지는 재결정 모사로
for _ in range(10):                             #   다시 잇는다(같은 문 재핑=반대쪽 해석이라, 건넌
    if d6.zone_at.get((b6['x'], b6['y'])) == 'c0':   # 뒤 재핑하면 셔틀 — 관찰 카드 그대로. 게이트는
        break                                   #   '건너기 전까지만' 재핑한다)
    d6.view(b6, [b6])
    d6.act(b6, {'type': 'goto', 'target': door6['target']}, [b6])
    w6 = walk_out(d6, b6, [b6])
check("⑥ 문 통과 → 문턱이 아니라 '다음 공간'(통로)에 들어선 채 재결정",
      d6.zone_at.get((b6['x'], b6['y'])) == 'c0')
obs6b = d6.view(b6, [b6])                       # 통로에서 건너방 문으로 — 새 방도 정지 없이 들어선다
door6b = next(o for o in obs6b['options'] if o['type'] == 'goto'
              and str(o.get('target', '')).startswith('d')
              and '가 본 곳' not in o['label'])
w6b = None
for _ in range(10):
    if d6.zone_at.get((b6['x'], b6['y'])) == 'r1':
        break
    d6.view(b6, [b6])
    d6.act(b6, {'type': 'goto', 'target': door6b['target']}, [b6])
    w6b = walk_out(d6, b6, [b6])
check("⑥ 문 너머 처음 방 = 들어선 채 완료(entered 정지 폐지 — 볼 게 있으면 sighted 가 알린다)",
      d6.zone_at.get((b6['x'], b6['y'])) == 'r1'
      and not any(r and r.get('result') == 'entered' for r in (w6, w6b)))

# ───────────────────── ⑦ 정지 신호 개정(새 오브젝트 목격) ─────────────────────
print("── ⑦ 정지 신호 = 새 오브젝트가 시야에 들 때(벽 제외)")
rows7 = ['###################',
         '#...###########...#',
         '#.1.' + '.' * 11 + '.>.#',
         '#...###########...#',
         '###################']
d7, st7 = G.Dungeon.from_ascii(rows7, seed=7, scan=True)
b7 = mkbot('1', *st7['1'])
d7.view(b7, [b7])
check("⑦ 스폰에서 보이던 문 = seen_keys 씨딩(개시 때 보인 건 '새것' 아님)",
      'd0' in b7.get('seen_keys', set()))
b7['plan'] = [{'type': 'search'}]               # 작정을 품고 걷는다 — 정지가 찢어야 한다
d7.act(b7, {'type': 'goto', 'target': 'exit'}, [b7])   # 엔진 해석은 무조건 — 여기선 물리(정지)만
results7 = []
w7 = walk_out(d7, b7, [b7])
results7.append(w7)
check("⑦ 걷다 새 문이 눈에 들면 sighted 정지 + 남은 작정 파기",
      w7 is not None and w7['result'] == 'sighted'
      and any(x.get('kind') == 'door' for x in w7['seen'])
      and b7['plan'] == [] and b7['order'] is None)
d7.view(b7, [b7])
d7.act(b7, {'type': 'goto', 'target': 'exit'}, [b7])
w7b = walk_out(d7, b7, [b7])
results7.append(w7b)
check("⑦ 다시 걷다 계단이 눈에 들면 sighted 정지(멈춰 묻는다)",
      w7b is not None and w7b['result'] == 'sighted'
      and any(x.get('kind') == 'exit' for x in w7b['seen']))
d7.view(b7, [b7])
d7.act(b7, {'type': 'goto', 'target': 'exit'}, [b7])
w7c = walk_out(d7, b7, [b7])
results7.append(w7c)
check("⑦ 처음 방 진입은 정지 사유 아님 — 곧장 계단까지(entered 폐지)",
      w7c is not None and w7c['result'] == 'at_exit'
      and not any(r and r['result'] == 'entered' for r in results7))
w7d = go_until(d7, b7, [b7], 'd0', 'arrived')   # 되짚기: 전부 본 길 — 관통(무정지 한 order)
check("⑦ 다 본 길 되짚기 = 정지 없이 끝까지 관통(볼 게 없으면 멈출 이유도 없다)",
      w7d is not None and w7d['result'] == 'arrived'
      and d7.zone_at[(b7['x'], b7['y'])] == 'r0')

# ───────────────────── ⑧ 탐색 종점(명사 = 아는 문·본 막다른 곳) ─────────────────────
print("── ⑧ 탐색 종점")
rows8 = ['##########',
         '#...######',
         '#.1......#',
         '#>..######',
         '##########']
d8, st8 = G.Dungeon.from_ascii(rows8, seed=7, scan=True)
b8 = mkbot('1', *st8['1'])
d8.view(b8, [b8])
r8 = d8.act(b8, {'type': 'explore', 'target': 'E'}, [b8])   # 방의 탐색 종점 = 아는 문(명사)
w8a = walk_out(d8, b8, [b8])
check("⑧ 방에서 탐색 = 문을 지나 다음 공간까지(시야 가장자리 정지 폐기)",
      r8['result'] == 'pathed' and d8.zone_at[(b8['x'], b8['y'])] == 'c0')
d8.view(b8, [b8])
steps8 = 0
d8.act(b8, {'type': 'explore', 'target': 'E'}, [b8])        # 통로의 탐색 종점 = 본 막다른 곳
w8 = None
while b8.get('order') and steps8 < 60:
    w8 = d8.step_order(b8, [b8])
    steps8 += 1
check("⑧ 빈 복도 = 막다른 곳까지 한 order 로 끝까지(중간 재결정 없음)",
      w8 is not None and w8['result'] == 'arrived'
      and (b8['x'], b8['y']) == (8, 2) and steps8 == 4)
check("⑧ 개시 때 이미 보이던 계단은 '새것'이 아니다(두 leg 모두 계단 정지 없음)",
      d8.exit == (1, 3))                        # 계단이 처음부터 시야 안이었는데 완주했다

# ───────────────────── ⑨ 시야-온리·출처 딱지 ─────────────────────
print("── ⑨ 시야-온리·출처 딱지")
no_xy = all('x' not in e and 'y' not in e for e in z5['doors'])
check("⑨ 구조 obs 에 좌표 무노출(방위·거리·딱지뿐)", no_xy)
check("⑨ 문 항목 스키마 고정({id,bearing,dist,seen,been})",
      all(set(dr) == {'id', 'bearing', 'dist', 'seen', 'been'} for dr in z5['doors']))
bc = mkbot('1', cav5.x + cav5.w // 2, cav5.y + cav5.h // 2)   # 공동 한복판(문에서 먼) 낯선 봇
obsc = dm5.view(bc, [bc])
check("⑨ 미답 공간 한복판 = 문 어휘 없음·크기 모름(전지성 제거 실증)",
      obsc['zone']['doors'] == [] and 'size' not in obsc['zone']
      and obsc['zone']['checked'].get('full') is False)
rows9 = ['#######',
         '#1.s^>#',
         '#######']
d10, st10 = G.Dungeon.from_ascii(
    rows9, seed=7, monsters={'s': {'kind': '그림자거미', 'concealed': True}},
    traps=[{'kind': 'spike', 'hidden': True}], scan=True)
b10 = mkbot('1', *st10['1'])
obs10 = d10.view(b10, [b10])
w10 = brains._wire(obs10)
check("⑨ 숨은 함정·매복몹 = obs·wire 침묵(발각 전엔 없다)",
      obs10['sights']['traps'] == [] and obs10['sights']['monsters'] == []
      and '거미' not in w10 and '함정' not in w10.split('## 판단')[0])
d10.traps[0].hidden = False                     # 발각(수색 성공의 결과만 재현)
obs10b = d10.view(b10, [b10])
w10b = brains._wire(obs10b)
check("⑨ 발각된 함정 = sights.traps + wire (발각됨) 딱지",
      len(obs10b['sights']['traps']) == 1 and '발각됨' in w10b)

# ───────────────────── ⑩ wire 전수성(그림≡문장) ─────────────────────
print("── ⑩ wire 전수성 — 다시드·전위치 스윕")
views = 0
bad_slot = bad_door = bad_mon = bad_wall = 0
for s in range(6):
    dz = Dungeon(seed=s, n_monsters=2, n_traps=2, n_lurkers=0, scan=True)
    cells = sorted(dz.zone_at)
    for i, (x, y) in enumerate(cells):
        if i % 3:
            continue                            # 1/3 표본(계산량 조절 — 그래도 수백 뷰)
        if dz.monster_at(x, y) or dz.feature_at(x, y):
            continue
        bb = mkbot('9', x, y)
        obs = dz.view(bb, [bb])
        msg = brains._wire(obs)
        views += 1
        if any(("- %s:" % KR8[k]) not in msg for k in KR8):
            bad_slot += 1                       # 8방위 슬롯은 빠짐없이 발화(빈 방향도)
        zz = obs['zone']
        for dr in zz['doors']:
            if dr['dist'] == 0 or dr['bearing'] == '-':
                if dr['id'] not in msg:
                    bad_door += 1
                continue
            line = next((l for l in msg.splitlines()
                         if l.startswith("- %s:" % KR8.get(dr['bearing'], '?'))), '')
            if dr['id'] not in line:
                bad_door += 1                   # 실린 문은 제 방위 슬롯 문장에 등장해야 한다
        for m in obs['sights']['monsters']:
            if m['dist'] > 0 and m['id'] not in msg:
                bad_mon += 1
        for k in KR8:
            line = next((l for l in msg.splitlines()
                         if l.startswith("- %s:" % KR8[k])), '')
            if line.endswith('벽') and any(
                    dr['bearing'] == k and dr['dist'] > 0 for dr in zz['doors']):
                bad_wall += 1                   # 문이 실린 방위가 '벽'으로 발화되면 계약 위반
check("⑩ [%d뷰] 8방위 슬롯 전부 발화" % views, views > 200 and bad_slot == 0)
check("⑩ 실린 문이 제 방위 슬롯에 등장(그림≡문장)", bad_door == 0)
check("⑩ 보이는 몹 전부 문장에 등장", bad_mon == 0)
check("⑩ '벽' 발화는 정말 빈 방향뿐", bad_wall == 0)
dz10 = Dungeon(seed=7, scan=True)               # 문턱(문 타일 위) 직렬화 무사고
dcell = next(v.cell for v in dz10.doors.values() if v.cell)
bt = mkbot('9', *dcell)
obst = dz10.view(bt, [bt])
check("⑩ 문턱(문 위) = zone kind '문턱' + wire 무사고",
      obst['zone']['kind'] == '문턱' and '문턱' in brains._wire(obst))

# ───────────────────── ⑪ 스위치(scan=False = 구판 자구) ─────────────────────
print("── ⑪ 스위치")
d11, st11 = G.Dungeon.from_ascii(rows, seed=7)              # scan 기본 꺼짐
b11 = mkbot('1', *st11['1'])
obs11 = d11.view(b11, [b11])
check("⑪ scan 꺼짐 → 구조 어휘 전무(zone·traps·문 옵션 없음)",
      'zone' not in obs11 and 'traps' not in obs11['sights']
      and not any(str(o.get('target', '')).startswith('d') for o in obs11['options']))
check("⑪ scan 꺼짐 → wire 는 구판 구성(지금 보이는 것)",
      '## 지금 보이는 것' in brains._wire(obs11)
      and '## 장소' not in brains._wire(obs11))
check("⑪ scan 켬 → wire 는 트리(장소 절)", '## 장소' in w10b)

# ───────────────────── ⑫ 풀게임 종결·결정론 ─────────────────────
print("── ⑫ scan-on 풀게임(더미) 종결·결정론")


def play(seed, ticks=600, sig=False):
    dd = Dungeon(seed=seed, scan=True)
    bb = [spawn(dd, '1', [])]
    bb.append(spawn(dd, '2', bb))
    for b in bb:
        b['ledger'] = new_ledger()              # 러너와 같은 조건(장부+스캔 켬)
    done = False
    for t in range(1, ticks + 1):
        dd.turn = t
        for b in bb:
            if not b['alive'] or b['won']:
                continue
            if b.get('order'):
                dd.step_order(b, bb)
            else:
                dd.act(b, dummy_brain(dd.view(b, bb), b['char']), bb)
        dd.monster_turn(bb)
        if all(b['won'] or not b['alive'] for b in bb):
            done = True
            break
    if sig:
        return (tuple((b['x'], b['y'], b['hp'], b['won'], b['bag']) for b in bb),
                tuple((m.x, m.y, m.hp, m.alive, m.state) for m in dd.monsters),
                tuple(tuple(sorted(b.get('zones_entered', set()))) for b in bb),
                tuple(tuple(sorted(b.get('doors_seen', set()))) for b in bb),
                tuple(tuple(sorted(b.get('seen_keys', set()))) for b in bb))
    return done


done_n = sum(play(s) for s in range(30))
check("⑫ [30시드] scan-on 풀게임 항상 종료(목격 정지가 교착을 만들지 않는다)",
      done_n == 30)
bad = sum(1 for s in range(8) if play(s, sig=True) != play(s, sig=True))
check("⑫ [8시드] 결정론 — 같은 시드 = 같은 판(구역·문·목격 장부 서명 포함)", bad == 0)

# ───────────────────── ⑬ 문 광학(불투명 문) ─────────────────────
print("── ⑬ 문 광학 — 벽처럼 막고 바닥처럼 지나간다")
dr13 = next(v for v in dz10.doors.values() if v.cell)
sa, sb = dr13.sides[dr13.zones[0]], dr13.sides[dr13.zones[1]]
va = dz10.visible_cells(*sa)
vc = dz10.visible_cells(*dr13.cell)
check("⑬ 문 너머 불가시(문 자체는 보인다) · 문 위=양쪽 가시",
      sb not in va and dr13.cell in va and sa in vc and sb in vc)
check("⑬ 문 통행 가능(BFS·봇·몹 공통 지형)",
      dz10.walkable(dr13.cell[0], dr13.cell[1], [])
      and dz10._monster_walkable(dr13.cell[0], dr13.cell[1], []))
rows13 = ['#######',
          '#1.+.>#',
          '#######']
d13, st13 = G.Dungeon.from_ascii(rows13, seed=7, scan=True)
b13 = mkbot('1', *st13['1'])
obs13 = d13.view(b13, [b13])
check("⑬ 손그림 문(+)도 광학 차단 — 계단이 문 뒤라 안 보인다",
      obs13['sights']['exit'] is None
      and any(str(o.get('target', '')).startswith('d') for o in obs13['options']))
d13.act(b13, {'type': 'goto',
              'target': next(o['target'] for o in obs13['options']
                             if str(o.get('target', '')).startswith('d'))}, [b13])
w13 = walk_out(d13, b13, [b13])
check("⑬ 문턱에 올라서는 순간 다음 공간이 열린다 — 그 자리서 sighted(계단 발견)",
      w13 is not None and w13['result'] == 'sighted'
      and any(x.get('kind') == 'exit' for x in w13['seen'])
      and (b13['x'], b13['y']) == (3, 1)
      and d13.view(b13, [b13])['zone']['kind'] == '문턱')
w13b = go_until(d13, b13, [b13], 'exit', 'at_exit')
check("⑬ 발견 후 핑 → 계단 앞(at_exit)", w13b is not None and w13b['result'] == 'at_exit')

# ───────────────────── ⑭ 정직한 탐색 폴백(D19 개정 2026-09-06) — 안 본 계단으로 걷지 않는다 ─────────────────────
print("── ⑭ 탐색 폴백 — 걷는 곳은 캐릭터가 아는 곳뿐")
ROWS14 = ["###############",
          "#1...+....+...#",
          "#....#....#..>#",
          "###############"]


def scene14():
    d, st = G.Dungeon.from_ascii(ROWS14, seed=7, scan=True)
    b = mkbot('1', *st['1'], ledger=True)
    zA = d.zone_at[(2, 1)]; zB = d.zone_at[(7, 1)]; zC = d.zone_at[(12, 1)]
    dAB = next(k for k, dr in d.doors.items() if set(dr.zones) == {zA, zB})
    dBC = next(k for k, dr in d.doors.items() if set(dr.zones) == {zB, zC})
    floor = set(d.zones[zA].cells) | set(d.zones[zB].cells) | {d.doors[dAB].cell, d.doors[dBC].cell}
    seen = set()
    for (x, y) in floor:                            # A·B 를 걸어 다닌 봇의 평생 시야(벽 포함)
        seen |= set(d.visible_cells(x, y))
    b['seen_cells'] = seen
    b['zone_seen'] = {zA: set(d.zones[zA].cells), zB: set(d.zones[zB].cells)}
    b['zones_entered'] = {zA, zB}                   # A·B 에 들어가 봤다
    b['doors_seen'] = {dAB, dBC}                    # 두 문을 봤다(C 너머는 안 가 봄)
    b['seen_keys'] = set()                          # 계단은 본 적 없다
    return d, b, zC, dBC


d14, b14, zC, dBC = scene14()
r = d14._set_explore(b14, None, [b14])
check("⑭ 계단 미목격·새 길 없음 → 기억 속 안 가 본 문(d%s) 건너편으로(door 병기, to_exit 없음)" % dBC[1:],
      r['result'] == 'pathed' and r.get('door') == dBC and not r.get('to_exit')
      and b14['order'] == '@%d,%d' % d14.doors[dBC].sides[zC])
d14, b14, zC, dBC = scene14()
b14['seen_keys'] = {'exit'}                          # 계단을 본 적 있다 → 기억의 계단
r = d14._set_explore(b14, None, [b14])
check("⑭ 계단을 본 적 있으면 기억의 계단행(to_exit+remembered)",
      r['result'] == 'pathed' and r.get('to_exit') is True and r.get('remembered') is True)
d14, b14, zC, dBC = scene14()
b14['zones_entered'].add(zC)                         # 문 너머도 가 봤지만 B 의 구석 두 칸은 못 봤다
b14['seen_cells'] -= {(9, 2), (8, 2)}
r = d14._set_explore(b14, None, [b14])
check("⑭ 문은 다 가 봤고 계단 미목격 → 기억 속 안 본 가장자리로(frontier)",
      r['result'] == 'pathed' and r.get('frontier') is True and b14['order'] in ('@9,1', '@8,1', '@7,2'))
d14, b14, zC, dBC = scene14()
b14['zones_entered'].add(zC)                         # 문 너머도 다 가 봤고 본 칸 가장자리도 없다(계단만 못 봄 — 단위 장면:
b14['seen_cells'] = {(x, y) for y in range(d14.h) for x in range(d14.w)}   # 실 맵에선 '다 봤는데 계단만 못 봄'은 없다)
r = d14._set_explore(b14, None, [b14])
check("⑭ 전부 소진 → no_path+exhausted·order 파기(안 본 계단으로 안 걷는다)",
      r['result'] == 'no_path' and r.get('exhausted') is True and b14['order'] is None)
o = d14.view(b14, [b14])
check("⑭ 소진 시 '탐색' 어휘 없음 + obs.exhausted", not any(x['type'] == 'explore' for x in o['options'])
      and o.get('exhausted') is True)
w = brains._wire(o)
check("⑭ 렌더 '새 길이 없다'(관찰 사실만, 물음표 0)", "새 길이 없다" in w and "?" not in
      [ln for ln in w.splitlines() if "새 길이 없다" in ln][0])
check("⑭ 자기 관측 문장(exhausted)", "기억 속에도 안 가 본 문이 없다" in brains._last_prose(
    {'type': 'explore', 'result': 'no_path', 'target': 'auto', 'exhausted': True}))
d14, b14, zC, dBC = scene14()
o = d14.view(b14, [b14])
check("⑭ 갈 곳(기억 속 문)이 있으면 '탐색' 어휘 있음", any(x['type'] == 'explore' for x in o['options'])
      and 'exhausted' not in o)
dm, stm = G.Dungeon.from_ascii(["######", "#1..>#", "######"], seed=7, scan=False)
bm = mkbot('1', *stm['1'])                           # 기억 장치 없는 봇(장부·스캔 둘 다 없음)
dm.visited.update({(1, 1), (2, 1), (3, 1), (4, 1)})   # 발자국으로 '새 길' 소거(구판 프런티어 기준 — 계단 칸까지)
r = dm._set_explore(bm, None, [bm])
check("⑭ scan 없는 판(평생 시야 장부 없음)은 구 폴백 유지(to_exit, remembered 없음)",
      r.get('to_exit') is True and not r.get('remembered'))


def once14():
    d, b, zC, dBC = scene14()
    r = d._set_explore(b, None, [b])
    return (r, b['order'])


check("⑭ 결정론", once14() == once14())

print("=" * 44)
if C.failed:
    print("RESULT: %d FAIL" % C.failed)
    raise SystemExit(1)
print("RESULT: ALL PASS — 스캐너·보고 이동(D19 정정판) 계약 건전")

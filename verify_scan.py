# -*- coding: utf-8 -*-
"""스캐너·보고 이동(D19) 헤들리스 검증 — 16번째 게이트.
D19: "격자의 구조는 엔진이 읽고, 갈 곳의 선택은 에이전트가" + 헌법 두 전제(그림≡문장·의도≡이동).
게이트:
  ① 기하 분류: 격자만 읽어 방(2×2 블록)/통로(폭1) 컴포넌트 — 출생기록 무관(from_ascii 다방 실증)
  ② 사전등록 미로 정합: 방3·문5·갈림길2·막다른곳3·공동 15×17·계단→공동 (EXP_D19_MAZE.md 의 지도)
  ③ 생성 맵 스윕: 전 바닥 구역 배정 · 문의 양쪽 문턱은 서로 직교 인접 · 결정론(2회 스캔 동일)
  ④ 주소 어휘: '방 r0' 뭉개짐 치료(두 방=두 주소) · 장부(D17) 주소도 기하 구역 명의
  ⑤ 구조는 훤히: 공동 진입 — 크기·상대위치·안 보이는 계단(구조 유래)·goto 핑 → 도착
  ⑥ 문 핑 = 지나 들어서기: goto 문 → 반대쪽 칸(다음 공간) 도착
  ⑦ 처음 방 정지: 첫 진입=entered(작정 파기) · 재진입=통과 · 통로 진입=무정지 · 스폰 방=무정지
  ⑧ 탐색 종점: 빈 복도=끝까지 한 order · 새 내용물 시야 등장=sighted 정지 (개시 때 보인 건 제외)
  ⑨ 시야-온리·출처 딱지: obs 에 좌표 무노출 · 안 보이는 문 seen=false · 숨은 함정/매복 침묵
  ⑩ wire 전수성(그림≡문장): 8방위 슬롯 전부 발화(빈 방향='벽') · 모든 문·보이는 내용물이
     제 방위 슬롯 문장에 등장 — 다시드·전위치 스윕
  ⑪ 스위치: scan=False → obs·옵션·wire 구판 자구 그대로(D19 어휘 전무)
  ⑫ [30시드] scan-on 풀게임 항상 종료 + [8시드] 결정론(zones_entered 서명 포함)
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
check("② 계단은 공동 안(구조 조회의 치료 대상)", dm.zone_at[dm.exit] == cav.id)
small = next(z for z in mrooms if z is not cav and len(z.doors) == 3)
check("② 작은 방 = 문 3(사전등록 문구 그대로)", small is not None)

# ───────────────────── ③ 생성 맵 스윕 + 결정론 ─────────────────────
print("── ③ 생성 맵 스윕(격자·문 불변식)")
ok_cover = ok_door = ok_det = True
for s in range(12):
    dz = Dungeon(seed=s, scan=True)
    floors = {(x, y) for y in range(dz.h) for x in range(dz.w)
              if dz.grid[y][x] == G.FLOOR}
    if set(dz.zone_at) != floors:
        ok_cover = False
    for door in dz.doors.values():
        a, b = door.sides[door.zones[0]], door.sides[door.zones[1]]
        if abs(a[0] - b[0]) + abs(a[1] - b[1]) != 1:
            ok_door = False                     # 문턱 대표칸 쌍은 직교 인접이어야 '지나기'가 성립
        if (dz.zone_at[a] != door.zones[0] or dz.zone_at[b] != door.zones[1]):
            ok_door = False
    dz2 = Dungeon(seed=s, scan=True)
    if ({z: sorted(dz.zones[z].cells) for z in dz.zones}
            != {z: sorted(dz2.zones[z].cells) for z in dz2.zones}
            or sorted(dz.doors) != sorted(dz2.doors)):
        ok_det = False
check("③ [12시드] 전 바닥 배정(빠짐·중복 없음)", ok_cover)
check("③ [12시드] 문턱 쌍=직교 인접 + 구역 소속 정합", ok_door)
check("③ [12시드] 스캔 결정론(같은 격자=같은 구역·문)", ok_det)

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

# ───────────────────── ⑤ 구조는 훤히(공동 치료) ─────────────────────
print("── ⑤ 구조는 훤히, 내용물은 시야대로")
dm5, _ = G.Dungeon.from_ascii(spec['map'], seed=7, scan=True)
west = dm5.doors['d3'].sides[cav.id]            # 공동의 서쪽 입구 칸(문턱)
b5 = mkbot('1', *west)
obs5 = dm5.view(b5, [b5])
z5 = obs5['zone']
check("⑤ 들어선 공간의 뼈대: 종류·크기·상대 위치", z5['kind'] == '방'
      and z5['size'] == [15, 17] and z5.get('at') == '서쪽 가장자리')
check("⑤ 계단이 안 보이는데(내용물 광학) 구조로는 안다",
      obs5['sights']['exit'] is None and isinstance(z5.get('exit'), dict)
      and set(z5['exit']) == {'bearing', 'dist'})
opt5 = [o for o in obs5['options'] if o['type'] == 'goto' and o.get('target') == 'exit']
check("⑤ 안 보이는 계단 = 이동 옵션(출처 딱지 명시)",
      len(opt5) == 1 and '방 구조로 앎' in opt5[0]['label'])
check("⑤ _valid_targets 도 구조 유래 exit 허용(brains 계약)",
      'exit' in brains._valid_targets(obs5))
r5 = dm5.act(b5, {'type': 'goto', 'target': 'exit'}, [b5])
w5 = walk_out(dm5, b5, [b5])
check("⑤ 핑 → 공동 관통 → 계단 앞(at_exit) — 공동 병목의 물리 치료",
      r5['result'] == 'pathed' and w5 is not None and w5['result'] == 'at_exit')
check("⑤ 확인 딱지: 큰 방은 아직 다 못 봤다(frac<1 + 못 본 쪽 방위)",
      z5['checked']['frac'] < 1 and z5['checked'].get('todo') in KR8)

# ───────────────────── ⑥ 문 핑 = 지나 들어서기 ─────────────────────
print("── ⑥ 문 핑(지나 들어서기)")
d6, st6 = G.Dungeon.from_ascii(rows, seed=7, scan=True)
b6 = mkbot('1', *st6['1'])
obs6 = d6.view(b6, [b6])
door6 = next(o for o in obs6['options'] if o['type'] == 'goto'
             and str(o.get('target', '')).startswith('d'))
check("⑥ 문이 이동 옵션에 있다(1:1 — 문 어휘의 리모컨 편입)", door6 is not None)
check("⑥ 문 id 는 _valid_targets(goto)에, interact 엔 없음",
      door6['target'] in brains._valid_targets(obs6)
      and door6['target'] not in brains._valid_targets(obs6, verb='interact'))
r6 = d6.act(b6, {'type': 'goto', 'target': door6['target']}, [b6])
w6 = walk_out(d6, b6, [b6])
check("⑥ 문 통과 → 문턱이 아니라 '다음 공간'(통로)에 들어선 채 재결정",
      r6['result'] == 'pathed' and w6 is not None and w6['result'] == 'arrived'
      and d6.zone_at[(b6['x'], b6['y'])] == 'c0')
obs6b = d6.view(b6, [b6])                       # 통로에서 건너방 문으로 — 이번엔 방이라 entered
door6b = next(o for o in obs6b['options'] if o['type'] == 'goto'
              and str(o.get('target', '')).startswith('d')
              and '가 본 곳' not in o['label'])
d6.act(b6, {'type': 'goto', 'target': door6b['target']}, [b6])
w6b = walk_out(d6, b6, [b6])
check("⑥ 문 너머가 처음 방이면 들어선 걸음이 곧 entered(결정 하나로 합침)",
      w6b is not None and w6b['result'] == 'entered'
      and d6.zone_at[(b6['x'], b6['y'])] == 'r1')

# ───────────────────── ⑦ 처음 방 정지 ─────────────────────
print("── ⑦ 처음 방 정지(무조건 정지·판단 요청)")
rows7 = ['###################',
         '#...###########...#',
         '#.1.' + '.' * 11 + '.>.#',
         '#...###########...#',
         '###################']
d7, st7 = G.Dungeon.from_ascii(rows7, seed=7, scan=True)
b7 = mkbot('1', *st7['1'])
obs7 = d7.view(b7, [b7])
check("⑦ 스폰 방 = 들어와 본 곳(첫 결정에 entered 정지 없음)",
      'r0' in b7['zones_entered'])
b7['plan'] = [{'type': 'search'}]               # 작정을 품고 걷는다 — 정지가 찢어야 한다
d7.act(b7, {'type': 'goto', 'target': 'exit'}, [b7])   # 구조 유래가 아니라도 엔진 해석은 무조건 —
                                                #   여기선 물리(정지)만 본다(어휘 게이트는 ⑤가 담당)
w7 = walk_out(d7, b7, [b7])
check("⑦ 첫 진입 방에서 entered 정지 + 남은 작정 파기",
      w7 is not None and w7['result'] == 'entered'
      and w7['zone']['id'] == 'r1' and b7['plan'] == [] and b7['order'] is None)
check("⑦ 통로 진입은 정지 아님(빈 복도는 끝까지)",
      'c0' in b7['zones_entered'])              # 통로를 지나왔는데 통로에서 안 멈췄다
d7.act(b7, {'type': 'goto', 'target': 'exit'}, [b7])
w7b = walk_out(d7, b7, [b7])
check("⑦ 아는 방(재진입)은 통과 — 계단까지 간다",
      w7b is not None and w7b['result'] == 'at_exit')

# ───────────────────── ⑧ 탐색 종점(새 명사가 나타나면 멈춤) ─────────────────────
print("── ⑧ 탐색 종점")
rows8 = ['##########',
         '#...######',
         '#.1......#',
         '#>..######',
         '##########']
d8, st8 = G.Dungeon.from_ascii(rows8, seed=7, scan=True)
b8 = mkbot('1', *st8['1'])
d8.view(b8, [b8])
r8 = d8.act(b8, {'type': 'explore', 'target': 'E'}, [b8])   # 방의 탐색 종점 = 문(명사)
walk_out(d8, b8, [b8])
check("⑧ 방에서 탐색 = 문을 지나 다음 공간까지(시야 가장자리 정지 폐기)",
      r8['result'] == 'pathed' and d8.zone_at[(b8['x'], b8['y'])] == 'c0')
d8.view(b8, [b8])
steps8 = 0
d8.act(b8, {'type': 'explore', 'target': 'E'}, [b8])        # 통로의 탐색 종점 = 막다른 곳
w8 = None
while b8.get('order') and steps8 < 60:
    w8 = d8.step_order(b8, [b8])
    steps8 += 1
check("⑧ 빈 복도 = 막다른 곳까지 한 order 로 끝까지(중간 재결정 없음)",
      w8 is not None and w8['result'] == 'arrived'
      and (b8['x'], b8['y']) == (8, 2) and steps8 == 4)
check("⑧ 개시 때 이미 보이던 계단은 '새 명사'가 아니다(정지 없음)",
      d8.exit == (1, 3))                        # 계단이 처음부터 시야 안이었는데 완주했다
d9, st9 = G.Dungeon.from_ascii(rows7, seed=7, scan=True)   # 복도 걷다 계단이 눈에 든다
b9 = mkbot('1', *st9['1'])
d9.view(b9, [b9])
d9.act(b9, {'type': 'explore', 'target': 'E'}, [b9])       # 문 너머(통로)로 탐색
walk_out(d9, b9, [b9])                                     # 통로 도착 → 재결정
d9.view(b9, [b9])
d9.act(b9, {'type': 'explore', 'target': 'E'}, [b9])       # 통로 끝(오른방 문)으로 탐색
w9 = walk_out(d9, b9, [b9])
check("⑧ 걷다 계단이 시야에 새로 들면 sighted 정지(멈춰 묻는다)",
      w9 is not None and w9['result'] == 'sighted'
      and any(x.get('kind') == 'exit' for x in w9['seen']))

# ───────────────────── ⑨ 시야-온리·출처 딱지 ─────────────────────
print("── ⑨ 시야-온리·출처 딱지")
no_xy = all('x' not in e and 'y' not in e
            for e in z5['doors'] + [z5['exit']])
check("⑨ 구조 obs 에 좌표 무노출(방위·거리·딱지뿐)", no_xy)
far_doors = [dr for dr in z5['doors'] if not dr['seen']]
check("⑨ 안 보이는 문 seen=false(출처 딱지 재료)",
      all(set(dr) == {'id', 'bearing', 'dist', 'seen', 'been'} for dr in z5['doors']))
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
                bad_door += 1                   # 문은 제 방위 슬롯 문장에 등장해야 한다
        for m in obs['sights']['monsters']:
            if m['dist'] > 0 and m['id'] not in msg:
                bad_mon += 1
        for k in KR8:
            line = next((l for l in msg.splitlines()
                         if l.startswith("- %s:" % KR8[k])), '')
            if line.endswith('벽') and any(
                    dr['bearing'] == k and dr['dist'] > 0 for dr in zz['doors']):
                bad_wall += 1                   # 문이 있는 방위가 '벽'으로 발화되면 계약 위반
check("⑩ [%d뷰] 8방위 슬롯 전부 발화" % views, views > 200 and bad_slot == 0)
check("⑩ 모든 문이 제 방위 슬롯에 등장(그림≡문장)", bad_door == 0)
check("⑩ 보이는 몹 전부 문장에 등장", bad_mon == 0)
check("⑩ '벽' 발화는 정말 빈 방향뿐", bad_wall == 0)

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
                tuple(tuple(sorted(b.get('zones_entered', set()))) for b in bb))
    return done


done_n = sum(play(s) for s in range(30))
check("⑫ [30시드] scan-on 풀게임 항상 종료(처음 방 정지가 교착을 만들지 않는다)",
      done_n == 30)
bad = sum(1 for s in range(8) if play(s, sig=True) != play(s, sig=True))
check("⑫ [8시드] 결정론 — 같은 시드 = 같은 판(구역 발자국 서명 포함)", bad == 0)

print("=" * 44)
if C.failed:
    print("RESULT: %d FAIL" % C.failed)
    raise SystemExit(1)
print("RESULT: ALL PASS — 스캐너·보고 이동(D19) 계약 건전")

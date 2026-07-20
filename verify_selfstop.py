# -*- coding: utf-8 -*-
"""자기 관찰 정지(D21, 07-20) 헤들리스 검증 — 19번째 게이트.
재회(①)="아는 구역에 새 연결로 들어서면 정지+낯익음 보고"(고리의 정보 가치=연결의 발견),
맴돎(②)="결정 없이 걸음만 이었는데 새로 본 칸 0 + 밟았던 칸 되밟기 → 정지+관찰 보고".
둘 다 금지·조향이 아니라 정지+사실 제시 — 판단은 두뇌 몫(처방 사다리 ③).
'계속 이동'의 해석: 결정(act)·새 목격이 창을 접는다 — 동행의 곁 대기(비결정 무보행)는 안 접는다
(회전 셔틀의 간헐 대기가 창을 접으면 그물이 뚫린다).
게이트:
  ① 스위치: 엔진 기본 0 / from_ascii 기본 0 (기존 verify 비트 동일)
  ② 재회: 고리 일주 → 아는 방 재진입에 reunion 발화 + 이름=사람말(좌표·번호 없음)
  ③ 재회 에지 소진: 같은 문 왕복·아는 에지 재통과 무발화(재방문 과제약 금지)
  ④ 구조 조회 재회 표기: been 문에 to(너머 이름) — selfstop=0 이면 없음 / wire "너머는" 렌더
  ⑤ 맴돎 경계: 다 본 고리 한 바퀴(26걸음, 새 목격 0)=무발화(직행 주파 보존 — 되밟기 없음),
     두 바퀴째 첫 되밟기에서 wander 발화(steps=27)
  ⑥ 3인 회전 셔틀 회귀(07-20 큰 판, 결정 0 ~50틱 실측): selfstop=0=회전 지속(버그 재현),
     selfstop=1=K틱 내 wander 재결정
  ⑦ 어투·계약: reunion/wander 문장에 물음표 0(질문형 금지)·좌표 무노출, act()=맴돎 창 리셋,
     장부 봇의 재회 이름="샘 있던 방"(내용물 우선)
  ⑧ 결정론: 같은 시나리오 2회 = 같은 결과열
(기존 verify 18종은 별도 실행.)
"""
import json

import brains
import dungeon_gm as G
from dungeon_gm import Dungeon, new_ledger


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


# ── 무대 1: 고리 맵(손그림) — 방 A(좌)·방 B(우, 샘)·윗 통로·아랫 U자 통로 = 한 바퀴 고리 ──
RING_ROWS = [
    "#############",
    "#...#####.~.#",
    "#.1.+...+...#",
    "#...#####..>#",
    "##+######+###",
    "##.######.###",
    "##.######.###",
    "##.######.###",
    "##........###",
    "#############",
]
# 고리 한 바퀴(A 안 (2,2)에서 출발, 시계 반대: 아래 문 → U자 → 방 B → 윗 통로 → 방 A)
RING_LAP = [(2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (3, 8), (4, 8), (5, 8),
            (6, 8), (7, 8), (8, 8), (9, 8), (9, 7), (9, 6), (9, 5), (9, 4), (9, 3),
            (9, 2), (8, 2), (7, 2), (6, 2), (5, 2), (4, 2), (3, 2), (2, 2)]


def drive(d, b, bots, tx, ty, cap=120):
    """목적지까지 자동보행 반복 — 정지(재결정)가 나면 실제 흐름처럼 재핑+맴돎 창 리셋(act 모사)."""
    out = []
    while (b['x'], b['y']) != (tx, ty) and len(out) < cap:
        if not b.get('order'):
            b['order'] = '@%d,%d' % (tx, ty)
            b['path'] = d.path_to(b['x'], b['y'], tx, ty, bots)
            b['wander'] = None                # 재핑=새 결정(act 모사)
            if not b['path']:
                break
        out.append(d.step_order(b, bots))
    return out


def explore_ring(ledger=False):
    """고리 맵 한 판 세팅 + 3구간 탐험(윗길로 B → 아래로 U자 중앙 → 왼쪽으로 A 복귀)."""
    d, starts = Dungeon.from_ascii(RING_ROWS, scan=True)
    d.selfstop = True
    b = mkbot('1', *starts['1'], ledger=ledger)
    bots = [b]
    d.view(b, bots)                           # 결정 시점 목격 씨딩(실행 흐름 그대로)
    legs = [drive(d, b, bots, 10, 2),         # ① 윗 통로로 방 B(샘 곁)
            drive(d, b, bots, 5, 8),          # ② 오른쪽 문·U자로 내려가 바닥 중앙
            drive(d, b, bots, 2, 2)]          # ③ 왼쪽 통로로 방 A 재진입 ← 여기가 재회
    return d, b, bots, legs


# ───────────────────── ① 스위치 ─────────────────────
print("── ① 스위치 기본값")
check("① 엔진 직생성 기본 selfstop=0 (기존 verify 비트 동일)",
      Dungeon(seed=7).selfstop is False)
check("① from_ascii 기본 selfstop=0", Dungeon.from_ascii(RING_ROWS)[0].selfstop is False)
d_off, st_off = Dungeon.from_ascii(RING_ROWS, scan=True)
b_off = mkbot('1', *st_off['1'])
d_off.view(b_off, [b_off])
res_off = (drive(d_off, b_off, [b_off], 10, 2) + drive(d_off, b_off, [b_off], 5, 8)
           + drive(d_off, b_off, [b_off], 2, 2))
check("① selfstop=0: 같은 탐험에 reunion/wander 전무(격리)",
      all(r.get('result') not in ('reunion', 'wander') for r in res_off))

# ───────────────────── ② 재회 발화 ─────────────────────
print("── ② 재회(고리 일주)")
d1, b1, bots1, legs1 = explore_ring()
flat1 = [r for leg in legs1 for r in leg]
reun = [r for r in flat1 if r.get('result') == 'reunion']
check("② 고리 일주 → 재회 정확히 1회(③구간 방 A 재진입)",
      len(reun) == 1 and reun[0] in legs1[2])
check("② 재회 좌표 = 방 A 문지방 너머(왼쪽 문으로 새 연결)",
      bool(reun) and tuple(reun[0].get('to') or ()) == (2, 3))
name1 = (reun[0].get('name') or '') if reun else ''
check("② 이름=사람말 — 숫자·id·좌표 없음, 비어 있지 않음",
      bool(name1) and not any(ch.isdigit() for ch in name1) and '@' not in name1)
check("② 재회 정지=재결정(order·작정 파기)",
      bool(reun) and b1.get('plan') == [] )
check("② 앞 구간(처음 길)엔 재회 없음(첫 발견≠재회)",
      all(r.get('result') != 'reunion' for r in legs1[0] + legs1[1]))

# ───────────────────── ③ 에지 소진 — 재방문 과제약 금지 ─────────────────────
print("── ③ 재회 에지 소진")
jaunt = drive(d1, b1, bots1, 2, 5) + drive(d1, b1, bots1, 2, 2)   # 같은 문 왕복
check("③ 같은 문 왕복 = 재회 무발화(정당한 재방문)",
      all(r.get('result') != 'reunion' for r in jaunt))
lap_again = drive(d1, b1, bots1, 10, 2) + drive(d1, b1, bots1, 2, 2)  # 고리 재일주(전 에지 기지)
check("③ 아는 에지 재통과 = 재회 무발화(에지 장부 소진)",
      all(r.get('result') != 'reunion' for r in lap_again))

# ───────────────────── ④ 구조 조회 재회 표기 ─────────────────────
print("── ④ 구조 조회 to(너머 이름) + wire")
obs4 = d1.view(b1, bots1)
doors4 = (obs4.get('zone') or {}).get('doors') or []
tos = [dd for dd in doors4 if dd.get('to')]
check("④ been 문에 to(너머 이름) 실림", bool(tos) and all(dd['been'] for dd in tos))
check("④ to=사람말(숫자·좌표 없음)",
      bool(tos) and all(not any(ch.isdigit() for ch in dd['to']) for dd in tos))
w4 = brains._wire(obs4)
check("④ wire 렌더 '너머는' 발화", '너머는' in w4)
d1.selfstop = False
doors4b = (d1.view(b1, bots1).get('zone') or {}).get('doors') or []
check("④ selfstop=0 이면 to 없음(계약 격리)", all('to' not in dd for dd in doors4b))
d1.selfstop = True

# ───────────────────── ⑤ 맴돎 경계 — 직행 보존 vs 되밟기 발화 ─────────────────────
print("── ⑤ 맴돎(다 본 고리 두 바퀴)")
b1['order'], b1['path'] = '@2,2', [c for c in RING_LAP] + [c for c in RING_LAP]
b1['wander'] = None
r5, seq5 = None, []
for _ in range(80):
    r5 = d1.step_order(b1, bots1)
    seq5.append(r5)
    if r5.get('result') != 'walking':
        break
check("⑤ 한 바퀴(26걸음, 새 목격 0·되밟기 없음) = 무발화 — 직행 주파 보존",
      all(r.get('result') == 'walking' for r in seq5[:26]))
check("⑤ 두 바퀴째 첫 되밟기 = wander 발화(steps=27, N=%d 이상)" % G.WANDER_N,
      r5 is not None and r5.get('result') == 'wander' and r5.get('steps') == 27
      and r5['steps'] >= G.WANDER_N)
check("⑤ 발화 후 창 리셋(재무장 — 연사 아님)", b1.get('wander') is None)

# ───────────────────── ⑥ 3인 회전 셔틀 회귀(07-20 큰 판 로그 재구성) ─────────────────────
# 큰 판 로그(t85~132)의 병리 = 세 봇이 시야 안에 뭉친 채 서로를 쫓아(순환 follow) 매 틱 자리를
# 바꾸며 회전 — 곁이 안 되어 idle 안 걸리고, 새 목격이 없어 sighted 안 걸리고, 목표가 움직여
# arrived 안 걸린다 → 결정 0으로 ~50틱 소진. 최소 재현: 짧은 방(전부 시야 안)에 세 봇을
# 순환 follow(1→2→3→1) — 실측 45틱 133걸음 회전 지속·명령 유지(faithful).
print("── ⑥ 3인 회전 셔틀(시야 안에 뭉쳐 순환 follow — 큰 판 t85~132 재구성)")
CAR_ROWS = ["#######",
            "#.....#",
            "#.###.#",
            "#.###.#",
            "#.###.#",
            "#.....#",
            "###>###",
            "#######"]


def carousel(selfstop, ticks=45):
    d, _ = Dungeon.from_ascii(CAR_ROWS, scan=True)
    d.selfstop = selfstop
    a, k, c = mkbot('1', 1, 1), mkbot('2', 3, 1), mkbot('3', 5, 1)
    bots = [a, k, c]
    for b in bots:
        d.view(b, bots)
    d.act(a, {'type': 'follow', 'target': 'b2'}, bots)   # 두란→카야
    d.act(k, {'type': 'follow', 'target': 'b3'}, bots)   # 카야→피른
    d.act(c, {'type': 'follow', 'target': 'b1'}, bots)   # 피른→두란(고리)
    log = []
    for t in range(ticks):
        for b in bots:
            if b.get('order'):
                log.append((t, b['char'], d.step_order(b, bots)))
    return log, bots


log_off, bots_off = carousel(False)
moved = sum(1 for _, _, r in log_off if r.get('to') or r.get('swap'))
check("⑥ selfstop=0: 45틱 회전 지속(≥60걸음)·wander 전무·명령 유지(버그 재현)",
      all(r.get('result') != 'wander' for _, _, r in log_off) and moved >= 60
      and sum(1 for b in bots_off if b.get('order')) >= 2)
log_on, _ = carousel(True)
wt = [t for t, _, r in log_on if r.get('result') == 'wander']
check("⑥ selfstop=1: wander 재결정 도달(회귀 그물 — 회전이 스스로 끊긴다)",
      bool(wt))

# ───────────────────── ⑦ 어투·계약 ─────────────────────
print("── ⑦ 어투(질문형 금지)·act 리셋·장부 이름")
p_reu = brains._last_prose({'type': 'walk', 'result': 'reunion', 'name': '샘 있던 방'})
p_wan = brains._last_prose({'type': 'walk', 'result': 'wander', 'steps': 12})
check("⑦ reunion/wander 문장: 물음표 0(관찰 사실만) + JSON 폴백 아님",
      '?' not in p_reu and '?' not in p_wan
      and not p_reu.startswith('{') and not p_wan.startswith('{')
      and '샘 있던 방' in p_reu and '12' in p_wan)
import re
coord = re.compile(r'@|\d+\s*,\s*\d+')        # 좌표 = '@x,y' 또는 'x,y'(한글 쉼표는 정상 문장부호)
check("⑦ 문장에 좌표 무노출(@·숫자쌍 없음 — 한글 쉼표는 무관)",
      not coord.search(p_reu) and not coord.search(p_wan))
b7 = mkbot('7', 2, 2)
b7['wander'] = {'cells': {(9, 9)}, 'n': 7}
d1.act(b7, {'type': 'search'}, [b7])
check("⑦ act(새 결정) = 맴돎 창 리셋", b7.get('wander') is None)
d7, b7l, bots7, legs7 = explore_ring(ledger=True)
reun7 = [r for leg in legs7 for r in leg if r.get('result') == 'reunion']
zidB = d7.zone_at.get((10, 2))
check("⑦ 장부 봇의 구역 이름 = '샘 있던 방'(내용물 우선)",
      zidB is not None and d7._zone_name(b7l, zidB) == '샘 있던 방')
check("⑦ 장부 봇도 재회 1회(장부 유무와 발화 무관)", len(reun7) == 1)
check("⑦ 결과 dict JSON 직렬화 가능(스트림 계약)",
      bool(json.dumps(reun7[0], ensure_ascii=False)) if reun7 else False)

# ───────────────────── ⑧ 결정론 ─────────────────────
print("── ⑧ 결정론")
_, _, _, legsA = explore_ring()
_, _, _, legsB = explore_ring()
sigA = [(r.get('result'), r.get('steps'), r.get('name')) for leg in legsA for r in leg]
sigB = [(r.get('result'), r.get('steps'), r.get('name')) for leg in legsB for r in leg]
check("⑧ 같은 시나리오 2회 = 같은 결과열", sigA == sigB)

print()
if C.failed:
    print("FAIL — %d개 실패" % C.failed)
    raise SystemExit(1)
print("ALL PASS — verify_selfstop (D21 재회·맴돎)")

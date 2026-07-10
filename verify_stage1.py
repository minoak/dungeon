# -*- coding: utf-8 -*-
"""Stage 1 헤들리스 검증 — features / room graph / path_to / 동일시드 재현.
계획서(whimsical-shimmying-nebula.md) Stage 1 검증 항목의 결정론 회귀 도구.

[v2] 어드버서리얼 리뷰가 잡은 '공통 맹점' 제거:
  · seed 7 하나에만 박혀 path_to non-walkable 분기를 한 번도 안 밟던 문제 → 200시드 스윕.
  · 방 중첩(AABB) / 지형 연결성 / 몹 핑 직교 인접·거짓 도달불가를 다중 시드로 검사."""
from collections import deque
from dungeon_gm import Dungeon, MOVES, FLOOR

ORTHO = ((0, -1), (0, 1), (1, 0), (-1, 0))


class C:
    failed = 0


def check(name, cond):
    print(("  OK   " if cond else " FAIL  ") + name)
    if not cond:
        C.failed += 1


d = Dungeon(seed=7, depth=1)

# ── 1) FEATURES — 출구/보물 흡수 ──────────────────────────────
exit_feats = [f for f in d.features.values() if f.type == 'exit']
treas_feats = [f for f in d.features.values() if f.type == 'treasure']
check("exit feature 정확히 1개", len(exit_feats) == 1)
check("exit 좌표 = d.exit 프로퍼티 일치",
      bool(exit_feats) and (exit_feats[0].x, exit_feats[0].y) == d.exit)
check("treasure features = d.treasures 집합 일치",
      {(f.x, f.y) for f in treas_feats} == d.treasures)
check("exit feature 가 방 안(room_id 보유)",
      bool(exit_feats) and exit_feats[0].room_id is not None)
check("feature.as_dict 가 perception_gate 포함",
      'perception_gate' in exit_feats[0].as_dict())
check("모든 feature 가 정수 id·맵내 좌표 보유",
      all(isinstance(f.id, int) and 0 <= f.x < d.w and 0 <= f.y < d.h
          for f in d.features.values()))

# ── 2) ROOM GRAPH — id/타입/연결성 ───────────────────────────
ids = [r.id for r in d.rooms]
check("room id = 0..n-1 연속", ids == list(range(len(d.rooms))))
check("room 타입 ⊆ {entrance,exit,standard}",
      {r.type for r in d.rooms} <= {'entrance', 'exit', 'standard'})
check("exit 타입 방 정확히 1개(출구가 방 안)",
      sum(1 for r in d.rooms if r.type == 'exit') == 1)
check("entrance 타입 방 ≤ 1개",
      sum(1 for r in d.rooms if r.type == 'entrance') <= 1)
seen, q = {0}, deque([0])
while q:
    rid = q.popleft()
    for nb in d.rooms[rid].neighbours:
        if nb not in seen:
            seen.add(nb); q.append(nb)
check("방 그래프 연결성(방0→전 방 도달)", len(seen) == len(d.rooms))
check("neighbours 대칭(a∈nb면 nb∈a)",
      all(r.id in d.rooms[nb].neighbours for r in d.rooms for nb in r.neighbours))

# ── 3) PATH_TO — 8연결·코너컷금지·도달 (walkable 목표) ────────
bots = []
ent = next((r for r in d.rooms if r.type == 'entrance'), d.rooms[0])
sx, sy = ent.center
ex, ey = d.exit
path = d.path_to(sx, sy, ex, ey, bots)
check("path 비어있지 않음(출구까지 경로 존재)", len(path) > 0)
prev, ok_steps, ok_corner = (sx, sy), True, True
for (cx, cy) in path:
    ddx, ddy = cx - prev[0], cy - prev[1]
    if max(abs(ddx), abs(ddy)) != 1 or not d.walkable(cx, cy, bots):
        ok_steps = False
    if ddx and ddy and not (d.walkable(prev[0] + ddx, prev[1], bots)
                            and d.walkable(prev[0], prev[1] + ddy, bots)):
        ok_corner = False
    prev = (cx, cy)
check("path 모든 스텝 8-인접 & walkable", ok_steps)
check("path 대각선 코너컷 없음", ok_corner)
check("path 마지막 칸 = 출구(walkable 목표는 그 칸)", bool(path) and path[-1] == (ex, ey))
check("이미 도착이면 빈 경로", d.path_to(sx, sy, sx, sy, bots) == [])

# ── 4) 동일 시드 재현 + 시드/깊이 분기 ────────────────────────
def fingerprint(dg):
    return (tuple(tuple(r) for r in dg.rooms),       # 방 기하
            tuple(r.type for r in dg.rooms),         # 방 타입
            dg.exit, tuple(sorted(dg.treasures)),    # 출구·보물
            tuple(dg.d20() for _ in range(30)))      # 생성 후 d20 30연속

a = fingerprint(Dungeon(seed=7, depth=1))
check("같은 (시드,깊이) → 완전 동일(맵+타입+출구+보물+d20×30)",
      a == fingerprint(Dungeon(seed=7, depth=1)))
check("다른 시드 → 다른 판", a != fingerprint(Dungeon(seed=8, depth=1)))
check("같은 시드 다른 깊이 → 다른 판(파생 시드)", a != fingerprint(Dungeon(seed=7, depth=2)))
import random as _r
_r.seed(999); g1 = fingerprint(Dungeon(seed=7, depth=1))
_r.seed(123); g2 = fingerprint(Dungeon(seed=7, depth=1))
check("전역 random 상태와 무관(독립 RNG 스트림)", g1 == g2 == a)
# 시그니처 위치 계약: Dungeon(master_seed, depth) 가 계획서 솔기와 일치
check("위치 인자 Dungeon(7,2) = 키워드 seed=7,depth=2 (계획 솔기①)",
      fingerprint(Dungeon(7, 2)) == fingerprint(Dungeon(seed=7, depth=2)))
check("_derive_seed 32비트 초과·음수 구분(앨리어싱 없음)",
      len({Dungeon._derive_seed(s, 1) for s in (7, 7 + 2**32, -1, 0xFFFFFFFF)}) == 4)

# ── 5) 다중 시드 불변식 스윕 (seed 7 맹점 제거) ───────────────
SEEDS = range(0, 200)


def rooms_disjoint(dg):
    cells = set()
    for r in dg.rooms:
        for y in range(r.y, r.y + r.h):
            for x in range(r.x, r.x + r.w):
                if (x, y) in cells:
                    return False
                cells.add((x, y))
    return True


def graph_connected(dg):
    s, qq = {dg.rooms[0].id}, deque([dg.rooms[0].id])
    while qq:
        rid = qq.popleft()
        for nb in dg.rooms[rid].neighbours:
            if nb not in s:
                s.add(nb); qq.append(nb)
    return len(s) == len(dg.rooms)


def geometry_connected(dg):
    # 몹 제거(지형만) → 방0 중심에서 다른 모든 방 중심 도달 가능해야(체인 연결)
    dg.monsters = []
    cx, cy = dg.rooms[0].center
    for r in dg.rooms[1:]:
        if (cx, cy) != r.center and not dg.path_to(cx, cy, r.center[0], r.center[1], []):
            return False
    return True


check("[200시드] 방끼리 안 겹침(AABB)", all(rooms_disjoint(Dungeon(seed=s)) for s in SEEDS))
check("[200시드] 방 그래프 연결성", all(graph_connected(Dungeon(seed=s)) for s in SEEDS))
check("[200시드] 지형 연결성(몹 제거 시 전 방 도달)",
      all(geometry_connected(Dungeon(seed=s)) for s in SEEDS))
check("[200시드] exit feature 항상 방 안",
      all(Dungeon(seed=s).features[Dungeon(seed=s)._exit_fid].room_id is not None for s in SEEDS))

# ── 6) path_to non-walkable 분기 (리뷰가 잡은 미검증 분기) ────
def ortho_adj(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1


bad_ortho = bad_reach = tested = 0
for s in SEEDS:
    dg = Dungeon(seed=s)
    e = next((r for r in dg.rooms if r.type == 'entrance'), dg.rooms[0])
    sxx, syy = e.center
    for m in dg.monsters:
        tested += 1
        p = dg.path_to(sxx, syy, m.x, m.y, [])
        if p:                               # 끝칸은 몹에 직교 인접 + walkable(전투 가능 위치)이어야
            if not (ortho_adj(p[-1], (m.x, m.y)) and dg.walkable(p[-1][0], p[-1][1], [])):
                bad_ortho += 1
        elif not ortho_adj((sxx, syy), (m.x, m.y)):
            # [] 인데 시작이 이미 인접도 아니면 → 직교 인접칸이 정말 다 도달불가여야(거짓 도달불가 금지)
            reachable = any((m.x + dx, m.y + dy) != (sxx, syy)
                            and dg.walkable(m.x + dx, m.y + dy, [])
                            and dg.path_to(sxx, syy, m.x + dx, m.y + dy, [])
                            for dx, dy in ORTHO)
            if reachable:
                bad_reach += 1
check("[200시드] 몹 핑 끝칸 = 직교 인접·walkable (대각/거리2 아님)", bad_ortho == 0)
check("[200시드] 몹 핑 [] = 진짜 도달불가만 (거짓 도달불가 0)", bad_reach == 0)
print(f"        (non-walkable 분기 {tested}회 실측)")

print("\n" + "=" * 44)
print("RESULT: " + ("ALL PASS" if C.failed == 0 else f"{C.failed} FAILED"))
import sys
sys.exit(1 if C.failed else 0)

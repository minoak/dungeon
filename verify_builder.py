# -*- coding: utf-8 -*-
"""월드 빌더(D20) 헤들리스 검증 — 18번째 게이트.
사슬(외길) → 주 고리(방 6~8 원환)+막다른 가지(4~6) — SPD LoopBuilder식 메커니즘 재구현.
격자=유일 인터페이스: 빌더는 격자만 뱉고, 스캐너는 격자만 읽는다(사이드채널 금지).
게이트:
  ① 스위치 격리: loops 미지정=False 경로가 rng 무소비·격자 비트 동일(기존 17종 게이트의 전제)
  ② [200시드] 방 겹침 0 (AABB 1칸 간격 — 러너 기본 56×20)
  ③ [200시드] 지형 연결: 모든 바닥 칸이 직교 단일 컴포넌트(고립 방·끊긴 통로 없음)
  ④ [200시드] 고리 실존: 방 그래프에 사이클(E≥V) + 전 방 그래프 도달 — '갈림길이 진짜 선택'의 골격
  ⑤ [200시드] 막다른 가지: 가지가 배속된 판엔 디그리 1 방(곁방)이 실재
  ⑥ [8시드] 결정론: 같은 시드 = 같은 격자·같은 에지(리플레이 헌법)
  ⑦ [50시드] 스캐너 접속(scan+loops): 구역 재구성 무사고·문(+) 실발화·존 그래프 단일 연결
  ⑧ [50시드] 큰 격자(80×30): 겹침 0·연결·사이클 — 큰 판 1층 테스트의 사전 건전성
  ⑨ [30시드] loops 풀게임(더미 2인) 항상 종결 + [8시드] 판 결정론
  ⑩ 손그림 하위호환: from_ascii 판에 loops 필드 기본 존재(속성 크래시 방지)
(기존 verify 17종은 별도 실행 — loops 기본 0이라 비트 동일.)
"""
import os

os.environ["DUNGEON_BESTIARY_FILE"] = ""   # 도감 영속 차단(게이트 격리 원칙)

from dungeon_gm import Dungeon, FLOOR, DOOR, spawn, dummy_brain


class C:
    failed = 0


def check(name, cond):
    print(("  OK   " if cond else " FAIL  ") + name)
    if not cond:
        C.failed += 1


def sig(d):
    return (tuple(tuple(row) for row in d.grid), tuple(sorted(d._edges)))


def overlap0(d):
    rs = d.rooms
    for i, a in enumerate(rs):
        for b in rs[i + 1:]:
            if (a.x < b.x + b.w + 1 and b.x < a.x + a.w + 1
                    and a.y < b.y + b.h + 1 and b.y < a.y + a.h + 1):
                return False
    return True


def connected(d):
    """모든 바닥(FLOOR·DOOR) 칸이 직교 한 덩어리 — 봇의 세계에 섬이 없다."""
    cells = {(x, y) for y in range(d.h) for x in range(d.w)
             if d.grid[y][x] in (FLOOR, DOOR)}
    if not cells:
        return False
    seen, front = set(), [next(iter(cells))]
    seen.add(front[0])
    while front:
        x, y = front.pop()
        for nx, ny in ((x+1, y), (x-1, y), (x, y+1), (x, y-1)):
            if (nx, ny) in cells and (nx, ny) not in seen:
                seen.add((nx, ny))
                front.append((nx, ny))
    return seen == cells


def graph_stats(d):
    """방 그래프: (전 방 도달?, 사이클 존재?, 디그리1 방 수). 에지=_plan_edges 기록."""
    edges = {frozenset(e) for e in d._edges}
    deg = {r.id: 0 for r in d.rooms}
    adj = {r.id: [] for r in d.rooms}
    for e in edges:
        a, b = tuple(e)
        deg[a] += 1
        deg[b] += 1
        adj[a].append(b)
        adj[b].append(a)
    seen, front = {d.rooms[0].id}, [d.rooms[0].id]
    while front:
        cur = front.pop()
        for n in adj[cur]:
            if n not in seen:
                seen.add(n)
                front.append(n)
    reach = len(seen) == len(d.rooms)
    cycle = len(edges) >= len(d.rooms)          # 연결 그래프에서 E≥V ⇔ 사이클
    dead = sum(1 for v in deg.values() if v == 1)
    return reach, cycle, dead


# ① 스위치 격리 — loops 기본값 경로 = loops=False 와 비트 동일(rng 무소비 증명)
bad = sum(1 for s in range(8)
          if sig(Dungeon(seed=s)) != sig(Dungeon(seed=s, loops=False)))
check("① 스위치 격리 — 기본 경로 비트 동일(8시드)", bad == 0)

# ②~⑤ [200시드] 러너 기본 크기 스윕
ov = conn = reach_n = cyc = ring_ok = br_n = br_dead = 0
nrooms = []
for s in range(200):
    d = Dungeon(seed=s, w=56, h=20, loops=True)
    nrooms.append(len(d.rooms))
    ov += overlap0(d)
    conn += connected(d)
    reach, cycle, dead = graph_stats(d)
    reach_n += reach
    ring = min(d._ring_target, len(d.rooms))
    if ring >= 3:
        ring_ok += 1
        cyc += cycle
    if len(d.rooms) > ring:                     # 가지가 실제 배속된 판
        br_n += 1
        br_dead += (dead >= 1)
print("  [실측] 방 수 min/avg/max = %d/%.1f/%d · 고리 성립 %d/200 · 가지 판 %d"
      % (min(nrooms), sum(nrooms) / len(nrooms), max(nrooms), ring_ok, br_n))
check("② [200시드] 방 겹침 0", ov == 200)
check("③ [200시드] 지형 연결(섬 없음)", conn == 200)
check("④ [200시드] 방 그래프 전 방 도달", reach_n == 200)
check("④ [200시드] 고리 실존(사이클) — 고리 성립 판 전부", ring_ok > 0 and cyc == ring_ok)
check("④ 고리 성립이 기본(56×20에서 방 6+ 배치)", ring_ok >= 190)
check("⑤ 막다른 가지 실재 — 가지 판 전부", br_n > 0 and br_dead == br_n)

# ⑥ 결정론
bad = sum(1 for s in range(8)
          if sig(Dungeon(seed=s, w=56, h=20, loops=True))
          != sig(Dungeon(seed=s, w=56, h=20, loops=True)))
check("⑥ [8시드] 결정론 — 같은 시드 = 같은 격자·에지", bad == 0)

# ⑦ [200시드] 스캐너 접속 — 빌더 산출물이 스캐너의 서식지(D20 계약)
#    (50시드였다가 200으로 — 정착 루프 이전 실패 3판 중 1판만 50 안이었다: 커버리지 교훈)
zc = dtile = zconn = 0
NSCAN = 200
for s in range(NSCAN):
    d = Dungeon(seed=s, w=56, h=20, loops=True, scan=True)
    if not d.zones:
        continue
    zc += 1
    dtile += any(d.grid[y][x] == DOOR for y in range(d.h) for x in range(d.w))
    adj = {z: set() for z in d.zones}
    for door in d.doors.values():
        za, zb = door.zones
        adj[za].add(zb)
        adj[zb].add(za)
    start = next(iter(d.zones))
    seen, front = {start}, [start]
    while front:
        cur = front.pop()
        for n in adj[cur]:
            if n not in seen:
                seen.add(n)
                front.append(n)
    zconn += (len(seen) == len(d.zones))
check("⑦ [%d시드] 스캐너 구역 재구성 무사고" % NSCAN, zc == NSCAN)
check("⑦ [%d시드] 문 타일(+) 실발화(%d판)" % (NSCAN, dtile), dtile >= NSCAN * 0.9)
check("⑦ [%d시드] 존 그래프 단일 연결(봇의 눈에도 이어진 세계)" % NSCAN, zconn == NSCAN)

# ⑧ [50시드] 큰 격자 — 큰 판 1층 테스트의 사전 건전성
ov = conn = cyc = 0
big_rooms = []
for s in range(50):
    d = Dungeon(seed=s, w=80, h=30, loops=True)
    big_rooms.append(len(d.rooms))
    ov += overlap0(d)
    conn += connected(d)
    reach, cycle, _ = graph_stats(d)
    cyc += (reach and cycle)
print("  [실측] 80×30 방 수 min/avg/max = %d/%.1f/%d"
      % (min(big_rooms), sum(big_rooms) / len(big_rooms), max(big_rooms)))
check("⑧ [50시드] 80×30 — 겹침 0·연결·사이클 전부", ov == conn == cyc == 50)

# ⑨ [30시드] loops 풀게임 종결(더미 2인) + 결정론
def play(seed, ticks=600, sig_out=False):
    dd = Dungeon(seed=seed, w=56, h=20, loops=True)
    bb = [spawn(dd, '1', [])]
    bb.append(spawn(dd, '2', bb))
    done = False
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
        if all(b['won'] or not b['alive'] for b in bb):
            done = True
            break
    if sig_out:
        return (tuple((b['x'], b['y'], b['hp'], b['won'], b['bag']) for b in bb),
                tuple((m.x, m.y, m.hp, m.alive) for m in dd.monsters))
    return done


done_n = sum(play(s) for s in range(30))
check("⑨ [30시드] 고리 판 풀게임 항상 종결", done_n == 30)
bad = sum(1 for s in range(8) if play(s, sig_out=True) != play(s, sig_out=True))
check("⑨ [8시드] 풀게임 결정론", bad == 0)

# ⑩ 손그림 하위호환
d, starts = Dungeon.from_ascii(["#####", "#1.>#", "#####"])
check("⑩ from_ascii — loops 필드 기본 존재(False·에지 0)",
      d.loops is False and d._edges == [] and d._ring_target == 0)

print("=" * 44)
if C.failed:
    print("RESULT: %d FAIL" % C.failed)
    raise SystemExit(1)
print("RESULT: ALL PASS — 월드 빌더(고리+가지) 격자 계약 건전")

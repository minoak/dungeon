# -*- coding: utf-8 -*-
"""던전 생성 프로필(D88, 2026-09-20) 헤들리스 검증 — 76번째 게이트. LLM 0콜(엔진 직접 생성 + 더미 두뇌 러너 · 상태 폴더는 tempfile).
새 생성기 dungeon_concept.ConceptDungeon(큰 홀·회랑·작은 방 · 폭 2~3 통로 · 기둥)을 러너 스위치 DUNGEON_ARCH=concept 뒤에 붙였다.
구역 스캐너는 블록 크기를 프로필 값(Dungeon.ZONE_BLOCK — 기본 2, concept 4 + 홀로 선 기둥 투과)으로 읽는다.
게이트:
  ① 스위치 끔 = 옛 판 그대로: 기본 Dungeon 의 ZONE_BLOCK·이름 임계 · [40시드+손그림] K=2 분류가 옛 2×2 코드(이 파일의 사본)와 같은 결과 ·
     기본 level_snapshot 에 architecture·art_style 없음 · 러너 미설정/'' /모르는 값 = 옛 생성기·지문에 arch 없음 · 미설정 판과 '' 판의 스트림 바이트 동일 ·
     켠 판은 W/H 미지정이면 42×34 · scan 메타는 늘 참
  ② [깊이 1~6 × 25시드 · 마지막 깊이만 보스] 예외 0 · 바닥∪문 단일 연결 · 출구·피처·몹·함정 도달 · 기둥은 벽(못 밟는다) · 계획 밖 홀로 선 벽 0 ·
     보스층엔 보스·봉인·boss_front · 같은 시드 = 같은 층(전역 random 오염 무관) · level_snapshot 은 rng 를 안 굴린다
  ③ [120시드] 구역 건전성(K=4): zone_at = 모든 바닥 · 통로 구역 존재 · 구역 그래프 단일 연결 · 모든 '+' 칸이 문 명사(cell)로 등재되고 양쪽이 다른 구역 ·
     모든 문 타일의 양 어깨가 벽(09-20 수선) · 가장 큰 구역 점유율 상한(실측 고정) · 갈림길/막다른 곳은 비어 있다
  ③-2 방 수가 격자 넓이를 따라간다(09-20 개정 — 민옥 "던전을 조금 더 크게 하고 층을 3층으로"): 기준 42×34 는 옛 고정값 (5,8) 그대로 =
     결정론의 닻 · 더 작은 격자도 그 아래로 안 내려간다 · 론처가 주는 54×42 는 방·바닥이 실제로 늘고 구역 뭉갬은 오히려 내려간다
  ④ 문장층(K>2 에서 거짓이 되던 말): 통로 길이 = bbox 긴 변(칸 수 아님) · obs zone.ends 빈 목록 · 프롬프트에 '갈림길'·'막다른 곳' 줄 없음 ·
     이름 임계가 프로필 값(넓은 방·작은 방·긴 통로가 셋 다 실제로 갈린다)
  ⑤ 견고화: scan 강제 · 최소 격자 가드(명시 문장 ValueError) · 작은 격자의 완화 폴백(26×17 에서도 방 5+·연결) · from_ascii 경유 인스턴스의 level_snapshot
  ⑥ 피클(D79): dumps/loads 왕복 뒤 level_snapshot·구역·문 동일 · 클래스 모듈 = 루트 'dungeon_concept'(art/ 재수출과 같은 객체) ·
     snapshot.write → **새 프로세스**의 snapshot.load 가 되살린다
  ⑦ [12시드] 더미 2인 풀게임 종결 + [4시드] 결정론
  ⑧ 러너(ARCH=concept · compose): run_meta arch·arch_v·w·h(42×34) · level 줄에 architecture·rooms[].art_style · 층 전이 · 층을 짓는 세 자리가 같은 생성기
     (new_floor(1)·(2) 의 격자 = 스트림의 1·2층 — 주점 소문 미리보기가 실제 층과 같다) · 곱게 멈춤 → 이어가기(같은 몸 · 다시 짓지 않는다 · 대조군과 같은 틱) ·
     ARCH 가 다른 러너는 그 스냅샷을 거절(지문) · menu 모드 자식 프로세스 판도 끝까지
  ⑨ 자기 등록(_run_gates.sh)
"""
import contextlib
import io
import json
import os
import pickle
import random
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="wl_arch_")
STATE = os.path.join(TMP, "state")
os.makedirs(STATE, exist_ok=True)
for _k in [k for k in os.environ if k.startswith("DUNGEON_")]:       # 게이트 환경(_run_gates.sh)의 값까지 걷고 이 게이트의 판을 명시한다
    os.environ.pop(_k)
RUN_ENV = dict(DUNGEON_BRAIN_BACKEND="dummy", DUNGEON_GM="0", DUNGEON_STEP_DELAY="0", DUNGEON_BESTIARY_FILE="",
               DUNGEON_PARTY_FILE=os.path.join(HERE, "party.json"), DUNGEON_STATE_DIR=STATE,
               # ⚠️D92(09-20) 로 시드가 7 → 9 로 바뀌었다: 엔진 소유 소품(concept 프로필에 딸린 통·상자·항아리)이 놓이면서
               #   spawn 의 후보 칸이 줄어 파티 출발 자리가 달라졌고, 시드 7 의 더미 2인은 36틱 안에 계단에 닿지 못한다
               #   (같은 조건 14시드 스윕: 120틱 안 하강 소품 켠 판 8/14 중앙값 57 · 끈 판 7/14 중앙값 45 — 느려진 게 아니라
               #   출발 자리가 달라진 것. 시드 9 는 7틱에 하강). ⑧ 은 '층 전이가 난다'를 보는 자리라 빠른 시드를 쓴다.
               #   ⚠️'시드 7 을 두고 틱 상한만 올리자'는 안 된다 — 같은 조건 자식 프로세스로 재봤더니 시드 7 은 200틱 안에도
               #   하강하지 않는다(09-20 수선 측정). 대신 '이동이 느려지는 회귀'의 핀은 여기가 아니라 ⑦ 이다(12시드 × 600틱 종결).
               DUNGEON_RUNS_DIR=os.path.join(TMP, "runs"), DUNGEON_SEED="9", DUNGEON_DEPTHS="2", DUNGEON_TURNS="36",
               DUNGEON_ARCH="concept")                                # 행동 모드는 실판 기본(compose) — menu 는 ⑧ 끝의 자식 프로세스
os.environ.update(RUN_ENV)

import brains                                        # noqa: E402
brains._call_claude = lambda prompt, model="haiku": ""   # 안전핀(더미 백엔드라 닿지 않는다)
import dungeon_gm as G                               # noqa: E402
import dungeon_concept as DC                         # noqa: E402
import snapshot                                      # noqa: E402
import show_runner                                   # noqa: E402
import time as _time                                 # noqa: E402
_time.sleep = lambda s: None
show_runner.STEP_DELAY = 0

from dungeon_gm import FLOOR, DOOR, WALL             # noqa: E402
from dungeon_concept import ConceptDungeon           # noqa: E402


class C:
    failed = 0


def check(name, ok, detail=""):
    print("  %s %s%s" % ("OK  " if ok else "FAIL", name, (" — " + str(detail)) if (detail and not ok) else ""))
    if not ok:
        C.failed += 1


KW = dict(w=42, h=34, scan=True, loops=True, n_traps=3, n_lurkers=1, n_potions=1, n_gear=3)
DEPTHS = 6


def build(seed, depth=1, **over):
    return ConceptDungeon(seed=seed, depth=depth, n_monsters=2 + depth - 1, boss=(depth == DEPTHS), **{**KW, **over})


def walk_cells(d):
    return {(x, y) for y in range(d.h) for x in range(d.w) if d.grid[y][x] in (FLOOR, DOOR)}


def flood(cells):
    start = min(cells)
    seen, todo = {start}, [start]
    for x, y in todo:
        for p in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if p in cells and p not in seen:
                seen.add(p)
                todo.append(p)
    return seen


def zone_graph_connected(d):
    adj = {z: set() for z in d.zones}
    for dr in d.doors.values():
        za, zb = dr.zones
        adj[za].add(zb)
        adj[zb].add(za)
    seen, todo = set(), [next(iter(d.zones))]
    while todo:
        z = todo.pop()
        if z not in seen:
            seen.add(z)
            todo.extend(adj[z] - seen)
    return len(seen) == len(d.zones)


def old_components(d):
    """옛 _zone_components(2×2 하드코딩, night-0920 기준)의 사본 — K=2 경로가 글자 하나 안 바뀌었는지의 잣대."""
    from collections import deque
    floors = [(x, y) for y in range(d.h) for x in range(d.w) if d.grid[y][x] == FLOOR]
    fset = set(floors)
    room_cells = set()
    for (x, y) in floors:
        for ox, oy in ((0, 0), (-1, 0), (0, -1), (-1, -1)):
            bx, by = x + ox, y + oy
            if {(bx, by), (bx + 1, by), (bx, by + 1), (bx + 1, by + 1)} <= fset:
                room_cells.add((x, y))
                break
    comp_at, comps = {}, []
    for c in floors:
        if c in comp_at:
            continue
        comp, queue = {c}, deque([c])
        while queue:
            px, py = queue.popleft()
            for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0)):
                n = (px + dx, py + dy)
                if n in fset and n not in comp and ((n in room_cells) == (c in room_cells)):
                    comp.add(n)
                    queue.append(n)
        idx = len(comps)
        comps.append(('방' if c in room_cells else '통로', comp))
        for cc in comp:
            comp_at[cc] = idx
    return comp_at, room_cells, comps


def probe(env, code):
    e = {k: v for k, v in os.environ.items() if not k.startswith("DUNGEON_")}
    e.update(PYTHONUTF8="1", DUNGEON_BRAIN_BACKEND="dummy", DUNGEON_BESTIARY_FILE="", DUNGEON_STATE_DIR=os.path.join(TMP, "probe"), **env)
    p = subprocess.run([sys.executable, "-c", code], cwd=HERE, env=e, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return json.loads(p.stdout.splitlines()[-1]) if p.returncode == 0 and p.stdout.strip() else {"err": p.stderr[-300:]}


def child_run(tag, **env):
    """러너를 자식 프로세스로 — (코드, 출력 꼬리, 스트림 원문, 줄들)."""
    st = os.path.join(TMP, tag)
    os.makedirs(st, exist_ok=True)
    e = {k: v for k, v in os.environ.items() if not k.startswith("DUNGEON_")}
    e.update(PYTHONUTF8="1", DUNGEON_BRAIN_BACKEND="dummy", DUNGEON_GM="0", DUNGEON_STEP_DELAY="0", DUNGEON_BESTIARY_FILE="",
             DUNGEON_PARTY_FILE=os.path.join(HERE, "party.json"), DUNGEON_STATE_DIR=st, DUNGEON_RUNS_DIR=os.path.join(TMP, tag + "_runs"),
             DUNGEON_ACTION_MODE="menu", DUNGEON_SKILLS="0", DUNGEON_TRPG_COMBAT="0", DUNGEON_RANDOM_SKILL="0",
             DUNGEON_SEED="7", DUNGEON_DEPTHS="2", **env)
    p = subprocess.run([sys.executable, "show_runner.py"], cwd=HERE, env=e, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    sp = os.path.join(st, "stream.jsonl")
    raw = open(sp, "rb").read() if os.path.isfile(sp) else b""
    return p.returncode, p.stdout.decode("utf-8", "replace")[-600:], raw, [json.loads(ln) for ln in raw.decode("utf-8").splitlines() if ln.strip()]


def sans_started(raw):
    lines = raw.split(b"\n")
    head = json.loads(lines[0])
    head.pop("started", None)
    return [json.dumps(head, ensure_ascii=False, sort_keys=True).encode("utf-8")] + lines[1:]


# ── ① 스위치 끔 = 옛 판 그대로 ─────────────────────────────────
print("── ① 스위치 끔 = 옛 판 그대로")
check("① 기본 Dungeon: ZONE_BLOCK 2 · 이름 임계 30/12/10(옛 값)",
      (G.Dungeon.ZONE_BLOCK, G.Dungeon.ZONE_BIG_ROOM, G.Dungeon.ZONE_SMALL_ROOM, G.Dungeon.ZONE_LONG_CORRIDOR) == (2, 30, 12, 10))
same = 0
for s in range(40):
    d = G.Dungeon(seed=s, w=56, h=20, scan=True, loops=True)
    a, b = d._zone_components(), old_components(d)
    same += (a[0] == b[0] and a[1] == b[1] and a[2] == b[2])
hand, _ = G.Dungeon.from_ascii(["###########", "#1..#.....#", "#...+.##..#", "#...#..#.>#", "###########"], scan=True)
check("① [40시드+손그림] K=2 분류 = 옛 2×2 코드와 같은 결과(번호·순서까지)",
      same == 40 and hand._zone_components() == old_components(hand), same)
base = G.Dungeon(seed=7, w=56, h=20, scan=True, loops=True)
lv0 = base.level_snapshot()
check("① 기본 level_snapshot: architecture 없음 · rooms[] 에 art_style 없음 · 통로 길이 = 칸 수",
      "architecture" not in lv0 and all("art_style" not in r for r in lv0["rooms"])
      and all(base._zone_len(z) == len(z.cells) for z in base.zones.values() if z.kind == '통로'))
CODE = ("import json, show_runner as s; print(json.dumps({'arch': s.DUNGEON_ARCH, 'cls': s.FLOOR_CLS.__module__ + '.' + s.FLOOR_CLS.__name__, "
        "'w': s.DUNGEON_W, 'h': s.DUNGEON_H, 'fp': [s._world_fingerprint().get('arch'), s._world_fingerprint().get('arch_v')], "
        "'fpkeys': len(s._world_fingerprint()), 'scan': s.SCAN_ON}))")
p_off, p_empty, p_junk = probe({}, CODE), probe({"DUNGEON_ARCH": ""}, CODE), probe({"DUNGEON_ARCH": "classic"}, CODE)
p_on, p_wh = probe({"DUNGEON_ARCH": "concept"}, CODE), probe({"DUNGEON_ARCH": "concept", "DUNGEON_W": "60", "DUNGEON_H": "30"}, CODE)
check("① 러너 스위치: 미설정 = '' = 모르는 값 → 옛 생성기 · 56×20 · 지문에 arch 없음",
      p_off == p_empty == p_junk and p_off.get("arch") == "" and p_off.get("cls") == "dungeon_gm.Dungeon"
      and (p_off.get("w"), p_off.get("h")) == (56, 20) and p_off.get("fp") == [None, None], p_off)
check("① 러너 스위치: concept → ConceptDungeon · W/H 미지정이면 42×34 · 명시하면 그 값 · 지문에 arch·arch_v(열쇠 둘만 늘어난다)",
      p_on.get("cls") == "dungeon_concept.ConceptDungeon" and (p_on.get("w"), p_on.get("h")) == (42, 34)
      and p_on.get("fp") == ["concept", 2] and (p_wh.get("w"), p_wh.get("h")) == (60, 30)
      and p_on.get("fpkeys") == p_off.get("fpkeys", 0) + 2, (p_on, p_wh))
p_scan0, p_off_scan0 = probe({"DUNGEON_ARCH": "concept", "DUNGEON_SCAN": "0"}, CODE), probe({"DUNGEON_SCAN": "0"}, CODE)
check("① 러너 스위치: concept 판은 DUNGEON_SCAN=0 을 줘도 scan 메타가 참(True)을 말한다 · 끈 판의 SCAN=0 은 옛 그대로",
      p_scan0.get("scan") is True and p_off_scan0.get("scan") is False, (p_scan0, p_off_scan0))
rc_a, out_a, raw_a, rows_a = child_run("off_unset", DUNGEON_TURNS="25", DUNGEON_W="40", DUNGEON_H="16")
rc_b, out_b, raw_b, rows_b = child_run("off_empty", DUNGEON_TURNS="25", DUNGEON_W="40", DUNGEON_H="16", DUNGEON_ARCH="")
check("① 끈 판의 스트림: 미설정과 '' 가 바이트 동일(started 제외) · run_meta 에 arch 없음 · level 에 architecture 없음",
      rc_a == 0 and rc_b == 0 and bool(raw_a) and sans_started(raw_a) == sans_started(raw_b)
      and "arch" not in rows_a[0] and "arch_v" not in rows_a[0]
      and all("architecture" not in r for r in rows_a if r["kind"] == "level"), (rc_a, rc_b, out_a[-200:]))

# ── ② 생성 스윕 ────────────────────────────────────────────
print("── ② 생성 스윕(깊이 1~%d × 25시드)" % DEPTHS)
NS = 25
errs, disc, unreach, colbad, stray, bossbad, nondet, rngmoved, built = [], 0, 0, 0, 0, 0, 0, 0, 0
for depth in range(1, DEPTHS + 1):
    for s in range(NS):
        try:
            d = build(s, depth)
        except Exception as e:                       # noqa: BLE001 — 예외 0 이 검사 대상
            errs.append((s, depth, "%s: %s" % (type(e).__name__, e)))
            continue
        built += 1
        cells = walk_cells(d)
        seen = flood(cells)
        disc += (seen != cells)
        spots = [tuple(d.exit)] + [(f.x, f.y) for f in d.features.values()] + [(m.x, m.y) for m in d.monsters] + [(t.x, t.y) for t in d.traps]
        unreach += sum(1 for c in spots if c not in seen)
        colbad += sum(1 for (x, y) in d.columns if d.grid[y][x] != WALL or d.walkable(x, y, []))
        planned = set(d.columns)
        stray += sum(1 for y in range(1, d.h - 1) for x in range(1, d.w - 1)
                     if (x, y) not in planned and d.grid[y][x] == WALL
                     and all(d.grid[yy][xx] in (FLOOR, DOOR) for xx, yy in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))))
        if depth == DEPTHS:
            front = d.boss_front()
            bossbad += not (d.boss is not None and d.boss.alive and d.sealed and front is not None and front in seen
                            and d.grid[front[1]][front[0]] == FLOOR)
        else:
            bossbad += (d.boss is not None)
        st0 = d.rng.getstate()
        snap = d.level_snapshot()
        rngmoved += (d.rng.getstate() != st0)
        random.seed(12345 + s)                       # 전역 random 을 흔들어도 같은 층(굴림은 전부 self.rng)
        random.random()
        nondet += (build(s, depth).level_snapshot() != snap)
check("② 예외 0 · %d층 생성" % (NS * DEPTHS), not errs and built == NS * DEPTHS, errs[:3])
check("② 바닥∪문 단일 연결 · 출구·피처·몹·함정 전부 도달", disc == 0 and unreach == 0, (disc, unreach))
check("② 기둥 = 벽 칸(못 밟는다) · 계획 밖 홀로 선 벽 0", colbad == 0 and stray == 0, (colbad, stray))
check("② 보스: 마지막 깊이에만 · 보스·봉인·boss_front(도달 가능한 바닥 칸)", bossbad == 0, bossbad)
check("② 결정론: 같은 시드 = 같은 level_snapshot(전역 random 무관) · level_snapshot 은 rng 를 안 굴린다", nondet == 0 and rngmoved == 0, (nondet, rngmoved))

# ── ③ 구역 건전성 ──────────────────────────────────────────
print("── ③ 구역 건전성(K=4 · 120시드)")
NZ = 120
zbad, nocorr, gbad, plusbad, ends, shares, styles = 0, 0, 0, 0, 0, [], set()
noshoulder = ndoors = 0
names3 = set()
for s in range(NZ):
    d = build(s)
    styles.update(d.room_styles.values())
    floors = {c for c in walk_cells(d) if d.grid[c[1]][c[0]] == FLOOR}
    zbad += (set(d.zone_at) != floors)
    nocorr += not any(z.kind == '통로' for z in d.zones.values())
    gbad += not zone_graph_connected(d)
    plus = {c for c in walk_cells(d) if d.grid[c[1]][c[0]] == DOOR}
    cells = {dr.cell for dr in d.doors.values() if dr.cell}
    plusbad += (plus != cells) or any(dr.zones[0] == dr.zones[1] for dr in d.doors.values())
    noshoulder += sum(1 for (x, y) in plus if not ((d.grid[y][x - 1] == WALL and d.grid[y][x + 1] == WALL)
                                                   or (d.grid[y - 1][x] == WALL and d.grid[y + 1][x] == WALL)))
    ndoors += len(plus)
    ends +=sum(len(z.junctions) + len(z.deadends) for z in d.zones.values())
    shares.append(max(len(z.cells) for z in d.zones.values()) / float(len(floors)))
    allseen = {'zone_seen': {z.id: set(z.cells) for z in d.zones.values()}}
    names3.update(d._zone_name(allseen, z.id) for z in d.zones.values())
big50 = sum(1 for v in shares if v >= .5)
print("  [실측] 가장 큰 구역 점유율 평균 %.3f · 최대 %.3f · 절반 이상 %d/%d (옛 2×2 로 읽으면 42/200 · 통로 구역 0개 56/100)"
      % (sum(shares) / NZ, max(shares), big50, NZ))
check("③ zone_at = 모든 바닥 칸 · 통로 구역이 있다 · 구역 그래프 단일 연결", zbad == 0 and nocorr == 0 and gbad == 0, (zbad, nocorr, gbad))
check("③ 모든 '+' 칸이 문 명사(cell)로 등재 · 문의 양쪽은 서로 다른 구역", plusbad == 0, plusbad)
check("③ 모든 문 타일의 양 어깨(좌우 또는 위아래)가 벽이다 — 문짝 옆으로 돌아 들어가는 문 0(09-20 수선 · 수선 전 6.1%%) · 문 %d개" % ndoors,
      noshoulder == 0 and ndoors > 0, (noshoulder, ndoors))
check("③ 가장 큰 구역 점유율: 최대 < 0.80 · 절반 이상인 시드 ≤ 6/120(실측 고정)", max(shares) < .80 and big50 <= 6, (max(shares), big50))
check("③ 갈림길·막다른 곳은 비어 있다(폭 1 길의 명사 — 넓은 통로 프로필은 말하지 않는다)", ends == 0, ends)
check("③ 방 유형이 다 나온다(hall·pillared_hall·gallery·chamber·two_columns)",
      styles == {'hall', 'pillared_hall', 'gallery', 'chamber', 'two_columns'}, styles)

# ── ③-2 방 수가 격자 넓이를 따라간다(09-20 개정) ──────────────
# 왜 이 자리에 핀을 박나: 격자만 키우면 방 수가 그대로라 늘어난 넓이가 전부 빈 암반과 긴 통로가 된다.
#   그리고 기준 격자(42×34)에서 뽑는 방 수가 한 칸이라도 달라지면 이 파일의 ①~⑧ 기준값과 옛 판의 결정론이 통째로 어긋난다.
print("── ③-2 방 수 비례(기준 42×34 = 옛 값 · 론처 54×42)")
BIG = {**KW, 'w': 54, 'h': 42}          # 론처 MAPS['concept'] 가 주는 크기
r42, r54, r26 = (ConceptDungeon(seed=0, **KW)._room_target_range(),
                 ConceptDungeon(seed=0, **BIG)._room_target_range(),
                 ConceptDungeon(seed=0, **{**KW, 'w': DC.MIN_W, 'h': DC.MIN_H})._room_target_range())
check("③-2 기준 격자(42×34)의 방 수 목표 = 옛 고정값 (5, 8) — 여기가 결정론의 닻이다", r42 == (5, 8), r42)
check("③-2 기준보다 작은 격자(%d×%d)도 (5, 8) 아래로 안 내려간다 — 마지막 폴백이 방 5개를 요구한다" % (DC.MIN_W, DC.MIN_H),
      r26 == (5, 8), r26)
check("③-2 54×42 는 목표가 는다(넓이비 %.2f 배)" % ((54 * 42) / float(42 * 34)), r54 == (8, 13), r54)
bshares, brooms, bfloors, bnocorr, bgbad = [], 0, 0, 0, 0
srooms = sfloors = 0
for s in range(NZ):
    ds = build(s)
    srooms += len(ds.rooms)
    sfloors += sum(1 for c in walk_cells(ds) if ds.grid[c[1]][c[0]] == FLOOR)
    db = ConceptDungeon(seed=s, **BIG)
    bfl = {c for c in walk_cells(db) if db.grid[c[1]][c[0]] == FLOOR}
    bshares.append(max(len(z.cells) for z in db.zones.values()) / float(len(bfl)))
    brooms += len(db.rooms)
    bfloors += len(bfl)
    bnocorr += not any(z.kind == '통로' for z in db.zones.values())
    bgbad += not zone_graph_connected(db)
print("  [실측 %d시드] 42×34 방 %.2f·바닥 %.0f·뭉갬 평균 %.3f  →  54×42 방 %.2f·바닥 %.0f·뭉갬 평균 %.3f(최대 %.3f)"
      % (NZ, srooms / float(NZ), sfloors / float(NZ), sum(shares) / NZ,
         brooms / float(NZ), bfloors / float(NZ), sum(bshares) / NZ, max(bshares)))
check("③-2 54×42: 방·바닥이 실제로 는다(방 ≥ 9 · 바닥 ≥ 650칸)", brooms / float(NZ) >= 9 and bfloors / float(NZ) >= 650,
      (brooms / float(NZ), bfloors / float(NZ)))
check("③-2 54×42 구역 건전성: 뭉갬 최대 < 0.50 · 절반 이상 0시드 · 통로 구역 있음 · 구역 그래프 단일 연결(실측 고정 — 42×34 보다 낫다)",
      max(bshares) < .50 and sum(1 for v in bshares if v >= .5) == 0 and bnocorr == 0 and bgbad == 0,
      (max(bshares), bnocorr, bgbad))

# ── ④ 문장층 ───────────────────────────────────────────────
print("── ④ 문장층")
check("④ 이름 임계 = 프로필 값: 넓은 방·방·작은 방·긴 통로·통로가 전부 실제로 갈린다",
      {'넓은 방', '방', '작은 방', '긴 통로', '통로'} <= names3, names3)
lenbad = wirebad = seen_len = 0
NAMES = {"1": "두란", "2": "카야"}
for s in range(12):
    d = build(s)
    for z in d.zones.values():
        if z.kind != '통로':
            continue
        lenbad += (d._zone_len(z) != max(z.w, z.h))
        b = G.spawn(d, '1', [])
        d.visited.discard((b['x'], b['y']))
        b['x'], b['y'] = min(z.cells)
        o = d.view(b, [b])
        zo = o.get('zone') or {}
        if zo.get('kind') != '통로' or zo.get('ends') != [] or ('len' in zo and zo['len'] != max(z.w, z.h)):
            wirebad += 1
        seen_len += ('len' in zo)
        w = brains._wire(o, NAMES, compose=True)
        wirebad += ('갈림길' in w) or ('막다른 곳' in w)
check("④ 통로 길이 = bbox 긴 변 · obs zone.ends = [] · 프롬프트에 '갈림길'·'막다른 곳' 없음(길이가 실린 관측 %d)" % seen_len,
      lenbad == 0 and wirebad == 0 and seen_len > 0, (lenbad, wirebad, seen_len))

# ── ⑤ 견고화 ───────────────────────────────────────────────
print("── ⑤ 견고화")
d = ConceptDungeon(seed=3, w=42, h=34, scan=False)
check("⑤ scan 강제: scan=False 를 줘도 켜진다 — 문 타일이 있으면 문 명사도 있다",
      d.scan is True and d.zones and sum(row.count(DOOR) for row in d.grid) == sum(1 for dr in d.doors.values() if dr.cell))
msgs = []
for (w_, h_) in ((40, 16), (24, 10), (25, 34), (42, 16)):
    try:
        ConceptDungeon(seed=1, w=w_, h=h_)
        msgs.append("no error %dx%d" % (w_, h_))
    except ValueError as e:
        msgs.append(str(e))
check("⑤ 최소 격자 가드: 작은 격자는 ValueError 가 이유를 말한다(randint 'empty range' 아님)",
      all(("최소 %dx%d" % (DC.MIN_W, DC.MIN_H)) in m for m in msgs), msgs)
small_ok = 0
for s in range(30):
    d = ConceptDungeon(seed=s, w=DC.MIN_W, h=DC.MIN_H, loops=True, n_monsters=2, n_traps=3, n_lurkers=1, boss=True)
    cells = walk_cells(d)
    small_ok += (len(d.rooms) >= 5 and flood(cells) == cells and tuple(d.exit) in cells and zone_graph_connected(d))
check("⑤ [30시드] 최소 격자 %d×%d: 완화 폴백이 방 5개 이상·연결된 층을 낸다(RuntimeError 없음)" % (DC.MIN_W, DC.MIN_H), small_ok == 30, small_ok)
wide_ok = 0
for s in range(20):
    d = ConceptDungeon(seed=s, w=56, h=20, loops=True)
    cells = walk_cells(d)
    wide_ok += (flood(cells) == cells and zone_graph_connected(d))
check("⑤ [20시드] 러너 옛 기본 격자(56×20)를 명시해도 연결된 층이 지어진다", wide_ok == 20, wide_ok)
asc, _ = ConceptDungeon.from_ascii(["#######", "#1...>#", "#######"], scan=True)
lva = asc.level_snapshot()
check("⑤ from_ascii 경유(__new__) 인스턴스: level_snapshot 이 건축 기록 없이도 돈다(부모 스냅샷 그대로)",
      "architecture" not in lva and all("art_style" not in r for r in lva["rooms"]))

# ── ⑥ 피클(D79) ────────────────────────────────────────────
print("── ⑥ 피클(D79)")
pk = 0
for s in range(10):
    d = build(s, 1 + s % DEPTHS)
    d2 = pickle.loads(pickle.dumps(d, protocol=pickle.HIGHEST_PROTOCOL))   # 방금 이 프로세스가 만든 바이트만 되읽는다
    pk += (type(d2) is ConceptDungeon and d2.level_snapshot() == d.level_snapshot() and d2.rng.getstate() == d.rng.getstate()
           and {k: (v.kind, v.cells) for k, v in d2.zones.items()} == {k: (v.kind, v.cells) for k, v in d.zones.items()}
           and {k: (v.zones, v.cell) for k, v in d2.doors.items()} == {k: (v.zones, v.cell) for k, v in d.doors.items()})
check("⑥ [10시드] dumps/loads 왕복: level_snapshot·rng·구역·문 동일", pk == 10, pk)
sys.path.insert(0, os.path.join(HERE, "art", "dungeon-v2"))
import concept_dungeon as LAB                        # noqa: E402 — 실험실의 재수출
sys.path.pop(0)
check("⑥ 클래스 모듈 = 루트 'dungeon_concept' · art/dungeon-v2 재수출은 같은 객체(피클 경로가 하나)",
      ConceptDungeon.__module__ == "dungeon_concept" and LAB.ConceptDungeon is ConceptDungeon)
sdir = os.path.join(TMP, "snap")
d = build(5, DEPTHS)
snapshot.write(sdir, {"run_id": "arch-gate", "d": d, "bots": [], "sheets": {}, "next_turn": 1, "stream_pos": 0, "seed": 5, "started": "x"},
               {"run_id": "arch-gate"})
got = probe({}, "import json, snapshot; s, m = snapshot.load(%r); d = s['d']; "
                "print(json.dumps({'cls': type(d).__module__ + '.' + type(d).__name__, 'grid': d.level_snapshot()['grid'], "
                "'arch': d.level_snapshot()['architecture']['version'], 'boss': d.boss is not None}))" % os.path.join(sdir, snapshot.PKL))
check("⑥ snapshot.write → 새 프로세스의 snapshot.load: 같은 클래스·같은 격자·보스까지",
      got.get("cls") == "dungeon_concept.ConceptDungeon" and got.get("grid") == d.level_snapshot()["grid"]
      and got.get("arch") == DC.ARCH_VERSION and got.get("boss") is True, str(got)[:200])

# ── ⑦ 더미 풀게임 ──────────────────────────────────────────
print("── ⑦ 더미 풀게임")


def play(seed, ticks=600, sig_out=False):
    dd = ConceptDungeon(seed=seed, w=42, h=34, loops=True)
    bb = [G.spawn(dd, '1', [])]
    bb.append(G.spawn(dd, '2', bb))
    done = False
    for _t in range(ticks):
        for b in bb:
            if not b['alive'] or b['won']:
                continue
            if b.get('order'):
                dd.step_order(b, bb)
            else:
                dd.act(b, G.dummy_brain(dd.view(b, bb), b['char']), bb)
        for _e in dd.monster_turn(bb):
            pass
        if all(b['won'] or not b['alive'] for b in bb):
            done = True
            break
    if sig_out:
        return (tuple((b['x'], b['y'], b['hp'], b['won'], tuple(sorted(b['bag'].items())) if isinstance(b['bag'], dict) else b['bag']) for b in bb),
                tuple((m.x, m.y, m.hp, m.alive) for m in dd.monsters))
    return done


done_n = sum(play(s) for s in range(12))
check("⑦ [12시드] 더미 2인 풀게임 항상 종결(600틱 안 — 실측 150시드 최장 258틱)", done_n == 12, done_n)
check("⑦ [4시드] 풀게임 결정론", all(play(s, sig_out=True) == play(s, sig_out=True) for s in range(4)))

# ── ⑧ 러너 ────────────────────────────────────────────────
print("── ⑧ 러너(ARCH=concept · compose)")


def run_main():
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            show_runner.main()
        except SystemExit:
            pass
    with open(os.path.join(STATE, "stream.jsonl"), encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


def ticks_of(rows, after=0):
    return [json.dumps({k: v for k, v in r.items()}, ensure_ascii=False, sort_keys=True)
            for r in rows if r["kind"] in ("tick", "level", "descend", "end") and r.get("turn", 0) > after]


ctrl = run_main()                                    # 대조군: 멈춤 없이 끝까지
meta = ctrl[0]
levels = [r for r in ctrl if r["kind"] == "level"]
check("⑧ run_meta: arch 'concept' · arch_v 2 · w×h 42×34 · compose 판",
      meta.get("arch") == "concept" and meta.get("arch_v") == DC.ARCH_VERSION and (meta.get("w"), meta.get("h")) == (42, 34)
      and bool(brains.COMPOSE), {k: meta.get(k) for k in ("arch", "arch_v", "w", "h")})
check("⑧ level 줄: architecture{version·columns·corridors·extra_connections} · rooms[].art_style · 격자 42×34 · 글리프는 #.+ 뿐",
      bool(levels) and all(set(lv.get("architecture") or {}) == {"version", "columns", "corridors", "extra_connections"}
                           and all("art_style" in r for r in lv["rooms"]) and len(lv["grid"]) == 34 and len(lv["grid"][0]) == 42
                           and set("".join(lv["grid"])) <= set("#.+") for lv in levels))
check("⑧ 층 전이: 1층 → 2층(descend) · 예외 없이 end 한 줄",
      [lv["depth"] for lv in levels] == [1, 2] and sum(r["kind"] == "end" for r in ctrl) == 1, [lv["depth"] for lv in levels])
check("⑧ 층을 짓는 세 자리가 같은 생성기: new_floor(1)·(2) 의 격자 = 스트림의 1·2층(주점 소문 미리보기 = 실제 층)",
      len(levels) == 2 and ["".join(r) for r in show_runner.new_floor(1, {}).grid] == levels[0]["grid"]
      and ["".join(r) for r in show_runner.new_floor(2, {}).grid] == levels[1]["grid"]
      and isinstance(show_runner.new_floor(1, {}), ConceptDungeon))

STOP_AT = 14
calls = {"n": 0}
_orig_stop = show_runner.run_control.stop_requested


def _fake_stop(state):
    calls["n"] += 1
    return {"id": "arch-gate", "pages": False} if calls["n"] == STOP_AT else None


show_runner.run_control.stop_requested = _fake_stop
try:
    stopped = run_main()
finally:
    show_runner.run_control.stop_requested = _orig_stop
pkl = os.path.join(STATE, snapshot.PKL)
check("⑧ 곱게 멈춤: stopped 줄(turn %d) · end 없음 · 스냅샷이 남는다" % (STOP_AT - 1),
      any(r["kind"] == "stopped" and r["turn"] == STOP_AT - 1 for r in stopped) and not any(r["kind"] == "end" for r in stopped)
      and os.path.isfile(pkl))
show_runner.RESUME_PATH = pkl
_arch = show_runner.DUNGEON_ARCH
show_runner.DUNGEON_ARCH = ""                        # 생성기가 다른 러너가 이 스냅샷을 열면 — 지문이 거절한다(파일은 그대로)
_s, _m, fail = show_runner._load_resume()
show_runner.DUNGEON_ARCH = _arch
check("⑧ ARCH 가 다른 러너는 이 스냅샷을 거절한다(사유에 arch) · 스냅샷은 그대로",
      _s is None and fail is not None and "arch" in fail.get("reason", "") and os.path.isfile(pkl), fail)
resumed = run_main()
show_runner.RESUME_PATH = ""
rs_meta = [r for r in resumed if r["kind"] == "run_meta"]
check("⑧ 이어가기: run_meta 한 줄(resume_failed 없음) · resume 줄 · 끝까지 · 끝난 판의 스냅샷은 지워진다",
      len(rs_meta) == 1 and "resume_failed" not in rs_meta[0] and any(r["kind"] == "resume" for r in resumed)
      and sum(r["kind"] == "end" for r in resumed) == 1 and not os.path.isfile(pkl))
check("⑧ 이어간 판 = 끊기지 않은 판: 멈춘 틱 뒤의 tick·level·descend·end 줄이 대조군과 같다(층을 다시 짓지 않았다)",
      ticks_of(resumed, STOP_AT - 1) == ticks_of(ctrl, STOP_AT - 1) and len(ticks_of(ctrl, STOP_AT - 1)) > 5,
      (len(ticks_of(resumed, STOP_AT - 1)), len(ticks_of(ctrl, STOP_AT - 1))))
rc_m, out_m, raw_m, rows_m = child_run("on_menu", DUNGEON_TURNS="30", DUNGEON_ARCH="concept")
check("⑧ menu 모드 자식 프로세스 판(ARCH=concept): 코드 0 · arch 메타 · end 한 줄",
      rc_m == 0 and rows_m and rows_m[0].get("arch") == "concept" and (rows_m[0].get("w"), rows_m[0].get("h")) == (42, 34)
      and sum(r["kind"] == "end" for r in rows_m) == 1, (rc_m, out_m[-300:]))
rc_s, out_s, _raw, _rows = child_run("on_small", DUNGEON_TURNS="5", DUNGEON_ARCH="concept", DUNGEON_W="40", DUNGEON_H="16")
check("⑧ 너무 작은 격자를 명시한 concept 판은 시작에서 이유를 말하고 선다(조용히 옛 생성기로 바꾸지 않는다)",
      rc_s != 0 and "최소" in out_s, (rc_s, out_s[-200:]))

# ── ⑨ 자기 등록 ─────────────────────────────────────────────
print("── ⑨ 등록")
with open(os.path.join(HERE, "_run_gates.sh"), encoding="utf-8") as f:
    check("⑨ _run_gates.sh 에 verify_arch 등록", "verify_arch" in f.read())

print("=" * 44)
if C.failed:
    print("RESULT: %d FAIL" % C.failed)
    raise SystemExit(1)
print("ALL PASS — verify_arch (D88 던전 생성 프로필 concept · 구역 블록 K=4 · 끔=옛 판 그대로)")

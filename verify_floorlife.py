# -*- coding: utf-8 -*-
"""D92 던전의 물건들(2026-09-20) — 엔진 소유 소품(통행 차단) · 뒤지는 통 · 읽는 석판 · 모닥불 — 헤들리스 검증. 실 LLM 0콜.
(파트너 "던전에 추가 오브젝트나 몬스터 혹은 이벤트를 넣는 것만 하면 될 것 같아" ·
 작업지시서 art/dungeon-v2/IMPLEMENTATION_GUIDE.md '소품 배치'와 '본편 통합 순서' 2~3.
 소품은 생성 프로필(DUNGEON_ARCH=concept)에 딸린 지형의 일부고, 살림(뒤지는 통·석판·모닥불)은 스위치 DUNGEON_FLOOR_LIFE 뒤다.)
게이트:
  ① 끈 판 그대로: floor_life 를 안 준 층 == 준 층(꺼짐) — 스냅샷·관측·rng 동일 · 기본 Dungeon 엔 props 가 없다(level 줄에도)
  ② [12시드 × 깊이 1~5] 소품 배치 뒤에도 모든 바닥·출구·피처가 서로 닿는다(엔진의 이동 규칙 = 8방향·대각 코너컷 금지) ·
     소품은 바닥 칸에만 · 문 3×3·함정 칸·몹 주변 8칸·피처와 직교 인접 칸은 비어 있다 · 격자·구역 분류는 소품을 바닥으로 본다
  ③ 소품 칸에는 아무도 서지 않는다: spawn(3인) · arrive_cells(러너 도착 칸) · boss_front(D67 프리셋 닻) · walkable·몹 걸음·거리맵
  ④ [6시드] 더미 풀판: 캐릭터·몹이 소품 칸을 밟은 적 0 · 판은 끝난다
  ⑤ 스트림: concept 자식 러너의 level 줄에 props[{id,kind,x,y,blocks}] — 클라이언트 어휘(dungeonDecor.ts PROP_KINDS)와 같은 낱말
  ⑥ 뒤지기: 승격한 소품은 곁에 설 자리가 있다 · 같은 세계 = 같은 결과(결정론) · 두 번째는 used_up(once) · 소지 변화
  ⑦ 석판: 본문의 숫자가 실제 층과 같다 · 계단의 방향·위치는 말하지 않는다 · 보스층엔 봉인 석판 하나(BOSS_FLOOR_NOTICE 와 같은 사실)
  ⑧ 모닥불: 2층부터 · once 가 아니다(쓸 때마다) · 상한은 maxhp
  ⑨ 피클 왕복: 소품·다 쓴 상태·석판 본문이 남는다 · 그 칸이 없는 옛 스냅샷도 그대로 돈다(클래스 속성·getattr)
  ⑩ 배선: 러너 스위치·생성 세 자리·지문·run_meta 는 켠 판에만 · _run_gates.sh 등록
  ⑪ 관측(09-20 수선): 눈에 든 소품이 sights.blocked(방위·거리·칸 수)·7×7 그림·판단 프롬프트에 사실로 실린다
     — D19 전제 1 '그림에 그려진 구조가 문장에 없으면 계약 위반'. 소품이 없는 세계의 관측은 글자까지 그대로
(기존 verify 는 별도 실행 — '스위치 끈 판 = 옛 판과 바이트 동일'의 본 검사는 verify_skill_off, 지형 계약은 verify_arch.)
"""
import json
import os
import pickle
import re
import subprocess
import sys
import tempfile

TMP = tempfile.mkdtemp(prefix="wl_floorlife_")
STATE = os.path.join(TMP, "state")
os.makedirs(STATE, exist_ok=True)
os.environ.update(DUNGEON_GM="0", DUNGEON_STEP_DELAY="0", DUNGEON_BESTIARY_FILE="", DUNGEON_STATE_DIR=STATE,
                  DUNGEON_BRAIN_BACKEND="dummy")

import brains                                        # noqa: E402
brains._call_claude = lambda prompt, model="haiku": ""   # LLM 무력화(0콜)
import dungeon_concept as DC                         # noqa: E402
import dungeon_gm as G                               # noqa: E402
import entities as ENT                               # noqa: E402
import interactables as IA                           # noqa: E402
import show_runner                                   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ORTH = ((0, -1), (0, 1), (1, 0), (-1, 0))
LIFE_TYPES = tuple(G.Dungeon.LIFE_RUMMAGE_IDS) + (G.Dungeon.LIFE_TABLET_ID, G.Dungeon.LIFE_CAMPFIRE_ID)


class C:
    failed = 0
    n = 0


def check(name, cond, extra=None):
    C.n += 1
    print(("  OK   " if cond else " FAIL  ") + name + ("" if cond or extra is None else "  << %s" % (extra,)))
    if not cond:
        C.failed += 1


def src(rel):
    with open(os.path.join(HERE, rel), encoding="utf-8") as f:
        return f.read()


def build(seed, depth=1, life=True, boss=False, cls=DC.ConceptDungeon, **over):
    kw = dict(seed=seed, depth=depth, n_monsters=2 + depth, n_traps=3, n_lurkers=1, n_potions=1, n_gear=3,
              loops=True, scan=True, floor_life=life, boss=boss)
    kw.update(over)
    return cls(**kw)


def standable(d, x, y):
    """엔진이 '설 수 있다'고 보는 칸(몹·봇 무관한 지형만) — 소품은 바닥을 막는다."""
    return 0 <= x < d.w and 0 <= y < d.h and d.grid[y][x] != G.WALL and not d.prop_at(x, y)


def flood(d):
    """엔진의 이동 규칙으로 닿는 칸 — 8방향, 대각은 양 직교 칸이 둘 다 열려 있을 때만(코너컷 금지)."""
    cells = {(x, y) for y in range(d.h) for x in range(d.w) if standable(d, x, y)}
    start = min(cells)
    seen, todo = {start}, [start]
    for x, y in todo:                    # todo 는 돌면서 늘어난다(BFS)
        for dx, dy in G.MOVES.values():
            nx, ny = x + dx, y + dy
            if (nx, ny) in seen or (nx, ny) not in cells:
                continue
            if dx and dy and not (standable(d, x + dx, y) and standable(d, x, y + dy)):
                continue
            seen.add((nx, ny))
            todo.append((nx, ny))
    return seen, cells


def life_feats(d, *types):
    return [f for f in d.features.values() if f.type in (types or LIFE_TYPES)]


def obs_sig(d, bots):
    return json.dumps([d.view(b, bots) for b in bots], ensure_ascii=False, sort_keys=True, default=str)


print("── ① 끈 판 그대로")
base_kw = dict(seed=7, w=44, h=18, n_monsters=2, n_traps=3, n_lurkers=1, scan=True, loops=True)
d_unset, d_off = G.Dungeon(**base_kw), G.Dungeon(floor_life=False, **base_kw)
fresh_rng = d_off.rng.getstate()                     # 스폰이 굴림을 쓰기 전에 떠 둔다(아래 세 번째 검사의 기준)
b_unset = [G.spawn(d_unset, "1", [])]
b_off = [G.spawn(d_off, "1", [])]
check("① floor_life 미지정 == floor_life=False — 스냅샷·관측·rng 상태 동일",
      d_unset.level_snapshot() == d_off.level_snapshot() and obs_sig(d_unset, b_unset) == obs_sig(d_off, b_off)
      and d_unset.rng.getstate() == d_off.rng.getstate())
check("① 끈 판엔 소품도 살림도 없다 · level 줄에 props 칸이 없다(옛 소비자가 보던 그대로)",
      d_off.props == () and d_off.prop_cells == frozenset() and not life_feats(d_off)
      and "props" not in d_off.level_snapshot() and d_off.floor_life is False)
d_on = G.Dungeon(floor_life=True, **base_kw)
check("① 켠 판은 살림이 는다 — 옛 생성기(소품 없음)에도 뒤지는 통·석판이 선다 · 굴림은 그대로(판정 rng 무소비)",
      bool(life_feats(d_on)) and d_on.props == () and d_on.rng.getstate() == fresh_rng
      and len(d_on.features) > len(d_off.features))
c_off, c_on = build(3, 2, life=False), build(3, 2, life=True)
check("① concept 프로필: 소품은 스위치와 무관한 지형의 일부(끈 판에도 있다) · 살림만 스위치를 탄다",
      bool(c_off.props) and c_off.props == c_on.props and not life_feats(c_off) and bool(life_feats(c_on))
      and c_off.level_snapshot()["grid"] == c_on.level_snapshot()["grid"])

print("── ② [12시드 × 깊이 1~5] 소품 배치 뒤의 연결성·비우는 칸")
bad = []
for seed in range(1, 13):
    for depth in range(1, 6):
        d = build(seed, depth, boss=(depth == 5))
        seen, cells = flood(d)
        tag = (seed, depth)
        if seen != cells:
            bad.append(("연결", tag, len(cells) - len(seen)))
        if not all(d.grid[p["y"]][p["x"]] == G.FLOOR for p in d.props):
            bad.append(("바닥아님", tag, None))
        if any(not standable(d, f.x, f.y) and f.type not in G.Dungeon.LIFE_RUMMAGE_IDS for f in d.features.values()):
            bad.append(("피처가 소품 칸", tag, None))
        if any(d.prop_at(t.x, t.y) for t in d.traps) or any(d.prop_at(m.x, m.y) for m in d.monsters):
            bad.append(("함정·몹이 소품 칸", tag, None))
        for p in d.props:
            x, y = p["x"], p["y"]
            if any(d.grid[y + dy][x + dx] == G.DOOR for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                   if 0 <= x + dx < d.w and 0 <= y + dy < d.h):
                bad.append(("문 곁", tag, (x, y)))
            if any(abs(f.x - x) + abs(f.y - y) <= 1 and f.type not in LIFE_TYPES
                   for f in d.features.values()):      # 살림(석판·모닥불)은 소품 **뒤에** 놓이므로 이 규칙의 대상이 아니다
                bad.append(("피처 곁", tag, (x, y)))
            if any(max(abs(m.x - x), abs(m.y - y)) <= 1 for m in d.monsters):
                bad.append(("몹 곁", tag, (x, y)))
        if set("".join(d.level_snapshot()["grid"])) - set("#.+"):
            bad.append(("새 글리프", tag, None))
check("② 모든 바닥·출구·피처가 서로 닿는다(8방향 코너컷 금지) · 문 3×3·피처 곁·몹 8칸·함정 칸은 비었다 · 격자 글리프 불변",
      not bad, bad[:4])
d = build(5, 3)
check("② 스캐너는 소품을 바닥으로 본다 — 전 바닥 구역 배정 불변(소품 칸도 구역이 있다)",
      bool(d.zones) and set(d.zone_at) == {(x, y) for y in range(d.h) for x in range(d.w) if d.grid[y][x] == G.FLOOR}
      and all((p["x"], p["y"]) in d.zone_at for p in d.props))
check("② 소품 종류 어휘 = 클라이언트 그림 어휘(game/src/scene/dungeonDecor.ts PROP_KINDS)",
      {p["kind"] for s in range(1, 8) for p in build(s, 2).props}
      <= set(re.findall(r"(\w+): \d", re.search(r"PROP_KINDS[^=]*= \{([^}]*)\}", src(os.path.join("game", "src", "scene", "dungeonDecor.ts"))).group(1))))

print("── ③ 소품 칸에는 아무도 서지 않는다")
stood = []
for seed in range(1, 9):
    d = build(seed, 5, boss=True)
    bots = []
    for c in ("1", "2"):
        bots.append(G.spawn(d, c, bots))
    stood += [(seed, b["char"]) for b in bots if d.prop_at(b["x"], b["y"])]
    stood += [(seed, "arrive", c) for c in show_runner.arrive_cells(d, *d.exit, 9) if d.prop_at(*c)]
    fr = d.boss_front()
    if fr is not None and d.prop_at(*fr):
        stood.append((seed, "boss_front", fr))
check("③ spawn·arrive_cells·boss_front 가 소품 칸을 피한다(8시드 × 2인)", not stood, stood[:4])
d = build(4, 2)
px, py = d.props[0]["x"], d.props[0]["y"]
check("③ walkable·몹 걸음·거리맵이 같은 눈 — 소품 칸은 못 들어가고, 지형 거리맵에도 없다",
      d.walkable(px, py, []) is False and d._monster_walkable(px, py, []) is False
      and d.walkable(px, py, [], ally_pass=True) is False and (px, py) not in d._terrain_dist_from(*d.exit))

print("── ④ [6시드] 더미 풀판 — 소품 칸을 밟은 적 0")
walked, ended = [], 0
for seed in range(1, 7):
    d = build(seed, 1)
    bots = [G.spawn(d, "1", [])]
    bots.append(G.spawn(d, "2", bots))
    for _t in range(400):
        for b in bots:
            if not b["alive"] or b["won"]:
                continue
            if b.get("order"):
                d.step_order(b, bots)
            else:
                d.act(b, G.dummy_brain(d.view(b, bots), b["char"]), bots)
            if d.prop_at(b["x"], b["y"]):
                walked.append((seed, b["char"], b["x"], b["y"]))
        for _e in d.monster_turn(bots):
            pass
        walked += [(seed, m.kind, m.x, m.y) for m in d.monsters if m.alive and d.prop_at(m.x, m.y)]
        if all(b["won"] or not b["alive"] for b in bots):
            ended += 1
            break
check("④ 캐릭터·몹이 소품 칸에 선 적 0 · 6판 전부 끝난다", not walked and ended == 6, (walked[:3], ended))

print("── ⑤ 스트림 level 줄의 props")
st = os.path.join(TMP, "runstate")
os.makedirs(st, exist_ok=True)
env = {k: v for k, v in os.environ.items() if not k.startswith("DUNGEON_")}
env.update(PYTHONUTF8="1", DUNGEON_BRAIN_BACKEND="dummy", DUNGEON_GM="0", DUNGEON_STEP_DELAY="0",
           DUNGEON_BESTIARY_FILE="", DUNGEON_PARTY_FILE=os.path.join(HERE, "party.json"), DUNGEON_STATE_DIR=st,
           DUNGEON_RUNS_DIR=os.path.join(TMP, "runs"), DUNGEON_ACTION_MODE="menu", DUNGEON_SKILLS="0",
           DUNGEON_TRPG_COMBAT="0", DUNGEON_RANDOM_SKILL="0", DUNGEON_SEED="9", DUNGEON_DEPTHS="1",
           DUNGEON_TURNS="8", DUNGEON_ARCH="concept", DUNGEON_FLOOR_LIFE="1")
rc = subprocess.run([sys.executable, "-c", "import show_runner as s; s.main()"], cwd=HERE, env=env,
                    capture_output=True, timeout=300).returncode
rows = [json.loads(ln) for ln in open(os.path.join(st, "stream.jsonl"), encoding="utf-8") if ln.strip()]
lv = next((r for r in rows if r.get("kind") == "level"), {})
props = lv.get("props") or []
check("⑤ 자식 러너(concept · 살림 켬): 코드 0 · level 줄의 props[{id,kind,x,y,blocks}] · run_meta 열쇠 · 살림 피처가 선다",
      rc == 0 and bool(props) and all(set(p) == {"id", "kind", "x", "y", "blocks"} and p["blocks"] is True for p in props)
      and rows[0].get("floor_life") is True and rows[0].get("arch") == "concept"
      and any(f["type"] in LIFE_TYPES for f in lv.get("features") or []), (rc, len(props)))
check("⑤ 스트림의 props 는 격자 바닥 칸이고 피처·함정과 겹치지 않는다(승격한 것만 같은 칸)",
      all(lv["grid"][p["y"]][p["x"]] == "." for p in props)
      and all(not any(f["x"] == p["x"] and f["y"] == p["y"] and f["type"] not in G.Dungeon.LIFE_RUMMAGE_IDS
                      for f in lv["features"]) for p in props)
      and not any(t["x"] == p["x"] and t["y"] == p["y"] for t in lv["traps"] for p in props))

print("── ⑥ 뒤지기")
d = build(6, 3)
rums = life_feats(d, *G.Dungeon.LIFE_RUMMAGE_IDS)
check("⑥ 승격한 소품은 소품 칸에 서 있고 곁에 설 자리가 있다(못 뒤지는 통을 만들지 않는다) · 수는 2~4",
      bool(rums) and G.Dungeon.LIFE_RUMMAGE[0] <= len(rums) <= G.Dungeon.LIFE_RUMMAGE[1]
      and all(d.prop_at(f.x, f.y) for f in rums)
      and all(any(standable(d, f.x + dx, f.y + dy) for dx, dy in ORTH) for f in rums), len(rums))
f0 = sorted(rums, key=lambda f: f.id)[0]
d2 = build(6, 3)
bot = G.spawn(d, "1", [])
bot["x"], bot["y"] = next((f0.x + dx, f0.y + dy) for dx, dy in ORTH if standable(d, f0.x + dx, f0.y + dy))
bot2 = G.spawn(d2, "1", [])
bot2["x"], bot2["y"] = bot["x"], bot["y"]
r1 = d._interact(bot, "f%d" % f0.id, [bot])
r2 = d2._interact(bot2, "f%d" % f0.id, [bot2])
r3 = d._interact(bot, "f%d" % f0.id, [bot])
check("⑥ 같은 세계 = 같은 것이 나온다(결정론 · 판정 rng 무접촉) · 두 번째는 used_up(once) · 피처는 남는다",
      r1.get("result") == "rummaged" and r1.get("got") == r2.get("got") and r1["got"] in ("potion", "treasure", "nothing")
      and r3.get("result") == "used_up" and d.feature_at(f0.x, f0.y) is not None, (r1, r3))

print("── ⑦ 석판")
tabs = []
for seed in range(1, 10):
    for depth in (1, 5):
        dd = build(seed, depth, boss=(depth == 5))
        ts = life_feats(dd, G.Dungeon.LIFE_TABLET_ID)
        for f in ts:
            tabs.append((dd, f, (dd.use_over or {})[f.id]["text"]))
        if not (G.Dungeon.LIFE_TABLETS[0] <= len(ts) <= G.Dungeon.LIFE_TABLETS[1]):
            tabs.append((dd, None, "개수 %d" % len(ts)))
nums = [(t, dd) for dd, f, t in tabs if f is not None]
check("⑦ 본문의 숫자가 실제 층과 같다 — 함정 수·방 수·처음 있던 몹",
      all(f is not None for dd, f, t in tabs)
      and all((("함정은 %d개" % len(dd.traps)) in t if "함정" in t else True)
              and (("방 %d개" % len(dd.rooms)) in t if "방 " in t else True) for t, dd in nums), [t for t, _ in nums][:3])
check("⑦ 계단의 방향·위치는 말하지 않는다(D19 '층 지도 안 줌')",
      not any(w in t for t, _ in nums for w in ("계단", "출구", "동쪽", "서쪽", "남쪽", "북쪽")))
seal = [(dd, f, t) for dd, f, t in tabs if f is not None and t == G.Dungeon.LIFE_TABLET_SEAL]
check("⑦ 봉인 석판은 보스층에만·층당 하나 — BOSS_FLOOR_NOTICE 와 같은 사실(보스가 쓰러져야 출구가 열린다)",
      bool(seal) and all(dd.boss_on for dd, f, t in seal)
      and all(sum(1 for dd2, f2, t2 in seal if dd2 is dd) == 1 for dd, f, t in seal)
      and "봉인" in G.BOSS_FLOOR_NOTICE)
dd, f, _t = seal[0]
bot = G.spawn(dd, "1", [])
bot["x"], bot["y"] = next((f.x + dx, f.y + dy) for dx, dy in ORTH if standable(dd, f.x + dx, f.y + dy))
res = dd._interact(bot, "f%d" % f.id, [bot])
check("⑦ 읽으면 그 층의 본문이 돌아온다(정의 한 장의 글이 아니라 세계의 상태 — use_over) · 문장에 JSON 폴백 없음",
      res.get("result") == "read" and res.get("text") == G.Dungeon.LIFE_TABLET_SEAL
      and IA.prose(res) and G.Dungeon.LIFE_TABLET_SEAL in IA.prose(res))

print("── ⑧ 모닥불")
fires = {depth: sum(bool(life_feats(build(s, depth), G.Dungeon.LIFE_CAMPFIRE_ID)) for s in range(1, 13))
         for depth in (1, 2, 3)}
check("⑧ 1층엔 없고 2층부터 층당 0~1(12시드)", fires[1] == 0 and 0 < fires[2] <= 12 and 0 < fires[3] <= 12, fires)
dd = next(d_ for d_ in (build(s, 3) for s in range(1, 30)) if life_feats(d_, G.Dungeon.LIFE_CAMPFIRE_ID))
f = life_feats(dd, G.Dungeon.LIFE_CAMPFIRE_ID)[0]
bot = G.spawn(dd, "1", [])
bot["x"], bot["y"] = next((f.x + dx, f.y + dy) for dx, dy in ORTH if standable(dd, f.x + dx, f.y + dy))
bot["hp"] = bot["maxhp"] - 3
a = dd._interact(bot, "f%d" % f.id, [bot])
b = dd._interact(bot, "f%d" % f.id, [bot])
bot["hp"] = bot["maxhp"]
c = dd._interact(bot, "f%d" % f.id, [bot])
check("⑧ 곁에서 쓰면 HP — once 가 아니다(쓸 때마다) · 상한은 maxhp · '안전'은 약속하지 않는다(사실만)",
      a.get("result") == "warmed" and a.get("heal") == 2 and b.get("result") == "warmed" and b.get("heal") == 1
      and c.get("result") == "warmed" and c.get("heal") == 0 and bot["hp"] == bot["maxhp"]
      and "안전" not in (IA.prose(a) or ""), (a, b, c))

print("── ⑨ 피클 왕복")
dd = build(8, 4)
f = sorted(life_feats(dd, *G.Dungeon.LIFE_RUMMAGE_IDS), key=lambda x: x.id)[0]
bot = G.spawn(dd, "1", [])
bot["x"], bot["y"] = next((f.x + dx, f.y + dy) for dx, dy in ORTH if standable(dd, f.x + dx, f.y + dy))
dd._interact(bot, "f%d" % f.id, [bot])
back = pickle.loads(pickle.dumps(dd, protocol=pickle.HIGHEST_PROTOCOL))
check("⑨ 소품·다 쓴 상태·석판 본문이 되살아난다 · 같은 층",
      back.props == dd.props and back.prop_cells == dd.prop_cells and back.use_spent.keys() == dd.use_spent.keys()
      and back.use_over == dd.use_over and back.level_snapshot() == dd.level_snapshot())
old = pickle.loads(pickle.dumps(dd, protocol=pickle.HIGHEST_PROTOCOL))
for attr in ("props", "prop_cells", "floor_life", "use_over"):
    old.__dict__.pop(attr, None)                       # 그 칸이 없던 옛 스냅샷(D79)
check("⑨ 그 칸이 없는 옛 스냅샷도 그대로 돈다 — 클래스 속성·getattr(소품 없음 = 옛 판)",
      old.prop_at(0, 0) is False and old.walkable(*dd.exit, []) is True
      and IA.use_of(old, old.features[f.id]) is not None and "props" not in old.level_snapshot())
asc, _ = DC.ConceptDungeon.from_ascii(["#######", "#1...>#", "#######"], scan=True)
check("⑨ from_ascii(__new__) 경유 인스턴스도 산다 — 소품 없음·살림 없음·level 줄에 props 없음",
      asc.props == () and asc.floor_life is False and "props" not in asc.level_snapshot() and asc.prop_at(2, 1) is False)

print("── ⑩ 배선")
rs = src("show_runner.py")
check("⑩ 러너: 스위치(기본 0) · 층 생성 세 자리에 같은 인자 · 지문·run_meta 는 켠 판에만 · 도착 칸도 같은 눈",
      'DUNGEON_FLOOR_LIFE", "0") == "1"' in rs and rs.count("floor_life=FLOOR_LIFE_ON,") == 3
      and rs.count('**({"floor_life": True} if FLOOR_LIFE_ON else {})') == 2
      and "d.prop_at(nx, ny)" in rs and show_runner.FLOOR_LIFE_ON is False)
gm, dc, ia = src("dungeon_gm.py"), src("dungeon_concept.py"), src("interactables.py")
check("⑩ 엔진: 막는 자리가 한 눈(walkable·몹 걸음·거리맵·프런티어·스폰) · 굴림은 해시(_life_roll) · 소품 배치는 프로필",
      gm.count("prop_cells") >= 4 and "def prop_at" in gm and "def _life_roll" in gm
      and "not dungeon.prop_at(x, y)" in gm and "def _place_props" in dc
      and "self.rng" not in dc.split("def _place_props")[1].split("def boss_front")[0]
      and "use_over" in ia)
check("⑩ 정의(JSON) 한 장씩 — 뒤지는 것 셋·석판·모닥불이 엔티티 저장소에 있고 엔진 예약 타입이 아니다",
      all(ENT.get(e)["type"] == e and (ENT.get(e)["comps"].get("use") or {}).get("kind") for e in LIFE_TYPES)
      and not (set(LIFE_TYPES) & set(ENT.USE_RESERVED_TYPES))
      and {(f.type, f.name) for f in life_feats(build(2, 3))} <= {(o["type"], o["name"]) for o in ENT.by_kind("object")})
check("⑩ 게이트 등록(_run_gates.sh)", re.search(r"\bverify_floorlife\b", src("_run_gates.sh")) is not None)
# 09-20 수선: 새 피처 다섯에 관전 화면의 그림이 없으면 Kenney 폴백 타일(정체불명 회색 칸)이 선다 — 다섯 다 제 그림이 있어야 하고,
#   승격한 소품은 소품 레이어가 이미 그렸으니 피처 루프가 그 칸을 건너뛰어야 한다(같은 물건이 둘로 보이지 않게).
flat = src(os.path.join("game", "src", "scene", "dungeonPrototypeFlat.ts"))
ds = src(os.path.join("game", "src", "scene", "DungeonScene.ts"))
check("⑩ 관전 화면: 새 피처 다섯에 제 그림이 있다(dungeonLifeVisual) · 옛 그림 렌더러도 같이 본다 · 소품 칸은 두 번 안 그린다",
      all(("key === 'feat:%s'" % t) in flat for t in LIFE_TYPES)
      and "dungeonLifeVisual" in flat and "?? dungeonLifeVisual(key)" in ds
      and "this.propCells.has(ft.x + ',' + ft.y)" in ds)

print("── ⑪ 관측 — 그림에 선 소품이 문장에도 있다(09-20 수선)")
# D19 전제 1: 그림에 그려진 구조가 문장에 없으면 계약 위반. 소품은 통행을 막는데 격자는 '.'(바닥)라
#   문장·그림 둘 다에 사실이 실려야 한다. 대상 id 도 동사도 없다 — '지나갈 수 없다'는 사실뿐.
d = build(3, 2)
bots = [G.spawn(d, "1", [])]
here = next(((px + dx, py + dy) for (px, py) in sorted(d.prop_cells) for dx, dy in ORTH
             if d.walkable(px + dx, py + dy, bots) and not d.feature_at(px + dx, py + dy)), None)
bots[0]["x"], bots[0]["y"] = here
obs = d.view(bots[0], bots)
blk = obs["sights"].get("blocked") or []
seen_props = {c for c in d.visible_cells(*here, G.SIGHT) if c in d.prop_cells}
check("⑪ 눈에 든 소품이 sights.blocked 에 방위·거리·칸 수로 실린다(대상 id 없음 · 합계 = 실제 보이는 소품 칸)",
      bool(blk) and sum(e["n"] for e in blk) == len(seen_props)
      and all(set(e) == {"bearing", "dist", "n"} for e in blk)
      and all(e["dist"] == min(max(abs(x - here[0]), abs(y - here[1])) for (x, y) in seen_props
                               if d._bearing(x - here[0], y - here[1]) == e["bearing"]) for e in blk), blk)
check("⑪ 7×7 그림도 같은 사실 — 소품 칸은 바닥('.')이 아니다 · legend 에 낱말 하나",
      any(G.PROP_BLOCK in row for row in obs["ascii_view"])
      and obs["legend"].get(G.PROP_BLOCK) and G.PROP_BLOCK not in "@#.+$>M^=~![)T "
      and sum(row.count(G.PROP_BLOCK) for row in obs["ascii_view"]) == len(seen_props))
txt = brains._wire(obs)
txt = txt if isinstance(txt, str) else "\n".join(str(x) for x in txt)
check("⑪ 판단 프롬프트에 그 줄이 있다(방위별 한 줄 — 조언·지시 없이 사실만)",
      all(("큰 물건이 바닥 %d칸을 채우고 있다 %dm (그 칸은 지나갈 수 없다)" % (e["n"], e["dist"])) in txt for e in blk))
d_bare = G.Dungeon(seed=7, w=44, h=18, n_monsters=2, n_traps=3, n_lurkers=1, scan=True, loops=True, floor_life=True)
b_bare = [G.spawn(d_bare, "1", [])]
o_bare = d_bare.view(b_bare[0], b_bare)
check("⑪ 소품이 없는 세계(옛 생성기·마을)의 관측은 글자까지 그대로 — blocked 키도 legend 낱말도 안 생긴다",
      "blocked" not in o_bare["sights"] and G.PROP_BLOCK not in o_bare["legend"]
      and not any(G.PROP_BLOCK in row for row in o_bare["ascii_view"]))

print("=" * 44)
if C.failed:
    print("RESULT: %d FAILED / %d" % (C.failed, C.n))
    raise SystemExit(1)
print("ALL PASS — verify_floorlife (D92 던전의 물건들: 끈 판 동일·연결성·통행 차단·뒤지기·석판·모닥불·스트림·피클·러너·관측, %d checks, 실 LLM 0콜)" % C.n)

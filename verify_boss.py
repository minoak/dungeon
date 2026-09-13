# -*- coding: utf-8 -*-
"""D65 보스층·워프게이트·귀환 — 최심층 보스를 잡으면 봉인이 풀린 게이트로 마을에 돌아와 원정이 끝난다 — 61번째 게이트. LLM 0콜.
(2026-09-13 파트너 "5층에 보스몹을 두고 클리어 시 보스룸 뒤로 보물상자와 워프게이트를 설치해서 마을로 이동" → "보스를 잡고 워프게이트를 타고
 돌아가는 것까지 관찰을 해 보고 싶으니까 이렇게 구현하면 될 것 같네")
게이트:
  ① 배치: Dungeon(boss=True) → 출구 방에 보스(BOSS_KIND, boss=True, 도주 없음) 출구 곁 · 상자 곁 · sealed · level_snapshot.gate · monsters[].boss
  ② 기본 끔: Dungeon() / from_ascii 장면 — boss_on/boss/sealed 기본값, 보스 종 없음, 스냅샷에 gate 없음
  ③ 봉인: 관측 exit{name 워프게이트, gate, sealed} · 프롬프트 "워프게이트(exit) … 봉인돼 있다" · 모인 파티가 써도 result locked(안 떠남) · 직전 결과 문장
  ④ 처치 → 해제: 보스 처치 attack 결과 unsealed · sealed False · 관측 "열려 있다" · 처치 문장에 봉인 해제 · 게이트 사용 = ascend{to_depth 0, gate} · 봇 warp/went up
  ⑤ 러너(더미 두뇌, 보스 수치만 약하게 흉내): run_meta.boss · level.gate(sealed) → 처치(unsealed) → ascend(to_depth 0, gate) → 마을 level(depth 0, gate 없음) → end.outcome returned · 생존자 · events.log 귀환 줄
  ⑥ 배선(소스): 러너 스위치·론처 옵션·화면 체크박스·STREAM_FORMAT·HARNESS D65·클라이언트 타입·로그 줄·씬·옛 뷰어·보스 정의
(기존 verify 60종은 별도 실행.)
"""
import contextlib
import io
import json
import os
import tempfile

STATE = os.path.join(tempfile.mkdtemp(prefix="wl_boss_"), "state")
os.makedirs(STATE, exist_ok=True)
os.environ.update(DUNGEON_GM="0", DUNGEON_STEP_DELAY="0", DUNGEON_TURNS="220", DUNGEON_W="40", DUNGEON_H="16",
                  DUNGEON_DEPTHS="1", DUNGEON_SEED="7", DUNGEON_MONSTERS="0", DUNGEON_TRAPS="0", DUNGEON_LURKERS="0",
                  DUNGEON_BESTIARY_FILE="", DUNGEON_PARTY_FILE="/nonexistent", DUNGEON_STATE_DIR=STATE, DUNGEON_BOSS="1")
os.environ.pop("DUNGEON_TOWN", None)

import brains                                        # noqa: E402
import dungeon_gm as G                               # noqa: E402
from dungeon_gm import Dungeon                       # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


class C:
    failed = 0


def check(name, cond):
    print(("  OK   " if cond else " FAIL  ") + name)
    if not cond:
        C.failed += 1


def src(path):
    with open(os.path.join(HERE, path), encoding="utf-8") as f:
        return f.read()


def make(boss=True):
    d = Dungeon(seed=7, depth=1, w=40, h=16, n_monsters=0, n_traps=0, n_lurkers=0, events=True, boss=boss)
    bots = []
    for c in "12":
        bots.append(G.spawn(d, c, bots, sheet=G.HEROES.get(c) or G.HEROES['1']))
    return d, bots


def gather(d, bots, avoid=()):
    """파티를 게이트 곁(체비셰프 1)으로 옮긴다 — 모임 규칙을 만족시켜 게이트 판정만 잰다."""
    ex, ey = d.exit
    cells = [(x, y) for y in range(d.h) for x in range(d.w) if d.grid[y][x] == G.FLOOR
             and max(abs(x - ex), abs(y - ey)) <= 1 and (x, y) != (ex, ey) and (x, y) not in avoid]
    cells.sort(key=lambda c: abs(c[0] - ex) + abs(c[1] - ey))   # 직교 인접 먼저 — interact 는 맨해튼 1 안에서만 닿는다
    for b, c in zip(bots, cells):
        b["x"], b["y"] = c


print("── ① 배치")
d, bots = make(True)
boss = d.boss
ex, ey = d.exit
snap = d.level_snapshot()
chests = [f for f in d.features.values() if f.type == "chest"]
check("① 보스 = BOSS_KIND(고블린 대장) · boss 표식 · 출구 방 · 출구 곁(체비셰프 1) · 도주 없음",
      boss is not None and boss.kind == G.BOSS_KIND == "고블린 대장" and boss.boss is True and d.boss_on and d.sealed
      and d._room_id_at(boss.x, boss.y) == d._room_id_at(ex, ey) and max(abs(boss.x - ex), abs(boss.y - ey)) == 1
      and boss.flee_frac is None and boss in d.monsters)
check("① 보물상자가 게이트 곁(출구 방)에 하나 더", any(d._room_id_at(f.x, f.y) == d._room_id_at(ex, ey)
                                                and max(abs(f.x - ex), abs(f.y - ey)) <= 2 for f in chests))
check("① level_snapshot.gate{sealed, boss} · monsters[].boss", snap.get("gate") == {"sealed": True, "boss": boss.id}
      and any(m.get("boss") is True and m["kind"] == G.BOSS_KIND for m in snap["monsters"]))
check("① 정의: entities/monster/goblin_chief.json — 수치 18/4/3/13 · 심층 즉시 해금",
      (boss.hp, boss.atk, boss.dmg, boss.ac) == (18, 4, 3, 13) and (G.ENT.lore().get("monster:고블린 대장") or {}).get("unlock", {}).get("count") == 1)

print("── ② 기본 끔")
d0, _ = make(False)
da, _st = Dungeon.from_ascii(["############", "#12.......>#", "############"], seed=7)
check("② Dungeon() 기본: boss_on False · 보스 없음 · sealed False · 스냅샷에 gate 없음",
      d0.boss_on is False and d0.boss is None and d0.sealed is False and "gate" not in d0.level_snapshot()
      and not any(m.kind == G.BOSS_KIND for m in d0.monsters))
check("② from_ascii 장면도 명시 초기화(스위치 함정 없음)", da.boss_on is False and da.boss is None and da.sealed is False)

print("── ③ 봉인")
gather(d, bots, avoid=((boss.x, boss.y),))
o = d.view(bots[0], bots)
ex_obs = o["sights"]["exit"]
names = {b["char"]: b.get("name") or b["job"] for b in bots}
wire = brains._wire(o, names, compose=False)
check("③ 관측 exit: name 워프게이트 · gate · sealed", ex_obs and ex_obs.get("name") == "워프게이트" and ex_obs.get("gate") is True and ex_obs.get("sealed") is True)
check("③ 프롬프트: '워프게이트(exit)' + '봉인돼 있다'", "워프게이트(exit)" in wire and "봉인돼 있다" in wire and "계단(exit)" not in wire)
r = d.act(bots[0], {"type": "interact", "target": "exit"}, bots)
check("③ 모인 파티가 써도 locked — 아무도 안 떠난다", r.get("result") == "locked" and r.get("what") == "워프게이트"
      and not any(b.get("won") for b in bots) and d.sealed)
bots[0]["last"] = dict(r)
check("③ 직전 결과 문장(사실만) · 꼬리표 '봉인'", "봉인돼 있어 열리지 않았다" in brains._last_prose(bots[0]["last"], names)
      and any(k == "blocked" and lab == "봉인" for k, lab, _ in G.event_tags(dict(r, char="1"))))

print("── ④ 처치 → 해제 → 귀환")
b1 = bots[0]
boss.hp = 1                                            # 판정은 그대로(주사위) — 한 번만 맞으면 죽는 몸
adj = [(x, y) for y in range(d.h) for x in range(d.w) if d.grid[y][x] == G.FLOOR and abs(x - boss.x) + abs(y - boss.y) == 1
       and (x, y) != d.exit and all((x, y) != (bb["x"], bb["y"]) for bb in bots)]
b1["x"], b1["y"] = adj[0]
d.view(b1, bots)
res = None
for _ in range(40):
    res = d.act(b1, {"type": "attack", "target": "m%d" % boss.id}, bots)
    if res.get("killed"):
        break
check("④ 보스 처치 결과 unsealed · sealed False · 보스 죽음", res and res.get("killed") and res.get("unsealed") is True and d.sealed is False and not boss.alive)
check("④ 처치 문장에 봉인 해제", "봉인이 풀렸다" in brains._last_prose(dict(res), names))
gather(d, bots)
o2 = d.view(bots[0], bots)
wire2 = brains._wire(o2, names, compose=False)
check("④ 관측·프롬프트: sealed False · '열려 있다(마을로 통한다)'", o2["sights"]["exit"].get("sealed") is False and "열려 있다(마을로 통한다)" in wire2)
r2 = d.act(bots[0], {"type": "interact", "target": "exit"}, bots)
check("④ 게이트 사용 = ascend{to_depth 0, gate} · 전원 won/went up/warp", r2.get("result") == "ascend" and r2.get("to_depth") == 0 and r2.get("gate") is True
      and sorted(r2.get("party") or []) == ["1", "2"] and all(b.get("won") and b.get("went") == "up" and b.get("warp") for b in bots))
bots[0]["last"] = dict(r2)
check("④ 직전 결과 문장 — 워프게이트로 마을 귀환 · 꼬리표 '워프게이트로 마을로'", "워프게이트를 지나 마을로 돌아갔다" in brains._last_prose(bots[0]["last"], names)
      and any(k == "ascend" and "워프게이트" in det for k, _, det in G.event_tags(dict(r2, char="1"))))

print("── ⑤ 러너(더미 두뇌·약한 보스 흉내)")
orig_stats = G.ENT.monster_stats


def weak(kind):                                        # 보스 수치만 1/0/0/5 — 더미 두뇌가 처치까지 갈 수 있게(판정·배선은 그대로)
    s = dict(orig_stats(kind))
    if kind == G.BOSS_KIND:
        s.update(hp=1, atk=0, dmg=0, ac=5)
    return s


G.ENT.monster_stats = weak
import show_runner                                     # noqa: E402  (env 는 위에서 — 보스 켬·마을 없음·1층=최심층)
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    try:
        show_runner.main()
    except SystemExit:
        pass
G.ENT.monster_stats = orig_stats
with open(os.path.join(STATE, "stream.jsonl"), encoding="utf-8") as f:
    rows = [json.loads(ln) for ln in f if ln.strip()]
meta, end = rows[0], rows[-1]
levels = [r for r in rows if r.get("kind") == "level"]
ticks = [r for r in rows if r.get("kind") == "tick"]
kills = [(r["turn"], e) for r in ticks for e in (r.get("events") or []) if e.get("type") == "attack" and e.get("unsealed")]
asc = [r for r in rows if r.get("kind") == "ascend"]
gates = [(r["turn"], e) for r in ticks for e in (r.get("events") or []) if e.get("type") == "interact" and e.get("result") == "ascend"]
check("⑤ run_meta.boss · 1층 level.gate(sealed) · 처치(unsealed) 사건", meta.get("boss") is True and levels and levels[0].get("gate") == {"sealed": True, "boss": 0} and len(kills) == 1)
check("⑤ ascend{to_depth 0, gate} · 게이트 사용 사건(gate) · 마을 level(depth 0, gate 없음)",
      len(asc) == 1 and asc[0].get("to_depth") == 0 and asc[0].get("gate") is True and gates and gates[0][1].get("gate") is True
      and len(levels) == 2 and levels[1].get("depth") == 0 and "gate" not in levels[1])
check("⑤ end.outcome returned · 생존자 2 · 순서(처치 < 게이트)", end.get("kind") == "end" and end.get("outcome") == "returned"
      and sorted(end.get("survivors") or []) == ["1", "2"] and not end.get("fallen") and kills[0][0] < gates[0][0] == asc[0]["turn"])
with open(os.path.join(STATE, "events.log"), encoding="utf-8") as f:
    log = f.read()
check("⑤ events.log — 귀환 줄·종료 줄", "봉인 풀린 워프게이트로 마을 귀환" in log and "워프게이트로 마을 귀환!! (원정 완료)" in log)

print("── ⑥ 배선(소스)")
check("⑥ 러너 스위치·전이·종료", all(s_ in src("show_runner.py") for s_ in ("DUNGEON_BOSS", "boss=BOSS_ON and nd >= DEPTHS", 'outcome = "returned"', "elif nd == 0:")))
check("⑥ 론처 옵션·화면 체크박스", 'env["DUNGEON_BOSS"]' in src("launcher.py") and 'id="boss" checked' in src(os.path.join("launcher", "index.html"))
      and "boss: $('boss').checked" in src(os.path.join("launcher", "index.html")))
check("⑥ 문서: STREAM_FORMAT(boss·gate·returned) · HARNESS D65", all(s_ in src("STREAM_FORMAT.md") for s_ in ("| `boss` |", "| `gate` |", "`returned`"))
      and "D65" in src(os.path.join("design", "HARNESS_DESIGN.md")))
check("⑥ 클라이언트: 타입·로그 줄·씬·몬스터 키 · 옛 뷰어 · 보스 정의",
      "boss?: boolean" in src(os.path.join("game", "src", "stream", "types.ts")) and "gate?:" in src(os.path.join("game", "src", "stream", "types.ts"))
      and "'locked'" in src(os.path.join("game", "src", "text", "evline.ts")) and "unsealed" in src(os.path.join("game", "src", "text", "evline.ts"))
      and "exitObj" in src(os.path.join("game", "src", "scene", "DungeonScene.ts")) and "'고블린 대장'" in src(os.path.join("game", "src", "assets", "world.ts"))
      and "'locked'" in src(os.path.join("viewer", "index.html")) and os.path.exists(os.path.join(HERE, "entities", "monster", "goblin_chief.json")))

print("── ⑦ 프리셋(D67): 보스방 앞에서 시작")
front = d.boss_front()
ex7, ey7 = d.exit
room7 = d.rooms[d._room_id_at(ex7, ey7)]
check("⑦ boss_front = 보스룸 밖 바닥 칸이고 방 테두리 관통 칸에 인접(체비셰프 1)", front is not None and d.grid[front[1]][front[0]] == G.FLOOR and not room7.contains(*front)
      and any(d.grid[y][x] in (G.FLOOR, G.DOOR) and not room7.contains(x, y) and (room7.x - 1 <= x <= room7.x + room7.w) and (room7.y - 1 <= y <= room7.y + room7.h)
              for x in range(front[0] - 1, front[0] + 2) for y in range(front[1] - 1, front[1] + 2) if (x, y) != tuple(front)))
STATE7 = os.path.join(tempfile.mkdtemp(prefix="wl_boss7_"), "state")
os.makedirs(STATE7, exist_ok=True)
import importlib, subprocess, sys
env7 = dict(os.environ, DUNGEON_STATE_DIR=STATE7, DUNGEON_START="boss", DUNGEON_TOWN="1", DUNGEON_DEPTHS="2", DUNGEON_TURNS="3",
            DUNGEON_MONSTERS="1", DUNGEON_BOSS="0")          # 마을 켬·보스 끔을 줘도 프리셋이 덮는다
rc = subprocess.run([sys.executable, os.path.join(HERE, "show_runner.py")], env=env7, capture_output=True, text=True, timeout=300).returncode
with open(os.path.join(STATE7, "stream.jsonl"), encoding="utf-8") as f:
    rows7 = [json.loads(ln) for ln in f if ln.strip()]
meta7 = rows7[0]
lv7 = next(r for r in rows7 if r.get("kind") == "level")
def front_from_level(lv):                              # boss_front 와 같은 규칙을 스냅샷(grid·rooms·exit)에서 — 러너 생성 인자에 무관
    grid = lv["grid"]; w, h = lv["w"], lv["h"]
    ex_, ey_ = lv["exit"]
    rm = next(r for r in lv["rooms"] if r["x"] <= ex_ < r["x"] + r["w"] and r["y"] <= ey_ < r["y"] + r["h"])
    inside = lambda x, y: rm["x"] <= x < rm["x"] + rm["w"] and rm["y"] <= y < rm["y"] + rm["h"]
    cands = []
    for y in range(rm["y"] - 1, rm["y"] + rm["h"] + 1):
        for x in range(rm["x"] - 1, rm["x"] + rm["w"] + 1):
            if inside(x, y) or not (0 <= x < w and 0 <= y < h) or grid[y][x] not in (G.FLOOR, G.DOOR):
                continue
            dx = -1 if x < rm["x"] else (1 if x >= rm["x"] + rm["w"] else 0)
            dy = -1 if y < rm["y"] else (1 if y >= rm["y"] + rm["h"] else 0)
            ox, oy = x + dx, y + dy
            if 0 <= ox < w and 0 <= oy < h and grid[oy][ox] == G.FLOOR and not inside(ox, oy):
                cands.append((ox, oy))
    cands.sort(key=lambda c: (c[1], c[0]))
    return cands[0] if cands else None
fr7 = front_from_level(lv7)
check("⑦ 러너: run_meta.start=boss·town False·boss True · 첫 level.depth == depths(2)·gate", meta7.get("start") == "boss" and meta7.get("town") is False and meta7.get("boss") is True
      and lv7.get("depth") == 2 and lv7.get("gate", {}).get("sealed") is True)
check("⑦ 파티가 보스룸 앞 칸 곁(체비셰프 ≤2)에서 시작·보스룸 밖", fr7 is not None and all(max(abs(b["x"] - fr7[0]), abs(b["y"] - fr7[1])) <= 2 for b in lv7["party"])
      and not any(any(rm["type"] == "exit" and rm["x"] <= b["x"] < rm["x"] + rm["w"] and rm["y"] <= b["y"] < rm["y"] + rm["h"] for rm in lv7["rooms"]) for b in lv7["party"]))
check("⑦ 러너 정상 종료(rc 0)", rc == 0)

print("ALL PASS" if C.failed == 0 else "FAIL %d" % C.failed)

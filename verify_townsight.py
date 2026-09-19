# -*- coding: utf-8 -*-
"""D86 마을의 시야 = 지금 선 구역 · 이동은 거기에 맞게 — 73번째 게이트. LLM 0콜.
(2026-09-19 파트너 "지금은 시야를 전부 열어 주고 이동을 무제한 핑을 찍을수 있게 했는데 … 시야는 구역내에서는 전부 열리게 하고 … 이동 핑은
 제한을 둬보자" → "구역 내에서는 시야를 전부 주고 이동도 거기에 맞게 하자")
던전과 같은 문법을 마을에: 구역 = 방. 보이는 것은 지금 선 구역(건물·NPC·사람 전부) · 핑은 보이는 것 + 아는 장소(건물·입구는 고향이라 원래 안다 —
사람은 가 봐야 보인다: 지역 → 인물) · 걷다가 새 구역에 들어서면 멈춰 다시 본다. 러너 스위치 DUNGEON_TOWN_SIGHT=zone(기본 all = 옛 판 그대로).
게이트:
  ① 기본은 옛 그대로: 마을 전체가 보인다 · 관측에 town_sight 없음 · 새 구역에 들어서도 안 멈춘다
  ② 시야 = 지금 선 구역 ∪ 곁 한 칸: 다른 구역의 건물·NPC·입구는 sights 에 없다 · 같은 구역의 것은 전부 있다 · 구역마다 다르다
  ③ 아는 장소: 건물과 던전 입구는 장부에 미리(가 본 적 없어도 known.statics 에 구역·방위·거리) · NPC 는 없다 · 그 id 로 goto 가 된다
  ④ 새 구역에 들어서면 멈춘다(zone_enter — 작정·경로를 비우고 직전 결과에 구역 이름) · 같은 구역 안의 걸음은 안 멈춘다 ·
     자동 접근(멀리서 use)으로 걷던 걸음도 같은 규칙 · 멈춘 자리에서 새 구역의 사람·NPC 가 보인다
  ⑤ 던전 층은 그대로(스위치를 켜도 시야 엔진 무변화)
  ⑥ 프롬프트 문장: 마을 줄 · 기억 절 머리 · 직전 결과 · 옛 문장은 끈 판에만
  ⑦ 러너: run_meta.town_sight · 풀런(각본)에서 zone_enter 사건 · 끈 판엔 없음 · 지문은 켠 판에만
  ⑧ 배선(론처·문서)
(기존 verify 72종은 별도 실행.)
"""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = tempfile.mkdtemp(prefix="wl_townsight_")
STATE = os.path.join(ROOT, "state")
os.makedirs(STATE, exist_ok=True)
BASE_ENV = dict(DUNGEON_GM="0", DUNGEON_STEP_DELAY="0", DUNGEON_TURNS="120", DUNGEON_W="40", DUNGEON_H="16",
                DUNGEON_DEPTHS="2", DUNGEON_SEED="7", DUNGEON_MONSTERS="0", DUNGEON_TRAPS="0", DUNGEON_LURKERS="0",
                DUNGEON_BESTIARY_FILE="", DUNGEON_PARTY_FILE=os.path.join(HERE, "party.json"), DUNGEON_STATE_DIR=STATE,
                DUNGEON_TOWN="1", DUNGEON_BRAIN_BACKEND="dummy", DUNGEON_BOSS="0", DUNGEON_RUNS_DIR=os.path.join(ROOT, "runs"),
                DUNGEON_ACTION_MODE="compose", DUNGEON_TOWN_SIGHT="zone")
os.environ.update(BASE_ENV)
for k in ("DUNGEON_QUESTS", "DUNGEON_TOWN_APART", "DUNGEON_NPC_BRAIN", "DUNGEON_SOLO", "DUNGEON_START", "DUNGEON_MENU", "DUNGEON_RESUME",
          "DUNGEON_PARTYFORM", "DUNGEON_STRANGERS"):
    os.environ.pop(k, None)

import brains                                        # noqa: E402
brains._call_claude = lambda prompt, model="haiku": ""
import dungeon_gm as G                               # noqa: E402
import show_runner                                   # noqa: E402
import time as _time                                 # noqa: E402
_time.sleep = lambda s: None
show_runner.STEP_DELAY = 0


class C:
    failed = 0


def check(name, ok, detail=""):
    print("  %s %s%s" % ("OK  " if ok else "FAIL", name, (" — " + str(detail)) if (detail and not ok) else ""))
    if not ok:
        C.failed += 1


SHEETS = show_runner.load_party(os.path.join(HERE, "party.json"))
NAMES = {c: SHEETS[c]["name"] for c in SHEETS}


def town(sight="zone"):
    old = show_runner.TOWN_SIGHT
    show_runner.TOWN_SIGHT = sight
    try:
        d, _ = show_runner.build_town(apart=True, walkers=True)
    finally:
        show_runner.TOWN_SIGHT = old
    d.composed_actions = d.auto_approach = True
    bs = []
    for c in sorted(SHEETS):
        b = G.spawn(d, c, bs, sheet=dict(SHEETS[c]))
        b["ledger"] = G.new_ledger()
        bs.append(b)
    d.turn = 1
    return d, bs


def cells(d, zid):
    return [(x, y) for y in range(d.h) for x in range(d.w)
            if d._zone_id(x, y) == zid and d.grid[y][x] == G.FLOOR and not d.feature_at(x, y)]


def put(b, xy):
    b["x"], b["y"] = xy


def walk(d, bots, b, action, limit=90):
    """핑 하나를 끝까지 — 멈출 때마다 같은 핑을 다시 찍는다. 반환 [(틱, 구역, 멈춘 사유)]."""
    stops = []
    dec, err = G.CA.parse(action, d.view(b, bots))
    assert not err, err
    d.act(b, dec, bots)
    for t in range(2, limit):
        d.turn = t
        if b.get("order"):
            d.step_order(b, bots)
            continue
        stops.append((t, d._town_zone(b["x"], b["y"]), (b.get("last") or {}).get("result")))
        o = d.view(b, bots)
        if (b.get("last") or {}).get("result") in ("at_exit", "arrived", "need_party", "wait_allies", "exit"):
            break
        dec, err = G.CA.parse(action, o)
        if err:
            stops.append((t, "parse", err))
            break
        d.act(b, dec, bots)
    return stops


print("── ① 기본은 옛 그대로")
d0, bots0 = town("all")
g0 = cells(d0, "guild_district")
put(bots0[0], g0[len(g0) // 2]); put(bots0[1], cells(d0, "temple_district")[0]); put(bots0[2], cells(d0, "main_street")[0])
o0 = d0.view(bots0[0], bots0)
check("① 마을 전체가 보인다(칸 = w×h) · 다른 구역의 NPC·입구도 sights 에 · 관측에 town_sight 없음",
      d0.town_sight is None and len(d0.visible_cells(bots0[0]["x"], bots0[0]["y"])) == d0.w * d0.h
      and {"성직자", "주점 주인"} <= {f["name"] for f in o0["sights"]["features"]} and o0["sights"].get("exit") and "town_sight" not in o0)
st0 = walk(d0, bots0, bots0[0], {"type": "goto", "target": "exit"})
check("① 입구로 핑 한 번 — 구역을 넘어도 안 멈춘다(zone_enter 없음)", not any(r == "zone_enter" for _, _, r in st0) and len(st0) <= 2, st0)

print("── ② 시야 = 지금 선 구역")
d, bots = town()
b1, b2, b3 = bots
g, ms, tv, tp = cells(d, "guild_district"), cells(d, "main_street"), cells(d, "main_street"), cells(d, "temple_district")
put(b1, g[len(g) // 2]); put(b2, ms[len(ms) // 2]); put(b3, tv[len(tv) // 2])
vis = d.visible_cells(b1["x"], b1["y"])
zone_all = {(x, y) for y in range(d.h) for x in range(d.w) if d._zone_id(x, y) == "guild_district"}
check("② 보이는 칸 = 길드 구역 전부 ∪ 곁 한 칸(마을 전체가 아니다)", d.town_sight == "zone" and zone_all <= vis and len(vis) < d.w * d.h // 2
      and all(d._zone_id(x, y) == "guild_district" or max(abs(x - b1["x"]), abs(y - b1["y"])) <= 1 for x, y in vis))
o = d.view(b1, bots)
fn = {f["name"] for f in o["sights"]["features"]}
check("② 같은 구역의 건물·NPC 는 전부 · 다른 구역의 NPC·건물·입구·사람은 sights 에 없다",
      {"모험가 길드", "길드 접수원"} <= fn and not ({"성직자", "주점 주인", "신전", "주점"} & fn) and not o["sights"].get("exit")
      and o["sights"]["bots"] == [] and o.get("town_sight") == "zone", sorted(fn))
o3 = d.view(b3, bots)
check("② 구역마다 다르다 — 주점 구역에서는 주점 주인이 보이고 접수원은 안 보인다",
      "주점 주인" in {f["name"] for f in o3["sights"]["features"]} and "길드 접수원" not in {f["name"] for f in o3["sights"]["features"]})

print("── ③ 아는 장소")
ks = {e["name"]: e for e in (o.get("known") or {}).get("statics", [])}
check("③ 가 본 적 없어도 건물과 던전 입구를 안다(구역·방위·거리) · NPC 는 아는 곳에 없다",
      {"던전 입구", "신전", "주점"} <= set(ks) and ks["던전 입구"]["zone"] == "던전 입구 지구" and ks["던전 입구"].get("id") == "exit"
      and ks["신전"].get("dist") and not ({"성직자", "주점 주인", "길드 접수원"} & set(ks)), sorted(ks))
check("③ 그 id 로 goto 가 된다(입구·건물) · 안 보이는 NPC 는 대상이 아니다",
      G.CA.parse({"type": "goto", "target": "exit"}, o)[1] is None and G.CA.parse({"type": "goto", "target": ks["주점"]["id"]}, o)[1] is None
      and G.CA.parse({"type": "use", "target": "f%d" % next(f.id for f in d.features.values() if f.name == "주점 주인")}, o)[1] == "invalid_target")

print("── ④ 새 구역에 들어서면 멈춘다")
st = walk(d, bots, b1, {"type": "goto", "target": "exit"})
zs = [z for _, z, r in st if r == "zone_enter"]
check("④ 길드 → 던전 입구: 새 구역에 들어설 때마다 멈춘다(상점가 → 던전 입구 지구) · 끝은 입구 도착",
      zs == ["상점가", "던전 입구 지구"] and st[-1][2] in ("at_exit", "arrived"), st)
d4, bots4 = town()
c1, c2, c3 = bots4
shop = cells(d4, "shop_district")
put(c1, g[len(g) // 2]); put(c2, shop[len(shop) // 2]); put(c3, tp[0])
dec4, _ = G.CA.parse({"type": "goto", "target": "exit"}, d4.view(c1, bots4))
d4.act(c1, dec4, bots4)
res4 = None
for t in range(2, 40):
    d4.turn = t
    res4 = d4.step_order(c1, bots4)
    if res4.get("result") == "zone_enter":
        break
o4 = d4.view(c1, bots4)
check("④ 멈춘 순간: 결과에 구역 이름 · 작정·경로가 비었다 · 직전 결과(obs.last)에 실린다 · 새 구역의 사람(2)과 대장간이 이제 보인다",
      res4 and res4.get("zone") == "상점가" and not c1.get("order") and c1.get("path") == [] and o4["last"]["result"] == "zone_enter"
      and [x["char"] for x in o4["sights"]["bots"]] == ["2"] and "대장간" in {f["name"] for f in o4["sights"]["features"]},
      (res4, [x["char"] for x in o4["sights"]["bots"]]))
d5, bots5 = town()
e1 = bots5[0]
put(e1, g[0]); put(bots5[1], tp[0]); put(bots5[2], tp[1])
far = max(g, key=lambda c: abs(c[0] - g[0][0]) + abs(c[1] - g[0][1]))
e1["order"], e1["path"] = "@%d,%d" % far, d5.path_to(g[0][0], g[0][1], far[0], far[1], bots5)
inside = [d5.step_order(e1, bots5).get("result") for _ in range(len(e1["path"]))]
check("④ 같은 구역 안의 걸음은 안 멈춘다", "zone_enter" not in inside and len(inside) >= 5, inside[:6])
d6, bots6 = town()
f1 = bots6[0]
put(f1, g[len(g) // 2]); put(bots6[1], tp[0]); put(bots6[2], tp[1])
tav_id = next(e["id"] for e in d6.view(f1, bots6)["known"]["statics"] if e["name"] == "주점")
st6 = walk(d6, bots6, f1, {"type": "goto", "target": tav_id})
check("④ 아는 건물(주점)로 가는 길도 같은 규칙 — 구역마다 멈추고 끝내 닿는다", any(r == "zone_enter" for _, _, r in st6) and st6[-1][1] == "번화가", st6)

print("── ⑤ 던전 층은 그대로")
fl = G.Dungeon(seed=7, w=40, h=16)
fl.town_sight = "zone"
fb = G.spawn(fl, "1", [])
fl0 = G.Dungeon(seed=7, w=40, h=16)
fb0 = G.spawn(fl0, "1", [])
check("⑤ 마을이 아니면 스위치가 있어도 시야 엔진 그대로(같은 칸)", fl.visible_cells(fb["x"], fb["y"]) == fl0.visible_cells(fb0["x"], fb0["y"]))

print("── ⑥ 프롬프트 문장")
w = brains._wire(o, NAMES, compose=True)
w0 = brains._wire(o0, NAMES, compose=True)
check("⑥ 켠 판: '보이고 들리는 것은 지금 서 있는 구역 안뿐이다' · '## 네가 아는 곳과 기억하는 것' · 아는 곳 줄에 던전 입구",
      "보이고 들리는 것은 지금 서 있는 구역 안뿐이다" in w and "## 네가 아는 곳과 기억하는 것" in w and "던전 입구" in w.split("## 네가 아는 곳과 기억하는 것")[1])
check("⑥ 끈 판: 옛 문장 그대로('길과 건물이 어디 있는지는 다 안다. 사람과 목소리는 같은 구역 안에서만') · 새 문장 없음",
      "길과 건물이 어디 있는지는 다 안다. 사람과 목소리는 같은 구역 안에서만 보이고 들린다" in w0 and "지금 서 있는 구역 안뿐" not in w0)
check("⑥ 직전 결과 문장", "걷다가 번화가에 들어섰다 — 이 구역이 이제 보인다" in brains._last_prose({"type": "walk", "result": "zone_enter", "zone": "번화가"}, NAMES))

print("── ⑦ 러너")
def probe(env):
    e = {k: v for k, v in os.environ.items() if not k.startswith("DUNGEON_")}
    e.update(PYTHONUTF8="1", **env)
    p = subprocess.run([sys.executable, "-c", "import json, show_runner as s; print(json.dumps({'sight': s.TOWN_SIGHT, 'fp': s._world_fingerprint().get('town_sight')}))"],
                       cwd=HERE, env=e, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return json.loads(p.stdout.splitlines()[0]) if p.returncode == 0 and p.stdout.strip() else {"err": p.stderr[-300:]}
check("⑦ 스위치: 기본 all(지문 열쇠 없음) · zone 이면 지문에 · 마을 판이 아니면 지문에 없다",
      probe({k: v for k, v in BASE_ENV.items() if k != "DUNGEON_TOWN_SIGHT"}) == {"sight": "all", "fp": None}
      and probe(BASE_ENV) == {"sight": "zone", "fp": "zone"} and probe({**BASE_ENV, "DUNGEON_TOWN": "0"}) == {"sight": "zone", "fp": None})
_dummy = G.dummy_brain
def scripted(obs, char="?"):                           # 입구가 보이거나 아는 곳이면 그리로(더미는 안 보이는 입구를 모른다)
    if obs.get("town"):
        ex = obs["sights"].get("exit")
        if ex and ex.get("adj"):
            return {"type": "interact", "target": "exit"}
        return {"type": "goto", "target": "exit"}
    return _dummy(obs, char)
G.dummy_brain = scripted
try:
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            show_runner.main()
        except SystemExit:
            pass
finally:
    G.dummy_brain = _dummy
with open(os.path.join(STATE, "stream.jsonl"), encoding="utf-8") as f:
    rows = [json.loads(ln) for ln in f if ln.strip()]
ze = [(r["turn"], e.get("char"), e.get("zone")) for r in rows if r["kind"] == "tick" for e in (r.get("events") or []) if e.get("result") == "zone_enter"]
check("⑦ 풀런: run_meta.town_sight 'zone' · zone_enter 사건이 캐릭터마다 · 셋이 입구에 모여 하강한다(옛 모임 규칙 그대로)",
      rows[0].get("town_sight") == "zone" and {c for _, c, _ in ze} == {"1", "2", "3"} and any(r["kind"] == "descend" for r in rows), ze[:4])

print("── ⑧ 배선(론처·문서)")
def text(*p):
    with open(os.path.join(HERE, *p), encoding="utf-8") as f:
        return f.read()
lp, lh, hd, fmt = text("launcher.py"), text("launcher", "index.html"), text("design", "HARNESS_DESIGN.md"), text("STREAM_FORMAT.md")
check("⑧ 론처: 체크박스(기본 끔)·옵션·환경변수", 'id="townSight">' in lh and 'id="townSight" checked' not in lh and "town_sight: $('townSight').checked ? 'zone' : 'all'" in lh
      and 'env["DUNGEON_TOWN_SIGHT"] = "zone" if opts.get("town_sight") == "zone" else "all"' in lp)
check("⑧ 문서: HARNESS D86 · STREAM_FORMAT(town_sight·zone_enter)", "## [결정] D86." in hd and "DUNGEON_TOWN_SIGHT" in hd and "town_sight" in fmt and "zone_enter" in fmt)

print("=" * 44)
print("ALL PASS — verify_townsight (D86 마을의 시야 = 지금 선 구역: 구역 시야 · 아는 장소 · 새 구역에 들어서면 멈춘다 · 던전 무변화)"
      if not C.failed else "FAILED %d" % C.failed)
sys.exit(1 if C.failed else 0)

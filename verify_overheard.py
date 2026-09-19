# -*- coding: utf-8 -*-
"""D90 마을 생활 — 구역의 '들린 말'. LLM 0콜.
(2026-09-20 — 파트너 메모 WONDERLAND_CHANGES_2026-09-11.md §4-4 "거리 분위기 '들린 말' 한 줄 고정 풀(0콜)" ·
 완성 기준 "실제로 이 마을에서 캐릭터가 살아간다는 걸 보여 주고")
마을의 한 구역에 들어선 **첫 관측**에 그 구역 사람들끼리 나누던 말 한 줄이 실린다(notices kind 'overheard'). 풀 = 구역 정의
(entities/map/<구역>.json)의 overheard 부품. 러너 스위치 DUNGEON_TOWN_LIFE=1(러너 기본 0 — 론처가 켠다 · 이 스위치 뒤에 마을의 다른 생활 부품도 선다).
게이트:
  ① 정의: v4 마을의 여섯 구역 전부에 8~12 문장 · 빈 문장·중복 없음 · 검증기(문장 목록만) · 기능을 약속하거나 어디로 가라는 말이 없다(금칙어)
  ② 기본은 옛 그대로: 스위치 상수 0 · 마을에 풀이 안 걸린다 · 관측에 없다 · 봇에 장부가 안 생긴다
  ③ 구역에 들어선 첫 관측에 한 번: 같은 구역의 다음 관측엔 없다 · 다른 구역에 들어서면 그 구역의 말 · 돌아오면 다시 한 번(방문마다) ·
     한 관측 안에서 두 번 소비되지 않는다(메뉴의 의뢰 줄이 _notices 를 한 번 더 부른다)
  ④ 고르기 = (시드·구역·캐릭터) 해시 + 방문 횟수: 같은 조건은 같은 말(결정론) · 풀을 한 바퀴 돌기 전엔 같은 말을 다시 안 듣는다 ·
     판정 rng 무접촉(d.rng·walk_rng 상태 불변)
  ⑤ 프롬프트: 한 줄('…에 들어서며 들린 말' · 네게 한 말이 아니다) · 메뉴형·조합형 둘 다 · '그 밖의 정보' 누수 없음
  ⑥ 러너: 끈 판의 스트림엔 열쇠가 없다 · 켠 판은 run_meta.town_life · tick.overheard [{char,zone,text}] · events.log 한 줄 ·
     들린 말 풀만 건 판은 끈 판과 tick.overheard 말고는 (started 빼고) 같다(판정 무접촉의 실증 — 같은 스위치 뒤의 다른 생활 부품과는 떼어서 본다)
  ⑦ 배선: 러너 소스 · 세계 지문(서브프로세스 — 기본/켬/마을 아님) · 검증기 화이트리스트
(기존 게이트는 별도 실행.)
"""
import contextlib
import copy
import functools
import io
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = tempfile.mkdtemp(prefix="wl_overheard_")
STATE = os.path.join(ROOT, "state")
os.makedirs(STATE, exist_ok=True)
BASE_ENV = dict(DUNGEON_GM="0", DUNGEON_STEP_DELAY="0", DUNGEON_TURNS="60", DUNGEON_W="40", DUNGEON_H="16",
                DUNGEON_DEPTHS="2", DUNGEON_SEED="7", DUNGEON_MONSTERS="0", DUNGEON_TRAPS="0", DUNGEON_LURKERS="0",
                DUNGEON_BESTIARY_FILE="", DUNGEON_PARTY_FILE=os.path.join(HERE, "party.json"), DUNGEON_STATE_DIR=STATE,
                DUNGEON_TOWN="1", DUNGEON_BRAIN_BACKEND="dummy", DUNGEON_BOSS="0", DUNGEON_RUNS_DIR=os.path.join(ROOT, "runs"),
                DUNGEON_ACTION_MODE="compose")
os.environ.update(BASE_ENV)
for k in ("DUNGEON_QUESTS", "DUNGEON_TOWN_APART", "DUNGEON_NPC_BRAIN", "DUNGEON_SOLO", "DUNGEON_START", "DUNGEON_MENU", "DUNGEON_RESUME",
          "DUNGEON_PARTYFORM", "DUNGEON_STRANGERS", "DUNGEON_TOWN_SIGHT", "DUNGEON_NPC_REPLY", "DUNGEON_TOWN_LIFE"):
    os.environ.pop(k, None)

import brains                                        # noqa: E402
brains._call_claude = lambda prompt, model="haiku": ""
import dungeon_gm as G                               # noqa: E402
import entities as ENT                               # noqa: E402
import show_runner as R                              # noqa: E402
import time as _time                                 # noqa: E402
_time.sleep = lambda s: None
R.STEP_DELAY = 0


class C:
    failed = 0


def check(name, ok, detail=""):
    print("  %s %s%s" % ("OK  " if ok else "FAIL", name, (" — " + str(detail)) if (detail and not ok) else ""))
    if not ok:
        C.failed += 1


def src(*p):
    with open(os.path.join(HERE, *p), encoding="utf-8") as f:
        return f.read()


SHEETS = R.load_party(os.path.join(HERE, "party.json"))
NAMES = {c: SHEETS[c]["name"] for c in SHEETS}


def town(on=True, quests=False):
    old = R.TOWN_LIFE_ON
    R.TOWN_LIFE_ON = on
    try:
        d, _ = R.build_town(apart=True, walkers=True, quests=(G.new_quests() if quests else None))
    finally:
        R.TOWN_LIFE_ON = old
    bs = []
    for c in sorted(SHEETS):
        bs.append(G.spawn(d, c, bs, sheet=dict(SHEETS[c])))
    d.turn = 1
    return d, bs


def cell_in(d, zone, skip=0):
    """그 구역(이름)의 빈 바닥 칸 하나."""
    cs = [(x, y) for y in range(d.h) for x in range(d.w)
          if d.grid[y][x] == G.FLOOR and not d.feature_at(x, y) and d._town_zone(x, y) == zone]
    return cs[skip]


def heard(obs):
    return [n for n in (obs.get("notices") or []) if n.get("kind") == "overheard"]


print("── ① 정의")
with open(os.path.join(HERE, "town.json"), encoding="utf-8") as f:
    layout_path = os.path.join(HERE, json.load(f)["layout"])
with open(layout_path, encoding="utf-8") as f:
    regions = json.load(f)["regions"]
ents = sorted({r["entity"] for r in regions})
pools = {e: (ENT.get(e)["comps"].get("overheard") or []) for e in ents}
check("① v4 마을의 구역 여섯 전부에 풀이 있다 · 구역마다 8~12 문장", len(ents) == 6 and all(8 <= len(v) <= 12 for v in pools.values()),
      {e: len(v) for e, v in pools.items()})
flat = [s for v in pools.values() for s in v]
check("① 빈 문장·앞뒤 공백·중복 없음(구역을 넘어서도)", all(s and s == s.strip() for s in flat) and len(set(flat)) == len(flat))
BAN = ("살 수 있", "팔아", "묵으면", "가 보", "가봐", "가 봐", "내려가 봐", "내려가라", "들러", "찾아가", "하세요", "하시오", "해 보", "추천")
bad = [(w, s) for s in flat for w in BAN if w in s]
check("① 금칙어 없음 — 기능을 약속하거나(살 수 있다·묵으면) 어디로 가라고 권하는 말이 없다", not bad, bad[:3])
check("① 정의 note 에 임시 문장 표식", all("overheard" in (ENT.get(e).get("note") or "") for e in ents))


def problems(value):
    """구역 정의 하나에 overheard=value 를 넣었을 때 검증기가 내는 문제 줄들."""
    return ENT._problems([(os.path.join(ENT.ROOT, "map", "x.json"),
                           {"id": "x", "kind": "map", "name": "x", "comps": {"space": {"role": "district"}, "overheard": value}})], ENT.ROOT)


bad_shapes = [v for v in ([], ["", "말"], "문장 하나", [3]) if not any("overheard" in p for p in problems(v))]
check("① 검증기: overheard 는 비어 있지 않은 문장 목록만(빈 목록·빈 문장·문자열·숫자는 로드 단계에서 걸린다) · 바른 꼴은 통과 · map 화이트리스트",
      not bad_shapes and not problems(["지나가는 말"]) and "overheard" in ENT.COMPS["map"], bad_shapes)

print("── ② 기본은 옛 그대로")
d0, bots0 = town(on=False)
o0 = d0.view(bots0[0], bots0)
check("② 러너 스위치 기본 0 · 끈 마을엔 풀이 안 걸린다 · 관측에 없다 · 봇에 장부가 안 생긴다 · 엔진 기록도 없다",
      R.TOWN_LIFE_ON is False and not hasattr(d0, "zone_overheard") and not heard(o0)
      and "overheard" not in bots0[0] and not hasattr(d0, "overheard_log"))

print("── ③ 구역에 들어선 첫 관측에 한 번")
d, bots = town(quests=True)
a = bots[0]
zones = sorted(d.zone_overheard)
check("③ 켠 마을: 구역 이름 → 문장들(여섯 구역)", len(zones) == 6 and all(d.zone_overheard[z] == pools[e] for z in zones
                                                                for e in ents if ENT.get(e)["name"] == z), zones)
guild = next(z for z in zones if "길드" in z)
street = next(z for z in zones if z == "번화가")
a["x"], a["y"] = cell_in(d, guild)
o1 = d.view(a, bots)
h1 = heard(o1)
check("③ 첫 관측: 한 줄 {kind, zone, text} — 그 구역의 풀에서", len(h1) == 1 and h1[0]["zone"] == guild and h1[0]["text"] in d.zone_overheard[guild], h1)
check("③ 의뢰 장부가 걸린 판(메뉴가 _notices 를 한 번 더 부른다)에서도 관측에 실린다 — 한 관측 안에서 두 번 소비되지 않는다",
      len(h1) == 1 and a["overheard"]["n"] == {guild: 1})
check("③ 같은 구역의 다음 관측엔 없다(자리를 옮겨도)", not heard(d.view(a, bots))
      and (a.update(dict(zip(("x", "y"), cell_in(d, guild, 5)))) or not heard(d.view(a, bots))))
a["x"], a["y"] = cell_in(d, street)
h2 = heard(d.view(a, bots))
check("③ 다른 구역에 들어선 첫 관측 → 그 구역의 말", len(h2) == 1 and h2[0]["zone"] == street and h2[0]["text"] in d.zone_overheard[street], h2)
a["x"], a["y"] = cell_in(d, guild)
h3 = heard(d.view(a, bots))
check("③ 돌아오면 다시 한 번(방문마다) · 지난번과 다른 말 · 방문 횟수 장부", len(h3) == 1 and h3[0]["text"] != h1[0]["text"]
      and a["overheard"] == {"zone": guild, "n": {guild: 2, street: 1}}, (h3, a.get("overheard")))
log = list(d.overheard_log)
check("③ 엔진의 관전용 기록(러너가 틱마다 비운다): 실린 순서대로 {char, zone, text}",
      [(x["char"], x["zone"]) for x in log] == [("1", guild), ("1", street), ("1", guild)] and log[0]["text"] == h1[0]["text"], log)

print("── ④ 고르기 = 해시 + 방문 횟수")
dA, botsA = town()
dB, botsB = town()
for dd, bb in ((dA, botsA), (dB, botsB)):
    bb[0]["x"], bb[0]["y"] = cell_in(dd, guild)
check("④ 결정론: 같은 시드·구역·캐릭터·방문 횟수 → 같은 말", heard(dA.view(botsA[0], botsA)) == heard(dB.view(botsB[0], botsB)))
seq = []
dC, botsC = town()
c = botsC[0]
for i in range(len(dC.zone_overheard[guild])):
    c["x"], c["y"] = cell_in(dC, guild)
    seq.append(heard(dC.view(c, botsC))[0]["text"])
    c["x"], c["y"] = cell_in(dC, street)
    dC.view(c, botsC)
check("④ 풀을 한 바퀴 돌기 전엔 같은 말을 다시 안 듣는다(방문 %d번 = 풀 전부)" % len(seq), sorted(seq) == sorted(dC.zone_overheard[guild]))
firsts = set()
for seed in range(1, 9):
    dS, botsS = town()
    dS.master_seed = seed
    for b in botsS:
        b["x"], b["y"] = cell_in(dS, guild, int(b["char"]))
        firsts.add(heard(dS.view(b, botsS))[0]["text"])
check("④ 시드·캐릭터가 달라지면 첫 말도 달라진다(8시드 × 3인 — 네 가지 넘게)", len(firsts) >= 4, len(firsts))
dE, botsE = town()
e = botsE[0]
e["x"], e["y"] = cell_in(dE, guild)
st0 = (dE.rng.getstate(), getattr(dE, "walk_rng", dE.rng).getstate())
dE.view(e, botsE)
check("④ 판정 rng 무접촉: 들린 말이 실린 관측 앞뒤로 d.rng·walk_rng 상태가 같다",
      st0 == (dE.rng.getstate(), getattr(dE, "walk_rng", dE.rng).getstate()))

print("── ⑤ 프롬프트")
dF, botsF = town()
f = botsF[0]
f["x"], f["y"] = cell_in(dF, guild)
oF = dF.view(f, botsF)
snap = copy.deepcopy(oF)
wm, wc = brains._wire(oF, NAMES), None
dF2, botsF2 = town()
dF2.composed_actions = dF2.auto_approach = True
botsF2[0]["x"], botsF2[0]["y"] = cell_in(dF2, guild)
oC = dF2.view(botsF2[0], botsF2)
wc = brains._wire(oC, NAMES, compose=True)
line = "- %s에 들어서며 들린 말(마을 사람들끼리 나누는 말이다 — 네게 한 말이 아니다): 「%s」" % (guild, heard(oF)[0]["text"])
check("⑤ 한 줄 — 메뉴형·조합형 둘 다 · _wire 는 관측을 안 바꾼다", line in wm and line in wc and oF == snap, [ln for ln in wm.split("\n") if "들린 말" in ln])
check("⑤ '그 밖의 정보' 누수 없음(새 열쇠 없음 — notices 안에 실린다)", "## 그 밖의 정보" not in wm and "## 그 밖의 정보" not in wc)
check("⑤ 끈 판 프롬프트엔 없다", "들린 말" not in brains._wire(o0, NAMES))

print("── ⑥ 러너")


def run(life, only_pool=False):
    """러너 풀런(더미 두뇌) → (스트림 줄들, events.log). only_pool = 스위치는 끈 채 마을에 들린 말 풀만 건다 — 같은 스위치 뒤의 다른 생활 부품
    (마을 오브젝트·새 주민)과 떼어서, 들린 말 하나가 판정에 닿지 않는다는 것만 본다."""
    st = tempfile.mkdtemp(prefix="run_", dir=ROOT)
    old = (R.STATE, R.TOWN_LIFE_ON, R.build_town)
    R.STATE, R.TOWN_LIFE_ON = st, life
    if only_pool:
        @functools.wraps(old[2])                       # town_for_run 이 시그니처(apart·guide)를 본다
        def with_pool(*a_, **k_):
            dd, ss = old[2](*a_, **k_)
            dd.zone_overheard = {z_: list(v_) for z_, v_ in d.zone_overheard.items()}
            return dd, ss
        R.build_town = with_pool
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                R.main()
            except SystemExit:
                pass
    finally:
        R.STATE, R.TOWN_LIFE_ON, R.build_town = old
    with open(os.path.join(st, "stream.jsonl"), encoding="utf-8") as fh:
        rows = [json.loads(ln) for ln in fh if ln.strip()]
    with open(os.path.join(st, "events.log"), encoding="utf-8") as fh:
        return rows, fh.read()


rows_off, log_off = run(False)
rows_on, log_on = run(True)
rows_pool, _ = run(False, only_pool=True)
check("⑥ 끈 판: run_meta.town_life·tick.overheard 없음 · events.log 에 줄 없음",
      "town_life" not in rows_off[0] and not any("overheard" in r for r in rows_off) and "들린 말" not in log_off)
oh = [(r["turn"], x) for r in rows_on if r["kind"] == "tick" for x in (r.get("overheard") or [])]
check("⑥ 켠 판: run_meta.town_life · 첫 틱에 셋 다 제 구역의 말 · 그 뒤로도 구역을 옮길 때마다 · events.log 한 줄",
      rows_on[0].get("town_life") is True and {x["char"] for t, x in oh if t == 1} == {"1", "2", "3"} and len(oh) > 3
      and all(x["text"] in d.zone_overheard[x["zone"]] for _, x in oh) and "에 들어서며 들린 말: 「" in log_on, oh[:4])


def strip(rows):
    return [json.dumps({k_: v_ for k_, v_ in r.items() if k_ not in ("started", "overheard")}, ensure_ascii=False, sort_keys=True) for r in rows]


check("⑥ 들린 말 풀만 건 판은 끈 판과 tick.overheard 말고는 (started 빼고) 같다 — 판정·걸음·굴림 무접촉",
      any("overheard" in r for r in rows_pool) and strip(rows_pool) == strip(rows_off), (len(rows_pool), len(rows_off)))

print("── ⑦ 배선")
rs = src("show_runner.py")
check("⑦ 러너 소스: 스위치(기본 0)·build_town 이 풀을 건다·tick.overheard·run_meta·지문",
      'TOWN_LIFE_ON = os.environ.get("DUNGEON_TOWN_LIFE", "0") == "1"' in rs and "d.zone_overheard = oh_" in rs
      and '"overheard": overheard' in rs and rs.count('{"town_life": True} if (TOWN_LIFE_ON and TOWN_ON)') == 2)


def probe(env):
    e_ = {k_: v_ for k_, v_ in os.environ.items() if not k_.startswith("DUNGEON_")}
    e_.update(PYTHONUTF8="1", **env)
    p = subprocess.run([sys.executable, "-c", "import json, show_runner as s; print(json.dumps({'on': s.TOWN_LIFE_ON, 'fp': s._world_fingerprint().get('town_life')}))"],
                       cwd=HERE, env=e_, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return json.loads(p.stdout.splitlines()[0]) if p.returncode == 0 and p.stdout.strip() else {"err": p.stderr[-300:]}


check("⑦ 세계 지문: 기본은 열쇠 없음 · 켠 마을 판에만 · 마을 판이 아니면 없음",
      probe(BASE_ENV) == {"on": False, "fp": None} and probe({**BASE_ENV, "DUNGEON_TOWN_LIFE": "1"}) == {"on": True, "fp": True}
      and probe({**BASE_ENV, "DUNGEON_TOWN_LIFE": "1", "DUNGEON_TOWN": "0"}) == {"on": True, "fp": None})

print("=" * 44)
if C.failed:
    print("RESULT: %d FAIL" % C.failed)
    raise SystemExit(1)
print("ALL PASS — verify_overheard (D90 들린 말: 구역 여섯·첫 관측 한 번·방문마다·해시 고르기·rng 무접촉·끈 판 그대로)")

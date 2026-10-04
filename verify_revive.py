# -*- coding: utf-8 -*-
"""부활(D99, 2026-10-04) 헤들리스 검증 — 86번째 게이트. LLM 0콜(각본 더미 두뇌 · 상태 폴더는 tempfile).
파트너: "3층에서 죽음을 맞이하면 무덤이 죽은 자리에 생기고 캐릭터는 성당에서 다시 살아나 일단 아이템을 가지고 부활할수 있게
해주자 기억도 죽기 전까지 유지하는거고" · "어차피 이 게임은 에이전트 1인칭의 시점을 보는거였잖아 … 동료 캐릭터는 일단 마을에서
규칙엔진으로 돌아가게 하거나 대기 시키고 메인 플레이어가 죽으면 다시 돌아가게 하자" · "일단은 성당은 신전이 맞아".
스위치 DUNGEON_REVIVE(러너 기본 0 · 원정 고리 판에서만 · 파티 결성 판에서는 꺼짐) 뒤에서 —
쓰러진 몸은 대기 장부로 가고, 일행이 마을에 들어서는 순간 신전 문턱 곁에서 깨어난다. 메인(1번)이 던전에서 쓰러지면 그 틱에
살아 있던 동료도 함께 마을로 돌아온다. 마을에서 쓰러지면 그 틱에 깨어난다. 전멸은 없다.
죽음은 게이트 안에서만 일으킨다 — 몹 차례(monster_turn) 끝에 정해진 틱에 엔진의 공통 사망 처리(_on_down)로 쓰러뜨린다
(모든 사망 경로가 지나는 길 · 묘·목격·사인 기록이 실판과 같다).
게이트:
  ① 스위치 끔 = 옛 판 그대로: 미지정 판과 '0' 판의 스트림 바이트 동일 · run_meta·세계 지문에 revive 없음 · 쓰러진 동료는
     돌아오지 않는다(revive 줄 0 · 다음 원정의 지하 1층에 그 사람이 없다)
  ② 동료가 먼저 쓰러짐(켠 판): 첫 마을 귀환 전까지의 줄이 끈 판과 같다 · 워프로 돌아온 마을의 level 에 그 사람이 있다 —
     신전 문턱 곁(2칸 안) · HP 가득 · 지닌 것(장비·물약·축복·보물·능력치) 쓰러지기 전 그대로 · revive 줄(사인·층) ·
     그 사람의 첫 관측 = '신전 앞에서 다시 깨어났다' · 기억에 '네가 쓰러짐'(도감이 사인을 가린다) · 프롬프트 글에 둘 다 실린다 ·
     캠페인 기록(D78)이 판 끝의 그 사람을 쓰러진 채로 적지 않는다
  ③ 메인이 쓰러짐: 그 틱에 ascend(fell=1번 · gate 없음) → 마을 level → revive · 메인은 신전 곁, 동료는 던전 입구 곁 ·
     동료의 첫 관측 = '쓰러져 원정이 끝났다' · NPC 가 아는 사실이 '워프게이트로 귀환'이라 말하지 않는다 · 보고 → 결산(쓰러짐에 메인) ·
     판은 틱 상한까지 흐른다
  ④ 모두 쓰러짐: wiped 가 없다 · 셋 다 신전 곁에서 깨어나고 다음 원정이 이어진다
  ⑤ 두 번 쓰러지면 두 번 깨어난다: 원정마다 결산의 쓰러짐에 메인 · end 의 fallen 에 두 번
  ⑥ 마을에서 쓰러짐: 그 틱에 신전 곁에서 깨어난다(다음 틱 기록에 살아 있다)
  ⑦ 피클 이어가기(D79): 동료가 쓰러진 뒤 멈춘 스냅샷에 대기 장부가 얼어 있다 · 부활을 끈 러너는 그 스냅샷을 거절한다(지문 revive) ·
     이어간 판의 꼬리가 대조군과 같다
  ⑧ 배선: 론처 env 줄 · 화면 본문(원정 고리 칸 값) · 옵션 판 번호 3 · 러너 조건(고리 판만 · 파티 결성 판 끔) · 자기 등록(_run_gates.sh)
"""
import contextlib
import io
import shutil
import json
import os
import pickle
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="wl_revive_")
STATE = os.path.join(TMP, "state")
os.makedirs(STATE, exist_ok=True)
for _k in [k for k in os.environ if k.startswith("DUNGEON_")]:   # 게이트 환경(_run_gates.sh)의 값까지 걷고 이 게이트의 판을 명시한다
    os.environ.pop(_k)
RUN_ENV = dict(DUNGEON_BRAIN_BACKEND="dummy", DUNGEON_ACTION_MODE="menu", DUNGEON_SKILLS="0",
               DUNGEON_TRPG_COMBAT="0", DUNGEON_RANDOM_SKILL="0", DUNGEON_BESTIARY_FILE="",
               DUNGEON_GM="0", DUNGEON_STEP_DELAY="0", DUNGEON_PARTY_FILE=os.path.join(HERE, "party.json"),
               DUNGEON_STATE_DIR=STATE, DUNGEON_RUNS_DIR=os.path.join(TMP, "runs"),
               # 작은 판(verify_loop 와 같은 모양): 마을 → 보스 하나뿐인 지하 1층 → 워프 귀환 → 보고 → 다음 원정
               DUNGEON_SEED="7", DUNGEON_W="40", DUNGEON_H="16", DUNGEON_TOWN="1", DUNGEON_BOSS="1",
               DUNGEON_DEPTHS="1", DUNGEON_TURNS="340", DUNGEON_MONSTERS="0", DUNGEON_TRAPS="0",
               DUNGEON_LURKERS="0", DUNGEON_GEAR="0", DUNGEON_POTIONS="0", DUNGEON_LOOP="1")
os.environ.update(RUN_ENV)

import brains                                        # noqa: E402
brains._call_claude = lambda prompt, model="haiku": ""   # 안전핀(더미 백엔드라 닿지 않는다)
import dungeon_gm as G                               # noqa: E402
import snapshot                                      # noqa: E402
import show_runner                                   # noqa: E402
import time as _time                                 # noqa: E402
_time.sleep = lambda s: None
show_runner.STEP_DELAY = 0
TURNS = int(RUN_ENV["DUNGEON_TURNS"])


class C:
    failed = 0


def check(name, ok, detail=""):
    print("  %s %s%s" % ("OK  " if ok else "FAIL", name, (" — " + str(detail)) if (detail and not ok) else ""))
    if not ok:
        C.failed += 1


# ── 각본 두뇌(0콜, verify_loop 와 같은 길): 마을에선 던전 입구(돌아온 뒤면 접수원)로, 던전에선 보스를 치고 워프게이트로 ──
_stats = G.ENT.monster_stats
G.ENT.monster_stats = lambda kind: {**_stats(kind), "hp": 1, "atk": 0, "dmg": 0, "ac": 5}   # 게이트 전용: 보스도 한 대에, 몹은 아무도 못 다치게
OBS = []                                             # (char, turn, obs) — 깨어남·돌아옴의 첫 관측만 모은다


def scripted(obs, char="?"):
    lt = (obs.get("last") or {}).get("type")
    if lt in ("revived", "recalled"):
        OBS.append((char, obs.get("turn"), obs))
    s = obs["sights"]
    if obs.get("town"):
        if obs.get("expedition_returned"):
            rec = next((f for f in (s.get("features") or [])
                        if f.get("type") == "npc" and f.get("name") == "길드 접수원"), None)
            if rec:
                return {"type": "interact" if rec.get("adj") else "goto", "target": rec["id"]}
            return {"type": "explore"}
        ex = s.get("exit")
        return ({"type": "interact" if ex.get("adj") else "goto", "target": "exit"}) if ex else {"type": "explore"}
    for m in s["monsters"]:
        if m["adj"]:
            return {"type": "attack", "target": m["id"]}
    if s["monsters"]:
        return {"type": "goto", "target": min(s["monsters"], key=lambda m: m["dist"])["id"]}
    ex = s.get("exit")
    return ({"type": "interact" if ex.get("adj") else "goto", "target": "exit"}) if ex else {"type": "explore"}


G.dummy_brain = scripted

# 지닌 것의 재료를 판의 첫 스폰에만 심는다 — 그 뒤의 재스폰(층 전이·깨어남)은 '이어진 몸'이어야 한다
SEED_GEAR = {"weapon": "장검", "armor": "가죽 갑옷", "potions": 3, "boons": 2, "bag": 5, "str_up": 2, "dex_up": 1}
_spawn = G.spawn
seeded = set()


def spawn_seeded(d, char, bots, **kw):
    b = _spawn(d, char, bots, **kw)
    if char not in seeded:
        seeded.add(char)
        b["weapon"] = {"id": 9001, "name": SEED_GEAR["weapon"], "bonus": 2, "worn": [char]}
        b["armor"] = {"id": 9002, "name": SEED_GEAR["armor"], "bonus": 1, "worn": [char]}
        b["potions"], b["boons"], b["bag"] = SEED_GEAR["potions"], SEED_GEAR["boons"], SEED_GEAR["bag"]
        b["str"] += SEED_GEAR["str_up"]
        b["dex"] += SEED_GEAR["dex_up"]
    return b


G.spawn = spawn_seeded
_bot_snapshot = G.bot_snapshot
G.bot_snapshot = lambda b: {**_bot_snapshot(b), "gstr": b.get("str"), "gdex": b.get("dex")}   # 게이트 전용: 능력치도 스트림으로 본다
CARRY = ("bag", "potions", "boons", "gstr", "gdex")

# ── 죽음의 각본: 몹 차례 끝에 정해진 틱에 엔진의 공통 사망 처리로 쓰러뜨린다 ──
SCHED = []          # {"depth", "visit"(원정 번호), "tick"(그 층에 든 뒤 몇 틱째) | "turn"(마을은 절대 틱), "chars"}
_mt = G.Dungeon.monster_turn


def _visit(d):
    """그 층이 몇 번째 원정의 층인가 — 층의 시드(expedition_seed(n))에서 읽는다. 프로세스 카운터로 세면 이어간 판에서 0부터 다시 세어
    같은 죽음을 두 번 일으킨다(첫 실행에서 실제로 그랬다). 마을은 늘 1."""
    if d.depth == 0:
        return 1
    return next((n for n in range(1, 30) if d.master_seed == show_runner.expedition_seed(n)), 0)


def _kill(d, b, bots, by="고블린"):
    b["hp"], b["alive"] = 0, False
    ev = {"type": "monster_attack", "id": "m999", "monster": by, "target": b["char"], "roll": 20, "mod": 0,
          "total": 20, "ac": 10, "hit": True, "dmg": 99, "hp": 0, "down": True}
    g = d._on_down(b, bots, by=by, witness=False)
    if g:
        ev["grave"] = g
    return ev


def monster_turn_scripted(self, bots):
    evs = _mt(self, bots)
    if not hasattr(self, "_gate_t0"):                    # 층 객체마다 한 번 — 그 층에 든 틱(객체에 적는다 — 피클을 건너 이어간 판에도 남는다)
        self._gate_visit, self._gate_t0 = _visit(self), self.turn
    for s in SCHED:
        if s["depth"] != self.depth or s.get("visit", 1) != self._gate_visit:
            continue
        hit = (self.turn == s["turn"]) if "turn" in s else (self.turn - self._gate_t0 == s["tick"])
        if not hit:
            continue
        for c in s["chars"]:
            b = next((x for x in bots if x["char"] == c and x["alive"]), None)
            if b is not None:
                evs.append(_kill(self, b, bots))
    return evs


G.Dungeon.monster_turn = monster_turn_scripted


def run(revive, sched=(), resume=""):
    """러너 한 판 — revive 는 show_runner.REVIVE_ON(스위치 상수는 import 때 굳는다). 스트림 줄을 돌려준다."""
    seeded.clear()
    del OBS[:]
    SCHED[:] = [dict(s) for s in sched]
    old = (show_runner.REVIVE_ON, show_runner.LOOP_ON)
    show_runner.REVIVE_ON, show_runner.LOOP_ON, show_runner.RESUME_PATH = revive, True, resume
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                show_runner.main()
            except SystemExit:
                pass
    finally:
        (show_runner.REVIVE_ON, show_runner.LOOP_ON), show_runner.RESUME_PATH = old, ""
    with open(os.path.join(STATE, "stream.jsonl"), encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


def canon(rows):
    return [json.dumps({k: v for k, v in r.items() if not (r.get("kind") == "run_meta" and k in ("started", "revive"))},
                       ensure_ascii=False, sort_keys=True) for r in rows]


def kinds(rows, kind):
    return [r for r in rows if r.get("kind") == kind]


def upto_first(rows, kind):
    """그 kind 의 첫 줄까지(포함)."""
    out = []
    for r in rows:
        out.append(r)
        if r.get("kind") == kind:
            break
    return out


def after(rows, i_kind_row):
    i = rows.index(i_kind_row)
    return rows[i + 1:]


def temple_cell(level):
    f = next((f for f in (level.get("features") or []) if f.get("type") == "building" and f.get("name") == "신전"), None)
    return (f["x"], f["y"]) if f else None


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def party_of(level):
    return {p["char"]: p for p in (level.get("party") or [])}


def gear_name(p, slot):
    return (p.get(slot) or {}).get("name")


def body_same(p, q):
    return (all(p.get(k) == q.get(k) for k in CARRY)
            and gear_name(p, "weapon") == gear_name(q, "weapon") and gear_name(p, "armor") == gear_name(q, "armor"))


COMPANION_DOWN = [{"depth": 1, "visit": 1, "tick": 2, "chars": ["2"]}]
MAIN_DOWN = [{"depth": 1, "visit": 1, "tick": 2, "chars": ["1"]}]
ALL_DOWN = [{"depth": 1, "visit": 1, "tick": 2, "chars": ["1", "2", "3"]}]
TWICE = [{"depth": 1, "visit": 1, "tick": 2, "chars": ["1"]}, {"depth": 1, "visit": 2, "tick": 2, "chars": ["1"]}]
TOWN_DOWN = [{"depth": 0, "turn": 3, "chars": ["2"]}]

# ── ① 스위치 끔 = 옛 판 그대로 ─────────────────────────────
print("── ① 스위치 끔 = 옛 판 그대로")
off1 = run(False, COMPANION_DOWN)
OFF1_PATH = os.path.join(TMP, "off1.jsonl")
shutil.copy2(os.path.join(STATE, "stream.jsonl"), OFF1_PATH)   # ② 의 캠페인 대조용(다음 판이 state 를 덮는다)
os.environ["DUNGEON_REVIVE"] = "0"                    # 명시적 '0' 도 같은 판(상수를 만드는 식 그대로 다시 계산)
off2 = run(os.environ.get("DUNGEON_REVIVE", "0") == "1" and show_runner.LOOP_ON and not show_runner.PARTYFORM_ON, COMPANION_DOWN)
os.environ.pop("DUNGEON_REVIVE", None)
check("① 미지정 판과 '0' 판의 스트림이 바이트 동일", canon(off1) == canon(off2) and len(off1) > 50, len(off1))
check("① 끈 판의 run_meta·세계 지문에 revive 없음",
      "revive" not in off1[0] and "revive" not in show_runner._world_fingerprint())
d1_off = [lv for lv in kinds(off1, "level") if lv["depth"] == 1]
downs_off = [e for t in kinds(off1, "tick") for e in (t.get("events") or []) if e.get("down")]
check("① 끈 판: 쓰러진 동료는 돌아오지 않는다(revive 줄 0 · 다음 원정의 지하 1층에 2번이 없다) · 죽음이 실제로 일어났다",
      not kinds(off1, "revive") and len(d1_off) >= 2 and "2" not in party_of(d1_off[1]) and "2" in party_of(d1_off[0])
      and [e["target"] for e in downs_off] == ["2"],
      ([sorted(party_of(lv)) for lv in d1_off], [e.get("target") for e in downs_off]))

# ── ② 동료가 먼저 쓰러짐 ───────────────────────────────────
print("── ② 동료가 먼저 쓰러짐 — 일행이 마을에 들어서면 신전 곁에서 깨어난다")
on2 = run(True, COMPANION_DOWN)
ON2_PATH = os.path.join(TMP, "on2.jsonl")
shutil.copy2(os.path.join(STATE, "stream.jsonl"), ON2_PATH)
obs2 = list(OBS)
asc2 = kinds(on2, "ascend")
check("② 켠 판의 run_meta 에 revive · 첫 마을 귀환(ascend)까지의 줄이 끈 판과 같다(갈라지는 자리는 깨어남뿐)",
      on2[0].get("revive") is True and bool(asc2)
      and canon(upto_first(on2, "ascend")) == canon(upto_first(off1, "ascend")) and len(upto_first(on2, "ascend")) > 20,
      len(upto_first(on2, "ascend")))
rv2 = kinds(on2, "revive")
lv_home = next((r for r in after(on2, asc2[0]) if r.get("kind") == "level"), {}) if asc2 else {}
home = party_of(lv_home)
tc = temple_cell(lv_home)
start1 = party_of([lv for lv in kinds(on2, "level") if lv["depth"] == 1][0])
check("② 워프로 돌아온 마을의 level 에 2번이 있다 — 신전 문턱 곁(2칸 안) · 1·3번은 던전 입구 쪽",
      lv_home.get("depth") == 0 and "2" in home and tc is not None and cheb((home["2"]["x"], home["2"]["y"]), tc) <= 2
      and all(cheb((home[c]["x"], home[c]["y"]), tc) > 2 for c in ("1", "3")),
      (tc, {c: (p["x"], p["y"]) for c, p in home.items()}))
check("② 깨어난 몸: HP 가득 · 지닌 것(장비·물약·축복·보물·능력치)은 쓰러지기 전 그대로 · 심은 재료가 실제로 실려 있다",
      "2" in home and home["2"]["hp"] == home["2"]["maxhp"] and home["2"]["alive"] is True
      and body_same(home["2"], start1["2"]) and gear_name(start1["2"], "weapon") == SEED_GEAR["weapon"]
      and start1["2"].get("boons") == SEED_GEAR["boons"],
      (home.get("2"), start1.get("2")))
check("② revive 줄 하나(2번 · 쓰러진 층 1 · 사인 고블린 · 신전) — level 바로 뒤",
      len(rv2) == 1 and [p["char"] for p in rv2[0]["party"]] == ["2"] and rv2[0]["party"][0].get("depth") == 1
      and rv2[0]["party"][0].get("by") == "고블린" and rv2[0].get("where") == "temple"
      and on2[on2.index(rv2[0]) - 1] is lv_home, rv2)
first2 = next((o for c, t, o in obs2 if c == "2"), None)
names2 = {"1": "두란", "2": "카야", "3": "피른"}
wired2 = brains._wire(first2, names2) if first2 else ""
mem2 = [e for e in ((first2 or {}).get("memories") or []) if e.get("kind") == "died"]
check("② 2번의 첫 관측: last = 깨어남(쓰러진 층 1) · 기억에 '네가 쓰러짐' 한 줄(사인은 도감이 가린다 — 처음 보는 종이면 낯선 짐승)",
      first2 is not None and first2["last"] == {"type": "revived", "depth": 1}
      and len(mem2) == 1 and mem2[0].get("depth") == 1 and mem2[0].get("by") in ("고블린", G.UNKNOWN_BEAST),
      (first2 or {}).get("last") if first2 else "관측 없음")
check("② 프롬프트 글에 실린다: '신전 앞에서 다시 깨어났다' · '[네가 쓰러짐] 지하 1층에서 … 쓰러졌다'",
      "마을 신전 앞에서 다시 깨어났다" in wired2 and "[네가 쓰러짐] 지하 1층에서" in wired2, len(wired2))
import campaign                                      # noqa: E402
p_off, p_on = campaign.project(OFF1_PATH), campaign.project(ON2_PATH)
check("② 캠페인 기록(D78): 깨어난 2번은 판 끝에 살아 있다 · 쓰러진 틱은 남는다('쓰러짐' 표시) · 끈 판은 옛 그대로(쓰러진 채)",
      p_on["chars"]["2"]["alive"] is True and p_on["chars"]["2"]["died_turn"] is not None
      and p_off["chars"]["2"]["alive"] is False and p_off["chars"]["2"]["died_turn"] == p_on["chars"]["2"]["died_turn"],
      (p_on["chars"]["2"], p_off["chars"]["2"]))
check("② 판 끝: 전멸·종료 없이 틱 상한까지 흐른다(outcome timeout · 쓰러짐에 2번 한 번)",
      on2[-1]["kind"] == "end" and on2[-1]["outcome"] == "timeout" and on2[-1]["fallen"].count("2") == 1,
      {k: on2[-1].get(k) for k in ("outcome", "fallen")})

# ── ③ 메인이 쓰러짐 ────────────────────────────────────────
print("── ③ 메인이 쓰러짐 — 그 틱에 일행이 함께 마을로")
on3 = run(True, MAIN_DOWN)
obs3 = list(OBS)
down3 = next((t for t in kinds(on3, "tick") for e in (t.get("events") or []) if e.get("down") and e.get("target") == "1"), None)
asc3 = kinds(on3, "ascend")
check("③ 메인이 쓰러진 그 틱에 ascend(fell=1 · gate 없음 · 일행=2·3) — 워프게이트를 탄 게 아니다",
      down3 is not None and bool(asc3) and asc3[0]["turn"] == down3["turn"] and asc3[0].get("fell") == "1"
      and "gate" not in asc3[0] and sorted(p["char"] for p in asc3[0]["party"]) == ["2", "3"],
      (down3 or {}).get("turn") if down3 else None)
lv3 = next((r for r in after(on3, asc3[0]) if r.get("kind") == "level"), {}) if asc3 else {}
home3, tc3 = party_of(lv3), temple_cell(lv3)
gate3 = tuple(lv3.get("exit") or (0, 0))
check("③ 마을 level: 메인은 신전 곁에서 깨어나고(HP 가득) 동료는 던전 입구 곁에 선다 · revive 줄 = 1번",
      lv3.get("depth") == 0 and tc3 is not None and set(home3) == {"1", "2", "3"}
      and cheb((home3["1"]["x"], home3["1"]["y"]), tc3) <= 2 and home3["1"]["hp"] == home3["1"]["maxhp"]
      and all(cheb((home3[c]["x"], home3[c]["y"]), gate3) <= 2 for c in ("2", "3"))
      and [p["char"] for p in (kinds(on3, "revive")[0]["party"] if kinds(on3, "revive") else [])] == ["1"],
      (tc3, gate3, {c: (p["x"], p["y"]) for c, p in home3.items()}))
rec3 = [(c, o) for c, t, o in obs3 if (o.get("last") or {}).get("type") == "recalled"]
wired3 = brains._wire(rec3[0][1], names2) if rec3 else ""
check("③ 동료의 첫 관측: last = 돌아옴(fell=1 · 층 1) · 글 '두란(봇1)가 지하 1층에서 쓰러져 원정이 끝났다'",
      sorted(c for c, o in rec3) == ["2", "3"] and all(o["last"] == {"type": "recalled", "fell": "1", "depth": 1} for c, o in rec3)
      and "두란(봇1)가 지하 1층에서 쓰러져 원정이 끝났다" in wired3,
      [(c, o.get("last")) for c, o in rec3])


class _Town:                                         # npc_facts 가 읽는 것만 — 마을을 짓지 않고 문장층만 본다
    npc_defs = {"길드 접수원": {"report": True, "role": "접수"}}
    parties = None
    expedition_returned = True
    expedition_fell = "두란"
    quest_ids = {}
    features = {}


_b = [{"char": "1", "name": "두란", "job": "전사", "hp": 14, "maxhp": 14, "alive": True}]
f3 = show_runner.npc_facts(_Town(), "길드 접수원", _b, ["1"], None, 1)
_Town.expedition_fell = None
f3w = show_runner.npc_facts(_Town(), "길드 접수원", _b, [], None, 1)
check("③ NPC 가 아는 사실: 메인이 쓰러져 돌아온 원정은 '워프게이트로 귀환'이라 하지 않는다(게이트로 돌아온 원정은 그대로)",
      any("두란이(가) 던전에서 쓰러져 원정이 끝났다" in s for s in f3) and not any("워프게이트" in s for s in f3)
      and any("워프게이트로 귀환" in s for s in f3w), f3)
exp3 = kinds(on3, "expedition")
check("③ 보고하면 결산(1차 쓰러짐 = 메인) · 다음 원정이 이어지고 판은 틱 상한까지(wiped 없음)",
      bool(exp3) and exp3[0].get("fallen") == ["1"] and on3[-1]["outcome"] == "timeout"
      and len([lv for lv in kinds(on3, "level") if lv["depth"] == 1]) >= 2,
      ([e.get("fallen") for e in exp3], on3[-1].get("outcome")))

# ── ④ 모두 쓰러짐 ─────────────────────────────────────────
print("── ④ 모두 쓰러짐 — 전멸은 없다")
on4 = run(True, ALL_DOWN)
asc4, rv4 = kinds(on4, "ascend"), kinds(on4, "revive")
lv4 = next((r for r in after(on4, asc4[0]) if r.get("kind") == "level"), {}) if asc4 else {}
tc4 = temple_cell(lv4)
check("④ 셋 다 같은 틱에 쓰러져도 판이 닫히지 않는다: ascend(fell=1 · 일행 없음) → 마을 → revive 셋 · 셋 다 신전 곁",
      bool(asc4) and asc4[0].get("fell") == "1" and asc4[0]["party"] == [] and bool(rv4)
      and sorted(p["char"] for p in rv4[0]["party"]) == ["1", "2", "3"] and tc4 is not None
      and all(cheb((p["x"], p["y"]), tc4) <= 2 for p in party_of(lv4).values()) and len(party_of(lv4)) == 3,
      (asc4[:1], rv4[:1]))
check("④ wiped 가 없다 · 다음 원정이 이어진다 · 틱 상한으로 끝난다",
      on4[-1]["outcome"] == "timeout" and len([lv for lv in kinds(on4, "level") if lv["depth"] == 1]) >= 2,
      on4[-1].get("outcome"))

# ── ⑤ 두 번 쓰러지면 두 번 깨어난다 ─────────────────────────
print("── ⑤ 두 번 쓰러지면 두 번 깨어난다")
on5 = run(True, TWICE)
rv5 = [r for r in kinds(on5, "revive") if [p["char"] for p in r["party"]] == ["1"]]
exp5 = kinds(on5, "expedition")
check("⑤ 메인이 두 원정에서 각각 쓰러지고 각각 깨어난다(revive 둘) · 두 결산의 쓰러짐 = 메인 · end 의 fallen 에 두 번",
      len(rv5) == 2 and len(exp5) >= 2 and exp5[0].get("fallen") == ["1"] and exp5[1].get("fallen") == ["1"]
      and on5[-1]["fallen"].count("1") == 2,
      (len(rv5), [e.get("fallen") for e in exp5], on5[-1].get("fallen")))

# ── ⑥ 마을에서 쓰러짐 ─────────────────────────────────────
print("── ⑥ 마을에서 쓰러짐 — 그 틱에 신전 곁에서")
on6 = run(True, TOWN_DOWN)
rv6 = kinds(on6, "revive")
nxt6 = next((t for t in kinds(on6, "tick") if t["turn"] == 4), {})
lv0 = kinds(on6, "level")[0]
b6 = {b["char"]: b for b in (nxt6.get("bots") or [])}
check("⑥ 마을에서 쓰러진 2번이 그 틱(t3)에 깨어난다(revive · 사인·층 0) · 다음 틱 기록에 살아 있고 신전 곁 · 쓰러짐에 센다",
      len(rv6) >= 1 and rv6[0]["turn"] == 3 and rv6[0]["party"][0]["char"] == "2" and rv6[0]["party"][0].get("depth") == 0
      and b6.get("2", {}).get("alive") is True and temple_cell(lv0) is not None
      and cheb((b6["2"]["x"], b6["2"]["y"]), temple_cell(lv0)) <= 2 and on6[-1]["fallen"].count("2") == 1,
      (rv6[:1], b6.get("2")))

# ── ⑦ 피클 이어가기 ───────────────────────────────────────
print("── ⑦ 피클 이어가기(2층짜리 판 — 1층에서 쓰러진 동료가 대기 장부에 든 채 일행은 2층에 있을 때 멈춘다)")
_depths = show_runner.DEPTHS
show_runner.DEPTHS = 2                               # 대기 장부는 층 전이 때 찬다 — 1층짜리 판에선 쓰러진 사람이 아직 bots 에 있다
ctrl7 = run(True, COMPANION_DOWN)
lv2 = next((lv for lv in kinds(ctrl7, "level") if lv["depth"] == 2), None)
STOP_AT = (lv2["turn"] + 3) if lv2 else 10           # 2층에 내려선 뒤 곱게 멈춘다
calls = {"n": 0}
_orig_stop = show_runner.run_control.stop_requested


def _fake_stop(state):
    calls["n"] += 1
    return {"id": "revive-gate", "pages": False} if calls["n"] == STOP_AT else None


show_runner.run_control.stop_requested = _fake_stop
try:
    stopped = run(True, COMPANION_DOWN)
finally:
    show_runner.run_control.stop_requested = _orig_stop
pkl = os.path.join(STATE, snapshot.PKL)
# 이 게이트가 방금 제 임시 폴더에 쓴 스냅샷만 연다(러너의 snapshot.load 와 같은 파일) — 바깥에서 온 피클이 아니다
snap_body = pickle.load(open(pkl, "rb")) if os.path.isfile(pkl) else {}
wt = snap_body.get("waiting") or {}
check("⑦ 동료가 쓰러진 뒤 멈춘 스냅샷: 2층(일행) · 대기 장부에 2번(지닌 장비·사인 그대로) · 지문에 revive · stopped 줄 · end 없음",
      lv2 is not None and getattr(snap_body.get("d"), "depth", None) == 2 and sorted(wt) == ["2"] and gear_name(wt["2"], "weapon") == SEED_GEAR["weapon"] and wt["2"].get("down_by", {}).get("by") == "고블린"
      and (snap_body.get("world") or {}).get("revive") is True and bool(kinds(stopped, "stopped")) and not kinds(stopped, "end"),
      (sorted(wt), (snap_body.get("world") or {}).get("revive")))
_rv = show_runner.REVIVE_ON
show_runner.REVIVE_ON = False                        # 부활을 끈 러너가 이 스냅샷을 열면 — 지문이 거절한다(파일은 그대로)
show_runner.RESUME_PATH = pkl
_s, _m, fail = show_runner._load_resume()
show_runner.RESUME_PATH = ""
show_runner.REVIVE_ON = _rv
check("⑦ 부활을 끈 러너는 그 스냅샷을 거절한다(사유에 revive) · 스냅샷은 그대로",
      _s is None and fail is not None and "revive" in fail.get("reason", "") and os.path.isfile(pkl), fail)
resumed = run(True, COMPANION_DOWN, resume=pkl)


def tail(rows, after_t):
    return canon([r for r in rows if r.get("kind") in ("tick", "level", "descend", "ascend", "expedition", "revive", "end")
                  and r.get("turn", 0) > after_t])


check("⑦ 이어간 판의 꼬리가 대조군과 같다(2번이 같은 자리에서 깨어난다) · end 한 줄",
      tail(resumed, STOP_AT - 1) == tail(ctrl7, STOP_AT - 1) and len(tail(ctrl7, STOP_AT - 1)) > 5
      and any(r.get("kind") == "revive" and r.get("turn", 0) > STOP_AT for r in resumed) and len(kinds(resumed, "end")) == 1,
      (len(tail(resumed, STOP_AT - 1)), len(tail(ctrl7, STOP_AT - 1))))
show_runner.DEPTHS = _depths

# ── ⑧ 배선 ────────────────────────────────────────────────
print("── ⑧ 배선")
lp = io.open(os.path.join(HERE, "launcher.py"), encoding="utf-8").read()
lh = io.open(os.path.join(HERE, "launcher", "index.html"), encoding="utf-8").read()
sr = io.open(os.path.join(HERE, "show_runner.py"), encoding="utf-8").read()
gates = io.open(os.path.join(HERE, "_run_gates.sh"), encoding="utf-8").read()
import launcher                                      # noqa: E402
check("⑧ 론처: env 줄(옵션 없으면 끈다) · 화면 본문이 원정 고리 칸 값을 revive 로 싣는다 · 옵션 판 번호 3(화면과 같다)",
      'env["DUNGEON_REVIVE"] = "1" if opts.get("revive") is True else "0"' in lp
      and "revive: $('loop').checked," in lh and launcher.OPTIONS_UI_VERSION == 3 and "presets.options_ui_version !== 3" in lh)
check("⑧ 러너: 원정 고리 판에서만 · 파티 결성 판은 끔 · run_meta·지문에 켠 판만",
      re.search(r'REVIVE_ON = os\.environ\.get\("DUNGEON_REVIVE", "0"\) == "1" and LOOP_ON and not PARTYFORM_ON', sr) is not None
      and sr.count('**({"revive": True} if REVIVE_ON else {})') == 2)
check("⑧ 자기 등록: _run_gates.sh 목록에 verify_revive", re.search(r"\bverify_revive\b", gates) is not None)

print()
if C.failed:
    print("FAILED %d — verify_revive" % C.failed)
    sys.exit(1)
print("ALL PASS — verify_revive (D99 부활: 끈 판 그대로 · 동료/메인/모두/두 번/마을 · 이어가기 · 배선)")

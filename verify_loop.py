# -*- coding: utf-8 -*-
"""원정 고리(D94, 2026-09-20) 헤들리스 검증 — 83번째 게이트. LLM 0콜(각본 더미 두뇌 · 상태 폴더는 tempfile).
파트너 교정: "귀환보고는 던전의 끝이지 판의 끝은 아니지 않아? 기본 게임은 루프 구조를 가지고 있어. 마을에서 생활하면서 던전에
내려가고 다시 마을로 돌아와, 던전에서 돌아오면 결산이 되는거고 말야". 스위치 DUNGEON_LOOP(러너 기본 0) 뒤에서 길드 보고가
판을 닫지 않는다 — 결산 한 줄을 내고 마을은 그대로 흐르며, 던전 입구를 다시 쓰면 새 시드의 지하 1층부터 다음 원정이다.
게이트:
  ① 스위치 끔 = 옛 판 그대로: 미지정 판과 '0' 판의 스트림 바이트 동일 · run_meta·세계 지문에 loop 없음 · expedition 줄 0 ·
     보고가 판을 닫는다(보고 틱이 곧 end, outcome 'returned')
  ② 원정 시드(순수 함수 expedition_seed): 1차 = 판의 시드 그대로 · 2차부터 다른 시드 · 두 번 불러도 같다 ·
     같은 원정 번호로 두 번 지은 지하 1층 격자가 같고 원정이 다르면 다르다 · 인자 없는 옛 new_floor(1) = 1차 원정의 층
  ③ 켠 판: 첫 보고 전까지의 줄이 끈 판과 같다(갈라지는 자리는 보고뿐) · 보고 뒤에도 틱이 이어진다 ·
     결산(expedition) 줄이 원정마다 한 번(보고 수와 같고 n 이 1,2,…) · 마을↔던전을 다시 오간다 ·
     2차 원정의 지하 1층 격자가 1차와 다르고 그 level_seed 가 expedition_seed(n) 에서 파생된 값이다
  ④ 이월(성장의 첫 칸): 2차 원정 지하 1층에 선 몸이 1차에서 돌아온 마을의 몸 그대로다(장비·축복·물약·보물·능력치) —
     새 이월 목록 없이 층 전이가 잇는 길 그대로
  ⑤ 시계는 MAX_TURNS: 원정 횟수 상한 없이 틱 상한이 판을 닫는다(outcome 'timeout', 마지막 틱 = 상한, end 한 줄)
  ⑥ 피클 이어가기(D79): 결산 뒤 스냅샷에 원정 번호가 얼어 있다 · 고리를 끈 러너는 그 스냅샷을 거절한다(지문 loop) ·
     이어간 판의 꼬리가 대조군과 같다(다시 짓지 않는다)
  ⑦ 세계가 거짓말하지 않는다: 결산으로 장부의 귀환·보고 표식이 비고 끝난 판이 '워프로 돌아온 판'이라 말하지 않는다 ·
     NPC 가 아는 사실이 2차 원정을 말한다(끈 판은 옛 문장 그대로)
  ⑧ 배선·자기 등록(_run_gates.sh)
"""
import contextlib
import hashlib
import io
import json
import os
import pickle
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="wl_loop_")
STATE = os.path.join(TMP, "state")
os.makedirs(STATE, exist_ok=True)
for _k in [k for k in os.environ if k.startswith("DUNGEON_")]:   # 게이트 환경(_run_gates.sh)의 값까지 걷고 이 게이트의 판을 명시한다
    os.environ.pop(_k)
RUN_ENV = dict(DUNGEON_BRAIN_BACKEND="dummy", DUNGEON_ACTION_MODE="menu", DUNGEON_SKILLS="0",
               DUNGEON_TRPG_COMBAT="0", DUNGEON_RANDOM_SKILL="0", DUNGEON_BESTIARY_FILE="",
               DUNGEON_GM="0", DUNGEON_STEP_DELAY="0", DUNGEON_PARTY_FILE=os.path.join(HERE, "party.json"),
               DUNGEON_STATE_DIR=STATE, DUNGEON_RUNS_DIR=os.path.join(TMP, "runs"),
               # 작은 판: 마을 → 보스 하나뿐인 지하 1층 → 워프 귀환 → 보고. 몹·함정·장비·물약은 0(이월 재료는 ④ 가 첫 스폰에 심는다)
               DUNGEON_SEED="7", DUNGEON_W="40", DUNGEON_H="16", DUNGEON_TOWN="1", DUNGEON_BOSS="1",
               DUNGEON_DEPTHS="1", DUNGEON_TURNS="340", DUNGEON_MONSTERS="0", DUNGEON_TRAPS="0",
               DUNGEON_LURKERS="0", DUNGEON_GEAR="0", DUNGEON_POTIONS="0")
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


# ── 각본 두뇌(0콜): 마을에선 던전 입구(돌아온 뒤면 접수원)로, 던전에선 보스를 치고 워프게이트로 ──
_stats = G.ENT.monster_stats
G.ENT.monster_stats = lambda kind: {**_stats(kind), "hp": 1, "atk": 0, "dmg": 0, "ac": 5}   # 게이트 전용: 보스도 한 대에(배관을 끝까지 본다)


def scripted(obs, char="?"):
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

# ④ 의 재료를 판의 첫 스폰에만 심는다 — 그 뒤 층 전이의 재스폰은 '이월된 몸'이어야 한다
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


def run(loop, resume=""):
    """러너 한 판 — loop 는 show_runner.LOOP_ON(스위치 상수는 import 때 굳는다). 스트림 줄을 돌려준다."""
    seeded.clear()
    old = show_runner.LOOP_ON
    show_runner.LOOP_ON, show_runner.RESUME_PATH = loop, resume
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                show_runner.main()
            except SystemExit:
                pass
    finally:
        show_runner.LOOP_ON, show_runner.RESUME_PATH = old, ""
    with open(os.path.join(STATE, "stream.jsonl"), encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


def canon(rows):
    """줄을 바이트 비교용 문자열로 — run_meta 의 started(유일한 비결정 필드)만 뺀다."""
    return [json.dumps({k: v for k, v in r.items() if not (r.get("kind") == "run_meta" and k == "started")},
                       ensure_ascii=False, sort_keys=True) for r in rows]


def before_report(rows):
    """첫 보고가 갈라놓기 전까지의 줄 — 켠 판은 expedition, 끈 판은 end 에서 갈린다."""
    out = []
    for r in rows:
        if r.get("kind") in ("expedition", "end"):
            break
        out.append(r)
    return out


def tail(rows, after):
    """세계의 줄만(resume·stopped 같은 운영 줄은 빼고) 그 틱 뒤로."""
    return canon([r for r in rows if r.get("kind") in ("tick", "level", "descend", "ascend", "expedition", "end")
                  and r.get("turn", 0) > after])


def kinds(rows, kind):
    return [r for r in rows if r.get("kind") == kind]


def reports_of(rows):
    return [r["turn"] for r in kinds(rows, "tick") for e in (r.get("events") or []) if e.get("result") == "npc_report"]


# ── ① 스위치 끔 = 옛 판 그대로 ─────────────────────────────
print("── ① 스위치 끔 = 옛 판 그대로")
off1 = run(False)
os.environ["DUNGEON_LOOP"] = "0"                      # 명시적 '0' 도 같은 판(상수를 만드는 식 그대로 다시 계산)
off2 = run(os.environ.get("DUNGEON_LOOP", "0") == "1" and show_runner.TOWN_ON
           and show_runner.QUESTS_ON and show_runner.NOTICES_ON)
os.environ.pop("DUNGEON_LOOP", None)
check("① 미지정 판과 '0' 판의 스트림이 바이트 동일", canon(off1) == canon(off2),
      hashlib.sha256("\n".join(canon(off1)).encode("utf-8")).hexdigest()[:12])
check("① 끈 판의 run_meta·세계 지문에 loop 없음",
      "loop" not in off1[0] and "loop" not in show_runner._world_fingerprint())
rep_t = (reports_of(off1) or [None])[0]
check("① 끈 판: 보고가 판을 닫는다(expedition 줄 0 · 보고 틱이 곧 end · outcome 'returned')",
      rep_t is not None and not kinds(off1, "expedition") and off1[-1]["kind"] == "end"
      and off1[-1]["outcome"] == "returned" and off1[-1]["turn"] == rep_t,
      (rep_t, off1[-1].get("outcome"), off1[-1].get("turn")))

# ── ② 원정 시드(순수 함수) ─────────────────────────────────
print("── ② 원정 시드")
es = show_runner.expedition_seed
check("② 1차 = 판의 시드 그대로 · 2차부터 다른 시드 · 두 번 불러도 같다",
      es(1) == show_runner.DUNGEON_SEED and es(0) == es(1) and len({es(1), es(2), es(3)}) == 3
      and (es(2), es(3)) == (es(2), es(3)), (es(1), es(2), es(3)))
g1 = ["".join(r) for r in show_runner.new_floor(1, {}, seed=es(1)).grid]
g1b = ["".join(r) for r in show_runner.new_floor(1, {}, seed=es(1)).grid]
g2 = ["".join(r) for r in show_runner.new_floor(1, {}, seed=es(2)).grid]
g2b = ["".join(r) for r in show_runner.new_floor(1, {}, seed=es(2)).grid]
g_old = ["".join(r) for r in show_runner.new_floor(1, {}).grid]
check("② 같은 원정 번호 = 같은 격자 · 원정이 다르면 다른 격자 · 인자 없는 옛 호출 = 1차 원정의 층",
      g1 == g1b and g2 == g2b and g1 != g2 and g_old == g1)

# ── ③ 켠 판: 보고가 판을 닫지 않는다 ───────────────────────
print("── ③ 켠 판(보고 = 원정의 끝, 판의 끝이 아니다)")
on = run(True)
reports, exps = reports_of(on), kinds(on, "expedition")
check("③ 켠 판의 run_meta 에 loop · 첫 보고 전까지의 줄이 끈 판과 같다(갈라지는 자리는 보고뿐)",
      on[0].get("loop") is True
      and canon(before_report(on))[1:] == canon(before_report(off1))[1:] and len(before_report(off1)) > 20,
      len(before_report(on)))
check("③ 보고 뒤에도 틱이 이어진다(마지막 틱 > 첫 보고 틱)",
      bool(reports) and kinds(on, "tick")[-1]["turn"] > reports[0], (reports, kinds(on, "tick")[-1]["turn"]))
check("③ 결산 줄이 원정마다 한 번(보고 수와 같다 · n 은 1,2,… · 틱이 보고와 같다)",
      len(exps) == len(reports) >= 2 and [e["n"] for e in exps] == list(range(1, len(exps) + 1))
      and [e["turn"] for e in exps] == reports, ([e.get("n") for e in exps], reports))
depths = [lv["depth"] for lv in kinds(on, "level")]
check("③ 마을↔던전을 다시 오간다(0,1,0,1,0 — 한 원정만 도는 끈 판은 0,1,0)",
      depths[:5] == [0, 1, 0, 1, 0] and [lv["depth"] for lv in kinds(off1, "level")] == [0, 1, 0],
      (depths, [lv["depth"] for lv in kinds(off1, "level")]))
d1 = [lv for lv in kinds(on, "level") if lv["depth"] == 1]
check("③ 원정마다 다른 지하 1층 · level_seed 가 expedition_seed(n) 파생값",
      len(d1) >= 2 and len({tuple(lv["grid"]) for lv in d1}) == len(d1)
      and [lv["level_seed"] for lv in d1] == [G.Dungeon._derive_seed(es(i + 1), 1) for i in range(len(d1))],
      [lv.get("level_seed") for lv in d1])

# ── ④ 이월 ────────────────────────────────────────────────
print("── ④ 이월(성장의 첫 칸)")
towns = [lv for lv in kinds(on, "level") if lv["depth"] == 0]
home1 = {p["char"]: p for p in (towns[1]["party"] if len(towns) > 1 else [])}    # 1차 원정에서 돌아온 마을
away2 = {p["char"]: p for p in (d1[1]["party"] if len(d1) > 1 else [])}          # 2차 원정의 지하 1층
start1 = {p["char"]: p for p in d1[0]["party"]}                                  # 1차 원정의 지하 1층(심은 재료가 실린 곳)


def gear_name(p, slot):
    return (p.get(slot) or {}).get("name")


check("④ 2차 원정 지하 1층의 몸 = 1차에서 돌아온 마을의 몸 그대로(장비·축복·물약·보물·능력치)",
      bool(away2) and set(home1) == set(away2)
      and all(all(away2[c].get(k) == home1[c].get(k) for k in CARRY)
              and gear_name(away2[c], "weapon") == gear_name(home1[c], "weapon")
              and gear_name(away2[c], "armor") == gear_name(home1[c], "armor") for c in home1),
      [(c, {k: (home1[c].get(k), away2.get(c, {}).get(k)) for k in CARRY}) for c in home1])
check("④ 심은 재료가 실제로 실려 있다(빈 값끼리 같아서 통과한 게 아니다)",
      bool(start1) and all(gear_name(p, "weapon") == SEED_GEAR["weapon"] and gear_name(p, "armor") == SEED_GEAR["armor"]
                           and p.get("boons") == SEED_GEAR["boons"] and p.get("potions") == SEED_GEAR["potions"]
                           and int(p.get("bag") or 0) >= SEED_GEAR["bag"] for p in start1.values()),
      [(c, gear_name(p, "weapon"), p.get("boons"), p.get("bag")) for c, p in start1.items()])

# ── ⑤ 시계는 MAX_TURNS ────────────────────────────────────
print("── ⑤ 시계는 MAX_TURNS")
check("⑤ 원정 횟수 상한이 아니라 틱 상한이 판을 닫는다(outcome 'timeout' · 마지막 틱 = 상한 · end 한 줄)",
      on[-1]["kind"] == "end" and on[-1]["outcome"] == "timeout" and on[-1]["turn"] == TURNS
      and len(kinds(on, "end")) == 1, {k: on[-1].get(k) for k in ("outcome", "turn")})

# ── ⑥ 피클 이어가기(D79) ──────────────────────────────────
print("── ⑥ 피클 이어가기")
STOP_AT = exps[0]["turn"] + 3                        # 첫 결산 바로 뒤에서 곱게 멈춘다
calls = {"n": 0}
_orig_stop = show_runner.run_control.stop_requested


def _fake_stop(state):
    calls["n"] += 1
    return {"id": "loop-gate", "pages": False} if calls["n"] == STOP_AT else None


show_runner.run_control.stop_requested = _fake_stop
try:
    stopped = run(True)
finally:
    show_runner.run_control.stop_requested = _orig_stop
pkl = os.path.join(STATE, snapshot.PKL)
# 이 게이트가 방금 제 임시 폴더에 쓴 스냅샷만 연다(러너의 snapshot.load 와 같은 파일) — 바깥에서 온 피클이 아니다
snap_body = pickle.load(open(pkl, "rb")) if os.path.isfile(pkl) else {}
check("⑥ 결산 뒤 스냅샷에 원정 번호가 얼어 있다(2차 원정 중) · stopped 줄 · end 없음",
      (snap_body.get("expedition") or {}).get("n") == 2 and (snap_body.get("world") or {}).get("loop") is True
      and bool(kinds(stopped, "stopped")) and not kinds(stopped, "end"), snap_body.get("expedition"))
_loop = show_runner.LOOP_ON
show_runner.LOOP_ON = False                          # 고리를 끈 러너가 이 스냅샷을 열면 — 지문이 거절한다(파일은 그대로)
show_runner.RESUME_PATH = pkl
_s, _m, fail = show_runner._load_resume()
show_runner.RESUME_PATH = ""
show_runner.LOOP_ON = _loop
check("⑥ 고리를 끈 러너는 그 스냅샷을 거절한다(사유에 loop) · 스냅샷은 그대로",
      _s is None and fail is not None and "loop" in fail.get("reason", "") and os.path.isfile(pkl), fail)
resumed = run(True, resume=pkl)
check("⑥ 이어간 판의 꼬리가 대조군과 같다(층을 다시 짓지 않는다) · end 한 줄",
      tail(resumed, STOP_AT - 1) == tail(on, STOP_AT - 1) and len(tail(on, STOP_AT - 1)) > 5
      and len(kinds(resumed, "end")) == 1, (len(tail(resumed, STOP_AT - 1)), len(tail(on, STOP_AT - 1))))

# ── ⑦ 세계가 거짓말하지 않는다 ─────────────────────────────
print("── ⑦ 세계가 거짓말하지 않는다")
endq = on[-1].get("quests") or {}
check("⑦ 결산이 장부의 귀환·보고 표식을 비운다 · 끝난 판이 '워프로 돌아온 판'이라 말하지 않는다(맡은 의뢰·완수는 그대로)",
      endq.get("returned") is None and endq.get("reported") is None and "warped" not in on[-1]
      and (off1[-1].get("quests") or {}).get("reported") is not None and off1[-1].get("warped") is True,
      (endq, on[-1].get("warped")))


class _Town:                                         # npc_facts 가 읽는 것만 — 마을을 짓지 않고 문장층만 본다
    npc_defs = {"길드 접수원": {"report": True, "role": "접수"}}
    parties = None
    expedition_returned = False
    quest_ids = {}
    features = {}


_b = [{"char": "1", "name": "두란", "job": "전사", "hp": 9, "maxhp": 14, "alive": True}]
f_old = show_runner.npc_facts(_Town(), "길드 접수원", _b, [], None)
f_new = show_runner.npc_facts(_Town(), "길드 접수원", _b, [], None, 2)
check("⑦ NPC 가 아는 사실: 끈 판은 옛 문장 · 2차 원정 판은 앞선 원정을 말한다('아직 안 내려갔다'가 거짓인 자리)",
      any("아직 던전에 내려가지 않았다" in s for s in f_old)
      and not any("아직 던전에 내려가지 않았다" in s for s in f_new)
      and any("앞선 원정 1번" in s and "2번째 원정" in s for s in f_new), f_new)

# ── ⑧ 배선·자기 등록 ──────────────────────────────────────
print("── ⑧ 배선·자기 등록")
rsrc = io.open(os.path.join(HERE, "show_runner.py"), encoding="utf-8").read()
gates_src = io.open(os.path.join(HERE, "_run_gates.sh"), encoding="utf-8").read()
check("⑧ 러너 배선: DUNGEON_LOOP 상수 · 결산 · 원정 시드 · 켠 판에만 적는 지문/run_meta",
      all(s in rsrc for s in ('LOOP_ON = os.environ.get("DUNGEON_LOOP", "0") == "1" and TOWN_ON and QUESTS_ON and NOTICES_ON',
                              "_settle_expedition(d, bots, turn, rep)", "def expedition_seed(n):",
                              'sw.emit("expedition"', '**({"loop": True} if LOOP_ON else {})',
                              "seed=expedition_seed(_exp_n() or 1)")))
check("⑧ _run_gates.sh 에 등록(부분 문자열이 아니라 낱말 경계로 — verify_isolated 와 같은 규칙)",
      re.search(r"\bverify_loop\b", gates_src) is not None)

print(("ALL PASS — verify_loop (원정 고리 D94 · 0콜 · 결산 %d회)" % len(exps)) if not C.failed else "FAILED %d" % C.failed)
sys.exit(1 if C.failed else 0)

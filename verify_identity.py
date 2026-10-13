# -*- coding: utf-8 -*-
"""p0.5.9 신원 ID-1 이름 층 — '기록은 내부 열쇠로, 호칭은 그릴 때' + 아는 사람 기억 자동 활성화(로어북처럼). LLM 0콜.
근거: .orch/drafts/identity_design_v2.md §0.2·§1(장부·호칭 함수 call)·§6(누출 중 ID-1 몫)·§7(ID-1 범위)·§8.1(판 2→3)·§8.4-1(게이트) ·
      DECISIONS 2026-10-12 62·67·69·76 · 2026-10-13(호칭 (가) · 아는 사람 기억은 로어북처럼 · 패치 번호 0.5.9).
게이트(설계 §8.4-1 번호 그대로 + 기억 자동 활성화 A):
  ① 시스템 누출 0 — 캐릭터·NPC 의 말에 실명이 없는 각본(사람 공격·피격·쓰러짐·묘·목격·교대·길막힘·건넴·친목·사회 사건·NPC 인사·수첩·이어하기)
     동안 이름을 모르는 관측자의 완성 프롬프트(시트+지침+관측)에 남의 실명이 한 번도 없다 = 엔진이 쓴 문장의 누출 0
  ①' 정상 공개는 말 속에만 — "나는 카야야"(캐릭터 말) · "어서 와, 카야"(NPC 고정 대사)의 실명은 '들은 말' 따옴표 본문 줄에만 · 호칭·사람 줄·
     결과·기억 문장엔 person_note 로 적기 전까지 없다 · 적은 뒤엔 호칭이 그 이름이 된다
  ② 파티 결성 뒤 people 에 새 이름이 없다 · 관계 뼈 party 는 있다
  ③ 같은 사건이 관측자마다 다른 호칭으로 그려진다 · 기억·down_by·목격·statics·last·trail 에 사람 실명 문자열이 새로 저장되지 않는다
  ④ NPC 두뇌 입력: 모험가 실명이 있고 '봇N'·'bN'·'모험가 N'·char 번호가 없다 · 들은 말 속 ID 낱말이 이름으로 바뀐다 · NPC 가 앞서 한 말(prev,
     되받기)에 남은 손잡이도 이름으로(p059b 리뷰) · 쓰러진 사람도 이름
  ⑤ 인물 기록 판의 NPC 인사가 실명으로 부른다(NPC 는 길드 등록으로 이름을 안다)
  ⑥ 남의 NPC 이름을 들어도 미리 쓴 로어북이 안 뜬다(거둠) · 내 기록은 뜬다
  ⑦ 판 2 스냅샷 이관: 한 명과 맞는 by → by_id · 맞는 사람 없음·동명이인 → by_unknown(렌더 '누군가', 실명 0) · 몹·함정의 by 그대로 ·
     party 항목 유지 · 이어하기 왕복(파일로 쓰고 되읽기)
  ⑧ 인물 기록이 꺼진 판은 옛 꼴(실명 호칭·'동료가 한 말'·묘 실명·결과 사본의 실명 칸) — 바이트 불변은 기준선(tools/baseline.py dungeon·classic)이 맡는다
  ⑨ NPC 정의 name 유일(내부 열쇠 'npc:<정의 name>' — 고치려면 이관 함수가 필요하다)
  ⑩ 호칭 함수 직접(p059b 리뷰): identity.call 우선순위 = 내 기록 > 살펴 안 것(inspected — MP1 사람 search 의 연결 자리, 지금은 비어 있다) >
     옛 판 명단 > 낯선 사람 · people_names 도 같은 순서 · inspected 이름은 호칭만이고 '네 기록' 줄은 안 만든다
  A  아는 사람 기억 자동 활성화(DECISIONS 2026-10-13 — 로어북처럼): 계기는 둘 — **보일 때**(사람 줄 바로 아래 '  · 네 기록: 이름 — 「…」') ·
     **들은 말에 그 이름이 나올 때**(시야 밖이면 '## 떠오른 기억', 설계 R6 — p059b 관리자 결정으로 유지) · 아무 계기 없으면(안 보이고 이름도 안 들리면)
     안 뜬다 · 남의 기록이 안 섞인다 · 모르는 사람엔 없다 · 같은 사람은 한 관측에 한 번 · 여러 명이면 전부 · NPC·방위 줄 판(scan)·시트 씨앗도 ·
     길이 = person_note 원문 상한
(기존 게이트는 별도 실행 — _run_gates.sh.)
"""
import copy
import io
import json
import os
import pickle
import random
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = tempfile.mkdtemp(prefix="wl_identity_")
STATE = os.path.join(ROOT, "state")
os.makedirs(STATE, exist_ok=True)
for k in [k for k in os.environ if k.startswith("DUNGEON_")]:
    del os.environ[k]
os.environ.update(DUNGEON_GM="0", DUNGEON_STEP_DELAY="0", DUNGEON_STATE_DIR=STATE, DUNGEON_RUNS_DIR=os.path.join(ROOT, "runs"),
                  DUNGEON_BRAIN_BACKEND="dummy", DUNGEON_ACTION_MODE="compose", DUNGEON_PARTYFORM="1", DUNGEON_STRANGERS="1",
                  DUNGEON_TOWN="1", DUNGEON_BESTIARY_FILE="", DUNGEON_PARTY_FILE=os.path.join(HERE, "party.json"))

import brains                                        # noqa: E402
brains._call_claude = lambda prompt, model="haiku": ""   # LLM 무력화(결정론) — 아래 스텁이 프롬프트만 가로챈다
import dungeon_gm as G                               # noqa: E402
import identity as ID                                # noqa: E402
import info_guard as IG                              # noqa: E402
import sheetkit                                      # noqa: E402
import show_runner                                   # noqa: E402
import snapshot                                      # noqa: E402


class C:
    failed = 0
    calls = 0


def check(name, ok, detail=""):
    print("  %s %s%s" % ("OK  " if ok else "FAIL", name, (" — " + str(detail)[:300]) if (detail and not ok) else ""))
    if not ok:
        C.failed += 1


SHEETS = show_runner.load_party(os.path.join(HERE, "party.json"))
REAL = {c: SHEETS[c]["name"] for c in SHEETS}       # 1 두란 · 2 카야 · 3 피른
JOBS = {c: SHEETS[c]["job"] for c in SHEETS}
ROWS = ["##############",
        "#............#",
        "#............#",
        "#............#",
        "#............#",
        "#...........>#",
        "##############"]
FLAGS = ("graves", "events", "relations", "trail_on", "give_verb", "bond_verb", "composed_actions", "auto_approach",
         "ally_doing", "motion", "status", "floor_on", "hail", "wait_verb")


def look(c):
    sh = dict(SHEETS[c])
    sh["look"] = sheetkit.random_look(random.Random("look:7:%s" % c), sh["sex"])
    return sh


def floor(people=True, scan=True, spots=((3, 2), (4, 2), (5, 2))):
    """던전 한 방(손그림) — 사람 셋이 나란히. scan=True 면 방위 줄 판(D19), False 면 '지금 보이는 것' 판."""
    d, _ = G.Dungeon.from_ascii(ROWS, seed=7, depth=1, scan=scan)
    for k in FLAGS:
        setattr(d, k, True)
    d.turn = 5
    bs = []
    for c, xy in zip(("1", "2", "3"), spots):
        b = G.spawn(d, c, bs, sheet=look(c))
        b["x"], b["y"] = xy
        if people:
            b["people"] = {}
        bs.append(b)
    for b in bs:
        d.view(b, bs)                                # 조합형 참조표(_target_refs)를 건다 — act 전에 한 번 본다
    return d, bs


def town(people=True):
    d, _ = show_runner.build_town(apart=True)
    d.composed_actions = d.auto_approach = True
    d.parties = G.new_parties()
    bs = []
    for c in sorted(SHEETS):
        b = G.spawn(d, c, bs, sheet=look(c))
        if people:
            b["people"] = {}
        bs.append(b)
    d.turn = 5
    return d, bs


def zone_cells(d, zid):
    return [(x, y) for y in range(d.h) for x in range(d.w)
            if d._zone_id(x, y) == zid and d.grid[y][x] == G.FLOOR and not d.feature_at(x, y)]


def prompt(d, bots, b, msgs=(), reply=None):
    """그 캐릭터가 실제로 받는 글 전체(시트+지침+관측) — _call_claude 를 가로채 본다(실 콜 0)."""
    seen = {}

    def stub(p, model="haiku"):
        seen["p"] = p
        return json.dumps(reply or {"type": "wait"}, ensure_ascii=False)
    old_call, old_env = brains._call_claude, os.environ.get("DUNGEON_BRAIN_BACKEND")
    brains._call_claude, os.environ["DUNGEON_BRAIN_BACKEND"] = stub, "claude_cli"   # 스텁이 백엔드보다 우선 — 실 콜 없음
    try:
        o = d.view(b, bots)
        o["messages"] = [dict(m) for m in msgs]
        book = G.SR.book(d)                          # think_all 과 같은 자리 — 받은 사회 사건(반응 기회, 꺼내면 비워진다)
        offered = book.offer(b["char"]) if book is not None else []
        if offered:
            o["social_events"] = offered
        dec = brains.claude_brain(o, b["char"], b, bots)
    finally:
        brains._call_claude = old_call
        os.environ["DUNGEON_BRAIN_BACKEND"] = old_env or "dummy"
    return seen.get("p", ""), dec, o


def strangers_named(p, viewer, known=()):
    """프롬프트에 나온 남의 실명 — 보는 사람 자신과 이미 아는 사람(known chars)은 뺀다."""
    return [REAL[c] for c in REAL if c != viewer["char"] and c not in known and REAL[c] in p]


def lines_with(p, word):
    return [ln for ln in p.splitlines() if word in ln]


def stored_strings(b):
    """몸에 저장된 기억·목격·쓰러진 사연·장부 statics·직전 결과·궤적 — 사람 실명이 새로 들어가면 안 되는 자리(③)."""
    keep = {k: b.get(k) for k in ("memories", "witnessed", "down_by", "last", "trail")}
    keep["statics"] = ((b.get("ledger") or {}).get("statics") or {})
    return json.dumps(keep, ensure_ascii=False, default=str)


# ── ① 시스템 누출 0 ─────────────────────────────────────────────────────
print("── ① 시스템 누출 0 — 말에 실명이 없는 각본에서 모르는 사람의 실명이 프롬프트에 한 번도 없다")
d, bots = floor()
b1, b2, b3 = bots
d.d20 = lambda: 20                                   # 판정 고정(명중) — 각본이 사건을 확실히 만든다
r_hit = d.act(b2, {"type": "attack", "target": "b1"}, bots)          # 사람이 사람을 친다(피격·목격)
b3["hp"] = 1
d.view(b2, bots)
r_kill = d.act(b2, {"type": "attack", "target": "b3"}, bots)         # 쓰러뜨린다(묘·목격·기억·쓰러진 사연)
p2, _, _ = prompt(d, bots, b2)                                       # 친 사람의 다음 판단(처치 결과가 궤적에 있을 때)
d._swap_displaced(b1, b2, bots)                                      # 교대(with)
b2["potions"] = 1
d.view(b2, bots)
r_give = d.act(b2, {"type": "give", "target": "b1", "item": "i1"}, bots)      # 건넴(받은 일)
d.view(b2, bots)
r_bond = d.act(b2, {"type": "bond", "target": "b1", "form": "어깨를 두드린다"}, bots)   # 친목(받은 일·사회 사건)
check("① 각본이 사건을 만들었다: 명중 · 쓰러뜨림(묘) · 건넴 · 친목",
      r_hit.get("hit") and r_kill.get("killed") and r_kill.get("grave") and r_give.get("result") == "given" and r_bond.get("result") == "done",
      [r_hit.get("result"), r_kill.get("result"), r_give.get("result"), r_bond.get("result")])
check("① 관전 원본(행동 결과 dict)은 실명 그대로 — 스트림·관전자는 다 안다",
      r_kill.get("target") == REAL["3"] and r_kill["grave"]["name"] == "%s의 묘" % REAL["3"])
p1, _, o1 = prompt(d, bots, b1)
check("① 피해자(두란)의 프롬프트: 남의 실명 0 — 피격·교대·건넴·친목·목격·기억·묘 전부 '낯선 사람'/'누군가'",
      not strangers_named(p1, b1) and len(p1) > 2000, strangers_named(p1, b1))
check("①  그 글의 실제 문장: 피격 '[피격] 낯선 사람(b2) −' · 교대 '[자리 교대] 낯선 사람' · 목격 '낯선 사람(봇3)가 낯선 사람에게 쓰러져 죽는 것을' · 묘 '누군가의 묘'",
      "[피격] 낯선 사람(b2) −" in p1 and "[자리 교대] 낯선 사람" in p1 and "낯선 사람(봇3)가 낯선 사람에게 쓰러져 죽는 것을" in p1
      and "누군가의 묘 f" in p1 and "[낯선 사람(봇3)의 죽음을 목격] 낯선 사람에게 죽었다" in p1, [ln for ln in p1.splitlines() if "낯선" in ln][:12])
check("① 친 사람(카야)의 프롬프트: 남의 실명 0 — 처치 '[처치] 낯선 사람(b3)' · 자기가 쓰러뜨린 죽음의 기억은 자기 이름(자기 일은 안다)",
      not strangers_named(p2, b2) and "[처치] 낯선 사람(b3)" in p2 and "[낯선 사람(봇3)의 죽음을 목격] 카야에게 죽었다" in p2,
      strangers_named(p2, b2) or [ln for ln in p2.splitlines() if "낯선" in ln][:8])
brains.NOTEBOOK_ON = True
b1.setdefault("dialogue", []).append({"from": "2", "text": "괜찮아?", "turn": 5, "to": "1", "to_me": True})
seen_nb = {}
_cc = brains._call_claude
brains._call_claude = lambda p, model="haiku": (seen_nb.__setitem__("p", p), '{"page": "x"}')[1]
os.environ["DUNGEON_BRAIN_BACKEND"] = "claude_cli"
try:
    brains.notebook_page(b1, {"depth": 1, "t0": 1, "t1": 5, "n": {}}, None, bots)
    brains.stop_page(b1, {"depth": 1, "t0": 1, "t1": 5, "n": {}}, None, bots)
finally:
    brains._call_claude = _cc
    os.environ["DUNGEON_BRAIN_BACKEND"] = "dummy"
check("① 수첩 재료(층을 떠날 때·멈출 때)도 남의 실명 0 · 모르는 사람은 '봇N'이 아니라 '낯선 사람(봇2)'",
      bool(seen_nb.get("p")) and not strangers_named(seen_nb["p"], b1) and "낯선 사람(봇2)→나" in seen_nb["p"], seen_nb.get("p", "")[-400:])
del d.d20                                            # 각본용 고정 판정을 걷는다(피클은 함수 객체를 못 싣는다 — 클래스의 d20 으로 돌아간다)
snapshot.write(STATE, {"d": d, "bots": bots, "sheets": SHEETS, "next_turn": 6, "stream_pos": 0, "seed": 7, "started": "x", "run_id": "r1"},
               {"run_id": "r1"})
snap_r, _m = snapshot.load(snapshot.paths(STATE)[0])
pr, _, _ = prompt(snap_r["d"], snap_r["bots"], snap_r["bots"][0])
check("① 이어하기(스냅샷 쓰고 되읽기) 뒤에도 남의 실명 0 · 판 %d" % snapshot.STATE_VERSION,
      snap_r["state_version"] == snapshot.STATE_VERSION and not strangers_named(pr, snap_r["bots"][0]) and "누군가의 묘" in pr, strangers_named(pr, snap_r["bots"][0]))

# 마을 — 사회 사건 · NPC 인사(실명은 NPC 대사 안에만)
dt, tb = town()
dt.give_verb = dt.bond_verb = True
t1, t2, t3 = tb
g = zone_cells(dt, "guild_district")
m = len(g) // 2
t1["x"], t1["y"] = g[m]
t2["x"], t2["y"] = next(c for c in g if c != g[m] and max(abs(c[0] - g[m][0]), abs(c[1] - g[m][1])) == 1)
t3["x"], t3["y"] = next(c for c in g if c not in (g[m], (t2["x"], t2["y"])) and max(abs(c[0] - g[m][0]), abs(c[1] - g[m][1])) == 2)
t2["potions"] = 1
for b in tb:
    dt.view(b, tb)
r_tg = dt.act(t2, {"type": "give", "target": "b1", "item": "i1"}, tb)
pt1, _, ot1 = prompt(dt, tb, t1)
check("① 마을(파티 결성·인물 기록 판): 건넴(받은 일)·사회 사건이 '낯선 사람' — 남의 실명 0",
      r_tg.get("result") == "given" and not strangers_named(pt1, t1) and bool(ot1.get("social_events")) and "낯선 사람(봇2)에게서" in pt1,
      (r_tg.get("result"), strangers_named(pt1, t1), ot1.get("social_events")))

# ── ①' 정상 공개는 말 속에만 ─────────────────────────────────────────────
print("── ①' 정상 공개 — 실명은 들은 말의 따옴표 본문에만, 적은 뒤에야 호칭이 된다")
hi = [{"from": "2", "text": "나는 카야야. 아까는 미안.", "turn": 5, "to": "1", "to_me": True}]
p1b, dec1b, _ = prompt(d, bots, b1, hi, {"type": "wait", "person_note": {"target": "b2", "name": "카야", "text": "나를 쳤다. 자기를 카야라 했다"}})
check("①' 들은 말 속 '카야'만 — 그 줄 밖(호칭·사람 줄·결과·기억)엔 없다",
      lines_with(p1b, REAL["2"]) == ['- 낯선 사람(봇2): "나는 카야야. 아까는 미안." (너에게)'], lines_with(p1b, REAL["2"]))
check("①' 들은 에이전트가 정리한다(엔진은 판정하지 않는다): person_note → {to:'2', name:'카야'}", dec1b.get("person_note", {}).get("name") == "카야", dec1b.get("person_note"))
b1["people"]["b2"] = {"name": "카야", "text": "나를 쳤다. 자기를 카야라 했다", "turn": 5, "src": "self"}
d.d20 = lambda: 20
d.view(b2, bots)
d.act(b2, {"type": "attack", "target": "b1"}, bots)
del d.d20
p1c, _, _ = prompt(d, bots, b1)
check("①' 적은 뒤엔 호칭이 그 이름: 피격 '[피격] 카야(b2)' · 사람 줄 '카야(봇2)' · 명단 '카야(봇2), 도적'",
      "[피격] 카야(b2)" in p1c and "카야(봇2) [b2]" in p1c and "- 카야(봇2), 도적" in p1c and "낯선 사람(봇2)" not in p1c)
nm_names = ["%s의 묘" % REAL["3"]]
check("①' 이름을 모르는 피른의 묘는 여전히 '누군가의 묘'", "누군가의 묘" in p1c and not any(x in p1c for x in nm_names))
rc = next(f for f in dt.features.values() if f.type == "npc" and f.name == "길드 접수원")
p_npc, _, _ = prompt(dt, tb, t1, [{"from": "npc:길드 접수원", "text": "어서 와, 카야. 물약 챙겼어?", "turn": 6, "to": "2"}])
check("①' NPC 대사 속 실명(NPC 는 이름을 안다)도 들은 말 줄에만 — 누출이 아니다(DECISIONS 69)",
      lines_with(p_npc, REAL["2"]) == ['- 길드 접수원: "어서 와, 카야. 물약 챙겼어?" (낯선 사람(봇2)에게)'], lines_with(p_npc, REAL["2"]))

# ── ② 파티 결성 ─────────────────────────────────────────────────────────
print("── ② 파티 결성은 소개가 아니다")
dp, pb = town()
c1, c2, c3 = pb
for b, xy in zip(pb, (g[m], g[m + 1], g[m + 2])):
    b["x"], b["y"] = xy
dp.relations = True
dp._party_form(c1, "b2", pb)
rf = dp._party_form(c2, "b1", pb)
check("② 맺어진다 · 두 몸의 people 에 새 이름 없음 · 관계 뼈 party ×1",
      rf["result"] == "party_formed" and c1["people"] == {} and c2["people"] == {}
      and c1["relations"]["2"]["bones"]["party"]["n"] == 1 and c2["relations"]["1"]["bones"]["party"]["n"] == 1)
pp2, _, _ = prompt(dp, pb, c2)
check("② 맺은 뒤 명단은 '낯선 사람(봇1), 전사' — 실명 0", "- 낯선 사람(봇1), 전사" in pp2 and not strangers_named(pp2, c2))

# ── ③ 관측자마다 다른 호칭 · 저장에 실명 없음 ────────────────────────────
print("── ③ 같은 사건, 다른 호칭 · 저장본에 실명 없음")
d3, b3s = floor()
x1, x2, x3 = b3s
d3.d20 = lambda: 20
x1["people"]["b2"] = {"name": "칼잡이", "text": "도적 같다", "turn": 4, "src": "self"}
d3.act(x2, {"type": "attack", "target": "b3"}, b3s)                  # 2 가 3 을 친다 — 1 은 목격자, 3 은 피해자
q1, _, _ = prompt(d3, b3s, x1)
q3, _, _ = prompt(d3, b3s, x3)
check("③ 같은 공격자를 1 은 '칼잡이'(내 기록), 3 은 '낯선 사람'으로 부른다",
      "낯선 사람(봇3)가 칼잡이에게 맞는 것을" in q1 and "[피격] 낯선 사람(b2)" in q3 and "칼잡이" not in q3)
x3["hp"] = 1
d3.view(x2, b3s)
d3.act(x2, {"type": "attack", "target": "b3"}, b3s)
bad3 = {b["char"]: [REAL[c] for c in REAL if REAL[c] in stored_strings(b)] for b in b3s}
check("③ 기억·목격·down_by·statics·last·trail 에 사람 실명 문자열 0(인물 기록 판의 몸 셋 — 열쇠만)",
      not any(bad3.values()) and (x1.get("memories") or [{}])[-1].get("by_id") == "b2" and x3["down_by"].get("by_id") == "b2"
      and "by" not in x3["down_by"], (bad3, x3.get("down_by")))
check("③ 저장용 정제(IG.public ⑤)는 열쇠를 남기고 실명 칸만 걷는다 — 옛 판 몸에는 손대지 않는다",
      IG.public({"type": "hurt", "by": "카야", "by_id": "b2", "by_kind": "bot"}, x1) == {"type": "hurt", "by_id": "b2", "by_kind": "bot"}
      and IG.public({"type": "hurt", "by": "카야", "by_id": "b2", "by_kind": "bot"}, {"char": "9"})["by"] == "카야"
      and IG.public({"type": "hurt", "by": "고블린", "by_id": "m1"}, x1)["by"] == "고블린")

# ── ④ NPC 두뇌 입력 ─────────────────────────────────────────────────────
print("── ④ NPC 두뇌 입력 — 이름은 실명, ID·봇 라벨은 없다")
seen4 = {}
_cc = brains._call_claude
brains._call_claude = lambda p, model="haiku": (seen4.__setitem__("p", p), '{"line": "그래."}')[1]
os.environ["DUNGEON_BRAIN_BACKEND"] = "claude_cli"
try:
    facts4 = show_runner.npc_facts(dt, "길드 접수원", tb, ["3"], None, 0, REAL)
    brains.npc_reply(t1, {"result": "npc_talk", "npc": "길드 접수원", "line": "어서 와요."}, "봇2랑 b3한테 물어봐. 나 말고.", facts4,
                     npc={"name": "길드 접수원"}, names=REAL)
finally:
    brains._call_claude = _cc
    os.environ["DUNGEON_BRAIN_BACKEND"] = "dummy"
p4 = seen4.get("p", "")
check("④ 화자 = 실명(직업) · 들은 말의 '봇2'·'b3' → '카야'·'피른' · '봇N'·'bN'·'모험가 N'·처음 보는 모험가 없음",
      ("%s(%s)이(가) 네게 말을 걸었다" % (REAL["1"], JOBS["1"])) in p4 and '"카야랑 피른한테 물어봐. 나 말고."' in p4
      and not re.search(r"봇\s*\d|(?<![0-9A-Za-z])b\d+(?![0-9A-Za-z])|모험가 \d|처음 보는 모험가", p4), p4[-500:])
check("④ NPC 가 아는 사실: 마을의 모험가 실명(인물 기록 판에서도) · 쓰러진 사람은 번호가 아니라 이름",
      any(REAL["2"] in f and "마을의 모험가" in f for f in facts4) and "이번 원정에서 쓰러진 사람: %s" % REAL["3"] in facts4
      and not any("통성명" in f for f in facts4), facts4)
check("④ 손잡이 바꾸기는 NPC 입력에만 — 명단에 없는 번호는 그대로 · 낱말 일부(ab12·b2c)는 안 건드린다",
      ID.npc_heard("봇9·b2c·ab12·b2!", REAL) == "봇9·b2c·ab12·카야!")
seen4b = {}
brains._call_claude = lambda p, model="haiku": (seen4b.__setitem__("p", p), '{"line": "응."}')[1]
os.environ["DUNGEON_BRAIN_BACKEND"] = "claude_cli"
try:                                                 # 되받기(npc_say) — NPC 가 앞서 이 사람에게 한 말(prev)에 손잡이가 남아 있던 경우(c05 t84 처럼 따라 말함)
    brains.npc_reply(t1, {"result": "npc_say", "npc": "길드 접수원", "prev": "b2랑 봇 3 얘기는 들었어요."}, "그래서 어떻게 됐어요?", facts4,
                     npc={"name": "길드 접수원"}, names=REAL)
finally:
    brains._call_claude = _cc
    os.environ["DUNGEON_BRAIN_BACKEND"] = "dummy"
p4b = seen4b.get("p", "")
check("④ NPC 가 앞서 한 말(prev)의 'b2'·'봇 3'도 이름으로 — '조금 전 네가 이 사람에게 한 말: \"카야랑 피른 얘기는 들었어요.\"' · 손잡이 0",
      '- 조금 전 네가 이 사람에게 한 말: "카야랑 피른 얘기는 들었어요."' in p4b
      and not re.search(r"봇\s*\d|(?<![0-9A-Za-z])b\d+(?![0-9A-Za-z])", p4b), p4b[-400:])

# ── ⑤ NPC 인사 ─────────────────────────────────────────────────────────
print("── ⑤ NPC 인사 — 인물 기록 판도 실명으로 부른다")
t3["npc_hailed"] = set()
t3["x"], t3["y"] = next((x, y) for x, y in g if max(abs(x - rc.x), abs(y - rc.y)) == 2)
hails = [h for h in dt.npc_greetings(tb) if h[1] == "3"]
check("⑤ 인사 문장에 '%s'(모험가 대신)" % REAL["3"], hails and all(REAL["3"] in h[2] for h in hails), [h[2][:40] for h in hails])

# ── ⑥ 로어북 거둠 ─────────────────────────────────────────────────────
print("── ⑥ 미리 쓴 NPC 로어북은 거뒀다 · 내 기록만 떠오른다")
say6 = [{"from": "2", "text": "길드 접수원이 물약을 준대.", "turn": 5, "to": "1", "to_me": True}]
d6, b6 = floor()
p6, _, _ = prompt(d6, b6, b6[0], say6)
check("⑥ 던전에서 'NPC 이름'을 들어도(내 기록 없음) 아무것도 안 뜬다", "## 떠오른 기억" not in p6 and "원정 물품" not in p6)
b6[0]["people"]["npc:길드 접수원"] = {"name": "길드 접수원", "text": "물약을 하나 준다", "turn": 4, "src": "self"}
p6b, _, _ = prompt(d6, b6, b6[0], say6)
check("⑥ 내 기록은 뜬다 — '- 길드 접수원: 「물약을 하나 준다」'", "## 떠오른 기억" in p6b and "- 길드 접수원: 「물약을 하나 준다」" in p6b)

# ── ⑦ 판 2 → 3 이관 ───────────────────────────────────────────────────
print("── ⑦ 판 2 스냅샷 이관(_m2_refs)")
sheets7 = {"1": {"name": "두란", "job": "전사"}, "2": {"name": "카야", "job": "도적"}, "3": {"name": "피른", "job": "궁수"},
           "4": {"name": "피른", "job": "궁수"}}          # 동명이인(피른 둘)
body7 = {"char": "1", "name": "두란", "job": "전사", "people": {"b2": {"name": "카야", "text": "도적", "turn": 3, "src": "party"}},
         "memories": [{"kind": "fallen", "char": "3", "by": "카야", "by_kind": "bot", "zone": "방", "turn": 3},
                      {"kind": "fallen", "char": "2", "by": "피른", "by_kind": "bot", "zone": "방", "turn": 4},
                      {"kind": "fallen", "char": "4", "by": "모르는이", "by_kind": "bot", "zone": "방", "turn": 4},
                      {"kind": "fallen", "char": "4", "by": "고블린", "zone": "방", "turn": 4},
                      {"kind": "fallen", "char": "4", "by": "가시 함정", "by_kind": "trap", "zone": "방", "turn": 4}],
         "witnessed": [{"kind": "ally_hurt", "char": "3", "by": "카야", "by_kind": "bot", "dmg": 2}],
         "down_by": {"by": "카야", "by_kind": "bot", "turn": 3, "depth": 1}}
raw7 = {"version": 2, "state_version": 2, "sheets": sheets7, "bots": [body7], "worlds": [], "waiting": {}, "d": None}
up7 = snapshot.upgrade(copy.deepcopy(raw7))
mem7 = up7["bots"][0]["memories"]
check("⑦ 한 명과 맞는 by → by_id(b2) · 동명이인(피른 둘)·없는 이름 → by_unknown · 원문 by 는 남긴다",
      mem7[0].get("by_id") == "b2" and mem7[0]["by"] == "카야" and mem7[1].get("by_unknown") is True and "by_id" not in mem7[1]
      and mem7[2].get("by_unknown") is True, mem7[:3])
check("⑦ 몹·함정의 by 는 그대로(by_id·by_unknown 없음) · 목격·down_by 도 잇는다 · party 항목 유지 · 지금 판(p0.5.10부터 판 번호를 박지 않는다)",
      mem7[3] == raw7["bots"][0]["memories"][3] and mem7[4] == raw7["bots"][0]["memories"][4]
      and up7["bots"][0]["witnessed"][0].get("by_id") == "b2" and up7["bots"][0]["down_by"].get("by_id") == "b2"
      and up7["bots"][0]["people"]["b2"]["src"] == "party" and up7["state_version"] == snapshot.STATE_VERSION >= 3)
check("⑦ 이관은 제자리·한 번(다시 올려도 같다)", snapshot.upgrade(copy.deepcopy(up7)) == up7)
d7, b7 = floor(scan=False)
b7[0]["memories"] = copy.deepcopy(mem7[:3])
b7[0]["people"] = {}
p7, _, _ = prompt(d7, b7, b7[0])
mem_lines = [ln for ln in p7.splitlines() if ln.startswith("- [") and "의 죽음을 목격]" in ln]
check("⑦ 렌더: 잇지 못한 옛 기억(동명이인·없는 이름)은 '누군가에게' — 원문 실명(피른·모르는이)이 새지 않는다 · 이은 기억은 보는 사람 호칭(낯선 사람)",
      len(mem_lines) == 3 and "모르는이" not in p7 and "피른에게" not in p7 and sum("누군가에게 죽었다" in ln for ln in mem_lines) == 2
      and sum("낯선 사람에게 죽었다" in ln for ln in mem_lines) == 1, mem_lines)
S7 = os.path.join(ROOT, "s7")
os.makedirs(S7)
with open(os.path.join(S7, "snapshot.pkl"), "wb") as f:
    pickle.dump({**raw7, "next_turn": 4, "stream_pos": 0, "seed": 7, "started": "x", "run_id": "r7"}, f, protocol=pickle.HIGHEST_PROTOCOL)
with io.open(os.path.join(S7, "snapshot.json"), "w", encoding="utf-8") as f:
    json.dump({"version": 2, "state_version": 2, "run_id": "r7"}, f, ensure_ascii=False)
s7, _m7 = snapshot.load(os.path.join(S7, "snapshot.pkl"))
snapshot.write(S7, {k: v for k, v in s7.items() if k not in ("version", "state_version")}, {"run_id": "r7"})
s7b, _m7b = snapshot.load(os.path.join(S7, "snapshot.pkl"))
check("⑦ 이어하기 왕복: 판 2 파일 → 로더가 지금 판으로 → 다시 써서 되읽어도 같다 · 요약도 지금 판",
      s7["state_version"] == s7b["state_version"] == snapshot.STATE_VERSION and s7b["bots"] == s7["bots"]
      and (snapshot.read_meta(S7) or {}).get("state_version") == snapshot.STATE_VERSION)

# ── ⑧ 인물 기록이 꺼진 판 ──────────────────────────────────────────────
print("── ⑧ 인물 기록이 꺼진 판은 옛 꼴")
d8, b8 = floor(people=False)
d8.d20 = lambda: 20
d8.act(b8[1], {"type": "attack", "target": "b1"}, b8)
b8[2]["hp"] = 1
d8.view(b8[1], b8)
d8.act(b8[1], {"type": "attack", "target": "b3"}, b8)
p8, _, o8 = prompt(d8, b8, b8[0], [{"from": "2", "text": "가자", "turn": 5, "to": "1", "to_me": True}])
check("⑧ 실명 호칭 그대로('[피격] 카야(b2)' · '피른의 묘' · '## 동료가 한 말') · people 없음 · 결과 사본의 실명 칸 그대로(옛 저장 꼴)",
      "[피격] 카야(b2)" in p8 and "피른의 묘" in p8 and "## 동료가 한 말" in p8 and "people" not in o8
      and b8[0]["memories"][-1].get("by") == "카야" and "PEOPLE:" not in p8)

# ── ⑨ NPC 정의 name 유일 ──────────────────────────────────────────────
print("── ⑨ NPC 정의 name 유일")
npc_names = [x.get("name") for x in G.ENT.by_kind("npc")]
check("⑨ NPC 정의 name 이 서로 다르다(내부 열쇠 'npc:<정의 name>' — 바꾸려면 이관 함수가 필요하다) · %d명" % len(npc_names),
      len(npc_names) >= 10 and len(set(npc_names)) == len(npc_names), npc_names)

# ── ⑩ 호칭 함수 직접 ──────────────────────────────────────────────────
print("── ⑩ identity.call — 내 기록 > 살펴 안 것(inspected, MP1 연결 자리) > 옛 판 명단 > 낯선 사람")
v10 = {"char": "1", "name": REAL["1"], "people": {"b2": {"name": "칼잡이", "text": "", "turn": 1, "src": "self"}},
       "inspected": {"b2": {"name": REAL["2"]}, "b3": {"name": REAL["3"]}}}
old10 = {"char": "1", "name": REAL["1"]}                 # 인물 기록이 꺼진 판(people 칸 없음)
check("⑩ 내 기록(칼잡이)이 살펴 안 이름(카야)보다 앞 · 기록 없으면 살펴 안 이름(피른) · 둘 다 없으면 낯선 사람 · 'b2'·'2' 같은 사람 · 자기 = '너'",
      ID.call(v10, "b2") == "칼잡이" and ID.call(v10, "2") == "칼잡이" and ID.call(v10, "b3") == REAL["3"]
      and ID.call(v10, "b9") == ID.STRANGER and ID.call(v10, "b1") == ID.SELF)
check("⑩ 옛 판(인물 기록 꺼짐)은 명단 실명 → 자리 기본값 · inspected 를 보지 않는다 · NPC 는 정의 이름(ID-6 전)",
      ID.call(old10, "b2", REAL) == REAL["2"] and ID.call(old10, "b9", REAL, default="동료") == "동료"
      and ID.call({**old10, "inspected": {"b9": {"name": "x"}}}, "b9", REAL) == ID.STRANGER and ID.call(v10, "npc:대장장이") == "대장장이")
check("⑩ 호칭 사전(people_names)도 같은 순서 — {'2': 칼잡이, '3': 피른} · inspected 가 비면(지금 게임) 옛 사전 그대로",
      ID.people_names(v10) == {"2": "칼잡이", "3": REAL["3"]} and ID.people_names({"people": {"b2": {"name": "칼잡이"}}}) == {"2": "칼잡이"})
d10i, b10i = floor(scan=False)
b10i[0]["inspected"] = {"b3": {"name": REAL["3"]}}       # MP1 이 채울 자리를 손으로 — 호칭은 타고, 내 기록 줄은 안 생긴다
p10i, _, _ = prompt(d10i, b10i, b10i[0])
check("⑩ 렌더: 살펴 안 이름은 호칭(피른(봇3))만 — '네 기록' 줄은 없다(내 기록이 아니다)",
      "- %s(봇3) [b3]" % REAL["3"] in p10i and "네 기록" not in p10i and "낯선 사람(봇2) [b2]" in p10i)

# ── A 아는 사람 기억 자동 활성화 ───────────────────────────────────────
print("── A 아는 사람 기억 자동 활성화(로어북처럼 — 계기 = 보일 때 · 이름이 들릴 때 · 내 기록만)")
dA, bA = floor(scan=False, spots=((3, 2), (4, 2), (5, 2)))
a1, a2, a3 = bA
a1["people"] = {"b2": {"name": "칼잡이", "text": "도적 같다. 말수가 적다", "turn": 4, "src": "self"},
                "b3": {"name": "활잡이", "text": "", "turn": 4, "src": "self"}}
a2["people"] = {"b3": {"name": "새벽", "text": "다른 사람이 쓴 기록 — 섞이면 안 된다", "turn": 4, "src": "self"}}
pA, _, _ = prompt(dA, bA, a1)
LA = pA.splitlines()
i2 = next(i for i, ln in enumerate(LA) if ln.startswith("- 칼잡이(봇2) [b2]"))
i3 = next(i for i, ln in enumerate(LA) if ln.startswith("- 활잡이(봇3) [b3]"))
check("A 보일 때 뜬다: 그 사람 줄 바로 아래 '  · 네 기록: 칼잡이 — 「…」' · 사람 줄은 아는 사람도 겉모습 꼴",
      LA[i2 + 1] == "  · 네 기록: 칼잡이 — 「도적 같다. 말수가 적다」" and "겉모습:" in LA[i2], LA[i2:i2 + 2])
check("A 여러 명이 보이면 전부 · 이름만 적은 사람은 '(이름만 적어 두었다)'", LA[i3 + 1] == "  · 네 기록: 활잡이 (이름만 적어 두었다)", LA[i3:i3 + 2])
check("A 남의 기록이 섞이지 않는다 — 카야(2)가 피른에 대해 쓴 '새벽'은 두란(1)의 글에 없다",
      "새벽" not in pA and "다른 사람이 쓴 기록" not in pA)
pA2, _, _ = prompt(dA, bA, a2)
check("A 각자의 것 — 카야(2)의 글엔 자기 기록(새벽)만 · 두란(1)이 쓴 '칼잡이'·'활잡이'는 없다 · 두란은 모르는 사람(기록 없음)이라 네 기록 줄이 없다",
      "  · 네 기록: 새벽 — 「다른 사람이 쓴 기록 — 섞이면 안 된다」" in pA2 and "칼잡이" not in pA2 and "활잡이" not in pA2
      and sum(ln.startswith("  · 네 기록:") for ln in pA2.splitlines()) == 1)
pA3, _, _ = prompt(dA, bA, a3)
check("A 모르는 사람엔 아무것도 안 뜬다 — 기록이 없는 피른(3)의 글엔 '네 기록' 줄이 없다", "네 기록" not in pA3)
pA4, _, _ = prompt(dA, bA, a1, [{"from": "2", "text": "칼잡이라고 불러도 돼. 활잡이는 어디 갔지?", "turn": 5, "to": "1", "to_me": True}])
check("A 같은 사람 기록은 한 관측에 한 번 — 이름을 들어도(조건 c) 보이는 사람은 줄 아래 한 번뿐",
      pA4.count("네 기록: 칼잡이") == 1 and pA4.count("네 기록: 활잡이") == 1 and "## 떠오른 기억" not in pA4)
a3["x"], a3["y"] = 12, 5                             # 피른을 시야 밖(같은 방이라도 멀리)으로 — 아래에서 보이는지 확인한다
far = not any(b_.get("char") == "3" for b_ in dA.view(a1, bA)["sights"]["bots"])
if far:
    pA5, _, _ = prompt(dA, bA, a1)
    check("A 아무 계기 없으면 안 뜬다 — 시야 밖 활잡이(3)의 기록 줄은 없다(이름을 들은 말도 없다 · 명단의 호칭은 기록이 아니다)",
          "네 기록: 활잡이" not in pA5 and "## 떠오른 기억" not in pA5 and "네 기록: 칼잡이" in pA5)
    gone, gone_line = "활잡이", "- 활잡이: 「(이름만 적어 두었다)」"
else:
    a1["people"]["b9"] = {"name": "유령", "text": "어디에도 없는 사람", "turn": 4, "src": "self"}
    pA5, _, _ = prompt(dA, bA, a1)
    check("A 아무 계기 없으면 안 뜬다 — 이 층에 없는 사람(b9)의 기록은 없다(이름을 들은 말도 없다)", "유령" not in pA5 and "어디에도 없는" not in pA5)
    gone, gone_line = "유령", "- 유령: 「어디에도 없는 사람」"
pA5b, _, _ = prompt(dA, bA, a1, [{"from": "2", "text": "%s 못 봤어?" % gone, "turn": 5, "to": "1", "to_me": True}])
check("A 둘째 계기 — 시야 밖이어도 들은 말에 그 이름이 나오면 '## 떠오른 기억'에 한 번(설계 R6 유지 · p059b 관리자 결정) · 사람 줄 아래 꼴은 아니다",
      "## 떠오른 기억" in pA5b and pA5b.count(gone_line) == 1 and ("네 기록: %s" % gone) not in pA5b, [ln for ln in pA5b.splitlines() if gone in ln])
a1["people"]["b2"] = {"name": "가" * 40, "text": "나" * 300, "turn": 4, "src": "sheet"}
pA6, _, _ = prompt(dA, bA, a1)
check("A 길이 = person_note 원문 상한(이름 %d · 한 줄 %d) — 시트 씨앗이 길어도" % (brains.PERSON_NAME_LEN, brains.NOTE_LEN),
      "  · 네 기록: %s — 「%s」" % ("가" * brains.PERSON_NAME_LEN, "나" * brains.NOTE_LEN) in pA6)
dS, bS = floor(scan=True)
bS[0]["people"] = {"b2": {"name": "칼잡이", "text": "도적 같다", "turn": 4, "src": "self"}}
pS, _, _ = prompt(dS, bS, bS[0])
check("A 방위 줄 판(던전 scan)에도 — 방위 줄 아래 '  · 칼잡이(봇2) [b2] — 네 기록: 칼잡이 — 「도적 같다」' 한 번",
      pS.count("  · 칼잡이(봇2) [b2] — 네 기록: 칼잡이 — 「도적 같다」") == 1 and pS.count("네 기록") == 1)
dN, bN = town()
n1 = bN[0]
nf = next(f for f in dN.features.values() if f.type == "npc" and f.name == "주점 주인")
t_ = zone_cells(dN, "main_street")
n1["x"], n1["y"] = next((x, y) for x, y in t_ if max(abs(x - nf.x), abs(y - nf.y)) <= 2 and (x, y) != (nf.x, nf.y))
n1["people"]["npc:주점 주인"] = {"name": "수다쟁이 주인", "text": "소문을 숫자까지 안다", "turn": 4, "src": "self"}
pN, _, oN = prompt(dN, bN, n1)
fidN = next(f["id"] for f in oN["sights"]["features"] if f["type"] == "npc" and f["name"] == "주점 주인")
LN = pN.splitlines()
iN = next(i for i, ln in enumerate(LN) if ln.startswith("- 주점 주인 %s" % fidN))
check("A NPC 도 같은 규칙 — 그 줄 바로 아래 '  · 네 기록: 수다쟁이 주인 — 「…」'(내가 붙인 이름)",
      LN[iN + 1] == "  · 네 기록: 수다쟁이 주인 — 「소문을 숫자까지 안다」", LN[iN:iN + 2])
dR, bR = town()
for b in bR:
    b["people"] = {"b%s" % oc: {"name": SHEETS[oc]["name"], "text": str(t), "turn": 0, "src": "sheet"}
                   for oc, t in sorted((SHEETS[b["char"]].get("relationships") or {}).items()) if oc in SHEETS and oc != b["char"]}
gR = zone_cells(dR, "guild_district")
for b, xy in zip(bR, (gR[3], gR[4], gR[5])):
    b["x"], b["y"] = xy
pR, _, _ = prompt(dR, bR, bR[0])
check("A 시트 씨앗(판 전부터 아는 사이)도 보이면 뜬다 — 두란의 카야·피른 기록 각 한 줄",
      pR.count("  · 네 기록: %s — 「%s」" % (REAL["2"], SHEETS["1"]["relationships"]["2"])) == 1
      and pR.count("  · 네 기록: %s — 「" % REAL["3"]) == 1)

print("=" * 44)
print("ALL PASS — verify_identity (p0.5.9 신원 ID-1 이름 층: 시스템 누출 0 · 정상 공개는 말 속에만 · 파티 결성 ≠ 소개 · 열쇠로 저장 · NPC 는 이름을 안다 · "
      "로어북 거둠 · 판 2→3 이관 · 꺼진 판 옛 꼴 · 아는 사람 기억 자동 활성화, 실 LLM 0콜)"
      if not C.failed else "FAILED %d" % C.failed)
sys.exit(1 if C.failed else 0)

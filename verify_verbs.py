# -*- coding: utf-8 -*-
"""p0.5.28 동사를 데이터로(DECISIONS 10-18 동사 작업 순서 ① 구조 패치 — 동작 변화 0) — 헤들리스 검증. LLM 0콜.
게이트:
  ① 세트 읽기: entities/verb_set.json 의 동사 = CA.COMMON(순서) · VERBS = 동사 정의의 comps.verb(설명은 말 파일에서) · DISTANCE_ACTIONS·OPEN_END 는
     정의에서 지은 것 · 처리기 열쇠가 엔진에 있다 · 지금 세트 = v0.5.29 의 11개(v0.5.27 의 9개 + use 다음 buy·sell — 순서·처리기·칸)
  ② 잘못된 세트 거부: 없는 동사 · 처리기 없음 · 중복 · 엔진이 따로 읽는 이름을 한 번에 나열 · 꼴(목록 아님·빈 목록·없는 파일·JSON 아님) · 거절돼도 쓰던 세트 그대로
  ③ 동사 정의 검증기: id 꼴 · 모르는 칸 · 칸마다 받는 값 · 설명 한 줄 — 한 번에 나열 · 지금 정의 11장은 깨끗하다
  ④ 데이터만으로 동사 추가(처리기가 이미 있는 것 · 시험용 임시 세트 — 코드 무수정): 정의 JSON + 말 파일 + 세트 한 줄 → 지침 행동 사전 줄 · 관측 COMMON 줄 ·
     파서(칸 규칙 = 정의) · 자동 접근 → 처리기 판정 · 대상 안 적는 동사(열린 결말 — 작정이 끊긴다) · 되돌리면 그대로 · 실제 세트·정의엔 없다
  ⑤ 지침 '행동 사전' 절이 세트에서 생긴다: 파일엔 동사 줄이 없고 표식 하나 · 줄 = 세트 순서 · 순서를 바꾸면 따라 바뀐다 · 빼면 지침·COMMON·파서에서 빠진다
  ⑥ 지침 문장 대조: 먼저 걸어가는 동사 목록 = approach · item 문장의 동사 = item 칸 · 몸짓 글자 수 = form
  ⑦ 하드코딩 잔재: 조합형 길(파서·작정·실행·사거리·판정 상태·접근 개시·작정 접수·then)에 옛 동사 목록이 없다(소스)
  ⑧ 배선: _run_gates.sh · VERSION 0.5.28 이상 · PATCH_NOTES · CHANGELOG · STREAM_FORMAT · prompts/README · check_words 가 세트를 센다
"""
import inspect
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="wl_verbs_")
os.environ.update(DUNGEON_GM="0", DUNGEON_BESTIARY_FILE="", DUNGEON_STATE_DIR=os.path.join(TMP, "state"),
                  DUNGEON_BRAIN_BACKEND="dummy", DUNGEON_ACTION_MODE="compose")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import brains                                        # noqa: E402
import composed_actions as CA                        # noqa: E402
import dungeon_gm as G                               # noqa: E402
import entities as ENT                               # noqa: E402
import scenario                                      # noqa: E402
import words as WD                                   # noqa: E402


class C:
    failed = 0
    n = 0


def check(name, ok, detail=""):
    C.n += 1
    print("  %s %s%s" % ("OK  " if ok else "FAIL", name, (" — " + str(detail)[:400]) if (detail and not ok) else ""))
    if not ok:
        C.failed += 1


def src(*p):
    with io.open(os.path.join(HERE, *p), encoding="utf-8") as f:
        return f.read()


def write_set(name, doc):
    p = os.path.join(TMP, name + ".json")
    with io.open(p, "w", encoding="utf-8") as f:
        f.write(doc if isinstance(doc, str) else json.dumps(doc, ensure_ascii=False))
    return p


def try_set(path, defs=None):
    """세트를 써 본다 → 거절 문장(받아들였으면 None)."""
    try:
        CA.use_set(path, defs)
        return None
    except CA.VerbError as e:
        return str(e)


def guide():
    return brains._load_prompt(os.path.join("prompts", "adventurer_prompt.md"))


def verb_lines(text):
    """지침 글 → 'COMMON' 줄 다음의 동사 줄들(빈 줄 앞까지)."""
    ls = text.split("\n")
    i = ls.index("COMMON")
    out = []
    for ln in ls[i + 1:]:
        if not ln:
            break
        out.append(ln)
    return out


def common_line(obs):
    return next(ln for ln in brains._wire(obs, compose=True).split("\n") if ln.startswith("COMMON: "))


def scene():
    d, bots = scenario.build({"map": ["##############", "#1...2......>#", "#............#", "##############"],
                              "seed": 7, "bots": {"1": {"potions": 3}, "2": {"potions": 0}}})
    d.give_verb = d.bond_verb = True
    return d, bots


SET = json.loads(src("entities", "verb_set.json"))
DEFS = {d["id"]: d for d in ENT.by_kind("verb")}
BASE_GUIDE = (brains.COMPOSE_PROMPT, brains.COMPOSE_PROMPT_SOLO)

print("── ① 세트 읽기")
check("① 세트 파일의 동사 = CA.COMMON(순서 그대로) · 세트의 동사마다 동사 정의(entities/verb/<동사>.json)",
      list(CA.COMMON) == SET["verbs"] and all(v in DEFS for v in SET["verbs"]), (CA.COMMON, SET))
check("① VERBS = 동사 정의의 comps.verb(설명은 말 파일에서 합친 글 — 표시가 남지 않는다) · 처리기 열쇠는 모두 엔진(HANDLERS)에 있다",
      CA.VERBS == {v: DEFS[v]["comps"]["verb"] for v in CA.COMMON} and all(s["handler"] in CA.HANDLERS for s in CA.VERBS.values())
      and all(s["desc"] and s["desc"] != WD.WORD_MARK for s in CA.VERBS.values()), CA.VERBS)
check("① DISTANCE_ACTIONS = approach 동사 · OPEN_END = open_end 동사(세트 순서) · handler_of = 정의의 처리기(세트 밖 이름은 그대로)",
      CA.DISTANCE_ACTIONS == tuple(v for v in CA.COMMON if CA.VERBS[v].get("approach"))
      and CA.OPEN_END == tuple(v for v in CA.COMMON if CA.VERBS[v].get("open_end"))
      and all(CA.handler_of(v) == CA.VERBS[v]["handler"] for v in CA.COMMON)
      and [CA.handler_of(t) for t in ("party_form", "interact", "follow", "fireball")] == ["party_form", "interact", "follow", "fireball"])
OLD = {"goto": {"handler": "goto", "target": "required", "memory_target": True},
       "explore": {"handler": "explore", "target": "required"},
       "search": {"handler": "search", "target": "required", "default_target": "self", "approach": True},
       "attack": {"handler": "attack", "target": "required", "approach": True},
       "use": {"handler": "use", "target": "required", "item": "optional", "approach": True},
       "buy": {"handler": "buy", "target": "required"},                                    # p0.5.29 — 상품은 문턱 2칸 안에서만 대상이라 걷지 않는다
       "sell": {"handler": "sell", "target": "required", "item": "required", "approach": True},
       "give": {"handler": "give", "target": "required", "item": "required", "approach": True},
       "bond": {"handler": "bond", "target": "required", "form": 120, "approach": True},
       "wait": {"handler": "wait", "target": "optional", "open_end": True},
       "rest": {"handler": "rest", "target": "optional", "open_end": True}}
check("① 지금 세트 = v0.5.29 의 11개 — v0.5.27 의 9개 + use 다음 buy·sell · 순서 · 처리기(같은 이름) · 칸(자동 접근 search·attack·use·sell·give·bond · 열린 결말 wait·rest · "
      "소지품 use 선택/sell·give 꼭 · 몸짓 bond 120자 · 기억 속 장소 goto · 기본 대상 search=self)",
      CA.COMMON == ("goto", "explore", "search", "attack", "use", "buy", "sell", "give", "bond", "wait", "rest")
      and {v: {k: x for k, x in s.items() if k != "desc"} for v, s in CA.VERBS.items()} == OLD
      and CA.DISTANCE_ACTIONS == ("search", "attack", "use", "sell", "give", "bond") and CA.OPEN_END == ("wait", "rest"), CA.VERBS)
d1, bots1 = scene()
b1 = bots1[0]
d1.view(b1, bots1)
b1["ledger"]["statics"]["f987"] = {"id": "f987", "type": "chest", "name": "상자", "x": 10, "y": 2, "zone": "?", "turn": 1}   # 시야 밖 기억 속 상자
o1 = d1.view(b1, bots1)
p_mem = CA.parse({"type": "goto", "target": "f987"}, o1)
r_mem = d1.act(b1, dict(p_mem[0] or {"type": "goto", "target": "f987"}), bots1)
check("① 기억 속 장소(goto 의 memory_target): 관측 known 의 ID 를 goto 는 받고 explore·attack 은 안 받는다 · 지금 안 보여도 기억대로 걷는다(pathed — lost 아님)",
      [e.get("id") for e in o1["known"]["statics"]] == ["f987"] and p_mem == ({"type": "goto", "target": "f987"}, None)
      and CA.parse({"type": "explore", "target": "f987"}, o1) == (None, "invalid_target") and CA.parse({"type": "attack", "target": "f987"}, o1) == (None, "invalid_target")
      and r_mem.get("result") == "pathed" and r_mem["resolution"]["type"] == "goto", (p_mem, r_mem.get("result")))
a_s = {"type": "search"}
CA.normalize(b1, a_s)
check("① 기본 대상·대상 안 적는 동사: 규칙 두뇌의 search(대상 없음) → 행동자 자신 · 작정의 wait·rest(대상 없음)는 참조 없이 유효 · attack(대상 없음)은 깨진다",
      a_s == {"type": "search", "target": "b1"} and CA.plan_step(d1, b1, {"type": "wait"}, bots1) == {"type": "wait"}
      and CA.plan_step(d1, b1, {"type": "rest"}, bots1) == {"type": "rest"} and CA.plan_step(d1, b1, {"type": "attack"}, bots1) is None, a_s)

print("── ② 잘못된 세트 거부")
extra_defs = dict(DEFS)
extra_defs["warp"] = {"id": "warp", "kind": "verb", "name": "순간 이동", "comps": {"verb": {"handler": "teleport", "target": "required", "desc": "x"}}}
extra_defs["party_leave"] = {"id": "party_leave", "kind": "verb", "name": "x", "comps": {"verb": {"handler": "wait", "target": "optional", "desc": "x"}}}
msg = try_set(write_set("bad_all", {"verbs": ["goto", "take", "goto", "interact", "warp", "party_leave", "rest"]}), extra_defs)
want = ("동사 'take' 의 정의가 없다", "동사 'goto' 가 두 번 나온다", "동사 'interact' 는 엔진이 따로 읽는 이름이다", "동사 'warp' 의 처리기 'teleport' 가 엔진에 없다",
        "동사 'party_leave' 는 엔진이 따로 읽는 이름이다")
check("② 없는 동사 · 중복 · 엔진이 따로 읽는 이름(옛 별칭·파티 동사) · 처리기 없음 — 거절 다섯 줄을 한 번에(그 밖 줄 없음)",
      msg is not None and all(w in msg for w in want) and len(msg.split("\n")) == len(want), msg)
shape = [try_set(write_set("bad_str", {"verbs": "goto"})), try_set(write_set("bad_empty", {"verbs": []})),
         try_set(write_set("bad_list", ["goto"])), try_set(os.path.join(TMP, "none.json")), try_set(write_set("bad_json", "{verbs: [goto]"))]
check("② 꼴: verbs 가 목록이 아님 · 빈 목록 · 세트가 객체가 아님 · 없는 파일 · JSON 아님 — 모두 거절(무엇이 틀렸는지)",
      all(shape[:3]) and all("verbs 는 동사 이름(문자열)의 비지 않은 목록" in m for m in shape[:3])
      and "못 읽는다 — FileNotFoundError" in (shape[3] or "") and "못 읽는다 — JSONDecodeError" in (shape[4] or ""), shape)
check("② 거절돼도 쓰던 세트 그대로(COMMON·VERBS·자동 접근·열린 결말 · 지침)",
      list(CA.COMMON) == SET["verbs"] and CA.VERBS == {v: DEFS[v]["comps"]["verb"] for v in CA.COMMON}
      and CA.DISTANCE_ACTIONS == ("search", "attack", "use", "sell", "give", "bond") and CA.OPEN_END == ("wait", "rest") and guide() == BASE_GUIDE)

print("── ③ 동사 정의 검증기")
bad_def = {"id": "Bad-Verb", "name": "x", "kind": "verb", "tags": ["verb"],
           "comps": {"verb": {"handler": "", "target": "maybe", "default_target": "here", "memory_target": False, "item": "many", "form": 0,
                              "approach": "yes", "open_end": 1, "desc": "한 줄\n두 줄", "color": "red"}}}
probs = ENT._problems([(os.path.join(ENT.ROOT, "verb", "Bad-Verb.json"), bad_def)], ENT.ROOT)
want3 = ("동사 id 는 소문자 낱말", "verb 가 모르는 칸 ['color']", "verb.handler 는 처리기 열쇠", "verb.target 은 required|optional",
         "verb.default_target 은 self", "verb.memory_target 는 true", "verb.approach 는 true", "verb.open_end 는 true", "verb.item 은 required|optional",
         "verb.form 은 정수≥1", "verb.desc(말 파일)는 비지 않은 한 줄")
check("③ 거절 11종을 한 번에 — id 꼴 · 모르는 칸 · 처리기 열쇠 · target · default_target · true 아닌 플래그 셋 · item · form · 여러 줄 설명",
      all(any(w in p for p in probs) for w in want3) and len(probs) == len(want3), probs)
opt_def = {"id": "linger", "name": "x", "kind": "verb", "comps": {"verb": {"handler": "wait", "target": "optional", "default_target": "self", "desc": "x"}}}
probs2 = ENT._problems([(os.path.join(ENT.ROOT, "verb", "linger.json"), opt_def)], ENT.ROOT)
check("③ 기본 대상은 대상을 꼭 적는 동사만(target optional + default_target 은 거절) · 지금 정의 11장은 깨끗하다",
      len(probs2) == 1 and "target 이 required 인 동사만" in probs2[0]
      and ENT._problems([(os.path.join(ENT.ROOT, "verb", v + ".json"), DEFS[v]) for v in CA.COMMON], ENT.ROOT) == [], (probs2,))

print("── ④ 데이터만으로 동사 추가(처리기가 이미 있는 것 — 시험용 임시 세트)")
eroot, wroot = os.path.join(TMP, "entities"), os.path.join(TMP, "world")
shutil.copytree(ENT.ROOT, eroot)
shutil.copytree(WD.WORDS_ROOT, wroot)
NEW = {"hand": ("쥐여 주기", {"handler": "give", "target": "required", "item": "required", "form": 8, "approach": True},
                "`item`을 `target`의 손에 쥐여 준다. 곁들이는 몸짓은 `form`에 8자까지."),
       "idle": ("가만히 있기", {"handler": "wait", "target": "optional", "open_end": True}, "제자리에서 가만히 있는다. `target`은 적지 않는다."),
       "peek": ("둘러보기", {"handler": "search", "target": "required", "default_target": "self", "approach": True}, "`target` 둘레를 둘러본다."),
       "strike": ("치기", {"handler": "attack", "target": "required", "approach": True}, "`target`을 친다."),
       "nap": ("눈 붙이기", {"handler": "rest", "target": "optional", "open_end": True}, "제자리에서 눈을 붙인다. `target`은 적지 않는다.")}
ASENT = "- 이동은 세계가 대신 걷는다. %s는 대상이 멀면 닿는 곳까지 먼저 걸어간 뒤 한다. 이동이 중단되면 다시 판단한다."   # 지침 문장 — 목록 자리(approach)
ISENT = "`target`은 관측에 나온 ID이고, `self`는 너 자신이다. `item`은 소지품 ID(`i...`)이며 %s에만 붙인다."   # 지침 문장 — 목록 자리(item)
for vid, (nm, vb, desc) in NEW.items():
    with io.open(os.path.join(eroot, "verb", vid + ".json"), "w", encoding="utf-8") as f:
        json.dump({"id": vid, "name": nm, "kind": "verb", "tags": ["verb"], "comps": {"verb": dict(vb, desc=WD.WORD_MARK)}}, f, ensure_ascii=False, indent=2)
    with io.open(os.path.join(wroot, "verb", vid + ".md"), "w", encoding="utf-8") as f:
        f.write(WD.render("verb", vid, nm, [("verb.desc", desc)]))
tdefs = {d["id"]: d for d in ENT.read(eroot, words_root=wroot).values() if d["kind"] == "verb"}
tset = write_set("with_new", {"verbs": SET["verbs"] + list(NEW)})
before_src = src("composed_actions.py")
names = CA.use_set(tset, tdefs)
check("④ 정의 JSON + 말 파일(임시 저장소 — 저장소 로더·말 합치기를 그대로 지난다) + 세트 한 줄 → COMMON 끝에 hand·idle·peek·strike·nap · 자동 접근 hand·peek·strike · "
      "열린 결말 idle·nap",
      names == tuple(SET["verbs"]) + tuple(NEW) and CA.DISTANCE_ACTIONS[-3:] == ("hand", "peek", "strike") and CA.OPEN_END[-2:] == ("idle", "nap")
      and CA.VERBS["hand"]["desc"] == NEW["hand"][2] and [CA.handler_of(v) for v in NEW] == ["give", "wait", "search", "attack", "rest"], (names, CA.DISTANCE_ACTIONS))
g_new = guide()
lines_new = verb_lines(g_new[0])
added = ["- `%s`: %s" % (v, NEW[v][2]) for v in NEW]
WORLD_NEW, ITEM_NEW = ASENT % "search·attack·use·sell·give·bond·hand·peek·strike", ISENT % "use·sell·give·hand"
check("④ 지침 행동 사전: 새 동사 줄 다섯이 세트 순서대로 rest 줄 뒤에 — 문장 안의 동사 목록도 세트에서(먼저 걸어가는 동사 …·bond·hand·peek·strike · "
      "소지품을 받는 동사 use·sell·give·hand — 문장 전체) — 그 다섯과 두 목록을 되돌리면 기본 지침과 바이트 같다(파티·혼자)",
      lines_new[-5:] == added and lines_new[:-5] == verb_lines(BASE_GUIDE[0])
      and all(WORLD_NEW in g.split("\n") and ITEM_NEW in g.split("\n") for g in g_new)
      and all(g.replace("\n" + "\n".join(added), "", 1).replace(WORLD_NEW, ASENT % "search·attack·use·sell·give·bond").replace(ITEM_NEW, ISENT % "use·sell·give") == b
              for g, b in zip(g_new, BASE_GUIDE)), lines_new[-6:])
d4, bots4 = scene()
o4 = d4.view(bots4[0], bots4)
check("④ 관측 COMMON 줄 = 세트 그대로(… / rest / hand / idle / peek / strike / nap)", common_line(o4) == "COMMON: " + " / ".join(names), common_line(o4))
p_ok = CA.parse({"type": "hand", "target": "b2", "item": "i1", "form": "손을 내민다 천천히"}, o4)
check("④ 파서 = 정의의 칸 규칙: hand(소지품 꼭 — 빠지면 missing_item · 대상 꼭 — missing_target · 몸짓 8자에서 자름) · idle(대상 안 적음 · 적으면 관측 ID 만 · "
      "소지품 칸 없음 — unexpected_item · 몸짓 칸 없음 — 버림) · peek(대상을 빼면 self = 행동자)",
      p_ok == ({"type": "hand", "target": "b2", "item": "i1", "form": "손을 내민다 천"}, None)
      and CA.parse({"type": "hand", "target": "b2"}, o4) == (None, "missing_item") and CA.parse({"type": "hand", "item": "i1"}, o4) == (None, "missing_target")
      and CA.parse({"type": "idle", "form": "x"}, o4) == ({"type": "idle"}, None) and CA.parse({"type": "idle", "target": "b2"}, o4) == ({"type": "idle", "target": "b2"}, None)
      and CA.parse({"type": "idle", "target": "zz9"}, o4) == (None, "invalid_target") and CA.parse({"type": "idle", "item": "i1"}, o4) == (None, "unexpected_item")
      and CA.parse({"type": "peek"}, o4) == ({"type": "peek", "target": "b1"}, None), p_ok)
r_start = d4.act(bots4[0], dict(p_ok[0]), bots4)
events = [r_start]
for _ in range(20):
    if not bots4[0].get("order"):
        break
    d4.turn += 1
    events.append(d4.step_order(bots4[0], bots4))
last = events[-1]
check("④ 먼 상대에게 hand → 자동 접근(approaching — 판정 머리의 동사는 hand) → 곁에 닿아 처리기 give 가 건넨다(given · 물약 3→2 / 0→1)",
      r_start.get("result") == "approaching" and r_start["resolution"]["type"] == "hand" and last.get("result") == "given" and last.get("to") == "2"
      and last.get("approach_status") == "completed" and bots4[0]["potions"] == 2 and bots4[1]["potions"] == 1, [(e.get("type"), e.get("result")) for e in events])
o4b = d4.view(bots4[0], bots4)
then = brains._then({"then": [{"type": "idle"}, {"type": "goto", "target": "b2"}]}, o4b)
dec_idle = brains._parse_decision(json.dumps({"reason": "r", "type": "idle", "then": [{"type": "goto", "target": "b2"}]}), None, o4b, "1", bots4)
r_idle = d4.act(bots4[0], {"type": "idle", "then": [{"type": "goto", "target": "b2"}]}, bots4)
check("④ idle(처리기 wait · 열린 결말) → 처리기의 판정(waiting) · 이어질 작정은 then 에서 끊기고(idle 까지) · 결정 읽기가 버리고 · 엔진도 받지 않는다(plan 빈 목록)",
      r_idle.get("result") == "waiting" and r_idle["resolution"]["type"] == "idle" and then == [{"type": "idle"}]
      and dec_idle.get("type") == "idle" and "then" not in dec_idle and bots4[0].get("plan") == [], (r_idle, then, dec_idle))
pk = CA.parse({"type": "peek"}, d4.view(bots4[0], bots4))[0]
r_peek = d4.act(bots4[0], pk, bots4) if pk else {}
a_pk = {"type": "peek"}
CA.normalize(bots4[0], a_pk)
check("④ peek(처리기 search) → 자기 자리 수색 · 찾은 것이 없으면 판정 상태 no_effect(search 의 규칙 — 동사 이름이 아니라 처리기 열쇠로) · "
      "규칙 두뇌의 peek(대상 없음)도 행동자로 · 작정의 idle(대상 없음)은 유효",
      r_peek.get("type") == "search" and r_peek.get("found") == [] and (r_peek.get("resolution") or {}).get("type") == "peek"
      and r_peek["resolution"]["status"] == "no_effect" and a_pk == {"type": "peek", "target": "b1"}
      and CA.plan_step(d4, bots4[0], {"type": "idle"}, bots4) == {"type": "idle"}, (r_peek.get("resolution"), a_pk))
dd, botsd = scenario.build({"map": ["######", "#1...#", "#.2.>#", "######"], "seed": 7, "bots": {"1": {"potions": 1}, "2": {"potions": 0}}})
dd.give_verb = dd.bond_verb = True
od = dd.view(botsd[0], botsd)
tgt_d = CA.entity(dd, botsd[0], "b2", botsd)
r_diag = dd.act(botsd[0], {"type": "hand", "target": "b2", "item": "i1"}, botsd)
d4f, bots4f = scene()
d4f.give_verb = False
d4f.view(bots4f[0], bots4f)
r_off = d4f.act(bots4f[0], {"type": "hand", "target": "b2", "item": "i1"}, bots4f)
check("④ 닿는 거리·접근 조건도 처리기(give)의 규칙: 대각선 곁이면 걷지 않고 바로 건넨다 · 건네기를 끈 판이면 hand 도 접근하지 않는다(too_far)",
      CA.in_range(dd, botsd[0], {"type": "hand"}, tgt_d) and not CA.in_range(dd, botsd[0], {"type": "idle"}, tgt_d)
      and r_diag.get("result") == "given" and r_off.get("result") == "too_far" and not bots4f[0].get("order"), (r_diag.get("result"), r_off.get("result")))
import skill_core as SK                              # noqa: E402
import repeat_signal as RS                           # noqa: E402
d4s, bots4s = scene()
b4s = bots4s[0]
b4s["atk_range"] = 3                                 # 활 든 사람 — 공격 처리기의 접근 반경은 사거리
d4s.skills = True
b4s["skill_cooldowns"] = {"zap": 2}
SK.complete(d4s, b4s, {"type": "peek", "action_id": "x1"}, {"resolution": {"phase": "resolved", "status": "no_effect"}, "found": []})
cd_peek = dict(b4s["skill_cooldowns"])
SK.complete(d4s, b4s, {"type": "idle", "action_id": "x2"}, {"resolution": {"phase": "resolved", "status": "no_effect"}})
cd_idle = dict(b4s["skill_cooldowns"])
check("④ 스킬 모듈의 공용 규칙도 처리기(attack·search)로: strike 의 접근 반경 = 사거리 3(peek 은 1) · 찾은 것 없는 peek 도 끝난 행동이라 스킬 대기시간 2→1 "
      "(변화 없는 idle 은 그대로)",
      SK.required_range(d4s, b4s, {"type": "strike"}) == 3 == SK.required_range(d4s, b4s, {"type": "attack"}) and SK.required_range(d4s, b4s, {"type": "peek"}) == 1
      and cd_peek == {"zap": 1} and cd_idle == {"zap": 1}, (cd_peek, cd_idle))
check("④ 반복 신호의 열쇠도 처리기로: idle(처리기 wait)은 대상을 적어도 기다리기 연속(wait) · nap(처리기 rest)은 대상을 적어도 끊긴다 · peek·strike 는 대상 ID",
      RS.key_of({"type": "idle"}) == RS.WAIT == RS.key_of({"type": "idle", "target": "b2"}) and RS.key_of({"type": "nap", "target": "b2"}) is None
      and RS.key_of({"type": "peek", "target": "b2"}) == "b2" and RS.key_of({"type": "strike", "target": "m1"}) == "m1")
sys.path.insert(0, os.path.join(HERE, "tools"))
import freedom_bench as FB                           # noqa: E402
import skill_schema as SS                            # noqa: E402
FB.CA = CA
cmb = list(FB.combos(o4))
sk = dict(next(iter(SS.PRESETS.values())), id="hand")
check("④ 세트를 읽는 다른 자리도 새 동사를 안다 — 스킬 이름 예약(hand 는 스킬 id 로 못 쓴다) · 벤치 조합 공간(hand 는 소지품과만 · idle 은 대상 없이 · peek 은 대상마다)",
      SS.validate(sk) == ["invalid_id"] and {"type": "hand", "target": "b2", "item": "i1"} in cmb and {"type": "hand", "target": "b2"} not in cmb
      and {"type": "idle"} in cmb and {"type": "peek", "target": "b2"} in cmb and "idle" in FB.targetless(), [c for c in cmb if c["type"] in NEW][:6])
CA.use_set()
d4c, bots4c = scene()
o4c = d4c.view(bots4c[0], bots4c)
check("④ 기본 세트로 되돌리면 그대로(COMMON·지침·관측 COMMON 줄 · 스킬 이름 hand 는 다시 쓸 수 있다 · idle 은 반복 열쇠 없음) · hand 는 다시 모르는 동사 · 코드(composed_actions.py)는 그대로 · "
      "실제 세트·정의 폴더엔 없다",
      list(CA.COMMON) == SET["verbs"] and guide() == BASE_GUIDE and common_line(o4c) == "COMMON: " + " / ".join(SET["verbs"]) and SS.validate(sk) == []
      and RS.key_of({"type": "idle"}) is None
      and CA.parse({"type": "hand", "target": "b2", "item": "i1"}, o4c) == (None, "invalid_type") and src("composed_actions.py") == before_src
      and not set(NEW) & set(DEFS) and not any(os.path.exists(os.path.join(ENT.ROOT, "verb", v + ".json")) for v in NEW))

print("── ⑤ 지침 '행동 사전' 절이 세트에서 생긴다")
raw = src("prompts", "adventurer_prompt.md")
sec = raw[raw.index("## 행동 사전"):raw.index("## 생각과 말")]
check("⑤ 지침 파일엔 동사 줄·동사 목록이 없다 — 행동 사전 절의 COMMON 아래 표식 하나(VERBS) · 문장 안 목록 자리 둘(approach · item) · 동사 설명은 말 파일(prompts/world/verb/)에만",
      raw.count(CA.VERB_MARK) == 1 and CA.VERB_MARK in sec and not re.search(r"^- `(?:%s)`:" % "|".join(SET["verbs"]), raw, re.M)
      and sorted(m.group(1) for m in CA.VERB_LIST.finditer(raw)) == ["approach", "item"]
      and "search·attack·use·sell·give·bond" not in brains._strip_comments(raw) and "use·sell·give" not in brains._strip_comments(raw)   # 사람용 메모(주석)의 예시는 뺀다
      and all(CA.VERBS[v]["desc"] not in raw for v in CA.COMMON) and all(os.path.isfile(WD.word_file(WD.WORDS_ROOT, "verb", v)) for v in CA.COMMON))
check("⑤ 게임이 읽은 지침(파티·혼자)의 COMMON 아래 줄 = 세트 순서대로 '- `동사`: 설명'(CA.guide_lines) · 표식·주석이 남지 않는다",
      all(verb_lines(g) == CA.guide_lines() == ["- `%s`: %s" % (v, CA.VERBS[v]["desc"]) for v in CA.COMMON] for g in BASE_GUIDE)
      and not any("VERBS" in g or "<!--" in g for g in BASE_GUIDE))
rev = list(reversed(SET["verbs"]))
CA.use_set(write_set("reversed", {"verbs": rev}))
d5, bots5 = scene()
g_rev, line_rev = guide(), common_line(d5.view(bots5[0], bots5))
CA.use_set(write_set("no_rest", {"verbs": [v for v in SET["verbs"] if v != "rest"]}))
d5b, bots5b = scene()
o5b = d5b.view(bots5b[0], bots5b)
g_cut, line_cut, p_cut = guide(), common_line(o5b), CA.parse({"type": "rest"}, o5b)
CA.use_set()
check("⑤ 세트 순서를 뒤집으면 지침 동사 줄·문장 안 목록(bond·give·sell·use·attack·search · give·sell·use)·관측 COMMON 줄이 함께 뒤집힌다(다른 글은 그대로)",
      verb_lines(g_rev[0]) == list(reversed(verb_lines(BASE_GUIDE[0]))) and line_rev == "COMMON: " + " / ".join(rev)
      and g_rev[0].replace("\n".join(verb_lines(g_rev[0])), "\n".join(verb_lines(BASE_GUIDE[0])))
      .replace(ASENT % "bond·give·sell·use·attack·search", ASENT % "search·attack·use·sell·give·bond").replace(ISENT % "give·sell·use", ISENT % "use·sell·give") == BASE_GUIDE[0], line_rev)
check("⑤ 세트에서 rest 를 빼면 지침의 rest 줄 · 관측 COMMON 줄의 rest · 파서(invalid_type)에서 함께 빠진다 — 되돌리면 그대로",
      "- `rest`:" not in g_cut[0] + g_cut[1] and verb_lines(g_cut[0]) == verb_lines(BASE_GUIDE[0])[:-1] and not line_cut.endswith("rest")
      and line_cut == "COMMON: " + " / ".join(SET["verbs"][:-1]) and p_cut == (None, "invalid_type") and guide() == BASE_GUIDE, (line_cut, p_cut))

print("── ⑥ 지침 문장 안의 동사 목록 · 설명의 숫자")
items = [v for v in CA.COMMON if CA.VERBS[v].get("item")]
check("⑥ 지침 문장 안의 동사 목록 = 세트에서 지은 것(문장 전체 · 파티·혼자): 먼저 걸어가는 동사 search·attack·use·sell·give·bond(approach 칸) · 소지품을 받는 동사 use·sell·give(item 칸)",
      all(ASENT % "search·attack·use·sell·give·bond" in g.split("\n") and ISENT % "use·sell·give" in g.split("\n") for g in BASE_GUIDE)
      and CA.guide_list("approach", "·") == "·".join(CA.DISTANCE_ACTIONS) and CA.guide_list("item", "·") == "·".join(items), (CA.DISTANCE_ACTIONS, items))
bad_mark = None
try:
    brains._fill_verbs("x <!--VERBS:color:·--> y")
except CA.VerbError as e:
    bad_mark = str(e)
check("⑥ 목록 자리의 칸 이름이 틀리면 거절(VerbError — 게임이 뜨지 않는다)", bad_mark is not None and "모르는 칸" in bad_mark, bad_mark)
check("⑥ 몸짓 칸이 있는 동사의 설명이 그 글자 수를 말한다(bond 120자)",
      all(("%d자" % s["form"]) in s["desc"] for s in CA.VERBS.values() if s.get("form")) and any(s.get("form") for s in CA.VERBS.values()))

print("── ⑦ 하드코딩 잔재(조합형 길에 옛 동사 목록이 없다)")
VERB_ALT = "|".join(SET["verbs"])
old_typ = re.compile(r"\b(?:typ|action\['type'\]|step\['type'\])\s*(?:==|!=|in|not in)\s*\(?\s*'(?:%s)'" % VERB_ALT)
fns = [CA.parse, CA.plan_step, CA.execute, CA.normalize, CA.in_range, CA.decorate]
hit = {f.__name__: old_typ.findall(inspect.getsource(f)) for f in fns}
check("⑦ composed_actions 파서·작정·실행·별칭·사거리·판정 상태에 동사 이름 비교가 없다(동사 정의·처리기 열쇠로 본다) · 옛 COMMON·DISTANCE_ACTIONS 글자 목록 없음",
      not any(hit.values()) and "COMMON = ('" not in before_src and "DISTANCE_ACTIONS = ('" not in before_src
      and "('wait', 'rest'" not in before_src, hit)
then_src, dec_src = inspect.getsource(brains._then), inspect.getsource(brains._parse_decision)
act_src, app_src = inspect.getsource(G.Dungeon.act), inspect.getsource(G.Dungeon._begin_approach)
check("⑦ brains(작정 then · 결정 읽기의 열린 결말) · dungeon_gm(작정 접수 · 접근 개시)의 조합형 길이 세트를 읽는다(CA.OPEN_END · CA.handler_of)",
      "G.CA.OPEN_END" in then_src and "('wait', 'rest')" not in then_src and 'composed["type"] in G.CA.OPEN_END' in dec_src
      and 'composed["type"] in ("wait", "rest")' not in dec_src and "CA.OPEN_END if self.composed_actions" in act_src
      and "typ in ('follow', 'wait', 'rest')" not in act_src and "CA.handler_of(typ) if self.composed_actions" in app_src
      and "typ == 'give' and not self.give_verb" not in app_src)
check("⑦ 동사 설명 글이 코드에 없다(말 파일에만) · 스킬 이름 예약이 세트를 읽는다 · 벤치 조합이 동사 정의를 읽는다",
      not any(CA.VERBS[v]["desc"] in src(p) for v in CA.COMMON for p in ("composed_actions.py", "brains.py", "dungeon_gm.py"))
      and "getattr(CA, 'COMMON', ())" in src("skill_schema.py") and 'CA.VERBS.get(typ)' in src("tools", "freedom_bench.py")
      and 'typ == "bond"' not in src("tools", "freedom_bench.py"))
import repeat_signal as RS                           # noqa: E402
import social_reactions as SR                        # noqa: E402
import show_runner as R                              # noqa: E402
check("⑦ 결정(동사)을 읽고 판단하는 곳 — 사회 장부(건네기·친목·치료) · 반복 신호의 열쇠 · 제안 뒤 행동 답 · NPC 에게 건 말 — 이 처리기 열쇠로 본다",
      "CA.handler_of(action['type'])" in inspect.getsource(SR.physical) and "G.CA.handler_of(t)" in inspect.getsource(RS.key_of)
      and 'G.CA.handler_of(dec.get("type"))' in inspect.getsource(R.classify_reply) and src("show_runner.py").count('G.CA.handler_of(dec.get("type"))') == 2)

print("── ⑧ 배선")
gates = src("_run_gates.sh")
cw = subprocess.run([sys.executable, os.path.join(HERE, "tools", "check_words.py")], capture_output=True, text=True, encoding="utf-8",
                    env=dict(os.environ, PYTHONUTF8="1"))
check("⑧ _run_gates.sh 에 등록(낱말 경계) · VERSION 0.5.28 이상 · PATCH_NOTES 0.5.28 · CHANGELOG p0.5.28 · STREAM_FORMAT·prompts/README 가 세트·말 파일 자리를 적는다",
      re.search(r"(?<![\w])verify_verbs(?![\w])", gates) is not None
      and tuple(int(x) for x in src("VERSION").strip().split(".")) >= (0, 5, 28) and "## 0.5.28" in src("docs", "PATCH_NOTES.md")
      and "p0.5.28" in src("docs", "CHANGELOG.md") and "verb_set.json" in src("STREAM_FORMAT.md")
      and "verb_set.json" in src("prompts", "README.md") and "world/verb/" in src("prompts", "README.md"))
check("⑧ tools/check_words.py 가 0 으로 끝나고 세트를 센다(동사 %d개 · 정의 %d장 · 처리기 %d개)" % (len(CA.COMMON), len(DEFS), len(CA.HANDLERS)),
      cw.returncode == 0 and ("동사 세트 entities/verb_set.json — 동사 %d개(%s) · 동사 정의 %d장 · 처리기 %d개"
                              % (len(CA.COMMON), "·".join(CA.COMMON), len(DEFS), len(CA.HANDLERS))) in cw.stdout, cw.stdout[-300:])

shutil.rmtree(TMP, ignore_errors=True)
print()
if C.failed:
    print("FAIL — %d/%d" % (C.failed, C.n))
    sys.exit(1)
print("ALL PASS — verify_verbs (p0.5.28 동사를 데이터로: %d checks · 세트 읽기 · 잘못된 세트·정의 거부 · 데이터만으로 동사 추가 · 지침 행동 사전이 세트에서 · 문장 대조 · 잔재 · 배선, 실 LLM 0콜)" % C.n)

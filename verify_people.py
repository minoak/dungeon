# -*- coding: utf-8 -*-
"""D85 인물 기록 — "낯선 사람": 사람에 대한 지식은 겪은 만큼, 캐릭터가 직접 적는다 — 72번째 게이트. LLM 0콜.
(2026-09-19 파트너 "낯선 사람이 맞아 npc나 캐릭터나 플레이어 캐릭터는 한번에 구분을 못해야해, 말을 걸고 상호작용을 하면서 해당 캐릭터에
 대한 지식이 생기고 나면 거기에 대해 따로 저장할수 있게 하자 로어북처럼 그럼 다음에 비슷한 캐릭터를 만나도 "카야 , 도적" 이라는 로어북이
 활성화 되면 자연스럽게 그 캐릭터에 대한 기억이 떠오르게 되겠지" · "조건은 a 와 c로 하자")
지식 활성화 규칙(HARNESS D85): 인물 기록 = {열쇠: 그 사람(개체) · 조건: (a) 보일 때 (c) 들은 말에 내가 적어 둔 이름이 나올 때 · 내용·이름: 캐릭터가 쓴다}.
러너 스위치 DUNGEON_STRANGERS(기본 0 · 파티 결성 판에서만). 끄면 옛 판 그대로(몸에 bot['people'] 이 없으면 엔진·프롬프트가 옛 길).
게이트(조각 ① — 캐릭터끼리):
  ① 꺼진 몸은 옛 그대로: 관측에 people 없음 · 프롬프트에 실명·'- 동료:' · 호칭 사전 = 실명
  ② 낯선 사람: 첫 판단의 **프롬프트 전체**(시트+지침+관측)에 남의 실명·직업이 없다 · '낯선 사람(봇N)' + 겉모습(머리색·윗옷색·무기·갑옷) ·
     PEOPLE 규칙 블록 · 메뉴형 선택지 라벨도 같은 말을 한다(표기의 단일 진실원천)
  ③ 말한 사람·목격·직전 결과의 호칭도 '낯선 사람'
  ④ 기록 쓰기(person_note): 지금 보이거나 방금 내게 말한 사람만 · 자기 자신·안 보이는 사람·빈 이름은 버린다 · 길이 상한 ·
     think_all 이 몸의 기록에 겹쳐 쓴다(turn·depth·src self)
  ⑤ 조건 (a) 보일 때: 그 사람 줄에 '네 기록' · 그때부터 호칭은 내가 적은 이름(말한 사람 표기·말 상대 `to` 해석도)
  ⑥ 조건 (c) 들은 말에 이름이 나올 때: 안 보이는 사람의 기록이 '## 떠오른 기억'에 · 보이는 사람은 제 줄에 이미 있으니 안 뜬다 ·
     한 글자 이름은 열쇠가 못 된다 · 직업 같은 내용 글자는 열쇠가 아니다(이름만)
  ⑦ 파티 결성 = 소개: 맺는 순간 서로의 이름·직업이 기록된다(src party) — 내가 이미 적어 둔 기록은 안 덮는다
  ⑧ 러너: 스위치는 파티 결성 판에서만 · 씨앗 = 시트에 작가가 쓴 관계 문장(그 사람이 보일 때 뜬다, 시트에는 상시로 안 싣는다) ·
     층을 옮겨도 기록은 같은 객체 · run_meta.strangers
  ⑨ 겉모습 어휘(색 이름) · 배선(문서)
  ⑩ 조각 ② — NPC = 미리 준비된 로어북, 규칙은 평등하다(파트너 "각 npc들은 차라리 그럼 미리 준비된 로어북으로 활성화 시키면 되지 않아?
     규칙 자체는 평등하게 잡고 말이야"): 준비된 항목 = NPC 정의(이름 → 역할 — 특징) · (a) 보일 때는 그 줄이 이미 말한다(D69·D75) ·
     (c) 들은 말에 NPC 이름이 나오면 안 보여도 떠오른다 · 캐릭터는 NPC 에도 기록을 남길 수 있고(보이는 NPC · 방금 내게 말한 NPC)
     보일 때 그 줄에 · 이름을 들을 때 준비된 칸과 함께 뜬다 · 꺼진 몸은 아무것도 안 뜬다
(기존 verify 71종은 별도 실행.)
"""
import contextlib
import io
import json
import os
import random
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = tempfile.mkdtemp(prefix="wl_people_")
STATE = os.path.join(ROOT, "state")
os.makedirs(STATE, exist_ok=True)
BASE_ENV = dict(DUNGEON_GM="0", DUNGEON_STEP_DELAY="0", DUNGEON_TURNS="60", DUNGEON_W="40", DUNGEON_H="16",
                DUNGEON_DEPTHS="2", DUNGEON_SEED="7", DUNGEON_MONSTERS="0", DUNGEON_TRAPS="0", DUNGEON_LURKERS="0",
                DUNGEON_BESTIARY_FILE="", DUNGEON_PARTY_FILE=os.path.join(HERE, "party.json"), DUNGEON_STATE_DIR=STATE,
                DUNGEON_TOWN="1", DUNGEON_BRAIN_BACKEND="dummy", DUNGEON_BOSS="0", DUNGEON_RUNS_DIR=os.path.join(ROOT, "runs"),
                DUNGEON_ACTION_MODE="compose", DUNGEON_PARTYFORM="1", DUNGEON_STRANGERS="1", DUNGEON_STREAM_OBS="1")
os.environ.update(BASE_ENV)
for k in ("DUNGEON_QUESTS", "DUNGEON_TOWN_APART", "DUNGEON_NPC_BRAIN", "DUNGEON_SOLO", "DUNGEON_START", "DUNGEON_MENU", "DUNGEON_RESUME"):
    os.environ.pop(k, None)

import brains                                        # noqa: E402
brains._call_claude = lambda prompt, model="haiku": ""   # LLM 무력화(결정론)
import dungeon_gm as G                               # noqa: E402
import sheetkit                                      # noqa: E402
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
REAL = {c: SHEETS[c]["name"] for c in SHEETS}
JOBS = {c: SHEETS[c]["job"] for c in SHEETS}


def town(people=True, parties=True):
    d, _ = show_runner.build_town(apart=True)
    d.composed_actions = d.auto_approach = True
    d.parties = G.new_parties() if parties else None
    bs = []
    for c in sorted(SHEETS):
        sh = dict(SHEETS[c])
        sh["look"] = sheetkit.random_look(random.Random("look:7:%s" % c), sh["sex"])
        b = G.spawn(d, c, bs, sheet=sh)
        if people:
            b["people"] = {}
        bs.append(b)
    d.turn = 5
    return d, bs


def cells(d, zid):
    return [(x, y) for y in range(d.h) for x in range(d.w)
            if d._zone_id(x, y) == zid and d.grid[y][x] == G.FLOOR and not d.feature_at(x, y)]


def put(b, xy):
    b["x"], b["y"] = xy


def full_prompt(d, bots, b, msgs=(), reply=None):
    """그 캐릭터가 실제로 받는 글 전체(시트+지침+관측) — _call_claude 를 가로채 본다. reply(JSON dict)를 주면 그 응답으로 결정까지."""
    seen = {}
    def stub(prompt, model="haiku"):
        seen["p"] = prompt
        return json.dumps(reply or {"type": "search", "target": "self"}, ensure_ascii=False)
    old_call, old_env = brains._call_claude, os.environ.get("DUNGEON_BRAIN_BACKEND")
    brains._call_claude, os.environ["DUNGEON_BRAIN_BACKEND"] = stub, "claude_cli"   # 스텁이 백엔드보다 우선 — 실 콜 없음
    try:
        o = d.view(b, bots)
        o["messages"] = [dict(m) for m in msgs]
        dec = brains.claude_brain(o, b["char"], b, bots)
    finally:
        brains._call_claude = old_call
        os.environ["DUNGEON_BRAIN_BACKEND"] = old_env or "dummy"
    return seen.get("p", ""), dec, o


print("── ① 꺼진 몸은 옛 그대로")
d0, bots0 = town(people=False, parties=False)
g0 = cells(d0, "guild_district")
put(bots0[0], g0[len(g0) // 2]); put(bots0[1], g0[len(g0) // 2 + 2])
p0, _, o0 = full_prompt(d0, bots0, bots0[0])
check("① 관측에 people 없음 · 프롬프트에 '- 동료: 카야(봇2), 피른(봇3)'·'동료 카야(봇2)' · PEOPLE 블록·겉모습 없음 · 호칭 사전 = 실명",
      "people" not in o0 and "- 동료: 카야(봇2), 피른(봇3)" in p0 and "동료 카야(봇2)" in p0 and "PEOPLE:" not in p0 and "겉모습:" not in p0
      and brains._names_for(bots0[0], bots0) == REAL)

print("── ② 낯선 사람")
d, bots = town()
b1, b2, b3 = bots
g, t = cells(d, "guild_district"), cells(d, "tavern_district")
m = len(g) // 2
put(b1, g[m]); put(b2, g[m + 2]); put(b3, t[len(t) // 2])
p1, _, o1 = full_prompt(d, bots, b1)
leak = [w for w in (REAL["2"], REAL["3"], JOBS["2"], JOBS["3"]) if w in p1]
check("② 첫 판단의 프롬프트 전체에 남의 실명·직업이 없다", not leak and len(p1) > 2000, leak)
check("② '낯선 사람(봇2) [b2]' + 겉모습 · 안 보이는 3 은 어디에도 없다 · PEOPLE 규칙 블록 · '동료'라는 호칭이 사람 줄에 없다",
      "낯선 사람(봇2) [b2]" in p1 and "겉모습:" in p1 and "봇3" not in p1 and "PEOPLE:" in p1 and "person_note" in p1
      and "동료 낯선" not in p1 and o1["people"] == {})
lk = next(b_["looks"] for b_ in o1["sights"]["bots"] if b_["char"] == "2")
check("② 겉모습 = 머리색 · 윗옷색(직업·이름 없음)", "머리" in lk and "윗옷" in lk and JOBS["2"] not in lk and REAL["2"] not in lk, lk)
dm, botsm = town()
dm.composed_actions = dm.auto_approach = False
put(botsm[0], g[m]); put(botsm[1], g[m + 2]); put(botsm[2], t[len(t) // 2])
labels = " / ".join(o_["label"] for o_ in (dm.view(botsm[0], botsm).get("options") or []))
check("② 메뉴형 선택지 라벨도 '낯선 사람'이라 부른다(실명 없음)", "낯선 사람" in labels and REAL["2"] not in labels, labels[:200])

print("── ③ 말한 사람·목격·직전 결과의 호칭")
msg = [{"from": "2", "text": "나는 카야, 도적이야. 같이 다닐래?", "turn": 5, "to": "1", "to_me": True}]
p3, _, _ = full_prompt(d, bots, b1, msg)
check("③ 말한 사람 = '낯선 사람(봇2): \"나는 카야…\"' — 이름은 말의 내용으로만 들린다",
      '- 낯선 사람(봇2): "나는 카야, 도적이야. 같이 다닐래?"' in p3 and "- 카야" not in p3)
names1 = {**brains._names_for(b1, bots), "?": brains.STRANGER}
check("③ 직전 결과·목격 문장도 같은 호칭", "낯선 사람(봇2)" in brains._last_prose({"type": "bonded", "from": "2", "form": "손을 흔든다"}, names1)
      and REAL["2"] not in brains._last_prose({"type": "party_asked_by", "from": "2"}, names1))
d._witness(bots, b2["x"], b2["y"], {"kind": "ally_bond", "char": "2", "to": "3", "form": "어깨를 두드린다"}, exclude=("2",))
ow = d.view(b1, bots)
check("③ 엔진이 만든 목격 사실의 이름도 '낯선 사람'", all(w.get("name") == "낯선 사람" and REAL["3"] not in str(w.get("to_name")) for w in ow.get("witnessed") or [{}])
      and bool(ow.get("witnessed")), ow.get("witnessed"))

print("── ④ 기록 쓰기(person_note)")
note = {"target": "b2", "name": "카야", "text": "도적이라고 했다. 같이 다니자고 먼저 말을 걸어왔다"}
_, dec, _ = full_prompt(d, bots, b1, msg, {"type": "search", "target": "self", "person_note": note})
check("④ 보이는 사람에 대한 기록 → 결정에 person_note{to,name,text}", dec.get("person_note") == {"to": "2", "name": "카야", "text": note["text"]}, dec.get("person_note"))
bad = [({"target": "b3", "name": "피른", "text": "x"}, "안 보이고 말도 안 한 사람"), ({"target": "b1", "name": "나", "text": "x"}, "자기 자신"),
       ({"target": "b2", "name": "  ", "text": "x"}, "빈 이름"), ("카야는 도적", "객체가 아님")]
check("④ 버리는 것: " + " · ".join(w for _, w in bad),
      all("person_note" not in full_prompt(d, bots, b1, msg, {"type": "search", "target": "self", "person_note": pn})[1] for pn, _ in bad))
_, dec_l, _ = full_prompt(d, bots, b1, msg, {"type": "search", "target": "self", "person_note": {"target": "2", "name": "가" * 50, "text": "나" * 300}})
check("④ 길이 상한(이름 %d · 내용 %d) · target 은 'b2'|'2'|'봇2' 다 통한다" % (brains.PERSON_NAME_LEN, brains.NOTE_LEN),
      len(dec_l["person_note"]["name"]) == brains.PERSON_NAME_LEN and len(dec_l["person_note"]["text"]) == brains.NOTE_LEN)
old_dd = brains._dummy_decision
brains._dummy_decision = lambda obs, char, why="테스트": {**old_dd(obs, char, why), **({"person_note": {"to": "2", "name": "카야", "text": note["text"]}} if char == "1" else {})}
try:
    brains.think_all(d, bots, {b_["char"]: [] for b_ in bots})
finally:
    brains._dummy_decision = old_dd
e2 = b1["people"].get("b2") or {}
check("④ think_all 이 몸의 기록에 쓴다(turn·depth·src self) — 남의 몸은 그대로", e2.get("name") == "카야" and e2.get("text") == note["text"]
      and e2.get("turn") == d.turn and e2.get("src") == "self" and b2["people"] == {} and b3["people"] == {}, e2)

print("── ⑤ 조건 (a) — 보일 때 뜬다")
p5, _, o5 = full_prompt(d, bots, b1, msg)
check("⑤ 그 사람 줄에 '카야(봇2) [b2] … 네 기록: 「…」' · 겉모습 꼬리는 사라진다 · 말한 사람도 '카야(봇2)'",
      "- 카야(봇2) [b2]" in p5 and "네 기록: 「%s」" % note["text"] in p5 and "낯선 사람(봇2)" not in p5 and '- 카야(봇2): "나는 카야' in p5)
check("⑤ 말 상대(to)는 내 기록으로 푼다: '카야' → 2 · 적어 둔 적 없는 실명 '피른' → None · 번호는 그대로",
      brains._parse_to("카야", "1", bots, o5) == "2" and brains._parse_to("피른", "1", bots, o5) is None and brains._parse_to("b2", "1", bots, o5) == "2")
check("⑤ 남의 눈에는 여전히 낯선 사람(기록은 각자의 것)", "낯선 사람(봇1)" in full_prompt(d, bots, b2)[0] and REAL["1"] not in full_prompt(d, bots, b2)[0].split("# 모험가 지침")[1])

print("── ⑥ 조건 (c) — 들은 말에 내가 적어 둔 이름이 나올 때")
put(b2, t[0]); put(b3, g[m + 3])
heard = [{"from": "3", "text": "아까 카야가 주점 쪽으로 가던데?", "turn": 6, "to": "1", "to_me": True}]
p6, _, _ = full_prompt(d, bots, b1, heard)
check("⑥ 안 보이는 카야의 기록이 '## 떠오른 기억'에 · 말한 3 은 낯선 사람",
      "## 떠오른 기억" in p6 and "- 카야: 「%s」" % note["text"] in p6 and '- 낯선 사람(봇3): "아까 카야가' in p6)
check("⑥ 기록은 조건이 맞을 때만 실린다 — 통째로 실리지 않는다('그 밖의 정보' JSON 에 people 없음)", '"people"' not in p6 and "src" not in p6.split("## 떠오른 기억")[1][:400])
check("⑥ 이름이 안 나오면 안 뜬다 · 내용 글자(도적)는 열쇠가 아니다",
      "## 떠오른 기억" not in full_prompt(d, bots, b1, [{"from": "3", "text": "주점에 도적이 하나 있던데?", "turn": 6, "to": "1", "to_me": True}])[0])
put(b2, g[m + 2])
check("⑥ 보이는 사람은 제 줄에 이미 기록이 있으니 '떠오른 기억'에 또 뜨지 않는다", "## 떠오른 기억" not in full_prompt(d, bots, b1, heard)[0])
b1["people"]["b3"] = {"name": "피니", "text": "활을 멘다", "turn": 5, "src": "self"}
b1["people"]["b9"] = {"name": "가", "text": "한 글자 이름", "turn": 5, "src": "self"}
put(b3, t[1])
check("⑥ 한 글자 이름은 열쇠가 못 된다(아무 말에나 걸린다)", "한 글자 이름" not in full_prompt(d, bots, b1, [{"from": "2", "text": "가자, 피니는 어디 갔지?", "turn": 6, "to": "1", "to_me": True}])[0]
      and "- 피니: 「활을 멘다」" in full_prompt(d, bots, b1, [{"from": "2", "text": "가자, 피니는 어디 갔지?", "turn": 6, "to": "1", "to_me": True}])[0])

print("── ⑦ 파티 결성 = 소개")
d7, bots7 = town()
c1, c2, c3 = bots7
put(c1, g[m]); put(c2, g[m + 2]); put(c3, g[m + 3])
c1["people"]["b2"] = {"name": "눈 좋은 애", "text": "함정을 잘 본다", "turn": 1, "src": "self"}
d7._party_form(c1, "b2", bots7)
r7 = d7._party_form(c2, "b1", bots7)
check("⑦ 맺는 순간 서로의 이름·직업이 기록된다(src party) — 내가 이미 적어 둔 기록은 안 덮는다 · 파티 밖 3 은 그대로",
      r7["result"] == "party_formed" and c2["people"].get("b1") == {"name": REAL["1"], "text": JOBS["1"], "turn": d7.turn, "depth": d7.depth, "src": "party"}
      and c1["people"]["b2"]["name"] == "눈 좋은 애" and c3["people"] == {}, (c1["people"], c2["people"]))
p7 = full_prompt(d7, bots7, c2)[0]
check("⑦ 맺은 뒤 명단·사람 줄이 그 이름으로 · 파티 밖 3 은 여전히 낯선 사람", "- 두란(봇1), 전사" in p7 and "낯선 사람(봇3)" in p7 and REAL["3"] not in p7)

print("── ⑧ 러너")
def probe(env):
    e = {k: v for k, v in os.environ.items() if not k.startswith("DUNGEON_")}
    e.update(PYTHONUTF8="1", **env)
    p = subprocess.run([sys.executable, "-c", "import json, show_runner as s; print(json.dumps({'on': s.STRANGERS_ON, 'fp': 'strangers' in s._world_fingerprint()}))"],
                       cwd=HERE, env=e, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return json.loads(p.stdout.splitlines()[0]) if p.returncode == 0 and p.stdout.strip() else {"err": p.stderr[-300:]}
check("⑧ 스위치: 기본 꺼짐 · 파티 결성 판이 아니면 켜도 꺼짐 · 둘 다 켜면 켜짐(지문 열쇠)",
      probe({k: v for k, v in BASE_ENV.items() if k != "DUNGEON_STRANGERS"}) == {"on": False, "fp": False}
      and probe({**BASE_ENV, "DUNGEON_PARTYFORM": "0"}) == {"on": False, "fp": False} and probe(BASE_ENV) == {"on": True, "fp": True})
cap = []
_spawn = G.spawn
def spawn8(dd, char, bs, **k):
    b = _spawn(dd, char, bs, **k)
    cap.append((dd.depth, b))
    return b
G.spawn = spawn8
_dummy = G.dummy_brain
G.dummy_brain = lambda obs, char="?": ({"type": "search"} if obs.get("town") and obs.get("turn", 0) < 3 else _dummy(obs, char))
try:
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            show_runner.main()
        except SystemExit:
            pass
finally:
    G.spawn, G.dummy_brain = _spawn, _dummy
with open(os.path.join(STATE, "stream.jsonl"), encoding="utf-8") as f:
    rows8 = [json.loads(ln) for ln in f if ln.strip()]
mine8 = [(dep, b) for dep, b in cap if b["char"] == "1"]
seed = mine8[0][1].get("people") or {}
check("⑧ run_meta.strangers True · 씨앗 = 시트의 관계 문장(두란은 카야·피른을 이미 안다, src sheet) · 스트림의 실명은 그대로(관전자는 안다)",
      rows8[0].get("strangers") is True and sorted(seed) == ["b2", "b3"] and seed["b2"]["name"] == REAL["2"] and seed["b2"]["src"] == "sheet"
      and seed["b2"]["text"] == SHEETS["1"]["relationships"]["2"] and rows8[0]["party"][1]["name"] == REAL["2"])
obs8 = next((((r.get("decisions") or {}).get("1") or {}).get("obs") for r in rows8 if r["kind"] == "tick" and ((r.get("decisions") or {}).get("1") or {}).get("obs")), None)
check("⑧ 러너 판의 관측에 people(씨앗) · 시트에는 관계 문장을 상시로 싣지 않는다", obs8 is not None and sorted(obs8.get("people") or {}) == ["b2", "b3"]
      and "와의 관계:" not in brains._sheet(mine8[0][1], [b for _, b in cap[:3]]))
deps8 = sorted({dep for dep, _ in mine8})
check("⑧ 층을 옮겨도 기록은 같은 객체(이월)", len(deps8) >= 2 and all(b.get("people") is seed for _, b in mine8), deps8)

print("── ⑩ NPC = 미리 준비된 로어북 · 규칙은 평등하다")
book = brains._npc_book()
check("⑩ 준비된 항목 = NPC 정의에서(이름 → '역할 — 특징') — 길드 접수원·주점 주인·성직자·떠돌이 모험자…",
      book.get("길드 접수원", "").startswith("원정 물품 · 의뢰 접수와 귀환 보고 — ") and "주점 주인" in book and "성직자" in book and len(book) >= 5, sorted(book))
d10, bots10 = town()
a1, a2, a3 = bots10
put(a1, t[len(t) // 2]); put(a2, t[len(t) // 2 + 2]); put(a3, g[m])
o10 = d10.view(a1, bots10)
vis_npc = {f["name"] for f in o10["sights"]["features"] if f["type"] == "npc"}
say10 = [{"from": "2", "text": "길드 접수원한테 물약을 받을 수 있대.", "turn": 5, "to": "1", "to_me": True}]
check("⑩ 사실 기록: 마을에서는 NPC 가 어느 구역에서나 보인다(D60 마을 관측) — 마을 안에서는 NPC 의 조건 (a)가 늘 참이다(사람 지각 D70 과의 불평등은 파트너 결정 대기)",
      {"길드 접수원", "주점 주인", "성직자"} <= vis_npc and "## 떠오른 기억" not in full_prompt(d10, bots10, a1, say10)[0], sorted(vis_npc))


def floor10():
    fl = G.Dungeon(seed=7, w=40, h=16, n_monsters=0, n_traps=0, n_lurkers=0)
    fl.composed_actions = fl.auto_approach = True
    fl.turn = 9
    fb = []
    for c in ("1", "2"):
        b = G.spawn(fl, c, fb, sheet=dict(SHEETS[c]))
        b["people"] = {}
        fb.append(b)
    return fl, fb


fl10, fb10 = floor10()
p10 = full_prompt(fl10, fb10, fb10[0], say10)[0]
check("⑩ (c) 던전에서 남이 '길드 접수원'을 말하면 — 안 보여도 준비된 항목이 떠오른다(캐릭터의 기록과 같은 절)",
      "## 떠오른 기억" in p10 and "- 길드 접수원: 원정 물품 · 의뢰 접수와 귀환 보고" in p10)
near = next((f for f in d10.features.values() if f.type == "npc" and f.name == "주점 주인"), None)
put(a1, next((x, y) for x, y in t if max(abs(x - near.x), abs(y - near.y)) <= 2 and (x, y) != (near.x, near.y)))
o10b = d10.view(a1, bots10)
fid = next(f["id"] for f in o10b["sights"]["features"] if f["type"] == "npc" and f["name"] == "주점 주인")
p10b, dec10, _ = full_prompt(d10, bots10, a1, [{"from": "2", "text": "주점 주인이 소문을 안대.", "turn": 5, "to": "1", "to_me": True}],
                             {"type": "search", "target": "self", "person_note": {"target": fid, "name": "주점 주인", "text": "소문을 물으면 숫자까지 알려 준다. 말이 짧다"}})
check("⑩ (a) 보이는 NPC 는 제 줄이 이미 말한다 — 이름을 들어도 '떠오른 기억'에 또 뜨지 않는다 · 기록 쓰기는 NPC 에도(to = npc:<이름>)",
      "## 떠오른 기억" not in p10b and dec10.get("person_note") == {"to": "npc:주점 주인", "name": "주점 주인", "text": "소문을 물으면 숫자까지 알려 준다. 말이 짧다"},
      dec10.get("person_note"))
a1["people"]["npc:주점 주인"] = {"name": "주점 주인", "text": "소문을 물으면 숫자까지 알려 준다. 말이 짧다", "turn": 5, "src": "self"}
p10c = full_prompt(d10, bots10, a1)[0]
check("⑩ (a) 다시 보면 그 NPC 줄에 '네 기록: 「…」'", "네 기록: 「소문을 물으면 숫자까지 알려 준다. 말이 짧다」" in p10c)
fb10[0]["people"]["npc:주점 주인"] = dict(a1["people"]["npc:주점 주인"])
p10d = full_prompt(fl10, fb10, fb10[0], [{"from": "2", "text": "주점 주인이 널 찾던데?", "turn": 9, "to": "1", "to_me": True}])[0]
check("⑩ (c) 던전에서 이름을 들으면 준비된 칸 + 내 기록이 한 줄로 떠오른다",
      "- 주점 주인: 소문 · 쉬어 가는 자리" in p10d and "네 기록 「소문을 물으면 숫자까지 알려 준다. 말이 짧다」" in p10d)
_, dec10e, _ = full_prompt(d10, bots10, a1, [{"from": "npc:길드 접수원", "text": "두란 님, 어서 오세요.", "turn": 6, "to": "1", "to_me": True}],
                           {"type": "search", "target": "self", "person_note": {"target": "길드 접수원", "name": "접수원 누님", "text": "물약을 챙겨 준다"}})
check("⑩ 방금 내게 말한 NPC 에 대해서도 적을 수 있다 — 내가 붙인 이름으로", dec10e.get("person_note") == {"to": "npc:길드 접수원", "name": "접수원 누님", "text": "물약을 챙겨 준다"})
p10f = full_prompt(d0, bots0, bots0[0], say10)[0]
check("⑩ 꺼진 몸(옛 판)은 이름을 들어도 아무것도 안 뜬다", "## 떠오른 기억" not in p10f)

print("── ⑨ 겉모습 어휘 · 배선")
cw = sheetkit.color_word
check("⑨ 색 이름: 스와치의 머리색 여덟이 서로 구별되는 말로 · 깨진 값은 죽지 않는다",
      [cw(h) for h in ("#945c37", "#352c2c", "#d8ba77", "#a84c32", "#cbc8c3", "#415b73", "#38574e")] == ["갈색", "검은", "금빛", "붉은", "흰", "푸른", "녹색"]
      and cw("zz") == "빛바랜", [cw(h) for h in ("#945c37", "#352c2c", "#d8ba77", "#a84c32", "#cbc8c3", "#415b73", "#38574e")])
check("⑨ 겉모습 한 줄에 찬 무기·걸친 갑옷이 실린다", sheetkit.looks_line({"look": {"colors": {"hair": "#a84c32", "top": "#577348"}}, "weapon": {"name": "장검", "bonus": 1},
                                                                "armor": {"name": "사슬 갑옷", "bonus": 2}}) == "붉은 머리 · 녹색 윗옷 · 장검 · 사슬 갑옷")
def text(*p):
    with open(os.path.join(HERE, *p), encoding="utf-8") as f:
        return f.read()
hd, fmt = text("design", "HARNESS_DESIGN.md"), text("STREAM_FORMAT.md")
check("⑨ HARNESS D85(활성화 규칙 표·조건 a·c) · STREAM_FORMAT(strangers·person_note·obs.people·looks)",
      "## [결정] D85." in hd and "DUNGEON_STRANGERS" in hd and "(c) 들은 말에 내가 적어 둔 이름이 나올 때" in hd
      and all(s_ in fmt for s_ in ("strangers", "person_note", "obs.people", "looks")))

print("=" * 44)
print("ALL PASS — verify_people (D85 인물 기록: 낯선 사람 · 보는 사람 기준 호칭 · 기록 쓰기 · 보일 때/이름을 들을 때 떠오른다 · 파티 결성 = 소개)"
      if not C.failed else "FAILED %d" % C.failed)
sys.exit(1 if C.failed else 0)

# -*- coding: utf-8 -*-
"""친목(D47 ②, 2026-09-09 파트너 "잡담 뒤에 추가로 비슷한 형식으로 ['대화' '친목' '머리를 쓰다듬기'] … 이건 친목 행위라 일반 대화와는
별개") 검증 — 43번째 게이트. LLM 0콜.
곁(체비셰프≤1)의 동료에게 하는 몸짓 하나 — 형태(응답 form)는 캐릭터의 자유 문구(목록 아님: 기계는 횟수만, 형태는 기록으로),
물리 없음. 받은 쪽 자기 사건(bonded)·목격(ally_bond)·뼈 bond(쌍이 같이 '친목행위')·상세 기록(acts: 형태+상대 반응). 상대는 안 서고
(대기·휴식이면 깬다) 반응은 상대의 다음 결정에서 형태(행동|말|없음)로만 적힌다 — 시도했다고 반응까지 정해지지 않는다(초안 §A-3).
게이트:
  ① 상수·스위치: BONES bond '친목행위' · EVENT_KINDS bond/bonded · WITNESS_LABELS · BOND_LEN/ACTS_MAX/ACTS_SHOW · 엔진 기본 꺼짐 · 러너 기본 1
  ② _clean_form: 공백 접기·따옴표 제거·상한 · 빈 값
  ③ 메뉴: 곁의 동료에게 한 줄(`form` 안내) · 2칸 밖 없음 · 꺼진 판 없음 · 건네기 꺼도 친목은 산다
  ④ 물리: done/to/form · 받은 쪽 last/궤적(bonded) · 목격(ally_bond, 둘 제외) · 뼈 bond 양쪽 · acts 양쪽 · 층 집계 · form 정제(빈 값=몸짓)
  ⑤ 실패·정지: too_far · no_target · 꺼진 판 nothing · 걷는 상대 무정지 · 휴식 상대 깸
  ⑥ note_reply: 안 적힌 기록 전부에 · 적힌 것은 안 건드림 · ACTS_MAX 상한
  ⑦ 러너: settle_acts(친목 반응 말/없음) · replies 목록에 제안·친목 나란히
  ⑧ 관측·렌더: view relations acts(≤ACTS_SHOW) · wire '최근 친목·건네기' 양쪽 시점 · _last_prose · event_tags · _witness_prose · act_summary · _hist_item · 직전 판단
  ⑨ think_all: 메뉴 번호+form → dec.form · intent/history 에 form · form 없는 응답=엔진 '몸짓'
  ⑩ 지침·배선(소스): 친목 절·form 필드 · 러너 스위치·run_meta · build_town 미러링 · scenario 미러링 · 뷰어
(기존 verify 42종은 별도 실행.)
"""
import os
import tempfile

os.environ.update(DUNGEON_GM="0", DUNGEON_TURNS="4", DUNGEON_W="40", DUNGEON_H="16",
                  DUNGEON_SEED="7", DUNGEON_MONSTERS="0", DUNGEON_TRAPS="0", DUNGEON_LURKERS="0",
                  DUNGEON_DEPTHS="1", DUNGEON_BESTIARY_FILE="",
                  DUNGEON_STATE_DIR=os.path.join(tempfile.mkdtemp(prefix="wl_bond_"), "state"))
os.environ.pop("DUNGEON_PARTY_FILE", None)

import brains                                        # noqa: E402
import dungeon_gm as G                               # noqa: E402
from dungeon_gm import Dungeon                       # noqa: E402
import show_runner                                   # noqa: E402
show_runner.STEP_DELAY = 0
HERE = os.path.dirname(os.path.abspath(__file__))


class C:
    failed = 0


def check(name, cond):
    print(("  OK   " if cond else " FAIL  ") + name)
    if not cond:
        C.failed += 1


ROWS = ["############",
        "#12.3.....>#",
        "############"]
NAMES = {"1": "두란", "2": "카야", "3": "피른"}


def scene(give=True, bond=True, relations=True):
    d, st = Dungeon.from_ascii(ROWS, seed=7)
    d.events, d.relations, d.trail_on, d.floor_on = True, relations, True, True
    d.give_verb, d.bond_verb = give, bond
    bots = []
    for c in "123":
        b = G.spawn(d, c, bots, sheet=G.HEROES.get(c) or G.HEROES['1'])
        b["x"], b["y"] = st[c]
        b["name"] = NAMES[c]
        b["potions"], b["weapon"], b["armor"] = 0, None, None
        bots.append(b)
    d.turn = 5
    return d, bots


def bone(b, oc, kind):
    return (((b.get("relations") or {}).get(oc) or {}).get("bones") or {}).get(kind, {}).get("n", 0)


def acts(b, oc):
    return (((b.get("relations") or {}).get(oc) or {}).get("acts")) or []


def opts(d, b, bots, typ="bond"):
    return [o for o in d.view(b, bots)["options"] if o["type"] == typ]


print("── ① 상수·스위치")
check("① BONES bond='친목행위'(쌍이 같이) · EVENT_KINDS bond/bonded · WITNESS_LABELS ally_bond · 상한들",
      G.BONES.get("bond") == "친목행위" and "bond" not in G.STRONG_BONES
      and G.EVENT_KINDS.get("bond") is True and G.EVENT_KINDS.get("bonded") is True
      and G.WITNESS_LABELS.get("ally_bond") == "동료 친목" and G.BOND_LEN == 30 and G.ACTS_MAX == 8 and G.ACTS_SHOW == 4)
d_def = Dungeon(seed=7, w=30, h=12)
d_asc, _ = Dungeon.from_ascii(ROWS, seed=7)
check("① 엔진 기본 꺼짐(__init__·from_ascii) · 러너 기본 켬", d_def.bond_verb is False and d_asc.bond_verb is False and show_runner.BOND_ON is True)

print("── ② _clean_form")
cf = brains._clean_form
check("② 공백 접기·따옴표 제거·상한 30·빈 값",
      cf('  "머리  쓰다듬기" ') == "머리 쓰다듬기" and cf("'포옹'\n해줌") == "포옹 해줌" and len(cf("가" * 50)) == 30
      and cf(None) == "" and cf("") == "")

print("── ③ 메뉴")
d, bots = scene()
b1, b2, b3 = bots
bs = opts(d, b1, bots)
check("③ 곁의 카야(봇2)에게 한 줄(target b2, `form` 안내) · 피른(2칸) 없음",
      [o["target"] for o in bs] == ["b2"] and "친목: 카야(봇2)에게" in bs[0]["label"] and "`form`" in bs[0]["label"]
      and "item" not in bs[0])
check("③ 카야(봇2)에겐 두란(곁)만 · 피른(2칸) 없음", [o["target"] for o in opts(d, b2, bots)] == ["b1"])
d_off, bots_off = scene(bond=False)
check("③ 꺼진 판: 친목 줄 없음", opts(d_off, bots_off[0], bots_off) == [])
d_g, bots_g = scene(give=False, bond=True)
check("③ 건네기를 꺼도 친목은 산다", [o["target"] for o in opts(d_g, bots_g[0], bots_g)] == ["b2"] and opts(d_g, bots_g[0], bots_g, "give") == [])

print("── ④ 물리")
d, bots = scene()
b1, b2, b3 = bots
res = d.act(b1, {"type": "bond", "target": "b2", "form": " 머리  쓰다듬기 "}, bots)
check("④ 결과: done · to 2 · form 정제 · 두란 last=bond",
      res.get("result") == "done" and res.get("to") == "2" and res.get("form") == "머리 쓰다듬기" and (b1.get("last") or {}).get("type") == "bond")
check("④ 받은 쪽: last=bonded(from 1, form) · 궤적에도",
      (b2.get("last") or {}) == {"char": "2", "type": "bonded", "from": "1", "form": "머리 쓰다듬기"}
      and any(t.get("type") == "bonded" for t in b2.get("trail") or []))
check("④ 목격: 피른만 ally_bond{char 1, to 2, form}",
      (b3.get("witnessed") or []) == [{"kind": "ally_bond", "char": "1", "to": "2", "form": "머리 쓰다듬기"}]
      and not b1.get("witnessed") and not b2.get("witnessed"))
check("④ 뼈: 양쪽 bond ×1(친목행위) · gave/received 0 · talk 0",
      bone(b1, "2", "bond") == 1 and bone(b2, "1", "bond") == 1 and bone(b1, "2", "gave") == 0 and bone(b1, "2", "talk") == 0)
check("④ 상세 기록 양쪽: {t5, 친목, 머리 쓰다듬기, mine, reply None}",
      acts(b1, "2") == [{"turn": 5, "kind": "친목", "what": "머리 쓰다듬기", "mine": True, "reply": None}]
      and acts(b2, "1") == [{"turn": 5, "kind": "친목", "what": "머리 쓰다듬기", "mine": False, "reply": None}])
check("④ 층 집계: 두란 [친목] ×1 · 카야 [친목 받음] ×1 · 피른 목격 [동료 친목] ×1",
      b1["floor"]["n"].get("친목") == 1 and b2["floor"]["n"].get("친목 받음") == 1 and b3["floor"]["w"].get("동료 친목") == 1)
r_empty = d.act(b1, {"type": "bond", "target": "b2"}, bots)
r_long = d.act(b1, {"type": "bond", "target": "b2", "form": "가" * 50}, bots)
check("④ form 없음=몸짓 · 긴 문구는 30자", r_empty.get("form") == "몸짓" and len(r_long.get("form")) == 30)

print("── ⑤ 실패·정지")
d, bots = scene()
b1, b2, b3 = bots
r_far = d.act(b1, {"type": "bond", "target": "b3", "form": "포옹"}, bots)
r_no = d.act(b1, {"type": "bond", "target": "b9", "form": "포옹"}, bots)
check("⑤ too_far(피른 2칸) · no_target · 뼈·기록 없음",
      r_far["result"] == "too_far" and r_no["result"] == "no_target" and bone(b1, "3", "bond") == 0 and not acts(b1, "3"))
d_off, bots_off = scene(bond=False)
r_off = d_off.act(bots_off[0], {"type": "bond", "target": "b2", "form": "포옹"}, bots_off)
check("⑤ 꺼진 판: nothing · 뼈 없음", r_off["result"] == "nothing" and bone(bots_off[0], "2", "bond") == 0)
d, bots = scene()
b1, b2, b3 = bots
b2["order"], b2["path"] = "exit", [(b2["x"] + 1, b2["y"])]
d.act(b1, {"type": "bond", "target": "b2", "form": "어깨 두드리기"}, bots)
check("⑤ 걷는 상대는 안 선다", b2["order"] == "exit")
b2["order"], b2["path"], b2["rest"] = "rest", [], {"n": 1, "healed": 0, "allies": set()}
d.act(b1, {"type": "bond", "target": "b2", "form": "어깨 두드리기"}, bots)
check("⑤ 쉬는 상대는 깬다(order·rest 비움)", b2["order"] is None and b2.get("rest") is None)

print("── ⑥ note_reply·상한")
d, bots = scene()
b1, b2, b3 = bots
d.act(b1, {"type": "bond", "target": "b2", "form": "포옹"}, bots)
d.turn = 6
d.act(b1, {"type": "bond", "target": "b2", "form": "손잡기"}, bots)
d.note_reply(b2, b1, "말")
check("⑥ 안 적힌 기록 전부에 답이 적힌다(양쪽)",
      [a["reply"] for a in acts(b1, "2")] == ["말", "말"] and [a["reply"] for a in acts(b2, "1")] == ["말", "말"])
d.turn = 7
d.act(b1, {"type": "bond", "target": "b2", "form": "머리 쓰다듬기"}, bots)
d.note_reply(b2, b1, "행동")
check("⑥ 이미 적힌 것은 안 건드린다", [a["reply"] for a in acts(b1, "2")] == ["말", "말", "행동"])
for i in range(10):
    d.act(b1, {"type": "bond", "target": "b2", "form": "포옹 %d" % i}, bots)
check("⑥ ACTS_MAX 상한(오래된 것부터 바랜다)", len(acts(b1, "2")) == 8 and acts(b1, "2")[-1]["what"] == "포옹 9")
d_nr, bots_nr = scene(relations=False)
d_nr.act(bots_nr[0], {"type": "bond", "target": "b2", "form": "포옹"}, bots_nr)
check("⑥ 관계 장부 꺼진 판: 뼈·기록 없음(결과·받은 쪽 사건은 그대로)",
      not bots_nr[0].get("relations") and (bots_nr[1].get("last") or {}).get("type") == "bonded")

print("── ⑦ 러너 반응 집계")
d, bots = scene()
b1, b2, b3 = bots
d.act(b1, {"type": "bond", "target": "b2", "form": "포옹"}, bots)
oa = {"2": {"1": "친목"}}
reps = []
out = show_runner.settle_acts(d, bots, oa, {"2": {"type": "goto", "target": "f0", "say": "고마워", "to": "1", "src": "haiku"}}, reps)
check("⑦ 친목 뒤 첫 결정(말 to 1)=말 · 기록에 · replies",
      out == [{"from": "2", "to": "1", "kind": "친목", "how": "말"}] and acts(b2, "1")[-1]["reply"] == "말" and acts(b1, "2")[-1]["reply"] == "말")
d.turn = 6
d.act(b1, {"type": "bond", "target": "b2", "form": "손잡기"}, bots)
oa = {"2": {"1": "친목"}}
op = {"2": {"1": 6}}
reps = []
show_runner.settle_proposals(d, bots, op, {"2": {"type": "explore", "say": "", "src": "haiku"}}, reps)
show_runner.settle_acts(d, bots, oa, {"2": {"type": "explore", "say": "", "src": "haiku"}}, reps)
check("⑦ 같은 결정에 제안·친목 반응이 나란히(둘 다 없음)",
      reps == [{"from": "2", "to": "1", "kind": "제안", "how": "없음"}, {"from": "2", "to": "1", "kind": "친목", "how": "없음"}]
      and acts(b2, "1")[-1]["reply"] == "없음")
check("⑦ 폴백·건너뜀 결정은 형태 '없음'으로 닫힌다",
      show_runner.settle_acts(d, bots, {"2": {"1": "친목"}}, {"2": {"say": "", "src": "fallback"}}, [])[0]["how"] == "없음"
      and show_runner.settle_acts(d, bots, {"2": {"1": "친목"}}, {"2": {"type": "goto", "skipped": True}}, []) == [])

print("── ⑧ 관측·렌더")
d, bots = scene()
b1, b2, b3 = bots
res = d.act(b1, {"type": "bond", "target": "b2", "form": "머리 쓰다듬기"}, bots)
d.note_reply(b2, b1, "말")
o1 = d.view(b1, bots)
r1 = next((r for r in (o1.get("relations") or []) if r.get("char") == "2"), {})
check("⑧ view 관계 obs: 뼈 '친목행위 ×1' + acts",
      any(b_.get("label") == "친목행위" and b_.get("n") == 1 for b_ in r1.get("bones", []))
      and r1.get("acts") == [{"turn": 5, "kind": "친목", "what": "머리 쓰다듬기", "mine": True, "reply": "말"}])
w1 = brains._wire(o1, NAMES)
o2 = d.view(b2, bots)
w2 = brains._wire(o2, NAMES)
check("⑧ wire 양쪽 시점: '내가 … → 답: 말로' / '두란(봇1)가 … → 내 답: 말로'",
      "- 카야(봇2): 친목행위 ×1 (" in w1 and "· 최근 친목·건네기: t5 내가 머리 쓰다듬기 → 답: 말로" in w1
      and "· 최근 친목·건네기: t5 두란(봇1)가 머리 쓰다듬기 → 내 답: 말로" in w2)
for i in range(6):
    d.act(b1, {"type": "bond", "target": "b2", "form": "포옹 %d" % i}, bots)
o1b = d.view(b1, bots)
r1b = next((r for r in (o1b.get("relations") or []) if r.get("char") == "2"), {})
check("⑧ obs 의 acts 는 최근 ACTS_SHOW 건", len(r1b.get("acts") or []) == 4 and r1b["acts"][-1]["what"] == "포옹 5")
check("⑧ _last_prose 한 쪽/받은 쪽/실패",
      brains._last_prose(res, NAMES) == "카야(봇2)에게 몸짓을 했다 — 머리 쓰다듬기"
      and brains._last_prose({"type": "bonded", "from": "1", "form": "머리 쓰다듬기"}, NAMES) == "두란(봇1)가 너에게 몸짓을 했다 — 머리 쓰다듬기"
      and brains._last_prose({"type": "bond", "result": "too_far"}, NAMES) == "몸짓을 하려 했지만 — 곁에 없었다")
check("⑧ event_tags [친목] / [친목 받음]",
      G.event_tags(res, NAMES) == [("bond", "친목", "머리 쓰다듬기 → 카야")]
      and G.event_tags({"type": "bonded", "from": "1", "form": "머리 쓰다듬기"}, NAMES) == [("bonded", "친목 받음", "두란: 머리 쓰다듬기")])
d, bots = scene()
b1, b2, b3 = bots
d.act(b1, {"type": "bond", "target": "b2", "form": "머리 쓰다듬기"}, bots)
w = (d.view(b3, bots).get("witnessed") or [{}])[0]
check("⑧ 목격 문장 · act_summary · _hist_item · 직전 판단",
      brains._witness_prose(w) == "두란(봇1)가 카야(봇2)에게 몸짓하는 것을 — 머리 쓰다듬기"
      and show_runner.act_summary({"type": "bond", "result": "done", "to": "2", "form": "머리 쓰다듬기"}) == "봇2에게 친목 — 머리 쓰다듬기"
      and brains._hist_item({"type": "bond", "target": "b2", "form": "머리 쓰다듬기", "turn": 5}) == "친목 b2 [머리 쓰다듬기] (t5)")
o1 = d.view(b1, bots)
o1["intent"] = {"type": "bond", "target": "b2", "form": "머리 쓰다듬기", "turn": 5, "reason": "x"}
check("⑧ wire 직전 판단에 몸짓", "직전 판단(t5): bond b2 [머리 쓰다듬기]" in brains._wire(o1, NAMES))

print("── ⑨ think_all")
d, bots = scene()
b1, b2, b3 = bots
n_bond = opts(d, b1, bots)[0]["n"]
brains._call_claude = lambda prompt, model="haiku": '{"reason": "x", "choice": %d, "say": "", "form": " 어깨  두드리기 "}' % n_bond
out = brains.think_all(d, bots)
check("⑨ 메뉴 번호+form → dec {bond, b2, form 정제} · intent/history 에 form",
      out["1"].get("type") == "bond" and out["1"].get("target") == "b2" and out["1"].get("form") == "어깨 두드리기"
      and b1["intent"].get("form") == "어깨 두드리기" and (b1.get("history") or [{}])[-1].get("form") == "어깨 두드리기")
res = d.act(b1, out["1"], bots)
check("⑨ 집행: done · 카야 bonded", res.get("result") == "done" and (b2.get("last") or {}).get("form") == "어깨 두드리기")
brains._call_claude = lambda prompt, model="haiku": '{"reason": "x", "choice": %d, "say": "고마워", "to": "2"}' % n_bond
d, bots = scene()
out = brains.think_all(d, bots)
res = d.act(bots[0], out["1"], bots)
check("⑨ form 없는 응답: dec 에 form '' → 엔진 '몸짓' · 말은 그대로 실린다",
      out["1"].get("form") == "" and res.get("form") == "몸짓" and out["1"].get("say") == "고마워")
brains._call_claude = lambda prompt, model="haiku": '{"reason": "x", "choice": 1, "say": "", "form": "포옹"}'
d, bots = scene()
out = brains.think_all(d, bots)
check("⑨ 친목이 아닌 선택엔 form 이 안 실린다", "form" not in out["1"] or out["1"].get("type") == "bond")

print("── ⑩ 지침·배선(소스)")
import io as _io                                     # noqa: E402
mp = brains.MENU_PROMPT
check("⑩ 지침: 친목 절(어깨 두드리기·머리 쓰다듬기·포옹) · `form` 필드 설명 · 반응은 상대 몫 · 내 문장 제거",
      "- **친목**: 어깨 두드리기, 손잡기, 머리 쓰다듬기, 포옹처럼 곁에서 하는 몸짓" in mp
      and "`form` = **친목의 몸짓**" in mp and "시도했다고 상대의 반응까지 정해지진 않는다" in mp and "답이 필요할 때만" not in mp)
rsrc = _io.open(os.path.join(HERE, "show_runner.py"), encoding="utf-8").read()
check("⑩ 러너: DUNGEON_BOND · bond=BOND_ON · build_town 미러링 · act_summary bond",
      'DUNGEON_BOND' in rsrc and 'bond=BOND_ON' in rsrc and 'd.give_verb, d.bond_verb = GIVE_ON, BOND_ON' in rsrc
      and 'if t == "bond":' in rsrc)
ssrc = _io.open(os.path.join(HERE, "scenario.py"), encoding="utf-8").read()
vsrc = _io.open(os.path.join(HERE, "viewer", "index.html"), encoding="utf-8").read()
check("⑩ scenario 미러링 · 뷰어 친목 줄", '("bond_verb", "DUNGEON_BOND")' in ssrc and "t === 'bond'" in vsrc)

print()
if C.failed:
    print("FAIL — %d개 실패" % C.failed)
    raise SystemExit(1)
print("ALL PASS — verify_bond (D47 ② 친목: form 자유 문구·메뉴·물리 없음·무정지/깨움·목격·뼈·상세 기록+반응·렌더·배선)")

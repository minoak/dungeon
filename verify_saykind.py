# -*- coding: utf-8 -*-
"""말의 종류(D47, 2026-09-08 파트너 "'제안'이라는 대화는 캐릭터를 멈추게 하고 명확한 요구를 한다 — 일반 대화는 굳이 멈출 필요가
없다" → 첫 묶음 = 잡담·제안 2종 + 상대 반응 기록) 검증 — 41번째 게이트. LLM 0콜.
응답 JSON 정식 필드 `say_kind` ∈ 잡담(기본)|제안. 배달(들림)은 그대로 시야 안 전원, **정지(말 걸림)는 제안만**: to=번호 → 그 사람만,
대상 없음·all → 회의(시야 안 전원). 잡담은 들리기만(지목·방송 잡담은 D36 talk 뼈). 제안은 제 뼈(proposed/asked)로 따로 세고, 상대의
다음 결정에서 답했으면(answered/replied) 닫힌다 — 답하기 전 같은 사람의 재제안은 안 세운다(반복 방지). 걷는 동안 들린 말은 다음
결정까지 보관(배관, 437987d 재사용). 파트너 되물음 답: 제안 받으면 판단을 새로(자동 재개 없음) · 회의는 시야 안 인원만.
게이트:
  ① brains._parse_kind: 제안·요청·부탁·propose·request·ask → '제안' / 빈 값·모르는 값·잡담 → '잡담'
  ② 스위치·상수: SAYKIND_ON/PENDING_ON 러너 기본 1 · PENDING_MAX 6 · 엔진 BONES 에 4종 라벨 · 꺼진 판 note_proposal/note_answer 무동작
  ③ 잡담 지목: 배달 O(turn 스탬프·kind 없음) · 정지 0 · talk 뼈(지목 쌍만)
  ④ 제안 지목: 지목된 사람만 정지 · inbox kind=제안 · proposed/asked 뼈 · talk 0 · open 장부
  ⑤ 회의(대상 없음·all): 시야 안 전원 정지 · 각각 asked · 시야 밖은 배달도 정지도 없음(파트너 "회의는 시야 내 인원")
  ⑥ 반복 방지: 답하기 전 같은 사람의 재제안 = 정지 0·뼈 0 · 답한 뒤엔 D24 쿨다운(HAIL_CD) 지나 다시 선다
  ⑦ settle_proposals: 받은 봇의 첫 결정에서 닫힘 — 한 사람(또는 모두)에게 말하면 answered/replied, 아니면 뼈 없이 닫힘, 작정 집행은 유지
  ⑧ 배관: merge_inbox(보관+이번, 상한)·keep_pending(읽은 봇 비움·작정 집행·걷던 봇 보관)
  ⑨ wire: "(너에게 제안)"/"(모두에게 제안 — 회의)"/"(카야에게 제안)"/잡담 "(너에게)" · " — N턴 전" · 대화 장부 "(t5, 제안)" · 직전 판단 "(제안)"
  ⑩ claude_brain/think_all: say_kind 파싱(제안·기본 잡담·말 없으면 필드 없음) · intent·대화 장부에 종류
  ⑪ 스냅샷·관측: bot_snapshot relations 에 proposed 등 횟수 · view() 관계 obs 라벨 '제안함'
  ⑫ 러너 배선(소스): 스위치·settle·run_meta·보관 병합·층 전이 리셋·tick.answers
  ⑬ 스위치 off = D41 판(제안이든 잡담이든 지목이면 정지·talk 뼈, kind 미기록)
(기존 verify 40종은 별도 실행.)
"""
import os
import tempfile

os.environ.update(DUNGEON_GM="0", DUNGEON_TURNS="4", DUNGEON_W="40", DUNGEON_H="16",
                  DUNGEON_SEED="7", DUNGEON_MONSTERS="0", DUNGEON_TRAPS="0", DUNGEON_LURKERS="0",
                  DUNGEON_DEPTHS="1", DUNGEON_BESTIARY_FILE="",
                  DUNGEON_STATE_DIR=os.path.join(tempfile.mkdtemp(prefix="wl_saykind_"), "state"))
os.environ.pop("DUNGEON_PARTY_FILE", None)

import brains                                        # noqa: E402
import dungeon_gm as G                               # noqa: E402
from dungeon_gm import Dungeon                       # noqa: E402
import show_runner                                   # noqa: E402
show_runner.STEP_DELAY = 0


class C:
    failed = 0


def check(name, cond):
    print(("  OK   " if cond else " FAIL  ") + name)
    if not cond:
        C.failed += 1


ROWS = ["############",
        "#1.2.3....>#",
        "############"]
ROSTER = [{"char": "1", "name": "두란"}, {"char": "2", "name": "카야"}, {"char": "3", "name": "피른"}]
NAMES = {"1": "두란", "2": "카야", "3": "피른"}
OBS = {"sights": {"bots": [{"char": "2"}, {"char": "3"}]}}


def scene(hail=True, relations=True, far3=False):
    d, st = Dungeon.from_ascii(ROWS, seed=7)
    d.hail, d.relations, d.events = hail, relations, True
    bots = []
    for c in "123":
        b = G.spawn(d, c, bots, sheet=G.HEROES.get(c) or G.HEROES['1'])
        b["x"], b["y"] = st[c]
        b["name"] = NAMES[c]
        bots.append(b)
    if far3:
        bots[2]["x"] = 10                        # 피른을 시야(SIGHT=5) 밖으로 — 카야(x=3)와 7칸
    d.turn = 5
    for b in bots:
        b["order"], b["path"] = "exit", [(b["x"] + 1, b["y"])]   # 전원 '걷는 중'(말 걸림 대상)
    return d, bots


def bone(b, oc, kind):
    return (((b.get("relations") or {}).get(oc) or {}).get("bones") or {}).get(kind, {}).get("n", 0)


def walking(b):
    return b.get("order") == "exit"


print("── ① _parse_kind")
pk = brains._parse_kind
check("① 제안·요청·부탁·propose·request·ASK → '제안'",
      all(pk(x) == "제안" for x in ("제안", "제안: 같이 가자", "요청", "부탁", "propose", "proposal", "request", "ASK")))
check("① 빈 값·None·잡담·chat·모르는 값 → '잡담'",
      all(pk(x) == "잡담" for x in ("", None, "잡담", "chat", "헛소리", 0)))

print("── ② 스위치·상수·엔진 뼈")
check("② 러너 기본: SAYKIND_ON·PENDING_ON 켬 · PENDING_MAX=6",
      show_runner.SAYKIND_ON is True and show_runner.PENDING_ON is True and show_runner.PENDING_MAX == 6)
check("② 엔진 BONES 에 proposed/asked/answered/replied 라벨(기존 5종 유지)",
      all(k in G.BONES for k in ("proposed", "asked", "answered", "replied"))
      and all(k in G.BONES for k in ("talk", "fought", "waited", "rescued", "at_death"))
      and G.BONES["proposed"] == "제안함" and G.BONES["asked"] == "제안받음"
      and not any(k in G.STRONG_BONES for k in ("proposed", "asked", "answered", "replied")))
d0, bots0 = scene(relations=False)
d0.note_proposal(bots0[1], bots0[0]); d0.note_answer(bots0[1], bots0[0])
check("② 관계 장부 꺼진 판: note_proposal/note_answer 무동작",
      not (bots0[0].get("relations") or {}) and not (bots0[1].get("relations") or {}))

print("── ③ 잡담 지목 = 들리기만")
d, bots = scene()
op = {}
inbox, hails = show_runner.deliver_and_hail(d, bots, {"2": "두란, 여기 어둡네"}, {"2": "1"}, {"2": "잡담"}, op)
check("③ 배달 O(1·3, turn 스탬프, kind 없음) · 정지 0 · 전원 걷던 길 유지 · open 장부 없음",
      [m["from"] for m in inbox["1"]] == ["2"] and [m["from"] for m in inbox["3"]] == ["2"]
      and inbox["1"][0].get("turn") == 5 and "kind" not in inbox["1"][0] and inbox["1"][0].get("to") == "1"
      and hails == {} and all(walking(b) for b in bots) and op == {})
check("③ talk 뼈는 지목 쌍(1↔2)만 · 제안 뼈 0",
      bone(bots[0], "2", "talk") == 1 and bone(bots[1], "1", "talk") == 1 and bone(bots[2], "2", "talk") == 0
      and bone(bots[0], "2", "asked") == 0 and bone(bots[1], "1", "proposed") == 0)
d, bots = scene()
inbox, hails = show_runner.deliver_and_hail(d, bots, {"2": "다들 모여!"}, {"2": "all"}, {"2": "잡담"}, {})
check("③ 방송 잡담(all): 정지 0 · talk 뼈는 1·3 다(D41 방송=지목)",
      hails == {} and all(walking(b) for b in bots) and bone(bots[0], "2", "talk") == 1 and bone(bots[2], "2", "talk") == 1)
d, bots = scene()
inbox, hails = show_runner.deliver_and_hail(d, bots, {"2": "으, 어둡네"}, {}, {"2": "잡담"}, {})
check("③ 혼잣말 잡담: 배달 O · 정지 0 · 뼈 0",
      inbox["1"] and hails == {} and bone(bots[0], "2", "talk") == 0)

print("── ④ 제안 지목 = 그 사람만 선다")
d, bots = scene()
op = {}
inbox, hails = show_runner.deliver_and_hail(d, bots, {"2": "두란, 이쪽 문부터 보자"}, {"2": "1"}, {"2": "제안"}, op)
check("④ 들리긴 전원(kind=제안 표식) · 멈춤은 지목된 1만 · 3은 걷던 길 유지",
      inbox["1"][0].get("kind") == "제안" and inbox["3"][0].get("kind") == "제안"
      and hails == {"1": ["2"]} and bots[0].get("order") is None and walking(bots[2]))
check("④ 뼈: 카야 proposed→1 ×1 · 두란 asked←2 ×1 · talk 0 · 피른 무관",
      bone(bots[1], "1", "proposed") == 1 and bone(bots[0], "2", "asked") == 1
      and bone(bots[0], "2", "talk") == 0 and bone(bots[1], "1", "talk") == 0
      and bone(bots[2], "2", "asked") == 0 and bone(bots[1], "3", "proposed") == 0)
check("④ open 장부: {'1': {'2': 5}}", op == {"1": {"2": 5}})
check("④ 궤적/last: 두란의 정지 사유는 말 걸림(hail) — 엔진 문법 그대로",
      (bots[0].get("last") or {}).get("type") == "hail" and (bots[0]["last"].get("froms") == ["2"]))

print("── ⑤ 회의 = 대상 없는 제안 → 시야 안 전원")
d, bots = scene()
op = {}
inbox, hails = show_runner.deliver_and_hail(d, bots, {"2": "잠깐, 계단부터 정하자"}, {}, {"2": "제안"}, op)
check("⑤ 대상 없음: 1·3 모두 정지 · 각각 asked ×1 · 카야 proposed→1·→3 각 1 · open 둘",
      hails == {"1": ["2"], "3": ["2"]} and bots[0].get("order") is None and bots[2].get("order") is None
      and bone(bots[0], "2", "asked") == 1 and bone(bots[2], "2", "asked") == 1
      and bone(bots[1], "1", "proposed") == 1 and bone(bots[1], "3", "proposed") == 1
      and op == {"1": {"2": 5}, "3": {"2": 5}})
d, bots = scene()
inbox, hails = show_runner.deliver_and_hail(d, bots, {"2": "다들 모여"}, {"2": "all"}, {"2": "제안"}, {})
check("⑤ to=all 제안도 회의: 1·3 정지", hails == {"1": ["2"], "3": ["2"]})
d, bots = scene(far3=True)
op = {}
inbox, hails = show_runner.deliver_and_hail(d, bots, {"2": "잠깐, 계단부터 정하자"}, {}, {"2": "제안"}, op)
check("⑤ 시야 밖(피른 7칸): 배달 없음 · 정지 없음 · 뼈 없음 · open 에도 없음 — 회의는 시야 안 인원만",
      inbox["3"] == [] and hails == {"1": ["2"]} and walking(bots[2]) and bone(bots[2], "2", "asked") == 0
      and op == {"1": {"2": 5}})

print("── ⑥ 반복 방지 — 답하기 전 재제안은 안 세운다")
d, bots = scene()
op = {}
inbox, hails = show_runner.deliver_and_hail(d, bots, {"2": "두란, 이쪽 문부터"}, {"2": "1"}, {"2": "제안"}, op)
bots[0]["order"], bots[0]["path"] = "exit", [(bots[0]["x"] + 1, bots[0]["y"])]   # (가정) 두란이 안 답하고 다시 걷는다
d.turn = 6
inbox2, hails2 = show_runner.deliver_and_hail(d, bots, {"2": "두란! 문부터 보자니까"}, {"2": "1"}, {"2": "제안"}, op)
check("⑥ 응답 전 재제안(t6): 배달 O · 정지 0 · proposed/asked 그대로 ×1 · open 유지(t5)",
      inbox2["1"] and inbox2["1"][0].get("kind") == "제안" and hails2 == {} and walking(bots[0])
      and bone(bots[1], "1", "proposed") == 1 and bone(bots[0], "2", "asked") == 1 and op == {"1": {"2": 5}})
ans = show_runner.settle_proposals(d, bots, op, {"1": {"say": "알았다, 문은 내가 연다", "to": "2", "src": "haiku"}})
check("⑥ 두란이 답함(t6 결정, to=2): answered/replied 뼈 · open 닫힘 · 반환 {'1': {'2': True}}",
      ans == {"1": {"2": True}} and op == {"1": {}} and bone(bots[1], "1", "answered") == 1 and bone(bots[0], "2", "replied") == 1)
d.turn = 7
inbox3, hails3 = show_runner.deliver_and_hail(d, bots, {"2": "두란, 그럼 상자는?"}, {"2": "1"}, {"2": "제안"}, op)
check("⑥ 답한 뒤 새 제안(t7): 새 시도라 proposed ×2·open 다시 열림 — 정지는 D24 쿨다운(HAIL_CD=3, t5+3=8)에 막혀 0",
      bone(bots[1], "1", "proposed") == 2 and op == {"1": {"2": 7}} and hails3 == {} and walking(bots[0]))
show_runner.settle_proposals(d, bots, op, {"1": {"say": "", "src": "haiku"}})
d.turn = 8
inbox4, hails4 = show_runner.deliver_and_hail(d, bots, {"2": "두란, 상자 열자"}, {"2": "1"}, {"2": "제안"}, op)
check("⑥ 쿨다운 지난 뒤(t8) 새 제안: 다시 선다", hails4 == {"1": ["2"]} and bots[0].get("order") is None)

print("── ⑦ settle_proposals — 받은 봇의 첫 결정에서 닫힌다")
d, bots = scene()
op = {"1": {"2": 5, "3": 5}}
ans = show_runner.settle_proposals(d, bots, op, {"1": {"say": "가자", "to": "3", "src": "haiku"}})
check("⑦ 한 사람(3)에게만 답함: 3=True·2=False 둘 다 닫힘 · answered 는 3↔1 만",
      ans == {"1": {"2": False, "3": True}} and op == {"1": {}}
      and bone(bots[2], "1", "answered") == 1 and bone(bots[0], "3", "replied") == 1
      and bone(bots[1], "1", "answered") == 0 and bone(bots[0], "2", "replied") == 0)
d, bots = scene()
op = {"1": {"2": 5}}
ans = show_runner.settle_proposals(d, bots, op, {"1": {"say": "다들 잠깐", "to": "all", "src": "haiku"}})
check("⑦ 모두에게 답함(all) = 답함", ans == {"1": {"2": True}} and bone(bots[1], "1", "answered") == 1)
d, bots = scene()
op = {"1": {"2": 5}}
ans = show_runner.settle_proposals(d, bots, op, {"1": {"say": "", "src": "fallback"}})
check("⑦ 말 없이 결정(폴백 포함) = 답 없이 닫힘", ans == {"1": {"2": False}} and op == {"1": {}} and bone(bots[1], "1", "answered") == 0)
d, bots = scene()
op = {"1": {"2": 5}}
ans = show_runner.settle_proposals(d, bots, op, {"1": {"say": "", "src": "plan"}, "3": {"say": "응", "to": "2", "src": "haiku"}})
check("⑦ 작정 집행(plan)은 안 읽음 → 열어 둠 · 제안 안 받은 봇(3)은 무관", ans == {} and op == {"1": {"2": 5}})

print("── ⑧ 배관 — 걷는 동안 들린 말은 다음 결정까지")
m_old = {"from": "2", "text": "아까 말", "to": "all", "turn": 3}
m_new = {"from": "3", "text": "지금 말", "to": "1", "turn": 5}
m_x = {"from": "1", "text": "걷는 애에게", "to": "all", "turn": 5}
merged = show_runner.merge_inbox({"1": [m_old]}, {"1": [m_new], "2": [m_x], "3": []})
check("⑧ 병합: 보관된 말 + 이번 말(오래된 것부터), 없는 봇은 그대로", merged == {"1": [m_old, m_new], "2": [m_x], "3": []})
kept = show_runner.keep_pending(merged, {"1": {"src": "haiku"}, "2": {"src": "plan"}})
check("⑧ 소비: 결정한 봇은 비움 · 작정 집행 봇(안 읽음)·걷던 봇은 보관", kept == {"1": [], "2": [m_x], "3": []})
check("⑧ 상한: 오래된 것부터 바랜다(cap 2)",
      show_runner.merge_inbox({"1": [m_old, m_old, m_old]}, {"1": [m_new]}, cap=2)["1"] == [m_old, m_new])

print("── ⑨ wire 렌더")
base = {"job": "전사", "sex": "남", "hp": 9, "maxhp": 14, "str": 3, "dex": 1, "inventory": 0, "depth": 1, "pos": [5, 5], "turn": 9,
        "sights": {"exit": None, "features": [], "monsters": [], "ways": [], "bots": []},
        "party": [], "options": [], "ascii_view": ["@"], "legend": {},
        "messages": [{"from": "2", "text": "이쪽 문부터", "to": "1", "to_me": True, "kind": "제안", "turn": 8},
                     {"from": "3", "text": "계단부터 정하자", "kind": "제안", "turn": 8},
                     {"from": "2", "text": "피른아 같이", "to": "3", "kind": "제안", "turn": 8},
                     {"from": "3", "text": "어둡네", "to": "1", "to_me": True, "turn": 8},
                     {"from": "2", "text": "아까 한 말", "to": "all", "turn": 5}],
        "dialogue": [{"turn": 5, "from": "2", "to": "1", "text": "문 보자", "to_me": True, "kind": "제안"},
                     {"turn": 6, "from": "1", "to": "2", "text": "알았다", "mine": True}],
        "intent": {"type": "goto", "target": "d0", "say": "문은 내가 연다", "to": "2", "say_kind": "제안", "turn": 6}}
txt = brains._wire(base, NAMES)
check("⑨ 동료가 한 말: (너에게 제안) / (모두에게 제안 — 회의) / (피른에게 제안) / 잡담 (너에게) / 옛 말 ' — 4턴 전'",
      '카야(봇2): "이쪽 문부터" (너에게 제안)' in txt and '피른(봇3): "계단부터 정하자" (모두에게 제안 — 회의)' in txt
      and '카야(봇2): "피른아 같이" (피른(봇3)에게 제안)' in txt and '피른(봇3): "어둡네" (너에게)\n' in txt + "\n"
      and '카야(봇2): "아까 한 말" (모두에게) — 4턴 전' in txt)
check("⑨ 머리글: 너를 세운 건 제안뿐 · 대화 장부 '(t5, 제안)' · 내 말은 표식 없음 · 직전 판단의 말 '(제안)'",
      "## 동료가 한 말 (걷는 동안 들린 것까지 — 오래된 것부터. 너를 세운 건 제안뿐이다)" in txt
      and '카야(봇2)→나 (t5, 제안): "문 보자"' in txt and '나→카야(봇2) (t6): "알았다"' in txt
      and '그때 동료에게 한 말 (제안): "문은 내가 연다"' in txt)

print("── ⑩ 응답 파싱·intent·대화 장부")
brains._call_claude = lambda prompt, model="haiku": '{"reason": "x", "choice": 1, "say": "카야, 이리 와", "to": "카야", "say_kind": "제안"}'
dt, botst = scene()
for b in botst:
    b["order"], b["path"] = None, []
out = brains.think_all(dt, botst)
check("⑩ say_kind=제안 → dec.say_kind='제안' · to=2 · intent 에 say_kind · 내 말 장부에 kind",
      out["1"].get("say_kind") == "제안" and out["1"].get("to") == "2" and botst[0]["intent"].get("say_kind") == "제안"
      and any(m.get("mine") and m.get("kind") == "제안" for m in botst[0].get("dialogue") or []))
brains._call_claude = lambda prompt, model="haiku": '{"reason": "x", "choice": 1, "say": "흠, 어둡군", "to": "2"}'
dt, botst = scene()
for b in botst:
    b["order"], b["path"] = None, []
out = brains.think_all(dt, botst, {"1": [{"from": "2", "text": "문 보자", "to": "1", "kind": "제안", "turn": 3}]})
check("⑩ 필드 없음 → '잡담' · 들은 제안은 장부에 kind·제 turn(3)",
      out["1"].get("say_kind") == "잡담" and any(m.get("kind") == "제안" and m.get("turn") == 3 and m.get("to_me")
                                                for m in botst[0].get("dialogue") or []))
brains._call_claude = lambda prompt, model="haiku": '{"reason": "x", "choice": 1, "say": "", "say_kind": "제안"}'
dt, botst = scene()
for b in botst:
    b["order"], b["path"] = None, []
out = brains.think_all(dt, botst)
check("⑩ 말이 없으면 say_kind 도 없다(제안이라 적어도)", "say_kind" not in out["1"] and "to" not in out["1"])
check("⑩ 지침: say_kind 필드·잡담·제안·회의 문장이 리모컨 지침에 있다",
      "`say_kind`" in brains.MENU_PROMPT and "잡담" in brains.MENU_PROMPT and "회의" in brains.MENU_PROMPT
      and "상대의 진행 중인 행동은 취소하지 않는다" in brains.MENU_PROMPT)

print("── ⑪ 스냅샷·관측")
d, bots = scene()
show_runner.deliver_and_hail(d, bots, {"2": "두란, 이쪽 문부터"}, {"2": "1"}, {"2": "제안"}, {})
snap = G.bot_snapshot(bots[0])
check("⑪ bot_snapshot relations: {'2': {'asked': 1}}", snap.get("relations") == {"2": {"asked": 1}})
bots[0]["order"], bots[0]["path"] = None, []
o = d.view(bots[0], bots)
rel = next((r for r in (o.get("relations") or []) if r.get("char") == "2"), None)
check("⑪ view 관계 obs: 뼈 라벨 '제안받음' ×1", rel is not None and any(b_.get("kind") == "asked" and b_.get("label") == "제안받음" and b_.get("n") == 1
                                                                   for b_ in rel.get("bones", [])))
check("⑪ wire 관계 절: '카야(봇2): 제안받음 ×1'", "제안받음 ×1" in brains._wire(o, NAMES))

print("── ⑫ 러너 배선(소스)")
import io as _io                                     # noqa: E402
rsrc = _io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "show_runner.py"), encoding="utf-8").read()
check("⑫ 스위치·settle·run_meta·병합·보관·리셋·answers 계측 배선",
      'DUNGEON_SAYKIND' in rsrc and 'DUNGEON_PENDING' in rsrc and 'settle_proposals(d, bots, open_props, decisions)' in rsrc
      and 'say_kind=SAYKIND_ON' in rsrc and 'pending=PENDING_ON' in rsrc and 'merge_inbox(pending, inbox)' in rsrc
      and 'keep_pending(inbox, decisions)' in rsrc and rsrc.count('open_props = {}') == 2
      and 'deliver_and_hail(d, bots, says, say_to, say_kind, open_props)' in rsrc and '"answers": answers' in rsrc)

print("── ⑬ 스위치 off = D41 판")
show_runner.SAYKIND_ON = False
d, bots = scene()
op = {}
inbox, hails = show_runner.deliver_and_hail(d, bots, {"2": "두란, 여기 어둡네"}, {"2": "1"}, {"2": "잡담"}, op)
check("⑬ off: 지목 잡담도 세운다(D41) · talk 뼈 · kind 미기록 · open 없음",
      hails == {"1": ["2"]} and bone(bots[0], "2", "talk") == 1 and "kind" not in inbox["1"][0] and op == {})
d, bots = scene()
inbox, hails = show_runner.deliver_and_hail(d, bots, {"2": "잠깐"}, {}, {"2": "제안"}, op)
check("⑬ off: 대상 없는 제안은 혼잣말(회의 없음)", hails == {} and op == {})
show_runner.SAYKIND_ON = True

print()
if C.failed:
    print("FAIL — %d개 실패" % C.failed)
    raise SystemExit(1)
print("ALL PASS — verify_saykind (D47 말의 종류: 잡담/제안 파싱·정지는 제안만·회의=시야 안·반복 방지·반응 뼈·배관·렌더·스위치)")

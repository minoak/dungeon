# -*- coding: utf-8 -*-
"""건네기(D47 ②, 2026-09-09 파트너 "건네기를 만들려면 아이템 거래를 넣어야 해" · "제안은 열리게 하는 대신 응답에서 제안 승낙 시
선택지 안에서 행동할 수 있게") 검증 — 42번째 게이트. LLM 0콜.
곁(체비셰프≤1)의 동료에게 소지품(물약·무기·방어구)을 넘기는 즉시 동사. 메뉴 줄이 물건(item)을 정하고 엔진이 옮긴다(굴림 없음).
상대는 안 선다(걷는 동료는 다음 결정에서 '받음'을 읽는다), 대기·휴식 중이면 깨운다. 뼈 gave/received, 목격 ally_give, 상세 기록
(acts)에 반응 칸. 제안의 승낙은 말이 아니라 행동 — classify_reply(행동|말|없음)가 제안·친목·건네기에 같은 자로 붙는다.
게이트:
  ① 상수·스위치: BONES gave/received · EVENT_KINDS · WITNESS_LABELS · ITEM_KR · 엔진 기본 꺼짐(__init__·from_ascii) · 러너 기본 1
  ② 메뉴: 곁의 동료에게만 물건마다 한 줄(item 동봉) · 2칸 밖 없음 · 상대 슬롯 상태 라벨 · 꺼진 판·솔로 판 없음 · _pick 이 item 복사
  ③ 물약 물리: −1/+1 · 결과(given,to,what,potions) · 받은 쪽 last/궤적(received) · 목격(ally_give, 둘 제외) · 뼈 · acts 양쪽 · 층 집계
  ④ 장비 물리: 빈 슬롯=걸침(equipped) · 찬 슬롯=발밑 피처(placed) · 둘 다 찼으면 no_room(소지 유지)
  ⑤ 실패: too_far(2칸) · no_target · nothing(빈손) · 꺼진 판=nothing(이동 없음)
  ⑥ 정지 물리: 걷는 상대는 안 선다 · 대기·휴식 상대는 깬다
  ⑦ 표현: _last_prose(한 쪽·받은 쪽·실패) · event_tags [건넴]/[받음] · _witness_prose · act_summary · _hist_item · wire 직전 판단
  ⑧ 러너: classify_reply 7례 · settle_acts(첫 결정에서 닫힘·note_reply 양쪽·replies) · settle_proposals 의 행동 답(answered+뼈+replies)
  ⑨ think_all: 메뉴 번호 → dec.item · intent/history 에 item · bot_snapshot relations gave/received
  ⑩ 배선(소스): 러너 스위치·Dungeon 인자 2곳·run_meta·장부·리셋·이월 / scenario.py 미러링·potions 프리셋·프로브 출력 / 지침 문장
(기존 verify 41종은 별도 실행.)
"""
import os
import tempfile

os.environ.update(DUNGEON_GM="0", DUNGEON_TURNS="4", DUNGEON_W="40", DUNGEON_H="16",
                  DUNGEON_SEED="7", DUNGEON_MONSTERS="0", DUNGEON_TRAPS="0", DUNGEON_LURKERS="0",
                  DUNGEON_DEPTHS="1", DUNGEON_BESTIARY_FILE="",
                  DUNGEON_STATE_DIR=os.path.join(tempfile.mkdtemp(prefix="wl_give_"), "state"))
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


def scene(give=True, bond=True, relations=True, solo=False):
    d, st = Dungeon.from_ascii(ROWS, seed=7)
    d.events, d.relations, d.trail_on, d.floor_on = True, relations, True, True
    d.give_verb, d.bond_verb, d.solo = give, bond, solo
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


def opts(d, b, bots, typ="give"):
    return [o for o in d.view(b, bots)["options"] if o["type"] == typ]


print("── ① 상수·스위치")
check("① BONES gave/received 라벨 · 강한 뼈 아님",
      G.BONES.get("gave") == "물건을 건넴" and G.BONES.get("received") == "물건을 받음"
      and not any(k in G.STRONG_BONES for k in ("gave", "received")))
check("① EVENT_KINDS give/received 집계 · WITNESS_LABELS ally_give · ITEM_KR",
      G.EVENT_KINDS.get("give") is True and G.EVENT_KINDS.get("received") is True
      and G.WITNESS_LABELS.get("ally_give") == "동료 건넴" and G.ITEM_KR == {"potion": "회복 물약", "weapon": "무기", "armor": "방어구"})
d_def = Dungeon(seed=7, w=30, h=12)
d_asc, _ = Dungeon.from_ascii(ROWS, seed=7)
check("① 엔진 기본 꺼짐(__init__·from_ascii) · 러너 기본 켬",
      d_def.give_verb is False and d_asc.give_verb is False and show_runner.GIVE_ON is True)

print("── ② 메뉴")
d, bots = scene()
b1, b2, b3 = bots
b1["potions"], b1["weapon"] = 2, {"name": "단검", "bonus": 1}
gs = opts(d, b1, bots)
check("② 곁의 카야(봇2)에게 물약·단검 두 줄(item 동봉) · 2칸 밖 피른 없음 · 방어구 없음",
      [(o["target"], o["item"]) for o in gs] == [("b2", "potion"), ("b2", "weapon")]
      and "회복 물약 → 카야(봇2) (곁, 소지 2병)" in gs[0]["label"] and "단검 → 카야(봇2)" in gs[1]["label"]
      and "그가 바로 걸친다" in gs[1]["label"])
b2["weapon"] = {"name": "장검", "bonus": 2}
gs2 = opts(d, b1, bots)
check("② 상대 슬롯이 차 있으면 라벨이 '발밑에 놓인다'를 말한다", any("무기 자리가 차 있어 발밑에 놓인다" in o["label"] for o in gs2))
check("② 즉시행동군 자리: 이동(goto) 줄보다 앞", (lambda os_: min(i for i, o in enumerate(os_) if o["type"] == "give")
                                                     < min(i for i, o in enumerate(os_) if o["type"] == "goto"))(d.view(b1, bots)["options"]))
check("② 피른(봇3)의 메뉴엔 건네기 없음(곁에 아무도 없다)", opts(d, b3, bots) == [] if not b3.get("potions") else False)
d_off, bots_off = scene(give=False)
bots_off[0]["potions"] = 1
check("② 꺼진 판: 건네기 줄 없음", opts(d_off, bots_off[0], bots_off) == [])
d_solo, bots_solo = scene(solo=True)
bots_solo[0]["potions"] = 1
check("② 솔로 판: 건네기 줄 없음(남남)", opts(d_solo, bots_solo[0], bots_solo) == [])
o = d.view(b1, bots)
pick = brains._pick({"choice": gs[0]["n"]}, o)
check("② _pick 이 item 을 복사한다", pick == {"type": "give", "choice": gs[0]["n"], "target": "b2", "item": "potion"})

print("── ③ 물약 물리")
d, bots = scene()
b1, b2, b3 = bots
b1["potions"] = 2
res = d.act(b1, {"type": "give", "target": "b2", "item": "potion"}, bots)
check("③ 결과: given · to 2 · what 물약 · 남은 1 / 카야 소지 1 / 두란 last=give",
      res.get("result") == "given" and res.get("to") == "2" and res.get("what") == "물약" and res.get("potions") == 1
      and b1["potions"] == 1 and b2["potions"] == 1 and (b1.get("last") or {}).get("type") == "give")
check("③ 받은 쪽: last=received(from 1, 물약, 소지 1) · 궤적에도",
      (b2.get("last") or {}) == {"char": "2", "type": "received", "from": "1", "what": "물약", "item": "potion", "potions": 1}
      and any(t.get("type") == "received" for t in b2.get("trail") or []))
check("③ 목격: 피른만 ally_give{char 1, to 2, what 물약} · 둘은 아님",
      (b3.get("witnessed") or []) == [{"kind": "ally_give", "char": "1", "to": "2", "what": "물약"}]
      and not b1.get("witnessed") and not b2.get("witnessed"))
check("③ 뼈: 두란 gave→2 ×1 · 카야 received←1 ×1 · talk 0",
      bone(b1, "2", "gave") == 1 and bone(b2, "1", "received") == 1 and bone(b1, "2", "talk") == 0)
check("③ 상세 기록 양쪽: {t5, 건네기, 물약, mine, reply None}",
      acts(b1, "2") == [{"turn": 5, "kind": "건네기", "what": "물약", "mine": True, "reply": None}]
      and acts(b2, "1") == [{"turn": 5, "kind": "건네기", "what": "물약", "mine": False, "reply": None}])
check("③ 층 집계: 두란 [건넴] ×1 · 카야 [받음] ×1 · 피른 목격 [동료 건넴] ×1",
      b1["floor"]["n"].get("건넴") == 1 and b2["floor"]["n"].get("받음") == 1 and b3["floor"]["w"].get("동료 건넴") == 1)

print("── ④ 장비 물리")
d, bots = scene()
b1, b2, b3 = bots
b1["weapon"] = {"name": "단검", "bonus": 1}
res = d.act(b1, {"type": "give", "target": "b2", "item": "weapon"}, bots)
check("④ 빈 슬롯: 카야가 바로 걸친다(equipped) · 두란 빈손 · 받은 쪽 last equipped",
      res.get("result") == "given" and res.get("equipped") is True and b2["weapon"] == {"name": "단검", "bonus": 1}
      and b1["weapon"] is None and (b2.get("last") or {}).get("equipped") is True)
b1["armor"], b2["armor"] = {"name": "가죽 갑옷", "bonus": 1}, {"name": "사슬 갑옷", "bonus": 2}
res = d.act(b1, {"type": "give", "target": "b2", "item": "armor"}, bots)
f = d.feature_at(b2["x"], b2["y"])
check("④ 찬 슬롯: 발밑에 피처로 놓인다(placed) · 카야 갑옷 그대로 · 두란은 벗었다",
      res.get("result") == "given" and res.get("placed") is True and f is not None and f.type == "armor" and f.name == "가죽 갑옷"
      and b2["armor"]["name"] == "사슬 갑옷" and b1["armor"] is None and (b2.get("last") or {}).get("placed") is True)
b1["armor"] = {"name": "가죽 갑옷", "bonus": 1}
res2 = d.act(b1, {"type": "give", "target": "b2", "item": "armor"}, bots)
f1 = d.feature_at(b1["x"], b1["y"])
check("④ 상대 발밑이 찼으면 내 발밑에", res2.get("result") == "given" and res2.get("placed") is True and f1 is not None and f1.name == "가죽 갑옷")
b1["armor"] = {"name": "가죽 갑옷", "bonus": 1}
res3 = d.act(b1, {"type": "give", "target": "b2", "item": "armor"}, bots)
check("④ 둘 다 찼으면 no_room(소지 유지)", res3.get("result") == "no_room" and b1["armor"]["name"] == "가죽 갑옷")

print("── ⑤ 실패")
d, bots = scene()
b1, b2, b3 = bots
b1["potions"] = 1
r_far = d.act(b1, {"type": "give", "target": "b3", "item": "potion"}, bots)
r_no = d.act(b1, {"type": "give", "target": "b9", "item": "potion"}, bots)
b1["potions"] = 0
r_none = d.act(b1, {"type": "give", "target": "b2", "item": "potion"}, bots)
check("⑤ too_far(피른 2칸) · no_target(b9) · nothing(빈손) — 아무것도 안 옮긴다",
      r_far["result"] == "too_far" and r_no["result"] == "no_target" and r_none["result"] == "nothing"
      and b2["potions"] == 0 and b3["potions"] == 0 and not acts(b1, "2"))
d_off, bots_off = scene(give=False)
bots_off[0]["potions"] = 1
r_off = d_off.act(bots_off[0], {"type": "give", "target": "b2", "item": "potion"}, bots_off)
check("⑤ 꺼진 판: nothing · 이동 없음", r_off["result"] == "nothing" and bots_off[0]["potions"] == 1 and bots_off[1]["potions"] == 0)

print("── ⑥ 정지 물리")
d, bots = scene()
b1, b2, b3 = bots
b1["potions"] = 2
b2["order"], b2["path"] = "exit", [(b2["x"] + 1, b2["y"])]
d.act(b1, {"type": "give", "target": "b2", "item": "potion"}, bots)
check("⑥ 걷는 상대는 안 선다(order 유지) — 다음 결정에서 읽는다", b2["order"] == "exit" and b2["potions"] == 1)
b2["order"], b2["path"], b2["wait"] = "wait", [], {"n": 2, "allies": set()}
d.act(b1, {"type": "give", "target": "b2", "item": "potion"}, bots)
check("⑥ 대기 중인 상대는 깬다(order·wait 비움)", b2["order"] is None and b2.get("wait") is None and b2["potions"] == 2)

print("── ⑦ 표현")
d, bots = scene()
b1, b2, b3 = bots
b1["potions"] = 2
res = d.act(b1, {"type": "give", "target": "b2", "item": "potion"}, bots)
check("⑦ _last_prose 한 쪽/받은 쪽/실패",
      brains._last_prose(res, NAMES) == "카야(봇2)에게 물약을(를) 건넸다 (남은 물약 1병)"
      and brains._last_prose(b2["last"], NAMES) == "두란(봇1)에게서 물약을(를) 받았다 (소지 물약 1병)"
      and brains._last_prose({"type": "give", "result": "too_far"}, NAMES) == "건네려 했지만 — 곁에 없었다(붙어야 건넨다)")
check("⑦ event_tags [건넴] 물약 → 카야 / [받음] 물약 (두란)",
      G.event_tags(res, NAMES) == [("give", "건넴", "물약 → 카야")]
      and G.event_tags(b2["last"], NAMES) == [("received", "받음", "물약 (두란)")])
o3 = d.view(b3, bots)
w = (o3.get("witnessed") or [{}])[0]
check("⑦ 목격 문장(view 가 to_name 을 풀어 준다)",
      brains._witness_prose(w) == "두란(봇1)가 카야(봇2)에게 물약을(를) 건네는 것을")
check("⑦ act_summary · _hist_item · _VERB_KR",
      show_runner.act_summary(res) == "봇2에게 물약 건넴"
      and brains._hist_item({"type": "give", "target": "b2", "item": "potion", "turn": 5}) == "건네기 b2 회복 물약 (t5)")
o1 = d.view(b1, bots)
o1["intent"] = {"type": "give", "target": "b2", "item": "potion", "turn": 5, "reason": "x"}
check("⑦ wire 직전 판단에 물건", "직전 판단(t5): give b2 회복 물약" in brains._wire(o1, NAMES))

print("── ⑧ 러너 반응 집계")
cr = show_runner.classify_reply
check("⑧ classify_reply: 건네기·친목·동행·합류로 그를 향하면 행동 / 말 to 그·all = 말 / 그 외 없음",
      cr({"type": "give", "target": "b1", "item": "potion"}, "1") == "행동" and cr({"type": "bond", "target": "b1"}, "1") == "행동"
      and cr({"type": "follow", "target": "b1"}, "1") == "행동" and cr({"type": "goto", "target": "b1"}, "1") == "행동"
      and cr({"type": "goto", "target": "f0", "say": "응", "to": "1"}, "1") == "말" and cr({"type": "wait", "say": "다들", "to": "all"}, "1") == "말"
      and cr({"type": "goto", "target": "f0", "say": "응", "to": "3"}, "1") == "없음" and cr({"type": "goto", "target": "b3"}, "1") == "없음"
      and cr(None, "1") == "없음")
d, bots = scene()
b1, b2, b3 = bots
b1["potions"] = 1
d.act(b1, {"type": "give", "target": "b2", "item": "potion"}, bots)
oa = {"2": {"1": "건네기"}}
reps = []
out = show_runner.settle_acts(d, bots, oa, {"2": {"type": "give", "target": "b1", "item": "potion", "src": "haiku"}}, reps)
check("⑧ settle_acts: 카야의 첫 결정(되건네기)=행동 · 양쪽 기록에 reply · 장부 닫힘 · replies",
      out == [{"from": "2", "to": "1", "kind": "건네기", "how": "행동"}] and reps == out and oa == {"2": {}}
      and acts(b1, "2")[-1]["reply"] == "행동" and acts(b2, "1")[-1]["reply"] == "행동")
oa = {"2": {"1": "건네기"}}
out = show_runner.settle_acts(d, bots, oa, {"2": {"type": "goto", "target": "f0", "src": "plan"}}, [])
check("⑧ 작정 집행은 안 닫는다", out == [] and oa == {"2": {"1": "건네기"}})
d, bots = scene()
b1, b2, b3 = bots
op = {"2": {"1": 5}}
reps = []
ans = show_runner.settle_proposals(d, bots, op, {"2": {"type": "give", "target": "b1", "item": "potion", "say": "", "src": "haiku"}}, reps)
check("⑧ 제안의 승낙=행동: answered True · answered/replied 뼈 · replies {제안, 행동} · 장부 닫힘",
      ans == {"2": {"1": True}} and bone(b1, "2", "answered") == 1 and bone(b2, "1", "replied") == 1
      and reps == [{"from": "2", "to": "1", "kind": "제안", "how": "행동"}] and op == {"2": {}})
op = {"2": {"1": 5}}
reps = []
ans = show_runner.settle_proposals(d, bots, op, {"2": {"type": "goto", "target": "f0", "say": "", "src": "haiku"}}, reps)
check("⑧ 답 없음: False · replies {제안, 없음}", ans == {"2": {"1": False}} and reps == [{"from": "2", "to": "1", "kind": "제안", "how": "없음"}])
check("⑧ 하위호환: replies 인자 없이도 된다", show_runner.settle_proposals(d, bots, {"2": {"1": 5}}, {"2": {"say": "응", "to": "1", "src": "haiku"}}) == {"2": {"1": True}})

print("── ⑨ think_all·스냅샷")
d, bots = scene()
b1, b2, b3 = bots
b1["potions"] = 1
n_give = opts(d, b1, bots)[0]["n"]
brains._call_claude = lambda prompt, model="haiku": '{"reason": "x", "choice": %d, "say": ""}' % n_give
out = brains.think_all(d, bots)
check("⑨ 메뉴 번호 → dec {give, b2, item potion} · intent/history 에 item",
      out["1"].get("type") == "give" and out["1"].get("target") == "b2" and out["1"].get("item") == "potion"
      and b1["intent"].get("item") == "potion" and (b1.get("history") or [{}])[-1].get("item") == "potion")
d.act(b1, out["1"], bots)
check("⑨ bot_snapshot relations: 두란 {'2': {'gave': 1}} · 카야 {'1': {'received': 1}}",
      G.bot_snapshot(b1).get("relations") == {"2": {"gave": 1}} and G.bot_snapshot(b2).get("relations") == {"1": {"received": 1}})

print("── ⑩ 배선(소스)·지침")
import io as _io                                     # noqa: E402
rsrc = _io.open(os.path.join(HERE, "show_runner.py"), encoding="utf-8").read()
check("⑩ 러너: 스위치·Dungeon 인자 2곳·run_meta·장부·settle·replies·리셋·이월",
      'DUNGEON_GIVE' in rsrc and rsrc.count('give_verb=GIVE_ON, bond_verb=BOND_ON') == 2 and 'give=GIVE_ON' in rsrc
      and rsrc.count('open_acts = {}') == 2 and 'settle_acts(d, bots, open_acts, decisions, replies)' in rsrc
      and '"replies": replies' in rsrc and 'd.give_verb, d.bond_verb = GIVE_ON, BOND_ON' in rsrc
      and '"acts": [dict(a) for a in (e.get("acts") or [])]' in rsrc)
ssrc = _io.open(os.path.join(HERE, "scenario.py"), encoding="utf-8").read()
check("⑩ scenario.py: 스위치 미러링 · potions 프리셋 · 프로브 출력 item/form",
      '("give_verb", "DUNGEON_GIVE")' in ssrc and '"potions" in ov' in ssrc and '"item", "form"' in ssrc)
check("⑩ 지침: 건네기 절 · 내 문장('답이 필요할 때만') 제거 · 파트너 문장 유지",
      "- **건네기**: 가진 물약·무기·방어구를 넘긴다" in brains.MENU_PROMPT and "답이 필요할 때만" not in brains.MENU_PROMPT
      and "상대의 선택을 요청한다" in brains.MENU_PROMPT and "선택지의 행동(건네기·동행·합류)으로도 한다" in brains.MENU_PROMPT)
asrc = _io.open(os.path.join(HERE, "analyze_social.py"), encoding="utf-8").read()
vsrc = _io.open(os.path.join(HERE, "viewer", "index.html"), encoding="utf-8").read()
check("⑩ analyze_social 반응 형태 · 뷰어 건네기 줄", 'replies' in asrc and "t === 'give'" in vsrc)

print()
if C.failed:
    print("FAIL — %d개 실패" % C.failed)
    raise SystemExit(1)
print("ALL PASS — verify_give (D47 ② 건네기: 메뉴·물약/장비 물리·무정지/깨움·목격·뼈·상세 기록·반응 집계·표현·배선)")

# -*- coding: utf-8 -*-
"""지목(D41, 2026-09-06 파트너 발제 "말 걸림에 say 대상을 넣자" → 확정 "대상 없음=혼잣말, 아무도 안 멈춤") 검증 — 40번째 게이트. LLM 0콜.
말(say)에 정식 필드 `to`(봇 번호 | 이름 | all). 배달(들림)은 그대로 시야 안 전원, **정지(말 걸림)와 대화 뼈는 지목된 사람만**.
대상 없는 말 = 혼잣말·방송(들리지만 아무도 안 선다, 뼈도 안 쌓인다). 자유 텍스트 이름 파싱(07-24 기각 뒷문)이 아니라 응답 JSON 필드.
게이트:
  ① brains._parse_to: 번호·'b2'·'봇2'·이름 → 봇 번호 / all·모두·다들·전원 → 'all' / 자기 자신·미등재·빈 값 → None / 솔로(로스터 없음)는 시야 안 번호만
  ② dungeon_gm.addressed_to: to==나 / all → True, 없음·남 → False
  ③ 러너 deliver_and_hail(사회층 한 틱): 지목된 사람만 멈춤(들리긴 전원) · 대화 뼈도 지목 쌍만
  ④ 대상 없음(혼잣말): 배달 O · 정지 0 · 뼈 0
  ⑤ all: 시야 안 전원 정지·뼈
  ⑥ 스위치 off(SAYTO_ON=False) = 구판(들리면 전원 정지·배달 쌍 전부 뼈)
  ⑦ wire: "(너에게)"/"(모두에게)"/"(혼잣말)" 표식 · think_all 이 dec.to 를 intent 에 남김 · 스트림 decisions.to
(기존 verify 39종은 별도 실행.)
"""
import os
import tempfile

os.environ.update(DUNGEON_GM="0", DUNGEON_TURNS="4", DUNGEON_W="40", DUNGEON_H="16",
                  DUNGEON_SEED="7", DUNGEON_MONSTERS="0", DUNGEON_TRAPS="0", DUNGEON_LURKERS="0",
                  DUNGEON_DEPTHS="1", DUNGEON_BESTIARY_FILE="",
                  DUNGEON_STATE_DIR=os.path.join(tempfile.mkdtemp(prefix="wl_sayto_"), "state"))
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
OBS = {"sights": {"bots": [{"char": "2"}, {"char": "3"}]}}


def scene(hail=True, relations=True):
    d, st = Dungeon.from_ascii(ROWS, seed=7)
    d.hail, d.relations, d.events = hail, relations, True
    bots = []
    for c in "123":
        b = G.spawn(d, c, bots, sheet=G.HEROES.get(c) or G.HEROES['1'])
        b["x"], b["y"] = st[c]
        b["name"] = {"1": "두란", "2": "카야", "3": "피른"}[c]
        bots.append(b)
    d.turn = 5
    for b in bots:
        b["order"], b["path"] = "exit", [(b["x"] + 1, b["y"])]   # 전원 '걷는 중'(말 걸림 대상)
    return d, bots


def talk_n(b, oc):
    return (((b.get("relations") or {}).get(oc) or {}).get("bones") or {}).get("talk", {}).get("n", 0)


print("── ① _parse_to")
p = brains._parse_to
check("① 번호·b2·봇2·이름 → 봇 번호", p("2", "1", ROSTER, OBS) == "2" and p("b3", "1", ROSTER, OBS) == "3"
      and p("봇2", "1", ROSTER, OBS) == "2" and p("카야", "1", ROSTER, OBS) == "2" and p("피른!", "1", ROSTER, OBS) == "3")
check("① all·모두·다들·전원 → 'all'", all(p(x, "1", ROSTER, OBS) == "all" for x in ("all", "모두", "다들", "전원", "ALL")))
check("① 자기 자신·미등재·빈 값 → None", p("1", "1", ROSTER, OBS) is None and p("두란", "1", ROSTER, OBS) is None
      and p("고블린", "1", ROSTER, OBS) is None and p("", "1", ROSTER, OBS) is None and p(None, "1", ROSTER, OBS) is None)
check("① 솔로(로스터 없음): 시야 안 번호만 통과, 이름은 모름", p("2", "1", [], OBS) == "2" and p("카야", "1", [], OBS) is None
      and p("9", "1", [], OBS) is None)

print("── ② addressed_to")
check("② to==나 / all → True · 없음·남 → False",
      G.addressed_to({"from": "2", "to": "1"}, "1") and G.addressed_to({"from": "2", "to": "all"}, "1")
      and not G.addressed_to({"from": "2"}, "1") and not G.addressed_to({"from": "2", "to": "3"}, "1"))

print("── ③ 지목 정지·지목 뼈")
show_runner.SAYTO_ON = True
d, bots = scene()
inbox, hails = show_runner.deliver_and_hail(d, bots, {"2": "두란, 이쪽!"}, {"2": "1"})
check("③ 들리긴 전원(1·3 inbox) · 멈춤은 지목된 1만 · 3은 걷던 길 유지",
      [m["from"] for m in inbox["1"]] == ["2"] and [m["from"] for m in inbox["3"]] == ["2"]
      and inbox["1"][0].get("to") == "1" and hails == {"1": ["2"]}
      and bots[0].get("order") is None and bots[2].get("order") == "exit")
check("③ 대화 뼈는 지목 쌍(1↔2)만 · 3↔2 는 0", talk_n(bots[0], "2") == 1 and talk_n(bots[1], "1") == 1
      and talk_n(bots[2], "2") == 0 and talk_n(bots[1], "3") == 0)

print("── ④ 혼잣말")
d, bots = scene()
inbox, hails = show_runner.deliver_and_hail(d, bots, {"2": "으, 여긴 어둡네"}, {})
check("④ 대상 없음: 배달 O(1·3) · 정지 0 · 뼈 0",
      inbox["1"] and inbox["3"] and "to" not in inbox["1"][0] and hails == {}
      and bots[0].get("order") == "exit" and talk_n(bots[0], "2") == 0 and talk_n(bots[2], "2") == 0)

print("── ⑤ all")
d, bots = scene()
inbox, hails = show_runner.deliver_and_hail(d, bots, {"2": "다들 모여!"}, {"2": "all"})
check("⑤ all: 시야 안 전원 정지·뼈", hails == {"1": ["2"], "3": ["2"]} and talk_n(bots[0], "2") == 1 and talk_n(bots[2], "2") == 1)

print("── ⑥ 스위치 off = 구판")
show_runner.SAYTO_ON = False
d, bots = scene()
inbox, hails = show_runner.deliver_and_hail(d, bots, {"2": "으, 여긴 어둡네"}, {})
check("⑥ off: 대상 없어도 들리면 전원 정지·배달 쌍 뼈(구판)", hails == {"1": ["2"], "3": ["2"]}
      and talk_n(bots[0], "2") == 1 and talk_n(bots[2], "2") == 1)
show_runner.SAYTO_ON = True

print("── ⑦ 렌더·intent·스트림")
NAMES = {"1": "두란", "2": "카야", "3": "피른"}
base = {"job": "전사", "sex": "남", "hp": 9, "maxhp": 14, "str": 3, "dex": 1, "inventory": 0, "depth": 1, "pos": [5, 5],
        "sights": {"exit": None, "features": [], "monsters": [], "ways": [], "bots": []},
        "party": [], "options": [], "ascii_view": ["@"], "legend": {},
        "messages": [{"from": "2", "text": "이쪽!", "to": "1", "to_me": True}, {"from": "3", "text": "모여", "to": "all"},
                     {"from": "2", "text": "어둡네"}, {"from": "2", "text": "피른아", "to": "3"}]}
txt = brains._wire(base, NAMES)
check("⑦ wire: (너에게)/(모두에게)/(혼잣말)/(피른에게) 표식",
      '카야(봇2): "이쪽!" (너에게)' in txt and '피른(봇3): "모여" (모두에게)' in txt
      and '카야(봇2): "어둡네" (혼잣말)' in txt and '카야(봇2): "피른아" (피른(봇3)에게)' in txt)
brains._call_claude = lambda prompt, model="haiku": '{"reason": "x", "choice": 1, "say": "카야, 이리 와", "to": "카야"}'
dt, botst = scene()
for b in botst:
    b["order"], b["path"] = None, []
out = brains.think_all(dt, botst)
check("⑦ 응답 to(이름) → dec.to 봇 번호 · intent 에 to 남음",
      out["1"].get("to") == "2" and botst[0]["intent"].get("to") == "2")
brains._call_claude = lambda prompt, model="haiku": '{"reason": "x", "choice": 1, "say": "흠", "to": "1"}'
dt, botst = scene()
for b in botst:
    b["order"], b["path"] = None, []
out = brains.think_all(dt, botst)
check("⑦ 자기 자신 지목은 버린다(to 없음=혼잣말)", "to" not in out["1"])

print()
if C.failed:
    print("FAIL — %d개 실패" % C.failed)
    raise SystemExit(1)
print("ALL PASS — verify_sayto (D41 지목: to 파싱·지목 정지·지목 뼈·혼잣말·all·스위치·렌더·intent)")

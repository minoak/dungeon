# -*- coding: utf-8 -*-
"""p0.5.29 buy · sell 동사(민옥 10-18 "심플하게 buy를 두는게 좋겠어 그러면 자연스럽게 sell이 생기니까") — 헤들리스 검증. LLM 0콜.
근거: 실판(10-18) 160틱 동안 식사를 산 횟수 0 — 사기·팔기가 둘 다 use 라 `use f13 + item g1`(입력 오류)·`use f13`(구경)·`use f13 + item i7`(골드 팔기)만 되풀이.
원칙: 사실만 · 데이터 주도(동사 정의 + 말 파일 + 세트 한 줄 — 처리기만 코드) · 기능 플래그 없음 · 동사 유일함(한 일엔 맞는 동사 하나).
게이트:
  ① 동사·세트·말: buy(대상 = 상품 · 소지품 칸 없음 · 걷지 않음) · sell(대상 = 가게 · 소지품 꼭 · 자동 접근)이 세트의 use 다음 · 처리기 buy·sell ·
     설명 = 말 파일 · 사고팔기 말(prompts/actions/trade.md) 칸 셋 · 검증기가 모르는 자리·빠진 칸·남는 칸·짝 없는 중괄호를 거절
  ② 지침·관측 문장: 행동 사전의 buy·sell 줄 · 먼저 걸어가는 동사(sell 은 걷고 buy 는 아니다) · item 을 붙이는 동사 use·sell·give · use 설명에 거래 말 없음 ·
     관측 가게 줄 '- 주점 f… — 파는 것(buy)과 사들이는 값(sell):'(칸 설명 없음) · 메뉴형 가게 줄 그대로
  ③ buy 로 사기: 식사(그 자리에서 먹음) · 물약(소지 +1) · 장비(바로 든다) · 골드 차감 · 돈 부족 too_poor → 주점 주인의 정해진 말 그대로 ·
     상품이 아닌 대상 = no_effect(골드 그대로) · 입력 칸(item 없음 · 대상 꼭 · 문턱 밖 상품은 대상이 아님)
  ④ sell 로 팔기: 보물 2개(amount) · 헌 장비(손이 빈다) · 멀리서 sell = 걸어가서 판다 · 가게가 아닌 대상 = no_effect · 소지품 없이 missing_item / nothing ·
     사들이지 않는 것 no_deal(그대로)
  ⑤ 끊긴 use 길: use 상품(소지품을 들었든 아니든) · use 가게 + 소지품 = 사고팔지 않는다(no_effect · 골드·소지품·배고픔 그대로) · 결과 = 말 파일 문장 한 줄
     (무엇을 하라는 말 없음) · use 가게(소지품 없이) = 구경 그대로
  ⑥ 결과 type = 고른 동사: 결과·직전 결과(last)·판정 머리 = buy/sell · 꼬리표·1인칭 문장·관전 요약이 쓰임 결과를 그린다(폴백 없음) · 라우터 결과(대상 소실) 문장 ·
     동사 이름을 바꾼 시험 세트(purchase — 처리기 buy · vend — 처리기 sell)에서도 기록 type = purchase / vend · 가게 줄 '(purchase)…(vend)' ·
     vend 의 결과가 그려지고 지침 목록(먼저 걷는 동사 · item)에 vend(p0529b — 리뷰 권장)
  ⑦ 러너 판(더미 · 각본 두뇌): 잡화점에서 buy → sell → use 상품(끊김) — 스트림 이벤트·틱 결정 type buy·sell · events.log 문장 · 결산(end.summary)의 결정 갈래
  ⑧ 그대로인 길: 메뉴형 interact g<n> 사기 · 메뉴 '사기:' 줄 · NPC 두뇌의 가게 사실 · use 의 다른 쓰임(휴대식 먹기 · 묵기)
  ⑨ 배선: _run_gates.sh · VERSION 0.5.29 이상 · PATCH_NOTES · CHANGELOG · STREAM_FORMAT · prompts/README · check_words 사고팔기 말 줄 ·
     행동·관측 계약 compose-v0.6(p0529b — 세트가 바뀐 패치가 올린다: CA · 결정 메타 · 관측 · 러너 판 run_meta)
"""
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = tempfile.mkdtemp(prefix="wl_trade_")
STATE = os.path.join(ROOT, "state")
os.makedirs(STATE, exist_ok=True)
BASE_ENV = dict(DUNGEON_GM="0", DUNGEON_STEP_DELAY="0", DUNGEON_TURNS="30", DUNGEON_W="40", DUNGEON_H="16",
                DUNGEON_DEPTHS="2", DUNGEON_SEED="7", DUNGEON_MONSTERS="0", DUNGEON_TRAPS="0", DUNGEON_LURKERS="0",
                DUNGEON_BESTIARY_FILE="", DUNGEON_PARTY_FILE=os.path.join(HERE, "party.json"), DUNGEON_STATE_DIR=STATE,
                DUNGEON_TOWN="1", DUNGEON_BRAIN_BACKEND="dummy", DUNGEON_BOSS="0", DUNGEON_RUNS_DIR=os.path.join(ROOT, "runs"),
                DUNGEON_ACTION_MODE="compose")
os.environ.update(BASE_ENV)
for k in ("DUNGEON_QUESTS", "DUNGEON_TOWN_APART", "DUNGEON_NPC_BRAIN", "DUNGEON_SOLO", "DUNGEON_START", "DUNGEON_MENU", "DUNGEON_RESUME",
          "DUNGEON_PARTYFORM", "DUNGEON_STRANGERS", "DUNGEON_TOWN_SIGHT", "DUNGEON_NPC_REPLY", "DUNGEON_TOWN_LIFE", "DUNGEON_NOTICES",
          "DUNGEON_TOWN_BUILDINGS", "DUNGEON_TOWN_WALKERS", "DUNGEON_ARCH", "DUNGEON_FLOOR_LIFE", "DUNGEON_BESTIARY_PLUS", "DUNGEON_OFFER"):
    os.environ.pop(k, None)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import brains                                        # noqa: E402
brains._call_claude = lambda prompt, model="haiku": ""   # LLM 무력화(0콜)
import composed_actions as CA                        # noqa: E402
import dungeon_gm as G                               # noqa: E402
import entities as ENT                               # noqa: E402
import interactables as IA                           # noqa: E402
import show_runner as R                              # noqa: E402
import words as WD                                   # noqa: E402
import time as _time                                 # noqa: E402
_time.sleep = lambda s: None
R.STEP_DELAY = 0


class C:
    failed = 0
    n = 0


def check(name, ok, detail=""):
    C.n += 1
    print("  %s %s%s" % ("OK  " if ok else "FAIL", name, (" — " + str(detail)[:600]) if (detail and not ok) else ""))
    if not ok:
        C.failed += 1


def src(*p):
    with open(os.path.join(HERE, *p), encoding="utf-8") as f:
        return f.read()


SHEETS = R.load_party(os.path.join(HERE, "party.json"))
NAMES = {c: SHEETS[c]["name"] for c in SHEETS}
LINE = "돈 떨어졌으면 길드 가서 의뢰라도 받아 와."     # 주점 주인의 정해진 말(정의 line_too_poor — p0.5.27)


def town(on=True):
    """마을(마을 생활 켬/끔) + 파티 몸 셋. 정의의 말·값은 리포의 것 그대로."""
    old = R.TOWN_LIFE_ON
    R.TOWN_LIFE_ON = on
    try:
        d, _starts = R.build_town(None, apart=True, walkers=False, guide=False, quests=None)
    finally:
        R.TOWN_LIFE_ON = old
    bs = []
    for c in sorted(SHEETS):
        bs.append(G.spawn(d, c, bs, sheet=dict(SHEETS[c])))
    d.turn = 1
    return d, bs


def by_name(d, name):
    return next(f for f in d.features.values() if f.name == name)


def stand_by(d, f, bots=(), skip=()):
    """피처 곁(직교)의 걸을 수 있는 빈 칸(다른 몸이 없는)."""
    taken = {(o["x"], o["y"]) for o in bots} | set(skip)
    return next((f.x + dx, f.y + dy) for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0))
                if d.grid[f.y + dy][f.x + dx] == G.FLOOR and d.feature_at(f.x + dx, f.y + dy) is None and (f.x + dx, f.y + dy) not in taken)


def at_range(d, f, bots, n):
    """피처 f 와 같은 구역 · 체비셰프 n 칸 · 보이는 빈 바닥(가까운 순 첫 칸)."""
    taken = {(o["x"], o["y"]) for o in bots}
    z = d._town_zone(f.x, f.y)
    return min((y, x) for y in range(d.h) for x in range(d.w)
               if d.grid[y][x] == G.FLOOR and d.feature_at(x, y) is None and (x, y) not in taken and d._town_zone(x, y) == z
               and max(abs(x - f.x), abs(y - f.y)) == n and (f.x, f.y) in d.visible_cells(x, y))[::-1]


def put(b, xy):
    b["x"], b["y"] = xy


def act(d, b, bots, action):
    d.view(b, bots)                                   # 관측 = 참조(_target_refs)를 새로 짓는다(실판과 같은 순서)
    return d.act(b, dict(action), bots)


def wire(d, b, bots, compose=True):
    return brains._wire(d.view(b, bots), NAMES, compose=compose)


def gid_of(d, name):
    return next(g["gid"] for g in IA.goods(d) if g["name"] == name)


def hun(b):
    return b["needs"]["hunger"]


ASENT = "- 이동은 세계가 대신 걷는다. %s는 대상이 멀면 닿는 곳까지 먼저 걸어간 뒤 한다. 이동이 중단되면 다시 판단한다."
ISENT = "`target`은 관측에 나온 ID이고, `self`는 너 자신이다. `item`은 소지품 ID(`i...`)이며 %s에만 붙인다."
BUY_DESC, SELL_DESC = "`target`의 상품을 산다. 값은 골드로 낸다.", "`item`을 `target` 가게에 판다."

# ─────────────────────────────────────────────────────────────────────────────
print("── ① 동사·세트·말")
BUY, SELL = CA.VERBS.get("buy") or {}, CA.VERBS.get("sell") or {}
raw_buy, raw_sell = json.loads(src("entities", "verb", "buy.json")), json.loads(src("entities", "verb", "sell.json"))
check("① 세트에서 use 바로 다음 buy·sell · buy = 처리기 buy · 대상 꼭 · 소지품 칸 없음 · 걷지 않음(상품은 문턱 2칸 안에서만 대상) · "
      "sell = 처리기 sell · 대상 꼭 · 소지품 꼭 · 자동 접근 · 처리기 열쇠가 엔진에 있다",
      {"use", "buy", "sell"} <= set(CA.COMMON) and CA.COMMON.index("buy") == CA.COMMON.index("use") + 1 and CA.COMMON.index("sell") == CA.COMMON.index("buy") + 1
      and {k: v for k, v in BUY.items() if k != "desc"} == {"handler": "buy", "target": "required"}
      and {k: v for k, v in SELL.items() if k != "desc"} == {"handler": "sell", "target": "required", "item": "required", "approach": True}
      and "buy" not in CA.DISTANCE_ACTIONS and "sell" in CA.DISTANCE_ACTIONS and CA.HANDLERS.get("buy") is CA._buy and CA.HANDLERS.get("sell") is CA._sell,
      (CA.COMMON, BUY, SELL))
check("① 설명 = 말 파일(prompts/world/verb/buy.md·sell.md 의 verb.desc — 정의 JSON 엔 \"@prompts\" 표시만): '%s' · '%s'" % (BUY_DESC, SELL_DESC),
      BUY.get("desc") == BUY_DESC and SELL.get("desc") == SELL_DESC
      and raw_buy["comps"]["verb"]["desc"] == WD.WORD_MARK == raw_sell["comps"]["verb"]["desc"], (BUY.get("desc"), SELL.get("desc")))
TW = CA.trade_words()
bad_tw = CA.trade_problems({"shop": "파는 것({gold})", "use_good": "{shop} {", "extra": "x"})
check("① 사고팔기 말(prompts/actions/trade.md) = 칸 셋(shop·use_good·use_shop_item) · 칸마다 정해진 자리만 · 검증기가 빠진 칸·남는 칸·모르는 자리·짝 없는 중괄호를 한 번에 거절",
      set(TW) == {"shop", "use_good", "use_shop_item"} and CA.trade_problems(TW) == [] and len(bad_tw) == 4
      and any("`use_shop_item` 가 없다" in p for p in bad_tw) and any("`extra` 는 사고팔기 말이 아니다" in p for p in bad_tw)
      and any("{gold} 는 모르는 자리다" in p for p in bad_tw) and any("짝이 맞지 않는 중괄호" in p for p in bad_tw), bad_tw)

# ─────────────────────────────────────────────────────────────────────────────
print("── ② 지침·관측 문장")
GUIDES = (brains.COMPOSE_PROMPT, brains.COMPOSE_PROMPT_SOLO)
glines = [g.split("\n") for g in GUIDES]
check("② 지침 행동 사전(파티·혼자): use 줄 바로 다음 '- `buy`: %s' · '- `sell`: %s'" % (BUY_DESC, SELL_DESC),
      all(ls[ls.index(next(x for x in ls if x.startswith("- `use`:"))) + 1:][:2] == ["- `buy`: " + BUY_DESC, "- `sell`: " + SELL_DESC] for ls in glines))
check("② 지침 문장 안 목록 = 세트에서: 먼저 걸어가는 동사 search·attack·use·sell·give·bond(buy 는 걷지 않는다) · item 을 붙이는 동사 use·sell·give(잇는 말 '·')",
      all(ASENT % "search·attack·use·sell·give·bond" in ls and ISENT % "use·sell·give" in ls for ls in glines)
      and CA.guide_list("approach", "·") == "search·attack·use·sell·give·bond" and CA.guide_list("item", "·") == "use·sell·give")
use_desc = CA.VERBS["use"]["desc"]
check("② use 설명에 사고팔기 말이 없다(사기·팔기·산다·판다·상품·가게·골드) — 지침에 '상품 ID 를 use' 같은 옛 길 설명 없음",
      not any(w in use_desc for w in ("사기", "팔기", "산다", "판다", "상품", "가게", "골드"))
      and not any("상품 ID 를 use" in g or "팔기: `target`" in g for g in GUIDES), use_desc)
d, bots = town()
a, b, c = bots
TAV, GS, EQ = by_name(d, "주점"), by_name(d, "잡화점"), by_name(d, "장비점")
put(a, stand_by(d, TAV, bots))
w = wire(d, a, bots)
shop_ln = [ln for ln in w.split("\n") if ln.startswith("- 주점 f") and "사들이는 값" in ln]
check("② 관측 가게 줄 = '- 주점 f%d — 파는 것(buy)과 사들이는 값(sell):'(말 파일 trade.shop · 동사 이름은 세트에서) — 칸 설명(사기: 상품 ID 를 use · 팔기: target·item) 없음 · 다음 줄 상품 '[g1] 식사 — 3골드'" % TAV.id,
      shop_ln == ["- 주점 f%d — 파는 것(buy)과 사들이는 값(sell):" % TAV.id] and "상품 ID 를 use" not in w and "팔기:" not in w
      and w.split("\n")[w.split("\n").index(shop_ln[0]) + 1] == "  · [g1] 식사 — 3골드", shop_ln)
wm = wire(d, a, bots, compose=False)
check("② 메뉴형 관측의 가게 줄은 그대로 — '- 주점 f%d — 파는 것과 사들이는 값(값은 가게가 정한다):'" % TAV.id,
      ("- 주점 f%d — 파는 것과 사들이는 값(값은 가게가 정한다):" % TAV.id) in wm.split("\n") and "(buy)" not in wm)

# ─────────────────────────────────────────────────────────────────────────────
print("── ③ buy 로 사기")
gm, gp, gd = gid_of(d, "식사"), gid_of(d, "회복 물약"), gid_of(d, "단검")
a["gold"], a["needs"]["hunger"] = 10, 30
o3 = d.view(a, bots)
p3 = CA.parse({"type": "buy", "target": gm}, o3)
r = act(d, a, bots, {"type": "buy", "target": gm})
check("③ buy 식사(주점 %s · 3골드) = 그 자리에서 먹는다 — need_fill{via buy} · 골드 10 → 7 · 배고픔 30 → 100 · 문장 '주점에서 식사를 사 먹었다 — 3골드를 냈다(남은 골드 7)'" % gm,
      p3 == ({"type": "buy", "target": gm}, None) and r["result"] == "need_fill" and r.get("via") == "buy" and a["gold"] == 7 and hun(a) == 100
      and brains._last_prose(r) == "주점에서 식사를 사 먹었다 — 3골드를 냈다(남은 골드 7)", (p3, r))
a["gold"], a["needs"]["hunger"] = 1, 30
r = act(d, a, bots, {"type": "buy", "target": gm})
check("③ 돈이 모자라면(1골드로 식사 3) too_poor — 골드·배고픔 그대로 · 실패 · 문장 '값이 3골드인데 지닌 골드가 1다' · 주점 주인의 정해진 말 그대로(R.too_poor_says)",
      r["result"] == "too_poor" and a["gold"] == 1 and hun(a) == 30 and r["resolution"]["status"] == "failed"
      and brains._last_prose(r) == "주점에서 식사를 사려 했다 — 값이 3골드인데 지닌 골드가 1다" and R.too_poor_says(d, a, r) == [("주점 주인", LINE, a["char"])], r)
put(a, stand_by(d, GS, bots))
a["gold"], a["potions"] = 12, 0
r = act(d, a, bots, {"type": "buy", "target": gp})
check("③ buy 회복 물약(잡화점 %s · 10골드) = bought — 소지 물약 0 → 1 · 골드 12 → 2 · 문장 '잡화점에서 회복 물약을 샀다 — 10골드를 냈다(남은 골드 2) · 소지 물약 1병'" % gp,
      r["result"] == "bought" and a["potions"] == 1 and a["gold"] == 2
      and brains._last_prose(r) == "잡화점에서 회복 물약을 샀다 — 10골드를 냈다(남은 골드 2) · 소지 물약 1병", r)
put(a, stand_by(d, EQ, bots))
a["gold"], a["weapon"] = 20, None
r = act(d, a, bots, {"type": "buy", "target": gd})
check("③ buy 단검(장비점 %s · 8골드) = 바로 손에 든다(+1) · 골드 20 → 12" % gd,
      r["result"] == "bought" and (a.get("weapon") or {}).get("name") == "단검" and a["weapon"]["bonus"] == 1 and a["gold"] == 12 and r.get("slot") == "weapon", r)
r_f = act(d, a, bots, {"type": "buy", "target": "f%d" % EQ.id})
check("③ 상품이 아닌 대상(장비점 건물 f%d)에 buy = no_effect(not_for_sale) — 골드 그대로" % EQ.id,
      r_f["result"] == "no_effect" and r_f.get("reason_code") == "not_for_sale" and a["gold"] == 12, r_f)
o3b = d.view(a, bots)
far = at_range(d, GS, bots, 3)
put(c, far)
o3c = d.view(c, bots)
check("③ 입력 칸: buy 에 item 을 붙이면 unexpected_item · 대상 없이 missing_target · 문턱 3칸 밖의 상품은 대상이 아니다(invalid_target)",
      CA.parse({"type": "buy", "target": "g2", "item": "i7"}, o3b) == (None, "unexpected_item") and CA.parse({"type": "buy"}, o3b) == (None, "missing_target")
      and CA.parse({"type": "buy", "target": gp}, o3c) == (None, "invalid_target"))

# ─────────────────────────────────────────────────────────────────────────────
print("── ④ sell 로 팔기")
a["bag"], a["gold"] = 3, 0                            # ③ 의 자리(장비점 곁) · ③ 에서 산 단검을 든 채
o4 = d.view(a, bots)
p4 = CA.parse({"type": "sell", "target": "f%d" % EQ.id, "item": "i8", "amount": 2}, o4)
r = act(d, a, bots, {"type": "sell", "target": "f%d" % EQ.id, "item": "i8", "amount": 2})
check("④ sell 보물 2개(amount) → 장비점 = sold +12 · 보물 3 → 1 · 문장 '장비점에 보물 2개를 팔았다 — 12골드를 받았다(지금 골드 12)'",
      p4 == ({"type": "sell", "target": "f%d" % EQ.id, "item": "i8", "amount": 2}, None) and r["result"] == "sold" and r["got"] == 12
      and a["bag"] == 1 and a["gold"] == 12 and brains._last_prose(r) == "장비점에 보물 2개를 팔았다 — 12골드를 받았다(지금 골드 12)", (p4, r))
r = act(d, a, bots, {"type": "sell", "target": "f%d" % EQ.id, "item": "i2"})
check("④ sell 헌 장비(든 단검) → 장비점 = 파는 값의 절반 4 · 손이 빈다 · 골드 16 · D39 태그 '단검 1개 팖'",
      r["result"] == "sold" and r["got"] == 4 and a["weapon"] is None and a["gold"] == 16
      and (a.get("obj_tags") or {}).get(EQ.id, {}).get("note") == "단검 1개 팖", (r, (a.get("obj_tags") or {}).get(EQ.id)))
r = act(d, a, bots, {"type": "sell", "target": "f%d" % EQ.id, "item": "i7", "amount": 3})
check("④ 사들이지 않는 것(골드) = no_deal — 골드 그대로 16 · 실패", r["result"] == "no_deal" and a["gold"] == 16 and r["resolution"]["status"] == "failed", r)
put(a, at_range(d, EQ, bots, 2))
a["bag"] = 1
r_go = act(d, a, bots, {"type": "sell", "target": "f%d" % EQ.id, "item": "i8"})
evs4 = [r_go]
for _ in range(10):
    if not a.get("order"):
        break
    d.turn += 1
    evs4.append(d.step_order(a, bots))
check("④ 2칸 떨어져 sell = 걸어가서(approaching — 판정 머리 sell) 곁에 닿아 판다(sold · approach completed · 보물 1 → 0 · 골드 22)",
      r_go.get("result") == "approaching" and r_go["resolution"]["type"] == "sell" and evs4[-1].get("result") == "sold"
      and evs4[-1].get("approach_status") == "completed" and a["bag"] == 0 and a["gold"] == 22, [(e.get("type"), e.get("result")) for e in evs4])
bench = next(f for f in d.features.values() if f.type != "building" and f.type != "npc" and IA.use_of(d, f) and IA.use_of(d, f)["kind"] == "sit")
put(a, stand_by(d, bench, bots))
a["bag"] = 2
r_nb = act(d, a, bots, {"type": "sell", "target": "f%d" % bench.id, "item": "i8"})
o4b = d.view(a, bots)
r_ni = d.act(a, {"type": "sell", "target": "f%d" % bench.id}, bots)
check("④ 가게가 아닌 대상(%s f%d)에 sell = no_effect(not_a_shop) — 보물 그대로 · 소지품 없이 sell = missing_item(입력) / 엔진 nothing(item_not_owned)" % (bench.name, bench.id),
      r_nb["result"] == "no_effect" and r_nb.get("reason_code") == "not_a_shop" and a["bag"] == 2
      and CA.parse({"type": "sell", "target": "f%d" % bench.id}, o4b) == (None, "missing_item")
      and r_ni["result"] == "nothing" and r_ni.get("reason_code") == "item_not_owned", (r_nb, r_ni))

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑤ 끊긴 use 길(use 로는 사고팔지 않는다)")
put(a, stand_by(d, TAV, bots))
a["gold"], a["needs"]["hunger"], a["rations"] = 10, 30, 1
r_g = act(d, a, bots, {"type": "use", "target": gm})
last_g = dict(a["last"])                              # 에이전트가 보는 직전 결과(공개 사본 IG.public)
w_g = wire(d, a, bots)                                # 다음 판단의 완성 관측 글(러너 마을 = 궤적 판 — 직전 결과가 꼬리표로 그려진다)
r_gi = act(d, a, bots, {"type": "use", "target": gm, "item": "i7", "amount": 3})
r_si = act(d, a, bots, {"type": "use", "target": "f%d" % TAV.id, "item": "i7", "amount": 3})
r_sr = act(d, a, bots, {"type": "use", "target": "f%d" % TAV.id, "item": "i9"})
cut = (r_g, r_gi, r_si, r_sr)
check("⑤ use 상품(%s) · use 상품 + 골드 · use 주점 + 골드 · use 주점 + 휴대식 = 사고팔지도 먹지도 않는다 — 모두 no_effect(use_good·use_good·use_shop_item·use_shop_item) · "
      "골드 10 · 배고픔 30 · 휴대식 1 그대로 · 판정 no_effect" % gm,
      [x["result"] for x in cut] == ["no_effect"] * 4 and [x.get("reason_code") for x in cut] == ["use_good", "use_good", "use_shop_item", "use_shop_item"]
      and a["gold"] == 10 and hun(a) == 30 and a["rations"] == 1 and all(x["resolution"]["status"] == "no_effect" for x in cut), [(x["result"], x.get("reason_code")) for x in cut])
p_g, p_si = brains._last_prose(r_g), brains._last_prose(r_si)
want_g = "주점의 상품 식사에 use을(를) 시도했다 — 아무 일도 일어나지 않았다(골드·소지품 그대로)"
want_si = "주점에 골드을(를) 들고 use을(를) 시도했다 — 아무 일도 일어나지 않았다(골드·소지품 그대로)"
check("⑤ 결과 문장 = 말 파일(trade.use_good·use_shop_item)의 자리만 채운 한 줄: '%s' · '%s' — 무엇을 하라는 말(buy·sell·하라)이 없다 · 에이전트가 보는 직전 결과(공개 사본)로도 같은 문장" % (want_g, want_si),
      p_g == want_g and p_si == want_si and p_g == TW["use_good"].replace("{shop}", "주점").replace("{what}", "식사").replace("{verb}", "use")
      and brains._last_prose(last_g) == want_g
      and brains._last_prose(r_sr) == want_si.replace("골드을(를)", "휴대식을(를)")
      and not any(x in p for p in (p_g, p_si) for x in ("buy", "sell", "하라", "해라", "\n")), (p_g, p_si, brains._last_prose(r_sr)))
check("⑤ 꼬리표에도 그 문장('[변화 없음] %s' — 궤적 판의 에이전트는 꼬리표로 본다: 다음 판단의 완성 관측 글 '- 그 결과:' 줄) · 관전 요약 = 'use %s — 변화 없음 (use_good)'(기존 no_effect 꼴)" % (want_g, gm),
      G.event_tags(r_g) == [("misc", "변화 없음", want_g)] and ("- 그 결과: [변화 없음] " + want_g) in w_g.split("\n")
      and R.act_summary(r_g) == "use %s — 변화 없음 (use_good)" % gm, (G.event_tags(r_g), [ln for ln in w_g.split("\n") if "그 결과" in ln], R.act_summary(r_g)))
r_br = act(d, a, bots, {"type": "use", "target": "f%d" % TAV.id})
check("⑤ 소지품 없이 use 가게 = 지금처럼 구경(browsed · 진열과 사들이는 값) · 골드 그대로",
      r_br["result"] == "browsed" and r_br["type"] == "use" and r_br.get("wares") == ["식사 3골드"] and a["gold"] == 10, r_br)

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑥ 결과 type = 고른 동사")
put(a, stand_by(d, GS, bots))
a["gold"], a["potions"] = 20, 0
rb = act(d, a, bots, {"type": "buy", "target": gp})
last_b = dict(a["last"])
w_b = wire(d, a, bots)
rs = act(d, a, bots, {"type": "sell", "target": "f%d" % GS.id, "item": "i1"})
last_s = dict(a["last"])
w_s = wire(d, a, bots)
check("⑥ 결과 기록 type = buy / sell(처리기 이름도 동사 이름도 같다 — 결과 어휘의 꼴은 effect_type interact) · 직전 결과(last)·판정 머리(resolution.type)도 · "
      "다음 판단의 관측 글 '- 그 결과: [구입] 회복 물약 ← 잡화점 10골드 (남은 10)' · '[팔기] 회복 물약 1 → 잡화점 5골드 (지금 15)'",
      rb["type"] == "buy" and rs["type"] == "sell" and rb.get("effect_type") == rs.get("effect_type") == "interact"
      and last_b.get("type") == "buy" and last_s.get("type") == "sell" and rb["resolution"]["type"] == "buy" and rs["resolution"]["type"] == "sell"
      and "- 그 결과: [구입] 회복 물약 ← 잡화점 10골드 (남은 10)" in w_b.split("\n") and "- 그 결과: [팔기] 회복 물약 1 → 잡화점 5골드 (지금 15)" in w_s.split("\n"),
      (rb.get("type"), rs.get("type"), last_b.get("type"), last_s.get("type"), [ln for ln in (w_b + "\n" + w_s).split("\n") if "그 결과" in ln]))
check("⑥ 그리는 쪽 셋이 쓰임 결과로 그린다(폴백 없음): 1인칭 문장 = IA.prose · 꼬리표 = IA.event_tags('구입'·'팔기') · 관전 요약 = IA.prose",
      all(brains._last_prose(x) == IA.prose(x) and G.event_tags(x) == IA.event_tags(x) and R.act_summary(x) == IA.prose(x) for x in (rb, rs))
      and G.event_tags(rb)[0][:2] == ("loot", "구입") and G.event_tags(rs)[0][:2] == ("use", "팔기"), (G.event_tags(rb), G.event_tags(rs)))
lost_b = CA._base(a, {"type": "buy", "target": "g6"}, "lost")
nothing_s = CA._base(a, {"type": "sell", "target": "f%d" % GS.id, "item": "i1"}, "nothing", reason_code="item_not_owned")
check("⑥ 라우터 결과(buy 대상 소실 lost · sell 소지품 없음 nothing)도 사실 문장 — JSON 폴백·'기타' 꼬리표가 아니다",
      brains._last_prose(lost_b) == "g6에 buy을(를) 하려 했지만 — 그 대상을 지금 찾을 수 없었다(지금 보이는 대상에 없다)"
      and brains._last_prose(nothing_s) == "f%d에 sell을(를) 하려 했지만 — 요청한 소지품이 없다" % GS.id
      and G.event_tags(lost_b) == [("misc", "헛손질", "buy g6 (lost)")] and R.act_summary(nothing_s) == "sell f%d 실패 — nothing" % GS.id,
      (brains._last_prose(lost_b), brains._last_prose(nothing_s), G.event_tags(lost_b), R.act_summary(nothing_s)))
# 동사 이름을 바꾼 시험 세트(데이터만 — 처리기 buy 를 쓰는 동사 purchase · 처리기 sell 을 쓰는 동사 vend)
eroot, wroot = os.path.join(ROOT, "entities"), os.path.join(ROOT, "world")
shutil.copytree(ENT.ROOT, eroot)
shutil.copytree(WD.WORDS_ROOT, wroot)
for vid, nm, vb, desc in (("purchase", "사들이기(시험)", {"handler": "buy", "target": "required"}, "`target`의 상품을 사들인다."),
                          ("vend", "넘기기(시험)", {"handler": "sell", "target": "required", "item": "required", "approach": True}, "`item`을 `target` 가게에 넘긴다.")):
    with open(os.path.join(eroot, "verb", vid + ".json"), "w", encoding="utf-8") as f:
        json.dump({"id": vid, "name": nm, "kind": "verb", "tags": ["verb"], "comps": {"verb": dict(vb, desc=WD.WORD_MARK)}}, f, ensure_ascii=False, indent=2)
    with open(os.path.join(wroot, "verb", vid + ".md"), "w", encoding="utf-8") as f:
        f.write(WD.render("verb", vid, nm, [("verb.desc", desc)]))
tdefs = {x["id"]: x for x in ENT.read(eroot, words_root=wroot).values() if x["kind"] == "verb"}
tset = os.path.join(ROOT, "set_purchase.json")
with open(tset, "w", encoding="utf-8") as f:
    json.dump({"verbs": [{"buy": "purchase", "sell": "vend"}.get(v, v) for v in CA.COMMON]}, f)
CA.use_set(tset, tdefs)
try:
    a["gold"], a["potions"] = 15, 0
    o6 = d.view(a, bots)
    w6 = brains._wire(o6, NAMES, compose=True)
    p6 = CA.parse({"type": "purchase", "target": gp}, o6)
    r6 = d.act(a, dict(p6[0] or {}), bots)
    common6, buy_gone = list(CA.COMMON), CA.parse({"type": "buy", "target": gp}, o6)
    o6v = d.view(a, bots)
    p6v = CA.parse({"type": "vend", "target": "f%d" % GS.id, "item": "i1"}, o6v)
    r6v = d.act(a, dict(p6v[0] or {}), bots)
    last6v, sell_gone = dict(a["last"]), CA.parse({"type": "sell", "target": "f%d" % GS.id, "item": "i1"}, o6v)
    w6v = brains._wire(d.view(a, bots), NAMES, compose=True)
    g6v = brains._load_prompt(os.path.join("prompts", "adventurer_prompt.md"))   # 임시 세트의 지침은 다시 읽는다(모듈의 COMPOSE_PROMPT 는 import 때 값)
finally:
    CA.use_set()
check("⑥ 시험 세트(buy 대신 purchase — 처리기 buy · 데이터만): 기록 type = purchase(처리기 이름 buy 가 아니다) · bought · 1인칭 문장·꼬리표가 그린다 · "
      "관측 가게 줄 '(purchase)' · buy 는 모르는 동사 · 되돌리면 buy",
      p6[1] is None and r6.get("type") == "purchase" and r6.get("result") == "bought" and r6["resolution"]["type"] == "purchase"
      and brains._last_prose(r6) == IA.prose(r6) and G.event_tags(r6) == IA.event_tags(r6)
      and "— 파는 것(purchase)과 사들이는 값(vend):" in w6 and buy_gone == (None, "invalid_type") and "purchase" in common6
      and list(CA.COMMON).count("buy") == 1 and CA.shop_head() == "파는 것(buy)과 사들이는 값(sell)", (p6, r6.get("type"), [ln for ln in w6.split("\n") if "사들이는 값(" in ln]))
check("⑥ 같은 시험 세트(sell 대신 vend — 처리기 sell · 데이터만): 기록 type = vend(처리기 이름 sell 이 아니다) · sold(물약 1 → 0 · 골드 5 → 10) · 판정 머리 vend · "
      "1인칭 문장·꼬리표·관전 요약이 그린다(직전 결과 공개 사본 · 관측 '- 그 결과: [팔기] …') · 지침의 먼저 걷는 동사·item 목록에 vend(파티·혼자) · sell 은 모르는 동사 · 되돌리면 sell",
      p6v[1] is None and r6v.get("type") == "vend" and r6v.get("result") == "sold" and r6v["resolution"]["type"] == "vend" and a["potions"] == 0 and a["gold"] == 10
      and brains._last_prose(r6v) == IA.prose(r6v) == brains._last_prose(last6v) and G.event_tags(r6v) == IA.event_tags(r6v) and R.act_summary(r6v) == IA.prose(r6v)
      and ("- 그 결과: [팔기] 회복 물약 1 → 잡화점 5골드 (지금 10)") in w6v.split("\n")
      and all((ASENT % "search·attack·use·vend·give·bond") in g.split("\n") and (ISENT % "use·vend·give") in g.split("\n") for g in g6v)
      and sell_gone == (None, "invalid_type") and "vend" in common6 and "sell" not in common6 and CA.verb_of("sell") == "sell",
      (p6v, r6v.get("type"), r6v.get("result"), [ln for ln in w6v.split("\n") if "그 결과" in ln]))

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑦ 러너 판(더미 · 각본 두뇌)")
plan7 = {}


def scripted(obs, char="?"):
    """1번: 잡화점으로 → 회복 물약 buy → 그 물약을 sell → 상품에 use(끊긴 길) → 기다림. 나머지는 서 있는다. 0콜 각본."""
    if not obs.get("town") or char != "1":
        return {"type": "wait"}
    st = plan7.setdefault(char, {"step": 0})
    feats = {f["name"]: f for f in (obs.get("sights") or {}).get("features") or []}
    good = next((t["id"] for t in obs.get("targets") or [] if t.get("kind") == "good" and t.get("name") == "회복 물약"), None)
    shop = feats.get("잡화점")
    if st["step"] == 0:
        if good:
            st["step"] = 1
            return {"type": "buy", "target": good}
        return {"type": "goto", "target": shop["id"]} if shop else {"type": "wait"}
    if st["step"] == 1 and shop:
        st["step"] = 2
        return {"type": "sell", "target": shop["id"], "item": "i1"}
    if st["step"] == 2 and good:
        st["step"] = 3
        return {"type": "use", "target": good}
    return {"type": "wait"}


st7 = tempfile.mkdtemp(prefix="run_", dir=ROOT)
old7 = (R.STATE, R.TOWN_LIFE_ON, G.dummy_brain, R.MAX_TURNS)
R.STATE, R.TOWN_LIFE_ON, G.dummy_brain, R.MAX_TURNS = st7, True, scripted, 120
try:
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            R.main()
        except SystemExit:
            pass
finally:
    R.STATE, R.TOWN_LIFE_ON, G.dummy_brain, R.MAX_TURNS = old7
with open(os.path.join(st7, "stream.jsonl"), encoding="utf-8") as fh:
    rows7 = [json.loads(ln) for ln in fh if ln.strip()]
with open(os.path.join(st7, "events.log"), encoding="utf-8") as fh:
    log7 = fh.read()
ticks7 = [r_ for r_ in rows7 if r_["kind"] == "tick"]
evs7 = [e for r_ in ticks7 for e in r_.get("events") or [] if str(e.get("char")) == "1"]
decs7 = [(r_["turn"], (r_.get("decisions") or {}).get("1") or {}) for r_ in ticks7]
bought7 = next((e for e in evs7 if e.get("result") == "bought"), None)
sold7 = next((e for e in evs7 if e.get("result") == "sold"), None)
cut7 = next((e for e in evs7 if e.get("reason_code") == "use_good"), None)
check("⑦ 판이 끝까지 돈다 · 스트림 이벤트: buy → bought(type buy · effect_type interact · 골드 0) · sell → sold(type sell · 받은 5 · 골드 5) · use 상품 → no_effect(use_good)",
      rows7[-1]["kind"] == "end" and bought7 and bought7.get("type") == "buy" and bought7.get("effect_type") == "interact" and bought7.get("gold") == 0
      and sold7 and sold7.get("type") == "sell" and sold7.get("got") == 5 and sold7.get("gold") == 5 and cut7 and cut7.get("type") == "use",
      [(e.get("type"), e.get("result"), e.get("reason_code")) for e in evs7 if e.get("result") not in ("walking",)][:12])
types7 = [dc.get("type") for _t, dc in decs7 if dc.get("type") in ("buy", "sell")]
summ7 = (rows7[-1].get("summary") or {}).get("actions", {}).get("1", {}).get("types", {})
check("⑦ 틱 결정(tick.decisions)의 type = buy · sell(고른 동사 그대로) · events.log 에 사고판 1인칭 사실 문장 · 결산(end.summary)의 결정 갈래에 buy 1 · sell 1",
      types7 == ["buy", "sell"] and "잡화점에서 회복 물약을 샀다 — 10골드를 냈다(남은 골드 0)" in log7 and "잡화점에 회복 물약을 팔았다 — 5골드를 받았다(지금 골드 5)" in log7
      and summ7.get("buy") == 1 and summ7.get("sell") == 1, (types7, summ7, [ln for ln in log7.split("\n") if "잡화점" in ln][:4]))

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑧ 그대로인 길")
dm, bm = town()
dm.composed_actions = dm.auto_approach = False        # 메뉴형 경로 — verify_shop ⑩ 과 같은 꼴
mb = bm[0]
put(mb, stand_by(dm, by_name(dm, "잡화점"), bm))
mb["gold"], mb["potions"] = 12, 0
opts = [o["label"] for o in dm.view(mb, bm)["options"] if str(o.get("label", "")).startswith("사기:")]
rm = dm.act(mb, {"type": "interact", "target": gid_of(dm, "회복 물약")}, bm)
check("⑧ 메뉴형(비교용 옛 규칙): 가게 곁 '사기:' 메뉴 줄 · interact g<n> 로 산다(type interact · bought · 골드 2)",
      opts and opts[0].startswith("사기: 회복 물약 g") and rm["result"] == "bought" and rm["type"] == "interact" and mb["gold"] == 2, (opts, rm))
facts = R.shop_facts(d, "general_store")
check("⑧ NPC 두뇌의 가게 사실 그대로 — '사고파는 일은 가게 문턱에서 손님이 직접 한다(네가 물건을 건네거나 돈을 받지 않는다)'",
      facts and facts.endswith("사고파는 일은 가게 문턱에서 손님이 직접 한다(네가 물건을 건네거나 돈을 받지 않는다)"), facts)
INN = by_name(d, "공동 숙소")
put(a, stand_by(d, INN, bots))
a["gold"], a["hp"], a["rations"], a["needs"]["hunger"] = 5, 3, 1, 30
r_eat = act(d, a, bots, {"type": "use", "target": "self", "item": "i9"})
r_lodge = act(d, a, bots, {"type": "use", "target": "f%d" % INN.id})
check("⑧ use 의 다른 쓰임 그대로 — 휴대식 먹기(need_fill · 휴대식 0) · 공동 숙소 묵기(lodged · 1골드)",
      r_eat["result"] == "need_fill" and a["rations"] == 0 and r_lodge["result"] == "lodged" and r_lodge.get("paid") == 1 and a["gold"] == 4, (r_eat, r_lodge))

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑨ 배선")
cw = subprocess.run([sys.executable, os.path.join(HERE, "tools", "check_words.py")], capture_output=True, text=True, encoding="utf-8",
                    env=dict(os.environ, PYTHONUTF8="1"))
check("⑨ tools/check_words.py 가 0 으로 끝나고 사고팔기 말을 센다 — '사고팔기 말 prompts/actions/trade.md — 칸 3개(shop·use_good·use_shop_item) — 칸·자리 일치'",
      cw.returncode == 0 and "사고팔기 말 prompts/actions/trade.md — 칸 3개(shop·use_good·use_shop_item) — 칸·자리 일치" in cw.stdout, cw.stdout[-400:])
sf = src("STREAM_FORMAT.md")
check("⑨ _run_gates.sh 등록(낱말 경계) · VERSION 0.5.29 이상 · PATCH_NOTES 0.5.29 · CHANGELOG p0.5.29 · STREAM_FORMAT(type buy·sell · use_good·use_shop_item) · prompts/README(trade.md)",
      re.search(r"(?<![\w])verify_trade(?![\w])", src("_run_gates.sh")) is not None
      and tuple(int(x) for x in src("VERSION").strip().split(".")) >= (0, 5, 29) and "## 0.5.29" in src("docs", "PATCH_NOTES.md")
      and "p0.5.29" in src("docs", "CHANGELOG.md") and '`type:"buy"`' in sf and '`type:"sell"`' in sf and "use_good" in sf and "use_shop_item" in sf
      and "actions/trade.md" in src("prompts", "README.md"))
check("⑨ 행동·관측 계약 compose-v0.6(p0.5.29b — 동사 세트가 바뀐 패치가 올린다): CA.PROFILE·CA.SCHEMA · 결정 메타 compose_profile · 관측 action_schema · "
      "러너 판 run_meta.compose_profile · STREAM_FORMAT",
      CA.PROFILE == CA.SCHEMA == "compose-v0.6" and brains.action_metadata().get("compose_profile") == "compose-v0.6" and o3.get("action_schema") == "compose-v0.6"
      and rows7[0].get("kind") == "run_meta" and rows7[0].get("compose_profile") == "compose-v0.6" and "`compose-v0.6`" in sf,
      (CA.PROFILE, CA.SCHEMA, rows7[0].get("compose_profile"), o3.get("action_schema")))

shutil.rmtree(ROOT, ignore_errors=True)
print()
if C.failed:
    print("FAIL — %d/%d" % (C.failed, C.n))
    sys.exit(1)
print("ALL PASS — verify_trade (p0.5.29 buy · sell 동사: %d checks · 동사·세트·말 · 지침·관측 문장 · buy 사기 · sell 팔기 · 끊긴 use 길 · 결과 type · 러너 판 · 그대로인 길 · 배선, 실 LLM 0콜)" % C.n)

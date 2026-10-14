# -*- coding: utf-8 -*-
"""p0.5.13 골드와 가게(경제 1a — .orch/drafts/economy_design.md §2·§4.1·§5·§6·§7·§8.1, DECISIONS 2026-10-14 경제 §10) — 헤들리스 검증. LLM 0콜.
게이트:
  ① 정의·검증기: 장비점·잡화점 = 가게(파는 것·값·사들이는 값 = 설계 §5.2 초기 값표) · 숙소 셋 묵는 값 1·4·8 · 의뢰 보상 15·12·8 · 골드 아이템(설명·규칙) ·
     상인 둘의 선물 없음(판매로) + 맡은 가게 · 접수원·성직자 선물 그대로 · 검증기가 잘못된 가게·값·보상·맡은 가게를 거절한다
  ② 시작 지갑: 새 몸 골드 5 · 스트림 스냅샷 늘 gold · 관측 gold · '네 상태' 첫 줄 '골드 5' · 소지품 i7(골드 — 액수) · i8(보물 — 있을 때만) · 옛 관측(칸 없음)은 옛 줄
  ③ 가게 관측: 문턱 2칸 안에서만 가게 항목(상품 g1~g5 · 사들이는 값) + 상품 대상(값·설명) · 3칸 밖·끈 판(마을 생활 꺼짐)엔 없다 · 팔기 설명은 가게 곁에서만
  ④ 사기: 골드 모자람 = too_poor(지갑·소지 그대로) · 물약 = 골드 −10·물약 +1 · 빈손에 무기 = 바로 든다 · 들던 무기는 같은 번호로 발밑에 · 발밑이 차 있으면
     no_room(골드 그대로 — 원자적) · 3칸 밖은 못 산다(대상 소실 · 메뉴형 too_far) · 목격은 물건 이름만(값·지갑 없음)
  ⑤ 팔기: 보물 2개 = +12(amount) · 지닌 것보다 많이 = not_enough(그대로) · 골드·축복은 안 산다(no_deal) · 장비점 장검 = 15(절반) · 잡화점 물약 = 5 ·
     장비점은 물약을 안 산다 · 1인칭 문장·궤적 꼬리표·관전 요약 · D39 태그
  ⑥ 묵기 값: 모자라면 too_poor(HP·지갑 그대로) · 묵으면 값을 내고 다 낫는다(paid·gold) · '대상의 현재 사실' 줄에 값
  ⑦ 건네기: 골드 3(amount) · 보물 2개 · 빼면 1 · 지닌 것보다 많이 = not_enough(둘 다 그대로) · 받은 쪽 기록(액수·제 지갑) · 곁의 목격은 액수 없음 ·
     입력 칸 amount: 정수 1~9999 · 엉뚱한 값은 invalid_amount · 물약에 붙인 amount 는 버린다
  ⑧ 의뢰 보상: 보고한 사람에게 완수한 의뢰의 골드 · 장부 paid · 두 번째 보고는 다시 주지 않는다 · 미완은 보상 없음 · 게시판 보상 문장 'N골드' · NPC 두뇌 장면에 보상
  ⑨ 선물 → 판매: 장비 상인·아이템 상인에게 말을 걸면 대화만(npc_talk · npc_offer 빈 목록) · 접수원은 물약+단검·성직자는 축복 그대로 · 상인 문장에 선물 말 없음 ·
     NPC 두뇌 사실에 맡은 가게의 값(마을 생활 판만 — 옛 마을은 값을 말하지 않는다)
  ⑩ 메뉴형: 가게 곁이면 '사기:' 메뉴 줄 · 그 줄(interact g<n>)로 산다
  ⑪ 저장 이관(5→6): 옛 몸에 골드 5 · 이미 보고한 완수는 보상 받은 것으로 · 보고 전 완수는 다음 보고에 받는다 · 피클에 얼어 있던 상인 선물·옛 대사가 지금 정의로
  ⑫ 러너 판(더미 · 임시 state · 각본 두뇌): 공동 숙소에 묵고(1골드) 잡화점에서 물약을 사려다 모자란다 — 스트림 tick.bots[].gold(늘) · lodged paid · too_poor ·
     층 이월(_carry)이 골드를 옮긴다
  ⑬ 배선: 결과 어휘(IA.RESULTS) · 실패 결과의 resolution · 관전 화면(evline·FocusCard)이 새 결과·골드를 읽는다 · STREAM_FORMAT · _run_gates.sh 등록
"""
import contextlib
import copy
import io
import json
import os
import pickle
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = tempfile.mkdtemp(prefix="wl_shop_")
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

import brains                                        # noqa: E402
brains._call_claude = lambda prompt, model="haiku": ""   # LLM 무력화(0콜)
import composed_actions as CA                        # noqa: E402
import dungeon_gm as G                               # noqa: E402
import entities as ENT                               # noqa: E402
import info_guard as IG                              # noqa: E402
import interactables as IA                           # noqa: E402
import show_runner as R                              # noqa: E402
import snapshot as S                                 # noqa: E402
import time as _time                                 # noqa: E402
_time.sleep = lambda s: None
R.STEP_DELAY = 0


class C:
    failed = 0


def check(name, ok, detail=""):
    print("  %s %s%s" % ("OK  " if ok else "FAIL", name, (" — " + str(detail)) if (detail and not ok) else ""))
    if not ok:
        C.failed += 1


def src(*p):
    with open(os.path.join(HERE, *p), encoding="utf-8") as f:
        return f.read()


SHEETS = R.load_party(os.path.join(HERE, "party.json"))
NAMES = {c: SHEETS[c]["name"] for c in SHEETS}


def town(on=True, path=None, quests=False):
    """마을(마을 생활 켬/끔) + 파티 몸 셋. 정의의 말·값은 리포의 것 그대로."""
    old = R.TOWN_LIFE_ON
    R.TOWN_LIFE_ON = on
    try:
        d, starts = R.build_town(path, apart=True, walkers=True, guide=True, quests=(G.new_quests() if quests else None))
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


def near(d, f, bots=(), lo=1, hi=2, skip=()):
    """피처 f 와 같은 구역의 빈 바닥 칸(체비셰프 lo~hi, 가까운 순 — 다른 몸·skip 이 없는)."""
    taken = {(o["x"], o["y"]) for o in bots} | set(skip)
    z = d._town_zone(f.x, f.y)
    return min(((max(abs(x - f.x), abs(y - f.y)), x, y) for y in range(d.h) for x in range(d.w)
                if d.grid[y][x] == G.FLOOR and d.feature_at(x, y) is None and (x, y) not in taken and d._town_zone(x, y) == z
                and lo <= max(abs(x - f.x), abs(y - f.y)) <= hi))[1:]


def put(b, xy):
    b["x"], b["y"] = xy


def act(d, b, bots, action):
    d.view(b, bots)                                   # 관측 = 참조(_target_refs)를 새로 짓는다(실판과 같은 순서)
    return d.act(b, dict(action), bots)


def wire(d, b, bots):
    return brains._wire(d.view(b, bots), NAMES, compose=True)


# ─────────────────────────────────────────────────────────────────────────────
print("── ① 정의·검증기")
eq_use, gs_use = ENT.comps_of("equipment_store", True)["use"], ENT.comps_of("general_store", True)["use"]
check("① 장비점 = 가게: 단검 8 · 가죽 갑옷 12 · 장검 30 · 사슬 갑옷 45 · 보물 6에 사들임(설계 §5.2) · 끈 판(life 없이)엔 쓰임이 없다",
      eq_use["kind"] == "shop" and [(e["item"], e["price"]) for e in eq_use["sells"]] == [("dagger", 8), ("leather_armor", 12), ("longsword", 30), ("chain_mail", 45)]
      and eq_use["buys"] == {"treasure": 6} and ENT.comps_of("equipment_store", False).get("use") is None)
check("① 잡화점 = 가게: 회복 물약 10 · 보물 6에 사들임 · 휴대식(1b)·두건(MP 8)은 아직 없다",
      gs_use["kind"] == "shop" and [(e["item"], e["price"]) for e in gs_use["sells"]] == [("potion", 10)] and gs_use["buys"] == {"treasure": 6})
check("① 숙소 셋의 묵는 값: 공동 숙소 1 · 일반 여관 4 · 정원 숙소 8",
      [ENT.comps_of(e, True)["use"].get("price") for e in ("shared_lodging", "ordinary_inn", "garden_inn")] == [1, 4, 8]
      and all(ENT.comps_of(e, True)["use"]["kind"] == "lodge" for e in ("shared_lodging", "ordinary_inn", "garden_inn")))
check("① 의뢰 보상: 고블린 소탕 15 · 2층 답사 12 · 잃어버린 장신구 8 — 보상 문장은 'N골드'",
      [G.quest_def(q)["gold"] for q in ("goblin_cull", "reach_floor_2", "lost_trinket")] == [15, 12, 8]
      and G.quest_def("goblin_cull")["reward"] == "15골드")
check("① 상인 둘의 선물 없음(판매로) + 맡은 가게 · 여관주인은 맡은 숙소 · 접수원(물약+단검)·성직자(축복) 선물은 그대로",
      ENT.npc("gear_merchant")["gift"] is None and ENT.npc("item_merchant")["gift"] is None
      and ENT.npc("gear_merchant")["shop"] == "equipment_store" and ENT.npc("item_merchant")["shop"] == "general_store"
      and ENT.npc("innkeeper")["shop"] == "ordinary_inn"
      and ENT.npc("guild_receptionist")["gift"] == {"potions": 1, "weapon": "단검"} and ENT.npc("temple_attendant")["gift"].get("boon"))
gdef = ENT.item_def("gold")
check("① 골드 = 아이템(type gold · 설명) · 다루는 규칙 둘(골드·보물)이 amount 를 말한다 · 시작 지갑 상수 5",
      gdef is not None and gdef["name"] == "골드" and "gold" in ENT.ITEM_TYPES and "`amount`" in ENT.item_rule("gold")
      and "`amount`" in ENT.item_rule("treasure") and G.START_GOLD == 5)
P = ENT._use_problems
check("① 검증기(가게): 빈 상품 · 값 0 · 같은 물건 둘 · 모르는 buys type · once 를 거절한다",
      P("t", {"kind": "shop", "sells": []}) and P("t", {"kind": "shop", "sells": [{"item": "potion", "price": 0}]})
      and P("t", {"kind": "shop", "sells": [{"item": "potion", "price": 3}, {"item": "potion", "price": 4}]})
      and P("t", {"kind": "shop", "sells": [{"item": "potion", "price": 3}], "buys": {"gold": 1}})
      and P("t", {"kind": "shop", "sells": [{"item": "potion", "price": 3}], "once": True})
      and not P("t", {"kind": "shop", "sells": [{"item": "potion", "price": 3}], "buys": {"treasure": 2}}))
defs = ENT.load()
SP = lambda u: ENT._shop_problems("t", u, defs)   # noqa: E731
check("① 검증기(가게 2차): 아이템이 아닌 것(통)·축복의 물약·보물을 팔 수 없다 · buys 가 파는 type 과 겹치면 거절",
      SP({"kind": "shop", "sells": [{"item": "barrel", "price": 3}]}) and SP({"kind": "shop", "sells": [{"item": "boon", "price": 3}]})
      and SP({"kind": "shop", "sells": [{"item": "treasure", "price": 3}]})
      and SP({"kind": "shop", "sells": [{"item": "potion", "price": 3}], "buys": {"potion": 1}})
      and not SP({"kind": "shop", "sells": [{"item": "dagger", "price": 3}], "buys": {"treasure": 1}}))


def problems_with(edit):
    """정의 사본(임시 폴더)에 edit(defs 사전) 을 가하고 읽은 문제 목록."""
    root = tempfile.mkdtemp(prefix="defs_", dir=ROOT)
    for d_ in ENT.load().values():
        pass
    import glob
    import shutil
    for p in glob.glob(os.path.join(ENT.ROOT, "*", "*.json")):
        dst = os.path.join(root, os.path.basename(os.path.dirname(p)))
        os.makedirs(dst, exist_ok=True)
        shutil.copy(p, dst)
    edit(root)
    try:
        ENT.read(root)
        return ""
    except ENT.EntityError as e:
        return str(e)


def jedit(root, kind, eid, fn):
    p = os.path.join(root, kind, eid + ".json")
    with open(p, encoding="utf-8") as f:
        dd = json.load(f)
    fn(dd)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(dd, f, ensure_ascii=False)


e1 = problems_with(lambda r: jedit(r, "quest", "goblin_cull", lambda d_: d_["comps"]["quest"].update(gold=0)))
e2 = problems_with(lambda r: jedit(r, "npc", "smith", lambda d_: d_["comps"]["npc"].update(shop="temple")))
e3 = problems_with(lambda r: jedit(r, "building", "shared_lodging", lambda d_: d_["comps"]["life"]["use"].update(price=-1)))
e4 = problems_with(lambda r: jedit(r, "building", "general_store", lambda d_: d_["comps"]["life"]["use"]["sells"].append({"item": "nope", "price": 3})))
check("① 검증기(정의 읽기): 보상 0 · 쓰임 없는 건물을 맡은 가게로 · 음수 묵는 값 · 없는 상품을 로드 단계에서 거절한다",
      "quest.gold" in e1 and "npc.shop" in e2 and "price" in e3 and "'nope'" in e4, (e1[:80], e2[:80], e3[:80], e4[:80]))

# ─────────────────────────────────────────────────────────────────────────────
print("── ② 시작 지갑·관측")
d, bots = town(on=True, quests=True)
b1, b2, b3 = bots
obs = d.view(b1, bots)
w = brains._wire(obs, NAMES, compose=True)
check("② 새 몸 골드 5 · 스트림 스냅샷에 gold · 관측 gold",
      b1["gold"] == 5 and G.bot_snapshot(b1)["gold"] == 5 and obs["gold"] == 5)
check("② '네 상태' 첫 줄에 '골드 5' · 소지품 i7 골드(액수 · 설명·규칙) · 보물이 없으면 i8 없음",
      "- HP %d/%d, 골드 5, 모은 보물 0개" % (b1["hp"], b1["maxhp"]) in w
      and any(t["id"] == "i7" and t["name"] == "골드" and t["count"] == 5 for t in obs["items"])
      and "[i7] 골드 (item, currency) · 5골드" in w and not any(t["id"] == "i8" for t in obs["items"]))
b1["bag"] = 2
obs = d.view(b1, bots)
check("② 보물이 있으면 i8(개수 · 설명에 amount 규칙)",
      any(t["id"] == "i8" and t["name"] == "보물" and t["count"] == 2 and "`amount`" in t.get("rule", "") for t in obs["items"]))
b1["bag"] = 0
old_obs = {k: v for k, v in d.view(b1, bots).items() if k != "gold"}
check("② 옛 관측(gold 칸 없음)은 옛 줄 그대로 — '모은 보물'이 첫 칸",
      "- HP %d/%d, 모은 보물 0개" % (b1["hp"], b1["maxhp"]) in brains._wire(old_obs, NAMES, compose=True))
check("② 관측 칸 등록 — 그리지 않는 칸 없음(gold 포함)", not brains.unwired_keys(d.view(b1, bots)))

# ─────────────────────────────────────────────────────────────────────────────
print("── ③ 가게 관측")
EQ, GS = by_name(d, "장비점"), by_name(d, "잡화점")
put(b1, stand_by(d, EQ, bots))
obs = d.view(b1, bots)
shop_n = [n for n in obs.get("notices") or [] if n.get("kind") == "shop"]
goods_t = [t for t in obs["targets"] if t["kind"] == "good"]
w = brains._wire(obs, NAMES, compose=True)
check("③ 장비점 곁: 가게 항목 하나(상품 g1~g4 · 사들이는 값 보물 6·단검 4·가죽 갑옷 6·장검 15·사슬 갑옷 22)",
      len(shop_n) == 1 and [g["tid"] for g in shop_n[0]["goods"]] == ["g1", "g2", "g3", "g4"]
      and [(x["name"], x["price"]) for x in shop_n[0]["buys"]] == [("보물", 6), ("단검", 4), ("가죽 갑옷", 6), ("장검", 15), ("사슬 갑옷", 22)], shop_n)
check("③ 상품 대상 넷(값·가게 이름·물건 설명·다루는 규칙) · 프롬프트 줄 '[g3] 장검 (item, good) · 값 30골드 (장비점)' · 팔기 설명은 가게 항목에",
      [t["id"] for t in goods_t] == ["g1", "g2", "g3", "g4"] and all(t.get("desc") and t.get("rule") for t in goods_t)
      and "- [g3] 장검 (item, good) · 값 30골드 (장비점)" in w and "팔기: `target` 은 이 가게(f%d)" % EQ.id in w
      and "  · [g1] 단검 — 8골드" in w and "사들이는 값: 보물 6골드" in w)
far = next((x, y) for y in range(d.h) for x in range(d.w)
           if d.grid[y][x] == G.FLOOR and d.feature_at(x, y) is None and max(abs(x - EQ.x), abs(y - EQ.y)) == 3)
put(b1, far)
obs_far = d.view(b1, bots)
check("③ 문턱 3칸 밖: 가게 항목·상품 대상·팔기 설명 없음",
      not [n for n in obs_far.get("notices") or [] if n.get("kind") == "shop"] and not [t for t in obs_far["targets"] if t["kind"] == "good"]
      and "팔기:" not in brains._wire(obs_far, NAMES, compose=True))
d_off, bots_off = town(on=False)
check("③ 마을 생활을 끈 판: 가게가 없다(상품 0 · 가게 항목 0) — 묵기도 없다",
      IA.shops(d_off) == [] and IA.goods(d_off) == []
      and not any(IA.notices(d_off, b) for b in bots_off))
check("③ 상품 번호: 가게(피처 번호 순) × sells 순 — g5 = 잡화점 회복 물약 10",
      [(g["gid"], g["name"], g["price"]) for g in IA.goods(d)] == [("g1", "단검", 8), ("g2", "가죽 갑옷", 12), ("g3", "장검", 30), ("g4", "사슬 갑옷", 45), ("g5", "회복 물약", 10)]
      and IA.good(d, "g5")["fid"] == GS.id)

# ─────────────────────────────────────────────────────────────────────────────
print("── ④ 사기")
put(b1, stand_by(d, GS, bots))
b1["gold"], b1["potions"] = 5, 0
r = act(d, b1, bots, {"type": "use", "target": "g5"})
check("④ 골드 5로 물약(10) = too_poor — 지갑·소지 그대로 · 실패(resolution failed) · 문장 '값이 10골드인데 지닌 골드가 5다'",
      r["result"] == "too_poor" and r["price"] == 10 and r["gold"] == 5 and b1["gold"] == 5 and b1["potions"] == 0
      and r["resolution"]["status"] == "failed" and "값이 10골드인데 지닌 골드가 5다" in brains._last_prose(r), r)
b1["gold"] = 23
r = act(d, b1, bots, {"type": "use", "target": "g5"})
check("④ 골드 23으로 물약 = bought — 골드 13 · 물약 1 · 문장 '잡화점에서 회복 물약을 샀다 — 10골드를 냈다(남은 골드 13)'",
      r["result"] == "bought" and b1["gold"] == 13 and b1["potions"] == 1 and r["potions"] == 1 and r["effect_type"] == "interact"
      and brains._last_prose(r).startswith("잡화점에서 회복 물약을 샀다 — 10골드를 냈다(남은 골드 13)"), r)
b1["gold"] = 12
r = act(d, b1, bots, {"type": "use", "target": "g5", "item": "i7", "amount": 1})
check("④ 골드(i7)를 상품에 써도 산다 — 값은 가게가 정한다(적은 액수 1은 보지 않는다) · 골드 2 · 물약 2",
      r["result"] == "bought" and b1["gold"] == 2 and b1["potions"] == 2, r)
put(b1, stand_by(d, EQ, bots))
b1["weapon"], b1["gold"] = None, 40
r = act(d, b1, bots, {"type": "use", "target": "g1"})
check("④ 빈손에 단검(8) = 바로 든다(+1 · 손에서 태어난 번호) · 골드 32",
      r["result"] == "bought" and b1["weapon"]["name"] == "단검" and b1["weapon"]["bonus"] == 1 and b1["gold"] == 32 and r["slot"] == "weapon", r)
dagger_id = b1["weapon"]["id"]
r = act(d, b1, bots, {"type": "use", "target": "g3"})
dropped = d.features.get(dagger_id)
check("④ 단검을 든 채 장검(30) = 장검을 들고 단검은 같은 번호로 발밑에(바꿔 들기 문법) · 골드 2",
      r["result"] == "bought" and b1["weapon"]["name"] == "장검" and b1["gold"] == 2 and r.get("dropped") == "단검"
      and dropped is not None and (dropped.x, dropped.y) == (b1["x"], b1["y"]) and dropped.type == "weapon", r)
b1["gold"] = 60
r = act(d, b1, bots, {"type": "use", "target": "g1"})
check("④ 발밑이 차 있는데(내려놓은 단검) 무기를 사면 no_room — 골드·손 그대로(원자적)",
      r["result"] == "no_room" and b1["gold"] == 60 and b1["weapon"]["name"] == "장검", r)
put(b1, far)
obs_f = d.view(b1, bots)
r_far = d._interact(b1, "g1", bots)
check("④ 3칸 밖: 상품이 대상이 아니다(조합형 invalid_target) · 메뉴형 interact g1 = too_far · 골드 그대로",
      CA.parse({"type": "use", "target": "g1"}, obs_f)[1] == "invalid_target" and r_far["result"] == "too_far" and b1["gold"] == 60, r_far)
check("④ 묵은 참조(작정·자동 접근이 들고 다니는 g1)도 3칸 밖에선 실물이 아니다 — 2칸 안에선 실물",
      CA.entity(d, b1, "g1", bots, refs={"g1": {"kind": "good", "gid": "g1", "shop": "f%d" % EQ.id}}) is None
      and CA.entity(d, dict(b1, x=EQ.x, y=EQ.y + 2 if d.grid[EQ.y + 2][EQ.x] == G.FLOOR else EQ.y), "g1", bots,
                    refs={"g1": {"kind": "good", "gid": "g1", "shop": "f%d" % EQ.id}}) is not None)


def wall_scene(wall):
    """p0513b(Codex 리뷰 P2) 합성 장면 — 2칸 거리의 가게 하나(쓰임은 세계의 상태 use_over), 사이에 벽이 있거나 없다."""
    ds, st = G.Dungeon.from_ascii(["#######", "#1%s..>#" % ("#" if wall else "."), "#######"], seed=7)
    ds.composed_actions = True
    fid = ds._add_feature("building", "시험 가게", 3, 1)
    ds.use_over = {fid: {"kind": "shop", "sells": [{"item": "potion", "price": 3}]}}
    bs = G.spawn(ds, "1", [], sheet=G.HEROES["1"])
    put(bs, st["1"])
    return ds, bs, fid


dw, bw, fw = wall_scene(True)
do, bo, fo = wall_scene(False)
ow, oo = dw.view(bw, [bw]), do.view(bo, [bo])
ref_ = {"g1": {"kind": "good", "gid": "g1", "shop": "f%d" % fw}}
rw, ro = dw._interact(bw, "g1", [bw]), do._interact(bo, "g1", [bo])
check("④ p0513b(리뷰 P2): 2칸 안이어도 벽 너머(안 보이는) 가게 = 가게 항목·상품 대상 없음 · 묵은 참조도 실물 아님 · 사기 no_target(골드 그대로) — 벽이 없으면 보이고 산다",
      not IA.notices(dw, bw) and not [t for t in ow["targets"] if t["kind"] == "good"]
      and CA.entity(dw, bw, "g1", [bw], refs=ref_) is None and rw["result"] == "no_target" and bw["gold"] == 5
      and IA.notices(do, bo) and [t["id"] for t in oo["targets"] if t["kind"] == "good"] == ["g1"]
      and CA.entity(do, bo, "g1", [bo], refs=ref_) is not None and ro["result"] == "bought" and bo["gold"] == 2, (rw, ro))
for o in bots:
    o.pop("witnessed", None)
put(b1, stand_by(d, GS, bots))
put(b2, near(d, GS, bots, 1, 4, skip=[(b1["x"], b1["y"])]))
b1["gold"] = 20
act(d, b1, bots, {"type": "use", "target": "g5"})
seen = [x for x in (b2.get("witnessed") or []) if x.get("kind") == "ally_use"]
check("④ 곁의 사람은 '회복 물약을 샀다'를 본다 — 값·남은 지갑은 없다",
      seen and seen[-1].get("result") == "회복 물약을 샀다" and not any(k in seen[-1] for k in ("price", "gold")), seen)

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑤ 팔기")
put(b1, (EQ.x, EQ.y))                                 # 문턱 칸(발밑 — 문턱은 몸을 막지 않는다): ④ 에서 내려놓은 단검이 곁 칸을 차지하고 있다
b1["bag"], b1["gold"] = 3, 0
r = act(d, b1, bots, {"type": "use", "target": "f%d" % EQ.id, "item": "i8", "amount": 2})
check("⑤ 장비점에 보물 2개(amount) = sold — +12 · 보물 1 · 문장 '장비점에 보물 2개를 팔았다 — 12골드를 받았다(지금 골드 12)'",
      r["result"] == "sold" and r["n"] == 2 and r["got"] == 12 and b1["gold"] == 12 and b1["bag"] == 1
      and brains._last_prose(r) == "장비점에 보물 2개를 팔았다 — 12골드를 받았다(지금 골드 12)", r)
r = act(d, b1, bots, {"type": "use", "target": "f%d" % EQ.id, "item": "i8", "amount": 5})
check("⑤ 지닌 것(1)보다 많이(5) = not_enough — 보물·골드 그대로 · 실패", r["result"] == "not_enough" and r["have"] == 1 and b1["bag"] == 1
      and b1["gold"] == 12 and r["resolution"]["status"] == "failed", r)
r = act(d, b1, bots, {"type": "use", "target": "f%d" % EQ.id, "item": "i7", "amount": 3})
check("⑤ 골드는 안 산다(no_deal — 그대로) · 문장 '이 가게는 골드를 사들이지 않는다'",
      r["result"] == "no_deal" and b1["gold"] == 12 and "이 가게는 골드를 사들이지 않는다" in brains._last_prose(r), r)
b1["boons"] = 1
r = act(d, b1, bots, {"type": "use", "target": "f%d" % EQ.id, "item": "i4"})
check("⑤ 축복의 물약도 안 산다(신의 몫 — no_deal, 그대로)", r["result"] == "no_deal" and b1["boons"] == 1, r)
b1["weapon"] = {"id": d._alloc_fid(), "name": "장검", "bonus": 2, "worn": [b1["char"]]}
r = act(d, b1, bots, {"type": "use", "target": "f%d" % EQ.id, "item": "i2"})
check("⑤ 장비점에 장검 = 파는 값의 절반 15 · 손이 빈다", r["result"] == "sold" and r["got"] == 15 and b1["weapon"] is None and b1["gold"] == 27, r)
b1["potions"] = 2
r = act(d, b1, bots, {"type": "use", "target": "f%d" % EQ.id, "item": "i1"})
check("⑤ 장비점은 물약을 안 산다(no_deal)", r["result"] == "no_deal" and b1["potions"] == 2, r)
put(b1, (GS.x, GS.y))
r = act(d, b1, bots, {"type": "use", "target": "f%d" % GS.id, "item": "i1", "amount": 2})
check("⑤ 잡화점은 물약을 5(절반)에 산다 — 물약에 붙인 amount 는 버려져 한 병씩", r["result"] == "sold" and r["got"] == 5 and b1["potions"] == 1 and r["n"] == 1, r)
tags = G.event_tags(r)
check("⑤ 궤적 꼬리표(새 키 없음 · EVENT_KINDS 안) · 관전 요약 = 1인칭 문장 · D39 태그 '들러 봄'·'회복 물약 1개 팖'",
      all(k in G.EVENT_KINDS for k, _, _ in tags) and tags[0][1] == "팔기" and R.act_summary(r) == IA.prose(r)
      and IA.tried(d, GS) == "들러 봄" and (b1.get("obj_tags") or {}).get(GS.id, {}).get("note") == "회복 물약 1개 팖", (tags, b1.get("obj_tags")))
r = act(d, b1, bots, {"type": "use", "target": "f%d" % GS.id})
check("⑤ 물건 없이 가게를 쓰면 진열·값(browsed + buys) — '잡화점에 진열된 것을 구경했다: 회복 물약 10골드 · 사들이는 것: 보물 6골드, 회복 물약 5골드'",
      r["result"] == "browsed" and IA.prose(r) == "잡화점에 진열된 것을 구경했다: 회복 물약 10골드 · 사들이는 것: 보물 6골드, 회복 물약 5골드", r)

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑥ 묵기 값")
INN = by_name(d, "일반 여관")
put(b2, stand_by(d, INN, bots))
b2["hp"], b2["gold"], b2["status"] = 3, 3, {"출혈": {"n": 1, "by": "x", "since": 0}}
r = act(d, b2, bots, {"type": "use", "target": "f%d" % INN.id})
check("⑥ 골드 3으로 일반 여관(4) = too_poor — HP·상태·지갑 그대로 · 문장 '일반 여관에 묵으려 했다 — 값이 4골드인데 지닌 골드가 3다'",
      r["result"] == "too_poor" and r["use_kind"] == "lodge" and b2["hp"] == 3 and b2["gold"] == 3 and b2["status"]
      and IA.prose(r) == "일반 여관에 묵으려 했다 — 값이 4골드인데 지닌 골드가 3다", r)
b2["gold"] = 9
r = act(d, b2, bots, {"type": "use", "target": "f%d" % INN.id})
check("⑥ 골드 9로 묵으면 4를 내고 다 낫는다(paid 4 · gold 5 · 상태 소거) · 문장 꼬리 '4골드를 냈다(남은 골드 5)'",
      r["result"] == "lodged" and r["paid"] == 4 and r["gold"] == 5 and b2["gold"] == 5 and b2["hp"] == b2["maxhp"] and not b2["status"]
      and IA.prose(r).endswith("· 4골드를 냈다(남은 골드 5)"), r)
check("⑥ '대상의 현재 사실'·메뉴 줄 꼬리에 값 — '묵으면 HP 가 전부 돌아오고 몸 상태가 낫는다 — 값 4골드'",
      "- f%d 일반 여관: 묵으면 HP 가 전부 돌아오고 몸 상태가 낫는다 — 값 4골드" % INN.id in wire(d, b2, bots))

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑦ 건네기")
b3["x"], b3["y"] = next((b2["x"] + dx, b2["y"] + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)   # b2 곁(체비셰프 1)의 빈 바닥 — 건네기는 곁에서
                        if (dx or dy) and d.grid[b2["y"] + dy][b2["x"] + dx] == G.FLOOR and d.feature_at(b2["x"] + dx, b2["y"] + dy) is None
                        and not any((o["x"], o["y"]) == (b2["x"] + dx, b2["y"] + dy) for o in bots))
put(b1, near(d, INN, bots, 1, 4))                     # 곁에서 지켜보는 사람(같은 구역)
for o in bots:
    o.pop("witnessed", None)
b2["gold"], b3["gold"] = 10, 1
r = act(d, b2, bots, {"type": "give", "target": "b" + b3["char"], "item": "i7", "amount": 3})
rec = b3.get("last") or {}
check("⑦ 골드 3 = 건넨 쪽 7 · 받은 쪽 4(원자적) · 결과 what '골드 3' · 받은 기록(액수·받은 쪽 지갑)",
      r["result"] == "given" and r["what"] == "골드 3" and r["amount"] == 3 and b2["gold"] == 7 and b3["gold"] == 4
      and rec.get("type") == "received" and rec.get("amount") == 3 and rec.get("gold") == 4, (r, rec))
check("⑦ 문장: '…에게 골드 3을(를) 건넸다 (남은 골드 7)' · 받은 쪽 '…에게서 골드 3을(를) 받았다 (지금 골드 4)'",
      brains._last_prose(r).endswith("골드 3을(를) 건넸다 (남은 골드 7)") and brains._last_prose(rec).endswith("골드 3을(를) 받았다 (지금 골드 4)"),
      (brains._last_prose(r), brains._last_prose(rec)))
wit = [x for o in bots if o is not b2 and o is not b3 for x in (o.get("witnessed") or []) if x.get("kind") == "ally_give"]
check("⑦ 받은 기록에 건넨 쪽의 지갑이 없다 · 곁의 목격은 '골드'뿐(액수 없음)",
      rec.get("gold") == 4 and wit and all(x.get("what") == "골드" for x in wit), (rec, wit))
r = act(d, b2, bots, {"type": "give", "target": "b" + b3["char"], "item": "i7", "amount": 30})
check("⑦ 지닌 것(7)보다 많이(30) = not_enough — 둘 다 그대로 · 문장 '지닌 골드가 7다(30골드를 건네려 했다)'",
      r["result"] == "not_enough" and b2["gold"] == 7 and b3["gold"] == 4 and "지닌 골드가 7다(30골드를 건네려 했다)" in brains._last_prose(r), r)
r = act(d, b2, bots, {"type": "give", "target": "b" + b3["char"], "item": "i7"})
check("⑦ amount 를 빼면 1골드", r["result"] == "given" and r["amount"] == 1 and b2["gold"] == 6 and b3["gold"] == 5, r)
d.view(b2, bots)
refs7 = dict(b2["_target_refs"])                    # 작정(then)이 들고 다니는 참조 — 그때의 액수(6)
b2["gold"], b2["bag"] = 5, 2
check("⑦ p0513b(리뷰 권장): 골드·보물은 수량형 — 액수가 바뀌어도 작정의 i7·i8 참조가 그대로 실물(다음 건네기가 plan_broken 이 되지 않는다)",
      CA.entity(d, b2, "i7", bots, refs=refs7) is not None and refs7.get("i8") is None
      and CA.entity(d, b2, "i8", bots, refs={**refs7, "i8": {"kind": "item", "slot": "treasure", "value": 9}}) is not None)
b2["gold"] = 6
b2["bag"], b3["bag"] = 3, 0
r = act(d, b2, bots, {"type": "give", "target": "b" + b3["char"], "item": "i8", "amount": 2})
check("⑦ 보물 2개 = 건넨 쪽 1 · 받은 쪽 2 · what '보물 2개'", r["result"] == "given" and r["what"] == "보물 2개" and b2["bag"] == 1 and b3["bag"] == 2, r)
pub = IG.public(b3["last"], b3)
check("⑦ 받은 쪽 공개 사본(IG.public) = 받은 것·개수·제 보물 수뿐 — 건넨 쪽의 남은 것(보물 1·골드)은 없다",
      set(pub) == {"char", "type", "from", "what", "item", "amount", "bag"} and pub["bag"] == 2 and pub["amount"] == 2, pub)
o7 = d.view(b2, bots)
check("⑦ 입력 칸 amount: '3' → 3 · 3.0 → 3 · 0·-1·'세 개'·10000·true → invalid_amount · 물약에 붙이면 버린다",
      CA.parse({"type": "give", "target": "b" + b3["char"], "item": "i7", "amount": "3"}, o7)[0].get("amount") == 3
      and CA.parse({"type": "give", "target": "b" + b3["char"], "item": "i7", "amount": 3.0}, o7)[0].get("amount") == 3
      and all(CA.parse({"type": "give", "target": "b" + b3["char"], "item": "i7", "amount": v}, o7)[1] == "invalid_amount"
              for v in (0, -1, "세 개", 10000, True))
      and "amount" not in (CA.parse({"type": "give", "target": "b" + b3["char"], "item": "i8", "amount": None}, o7)[0] or {}))
g_before = (b2["gold"], b3["gold"])
r_bad = d._give(b2, "b" + b3["char"], "gold", bots, amount="많이")
check("⑦ 메뉴형·BYO 길(parse 없이 엔진 지점)의 엉뚱한 amount 는 1로 읽는다 — 죽지 않는다 · 음수로 지갑이 늘지 않는다",
      r_bad["result"] == "given" and r_bad["amount"] == 1 and (b2["gold"], b3["gold"]) == (g_before[0] - 1, g_before[1] + 1)
      and d._give(b2, "b" + b3["char"], "gold", bots, amount=-5)["amount"] == 1 and IA.count(None) == 1 and IA.count("3") == 3, r_bad)
b2["potions"] = 2
o7 = d.view(b2, bots)
check("⑦ 물약에 붙인 amount 는 행동에 실리지 않는다(한 병씩)",
      "amount" not in CA.parse({"type": "give", "target": "b" + b3["char"], "item": "i1", "amount": 2}, o7)[0])

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑧ 의뢰 보상")
dq, bq = town(on=True, quests=True)
Q = dq.quests
Q["accepted"] = {"goblin_cull": {"turn": 1, "by": "1"}, "lost_trinket": {"turn": 1, "by": "1"}, "reach_floor_2": {"turn": 1, "by": "2"}}
Q["done"] = {"goblin_cull": 5, "lost_trinket": 6}
Q["returned"] = 7
dq.expedition_returned = True
GR = by_name(dq, "길드 접수원")
rep_b = bq[1]
put(rep_b, stand_by(dq, GR, bq))
gold0 = rep_b["gold"]
r = act(dq, rep_b, bq, {"type": "use", "target": "f%d" % GR.id})
check("⑧ 보고한 사람에게 완수한 의뢰 둘의 골드(15+8=23) · 미완(2층 답사)은 보상 없음 · 장부 paid · 결과 reward·paid·gold",
      r["result"] == "npc_report" and r["reward"] == 23 and sorted(r["paid"]) == ["goblin_cull", "lost_trinket"]
      and rep_b["gold"] == gold0 + 23 and r["gold"] == rep_b["gold"] and set(Q["paid"]) == {"goblin_cull", "lost_trinket"}
      and all(bb["gold"] == 5 for bb in bq if bb is not rep_b), r)
check("⑧ 문장 '…원정을 보고했다 (…) — 보상 23골드를 받았다(지금 골드 28)' · 궤적 꼬리표 '보상 23골드'",
      brains._last_prose(r).endswith("— 보상 23골드를 받았다(지금 골드 28)") and "보상 23골드" in G.event_tags(r)[0][2], brains._last_prose(r))
scene = {}
brains._call_claude = lambda prompt, model="haiku": scene.setdefault("p", prompt) and ""
brains.npc_reply(rep_b, r, None, ["사실"], npc=dq.npc_defs.get(GR.name))
brains._call_claude = lambda prompt, model="haiku": ""
check("⑧ NPC 두뇌 장면에 '완수한 의뢰의 보상으로 23골드를 이 사람에게 건넸다'", "보상으로 23골드를 이 사람에게 건넸다" in scene.get("p", ""))
Q["reported"], Q["returned"] = None, 9
dq.expedition_returned = True
Q["done"]["reach_floor_2"] = 8
r2 = act(dq, rep_b, bq, {"type": "use", "target": "f%d" % GR.id})
check("⑧ 다음 원정의 보고 = 새로 완수한 2층 답사(12)만 — 앞서 받은 둘은 다시 주지 않는다",
      r2["result"] == "npc_report" and r2.get("reward") == 12 and r2["paid"] == ["reach_floor_2"] and rep_b["gold"] == gold0 + 35, r2)
Q["reported"], Q["returned"] = None, 11
dq.expedition_returned = True
r3 = act(dq, rep_b, bq, {"type": "use", "target": "f%d" % GR.id})
check("⑧ 새 완수 없이 또 보고 = 보상 칸 없음(골드 그대로)", r3["result"] == "npc_report" and "reward" not in r3 and rep_b["gold"] == gold0 + 35, r3)
obs_q = dq.view(bq[0], bq)
check("⑧ 게시판·맡은 의뢰의 보상 문장은 'N골드'(관측 · 메뉴 · NPC 사실)",
      "(보상: 15골드)" in brains._wire({**obs_q, "notices": dq._notices(bq[0]) or [{"kind": "board", "name": "모험가 길드", "quests": [
          {"title": "고블린 소탕", "goal": "x", "reward": "15골드"}]}]}, NAMES, compose=True)
      and "보상: 15골드" in " ".join(R.npc_facts(dq, GR.name, bq, [], Q)))

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑨ 선물 → 판매")
GM_, IM_ = by_name(d, "장비 상인"), by_name(d, "아이템 상인")
b4 = copy.deepcopy(b1)
b4.update(weapon=None, potions=0, boons=0, npc_met=set(), shop_served=set(), gold=5)
check("⑨ 상인 둘: 세계가 건넬 것이 없다(npc_offer 빈 목록) — 빈손이어도 · 마을의 선물 장부에 없다",
      d.npc_offer(b4, GM_.name) == [] and d.npc_offer(b4, IM_.name) == [] and GM_.name not in d.npc_gifts and IM_.name not in d.npc_gifts)
talks = {}
for f_ in (GM_, IM_):
    bb = copy.deepcopy(b4)
    put(bb, stand_by(d, f_, bots))
    talks[f_.name] = d._interact(bb, "f%d" % f_.id, [bb])
    check("⑨ %s에게 말을 걸면 대화만(npc_talk) — 소지 그대로" % f_.name,
          talks[f_.name]["result"] == "npc_talk" and bb["potions"] == 0 and bb["weapon"] is None, talks[f_.name])
GR_d = by_name(d, "길드 접수원")
bb = copy.deepcopy(b4)
put(bb, stand_by(d, GR_d, bots))
rg = d._interact(bb, "f%d" % GR_d.id, [bb])
check("⑨ 접수원 원정 물품은 그대로(물약 + 빈손이면 단검)", rg["result"] == "npc_gift" and bb["potions"] == 1 and bb["weapon"]["name"] == "단검", rg)
TA = by_name(d, "성직자")
bb = copy.deepcopy(b4)
put(bb, stand_by(d, TA, bots))
rt = d._interact(bb, "f%d" % TA.id, [bb])
check("⑨ 성직자 축복은 그대로", rt["result"] == "npc_gift" and bb.get("boons") == 1, rt)
texts = " ".join(str(v) for e in ("gear_merchant", "item_merchant") for v in ENT.npc(e, life=True).values() if isinstance(v, str))
texts += " ".join(str(v) for e in ("gear_merchant", "item_merchant") for v in (ENT.comps_of(e, True).get("story") or {}).values())
check("⑨ 상인 문장(대사·재방문·역할·성격·특징·이야기)에 선물·'값을 못 매겨'가 없다",
      not any(w_ in texts for w_ in ("가져가게", "단검 하나", "단검을 하나 준다", "물약 하나", "값을 못", "그냥 쥐여", "한 사람에 하나")), texts[:200])
facts_g = " ".join(R.npc_facts(d, GM_.name, bots, [], d.quests))
facts_i = " ".join(R.npc_facts(d, IM_.name, bots, [], d.quests))
facts_inn = " ".join(R.npc_facts(d, "여관주인", bots, [], d.quests))
check("⑨ NPC 두뇌 사실: 장비 상인 = 장비점 값(판다·사들인다) · 아이템 상인 = 잡화점 값 · 여관주인 = 묵는 값 4 · 깎아 주지 않는다",
      "판다: 단검 8골드 · 가죽 갑옷 12골드 · 장검 30골드 · 사슬 갑옷 45골드" in facts_g and "사들인다: 보물 6골드" in facts_g
      and "판다: 회복 물약 10골드" in facts_i and "묵는 값: 4골드" in facts_inn and "깎아 주지 않는다" in facts_g, (facts_g, facts_i, facts_inn))
d_old, bots_old = town(on=False, path=os.path.join(HERE, "town-v0.json"))
facts_old = " ".join(R.npc_facts(d_old, "장비 상인", bots_old, [], None))
check("⑨ 옛 마을(가게가 없다)의 장비 상인은 값을 말하지 않는다 — 선물도 없다",
      "골드" not in facts_old and "장비 상인" not in d_old.npc_gifts and "아이템 상인" not in d_old.npc_gifts, facts_old)

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑩ 메뉴형")
dm, bm = town(on=True)
dm.composed_actions = dm.auto_approach = False        # 메뉴형 경로(게이트·메뉴형 판) — verify_townlife ③ 과 같은 꼴
mb = bm[0]
put(mb, stand_by(dm, by_name(dm, "잡화점"), bm))
mb["gold"] = 12
opts = [o for o in dm.view(mb, bm)["options"] if o["type"] == "interact" and str(o.get("target", "")).startswith("g")]
check("⑩ 잡화점 곁의 메뉴 줄 '사기: 회복 물약 g5 — 10골드 (잡화점)' · 가게 줄 머리 '사고팔기:'",
      [o["label"] for o in opts] == ["사기: 회복 물약 g5 — 10골드 (잡화점)"]
      and any(o["label"].startswith("사고팔기: 잡화점") for o in dm.view(mb, bm)["options"]), [o["label"] for o in opts])
rm = dm.act(mb, {"type": "interact", "target": "g5"}, bm)
check("⑩ 그 줄(interact g5)로 산다 — 골드 2 · 물약 1", rm["result"] == "bought" and mb["gold"] == 2 and mb["potions"] == 1, rm)
wm = brains._wire(dm.view(mb, bm), NAMES, compose=False)
check("⑩ 메뉴형 관측의 가게 항목은 '상품 ID 를 use'라고 말하지 않는다(사기는 메뉴 줄)", "잡화점 f" in wm and "상품 ID 를 use" not in wm)

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑪ 저장 이관(5→6)")
ds, bs = town(on=True, quests=True)
GMs, IMs = by_name(ds, "장비 상인"), by_name(ds, "아이템 상인")
ds.npc_gifts[GMs.name], ds.npc_gifts[IMs.name] = {"weapon": "단검"}, {"potions": 1}           # 옛 피클에 얼어 있던 선물
ds.npc_lines[IMs.name] = "물약 하나 가져가게. 한 사람에 하나씩이야 — 던전에선 그게 목숨값이지."
ds.feature_roles[IMs.id] = "잡화점의 상인 · 한 사람에 물약 하나"
EQs = by_name(ds, "장비점")
ds.feature_roles[EQs.id] = "진열된 것 구경(아직 사고팔 수는 없다)"
ds.place_story[EQs.id] = {"trait": "무기와 방어구를 진열한 가게. 구경만 된다(사고팔기는 아직 없다)", "history": "옛 이야기"}
for b_ in bs:
    b_.pop("gold")
q5 = ds.quests
q5["accepted"] = {"goblin_cull": {"turn": 1, "by": "1"}, "lost_trinket": {"turn": 1, "by": "1"}}
q5["done"] = {"goblin_cull": 3, "lost_trinket": 9}
snap5 = {"version": 2, "state_version": 5, "d": ds, "bots": bs, "sheets": SHEETS, "quests": q5,
         "expedition": {"n": 2, "t0": 5, "fallen": 0, "said": ["goblin_cull"]}}
snap6 = S.upgrade(pickle.loads(pickle.dumps(snap5)))   # 이 프로세스가 방금 만든 바이트만 되읽는다(피클 왕복 = 이어가기와 같은 길) — 밖에서 온 데이터가 아니다
d6 = snap6["d"]
check("⑪ 판 번호 6 · 옛 몸마다 골드 5",
      S.STATE_VERSION == 6 and snap6["state_version"] == 6 and all(b_["gold"] == 5 for b_ in snap6["bots"]))
check("⑪ 앞선 결산이 적은 완수(고블린 소탕)는 보상 받은 것으로 · 보고 전 완수(장신구)는 아직 — 다음 보고에 받는다",
      set(snap6["quests"]["paid"]) == {"goblin_cull"})
GR6 = by_name(d6, "길드 접수원")
b6 = snap6["bots"][0]
d6.quests = snap6["quests"]
d6.quests["returned"] = 10
d6.expedition_returned = True
put(b6, stand_by(d6, GR6, snap6["bots"]))
r6 = act(d6, b6, snap6["bots"], {"type": "use", "target": "f%d" % GR6.id})
check("⑪ 이관 뒤 보고 = 장신구 8만", r6.get("reward") == 8 and r6["paid"] == ["lost_trinket"] and b6["gold"] == 13, r6)
check("⑪ 피클에 얼어 있던 상인 선물은 걷히고 대사·역할·가게의 역할·특징은 지금 정의로",
      GMs.name not in d6.npc_gifts and IMs.name not in d6.npc_gifts and d6.npc_lines[IMs.name] == ENT.npc("item_merchant", life=True)["line"]
      and d6.feature_roles[IMs.id] == ENT.npc("item_merchant", life=True)["role"]
      and d6.feature_roles[EQs.id] == ENT.comps_of("equipment_store", True)["building"]["role"]
      and d6.place_story[EQs.id]["trait"] == ENT.comps_of("equipment_store", True)["story"]["trait"]
      and "길드 접수원" in d6.npc_gifts)
q_rep = {"accepted": {"goblin_cull": {}}, "done": {"goblin_cull": 2}, "progress": {}, "returned": 3, "reported": 4}
s_rep = S.upgrade({"version": 2, "state_version": 5, "bots": [{"char": "1"}], "quests": q_rep})
check("⑪ 보고를 이미 찍은 옛 장부: 그 완수는 받은 것으로 · 이미 골드가 있는 몸은 그대로",
      set(s_rep["quests"]["paid"]) == {"goblin_cull"} and s_rep["bots"][0]["gold"] == 5
      and S.upgrade({"version": 2, "state_version": 5, "bots": [{"char": "1", "gold": 40}]})["bots"][0]["gold"] == 40)

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑫ 러너 판(더미 · 각본 두뇌)")
real_dummy = G.dummy_brain
plan12 = {}


def scripted(obs, char="?"):
    """1번: 공동 숙소에 묵고(1골드) → 잡화점에서 물약(10)을 사려 한다(모자람). 나머지는 서 있는다. 0콜 각본."""
    if not obs.get("town") or char != "1":
        return {"type": "wait"}
    st = plan12.setdefault(char, {"step": 0})
    feats = {f["name"]: f for f in (obs.get("sights") or {}).get("features") or []}
    if st["step"] == 0:                                # 묵을 때까지 다시 청한다(걷는 동안 인사·구역 경계로 멈추면 두뇌가 다시 고른다 — 실판과 같은 길)
        if (obs.get("last") or {}).get("result") == "lodged":
            st["step"] = 1
        else:
            f = feats.get("공동 숙소")
            return {"type": "use", "target": f["id"]} if f else {"type": "wait"}
    if st["step"] == 1:
        if any(t.get("id") == "g5" for t in obs.get("targets") or []):
            st["step"] = 2
            return {"type": "use", "target": "g5"}
        f = feats.get("잡화점")
        return {"type": "goto", "target": f["id"]} if f else {"type": "wait"}
    return {"type": "wait"}


st12 = tempfile.mkdtemp(prefix="run_", dir=ROOT)
old12 = (R.STATE, R.TOWN_LIFE_ON, G.dummy_brain)
R.STATE, R.TOWN_LIFE_ON, G.dummy_brain = st12, True, scripted
old12_turns, R.MAX_TURNS = R.MAX_TURNS, 160            # 광장 → 공동 숙소 → 잡화점까지 걸을 틱
try:
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            R.main()
        except SystemExit:
            pass
finally:
    R.STATE, R.TOWN_LIFE_ON, G.dummy_brain = old12
    R.MAX_TURNS = old12_turns
with open(os.path.join(st12, "stream.jsonl"), encoding="utf-8") as fh:
    rows12 = [json.loads(ln) for ln in fh if ln.strip()]
ticks = [r_ for r_ in rows12 if r_["kind"] == "tick"]
evs = [e for r_ in ticks for e in r_.get("events") or [] if e.get("char") == "1"]
lodged = next((e for e in evs if e.get("result") == "lodged"), None)
poor = next((e for e in evs if e.get("result") == "too_poor"), None)
g1 = [next(b_["gold"] for b_ in r_["bots"] if b_["char"] == "1") for r_ in ticks]
check("⑫ 판이 끝까지 돈다 · 모든 틱의 tick.bots[] 에 gold · 첫 틱 5",
      rows12[-1]["kind"] == "end" and all("gold" in b_ for r_ in ticks for b_ in r_["bots"]) and g1[0] == 5, (rows12[-1].get("kind"), g1[:3]))
check("⑫ 공동 숙소에 묵어 1골드를 냈다(paid 1 · 골드 4) · 잡화점에서 물약을 사려다 모자랐다(too_poor 10/4) · 스트림 골드 5 → 4",
      lodged and lodged.get("paid") == 1 and lodged.get("gold") == 4 and poor and poor.get("price") == 10 and poor.get("gold") == 4
      and g1[-1] == 4, ([(e.get("type"), e.get("result"), e.get("target")) for e in evs if e.get("result") not in ("walking",)][:12], g1[-1:]))
check("⑫ 층 이월(_carry)이 골드를 옮긴다 — 러너 소스(새 몸의 시작 지갑을 지닌 골드로 덮는다)",
      'n["gold"] = b.get("gold", 0)' in src("show_runner.py"))

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑬ 배선")
check("⑬ 결과 어휘(IA.RESULTS)에 bought·sold·too_poor·no_deal·not_enough·no_room · 쓰임 kind shop(검증기 ↔ 처리기)",
      {"bought", "sold", "too_poor", "no_deal", "not_enough", "no_room"} <= set(IA.RESULTS) and "shop" in IA.KINDS and "shop" in ENT.USE_KINDS)
check("⑬ 실패 결과의 resolution = failed(too_poor·no_deal·not_enough)",
      all(CA.decorate({"char": "1"}, {"type": "use"}, {"result": r_})["resolution"]["status"] == "failed" for r_ in ("too_poor", "no_deal", "not_enough")))
ev_ts, fc_ts = src("game", "src", "text", "evline.ts"), src("game", "src", "ui", "FocusCard.ts")
check("⑬ 관전 화면: 사건 줄이 새 결과를 읽는다(bought·sold·too_poor·no_deal·not_enough·no_room·paid·reward) · 초점 카드에 골드",
      all("r === '%s'" % r_ in ev_ts for r_ in ("bought", "sold", "too_poor", "no_deal", "not_enough", "no_room"))
      and "e.paid" in ev_ts and "e.reward" in ev_ts and "b.gold" in fc_ts and "gold?: number" in src("game", "src", "stream", "types.ts"))
check("⑬ p0513b(리뷰 P1): 초점 카드의 세는 칸(골드·보물·물약·축복)은 숫자만 · 이스케이프해 그린다 — 판 파일의 값을 그대로 innerHTML 에 넣지 않는다",
      "cnt(b.gold)" in fc_ts and "esc(String(gold))" in fc_ts and "esc(String(bag))" in fc_ts
      and not any(x in fc_ts for x in ("${b.gold}", "${b.bag}", "${b.potions ?? 0}", "${b.boons}")))
sf = src("STREAM_FORMAT.md")
check("⑬ STREAM_FORMAT: 골드와 가게 절(tick.bots[].gold · bought · sold · too_poor · npc_report reward · give amount)",
      "## 골드와 가게" in sf and all(k in sf for k in ("`bought`", "`sold`", "`too_poor`", "`reward`", "`amount`")))
check("⑬ _run_gates.sh 에 verify_shop 등록", "verify_shop" in src("_run_gates.sh"))

print("ALL PASS — verify_shop (p0.5.13 골드와 가게: 정의·지갑·가게 관측·사기·팔기·묵기 값·건네기·의뢰 보상·선물→판매·메뉴형·이관·러너·배선, 실 LLM 0콜)"
      if not C.failed else "FAIL %d — verify_shop" % C.failed)
raise SystemExit(1 if C.failed else 0)

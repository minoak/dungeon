# -*- coding: utf-8 -*-
"""아이템 설명 칸(p0.5.6, 2026-10-12 — .orch/drafts/item_desc_design.md · DECISIONS 10-12 "아이템이면 모두 설명이 붙어야 맞다") 게이트.
LLM 0콜, 라이브 데이터 무접촉(임시 폴더만 쓴다).
  ① 로드 거절: 정의·말 파일·규칙 파일을 임시 사본에서 깨뜨리면 한 번에 나열하며 죽는다 — 설명 없는 아이템 · 아이템 type 인데 item 부품 없음 ·
     엔진이 들 수 없는 것(상자)의 item 부품 · 태그만 있음 · item 부품의 모르는 칸 · 모르는 중괄호 자리 · 장비 아닌 것의 {bonus} · 축복 아닌 것의 {stat} ·
     규칙 칸 빠짐·남음·중괄호 · 모르는 선물 무기 이름 / 리포 정본은 그대로 읽힌다(아이템 7장 = ITEM_TYPES 전부 · 보물에 item 태그)
  ② 조회 전수(G7): 엔진이 몸·바닥에 아이템을 만드는 길마다 item_def 가 풀린다 — GEAR_CYCLE · 손그림 글리프($ ! ) [) · 숨은 보물 ·
     뒤지기 USE_LOOT · 마을 인물 선물(물약·무기·축복) · 소지 칸 i1~i4 · 생성 층 · 정의가 여럿인 type 의 모르는 이름은 None(거짓 설명 없음)
  ③ 관측: 바닥 물약·단검·가죽 갑옷·보물·장검 + 소지 i1~i4 장면의 조합형 프롬프트 — 아이템마다 '· 설명:' 줄, 물건 설명은 같은 글 한 번 ·
     규칙은 type 당 한 번 · 수치 = 코드(장검 +2 = GEAR_KINDS · 축복 = 전사 힘 / 궁수 민첩 · {gain} = Dungeon.BLESS_GAIN) · 중괄호가 새지 않음 ·
     상자·사람·문 줄엔 설명 없음 · 축복 물약의 옛 effect 칸 없음 · 관측 dict 는 줄마다 desc·rule(자기 두뇌용)
  ④ 보이는 범위: 남이 든 것·목격 문장에 설명 문자열이 없다 · item.lore 를 달아도 어떤 프롬프트에도 안 나온다(물건 search 전까지)
  ⑤ 규칙 문장의 참(설명이 약속하는 결과 규칙을 엔진으로 — 엔진이 바뀌면 여기가 말을 고치라고 알린다): 만피에도 물약 한 병 소모 ·
     물약·축복 한 병씩 건네기 · 축복을 남에게 쓰면 변화 없음 · 무기·갑옷 바꿔 들기 = 들던 것이 같은 번호로 그 자리에 · 보물 줍기 = 모은 보물 +1 ·
     건넨 장비가 상대 발밑(spot theirs) / 상대 발밑이 차면 내 발밑(spot mine — D6 결과 문장 갈림) / 둘 다 차면 no_room
  ⑥ 메뉴형(classic)엔 설명이 없다(D9): 관측에 대상 목록 없음 · 프롬프트·메뉴 라벨에 설명 문자열 없음 · 옛 라벨 문구 그대로
  ⑦ 이어가기: 피클 왕복 뒤 같은 프롬프트 · 옛 스냅샷(fixtures/snapshot_v052)의 피처·몸으로도 설명이 그려진다(피처 꼴 무변경)
  ⑧ 생성 길 한 길(D5): place_def — 던전 살림 소품(통·궤짝·항아리·석판·모닥불)의 특징 한 줄이 던전 관측에 · 아이템·설비엔 이야기 없음 ·
     place_def 와 옛 _add_feature 길의 피처 꼴(번호·type·이름·자리·숨김)이 같다
  ⑨ 배선: 게이트 목록 · check_words 가 아이템 정의·규칙 칸 수를 찍는다
"""
import io
import json
import os
import pickle
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="wl_items_")
FIX = os.path.join(HERE, "fixtures", "snapshot_v052")
os.environ.update(DUNGEON_GM="0", DUNGEON_BRAIN_BACKEND="dummy", DUNGEON_STEP_DELAY="0", DUNGEON_BESTIARY_FILE="",
                  DUNGEON_STATE_DIR=os.path.join(TMP, "state"))
os.environ.pop("DUNGEON_PARTY_FILE", None)

import brains                                        # noqa: E402
import composed_actions as CA                        # noqa: E402
import dungeon_gm as G                               # noqa: E402
import entities as ENT                               # noqa: E402
import interactables as IA                           # noqa: E402
import show_runner                                   # noqa: E402
import snapshot                                      # noqa: E402
import words as WD                                   # noqa: E402

checks, fails = 0, []


def check(label, ok, detail=""):
    global checks
    checks += 1
    print(("  OK   " if ok else " FAIL  ") + label + (("  — " + str(detail)[:600]) if (detail != "" and not ok) else ""))
    if not ok:
        fails.append(label)


def rewrite(path, fn):
    with io.open(path, encoding="utf-8") as f:
        txt = f.read()
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(fn(txt))


def jedit(path, fn):
    with io.open(path, encoding="utf-8") as f:
        doc = json.load(f)
    fn(doc)
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)


defs = ENT.reload()
ITEM_IDS = ("potion", "boon", "treasure", "dagger", "longsword", "leather_armor", "chain_mail")

print("── ① 로드 거절 · 정본")
items = {d["id"]: d for d in defs.values() if (d.get("comps") or {}).get("item")}
check("① 정본: 아이템 정의 7장(축복의 물약 새 정의 포함) · type 이 ITEM_TYPES 를 다 덮는다 · 전부 설명이 있고 태그 item · 보물 태그 (object, item)",
      set(items) == set(ITEM_IDS) and {d["type"] for d in items.values()} == set(ENT.ITEM_TYPES)
      and all(d["comps"]["item"]["desc"].strip() and "item" in d["tags"] for d in items.values())
      and ENT.feature_tags("treasure") == ["object", "item"] and defs["boon"]["type"] == "boon" and not defs["boon"].get("sprite"))
check("① 정본: 아이템 아닌 오브젝트엔 item 부품·태그가 없다(상자·샘·출구·쓰임 오브젝트)",
      not any(((d.get("comps") or {}).get("item") or "item" in (d.get("tags") or [])) for d in ENT.by_kind("object") if d["id"] not in ITEM_IDS))
check("① 정본: 다루는 규칙 칸 = ITEM_TYPES · 한 줄씩 · 중괄호 없음",
      set(WD.action_words(ENT.ITEM_RULES)) == set(ENT.ITEM_TYPES)
      and all("{" not in v and "\n" not in v for v in WD.action_words(ENT.ITEM_RULES).values()))
root, wroot, aroot = os.path.join(TMP, "entities"), os.path.join(TMP, "world"), os.path.join(TMP, "actions")
shutil.copytree(ENT.ROOT, root)
shutil.copytree(WD.WORDS_ROOT, wroot)
shutil.copytree(WD.ACTIONS_ROOT, aroot)
check("① 임시 사본(정의·말·규칙)은 고치기 전에 정본과 같게 읽힌다", ENT.read(root, words_root=wroot, rules_root=aroot) == defs)
obj, wobj = os.path.join(root, "object"), os.path.join(wroot, "object")
jedit(os.path.join(obj, "potion.json"), lambda d: d["comps"].pop("item"))                                  # a 아이템 type 인데 부품 없음(태그는 남음)
os.remove(os.path.join(wobj, "potion.md"))
jedit(os.path.join(obj, "chest.json"), lambda d: (d["comps"].update(item={"desc": "열면 보물이 나온다"}), d["tags"].append("item")))   # b 설비에 item
jedit(os.path.join(obj, "treasure.json"), lambda d: d["tags"].remove("item"))                              # c 부품만 있고 태그 없음
rewrite(os.path.join(wobj, "dagger.md"), lambda t: t.replace("+{bonus}", "+{foo}"))                        # d 모르는 자리
rewrite(os.path.join(wobj, "treasure.md"), lambda t: t.replace("값나가는", "{bonus}만큼 값나가는"))          # e 장비 아닌 것의 {bonus}
rewrite(os.path.join(wobj, "chain_mail.md"), lambda t: t.replace("쇠고리를", "{stat} 쇠고리를 {"))          # f 축복 아닌 것의 {stat} · 짝 없는 중괄호
jedit(os.path.join(obj, "leather_armor.json"), lambda d: d["comps"]["item"].update(note="x"))              # g item 부품의 모르는 칸
rewrite(os.path.join(wobj, "longsword.md"), lambda t: t.split("## `item.desc`")[0] + "## `item.desc` — 빈 설명\n\n")   # h 빈 설명
rewrite(os.path.join(aroot, "item_rules.md"), lambda t: t.replace("## `boon`", "## `chest`").replace("그 자리에 놓인다.", "그 자리에 {bonus} 놓인다.", 1))   # i·j·k
jedit(os.path.join(root, "npc", "gear_merchant.json"), lambda d: d["comps"]["npc"]["gift"].update(weapon="명검"))   # l 모르는 선물 무기
try:
    ENT.read(root, words_root=wroot, rules_root=aroot)
    msg = ""
except ENT.EntityError as e:
    msg = str(e)
want = ("potion.json: type 'potion' 은(는) 아이템이다",
        "type 'chest' 은(는) 엔진이 몸에 들 수 없다", "태그 item 과 item 부품은 함께", "{foo} 는 모르는 자리", "{bonus} 는 장비(equipment.bonus)가 있는 정의만",
        "{stat} 는 축복의 물약(type boon)만", "짝이 맞지 않는 중괄호", "item 부품은 desc(물건 설명)·lore(속) 칸만", "item.desc(물건 설명)가 없다",
        "아이템 type `boon` 의 다루는 규칙 칸이 없다", "칸 `chest` 는 아이템 type 이 아니다", "`weapon` 칸에 중괄호를 쓸 수 없다",
        "npc.gift.weapon '명검' 는 무기 정의의 이름이 아니다")
check("① 거절 13종을 한 번에 나열 — 부품 없음·설비의 부품·태그만·모르는 자리·{bonus}·{stat}·짝 없는 중괄호·모르는 칸·빈 설명·규칙 빠짐·규칙 남음·규칙 중괄호·선물 무기",
      all(w in msg for w in want), [w for w in want if w not in msg] or msg)
check("① 리포 정본은 그대로(임시 사본만 깨뜨렸다)", ENT.reload() == defs)

print("── ② 조회 전수(G7)")
gear_ok = all(ENT.item_def(ENT.get(e)["type"], ENT.object_name(e)) is ENT.get(e) for e in G.GEAR_CYCLE)
asc, _ = G.Dungeon.from_ascii(["#########", "#1$!)[=>#", "#########"], seed=3)
asc_items = [f for f in asc.features.values() if f.type in ENT.ITEM_TYPES]
gifts = [ENT.npc(n["id"])["gift"] for n in ENT.by_kind("npc") if ENT.npc(n["id"]).get("gift")]
gift_ok = all((not g.get("potions") or ENT.item_def("potion") is ENT.get("potion"))
              and (not g.get("weapon") or (ENT.item_def("weapon", g["weapon"]) or {}).get("name") == g["weapon"])
              and (not g.get("boon") or ENT.item_def("boon") is ENT.get("boon")) for g in gifts)
loot = {e["item"] for d in ENT.by_kind("object") for e in ((d["comps"].get("use") or {}).get("loot") or [])} - {"nothing"}
gen = G.Dungeon(seed=11, w=44, h=18, n_monsters=1, n_traps=1, n_potions=2, n_gear=4)
gen_items = [f for f in gen.features.values() if f.type in ENT.ITEM_TYPES]
check("② GEAR_CYCLE 4 · 손그림 글리프 4($ ! ) [) · 생성 층(물약 2·장비 4·보물·숨은 보물) 의 아이템 피처가 전부 제 정의로 풀린다",
      gear_ok and len(asc_items) == 4 and all(ENT.item_def(f.type, f.name) for f in asc_items)
      and len(gen_items) >= 8 and all(ENT.item_def(f.type, f.name) and ENT.item_def(f.type, f.name)["type"] == f.type for f in gen_items)
      and any(f.name == "숨은 보물" for f in gen_items), [(f.type, f.name) for f in gen_items])
check("② 숨은 보물 → 보물 정의(type 의 정의가 하나뿐) · 뒤지기 USE_LOOT(물약·보물) · 마을 인물 선물(물약·무기 이름·축복) 전부 풀린다",
      ENT.item_def("treasure", "숨은 보물") is ENT.get("treasure") and loot == {"potion", "treasure"} <= set(ENT.USE_LOOT)
      and all(ENT.item_def(t) for t in loot) and gifts and gift_ok)
check("② 소지 칸 i1~i4 = 물약·무기·갑옷·축복 → 정의 · 정의가 여럿인 type 의 모르는 이름은 None(거짓 설명보다 빈칸) · 아이템 아닌 type 은 None",
      CA.ITEM_SLOTS == {"i1": "potion", "i2": "weapon", "i3": "armor", "i4": "boon"}
      and ENT.item_def("potion", "회복 물약") is ENT.get("potion") and ENT.item_def("boon", "축복의 물약") is ENT.get("boon")
      and ENT.item_def("weapon", "장검") is ENT.get("longsword") and ENT.item_def("armor", "사슬 갑옷") is ENT.get("chain_mail")
      and ENT.item_def("weapon", "이름 모를 칼") is None and ENT.item_def("armor") is None and ENT.item_def("chest") is None)

print("── ③ 관측(조합형)")
ROWS = ["##############",
        "#1!)[$=...2.>#",
        "#............#",
        "##############"]
NAMES = {"1": "두란", "2": "카야", "3": "피른"}


def scene(rows=ROWS, job2=None):
    d, st = G.Dungeon.from_ascii(rows, seed=7)
    d.composed_actions, d.auto_approach = True, True
    d.give_verb = d.bond_verb = d.events = True
    bots = []
    for c in sorted(st):
        b = G.spawn(d, c, bots, sheet=G.HEROES.get(c) or G.HEROES["1"])
        b["x"], b["y"] = st[c]
        b["name"] = NAMES[c]
        b["potions"], b["weapon"], b["armor"], b["boons"] = 0, None, None, 0
        bots.append(b)
    d.turn = 3
    return d, bots


def prompt(d, b, bots, compose=True):
    o = d.view(b, bots)
    return brains._wire(o, {k: v for k, v in NAMES.items()}, compose=compose), o


d3, bots3 = scene()
a3, c3 = bots3
ls_id = d3.place_def("longsword", 3, 2)
a3.update(potions=2, boons=1, weapon={"id": d3._alloc_fid(), "name": "단검", "bonus": 1, "worn": ["1"]},
          armor={"id": d3._alloc_fid(), "name": "사슬 갑옷", "bonus": 2, "worn": ["1"]})
w3, o3 = prompt(d3, a3, bots3)
sec = w3[w3.index("## 대상 — 지금"):w3.index("## 행동과 의사소통")]
lines = sec.split("\n")
desc = {e: ENT.item_desc(ENT.get(e), **(d3.bless_fill(a3) if e == "boon" else {})) for e in ITEM_IDS}
rule = {t: ENT.item_rule(t) for t in ENT.ITEM_TYPES}
under = {}                                          # 대상 줄 → 바로 아래 '· 설명:' 줄
for i, ln in enumerate(lines):
    if ln.startswith("- [") and i + 1 < len(lines) and lines[i + 1].startswith("  · 설명: "):
        under[ln.split("]")[0][3:]] = lines[i + 1][len("  · 설명: "):]
tid = {t["name"]: t["id"] for t in o3["targets"] if t.get("kind") == "feature"}
check("③ 모든 물건 설명이 대상 절에 정확히 한 번(바닥 단검 + 소지 단검 → 한 번) · 규칙도 type 당 한 번",
      all(sec.count(desc[e]) == 1 for e in ITEM_IDS) and all(sec.count(rule[t]) == 1 for t in ENT.ITEM_TYPES),
      {e: sec.count(desc[e]) for e in ITEM_IDS})
check("③ 줄 꼴: 처음 나온 줄 아래 '  · 설명: <물건 설명> <규칙>' — 바닥 물약 = 물약 설명+규칙 · 소지 물약 i1 은 설명 줄 없음 · 소지 단검 i2 는 줄 없음(바닥 단검이 먼저) · 사슬 갑옷 i3 은 설명만",
      under.get(tid["회복 물약"]) == desc["potion"] + " " + rule["potion"] and "i1" not in under and "i2" not in under
      and under.get(tid["단검"]) == desc["dagger"] + " " + rule["weapon"] and under.get(tid["장검"]) == desc["longsword"]
      and under.get(tid["가죽 갑옷"]) == desc["leather_armor"] + " " + rule["armor"] and under.get("i3") == desc["chain_mail"]
      and under.get(tid["보물"]) == desc["treasure"] + " " + rule["treasure"] and under.get("i4") == desc["boon"] + " " + rule["boon"], under)
check("③ 수치 = 코드: 장검 설명에 +GEAR_KINDS['장검'] · 단검 +1 · 사슬 갑옷 +2 · 축복(전사) = 힘 +BLESS_GAIN · 대상 절에 중괄호 없음",
      ("+%d" % G.GEAR_KINDS["장검"]) in desc["longsword"] and ("+%d" % G.GEAR_KINDS["단검"]) in desc["dagger"]
      and ("+%d" % G.GEAR_KINDS["사슬 갑옷"]) in desc["chain_mail"] and ("힘 +%d" % G.Dungeon.BLESS_GAIN) in desc["boon"]
      and "{" not in sec and "}" not in sec, desc)
check("③ 상자·사람·계단·나 줄엔 설명이 없다 · 관측 dict: 아이템 줄만 desc·rule(줄마다 — 자기 두뇌용) · 축복 물약 옛 effect 칸 없음",
      not any(k in under for k in (tid["상자"], "b2", "exit", "self", "b1"))
      and all(("desc" in t) == (t["id"] in [tid[n] for n in ("회복 물약", "단검", "가죽 갑옷", "보물", "장검")] or t["id"] in ("i1", "i2", "i3", "i4"))
              for t in o3["targets"])
      and all(t.get("rule") == rule[CA.ITEM_SLOTS[t["id"]]] for t in o3["items"])
      and next(t for t in o3["items"] if t["id"] == "i2")["desc"] == desc["dagger"]
      and not any("effect" in t for t in o3["targets"] + o3["items"]))
arch = dict(a3, atk_range=2)
check("③ 축복 설명은 지닌 몸을 따른다 — 궁수(원거리) = 민첩 · 지닌 사람이 없는 자리 = '공격에 쓰는 능력치' · _bless 와 같은 함수(bless_stat)",
      ENT.item_desc(ENT.get("boon"), **d3.bless_fill(arch)) == desc["boon"].replace("힘", "민첩")
      and "공격에 쓰는 능력치" in ENT.item_desc(ENT.get("boon"), gain=1)
      and d3.bless_stat(arch) == "dex" and d3.bless_stat(a3) == "str")

print("── ④ 보이는 범위")
c3["x"], c3["y"] = 4, 2                             # 장검(3,2) 곁 — 두란의 시야 안
w4, _ = prompt(d3, c3, bots3)
check("④ 카야(봇2)의 프롬프트: 두란이 든 사슬 갑옷·축복의 물약 설명이 없다(남이 든 것은 이름만) · 바닥 물건 설명은 있다",
      desc["chain_mail"] not in w4 and desc["boon"] not in w4 and desc["longsword"] in w4)
eq4 = d3._interact(c3, "f%d" % ls_id, bots3)        # 줍는 것을 두란이 본다
o4 = d3.view(a3, bots3)
wit = " ".join(brains._witness_prose(w) for w in (o4.get("witnessed") or []))
check("④ 목격 문장(카야가 장검을 챙김)에 설명 문자열이 없다",
      eq4.get("result") == "equip" and "장검" in wit and desc["longsword"] not in wit, (eq4.get("result"), wit))
d4l, bots4l = scene()
d4l.place_def("longsword", 2, 2)
lsdef = ENT.get("longsword")
lsdef["comps"]["item"]["lore"] = "북쪽 대장간의 낙인 — 비밀 내력"   # 메모리의 정의에만(파일 무수정)
try:
    w4l, o4l = prompt(d4l, bots4l[0], bots4l)
    w4m, _ = prompt(d4l, bots4l[0], bots4l, compose=False)
finally:
    lsdef["comps"]["item"].pop("lore", None)
check("④ item.lore 는 자리만 — 정의에 있어도 조합형·메뉴형 프롬프트·관측 dict 어디에도 안 나온다",
      "비밀 내력" not in w4l and "비밀 내력" not in w4m and "비밀 내력" not in json.dumps(o4l, ensure_ascii=False, default=str))

print("── ⑤ 규칙 문장의 참(엔진)")
d5, bots5 = scene()
a5, c5 = bots5
c5["x"] = a5["x"] + 1                               # 곁
a5["potions"] = 2
d5.view(a5, bots5)
r5 = CA.execute(d5, a5, {"type": "use", "target": "self", "item": "i1", "action_id": "t5"}, bots5)
check("⑤ 물약: 상처가 없어도 한 병이 준다(healed heal 0 · 2 → 1)", r5.get("result") == "healed" and r5.get("heal") == 0 and a5["potions"] == 1, r5)
g5 = d5._give(a5, "b2", "potion", bots5)          # 엔진 지점 직접(조합형 give i1/i4 도 이 함수로 온다 — CA.execute)
a5["boons"] = 2
g5b = d5._give(a5, "b2", "boon", bots5)
check("⑤ 물약·축복은 건네면 한 병씩 넘어간다", g5.get("result") == "given" and a5["potions"] == 0 and c5["potions"] == 1
      and g5b.get("result") == "given" and a5["boons"] == 1 and c5["boons"] == 1)
d5.view(a5, bots5)
u5 = CA.execute(d5, a5, {"type": "use", "target": "b2", "item": "i4", "action_id": "t5b"}, bots5)
boons_after_other = a5["boons"]
s5 = a5["str"]
d5.view(a5, bots5)
u5s = CA.execute(d5, a5, {"type": "use", "target": "self", "item": "i4", "action_id": "t5c"}, bots5)
check("⑤ 축복은 자기 자신만 — 남에게 쓰면 변화 없음(no_item_effect, 병 그대로 1) · 자기에게 쓰면 힘 +BLESS_GAIN(병 0)",
      u5.get("result") == "no_effect" and u5.get("reason_code") == "no_item_effect" and boons_after_other == 1
      and u5s.get("result") == "drink_boon" and a5["str"] == s5 + G.Dungeon.BLESS_GAIN and a5["boons"] == 0, (u5, u5s))
for slot, old_nm, new_eid in (("weapon", "단검", "longsword"), ("armor", "가죽 갑옷", "chain_mail")):
    d5s, bots5s = scene(["########", "#1.2..>#", "########"])
    b5 = bots5s[0]
    oid = d5s._alloc_fid()
    b5[slot] = {"id": oid, "name": old_nm, "bonus": G.GEAR_KINDS[old_nm], "worn": ["1"]}
    nf = d5s.place_def(new_eid, b5["x"] + 1, b5["y"])
    e5 = d5s._interact(b5, "f%d" % nf, bots5s)
    left = d5s.feature_at(b5["x"] + 1, b5["y"])
    check("⑤ %s 바꿔 들기: 하나만 든다(새것을 든다) · 들던 %s 는 같은 번호(f%d)로 그 자리에" % (slot, old_nm, oid),
          e5.get("result") == "equip" and b5[slot]["name"] == ENT.object_name(new_eid) and left is not None
          and left.id == oid and left.name == old_nm and left.type == slot and e5.get("dropped_id") == "f%d" % oid, e5)
d5t, bots5t = scene()
tf = next(f for f in d5t.features.values() if f.type == "treasure")
bt = bots5t[0]
bt["x"] = tf.x - 1
bag0 = bt.get("bag", 0)
rt5 = d5t._interact(bt, "f%d" % tf.id, bots5t)
check("⑤ 보물: 주우면 모은 보물이 하나 는다", rt5.get("result") == "treasure" and bt["bag"] == bag0 + 1, rt5)
d5g, bots5g = scene(["#########", "#1.2...>#", "#########"])
gb, gc = bots5g
gc["x"] = gb["x"] + 1
gb["armor"], gc["armor"] = {"name": "가죽 갑옷", "bonus": 1}, {"name": "사슬 갑옷", "bonus": 2}
gt = d5g._give(gb, "b2", "armor", bots5g)
lt = dict(gc.get("last") or {})
gb["armor"] = {"name": "가죽 갑옷", "bonus": 1}
gm = d5g._give(gb, "b2", "armor", bots5g)
lm = dict(gc.get("last") or {})
gb["armor"] = {"name": "가죽 갑옷", "bonus": 1}
gn = d5g._give(gb, "b2", "armor", bots5g)
names5 = {"1": "두란", "2": "카야"}
check("⑤ 건네기 배치: 상대 칸이 차 있으면 상대 발밑(spot theirs) → 거기가 차면 내 발밑(spot mine) → 둘 다 차면 no_room(소지 유지)",
      gt.get("placed") is True and gt.get("spot") == "theirs" and lt.get("spot") == "theirs"
      and d5g.feature_at(gc["x"], gc["y"]) is not None and gm.get("placed") is True and gm.get("spot") == "mine" and lm.get("spot") == "mine"
      and d5g.feature_at(gb["x"], gb["y"]) is not None and gn.get("result") == "no_room" and gb["armor"]["name"] == "가죽 갑옷", (gt, gm, gn))
check("⑤ 결과 문장이 놓인 자리로 갈린다(D6) — 건넨 쪽 '그의 발밑'/'네 발밑' · 받은 쪽 '발밑'/'건넨 이의 발밑' · 꼬리표·관전 요약도 · spot 없는 옛 기록은 옛 문장",
      "그의 발밑에 놓였다" in brains._last_prose(gt, names5) and "네 발밑에 놓였다" in brains._last_prose(gm, names5)
      and "그의 발밑" not in brains._last_prose(gm, names5)
      and "건넨 이의 발밑" not in brains._last_prose(lt, names5) and "발밑에 놓였다(걸칠지는 네 몫)" in brains._last_prose(lt, names5)
      and "건넨 이의 발밑에 놓였다" in brains._last_prose(lm, names5)
      and any("내 발밑" in t[2] for t in G.event_tags(gm, names5)) and any("건넨 이의 발밑" in t[2] for t in G.event_tags(lm, names5))
      and "건넨 이의 발밑" in show_runner.act_summary(gm) and "그의 발밑" in show_runner.act_summary(gt)
      and "그의 발밑에 놓였다" in brains._last_prose({k: v for k, v in gm.items() if k != "spot"}, names5))

print("── ⑥ 메뉴형(classic)엔 설명이 없다(D9)")
d6, bots6 = scene()
d6.composed_actions = False
d6.place_def("longsword", 1, 2)                     # 곁(바로 아래) — 메뉴의 장비 줄이 선다
a6 = bots6[0]
a6.update(potions=1, boons=1, weapon={"name": "단검", "bonus": 1})
w6, o6 = prompt(d6, a6, bots6, compose=False)
labels = " ".join(o["label"] for o in o6.get("options") or [])
check("⑥ 메뉴형 관측엔 대상 목록이 없고 프롬프트·메뉴 라벨에 설명·규칙 문자열이 없다 · 옛 라벨 문구('상처가 전부 아문다'·'바꾸면 헌것은 그 자리에 놓는다') 그대로",
      "targets" not in o6 and "· 설명:" not in w6 and not any(s in w6 + labels for s in list(desc.values()) + list(rule.values()))
      and "상처가 전부 아문다" in labels and "바꾸면 헌것은 그 자리에 놓는다" in labels, labels[:300])

print("── ⑦ 이어가기")
# 피클: 이 프로세스가 방금 만든 객체의 왕복과 리포 고정 자료(fixtures — 코드와 같은 신뢰 급, verify_info_guard 와 같은 관행)만 읽는다
d7, bots7 = pickle.loads(pickle.dumps((d3, bots3)))
w7, _ = prompt(d7, bots7[0], bots7)
w3b, _ = prompt(d3, a3, bots3)
check("⑦ 피클 왕복 뒤 같은 프롬프트(설명은 피처·몸에 안 적힌다 — 보일 때 정의에서)", w7 == w3b and desc["longsword"] not in json.dumps(
    {k: v for k, v in vars(d7).items() if k == "features"}, default=lambda f: f.as_dict(), ensure_ascii=False))
S7 = os.path.join(TMP, "s52", "state")
shutil.copytree(FIX, S7)
s7, _m7 = snapshot.load(os.path.join(S7, "snapshot.pkl"))
od = s7["d"]
ob = next(b for b in snapshot._bodies(s7) if b.get("alive"))
od.composed_actions = True
ob = dict(ob, potions=1, weapon=ob.get("weapon") or {"name": "장검", "bonus": 2})
oo = od.view(ob, [ob])
fitems = [t for t in oo["targets"] if t.get("kind") == "feature" and ENT.feature_tags(next((f.type for f in od.features.values() if "f%d" % f.id == t["id"]), "")) == ["object", "item"]]
check("⑦ 옛 스냅샷(v0.5.2 고정 자료)의 던전·몸: 소지 물약·장비 줄에 설명 · 보이는 바닥 아이템도 설명(피처 꼴 무변경)",
      all(t.get("desc") for t in oo["items"] if t["slot"] in ("potion", "weapon")) and all(t.get("desc") for t in fitems)
      and "· 설명: " in brains._wire(oo, {}, compose=True), [(t["id"], t.get("desc")) for t in oo["items"]])

print("── ⑧ 생성 길 한 길(D5)")
fl = G.Dungeon(seed=21, w=44, h=18, n_monsters=1, n_traps=1, n_potions=1, n_gear=2, floor_life=True)
life = [f for f in fl.features.values() if f.type in G.Dungeon.LIFE_RUMMAGE_IDS + (G.Dungeon.LIFE_TABLET_ID, G.Dungeon.LIFE_CAMPFIRE_ID)]
ps = getattr(fl, "place_story", None) or {}
check("⑧ 던전 살림 소품마다 place_story = 정의의 story(특징 한 줄) · 아이템·설비·출구엔 이야기 없음",
      bool(life) and all(ps.get(f.id) == ENT.get(f.type)["comps"]["story"] for f in life)
      and set(ps) == {f.id for f in life}, (len(life), sorted(ps)))
d8, bots8 = scene(["#########", "#1......#", "#......>#", "#########"])
b8 = bots8[0]
tf8 = d8.place_def("barrel", 5, 1)
w8, o8 = prompt(d8, b8, bots8)
trait = ENT.get("barrel")["comps"]["story"]["trait"]
check("⑧ 던전 관측의 통 줄 끝에 특징 한 줄(about) — 옛 길(_add_feature)은 이야기가 없었다",
      any(f.get("about") == trait for f in o8["sights"]["features"]) and (" — " + trait) in w8)
twin, _ = G.Dungeon.from_ascii(["#########", "#1......#", "#......>#", "#########"], seed=7)
old = twin._add_feature("barrel", ENT.object_name("barrel"), 5, 1)
fa, fb = d8.features[tf8], twin.features[old]
hid = d8.place_def("treasure", 3, 2, concealed=True, perception_gate=G.PASSIVE_DC, name="숨은 보물")
hold = twin._add_feature("treasure", "숨은 보물", 3, 2, concealed=True, perception_gate=G.PASSIVE_DC)
check("⑧ place_def 와 옛 _add_feature 의 피처 꼴이 같다(번호·type·이름·자리·숨김·인지 난도 — 스트림 level·features 바이트 그대로)",
      fa.as_dict() == fb.as_dict() and d8.features[hid].as_dict() == twin.features[hold].as_dict() and hid not in (getattr(d8, "place_story", None) or {}))
try:
    d8.place_def("goblin", 4, 1)
    bad8 = False
except ValueError:
    bad8 = True
check("⑧ place_def 는 오브젝트 정의만(몬스터 id 는 거절) · interactables.place 는 바닥 검사를 얹은 겉(같은 길)", bad8
      and "d.place_def(eid, x, y)" in open(os.path.join(HERE, "interactables.py"), encoding="utf-8").read())

print("── ⑨ 배선")
with io.open(os.path.join(HERE, "_run_gates.sh"), encoding="utf-8") as f:
    gates = f.read()
out = subprocess.run([sys.executable, os.path.join(HERE, "tools", "check_words.py")], capture_output=True, text=True, encoding="utf-8",
                     env=dict(os.environ, PYTHONUTF8="1"))
check("⑨ 게이트 목록에 verify_items · check_words 가 0 으로 끝나고 아이템 정의 7장·규칙 칸 5개를 찍는다",
      "verify_items" in gates and out.returncode == 0 and "아이템 정의 7장(설명 7개)" in out.stdout and "칸 5개" in out.stdout, out.stdout + out.stderr)

shutil.rmtree(TMP, ignore_errors=True)
if fails:
    print("FAIL — verify_items (%d/%d): %s" % (len(fails), checks, " · ".join(fails)))
    sys.exit(1)
print("ALL PASS — verify_items (%d checks, 실 LLM 0콜)" % checks)

# -*- coding: utf-8 -*-
"""D89 쓰임 부품(2026-09-20) — 오브젝트·건물과의 상호작용을 정의(JSON)의 use{kind} 가 낸다 — 헤들리스 검증. LLM 0콜.
(설계 원장 D83 의 남은 기둥 C "마을에서 할 일의 행동 수단이 없다" · D69 결정 ② "정의의 부품이 관측 대상·메뉴를 낸다 … 엔진은
 부품만 보고, 새 건물은 JSON 한 장". 새 동사 없음 — 전부 기존 use(메뉴형 interact) 밑. 돈·가격·매매 없음.)
게이트:
  ① 정의·검증기: COMPS(object: use·story / building: use) · 최소 정의 4장(read·sit·drink·rummage) · kind 어휘 = 처리기 어휘 ·
     여기서 보는 8 kind 전부 통과(D95 공물은 세계의 스위치 뒤 — verify_offer 가 본다) ·
     거절(모르는 kind·모르는 칸·빈 글·음수 회복·빈 진열·모르는 추첨 항목·rummage once:false·엔진 타입에 use·NPC 에 use)
  ② 부품 없는 세계 = 옛 판 그대로: 생성 층 3시드의 obs 에 use 칸 없음 · 부품 없는 건물은 메뉴 줄 없음·써도 nothing ·
     모르는 타입(묘)은 옛 줄 '상호작용: …' 그대로·nothing · 조합형 태그 옛 그대로
  ③ 메뉴 경로(8 kind): 줄 머리(읽기·앉기·…·묵기 문턱) · 결과 이름·사실 칸 · HP 변화(상한) · 피처 존속 · 멀면 too_far · 판정 rng 무접촉
  ④ 뒤지기: 추첨은 세계 시드·자리의 해시(같은 세계 = 같은 것, 누가 뒤지든) · 물약/보물/빈손의 소지 변화 · 보물 = 의뢰 진행(D69) ·
     두 번째는 used_up · once 는 세계의 상태(다른 사람에게도) · 가중표가 세 항목을 다 낸다(자리 300곳)
  ⑤ 읽기 texts[]: 읽는 사람마다 제 쪽수 · 끝나면 처음으로
  ⑥ 묵기(건물): HP 전부 + 상태 태그 소거(D34 — 휴식 완료와 같은 소거) · 성한 몸이면 사실만
  ⑦ 조합형 경로(scenario.build, DUNGEON_ACTION_MODE=compose): 대상 태그(interactable + kind 태그) · '대상의 현재 사실' 줄 ·
     use → result + effect_type interact · 멀리서 use = 접근 뒤 실행 · used_up 은 resolution no_effect · '그 밖의 정보' 누출 없음
  ⑧ 표현: _last_prose·event_tags·act_summary 가 JSON 폴백·'기타' 가 아니다(메뉴형·조합형 결과 둘 다) · 조사(을/를·은/는)
  ⑨ 목격: 기존 ally_use{what,id,result} 재사용 — 곁의 사람만, 당사자 제외 · 문장 '…을(를) 사용하는 것을 (앉아 쉬었다)'
  ⑩ 오브젝트 태그(D39): 쓰고도 남는 오브젝트라 '앉아 봄 ×N'·'뒤져 봄 ×1 (물약 나옴)' · 스위치 꺼진 판엔 없음
  ⑪ 피클 왕복: 다 쓴 상태(use_spent)·읽던 쪽수가 남는다 · 속성이 없는 옛 스냅샷도 그대로 돈다(getattr)
  ⑫ 배치 도우미 place(): 이름·type·story 등록 · 바닥 아님/이미 찬 칸/오브젝트 아님 = ValueError
  ⑬ 배선: _interact 훅 한 곳 · decorate 의 used_up · 러너 생성 세 자리 무접촉 · _run_gates.sh 등록
  ⑭ 진짜 마을(build_town): 부품 없는 건물 문턱엔 줄이 없고, 정의(메모리)에 use 를 달면 '묵기 … (문턱)'이 열린다 — 떼면 다시 없다
  ⑮ 다 쓴 것은 다 쓴 것으로 보인다(09-20 리뷰 수선): once 로 다 쓴 뒤 **다른 봇**의 관측 use 칸 = {kind, spent} · 메뉴 라벨·조합형 사실 줄에
     효과 수치가 없고 '이미 쓰였다'만 · 안 쓴 것은 옛 줄 그대로 · read 의 동사 변형(verb look = 살펴보기 — 라벨·태그·문장·꼬리표, 결과 이름은 read)
(기존 verify 는 별도 실행 — 'use 부품이 없는 세계는 옛 판과 바이트 동일'의 본 검사는 verify_skill_off.)
"""
import os
import pickle
import tempfile

STATE = os.path.join(tempfile.mkdtemp(prefix="wl_use_"), "state")
os.makedirs(STATE, exist_ok=True)
os.environ.update(DUNGEON_GM="0", DUNGEON_BESTIARY_FILE="", DUNGEON_STATE_DIR=STATE, DUNGEON_BRAIN_BACKEND="dummy",
                  DUNGEON_ACTION_MODE="compose")   # 조합형 게이트 — _run_gates.sh 의 menu 기본을 파일 안에서 덮는다(verify_guild 선례).
for k in ("DUNGEON_MENU", "DUNGEON_SCAN"):         #   메뉴 경로는 아래에서 from_ascii(composed_actions=False) 장면으로 따로 돈다
    os.environ.pop(k, None)

import brains                                        # noqa: E402
brains._call_claude = lambda prompt, model="haiku": ""   # LLM 무력화(0콜)
import composed_actions as CA                        # noqa: E402
import dungeon_gm as G                               # noqa: E402
import entities as ENT                               # noqa: E402
import interactables as IA                           # noqa: E402
import scenario                                      # noqa: E402
import show_runner                                   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


class C:
    failed = 0


def check(name, cond):
    print(("  OK   " if cond else " FAIL  ") + name)
    if not cond:
        C.failed += 1


def src(path):
    with open(os.path.join(HERE, path), encoding="utf-8") as f:
        return f.read()


def mkbot(char, x, y, hp=14, maxhp=14):
    return {"char": char, "x": x, "y": y, "hp": hp, "maxhp": maxhp, "str": 3, "dex": 0, "wdmg": 4, "stealth": 0,
            "search_r": 1, "job": "전사", "sex": "남", "persona": "", "bag": 0, "potions": 0, "weapon": None, "armor": None,
            "alive": True, "won": False, "order": None, "path": [], "plan": [], "last": None, "aware_of": set(),
            "name": {"1": "두란", "2": "카야"}.get(char, "피른")}


def odef(eid, name, use, ftype=None, story=None):
    return {"id": eid, "name": name, "kind": "object", "type": ftype or eid, "tags": ["object"],
            "comps": {"use": use, **({"story": story} if story else {})}}


def bdef(eid, name, use=None):
    return {"id": eid, "name": name, "kind": "building", "tags": ["town", "building"],
            "comps": {"building": {"size": [9, 6], "entrance": [4, 5], "texture": "ordinary_inn"}, **({"use": use} if use else {})}}


def problems(defn):
    return ENT._problems([(os.path.join(defn["kind"], defn["id"] + ".json"), defn)], ".")


def inject(defn):
    """게이트 전용 정의 — 검증기를 통과한 것만 메모리의 정의 사전에 넣는다(파일·정본 폴더 무접촉)."""
    p = problems(defn)
    assert not p, p
    ENT.load()[defn["id"]] = defn


print("── ① 정의·검증기")
check("① COMPS: object 에 use·story · building 에 use (npc·monster 에는 없음)",
      {"use", "story"} <= ENT.COMPS["object"] and "use" in ENT.COMPS["building"]
      and "use" not in ENT.COMPS["npc"] and "use" not in ENT.COMPS["monster"])
check("① 쓰임 kind 어휘 9종(D95 공물은 세계의 스위치 뒤 — verify_offer 가 본다) — 검증기(entities.USE_KINDS) = 처리기(interactables.KINDS) · 결과 이름 11종",
      set(ENT.USE_KINDS) == set(IA.KINDS) == {"read", "sit", "drink", "browse", "practice", "rummage", "lodge", "warm", "offer"}
      and set(ENT.USE_GATED_KINDS) == set(IA._GATE_ATTR) == {"offer"}
      and IA.RESULTS == ("read", "sat", "drank", "browsed", "practiced", "rummaged", "lodged", "warmed", "used_up",
                         "offered", "offer_short"))
base4 = {e: ENT.get(e) for e in ("stone_tablet", "bench", "well", "barrel")}
check("① 최소 정의 4장 — 석상 받침 read · 벤치 sit(heal 1) · 우물 drink(heal 1) · 통 rummage(once, 추첨표) · 전부 story.trait · 도감 본문 없음",
      [base4[e]["comps"]["use"]["kind"] for e in ("stone_tablet", "bench", "well", "barrel")] == ["read", "sit", "drink", "rummage"]
      and base4["bench"]["comps"]["use"]["heal"] == 1 and base4["barrel"]["comps"]["use"]["once"] is True
      and all(d_["comps"]["story"].get("trait") and not d_["comps"].get("knowledge") for d_ in base4.values())
      and all(d_["type"] == d_["id"] for d_ in base4.values()))
EXTRA = [odef("t_stall", "노점", {"kind": "browse", "wares": ["말린 과일", "밧줄", "등잔 기름"]}),
         odef("t_dummy", "허수아비", {"kind": "practice"}),
         odef("t_hearth", "화덕", {"kind": "warm", "heal": 2}),
         odef("t_shelf", "책장", {"kind": "read", "texts": ["첫째 글.", "둘째 글.", "셋째 글."]}),
         odef("t_crate_p", "물약 궤짝", {"kind": "rummage", "loot": [{"item": "potion", "w": 1}]}),
         odef("t_crate_t", "보물 궤짝", {"kind": "rummage", "loot": [{"item": "treasure", "w": 2}]}),
         odef("t_note", "쪽지", {"kind": "read", "text": "읽고 나면 바스러진다.", "once": True}),
         odef("t_stool", "걸상", {"kind": "sit", "heal": 0}),
         bdef("t_inn", "시험 여관", {"kind": "lodge"}),
         bdef("t_hut", "시험 헛간")]
check("① 검증기 통과 — 8 kind 전부(오브젝트 8 + 건물 lodge + 부품 없는 건물)", all(not problems(x) for x in EXTRA))
BAD = [(odef("b1", "x", {"kind": "dance"}), "use.kind"),
       (odef("b2", "x", {"kind": "sit", "price": 3}), "모르는 칸"),
       (odef("b3", "x", {"kind": "read"}), "use(read)"),
       (odef("b4", "x", {"kind": "read", "text": "a", "texts": ["b"]}), "use(read)"),
       (odef("b5", "x", {"kind": "read", "texts": []}), "use(read)"),
       (odef("b6", "x", {"kind": "drink", "heal": -1}), "use.heal"),
       (odef("b7", "x", {"kind": "browse", "wares": []}), "wares"),
       (odef("b8", "x", {"kind": "rummage", "loot": [{"item": "gold", "w": 1}]}), "loot"),
       (odef("b9", "x", {"kind": "rummage", "once": False, "loot": [{"item": "potion"}]}), "늘 한 번"),
       (odef("b10", "x", {"kind": "sit", "once": "yes"}), "use.once"),
       (odef("b11", "x", {"kind": "read", "text": "a"}, ftype="chest"), "제 뜻으로"),
       ({"id": "b12", "name": "x", "kind": "npc", "comps": {"npc": {"line": "a"}, "use": {"kind": "sit"}}}, "모르는 부품")]
check("① 검증기 거절 12건 — 모르는 kind·모르는 칸(price)·글 없음/둘 다/빈 목록·음수 회복·빈 진열·모르는 추첨 항목·rummage once:false·"
      "once 꼴·엔진 타입(chest)에 use·NPC 에 use", all(any(word in p for p in problems(x)) for x, word in BAD))
for x in EXTRA:
    inject(x)

print("── ② 부품 없는 세계 = 옛 판 그대로")
plain = []
for seed in (7, 37, 217):
    dg = G.Dungeon(seed=seed, w=44, h=18, n_monsters=2, n_traps=3, n_lurkers=1, scan=True, loops=True, composed_actions=True, auto_approach=True)
    bg = G.spawn(dg, "1", [])
    og = dg.view(bg, [bg])
    plain.append(all("use" not in f for f in og["sights"]["features"]) and all(IA.use_of(dg, f) is None for f in dg.features.values())
                 and not any("interactable" in t["tags"] for t in og["targets"] if t["kind"] == "feature"))
check("② 생성 층 3시드 — 피처에 쓰임 부품 없음 · obs 피처에 use 칸 없음 · 조합형 대상 태그 옛 그대로", all(plain))
ROWS = ["############",
        "#1........>#",
        "#..........#",
        "#2.........#",
        "############"]


def menu_scene(seed=7):
    d_, st = G.Dungeon.from_ascii(ROWS, seed=seed)
    d_.events = True
    return d_, st


d2, _ = menu_scene()
hut = d2._add_feature("building", "시험 헛간", 3, 2)
grave = d2._add_feature("grave", "누군가의 묘", 5, 2)
d2.building_defs = {hut: "t_hut"}
b2 = mkbot("1", 3, 1)
lab2 = [o["label"] for o in d2.view(b2, [b2])["options"]]
check("② 부품 없는 건물: 곁에서도 메뉴 줄 없음(D60 그대로) · 써도 nothing · obs 에 use 칸 없음",
      not any("시험 헛간" in l and not l.startswith("이동") for l in lab2)
      and d2.act(b2, {"type": "interact", "target": "f%d" % hut}, [b2])["result"] == "nothing"
      and all("use" not in f for f in d2.view(b2, [b2])["sights"]["features"]))
b2["x"] = 5
check("② 모르는 타입(묘): 옛 줄 '상호작용: 이름 id (발밑/인접)' 글자 그대로 · nothing",
      ("상호작용: 누군가의 묘 f%d (발밑/인접)" % grave) in [o["label"] for o in d2.view(b2, [b2])["options"]]
      and d2.act(b2, {"type": "interact", "target": "f%d" % grave}, [b2])["result"] == "nothing")

print("── ③ 메뉴 경로 — 8 kind")
d3, _ = menu_scene()
F = {}
for i, eid in enumerate(("stone_tablet", "bench", "well", "t_stall", "t_dummy", "barrel", "t_hearth")):
    F[eid] = IA.place(d3, eid, 2 + i, 2)
F["t_inn"] = d3._add_feature("building", "시험 여관", 9, 2)
d3.building_defs = {F["t_inn"]: "t_inn"}
rng0 = d3.rng.getstate()
b3 = mkbot("1", 2, 1, hp=9)
n_feat = len(d3.features)
HEADS = {"stone_tablet": "읽기: 석상 받침 f%d (발밑/인접)", "bench": "앉기: 벤치 f%d (발밑/인접) — 앉으면 HP +1 (상처가 있을 때)",
         "well": "마시기: 우물 f%d (발밑/인접) — 마시면 HP +1 (상처가 있을 때)", "t_stall": "구경하기: 노점 f%d (발밑/인접)",
         "t_dummy": "몸 풀기: 허수아비 f%d (발밑/인접)", "barrel": "뒤지기: 통 f%d (발밑/인접)",
         "t_hearth": "불 쬐기: 화덕 f%d (발밑/인접) — 불을 쬐면 HP +2 (상처가 있을 때)",
         "t_inn": "묵기: 시험 여관 f%d (문턱) — 묵으면 HP 가 전부 돌아오고 몸 상태가 낫는다"}
labels_ok, res3 = [], {}
for i, eid in enumerate(("stone_tablet", "bench", "well", "t_stall", "t_dummy", "barrel", "t_hearth", "t_inn")):
    b3["x"] = 2 + i
    o3 = d3.view(b3, [b3])
    labels_ok.append((HEADS[eid] % F[eid]) in [o["label"] for o in o3["options"] if o["type"] == "interact"])
    if eid == "t_inn":
        b3["status"] = {"출혈": {"n": 1}, "중독": {"n": 1}}
        b3["bleed_steps"], b3["slow_beat"] = 2, 1
    res3[eid] = d3.act(b3, {"type": "interact", "target": "f%d" % F[eid]}, [b3])
check("③ 메뉴 줄 — 줄 머리가 하는 일을 말한다(읽기·앉기·마시기·구경하기·몸 풀기·뒤지기·불 쬐기·묵기 문턱) · 수치는 몸에 남는 kind 만",
      all(labels_ok))
check("③ 결과 이름 — read·sat·drank·browsed·practiced·rummaged·warmed·lodged · 공통 칸(type interact·what·use_kind)",
      [res3[e]["result"] for e in ("stone_tablet", "bench", "well", "t_stall", "t_dummy", "barrel", "t_hearth", "t_inn")]
      == ["read", "sat", "drank", "browsed", "practiced", "rummaged", "warmed", "lodged"]
      and all(r["type"] == "interact" and r["what"] and r["use_kind"] in IA.KINDS for r in res3.values()))
check("③ 사실 칸 — 읽은 글 · 오른 HP(9→10→11 · 화덕 +2 → 13) · 진열 목록 · 나온 것",
      res3["stone_tablet"]["text"] == base4["stone_tablet"]["comps"]["use"]["text"]
      and (res3["bench"]["heal"], res3["bench"]["hp"]) == (1, 10) and (res3["well"]["heal"], res3["well"]["hp"]) == (1, 11)
      and (res3["t_hearth"]["heal"], res3["t_hearth"]["hp"]) == (2, 13)
      and res3["t_stall"]["wares"] == ["말린 과일", "밧줄", "등잔 기름"] and res3["barrel"]["got"] in ENT.USE_LOOT)
check("③ 묵기 — HP 전부(13→14, heal 1) · 상태 태그 소거(cleared [중독, 출혈] · 출혈 걸음·둔화 박자 0)",
      res3["t_inn"]["heal"] == 1 and b3["hp"] == 14 and res3["t_inn"]["cleared"] == ["중독", "출혈"]
      and b3["status"] == {} and b3["bleed_steps"] == 0 and b3["slow_beat"] == 0)
b3["x"] = 3
full = d3.act(b3, {"type": "interact", "target": "f%d" % F["bench"]}, [b3])
check("③ 성한 몸으로 앉으면 heal 0(상한 = maxhp) · 피처는 하나도 사라지지 않는다 · 판정 rng 무접촉(상태 그대로)",
      full["result"] == "sat" and full["heal"] == 0 and b3["hp"] == 14 and len(d3.features) == n_feat
      and d3.rng.getstate() == rng0)
b3["x"] = 6
check("③ 멀면 too_far(기존 거리 규칙 그대로 — 맨해튼 1)", d3.act(b3, {"type": "interact", "target": "f%d" % F["bench"]}, [b3])["result"] == "too_far")

print("── ④ 뒤지기")


def rummage_once(seed, eid, x=4, char="1"):
    d_, _ = menu_scene(seed)
    fid = IA.place(d_, eid, x, 2)
    b_ = mkbot(char, x, 1)
    return d_, b_, fid, d_.act(b_, {"type": "interact", "target": "f%d" % fid}, [b_])


_, _, _, ra = rummage_once(7, "barrel")
_, _, _, rb = rummage_once(7, "barrel", char="2")
got_by_seed = {s: rummage_once(s, "barrel")[3]["got"] for s in range(40)}
check("④ 추첨 = 세계 시드·자리의 해시 — 같은 세계는 누가 뒤지든 같은 것 · 시드가 다르면 달라진다(40시드에 둘 이상)",
      ra["got"] == rb["got"] and len(set(got_by_seed.values())) >= 2)
d4, _ = menu_scene()
f4 = d4._add_feature("barrel", "통", 1, 1)
seen_items = set()
for i in range(300):
    d4.features[f4].x, d4.features[f4].y = 1 + i % 10, 1 + (i // 10) % 3
    d4.features[f4].id = i
    seen_items.add(IA._draw(d4, d4.features[f4], base4["barrel"]["comps"]["use"]["loot"]))
d4.features[f4].id = f4
check("④ 가중표(빈손 3·물약 1·보물 1)가 세 항목을 다 낸다(번호·자리 300가지)", seen_items == set(ENT.USE_LOOT))
dp, bp, fp, rp = rummage_once(7, "t_crate_p")
check("④ 물약이 나온 통 — potions +1 · 결과에 소지 수 · 피처 존속", rp["got"] == "potion" and bp["potions"] == 1 and rp["potions"] == 1 and fp in dp.features)
rp2 = dp.act(bp, {"type": "interact", "target": "f%d" % fp}, [bp])
other = mkbot("2", 4, 1)
rp3 = dp.act(other, {"type": "interact", "target": "f%d" % fp}, [bp, other])
check("④ 두 번째는 used_up(소지 그대로) · once 는 세계의 상태 — 다른 사람이 뒤져도 used_up",
      rp2["result"] == "used_up" and bp["potions"] == 1 and rp3["result"] == "used_up" and other["potions"] == 0)
dq, _ = menu_scene()
fq = IA.place(dq, "t_crate_t", 4, 2)
dq.quests = G.new_quests()
dq.quests["accepted"]["lost_trinket"] = {"turn": 0, "by": "1"}
bq = mkbot("1", 4, 1)
rq = dq.act(bq, {"type": "interact", "target": "f%d" % fq}, [bq])
check("④ 보물이 나온 통 — bag +1 · 획득형 의뢰(D69 lost_trinket)가 센다(상자 선례)",
      rq["got"] == "treasure" and bq["bag"] == 1 and rq["bag"] == 1 and (rq.get("quest") or [{}])[0].get("done") is True
      and "lost_trinket" in dq.quests["done"])
dn, _ = menu_scene()
fn_ = IA.place(dn, "t_note", 4, 2)
bn = mkbot("1", 4, 1)
rn1 = dn.act(bn, {"type": "interact", "target": "f%d" % fn_}, [bn])
rn2 = dn.act(bn, {"type": "interact", "target": "f%d" % fn_}, [bn])
check("④ once 는 어느 kind 에나 — 쪽지(read, once): 한 번 읽히고 그 뒤는 used_up", rn1["result"] == "read" and rn2["result"] == "used_up" and rn2["use_kind"] == "read")

print("── ⑤ 읽기 texts[]")
d5, _ = menu_scene()
f5 = IA.place(d5, "t_shelf", 4, 2)
b5a, b5b = mkbot("1", 4, 1), mkbot("2", 3, 2)
reads = [d5.act(b5a, {"type": "interact", "target": "f%d" % f5}, [b5a, b5b]) for _ in range(4)]
rb5 = d5.act(b5b, {"type": "interact", "target": "f%d" % f5}, [b5a, b5b])
check("⑤ 읽을 때마다 다음 글(1/3 → 2/3 → 3/3 → 다시 1/3) · 읽는 사람마다 제 쪽수(카야는 1/3 부터) · 한 편짜리엔 page 칸 없음",
      [(r["page"], r["pages"], r["text"]) for r in reads] == [(1, 3, "첫째 글."), (2, 3, "둘째 글."), (3, 3, "셋째 글."), (1, 3, "첫째 글.")]
      and (rb5["page"], rb5["text"]) == (1, "첫째 글.") and "page" not in res3["stone_tablet"])

print("── ⑥ 묵기 — 성한 몸")
d6, _ = menu_scene()
f6 = d6._add_feature("building", "시험 여관", 4, 2)
d6.building_defs = {f6: "t_inn"}
b6 = mkbot("1", 4, 1)
r6 = d6.act(b6, {"type": "interact", "target": "f%d" % f6}, [b6])
check("⑥ 성한 몸으로 묵으면 heal 0·cleared [] — 문장은 '나을 상처가 없었다'(사실만)",
      r6["result"] == "lodged" and r6["heal"] == 0 and r6["cleared"] == [] and "나을 상처가 없었다" in IA.prose(r6))

print("── ⑦ 조합형 경로")
SC = {"map": ["##############", "#1..........>#", "#............#", "#2...........#", "##############"], "seed": 7,
      "bots": {"1": {"hp": 5}},
      "features": [{"type": "bench", "name": "벤치", "x": 2, "y": 2}, {"type": "barrel", "name": "통", "x": 6, "y": 2},
                   {"type": "t_crate_p", "name": "물약 궤짝", "x": 3, "y": 2},
                   {"type": "building", "name": "시험 여관", "x": 4, "y": 2, "entity": "t_inn"},
                   {"type": "building", "name": "시험 헛간", "x": 5, "y": 2, "entity": "t_hut"}]}
d7, bots7 = scenario.build(SC)
c1 = bots7[0]
c1["x"], c1["y"] = 2, 1
o7 = d7.view(c1, bots7)
fid7 = {f.name: "f%d" % f.id for f in d7.features.values()}
tg7 = {t["id"]: t["tags"] for t in o7["targets"] if t["kind"] == "feature"}
check("⑦ 조합형 판(scenario.build) — 대상 태그: 벤치 [object, interactable, seat] · 통 container · 쓰임 있는 건물 lodging · 없는 건물은 옛 [object]",
      d7.composed_actions is True and tg7[fid7["벤치"]] == ["object", "interactable", "seat"]
      and tg7[fid7["통"]] == ["object", "interactable", "container"]
      and tg7[fid7["시험 여관"]] == ["object", "interactable", "lodging"] and tg7[fid7["시험 헛간"]] == ["object"])
w7 = brains._wire(o7, {"1": "두란", "2": "카야"}, compose=True)
check("⑦ 조합형 문장 — '대상의 현재 사실'에 몸에 남는 쓰임만(벤치·여관 줄, 통은 태그만) · 대상 줄에 태그 · '그 밖의 정보' 누출 없음",
      ("- %s 벤치: 앉으면 HP +1 (상처가 있을 때)" % fid7["벤치"]) in w7
      and ("- %s 시험 여관: 묵으면 HP 가 전부 돌아오고 몸 상태가 낫는다" % fid7["시험 여관"]) in w7
      and ("- %s 통:" % fid7["통"]) not in w7 and "(object, interactable, seat)" in w7 and "## 그 밖의 정보" not in w7)
act7, err7 = CA.parse({"type": "use", "target": fid7["벤치"]}, o7)
r7 = d7.act(c1, act7, bots7)
check("⑦ use 벤치(곁) — type use · effect_type interact · result sat · HP 5→6 · resolution success",
      err7 is None and r7["type"] == "use" and r7.get("effect_type") == "interact" and r7["result"] == "sat" and c1["hp"] == 6
      and r7["resolution"]["status"] == "success")
o7b = d7.view(c1, bots7)
act7b, _ = CA.parse({"type": "use", "target": fid7["통"]}, o7b)
r7b = d7.act(c1, act7b, bots7)
steps = 0
while c1.get("order") and steps < 30:
    d7.turn += 1
    d7.step_order(c1, bots7)
    steps += 1
check("⑦ 멀리서 use 통 — 접근을 시작하고(approaching) 닿아서 한 번 뒤진다(자동 접근 = 기존 규칙 그대로)",
      r7b["result"] == "approaching" and (c1.get("last") or {}).get("result") == "rummaged" and abs(c1["x"] - 6) + abs(c1["y"] - 2) <= 1)
o7c = d7.view(c1, bots7)
act7c, _ = CA.parse({"type": "use", "target": fid7["통"]}, o7c)
r7c = d7.act(c1, act7c, bots7)
check("⑦ 다 쓴 통을 다시 use — used_up · resolution no_effect(실패가 아니라 변화 없음)",
      r7c["result"] == "used_up" and r7c["resolution"]["status"] == "no_effect")
c1["x"], c1["y"] = 4, 1
o7d = d7.view(c1, bots7)
r7d = d7.act(c1, CA.parse({"type": "use", "target": fid7["시험 여관"]}, o7d)[0], bots7)
c1["x"] = 5
o7e = d7.view(c1, bots7)
r7e = d7.act(c1, CA.parse({"type": "use", "target": fid7["시험 헛간"]}, o7e)[0], bots7)
check("⑦ use 건물 — 쓰임 있는 여관 = lodged(HP 전부) · 없는 헛간 = 옛 그대로 no_effect(no_intrinsic_use)",
      r7d["result"] == "lodged" and c1["hp"] == c1["maxhp"] and r7e["result"] == "no_effect" and r7e.get("reason_code") == "no_intrinsic_use")

print("── ⑧ 표현")
ALL_RES = list(res3.values()) + [full, rp, rp2, rq, rn2, reads[1], r6, r7, r7c, r7d]
ALL_RES.append({"type": "interact", "target": "f9", "result": "rummaged", "what": "통", "use_kind": "rummage", "got": "nothing"})
ALL_RES.append({"type": "interact", "target": "f9", "result": "used_up", "what": "쪽지", "use_kind": "read"})
prose_all = [brains._last_prose({k: v for k, v in r.items() if k != "char"}, {"1": "두란"}) for r in ALL_RES]
check("⑧ _last_prose — 새 결과 전부가 사실 문장(JSON 폴백·'상호작용(' 폴백 아님) · 조합형 결과(type use)도 같은 문장",
      all(isinstance(p, str) and p and "{" not in p and not p.startswith("상호작용(") for p in prose_all)
      and brains._last_prose(r7) == "벤치에 앉아 숨을 돌렸다(HP +1)")
check("⑧ 문장 표본 — 읽은 글 인용 · 쪽수 · 진열 · 조사(통을/허수아비를/쪽지는)",
      brains._last_prose(res3["stone_tablet"]) == '석상 받침의 글을 읽었다: "%s"' % res3["stone_tablet"]["text"]
      and brains._last_prose(reads[1]) == '책장의 글을 읽었다 (2/3): "둘째 글."'
      and brains._last_prose(res3["t_stall"]) == "노점에 진열된 것을 구경했다: 말린 과일, 밧줄, 등잔 기름"
      and brains._last_prose(res3["t_dummy"]) == "허수아비를 상대로 몸을 풀었다"
      and brains._last_prose(rp) == "물약 궤짝을 뒤졌다 — 물약 하나가 나왔다(소지 물약 1병)"
      and brains._last_prose(ALL_RES[-2]) == "통을 뒤졌다 — 비어 있다" and brains._last_prose(rp2) == "물약 궤짝은 이미 비어 있다"
      and brains._last_prose(ALL_RES[-1]) == "쪽지는 이미 쓰였다 — 더 나오는 것이 없다"
      and "몸이 다 나았다(HP +1, 나은 상태: 중독·출혈)" in brains._last_prose(res3["t_inn"]))
tags_all = [G.event_tags({k: v for k, v in r.items() if k != "char"}) for r in ALL_RES]
check("⑧ 궤적 꼬리표(event_tags) — '기타' 폴백 없음 · 키는 사건 사전 안(use·loot·misc) · 물약·보물은 [획득], 다 쓴 것은 [헛손질]",
      all(t and all(k in G.EVENT_KINDS and label != "기타" and "{" not in fact for k, label, fact in t) for t in tags_all)
      and G.event_tags(rp)[0][:2] == ("loot", "획득") and G.event_tags(rp2)[0][:2] == ("misc", "헛손질")
      and G.event_tags(res3["stone_tablet"])[0][:2] == ("use", "읽음"))
check("⑧ 관전 요약(act_summary) — 메뉴형·조합형 결과 둘 다 문장('상호작용 f… — read' 폴백 아님)",
      all(show_runner.act_summary(r) == IA.prose(r) for r in ALL_RES if r.get("char")))

print("── ⑨ 목격")
d9, _ = menu_scene()
f9 = IA.place(d9, "bench", 2, 2)
a9, w9, far9 = mkbot("1", 2, 1, hp=9), mkbot("2", 1, 3), mkbot("3", 9, 3)
d9.act(a9, {"type": "interact", "target": "f%d" % f9}, [a9, w9, far9])
wit = (w9.get("witnessed") or [{}])[-1]
check("⑨ 곁의 사람은 본다 — ally_use{char, what 벤치, id, result '앉아 쉬었다'} · 당사자에겐 없음(자기 경험 = last)",
      wit == {"kind": "ally_use", "char": "1", "what": "벤치", "id": "f%d" % f9, "result": "앉아 쉬었다"} and not a9.get("witnessed"))
check("⑨ 목격 문장 = 기존 '사용' 한 동사 — '두란(봇1)가 벤치 f…을(를) 사용하는 것을 (앉아 쉬었다)' · 집계 라벨 '동료 사용'",
      brains._witness_prose({**wit, "name": "두란"}) == "두란(봇1)가 벤치 f%d을(를) 사용하는 것을 (앉아 쉬었다)" % f9
      and G.WITNESS_LABELS.get(wit["kind"]) == "동료 사용")
d9.events = False
w9["witnessed"] = []
d9.act(a9, {"type": "interact", "target": "f%d" % f9}, [a9, w9, far9])
check("⑨ 사건층 스위치(events)가 꺼진 판엔 목격 없음(기존 _witness 규율 그대로)", not w9.get("witnessed"))

print("── ⑩ 오브젝트 태그(D39)")
d10, _ = menu_scene()
d10.objtags = True
fb10, fc10 = IA.place(d10, "bench", 2, 2), IA.place(d10, "t_crate_p", 3, 2)
b10 = mkbot("1", 2, 1, hp=9)
for _ in range(2):
    d10.act(b10, {"type": "interact", "target": "f%d" % fb10}, [b10])
b10["x"] = 3
d10.act(b10, {"type": "interact", "target": "f%d" % fc10}, [b10])
o10 = d10.view(b10, [b10])
tag10 = {f["name"]: f.get("tag") for f in o10["sights"]["features"]}
check("⑩ 쓰고도 남는 오브젝트라 태그가 붙는다 — 벤치 '앉아 봄 ×2' · 궤짝 '뒤져 봄 ×1 (물약 나옴)' · 메뉴 줄 접미",
      tag10["벤치"] == {"verb": "앉아 봄", "n": 2} and tag10["물약 궤짝"] == {"verb": "뒤져 봄", "n": 1, "note": "물약 나옴"}
      and any(l.startswith("뒤지기: 물약 궤짝") and l.endswith("— 뒤져 봄 ×1 (물약 나옴)") for l in [o["label"] for o in o10["options"]]))
d10b, _ = menu_scene()
fb10b = IA.place(d10b, "bench", 2, 2)
b10b = mkbot("1", 2, 1, hp=9)
d10b.act(b10b, {"type": "interact", "target": "f%d" % fb10b}, [b10b])
check("⑩ 스위치(objtags)가 꺼진 판 — 장부 안 쌓임 · obs 에 tag 없음", not b10b.get("obj_tags")
      and all("tag" not in f for f in d10b.view(b10b, [b10b])["sights"]["features"]))

print("── ⑪ 피클 왕복")
blob = pickle.dumps((dp, bp, d5, b5a))               # 이어가기(D79)가 세계를 피클로 얼린다 — 같은 길을 한 번 건너 본다
dp2, bp2, d52, b5a2 = pickle.loads(blob)             # (방금 이 프로세스가 만든 바이트만 읽는다 — 밖에서 온 데이터가 아니다)
check("⑪ 다 쓴 상태(use_spent)·읽던 쪽수가 피클을 건넌다 — 되살린 세계에서도 used_up · 다음 글은 2/3",
      dp2.use_spent == dp.use_spent and dp2.act(bp2, {"type": "interact", "target": "f%d" % fp}, [bp2])["result"] == "used_up"
      and d52.act(b5a2, {"type": "interact", "target": "f%d" % f5}, [b5a2])["page"] == 2)
d11, _ = menu_scene()
f11 = IA.place(d11, "t_crate_p", 4, 2)
b11 = mkbot("1", 4, 1)
check("⑪ 속성이 없는 세계(from_ascii·옛 스냅샷)도 그대로 돈다 — use_spent 는 처음 쓸 때 생긴다(getattr)",
      not hasattr(d11, "use_spent") and d11.act(b11, {"type": "interact", "target": "f%d" % f11}, [b11])["result"] == "rummaged"
      and f11 in d11.use_spent)

print("── ⑫ 배치 도우미 place()")
d12, _ = menu_scene()
fid12 = IA.place(d12, "well", 4, 2)


def raises(fn):
    try:
        fn()
    except ValueError:
        return True
    return False


check("⑫ place — 정의의 type·이름으로 피처 · story 는 place_story 에(피처 줄 끝의 about) · 피처 as_dict 필드는 옛 그대로",
      (d12.features[fid12].type, d12.features[fid12].name) == ("well", "우물")
      and d12.place_story[fid12] == base4["well"]["comps"]["story"]
      and next(f for f in d12.view(mkbot("1", 1, 1), [])["sights"]["features"] if f["id"] == "f%d" % fid12).get("about") == "두레박이 걸린 마을 우물"
      and set(d12.features[fid12].as_dict()) == {"id", "type", "name", "x", "y", "room_id", "concealed", "perception_gate"})
check("⑫ place 거절 — 벽 칸 · 이미 피처가 선 칸(출구 포함) · 오브젝트가 아닌 정의 = ValueError(시작 전에 죽는다)",
      raises(lambda: IA.place(d12, "bench", 0, 0)) and raises(lambda: IA.place(d12, "bench", 4, 2))
      and raises(lambda: IA.place(d12, "bench", 10, 1)) and raises(lambda: IA.place(d12, "t_inn", 5, 2)))

print("── ⑭ 진짜 마을(build_town, layout v4)의 건물 문턱")
dt, _ = show_runner.build_town()
bare = next(((fid, eid) for fid, eid in sorted((getattr(dt, "building_defs", None) or {}).items())
             if eid and not ENT.get(eid)["comps"].get("use")), None)
if bare is None:
    check("⑭ (건너뜀) 마을의 모든 건물 정의에 이미 use 부품이 있다", True)
else:
    fid_t, eid_t = bare
    ft = dt.features[fid_t]
    bt = mkbot("1", ft.x, ft.y, hp=5)
    head = lambda: [o["label"] for o in dt.view(bt, [bt]).get("options", []) if o["type"] == "interact" and o.get("target") == "f%d" % fid_t]
    before = head()
    ENT.get(eid_t)["comps"]["use"] = {"kind": "lodge"}          # 메모리의 정의에만 잠깐 단다(파일 무접촉) — '새 건물 기능은 JSON 한 장'의 모사
    try:
        after = head()
        rt = dt._interact(bt, "f%d" % fid_t, [bt])
    finally:
        del ENT.get(eid_t)["comps"]["use"]
    check("⑭ 부품 없는 건물(%s)의 문턱엔 상호작용 줄이 없다(D60) → 정의에 use 를 달면 '묵기: … (문턱)' 이 열리고 묵어진다 → 떼면 다시 없다" % ft.name,
          before == [] and len(after) == 1 and after[0].startswith("묵기: %s f%d (문턱)" % (ft.name, fid_t))
          and rt["result"] == "lodged" and bt["hp"] == bt["maxhp"] and head() == [])

print("── ⑮ 다 쓴 것은 다 쓴 것으로 보인다 + read 의 동사 변형")
inject(odef("t_flask", "약수 병", {"kind": "drink", "heal": 3, "once": True}))
inject(odef("t_bed", "꽃밭", {"kind": "read", "verb": "look", "texts": ["꽃이 피어 있다.", "벌이 오간다."]}))
d15, _ = menu_scene()
f15, f15b, f15c = IA.place(d15, "t_flask", 4, 2), IA.place(d15, "t_crate_p", 6, 2), IA.place(d15, "well", 8, 2)
a15, o15 = mkbot("1", 4, 1, hp=5), mkbot("2", 4, 3, hp=5)


def lab15(b_):
    return [o["label"] for o in d15.view(b_, [a15, o15])["options"] if o["type"] == "interact"]


def use15(b_, fid):
    return next(f["use"] for f in d15.view(b_, [a15, o15])["sights"]["features"] if f["id"] == "f%d" % fid)


before15 = lab15(o15)
check("⑮ 쓰기 전 — 다른 봇의 라벨에 효과 수치('마시면 HP +3')가 있고 use 칸은 {kind, heal}",
      ("마시기: 약수 병 f%d (발밑/인접) — 마시면 HP +3 (상처가 있을 때)" % f15) in before15 and use15(o15, f15) == {"kind": "drink", "heal": 3})
r15 = d15.act(a15, {"type": "interact", "target": "f%d" % f15}, [a15, o15])
after15 = lab15(o15)
check("⑮ 두란이 다 쓴 뒤 — 카야(다른 봇)의 라벨에 효과 수치가 없다: '… — 이미 쓰였다 — 더 나오는 것이 없다' · use 칸 = {kind, spent}(heal 없음)",
      r15["result"] == "drank" and ("마시기: 약수 병 f%d (발밑/인접) — 이미 쓰였다 — 더 나오는 것이 없다" % f15) in after15
      and not any("약수 병" in l and "HP +" in l for l in after15) and use15(o15, f15) == {"kind": "drink", "spent": True})
a15["x"], o15["x"] = 6, 6
d15.act(a15, {"type": "interact", "target": "f%d" % f15b}, [a15, o15])
a15["x"] = 8
twice15 = [d15.act(a15, {"type": "interact", "target": "f%d" % f15c}, [a15, o15])["result"] for _ in range(2)]
check("⑮ 뒤진 통 — 다른 봇의 라벨 '뒤지기: … — 이미 비어 있다' · once 가 아닌 우물은 몇 번을 써도 옛 칸 그대로(수치 유지)",
      ("뒤지기: 물약 궤짝 f%d (발밑/인접) — 이미 비어 있다" % f15b) in lab15(o15)
      and twice15 == ["drank", "drank"] and use15(o15, f15c) == {"kind": "drink", "heal": 1}
      and IA.fact_text({"kind": "drink", "heal": 1}) == "마시면 HP +1 (상처가 있을 때)")
SC15 = {"map": ["##############", "#1..........>#", "#............#", "#2...........#", "##############"], "seed": 7,
        "bots": {"1": {"hp": 5}, "2": {"hp": 5}},
        "features": [{"type": "t_flask", "name": "약수 병", "x": 2, "y": 2}, {"type": "t_bed", "name": "꽃밭", "x": 4, "y": 2}]}
dc15, bc15 = scenario.build(SC15)
ca15, cb15 = bc15[0], bc15[1]
ca15["x"], ca15["y"], cb15["x"], cb15["y"] = 2, 1, 2, 3
fidc = {f.name: "f%d" % f.id for f in dc15.features.values()}
w15a = brains._wire(dc15.view(cb15, bc15), {"1": "두란", "2": "카야"}, compose=True)
dc15.act(ca15, CA.parse({"type": "use", "target": fidc["약수 병"]}, dc15.view(ca15, bc15))[0], bc15)
w15b = brains._wire(dc15.view(cb15, bc15), {"1": "두란", "2": "카야"}, compose=True)
check("⑮ 조합형 '대상의 현재 사실' — 쓰기 전 '마시면 HP +3 …' → 두란이 다 쓴 뒤 카야의 프롬프트엔 '이미 쓰였다 …'만(효과 수치 없음)",
      ("- %s 약수 병: 마시면 HP +3 (상처가 있을 때)" % fidc["약수 병"]) in w15a
      and ("- %s 약수 병: 이미 쓰였다 — 더 나오는 것이 없다" % fidc["약수 병"]) in w15b and "HP +3" not in w15b)
ca15["x"] = 4
o15l = dc15.view(ca15, bc15)
tg15 = {t["id"]: t["tags"] for t in o15l["targets"] if t["kind"] == "feature"}
r15l = dc15.act(ca15, CA.parse({"type": "use", "target": fidc["꽃밭"]}, o15l)[0], bc15)
dm15, _ = menu_scene()
fm15 = IA.place(dm15, "t_bed", 4, 2)
bm15 = mkbot("1", 4, 1)
check("⑮ read 의 동사 변형(verb look) — 메뉴 줄 머리 '살펴보기' · 조합형 태그 lookable · 결과 이름은 read(+verb) · 문장 '꽃밭을 살펴보았다: …' · 꼬리표 [살펴봄]",
      ("살펴보기: 꽃밭 f%d (발밑/인접)" % fm15) in [o["label"] for o in dm15.view(bm15, [bm15])["options"]]
      and tg15[fidc["꽃밭"]] == ["object", "interactable", "lookable"]
      and r15l["result"] == "read" and r15l["verb"] == "look" and brains._last_prose(r15l) == "꽃밭을 살펴보았다: 꽃이 피어 있다."
      and G.event_tags(r15l)[0][:2] == ("use", "살펴봄") and "verb" not in res3["stone_tablet"])
check("⑮ 검증기 — 모르는 동사는 거절 · read 가 아닌 kind 에 verb 는 모르는 칸",
      any("verb" in p_ for p_ in problems(odef("b13", "x", {"kind": "read", "text": "a", "verb": "sniff"})))
      and any("모르는 칸" in p_ for p_ in problems(odef("b14", "x", {"kind": "sit", "verb": "look"}))))

print("── ⑬ 배선")
gm, ca, sr = src("dungeon_gm.py"), src("composed_actions.py"), src("show_runner.py")
check("⑬ _interact 훅은 한 곳(마지막 nothing 직전) · 꼬리표·문장·요약은 모듈로 넘긴다 · decorate 의 used_up = no_effect",
      gm.count("IA.handle(") == 1 and gm.index("IA.handle(") < gm.index("def _attack(") and "IA.event_tags(rec)" in gm
      and "G.IA.prose(last)" in src("brains.py") and "G.IA.summary(res)" in sr
      and "'no_effect', 'already_beside', 'used_up'" in ca)
check("⑬ 러너의 Dungeon( 생성 세 자리·지문은 무접촉(다른 게이트의 글자 검사) · interactables 는 엔진을 import 하지 않는다(순환 없음)",
      sr.count("give_verb=GIVE_ON, bond_verb=BOND_ON") == 2 and "import dungeon_gm" not in src("interactables.py")
      and "use_spent" not in sr)
check("⑬ _run_gates.sh 등록", "verify_use" in src("_run_gates.sh"))

if C.failed:
    print("FAILED %d" % C.failed)
    raise SystemExit(1)
print("ALL PASS — verify_use (D89 쓰임 부품: 8 kind · 메뉴형·조합형 · once · 목격 · 태그 · 피클, 실 LLM 0콜)")

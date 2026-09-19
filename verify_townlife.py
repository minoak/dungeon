# -*- coding: utf-8 -*-
"""D90 마을 생활 — 그림 속 고정물을 쓸 수 있는 오브젝트로 + 새 주민 + 건물의 쓰임. LLM 0콜.
(2026-09-20 — 파트너 "마을에서 커뮤니케이션 그리고 마을에서 여러 상호작용을 하면서 실제로 이 마을에서 캐릭터가 살아간다는 걸 보여줘야 해 …
 npc를 더 넣더라도 이 부분은 완성해야해" · 설계 원장 D83 의 남은 기둥 C "마을에서 할 일의 행동 수단이 없다")
마을 v4 그림 속 고정물(분수·우물·석상·알림판·벤치 셋·탁자·좌판 둘·화덕·훈련대·궤짝·천막·화단) 곁의 바닥 칸에 쓰임 부품(D89 use)이 달린
오브젝트가 서고, 숙소 셋은 묵기·가게 넷은 구경이 문턱에서 열리고, 새 주민(정착 일곱·행인 둘)이 선다. 전부 러너 스위치 DUNGEON_TOWN_LIFE=1
(러너 기본 0 — 론처가 켠다) 뒤다. 새 동사 없음(전부 기존 use/interact 밑) · 돈·가격·매매 없음.
게이트:
  ① 끈 판 = 옛 판: 스위치 상수 0 · 피처는 옛 19개(정착 셋·건물 열둘·행인 셋·입구) 그대로 · 건물에 쓰임·켠 판용 문장 없음 · 표식(town_life) 없음 ·
     layout 에서 life_* 필드를 지운 옛 layout 으로 지은 마을과 피처·행인 자리·rng 상태가 같다 · 러너 스트림도 (started 빼고) 글자까지 같다
  ② 배치: layout.json ↔ build.py 의 life_objects·life_npcs 가 글자까지 같다 · 켠 판 = 오브젝트 15·새 정착 주민 7·새 행인 2 ·
     전부 출발 자리에서 path_to 도달 · 한 칸에 하나 · 출발 자리 2칸 밖 · 구역 연결 칸·문턱이 아니다 · 새 행인은 제 걷는 자리(한 줄) 안에서만 걷는다
  ③ 쓰임(메뉴형): 오브젝트 15 + 건물 7 을 한 번씩 — 줄 머리·결과 이름·사실 칸 · 곁의 사람은 본다(ally_use) · 묵기가 다친 몸을 고친다 ·
     궤짝은 한 번(다 쓴 뒤 다른 봇의 라벨에 효과·'뒤지기' 약속 없음) · 알림판은 쪽마다 다른 글 · 화단은 '살펴보기' · 판정 rng 무접촉
  ④ 새 주민: 말 걸기(더미) = 켠 판용 대사 → 두 번째는 재방문 대사 · 옛 상인의 선물 그대로(물약 하나·빈손이면 단검) · 먼저 거는 인사({name}) ·
     NPC 두뇌의 재료(역할·성격·세계의 사실)가 새 주민에게도 선다 — 프롬프트에 성격이 실린다(두뇌 호출은 대역)
  ⑤ 문장: 켠 판의 어떤 문장도 '서비스는 아직 준비 중'·'손님 받을 준비가 안 됐어'를 말하지 않는다 · 끈 판의 정의 문장은 그대로 ·
     건물 역할 부품 스위치(NOTICES)를 끈 판은 쓰임을 못 찾으니 건물의 켠 판용 문장도 접는다(거짓 방지) · 임시 문장 표식(note)
  ⑥ 조합형 경로: 대상 태그(interactable + kind) · '대상의 현재 사실' 줄 · use → 결과 + effect_type interact · '그 밖의 정보' 누출 없음
  ⑦ 구역 시야(D86) 켠 판: 지금 선 구역의 오브젝트만 보이고 쓸 수 있다 · 다른 구역의 것은 안 보인다
  ⑧ 피클 왕복: 표식·다 쓴 상태·건물의 쓰임이 남는다
  ⑨ 러너 판(더미 · 임시 state): 보이는 것을 하나씩 써 보는 각본 두뇌로 마을 틱이 예외 없이 돈다 · run_meta.town_life · level.visual.npcs 10 ·
     스트림에 새 결과(둘 이상의 쓰임 결과 + 새 주민과의 말)
  ⑩ 배선·검증기: compile_layout 거절(벽·겹침·연결 칸·길을 막는 주민) · life 부품 검증기(판정 칸 덮어쓰기·모르는 부품 거절) · _run_gates.sh 등록
(기존 게이트는 별도 실행.)
"""
import ast
import contextlib
import copy
import functools
import io
import json
import os
import pickle
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = tempfile.mkdtemp(prefix="wl_townlife_")
STATE = os.path.join(ROOT, "state")
os.makedirs(STATE, exist_ok=True)
BASE_ENV = dict(DUNGEON_GM="0", DUNGEON_STEP_DELAY="0", DUNGEON_TURNS="60", DUNGEON_W="40", DUNGEON_H="16",
                DUNGEON_DEPTHS="2", DUNGEON_SEED="7", DUNGEON_MONSTERS="0", DUNGEON_TRAPS="0", DUNGEON_LURKERS="0",
                DUNGEON_BESTIARY_FILE="", DUNGEON_PARTY_FILE=os.path.join(HERE, "party.json"), DUNGEON_STATE_DIR=STATE,
                DUNGEON_TOWN="1", DUNGEON_BRAIN_BACKEND="dummy", DUNGEON_BOSS="0", DUNGEON_RUNS_DIR=os.path.join(ROOT, "runs"),
                DUNGEON_ACTION_MODE="compose")     # 실판 기본 = 조합형(게이트 기본 menu 를 파일 안에서 덮는다 — verify_use 선례). 메뉴 줄은 관측의 options 로 본다
os.environ.update(BASE_ENV)
for k in ("DUNGEON_QUESTS", "DUNGEON_TOWN_APART", "DUNGEON_NPC_BRAIN", "DUNGEON_SOLO", "DUNGEON_START", "DUNGEON_MENU", "DUNGEON_RESUME",
          "DUNGEON_PARTYFORM", "DUNGEON_STRANGERS", "DUNGEON_TOWN_SIGHT", "DUNGEON_NPC_REPLY", "DUNGEON_TOWN_LIFE", "DUNGEON_NOTICES",
          "DUNGEON_TOWN_BUILDINGS", "DUNGEON_TOWN_WALKERS", "DUNGEON_ARCH", "DUNGEON_FLOOR_LIFE", "DUNGEON_BESTIARY_PLUS"):
    os.environ.pop(k, None)

import brains                                        # noqa: E402
brains._call_claude = lambda prompt, model="haiku": ""   # LLM 무력화(0콜)
import composed_actions as CA                        # noqa: E402
import dungeon_gm as G                               # noqa: E402
import entities as ENT                               # noqa: E402
import interactables as IA                           # noqa: E402
import show_runner as R                              # noqa: E402
import town_layout as TL                             # noqa: E402
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
with open(os.path.join(HERE, "town.json"), encoding="utf-8") as f:
    LAYOUT_PATH = os.path.join(HERE, json.load(f)["layout"])
with open(LAYOUT_PATH, encoding="utf-8") as f:
    LAYOUT = json.load(f)
OLD_LAYOUT = {k: v for k, v in LAYOUT.items() if k not in ("life_objects", "life_npcs")}   # 이 작업 전의 layout(필드 둘만 없다)
OLD_DIR = os.path.join(ROOT, "oldtown")
os.makedirs(OLD_DIR, exist_ok=True)
with open(os.path.join(OLD_DIR, "layout.json"), "w", encoding="utf-8") as f:
    json.dump(OLD_LAYOUT, f, ensure_ascii=False)
with open(os.path.join(OLD_DIR, "town.json"), "w", encoding="utf-8") as f:
    json.dump({"layout": "layout.json"}, f)
OLD_TOWN = os.path.join(OLD_DIR, "town.json")


def town(on=True, path=None, sight=None, quests=False, spawn=True):
    old = (R.TOWN_LIFE_ON, R.TOWN_SIGHT)
    R.TOWN_LIFE_ON = on
    if sight:
        R.TOWN_SIGHT = sight
    try:
        d, starts = R.build_town(path, apart=True, walkers=True, guide=True, quests=(G.new_quests() if quests else None))
    finally:
        R.TOWN_LIFE_ON, R.TOWN_SIGHT = old
    bs = []
    if spawn:
        for c in sorted(SHEETS):
            bs.append(G.spawn(d, c, bs, sheet=dict(SHEETS[c])))
    d.turn = 1
    return d, bs, starts


def feats(d):
    return sorted((f.id, f.type, f.name, f.x, f.y, bool(getattr(f, "walker", False))) for f in d.features.values())


def by_name(d, name, nth=0):
    return [f for f in d.features.values() if f.name == name][nth]


def stand_by(d, f):
    """피처 곁(직교)의 걸을 수 있는 빈 칸 — NPC 는 몸이 칸을 막으니 곁에 선다."""
    return next((f.x + dx, f.y + dy) for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0))
                if d.grid[f.y + dy][f.x + dx] == G.FLOOR and d.feature_at(f.x + dx, f.y + dy) is None)


def cell_in(d, zone):
    """그 구역(이름)의 빈 바닥 칸 하나."""
    return next((x, y) for y in range(d.h) for x in range(d.w)
                if d.grid[y][x] == G.FLOOR and not d.feature_at(x, y) and d._town_zone(x, y) == zone)


def labels(d, b, bots):
    return [o["label"] for o in d.view(b, bots).get("options", []) if o["type"] == "interact"]


OLD_NPCS = ["길드 접수원", "성직자", "주점 주인"]
OLD_WALKERS = ["견습 모험자", "노점 상인", "떠돌이 모험자"]
NEW_SETTLED = {"innkeeper": "여관주인", "gear_merchant": "장비 상인", "item_merchant": "아이템 상인", "smith": "대장장이",
               "flower_elder": "화단지기 노인", "fountain_child": "잡화점 집 막내", "retired_adventurer": "은퇴한 모험자"}
NEW_WALKERS = {"town_resident": "동네 주민", "shop_porter": "짐꾼"}
OBJ_KIND = {"fountain": "drink", "well": "drink", "statue": "read", "guild_board": "read", "temple_bench": "sit", "guild_bench": "sit",
            "guild_bench_east": "sit", "tavern_table": "sit", "east_stall": "browse", "south_stall": "browse", "forge": "warm",
            "training_rack": "practice", "training_crate": "rummage", "camp_tent": "sit", "flowerbed": "read"}
BLD_KIND = {"일반 여관": "lodge", "정원 숙소": "lodge", "공동 숙소": "lodge", "대장간": "browse", "공방": "browse", "장비점": "browse", "잡화점": "browse"}

print("── ① 끈 판 = 옛 판")
d0, bots0, st0 = town(on=False)
d0o, _, st0o = town(on=False, path=OLD_TOWN)
check("① 러너 스위치 기본 0 · 끈 마을 = 피처 19(입구·정착 셋·건물 열둘·행인 셋) · 새 피처 타입·새 주민 없음 · 표식(town_life) 없음",
      R.TOWN_LIFE_ON is False and len(d0.features) == 19 and not hasattr(d0, "town_life")
      and sorted(f.name for f in d0.features.values() if f.type == "npc" and not f.walker) == OLD_NPCS
      and sorted(f.name for f in d0.features.values() if f.type == "npc" and f.walker) == OLD_WALKERS
      and {f.type for f in d0.features.values()} == {"exit", "npc", "building"} and len(d0.place_story) == 19, feats(d0)[:4])
check("① 끈 마을의 건물 — 쓰임 없음(문턱에 상호작용 줄 없음 · D60 그대로) · 역할·이야기는 옛 문장(숙소·가게 여덟 종의 '…서비스는 아직 준비 중이다')",
      all(IA.use_of(d0, f) is None for f in d0.features.values())
      and all("use" not in x for x in d0.view(bots0[0], bots0)["sights"]["features"])
      and sum("서비스는 아직 준비 중이다" in (s.get("history") or "") for s in d0.place_story.values()) == 9
      and by_name(d0, "일반 여관").id not in d0.feature_roles)
check("① 옛 layout(life_* 필드 없음)으로 지은 마을과 같다 — 피처(번호·타입·이름·자리)·출발 자리·판정 rng·행인 rng 상태",
      feats(d0) == feats(d0o) and st0 == st0o and d0.rng.getstate() == d0o.rng.getstate()
      and d0.walk_rng.getstate() == d0o.walk_rng.getstate() and d0.layout_result["map"] == d0o.layout_result["map"])


def run(on, path=None, brain=None):
    """러너 한 판(더미 두뇌 · DUNGEON_TURNS 60) → 스트림 행들. 상태 폴더는 임시(R.STATE) · 0콜. path = 다른 town.json, brain = 각본 두뇌."""
    st = tempfile.mkdtemp(prefix="run_", dir=ROOT)
    old = (R.STATE, R.TOWN_LIFE_ON, R.build_town, G.dummy_brain)
    R.STATE, R.TOWN_LIFE_ON = st, on
    if path:
        R.build_town = functools.partial(old[2], path)     # town_for_run 이 시그니처(apart·guide)를 본다 — partial 은 남은 인자를 그대로 보인다
    if brain:
        G.dummy_brain = brain
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                R.main()
            except SystemExit:
                pass
    finally:
        R.STATE, R.TOWN_LIFE_ON, R.build_town, G.dummy_brain = old
    with open(os.path.join(st, "stream.jsonl"), encoding="utf-8") as fh:
        return [json.loads(ln) for ln in fh if ln.strip()]


def strip(rows):
    return [json.dumps({k_: v_ for k_, v_ in r.items() if k_ != "started"}, ensure_ascii=False, sort_keys=True) for r in rows]


rows_off = run(False)
rows_old = run(False, path=OLD_TOWN)
check("① 러너 스트림: 끈 판 = 옛 layout 의 판과 (started 빼고) 글자까지 같다 · run_meta 에 town_life 없음 · 마을 level 의 피처 19",
      strip(rows_off) == strip(rows_old) and "town_life" not in rows_off[0]
      and len(next(r for r in rows_off if r["kind"] == "level" and r.get("depth") == 0)["features"]) == 19,
      (len(rows_off), len(rows_old)))

print("── ② 배치")
tree = ast.parse(src("art", "town-v4", "build.py"))
BUILD = {t.targets[0].id: ast.literal_eval(t.value) for t in tree.body
         if isinstance(t, ast.Assign) and isinstance(t.targets[0], ast.Name) and t.targets[0].id in ("life_objects", "life_npcs")}
check("② layout.json ↔ build.py — life_objects 15·life_npcs 7 이 글자까지 같다(layout.json 은 build.py 의 생성물)",
      [(o["id"], o["entity"], o["cell"]) for o in LAYOUT["life_objects"]] == [(i, e, c) for i, e, c in BUILD["life_objects"]]
      and [(n["id"], n["cell"], n["row"]) for n in LAYOUT["life_npcs"]] == [(i, c, r) for i, c, r in BUILD["life_npcs"]]
      and len(LAYOUT["life_objects"]) == 15 and len(LAYOUT["life_npcs"]) == 7 and set(o["id"] for o in LAYOUT["life_objects"]) == set(OBJ_KIND))
d1, bots1, st1 = town()
res1 = d1.layout_result
pad = res1["pad"]
objs = {o["id"]: d1.feature_at(o["x"], o["y"]) for o in res1["life_objects"]}
check("② 켠 마을 = 옛 19 + 오브젝트 15 + 새 정착 주민 7 + 새 행인 2 = 43 · 표식 town_life · 오브젝트는 정의의 이름·type · 쓰임 kind 가 표와 같다",
      len(d1.features) == 43 and d1.town_life is True
      and all(f is not None and (f.type, f.name) == (ENT.get(o["entity"])["type"], ENT.get(o["entity"])["name"])
              for o in res1["life_objects"] for f in [objs[o["id"]]])
      and {i: IA.use_of(d1, f)["kind"] for i, f in objs.items()} == OBJ_KIND
      and sorted(f.name for f in d1.features.values() if f.type == "npc" and not f.walker) == sorted(OLD_NPCS + list(NEW_SETTLED.values()))
      and sorted(f.name for f in d1.features.values() if f.type == "npc" and f.walker) == sorted(OLD_WALKERS + list(NEW_WALKERS.values())),
      len(d1.features))
cells = [(f.x, f.y) for f in d1.features.values()]
s1 = [tuple(v) for v in res1["starts"].values()]
conn = {(p[0] + pad, p[1] + pad) for c in LAYOUT["connections"] for p in c["cells"]}
doors = {tuple(e["cell"]) for e in res1["entrances"]}
check("② 한 칸에 하나 · 오브젝트는 출발 자리 2칸 밖 · 구역 연결 칸·건물 문턱이 아니다 · 전부 바닥",
      len(set(cells)) == len(cells)
      and all(max(abs(f.x - sx), abs(f.y - sy)) > G.PLACE_STORY_RANGE for f in objs.values() for sx, sy in s1)
      and not ({(f.x, f.y) for f in objs.values()} & (conn | doors)) and all(d1.grid[f.y][f.x] == G.FLOOR for f in objs.values()))
unreach = [f.name for f in d1.features.values() for sx, sy in [st1[sorted(st1)[0]]]
           if (f.x, f.y) != (sx, sy) and not d1.path_to(sx, sy, f.x, f.y, [])]
check("② 켠 판의 피처 43 전부 — 첫 출발 자리에서 path_to 가 닿는다(새 주민이 길을 막지 않는다)", not unreach, unreach)
walk_ok = True
wk = {f.name: fid for fid, f in d1.features.items() if f.walker and f.name in NEW_WALKERS.values()}
for _ in range(300):
    d1.walk_npcs(bots1)
    for nm, fid in wk.items():
        f = d1.features[fid]
        walk_ok = walk_ok and d1._in_walk_rect(f.x, f.y, d1.walkers[fid].get("rect")) and (f.x, f.y) not in doors
rects = {nm: d1.walkers[fid].get("rect") for nm, fid in wk.items()}
check("② 새 행인 둘은 제 걷는 자리(한 줄) 안에서만 걷는다(300틱) — 문턱 앞 칸·외길을 밟지 않는다(행인은 통행을 막는 몸)",
      walk_ok and len(wk) == 2 and all(r and r[3] == 1 for r in rects.values()), rects)

print("── ③ 쓰임(메뉴형)")
d3, bots3, _ = town()
d3.composed_actions = d3.auto_approach = False        # 메뉴형 경로(게이트·메뉴형 판) — interact 가 그대로 간다. 조합형은 ⑥
a, w, far = bots3
rng3 = d3.rng.getstate()
n_feat = len(d3.features)
HEAD = {"drink": "마시기", "sit": "앉기", "browse": "구경하기", "warm": "불 쬐기", "practice": "몸 풀기", "rummage": "뒤지기", "lodge": "묵기", "read": "읽기"}
RESULT = {"drink": "drank", "sit": "sat", "browse": "browsed", "warm": "warmed", "practice": "practiced", "rummage": "rummaged",
          "lodge": "lodged", "read": "read"}
got, heads_ok, wit_ok = {}, [], []
o3 = {o["id"]: d3.feature_at(o["x"], o["y"]) for o in d3.layout_result["life_objects"]}
targets3 = [(i, f, OBJ_KIND[i]) for i, f in o3.items()] + [(nm, by_name(d3, nm), k) for nm, k in BLD_KIND.items()]
for key, f, kind in targets3:
    a["x"], a["y"] = f.x, f.y                      # 오브젝트·문턱은 몸을 막지 않는다 — 그 칸에 선다(발밑)
    w["x"], w["y"] = stand_by(d3, f)
    far["x"], far["y"] = cell_in(d3, "신전 지구" if d3._town_zone(f.x, f.y) == "던전 입구 지구" else "던전 입구 지구")   # 다른 구역의 사람
    a["hp"], w["witnessed"] = max(1, a["maxhp"] - 3), []
    head = "살펴보기" if key == "flowerbed" else HEAD[kind]
    lab = [l for l in labels(d3, a, bots3) if (" %s f%d " % (f.name, f.id)) in l]
    heads_ok.append(len(lab) == 1 and lab[0].startswith(head + ": ") and ("(문턱)" in lab[0]) == (f.type == "building"))
    got[key] = d3.act(a, {"type": "interact", "target": "f%d" % f.id}, bots3)
    wit_ok.append(any(x.get("kind") == "ally_use" and x.get("id") == "f%d" % f.id for x in (w.get("witnessed") or []))
                  and not any(x.get("id") == "f%d" % f.id for x in (far.get("witnessed") or [])))
check("③ 메뉴 줄 22(오브젝트 15 + 건물 7) — 줄 머리가 하는 일을 말한다(마시기·앉기·읽기·살펴보기·구경하기·불 쬐기·몸 풀기·뒤지기·묵기 문턱)",
      all(heads_ok), [k for (k, _, _), ok in zip(targets3, heads_ok) if not ok])
check("③ 결과 이름 — kind 마다 제 결과(drank·sat·read·browsed·warmed·practiced·rummaged·lodged) · 공통 칸(type interact·what·use_kind)",
      all(got[k]["result"] == RESULT[kind] and got[k]["type"] == "interact" and got[k]["what"] == f.name and got[k]["use_kind"] == kind
          for k, f, kind in targets3), {k: got[k].get("result") for k, _, _ in targets3})
check("③ 몸에 남는 것 — 마시기·앉기·불 쬐기 HP +1 · 묵기는 HP 전부 · 구경은 진열 목록 · 석상은 받침의 글 · 화단은 살펴보기(verb look)",
      all(got[k]["heal"] == 1 for k in ("fountain", "well", "temple_bench", "tavern_table", "camp_tent", "forge"))
      and all(got[k]["heal"] == 3 and got[k]["hp"] == a["maxhp"] for k in ("일반 여관", "정원 숙소", "공동 숙소"))
      and got["east_stall"]["wares"] == ENT.get("produce_stall")["comps"]["use"]["wares"]
      and got["잡화점"]["wares"] == ENT.get("general_store")["comps"]["life"]["use"]["wares"]
      and got["statue"]["text"].startswith("받침돌에 새겨진 글") and got["flowerbed"].get("verb") == "look"
      and brains._last_prose(got["flowerbed"]).startswith("화단을 살펴보았다: ") and got["training_crate"]["got"] in ("nothing", "potion"))
check("③ 곁의 사람은 본다(ally_use — 같은 구역) · 멀리 다른 구역의 사람은 못 본다 · 피처는 하나도 사라지지 않는다 · 판정 rng 무접촉",
      all(wit_ok) and len(d3.features) == n_feat and d3.rng.getstate() == rng3, [k for (k, _, _), ok in zip(targets3, wit_ok) if not ok])
inn = by_name(d3, "일반 여관")
a["x"], a["y"] = inn.x, inn.y
a["hp"], a["status"], a["bleed_steps"], a["slow_beat"] = 2, {"출혈": {"n": 1}, "중독": {"n": 1}}, 3, 1
r_inn = d3.act(a, {"type": "interact", "target": "f%d" % inn.id}, bots3)
check("③ 묵기가 다친 몸을 고친다 — HP 2 → 전부 · 상태 태그(중독·출혈) 소거 · 문장 '일반 여관에 묵었다 — 몸이 다 나았다(…)'",
      r_inn["result"] == "lodged" and a["hp"] == a["maxhp"] and a["status"] == {} and r_inn["cleared"] == ["중독", "출혈"]
      and brains._last_prose(r_inn).startswith("일반 여관에 묵었다 — 몸이 다 나았다(HP +%d" % (a["maxhp"] - 2)))
crate = o3["training_crate"]
a["x"], a["y"] = crate.x, crate.y
w["x"], w["y"] = stand_by(d3, crate)
r_again = d3.act(a, {"type": "interact", "target": "f%d" % crate.id}, bots3)
lab_w = [l for l in labels(d3, w, bots3) if "훈련장 궤짝" in l]
check("③ 궤짝은 한 번 — 다시 뒤지면 used_up · 다 쓴 뒤 **다른 봇**의 줄은 '뒤지기: 훈련장 궤짝 … — 이미 비어 있다'(세계가 거짓말하지 않는다)",
      r_again["result"] == "used_up" and lab_w == ["뒤지기: 훈련장 궤짝 f%d (발밑/인접) — 이미 비어 있다" % crate.id], lab_w)
board = o3["guild_board"]
a["x"], a["y"] = board.x, board.y
pages = [d3.act(a, {"type": "interact", "target": "f%d" % board.id}, bots3) for _ in range(5)]
check("③ 길드 알림판 — 읽을 때마다 다음 쪽지(2/5 … 5/5 → 1/5 · 위에서 한 번 읽었다) · 의뢰 게시판(길드 문턱의 board)과 다른 피처",
      [p["page"] for p in pages] == [2, 3, 4, 5, 1] and len({p["text"] for p in pages}) == 5 and board.type == "guild_noticeboard"
      and max(abs(board.x - by_name(d3, "모험가 길드").x), abs(board.y - by_name(d3, "모험가 길드").y)) > 2)

print("── ④ 새 주민")
d4, bots4, _ = town(quests=True)
b4 = bots4[0]
b4["weapon"], b4["potions"] = None, 0
talk = {}
for eid, nm in list(NEW_SETTLED.items()) + list(NEW_WALKERS.items()):
    f = by_name(d4, nm)
    b4["x"], b4["y"] = stand_by(d4, f)
    lab = [l for l in labels(d4, b4, bots4) if l.startswith("말 걸기: %s " % nm)]
    talk[eid] = (lab, d4.act(b4, {"type": "interact", "target": "f%d" % f.id}, bots4),
                 d4.act(b4, {"type": "interact", "target": "f%d" % f.id}, bots4))
check("④ 새 주민 아홉 — 곁에 서면 '말 걸기' 줄 · 첫 말은 켠 판용 대사(정의의 line — life 가 있으면 그것) · 두 번째는 재방문 대사(again)",
      all(len(lab) == 1 and r1["line"] == ENT.npc(eid, life=True)["line"] and r2["line"] == ENT.npc(eid, life=True)["line_again"]
          and r2.get("again") is True for eid, (lab, r1, r2) in talk.items()), {e: v[1].get("result") for e, v in talk.items()})
check("④ 옛 상인의 선물은 옛 그대로(D32 상점 v0) — 장비 상인: 빈손이면 단검 · 아이템 상인: 한 사람에 물약 하나 · 나머지는 대화만",
      talk["gear_merchant"][1]["result"] == "npc_gift" and talk["gear_merchant"][1]["item"] == "단검" and b4["weapon"]["name"] == "단검"
      and talk["item_merchant"][1]["result"] == "npc_gift" and talk["item_merchant"][1]["item"] == "물약" and b4["potions"] == 1
      and all(talk[e][1]["result"] == "npc_talk" for e in talk if e not in ("gear_merchant", "item_merchant")))
c4 = bots4[1]
child = by_name(d4, "잡화점 집 막내")
c4["x"], c4["y"] = stand_by(d4, child)
hails = [h for h in d4.npc_greetings(bots4) if h[1] == c4["char"]]
check("④ 먼저 거는 인사(D71) — 새 주민도 곁을 지나면 한 번 건넨다({name} 자리 채움) · 같은 방문에 두 번은 없다",
      any(h[0] == "잡화점 집 막내" and h[2] == ENT.npc("fountain_child")["hail"].replace("{name}", c4["name"]) for h in hails)
      and not [h for h in d4.npc_greetings(bots4) if h[1] == c4["char"] and h[0] == "잡화점 집 막내"], hails)
seen_prompts = []
old_call = brains._call_claude
brains._call_claude = lambda prompt, model="haiku": (seen_prompts.append(prompt) or '{"line": "그래, 앉아."}')
try:
    lines4 = {nm: brains.npc_reply(b4, {"npc": nm, "result": "npc_talk", "line": d4.npc_lines[nm]}, "안녕하세요",
                                   R.npc_facts(d4, nm, bots4, [], d4.quests), npc=d4.npc_defs[nm])
              for nm in list(NEW_SETTLED.values()) + list(NEW_WALKERS.values())}
finally:
    brains._call_claude = old_call
check("④ NPC 두뇌의 재료 — 새 주민 아홉 전부 역할·성격이 정의에서 서고(npc_defs), 말 걸기 프롬프트에 그 성격이 실린다(두뇌 호출은 대역 · 0콜)",
      all(lines4.values()) and len(seen_prompts) == 9
      and all(d4.npc_defs[nm].get("role") and d4.npc_defs[nm].get("persona") for nm in lines4)
      and all(d4.npc_defs[nm]["persona"] in p for nm, p in zip(lines4, seen_prompts)))
ret = ENT.get("retired_adventurer")["comps"]
ret_text = " ".join([ret["npc"][k] for k in ("line", "line_again", "persona", "hail")] + list(ret["story"].values()))
check("④ 은퇴한 모험자 — 세계가 검증하지 않는 던전 주장이 없다(몇 층·어느 몬스터·함정·보물을 말하지 않는다 — 개인의 옛이야기만)",
      not any(wd in ret_text for wd in ("층", "고블린", "거미", "함정", "보물", "계단", "보스")), ret_text[:60])

print("── ⑤ 문장")
on_text = [s for st in d1.place_story.values() for s in st.values()] + list(d1.feature_roles.values()) \
    + list(d1.npc_lines.values()) + list(d1.npc_lines_again.values())
check("⑤ 켠 판의 어떤 문장도 '서비스는 아직 준비 중'·'손님 받을 준비가 안 됐어'·'샛길 쪽 뒷문'을 말하지 않는다",
      not [s for s in on_text if "서비스는 아직 준비 중" in s or "손님 받을 준비" in s or "샛길" in s])
LIFE_BLD = ("ordinary_inn", "garden_inn", "shared_lodging", "blacksmith", "craft_workshop", "equipment_store", "general_store", "small_home", "tavern")
check("⑤ 끈 판의 정의 문장은 그대로 — 건물 아홉의 원래 story·role 은 옛 글자(life 는 따로 든 칸) · 여관주인의 원래 대사도 그대로(옛 마을 이관 해시)",
      all("life" in ENT.get(e)["comps"] and ENT.comps_of(e)["story"] == ENT.get(e)["comps"]["story"] for e in LIFE_BLD)
      and all("서비스는 아직 준비 중이다" in ENT.get(e)["comps"]["story"]["history"] for e in LIFE_BLD[:8])
      and ENT.npc("innkeeper")["line"].startswith("빈 방은 많은데 아직 손님 받을 준비가 안 됐어")
      and ENT.npc("innkeeper", life=True)["line"] != ENT.npc("innkeeper")["line"] and ENT.npc("innkeeper")["role"] is None)
inn1 = by_name(d1, "일반 여관")
check("⑤ 켠 판의 일반 여관 — 역할 '묵어 가는 곳' · 특징 '…문턱에서 묵을 수 있다' · 관측의 about·role 로 실린다 · 되는 것만 말한다(묵기가 실제로 열려 있다)",
      d1.feature_roles[inn1.id] == "묵어 가는 곳" and "문턱에서 묵을 수 있다" in d1.place_story[inn1.id]["trait"]
      and IA.use_of(d1, inn1) == {"kind": "lodge"}
      and next(x for x in d1.view(bots1[0], bots1)["sights"]["features"] if x["id"] == "f%d" % inn1.id).get("role") == "묵어 가는 곳")
old_notices = R.NOTICES_ON
R.NOTICES_ON = False
try:
    dn, botsn, _ = town()
finally:
    R.NOTICES_ON = old_notices
innn = by_name(dn, "일반 여관")
check("⑤ 건물 역할 부품 스위치(NOTICES)를 끈 판 — 건물의 쓰임을 못 찾으니 켠 판용 문장도 접는다(건물·여관주인 다 옛 문장 그대로 = 거짓 없음) · 오브젝트는 그대로 선다",
      IA.use_of(dn, innn) is None and "문턱에서 묵을 수 있다" not in dn.place_story[innn.id]["trait"] and innn.id not in dn.feature_roles
      and dn.town_life is False and dn.npc_lines["여관주인"] == ENT.npc("innkeeper")["line"]
      and len([f for f in dn.features.values() if f.type not in ("npc", "building", "exit")]) == 15)
NEW_DEFS = [o["entity"] for o in LAYOUT["life_objects"] if o["entity"] not in ("bench", "well")] + list(NEW_SETTLED) + list(NEW_WALKERS) + list(LIFE_BLD)
check("⑤ 임시 문장 표식 — 새 정의·life 를 단 정의 전부 note 에 'D90'과 '임시'",
      all("D90" in (ENT.get(e).get("note") or "") and "임시" in ENT.get(e)["note"] for e in NEW_DEFS),
      [e for e in NEW_DEFS if "D90" not in (ENT.get(e).get("note") or "")])

print("── ⑥ 조합형 경로")
d6, bots6, _ = town()
c6 = bots6[0]
well6 = by_name(d6, "우물")
c6["x"], c6["y"], c6["hp"] = well6.x, well6.y + 1 if d6.grid[well6.y + 1][well6.x] == G.FLOOR else well6.y, 5
c6["x"], c6["y"] = stand_by(d6, well6)
o6 = d6.view(c6, bots6)
tg6 = {t["id"]: t["tags"] for t in o6["targets"] if t["kind"] == "feature"}
w6 = brains._wire(o6, NAMES, compose=True)
check("⑥ 조합형 판(실판 기본) — 대상 태그: 우물 [object, interactable, drinkable] · '대상의 현재 사실'에 '마시면 HP +1 …' · '그 밖의 정보' 누출 없음",
      d6.composed_actions is True and tg6["f%d" % well6.id] == ["object", "interactable", "drinkable"]
      and ("- f%d 우물: 마시면 HP +1 (상처가 있을 때)" % well6.id) in w6 and "## 그 밖의 정보" not in w6)
act6, err6 = CA.parse({"type": "use", "target": "f%d" % well6.id}, o6)
r6 = d6.act(c6, act6, bots6)
inn6 = by_name(d6, "정원 숙소")
c6["x"], c6["y"] = inn6.x, inn6.y
o6b = d6.view(c6, bots6)
r6b = d6.act(c6, CA.parse({"type": "use", "target": "f%d" % inn6.id}, o6b)[0], bots6)
tav6 = by_name(d6, "주점")
c6["x"], c6["y"] = tav6.x, tav6.y
r6c = d6.act(c6, CA.parse({"type": "use", "target": "f%d" % tav6.id}, d6.view(c6, bots6))[0], bots6)
check("⑥ use 우물 → type use · effect_type interact · drank · HP +1 / use 정원 숙소(문턱) → lodged · HP 전부 / 쓰임 없는 건물(주점)은 옛 그대로 no_effect",
      err6 is None and r6["type"] == "use" and r6.get("effect_type") == "interact" and r6["result"] == "drank" and r6["heal"] == 1
      and r6b["result"] == "lodged" and c6["hp"] == c6["maxhp"] and {t["id"]: t["tags"] for t in o6b["targets"]}["f%d" % inn6.id][-1] == "lodging"
      and r6c["result"] == "no_effect", (r6.get("result"), r6b.get("result"), r6c.get("result")))

print("── ⑦ 구역 시야(D86) 켠 판")
d7, bots7, _ = town(sight="zone")
c7 = bots7[0]
fb7 = by_name(d7, "화단")
c7["x"], c7["y"] = stand_by(d7, fb7)
d7.seen_cells = None if not hasattr(d7, "seen_cells") else d7.seen_cells
o7 = d7.view(c7, bots7)
names7 = {x["name"] for x in o7["sights"]["features"]}
r7 = d7.act(c7, CA.parse({"type": "use", "target": "f%d" % fb7.id}, o7)[0], bots7)
check("⑦ 마을 시야 = 구역(D86) — 주거구역에 서면 그 구역의 오브젝트·주민이 보이고(화단·우물·화단지기 노인) 번화가의 분수·좌판은 안 보인다 · 쓰임은 그대로 된다",
      d7.town_sight == "zone" and {"화단", "우물", "화단지기 노인"} <= names7 and not ({"분수", "채소 좌판", "대장간 화덕"} & names7)
      and r7["result"] == "read" and r7.get("verb") == "look", sorted(names7)[:8])

print("── ⑧ 피클 왕복")
blob = pickle.dumps((d3, bots3))                     # 이어가기(D79)가 세계를 피클로 얼린다 — 같은 길을 한 번 건너 본다
d8, bots8 = pickle.loads(blob)                       # (방금 이 프로세스가 만든 바이트만 읽는다 — 밖에서 온 데이터가 아니다)
a8 = bots8[0]
crate8 = d8.feature_at(crate.x, crate.y)
inn8 = by_name(d8, "공동 숙소")
a8["x"], a8["y"] = crate8.x, crate8.y
r8a = d8.act(a8, {"type": "interact", "target": "f%d" % crate8.id}, bots8)
a8["x"], a8["y"], a8["hp"] = inn8.x, inn8.y, 1
r8b = d8.act(a8, {"type": "interact", "target": "f%d" % inn8.id}, bots8)
check("⑧ 표식(town_life)·다 쓴 상태·읽던 쪽수가 피클을 건넌다 — 되살린 세계에서도 궤짝은 used_up · 건물의 묵기는 그대로 열려 있다",
      d8.town_life is True and r8a["result"] == "used_up" and r8b["result"] == "lodged" and a8["hp"] == a8["maxhp"]
      and len(d8.features) == len(d3.features))

print("── ⑨ 러너 판(더미 · 임시 state)")
real_dummy = G.dummy_brain
used9, tried9 = {}, {}


def scripted(obs, char="?"):
    """보이는 것(입구 빼고)을 하나씩 다 써 본다 — 곁이면 쓰고, 멀면 걸어간다. 0콜 각본."""
    if obs.get("town"):
        for f in sorted((obs.get("sights") or {}).get("features") or [], key=lambda x: (x.get("dist", 99), x["id"])):   # 가까운 것부터
            key = (char, f["id"])
            if f.get("type") == "exit" or key in used9 or tried9.get(key, 0) > 25:
                continue
            tried9[key] = tried9.get(key, 0) + 1
            if f.get("adj"):
                used9[key] = True
                return {"type": "use", "target": f["id"]}
            return {"type": "goto", "target": f["id"]}
    return real_dummy(obs, char)


rows9 = run(True, brain=scripted)
res9 = {}
for r in rows9:
    for e in (r.get("events") if isinstance(r.get("events"), list) else []):
        if e.get("type") in ("use", "interact"):
            res9[e.get("result")] = res9.get(e.get("result"), 0) + 1
lv9 = next(r for r in rows9 if r["kind"] == "level" and r.get("depth") == 0)
check("⑨ 켠 러너 판 60틱이 예외 없이 끝까지 돈다 · run_meta.town_life · 마을 level 의 피처 43 · visual.npcs 10(새 정착 주민도 기존 시트의 행으로)",
      rows9[-1]["kind"] == "end" and rows9[0].get("town_life") is True and len(lv9["features"]) == 43
      and len(lv9["visual"]["npcs"]) == 10 and sum(1 for r in rows9 if r["kind"] == "tick") == 60, (rows9[-1].get("kind"), len(lv9["features"])))
check("⑨ 스트림에 새 결과가 찍힌다 — 쓰임 결과(IA.RESULTS) 둘 이상 + 사람과의 말(npc_talk·npc_gift)",
      len([k for k in res9 if k in IA.RESULTS]) >= 2 and (res9.get("npc_talk", 0) + res9.get("npc_gift", 0)) >= 1, res9)

print("── ⑩ 배선·검증기")


def compile_err(**over):
    lay = copy.deepcopy(LAYOUT)
    lay.update(over)
    try:
        TL.compile_layout(lay)
    except ValueError as e:
        return str(e)
    return None


obj0 = LAYOUT["life_objects"][0]
check("⑩ compile_layout 거절 — 벽 칸의 오브젝트 · 기존 NPC 칸과 겹침 · 서로 겹침 · 구역 연결 칸 · id 중복 · entity 없음",
      "겹친다" in (compile_err(life_objects=[{**obj0, "cell": [0, 0]}]) or "")
      and "겹친다" in (compile_err(life_objects=[{**obj0, "cell": LAYOUT["npcs"][0]["cell"]}]) or "")
      and "겹친다" in (compile_err(life_npcs=[{"id": "x", "cell": obj0["cell"]}]) or "")
      and "연결 칸" in (compile_err(life_objects=[{**obj0, "cell": LAYOUT["connections"][0]["cells"][0]}]) or "")
      and "중복" in (compile_err(life_objects=[obj0, obj0]) or "")
      and "필요" in (compile_err(life_objects=[{"id": "x", "cell": obj0["cell"]}]) or ""))
check("⑩ compile_layout 거절 — 일반 여관 문턱의 하나뿐인 앞 칸에 선 주민은 길을 막는다(문턱이 고립된다) · 지금 배치는 통과 · life_* 없는 layout 의 결과엔 그 열쇠가 없다",
      "길을 막는다" in (compile_err(life_npcs=[{"id": "x", "cell": [31, 51]}]) or "")
      and compile_err() is None and "life_objects" not in TL.compile_layout(copy.deepcopy(OLD_LAYOUT)))


def problems(defn):
    return ENT._problems([(os.path.join(defn["kind"], defn["id"] + ".json"), defn)], ".")


def ndef(life):
    return {"id": "t_n", "name": "시험 주민", "kind": "npc", "comps": {"npc": {"line": "안녕."}, "life": life}}


check("⑩ life 부품 검증기 — 문장 칸은 통과 · 판정 칸(gift·walk·report) 덮어쓰기·모르는 부품·빈 문장·NPC 에 use 는 거절 · 건물 life.use 는 쓰임 검증기를 탄다",
      not problems(ndef({"npc": {"line": "어서 와.", "role": "주민"}, "story": {"trait": "사는 사람"}}))
      and all(problems(ndef(x)) for x in ({"npc": {"gift": {"potions": 9}}}, {"npc": {"walk": {"region": "x"}}}, {"npc": {"report": True}},
                                          {"shop": {"a": "b"}}, {"npc": {"line": " "}}, {"use": {"kind": "lodge"}}, {}))
      and problems({"id": "t_b", "name": "시험 가게", "kind": "building",
                    "comps": {"building": {"size": [9, 6], "entrance": [4, 5], "texture": "ordinary_inn"}, "life": {"use": {"kind": "browse", "wares": []}}}})
      and "life" in ENT.COMPS["npc"] and "life" in ENT.COMPS["building"] and "life" not in ENT.COMPS["object"])
sr = src("show_runner.py")
check("⑩ 러너 배선 — 스위치 상수는 하나(새로 정의하지 않는다) · 켠 판에서만 읽는다 · 생성 세 자리 무접촉 · _run_gates.sh 등록",
      sr.count('TOWN_LIFE_ON = os.environ.get("DUNGEON_TOWN_LIFE", "0") == "1"') == 1 and "life_objects" in sr and "life_npcs" in sr
      and sr.count("give_verb=GIVE_ON, bond_verb=BOND_ON") == 2 and "verify_townlife" in src("_run_gates.sh"))

if C.failed:
    print("FAILED %d" % C.failed)
    raise SystemExit(1)
print("ALL PASS — verify_townlife (D90 마을 생활: 오브젝트 15·건물의 쓰임 7·새 주민 9 · 끈 판 그대로 · 메뉴형·조합형·구역 시야·피클·러너, 실 LLM 0콜)")

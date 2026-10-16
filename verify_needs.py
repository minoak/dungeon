# -*- coding: utf-8 -*-
"""p0.5.16 욕구 틀 + 배고픔(경제 1b — .orch/drafts/economy_design.md §3·§4.1·§5.2·§7·§8.1, DECISIONS 10-14·10-15) — 헤들리스 검증. LLM 0콜.
p0.5.18 몸·기분 줄(DECISIONS 10-16 '문장 대원칙'·'몸·기분 줄'): 관측 두 줄 '- 몸: …'(보통이 아닌 단계의 몸 문장) · '- 기분: 좋다 / 좋지 않다 (이유: …)'
(기분 조각 합산 — 0 근처면 없음 · 이유는 같은 쪽 큰 것부터 2개 · 동점은 낮은 충족도·단계 먼저) · 새 문장 글자 그대로 · 결과 문장 간결 · need_mood 사건 ·
mood_now 관전 칸 · 이관 10→11 · 시험용 욕구로 기분까지 데이터만으로.
게이트:
  ① 정의·검증기: 배고픔 정의(시작 70 · 4틱마다 1 · 81 가득 참 · 단계 넷 · 굶주림 효과 둘 · 기분 셋 · 무게 둘 · 취향 어휘 8) · 음식 셋(휴대식 i9·식사·햇사과) ·
     가게(주점 식사 3 · 잡화점 휴대식 2 · 채소 좌판 햇사과 1) · 뒤지기 표에 휴대식 · 검증기가 잘못된 욕구·먹을 것을 한 번에 거절한다 ·
     단계 없는 욕구(이름·뜻만)는 받고 엔진이 건너뛴다 · 내성(tolerance) 칸은 자리만 받는다
  ② 데이터만으로 새 욕구: 코드는 그대로, 시험용 욕구 정의 한 장(+말 파일)만 더해 고리가 돈다 — 줄기 · 단계 문장 · 단계 사건 · 채우기(from_events)
     · 가득 참(몸에 안 들어가는 욕구 — 행동은 막지 않고 need_none) · 기분 조각 · 스트림(봇 스냅샷·run_meta.need_defs) · 코드에 욕구 id 글자가 없다
  ③ 배고픔 단계 경계: 100·81 배부름 / 80·41 보통(문장 없음) / 40·16 배고픔 / 15·0 굶주림 · 판 시작 70 → t120 배고픔 · t220 굶주림(그 틱의 need_stage)
  ④ 굶주림 효과(문장이 약속하는 규칙을 엔진으로): 쉬기(rest — 나을 몸 상태가 없으면 눕지 않고 사실 · 쉬는 도중이면 깬다 · 몸 상태가 있으면 눕고 HP 는 그대로 상태만 낫는다)·
     앉기·마시기·불 쬐기·묵기 HP 0(묵기는 몸 상태는 낫고 값은 낸다) · 물약은 그대로 · 메뉴·대상 사실 줄이 HP 를 약속하지 않는다 ·
     hp_drain 60틱마다 −1 · 최대 HP 의 절반(올림)에서 멈춤 · 이미 그 아래면 그대로 · 죽지 않는다 · 궤적 꼬리표
  ⑤ 먹기 끝까지: 휴대식 use(i9 — 조합형)·drink(메뉴형) · 가득 참 거절(물건 그대로 · 실패) · 주점 식사(사는 순간 먹는다 · 배부르면 사지 않는다 · 모자라면 too_poor) ·
     햇사과 · 휴대식 사기(먹지 않는다)·팔기 · 건네기 · 뒤지기 · 무게(높음·낮음 — 줄기·채움·기분 시간) · 취향(좋아함·싫어함·기본) · 시트 칸 거르기 ·
     줄 상한 문장 2개(낮은 단계부터 — 조각이 아니라 문장 수)
  ⑥ 저장·이어가기: 층 이월·부활(소스) · 이관 8→9(옛 몸에 시작값 · 주점 주인·주점·채소 좌판의 말을 지금 정의로) · 피클 왕복 · 이어간 세계에서 먹기
  ⑦ 남에게 안 보임: 남의 관측·프롬프트에 내 욕구·기분이 없다 · 내 결과의 숫자는 공개 투영이 걷는다 · 프롬프트에 숫자·단계 이름 없음 · 목격은 '먹었다'뿐 ·
     관전 칸(needs·moods·need_w·taste) · NPC 두뇌 사실(주점 값 — 남의 배고픔 없음)
  ⑧ 문장 게이트: 욕구·음식·엔진 문장이 명령·의무·청유 꼴로 끝나지 않는다(빨간불 표본은 잡는다) · 지침은 기능 설명 한 줄
  ⑨ 러너 판(더미 · 임시 state): tick.bots[].needs · need_stage 사건(char 대신 bot — 실행된 결정 = 그 char 의 이벤트 하나) · run_meta.need_defs · 관전 로그 ·
     배고파지면 휴대식을 먹는 각본 두뇌 — 행동이 낳은 단계 사건이 같은 틱 기록에 · 기분 조각의 스트림 만료 · 시험용 욕구를 더한 판에서도 단계 사건이 스트림에 나온다
  ⑩ 배선: _run_gates.sh · STREAM_FORMAT · VERSION
"""
import contextlib
import copy
import glob
import io
import json
import os
import pickle
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = tempfile.mkdtemp(prefix="wl_needs_")
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
import info_guard as IG                              # noqa: E402
import interactables as IA                           # noqa: E402
import needs as NE                                   # noqa: E402
import show_runner as R                              # noqa: E402
import snapshot as S                                 # noqa: E402
import words as WD                                   # noqa: E402
import time as _time                                 # noqa: E402
_time.sleep = lambda s: None
R.STEP_DELAY = 0


class C:
    failed = 0
    n = 0


def check(name, ok, detail=""):
    C.n += 1
    print("  %s %s%s" % ("OK  " if ok else "FAIL", name, (" — " + str(detail)) if (detail and not ok) else ""))
    if not ok:
        C.failed += 1


def src(*p):
    with open(os.path.join(HERE, *p), encoding="utf-8") as f:
        return f.read()


SHEETS = R.load_party(os.path.join(HERE, "party.json"))
NAMES = {c: SHEETS[c]["name"] for c in SHEETS}
HUNGER = ENT.get("hunger")["comps"]["need"]


def town(on=True):
    """마을(마을 생활 켬/끔) + 파티 몸 셋. 정의의 말·값은 리포의 것 그대로."""
    old = R.TOWN_LIFE_ON
    R.TOWN_LIFE_ON = on
    try:
        d, starts = R.build_town(None, apart=True, walkers=False, guide=False, quests=None)
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
    taken = {(o["x"], o["y"]) for o in bots} | set(skip)
    return next((f.x + dx, f.y + dy) for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0))
                if d.grid[f.y + dy][f.x + dx] == G.FLOOR and d.feature_at(f.x + dx, f.y + dy) is None and (f.x + dx, f.y + dy) not in taken)


def put(b, xy):
    b["x"], b["y"] = xy


def beside(d, b, bots):
    """몸 b 곁(직교)의 빈 바닥 칸 — 건네기·남에게 쓰기(닿아야 한다)."""
    taken = {(o["x"], o["y"]) for o in bots}
    return next((b["x"] + dx, b["y"] + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                if d.grid[b["y"] + dy][b["x"] + dx] == G.FLOOR and d.feature_at(b["x"] + dx, b["y"] + dy) is None and (b["x"] + dx, b["y"] + dy) not in taken)


def act(d, b, bots, action):
    d.view(b, bots)                                   # 관측 = 참조(_target_refs)를 새로 짓는다(실판과 같은 순서)
    return d.act(b, dict(action), bots)


def wire(d, b, bots, compose=True):
    return brains._wire(d.view(b, bots), NAMES, compose=compose)


def gid_of(d, name):
    return next(g["gid"] for g in IA.goods(d) if g["name"] == name)


def hun(b):
    return b["needs"]["hunger"]


def stage_events(d):
    return [e for e in NE.drain(d) if e.get("result") == "need_stage"]


# ─────────────────────────────────────────────────────────────────────────────
print("── ① 정의·검증기")
check("① 배고픔 정의 = 설계 초안(§3.3·§3.4): 시작 70 · 4틱마다 1 · 81 이상 가득 참(먹기 거절) · 단계 배부름 81·보통 41·배고픔 16·굶주림 0",
      HUNGER["start"] == 70 and HUNGER["decay"] == 4 and HUNGER["full_at"] == 81 and HUNGER["full_blocks"] is True
      and {k: (v["min"], v["word"]) for k, v in HUNGER["stages"].items()} == {"full": (81, "배부름"), "normal": (41, "보통"), "hungry": (16, "배고픔"), "starving": (0, "굶주림")})
check("① 문장은 보통 단계에만 없다(§3.2 — 대부분의 시간에 줄이 없다) · 굶주림에만 효과 둘(no_regen + hp_drain 60틱·50%) · 기분 셋(120·60·60틱)",
      [bool(HUNGER["stages"][k].get("line")) for k in ("full", "normal", "hungry", "starving")] == [True, False, True, True]
      and HUNGER["stages"]["starving"]["effects"] == {"no_regen": True, "hp_drain": {"every": 60, "floor": 50}}
      and not any(HUNGER["stages"][k].get("effects") for k in ("full", "normal", "hungry"))
      and {k: v["time"] for k, v in HUNGER["mood"].items()} == {"like": 120, "plain": 60, "dislike": 60})
LINE = {k: (HUNGER["stages"][k].get("line")) for k in HUNGER["stages"]}
check("① p0.5.18 몸 문장 글자 그대로(문장 대원칙 — 꾸밈 없이 상태): 배부름 '배가 부르다.' · 배고픔 '배가 고프다.' · 굶주림 '몹시 배고프다. 쉬어도 기운이 돌아오지 않는다.' · 보통 없음",
      LINE == {"full": "배가 부르다.", "normal": None, "hungry": "배가 고프다.", "starving": "몹시 배고프다. 쉬어도 기운이 돌아오지 않는다."}, LINE)
check("① p0.5.18 기분 값(임시)·이유 낱말 글자 그대로: 배고픔 −10 '배고픔' · 굶주림 −20 '굶주림' · 배부름·보통 칸 없음 · 좋아함 +15 '좋아하는 {what:을} 먹음' · "
      "기본 +8 '배불리 먹음' · 싫어함 −5 '입에 맞지 않는 음식' + 결과 꼬리 '입에 맞지 않았다.' · 문턱 3 · 이유 2개 · 기분 낱말 좋다·좋지 않다·이유",
      {k: (v.get("mood"), v.get("why")) for k, v in HUNGER["stages"].items()} == {"full": (None, None), "normal": (None, None), "hungry": (-10, "배고픔"), "starving": (-20, "굶주림")}
      and {k: (v["mood"], v["why"], v.get("line")) for k, v in HUNGER["mood"].items()} == {"like": (15, "좋아하는 {what:을} 먹음", None), "plain": (8, "배불리 먹음", None),
                                                                                         "dislike": (-5, "입에 맞지 않는 음식", "입에 맞지 않았다.")}
      and NE.MOOD_EDGE == 3 and NE.WHY_CAP == 2 and ENT.mood_words() == {"good": "좋다", "bad": "좋지 않다", "why": "이유"},
      ({k: (v.get("mood"), v.get("why")) for k, v in HUNGER["stages"].items()}, HUNGER["mood"], ENT.mood_words()))
check("① 무게(§3.8.2 — 등급 하나가 셋을 함께): 낮음 6틱·150%·50% · 높음 3틱·70%·150% · 보통 = decay·100·100(적지 않는다) · 취향 어휘 8(§3.6)",
      HUNGER["weights"] == {"낮음": {"every": 6, "fill": 150, "mood_time": 50}, "높음": {"every": 3, "fill": 70, "mood_time": 150}}
      and NE.weight(HUNGER, "보통") == {"every": 4, "fill": 100, "mood_time": 100}
      and HUNGER["tastes"] == ["고기", "생선", "단것", "과일", "채소", "빵", "매운 것", "따뜻한 것"] and NE.tastes() == HUNGER["tastes"])
foods = {e: ENT.get(e) for e in ("ration", "meal", "apple")}
check("① 음식 셋(§4.1): 휴대식 ration +50 빵 · 식사 food +70 고기·따뜻한 것 · 햇사과 food +20 과일 · 소지 칸 i9 = 휴대식(몸의 정수 rations)",
      [(d_["type"], d_["comps"]["satisfies"], d_["comps"]["taste"]) for d_ in foods.values()]
      == [("ration", {"hunger": 50}, ["빵"]), ("food", {"hunger": 70}, ["고기", "따뜻한 것"]), ("food", {"hunger": 20}, ["과일"])]
      and CA.ITEM_SLOTS["i9"] == "ration" and IA.COUNTED["ration"] == "rations" and set(ENT.FOOD_TYPES) == {"ration", "food"})
check("① 가게(§5.2): 주점 식사 3 · 잡화점 휴대식 2(1에 되산다) · 채소 좌판 햇사과 1 — 마을 생활 판에만 · 식사·사과는 되사지 않는다(지닐 수 없다)",
      ENT.comps_of("tavern", True)["use"] == {"kind": "shop", "sells": [{"item": "meal", "price": 3}]} and ENT.comps_of("tavern", False).get("use") is None
      and {"item": "ration", "price": 2} in ENT.comps_of("general_store", True)["use"]["sells"]
      and ENT.get("produce_stall")["comps"]["use"] == {"kind": "shop", "sells": [{"item": "apple", "price": 1}]}
      and IA.buy_list(ENT.comps_of("tavern", True)["use"]) == [] and ("휴대식", 1) in IA.buy_list(ENT.comps_of("general_store", True)["use"])
      and ENT.npc("tavern_keeper")["shop"] == "tavern")
check("① 뒤지기 표(통·궤짝·항아리)에 휴대식 — 가중치 1(낮게) · USE_LOOT 에 ration",
      "ration" in ENT.USE_LOOT and all({"item": "ration", "w": 1} in ENT.get(e)["comps"]["use"]["loot"] for e in ("barrel", "crate", "jar")))

TMP = tempfile.mkdtemp(prefix="defs_", dir=ROOT)
eroot, wroot = os.path.join(TMP, "entities"), os.path.join(TMP, "world")
shutil.copytree(ENT.ROOT, eroot)
shutil.copytree(WD.WORDS_ROOT, wroot)


def jw(path, doc):
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)


def jr(path):
    with io.open(path, encoding="utf-8") as f:
        return json.load(f)


bad = jr(os.path.join(eroot, "need", "hunger.json"))
bad["comps"]["need"]["wat"] = 1                                                  # a 모르는 칸
bad["comps"]["need"]["stages"]["hungry"]["min"] = 41                             # b min 겹침
bad["comps"]["need"]["stages"]["starving"]["effects"]["sleep"] = True            # c 모르는 효과
bad["comps"]["need"]["stages"]["hungry"]["effects"] = {"hp_drain": {"every": 0, "floor": 50}}   # d hp_drain 꼴
bad["comps"]["need"]["weights"]["보통"] = {"every": 4, "fill": 100, "mood_time": 100}            # e 보통을 적음
bad["comps"]["need"]["from_events"] = [{"event": "drank", "amount": 0}]          # f 채움 0
bad["comps"]["need"]["stages"]["hungry"]["mood"] = 0                             # l p0.5.18 단계 기분 값 0(값·이유는 짝 — 0 이면 칸을 두지 않는다)
bad["comps"]["need"]["mood"]["dislike"]["mood"] = 500                            # m p0.5.18 기분 값 범위 밖
jw(os.path.join(eroot, "need", "hunger.json"), bad)
with io.open(os.path.join(wroot, "need", "hunger.md"), encoding="utf-8") as f:
    hmd = f.read()
assert "\n좋아하는 {what:을} 먹음\n" in hmd                                       # 바꿀 자리가 주석이 아니라 값 줄인지(빨간불 거짓 통과 방지)
with io.open(os.path.join(wroot, "need", "hunger.md"), "w", encoding="utf-8", newline="\n") as f:
    f.write(hmd.replace("\n좋아하는 {what:을} 먹음\n", "\n좋아하는 {thing} 먹음\n"))   # g 모르는 자리(기분 이유)
with io.open(os.path.join(wroot, "mood.md"), encoding="utf-8") as f:
    mmd = f.read()
assert "\n## `bad`" in mmd
with io.open(os.path.join(wroot, "mood.md"), "w", encoding="utf-8", newline="\n") as f:
    f.write(mmd.replace("\n## `bad`", "\n## `worse`"))                           # n·o p0.5.18 기분 낱말 칸 빠짐·모르는 칸
eff = jr(os.path.join(eroot, "need", "hunger.json"))
r_ = jr(os.path.join(eroot, "object", "ration.json"))
r_["comps"]["satisfies"] = {"thirst": 10}                                         # h 없는 욕구
r_["comps"]["taste"] = ["초콜릿"]                                                 # i 어휘 밖 꼬리표
jw(os.path.join(eroot, "object", "ration.json"), r_)
p_ = jr(os.path.join(eroot, "object", "potion.json"))
p_["comps"]["satisfies"] = {"hunger": 5}                                          # j 먹는 type 이 아닌 것의 satisfies
jw(os.path.join(eroot, "object", "potion.json"), p_)
m_ = jr(os.path.join(eroot, "object", "meal.json"))
m_["comps"].pop("satisfies")                                                      # k 먹는 type 인데 satisfies 없음
jw(os.path.join(eroot, "object", "meal.json"), m_)
try:
    ENT.read(eroot, words_root=wroot)
    msg = ""
except ENT.EntityError as e:
    msg = str(e)
want = ("need 가 모르는 칸 ['wat']", "min 은 서로 달라야", "effects 는 {no_regen|hp_drain} 중에서", "effects.hp_drain 은",
        "need.weights 는 {낮음|높음", "need.from_events 는", "need.mood.like.why 의 자리는 {what}·{what:을|은|이|과} 뿐이다",
        "satisfies 의 'thirst' 는 단계가 있는 욕구 정의가 아니다", "taste 의 '초콜릿' 는 취향 어휘", "potion.json: type 'potion' — 먹는 type",
        "meal.json: type 'food' — 먹는 type",
        "need.stages.hungry 의 mood·why 는 짝", "need.mood.dislike 는 {time: 정수≥1(틱), mood: 0 아닌 정수",
        "prompts/world/mood.md: 칸 `bad` 가 없다", "prompts/world/mood.md: 칸 `worse` 는 기분 낱말이 아니다")
check("① 검증기 거절 15종을 한 번에 나열 — 모르는 칸·min 겹침·모르는 효과·hp_drain 꼴·보통 무게·채움 0·모르는 자리(기분 이유)·없는 욕구·어휘 밖 꼬리표·먹는 type 밖 satisfies·satisfies 없음 · "
      "p0.5.18 단계 기분 값 0·기분 값 범위 밖·기분 낱말 칸 빠짐·모르는 기분 낱말 칸",
      all(w_ in msg for w_ in want), [w_ for w_ in want if w_ not in msg] or msg[:300])
shutil.rmtree(TMP, ignore_errors=True)

# ─────────────────────────────────────────────────────────────────────────────
print("── ② 데이터만으로 새 욕구(시험용 정의 한 장 + 말 파일)")
TEST_DEF = {"id": "test_thirst", "name": "목마름", "kind": "need", "tags": ["need"],
            "comps": {"need": {"about": "@prompts", "start": 50, "decay": 2, "full_at": 90, "full_blocks": False,
                               "stages": {"full": {"min": 90, "word": "개운함", "line": "@prompts"},
                                          "normal": {"min": 30, "word": "보통"},
                                          "dry": {"min": 0, "word": "목마름", "line": "@prompts", "mood": -6, "why": "@prompts"}},   # p0.5.18 단계 기분
                               "mood": {"plain": {"time": 10, "mood": 4, "why": "@prompts"}},                                       # p0.5.18 마신 뒤 조각
                               "from_events": [{"event": "drank", "amount": 30}],
                               "tolerance": {"key": "item", "on": "mood", "steps": [100, 50]}}}}   # 내성은 자리만(엔진이 아직 읽지 않는다)
TEST_MD = ("# 목마름 · test_thirst\n\n## `need.about`\n마실 것이 필요한 정도\n\n## `need.stages.full.line`\n목이 시원하다.\n\n"
           "## `need.stages.dry.line`\n목이 탄다.\n\n## `need.stages.dry.why`\n목마름\n\n## `need.mood.plain.why`\n물을 마심\n")
IDLE_DEF = {"id": "test_idle", "name": "호기심(시험)", "kind": "need", "tags": ["need"], "comps": {"need": {"about": "@prompts"}}}
IDLE_MD = "# 호기심(시험) · test_idle\n\n## `need.about`\n새로운 것을 알고 싶은 정도\n"
TMP2 = tempfile.mkdtemp(prefix="defs2_", dir=ROOT)
eroot2, wroot2 = os.path.join(TMP2, "entities"), os.path.join(TMP2, "world")
shutil.copytree(ENT.ROOT, eroot2)
shutil.copytree(WD.WORDS_ROOT, wroot2)
for d_, md_ in ((TEST_DEF, TEST_MD), (IDLE_DEF, IDLE_MD)):
    jw(os.path.join(eroot2, "need", d_["id"] + ".json"), d_)
    with io.open(os.path.join(wroot2, "need", d_["id"] + ".md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(md_)
DEFS0 = ENT.load()
DEFS_T = ENT.read(eroot2, words_root=wroot2)          # 검증기를 통과한 정의 사전(시험 정의 둘 + 리포 정의 전부)
check("② 시험용 정의 둘(단계 있는 목마름 · 이름·뜻만 있는 호기심)이 검증기를 통과한다 · 말 파일이 합쳐진다 · 나머지 정의는 리포 그대로",
      DEFS_T["test_thirst"]["comps"]["need"]["stages"]["dry"]["line"] == "목이 탄다." and DEFS_T["test_idle"]["comps"]["need"]["about"] == "새로운 것을 알고 싶은 정도"
      and {k: v for k, v in DEFS_T.items() if not k.startswith("test_")} == DEFS0)
ENT._DEFS = DEFS_T                                     # 주입 — 코드는 하나도 안 고친다(정의 사전만 바뀐다 · needs._index 가 다시 짓는다)
try:
    check("② 엔진이 쓰는 욕구 = 단계가 있는 것만(배고픔·목마름) · 이름·뜻만 있는 것은 건너뛴다(시트 needs 칸의 열쇠로는 받는다)",
          [i for i, _ in NE.live()] == ["hunger", "test_thirst"] and [d_["id"] for d_ in NE.all_defs()] == ["hunger", "test_idle", "test_thirst"]
          and "test_idle" in (NE.sheet_fields({"needs": {"test_idle": {"level": "높음"}}}).get("needs") or {}))
    dT, botsT = town(on=True)
    aT, bT = botsT[0], botsT[1]
    check("② 새 몸에 새 욕구의 시작값(50) · 이름·뜻만 있는 욕구는 몸에 없다", aT["needs"] == {"hunger": 70, "test_thirst": 50})
    NE.tick(dT, botsT, 2)
    check("② 줄기: 2틱마다 1(목마름 49) · 배고픔은 제 박자(4틱 — 아직 70)", aT["needs"] == {"hunger": 70, "test_thirst": 49})
    aT["needs"]["test_thirst"] = 30
    NE.drain(dT)
    NE.tick(dT, botsT, 4)
    evT = [e for e in NE.drain(dT) if e.get("bot") == aT["char"]]
    check("② 단계 사건: 30 → 29 = 보통 → 목마름(need_stage · bot · char 없음) · 같은 틱 배고픔 69(보통 그대로)",
          {"type": "need", "bot": aT["char"], "result": "need_stage", "need": "test_thirst", "from": "normal", "to": "dry"} in evT
          and all("char" not in e for e in evT) and aT["needs"]["hunger"] == 69, evT)
    oT = dT.view(aT, botsT)
    wT = brains._wire(oT, NAMES, compose=True)
    check("② 단계 문장·기분(데이터만으로): '- 몸: 목이 탄다.' · '- 기분: 좋지 않다 (이유: 목마름)'(목마름 −6 · 배고픔 보통) — 숫자 없이 · 그 틱 need_mood(없음 → 좋지 않다)",
          oT.get("need_lines") == ["목이 탄다."] and oT.get("need_mood") == "좋지 않다 (이유: 목마름)"
          and "\n- 몸: 목이 탄다.\n- 기분: 좋지 않다 (이유: 목마름)\n" in wT
          and {"type": "need", "bot": aT["char"], "result": "need_mood", "from": None, "to": "bad", "sum": -6, "why": ["목마름"]} in evT,
          (oT.get("need_lines"), oT.get("need_mood"), [e for e in evT if e.get("result") == "need_mood"]))
    well = by_name(dT, "우물")
    put(aT, stand_by(dT, well, botsT))
    aT["hp"] = aT["maxhp"] - 2
    rT = act(dT, aT, botsT, {"type": "use", "target": "f%d" % well.id})
    evT = NE.drain(dT)
    fillT = next((e for e in evT if e.get("result") == "need_fill"), None)
    check("② 채우기(from_events): 우물을 마셨다(drank) → 목마름 +30(29 → 59) · need_fill{via event, src_key drank} 사건 · 단계 목마름 → 보통 · 행동 결과는 그대로(drank HP +1)",
          rT["result"] == "drank" and rT["heal"] == 1 and aT["needs"]["test_thirst"] == 59 and fillT
          and fillT["via"] == "event" and fillT["src_key"] == "drank" and fillT["before"] == 29 and fillT["after"] == 59 and fillT["bot"] == aT["char"]
          and any(e.get("result") == "need_stage" and e.get("to") == "normal" for e in evT), (rT.get("result"), evT))
    oT2 = dT.view(aT, botsT)
    check("② 기분 조각(데이터만으로): 마신 뒤 +4(10틱) — 몸 줄 없음(보통) · '기분: 좋다 (이유: 물을 마심)' · need_mood(좋지 않다 → 좋다) · 조각 = {src, size, what: 결과의 what(우물), until}",
          "need_lines" not in oT2 and oT2.get("need_mood") == "좋다 (이유: 물을 마심)"
          and aT["moods"] == [{"src": "test_thirst", "size": "plain", "what": "우물", "until": dT.turn + 10}]
          and {"type": "need", "bot": aT["char"], "result": "need_mood", "from": "bad", "to": "good", "sum": 4, "why": ["물을 마심"]} in evT,
          (oT2.get("need_mood"), aT["moods"], [e for e in evT if e.get("result") == "need_mood"]))
    NE.tick(dT, botsT, dT.turn + 10)
    evT3 = NE.drain(dT)
    check("② 10틱 뒤 조각이 걷힌다 — 기분 줄 없음(합 0) · need_mood(좋다 → 없음 · 합·이유 칸 없음)",
          NE.lines(aT) == [] and NE.mood_line(aT, dT.turn + 10) is None and aT["moods"] == []
          and {"type": "need", "bot": aT["char"], "result": "need_mood", "from": "good", "to": None} in evT3, evT3)
    NE.drain(dT)
    aT["needs"]["test_thirst"] = 95
    rT2 = act(dT, aT, botsT, {"type": "use", "target": "f%d" % well.id})
    evT2 = NE.drain(dT)
    check("② 가득 참(몸에 안 들어가는 욕구 — full_blocks false): 마시기는 막지 않는다(drank) · 더 차지 않는다(95 그대로) · need_none{why full} 사건 · 상태 문장 '목이 시원하다.'",
          rT2["result"] == "drank" and aT["needs"]["test_thirst"] == 95
          and any(e.get("result") == "need_none" and e.get("why") == "full" and e.get("need") == "test_thirst" for e in evT2)
          and dT.view(aT, botsT).get("need_lines") == ["목이 시원하다."], evT2)
    snapT = G.bot_snapshot(aT)
    check("② 스트림: 봇 스냅샷 needs 에 새 욕구 · run_meta.need_defs 에 새 욕구(단계·효과·기분 시간) — 이름·뜻만 있는 욕구는 없다",
          snapT["needs"].get("test_thirst") == 95 and "test_thirst" in NE.defs_meta() and "test_idle" not in NE.defs_meta()
          and NE.defs_meta()["test_thirst"]["stages"]["dry"] == {"min": 0, "word": "목마름", "mood": -6} and NE.defs_meta()["test_thirst"]["mood"] == {"plain": {"time": 10, "mood": 4}})
finally:
    ENT._DEFS = DEFS0
check("② 시험 정의를 걷으면 엔진도 걷는다(정의 사전이 곧 욕구 목록)", [i for i, _ in NE.live()] == ["hunger"])
CODE = ("needs.py", "dungeon_gm.py", "interactables.py", "composed_actions.py", "brains.py", "show_runner.py", "snapshot.py", "info_guard.py", "entities.py")
check("② 코드에 욕구 id 글자('hunger')가 없다 — 욕구는 정의(데이터)로만 들어온다(이 게이트가 코드 길을 숨기지 않는다)",
      not [f for f in CODE if re.search(r"['\"]hunger['\"]", src(f))], [f for f in CODE if re.search(r"['\"]hunger['\"]", src(f))])
shutil.rmtree(TMP2, ignore_errors=True)

# ─────────────────────────────────────────────────────────────────────────────
print("── ③ 배고픔 단계 경계")
check("③ 경계: 100·81 배부름 / 80·41 보통 / 40·16 배고픔 / 15·0 굶주림 · 81 부터 가득 참",
      [NE.stage_key(HUNGER, v) for v in (100, 81, 80, 41, 40, 16, 15, 0)] == ["full", "full", "normal", "normal", "hungry", "hungry", "starving", "starving"]
      and NE.is_full(HUNGER, 81) and not NE.is_full(HUNGER, 80))
dB, botsB = town(on=True)
aB = botsB[0]
rows, moods_, wires_ = [], [], []
for v in (100, 80, 40, 15):
    aB["needs"]["hunger"] = v
    oB_ = dB.view(aB, botsB)
    rows.append(oB_.get("need_lines"))
    moods_.append(oB_.get("need_mood"))
    sec_ = brains._wire(oB_, NAMES, compose=True).split("## 네 상태\n")[1].split("\n## ")[0]
    wires_.append([ln for ln in sec_.split("\n") if ln.startswith(("- 몸", "- 기분"))])
check("③ 단계 문장: 배부름·배고픔·굶주림은 제 문장 한 줄 · 보통은 줄이 없다(관측 칸도 없다)",
      rows == [[LINE["full"]], None, [LINE["hungry"]], [LINE["starving"]]], rows)
check("③ 관측 꼴 글자 그대로(p0.5.18): 100 '- 몸: 배가 부르다.'(기분 줄 없음 — 배부름 0) · 80 아무 줄도 없다 · "
      "40 '- 몸: 배가 고프다.' + '- 기분: 좋지 않다 (이유: 배고픔)' · 15 '- 몸: 몹시 배고프다. 쉬어도 기운이 돌아오지 않는다.' + '- 기분: 좋지 않다 (이유: 굶주림)'",
      wires_ == [["- 몸: 배가 부르다."], [], ["- 몸: 배가 고프다.", "- 기분: 좋지 않다 (이유: 배고픔)"],
                 ["- 몸: 몹시 배고프다. 쉬어도 기운이 돌아오지 않는다.", "- 기분: 좋지 않다 (이유: 굶주림)"]]
      and moods_ == [None, None, "좋지 않다 (이유: 배고픔)", "좋지 않다 (이유: 굶주림)"], (wires_, moods_))
dC, botsC = town(on=True)
aC = botsC[0]
st_at, md_at = {}, []
for t in range(1, 221):
    dC.turn = t
    NE.tick(dC, botsC, t)
    for e in NE.drain(dC):
        if e.get("bot") == aC["char"] and e.get("result") == "need_stage":
            st_at[e["to"]] = t
        if e.get("bot") == aC["char"] and e.get("result") == "need_mood":
            md_at.append((t, e["from"], e["to"], e.get("sum"), e.get("why")))
check("③ 판 시작 70 → t120 배고픔(40) · t220 굶주림(15) — 그 틱에 need_stage 한 줄씩(§3.4 — 400틱 한 바퀴)",
      st_at == {"hungry": 120, "starving": 220} and hun(aC) == 15, st_at)
check("③ 기분 변화 사건 need_mood: t120 없음 → 좋지 않다(−10 · 배고픔) · t220 좋지 않다 → 좋지 않다(−20 · 굶주림 — 이유가 바뀌어도 사건) · 그 밖의 틱엔 없다",
      md_at == [(120, None, "bad", -10, ["배고픔"]), (220, "bad", "bad", -20, ["굶주림"])], md_at)

# ─────────────────────────────────────────────────────────────────────────────
print("── ④ 굶주림 효과(쉬어도 기운이 돌아오지 않는다 · HP 가 천천히 줄다 절반에서 멈춘다)")
check("④ 굶주림 문장이 약속하는 것 = 엔진 효과 — '쉬어도 기운이 돌아오지 않는다'(no_regen) · 배부름 문장은 상태만('배가 부르다.' — 먹기 거절은 결과 문장이 말한다)",
      "쉬어도 기운이 돌아오지 않는다" in LINE["starving"] and LINE["full"] == "배가 부르다.")
dE, botsE = town(on=True)
aE, bE = botsE[0], botsE[1]
aE["needs"]["hunger"] = 10
aE["hp"] = aE["maxhp"] - 3
heal_res = {}
targets = {}
for f in dE.features.values():
    u_ = IA.use_of(dE, f) or {}
    if u_.get("kind") in ("sit", "drink", "warm") and u_.get("kind") not in targets:
        targets[u_["kind"]] = f
for k, f in sorted(targets.items()):
    put(aE, stand_by(dE, f, botsE) if f.type != "building" else (f.x, f.y))
    heal_res[k] = act(dE, aE, botsE, {"type": "use", "target": "f%d" % f.id})
check("④ 앉기·마시기·불 쬐기 = HP 0(상처가 있어도) · 결과에 no_regen · 문장 '— 기운이 돌아오지 않았다'",
      set(heal_res) == {"sit", "drink", "warm"} and all(r_["heal"] == 0 and r_.get("no_regen") == "hunger" and "기운이 돌아오지 않았다" in brains._last_prose(r_)
                                                      for r_ in heal_res.values()) and aE["hp"] == aE["maxhp"] - 3,
      {k: (r_.get("result"), r_.get("heal"), brains._last_prose(r_)) for k, r_ in heal_res.items()})
inn = by_name(dE, "공동 숙소")
put(aE, (inn.x, inn.y))
aE["gold"], aE["status"] = 5, {"출혈": {"n": 1, "by": "함정", "since": 0}}
r_l = act(dE, aE, botsE, {"type": "use", "target": "f%d" % inn.id})
check("④ 묵기 = HP 0 · 몸 상태는 낫는다(출혈 소거) · 값은 낸다(1골드) · 문장 '공동 숙소에 묵었다 — 기운이 돌아오지 않았다 · 나은 상태: 출혈 · 1골드를 냈다…'",
      r_l["result"] == "lodged" and r_l["heal"] == 0 and r_l.get("no_regen") == "hunger" and aE["status"] == {} and aE["gold"] == 4
      and aE["hp"] == aE["maxhp"] - 3 and brains._last_prose(r_l).startswith("공동 숙소에 묵었다 — 기운이 돌아오지 않았다 · 나은 상태: 출혈 · 1골드를 냈다"), brains._last_prose(r_l))
r_r = act(dE, aE, botsE, {"type": "rest"})
check("④ 쉬기(rest) = 눕지 않는다(order 없음 — 끝없는 휴식이 되지 않게) · 결과 no_regen · 변화 없음(no_effect) · 문장 '쉬려 했지만 — 기운이 돌아오지 않았다'",
      r_r["result"] == "no_regen" and not aE.get("order") and r_r["resolution"]["status"] == "no_effect"
      and brains._last_prose(r_r) == "쉬려 했지만 — 기운이 돌아오지 않았다", r_r)
aE["needs"]["hunger"] = 60
r_r2 = act(dE, aE, botsE, {"type": "rest"})
hp0 = aE["hp"]
r_tick = dE.step_order(aE, botsE)
aE["needs"]["hunger"] = 10
r_tick2 = dE.step_order(aE, botsE)
check("④ 쉬는 도중 굶주림에 들면 — 그 틱은 HP 가 안 차고 깬다(no_regen · order 없음) · 굶주리기 전 틱은 옛 휴식 그대로(HP +1)",
      r_r2["result"] == "resting" and r_tick.get("result") == "resting" and aE["hp"] == hp0 + 1 and r_tick2.get("result") == "no_regen" and not aE.get("order"),
      (r_r2.get("result"), r_tick.get("result"), r_tick2.get("result")))
BLEED = {"출혈": {"n": 1, "by": "함정", "since": 0}}
rest_out = {}
for label_, hp_ in (("만피", aE["maxhp"]), ("다침", aE["maxhp"] - 3)):
    aE["needs"]["hunger"], aE["hp"], aE["status"] = 10, hp_, copy.deepcopy(BLEED)
    r0_ = act(dE, aE, botsE, {"type": "rest"})
    ticks_ = [dE.step_order(aE, botsE) for _ in range(G.REST_MIN)]
    rest_out[label_] = (r0_.get("result"), [t_.get("result") for t_ in ticks_], aE["hp"] - hp_, dict(aE["status"]), ticks_[-1])
check("④ 굶주려도 몸 상태는 쉬어서 낫는다(HP 차단과 상태 회복은 따로) — 출혈이 있으면 눕는다 · 만피든 다친 몸이든 REST_MIN 틱 뒤 출혈 소거 · HP 는 그대로 · 결과 rested{healed 0, no_regen}",
      all(v_[0] == "resting" and v_[1] == ["resting"] * (G.REST_MIN - 1) + ["rested"] and v_[2] == 0 and v_[3] == {}
          and v_[4]["cleared"] == ["출혈"] and v_[4]["healed"] == 0 and v_[4].get("no_regen") == "hunger" for v_ in rest_out.values()) and not aE.get("order"),
      {k: v_[:4] for k, v_ in rest_out.items()})
rd_ = rest_out["다침"][4]
check("④ 굶주린 몸의 휴식 완료 문장 '쉬었다 — 기운이 돌아오지 않았다, 몸 상태는 나았다: 출혈' · 꼬리표 '휴식 완료 HP +0 · 기운 안 돎, 나음: 출혈'(HP 회복을 말하지 않는다)",
      brains._last_prose(rd_) == "쉬었다 — 기운이 돌아오지 않았다, 몸 상태는 나았다: 출혈"
      and G.event_tags(rd_) == [("rest_done", "휴식 완료", "HP +0 · 기운 안 돎, 나음: 출혈")], (brains._last_prose(rd_), G.event_tags(rd_)))
aE["needs"]["hunger"], aE["hp"], aE["status"] = 60, aE["maxhp"] - 3, copy.deepcopy(BLEED)
act(dE, aE, botsE, {"type": "rest"})
mid_ = [dE.step_order(aE, botsE)]
aE["needs"]["hunger"] = 10
mid_ += [dE.step_order(aE, botsE) for _ in range(G.REST_MIN - 1)]
check("④ 출혈을 안고 쉬다 굶주림에 들면 — 깨지 않고 쉬어 출혈만 낫는다(그 틱부터 HP 그대로)",
      [m_.get("result") for m_ in mid_] == ["resting"] * (G.REST_MIN - 1) + ["rested"] and aE["hp"] == aE["maxhp"] - 2 and aE["status"] == {}
      and mid_[-1]["healed"] == 1, [(m_.get("result"), m_.get("hp")) for m_ in mid_])
aE["potions"] = 1
r_p = act(dE, aE, botsE, {"type": "use", "target": "self", "item": "i1"})
check("④ 물약은 그대로 — 굶주려도 HP 가 다 찬다(효과는 쉬는 길만)", r_p["result"] == "healed" and aE["hp"] == aE["maxhp"], r_p)
aE["hp"] = aE["maxhp"] - 3
oE = dE.view(aE, botsE)
wE = brains._wire(oE, NAMES, compose=True)
oE_ok = dE.view(bE, botsE)                              # 대조군 — 굶주리지 않은 몸(같은 세계)
rest_kinds = ("sit", "drink", "warm", "lodge")
fE = [f_ for f_ in oE["sights"]["features"] if (f_.get("use") or {}).get("kind") in rest_kinds and not f_["use"].get("spent")]
fB = [f_ for f_ in oE_ok["sights"]["features"] if (f_.get("use") or {}).get("kind") in rest_kinds and not f_["use"].get("spent")]
check("④ 대상 사실 줄이 HP 를 약속하지 않는다(굶주린 몸 몫) — 앉기·마시기·불 쬐기에 회복 수치 없음 · 숙소 '묵으면 몸 상태가 낫는다'(HP 말 없음) · 대조군(굶주리지 않은 몸)은 옛 사실 그대로",
      fE and all("heal" not in f_["use"] for f_ in fE) and not re.search(r"(앉으면|마시면|불을 쬐면) HP", wE) and "HP 가 전부 돌아오고" not in wE
      and all(IA.fact_text(f_["use"]).startswith("묵으면 몸 상태가 낫는다") for f_ in fE if f_["use"]["kind"] == "lodge")
      and any("heal" in f_["use"] for f_ in fB) and all(IA.fact_text(f_["use"]).startswith("묵으면 HP 가 전부") for f_ in fB if f_["use"]["kind"] == "lodge"),
      ([f_["use"] for f_ in fE][:4], [ln for ln in wE.split("\n") if " HP " in ln][:3]))
dM, botsM = town(on=True)
dM.composed_actions = dM.auto_approach = False
dM.rest_verb = True
aM = botsM[0]
aM["hp"] = aM["maxhp"] - 3
labs_ok = [o["type"] for o in dM.view(aM, botsM)["options"]]
rest_lab_ok = next(o["label"] for o in dM.view(aM, botsM)["options"] if o["type"] == "rest")
aM["needs"]["hunger"] = 10
labs_st = [o["type"] for o in dM.view(aM, botsM)["options"]]
aM["status"] = {"출혈": {"n": 1, "by": "함정", "since": 0}}
rest_lab_st = [o["label"] for o in dM.view(aM, botsM)["options"] if o["type"] == "rest"]
check("④ 메뉴형: 다친 몸엔 '쉰다' 줄(틱마다 HP 회복) — 굶주리면 그 줄이 없다(회복을 약속하는 줄을 내지 않는다) · 굶주려도 몸 상태가 있으면 '쉰다' 줄(HP 말 없이 상태가 낫는다)",
      "rest" in labs_ok and "틱마다 HP" in rest_lab_ok and "rest" not in labs_st
      and len(rest_lab_st) == 1 and "HP" not in rest_lab_st[0] and "몸 상태(출혈·둔화·중독)가 낫는다" in rest_lab_st[0], (labs_ok, labs_st, rest_lab_st))
dD, botsD = town(on=True)
aD, bD, cD = botsD
aD["needs"]["hunger"], aD["hp"] = 5, aD["maxhp"]
bD["needs"]["hunger"], bD["hp"] = 5, 2
cD["needs"]["hunger"] = 50
cD["hp"] = cD["maxhp"]
floor_a = -(-aD["maxhp"] * 50 // 100)
drains, first_t = 0, None
dD.trail_on = True
for t in range(1, 1201):
    dD.turn = t
    NE.tick(dD, botsD, t)
    aD["needs"]["hunger"] = 5                           # 굶주림에 붙들어 둔다(줄기만 멈춘다 — 효과의 박자를 본다)
    bD["needs"]["hunger"] = 5
    cD["needs"]["hunger"] = 50                          # 보통에 붙들어 둔다(대조군)
    for e in NE.drain(dD):
        if e.get("result") == "need_drain":
            drains += 1
            if e["bot"] == aD["char"] and drains == 1:
                first_t = t
check("④ hp_drain: 60틱마다 HP −1(첫 깎임 t60) · 최대 HP 의 절반(올림 %d)에서 멈춘다 · 이미 그 아래(HP 2)인 몸은 그대로 · 굶주리지 않은 몸은 안 깎인다 · 산다" % floor_a,
      first_t == 60 and aD["hp"] == floor_a and bD["hp"] == 2 and cD["hp"] == cD["maxhp"] and aD["alive"] and drains == aD["maxhp"] - floor_a,
      (first_t, aD["hp"], floor_a, bD["hp"], cD["hp"], drains))
tr_ = [e for e in (aD.get("trail") or []) if e.get("result") == "need_drain"]
tg_ = G.event_tags(tr_[0]) if tr_ else []
check("④ 깎인 틱은 그 몸의 궤적에 한 칸 — 꼬리표 '[허기] 기운이 빠졌다 (HP n/m)'(새 키 없음 · 숫자는 HP 뿐)",
      tr_ and tg_ and tg_[0][0] in G.EVENT_KINDS and tg_[0][1] == "허기" and tg_[0][2].startswith(NE.DRAIN_LINE), tg_)

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑤ 먹기 끝까지")
dF, botsF = town(on=True)
aF, bF, cF = botsF
aF["needs"]["hunger"], aF["rations"] = 40, 2
rF = act(dF, aF, botsF, {"type": "use", "target": "self", "item": "i9"})
evF = NE.drain(dF)
check("⑤ 휴대식 use(i9 → 나) = need_fill{via eat} · 배고픔 40 → 90 · 휴대식 1 · 성공 · 문장 '휴대식을 먹었다 (남은 휴대식 1개)' · 단계 사건 배고픔 → 배부름",
      rF["result"] == "need_fill" and rF["via"] == "eat" and rF["before"] == 40 and rF["after"] == 90 and hun(aF) == 90 and aF["rations"] == 1
      and rF["resolution"]["status"] == "success" and brains._last_prose(rF) == "휴대식을 먹었다 (남은 휴대식 1개)"
      and any(e.get("result") == "need_stage" and e.get("to") == "full" for e in evF), (rF, brains._last_prose(rF)))
oF = dF.view(aF, botsF)
wF = brains._wire(oF, NAMES, compose=True)
check("⑤ 먹은 뒤(배고픔 40 → 90): '- 몸: 배가 부르다.' · '- 기분: 좋다 (이유: 배불리 먹음)'(취향 없는 몸 = 기본 +8 · 배부름 0) · 조각 {src, size plain, what 휴대식, until} · "
      "need_mood(좋지 않다 → 좋다 — 행동이 낳은 사건)",
      oF.get("need_lines") == [LINE["full"]] and oF.get("need_mood") == "좋다 (이유: 배불리 먹음)"
      and "\n- 몸: 배가 부르다.\n- 기분: 좋다 (이유: 배불리 먹음)\n" in wF
      and aF["moods"] == [{"src": "hunger", "size": "plain", "what": "휴대식", "until": dF.turn + 60}]
      and {"type": "need", "bot": aF["char"], "result": "need_mood", "from": "bad", "to": "good", "sum": 8, "why": ["배불리 먹음"]} in evF,
      (oF.get("need_lines"), oF.get("need_mood"), aF["moods"], [e for e in evF if e.get("result") == "need_mood"]))
rF2 = act(dF, aF, botsF, {"type": "use", "target": "i9"})
check("⑤ 배가 불렀는데 또 먹으면(대상 i9 꼴도) = need_none{why full} · 휴대식 그대로 1 · 배고픔 그대로 · 실패 · 문장 '휴대식을 먹지 못했다 — 배가 부르다'(p0.5.18 간결) · "
      "꼬리표 '휴대식 — 배가 부르다' · 기분 사건 없음",
      rF2.get("result") == "need_none" and rF2.get("why") == "full" and rF2.get("via") == "eat" and aF["rations"] == 1 and hun(aF) == 90 and (rF2.get("resolution") or {}).get("status") == "failed"
      and brains._last_prose(rF2) == "휴대식을 먹지 못했다 — 배가 부르다" and G.event_tags(rF2) == [("misc", "헛손질", "휴대식 — 배가 부르다")]
      and not [e for e in NE.drain(dF) if e.get("result") == "need_mood"], (rF2, brains._last_prose(rF2), G.event_tags(rF2)))
put(bF, stand_by(dF, by_name(dF, "우물"), botsF))
put(aF, beside(dF, bF, botsF))
rF3 = act(dF, aF, botsF, {"type": "use", "target": "b%s" % bF["char"], "item": "i9"})
check("⑤ 휴대식을 남에게 쓰면 변화 없음(no_item_effect — 넘기려면 give) · 그대로", rF3["result"] == "no_effect" and aF["rations"] == 1, rF3)
rF4 = act(dF, aF, botsF, {"type": "give", "target": "b%s" % bF["char"], "item": "i9"})
wit = [x for x in (cF.get("witnessed") or []) if x.get("kind") == "ally_give"]
check("⑤ 건네기 = 하나씩(물약 문법) · 받은 쪽 휴대식 1 · 받은 기록 · 먹이기가 아니다(받은 쪽 배고픔 그대로)",
      rF4["result"] == "given" and rF4["what"] == "휴대식" and aF["rations"] == 0 and bF["rations"] == 1 and hun(bF) == 70
      and (bF.get("last") or {}).get("type") == "received", rF4)
bF["needs"]["hunger"] = 20
for o in botsF:
    o["witnessed"] = []
put(cF, beside(dF, bF, botsF))
rF5 = act(dF, bF, botsF, {"type": "use", "target": "self", "item": "i9"})
seenF = [x for x in (aF.get("witnessed") or []) + (cF.get("witnessed") or []) if x.get("kind") == "ally_use" and x.get("char") == bF["char"]]
check("⑤ 받은 사람이 먹는다 — 곁의 사람은 '휴대식 … 먹었다'만 본다(배가 얼마나 찼는지·기분은 없다)",
      rF5["result"] == "need_fill" and hun(bF) == 70 and seenF and all(set(x) <= {"kind", "char", "what", "result", "name", "id"} for x in seenF)
      and seenF[-1].get("what") == "휴대식" and seenF[-1].get("result") == "먹었다", seenF)
dG, botsG = town(on=True)
dG.composed_actions = dG.auto_approach = False
aG = botsG[0]
aG["rations"], aG["needs"]["hunger"] = 1, 30
optsG = [o for o in dG.view(aG, botsG)["options"] if o.get("item") == "ration"]
rG = dG.act(aG, {"type": "drink", "item": "ration"}, botsG)
check("⑤ 메뉴형: '휴대식을 먹는다' 줄(drink · item ration) · 그 줄로 먹는다(need_fill · 휴대식 0)",
      optsG and optsG[0]["label"].startswith("휴대식을 먹는다") and rG["result"] == "need_fill" and aG["rations"] == 0 and hun(aG) == 80, (optsG, rG))
# 가게 — 주점 식사(사는 순간 먹는다) · 햇사과 · 휴대식 사기·팔기
dH, botsH = town(on=True)
aH, bH, cH = botsH
TAV, GS, STALL = by_name(dH, "주점"), by_name(dH, "잡화점"), by_name(dH, "채소 좌판")
gm, gr, ga = gid_of(dH, "식사"), gid_of(dH, "휴대식"), gid_of(dH, "햇사과")
put(aH, stand_by(dH, TAV, botsH))
aH["gold"], aH["needs"]["hunger"] = 5, 40
oH = dH.view(aH, botsH)
wH = brains._wire(oH, NAMES, compose=True)
check("⑤ 주점 곁: 상품 식사(%s) — 대상 줄에 취향 꼬리표 '식사 — 고기·따뜻한 것' · 값 3골드 · 설명(물건 설명 + 규칙 '사는 순간 그 자리에서 먹는다')" % gm,
      ("- [%s] 식사 — 고기·따뜻한 것 (item, good) · 값 3골드 (주점)" % gm) in wH and ENT.item_rule("food") in wH and ENT.get("meal")["comps"]["item"]["desc"] in wH,
      [ln for ln in wH.split("\n") if gm in ln])
for o in botsH:
    o["witnessed"] = []
put(bH, beside(dH, aH, botsH))
rH = act(dH, aH, botsH, {"type": "use", "target": gm})
seenH = [x for x in (bH.get("witnessed") or []) if x.get("kind") == "ally_use" and x.get("char") == aH["char"]]
check("⑤ 주점 식사 사기 = 그 자리에서 먹는다 — need_fill{via buy} · 골드 2 · 배고픔 40 → 100 · 문장 '주점에서 식사를 사 먹었다 — 3골드를 냈다(남은 골드 2)'(p0.5.18 간결) · 목격 '식사를 사 먹었다'",
      rH["result"] == "need_fill" and rH["via"] == "buy" and aH["gold"] == 2 and hun(aH) == 100 and rH["price"] == 3 and rH["gold"] == 2
      and brains._last_prose(rH) == "주점에서 식사를 사 먹었다 — 3골드를 냈다(남은 골드 2)" and seenH and seenH[-1].get("result") == "식사를 사 먹었다",
      (rH, brains._last_prose(rH), seenH))
aH["gold"] = 10
rH2 = act(dH, aH, botsH, {"type": "use", "target": gm})
check("⑤ 배가 부르면 사지 않는다 — need_none{why full, via buy} · 골드 그대로 10 · 실패 · 문장 '주점에서 식사를 사지 않았다 — 배가 부르다'(p0.5.18 간결)",
      rH2.get("result") == "need_none" and rH2.get("via") == "buy" and aH["gold"] == 10 and (rH2.get("resolution") or {}).get("status") == "failed"
      and brains._last_prose(rH2) == "주점에서 식사를 사지 않았다 — 배가 부르다", (rH2, brains._last_prose(rH2)))
aH["gold"], aH["needs"]["hunger"] = 2, 30
rH3 = act(dH, aH, botsH, {"type": "use", "target": gm})
check("⑤ 배고픈데 골드가 모자라면 too_poor(값 3 · 지닌 2) — 배고픔·골드 그대로",
      rH3["result"] == "too_poor" and aH["gold"] == 2 and hun(aH) == 30, rH3)
put(aH, stand_by(dH, STALL, botsH))
aH["gold"] = 1
rH4 = act(dH, aH, botsH, {"type": "use", "target": ga})
check("⑤ 마지막 한 닢으로 햇사과(1) — 배고픔 30 → 50 · 골드 0", rH4["result"] == "need_fill" and hun(aH) == 50 and aH["gold"] == 0, rH4)
put(aH, stand_by(dH, GS, botsH))
aH["gold"], aH["rations"], aH["needs"]["hunger"] = 5, 0, 90
rH5 = act(dH, aH, botsH, {"type": "use", "target": gr})
check("⑤ 잡화점 휴대식 사기 = 소지 +1(먹지 않는다 — 배가 불러도 산다) · 골드 3 · 문장 '잡화점에서 휴대식을 샀다 — 2골드를 냈다(남은 골드 3)'",
      rH5["result"] == "bought" and aH["rations"] == 1 and aH["gold"] == 3 and hun(aH) == 90
      and brains._last_prose(rH5).startswith("잡화점에서 휴대식을 샀다 — 2골드를 냈다(남은 골드 3)"), (rH5, brains._last_prose(rH5)))
put(aH, (GS.x, GS.y))
rH6 = act(dH, aH, botsH, {"type": "use", "target": "f%d" % GS.id, "item": "i9"})
check("⑤ 휴대식 팔기 = 잡화점이 1(절반)에 되산다 · 소지 0", rH6["result"] == "sold" and rH6["got"] == 1 and aH["rations"] == 0 and aH["gold"] == 4, rH6)
# 뒤지기 — 세계 시드·자리의 해시로 휴대식이 나오는 통
dR, stR = G.Dungeon.from_ascii(["#########", "#1.....>#", "#########"], seed=3)
dR.composed_actions = dR.objtags = True
found = None
for seed in range(1, 400):
    dR.master_seed = seed
    fid = dR.place_def("barrel", 2, 1)
    if IA._draw(dR, dR.features[fid], ENT.get("barrel")["comps"]["use"]["loot"]) == "ration":
        found = fid
        break
    del dR.features[fid]
bR = G.spawn(dR, "1", [], sheet=G.HEROES["1"])
put(bR, stR["1"])
rR = act(dR, bR, [bR], {"type": "use", "target": "f%d" % found}) if found else {}
check("⑤ 던전 통을 뒤져 휴대식 — 소지 +1 · 문장 '통을 뒤졌다 — 휴대식 하나가 나왔다(소지 휴대식 1개)' · 오브젝트 태그 '휴대식 나옴'",
      found and rR.get("got") == "ration" and bR["rations"] == 1 and brains._last_prose(rR) == "통을 뒤졌다 — 휴대식 하나가 나왔다(소지 휴대식 1개)"
      and (bR.get("obj_tags") or {}).get(found, {}).get("note") == "휴대식 나옴", (found, rR))
# 무게·취향 — 시트 칸
sheet_hi = dict(SHEETS["1"], needs={"hunger": {"level": "높음", "why": "먹는 걸 좋아한다", "src": "model"}}, taste={"likes": ["고기"], "dislikes": ["과일"]})
sheet_lo = dict(SHEETS["2"], needs={"hunger": {"level": "낮음"}})
dW, _ = town(on=True)
bw_hi = G.spawn(dW, "1", [], sheet=sheet_hi)
bw_lo = G.spawn(dW, "2", [bw_hi], sheet=sheet_lo)
bw_mid = G.spawn(dW, "3", [bw_hi, bw_lo], sheet=dict(SHEETS["3"]))
for t in range(1, 13):
    NE.tick(dW, [bw_hi, bw_lo, bw_mid], t)
check("⑤ 무게 — 줄기: 높음 3틱마다(12틱에 −4) · 보통 4틱(−3) · 낮음 6틱(−2) · 몸의 need_w 는 보통이 아닐 때만",
      (hun(bw_hi), hun(bw_mid), hun(bw_lo)) == (66, 67, 68) and bw_hi.get("need_w") == {"hunger": "높음"} and "need_w" not in bw_mid,
      (hun(bw_hi), hun(bw_mid), hun(bw_lo)))
for b_ in (bw_hi, bw_lo, bw_mid):
    b_["needs"]["hunger"], b_["rations"], b_["moods"] = 20, 1, []
r_hi = dW._eat_ration(bw_hi, [bw_hi])
r_lo = dW._eat_ration(bw_lo, [bw_lo])
r_mid = dW._eat_ration(bw_mid, [bw_mid])
check("⑤ 무게 — 채움: 휴대식 +50 이 높음 +35(70%) · 보통 +50 · 낮음 +75(150%) · 기분 시간: 높음 90틱(150%) · 보통 60 · 낮음 30(50%)",
      (r_hi["after"], r_mid["after"], r_lo["after"]) == (55, 70, 95)
      and [b_["moods"][0]["until"] - dW.turn for b_ in (bw_hi, bw_mid, bw_lo)] == [90, 60, 30],
      ((r_hi["after"], r_mid["after"], r_lo["after"]), [b_["moods"][0]["until"] - dW.turn for b_ in (bw_hi, bw_mid, bw_lo)]))
mood_lines = {}
for food_, e_ in (("meal", "like"), ("apple", "dislike"), ("ration", "plain")):
    bw_hi["needs"]["hunger"], bw_hi["moods"] = 10, []
    rr_ = NE.eat(dW, bw_hi, ENT.get(food_), dW.turn)
    mood_lines[food_] = (rr_["mood"], hun(bw_hi), NE.mood_line(bw_hi, dW.turn), NE.prose(rr_), G.event_tags(rr_))
check("⑤ 취향(§3.6 — 싫어함을 먼저 본다 · 무게 높음 70%): 좋아함(고기) 식사 10→59 '좋다 (이유: 좋아하는 식사를 먹음)' · "
      "싫어함(과일) 햇사과 10→24 '좋지 않다 (이유: 배고픔, 입에 맞지 않는 음식)' + 결과 '햇사과를 먹었다 — 입에 맞지 않았다' · 맞는 게 없는 휴대식 10→45 '좋다 (이유: 배불리 먹음)' · 배는 취향과 무관하게 찬다",
      mood_lines == {"meal": ("like", 59, "좋다 (이유: 좋아하는 식사를 먹음)", "식사를 먹었다", [("use", "먹음", "식사")]),
                     "apple": ("dislike", 24, "좋지 않다 (이유: 배고픔, 입에 맞지 않는 음식)", "햇사과를 먹었다 — 입에 맞지 않았다", [("use", "먹음", "햇사과 — 입에 맞지 않았다")]),
                     "ration": ("plain", 45, "좋다 (이유: 배불리 먹음)", "휴대식을 먹었다", [("use", "먹음", "휴대식")])}, mood_lines)
both_ = G.spawn(dW, "1", [], sheet=dict(SHEETS["1"], taste={"likes": ["고기"], "dislikes": ["따뜻한 것"]}))
both_["needs"]["hunger"] = 10
rb_ = NE.eat(dW, both_, ENT.get("meal"), dW.turn)
check("⑤ 취향 — 한 음식이 좋아함(고기)·싫어함(따뜻한 것)에 다 맞으면 싫어함이 이긴다(§3.6 '좋아함보다 먼저 본다') — 10→80 보통 · '좋지 않다 (이유: 입에 맞지 않는 음식)'",
      rb_["mood"] == "dislike" and both_["moods"] == [{"src": "hunger", "size": "dislike", "what": "식사", "until": dW.turn + 60}]
      and NE.mood_line(both_, dW.turn) == "좋지 않다 (이유: 입에 맞지 않는 음식)", (rb_, both_.get("moods")))
put(aH, stand_by(dH, STALL, botsH))
aH.update(gold=1, taste={"likes": [], "dislikes": ["과일"]}, moods=[])
aH["needs"]["hunger"] = 30
rH7 = act(dH, aH, botsH, {"type": "use", "target": ga})
check("⑤ 싫어하는 음식을 사 먹으면 결과 문장 '채소 좌판에서 햇사과를 사 먹었다 — 입에 맞지 않았다 · 1골드를 냈다(남은 골드 0)' · 꼬리표에도 '· 입에 맞지 않았다'",
      rH7["result"] == "need_fill" and rH7.get("mood") == "dislike"
      and brains._last_prose(aH["last"]) == "채소 좌판에서 햇사과를 사 먹었다 — 입에 맞지 않았다 · 1골드를 냈다(남은 골드 0)"
      and G.event_tags(rH7) == [("use", "사 먹음", "햇사과 ← 채소 좌판 1골드 (남은 0) · 입에 맞지 않았다")], (rH7, brains._last_prose(aH["last"]), G.event_tags(rH7)))
sf_ = NE.sheet_fields({"needs": {"hunger": {"level": "높음", "why": "가" * 60, "src": "model"}, "nope": {"level": "높음"}, "test_x": {"level": "엄청"}},
                       "taste": {"likes": ["고기", "단것", "빵", "초콜릿"], "dislikes": ["고기", "생선", "채소"]}})
check("⑤ 시트 칸 거르기(판을 막지 않는다): 모르는 욕구·등급이 아닌 값은 그 칸만 버린다 · why 40자 · 좋아함 2 · 싫어함 1(겹치면 싫어함에서 뺀다) · 어휘 밖 꼬리표 버림",
      sf_ == {"needs": {"hunger": {"level": "높음", "why": "가" * 40, "src": "model"}}, "taste": {"likes": ["고기", "단것"], "dislikes": ["생선"]}}, sf_)
pf = os.path.join(ROOT, "party_needs.json")
jw(pf, {"1": dict(SHEETS["1"], needs={"hunger": {"level": "낮음"}}, taste={"likes": ["빵"], "dislikes": []}), "2": dict(SHEETS["2"])})
with contextlib.redirect_stderr(io.StringIO()) as err_:
    lp = R.load_party(pf)
check("⑤ load_party 가 needs·taste 칸을 받는다(폴백 없음 · 시트에 그대로) · 칸이 없는 시트는 칸도 없다",
      not err_.getvalue() and lp["1"].get("needs") == {"hunger": {"level": "낮음"}} and lp["1"].get("taste") == {"likes": ["빵"], "dislikes": []}
      and "needs" not in lp["2"] and "taste" not in lp["2"], (err_.getvalue()[:200], lp.get("1")))
# 두 욕구 동시(시험용 목마름 −6 · 마신 뒤 +4) — 몸 줄 상한 · 기분 합산 · 이유 2개 · 문턱 · 동점
PLAIN_H = {"src": "hunger", "size": "plain", "what": "휴대식", "until": 999}       # 먹은 뒤 기본 조각 +8
DISLIKE_H = {"src": "hunger", "size": "dislike", "what": "휴대식", "until": 999}   # 싫어한 음식 −5
PLAIN_T = {"src": "test_thirst", "size": "plain", "until": 999}                  # 마신 뒤 +4


def body_mood(d_, b_, bots_, h_, t_, moods_):
    b_["needs"]["hunger"], b_["needs"]["test_thirst"], b_["moods"] = h_, t_, [dict(m) for m in moods_]
    o_ = d_.view(b_, bots_)
    return o_.get("need_lines"), o_.get("need_mood")


ENT._DEFS = DEFS_T
try:
    dL, botsL = town(on=True)
    aL = botsL[0]
    lnL = body_mood(dL, aL, botsL, 12, 5, [PLAIN_H])
    lnL2 = body_mood(dL, aL, botsL, 5, 20, [PLAIN_H])
    lnL3 = body_mood(dL, aL, botsL, 30, 50, [PLAIN_H])
    lnL4 = body_mood(dL, aL, botsL, 10, 5, [DISLIKE_H])
    lnL5 = body_mood(dL, aL, botsL, 60, 5, [PLAIN_H])
    lnL6 = body_mood(dL, aL, botsL, 60, 5, [PLAIN_H, PLAIN_T])
    wL6 = brains._wire(dL.view(aL, botsL), NAMES, compose=True)
    combos_ = []
    for h_ in (100, 60, 30, 5):
        for t_ in (95, 50, 5):
            for md_ in ([], [PLAIN_H], [DISLIKE_H], [PLAIN_H, PLAIN_T]):
                ln_, nm_ = body_mood(dL, aL, botsL, h_, t_, md_)
                s_ = sum(m for m, _w in NE._parts(aL, dL.turn))
                why_ = (NE.mood_of(aL, dL.turn) or {}).get("why") or []
                combos_.append((len(NE.sentences(" ".join(ln_ or []))), (nm_ is None) == (abs(s_) < NE.MOOD_EDGE), len(why_)))
    body_mood(dL, aL, botsL, 60, 60, [dict(PLAIN_H, until=dL.turn + 5)])
    cut_ = (NE.mood_line(aL, dL.turn + 4), NE.mood_line(aL, dL.turn + 5), (NE.mood_of(aL) or {}).get("key"))   # 틱 머리가 걷기 전에도 관측은 until 에서 자른다
    TIE = copy.deepcopy(DEFS_T)
    TIE["test_thirst"]["comps"]["need"]["stages"]["dry"]["mood"] = -10       # 목마름도 −10 — 배고픔과 동점
    ENT._DEFS = TIE
    tie1 = body_mood(dL, aL, botsL, 30, 5, [])                               # 목마름 5 < 배고픔 30 — 낮은 충족도 먼저
    tie2 = body_mood(dL, aL, botsL, 20, 25, [])                              # 배고픔 20 < 목마름 25
    tie3 = body_mood(dL, aL, botsL, 20, 20, [])                              # 같은 충족도 — 욕구 id 순(hunger < test_thirst)
    SAME = copy.deepcopy(DEFS_T)
    SAME["test_thirst"]["comps"]["need"]["stages"]["dry"]["why"] = "배고픔"  # 두 조각이 같은 이유 낱말
    ENT._DEFS = SAME
    same1 = body_mood(dL, aL, botsL, 30, 5, [DISLIKE_H])                     # −10(배고픔) −6(배고픔) −5(입에 맞지 않는 음식)
finally:
    ENT._DEFS = DEFS0
st1_ = NE.sentences(LINE["starving"])
check("⑤ '몸:' 줄 상한 = 문장 2개(§10-20 — 문장 수): 굶주림(두 문장)이면 그것만으로 찬다(목마름은 밀린다) · 목마름이 더 낮으면 '목이 탄다.' + 굶주림의 앞 문장 · "
      "기분 조각은 몸 줄에 없다 · 욕구 둘 × 조각 4가지 48경우 모두 2문장 이하",
      len(st1_) == 2 and lnL[0] == ["목이 탄다.", st1_[0]] and lnL2[0] == [LINE["starving"]] and lnL3[0] == [LINE["hungry"]]
      and max(c_[0] for c_ in combos_) == 2 and len(combos_) == 48, (lnL, lnL2, lnL3, combos_))
check("⑤ 기분 합산(두 욕구): 굶주림 −20 + 목마름 −6 + 기본 +8 = −18 '좋지 않다 (이유: 굶주림, 목마름)'(같은 쪽만 · 큰 것부터) · "
      "배고픔 −10 + 기본 +8 = −2 → 문턱(3) 아래 기분 줄 없음 · 굶주림 −20·목마름 −6·싫어함 −5 셋이어도 이유 2개 '굶주림, 목마름'",
      lnL[1] == "좋지 않다 (이유: 굶주림, 목마름)" and lnL2[1] == "좋지 않다 (이유: 굶주림, 목마름)" and lnL3[1] is None
      and lnL4[1] == "좋지 않다 (이유: 굶주림, 목마름)", (lnL, lnL2, lnL3, lnL4))
check("⑤ 반대쪽 조각은 이유가 아니다: 목마름 −6 + 기본 +8 = +2 → 줄 없음 · 여기에 마신 뒤 +4 = +6 '좋다 (이유: 배불리 먹음, 물을 마심)' — 프롬프트 '- 몸: 목이 탄다.' 다음 줄 '- 기분: 좋다 (이유: 배불리 먹음, 물을 마심)' · "
      "48경우 모두 '줄 없음 ⇔ |합| < 문턱' · 이유 ≤ 2",
      lnL5 == (["목이 탄다."], None) and lnL6 == (["목이 탄다."], "좋다 (이유: 배불리 먹음, 물을 마심)")
      and "\n- 몸: 목이 탄다.\n- 기분: 좋다 (이유: 배불리 먹음, 물을 마심)\n" in wL6
      and all(c_[1] for c_ in combos_) and max(c_[2] for c_ in combos_) == 2, (lnL5, lnL6, [c_ for c_ in combos_ if not c_[1]]))
check("⑤ 동점(배고픔 −10 = 목마름 −10): 낮은 충족도 먼저 — 목마름 5·배고픔 30 '목마름, 배고픔' · 배고픔 20·목마름 25 '배고픔, 목마름' · 같은 충족도 20 은 욕구 id 순 '배고픔, 목마름'",
      tie1[1] == "좋지 않다 (이유: 목마름, 배고픔)" and tie2[1] == "좋지 않다 (이유: 배고픔, 목마름)" and tie3[1] == "좋지 않다 (이유: 배고픔, 목마름)",
      (tie1, tie2, tie3))
check("⑤ 같은 이유 낱말은 한 번('배고픔, 입에 맞지 않는 음식' — '배고픔, 배고픔'이 아니다) · 조각은 until 틱부터 관측에 없다(틱 머리가 걷기 전에도 — t+4 '좋다 (이유: 배불리 먹음)' · t+5 없음 · "
      "관전 스냅샷은 몸의 목록 그대로)",
      same1[1] == "좋지 않다 (이유: 배고픔, 입에 맞지 않는 음식)" and cut_ == ("좋다 (이유: 배불리 먹음)", None, "good"), (same1, cut_))

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑥ 저장·이어가기")
rsrc = src("show_runner.py")
carry_src = rsrc.split("def _carry(")[1].split("\n    def ")[0]
wake_src = rsrc.split("def _wake(")[1].split("\n    def ")[0]
check("⑥ 층 이월(_carry): 휴대식·충족도·기분 조각이 그 몸을 따라간다 · 부활(_wake): 판 시작과 같은 값(G.NE.reset — _carry 뒤)",
      'n["rations"] = b.get("rations", 0)' in carry_src and "G.NE.carry(b, n)" in carry_src
      and "G.NE.reset(n)" in wake_src and wake_src.index("_carry(") < wake_src.index("G.NE.reset(n)"))
o_ = {"needs": {"hunger": 33}, "moods": [{"src": "hunger", "size": "plain", "what": "x", "until": 99}]}
n_ = G.spawn(dB, "1", [], sheet=dict(SHEETS["1"]))
NE.carry(o_, n_)
n2_ = dict(n_)
NE.reset(n2_)
check("⑥ carry = 충족도·기분 조각 사본(같은 객체 아님) · reset = 시작값(70)·기분 없음",
      n_["needs"] == {"hunger": 33} and n_["needs"] is not o_["needs"] and n_["moods"] == o_["moods"] and n_["moods"][0] is not o_["moods"][0]
      and n2_["needs"] == {"hunger": 70} and n2_["moods"] == [])
dS, botsS = town(on=True)
TK, TV, ST = by_name(dS, "주점 주인"), by_name(dS, "주점"), by_name(dS, "채소 좌판")
dS.npc_lines[TK.name] = "안은 아직 준비 중이야. 바깥 탁자는 비어 있으니 앉았다 가도 돼."          # 옛 피클에 얼어 있던 말
dS.npc_lines_again[TK.name] = "아까 왔잖아. 안은 아직이라니까 — 바깥 탁자는 그대로 있어."
dS.npc_defs[TK.name] = {k: v for k, v in dS.npc_defs[TK.name].items() if k != "shop"}
dS.place_story[ST.id] = {"trait": "채소와 과일을 늘어놓은 좌판. 구경만 된다(사고팔기는 아직 없다)", "history": "옛 이야기"}
for b_ in botsS:
    for k in ("needs", "moods", "rations"):
        b_.pop(k)
snap8 = {"version": 2, "state_version": 8, "d": dS, "bots": botsS, "sheets": SHEETS}
snap9 = S.upgrade(pickle.loads(pickle.dumps(snap8)))   # 이 프로세스가 방금 만든 바이트만 되읽는다(피클 왕복 = 이어가기와 같은 길)
d9 = snap9["d"]
check("⑥ 이관 8→9: 판 번호 9 이상(p0.5.17: 판 10 — 소문 거둠) · 옛 몸마다 배고픔 시작값 70 · 빈 기분 · 휴대식 0",
      S.STATE_VERSION >= 9 and 8 in S.MIGRATIONS and snap9["state_version"] == S.STATE_VERSION
      and all(b_.get("needs") == {"hunger": 70} and b_.get("moods") == [] and b_.get("rations") == 0 for b_ in snap9["bots"]))
check("⑥ 이관 8→9: 피클에 얼어 있던 주점 주인의 '안은 아직 준비 중'·맡은 가게 없음 · 채소 좌판의 '구경만 된다'가 지금 정의로",
      d9.npc_lines[TK.name] == ENT.npc("tavern_keeper", life=True)["line"] and d9.npc_lines_again[TK.name] == ENT.npc("tavern_keeper", life=True)["line_again"]
      and d9.npc_defs[TK.name].get("shop") == "tavern" and d9.place_story[ST.id]["trait"] == ENT.get("produce_stall")["comps"]["story"]["trait"]
      and "준비 중" not in d9.npc_lines[TK.name] and "구경만" not in d9.place_story[ST.id]["trait"])
again = S.upgrade(copy.deepcopy({**snap9, "state_version": 8}))
check("⑥ 이관은 제자리·한 번 — 이미 칸이 있는 몸은 그대로(다시 올려도 같다)",
      [b_.get("needs") for b_ in again["bots"]] == [b_.get("needs") for b_ in snap9["bots"]] and all(b_.get("needs") for b_ in again["bots"]))
dS10, botsS10 = town(on=True)
OLD_PIECE = {"src": "hunger", "size": "like", "line": "좋아하는 식사를 먹어 기분이 아주 좋다.", "until": 300}   # 0.5.16~0.5.17 꼴(문장)
NEW_PIECE = {"src": "hunger", "size": "plain", "what": "휴대식", "until": 300}
botsS10[0]["needs"]["hunger"], botsS10[0]["moods"] = 33, [dict(OLD_PIECE)]
botsS10[1]["moods"] = [dict(NEW_PIECE)]
snap10 = {"version": 2, "state_version": 10, "d": dS10, "bots": botsS10, "sheets": SHEETS,
          "waiting": {"3": {**copy.deepcopy(botsS10[2]), "moods": [dict(OLD_PIECE), dict(NEW_PIECE)]}}}
up10 = S.upgrade(pickle.loads(pickle.dumps(snap10)))   # 이 프로세스가 방금 만든 바이트만 되읽는다
w10 = up10["waiting"]["3"]
check("⑥ 이관 10→11(p0.5.18): 판 11 이상 · 옛 꼴 기분 조각(문장 line)은 걷는다 · 새 꼴 조각·충족도는 그대로 · 부활 대기 몸도 · 다시 올려도 같다",
      S.STATE_VERSION >= 11 and S.MIGRATIONS[10] is S._m10_moods and up10["state_version"] == S.STATE_VERSION
      and up10["bots"][0]["moods"] == [] and up10["bots"][0]["needs"] == {"hunger": 33} and up10["bots"][1]["moods"] == [NEW_PIECE]
      and w10["moods"] == [NEW_PIECE] and S.upgrade(copy.deepcopy({**up10, "state_version": 10}))["bots"] == up10["bots"],
      ([b_.get("moods") for b_ in up10["bots"]], w10.get("moods")))
aP = botsF[0]
aP["needs"]["hunger"], aP["moods"] = 30, [{"src": "hunger", "size": "like", "what": "식사", "until": dF.turn + 40}]
oP0 = dF.view(aP, botsF)
before_p = (oP0.get("need_lines"), oP0.get("need_mood"))
dP, botsP = pickle.loads(pickle.dumps((dF, botsF)))   # 이 프로세스가 방금 만든 바이트만 되읽는다(이어가기 스냅샷과 같은 길 — 밖에서 온 데이터가 아니다)
oP1 = dP.view(botsP[0], botsP)
check("⑥ 피클 왕복 뒤 같은 '몸:'·'기분:'(배고픔 −10 + 좋아함 +15 = '좋다 (이유: 좋아하는 식사를 먹음)') · 세계의 욕구 사건 버퍼(need_log)는 옛 피클에 없어도 된다(getattr)",
      (oP1.get("need_lines"), oP1.get("need_mood")) == before_p == ([LINE["hungry"]], "좋다 (이유: 좋아하는 식사를 먹음)")
      and NE.drain(type("OldWorld", (), {})()) == [], (before_p, oP1.get("need_mood")))
aP2 = botsP[0]
aP2["rations"] = 1
if hasattr(dP, "need_log"):
    del dP.need_log                                    # 옛 피클(이 칸이 생기기 전)에서 이어간 세계 — 처음 쓸 때 만든다
NE.drain(dP)
rP = act(dP, aP2, botsP, {"type": "use", "target": "self", "item": "i9"})
evP = NE.drain(dP)
check("⑥ 이어간 세계(피클 왕복 · 사건 버퍼 없음)에서 먹기 — need_fill 30 → 80 · 휴대식 0 · 단계 사건(배고픔 → 보통)·기분 사건(좋다 → 좋다, 이유가 '배불리 먹음'으로)이 버퍼에 생긴다 · "
      "새 기분 조각이 옛 것을 덮는다",
      rP["result"] == "need_fill" and rP["before"] == 30 and rP["after"] == 80 and aP2["rations"] == 0
      and [(e["result"], e["bot"], e["to"]) for e in evP] == [("need_stage", aP2["char"], "normal"), ("need_mood", aP2["char"], "good")]
      and evP[1]["why"] == ["배불리 먹음"] and evP[1]["from"] == "good"
      and aP2["moods"] == [{"src": "hunger", "size": "plain", "what": "휴대식", "until": dP.turn + 60}], (rP, evP, aP2.get("moods")))

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑦ 남에게 안 보임")
dV, botsV = town(on=True)
aV, bV, cV = botsV
aV["needs"]["hunger"] = 30
put(bV, stand_by(dV, by_name(dV, "우물"), botsV))
put(aV, stand_by(dV, by_name(dV, "우물"), botsV, skip=[(bV["x"], bV["y"])]))
oB = dV.view(bV, botsV)
wB = brains._wire(oB, NAMES, compose=True)
check("⑦ 곁의 사람(봇2)의 관측·프롬프트에 봇1 의 욕구·기분이 없다(보통인 자기 몸은 '몸:'·'기분:' 줄도 없다) · 시야에 needs·mood_now 칸 없음",
      "need_lines" not in oB and "need_mood" not in oB and LINE["hungry"] not in wB and "배고픔" not in wB
      and not re.search(r"\n- (몸|기분): ", wB)
      and not any(k_ in json.dumps(oB.get("sights"), ensure_ascii=False) for k_ in ("needs", "mood_now", "moods")))
wA = wire(dV, aV, botsV)
st_sec = wA.split("## 네 상태")[1].split("##")[0]
check("⑦ 내 프롬프트: '- 몸: 배가 고프다.' · '- 기분: 좋지 않다 (이유: 배고픔)' 두 줄 — 숫자(충족도·기분 합)·단계 id·다른 단계 이름(굶주림·배부름)·무게 등급이 없다 "
      "(이유 낱말 '배고픔'은 말 파일의 why)",
      "\n- 몸: 배가 고프다.\n- 기분: 좋지 않다 (이유: 배고픔)\n" in wA and not re.search(r"\n- (몸|기분):[^\n]*\d", wA)
      and "굶주림" not in wA and "배부름" not in wA and "충족" not in wA and "보통" not in st_sec and "hungry" not in wA and "-10" not in st_sec)
aV["rations"] = 1
rV = act(dV, aV, botsV, {"type": "use", "target": "self", "item": "i9"})
lastV = aV["last"]
check("⑦ 내 결과의 숫자는 공개 투영이 걷는다 — last·궤적에 before·after·tol 이 없다(스트림 원본엔 있다) · 기분 사건(need_mood)의 from·to·sum 도 걷는다",
      all(k in rV for k in ("before", "after", "tol")) and not any(k in lastV for k in ("before", "after", "tol"))
      and lastV.get("result") == "need_fill" and lastV.get("what") == "휴대식"
      and not any(k in IG.public({"result": "need_stage", "need": "hunger", "from": "normal", "to": "hungry", "before": 1}) for k in ("from", "to", "before"))
      and IG.public({"result": "need_mood", "from": None, "to": "bad", "sum": -10, "why": ["배고픔"]}) == {"result": "need_mood", "why": ["배고픔"]})
check("⑦ 관전 칸: 몸의 needs·moods·need_w·taste · 봇 스냅샷의 mood_now 는 공개 투영의 관전 칸(SPECTATOR_KEYS — 어느 깊이든 걷는다)",
      {"needs", "moods", "need_w", "taste", "mood_now"} <= set(IG.SPECTATOR_KEYS)
      and IG.public({"result": "x", "deep": {"needs": {"hunger": 3}, "moods": [1], "taste": {"likes": ["빵"]}, "mood_now": {"key": "bad", "sum": -10}}})
      == {"result": "x", "deep": {}})
facts_tk = " ".join(R.npc_facts(dV, "주점 주인", botsV, [], None))
check("⑦ NPC 두뇌 사실(주점 주인): 맡은 가게의 값 '판다: 식사 3골드' · 손님의 배고픔·기분은 없다",
      "판다: 식사 3골드" in facts_tk and LINE["hungry"] not in facts_tk and "배고" not in facts_tk, facts_tk)

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑧ 문장 게이트(지시·의무·청유 없음)")
need_md = sorted(glob.glob(os.path.join(WD.WORDS_ROOT, "need", "*.md")))
texts = []
for p_ in need_md:
    with io.open(p_, encoding="utf-8") as f:
        texts += [v for v in WD.parse(f.read())[0].values() if isinstance(v, str)]
texts += [ENT.item_rule("ration"), ENT.item_rule("food")] + [ENT.get(e)["comps"]["item"]["desc"] for e in ("ration", "meal", "apple")]
texts += [NE.NO_REGEN_TAIL, NE.FULL_FALLBACK, NE.DRAIN_LINE, brains._last_prose(rF), brains._last_prose(rF2), brains._last_prose(rH), brains._last_prose(rH2),
          brains._last_prose(r_r), brains._last_prose(r_l), ENT.get("produce_stall")["comps"]["story"]["trait"]]
texts += list(ENT.mood_words().values()) + [brains._last_prose(aH["last"]), "좋지 않다 (이유: 배고픔, 입에 맞지 않는 음식)"]   # p0.5.18 기분 낱말·싫어한 음식 결과·기분 줄
probs = [p for t_ in texts for p in NE.order_problems(t_)]
check("⑧ 욕구 말 파일(몸 문장·이유 낱말·결과 꼬리) · 기분 낱말 · 음식 설명·규칙 · 엔진 문장 · 결과 문장 %d개 — 명령·의무·청유 꼴로 끝나는 문장 0" % len(texts),
      not probs and len(texts) >= 25, probs)
red = ["배가 고프면 주점에 가야 한다.", "먹어야 한다.", "식사를 하자.", "주점에 가라.", "휴대식을 먹어라."]
check("⑧ 문장 게이트 빨간불 표본 5개는 전부 잡는다(말끝 꼴)", all(NE.order_problems(t_) for t_ in red), [t_ for t_ in red if not NE.order_problems(t_)])
sv = ENT.npc("street_vendor")
check("⑧ 가게가 생겨 거짓이 된 말(§7): 노점 상인의 '아직 값은 안 매겼어요'·'사고파는 건 아직'·'(아직 사고팔 수는 없다)' · 주점 주인(마을 생활)의 '안은 아직 준비 중'이 없다",
      not any("아직" in (sv.get(k) or "") for k in ("line", "line_again", "role")) and "아직" not in ENT.get("street_vendor")["comps"]["story"]["trait"]
      and "준비 중" not in ENT.npc("tavern_keeper", life=True)["line"] and "준비 중" not in ENT.npc("tavern_keeper", life=True)["line_again"])
cp = brains.COMPOSE_PROMPT
gl_ = [ln for ln in cp.split("\n") if ln.startswith(("- `몸", "- `기분"))]
check("⑧ 지침(p0.5.18): 기능 설명 두 줄 그대로 '- `몸:`은 지금 몸 상태다.' · '- `기분:`은 지금 기분과 그 이유다.'(권유 없음) · 옛 '몸과 기분' 없음 · use 설명에 '먹기' · "
      "'먹어라'·'유지하라'·'채워라' 없음 · 상태 줄 머리 = 지침의 낱말(몸·기분)",
      gl_ == ["- `몸:`은 지금 몸 상태다.", "- `기분:`은 지금 기분과 그 이유다."] and "몸과 기분" not in cp and not any(NE.order_problems(ln[2:]) for ln in gl_)
      and "먹기" in cp and not any(w_ in cp for w_ in ("먹어라", "유지하라", "채워라", "먹어야"))
      and (brains.BODY_HEAD, brains.MOOD_HEAD) == ("몸", "기분") and not hasattr(brains, "NEED_HEAD")
      and {"need_lines", "need_mood", "rations"} <= brains._WIRE_KEYS, gl_)

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑨ 러너 판(더미 · 임시 state)")


def wait_brain(obs, char="?"):
    return {"type": "wait"}


def eat_brain(obs, char="?"):
    """각본 두뇌 — '몸:' 줄(need_lines)이 있고 휴대식을 지녔으면 먹는다(use i9 → 나), 아니면 기다린다."""
    return {"type": "use", "target": "self", "item": "i9"} if obs.get("need_lines") and obs.get("rations") else {"type": "wait"}


def run(turns, defs=None, life=True, brain=wait_brain, rations=0):
    """러너 판 한 번(임시 state · 각본 두뇌). rations = 스폰 몸마다 쥐여 줄 휴대식(스폰을 감싼다 — 코드는 그대로). 0콜."""
    st = tempfile.mkdtemp(prefix="run_", dir=ROOT)
    old = (R.STATE, R.TOWN_LIFE_ON, R.MAX_TURNS, G.dummy_brain, G.spawn)
    R.STATE, R.TOWN_LIFE_ON, R.MAX_TURNS = st, life, turns
    G.dummy_brain = brain
    if rations:
        spawn0 = old[4]

        def _spawn(*a, **k):
            b_ = spawn0(*a, **k)
            b_["rations"] = rations
            return b_
        G.spawn = _spawn
    if defs is not None:
        ENT._DEFS = defs
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try:
                R.main()
            except SystemExit:
                pass
    finally:
        R.STATE, R.TOWN_LIFE_ON, R.MAX_TURNS, G.dummy_brain, G.spawn = old
        ENT._DEFS = DEFS0
    with open(os.path.join(st, "stream.jsonl"), encoding="utf-8") as fh:
        rows_ = [json.loads(ln) for ln in fh if ln.strip()]
    with open(os.path.join(st, "events.log"), encoding="utf-8") as fh:
        evlog_ = fh.read()
    return rows_, evlog_


rows9, ev9 = run(240, brain=eat_brain, rations=1)
ticks9 = [r_ for r_ in rows9 if r_["kind"] == "tick"]
need9 = [e for r_ in ticks9 for e in r_.get("events") or [] if e.get("type") == "need"]
st9 = [(r_["turn"], e["bot"], e["to"]) for r_ in ticks9 for e in r_.get("events") or [] if e.get("result") == "need_stage" and e.get("to") == "hungry"]
check("⑨ 판이 끝까지 돈다 · 모든 틱의 tick.bots[] 에 needs · run_meta.need_defs.hunger(시작값·단계·효과)",
      rows9[-1]["kind"] == "end" and all("needs" in b_ for r_ in ticks9 for b_ in r_["bots"])
      and rows9[0]["need_defs"]["hunger"]["stages"]["starving"]["effects"]["hp_drain"] == {"every": 60, "floor": 50}
      and rows9[0]["need_defs"]["hunger"]["start"] == 70, (rows9[-1].get("kind"), rows9[0].get("need_defs")))
check("⑨ t120 에 셋 다 보통 → 배고픔(need_stage · bot · char 없음 — 실행된 결정 = 그 char 의 이벤트 하나 규칙 그대로) · 관전 로그 '배고픔: 보통 → 배고픔'",
      sorted(st9) == [(120, c, "hungry") for c in ("1", "2", "3")] and all("char" not in e for e in need9)
      and "배고픔: 보통 → 배고픔" in ev9 and ev9.index("-- tick 120 --") < ev9.index("배고픔: 보통 → 배고픔") < ev9.index("=== 시간 종료"),
      (st9, [ln for ln in ev9.split("\n") if "배고픔" in ln][:3]))
eat9 = {}
for r_ in ticks9:
    evs_ = r_.get("events") or []
    for i_, e in enumerate(evs_):
        if e.get("type") == "use" and e.get("result") == "need_fill":
            j_ = next((j for j, x in enumerate(evs_) if j > i_ and x.get("type") == "need" and x.get("bot") == e["char"] and x.get("result") == "need_stage"), None)
            sb_ = next(b_ for b_ in r_["bots"] if b_["char"] == e["char"])
            eat9.setdefault(e["char"], []).append((r_["turn"], e, evs_[j_] if j_ is not None else None, sb_))
ok_eat9 = sorted(eat9) == ["1", "2", "3"] and all(len(v_) == 1 for v_ in eat9.values())
check("⑨ 각본 두뇌가 배고파진 뒤 휴대식을 먹는다(셋 다 한 번) — 행동 사건 use·need_fill(char) 뒤에 같은 틱 그 몸의 need_stage 배고픔 → 배부름(bot · 행동이 낳은 사건이 틱 기록에 실린다) · "
      "그 틱 tick.bots[] 의 needs = 먹은 뒤 값 · moods = 기본 기분 조각(60틱 · 먹은 것 이름) · mood_now = 좋다(+8 · 배불리 먹음) · 관전 로그 '🍞 휴대식을 먹었다'",
      ok_eat9 and all(T_ > 120 and e["before"] < 41 and e["after"] == e["before"] + 50 and st_ and (st_["from"], st_["to"]) == ("hungry", "full")
                      and sb_["needs"]["hunger"] == e["after"] and sb_.get("rations", 0) == 0
                      and sb_.get("moods") == [{"src": "hunger", "size": "plain", "what": "휴대식", "until": T_ + 60}]
                      and sb_.get("mood_now") == {"key": "good", "sum": 8, "why": ["배불리 먹음"]}
                      for (T_, e, st_, sb_), in eat9.values())
      and "🍞 휴대식을 먹었다" in ev9, {c: [(T_, e.get("before"), e.get("after"), st_, sb_.get("moods"), sb_.get("mood_now")) for T_, e, st_, sb_ in v_]
                                        for c, v_ in eat9.items()})
md9 = {c: [(r_["turn"], e["from"], e["to"], e.get("sum"), e.get("why")) for r_ in ticks9 for e in r_.get("events") or []
           if e.get("result") == "need_mood" and e.get("bot") == c] for c in ("1", "2", "3")}
now9 = {c: {r_["turn"]: next(b_ for b_ in r_["bots"] if b_["char"] == c).get("mood_now") for r_ in ticks9} for c in ("1", "2", "3")}
check("⑨ 기분 사건(스트림 need_mood · bot): t120 없음 → 좋지 않다(−10 · 배고픔) · 먹은 틱 좋지 않다 → 좋다(+8 · 배불리 먹음) · 60틱 뒤 조각이 끝나 좋다 → 없음 — 셋 다 · "
      "tick.bots[].mood_now 는 t119 없음 · t120 좋지 않다 · 조각이 끝난 틱 없음 · 관전 로그 '기분: 없음 → 좋지 않다 (배고픔 · 합 -10)'",
      ok_eat9 and all(md9[c] == [(120, None, "bad", -10, ["배고픔"]), (eat9[c][0][0], "bad", "good", 8, ["배불리 먹음"]), (eat9[c][0][0] + 60, "good", None, None, None)]
                      and now9[c][119] is None and now9[c][120] == {"key": "bad", "sum": -10, "why": ["배고픔"]} and now9[c][eat9[c][0][0] + 60] is None
                      for c in md9)
      and "기분: 없음 → 좋지 않다 (배고픔 · 합 -10)" in ev9 and "기분: 좋지 않다 → 좋다 (배불리 먹음 · 합 +8)" in ev9 and "기분: 좋다 → 없음" in ev9,
      (md9, [ln for ln in ev9.split("\n") if "기분:" in ln][:6]))
exp9 = {c: [(r_["turn"], bool(next(b_ for b_ in r_["bots"] if b_["char"] == c).get("moods"))) for r_ in ticks9 if v_[0][0] <= r_["turn"] < v_[0][0] + 70]
        for c, v_ in eat9.items()} if ok_eat9 else {}
check("⑨ 기분 조각 만료(스트림): 먹은 틱부터 60틱 동안 tick.bots[].moods 가 있고 그 틱(until)부터 없다 — 셋 다",
      ok_eat9 and all(len(rs_) == 70 and all(has_ == (t_ < eat9[c][0][0] + 60) for t_, has_ in rs_) for c, rs_ in exp9.items()),
      {c: [t_ for t_, has_ in rs_ if has_][-1:] for c, rs_ in exp9.items()})
tw_src = rsrc.split("def _tick_world(")[1].split("\n    def ")[0]
check("⑨ 러너 틱 순서(소스): 판단 전 줄기(G.NE.tick) → 틱 머리 사건이 events 맨 앞 → 행동이 낳은 사건은 tick 기록 직전에(G.NE.drain 두 번)",
      0 <= tw_src.find("G.NE.tick(d, bots, turn)") < tw_src.find("brains.think_all(") < tw_src.find('event("-- tick %d --') < tw_src.find("turn_events = list(_need_events(need_pre))")
      < tw_src.find("turn_events += _need_events(G.NE.drain(d))") < tw_src.find("tick_rec = {"))
rowsT, evT_ = run(45, defs=DEFS_T)
stT = [(r_["turn"], e["bot"], e["need"], e["to"]) for r_ in rowsT if r_["kind"] == "tick" for e in r_.get("events") or [] if e.get("result") == "need_stage"]
mdT = [(r_["turn"], e["bot"], e["from"], e["to"], e.get("why")) for r_ in rowsT if r_["kind"] == "tick" for e in r_.get("events") or [] if e.get("result") == "need_mood"]
check("⑨ 시험용 욕구를 더한 판(코드 그대로): t42 에 셋 다 보통 → 목마름 · 같은 틱 기분 없음 → 좋지 않다(목마름) · run_meta.need_defs 에 test_thirst(기분 값 −6) · 배고픔은 제 박자(t44 에 59)",
      sorted(stT) == [(42, c, "test_thirst", "dry") for c in ("1", "2", "3")] and "test_thirst" in rowsT[0]["need_defs"]
      and sorted(mdT) == [(42, c, None, "bad", ["목마름"]) for c in ("1", "2", "3")] and rowsT[0]["need_defs"]["test_thirst"]["stages"]["dry"]["mood"] == -6
      and [(b_.get("needs") or {}).get("hunger") for b_ in [r_ for r_ in rowsT if r_["kind"] == "tick"][43]["bots"]] == [59, 59, 59], (stT, mdT))

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑩ 배선")
sf = src("STREAM_FORMAT.md")
check("⑩ STREAM_FORMAT: 욕구 절(tick.bots[].needs·moods · need_fill · need_none · need_stage · need_drain · bot · run_meta.need_defs · rations) · "
      "p0.5.18 몸·기분 줄(need_mood 사건 · mood_now · 관측 need_mood · 저장 판 11)",
      "## 욕구와 배고픔" in sf and all(k in sf for k in ("`tick.bots[].needs`", "need_fill{", "need_none{", "need_stage{", "need_drain{", "`run_meta.need_defs`",
                                                     "`moods`", "`rations`", "char` 대신 `bot`", "| `need` |",
                                                     "need_mood{", "`mood_now`", "`need_mood`", "_m10_moods")))
check("⑩ _run_gates.sh 에 verify_needs 등록 · VERSION 0.5.18 이상 · 말 파일 검사 도구가 기분 낱말을 센다", "verify_needs" in src("_run_gates.sh")
      and tuple(int(x) for x in src("VERSION").strip().split(".")) >= (0, 5, 18) and "MOOD_WORDS" in src("tools", "check_words.py"))

shutil.rmtree(ROOT, ignore_errors=True)
print("ALL PASS — verify_needs (p0.5.16 욕구 틀 + 배고픔 · p0.5.18 몸·기분 줄: %d checks · 정의·검증기 · 데이터만으로 새 욕구(기분까지) · 단계 경계 · 굶주림 효과 · 먹기 끝까지 · "
      "기분 합산·이유·문턱·동점 · 저장 · 남에게 안 보임 · 문장 · 러너 · 배선, 실 LLM 0콜)" % C.n
      if not C.failed else "FAIL %d — verify_needs" % C.failed)
raise SystemExit(1 if C.failed else 0)

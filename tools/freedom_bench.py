#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""행동 자유도 벤치마크(t06, 2026-10-11) — 게임 안 모델이 행동 사전의 행동을 얼마나 다양하게 엮어 세계에서 서로 다른
결과를 내는지 코드로 잰다. 쓰임 둘: ① 행동 사전 형식 비교(기준선 + 초안 6개) ② 배선(세계가 반응하는 조합 늘리기) 전후 비교.

재현의 세 기둥 — 같은 장면 · 같은 지침 · 같은 채점.
  · 장면: 론처 표준 원정 설정(아래 GAME_ENV — 실판 기록을 읽지 않는다, 값은 코드에 고정)으로 게임의 생성기(마을 town_for_run · 던전 new_floor)를
    시드 고정으로 돌리고, 자리·몸 상태만 코드로 정한 뒤 **실제 think_all 이 모델에게 넘기는 관측**을 그대로 잡는다
    (claude_brain 만 가로채 그 순간의 세계·관측을 피클로 얼린다 = 상태 스냅샷).
  · 지침: 작업 사본 prompts/adventurer_prompt.md 의 '## 행동 사전' 절만 초안(tools/bench_variants/<변형>.md — p0.5.5 에 .orch/drafts/
    에서 저장소 안으로 옮겼다, 바이트 그대로)으로 갈아 끼운 파일을 brains._load_prompt 로 읽고,
    결정은 brains.claude_brain(시트 + 지침 + _wire 관측 + 입력 오류 재요청 1회 — 게임과 같은 길)으로 받는다.
    초안 절 끝에는 기준선의 SKILL 치환 앵커 문장을 덧붙여 모든 변형이 같은 스킬 안내를 받게 하고, 치환 여부를 검사해 meta.json 에 남긴다.
    p0.5.5(master_plan §7.2·§7.4): 새 공용 행동의 문장은 지침이 아니라 관측의 '추가 행동' 블록에 붙는다 — 판단 전 검사가
    SKILL 유무 × 추가 행동 유무 4조합에서 치환과 블록(모든 변형이 같은 바이트)을 함께 본다.
  · 채점(모델 판정 없음): 결정을 장면 사본에서 엔진으로 끝까지 굴린다(d.act → 주문이 끝날 때까지 step_order). 판정은 엔진의
    resolution.status(success/no_effect/failed), 결과 꼬리표는 event_tags(모델이 다음 관측에서 보는 그 꼬리표)의 첫 라벨.
    주사위를 쓰는 조합은 고정 시드 여러 개로 굴려 '그 조합이 낼 수 있는 결과'를 모은다(운이 아니라 고른 조합을 잰다).
    행동 전후 상태 차이를 '행동 자체'와 '부수'(접근·이동 중 일어난 일)로 갈라 기록하고, 채점은 행동 자체로만 한다(아래 '상태 차이' 절).
  · 호출: 인프라 실패(타임아웃·429·5xx)는 같은 프롬프트로 다시 부르고, 끝내 실패하면 결측으로 남겨 지표 분모에서 뺀다.

사용(리포 루트에서, 모두 포그라운드):
  python tools/freedom_bench.py                         # dummy(고정 응답) — LLM 0콜, 전 과정 한 번
  python tools/freedom_bench.py --mock-infra            # dummy + 모의 호출 실패(429 재호출·타임아웃 결측) 경로 확인
  python tools/freedom_bench.py --space-only            # 장면별 가능 공간만
  python tools/freedom_bench.py --show s3_wounded_ally  # 장면 관측 원문 보기
  python tools/freedom_bench.py --brain gemini          # 본 실행(장면 8 × 변형 7 × 반복 3) — 관리자 전용
  python tools/freedom_bench.py --rescore ab_runs/freedom_bench/<run>   # 기록된 응답을 지금 엔진으로 다시 채점(배선 전후)
  python tools/freedom_bench.py --seq all               # 연속 판단 장면(p0.5.5 §7.4) — dummy, LLM 0콜
  python tools/freedom_bench.py --seq all --brain gemini --variants baseline --reps 3   # 연속 장면 본 실행 — 관리자 전용
결과: ab_runs/freedom_bench/<run>/ (.gitignore 의 ab_runs/ — 저장소 밖)

연속 판단 장면(p0.5.5, master_plan §7.4 — B1 '에이전트가 hide→steal 을 스스로 하나'가 첫 사용처): 장면당 판단 1회로는 2~3단계 연계를
못 잰다. 같은 판단 주체가 세계 안에서 최대 SEQ_MAX 판단을 이어 간다 — 틱마다 게임의 think_all(관측·기억 주입·intent·history·note·
대화 장부)로 판단하고, d.act·step_order 로 굴리고, 몹 턴·행인 걸음·말 배달(deliver_and_hail)·NPC 인사를 돌린다. 다른 캐릭터는
고정 대본(없으면 wait). 지표: 목표 완주율 · 판단 수 · 형식 오류 · 판단당 프롬프트 길이 · 기억 유지(앞 판단의 note 가 다음 프롬프트에 있나).
"""
import argparse
import collections
import copy
import hashlib
import json
import os
import pickle
import random
import re
import subprocess
import sys
import time
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT_ROOT = os.path.join(ROOT, "ab_runs", "freedom_bench")

# ── 게임 설정 — 론처 표준 원정 + concept 맵 + 켜 둔 실험 옵션(2026-10-07 판 구성을 옮겨 적은 고정값) ─────────────
# 엔진 모듈이 import 시점에 환경을 읽으므로 import 전에 건다. 셸에 남은 DUNGEON_* 는 지운다(게이트용 menu 모드 등이 새지 않게) —
# 모델 배선 값(DUNGEON_MODEL_* · DUNGEON_GEMINI_* · DUNGEON_BRAIN_TIMEOUT/MAXTOK)만 게임처럼 물려받는다.
SCENE_SEED = 4242
GAME_ENV = {
    "DUNGEON_ACTION_MODE": "compose", "DUNGEON_SKILLS": "1", "DUNGEON_TRPG_COMBAT": "1", "DUNGEON_RANDOM_SKILL": "1",
    "DUNGEON_TOWN": "1", "DUNGEON_ARCH": "concept", "DUNGEON_W": "54", "DUNGEON_H": "42", "DUNGEON_MONSTERS": "4",
    "DUNGEON_TRAPS": "3", "DUNGEON_LURKERS": "1", "DUNGEON_POTIONS": "1", "DUNGEON_GEAR": "3",
    "DUNGEON_DEPTHS": "3", "DUNGEON_TURNS": "1800", "DUNGEON_SIGHT": "6", "DUNGEON_SOLO": "0",
    "DUNGEON_PARTYFORM": "1", "DUNGEON_STRANGERS": "1", "DUNGEON_TOWN_SIGHT": "zone", "DUNGEON_TOWN_APART": "0",
    "DUNGEON_LOOP": "1", "DUNGEON_TOWN_LIFE": "1", "DUNGEON_NPC_REPLY": "1", "DUNGEON_NPC_BRAIN": "1",
    "DUNGEON_FLOOR_LIFE": "1", "DUNGEON_BESTIARY_PLUS": "1", "DUNGEON_BOSS": "1",
    "DUNGEON_GM": "0", "DUNGEON_BESTIARY_FILE": "", "DUNGEON_STEP_DELAY": "0", "DUNGEON_SEED": str(SCENE_SEED),
    # 장면은 늘 이 백엔드 이름으로 짓는다(build_town 의 NPC 되받기 표식이 백엔드를 본다 — 모드마다 관측이 달라지면 안 된다).
    # dummy 모드는 호출 함수(_call_claude)만 갈아 끼우고, 나가는 HTTP 한 점(_http_post)도 막는다.
    "DUNGEON_BRAIN_BACKEND": "gemini_api",
}
KEEP_ENV = ("DUNGEON_MODEL_", "DUNGEON_GEMINI_", "DUNGEON_BRAIN_TIMEOUT", "DUNGEON_BRAIN_MAXTOK")

ACTOR, ALLY, OFFSTAGE = "3", "1", "2"   # party.json 기본 파티: 피른(궁수·사거리 2) 이 판단 주체, 두란(전사) 동료, 카야(도적)는 화면 밖
VARIANTS = ("baseline", "A-claude", "A-codex", "B-claude", "B-codex", "C-claude", "C-codex")
VARIANT_DIR = "tools/bench_variants"   # 초안 변형(행동 사전 절) — 리포 루트 기준. p0.5.5 에 .orch/drafts/ 에서 옮겼다(바이트 그대로)
SECTION = "## 행동 사전"
SEEDS = (11, 22, 33, 44, 55)            # 주사위 조합을 굴리는 고정 시드(주사위를 안 쓰는 조합은 첫 시드 한 번만)
MAX_STEPS = 200                         # 접근·이동을 끝까지 굴리는 틱 상한(마을 끝에서 끝 ~120걸음, 넘으면 '미확정' = 실패로 센다)
BOND_FORM = "어깨를 가볍게 두드린다"      # 가능 공간 대입용 몸짓(엔진은 문구를 판정에 안 쓴다)
KIND_OF = {"bot": "b", "monster": "m", "exit": "exit", "door": "d", "way": "w", "trap": "t", "quest": "q", "item": "i"}
TARGETLESS = ("wait", "rest", "party_leave")   # 엔진이 대상을 읽지 않는 동사
G = SR = brains = CA = bestiary = None   # 엔진 모듈 — _engine() 이 환경을 건 뒤 채운다


def _engine(state_dir, call_limit=0):
    """환경을 게임 설정으로 맞추고 엔진을 import 한다. call_limit = 게임의 전송 상한(D96 DUNGEON_API_CALL_LIMIT — 본 실행 안전망)."""
    global G, SR, brains, CA, bestiary
    for k in [k for k in os.environ if k.startswith("DUNGEON_") and not k.startswith(KEEP_ENV)]:
        del os.environ[k]
    os.environ.update(GAME_ENV, PYTHONUTF8="1", DUNGEON_STATE_DIR=state_dir,
                      DUNGEON_PARTY_FILE=os.path.join(ROOT, "party.json"), DUNGEON_API_CALL_LIMIT=str(call_limit),
                      DUNGEON_BRAIN_LOG=os.path.join(os.path.dirname(state_dir), "brain_calls.jsonl"))
    os.makedirs(state_dir, exist_ok=True)
    import show_runner as SR_
    import brains as brains_
    import dungeon_gm as G_
    import composed_actions as CA_
    import bestiary as bestiary_
    G, SR, brains, CA, bestiary = G_, SR_, brains_, CA_, bestiary_


# ── 장면 ─────────────────────────────────────────────────────────────────────────────────────────────
def _bots(d, sheets):
    """show_runner.main 의 새 판 캐릭터 놓기와 같은 칸들(시트·도감 발급기·공간 장부·인물 기록)."""
    names = {c: (sheets[c].get("name") or "봇%s" % c) for c in sorted(sheets)}
    keys = {c: (sheets[c].get("id") or names[c]) for c in sorted(sheets)}
    iss = bestiary.Issuer(keys)
    bots = []
    for c in sorted(sheets):
        b = G.spawn(d, c, bots, sheet=sheets[c], apart=SR.SOLO_ON)
        b["known"], b["book"] = iss.known(keys[c]), iss.record(keys[c])
        if SR.LEDGER_ON:
            b["ledger"] = G.new_ledger()
        if SR.STRANGERS_ON:
            b["people"] = {"b%s" % oc: {"name": sheets[oc].get("name") or "봇%s" % oc, "text": str(txt), "turn": 0, "src": "sheet"}
                           for oc, txt in sorted((sheets[c].get("relationships") or {}).items()) if oc in sheets and oc != c}
        bots.append(b)
    return bots


def _place(d, b, xy):
    """캐릭터를 칸에 세운다(러너의 마을 출발 자리 놓기와 같은 손질). 빈 바닥이 아니면 장면 저작 오류로 죽는다."""
    x, y = xy
    if d.grid[y][x] != G.FLOOR or d.feature_at(x, y) or d.monster_at(x, y):
        raise ValueError("장면 자리 %r 가 빈 바닥이 아니다" % (xy,))
    d.visited.discard((b["x"], b["y"]))
    b["x"], b["y"] = x, y
    d.visited.add((x, y))


def _starter_kit(d, b, potions=1):
    """마을 길드 접수원의 첫 선물(물약 + 빈손이면 단검)을 받고 내려온 몸 — dungeon_gm._interact 의 선물 칸과 같은 꼴."""
    b["potions"] = b.get("potions", 0) + potions
    if not b.get("weapon"):
        b["weapon"] = {"id": d._alloc_fid(), "name": "단검", "bonus": G.GEAR_KINDS.get("단검", 1), "worn": [b["char"]]}


def _town():
    sheets = SR.load_party(SR.PARTY_FILE)
    quests = G.new_quests()
    d, _starts = SR.town_for_run(SR.TOWN_APART_ON, quests, SR.TOWN_WALKERS_ON, SR.TOWN_GUIDE_ON)
    d.lore = G.ENT.lore(plus=SR.BESTIARY_PLUS_ON)
    d.plan_max = 0
    d.parties = G.new_parties()
    SR._partyform_town(d)
    d.elsewhere, d.turn = [], 1
    return d, _bots(d, sheets)


def _floor(drop_monsters=()):
    """던전 1층(러너 new_floor 그대로) + 세 사람이 맺은 파티(입구 규칙: 3명). drop_monsters = 장면 밖으로 치우는 몹 번호."""
    sheets = SR.load_party(SR.PARTY_FILE)
    d = SR.new_floor(1, G.ENT.lore(plus=SR.BESTIARY_PLUS_ON), G.new_quests())
    d.plan_max = 0
    d.parties = G.new_parties()
    G.party_join(d.parties, sorted(sheets))
    d.elsewhere, d.turn = [], 1
    d.monsters = [m for m in d.monsters if m.id not in drop_monsters]
    bots = _bots(d, sheets)
    for b in bots:
        if b["char"] in (ACTOR, ALLY):
            _starter_kit(d, b)
    _place(d, _bot(bots, OFFSTAGE), (38, 4))   # 카야 — 출구 방(어느 장면에서도 시야 밖)
    return d, bots


def _bot(bots, c):
    return next(b for b in bots if b["char"] == c)


def _greetings(d, bots, inbox):
    """러너 틱 머리의 마을 NPC 인사(D71 — 고정 문장, 0콜)를 받은편지함에 넣는다(show_runner._tick_world 와 같은 꼴)."""
    for nm_, ch_, line_, _hx, _hy, _key in d.npc_greetings(bots):
        inbox.setdefault(ch_, []).append({"from": "npc:" + nm_, "text": line_, "turn": d.turn, "to": ch_})
    return inbox


def s1_town_guild():
    d, bots = _town()
    _place(d, _bot(bots, ACTOR), (70, 19))   # 모험가 길드 문턱 곁 — 게시판 의뢰(q)가 보이는 거리
    return d, bots, _greetings(d, bots, {})


def s2_room_objects():
    d, bots = _floor(drop_monsters=(0, 2))
    G.IA.place(d, "floor_tablet", 16, 25)    # 읽을거리(석판) — 장면 저작(IA.place 는 층 생성·마을 살림과 같은 배치 도우미)
    _place(d, _bot(bots, ACTOR), (19, 28))
    _place(d, _bot(bots, ALLY), (18, 27))
    return d, bots, {}


def s3_wounded_ally():
    d, bots = _floor(drop_monsters=(4,))
    me, ally = _bot(bots, ACTOR), _bot(bots, ALLY)
    _place(d, me, (4, 27))
    _place(d, ally, (7, 29))
    me["potions"] = 2
    ally["hp"] = 3
    d._apply_status(ally, "출혈", "고블린", bots, by_kind="monster")
    return d, bots, {}


def s4_monster():
    d, bots = _floor()
    _place(d, _bot(bots, ACTOR), (47, 19))   # 고블린(42,22)이 보이지만 사거리 밖
    _place(d, _bot(bots, ALLY), (48, 18))
    return d, bots, {}


def s5_floor_loot():
    d, bots = _floor(drop_monsters=(3,))
    G.IA.place(d, "treasure", 30, 14)
    _place(d, _bot(bots, ACTOR), (27, 19))
    _place(d, _bot(bots, ALLY), (28, 18))
    return d, bots, {}


def s6_trap():
    d, bots = _floor()
    trap = next(t for t in d.traps if (t.x, t.y) == (8, 13))
    trap.hidden = False                      # 이미 찾아낸 함정(수색으로 드러난 뒤의 모습)
    _place(d, _bot(bots, ACTOR), (4, 15))
    _place(d, _bot(bots, ALLY), (3, 16))
    return d, bots, {}


def s7_fork():
    d, bots = _floor()
    _place(d, _bot(bots, ACTOR), (40, 13))   # 출구 방과 동쪽 큰 방을 잇는 통로 — 문 둘, 길 N·S·SE
    _place(d, _bot(bots, ALLY), (40, 14))
    return d, bots, {}


def s8_proposal():
    d, bots = _town()
    me, ally = _bot(bots, ACTOR), _bot(bots, ALLY)
    _place(d, me, (27, 36))                  # 주점 앞 — 동료 두란이 곁에서 파티를 청한다
    _place(d, ally, (28, 36))
    for b in bots:                           # t1 관측(마을 안내 문단은 첫 관측 1회)은 이미 지나갔다
        d.view(b, bots)
    inbox, _hails = SR.deliver_and_hail(d, bots, {ALLY: "피른, 나랑 파티 맺자. 카야까지 셋이 모이면 바로 던전에 내려갈 수 있어."},
                                        {ALLY: ACTOR}, {ALLY: "제안"}, {})
    d.turn = 2
    return d, bots, _greetings(d, bots, inbox)


SCENES = collections.OrderedDict([
    ("s1_town_guild", ("마을 — 모험가 길드 문턱 곁(접수원·게시판 의뢰·행인·벤치)", s1_town_guild)),
    ("s2_room_objects", ("던전 방 — 나무 상자·항아리·석판·바닥 갑옷·문, 동료 곁", s2_room_objects)),
    ("s3_wounded_ally", ("던전 방 — 크게 다친 동료(HP 3/14·출혈), 내 회복 물약 2병", s3_wounded_ally)),
    ("s4_monster", ("던전 방 — 고블린이 보인다(사거리 밖)·석판·보물, 동료 곁", s4_monster)),
    ("s5_floor_loot", ("던전 방 — 바닥의 보물·회복 물약·상자, 동료 곁", s5_floor_loot)),
    ("s6_trap", ("던전 방 — 이미 드러난 함정, 동료 곁", s6_trap)),
    ("s7_fork", ("던전 통로 — 갈래 길(대상은 길·문·동료 정도)", s7_fork)),
    ("s8_proposal", ("마을 주점 앞 — 동료 두란의 파티 제안을 방금 받음", s8_proposal)),
])


class Scene:
    """얼린 장면 — blob = pickle((세계, 사람들, 판단 주체의 관측)). 모든 판단·채점은 이 바이트에서 새 사본을 푼다.
    피클은 이 프로세스가 방금 만든 바이트만 푼다(디스크의 scenes/*.pkl 은 기록용으로 쓰기만 하고 이 도구는 읽지 않는다)."""

    def __init__(self, name, desc, blob, solo):
        self.name, self.desc, self.blob, self.solo = name, desc, blob, solo
        _d, bots, obs = pickle.loads(blob)
        self.obs = obs
        me = _bot(bots, ACTOR)
        self.names = brains._names_for(me, [] if solo else bots)
        self.text = brains._wire(obs, self.names, compose=True)
        self.fingerprint = hashlib.sha256((self.text + json.dumps(obs.get("targets"), ensure_ascii=False, sort_keys=True))
                                          .encode("utf-8")).hexdigest()[:16]

    def thaw(self):
        d, bots, obs = pickle.loads(self.blob)
        return d, bots, obs, _bot(bots, ACTOR)


def build_scene(name):
    """장면을 짓고 실제 think_all 로 판단 주체의 관측을 만든다(claude_brain 만 가로챔 — 관측 조립·받은편지함 주입은 게임 그대로)."""
    desc, fn = SCENES[name]
    d, bots, inbox = fn()
    got = {}

    def capture(obs, char="?", bot=None, roster=None, solo=False):
        if char == ACTOR:
            got["blob"] = pickle.dumps((d, bots, obs), protocol=4)
            got["solo"] = bool(solo)
        return {"type": "wait", "say": "", "reason": "", "src": "haiku"}

    with patch.object(brains, "claude_brain", capture):
        brains.think_all(d, bots, inbox)
    if "blob" not in got:
        raise RuntimeError("%s: 판단 주체가 이번 틱에 판단하지 않았다" % name)
    return Scene(name, desc, got["blob"], got["solo"])


# ── 지침 변형 ─────────────────────────────────────────────────────────────────────────────────────────
def _section_span(text):
    a = text.index(SECTION)
    b = text.find("\n## ", a + len(SECTION))
    return a, (len(text) if b < 0 else b + 1)


# claude_brain 은 관측에 SKILL 이 있으면 지침의 이 문장을 SKILL_HINT 로 바꿔 스킬을 안내한다(brains.py claude_brain 의 replace).
# 기준선은 행동 사전 절에 이 문장이 있고 초안 6개엔 없다 — 변형을 만들 때 절 끝에 같은 문장을 넣어 모두 같은 치환을 받게 한다(t06b).
SKILL_ANCHOR = "매 판단에 제시되는 COMMON에서 행동 이름을 고른다."
SKILL_HINT = "매 판단에 제시되는 COMMON 또는 SKILL에서 행동 이름을 고른다."


def build_variants(out_dir):
    """작업 사본 지침에서 '## 행동 사전' 절만 초안으로 바꾼 파일을 만들고 게임 로더(brains._load_prompt)로 읽는다.
    초안 절에 SKILL_ANCHOR 가 없으면 절 끝에 그 문장 한 줄을 붙인다(초안 파일은 그대로).
    반환 {이름: {"text", "solo", "sha", "anchor_added"}} — 원문 파일은 out_dir/variants/ 에 남긴다(감사용)."""
    with open(os.path.join(ROOT, "prompts", "adventurer_prompt.md"), encoding="utf-8") as f:
        base = f.read().replace("\r\n", "\n")
    a, b = _section_span(base)
    if SKILL_ANCHOR not in base[a:b]:
        raise RuntimeError("기준선 행동 사전 절에 SKILL 치환 앵커 문장이 없다 — 지침이나 claude_brain 의 치환 대상이 바뀌었는지 확인")
    vdir = os.path.join(out_dir, "variants")
    os.makedirs(vdir, exist_ok=True)
    out = {}
    for name in VARIANTS:
        added = False
        if name == "baseline":
            raw = base
        else:
            with open(os.path.join(ROOT, VARIANT_DIR, name + ".md"), encoding="utf-8") as f:
                draft = f.read().replace("\r\n", "\n")
            da, db = _section_span(draft)
            sec = draft[da:db].rstrip("\n")
            if SKILL_ANCHOR not in sec:
                sec, added = sec + "\n\n" + SKILL_ANCHOR, True
            raw = base[:a] + sec + "\n\n" + base[b:]
        path = os.path.join(vdir, name + ".md")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(raw)
        text, solo = brains._load_prompt(path)      # 절대 경로 — os.path.join(HERE, 절대경로) 는 절대경로 그대로
        out[name] = {"text": text, "solo": solo, "sha": hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16], "anchor_added": added}
    if (out["baseline"]["text"], out["baseline"]["solo"]) != (brains.COMPOSE_PROMPT, brains.COMPOSE_PROMPT_SOLO):
        raise RuntimeError("기준선 지침이 게임이 읽은 지침(brains.COMPOSE_PROMPT)과 다르다 — 로더 경로가 바뀌었는지 확인")
    return out


EXTRA_PROBE = "bench_probe"            # 4조합 검사 전용 — 등록부에 잠깐 꽂는 검증용 동사(판단·채점에는 안 쓴다)
EXTRA_PROBE_WORD = "벤치 검사용 — 추가 행동 블록이 모든 변형에 같은 바이트로 붙는지 본다"


def _extra_block(prompt):
    """프롬프트의 '추가 행동' 블록 — 관측의 COMMON 줄(마지막 'COMMON: ' 줄) 다음부터 '의사소통' 줄 앞까지."""
    lines = prompt.split("\n")
    heads = [n for n, ln in enumerate(lines) if ln.startswith("COMMON: ")]
    if not heads:
        return []
    i = heads[-1]
    j = next((n for n, ln in enumerate(lines) if n > i and ln.startswith("의사소통: ")), i + 1)
    return lines[i + 1:j]


def skill_hint_check(scenes, vtexts):
    """변형마다 게임 조립 경로(claude_brain)로 프롬프트를 만들어 본다(가짜 응답, 0콜) — SKILL 유무 × 추가 행동 유무 4조합(§7.4):
      · SKILL 안내 치환: SKILL 이 있으면 SKILL_HINT 가 있고 앵커가 안 남는다 / 없으면 앵커 그대로·안내 없음
      · 추가 행동 블록(관측 _wire 의 COMMON 줄 아래, p0.5.5): 있으면 머리 줄로 시작하고 모든 변형이 바이트까지 같다 / 없으면 블록 없음
    'SKILL 없음'은 같은 장면 관측에서 skills 를 뺀 사본, '추가 행동 있음'은 등록부에 검증용 동사(EXTRA_PROBE)를 잠깐 꽂고 관측에 노출한 사본
    (등록부가 비어 있어도 길을 굴린다 — 노출 조건 자체는 verify_common_registry 의 몫). 하나라도 실패하면 판단 전에 멈춘다."""
    sc = next((s for s in scenes.values() if s.obs.get("skills")), None)
    if sc is None:
        return {"skipped": "SKILL 이 실린 장면이 없다"}
    words = dict(CA._extra_words(), **{EXTRA_PROBE: EXTRA_PROBE_WORD})
    combos_ = (("skill+extra", True, True), ("skill", True, False), ("extra", False, True), ("none", False, False))
    out, blocks = {}, {}
    with patch.dict(CA.COMMON_EXT, {EXTRA_PROBE: {"expose": lambda view: True, "run": None}}), patch.object(CA, "_EXTRA_LINES", words):
        for v, vt in vtexts.items():
            out[v] = {"scene": sc.name, "anchor_added": vt["anchor_added"]}
            for name, skills, extra in combos_:
                def edit(obs, skills=skills, extra=extra):
                    if not skills:
                        obs.pop("skills", None)
                    if extra:                     # 장면에 이미 노출된 등록부 동사가 있으면 그 줄들 뒤에 검사용 동사 한 줄
                        obs["common_extra"] = list(obs.get("common_extra") or []) + [EXTRA_PROBE]
                    else:                         # '추가 행동 없음' = 블록이 없는 관측 — 장면에 실제 노출 동사가 있어도 걷는다(p0.5.5b)
                        obs.pop("common_extra", None)
                _dec, calls = decide(sc, vt, lambda p, m: ('{"reason":"치환 검사","type":"wait"}', None), obs_edit=edit)
                p = calls[0]["prompt"]
                blk = _extra_block(p)
                hint_ok = (SKILL_HINT in p and SKILL_ANCHOR not in p) if skills else (SKILL_ANCHOR in p and SKILL_HINT not in p)
                extra_ok = (bool(blk) and blk[0] == words["header"] and blk[-1] == "- %s: %s" % (EXTRA_PROBE, EXTRA_PROBE_WORD)) if extra \
                    else (words["header"] not in p)
                if extra:
                    blocks.setdefault(name, set()).add("\n".join(blk))
                out[v][name] = {"skill_hint": SKILL_HINT in p, "anchor_left": SKILL_ANCHOR in p, "extra_block": len(blk),
                                "pass": hint_ok and extra_ok}
            out[v]["pass"] = all(out[v][n]["pass"] for n, _s, _e in combos_)
    same = all(len(b) == 1 for b in blocks.values())
    for v in out:
        out[v]["same_block"] = same                       # 추가 행동 블록이 모든 변형에서 같은 바이트(조합별)
        out[v]["pass"] = out[v]["pass"] and same
    bad = [v for v, r in out.items() if not r["pass"]]
    if bad:
        raise RuntimeError("SKILL 안내 치환·추가 행동 블록 검사 실패: %s" % ", ".join(bad))
    return out


# ── 정규화·채점 ───────────────────────────────────────────────────────────────────────────────────────
def normalize(action, obs):
    """행동 → (type, 대상 종류, 아이템 종류) + 기록용 세부(sub). 대상 종류 = ID 접두어 + 피처 종류:
    self · b 모험가 · npc 마을 인물 · m 몬스터 · f 물건·시설 · exit 계단·입구 · d 문 · w 길 · t 함정 · q 의뢰 · i 소지품 · mem 기억 속 대상."""
    typ, tid, item = action.get("type"), action.get("target"), action.get("item")
    kind, sub = "-", ""
    # 같은 동작은 같은 키(t06c 리뷰 2). 엔진이 대상을 안 읽는 동사(wait·rest·party_leave)는 대상을 적어 와도 무대상 —
    # 파서는 wait+self 를 받아 주지만 실행은 같다. 내 소지품을 대상으로 한 use(item 없음 또는 같은 칸)는 엔진에서 자신에게 쓰는 것과
    # 같은 길이다(CA.execute: item_id = item 또는 대상, 받는 사람 = 자신) → 'use self+<칸>'.
    if typ in TARGETLESS:
        tid = None
    own = {e["id"]: e["slot"] for e in obs.get("items", [])}
    if typ == "use" and tid in own and (not item or item == tid):
        tid, item = "self", tid
    if tid:
        if tid in ("self", obs.get("actor")):
            kind = "self"
        else:
            t = next((x for x in obs.get("targets", []) if x["id"] == tid), None)
            if t is None:
                kind, sub = "mem", next((e.get("kind", "") for e in (obs.get("known") or {}).get("statics", []) if e.get("id") == tid), "")
            elif t["kind"] == "feature":
                f = next((x for x in obs["sights"].get("features", []) if x["id"] == tid), {})
                kind = "npc" if f.get("type") == "npc" else "f"
                sub = f.get("name", "") if kind == "npc" else f.get("type", "")
            else:
                kind = KIND_OF.get(t["kind"], t["kind"])
                sub = t.get("slot") or t.get("name", "")
    ikind = next((e["slot"] for e in obs.get("items", []) if e["id"] == item), item) if item else "-"
    out = {"type": typ, "kind": kind, "item": ikind, "sub": sub}
    extra = {f: action[f] for f in CA.fields() if f not in CA.BASE_FIELDS and action.get(f)}   # p0.5.5 등록부 동사의 새 입력 칸(mode·request·loot …)
    if extra:                                                                                   #   — 있을 때만(옛 기록·상시 동사의 키는 그대로)
        out["fields"] = extra
    return out


def attempt_key(n):
    tail = "".join(" %s=%s" % kv for kv in sorted((n.get("fields") or {}).items()))   # p0.5.5: 같은 동사도 mode·request 가 다르면 다른 시도
    return "%s %s%s%s" % (n["type"], n["kind"], "" if n["item"] == "-" else "+" + n["item"], tail)


def result_key(n, label):
    return "%s → %s" % (attempt_key(n), label)


REISSUE = 5                             # 걷다가 '새로 본 것'으로 멈추면 같은 의도를 다시 내는 횟수 상한(모델이 고집한다고 가정)


# ── 상태 차이(t06c 리뷰 1) ────────────────────────────────────────────────────────────────────────────
# 행동 하나를 굴리는 동안의 세계 변화를 사진 두 장의 차이로 잰다. 가르는 기준:
#   · 행동 자체 변화(own) = 마지막 사건(엔진 판정을 실은 사건 — 접근 끝의 실행, 걸음의 도착) 직전 → 직후의 차이.
#     goto·explore·문 통과는 걷는 것이 곧 행동이라 전체 위치 변화도 행동 자체에 넣는다.
#     마지막 사건이 접근 걸음(엔진이 action_type 을 붙인 walk — 놓침·막힘·함정 등으로 실행 전에 끝남)이면 행동 자체 변화는 없다.
#   · 접근·이동이 지나가다 보물/물약을 주워 멈추면 새로 본 것과 같이 같은 행동을 다시 낸다(목표 칸이면 그게 결과).
#   · 부수 변화(side) = 시작 → 마지막 사건 직전의 차이(접근·이동·재발행 중에 일어난 일 — 지나가다 보물 줍기, 함정 밟기 등).
#     위치(내 걸음·동료와 자리 교대)와 발견(새로 본 것)은 수단이라 빼고, 발견은 seen 수로 따로 센다.
#   · 채점(효과 있음/변화 없음/실패)은 마지막 사건의 엔진 판정(+보정 둘)만 본다 — 부수 변화는 따로 기록·집계한다.
def _snap(d, bots, me):
    def body(b):
        rel = b.get("relations") or {}
        return {"pos": (b["x"], b["y"]), "HP": b.get("hp"), "살아 있음": bool(b.get("alive")), "층을 떠남": bool(b.get("won")),
                "보물": b.get("bag", 0), "물약": b.get("potions", 0), "축복 물약": b.get("boons", 0),
                "무기": (b.get("weapon") or {}).get("name"), "방어구": (b.get("armor") or {}).get("name"),
                "상태": ",".join(sorted(b.get("status") or {})), "힘": b.get("str"), "민첩": b.get("dex"),
                "관계": {"%s:%s" % (o, k): v.get("n", 0) for o, e in rel.items() if isinstance(e, dict)
                         for k, v in (e.get("bones") or {}).items() if isinstance(v, dict)},
                "만난 NPC": ",".join(sorted(b.get("npc_met") or ())),
                # p0.5.5(§7.4): 즉시 HP 가 안 바뀌는 새 효과도 차이로 보이게 — 새 상태 장부(§4.4 conditions)·새 소지품 칸(§4.3 ITEM_SLOTS 의
                #   물약·축복·장비 밖 칸). 아직 없는 칸이라 지금은 늘 빈 값(옛 기록 --rescore 도 그대로 돈다).
                "조건": ",".join(sorted(b.get("conditions") or {})),
                "소지품(그 밖)": {s: CA.item_value(b, s) for s in CA.ITEM_SLOTS.values()
                              if s not in ("potion", "boon", "weapon", "armor") and CA.item_value(b, s)}}
    q = getattr(d, "quests", None) or {}
    return {"me": body(me), "others": {b["char"]: body(b) for b in bots if b is not me},
            "mon": {"m%d" % m.id: (m.hp, bool(m.alive), (m.x, m.y), str(getattr(m, "state", ""))) for m in d.monsters},
            "feat": {"f%d" % f.id: (f.name, bool(f.concealed)) for f in d.features.values()},
            "trap": {"t%d" % i: (bool(t.hidden), bool(t.sprung)) for i, t in enumerate(d.traps)},
            "world": {"맡은 의뢰": ",".join(sorted(q.get("accepted") or {})), "다 쓴 오브젝트": len(getattr(d, "use_spent", None) or {}),
                      "파티": json.dumps(getattr(d, "parties", None), sort_keys=True, default=str)},
            "seen": frozenset(((me.get("ledger") or {}).get("statics") or {}))}


def _diff(a, b):
    """사진 두 장의 차이 → [[분류, 무엇, 전, 후]]. 분류: me · pos · others · monster · world · seen."""
    out = []

    def body(cat, who, x, y):
        for k in x:
            if k == "관계":
                for kk in sorted(set(x[k]) | set(y[k])):
                    if x[k].get(kk, 0) != y[k].get(kk, 0):
                        out.append([cat, "%s관계 %s" % (who, kk), x[k].get(kk, 0), y[k].get(kk, 0)])
            elif x[k] != y[k]:
                out.append(["pos" if k == "pos" else cat, who + k, list(x[k]) if k == "pos" else x[k], list(y[k]) if k == "pos" else y[k]])
    body("me", "", a["me"], b["me"])
    for c in sorted(set(a["others"]) & set(b["others"])):
        body("others", "b%s " % c, a["others"][c], b["others"][c])
    for m in sorted(set(a["mon"]) | set(b["mon"])):
        x, y = a["mon"].get(m), b["mon"].get(m)
        if x != y:
            if x and y and x[2] != y[2] and x[:2] == y[:2] and x[3] == y[3]:
                out.append(["monster", m + " 위치", list(x[2]), list(y[2])])
            else:
                out.append(["monster", m, list(x) if x else None, list(y) if y else None])
    for f in sorted(set(a["feat"]) | set(b["feat"])):
        x, y = a["feat"].get(f), b["feat"].get(f)
        if x != y:
            cat = "seen" if (x and y and x[1] and not y[1]) else "world"
            out.append([cat, "%s %s" % (f, (x or y)[0]), "있음" if x else "없음", "없음" if not y else ("숨음" if y[1] else "있음")])
    for t in sorted(a["trap"]):
        x, y = a["trap"][t], b["trap"].get(t)
        if x != y:
            out.append(["seen" if (x[0] and not y[0] and not y[1]) else "world", t + " 함정",
                        "숨음" if x[0] else "발동" if x[1] else "드러남", "숨음" if y[0] else "발동" if y[1] else "드러남"])
    for k in a["world"]:
        if a["world"][k] != b["world"][k]:
            out.append(["world", k, a["world"][k], b["world"][k]])
    new = len(b["seen"] - a["seen"])
    if new:
        out.append(["seen", "새로 본 것", 0, new])
    return out


def _change_key(c):
    """집계용 변화 이름 — 번호(f19·t1·m1·b1)를 떼서 장면·변형을 넘어 같은 종류끼리 모이게 한다."""
    cat, what, x, y = c
    if cat == "monster":
        return "monster:" + ("위치" if what.endswith("위치") else "HP·생사·상태")
    if what[:1] in "ft" and what[1:2].isdigit():
        return "%s:%s %s→%s" % (cat, what.split(" ", 1)[1], x, y)
    if cat == "others":
        return "others:" + what.split(" ", 1)[1]
    return "%s:%s" % (cat, what)


def _discovery_stop(ev):
    """걷던 중 행동과 무관한 일로 선 걸음인가 — 새로 본 것(엔진은 접촉 전에 멈추고 다시 묻는다)·지나가다 주운 보물/물약.
    함정 발동·피격·길막힘·놓침은 아니다(그건 그 걸음의 결과로 남긴다)."""
    if ev.get("type") != "walk":
        return False
    r = ev.get("result")
    return r in ("sighted", "zone_enter", "treasure", "potion") or (r == "encounter" and not ev.get("trap") and not ev.get("hurt"))


def resolve_once(scene, action, seed):
    """장면 사본에서 결정 하나를 결과가 나올 때까지 굴린다 — 나머지 세계는 멈춰 있다(몹·동료·행인 턴 없음, 판단 주체만 움직인다).
    ① d.act → 주문(order)이 남은 동안 틱마다 step_order(러너의 자동보행 그대로).
    ② 걸음이 새로 본 것으로 멈췄으면(_discovery_stop) 같은 행동을 다시 낸다(최대 REISSUE회) — 길(w)은 이번 관측에서만 유효한
       ID 라, 그 참조의 기준(관측 차례·출발 칸)만 지금 자리로 옮겨 같은 종점으로 다시 걷게 한다.
    ③ 판정 = 엔진 resolution.status, 보정 둘(engine_status 에 원래 값을 남긴다):
       · 엔진이 success 로 둔 결과의 꼬리표 키가 'misc'(헛손질·파티 결성 안 됨·입구에서 막힘 등) → 실패.
         CA.decorate 가 모르는 결과 코드를 success 로 두는 구멍.
       · goto/explore 의 걸음이 목표 칸 위에서 끝났는데 엔진이 failed(걸음 멈춤 사건: 함정 밟음·계단 도착 at_exit) → 성공.
         goto 의 뜻은 그 칸에 닿는 것이다(goto t = 함정을 밟는다 — 행동 사실 시트).
    ④ 상태 차이: 위 '상태 차이' 절의 기준으로 own(행동 자체) · side(부수) · seen(새로 본 것 수)을 남긴다."""
    d, bots, _obs, me = scene.thaw()
    d.rng.seed(seed)
    act = {k: copy.deepcopy(v) for k, v in action.items() if k in CA.fields()}   # p0.5.5: 등록부 동사의 새 입력 칸도
    act["src"] = "haiku"
    rng0 = d.rng.getstate()
    steps = reissued = 0
    s0 = before_last = _snap(d, bots, me)
    try:
        goal = CA.entity(d, me, act["target"], bots) if act.get("target") else None
        goal = tuple(goal[1]) if goal else None
        ev = [d.act(me, dict(act), bots)]
        while True:
            while me.get("order") and me.get("alive") and not me.get("won") and steps < MAX_STEPS:
                d.turn += 1
                before_last = _snap(d, bots, me)
                ev.append(d.step_order(me, bots))
                steps += 1
            picked_goal = ev[-1].get("result") in ("treasure", "potion") and goal is not None and (me["x"], me["y"]) == goal
            if (me.get("order") or not me.get("alive") or me.get("won") or reissued >= REISSUE or not _discovery_stop(ev[-1])
                    or picked_goal):                 # 목표 칸의 보물·물약을 주워 멈췄으면 그게 결과(goto 보물 = 줍기)
                break
            ref = (me.get("_target_refs") or {}).get(act.get("target"))
            if ref and ref.get("kind") == "way":
                ref.update(epoch=me.get("_way_epoch"), origin=(me["x"], me["y"]))
            reissued += 1
            before_last = _snap(d, bots, me)
            ev.append(d.act(me, dict(act), bots))
    except Exception as e:                    # 엔진이 죽는 조합 = 게임 코드 확인 후보(보고에 실린다)
        return {"status": "crash", "engine_status": "crash", "label": "엔진 예외 %s" % type(e).__name__, "tag": "crash",
                "fact": str(e)[:80], "result": None, "reason": None, "steps": steps, "reissued": reissued, "rng": True,
                "own": [], "side": [], "seen": 0}
    s1 = _snap(d, bots, me)
    final = ev[-1]
    # 마지막 사건이 접근 걸음(엔진이 action_type 을 붙인 walk)이면 행동은 실행되지 못했다 — 행동 자체 변화 없음, 그동안의 변화는 전부 부수.
    # 접근 없는 걸음(goto·explore·문 통과의 walk)은 걷는 것이 행동이라 전체 위치 변화를 행동 자체에 넣는다.
    approach_walk = final.get("type") == "walk" and "action_type" in final
    own, upto = ([], s1) if approach_walk else (_diff(before_last, s1), before_last)
    if final.get("type") == "walk" and not approach_walk and s0["me"]["pos"] != s1["me"]["pos"]:
        own = [c for c in own if not (c[0] == "pos" and c[1] == "pos")] + [["pos", "pos", list(s0["me"]["pos"]), list(s1["me"]["pos"])]]
    side = [c for c in _diff(s0, upto) if c[0] not in ("pos", "seen") and not (c[0] == "others" and c[1].endswith(" pos"))]
    seen = sum(c[3] if c[1] == "새로 본 것" else 1 for c in _diff(s0, s1) if c[0] == "seen")
    res = final.get("resolution") or {}
    engine = "timeout" if me.get("order") else (res.get("status") or "unknown")
    key, label, fact = G.event_tags(final)[0]
    if goal is None and act.get("target"):    # 기억 속 대상(시야 밖에서 goto)은 엔진의 대상 해석기로 자리를 찾는다
        end = d._resolve_target(act["target"], bots)
        goal = tuple(end[1]) if end else None
    status = engine
    if engine == "success" and key == "misc":
        status = "failed"
    elif (engine == "failed" and act["type"] in ("goto", "explore") and final.get("type") == "walk" and goal
          and (me["x"], me["y"]) == goal):
        status = "success"
    return {"status": status, "engine_status": engine, "label": label, "tag": key, "fact": str(fact)[:80],
            "result": final.get("result"), "reason": res.get("reason"), "steps": steps, "reissued": reissued,
            "rng": d.rng.getstate() != rng0, "own": own, "side": side, "seen": seen}


def resolve(scene, action, seeds=SEEDS):
    outs = []
    for s in seeds:
        o = resolve_once(scene, action, s)
        outs.append(o)
        if not o["rng"]:
            break                             # 주사위를 안 쓴 조합 — 시드와 무관하게 같은 결과
    return outs


def classify(outs):
    sts = {o["status"] for o in outs}
    if "success" in sts:
        return "효과"
    if sts & {"failed", "timeout", "crash", "unknown", None}:
        return "실패"
    return "변화 없음"


def corrections(rows):
    """벤치 판정 보정(resolve_once ③)이 걸린 행 수 — 시드 결과 중 하나라도 보정되면 1."""
    c = {"misc": 0, "goal": 0}
    for r in rows:
        outs = r.get("outcomes") or []
        c["misc"] += any(o.get("engine_status") == "success" and o["status"] == "failed" for o in outs)
        c["goal"] += any(o.get("engine_status") == "failed" and o["status"] == "success" for o in outs)
    return c


def score(scene, action):
    """결정(파서를 통과한 행동) → 정규화 · 시드별 결과 · 분류 · 효과 결과 키 · 부수 변화 · 판정-상태 대조.
    대조(채점엔 안 쓴다 — 엔진 판정과 실제 상태 차이가 어긋나는 자리를 보이려는 것):
      success_no_change = 효과로 셌는데 성공한 시드 모두 행동 자체 변화가 없다(제자리 도착·만피 휴식·기다림 끝 등)
      change_not_effect = 효과가 아닌데 행동 자체 변화(위치·발견 제외)가 있다."""
    n = normalize(action, scene.obs)
    outs = resolve(scene, action)
    cat = classify(outs)
    eff = sorted({result_key(n, o["label"]) for o in outs if o["status"] == "success"})
    side = sorted({_change_key(c) for o in outs for c in o["side"]})
    flags = []
    if cat == "효과" and not any(o["own"] for o in outs if o["status"] == "success"):
        flags.append("success_no_change")
    if cat != "효과" and any(c[0] not in ("pos", "seen") for o in outs for c in o["own"]):
        flags.append("change_not_effect")
    return {"norm": n, "attempt": attempt_key(n), "outcomes": outs, "category": cat, "effects": eff, "side": side, "flags": flags}


# ── 가능 공간 ─────────────────────────────────────────────────────────────────────────────────────────
def _ext_field_combos(spec):
    """등록부 동사의 새 입력 칸 조합 — 허용 값이 정해진 칸만 펼친다(선택 칸은 '없음'도 하나). 자유 문구 칸은 비우고, 필수면 자리표 '?'."""
    out = [{}]
    req = set(spec.get("required") or ())
    for name, allowed in sorted((spec.get("fields") or {}).items()):
        vals = list(allowed) if allowed else ["?"] if name in req else []
        opts = vals + ([] if name in req else [None])
        out = [{**o, **({name: v} if v is not None else {})} for o in out for v in opts]
    return out


def exposed_types(obs):
    """이번 화면에 제시된 동사 — 상시 9개 + 노출된 추가 행동 + 관측에 실린 SKILL + 파티 판의 PARTY(가능 공간의 둘째 분모)."""
    return (set(CA.common_types(obs)) | {s["id"] for s in obs.get("skills", [])}
            | (set(CA.PARTY) if obs.get("partyform") is not None else set()))


def combos(obs):
    """type × 보이는 대상 × 소지품 전수(COMMON + 등록부 전체 + 관측에 실린 SKILL + 파티 판의 PARTY). goto 는 기억 속 정적 대상도.
    p0.5.5: 등록부 동사는 이번에 노출됐든 아니든 전부 넣는다 — 노출 밖 알려진 동사를 시도할 자유도 공간이다(분모는 possible_space 가 둘로 가른다)."""
    types = (list(CA.COMMON) + list(CA.COMMON_EXT) + [s["id"] for s in obs.get("skills", [])]
             + (list(CA.PARTY) if obs.get("partyform") is not None else []))
    tids = ["self"] + [t["id"] for t in obs.get("targets", []) if t["id"] not in ("self", obs.get("actor"))]
    mem = [e["id"] for e in (obs.get("known") or {}).get("statics", []) if e.get("id") and e["id"] not in tids]
    items = [e["id"] for e in obs.get("items", [])]
    for typ in types:
        spec = CA.COMMON_EXT.get(typ)
        if spec is not None:
            for t in (tids if spec.get("target", True) else [None]):
                for fv in _ext_field_combos(spec):
                    yield {"type": typ, **({"target": t} if t else {}), **fv}
            continue
        if typ in TARGETLESS:
            yield {"type": typ}
            yield {"type": typ, "target": "self"}   # 파서가 받는 꼴이라 공간에도 넣는다(정규화로 같은 키가 된다)
            continue
        for t in tids + (mem if typ == "goto" else []):
            if typ == "give":
                for i in items:
                    yield {"type": typ, "target": t, "item": i}
            elif typ == "use":
                yield {"type": typ, "target": t}
                for i in items:
                    yield {"type": typ, "target": t, "item": i}
            elif typ == "bond":
                yield {"type": typ, "target": t, "form": BOND_FORM}
            else:
                yield {"type": typ, "target": t}


def possible_space(scene):
    """장면의 모든 조합을 게임 파서(brains._compose_pick) → 엔진으로 굴린다. 파서가 거절한 조합은 공간 밖(형식 오류).
    분모 둘(p0.5.5 §7.4): 전체 = 등록부 전체 / 노출 = 이번 화면에 제시된 동사만(exposed_types). 등록부가 빈 지금은 둘이 같다."""
    rows, eff, eff_x, rejected = [], set(), set(), 0
    shown = exposed_types(scene.obs)
    for c in combos(scene.obs):
        parsed, err = brains._compose_pick(dict(c), scene.obs)
        if err:
            rejected += 1
            continue
        s = score(scene, parsed)
        rows.append({"combo": c, "exposed": c["type"] in shown, **s})
        eff.update(s["effects"])
        if c["type"] in shown:
            eff_x.update(s["effects"])
    cats = collections.Counter(r["category"] for r in rows)
    noeff = collections.defaultdict(set)      # 변화 없음 시도 → 대상 세부(같은 'use f' 라도 상자는 효과, 건물은 변화 없음일 수 있다)
    for r in rows:
        if r["category"] == "변화 없음":
            noeff[r["attempt"]].add(r["norm"]["sub"] or "")
    return {"rows": rows, "effects": sorted(eff), "n_combos": len(rows), "n_rejected": rejected, "categories": dict(cats),
            "effects_exposed": sorted(eff_x), "n_combos_exposed": sum(1 for r in rows if r["exposed"]),
            "noeffect_attempts": sorted(noeff), "noeffect_sub": {a: sorted(x for x in v if x) for a, v in sorted(noeff.items())}}


# ── 판단 ──────────────────────────────────────────────────────────────────────────────────────────────
def _stable(*parts):
    return int(hashlib.sha256("|".join(map(str, parts)).encode("utf-8")).hexdigest()[:12], 16)


def canned_caller(scene, space, variant, rep):
    """dummy 두뇌 — 장면의 유효 조합에서 결정론적으로 하나를 고른 JSON. 일곱에 하나쯤은 첫 응답을 없는 대상으로 내어
    입력 오류 → 재요청(claude_brain 의 1회) 경로까지 굴린다. 네트워크 0."""
    pool = [r["combo"] for r in space["rows"]]
    calls = []

    def call(prompt, model):
        k = len(calls)
        calls.append(1)
        r = random.Random(_stable(scene.name, variant, rep, k))
        if k == 0 and _stable(scene.name, variant, rep) % 7 == 0:
            return json.dumps({"reason": "[dummy] 없는 대상을 고른다", "type": "goto", "target": "x999"}, ensure_ascii=False), None
        c = r.choice(pool)
        return json.dumps({"reason": "[dummy] 고정 응답 %s" % c["type"], **c, "say": ""}, ensure_ascii=False), None
    return call


class InfraFailure(Exception):
    """호출 자체가 끝내 실패했다(한도·타임아웃·서버·연결) — 그 판단은 결측. 모델의 형식 오류가 아니다."""

    def __init__(self, labels):
        super().__init__(labels[-1])
        self.labels = labels


def infra_kind(why):
    """호출 실패 라벨의 갈래(t06c 리뷰 3). brains 의 라벨 문법: '타임아웃 Ns' · '호출 실패 <예외 타입>' · '빈 응답 rc=<HTTP>[ | 사유]'.
    반환 'fatal'(설정 문제 — 다시 불러도 같다: 키 없음·모델 이름·주소·호출 상한·4xx) | 'infra'(다시 부를 뜻이 있다: 타임아웃·연결·408·429·5xx)
    | None(응답은 왔다 — 빈 답·안전 차단·JSON 불량은 모델 쪽 결과라 게임처럼 claude_brain 이 다룬다)."""
    s = str(why or "")
    if not s:
        return None
    if s == brains.API_LIMIT_LABEL or (s.startswith("호출 실패 ") and s.split(" ", 2)[-1] in ("NoAPIKey", "UnknownModel", "InvalidBaseURL")):
        return "fatal"
    if s.startswith("타임아웃") or s.startswith("호출 실패 "):
        return "infra"
    m = re.search(r"rc=(\d+)", s)
    if m and m.group(1) != "200":
        code = int(m.group(1))
        return "infra" if code in (408, 429) or code >= 500 else "fatal"
    return None


class Pacer:
    """호출 함수(real)를 순차·간격 유지로 감싼다. 인프라 실패는 같은 프롬프트로 물러났다 다시 부르고(BACKOFF 만큼),
    끝내 실패하면 InfraFailure — 게임의 '입력 오류 재요청'(오류 덧말이 붙은 다른 프롬프트)으로 흘리지 않는다. 설정 문제는 실행을 멈춘다."""

    def __init__(self, real, interval, backoff=(30, 60, 120)):
        self.real, self.interval, self.backoff = real, interval, tuple(backoff)
        self.last, self.sent, self.retries = 0.0, 0, 0

    def __call__(self, prompt, model):
        labels = []
        for i in range(len(self.backoff) + 1):
            wait = self.interval - (time.time() - self.last)
            if wait > 0:
                time.sleep(wait)
            self.last = time.time()
            self.sent += 1
            out, why = self.real(prompt, model)
            kind = infra_kind(why)
            if kind == "fatal":
                raise SystemExit("본 실행 중단 — %s(지금까지의 응답은 responses.jsonl 에 남아 있다)" % why)
            if kind != "infra":
                return out, why
            labels.append(why)
            if i < len(self.backoff):
                self.retries += 1
                if self.backoff[i]:
                    print("    [대기] %s — %ds 뒤 다시" % (why, self.backoff[i]), flush=True)
                    time.sleep(self.backoff[i])
        raise InfraFailure(labels)


def mock_infra(call, key):
    """dummy --mock-infra 의 고장 주입(결정론): 판단 열셋 중 하나는 끝까지 타임아웃(결측), 둘은 첫 전송만 429(다시 불러 회복)."""
    h, sent = _stable(key, "infra") % 13, []

    def wrapped(prompt, model):
        sent.append(1)
        if h == 0:
            return "", "타임아웃 60s"
        if h in (1, 2) and len(sent) == 1:
            return "", "빈 응답 rc=429 | RESOURCE_EXHAUSTED"
        return call(prompt, model)
    return wrapped


def decide(scene, variant, caller, obs_edit=None):
    """게임 경로 그대로 한 번 판단한다 — claude_brain(시트 + 이 변형의 지침 + 관측, 입력 오류면 1회 재요청).
    obs_edit(관측) = 판단 전 관측 사본 손질(4조합 검사 전용 — 채점 판단에는 안 쓴다)."""
    d, bots, obs, me = scene.thaw()
    if obs_edit:
        obs_edit(obs)
    roster = [] if scene.solo else bots
    calls = []

    def recorder(prompt, model):
        out, why = caller(prompt, model)
        calls.append({"prompt": prompt, "raw": out, "why": why})
        return out, why

    with patch.object(brains, "COMPOSE_PROMPT", variant["text"]), patch.object(brains, "COMPOSE_PROMPT_SOLO", variant["solo"]), \
            patch.object(brains, "_call_claude", recorder):
        dec = brains.claude_brain(obs, ACTOR, me, roster, scene.solo)
    return dec, calls


def score_response(scene, calls, dec):
    """한 판단의 채점 — 첫 응답의 형식 오류 여부(게임 파서로 다시 읽는다)와 게임이 실행할 최종 결정의 결과."""
    _d, bots, obs, _me = scene.thaw()
    first = brains._parse_decision(calls[0]["raw"], calls[0]["why"], obs, ACTOR, [] if scene.solo else bots) if calls else {"src": "error"}
    row = {"first_error": first.get("input_error") if first.get("src") == "error" else None,
           "final_error": dec.get("input_error") if dec.get("src") == "error" else None}
    if dec.get("src") == "error":
        row.update(norm=None, attempt=None, outcomes=[], category="형식 오류", effects=[], side=[], flags=[])
    else:
        row.update(score(scene, {k: dec[k] for k in CA.fields() if dec.get(k) is not None}))
    row["prompt_chars"] = len(calls[0]["prompt"]) if calls else None   # p0.5.5 지표 '판단당 프롬프트 길이'(첫 요청 — 재요청 덧말 제외)
    return row


# ── 집계 ──────────────────────────────────────────────────────────────────────────────────────────────
CATS = ("효과", "변화 없음", "실패", "형식 오류")


def summarize(rows, spaces):
    """변형별 지표. 결측(인프라 실패로 판단이 없는 행)은 모든 분모에서 빼고 따로 센다."""
    out = {}
    for v in sorted({r["variant"] for r in rows}, key=lambda x: VARIANTS.index(x) if x in VARIANTS else 99):
        v_all = [r for r in rows if r["variant"] == v]
        vr = [r for r in v_all if r["category"] != "결측"]
        per = {}
        for s in spaces:
            sr = [r for r in vr if r["scene"] == s]
            if not sr:
                continue
            eff = sorted({k for r in sr for k in r["effects"]})
            space_eff = set(spaces[s]["effects"])
            subs = collections.defaultdict(set)
            for r in sr:
                if r["category"] == "변화 없음":
                    subs[r["attempt"]].add(r["norm"]["sub"] or "")
            per[s] = {"n": len(sr), "effects": eff, "n_effects": len(eff),
                      "noeffect": sorted(subs), "noeffect_sub": {a: sorted(x for x in ss if x) for a, ss in subs.items()},
                      "reach": (len(set(eff) & space_eff) / len(space_eff)) if space_eff else None,
                      "outside_space": sorted(set(eff) - space_eff),
                      "side": {r["attempt"]: r["side"] for r in sr if r["side"]},
                      "categories": dict(collections.Counter(r["category"] for r in sr))}
        n = len(vr)
        hit = sum(len(set(p["effects"]) & set(spaces[s]["effects"])) for s, p in per.items())
        tot = sum(len(spaces[s]["effects"]) for s in per)
        sx = {s: set(spaces[s].get("effects_exposed", spaces[s]["effects"])) for s in per}   # p0.5.5 둘째 분모 — 이번 화면에 제시된 동사의 효과
        hit_x = sum(len(set(p["effects"]) & sx[s]) for s, p in per.items())
        tot_x = sum(len(sx[s]) for s in per)
        chars = [r["prompt_chars"] for r in vr if r.get("prompt_chars")]
        out[v] = {"n": n, "per_scene": per,
                  "n_effects": sum(p["n_effects"] for p in per.values()),
                  "n_noeffect": sum(len(p["noeffect"]) for p in per.values()),
                  "reach": hit / tot if tot else None,
                  "reach_exposed": hit_x / tot_x if tot_x else None,
                  "prompt_chars_mean": round(sum(chars) / len(chars)) if chars else None,
                  "first_error_rate": sum(1 for r in vr if r["first_error"]) / n if n else None,
                  "final_error_rate": sum(1 for r in vr if r["final_error"]) / n if n else None,
                  "categories": {c: sum(1 for r in vr if r["category"] == c) for c in CATS},
                  "n_side": sum(1 for r in vr if r["side"]),
                  "side_kinds": dict(collections.Counter(k for r in vr for k in r["side"]).most_common()),
                  "flags": dict(collections.Counter(f for r in vr for f in r["flags"])),
                  "missing": len(v_all) - n,
                  "infra_retries": sum(r.get("infra_retries", 0) for r in v_all),
                  "types": dict(collections.Counter((r["norm"] or {}).get("type", "(오류)") for r in vr).most_common())}
    return out


def _pct(x):
    return "-" if x is None else "%.1f%%" % (100 * x)


def write_report(run_dir, summary, spaces, meta):
    L = ["# 행동 자유도 벤치마크 — %s" % meta["run_id"], "",
         "두뇌 `%s` · 장면 %d · 변형 %d · 반복 %d · 시드 %s · 장면 시드 %d" % (
             meta["brain"], len(spaces), len(summary), meta["reps"], list(SEEDS), SCENE_SEED), "",
         "- 시도 = `type 대상종류[+아이템]` (self·b 모험가·npc 마을 인물·m 몬스터·f 물건·시설·exit·d 문·w 길·t 함정·q 의뢰·i 소지품·mem 기억 속 대상)",
         "- 효과 결과 = 효과가 난 `시도 → 결과 꼬리표`의 서로 다른 수(장면별로 세어 더함) · 도달률 = 모델이 낸 효과 결과 ÷ 가능 공간의 효과 결과",
         "- 변화없음 시도 = 변화 없음으로 끝난 서로 다른 시도(배선 후보) · 형식오류(첫 응답) = 재요청 전 첫 응답이 게임 파서에서 거절된 비율"]
    cor = meta.get("corrections") or {}
    sp_c, rs_c = cor.get("space") or {}, cor.get("responses") or {}
    L.append("- 판정 보정(벤치 — 엔진 CA.decorate 구멍): ① 엔진 success 인데 꼬리표가 misc(헛손질·파티 결성 안 됨 등) → 실패 "
             "② goto/explore 가 목표 칸에서 끝났는데 엔진 failed(함정 밟음·계단 at_exit) → 성공 · 걸린 조합 수: 가능 공간 ①%s ②%s / "
             "모델 응답 ①%s ②%s (원래 값은 outcomes[].engine_status)" % (sp_c.get("misc", "-"), sp_c.get("goal", "-"),
                                                                      rs_c.get("misc", "-"), rs_c.get("goal", "-")))
    sp_rows = [r for sp in spaces.values() for r in sp.get("rows", [])]
    L.append("- 행동 자체 vs 부수(상태 차이): 행동 자체 = 마지막 사건(엔진 판정을 실은 실행·도착) 직전→직후 차이(goto·explore 는 전체 걸음 포함) · "
             "부수 = 그 앞(접근·이동·재발행) 동안의 차이에서 위치·발견을 뺀 것. 채점은 행동 자체의 엔진 판정만, 부수는 '부수효과' 칸에 따로 · "
             "판정-상태 대조(가능 공간): 효과인데 행동 자체 변화 없음 %d조합 · 효과 아닌데 행동 자체 변화 있음 %d조합" % (
                 sum("success_no_change" in r["flags"] for r in sp_rows), sum("change_not_effect" in r["flags"] for r in sp_rows)))
    L.append("- 인프라 실패(타임아웃·연결 오류·HTTP 408/429/5xx)는 같은 프롬프트로 최대 3회 다시 부르고, 끝내 실패하면 결측 — "
             "판단·형식오류율·도달률의 분모에서 뺀다(설정 문제·호출 상한은 실행을 멈춘다)")
    chk = meta.get("skill_hint_check") or {}
    if chk and "skipped" not in chk:
        four = all("same_block" in r for r in chk.values())   # p0.5.5 전 기록(--rescore 가 물려받은 meta)은 SKILL 치환만 본 검사
        L.append("- %s: %d/%d 변형 통과(앵커 문장을 덧붙인 변형: %s)" % (
            "SKILL 안내 치환·추가 행동 블록 검사(SKILL 유무 × 추가 행동 유무 4조합)" if four else "SKILL 안내 치환 검사(원 실행 — p0.5.5 전 꼴)",
            sum(1 for r in chk.values() if r["pass"]), len(chk), ", ".join(v for v, r in chk.items() if r["anchor_added"]) or "없음"))
    L.append("- 도달률(노출) = 이번 화면에 제시된 동사(상시 9개 + 노출된 추가 행동 + SKILL + PARTY)의 효과 결과만 분모로 — 등록부가 비면 도달률과 같다")
    L += ["", "## 장면별 가능 공간", "", "| 장면 | 조합(노출) | 효과 결과(서로 다른, 노출) | 변화 없음 시도(서로 다른) | 부수효과 조합 | 지문 |",
          "|---|---|---|---|---|---|"]
    for s, sp in spaces.items():
        L.append("| %s | %d (%d) | %d (%d) | %d | %d | `%s` |" % (
            s, sp["n_combos"], sp.get("n_combos_exposed", sp["n_combos"]), len(sp["effects"]), len(sp.get("effects_exposed", sp["effects"])),
            len(sp["noeffect_attempts"]), sum(1 for r in sp.get("rows", []) if r["side"]), meta["fingerprints"].get(s, "")))
    L += ["", "## 변형별 지표(전체)", "",
          "| 변형 | 판단 | 결측(인프라) | 효과 결과 | 변화없음 시도 | 도달률 | 도달률(노출) | 형식오류(첫 응답) | 효과/변화없음/실패/형식오류 | 부수효과(판단) | 판단당 프롬프트(자) | 행동 분포 |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for v, m in summary.items():
        L.append("| %s | %d | %d (재호출 %d) | %d | %d | %s | %s | %s | %s | %d | %s | %s |" % (
            v, m["n"], m["missing"], m["infra_retries"], m["n_effects"], m["n_noeffect"], _pct(m["reach"]), _pct(m.get("reach_exposed")),
            _pct(m["first_error_rate"]), "/".join(str(m["categories"][c]) for c in CATS), m["n_side"],
            m.get("prompt_chars_mean") if m.get("prompt_chars_mean") is not None else "-", " ".join("%s %d" % kv for kv in m["types"].items())))
    L += ["", "## 장면별 도달률", "", "| 변형 | " + " | ".join(spaces) + " |", "|---|" + "---|" * len(spaces)]
    for v, m in summary.items():
        L.append("| %s | %s |" % (v, " | ".join(("%s (%d)" % (_pct(m["per_scene"][s]["reach"]), m["per_scene"][s]["n_effects"]))
                                                 if s in m["per_scene"] else "-" for s in spaces)))
    noeff, subs, outside = collections.Counter(), collections.defaultdict(set), []
    for v, m in summary.items():
        for s, p in m["per_scene"].items():
            for a in p["noeffect"]:
                noeff[(s, a)] += 1
                subs[(s, a)].update(p["noeffect_sub"].get(a, ()))
            if p["outside_space"]:
                outside.append("- ⚠ %s · %s: 가능 공간 밖의 효과 결과 %s" % (v, s, ", ".join(p["outside_space"])))
    L += outside and ["", "## 확인 필요 — 모델의 효과 결과가 가능 공간에 없다(전수 대입이 놓친 조합)", ""] + outside or []
    L += ["", "## 변화 없음으로 끝난 시도(배선 후보) — 장면 · 시도(대상 세부) · 몇 변형에서 나왔나", ""]
    L += ["- %s · `%s`%s × %d" % (s, a, ("(%s)" % "·".join(sorted(subs[(s, a)]))) if subs[(s, a)] else "", n)
          for (s, a), n in sorted(noeff.items(), key=lambda kv: (-kv[1], kv[0]))] or ["- 없음"]
    side = collections.Counter()
    for m in summary.values():
        for s, p in m["per_scene"].items():
            for a, ks in p["side"].items():
                side[(s, a, " · ".join(ks))] += 1
    L += ["", "## 부수 효과(행동과 무관하게 접근·이동 중 일어난 변화) — 장면 · 시도 → 변화 · 몇 변형에서 나왔나", ""]
    L += ["- %s · `%s` → %s × %d" % (s, a, k, n) for (s, a, k), n in sorted(side.items(), key=lambda kv: (-kv[1], kv[0]))] or ["- 없음"]
    with open(os.path.join(run_dir, "summary.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")
    return "\n".join(L)


# ── 연속 판단 장면(p0.5.5, master_plan §7.4) ──────────────────────────────────────────────────────────
SEQ_MAX = 6                             # 한 장면에서 판단 주체가 내리는 판단 상한 ⚠️임시(§7.4)
SEQ_TICKS = 240                         # 틱 상한(걷기 포함 — 넘으면 거기서 끝, 목표 미달)
SCRIPT_WAIT = {"type": "wait", "say": "", "reason": "[대본] 기다린다", "src": "script"}


def _free_near(d, bots, b, r):
    """b 의 시야 안 · 체비셰프 r 안 · 빈 바닥(피처·몹·사람 없음) 칸 하나 — 가까운 순, 같으면 (y,x) 순(결정론, rng 무접촉)."""
    seen = d.visible_cells(b["x"], b["y"])
    taken = {(o["x"], o["y"]) for o in bots}
    cells = [(x, y) for y in range(b["y"] - r, b["y"] + r + 1) for x in range(b["x"] - r, b["x"] + r + 1)
             if 0 <= x < d.w and 0 <= y < d.h and (x, y) in seen and (x, y) not in taken and (x, y) != (b["x"], b["y"])
             and d.grid[y][x] == G.FLOOR and d.feature_at(x, y) is None and d.monster_at(x, y) is None]
    if not cells:
        raise ValueError("장면 자리: %s 곁에 빈 바닥이 없다" % b["char"])
    return min(cells, key=lambda c: (max(abs(c[0] - b["x"]), abs(c[1] - b["y"])), c[1], c[0]))


def q1_potion_relay():
    """던전 방 — 동료 두란이 크게 다쳤고(HP 3) 내 물약은 없다. 내 곁 바닥에 회복 물약 하나. 목표: 동료가 회복되거나 물약을 받는다."""
    d, bots = _floor(drop_monsters=(4,))
    me, ally = _bot(bots, ACTOR), _bot(bots, ALLY)
    _place(d, me, (4, 27))
    _place(d, ally, (7, 29))
    me["potions"] = 0
    ally["hp"] = 3
    G.IA.place(d, "potion", *_free_near(d, bots, me, 2))
    return d, bots, {}


def q1_goal(d, bots, s0):
    ally = _bot(bots, ALLY)
    return ally["hp"] > s0["ally_hp"] or ally.get("potions", 0) > s0["ally_potions"]


def q2_guild_errand():
    """마을 — 모험가 길드 문턱 곁(s1 과 같은 자리). 목표: 게시판 의뢰를 맡고, 마을 사람에게 말을 건다(둘 다)."""
    d, bots = _town()
    _place(d, _bot(bots, ACTOR), (70, 19))
    return d, bots, _greetings(d, bots, {})


def q2_goal(d, bots, s0):
    me = _bot(bots, ACTOR)
    return bool((getattr(d, "quests", None) or {}).get("accepted")) and len(me.get("npc_met") or ()) > s0["npc_met"]


def _seq_s0(d, bots):
    ally, me = _bot(bots, ALLY), _bot(bots, ACTOR)
    return {"ally_hp": ally["hp"], "ally_potions": ally.get("potions", 0), "npc_met": len(me.get("npc_met") or ())}


# 이름 → (설명, 장면, 목표 판정(d, bots, 시작 사진) → bool, 다른 캐릭터 대본 {char: [결정 …]} — 다 쓰면 wait)
SEQ_SCENES = collections.OrderedDict([
    ("q1_potion_relay", ("던전 방 — 다친 동료(HP 3), 내 물약 없음, 곁 바닥에 물약 하나 → 동료 회복/건네기", q1_potion_relay, q1_goal, {})),
    ("q2_guild_errand", ("마을 길드 문턱 — 의뢰 맡기 + 마을 사람에게 말 걸기", q2_guild_errand, q2_goal, {})),
])


def seq_dummy_caller(name, variant, rep, cur):
    """연속 장면 dummy 두뇌 — 지금 관측(cur['obs'])의 파서 통과 조합 중 결정론적으로 하나 + 매 판단 note 한 줄(기억 유지 확인용).
    판단 일곱에 하나쯤은 첫 응답을 없는 대상으로 내어 재요청 경로까지 굴린다. 네트워크 0."""
    def call(prompt, model):
        k, n = cur["k"], cur["calls"]
        cur["calls"] += 1
        obs = cur["obs"]
        if n == 0 and _stable(name, variant, rep, k) % 7 == 0:
            return json.dumps({"reason": "[dummy] 없는 대상을 고른다", "type": "goto", "target": "x999"}, ensure_ascii=False), None
        pool = [c for c in combos(obs) if not brains._compose_pick(dict(c), obs)[1]]
        c = random.Random(_stable(name, variant, rep, k, n)).choice(pool) if pool else {"type": "wait"}
        return json.dumps({"reason": "[dummy] 고정 응답 %s" % c["type"], **c, "say": "", "note": "dummy 기억 %d" % k},
                          ensure_ascii=False), None
    return call


def run_sequence(name, variant, caller_for, rep, seed):
    """연속 판단 장면 한 판 — 판단 주체가 최대 SEQ_MAX 판단을 이어 간다(세계 안에서, 기억·note 유지). caller_for(cur) → 호출 함수.
    틱 하나 = 러너 _tick_world 의 축소판: (들은 말 보관 합치기) → think_all(판단 주체만 실제 claude_brain, 다른 캐릭터는 대본) →
    판단 없는 몸은 step_order / 판단한 몸은 d.act → 몹 턴 → 행인 걸음 → 말 배달(deliver_and_hail) → NPC 인사(마을).
    사교 콜(걷는 동안 들은 말에 한마디)은 돌리지 않는다 — 들은 말은 pending 으로 다음 판단에 간다(LLM 콜을 판단에만 쓴다).
    형식 오류(재요청 뒤에도)는 그 판단을 '형식 오류'로 세고 판단 주체는 그 틱 기다린다(게임은 판단 정지 뒤 다시 묻는다 — 벤치는 다음 판단으로)."""
    desc, fn, goal_fn, script = SEQ_SCENES[name]
    d, bots, inbox = fn()
    me = _bot(bots, ACTOR)
    d.rng.seed(seed)
    s0 = _seq_s0(d, bots)
    solo = bool(getattr(d, "solo", False))
    steps, rec, pending, first_prompts = [], [], {}, []
    cur = {"obs": None, "k": 0, "calls": 0}
    caller = caller_for(cur)
    real_brain = brains.claude_brain
    queue = {c: [dict(x) for x in acts] for c, acts in script.items()}

    def recorder(prompt, model):
        out, why = caller(prompt, model)
        rec.append({"prompt": prompt, "raw": out, "why": why})
        return out, why

    def brain(obs, char="?", bot=None, roster=None, solo=False):
        if char != ACTOR:
            q = queue.get(char) or []
            return {**(q.pop(0) if q else SCRIPT_WAIT), "src": "script"}
        cur.update(obs=obs, k=len(steps), calls=0)
        n0 = len(rec)
        notes_before = list(me.get("notes") or [])
        dec = real_brain(obs, char, bot, roster, solo)
        calls = rec[n0:]
        first = (brains._parse_decision(calls[0]["raw"], calls[0]["why"], obs, ACTOR, [] if solo else bots)
                 if calls else {"src": "error"})
        prompt = calls[0]["prompt"] if calls else ""
        first_prompts.append(prompt)
        st = {"k": len(steps), "turn": d.turn, "first_error": first.get("input_error") if first.get("src") == "error" else None,
              "final_error": dec.get("input_error") if dec.get("src") == "error" else None,
              "prompt_chars": len(prompt), "memory_ok": all(n in prompt for n in notes_before), "notes_before": len(notes_before),
              "events": []}
        if dec.get("src") == "error":
            st.update(decision=None, attempt=None, category="형식 오류")
            steps.append(st)
            return {**SCRIPT_WAIT, "reason": "[벤치] 형식 오류 — 이 판단은 기다림으로", "src": "bench_error"}
        act = {k_: dec[k_] for k_ in CA.fields() if dec.get(k_) is not None}
        n = normalize(act, obs)
        st.update(decision=act, note=dec.get("note"), attempt=attempt_key(n), norm=n)
        steps.append(st)
        return dec

    t0_turn = d.turn
    ticks, goal_at, aborted = 0, None, None
    with patch.object(brains, "claude_brain", brain), patch.object(brains, "_call_claude", recorder), \
            patch.object(brains, "COMPOSE_PROMPT", variant["text"]), patch.object(brains, "COMPOSE_PROMPT_SOLO", variant["solo"]):
        try:
            while ticks < SEQ_TICKS:
                d.turn = t0_turn + ticks
                ticks += 1
                if SR.PENDING_ON:
                    inbox = SR.merge_inbox(pending, inbox)
                decisions = brains.think_all(d, bots, inbox)
                if SR.PENDING_ON:
                    pending = SR.keep_pending(inbox, decisions)
                says, say_to, say_kind = {}, {}, {}
                for b in bots:
                    if not b["alive"] or b["won"]:
                        continue
                    if b.get("order"):
                        res = d.step_order(b, bots)
                    else:
                        dec = decisions.get(b["char"])
                        if not dec:
                            continue
                        res = d.act(b, dec, bots)
                        if dec.get("say"):
                            says[b["char"]] = dec["say"]
                            if dec.get("to"):
                                say_to[b["char"]] = dec["to"]
                            if dec.get("say_kind"):
                                say_kind[b["char"]] = dec["say_kind"]
                    if b is me and steps:
                        tags = G.event_tags(res)
                        steps[-1]["events"].append({"type": res.get("type"), "result": res.get("result"),
                                                    "status": (res.get("resolution") or {}).get("status"),
                                                    "tag": tags[0][0], "label": tags[0][1]})
                d.monster_turn(bots)
                if SR.TOWN_WALKERS_ON and getattr(d, "walkers", None):
                    d.walk_npcs(bots)
                inbox, _hails = SR.deliver_and_hail(d, bots, says, say_to, say_kind, {})
                if getattr(d, "town", False) and SR.NPC_HAIL_ON:   # D71 NPC 가 먼저 거는 인사(고정 문장, 0콜) · D76 걸음을 멈춘다
                    for nm_, ch_, line_, _hx, _hy, _key in d.npc_greetings(bots):
                        inbox.setdefault(ch_, []).append({"from": "npc:" + nm_, "text": line_, "turn": d.turn, "to": ch_})
                        b_ = next((x for x in bots if x["char"] == ch_), None)
                        if SR.NPC_HAIL_STOP_ON and b_ is not None:
                            d.npc_hail_stop(b_, nm_)
                if goal_at is None and goal_fn(d, bots, s0):
                    goal_at = len(steps)
                if not me["alive"] or me["won"] or (not me.get("order") and (goal_at is not None or len(steps) >= SEQ_MAX)):
                    break
        except InfraFailure as e:              # 호출이 끝내 실패 — 이 판은 결측(지표 분모 밖)
            aborted = e.labels
        except brains.DecisionBlocked as e:    # 대본 쪽 판단 오류(있으면 안 된다) — 결측으로 남기고 계속
            aborted = ["판단 정지 %s" % sorted(e.errors)]
    for st in steps:
        ev = st["events"][-1] if st["events"] else None
        st["final"] = ev
        if st.get("category") != "형식 오류":
            st["category"] = ("미확정" if not ev else "효과" if ev["status"] == "success" and ev["tag"] != "misc"
                              else "변화 없음" if ev["status"] == "no_effect" else "실패")
    row = {"seq": name, "variant": variant["name"], "rep": rep, "seed": seed, "ticks": ticks,
           "goal": goal_at is not None, "goal_at": goal_at, "n_decisions": len(steps), "aborted": aborted,
           "chain": [st.get("attempt") or "(형식 오류)" for st in steps],
           "memory_ok": all(st["memory_ok"] for st in steps), "calls": len(rec), "steps": steps}
    return row, first_prompts


def summarize_seq(rows):
    """변형 × 장면별 지표. 결측(aborted) 판은 분모 밖."""
    out = {}
    for v in sorted({r["variant"] for r in rows}, key=lambda x: VARIANTS.index(x) if x in VARIANTS else 99):
        per = {}
        for s in SEQ_SCENES:
            rs = [r for r in rows if r["variant"] == v and r["seq"] == s]
            ok = [r for r in rs if not r["aborted"]]
            if not rs:
                continue
            st = [x for r in ok for x in r["steps"]]
            chars = [x["prompt_chars"] for x in st if x["prompt_chars"]]
            per[s] = {"runs": len(rs), "missing": len(rs) - len(ok),
                      "goal_rate": (sum(r["goal"] for r in ok) / len(ok)) if ok else None,
                      "decisions_mean": (sum(r["n_decisions"] for r in ok) / len(ok)) if ok else None,
                      "first_error_rate": (sum(1 for x in st if x["first_error"]) / len(st)) if st else None,
                      "prompt_chars_mean": round(sum(chars) / len(chars)) if chars else None,
                      "memory_ok_rate": (sum(r["memory_ok"] for r in ok) / len(ok)) if ok else None,
                      "categories": dict(collections.Counter(x["category"] for x in st)),
                      "chains": dict(collections.Counter(" → ".join(r["chain"]) for r in ok).most_common(5))}
        out[v] = per
    return out


def write_seq_report(run_dir, summary, meta):
    L = ["# 연속 판단 장면 — %s" % meta["run_id"], "",
         "두뇌 `%s` · 장면 %d · 변형 %d · 반복 %d · 판단 상한 %d · 틱 상한 %d" % (
             meta["brain"], len(meta["seqs"]), len(meta["variants"]), meta["reps"], SEQ_MAX, SEQ_TICKS), "",
         "- 완주율 = 목표에 닿은 판 ÷ 판(결측 제외) · 판단 = 판단 주체가 실제로 내린 판단 수 · 형식오류 = 첫 응답이 파서에서 거절된 판단 비율",
         "- 기억 유지 = 모든 판단에서 그 전에 남긴 note 가 프롬프트에 있었던 판의 비율 · 판단당 프롬프트 = 첫 요청 글자 수 평균",
         "- **dummy 의 완주율·선택은 모델의 것이 아니다**(관측에서 파서 통과 조합을 고르게 뽑는다 — 배관 확인용)", "",
         "| 변형 | 장면 | 판 | 결측 | 완주율 | 판단(평균) | 형식오류(첫 응답) | 판단당 프롬프트(자) | 기억 유지 | 효과/변화없음/실패/형식오류/미확정 |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for v, per in summary.items():
        for s, m in per.items():
            c = m["categories"]
            L.append("| %s | %s | %d | %d | %s | %s | %s | %s | %s | %s |" % (
                v, s, m["runs"], m["missing"], _pct(m["goal_rate"]),
                "-" if m["decisions_mean"] is None else "%.1f" % m["decisions_mean"], _pct(m["first_error_rate"]),
                m["prompt_chars_mean"] if m["prompt_chars_mean"] is not None else "-", _pct(m["memory_ok_rate"]),
                "/".join(str(c.get(k, 0)) for k in ("효과", "변화 없음", "실패", "형식 오류", "미확정"))))
    L += ["", "## 자주 나온 연계(장면 · 변형 · 판단 사슬 × 판 수)", ""]
    for v, per in summary.items():
        for s, m in per.items():
            for ch, n in m["chains"].items():
                L.append("- %s · %s · `%s` × %d" % (s, v, ch, n))
    with open(os.path.join(run_dir, "seq_summary.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")
    return "\n".join(L)


def run_seq(args):
    """연속 판단 장면 실행 — dummy(0콜) 또는 gemini(관리자 전용). 결과: <run>/sequences.jsonl · seq_summary.{json,md} · meta.json ·
    prompts/<장면>__<변형>__k<판단>.txt(반복 0 의 판단마다 첫 요청 원문)."""
    names = list(SEQ_SCENES) if args.seq == "all" else args.seq.split(",")
    variants = list(VARIANTS) if args.variants == "all" else args.variants.split(",")
    live = args.brain == "gemini"
    run_id = args.run_id or time.strftime("%Y%m%d-%H%M%S") + "-seq-" + args.brain
    run_dir = os.path.join(OUT_ROOT, run_id)
    os.makedirs(run_dir, exist_ok=True)
    total = len(names) * len(variants) * args.reps
    _engine(os.path.join(run_dir, "state"), call_limit=(2 * SEQ_MAX * total + 30) if live else 0)
    if live:
        import envload
        envload.load()
        if not os.environ.get("GEMINI_API_KEY"):
            raise SystemExit("GEMINI_API_KEY 가 없다(.env) — 본 실행을 못 한다")
    t0 = time.time()
    vtexts = build_variants(run_dir)
    meta = {"run_id": run_id, "brain": args.brain, "reps": args.reps, "seqs": names, "variants": variants,
            "seq_max": SEQ_MAX, "seq_ticks": SEQ_TICKS, "seeds": list(SEEDS), "actor": ACTOR, "game_env": GAME_ENV,
            "model": (brains.model_id("gemini_api", "haiku") if live else None),
            "git_head": _git("rev-parse", "HEAD"), "git_dirty": _git("status", "--porcelain").splitlines(),
            "bench_sha": _sha("tools/freedom_bench.py"), "variant_sha": {v: vtexts[v]["sha"] for v in variants},
            "action_schema": CA.SCHEMA, "registry": sorted(CA.COMMON_EXT)}
    _dump(os.path.join(run_dir, "meta.json"), meta)
    pacer = Pacer(brains._call_claude, args.interval) if live else Pacer(None, 0, backoff=(0, 0, 0))
    pdir = os.path.join(run_dir, "prompts")
    os.makedirs(pdir, exist_ok=True)
    blocked = (patch.object(brains, "_http_post", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("dummy 모드에서 HTTP 시도")))
               if not live else None)
    if blocked:
        blocked.start()
    rows, k = [], 0
    try:
        with open(os.path.join(run_dir, "sequences.jsonl"), "w", encoding="utf-8", newline="\n") as f:
            for rep in range(args.reps):
                for v in variants:
                    for n in names:
                        k += 1
                        seed = SEEDS[rep % len(SEEDS)]
                        def caller_for(cur, n=n, v=v, rep=rep):
                            if not live:                # dummy 는 판단마다 지금 관측에서 고르는 고정 응답(간격·물러남 0 — --mock-infra 면 고장 주입)
                                c = seq_dummy_caller(n, v, rep, cur)
                                pacer.real = mock_infra(c, (n, v, rep)) if args.mock_infra else c
                            return pacer
                        row, prompts = run_sequence(n, {**vtexts[v], "name": v}, caller_for, rep, seed)
                        if rep == 0:
                            for i, p in enumerate(prompts):
                                with open(os.path.join(pdir, "%s__%s__k%d.txt" % (n, v, i)), "w", encoding="utf-8", newline="\n") as pf:
                                    pf.write(p)
                        rows.append(row)
                        f.write(json.dumps(row, ensure_ascii=False) + "\n")
                        f.flush()
                        print("  [%3d/%d] %-16s %-9s r%d  %s" % (
                            k, total, n, v, rep, ("결측(인프라 실패 — %s)" % row["aborted"][-1]) if row["aborted"] else
                            "판단 %d · %s · 기억 %s  %s" % (row["n_decisions"], "완주(판단 %s)" % row["goal_at"] if row["goal"] else "미완",
                                                         "OK" if row["memory_ok"] else "끊김", " → ".join(row["chain"]))), flush=True)
    finally:
        if blocked:
            blocked.stop()
    summary = summarize_seq(rows)
    meta.update(calls_sent=pacer.sent if live else 0, infra_retries=pacer.retries, elapsed_s=round(time.time() - t0, 1))
    _dump(os.path.join(run_dir, "meta.json"), meta)
    _dump(os.path.join(run_dir, "seq_summary.json"), summary)
    print()
    print(write_seq_report(run_dir, summary, meta))
    print("\n끝(%.0fs, 실제 전송 %d회) — %s" % (time.time() - t0, meta["calls_sent"], run_dir))
    return run_dir


# ── 실행 ──────────────────────────────────────────────────────────────────────────────────────────────
def _git(*args):
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=20).stdout.strip()
    except Exception as e:
        return "(git 실패 %s)" % type(e).__name__


def _sha(path):
    try:
        with open(os.path.join(ROOT, path), "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]
    except OSError:
        return None


def _dump(path, obj):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def build_all(names, run_dir):
    """장면을 짓고 스냅샷(피클)·관측 원문·지문을 남긴다. 지난 실행의 지문과 다르면 알린다(같은 장면인지 확인)."""
    sdir = os.path.join(run_dir, "scenes")
    os.makedirs(sdir, exist_ok=True)
    prev = {}
    pf = os.path.join(OUT_ROOT, "scene_fingerprints.json")
    if os.path.exists(pf):
        with open(pf, encoding="utf-8") as f:
            prev = json.load(f)
    scenes = collections.OrderedDict()
    for n in names:
        sc = build_scene(n)
        scenes[n] = sc
        with open(os.path.join(sdir, n + ".pkl"), "wb") as f:
            f.write(sc.blob)
        with open(os.path.join(sdir, n + ".txt"), "w", encoding="utf-8", newline="\n") as f:
            f.write("# %s — %s\n# 지문 %s\n\n%s\n" % (n, sc.desc, sc.fingerprint, sc.text))
        if prev.get(n) and prev[n] != sc.fingerprint:
            print("  ⚠ %s 장면 지문이 지난 기록과 다르다(%s → %s) — 엔진·생성기가 바뀌었는지 확인" % (n, prev[n], sc.fingerprint))
        prev[n] = sc.fingerprint
    os.makedirs(OUT_ROOT, exist_ok=True)
    _dump(pf, prev)
    return scenes


def run(args):
    run_id = args.run_id or time.strftime("%Y%m%d-%H%M%S") + "-" + ("space" if args.space_only else args.brain)
    run_dir = os.path.join(OUT_ROOT, run_id)
    os.makedirs(run_dir, exist_ok=True)
    names = list(SCENES) if args.scenes == "all" else args.scenes.split(",")
    variants = list(VARIANTS) if args.variants == "all" else args.variants.split(",")
    total = len(names) * len(variants) * args.reps
    live = args.brain == "gemini" and not args.space_only
    # 전송 상한 = 판단마다 최대 2회(입력 오류 재요청) + 한도 물러남 여유 — 넘으면 게임의 D96 라벨이 나고 Pacer 가 실행을 멈춘다
    _engine(os.path.join(run_dir, "state"), call_limit=(2 * total + 30) if live else 0)
    if live:
        import envload
        envload.load()                       # 벤치 하니스 — .env 는 본 실행 프로세스에서만 읽는다(키는 출력·저장하지 않는다)
        if not os.environ.get("GEMINI_API_KEY"):
            raise SystemExit("GEMINI_API_KEY 가 없다(.env) — 본 실행을 못 한다")
    t0 = time.time()
    print("장면 짓기 …", flush=True)
    scenes = build_all(names, run_dir)
    print("가능 공간 전수 대입(LLM 없음) …", flush=True)
    spaces = collections.OrderedDict()
    with open(os.path.join(run_dir, "space.jsonl"), "w", encoding="utf-8", newline="\n") as f:
        for n, sc in scenes.items():
            sp = possible_space(sc)
            spaces[n] = sp
            for r in sp["rows"]:
                f.write(json.dumps({"scene": n, **r}, ensure_ascii=False) + "\n")
            print("  %-16s 조합 %3d(파서 거절 %d) · 효과 결과 %3d · 변화없음 시도 %2d · 부수효과 조합 %2d · %s"
                  % (n, sp["n_combos"], sp["n_rejected"], len(sp["effects"]), len(sp["noeffect_attempts"]),
                     sum(1 for r in sp["rows"] if r["side"]), " ".join("%s %d" % kv for kv in sp["categories"].items())), flush=True)
    meta = {"run_id": run_id, "brain": "space-only" if args.space_only else args.brain, "reps": args.reps,
            "scenes": names, "variants": variants, "seeds": list(SEEDS), "scene_seed": SCENE_SEED, "max_steps": MAX_STEPS,
            "actor": ACTOR, "ally": ALLY, "game_env": GAME_ENV,
            "model": (brains.model_id("gemini_api", "haiku") if args.brain == "gemini" else None),
            "git_head": _git("rev-parse", "HEAD"), "git_dirty": _git("status", "--porcelain").splitlines(),
            "bench_sha": _sha("tools/freedom_bench.py"),   # 이 스크립트 자체(채점 규칙이 바뀌면 같은 응답도 다르게 센다)
            "file_sha": {p: _sha(p) for p in ("prompts/adventurer_prompt.md", "brains.py", "composed_actions.py", "dungeon_gm.py",
                                               "dungeon_concept.py", "entities.py", "interactables.py", "show_runner.py", "party.json")
                         + tuple("%s/%s.md" % (VARIANT_DIR, v) for v in VARIANTS if v != "baseline")},
            "fingerprints": {n: sc.fingerprint for n, sc in scenes.items()}}
    if args.space_only:
        _dump(os.path.join(run_dir, "meta.json"), meta)
        _dump(os.path.join(run_dir, "space_summary.json"), {n: {k: v for k, v in sp.items() if k != "rows"} for n, sp in spaces.items()})
        print("끝(%.0fs) — %s" % (time.time() - t0, run_dir))
        return run_dir
    vtexts = build_variants(run_dir)
    meta["variant_sha"] = {v: vtexts[v]["sha"] for v in variants}
    meta["skill_hint_check"] = skill_hint_check(scenes, {v: vtexts[v] for v in variants})
    meta["skill_hint_prompts"] = {v: [0, 0] for v in variants}   # 실제 판단 프롬프트 중 SKILL 안내가 든 수 / 관측에 SKILL 이 있던 수
    _dump(os.path.join(run_dir, "meta.json"), meta)   # 판단 전에 먼저 남긴다 — 중간에 멈춰도 --rescore 로 집계할 수 있게
    # 실호출은 brains._call_claude(게임 백엔드) · dummy 는 판단마다 고정 응답 함수를 꽂는다(간격·물러남 0 — --mock-infra 면 고장 주입)
    pacer = Pacer(brains._call_claude, args.interval) if live else Pacer(None, 0, backoff=(0, 0, 0))
    pdir = os.path.join(run_dir, "prompts")
    os.makedirs(pdir, exist_ok=True)
    rows = []
    k = 0
    blocked = (patch.object(brains, "_http_post", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("dummy 모드에서 HTTP 시도")))
               if not live else None)
    if blocked:
        blocked.start()
    try:
        with open(os.path.join(run_dir, "responses.jsonl"), "w", encoding="utf-8", newline="\n") as f:
            for rep in range(args.reps):
                for v in variants:
                    for n, sc in scenes.items():
                        k += 1
                        if not live:
                            call = canned_caller(sc, spaces[n], v, rep)
                            pacer.real = mock_infra(call, (n, v, rep)) if args.mock_infra else call
                        r0 = pacer.retries
                        base = {"scene": n, "variant": v, "rep": rep}
                        try:
                            dec, calls = decide(sc, vtexts[v], pacer)
                        except InfraFailure as e:     # 끝내 호출 실패 — 결측(판단 없음, 분모 밖)
                            row = {**base, "responses": [], "decision": None, "infra": e.labels, "infra_retries": pacer.retries - r0,
                                   "first_error": None, "final_error": None, "norm": None, "attempt": None, "outcomes": [],
                                   "category": "결측", "effects": [], "side": [], "flags": []}
                        else:
                            ppath = os.path.join(pdir, "%s__%s.txt" % (n, v))
                            if calls and not os.path.exists(ppath):
                                with open(ppath, "w", encoding="utf-8", newline="\n") as pf:
                                    pf.write(calls[0]["prompt"])
                            if calls and sc.obs.get("skills"):
                                meta["skill_hint_prompts"][v][0] += SKILL_HINT in calls[0]["prompt"]
                                meta["skill_hint_prompts"][v][1] += 1
                            row = {**base, "responses": [{"raw": c["raw"], "why": c["why"]} for c in calls],
                                   "decision": {k_: v_ for k_, v_ in dec.items() if k_ not in ("attempt_errors",)},
                                   "infra_retries": pacer.retries - r0, **score_response(sc, calls, dec)}
                        rows.append(row)
                        f.write(json.dumps(row, ensure_ascii=False) + "\n")
                        f.flush()
                        print("  [%3d/%d] %-16s %-9s r%d  %-24s %s%s" % (
                            k, total, n, v, rep, row["attempt"] or ("(인프라 실패)" if row["category"] == "결측" else "(형식 오류)"),
                            row["category"], (" · 재호출 %d" % row["infra_retries"]) if row["infra_retries"] else ""), flush=True)
    finally:
        if blocked:
            blocked.stop()
    summary = summarize(rows, spaces)
    meta["corrections"] = {"space": corrections([r for sp in spaces.values() for r in sp["rows"]]), "responses": corrections(rows)}
    meta["calls_sent"] = pacer.sent if live else 0
    meta["infra_retries"] = pacer.retries
    meta["missing"] = sum(1 for r in rows if r["category"] == "결측")
    meta["mock_infra"] = bool(args.mock_infra and not live)
    meta["elapsed_s"] = round(time.time() - t0, 1)
    _dump(os.path.join(run_dir, "meta.json"), meta)
    _dump(os.path.join(run_dir, "summary.json"), {"variants": summary,
                                                  "spaces": {n: {k_: v_ for k_, v_ in sp.items() if k_ != "rows"} for n, sp in spaces.items()}})
    print()
    print(write_report(run_dir, summary, spaces, meta))
    print("\n끝(%.0fs, 실제 전송 %d회) — %s" % (time.time() - t0, meta["calls_sent"], run_dir))
    return run_dir


def rescore(args):
    """기록된 응답 원문을 지금 코드로 다시 지은 장면에서 다시 읽고 굴린다 — 같은 응답, 바뀐 세계(배선 전후). LLM 0콜
    (재요청 자리에도 기록된 둘째 응답을 돌려준다 — 기록이 없으면 빈 응답 = 형식 오류)."""
    src = os.path.abspath(args.rescore)
    with open(os.path.join(src, "meta.json"), encoding="utf-8") as f:
        old = json.load(f)
    run_id = "%s-rescore-%s" % (os.path.basename(src), time.strftime("%Y%m%d-%H%M%S"))
    run_dir = os.path.join(OUT_ROOT, run_id)
    os.makedirs(run_dir, exist_ok=True)
    _engine(os.path.join(run_dir, "state"))
    scenes = build_all(old["scenes"], run_dir)
    for n, sc in scenes.items():
        if old["fingerprints"].get(n) != sc.fingerprint:
            print("  ⚠ %s 관측 지문이 원 실행과 다르다 — 응답의 대상 ID 가 지금 관측에 없으면 형식 오류로 센다" % n)
    spaces = collections.OrderedDict((n, possible_space(sc)) for n, sc in scenes.items())
    rows = []
    with open(os.path.join(src, "responses.jsonl"), encoding="utf-8") as f:
        recs = [json.loads(ln) for ln in f if ln.strip()]
    no_http = patch.object(brains, "_http_post", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("재채점에서 HTTP 시도")))
    with open(os.path.join(run_dir, "responses.jsonl"), "w", encoding="utf-8", newline="\n") as f, no_http:
        for r in recs:
            if r["category"] == "결측":            # 원 실행에서 호출이 끝내 실패한 판단 — 다시 채점할 응답이 없다(결측 그대로)
                rows.append(r)
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
                continue
            sc = scenes[r["scene"]]
            replies = iter(r["responses"])
            caller = lambda p, m: (lambda c: (c["raw"], c["why"]))(next(replies, {"raw": "", "why": "기록 없음"}))
            dec, calls = decide(sc, {"text": brains.COMPOSE_PROMPT, "solo": brains.COMPOSE_PROMPT_SOLO}, caller)
            row = {**{k: r[k] for k in ("scene", "variant", "rep", "responses")}, "decision": dec,
                   "infra_retries": r.get("infra_retries", 0), **score_response(sc, calls, dec)}
            row["prompt_chars"] = r.get("prompt_chars")   # 재채점은 기준선 지침으로 다시 읽는다 — 길이는 원 실행의 값(없으면 비움)
            rows.append(row)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary = summarize(rows, spaces)
    meta = {**old, "run_id": run_id, "rescored_from": old["run_id"], "git_head": _git("rev-parse", "HEAD"),
            "bench_sha_original": old.get("bench_sha"), "bench_sha": _sha("tools/freedom_bench.py"),
            "git_dirty": _git("status", "--porcelain").splitlines(), "fingerprints": {n: sc.fingerprint for n, sc in scenes.items()},
            "corrections": {"space": corrections([r for sp in spaces.values() for r in sp["rows"]]), "responses": corrections(rows)}}
    _dump(os.path.join(run_dir, "meta.json"), meta)
    _dump(os.path.join(run_dir, "summary.json"), {"variants": summary,
                                                  "spaces": {n: {k_: v_ for k_, v_ in sp.items() if k_ != "rows"} for n, sp in spaces.items()}})
    print(write_report(run_dir, summary, spaces, meta))
    return run_dir


def show(args):
    import tempfile
    _engine(os.path.join(tempfile.mkdtemp(prefix="freedom_bench_"), "state"))
    sc = build_scene(args.show)
    print("# %s — %s (지문 %s)\n" % (sc.name, sc.desc, sc.fingerprint))
    print(sc.text)
    print("\n# 대상 목록")
    for t in sc.obs.get("targets", []):
        print("  %-8s %-8s %s" % (t["id"], attempt_key(normalize({"type": "·", "target": t["id"]}, sc.obs)).split(" ")[1], t.get("name", "")))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="행동 자유도 벤치마크(t06)")
    ap.add_argument("--brain", choices=("dummy", "gemini"), default="dummy",
                    help="dummy = 고정 응답(LLM 0콜) · gemini = 게임과 같은 Gemini Flash 경로(.env 키)")
    ap.add_argument("--scenes", default="all", help="쉼표 목록 또는 all: " + ",".join(SCENES))
    ap.add_argument("--variants", default="all", help="쉼표 목록 또는 all: " + ",".join(VARIANTS))
    ap.add_argument("--reps", type=int, default=3, help="장면 × 변형마다 판단 횟수")
    ap.add_argument("--interval", type=float, default=6.0, help="gemini 호출 사이 최소 간격(초) — 순차 호출, 기본 분당 10회 이하")
    ap.add_argument("--space-only", action="store_true", help="가능 공간만 계산(판단 없음)")
    ap.add_argument("--mock-infra", action="store_true", help="dummy 전용 — 호출 실패(429·타임아웃)를 결정론적으로 주입해 재호출·결측 경로를 굴린다")
    ap.add_argument("--rescore", metavar="RUN_DIR", help="기록된 응답을 지금 코드로 다시 채점(LLM 0콜)")
    ap.add_argument("--show", metavar="SCENE", help="장면 하나의 관측 원문과 대상 목록 출력")
    ap.add_argument("--seq", metavar="SEQS", help="연속 판단 장면(p0.5.5) — 쉼표 목록 또는 all: " + ",".join(SEQ_SCENES))
    ap.add_argument("--run-id", help="결과 폴더 이름(기본: 시각-모드)")
    args = ap.parse_args()
    if args.show:
        return show(args)
    if args.seq:
        return run_seq(args)
    if args.rescore:
        return rescore(args)
    return run(args)


if __name__ == "__main__":
    main()

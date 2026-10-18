# -*- coding: utf-8 -*-
"""행동 등록부 · 조건부 노출 · 관측 런타임 주입 · 라우터(p0.5.5 = master_plan 0.6단계, §7) 헤들리스 검증 — LLM 0콜(모델 응답은 전부 가짜).
등록부(composed_actions.COMMON_EXT)는 아직 비어 있다 — ①~⑦·⑩은 검증 전용 '프로브 동사'를 잠깐 등록해 길(노출·라우터·칸·주입·벤치)을 굴린다.
실제 등록 동사에 대해 이 파일이 따로 보는 것은 ① 비간섭(노출 목록·프롬프트 바이트) · ⑧ 꼴·이름·말 파일 · ⑨ 결과 문장뿐이다(등록부가 빈 지금은 0개라
헛돈다 — 부정 확인으로 검사 자체가 걸리는지는 본다). 그 동사의 효과·판정·노출 조건의 옳음은 그 동사 단계의 게이트 몫이다.
  ① 노출 조건은 공개 정보만 읽는다: 읽는 칸(EXPOSE_KEYS)이 전부 행동자 프롬프트에 그려지는 관측 칸 · 조건이 받는 것은 그 칸만 담은 사본
     (동사마다 새 사본 — 원본 관측 불변) · 행동자가 못 보는 것(숨은 함정·숨은 몹·벽 너머 몹·시야 밖 사람의 소지품)만 다른 두 세계에서
     노출 목록·추가 행동 블록·프롬프트 전체 바이트가 같다 · 세계를 몰래 읽는 부정 프로브는 갈린다(시험이 헛돌지 않는다) ·
     노출 계산은 판정 rng 를 건드리지 않는다 · 봇 dict 에 칸을 더하지 않는다(스냅샷 꼴 불변)
  ② 노출 밖이어도 알려진 동사는 시도할 수 있다: 블록에 없는 등록부 동사도 parse 가 받고 실행된다 · 모르는 동사는 invalid_type
  ③ 라우터(§6.3 경로 7): 스킬 켠 판에서도 등록부 동사는 스킬 경로·자동 접근을 타지 않는다 — 멀면 걸음 없이 too_far, 못 보면 lost,
     곁이면 효과 · 옛 규칙(등록부를 안 보는 라우터)이면 결과가 갈린다 · too_far·lost 는 등록된 문장·꼬리표(폴백 아님)
  ④ 새 입력 칸: 허용 값·필수·자유 문구 길이 · then(작정)·plan_step·_active_action·결과 머리가 칸을 보존 · 칸 오류에 받는 값
  ⑤ 지침 파일 불변(런타임 주입): 추가 행동이 나타나도 시트+지침 부분은 바이트가 같고 지침 = 게임이 읽은 지침 파일(스킬 치환만) ·
     블록은 관측의 COMMON 줄 바로 아래에만 · 스킬 판의 SKILL 안내 치환은 그대로
  ⑥ 기준선/변형 모두 같은 추가 블록: '## 행동 사전' 절을 벤치 변형(tools/bench_variants/)으로 갈아 끼운 지침에서도 블록 바이트가 같다
     (p0.5.6: 벤치의 variant_raw 로 짓는다 — 전문 변형 prompt-v0.5.5 는 파일 전체가 지침)
  ⑦ 등록부가 비면 관측 꼴이 v0.4 와 같다: common_extra 키 없음 · 블록 없음 · 입력 칸 = 기본 4칸 · SCHEMA 문자열만 compose-v0.5
  ⑧ 말 파일·이름: check_words 가 등록부와 일치 · 문장 없는 동사를 등록하면 check_words 실패 · 등록부 동사는 스킬 이름으로 못 쓴다 ·
     실제 등록부 동사의 꼴(조건·실행 함수·칸 정의·결과 코드 선언)과 이름 충돌(상시 9개·PARTY·스킬 예약·기본 스킬) 없음
  ⑨ 결과 문장(p0.5.5b): 실제 등록 동사가 선언한 결과 코드(spec 'results') + 라우터 결과(too_far·lost)마다 직전 결과 문장(_last_prose)과
     꼬리표(event_tags)가 폴백({type,target,status} JSON)이 아니다 — 최소 기록으로 · 시험 장면에서 보이는 대상마다 실제로 해 본 결과도
     선언 안이고 폴백이 아니다 · 문장 없는 결과를 내는 프로브는 이 검사에 걸린다(부정 확인)
  ⑩ 벤치(p0.5.5b): 노출되는 등록부 동사가 하나 있을 때 tools/freedom_bench.py 단일 장면(4조합 사전 검사 포함)·연속 장면 dummy 가
     끝까지 돈다 — 서브프로세스, 그 안에서만 동사를 등록, 결과는 임시 폴더
"""
import contextlib
import copy
import glob
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="wl_registry_")
os.environ.update(DUNGEON_ACTION_MODE="compose", DUNGEON_BRAIN_BACKEND="dummy", DUNGEON_GM="0", DUNGEON_STEP_DELAY="0",
                  DUNGEON_SKILLS="0", DUNGEON_TRPG_COMBAT="0", DUNGEON_RANDOM_SKILL="0", DUNGEON_NPC_BRAIN="0",
                  DUNGEON_BESTIARY_FILE="", DUNGEON_STATE_DIR=os.path.join(TMP, "state"))
for k in ("DUNGEON_PARTY_FILE", "DUNGEON_RESUME", "DUNGEON_START", "DUNGEON_SOLO", "DUNGEON_MENU", "DUNGEON_PARTYFORM",
          "DUNGEON_STREAM_OBS", "DUNGEON_RUNS_DIR", "DUNGEON_STRANGERS"):
    os.environ.pop(k, None)
sys.path.insert(0, os.path.join(HERE, "tools"))

import brains                                        # noqa: E402
import composed_actions as CA                        # noqa: E402
import dungeon_gm as G                               # noqa: E402
import info_guard as IG                              # noqa: E402
import scenario                                      # noqa: E402
import skill_schema as SS                            # noqa: E402
import check_words                                   # noqa: E402

fails = []


def check(name, ok, detail=""):
    print("  %s %s%s" % ("ok  " if ok else "FAIL", name, (" — " + str(detail)[:400]) if (detail != "" and not ok) else ""))
    if not ok:
        fails.append(name)


# ── 프로브 동사(검증 전용 — 이 파일 안에서만 잠깐 등록한다) ────────────────────────────────────────────────
SEEN_VIEWS = []                                      # 노출 조건이 받은 view(키·정체 확인용)
WORLD = {}                                           # 부정 프로브가 몰래 읽는 세계(이렇게 하면 안 된다는 본보기)


def _others(view):
    """self·행동자 말고 관측 대상이 하나라도 있나 — steal 노출 조건(§3.1)과 같은 꼴."""
    SEEN_VIEWS.append(view)
    view.setdefault("targets", []).append({"id": "변조"})   # 사본을 바꿔도 원본 관측·다음 동사의 사본은 그대로여야 한다
    return any(t["id"] not in ("self", view.get("actor"), "변조") for t in view["targets"])


def _has_item(view):
    SEEN_VIEWS.append(view)
    return bool(view.get("items"))


def _cheat(view):
    """부정 프로브 — view 를 안 보고 세계를 직접 읽는다(숨은 함정이 있으면 노출). ① 의 비간섭 시험이 이걸 잡아야 한다."""
    return any(t.hidden for t in WORLD["d"].traps)


def _run_touch(d, bot, action, target, bots):
    return CA._base(bot, action, "probe_done", kind=target[0])


def _run_pose(d, bot, action, target, bots):
    return CA._base(bot, action, "probe_done", kind=None)


def _run_walk(d, bot, action, target, bots):
    path = d.path_to(bot["x"], bot["y"], *target[1], bots)
    bot["order"], bot["path"] = "@%d,%d" % target[1], path
    return CA._base(bot, action, "pathed", len=len(path))


PROBES = {
    "probe_touch": {"expose": _others, "run": _run_touch, "fields": {"mode": ("soft", "hard"), "loot": None}, "results": ("probe_done",)},
    "probe_pose": {"expose": _has_item, "run": _run_pose, "target": False, "fields": {"request": ("stop", "drop")},
                   "required": ("request",), "results": ("probe_done",)},
    "probe_walk": {"expose": lambda view: False, "run": _run_walk, "range": lambda d, b, a, t: True, "fields": {"mode": ("soft", "hard")},
                   "results": ("pathed",)},
}
PROBE_WORDS = {"header": "COMMON의 추가 행동은 지금 상황에 맞는 것만 나타난다.",
               "probe_touch": "검증용 — 곁의 대상을 만진다", "probe_pose": "검증용 — 자세를 잡는다(대상 없음)",
               "probe_walk": "검증용 — 대상에게 걸어간다"}


@contextlib.contextmanager
def registered(probes=PROBES, words=PROBE_WORDS, clear=True):
    """프로브 동사를 잠깐 등록한다(clear = 실제 등록부를 비운 채로 — 프로브만)."""
    with patch.dict(CA.COMMON_EXT, probes, clear=clear), patch.object(CA, "_EXTRA_LINES", dict(words)):
        yield


def prompt_of(d, bots, b, instructions=None):
    """claude_brain 이 실제로 조립한 글 전체(_call_claude 가로챔, 실 콜 없음)."""
    got = {}

    def stub(prompt, model="haiku"):
        got["p"] = prompt
        return json.dumps({"type": "wait", "reason": "등록부 검증"}, ensure_ascii=False)
    obs = d.view(b, bots)
    ctx = patch.object(brains, "COMPOSE_PROMPT", instructions) if instructions is not None else contextlib.nullcontext()
    with patch.object(brains, "_call_claude", stub), ctx:
        brains.claude_brain(obs, b["char"], b, bots)
    return got["p"], obs


def block_of(prompt):
    """프롬프트의 '추가 행동' 블록 — 관측의 COMMON 줄 다음부터 '의사소통' 줄 앞까지(지침 변형 안의 같은 머리 줄과 헷갈리지 않게 마지막 COMMON 줄)."""
    lines = prompt.split("\n")
    i = max(n for n, ln in enumerate(lines) if ln.startswith("COMMON: "))
    j = next(n for n, ln in enumerate(lines) if n > i and ln.startswith("의사소통: "))
    return lines[i + 1:j]


MAP_A = ["##############",
         "#1.2...#.....#",
         "#......#.....#",
         "#......#3...>#",
         "##############"]
MAP_B = ["##############",
         "#1.2...#..g..#",
         "#....l.#.....#",
         "#.^....#3...>#",
         "##############"]


def world(hidden):
    """같은 시드의 장면 — 1·2 는 같은 방, 3 은 벽 너머(명단에는 있지만 안 보인다). hidden 이면 1 이 못 보는 것만 더한다:
    숨은 함정(2,3) · 숨은 몹 l(5,2, concealed) · 벽 너머 몹 g · 벽 너머 3 의 소지품(물약 5병 — 아니면 0)."""
    spec = {"map": MAP_B if hidden else MAP_A, "seed": 7}
    if hidden:
        spec["monsters"] = {"g": {"kind": "고블린"}, "l": {"kind": "고블린", "concealed": True}}
    d, bots = scenario.build(spec)
    d.turn = 1
    for b in bots:
        b["potions"] = (5 if hidden else 0) if b["char"] == "3" else 1
    return d, bots


print("── ① 노출 조건은 공개 정보만 읽는다")
drawn = set(brains._WIRE_KEYS) | set(brains._WIRE_SIDE_KEYS)
check("① 노출 조건이 읽는 칸(%s)은 전부 행동자 프롬프트에 그려지는 관측 칸 · 그리지 않는 'gear' 는 없다" % ",".join(CA.EXPOSE_KEYS),
      set(CA.EXPOSE_KEYS) <= drawn and "gear" not in CA.EXPOSE_KEYS, set(CA.EXPOSE_KEYS) - drawn)
dA, botsA = world(False)
dB, botsB = world(True)
check("① 두 세계의 차이는 1 이 못 보는 것뿐(숨은 함정·숨은 몹·벽 너머 몹과 사람은 1 의 대상 목록에 없다)",
      [t["id"] for t in dA.view(botsA[0], botsA)["targets"]] == [t["id"] for t in dB.view(botsB[0], botsB)["targets"]]
      and len(dB.traps) == 1 and dB.traps[0].hidden and any(m.concealed for m in dB.monsters) and len(dB.monsters) == 2
      and not dA.traps and not dA.monsters and botsB[2]["potions"] == 5 and botsA[2]["potions"] == 0)
with registered():
    SEEN_VIEWS.clear()
    rng0 = dA.rng.getstate()
    keys0 = sorted(botsA[0])
    oA = dA.view(botsA[0], botsA)
    check("① 노출 계산은 판정 rng 를 건드리지 않고 봇 dict 에 칸을 더하지 않는다(스냅샷 꼴 불변)",
          dA.rng.getstate() == rng0 and sorted(botsA[0]) == keys0)
    check("① 조건이 받은 view = EXPOSE_KEYS 칸만 · 원본 관측의 칸이 아니라 사본(조건이 바꿔도 관측 그대로) · 동사마다 새 사본",
          len(SEEN_VIEWS) == 2 and all(set(v) <= set(CA.EXPOSE_KEYS) for v in SEEN_VIEWS)
          and all(v["targets"] is not oA["targets"] for v in SEEN_VIEWS) and SEEN_VIEWS[0] is not SEEN_VIEWS[1]
          and not any(t["id"] == "변조" for t in oA["targets"]) and sum(t["id"] == "변조" for t in SEEN_VIEWS[1]["targets"]) == 0,
          [sorted(v) for v in SEEN_VIEWS])
    check("① 프로브 노출: 곁의 동료가 보이니 probe_touch · 물약이 있으니 probe_pose · probe_walk 는 조건 거짓(등록 순서대로)",
          oA.get("common_extra") == ["probe_touch", "probe_pose"], oA.get("common_extra"))
    dA, botsA = world(False)                                    # 새로 지은 두 세계에서 비교한다(관측마다 길 ID 세대가 오르므로 view 횟수를 맞춘다)
    dB, botsB = world(True)
    pA, oA = prompt_of(dA, botsA, botsA[0])
    pB, oB = prompt_of(dB, botsB, botsB[0])
    check("① 못 보는 것만 다른 두 세계: 노출 목록·추가 행동 블록·프롬프트 전체 바이트가 같다",
          oA.get("common_extra") == oB.get("common_extra") and block_of(pA) == block_of(pB) and pA == pB and bool(block_of(pA)))
with registered({**PROBES, "probe_cheat": {"expose": lambda view: _cheat(view), "run": _run_touch}},
                {**PROBE_WORDS, "probe_cheat": "부정 프로브"}):
    WORLD["d"] = dA
    xa = dA.view(botsA[0], botsA).get("common_extra")
    WORLD["d"] = dB
    xb = dB.view(botsB[0], botsB).get("common_extra")
check("① 세계를 몰래 읽는 부정 프로브는 두 세계에서 노출이 갈린다(비간섭 시험이 헛돌지 않는다)",
      "probe_cheat" not in (xa or []) and "probe_cheat" in (xb or []), (xa, xb))
real = dict(CA.COMMON_EXT)
dA, botsA = world(False)
dB, botsB = world(True)
pA0, oA0 = prompt_of(dA, botsA, botsA[0])
pB0, oB0 = prompt_of(dB, botsB, botsB[0])
check("① 실제 등록부(동사 %d개)도 같은 비간섭: 노출 목록·프롬프트 바이트가 같다" % len(real),
      oA0.get("common_extra") == oB0.get("common_extra") and pA0 == pB0)

print("── ② 노출 밖이어도 알려진 동사는 시도할 수 있다")
with registered():
    d2, bots2 = world(False)
    bots2[0]["potions"] = bots2[0]["gold"] = 0       # p0.5.13: 골드(i7 — 시작 지갑)도 소지품이다 — 비워야 '소지품 없음'
    o2 = d2.view(bots2[0], bots2)
    p2, _ = prompt_of(d2, bots2, bots2[0])
    act, err = CA.parse({"type": "probe_pose", "request": "stop"}, o2)
    unk = CA.parse({"type": "probe_unknown", "target": "b2"}, o2)
    walk, werr = CA.parse({"type": "probe_walk", "target": "b2", "mode": "soft"}, o2)
    check("② 물약이 없으면 probe_pose 는 블록에 없다(probe_touch 만) · 그래도 parse 가 받는다 · 노출 안 된 probe_walk 도 받는다 · 모르는 동사는 invalid_type",
          o2.get("common_extra") == ["probe_touch"] and "- probe_pose" not in p2 and "- probe_touch: " in p2
          and err is None and act == {"type": "probe_pose", "request": "stop"} and werr is None and unk == (None, "invalid_type"),
          (o2.get("common_extra"), err, werr, unk))
    r2 = d2.act(bots2[0], act, bots2)
    check("② 노출 밖 동사도 실행된다(대상 없는 동사 — 대상을 적어 와도 버린다)",
          r2.get("result") == "probe_done" and r2.get("request") == "stop" and "target" not in r2
          and CA.parse({"type": "probe_pose", "target": "b2", "request": "stop"}, o2)[0] == {"type": "probe_pose", "request": "stop"}, r2)

print("── ③ 라우터: 등록부를 먼저 본다 — 스킬 경로·자동 접근 없음(§6.3 경로 7)")
with registered():
    d3, bots3 = world(False)
    d3.skills = True
    for b in bots3:
        b["skills"] = list(SS.PRESETS)
    me = bots3[0]
    x0 = (me["x"], me["y"])
    o3 = d3.view(me, bots3)
    far, ferr = CA.parse({"type": "probe_touch", "target": "b2", "mode": "hard"}, o3)
    r3 = d3.act(me, far, bots3)
    check("③ 스킬 켠 판 · 2칸 떨어진 동료에게 등록부 동사: too_far · 걸음 0 · 접근 예약 없음 · 스킬 결과 아님 · resolution failed",
          ferr is None and r3.get("result") == "too_far" and (me["x"], me["y"]) == x0 and not me.get("approach") and not me.get("order")
          and not r3.get("skill_id") and r3["resolution"]["status"] == "failed" and r3.get("mode") == "hard", r3)
    check("③ route: 상시 9개=common · 등록부=ext · PARTY=party · 스킬=skill · 스킬 끈 판의 모르는 동사=None",
          [CA.route(d3, t) for t in ("attack", "probe_touch", "party_form", "push_slash")] == ["common", "ext", "party", "skill"]
          and CA.route(dA, "push_slash") is None and CA.route(dA, "probe_touch") == "ext")
    old_route = lambda d_, t_: ("common" if t_ in CA.COMMON else "party" if t_ in CA.PARTY else "skill" if d_.skills else None)
    d3b, bots3b = world(False)
    d3b.skills = True
    for b in bots3b:
        b["skills"] = list(SS.PRESETS)
    o3b = d3b.view(bots3b[0], bots3b)
    with patch.object(CA, "route", old_route):
        r3b = d3b.act(bots3b[0], CA.parse({"type": "probe_touch", "target": "b2"}, o3b)[0], bots3b)
    check("③ 옛 라우터(등록부를 안 보는 규칙)였다면 스킬 경로로 갔다 — 이 시험이 라우터를 실제로 가른다",
          r3b.get("result") != "too_far", r3b.get("result"))
    me["x"], me["y"] = 2, 1                                     # 동료(3,1) 곁
    o3c = d3.view(me, bots3)
    r3c = d3.act(me, CA.parse({"type": "probe_touch", "target": "b2", "mode": "soft", "loot": " 낡은   단검 "}, o3c)[0], bots3)
    check("③ 곁이면 효과(run) · 결과 머리가 새 입력 칸을 보존(mode·loot) · resolution success",
          r3c.get("result") == "probe_done" and r3c.get("kind") == "bot" and r3c.get("mode") == "soft" and r3c.get("loot") == "낡은 단검"
          and r3c["resolution"]["status"] == "success", r3c)
    o3d = d3.view(me, bots3)
    bots3[1]["x"], bots3[1]["y"] = 10, 2                        # 벽 너머로 — 지금은 안 보인다
    r3d = d3.act(me, {"type": "probe_touch", "target": "b2"}, bots3)
    check("③ 대상을 놓치면 lost(자동 접근·재조준 없음)", r3d.get("result") == "lost" and not me.get("order"), r3d)
    names = {"2": "두란", "?": "낯선 사람"}
    prose = [brains._last_prose(r, names) for r in (r3, r3d)]
    tags = [G.event_tags(r, names)[0] for r in (r3, r3d)]
    check("③ too_far·lost 는 등록된 문장·꼬리표(폴백 JSON 아님)",
          all("{" not in s and "probe_touch" in s for s in prose) and all(t[0] == "misc" and t[1] == "헛손질" and "{" not in t[2] for t in tags),
          (prose, tags))

print("── ④ 새 입력 칸: 꼴 검사 · 작정·plan_step·_active_action 보존")
with registered():
    d4, bots4 = world(False)
    o4 = d4.view(bots4[0], bots4)
    bad = CA.parse({"type": "probe_touch", "target": "b2", "mode": "wild"}, o4)
    miss = CA.parse({"type": "probe_pose"}, o4)
    up = CA.parse({"type": "probe_touch", "target": "b2", "mode": " HARD "}, o4)
    long_ = CA.parse({"type": "probe_touch", "target": "b2", "loot": "가" * 90}, o4)
    check("④ 허용 값 밖 = invalid_mode · 필수 칸 없음 = missing_request · 허용 값은 대소문자·공백 정리 · 자유 문구는 %d자" % CA.FIELD_LEN,
          bad == (None, "invalid_mode") and miss == (None, "missing_request") and up[0] == {"type": "probe_touch", "target": "b2", "mode": "hard"}
          and len(long_[0]["loot"]) == CA.FIELD_LEN and "mode" not in long_[0], (bad, miss, up))
    det = CA.error_detail({"type": "probe_touch", "target": "b2", "mode": "wild"}, o4, "invalid_mode")
    det0 = CA.error_detail({"type": "goto", "target": "x9"}, o4, "invalid_target")
    check("④ 칸 오류의 상세엔 받는 값(field_values) · 옛 오류의 상세 꼴은 그대로(칸 없음)",
          det.get("field_values") == ["soft", "hard"] and "field_values" not in det0)
    steps = brains._then({"then": [{"type": "probe_touch", "target": "b2", "mode": "hard", "loot": "물약"},
                                   {"type": "probe_pose", "request": "drop"}]}, o4)
    check("④ then(작정)이 새 칸을 보존", steps == [{"type": "probe_touch", "target": "b2", "mode": "hard", "loot": "물약"},
                                          {"type": "probe_pose", "request": "drop"}], steps)
    me4 = bots4[0]
    me4["_plan_refs"] = copy.deepcopy(me4["_target_refs"])
    me4["plan"] = [dict(s) for s in steps]
    s1 = d4.plan_step(me4, bots4)
    s2 = d4.plan_step(me4, bots4)
    check("④ plan_step: 대상 있는 동사는 참조를 다시 확인하고 칸을 그대로 · 대상 없는 등록부 동사는 참조 없이 유효",
          s1 == {"type": "probe_touch", "target": "b2", "mode": "hard", "loot": "물약"} and s2 == {"type": "probe_pose", "request": "drop"},
          (s1, s2))
    check("④ 입력 칸 = 기본 4칸 + 등록부 동사의 새 칸(정렬)", CA.fields() == CA.BASE_FIELDS + ("loot", "mode", "request"), CA.fields())
    o4b = d4.view(me4, bots4)
    r4 = d4.act(me4, CA.parse({"type": "probe_walk", "target": "b2", "mode": "soft"}, o4b)[0], bots4)
    act4 = dict(me4.get("_active_action") or {})
    check("④ 걷는 등록부 동사: _active_action 이 새 칸(mode)·행동 id 를 보존", r4.get("result") == "pathed" and act4.get("mode") == "soft"
          and act4.get("type") == "probe_walk" and act4.get("action_id"), act4)

print("── ⑤ 지침 파일 불변 — 새 문장은 관측에 붙는다(런타임 주입)")
d5, bots5 = world(False)
p_off, _ = prompt_of(d5, bots5, bots5[0])
with registered():
    d5b, bots5b = world(False)
    p_on, o_on = prompt_of(d5b, bots5b, bots5b[0])
head_on = p_on[:p_on.index(brains.COMPOSE_PROMPT) + len(brains.COMPOSE_PROMPT)] if brains.COMPOSE_PROMPT in p_on else None
head_off = p_off[:p_off.index(brains.COMPOSE_PROMPT) + len(brains.COMPOSE_PROMPT)] if brains.COMPOSE_PROMPT in p_off else None
with open(os.path.join(HERE, "prompts", "adventurer_prompt.md"), encoding="utf-8") as f:
    raw_prompt = f.read()
check("⑤ 지침 = 게임이 읽은 지침 파일 그대로 · 추가 행동이 나타나도 시트+지침 부분 바이트가 같다",
      head_on is not None and head_on == head_off and brains.COMPOSE_PROMPT == brains._load_prompt(os.path.join("prompts", "adventurer_prompt.md"))[0])
check("⑤ 블록은 관측의 COMMON 줄 바로 아래에만 — 지침 파일에는 그 문장이 없다",
      block_of(p_on) == [PROBE_WORDS["header"], "- probe_touch: " + PROBE_WORDS["probe_touch"], "- probe_pose: " + PROBE_WORDS["probe_pose"]]
      and p_on.count(PROBE_WORDS["header"]) == 1 and PROBE_WORDS["header"] not in raw_prompt and block_of(p_off) == []
      and p_on.replace("\n".join(block_of(p_on)) + "\n", "") == p_off, block_of(p_on))
with registered():
    d5s, bots5s = world(False)
    d5s.skills = True
    for b in bots5s:
        b["skills"] = list(SS.PRESETS)
    p_sk, o_sk = prompt_of(d5s, bots5s, bots5s[0])
check("⑤ 스킬 판: SKILL 안내 치환은 그대로 · 추가 행동 블록과 SKILL 절이 함께 온다",
      bool(o_sk.get("skills")) and "매 판단에 제시되는 COMMON 또는 SKILL에서 행동 이름을 고른다." in p_sk
      and "매 판단에 제시되는 COMMON에서 행동 이름을 고른다." not in p_sk and "\nSKILL:\n" in p_sk and block_of(p_sk) == block_of(p_on))

print("── ⑥ 기준선/변형 모두 같은 추가 블록")
import freedom_bench as FB                           # noqa: E402 — 벤치가 변형 지침을 짓는 바로 그 함수(variant_raw)로 짓는다(p0.5.6 전문 변형 포함)

variants = sorted(glob.glob(os.path.join(HERE, "tools", "bench_variants", "*.md")))
blocks, heads, fulls = {}, set(), {}
base6 = raw_prompt.replace("\r\n", "\n")
with registered():
    for path in variants:
        with open(path, encoding="utf-8") as f:
            draft6 = f.read().replace("\r\n", "\n")
        raw6, _added = FB.variant_raw(base6, draft6)
        fulls[os.path.basename(path)] = (FB.is_full(draft6), raw6 == draft6)
        text = brains._strip_comments(brains._variant(brains._fill_verbs(raw6), False))   # p0.5.28 동사 줄·목록 자리는 게임 로더처럼 세트로 채운다
        d6, bots6 = world(False)
        p6, _ = prompt_of(d6, bots6, bots6[0], instructions=text)
        blocks[os.path.basename(path)] = block_of(p6)
        heads.add(text in p6 and ". 는 대상이 멀면" not in text)   # p0.5.28 동사 목록 자리가 빈 채 걷힌 지침(로더 밖에서 지은 글)은 실린 지침이 아니다
check("⑥ 벤치 변형 %d개(tools/bench_variants/ — 절 변형 6 + 전문 변형 1) 모두 기준선과 같은 추가 블록 · 변형 지침이 실제로 실렸다" % len(variants),
      len(variants) == 7 and all(v == block_of(p_on) for v in blocks.values()) and heads == {True}, sorted(blocks))
check("⑥ 전문 변형(p0.5.6 prompt-v0.5.5 = v0.5.5 지침 전문)은 파일 그대로 지침이 된다 · 절 변형 6개는 '## 행동 사전' 절만 갈아 끼운다(기존 동작)",
      fulls.get("prompt-v0.5.5.md") == (True, True)
      and all(not full for name, (full, _same) in fulls.items() if name != "prompt-v0.5.5.md")
      and FB.variant_raw(base6, base6) == (base6, False), fulls)

print("── ⑦ 등록부가 비면 관측 꼴이 v0.4 와 같다(SCHEMA 문자열만)")
with patch.dict(CA.COMMON_EXT, {}, clear=True):
    d7, bots7 = world(False)
    p7, o7 = prompt_of(d7, bots7, bots7[0])
    check("⑦ common_extra 키 없음 · 블록 없음 · 입력 칸 = 기본 4칸 · common_types = 상시 9개 · SCHEMA compose-v0.5",
          "common_extra" not in o7 and block_of(p7) == [] and PROBE_WORDS["header"] not in p7 and CA.fields() == CA.BASE_FIELDS
          and CA.common_types(o7) == CA.COMMON and CA.SCHEMA == o7["action_schema"] == "compose-v0.5" and CA.known_types() == CA.COMMON)

print("── ⑧ 말 파일·이름")
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc_real = check_words.check_actions()
with patch.dict(CA.COMMON_EXT, PROBES, clear=False), contextlib.redirect_stdout(io.StringIO()) as bad_out:
    rc_bad = check_words.check_actions()
check("⑧ check_words: 말 파일이 실제 등록부와 일치 · 문장 없는 동사를 등록하면 실패(동사 이름을 짚는다)",
      rc_real == 0 and rc_bad == 1 and "probe_touch" in bad_out.getvalue(), buf.getvalue() + bad_out.getvalue())
skill = SS.make("probe_ok", "검증용", [{"type": "damage", "dice": "1d4"}])
with registered():
    clash = SS.validate({**skill, "id": "probe_touch"})
check("⑧ 등록부 동사는 스킬 이름으로 못 쓴다(invalid_id) · 등록 전엔 같은 이름이 통과했다",
      clash == ["invalid_id"] and SS.validate({**skill, "id": "probe_touch"}) == [], clash)
shape = []
for v, spec in real.items():
    ok_ = (callable(spec.get("expose")) and callable(spec.get("run")) and re.fullmatch(r"[a-z][a-z0-9_]*", v)
           and v not in CA.COMMON and v not in CA.PARTY and v not in SS.COMMON and v not in SS.PRESETS
           and all(a is None or (isinstance(a, tuple) and a) for a in (spec.get("fields") or {}).values())
           and set(spec.get("required") or ()) <= set(spec.get("fields") or {})
           and isinstance(spec.get("results"), tuple) and spec["results"] and all(isinstance(r, str) for r in spec["results"]))
    shape.append((v, bool(ok_)))
check("⑧ 실제 등록부 동사 %d개: 조건·실행 함수 · 칸 정의 꼴 · 결과 코드 선언 · 이름이 상시 9개·PARTY·스킬 예약·기본 스킬과 겹치지 않는다" % len(real),
      all(ok for _v, ok in shape) and not (set(real) & set(SS.PRESETS)), shape)

print("── ⑨ 실제 등록 동사의 결과 문장(직전 결과·꼬리표가 폴백이 아니다)")
NAMES = {"2": "두란", "?": "낯선 사람"}


def prose_problem(rec):
    """결과 기록 하나 → 문제 문자열(없으면 None). 폴백 = info_guard.fallback_json 그대로 나온 것."""
    try:
        p = brains._last_prose(rec, NAMES)
        t = G.event_tags(rec, NAMES)
    except Exception as e:                                  # 최소 기록으로 못 그리는 문장도 문제다(없는 칸은 .get 으로)
        return "%s/%s 예외 %s" % (rec.get("type"), rec.get("result"), type(e).__name__)
    fb = IG.fallback_json(rec)
    if p == fb or not t or tuple(t[0]) == ("misc", "기타", fb):
        return "%s/%s 폴백(%s · %s)" % (rec.get("type"), rec.get("result"), p[:40], t[0] if t else None)
    return None


def static_problems(verbs):
    """선언된 결과 코드 + 라우터 결과마다 최소 기록 {char, type, result, target}."""
    out = []
    for v, spec in verbs.items():
        for r in tuple(spec.get("results") or ()) + ("too_far", "lost"):
            prob = prose_problem({"char": "1", "type": v, "result": r, **({"target": "b2"} if spec.get("target", True) else {})})
            if prob:
                out.append(prob)
    return out


def dynamic_problems(verbs):
    """시험 장면(world A)에서 동사마다 보이는 대상 하나하나(대상 없는 동사는 한 번)에 실제로 해 본다 — 필수 칸은 첫 허용 값.
    결과 코드가 선언(+ too_far·lost) 안인지 · 그 결과의 문장·꼬리표가 폴백이 아닌지."""
    out, tried = [], 0
    for v, spec in verbs.items():
        d_, b_ = world(False)
        tids = [t["id"] for t in d_.view(b_[0], b_)["targets"]] if spec.get("target", True) else [None]
        for tid in tids:
            d_, b_ = world(False)
            o_ = d_.view(b_[0], b_)
            req = {f: ((spec.get("fields") or {}).get(f) or ("?",))[0] for f in (spec.get("required") or ())}
            act, err = CA.parse({"type": v, **({"target": tid} if tid else {}), **req}, o_)
            if err:
                out.append("%s %s 파서 거절 %s" % (v, tid, err))
                continue
            res = d_.act(b_[0], act, b_)
            tried += 1
            r = res.get("result")
            if r not in tuple(spec.get("results") or ()) + ("too_far", "lost") and res.get("type") == v:
                out.append("%s %s 선언 밖 결과 %s" % (v, tid, r))
            prob = prose_problem(b_[0].get("last") or {})
            if prob:
                out.append(prob)
    return out, tried


st_real = static_problems(real)
dy_real, tried_real = dynamic_problems(real)
check("⑨ 실제 등록 동사 %d개 — 선언된 결과 코드·too_far·lost 의 문장·꼬리표 폴백 없음(최소 기록) · 시험 장면 %d회 실행 결과도 선언 안·폴백 없음"
      % (len(real), tried_real), not st_real and not dy_real, st_real + dy_real)
with registered():
    st_probe = static_problems(PROBES)
    dy_probe, _n = dynamic_problems({"probe_touch": PROBES["probe_touch"]})
check("⑨ 부정 확인: 문장을 등록하지 않은 프로브 결과(probe_done)는 이 검사에 걸린다 · 라우터 결과(too_far·lost)는 등록부 공통 문장이라 안 걸린다",
      any("probe_touch/probe_done 폴백" in p for p in st_probe) and any("probe_touch/probe_done" in p for p in dy_probe)
      and not any(("/too_far" in p or "/lost" in p) for p in st_probe), (st_probe, dy_probe))

print("── ⑩ 벤치: 노출되는 등록부 동사가 하나 있을 때 단일·연속 dummy 가 끝까지 돈다")
BENCH_DRIVER = r'''
import os, sys
repo, out = sys.argv[1], sys.argv[2]
sys.path.insert(0, repo); sys.path.insert(0, os.path.join(repo, "tools"))
import freedom_bench as FB
FB.OUT_ROOT = out                                     # 결과·장면 지문 기록은 임시 폴더로(리포의 ab_runs 를 건드리지 않는다)
_engine = FB._engine
def engine(state_dir, call_limit=0):
    _engine(state_dir, call_limit)
    CA = FB.CA                                        # 이 프로세스 안에서만 등록 — 곁에 누가 보이면 노출되는 검증용 동사
    CA.COMMON_EXT["bench_reg_probe"] = {
        "expose": lambda view: any(t["id"] not in ("self", view.get("actor")) for t in view.get("targets", [])),
        "run": lambda d, bot, action, target, bots: CA._base(bot, action, "probe_done"),
        "fields": {"mode": ("soft", "hard")}, "results": ("probe_done",)}
    CA._EXTRA_LINES = dict(CA._extra_words(), bench_reg_probe="검증용 — 곁의 대상을 만진다")
FB._engine = engine
sys.argv = ["freedom_bench.py"] + sys.argv[3:]
FB.main()
'''
bench_out = os.path.join(TMP, "bench")
benv = {k: v for k, v in os.environ.items() if not k.startswith("DUNGEON_")}
benv["PYTHONUTF8"] = "1"
runs_ = {}
for rid, extra in (("reg-single", ["--scenes", "s1_town_guild,s3_wounded_ally", "--variants", "baseline,A-claude", "--reps", "1"]),
                   ("reg-seq", ["--seq", "q1_potion_relay", "--variants", "baseline", "--reps", "1"])):
    pb = subprocess.run([sys.executable, "-c", BENCH_DRIVER, HERE, bench_out, "--brain", "dummy", "--run-id", rid] + extra,
                        cwd=HERE, env=benv, capture_output=True, timeout=900)
    runs_[rid] = (pb.returncode, (pb.stdout + pb.stderr).decode("utf-8", "replace"))
rc1, out1 = runs_["reg-single"]
sd = os.path.join(bench_out, "reg-single")
meta1 = json.load(open(os.path.join(sd, "meta.json"), encoding="utf-8")) if os.path.exists(os.path.join(sd, "meta.json")) else {}
rows1 = [json.loads(x) for x in open(os.path.join(sd, "responses.jsonl"), encoding="utf-8")] if os.path.exists(os.path.join(sd, "responses.jsonl")) else []
space1 = [json.loads(x) for x in open(os.path.join(sd, "space.jsonl"), encoding="utf-8")] if os.path.exists(os.path.join(sd, "space.jsonl")) else []
txts = [open(p, encoding="utf-8").read() for p in glob.glob(os.path.join(sd, "scenes", "*.txt"))]
chk = meta1.get("skill_hint_check") or {}
check("⑩ 단일 장면 dummy 끝까지(rc 0 · 판단 4) · 4조합 사전 검사 2/2 변형 통과 · 장면 관측에 그 동사 줄 · 가능 공간에 그 동사(노출 표시)",
      rc1 == 0 and len(rows1) == 4 and len(chk) == 2 and all(r.get("pass") and r.get("same_block") for r in chk.values())
      and txts and all("- bench_reg_probe: 검증용" in t for t in txts)
      and any(r["combo"]["type"] == "bench_reg_probe" and r["exposed"] for r in space1), out1[-600:])
rc2, out2 = runs_["reg-seq"]
qd = os.path.join(bench_out, "reg-seq")
rows2 = [json.loads(x) for x in open(os.path.join(qd, "sequences.jsonl"), encoding="utf-8")] if os.path.exists(os.path.join(qd, "sequences.jsonl")) else []
k0 = glob.glob(os.path.join(qd, "prompts", "*__k0.txt"))
check("⑩ 연속 장면 dummy 끝까지(rc 0 · 결측 없음 · 판단 ≥1 · 기억 유지) · 판단 프롬프트에 추가 행동 블록",
      rc2 == 0 and len(rows2) == 1 and not rows2[0]["aborted"] and rows2[0]["n_decisions"] >= 1 and rows2[0]["memory_ok"]
      and k0 and "- bench_reg_probe: 검증용" in open(k0[0], encoding="utf-8").read(), out2[-600:])

print()
if fails:
    print("FAIL %d — %s" % (len(fails), " / ".join(fails)))
    sys.exit(1)
print("ALL PASS — verify_common_registry (p0.5.5 행동 등록부: 공개 정보만 읽는 노출·노출 밖 시도·라우터·입력 칸·런타임 주입·변형 같은 블록·빈 등록부 꼴·말 파일·결과 문장·벤치 완주, 실 LLM 0콜)")

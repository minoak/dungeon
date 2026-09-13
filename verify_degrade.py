# -*- coding: utf-8 -*-
"""D62 안전 차단 재요청 — 몸짓 서술만 접고, 접었음을 남긴다(지문 고정) — 60번째 게이트. LLM 0콜.
(2026-09-13 파트너 "프로를 돌리는건 비추 그럴거면 차라리 3.8플래시" → 4/4 차단(모델 공용 분류기) → t88 이분 4콜: 시트 단어 ∧ 몸짓 서술이
 다리, 하나만 빼도 통과 → "나도 A가 나아보이긴 하네" → 지문 고정 되물음 → "좋아 작업 부탁할게")
차단이면 대체 두뇌보다 먼저 프롬프트의 '· 최근 친목·건네기:' 줄(D47 ② acts 렌더)만 접고 같은 두뇌에게 다시 묻는다. 세계 장부·횟수 줄은
그대로. 통과한 결정에 brain_degraded{what,key,sticky} + 봇 dict 에 지문(brain_fold) 고정 — 다음 결정에서 같은 줄들이면 처음부터 접어 1콜,
줄이 바뀌면 전체 내용으로 복귀(전체가 통과하면 고정 해제). 접어도 막히면 대체 두뇌(opt-in) → 그래도 막히면 옛 정지.
게이트:
  ① 상수·렌더·_fold_gestures: 스위치 기본 켬 · 몸짓 줄이 ACTS_PREFIX 로 시작 · 접으면 그 줄만 사라지고 지문 12자 · 줄 없으면 (그대로, None)
  ② 차단 → 접기: 전체(차단) → 접은 것(통과) 2콜 같은 두뇌 · 접은 것 = _fold_gestures(전체) · 표식 sticky:false · brain_retries 1 · 봇 지문 고정 · 스냅샷 밖
  ③ 지문 고정: 같은 줄들 → 처음부터 접어 1콜 · 표식 sticky:true · brain_retries 없음
  ④ 지문 변경: 새 기록 → 전체 내용으로 1콜(통과) → 표식 없음·고정 해제 / 전체가 또 막히면 접기 → 새 지문 고정
  ⑤ 접어도 차단: 대체 두뇌 없음 → 2콜 뒤 오류(정지) / opt-in 대체 두뇌 → 접은 채로 3번째(표식 둘 다·덮어쓰기 해제)
  ⑥ 스위치 끔: 옛 동작(전체 → 덧말 재요청, 2콜, 오류)
  ⑦ 몸짓 줄 없는 판: 옛 동작(접을 것 없음)
  ⑧ 입력 오류(비차단) 경로 불변: 덧말 재요청 한 번, 표식 없음
  ⑨ 차단 원문 채집: 전체·접은 것만(덧말·대체 두뇌 시도는 안 남김)
  ⑩ 배선(소스): 러너 run_meta.block_degrade·⚠️ 줄 · STREAM_FORMAT · HARNESS D62 · _run_gates · 클라이언트 타입·표식
(기존 verify 59종은 별도 실행.)
"""
import os
import json
import tempfile
from unittest.mock import patch

STATE = os.path.join(tempfile.mkdtemp(prefix="wl_degrade_"), "state")
os.makedirs(STATE, exist_ok=True)
os.environ.update(DUNGEON_GM="0", DUNGEON_TURNS="4", DUNGEON_W="40", DUNGEON_H="16",
                  DUNGEON_SEED="7", DUNGEON_MONSTERS="0", DUNGEON_TRAPS="0", DUNGEON_LURKERS="0",
                  DUNGEON_DEPTHS="1", DUNGEON_BESTIARY_FILE="", DUNGEON_ACTION_MODE="compose",
                  DUNGEON_BRAIN_BACKEND="gemini_api", DUNGEON_STATE_DIR=STATE)
for k in ("DUNGEON_PARTY_FILE", "DUNGEON_BRAIN_FALLBACK", "DUNGEON_GEMINI_MODEL", "DUNGEON_BLOCK_DEGRADE"):
    os.environ.pop(k, None)

import brains                                        # noqa: E402
import dungeon_gm as G                               # noqa: E402
import scenario                                      # noqa: E402  (조합형 관측 = verify_brain_pause 와 같은 장면 빌더)

HERE = os.path.dirname(os.path.abspath(__file__))
BLOCKED = ("", "빈 응답 rc=200 | PROHIBITED_CONTENT")
OK_JSON = '{"type":"search","target":"self","reason":"살핀다"}'


class C:
    failed = 0


def check(name, cond):
    print(("  OK   " if cond else " FAIL  ") + name)
    if not cond:
        C.failed += 1


def tripwire(*args, **kwargs):
    raise AssertionError("검증 중 실제 백엔드 호출 금지")


brains._call_gemini = brains._call_cli = brains._call_anthropic = tripwire

ROWS = ["############",
        "#12.3.....>#",
        "############"]
NAMES = {"1": "두란", "2": "카야", "3": "피른"}


def scene():
    """조합형 관측(compose-v0.4 · 행동 계약 v0.5)이 나오는 장면 — 흉내 응답 `search self` 가 수락돼야 접기 경로를 잴 수 있다."""
    d, bots = scenario.build({"map": ROWS, "seed": 7,
                              "bots": {"1": {"potions": 0}, "2": {"potions": 0}, "3": {"potions": 0}}})
    d.composed_actions = d.auto_approach = True
    d.events, d.relations, d.trail_on, d.floor_on = True, True, True, True
    d.give_verb, d.bond_verb = True, True
    for b in bots:
        b["name"] = NAMES.get(b["char"], b.get("name"))
    d.turn = 5
    return d, bots


class Brain:
    """_call_claude 흉내 — block: gestures(몸짓 줄 있으면 차단) | all(gemini 면 전부 차단) | none. 대체 두뇌(anthropic)는 늘 통과."""
    def __init__(self, block="gestures"):
        self.calls, self.block = [], block

    def __call__(self, prompt, model="haiku"):
        be = brains.backend_name()
        self.calls.append((be, prompt))
        has = brains.ACTS_PREFIX in prompt
        if be == "gemini_api" and (self.block == "all" or (self.block == "gestures" and has)):
            return BLOCKED
        return OK_JSON

    @property
    def backends(self):
        return [b for b, _ in self.calls]


def ask(mock, obs, bot, bots, **env):
    with patch.dict(os.environ, **env), \
            patch.object(brains, "_call_claude", side_effect=mock), \
            patch.object(brains.G, "dummy_brain", side_effect=AssertionError("자동 대행 금지")):
        return brains.claude_brain(obs, bot["char"], bot, bots)


def has_prefix(prompt):
    return brains.ACTS_PREFIX in prompt


def blocklog_count():
    p = os.path.join(STATE, "brain_block.log")
    if not os.path.exists(p):
        return 0
    with open(p, encoding="utf-8") as f:
        return sum(1 for ln in f if ln.strip())


print("── ① 상수·렌더·_fold_gestures")
d, bots = scene()
b1, b2, b3 = bots
d.view(b1, bots)                                              # 조합형 대상 해석은 '지금 보이는 실물'(관측 등록) 기준 — 먼저 한 번 본다
r_bond = d.act(b1, {"type": "bond", "target": "b2", "form": "등을 토닥이며 안심시켜준다"}, bots)   # 두란→카야 몸짓 한 건: 뼈 bond + 양쪽 장부 acts
assert r_bond.get("result") == "done", r_bond                # (acts 만 있고 뼈가 없으면 관측 relations 에 안 실린다 — 실판과 같은 경로로)
obs = d.view(b1, bots)
names = {b["char"]: b["name"] for b in bots}
wire = brains._wire(obs, names, compose=True)
gest_lines = [ln for ln in wire.split("\n") if ln.startswith(brains.ACTS_PREFIX)]
check("① 스위치 기본 켬(DUNGEON_BLOCK_DEGRADE 미설정)", brains.BLOCK_DEGRADE_ON is True)
check("① 렌더: 몸짓 줄이 ACTS_PREFIX 로 시작하고 형태를 담는다", len(gest_lines) == 1 and "등을 토닥이며" in gest_lines[0])
folded, key = brains._fold_gestures(wire)
check("① 접으면 그 줄만 사라지고 지문 12자", key and len(key) == 12 and not has_prefix(folded)
      and folded.count("\n") == wire.count("\n") - 1 and "카야" in folded)
check("① 줄 없으면 (그대로, None)", brains._fold_gestures("# 시트\n- 성격: x") == ("# 시트\n- 성격: x", None))

print("── ② 차단 → 접기")
mock = Brain("gestures")
dec = ask(mock, obs, b1, bots)
check("② 2콜: 전체(몸짓 줄 있음) → 접은 것(없음)", len(mock.calls) == 2 and has_prefix(mock.calls[0][1]) and not has_prefix(mock.calls[1][1]))
check("② 접은 것 = _fold_gestures(전체) · 지문 = 렌더 지문", mock.calls[1][1] == brains._fold_gestures(mock.calls[0][1])[0]
      and brains._fold_gestures(mock.calls[0][1])[1] == key)
check("② 같은 두뇌 · 대체 두뇌 없음", mock.backends == ["gemini_api", "gemini_api"] and "brain_fallback" not in dec)
check("② 결정 성공 · 표식 sticky:false · 차단 오류 보존", dec.get("src") != "error"
      and dec.get("brain_degraded") == {"what": "gestures", "key": key, "sticky": False}
      and len(dec.get("brain_retries") or []) == 1 and "PROHIBITED_CONTENT" in dec["brain_retries"][0]["reason"])
check("② 봇에 지문 고정 · 스냅샷(스트림) 밖", b1.get("brain_fold") == key and "brain_fold" not in G.bot_snapshot(b1))
check("② 차단 원문 1건 채집(전체)", blocklog_count() == 1)

print("── ③ 지문 고정")
mock = Brain("gestures")
dec = ask(mock, obs, b1, bots)
check("③ 같은 줄들 → 처음부터 접어 1콜", len(mock.calls) == 1 and not has_prefix(mock.calls[0][1]))
check("③ 표식 sticky:true · 재시도 기록 없음", dec.get("brain_degraded") == {"what": "gestures", "key": key, "sticky": True}
      and "brain_retries" not in dec and b1.get("brain_fold") == key)
check("③ 채집 없음(차단 없었다)", blocklog_count() == 1)

print("── ④ 지문 변경")
d.view(b2, bots)
assert d.act(b2, {"type": "bond", "target": "b1", "form": "어깨를 두드린다"}, bots).get("result") == "done"   # 카야→두란: 두란 장부의 카야 줄에 기록 추가 → 지문이 달라진다
obs2 = d.view(b1, bots)
key2 = brains._fold_gestures(brains._wire(obs2, names, compose=True))[1]
check("④ 새 기록 → 지문 바뀜", key2 and key2 != key)
mock = Brain("none")
dec = ask(mock, obs2, b1, bots)
check("④ 전체 내용으로 1콜(통과) → 표식 없음 · 고정 해제", len(mock.calls) == 1 and has_prefix(mock.calls[0][1])
      and "brain_degraded" not in dec and "brain_fold" not in b1)
mock = Brain("gestures")
dec = ask(mock, obs2, b1, bots)
check("④ 전체가 또 막히면 접기 → 새 지문 고정", len(mock.calls) == 2 and has_prefix(mock.calls[0][1]) and not has_prefix(mock.calls[1][1])
      and dec.get("brain_degraded") == {"what": "gestures", "key": key2, "sticky": False} and b1.get("brain_fold") == key2)
check("④ 채집 +1(전체)", blocklog_count() == 2)

print("── ⑤ 접어도 차단")
b1.pop("brain_fold", None)
mock = Brain("all")
dec = ask(mock, obs2, b1, bots)
check("⑤ 대체 두뇌 없음: 전체 → 접기 → 오류(정지), 2콜", len(mock.calls) == 2 and has_prefix(mock.calls[0][1]) and not has_prefix(mock.calls[1][1])
      and dec.get("src") == "error" and len(dec.get("attempt_errors") or []) == 2 and "brain_fold" not in b1)
check("⑤ 채집 +2(전체·접은 것)", blocklog_count() == 4)
mock = Brain("all")
dec = ask(mock, obs2, b1, bots, DUNGEON_BRAIN_FALLBACK="anthropic_api")
check("⑤ opt-in 대체 두뇌: 전체(gemini) → 접기(gemini) → 접은 채 대체 두뇌", mock.backends == ["gemini_api", "gemini_api", "anthropic_api"]
      and mock.calls[2][1] == mock.calls[1][1] and not has_prefix(mock.calls[2][1]))
check("⑤ 표식 둘 다 · 재시도 2 · 덮어쓰기 해제", dec.get("brain_fallback") == "anthropic_api"
      and dec.get("brain_degraded") == {"what": "gestures", "key": key2, "sticky": False}
      and len(dec.get("brain_retries") or []) == 2 and brains.backend_name() == "gemini_api")
check("⑤ 채집 +2(대체 두뇌 시도는 안 남김)", blocklog_count() == 6)

print("── ⑥ 스위치 끔 · ⑦ 몸짓 줄 없는 판 · ⑧ 입력 오류 경로")
b1.pop("brain_fold", None)
mock = Brain("gestures")
with patch.object(brains, "BLOCK_DEGRADE_ON", False):
    dec = ask(mock, obs2, b1, bots)
check("⑥ 끄면 옛 동작: 전체 → 덧말 재요청(몸짓 줄 그대로) 2콜, 오류", len(mock.calls) == 2 and has_prefix(mock.calls[1][1])
      and "직전 응답의 입력 오류" in mock.calls[1][1] and dec.get("src") == "error" and "brain_fold" not in b1)
check("⑥ 채집 +1(덧말 재요청은 안 남김)", blocklog_count() == 7)
d2, bots2 = scene()
obs3 = d2.view(bots2[0], bots2)
mock = Brain("all")
dec = ask(mock, obs3, bots2[0], bots2)
check("⑦ 접을 줄이 없으면 옛 동작(2콜, 오류, 고정 없음)", len(mock.calls) == 2 and not any(has_prefix(p) for _, p in mock.calls)
      and "직전 응답의 입력 오류" in mock.calls[1][1] and dec.get("src") == "error" and "brain_fold" not in bots2[0])
check("⑦ 채집 +1", blocklog_count() == 8)


class Bad:
    def __init__(self):
        self.calls = []

    def __call__(self, prompt, model="haiku"):
        self.calls.append(prompt)
        return "이건 JSON 이 아니다" if len(self.calls) == 1 else OK_JSON


bad = Bad()
dec = ask(bad, obs2, b1, bots)
check("⑧ 입력 오류(비차단): 덧말 재요청 한 번 · 몸짓 줄 그대로 · 표식 없음", len(bad.calls) == 2 and has_prefix(bad.calls[1])
      and "직전 응답의 입력 오류" in bad.calls[1] and dec.get("src") != "error" and "brain_degraded" not in dec
      and len(dec.get("brain_retries") or []) == 1)
check("⑧ 채집 없음", blocklog_count() == 8)

print("── ⑨ 채집 로그 내용 · ⑩ 배선(소스)")
with open(os.path.join(STATE, "brain_block.log"), encoding="utf-8") as f:
    rows = [json.loads(ln) for ln in f if ln.strip()]
check("⑨ 채집 항목 = 전체 5 + 접은 것 3", len(rows) == 8 and sum(1 for r in rows if has_prefix(r["prompt"])) == 5
      and all(r["char"] == "1" and "PROHIBITED_CONTENT" in r["label"] for r in rows))


def src(path):
    with open(os.path.join(HERE, path), encoding="utf-8") as f:
        return f.read()


check("⑩ 러너: run_meta.block_degrade · ⚠️ 줄", "block_degrade=brains.BLOCK_DEGRADE_ON" in src("show_runner.py")
      and 'dec.get("brain_degraded")' in src("show_runner.py"))
check("⑩ STREAM_FORMAT: brain_degraded · block_degrade", "brain_degraded" in src("STREAM_FORMAT.md") and "`block_degrade`" in src("STREAM_FORMAT.md"))
check("⑩ HARNESS D62 절", "D62" in src(os.path.join("design", "HARNESS_DESIGN.md")))
check("⑩ 게이트 등록", "verify_degrade" in src("_run_gates.sh"))
check("⑩ 클라이언트: 타입 · 로그 줄 · 초점 카드 표식", "brain_degraded" in src(os.path.join("game", "src", "stream", "types.ts"))
      and "degMark" in src(os.path.join("game", "src", "text", "evline.ts"))
      and "degMark" in src(os.path.join("game", "src", "ui", "FocusCard.ts")))

print("ALL PASS" if C.failed == 0 else "FAIL %d" % C.failed)

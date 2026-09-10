# -*- coding: utf-8 -*-
"""조합형 선행 프로브 검증. 가짜 모델 응답 → 파서 → 실제 엔진/스트림, 실 LLM 0콜."""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

TMP = tempfile.TemporaryDirectory(prefix="wl_compose_")
ROOT = Path(__file__).resolve().parent
os.environ.update(DUNGEON_ACTION_MODE="compose", DUNGEON_BRAIN_BACKEND="dummy",
                  DUNGEON_GM="0", DUNGEON_STEP_DELAY="0", DUNGEON_TURNS="12",
                  DUNGEON_W="40", DUNGEON_H="16", DUNGEON_DEPTHS="1",
                  DUNGEON_SEED="7", DUNGEON_BESTIARY_FILE="",
                  DUNGEON_STATE_DIR=str(Path(TMP.name) / "state"),
                  DUNGEON_STREAM_OBS="1")
for name in ("DUNGEON_GIVE", "DUNGEON_BOND", "DUNGEON_WAIT", "DUNGEON_REST"):
    os.environ[name] = "1"
os.environ.pop("DUNGEON_PARTY_FILE", None)

import brains
import dungeon_gm as G
import launcher
import scenario
import show_runner

checks = 0


def check(label, condition):
    global checks
    assert condition, label
    checks += 1
    print("  OK " + label)


def scene():
    d, bots = scenario.build({"map": ["############", "#12.g.....>#", "#..=.......#", "############"],
                           "seed": 7, "bots": {"1": {"potions": 2}, "2": {"potions": 0}}})
    d.composed_actions = False
    return d, bots


def decide(d, bots, payload, obs=None):
    obs = d.view(bots[0], bots) if obs is None else obs
    captured = []
    def call(prompt, model="haiku"):
        captured.append(prompt)
        return json.dumps({"reason": "검증용 판단", **payload}, ensure_ascii=False)
    with patch.object(brains, "_call_claude", call):
        dec = brains.claude_brain(obs, "1", bots[0], bots)
    return dec, captured[0]


check("실험 모드와 compose-v0.4 기록", not brains.MENU and brains.COMPOSE
      and brains.action_metadata() == {"action_mode": "compose", "compose_profile": "compose-v0.4", "auto_approach": True})
d, bots = scene()
obs = d.view(bots[0], bots)
saved = copy.deepcopy(obs)
obs["options"] = [{"n": 1, "type": "wait", "label": "이 메뉴 문구는 모델에게 보이면 안 된다"}]
dec, prompt = decide(d, bots, {"type": "give", "target": "b2", "item": "potion",
                              "say": "이걸 받아.", "say_kind": "제안", "to": "2"}, obs)
check("번호 목록 없이 대상·행동·말을 한 판단 공간에 표시", "# 판단 공간" in prompt and "[b2]" in prompt
      and "COMMON:" in prompt and "의사소통: 잡담 / 제안" in prompt
      and "이 메뉴 문구" not in prompt and "# 선택지" not in prompt)
check("직접 건네기는 goto 보정 없이 물리로 전달", dec["type"] == "give" and dec["item"] == "potion"
      and dec["to"] == "2" and dec["say_kind"] == "제안")
result = d.act(bots[0], dec, bots)
check("실제 물약 소유권 이전", result["result"] == "given" and bots[0]["potions"] == 1 and bots[1]["potions"] == 1)
dec, _ = decide(d, bots, {"type": "bond", "target": "b2", "form": "손을\n가볍게 잡는다"})
result = d.act(bots[0], dec, bots)
check("친목 form 정제와 수신 사건", result["result"] == "done" and result["form"] == "손을 가볍게 잡는다"
      and bots[1]["last"]["type"] == "bonded")
check("직렬화가 원래 관측을 바꾸지 않음", all(obs[k] == v for k, v in saved.items() if k != "options"))

d, bots = scene()
bots[1]["x"] = 4
dec, _ = decide(d, bots, {"type": "give", "target": "b2", "item": "potion"})
result = d.act(bots[0], dec, bots)
check("멀리 있는 알려진 대상: 파싱 성공 후 접근 시작", dec["src"] == "haiku" and result["result"] == "approaching"
      and bots[0].get("order") and bots[0]["potions"] == 2)

for payload, error in [({"type": "attack", "target": "m999"}, "invalid_target"),
                       ({"type": "use", "target": "b2"}, "invalid_type"),
                       ({"type": "give", "target": "b2", "item": "i1"}, "invalid_item"),
                       ({"type": "search", "target": "b2"}, "unexpected_target"),
                       ({"choice": 1}, "invalid_type")]:
    d, bots = scene()
    obs = d.view(bots[0], bots)
    expected = G.dummy_brain(obs, "1")
    dec, _ = decide(d, bots, payload, obs)
    check(error + ": 기록하고 같은 결정에서 규칙두뇌로 대체", dec.get("input_error") == error
          and dec["src"] == "fallback" and all(dec[k] == v for k, v in expected.items()))
    d.act(bots[0], dec, bots)

d, bots = scene()
hidden_id = "m%d" % d.monsters[0].id
d.monsters[0].concealed = True
dec, _ = decide(d, bots, {"type": "goto", "target": hidden_id})
check("세계에 존재해도 현재 모르는 ID는 차단", dec.get("input_error") == "invalid_target")

d, bots = scene()
obs = d.view(bots[0], bots)
obs["known"] = {"statics": [{"id": "f987", "kind": "상자", "zone": "이전 방", "turn": 1}]}
move, why = brains._compose_pick({"type": "goto", "target": "f987"}, obs)
_, attack_why = brains._compose_pick({"type": "attack", "target": "f987"}, obs)
check("기억 속 정적 대상은 귀환에만 사용", move and why is None and attack_why == "invalid_target")
for typ in ("search", "drink", "wait", "rest", "explore"):
    d, bots = scene()
    dec, _ = decide(d, bots, {"type": typ})
    result = d.act(bots[0], dec, bots)
    check(typ + ": 대상 없는 기존 동작 연결", dec["type"] == typ and dec["src"] == "haiku"
          and ((result.get("radius") == 1 and "found" in result) if typ == "search" else "result" in result))

d, bots = scene()
obs = d.view(bots[0], bots)
direction = obs["sights"]["ways"][0]["bearing"]
dec, _ = decide(d, bots, {"type": "explore", "target": direction}, obs)
check("관측에 나온 방향 탐색", dec.get("target") == direction and dec["src"] == "haiku")
dec, _ = decide(d, bots, {"type": "goto", "target": "b2", "then": [{"type": "search"}]})
check("기존 객체 작정 유지", dec["then"] == [{"type": "search"}])
dec, _ = decide(d, bots, {"type": "goto", "target": "b2", "then": [1]})
check("번호 작정은 숨긴 메뉴를 참조하지 않음", "then" not in dec)
with patch.dict(os.environ, {"DUNGEON_GIVE": "0"}):
    dec, prompt = decide(d, bots, {"type": "give", "target": "b2", "item": "potion"})
    check("꺼진 기능은 현재 행동 목록과 파서에서 제외", dec.get("input_error") == "invalid_type"
          and "give" not in prompt.rsplit("COMMON:", 1)[1].splitlines()[0])

# 실제 모델 대신 고정 JSON 응답으로 러너 전체를 두 번 돌려 기록과 결정론 확인.
def run():
    with patch.object(brains, "_call_claude", lambda *a, **k: '{"reason":"주변을 살핀다","type":"search","target":"self"}'), \
            contextlib.redirect_stdout(io.StringIO()):
        show_runner.main()
    records = [json.loads(s) for s in (Path(os.environ["DUNGEON_STATE_DIR"]) / "stream.jsonl").read_text(encoding="utf-8").splitlines()]
    records[0].pop("started", None)
    return records

first, second = run(), run()
check("고정 응답 원정 2회 결정론", first == second and first[-1]["kind"] == "end")
check("스트림에서 compose 실험을 식별", first[0]["action_mode"] == "compose" and first[0]["compose_profile"] == "compose-v0.4"
      and first[0]["menu"] is False)
decisions = [v for rec in first for v in rec.get("decisions", {}).values()]
check("러너 결정은 직접 행동이며 관측도 보존", decisions and all("choice" not in v for v in decisions)
      and any(v.get("src") == "haiku" and "obs" in v for v in decisions))

# 론처가 설정을 실제 자식 러너에 전달하는가: 임시 디렉터리·dummy만 사용.
runner = launcher.Runner(str(ROOT), str(Path(TMP.name) / "launch"), str(Path(TMP.name) / "runs"))
try:
    with patch.dict(os.environ, {"DUNGEON_ACTION_MODE": "menu", "DUNGEON_MENU": "1"}):
        reply = runner.start({"party": "default", "brain": "dummy", "seed": 7}, "unused")
    runner.proc.wait(timeout=45)
    meta = json.loads((Path(runner.state_dir) / "stream.jsonl").read_text(encoding="utf-8").splitlines()[0])
    check("론처는 부모의 구형 설정과 무관하게 기본 compose로 실행", reply["action_mode"] == "compose" and meta["action_mode"] == "compose"
          and runner.status()["action_mode"] == "compose" and runner.proc.returncode == 0)
finally:
    runner.stop()
try:
    runner.start({"party": "default", "brain": "dummy", "action_mode": "typo"}, "unused")
    raise AssertionError("불명 모드가 접수됨")
except launcher.BadRequest:
    check("잘못된 론처 모드는 실행 전에 거부", not runner.running())

for mode, expected in [("menu", True), ("free", False)]:
    env = {**os.environ, "DUNGEON_ACTION_MODE": mode}
    raw = subprocess.check_output([sys.executable, "-c", "import brains,json;print(json.dumps([brains.MENU,brains.COMPOSE,brains.action_metadata()]))"], cwd=ROOT, env=env, text=True)
    value = json.loads(raw)
    check(mode + ": 별도 프로세스에서 기존 모드 복귀", value[:2] == [expected, False] and value[2]["action_mode"] == mode)

env = {k: v for k, v in os.environ.items() if k not in ('DUNGEON_ACTION_MODE', 'DUNGEON_MENU')}
raw = subprocess.check_output([sys.executable, '-c',
    'import brains,json;print(json.dumps([brains.COMPOSE,brains.MENU,brains.action_metadata()]))'],
    cwd=ROOT, env=env, text=True)
value = json.loads(raw)
check('설정 없는 직접 실행도 조합형이 기본', value[:2] == [True, False] and value[2]['action_mode'] == 'compose')

TMP.cleanup()
print("ALL PASS — verify_compose (%d checks, 실 LLM 0콜)" % checks)

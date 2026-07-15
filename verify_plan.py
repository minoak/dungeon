# -*- coding: utf-8 -*-
"""작정 큐(D16) 헤들리스 검증 — 12번째 게이트.
D16: "에이전트는 결정 시 현재 행동에 더해 최대 2수를 이어 작정할 수 있다. 큐는 세계에 거는
예약이 아니라 에이전트가 품는 의도이며, 세계는 언제든 그것을 찢을 권리를 갖는다."
게이트:
  ① then 저작 검증(brains._then): 보이는 id만·환각부터 뒤 드랍·상한 PLAN_MAX·메뉴 번호 관용·
     explore 방위 정규화·비리스트 무시
  ② 접수·집행: act(then)→bot['plan'] 보관 / think_all 이 plan 봇을 LLM 없이(콜 0) src='plan'
     결정으로 집행 + intent 갱신(판단의 연속)
  ③ 착수 시점 재검증: 대상 소멸(goto/attack/interact)·인접 아님(attack/interact)·알 수 없는
     동사 → 계획 파기 + last=plan_broken(사유) + 같은 틱 LLM 재결정 폴스루
  ④ 인터럽트 파기: 피격(_monster_attack hit)·경로 경합(blocked) → plan 소거
  ⑤ lost 파기: 움직이는 목표 허탕 → plan 소거
  ⑥ explore 작정 = 발동 시점 그 자리 해석(plan_step 무조건 통과, _set_explore 가 현재 위치 기준)
  ⑦ 스트림 계약 불변: bot_snapshot 에 plan/then 없음 + 재스폰 봇 plan 빈 채(층 리셋)
  ⑧ 하위호환: then 없는 결정은 plan 미접촉(기존 흐름 그대로)
  ⑨ 러너 통합(스텁 판, STREAM_OBS=1): then 이 스트림에 실림 / src='plan' 결정 발화 /
     **작정 연속성 전수 감사** — then 딸린 결정의 다음 결정은 (a) src='plan'으로 then[0]과 일치
     하거나 (b) obs.last 가 파기 사유(hurt/encounter/blocked/lost/no_path/plan_broken)를 보고 /
     ab_menu.parse_stream 의 llm_calls+plan_steps==decisions / 2회 실행 결정론
(기존 verify 11종은 별도 실행.)
"""
import io
import os
import re
import json
import contextlib

os.environ.update(DUNGEON_GM="0", DUNGEON_TURNS="120", DUNGEON_W="40", DUNGEON_H="16",
                  DUNGEON_SEED="7", DUNGEON_MONSTERS="3", DUNGEON_TRAPS="3",
                  DUNGEON_LURKERS="1", DUNGEON_DEPTHS="2",
                  DUNGEON_MENU="1", DUNGEON_STEP_DELAY="0",
                  DUNGEON_PARTY_FILE="/nonexistent",     # 내장 2인 고정(회귀 그물)
                  DUNGEON_STREAM_OBS="1",                # ⑨ 파기 사유 감사(obs.last)에 필요
                  DUNGEON_STATE_DIR=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                 "state_planverify"))
os.environ["DUNGEON_BESTIARY_FILE"] = ""   # 도감 영속 차단(게이트 격리 원칙)

import brains
import dungeon_gm as G


class C:
    failed = 0


def check(name, cond):
    print("  [%s] %s" % ("OK" if cond else "FAIL", name))
    if not cond:
        C.failed += 1


TEAR_REASONS = {"hurt", "plan_broken"}          # last.type 로 오는 파기 사유
TEAR_RESULTS = {"encounter", "blocked", "lost", "no_path",
                "sighted"}   # last.result 로 오는 파기 사유(sighted=D19 목격 정지, SCAN 기본 1 승격으로 합류)


# ───────────────────── ① then 저작 검증 (순수 함수) ─────────────────────
def unit_then():
    obs = {"sights": {"exit": {"id": "exit"}, "features": [{"id": "f1"}],
                      "monsters": [{"id": "m2"}], "bots": []},
           "party": [],
           "options": [{"n": 1, "type": "goto", "target": "exit", "label": "이동: 계단"},
                       {"n": 2, "type": "search", "label": "수색"}]}
    t = brains._then({"then": [{"type": "interact", "target": "f1"},
                               {"type": "goto", "target": "exit"},
                               {"type": "search"}]}, obs)
    check("① 유효 then 통과 + 상한 %d수 절단" % G.PLAN_MAX,
          t == [{"type": "interact", "target": "f1"}, {"type": "goto", "target": "exit"}])
    t = brains._then({"then": [{"type": "goto", "target": "f99"}, {"type": "search"}]}, obs)
    check("① 환각 id → 그 항목부터 뒤 전부 드랍", t == [])
    t = brains._then({"then": [{"type": "search"}, {"type": "goto", "target": "f99"}]}, obs)
    check("① 앞수 유효·뒷수 불량 → 앞수만 생존", t == [{"type": "search"}])
    t = brains._then({"then": [1, 2]}, obs)
    check("① 메뉴 번호 관용(엔진 열거 행동으로 해석)",
          t == [{"type": "goto", "target": "exit"}, {"type": "search"}])
    t = brains._then({"then": [{"type": "explore", "target": "ne"}]}, obs)
    check("① explore 방위 정규화(ne→NE)", t == [{"type": "explore", "target": "NE"}])
    check("① 비리스트/부재 then 무시",
          brains._then({"then": "search"}, obs) == [] and brains._then({}, obs) == [])


# ───────────────────── ②~⑧ 엔진 유닛 ─────────────────────
def call_counter(sink, then_json=""):
    def stub(prompt, model="haiku"):
        sink.append(prompt)
        ns = re.findall(r"^(\d+)\. ", prompt, re.M)
        return ('{"reason": "검증 판단", "choice": %s%s, "say": "간다"}'
                % (ns[-1] if ns else 1, then_json))
    return stub


def units():
    # ② 접수: act(then) → plan 보관
    d = G.Dungeon(seed=7)
    bots = []
    for c in "12":
        bots.append(G.spawn(d, c, bots))
    b1, b2 = bots
    d.act(b1, {"type": "explore", "then": [{"type": "search"}, {"type": "explore"}]}, bots)
    check("② act(then) → bot['plan'] 보관(2수)",
          b1["plan"] == [{"type": "search"}, {"type": "explore"}])
    d.act(b1, {"type": "explore", "then": [dict(s) for s in [{"type": "search"}]] * 5}, bots)
    check("② 엔진측 상한 방어(PLAN_MAX 절단)", len(b1["plan"]) == G.PLAN_MAX)

    # ② 집행: plan 봇은 LLM 콜 0 + src='plan' + intent 갱신
    b1["order"], b1["path"] = None, []
    b1["plan"] = [{"type": "search"}]
    b2["plan"] = []
    calls = []
    brains._call_claude = call_counter(calls)
    dec = brains.think_all(d, bots, {})
    check("② plan 봇 = src'plan' 결정·search 집행",
          dec["1"].get("src") == "plan" and dec["1"].get("type") == "search")
    check("② plan 봇 LLM 콜 0 (사고 봇만 콜: %d)" % len(calls), len(calls) == 1)
    check("② 작정 수도 intent 갱신(판단의 연속)",
          b1["intent"].get("type") == "search" and b1["intent"].get("src") == "plan")
    check("② 집행 후 큐 소진", b1["plan"] == [])

    # ③ 착수 재검증 — 대상 소멸/인접 아님/알 수 없는 동사
    m = next(mm for mm in d.monsters if mm.alive)
    b1["plan"] = [{"type": "attack", "target": "m%d" % m.id}]
    alive_save = m.alive
    m.alive = False
    step = d.plan_step(b1, bots)
    check("③ attack 대상 소멸 → 파기+plan_broken(대상 소멸)",
          step is None and b1["plan"] == [] and
          (b1.get("last") or {}).get("type") == "plan_broken" and
          b1["last"].get("why") == "대상 소멸")
    m.alive = alive_save
    m.x, m.y = d.exit[0], d.exit[1]                      # 봇에게서 먼 자리로(비인접 보장 목적)
    if abs(b1["x"] - m.x) + abs(b1["y"] - m.y) == 1:     # 우연 인접이면 봇을 비켜 둠
        b1["x"] = m.x + 5
    b1["plan"] = [{"type": "attack", "target": "m%d" % m.id}]
    step = d.plan_step(b1, bots)
    check("③ attack 비인접 → 파기+plan_broken(인접 아님)",
          step is None and b1["last"].get("why") == "인접 아님")
    b1["plan"] = [{"type": "goto", "target": "m999"}]
    step = d.plan_step(b1, bots)
    check("③ goto 대상 소멸 → 파기(작정은 explore 폴백 안 탐)",
          step is None and b1["last"].get("why") == "대상 소멸")
    b1["plan"] = [{"type": "dance"}]
    step = d.plan_step(b1, bots)
    check("③ 알 수 없는 동사 → 파기", step is None and b1["last"].get("why") == "알 수 없는 동사")
    # ③ 파기 직후 같은 틱 LLM 폴스루(think_all 경유)
    b1["plan"] = [{"type": "goto", "target": "m999"}]
    calls = []
    brains._call_claude = call_counter(calls)
    dec = brains.think_all(d, [b1], {})
    check("③ 파기 봇 같은 틱 LLM 재결정(src≠plan) + obs 에 plan_broken 노출",
          dec["1"].get("src") != "plan" and len(calls) == 1 and
          "작정이 깨졌다" in calls[0])   # D17-3: wire 가 문장형 — plan_broken 은
                                         #   _last_prose 어휘("작정이 깨졌다")로 노출된다

    # ④ 인터럽트 파기 — 피격 / 경로 경합(blocked)
    hurt_bot = G.spawn(G.Dungeon(seed=9), "1", [])
    hurt_bot["dex"] = -30                                # AC 바닥 → 항상 명중(결정론 무관 표적)
    hurt_bot["order"], hurt_bot["path"] = "exit", [(1, 1)]
    hurt_bot["plan"] = [{"type": "search"}]
    d9 = G.Dungeon(seed=9)
    ev = d9._monster_attack(d9.monsters[0], hurt_bot)
    check("④ 피격 인터럽트 → order·plan 동시 파기",
          ev["hit"] and hurt_bot["plan"] == [] and hurt_bot["order"] is None)
    m2 = next(mm for mm in d.monsters if mm.alive)
    m2.concealed = False
    b2["order"], b2["path"] = "@%d,%d" % (m2.x + 3, m2.y), [(m2.x, m2.y)]
    b2["plan"] = [{"type": "search"}]
    res = d.step_order(b2, bots)
    check("④ 경로 경합(blocked) → plan 파기",
          res["result"] == "blocked" and b2["plan"] == [])

    # ⑤ lost 파기 — 움직이는 목표 허탕
    m3 = next(mm for mm in d.monsters if mm.alive)
    b1["order"], b1["path"] = "m%d" % m3.id, []
    m3.x, m3.y = (b1["x"] + 7) % d.w, b1["y"]            # 곁에 없게 옮겨 둠
    if abs(b1["x"] - m3.x) + abs(b1["y"] - m3.y) <= 1:
        m3.x = (b1["x"] + 9) % d.w
    b1["plan"] = [{"type": "search"}]
    res = d.step_order(b1, bots)
    check("⑤ lost(허탕) → plan 파기", res["result"] == "lost" and b1["plan"] == [])

    # ⑥ explore 작정 = 발동 시점 자리 해석(plan_step 통과 → _set_explore 현재 위치)
    b1["plan"] = [{"type": "explore"}]
    step = d.plan_step(b1, bots)
    check("⑥ explore 작정 착수 통과(열린 동사)", step == {"type": "explore"})
    res = d.act(b1, step, bots)
    check("⑥ 발동 시점 해석(현재 위치 기준 pathed/no_path)",
          res["type"] == "explore" and res["result"] in ("pathed", "no_path"))

    # ⑦ 계약 불변 + 층 리셋
    check("⑦ bot_snapshot 에 plan 없음(화이트리스트 밖)",
          all("plan" not in G.bot_snapshot(b) for b in bots))
    n = G.spawn(G.Dungeon(seed=7, depth=2), "1", [])
    check("⑦ 재스폰 봇 plan 빈 채(층 전이 리셋)", n.get("plan") == [])

    # ⑧ 하위호환 — then 없는 결정은 plan 미접촉
    b2["plan"] = [{"type": "search"}]
    d.act(b2, {"type": "explore"}, bots)
    check("⑧ then 없는 act 는 plan 미접촉", b2["plan"] == [{"type": "search"}])
    b2["plan"] = []


# ───────────────────── ⑨ 러너 통합(스텁 판) ─────────────────────
def run_stub_game():
    import show_runner
    show_runner.STEP_DELAY = 0
    import time as _t
    _t.sleep = lambda s: None
    with contextlib.redirect_stdout(io.StringIO()), \
         contextlib.redirect_stderr(io.StringIO()):
        show_runner.main()
    p = os.path.join(show_runner.STATE, "stream.jsonl")
    return open(p, encoding="utf-8").read()


def normalized(raw):
    out = []
    for line in raw.splitlines():
        r = json.loads(line)
        r.pop("started", None)
        out.append(json.dumps(r, ensure_ascii=False, sort_keys=True))
    return out


def audit_plan(raw):
    """작정 연속성 전수 감사 — then 딸린 결정의 다음 결정은 계획 이행이거나 정직한 파기 보고."""
    then_n = plan_n = follow_ok = tear_ok = bad = 0
    pending = {}                     # char -> 남은 then 수 목록
    for line in raw.splitlines():
        r = json.loads(line)
        if r["kind"] == "level":
            pending = {}             # 강하 = 재스폰 = plan 리셋
            continue
        if r["kind"] != "tick":
            continue
        for c, dec in sorted((r.get("decisions") or {}).items()):
            if dec.get("skipped"):
                continue
            if dec.get("src") == "plan":
                plan_n += 1
            exp = pending.pop(c, None)
            if exp:
                o = dec.get("obs") or {}
                last = o.get("last") or {}
                if (dec.get("src") == "plan"
                        and dec.get("type") == exp[0].get("type")
                        and dec.get("target") == exp[0].get("target")):
                    follow_ok += 1
                    rest = exp[1:]           # 이 plan 결정 뒤에도 남은 수가 있으면 계속 추적
                    if rest:
                        pending[c] = rest
                elif (last.get("type") in TEAR_REASONS
                        or last.get("result") in TEAR_RESULTS):
                    tear_ok += 1             # 파기 = obs.last 가 사유를 보고(정직)
                else:
                    bad += 1
            if dec.get("then"):
                then_n += 1
                pending[c] = list(dec["then"])
    return then_n, plan_n, follow_ok, tear_ok, bad


def main():
    print("== 작정 큐(D16) 검증 ==")
    unit_then()
    units()

    brains._call_claude = call_counter(
        [], then_json=', "then": [{"type": "search"}, {"type": "explore"}]')
    raw1 = run_stub_game()
    raw2 = run_stub_game()
    then_n, plan_n, follow_ok, tear_ok, bad = audit_plan(raw1)
    check("⑨ 표본 충분(then %d·plan 집행 %d)" % (then_n, plan_n),
          then_n >= 5 and plan_n >= 5)
    check("⑨ 작정 연속성 전수 감사(이행 %d·정직 파기 %d·위반 %d)"
          % (follow_ok, tear_ok, bad), bad == 0 and follow_ok >= 3)
    import ab_menu
    m = ab_menu.parse_stream(os.path.join(os.environ["DUNGEON_STATE_DIR"], "stream.jsonl"))
    check("⑨ 계측 분리(llm_calls %d + plan_steps %d == decisions %d)"
          % (m["llm_calls"], m["plan_steps"], m["decisions"]),
          m["llm_calls"] + m["plan_steps"] == m["decisions"] and m["plan_steps"] == plan_n)
    check("⑨ 결정론(2회 라인 동일, started 제외)", normalized(raw1) == normalized(raw2))

    print("=" * 44)
    if C.failed:
        print("RESULT: %d FAIL" % C.failed)
        raise SystemExit(1)
    print("RESULT: ALL PASS — 작정 큐(D16) 계약 건전")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""판단 되먹임(intent, D15①) 헤들리스 검증 — 11번째 게이트.
게이트:
  ① 첫 결정: 프롬프트 obs 에 intent 없음(백지 출발) + 결정 후 bot['intent'] 저장(빈 필드 제외)
  ② 두 번째 결정: 프롬프트 obs.intent == 직전 결정 파생값(LLM 이 실제로 보는 것으로 검증)
  ③ order 자동보행 스킵 봇: think_all 제외 + intent 보존(걷는 내내 마지막 판단 유지)
  ④ 폴백 결정도 기억된다(src=fallback — [폴백] reason 이 그대로 남아 정직)
  ⑤ 스트림 계약 불변: bot_snapshot 에 intent 없음(화이트리스트 밖)
  ⑥ 러너 통합(STREAM_OBS=1 스텁 판): decisions[].obs.intent == 같은 층 그 캐릭터의 직전
     decision 파생값(스트림에서 재구성 가능 = 새 원천 없음 — D38 궤적 판은 직전 **실** 결정+그 turn)
     / 층 첫 결정 intent 없음(강하 리셋)
     / 2회 실행 결정론(started 제외 라인 동일)
  ⑦ 강하 재스폰 봇에 intent 없음(층 전이 리셋 경로)
(기존 verify 10종은 별도 실행.)
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
                  DUNGEON_STREAM_OBS="1",                # ⑥ 파생 가능성 검증에 필요
                  DUNGEON_STATE_DIR=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                 "state_intentverify"))
os.environ["DUNGEON_BESTIARY_FILE"] = ""   # 도감 영속 차단(게이트 격리 원칙)

import brains
import dungeon_gm as G


class C:
    failed = 0


def check(name, cond):
    print("  [%s] %s" % ("OK" if cond else "FAIL", name))
    if not cond:
        C.failed += 1


INTENT_KEYS = ("target", "say", "reason", "src")


def derive(dec):
    """brains.think_all 의 저장 규칙 미러 — 검증은 독립 재계산으로."""
    it = {"type": dec.get("type", "")}
    for k in INTENT_KEYS:
        if dec.get(k):
            it[k] = dec[k]
    return it


def wire_tap(sink):
    """brains._wire 래핑 — 프롬프트로 나가기 직전의 obs(dict 원형)를 캡처.
    (구판은 프롬프트의 ```json 블록을 파싱했다 — D17-3 문장형 직렬화로 JSON 블록이 사라져
    캡처 지점을 wire 입구로 옮김. 검사 본질 'LLM 이 실제로 보는 것' 불변.)"""
    orig = brains._wire

    def tap(obs, names=None):
        sink.append(obs)
        return orig(obs, names)
    return tap


# ───────────────────── ①~④ 유닛(스텁 _call_claude, 실 claude_brain 경유) ─────────────────────
def stub_factory(sink):
    def stub(prompt, model="haiku"):
        sink.append(prompt)
        ns = re.findall(r"^(\d+)\. ", prompt, re.M)
        return '{"reason": "검증 판단", "choice": %s, "say": "간다"}' % (ns[-1] if ns else 1)
    return stub


def units():
    prompts, seen = [], []
    brains._call_claude = stub_factory(prompts)
    orig_wire = brains._wire
    brains._wire = wire_tap(seen)
    d = G.Dungeon(seed=7)
    bots = []
    for c in "12":
        bots.append(G.spawn(d, c, bots))

    dec1 = brains.think_all(d, bots, {})
    first = list(seen)
    check("① 첫 결정 obs 에 intent 없음 (%d봇)" % len(first),
          len(first) == 2 and all("intent" not in o for o in first))
    check("① 결정 후 bot['intent'] == 파생값",
          all(b["intent"] == derive(dec1[b["char"]]) for b in bots))

    prompts.clear(); seen.clear()
    dec2 = brains.think_all(d, bots, {})
    ok2 = 0
    for b in bots:
        o = next((v for v in seen if v.get("pos") == [b["x"], b["y"]]), None)
        if o is not None and o.get("intent") == derive(dec1[b["char"]]):
            ok2 += 1
    check("② 두 번째 결정 obs.intent == 직전 결정 (%d/2)" % ok2, ok2 == 2)
    brains._wire = orig_wire

    save = bots[0].get("order")
    bots[0]["order"] = {"kind": "_verify"}          # think_all 은 truthiness 만 본다
    keep = dict(bots[0]["intent"])
    dec3 = brains.think_all(d, bots, {})
    check("③ order 봇 스킵 + intent 보존",
          "1" not in dec3 and bots[0]["intent"] == keep and "2" in dec3)
    bots[0]["order"] = save

    brains._call_claude = lambda prompt, model="haiku": ""   # 빈 응답 → 폴백 경로
    dec4 = brains.think_all(d, bots, {})
    check("④ 폴백 결정도 intent 에 남고 src=fallback",
          all(dec4[c].get("src") == "fallback" and
              b["intent"].get("src") == "fallback"
              for c, b in ((bb["char"], bb) for bb in bots) if c in dec4))

    check("⑤ bot_snapshot 에 intent 없음(계약 불변)",
          all("intent" not in G.bot_snapshot(b) for b in bots))

    d2 = G.Dungeon(seed=7, depth=2)
    n = G.spawn(d2, "1", [])
    check("⑦ 강하 재스폰 봇에 intent 없음(층 리셋)", "intent" not in n)


# ───────────────────── ⑥ 러너 통합(verify_menu ⑦ 하네스 계승) ─────────────────────
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


def audit_stream(raw):
    """층 세그먼트별 직전 결정 지도로 obs.intent 전수 감사 — 스트림만으로 재구성.
    D38(09-06, run_meta.trail=true 판): 작정 수(src=plan)는 intent 를 덮지 않는다 — 직전 '실' 결정이
    기준이고, 그 결정의 tick turn 이 intent.turn 으로 붙는다(궤적 판의 저장 규칙 미러)."""
    prev = {}                      # char -> (직전 decision, 그 turn) (층 내)
    trail = False
    n_dec = n_with = bad = first_bad = 0
    for line in raw.splitlines():
        r = json.loads(line)
        if r["kind"] == "run_meta":
            trail = bool(r.get("trail"))
            continue
        if r["kind"] == "level":
            prev = {}              # 강하 = 재스폰 = intent 리셋
            continue
        if r["kind"] != "tick":
            continue
        for c, dec in sorted((r.get("decisions") or {}).items()):
            if dec.get("src") == "plan" and "obs" not in dec:
                continue           # 작정 집행 수 = view() 없음(obs 없음) — 되먹임 비교 대상 아님(D16)
            o = dec.get("obs") or {}
            n_dec += 1
            if c in prev:
                n_with += 1
                pd, pt = prev[c]
                want = derive(pd)
                if trail:
                    want["turn"] = pt
                if o.get("intent") != want:
                    bad += 1
            else:
                if "intent" in o:
                    first_bad += 1
            if not (trail and dec.get("src") == "plan"):   # 궤적 판: 작정 수는 intent 를 안 덮는다
                prev[c] = (dec, r["turn"])
    return n_dec, n_with, bad, first_bad


def main():
    print("== 판단 되먹임(intent) 검증 ==")
    units()

    brains._call_claude = stub_factory([])
    raw1 = run_stub_game()
    raw2 = run_stub_game()
    n_dec, n_with, bad, first_bad = audit_stream(raw1)
    check("⑥ 러너 판 결정 표본 충분(%d결정, 되먹임 %d)" % (n_dec, n_with),
          n_dec >= 10 and n_with >= 5)
    check("⑥ obs.intent == 직전 decision 파생(불일치 %d)" % bad, bad == 0)
    check("⑥ 층/판 첫 결정에 intent 없음(위반 %d)" % first_bad, first_bad == 0)
    check("⑥ 결정론(2회 라인 동일, started 제외)", normalized(raw1) == normalized(raw2))

    print("=" * 44)
    if C.failed:
        print("RESULT: %d FAIL" % C.failed)
        raise SystemExit(1)
    print("RESULT: ALL PASS — 판단 되먹임(자기 기억) 계약 건전")


if __name__ == "__main__":
    main()

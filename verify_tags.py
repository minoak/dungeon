#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_tags — 태그 발급기(tags.py) 게이트 (9번째)
  ① 결정론: 같은 스트림 2회 발급 = 동일 원장
  ② 스키마: D5 프리미티브 5필드(kind/대상/원천참조/월드시간/수명) + 등록부 정합
  ③ 원장 감사: 스트림을 독립 재집계한 수와 태그 수 일치(kill/fallen/treasure/발견/결말)
  ④ 원천 참조 유효성: 태그의 line/ev 가 실제 스트림 라인·이벤트를 가리킴
  ⑤ 라이브: 헤들리스 한 판(더미 두뇌) 스트림 → 발급 → 불변식(outcome 존재·감사 일치·결정론)
고정 픽스처 = ab_runs 12판(+d1smoke 유효 prefix). 픽스처 없으면 ⑤만 수행.
"""
import os
import io
import glob
import json
import shutil
import contextlib

# ── 라이브 판 환경: import 전에 고정(verify_stream 패턴) ──
STATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state_tagverify")
os.environ.update(DUNGEON_GM="0", DUNGEON_TURNS="200", DUNGEON_W="40", DUNGEON_H="16",
                  DUNGEON_SEED="7", DUNGEON_MONSTERS="2", DUNGEON_TRAPS="3",
                  DUNGEON_LURKERS="1", DUNGEON_DEPTHS="2",
                  DUNGEON_STEP_DELAY="0", DUNGEON_STATE_DIR=STATE_DIR,
                  DUNGEON_PARTY_FILE="/nonexistent")   # 내장 2인 고정(회귀 그물)
os.environ.pop("DUNGEON_STREAM_OBS", None)

import tags as T
import brains
brains._call_claude = lambda prompt, model="haiku": ""   # LLM 무력화 → dummy 폴백(결정론)
os.environ["DUNGEON_BESTIARY_FILE"] = ""   # 도감 영속 차단(리뷰 픽스) — 셸/tmux env 잔재가 라이브 원장을 읽고 쓰는 오염 방지
import show_runner
show_runner.STEP_DELAY = 0
import time as _time
_time.sleep = lambda s: None                             # 러너 고정 sleep 제거(검증 속도)

PASS = FAIL = 0


def check(name, cond):
    global PASS, FAIL
    print(("  OK   " if cond else "  FAIL ") + name)
    PASS, FAIL = PASS + (1 if cond else 0), FAIL + (0 if cond else 1)


def audit(lines):
    """태그 규칙과 독립적인 재집계(이벤트 원장 직접 카운트)."""
    a = {"killed": 0, "down": 0, "treasure": 0, "found_trap": 0,
         "found_monster": 0, "found_treasure": 0, "crit": 0,
         "we_surprise": 0, "outcome": None, "descend": 0}
    for _, o in lines:
        k = o.get("kind")
        if k == "end":
            a["outcome"] = o.get("outcome")
        if k == "descend":
            a["descend"] += 1
        if k != "tick":
            continue
        for e in o.get("events") or []:
            t = e.get("type")
            if t == "attack" and e.get("result") == "attack" and e.get("hit"):
                a["killed"] += 1 if e.get("killed") else 0
                a["crit"] += 1 if e.get("crit") else 0
                a["we_surprise"] += 1 if e.get("surprise") else 0
            if e.get("down") or (e.get("trap") or {}).get("down"):
                a["down"] += 1
            if t == "walk" and (e.get("result") == "treasure" or e.get("treasure")):
                a["treasure"] += 1
            if t == "interact" and e.get("result") in ("treasure", "chest_loot"):
                a["treasure"] += 1
            for f in e.get("found") or []:
                key = "found_" + str(f.get("kind"))
                if key in a:
                    a[key] += 1
    return a


def count(tags_, kind):
    return sum(1 for t in tags_ if t["kind"] == kind)


def gate(lines):
    """(결정론, 스키마, 감사, 원천참조, 태그수) — 한 스트림에 대한 4중 게이트."""
    tg1, tg2 = T.issue(lines), T.issue(lines)
    ok_det = tg1 == tg2
    ok_schema = all(
        t["kind"] in T.KINDS and t["axis"] == T.KINDS[t["kind"]][0]
        and set(t) == {"kind", "axis", "subject", "turn", "depth", "line", "ev", "ttl", "detail"}
        for t in tg1)
    a = audit(lines)
    ok_audit = (count(tg1, "kill") == a["killed"]
                and count(tg1, "fallen") == a["down"]
                and count(tg1, "treasure") == a["treasure"]
                and count(tg1, "spotted_trap") == a["found_trap"]
                and count(tg1, "spotted_lurker") == a["found_monster"]
                and count(tg1, "spotted_treasure") == a["found_treasure"]
                and count(tg1, "critical_hit") == a["crit"]
                and count(tg1, "we_ambush") == a["we_surprise"]
                and count(tg1, "descended") == a["descend"]
                and count(tg1, "first_blood") == (1 if a["killed"] else 0)
                and count(tg1, "outcome") == (1 if a["outcome"] else 0))
    if a["outcome"]:
        oc = next(t for t in tg1 if t["kind"] == "outcome")
        ok_audit = ok_audit and oc["detail"]["outcome"] == a["outcome"]
    by_line = dict(lines)
    ok_src = True
    for t in tg1:
        o = by_line.get(t["line"])
        if o is None:
            ok_src = False
            break
        if t["ev"] is not None:
            evs = o.get("events") or []
            if not (0 <= t["ev"] < len(evs)):
                ok_src = False
                break
    return ok_det, ok_schema, ok_audit, ok_src, len(tg1)


def main():
    print("== 태그 발급기(D5 원장) 검증 ==")
    fixtures = sorted(glob.glob("ab_runs/*/stream.jsonl"))
    if os.path.exists("state_d1smoke/stream.jsonl"):
        fixtures.append("state_d1smoke/stream.jsonl")
    if fixtures:
        det = sch = aud = src = True
        total = 0
        for p in fixtures:
            d, s, a, r, n = gate(T.read_stream(p))
            det, sch, aud, src, total = det and d, sch and s, aud and a, src and r, total + n
        check("① 결정론(2회 동일) — 픽스처 %d판" % len(fixtures), det)
        check("② 스키마(프리미티브 5필드+등록부) — %d태그" % total, sch)
        check("③ 원장 감사(독립 재집계 일치)", aud)
        check("④ 원천 참조 유효성(line/ev)", src)
    else:
        print("  (픽스처 없음 — ①~④ 건너뜀)")

    # ⑤ 라이브 한 판
    try:
        with contextlib.redirect_stdout(io.StringIO()), \
             contextlib.redirect_stderr(io.StringIO()):
            show_runner.main()
        lines = T.read_stream(os.path.join(STATE_DIR, "stream.jsonl"))
        d, s, a_ok, r, n = gate(lines)
        tg = T.issue(lines)
        check("⑤ 라이브 발급(태그 %d개·결말 태그 존재)" % n, count(tg, "outcome") == 1)
        check("⑤ 라이브 4중 게이트(결정론·스키마·감사·참조)", d and s and a_ok and r)
    finally:
        shutil.rmtree(STATE_DIR, ignore_errors=True)

    print()
    print("=" * 44)
    print("RESULT: " + ("ALL PASS — 태그 원장(D5) 건전" if FAIL == 0 else "%d FAIL" % FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())

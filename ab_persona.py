#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""검증② 기준선: 페르소나 분화 — 같은 시드·시트 교차(몸 고정, 마음 회전)·실Haiku·헤들리스.

D13 검증②: "같은 상황, 다른 시트 → 관찰 가능하게 다른 선택"(핵심 가설)의 첫 계측.
시점 = 태그 주석층(D15②) 이전 — 주석층이 계측 축을 늘리기 전의 깨끗한 기준선(전후 비교용).

설계:
  base  = party.json 원본 (전사몸=두란, 도적몸=카야, 바드몸=피른)
  cross = party_crossed.json — 몸(job/스탯)은 자리에 두고 마음(persona/name/speech/goal/
          relationships/sex)만 회전: 전사몸←카야, 도적몸←피른, 바드몸←두란.
  같은 시드에서 두 암의 차이는 전부 프롬프트 전용 필드(마음)의 몫 — 엔진 판정 무관여.
  해석 피벗 둘: 같은 몸이 암에 따라 다르게 움직이면 = 마음이 운전 / 같으면 = 몸이 운전.
  주의(정직 보고): 원본 persona 문장엔 몸 능력 서술이 섞여 있음("함정·기습에 능하다") —
  교차 암에서 능력 주장과 실제 스탯의 어긋남은 편집하지 않고 그대로 둠(교차의 정의 유지).
  이 어긋남이 낳는 행동(예: 수색반경 1로 도적처럼 수색)도 페르소나 구동의 증거로 계측된다.

격리: ab_menu와 동일 — 판별 STATE_DIR / 도감 영속 차단(DUNGEON_BESTIARY_FILE="") / GM=0.
리모컨(DUNGEON_MENU=1) 고정 = 채택된 기본값. stream.jsonl 이 원본 데이터(지표는 재산출 가능).

사용: cd ~/dungeon && python3 ab_persona.py [--seeds 1,2,3,4,5,6] [--jobs 2] [--turns 150]
     [--depths 1] [--arms base,cross]   # 안 돌린 암은 ab_runs 기존 판 재파싱(ab_menu 동일)
"""
import os
import sys
import json
import argparse
import subprocess
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
AB_ROOT = os.path.join(HERE, "ab_runs")
PARTY = {"base": os.path.join(HERE, "party.json"),
         "cross": os.path.join(HERE, "party_crossed.json")}
MIND = {"base": {"1": "두란", "2": "카야", "3": "피른"},      # 몸 슬롯 → 마음(이름)
        "cross": {"1": "카야", "2": "피른", "3": "두란"}}
BODY = {"1": "전사", "2": "도적", "3": "바드"}
ACT_TYPES = ("attack", "search", "explore", "goto", "interact")


def run_one(seed, arm, turns, depths):
    tag = "persona_%s_s%d" % (arm, seed)
    outdir = os.path.join(AB_ROOT, tag)
    os.makedirs(outdir, exist_ok=True)
    env = dict(os.environ)
    env.update({"DUNGEON_SEED": str(seed), "DUNGEON_MENU": "1",
                "DUNGEON_PARTY_FILE": PARTY[arm],
                "DUNGEON_GM": "0", "DUNGEON_STEP_DELAY": "0",
                "DUNGEON_TURNS": str(turns), "DUNGEON_DEPTHS": str(depths),
                "DUNGEON_STATE_DIR": outdir, "PYTHONUTF8": "1",
                "DUNGEON_BESTIARY_FILE": ""})   # 도감 영속 차단 — 라이브 원장 보호 + 암 비교성
    try:
        with open(os.path.join(outdir, "runner.out"), "w", encoding="utf-8") as lg:
            subprocess.run([sys.executable, os.path.join(HERE, "show_runner.py")],
                           stdout=lg, stderr=subprocess.STDOUT, env=env, timeout=5400)
    except subprocess.TimeoutExpired:
        return tag, {"error": "hard_timeout"}
    # 시트 폴백 = 실험 무효(2인 HEROES 로 조용히 굴러감) — runner.out 에서 즉시 적발
    try:
        head = open(os.path.join(outdir, "runner.out"), encoding="utf-8").read(2000)
        if "폴백" in head:
            return tag, {"error": "party_fallback: " + head.splitlines()[0][:120]}
    except OSError:
        pass
    try:                                 # 한 판이 깨져도 나머지 집계는 산다
        m = parse_stream(os.path.join(outdir, "stream.jsonl"))
    except Exception as e:
        print("  FAIL %-18s %r" % (tag, e), flush=True)
        return tag, {"error": repr(e)}
    print("  done %-18s outcome=%-8s tick=%3d 보물=%d 폴백=%.0f%%"
          % (tag, m["outcome"], m["end_turn"], m["treasure"], 100 * m["fallback_rate"]),
          flush=True)
    return tag, m


def parse_stream(path):
    recs = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    end = next((r for r in recs if r["kind"] == "end"), None)
    if end is None:
        raise ValueError("end 레코드 없음(판이 완주 못함)")
    ticks = [r for r in recs if r["kind"] == "tick"]
    dec_n = fb = says = delivered = plan_n = 0
    pairs = switches = search_rep = 0
    last = {}
    chars = {}                           # 몸 슬롯별 행동 프로파일(검증②의 계측 대상)

    def prof(c):
        if c not in chars:
            chars[c] = {k: 0 for k in ACT_TYPES}
            chars[c].update({"decisions": 0, "fallback": 0, "says": 0, "other": 0})
        return chars[c]

    for t in ticks:
        for c, d in sorted((t.get("decisions") or {}).items()):
            if d.get("skipped"):
                continue
            p = prof(c)
            dec_n += 1
            p["decisions"] += 1
            if d.get("src") == "plan":       # 작정 집행(D16) — 결정점이되 LLM 콜 아님
                plan_n += 1
            if d.get("src") == "fallback":
                fb += 1
                p["fallback"] += 1
            if d.get("say"):
                says += 1
                p["says"] += 1
            ty = d.get("type")
            p[ty if ty in ACT_TYPES else "other"] += 1
            key = (ty, d.get("target"))
            if c in last:
                pairs += 1
                if key != last[c]:
                    switches += 1
                if key[0] == "search" and last[c][0] == "search":
                    search_rep += 1
            last[c] = key
        for msgs in (t.get("inbox") or {}).values():
            delivered += len(msgs)
    return {"outcome": end["outcome"], "end_turn": end["turn"],
            "survivors": len(end["survivors"]), "deaths": len(end["fallen"]),
            "treasure": sum(b["bag"] for b in end["bots"]),
            "decisions": dec_n, "fallback": fb,
            "llm_calls": dec_n - plan_n, "plan_steps": plan_n,   # 작정(D16) 분리 — 구판은 plan 0
            "fallback_rate": (fb / (dec_n - plan_n)) if dec_n - plan_n else 0.0,
            "says": says, "delivered": delivered,
            "switch_pairs": pairs, "switches": switches,
            "churn": (switches / pairs) if pairs else 0.0,
            "search_repeat": search_rep, "chars": chars}


def agg(rows, key):
    vals = [r[key] for r in rows if "error" not in r]
    return sum(vals) / len(vals) if vals else float("nan")


def agg_char(rows, c, key):
    vals = [r["chars"][c][key] for r in rows
            if "error" not in r and c in r.get("chars", {})]
    return sum(vals) / len(vals) if vals else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="1,2,3,4,5,6")
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--turns", type=int, default=150)
    ap.add_argument("--depths", type=int, default=1)
    ap.add_argument("--arms", default="base,cross")
    a = ap.parse_args()
    seeds = [int(s) for s in a.seeds.split(",") if s.strip()]
    arms = [x.strip() for x in a.arms.split(",") if x.strip()]
    for arm in arms:
        if arm not in PARTY:
            sys.exit("모르는 암: %r (base/cross)" % arm)
        if not os.path.exists(PARTY[arm]):
            sys.exit("시트 파일 없음: %s" % PARTY[arm])
    jobs = [(s, arm) for s in seeds for arm in arms]
    print("검증② 기준선 시작: 시드 %s × 암%s (turns=%d depths=%d jobs=%d)"
          % (seeds, arms, a.turns, a.depths, a.jobs), flush=True)
    results = {}
    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        futs = [ex.submit(run_one, s, arm, a.turns, a.depths) for s, arm in jobs]
        for f in futs:
            tag, met = f.result()
            results[tag] = met
    for s in seeds:                      # 이번에 안 돌린 암 = 디스크의 기존 판 재파싱
        for arm in ("base", "cross"):
            tag = "persona_%s_s%d" % (arm, s)
            if tag not in results:
                try:
                    results[tag] = parse_stream(os.path.join(AB_ROOT, tag, "stream.jsonl"))
                except Exception as e:
                    results[tag] = {"error": repr(e)}

    out = {"seeds": seeds, "turns": a.turns, "depths": a.depths,
           "mind": MIND, "body": BODY, "runs": results}
    with open(os.path.join(AB_ROOT, "persona_results.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    rows = {arm: [results["persona_%s_s%d" % (arm, s)] for s in seeds]
            for arm in ("base", "cross")}
    esc = lambda rs: sum(1 for r in rs if r.get("outcome") == "escaped")
    print("\n===== 전역 집계 (시드 %d개 평균) =====" % len(seeds))
    print("%-22s %10s %10s" % ("지표", "base", "cross"))
    print("%-22s %10s %10s" % ("탈출 판 수", esc(rows["base"]), esc(rows["cross"])))
    for k, label in [("end_turn", "종료 틱"), ("survivors", "생존자"), ("deaths", "사망"),
                     ("treasure", "보물"), ("decisions", "재결정 수(작정 포함)"),
                     ("llm_calls", "LLM 콜 수"), ("plan_steps", "작정 집행 수"),
                     ("fallback_rate", "폴백률"), ("churn", "타겟 스위치율"),
                     ("search_repeat", "수색 연속반복"), ("says", "say 수"),
                     ("delivered", "배달된 말")]:
        print("%-22s %10.2f %10.2f" % (label, agg(rows["base"], k), agg(rows["cross"], k)))

    print("\n===== 몸 피벗 — 같은 몸, 다른 마음 (암 간 차이 = 마음의 몫) =====")
    print("%-14s %-12s" % ("몸", "지표") + "".join("%10s" % k for k in ACT_TYPES)
          + "%10s" % "says")
    for c in ("1", "2", "3"):
        for arm in ("base", "cross"):
            label = "%s(%s)" % (BODY[c], arm)
            mind = MIND[arm][c]
            print("%-14s %-12s" % (label, "마음=" + mind)
                  + "".join("%10.2f" % agg_char(rows[arm], c, k) for k in ACT_TYPES)
                  + "%10.2f" % agg_char(rows[arm], c, "says"))

    print("\n===== 마음 피벗 — 같은 마음, 다른 몸 (암 간 유사 = 마음이 이월) =====")
    for name in ("두란", "카야", "피른"):
        for arm in ("base", "cross"):
            c = next(k for k, v in MIND[arm].items() if v == name)
            print("%-14s %-12s" % (name + "(" + arm + ")", "몸=" + BODY[c])
                  + "".join("%10.2f" % agg_char(rows[arm], c, k) for k in ACT_TYPES)
                  + "%10.2f" % agg_char(rows[arm], c, "says"))

    errs = [t for t, m in results.items() if "error" in m]
    if errs:
        print("\n오류 판:", errs)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A/B 실측: 자유서술(DUNGEON_MENU=0) vs 리모컨(DUNGEON_MENU=1) — 같은 시드·실Haiku·헤들리스.

사전 등록 판정 규칙(2026-07-03, 리모컨 토론 합의):
  리모컨이 '지지만 않으면' 채택(무승부=채택 — BYO 계약 단순화·환각 차단·작은 두뇌 친화 실익).
  자유서술이 명백히 이길 때만(예: churn 급증으로 목표 지속성 붕괴, 생존/완주 급락) 재고.
알려진 교란(보고 시 명시 — 이 실험은 '제품 단위' 비교라 메뉴 메커니즘과 프롬프트 톤을 분리 못함):
  메뉴판에만 있는 지침 ① '목표를 쉽게 버리지 마라'(churn에 영향) ② "'공격'이 보인다고 반드시
  쳐야 하는 건 아니다"(전투 빈도·사망) ③ 보물 톤 완화 "챙길 만하다"(자유서술판은 "챙겨라") 및
  기습·explore 독려 문구 부재/약화(전투·탐색 지표).

지표는 각 판의 stream.jsonl 에서 기계 산출(STREAM_FORMAT.md 계약):
  outcome / 종료틱 / 생존·사망 / 보물 / 폴백률 / say·배달 / 타겟 스위치 churn / 수색 반복.

사용: cd ~/dungeon && python3 ab_menu.py [--seeds 1,2,3,4,5,6] [--jobs 2] [--turns 150] [--depths 1]
"""
import os
import sys
import json
import argparse
import subprocess
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
AB_ROOT = os.path.join(HERE, "ab_runs")


def run_one(seed, menu, turns, depths):
    tag = "%s_s%d" % ("menu" if menu else "free", seed)
    outdir = os.path.join(AB_ROOT, tag)
    os.makedirs(outdir, exist_ok=True)
    env = dict(os.environ)
    env.update({"DUNGEON_SEED": str(seed), "DUNGEON_MENU": "1" if menu else "0",
                "DUNGEON_GM": "0", "DUNGEON_STEP_DELAY": "0",
                "DUNGEON_TURNS": str(turns), "DUNGEON_DEPTHS": str(depths),
                "DUNGEON_STATE_DIR": outdir, "PYTHONUTF8": "1",
                "DUNGEON_BESTIARY_FILE": ""})   # 도감 영속 강제 차단 — 셸에 남은 env가 라이브
                                                # 원장을 오염시키거나(격리) 판 사이 지식이 누적돼
                                                # 암 비교성이 깨지는(A/B 전제) 두 사고를 함께 막는다
    try:
        with open(os.path.join(outdir, "runner.out"), "w", encoding="utf-8") as lg:
            subprocess.run([sys.executable, os.path.join(HERE, "show_runner.py")],
                           stdout=lg, stderr=subprocess.STDOUT, env=env, timeout=5400)
    except subprocess.TimeoutExpired:
        return tag, {"error": "hard_timeout"}
    try:                                 # 한 판이 깨져도 나머지 집계는 산다(하니스 쪽 폴백 안전망)
        m = parse_stream(os.path.join(outdir, "stream.jsonl"))
    except Exception as e:
        print("  FAIL %-10s %r" % (tag, e), flush=True)
        return tag, {"error": repr(e)}
    print("  done %-10s outcome=%-8s tick=%3d 보물=%d 폴백=%.0f%%"
          % (tag, m["outcome"], m["end_turn"], m["treasure"], 100 * m["fallback_rate"]),
          flush=True)
    return tag, m


def parse_stream(path):
    recs = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    end = next((r for r in recs if r["kind"] == "end"), None)
    if end is None:
        raise ValueError("end 레코드 없음(판이 완주 못함)")
    ticks = [r for r in recs if r["kind"] == "tick"]
    dec_n = fb = says = delivered = choice_n = explore_n = 0
    pairs = switches = search_rep = plan_n = 0
    wait_allies = 0
    last = {}            # char -> (type,target) 직전 결정 (skipped 제외)
    for t in ticks:
        for c, d in sorted((t.get("decisions") or {}).items()):
            if d.get("skipped"):
                continue
            dec_n += 1
            if d.get("src") == "plan":       # 작정 집행(D16) — 결정점이되 LLM 콜 아님.
                plan_n += 1                  #   churn 사슬엔 포함(기준선과 같은 의미 유지)
            if d.get("src") == "fallback":
                fb += 1
            if d.get("say"):
                says += 1
            if "choice" in d:
                choice_n += 1
            if d.get("type") == "explore":
                explore_n += 1
            key = (d.get("type"), d.get("target"))
            if c in last:
                pairs += 1
                if key != last[c]:
                    switches += 1
                if key[0] == "search" and last[c][0] == "search":
                    search_rep += 1
            last[c] = key
        for msgs in (t.get("inbox") or {}).values():
            delivered += len(msgs)
        for e in t.get("events") or []:
            if e.get("type") == "interact" and e.get("result") == "wait_allies":
                wait_allies += 1
    return {"outcome": end["outcome"], "end_turn": end["turn"],
            "survivors": len(end["survivors"]), "deaths": len(end["fallen"]),
            "treasure": sum(b["bag"] for b in end["bots"]),
            "decisions": dec_n, "fallback": fb,
            "llm_calls": dec_n - plan_n, "plan_steps": plan_n,   # 작정(D16) 분리 계측 —
            #   구판 스트림은 plan 없음 → llm_calls == decisions (기준선과 그대로 비교 가능)
            "fallback_rate": (fb / (dec_n - plan_n)) if dec_n - plan_n else 0.0,
            "choice_used": choice_n, "explore_n": explore_n,
            "says": says, "delivered": delivered,
            "switch_pairs": pairs, "switches": switches,
            "churn": (switches / pairs) if pairs else 0.0,
            "search_repeat": search_rep, "wait_allies": wait_allies}


def agg(rows, key):
    vals = [r[key] for r in rows if "error" not in r]
    return sum(vals) / len(vals) if vals else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="1,2,3,4,5,6")
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--turns", type=int, default=150)
    ap.add_argument("--depths", type=int, default=1)
    ap.add_argument("--arms", default="0,1",
                    help="다시 돌릴 암(0=자유서술,1=리모컨). 안 돌린 암은 ab_runs 기존 판을 재파싱(같은 시드 재사용)")
    a = ap.parse_args()
    seeds = [int(s) for s in a.seeds.split(",") if s.strip()]
    arms = [int(x) for x in a.arms.split(",") if x.strip()]
    jobs = [(s, menu) for s in seeds for menu in arms]
    print("A/B 시작: 시드 %s × 암%s (turns=%d depths=%d jobs=%d)"
          % (seeds, arms, a.turns, a.depths, a.jobs), flush=True)
    results = {}
    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        futs = [ex.submit(run_one, s, m, a.turns, a.depths) for s, m in jobs]
        for f in futs:
            tag, met = f.result()
            results[tag] = met
    for s in seeds:                          # 이번에 안 돌린 암 = 디스크의 기존 판 재파싱
        for arm, name in ((0, "free"), (1, "menu")):
            tag = "%s_s%d" % (name, s)
            if tag not in results:
                try:
                    results[tag] = parse_stream(os.path.join(AB_ROOT, tag, "stream.jsonl"))
                except Exception as e:
                    results[tag] = {"error": repr(e)}

    out = {"seeds": seeds, "turns": a.turns, "depths": a.depths, "runs": results}
    with open(os.path.join(AB_ROOT, "ab_results.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    free = [results["free_s%d" % s] for s in seeds]
    menu = [results["menu_s%d" % s] for s in seeds]
    esc = lambda rows: sum(1 for r in rows if r.get("outcome") == "escaped")
    print("\n===== A/B 집계 (시드 %d개 평균) =====" % len(seeds))
    print("%-22s %10s %10s" % ("지표", "자유서술", "리모컨"))
    print("%-22s %10s %10s" % ("탈출 판 수", esc(free), esc(menu)))
    for k, label in [("end_turn", "종료 틱"), ("survivors", "생존자"), ("deaths", "사망"),
                     ("treasure", "보물"), ("decisions", "재결정 수(작정 포함)"),
                     ("llm_calls", "LLM 콜 수"), ("plan_steps", "작정 집행 수"),
                     ("fallback_rate", "폴백률"), ("churn", "타겟 스위치율"),
                     ("search_repeat", "수색 연속반복"), ("says", "say 수"),
                     ("delivered", "배달된 말"), ("wait_allies", "계단 대기")]:
        print("%-22s %10.2f %10.2f" % (label, agg(free, k), agg(menu, k)))
    errs = [t for t, m in results.items() if "error" in m]
    if errs:
        print("오류 판:", errs)


if __name__ == "__main__":
    main()

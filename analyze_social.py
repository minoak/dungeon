#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""사회층 부검(0콜, D33 2026-09-05) — 한 판의 '진전 안 됨'을 숫자로. analyze_run.py 의 짝.
  python analyze_social.py runs/stream-XXXX.jsonl   (기본: state/stream.jsonl)

왜: 09-05 [L] 판 부검에서 "동행 대상을 놓치고 → 다시 모이고 → 이야기하다 → 진전 없음" 고리가
보였다(말 걸림 정지 96/218틱·전원 제자리 55틱·lost 9·follow 90틱·커버리지 0.42칸/틱). 스위치를
바꾼 뒤 같은 자로 다시 재야 비교가 된다 — 이 파일이 그 자다. LLM 0콜, 스트림만 읽는다.
지표: 말 걸림 정지 / 전원 제자리 틱·최장 정체 / follow 진행 틱·회전 / lost / 5틱 내 되밟기 /
저체력(hp<=4) 결정 / 물약 획득·음용 / 커버리지 / 사망 직전 5틱.
"""
import io
import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))


def load(path):
    recs = []
    with io.open(path, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                recs.append(json.loads(ln))
            except ValueError:
                pass
    return recs


def main(path):
    recs = load(path)
    meta = recs[0] if recs and recs[0].get("kind") == "run_meta" else {}
    names = {p["char"]: (p.get("name") or p.get("job")) for p in meta.get("party", [])}
    ticks = [r for r in recs if r.get("kind") == "tick"]
    end = next((r for r in recs if r.get("kind") == "end"), {})
    n = len(ticks)
    print("=" * 72)
    print("%s  ·  %d틱 · seed %s · sight %s · ally_sight %s · social %s · %s" % (
        os.path.basename(path), n, meta.get("seed"), meta.get("sight"), meta.get("ally_sight"),
        meta.get("social"), end.get("outcome") or "(진행 중)"))
    print("  파티: " + " · ".join("%s(%s)" % (v, k) for k, v in sorted(names.items())))

    # 말 걸림 정지 / 전원 제자리 / 정체 구간
    hails = sum(len(r.get("hails") or {}) for r in ticks)
    prev = None
    stall_turns = []
    visited = set()
    for r in ticks:
        pos = {b["char"]: (b["x"], b["y"]) for b in r.get("bots", []) if b["alive"] and not b["won"]}
        visited.update(pos.values())
        moved = sum(1 for c, p in pos.items() if prev and prev.get(c) and prev[c] != p)
        if prev is not None and moved == 0 and len(pos) >= 2:
            stall_turns.append(r["turn"])
        prev = pos
    runs, cur = [], []
    for t in stall_turns:
        if cur and t == cur[-1] + 1:
            cur.append(t)
        else:
            if cur:
                runs.append(cur)
            cur = [t]
    if cur:
        runs.append(cur)
    longest = max((len(x) for x in runs), default=0)

    # follow 진행·회전 / lost / 되밟기
    follow_ticks = cyc = 0
    hist = defaultdict(list)
    back, moves = Counter(), Counter()
    for r in ticks:
        fol = {b["char"]: str(b.get("order"))[7:] for b in r.get("bots", [])
               if str(b.get("order") or "").startswith("follow:b")}
        if fol:
            follow_ticks += 1
        if any(fol.get(t) == a or (fol.get(t) and fol.get(fol.get(t)) == a) for a, t in fol.items()):
            cyc += 1
        for b in r.get("bots", []):
            c, p = b["char"], (b["x"], b["y"])
            if hist[c] and hist[c][-1] != p:
                moves[c] += 1
                if p in hist[c][-6:-1]:
                    back[c] += 1
            hist[c].append(p)
    lost = [(r["turn"], names.get(e.get("char"), e.get("char"))) for r in ticks
            for e in r.get("events", []) if e.get("result") == "lost"]
    dec_types = Counter(d.get("type") for r in ticks for d in (r.get("decisions") or {}).values() if not d.get("skipped"))
    says = sum(1 for r in ticks for d in (r.get("decisions") or {}).values() if d.get("say") and not d.get("skipped"))
    n_dec = sum(dec_types.values())

    print("  말 걸림 정지 %d회(%.2f/틱) · 전원 제자리 %d틱(%.0f%%) · 최장 정체 %d틱 · 결정 %d(say %.0f%%)"
          % (hails, hails / max(n, 1), len(stall_turns), 100.0 * len(stall_turns) / max(n, 1), longest,
             n_dec, 100.0 * says / max(n_dec, 1)))
    print("  follow 진행 %d틱(%.0f%%) · 회전 follow %d틱 · 결정 분포 %s"
          % (follow_ticks, 100.0 * follow_ticks / max(n, 1), cyc, dict(dec_types.most_common(6))))
    print("  lost %d회 %s" % (len(lost), lost[:10]))
    print("  5틱 내 되밟기: " + " · ".join("%s %d/%d" % (names.get(c, c), back[c], moves[c]) for c in sorted(moves)))
    print("  커버리지 %d칸(%.2f칸/틱)" % (len(visited), len(visited) / max(n, 1)))

    # 저체력 결정 / 물약
    low = defaultdict(Counter)
    prev_hp = {}
    for r in ticks:
        for c, d in (r.get("decisions") or {}).items():
            h = prev_hp.get(c)
            if h is not None and h[0] <= 4 and not d.get("skipped"):
                low[c]["%s(물약%d)" % (d.get("type"), h[1])] += 1
        for b in r.get("bots", []):
            prev_hp[b["char"]] = (b["hp"], b.get("potions", 0))
    if low:
        print("  저체력(hp<=4) 결정: " + " · ".join("%s %s" % (names.get(c, c), dict(v)) for c, v in low.items()))
    gifts = [(r["turn"], names.get(e.get("char"), e.get("char")), e.get("item")) for r in ticks
             for e in r.get("events", []) if e.get("result") == "npc_gift"]
    drinks = [(r["turn"], names.get(e.get("char"), e.get("char"))) for r in ticks
              for e in r.get("events", []) if e.get("type") == "drink"]
    print("  상점 선물 %s · 물약 음용 %s" % (gifts, drinks))

    # 사망 직전
    for r in ticks:
        for e in r.get("events", []):
            if e.get("down"):
                t, c = r["turn"], (e.get("target") or e.get("char"))
                trail = []
                for rr in ticks:
                    if t - 5 <= rr["turn"] <= t:
                        h = next((b["hp"] for b in rr.get("bots", []) if b["char"] == c), None)
                        d = (rr.get("decisions") or {}).get(c)
                        trail.append("t%d hp%s %s" % (rr["turn"], h, (d or {}).get("type") or "-"))
                print("  사망 %s t%d: %s" % (names.get(c, c), t, " → ".join(trail)))
    return 0


if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "state", "stream.jsonl")
    raise SystemExit(main(p))

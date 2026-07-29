# -*- coding: utf-8 -*-
"""판 부검 도구 — 스트림(JSONL) 하나를 사람이 읽을 표로. LLM 0콜, 판을 안 돌린다.

왜: 부검 때마다 같은 숫자를 손으로 다시 셌다(follow 비중·커버리지·반복률). 그 숫자가
판정의 근거이자 다음 판의 대조군이라 매번 같은 자로 재야 한다.

쓰는 법:
    python3 analyze_run.py runs/xxx.jsonl [다른판.jsonl ...]
    python3 analyze_run.py state/stream.jsonl        # 돌고 있는 판도 읽힌다(유효 prefix)

읽는 법 — 이 도구가 답하는 질문:
  · **주관이 있나**: 캐릭터별 행동 분포. follow 가 결정의 몇 할인가.
    (2026-07-26 큰 판 기준선: 두란 follow 8/55 · 카야 17/57 · 피른 **34/51**)
  · **다시 고른 선택인가**: 직전 결정과 완전히 같은 비율. 높으면 결정 순간이 늘어도
    새 선택은 안 는다.
  · **얼마나 도나**: 커버리지(밟은 칸)/틱. 뭉치면 낮고 흩어지면 높다.
  · **솔로 판 전용**: 첫 조우 시점과, 조우 뒤 행동이 바뀌었나(만나서 뭉쳤나 갈라섰나).

⚠️ 스트림은 사실만 있다 — 해석은 사람이 한다. 이 도구는 세지 판정하지 않는다.
"""
import sys
import json
import collections


def load(path):
    recs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                recs.append(json.loads(line))
            except ValueError:
                break            # 유효 prefix — 돌고 있는 판의 잘린 마지막 줄
    return recs


def analyze(path):
    recs = load(path)
    meta = next((r for r in recs if r.get("kind") == "run_meta"), {})
    ticks = [r for r in recs if r.get("kind") == "tick"]
    end = next((r for r in recs if r.get("kind") == "end"), None)
    if not ticks:
        print("  (틱 없음 — 빈 판)")
        return

    # 이름은 run_meta.party 에 있다(틱 스냅샷의 bots[] 에는 없다 — 스트림 무수정 원칙의 흔적)
    names = {p.get("char"): p.get("name") for p in (meta.get("party") or [])
             if isinstance(p, dict) and p.get("name")}
    types, srcs = collections.defaultdict(collections.Counter), collections.Counter()
    prev, repeat, ndec = {}, collections.Counter(), collections.Counter()
    alive_ticks, says = collections.Counter(), collections.Counter()
    cells, first_meet, meet_turn = set(), {}, None
    per_bot_cells = collections.defaultdict(set)

    for r in ticks:
        t = r.get("turn")
        seen_together = collections.defaultdict(list)
        for b in r.get("bots") or []:
            c = b.get("char")
            names.setdefault(c, b.get("name") or "봇%s" % c)
            if b.get("alive") and not b.get("won"):
                alive_ticks[c] += 1
                if b.get("x") is not None:
                    cells.add((b["x"], b["y"]))
                    per_bot_cells[c].add((b["x"], b["y"]))
                    seen_together[c] = (b["x"], b["y"])
        # 첫 조우 = 두 사람이 서로 시야 반경(5) 안에 든 첫 틱 — 좌표 기반 근사(스트림엔 시야가 없다)
        chars = sorted(seen_together)
        for i, a in enumerate(chars):
            for bb in chars[i + 1:]:
                ax, ay = seen_together[a]
                bx, by = seen_together[bb]
                if max(abs(ax - bx), abs(ay - by)) <= 5:
                    key = (a, bb)
                    if key not in first_meet:
                        first_meet[key] = t
                        if meet_turn is None:
                            meet_turn = t
        for c, d in (r.get("decisions") or {}).items():
            ndec[c] += 1
            types[c][d.get("type")] += 1
            srcs[d.get("src")] += 1
            if (d.get("say") or "").strip():
                says[c] += 1
            key = (d.get("type"), d.get("target"))
            if prev.get(c) == key:
                repeat[c] += 1
            prev[c] = key

    n_t = len(ticks)
    tot_dec = sum(ndec.values())
    tot_alive = sum(alive_ticks.values())
    mode = []
    for k in ("solo", "ally_sight", "social", "motion", "scan", "menu"):
        if meta.get(k):
            mode.append(k)
    print("  판: %s틱 · 시드 %s · %sx%s · 두뇌 %s · 스위치[%s]"
          % (n_t, meta.get("seed"), meta.get("w"), meta.get("h"),
             meta.get("backend") or "claude_cli", " ".join(mode) or "-"))
    print("  결과: %s" % ((end or {}).get("outcome") or "(중단 — end 없음)"))
    print()
    print("  %-8s %7s %7s %8s %8s %8s   행동 분포"
          % ("인물", "생존틱", "결정", "반복", "say", "칸"))
    for c in sorted(ndec, key=lambda c: -ndec[c]):
        n = ndec[c]
        dist = " ".join("%s %d" % (k, v) for k, v in types[c].most_common())
        print("  %-8s %7d %7d %7.0f%% %7.0f%% %8d   %s"
              % ("%s(%s)" % (names.get(c, "?"), c), alive_ticks[c], n,
                 repeat[c] / n * 100, says[c] / n * 100, len(per_bot_cells[c]), dist))
    print()
    print("  합계: 결정 %d (%.2f/틱) · 말없이 걷는 틱 %.0f%% · 폴백 %.0f%%"
          % (tot_dec, tot_dec / n_t,
             (1 - tot_dec / tot_alive) * 100 if tot_alive else 0,
             srcs.get("fallback", 0) / tot_dec * 100 if tot_dec else 0))
    print("  커버리지: %d칸 (%.2f칸/틱)" % (len(cells), len(cells) / n_t))

    if meta.get("solo"):
        print()
        if first_meet:
            print("  조우(시야 반경 근사): " + " · ".join(
                "%s↔%s t%s" % (names.get(a, a), names.get(b, b), t)
                for (a, b), t in sorted(first_meet.items(), key=lambda kv: kv[1])))
            after = collections.Counter()
            for r in ticks:
                if r.get("turn", 0) < meet_turn:
                    continue
                for c, d in (r.get("decisions") or {}).items():
                    after[d.get("type")] += 1
            before = collections.Counter()
            for r in ticks:
                if r.get("turn", 0) >= meet_turn:
                    continue
                for c, d in (r.get("decisions") or {}).items():
                    before[d.get("type")] += 1
            nb, na = sum(before.values()), sum(after.values())
            print("  조우 전 follow 비중: %.0f%% (%d결정) → 조우 후: %.0f%% (%d결정)"
                  % (before.get("follow", 0) / nb * 100 if nb else 0, nb,
                     after.get("follow", 0) / na * 100 if na else 0, na))
        else:
            print("  조우 없음 — 셋이 판 내내 서로를 못 봤다")


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    for p in argv[1:]:
        print("=" * 78)
        print(p)
        print("=" * 78)
        try:
            analyze(p)
        except (OSError, ValueError) as e:
            print("  읽기 실패: %s" % e)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

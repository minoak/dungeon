#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
시나리오 러너 (디버깅 모드) — 손으로 그린 장면에서 바로 실험한다.
─────────────────────────────────────────────
왜: 풀판(수십 분~시간)은 결말 질문(탈출률·사망)용이다. "이 상황에서 에이전트가 뭘
하나" 같은 행동 질문은 장면 하나로 몇 분 안에 답이 나와야 한다 — 백로그 '시나리오
러너'의 v0(풀판 낚시 대체). verify 게이트들이 코드로 하던 장면 조립(arena/mkbot)을
JSON 저작으로 꺼낸 것: 새 장면 = 새 JSON 한 장, 코드 무수정.

사용:
  python3 scenario.py scenarios/궁지.json                 # 장면 실행(실Haiku, 스트림+콘솔)
  python3 scenario.py scenarios/궁지.json --brain dummy   # 규칙 두뇌(LLM 0콜 — 물리/배관 점검)
  python3 scenario.py scenarios/작정.json --probe 10      # 결정 프로브: 같은 장면 첫 결정 N콜 분포
  python3 scenario.py scenarios/작정.json --probe 10 --jobs 2

장면 JSON (기호는 dungeon_gm.Dungeon.from_ascii 참조):
  {"name": "궁지", "about": "설명", "seed": 7, "turns": 10,
   "map": ["#########", "#1g....>#", ...],
   "monsters": {"g": {"kind": "고블린", "state": "HUNTING", "target": "1"}},
   "traps": [{"kind": "spike", "hidden": true}],
   "bots": {"1": {"hp": 3, "known": ["monster:고블린"], "plan": [...], "intent": {...}}},
   "probe": {"bot": "1", "messages": [{"from": "2", "text": "물러서!"}]}}

⚠️ 실LLM 모드(haiku·probe)는 claude.exe 콜을 만든다 — 다른 실판(스모크·배치)이 도는
동안 병렬로 돌리면 그쪽 타임아웃·폴백률을 오염시킨다(배치 경합 실측 전례).
스트림: state_scenario/<이름>/stream.jsonl — STREAM_FORMAT 상속(뷰어·parse_stream 소비
가능. 뷰어로 보려면 runs/ 로 복사). 도감 원장(bestiary.json)은 절대 안 건드린다 —
장면 전제 지식은 bots[].known 으로 메모리에만 주입.
"""
import os
import sys
import json
import time
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import dungeon_gm as G
import brains
from stream import StreamWriter


def load_sheets():
    """party.json(있으면) → HEROES 폴백. 러너 load_party 의 라이트판(디버깅 도구라 관대)."""
    sheets = dict(G.HEROES)
    try:
        with open(os.path.join(HERE, "party.json"), encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            if k != "_" and isinstance(v, dict):
                sheets[k] = v
    except Exception:
        pass
    return sheets


SCAN_ON = os.environ.get("DUNGEON_SCAN", "1") != "0"   # 스캐너(D19) — 러너와 같은 스위치·같은 기본
                                                        #   (기본 1 승격: 2026-07-15 미로 판정 채택 — 파트너 육안)
ALLY_SIGHT_ON = os.environ.get("DUNGEON_ALLY_SIGHT", "0") != "0"   # 동료 시야 면제(07-26) —
                                                        #   러너와 같은 스위치·같은 기본(0). A/B 대조용


def build(spec):
    """장면 JSON → (dungeon, bots). 봇은 맵의 숫자 자리 그대로(스폰 탐색 우회)."""
    d, starts = G.Dungeon.from_ascii(spec["map"], seed=spec.get("seed", 7),
                                     monsters=spec.get("monsters"),
                                     traps=spec.get("traps"), scan=SCAN_ON)
    d.ally_sight = ALLY_SIGHT_ON       # from_ascii 는 __new__ 경유 — 스위치는 호출측이 켠다
    try:
        with open(os.path.join(HERE, "lore.json"), encoding="utf-8") as f:
            d.lore = json.load(f)
    except Exception:
        pass
    if not starts:
        raise ValueError("장면 맵에 봇 자리(숫자 1~9)가 없다")
    sheets = load_sheets()
    bots = []
    for c in sorted(starts):
        sheet = sheets.get(c) or G.HEROES.get(c) or next(iter(G.HEROES.values()))
        b = G.spawn(d, c, bots, sheet=sheet)
        d.visited.discard((b["x"], b["y"]))
        b["x"], b["y"] = starts[c]
        d.visited.add(starts[c])
        ov = (spec.get("bots") or {}).get(c) or {}
        if "hp" in ov:
            b["hp"] = min(int(ov["hp"]), b["maxhp"])
        if "bag" in ov:
            b["bag"] = int(ov["bag"])
        if "known" in ov:                      # 도감 게이팅 켬 — 장면 전제 지식(메모리 전용)
            b["known"] = set(ov["known"])
        if "plan" in ov:                       # 작정(D16) 프리셋 — 큐 물리를 LLM 없이 실험
            b["plan"] = [dict(s) for s in ov["plan"]][:G.PLAN_MAX]
        if "intent" in ov:
            b["intent"] = dict(ov["intent"])
        if "weapon" in ov:                     # 장비(07-30) 프리셋 — 착용 상태 장면 저작
            b["weapon"] = dict(ov["weapon"]) if ov["weapon"] else None
        if "armor" in ov:
            b["armor"] = dict(ov["armor"]) if ov["armor"] else None
        if "order" in ov:                      # 진행 중 order 프리셋(D18) — 동행 고착 류 장면 저작.
            b["order"] = ov["order"]           # path 는 안 깐다: follow 류는 자가 재경로로 자활,
                                               # goto 류는 다음 틱 _order_done 판정 — 장면 저작자 책임
        led = G.new_ledger()                   # 공간 장부(D17) — 장면은 라이브 판과 같은 조건(기본 켬)
        pre = ov.get("ledger")
        if isinstance(pre, dict):              # 장면 전제 기억: {"statics": ["chest","exit"...], "turn": N}
            t0 = int(pre.get("turn", 0))       #   — 피처 '종류'로 지정하면 장면의 실물 id 로 풀어 등재
            for want in pre.get("statics", []):
                for f in d.features.values():
                    if f.type == want and not f.concealed:
                        k = "exit" if f.type == "exit" else "f%d" % f.id
                        led["statics"][k] = {"id": k, "type": f.type, "name": f.name,
                                             "x": f.x, "y": f.y,
                                             "zone": d._zone_label(f.x, f.y), "turn": t0}
        b["ledger"] = led
        bots.append(b)
    for fs in spec.get("features") or []:      # 추가 피처 — from_ascii 글리프 밖(장비 상위 티어 등)
        d._add_feature(fs["type"], fs["name"], int(fs["x"]), int(fs["y"]),
                       concealed=bool(fs.get("concealed")))
    for m in d.monsters:                       # HUNTING/FLEEING 템플릿 목표 좌표 채움
        if m.target:
            t = next((b for b in bots if b["char"] == m.target), None)
            if t:
                m.last_seen, m.lost = (t["x"], t["y"]), 0
    d.turn = int(spec.get("turn_now", 0))      # 장면의 '지금' — 장부 '몇 턴 전' 라벨의 기준
    return d, bots


def summary(res):
    keep = ("type", "result", "target", "to", "trap", "found", "monsters",
            "roll", "total", "hit", "dmg", "hp", "loot", "why", "missing")
    return " ".join("%s=%s" % (k, json.dumps(res[k], ensure_ascii=False))
                    for k in keep if k in res)


def dummy_decide(d, bots, inbox):
    """think_all 의 규칙두뇌판(LLM 0콜) — 작정 큐(plan_step)는 동일하게 소비(물리 재현)."""
    out = {}
    for b in bots:
        if not b["alive"] or b["won"] or b.get("order"):
            continue
        step = d.plan_step(b, bots)
        if step:
            out[b["char"]] = {**step, "say": "", "reason": "[작정] 미리 정한 다음 수",
                              "src": "plan"}
            continue
        obs = d.view(b, bots)
        obs["messages"] = inbox.get(b["char"], [])
        dec = dict(G.dummy_brain(obs, b["char"]))
        dec.update(say="", reason="", src="dummy")
        out[b["char"]] = dec
    return out


def play(spec, brain, state_dir):
    d, bots = build(spec)
    turns = int(spec.get("turns", 12))
    os.makedirs(state_dir, exist_ok=True)
    sw = StreamWriter(os.path.join(state_dir, "stream.jsonl"))
    sw.emit("run_meta", v=1, started=time.strftime("%Y-%m-%dT%H:%M:%S"),
            seed=spec.get("seed", 7), w=d.w, h=d.h, depths=1,
            monsters=len(d.monsters), traps=len(d.traps),
            lurkers=sum(1 for m in d.monsters if m.concealed),
            max_turns=turns, gm=False, stream_obs=False, menu=brains.MENU,
            ledger=True,                       # 장면은 장부(D17) 상시 켬 — 라이브 판과 같은 조건
            scan=SCAN_ON,                      # 스캐너(D19) 여부 — 정지 물리가 달라진다(비교 전제)
            ally_sight=ALLY_SIGHT_ON,          # 동료 시야 면제(07-26) — 시야 물리 메타(A/B 전제)
            backend=brains.backend_name(),     # 두뇌 백엔드(2026-07-25 additive) — show_runner 와
                                               #   같은 필드명. 프로브도 어느 배관으로 잰 건지
                                               #   사후 판독돼야 한다(속도 실측이 이 파일도 쓴다)
            scenario=spec.get("name"),         # additive — 장면 실행 표식
            turn_now=int(spec.get("turn_now", 0)),   # 장부 시계 원점(additive) — 장부 스탬프는
                                               #   turn_now+tick 시계를 쓴다(리플레이 조인용)
            scenario_bots=spec.get("bots") or {},    # 장면 프리셋(지식·작정·장부 등, additive) —
                                               #   스트림 밖 원천 없음 계약을 장면에서도 닫는다
            bestiary={}, bestiary_file=False,
            party=[{k: b[k] for k in ("char", "job", "sex", "maxhp", "str", "dex",
                                      "wdmg", "stealth", "search_r", "persona")}
                   for b in bots])
    sw.emit("level", turn=0, **d.level_snapshot(),
            party=[G.bot_snapshot(b) for b in bots])
    print("== 장면: %s (%s 두뇌, %d틱) — %s ==" %
          (spec.get("name", "?"), brain, turns, spec.get("about", "")))
    inbox = {b["char"]: [] for b in bots}
    turn = 0
    for turn in range(1, turns + 1):
        d.turn = d.turn + 1                    # 장부 스탬프 — 장면 시작점(turn_now)에서 이어 센다
        inbox_in = inbox
        if brain == "haiku":
            decisions = brains.think_all(d, bots, inbox)
        else:
            decisions = dummy_decide(d, bots, inbox)
        print("-- tick %d --" % turn)
        turn_events = []
        says = {}
        for b in bots:
            if not b["alive"] or b["won"]:
                dec = decisions.get(b["char"])
                if dec is not None:
                    dec["skipped"] = True
                continue
            if b.get("order"):
                res = d.step_order(b, bots)
            else:
                dec = decisions.get(b["char"])
                if not dec:
                    continue
                res = d.act(b, dec, bots)
                res["reason"] = dec.get("reason", "")
                if dec.get("say"):
                    says[b["char"]] = dec["say"]
                    print('   봇%s \U0001f4ac "%s"' % (b["char"], dec["say"]))
            res["job"] = b["job"]
            turn_events.append(res)
            src = (decisions.get(b["char"]) or {}).get("src", "walk") \
                if not b.get("order") or res.get("type") != "walk" else "walk"
            print("   봇%s  %s%s" % (b["char"], summary(res),
                                     "  [작정]" if src == "plan" else ""))
        mon_events = d.monster_turn(bots)
        for e in mon_events:
            print("   몹  %s" % json.dumps(e, ensure_ascii=False))
        turn_events += mon_events
        inbox = {}
        for b in bots:
            seen = d.visible_cells(b["x"], b["y"]) if b["alive"] else set()
            inbox[b["char"]] = [{"from": oc, "text": t} for oc, t in says.items()
                                if oc != b["char"]
                                and any(o["char"] == oc and (o["x"], o["y"]) in seen
                                        for o in bots)]
        sw.emit("tick", turn=turn, inbox=inbox_in, decisions=decisions,
                events=turn_events,
                bots=[G.bot_snapshot(b) for b in bots],
                monsters=[m.as_dict() for m in d.monsters],
                features=[f.as_dict() for f in d.features.values()],
                traps=[t.as_dict() for t in d.traps])
        if all(not b["alive"] or b["won"] for b in bots):
            break
    won = sorted(b["char"] for b in bots if b["won"])
    dead = sorted(b["char"] for b in bots if not b["alive"])
    left = sorted(b["char"] for b in bots if b["alive"] and not b["won"])
    outcome = ("escaped" if won and not left else
               "wiped" if not won and not left else "timeout")
    sw.emit("end", turn=turn, outcome=outcome, depth=d.depth,
            survivors=won, fallen=dead, remaining=left,
            bots=[G.bot_snapshot(b) for b in bots])
    sw.close()
    print("== 끝: %s (생존 %s / 쓰러짐 %s / 잔류 %s) → %s ==" %
          (outcome, ",".join(won) or "-", ",".join(dead) or "-",
           ",".join(left) or "-", os.path.join(state_dir, "stream.jsonl")))


def probe(spec, n, jobs):
    d, bots = build(spec)
    pspec = spec.get("probe") or {}
    char = pspec.get("bot") or bots[0]["char"]
    b = next(bb for bb in bots if bb["char"] == char)
    obs = d.view(b, bots)
    obs["messages"] = pspec.get("messages") or []
    if b.get("intent"):
        obs["intent"] = b["intent"]
    print("== 프로브: %s / 봇%s(%s) / %d콜 (jobs %d) — %s ==" %
          (spec.get("name", "?"), char, b["job"], n, jobs, spec.get("about", "")))
    print("   (실Haiku 콜 — 다른 실판이 도는 중이면 경합 오염 주의)")

    def one(i):
        t0 = time.time()
        dec = brains.claude_brain(obs, char, b, bots)
        return time.time() - t0, dec

    with ThreadPoolExecutor(max_workers=jobs) as ex:
        rows = list(ex.map(one, range(n)))
    acts, thens, srcs = Counter(), Counter(), Counter()
    lat = sorted(t for t, _ in rows)
    for t, dec in rows:
        srcs[dec.get("src", "?")] += 1
        acts[("%s %s" % (dec.get("type"), dec.get("target", ""))).strip()] += 1
        th = dec.get("then")
        thens["then %d수" % len(th) if th else "then 없음"] += 1
        line = "  %5.1fs  %-16s" % (t, "%s %s" % (dec.get("type"), dec.get("target", "")))
        if th:
            line += "  then=" + json.dumps(th, ensure_ascii=False)
        if dec.get("src") == "fallback":
            line += "  [폴백] " + dec.get("reason", "")
        elif dec.get("reason"):
            line += "  | " + dec.get("reason", "")[:60]
        print(line)
    print("── 분포 ──")
    for k, v in acts.most_common():
        print("  %2d/%d  %s" % (v, n, k))
    print("  " + " · ".join("%s %d" % kv for kv in thens.most_common()))
    print("  src: " + " · ".join("%s %d" % kv for kv in srcs.most_common()))
    print("  지연: 최소 %.1fs / 중간 %.1fs / 최대 %.1fs"
          % (lat[0], lat[len(lat) // 2], lat[-1]))


def main():
    ap = argparse.ArgumentParser(description="시나리오 러너(디버깅 모드) — 장면 실행/결정 프로브")
    ap.add_argument("scene", help="장면 JSON 경로 (scenarios/*.json)")
    ap.add_argument("--brain", choices=["haiku", "dummy"], default="haiku",
                    help="장면 실행 두뇌(기본 haiku, dummy=LLM 0콜 물리 점검)")
    ap.add_argument("--probe", type=int, metavar="N",
                    help="결정 프로브: 같은 장면 첫 결정 N콜 분포(실Haiku)")
    ap.add_argument("--jobs", type=int, default=2,
                    help="프로브 동시 콜 수(기본 2 — 배치 경합 교훈)")
    a = ap.parse_args()
    with open(a.scene, encoding="utf-8") as f:
        spec = json.load(f)
    spec["name"] = spec.get("name") or os.path.splitext(os.path.basename(a.scene))[0]
    if a.probe:
        probe(spec, a.probe, a.jobs)
    else:
        play(spec, a.brain, os.path.join(HERE, "state_scenario", spec["name"]))


if __name__ == "__main__":
    import envload
    envload.load()      # show_runner 와 같은 규칙 — __main__ 안에서만(게이트는 안 밟는다)
    main()

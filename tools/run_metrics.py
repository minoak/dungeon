# -*- coding: utf-8 -*-
"""판 지표 v0(c16, 2026-10-16) — 스트림(JSONL)만 읽어 캐릭터별 다양성·루프·진행 숫자를 표로. LLM 0콜, 판을 안 돌린다, 스트림을 고치지 않는다.

왜: 민옥(10-15) "마을에서 얼마나 다양한 활동을 하는지", "다양함은 캐릭터 성격에 따라 다를 것", "한 판이나 두 판 돌리면서 정량평가".
0.5.13 실판 분석(.orch/drafts/run_0513_haiku_analysis.md)의 숫자를 손으로 셌다 — 패치 전후를 같은 자로 다시 재려고 남긴다.
설계 근거: 벤치 v2 §4(.orch/drafts/freedom_bench_v2_design.md) · 욕구 설계 §3.8.4·§9(.orch/drafts/economy_design.md). 지표 정의는 .orch/drafts/run_metrics_v0.md.

쓰는 법:
    python tools/run_metrics.py runs/a.jsonl [runs/b.jsonl …] [--ticks N] [--json]
      --ticks N  앞 N틱만 센다(turn ≤ N — 이어간 판의 앞 조각만 보거나, 길이가 다른 판을 같은 구간끼리 견줄 때)
      --json     표 대신 지표 dict 를 JSON 으로
    출력은 마크다운 표다(문서에 그대로 붙인다). 판이 둘 이상이면 끝에 판 비교 표가 붙는다.

읽는 법 — 세 갈래(욕구 설계 §3.8 관리자 정리):
  · 다양성: 동사 분포·엔트로피(유효 동사 수 = 2^H — 고르게 쓴 동사가 사실상 몇 개인가), 서로 다른 대상, 마을 구역, 말 건 사람, 마을 활동 종류
  · 루프: 같은 대상 연속(동사 무관 — repeat_signal.key_of 그대로) 5회 이상 구간, 기다리기 연속,
          반복 신호 재생(repeat_signal.see/step 을 그대로 돌려 5·10번째 · 변화 없음 — 궤적의 gap·said 를 뺀 판정을 나란히, run_metrics_v0.md §5)
  · 진행: 던전 진입·최대 깊이, 골드, 전원 같은 구역·서로 3칸 안 비율
⚠️ 세지 판정하지 않는다 — 해석은 사람이 한다. 본 스트림만 읽는다(파티 결성 판의 옆 파일 stream_side.jsonl 은 v0 밖 — 갈라진 세계의 판단은 빠진다).
⚠️ 반복 신호 재생은 관측 동봉 판(run_meta.stream_obs)이 아니면 근사다 — 관측을 스트림에서 다시 만든다(_pseudo_obs 머리글).
"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))   # 리포 루트 모듈 import 용
import collections
import copy
import json
import math
import os
import sys

import repeat_signal as RS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOOP_MIN = RS.AT[0]                       # 루프 구간의 최소 길이 = 반복 신호 첫 차례(5)
MOVES = ("goto", "explore", "wait")       # 움직임·머묾 — 결과가 나도 마을 '활동'으로 세지 않는다
ACT = {                                   # (동사, 결과) → 마을 활동 이름. 표에 없는 결과는 '동사/결과' 원문 그대로 센다(조용히 버리지 않는다)
    ("use", "npc_talk"): "NPC 대화", ("use", "npc_gift"): "NPC 선물", ("use", "npc_report"): "의뢰 보고",
    ("use", "quest_accepted"): "의뢰 맡기", ("use", "quest_already"): "의뢰 맡기",
    ("use", "bought"): "사기", ("use", "sold"): "팔기", ("use", "too_poor"): "돈 모자람",
    ("use", "no_deal"): "거래 안 됨", ("use", "not_enough"): "거래 안 됨", ("use", "no_room"): "거래 안 됨",
    ("use", "browsed"): "가게 구경", ("use", "lodged"): "묵기", ("use", "read"): "읽기", ("use", "sat"): "앉기",
    ("use", "drank"): "물 마시기", ("use", "warmed"): "불 쬐기", ("use", "practiced"): "연습", ("use", "rummaged"): "뒤지기",
    ("use", "used_up"): "다 쓴 것 쓰기", ("use", "healed"): "물약 마시기", ("use", "drink_boon"): "축복 물약", ("use", "equip"): "장비 바꾸기",
    ("use", "no_effect"): "헛손질", ("use", "exit"): "던전 입구 쓰기", ("use", "wait_allies"): "던전 입구 쓰기",
    ("use", "need_party"): "던전 입구 쓰기",
}
ACT_VERB = {"search": "살피기", "bond": "몸짓", "give": "건네기", "rest": "쉬기", "attack": "공격",
            "party_form": "파티 맺기", "party_leave": "파티 떠나기"}   # 결과와 무관하게 동사로 묶는 것
SAY_ALLY, SAY_NPC = "말(동료)", "말(NPC 지목)"                          # 판단의 say·to 로 세는 활동
TALK = {None: "보통", "close": "닫는 말", "busy": "거절", "away": "등 돌림"}   # NPC 대화 단계(사건·되받기의 talk 칸 — p0.5.10·0.5.14)
NEAR = 3                                  # '전원 곁' = 서로 체비셰프 3칸 안 — 0.5.13 손 분석의 '파티 함께 13%·최장 이산 248틱'이 이 정의였다


def _records(path):
    """유효 prefix — 돌고 있는 판의 잘린 마지막 줄에서 멈춘다(analyze_run 과 같은 규칙)."""
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except ValueError:
                return


def _entropy(counter):
    """섀넌 엔트로피(비트). 예) 동사 넷을 똑같이 썼으면 2.0, 하나만 썼으면 0."""
    n = sum(counter.values())
    return -sum(v / n * math.log2(v / n) for v in counter.values() if v) if n else 0.0


def _zone_fn(level):
    """마을 구역 판정기 (x, y) → 구역 이름. 스트림의 level.zones.town(p0.5.12 additive)이 있으면 그것.
    없으면(옛 판) 지금 마을 배치(town.json → layout)를 컴파일하되, 벽/바닥만 남긴 격자가 스트림 level.grid 와 같을 때만 쓴다
    (엔진 _town_zone 과 같은 규칙 — 구역 사각형에 테두리 pad 를 되돌려 비교). 다르면 None. 반환 (함수|None, 출처 글)."""
    town = (level.get("zones") or {}).get("town")
    if town:
        ids, cells = town.get("ids") or [], {}
        for y, row in enumerate(town.get("rows") or []):
            for i in range(0, len(row) - 2, 3):
                x0, n, k = row[i], row[i + 1], row[i + 2]
                for x in range(x0, x0 + n):
                    cells[(x, y)] = ids[k] if isinstance(k, int) and k < len(ids) else None
        return (lambda x, y: cells.get((x, y))), "스트림 level.zones"
    try:
        import town_layout as TL
        with open(os.path.join(ROOT, "town.json"), encoding="utf-8") as f:
            lp = json.load(f)["layout"]
        with open(os.path.join(ROOT, lp), encoding="utf-8") as f:
            res = TL.compile_layout(json.load(f))
    except Exception as e:                       # 배치 파일이 없거나 바뀐 꼴 — 구역 칸만 비운다
        return None, "구역 판정 불가(%s)" % type(e).__name__
    grid = ["".join("#" if ch == "#" else "." for ch in (r if isinstance(r, str) else "".join(r))) for r in res["map"]]
    if grid != level.get("grid"):
        return None, "구역 판정 불가(지금 마을 배치가 이 판의 격자와 다름)"
    pad = int(res.get("pad", 0) or 0)
    regions = (res.get("spaces") or {}).get("regions") or []

    def zone(x, y):
        lx, ly = x - pad, y - pad
        for r in regions:
            for rx, ry, rw, rh in r.get("rects", []):
                if rx <= lx < rx + rw and ry <= ly < ry + rh:
                    return r.get("name")
        return None
    return zone, "지금 마을 배치(%s — 격자 일치 확인)" % lp


def _pseudo_obs(snap, trail, gap, inbox, char, world):
    """반복 신호 재생용 '다시 만든 관측' — repeat_signal.see 가 읽는 칸만. 관측 동봉 판이 아니면 이것으로 근사한다.
    · 몸: 판단 직전 틱 끝의 봇 스냅샷(hp·maxhp·gold·bag·potions·boons·무기·방어구·status). 맡은 의뢰·파티원은 스냅샷에 없어 비교하지 않는다.
    · 결과: 직전 실판단 틱부터 이번 틱 앞까지 그 사람의 스트림 사건 + 러너·엔진이 궤적에만 넣는 칸 둘 — 지목한 말 `said`(show_runner 배달 —
      말 앞 40자 · 들은 사람은 다시 만들지 않는다)와 말 걸림 정지 `hail`(tick.hails = 그 틱 뒤 · npc_hails stopped = 그 틱 판단 앞).
      엔진 궤적과 같은 12칸 상한·gap. 사건에 러너가 붙인 속내(reason)는 뗀다(궤적엔 없다). 위급·회복(state)·피격 등 스트림에 없는 궤적 칸은 빠진다.
    · 들은 말: 이번 틱 inbox[char](to 가 나면 to_me).
    · 대상의 보이는 상태: 그 틱의 피처·봇·몬스터 전부를 '보인다'로 둔다 — 시야를 다시 계산하지 않으므로 '보이다 안 보임'은 못 잡는다('변화 없음' 쪽으로 기운다)."""
    feats, bots, mons = world
    return {
        "hp": snap.get("hp"), "maxhp": snap.get("maxhp"), "gold": snap.get("gold"), "inventory": snap.get("bag"),
        "potions": snap.get("potions"), "boons": snap.get("boons"), "gear": [snap.get("weapon"), snap.get("armor")],
        "status": snap.get("status") or [],
        "sights": {"features": [{"id": "f%s" % f.get("id"), "name": f.get("name"), "type": f.get("type")} for f in feats],
                   "bots": [{"char": b.get("char"), "hp": b.get("hp"), "maxhp": b.get("maxhp"), "status": b.get("status")} for b in bots],
                   "monsters": [{"id": "m%s" % m.get("id"), "kind": m.get("kind"), "hp": m.get("hp"), "state": m.get("state"),
                                 "status": m.get("status")} for m in mons],
                   "exit": {"gate": False, "sealed": False}},
        "trail": ([{"type": "gap", "n": gap}] if gap else []) + list(trail),
        "messages": [{**m, **({"to_me": True} if str(m.get("to")) == str(char) else {})} for m in inbox],
    }


def _together(st, t, ok):
    """'함께' 틱 세기 — 함께인 틱 수와, 함께가 아닌 틱이 가장 길게 이어진 구간(최장 갈라짐)."""
    st["ticks"] += 1
    if ok:
        st["same"] += 1
        st["run"] = 0
        return
    st["run"] += 1
    if st["run"] == 1:
        st["t0"] = t
    if st["run"] > st["max"]:
        st["max"], st["span"] = st["run"], (st["t0"], t)


def _together_out(st):
    return {"ticks": st["ticks"], "same": st["same"], "share": round(st["same"] / st["ticks"], 3) if st["ticks"] else None,
            "apart_max": st["max"], "apart_t": st["span"]}


def _label(key, fnames, names, depth=0):
    """대상 열쇠 → 사람이 읽는 이름. 피처·몬스터 번호는 층마다 다른 것이라 판단한 그 층의 이름으로 붙이고, 던전 층이면 앞에 'N층'을 단다
    (같은 f3 이라도 마을의 주점 주인과 1층의 보물은 다른 대상 — '서로 다른 대상'도 이 이름으로 센다)."""
    if key == RS.WAIT:
        return "기다리기"
    if key == "self":
        return "제자리"
    if key[:1] == "b" and key[1:] in names:
        return "%s(%s)" % (names[key[1:]], key)
    s = ("계단(exit)" if depth else "던전 입구(exit)") if key == "exit" else "%s(%s)" % (fnames[key], key) if key in fnames else key
    return ("%d층 " % depth if depth else "") + s


def measure(path, ticks=None):
    """스트림 하나 → 지표 dict(JSON 으로 내보낼 수 있는 꼴)."""
    meta, n_ticks, last_turn = {}, 0, 0
    names, persona = {}, {}
    fnames = {}
    zone_of, zone_src, depth, max_depth, first_dungeon = None, "-", 0, 0, None
    C = {}                                       # char → 누적
    rs_bots, cur, buf, gap = {}, {}, {}, {}      # 반복 신호 재생: 몸 dict · 지금 연속 구간 · 궤적 버퍼 · 잘린 수
    rs_nogap = {}                                # 같은 재생을 궤적의 생략 표식(gap)·내가 한 말(said) 없이 한 번 더 — run_metrics_v0.md §4

    def push(c, e):
        """궤적 버퍼에 한 칸 — 엔진 궤적 상한(dungeon_gm.TRAIL_MAX 12): 넘치면 앞을 버리고 gap 누적."""
        buf.setdefault(c, []).append(e)
        if len(buf[c]) > 12:
            gap[c] = gap.get(c, 0) + len(buf[c]) - 12
            del buf[c][:len(buf[c]) - 12]
    prev_snap, world = {}, ([], [], [])
    zone_t = {"ticks": 0, "same": 0, "run": 0, "max": 0, "t0": None, "span": None}   # 전원 같은 마을 구역
    near_t = {"ticks": 0, "same": 0, "run": 0, "max": 0, "t0": None, "span": None}   # 전원 서로 NEAR 칸 안(손 분석의 '함께')
    sig_real, sig_check = [], {"real": 0, "match": 0, "group_mismatch": 0}
    npc_replies, npc_brain = 0, 0

    def ch(c):
        c = str(c)
        if c not in C:
            C[c] = {"dec": 0, "plan": 0, "verbs": collections.Counter(), "keys": collections.Counter(), "seq": [],
                    "zones": set(), "depths": set(), "npc": collections.Counter(), "ally": collections.Counter(), "say_all": 0,
                    "acts": collections.Counter(), "talk": collections.Counter(), "status": collections.Counter(),
                    "gold": {"start": None, "end": None, "min": None}, "goldev": collections.Counter(), "goldsum": collections.Counter(),
                    "groups": [], "signals": [], "todo": [], "todo_dec": 0}
        return C[c]

    for rec in _records(path):
        k = rec.get("kind")
        if k == "run_meta":
            meta = rec
            for q in rec.get("party") or []:
                names[str(q.get("char"))] = q.get("name") or q.get("job") or "봇%s" % q.get("char")
                persona[str(q.get("char"))] = q.get("persona") or ""
                ch(q.get("char"))
        elif k == "level":
            depth = int(rec.get("depth") or 0)
            max_depth = max(max_depth, depth)
            if depth > 0 and first_dungeon is None:
                first_dungeon = rec.get("turn")
            fnames = {"f%s" % f.get("id"): f.get("name") for f in rec.get("features") or []}
            fnames.update({"m%s" % m.get("id"): m.get("name") or m.get("kind") for m in rec.get("monsters") or []})
            if depth == 0:
                zone_of, zone_src = _zone_fn(rec)
            for b in rec.get("party") or []:      # 층 전이 = 새 몸 — 반복 신호의 연속도 새로 센다(repeat_signal 머리글)
                c = str(b.get("char"))
                rs_bots[c], rs_nogap[c], cur[c], buf[c], gap[c] = {"char": c}, {"char": c}, None, [], 0
                prev_snap[c] = b
                g = ch(c)["gold"]
                if g["start"] is None and b.get("gold") is not None:
                    g["start"] = g["min"] = g["end"] = b.get("gold")
            world = (rec.get("features") or [], rec.get("party") or [], rec.get("monsters") or [])
        elif k == "tick":
            t = rec.get("turn") or 0
            if ticks and t > ticks:
                break
            n_ticks, last_turn = n_ticks + 1, t
            inbox = rec.get("inbox") or {}
            for h in rec.get("npc_hails") or []:      # NPC 인사에 선 몸은 이 틱에 판단한다 — 궤적에 말 걸림 한 칸(dungeon_gm.npc_hail_stop)
                if h.get("stopped") and str(h.get("char")) in C:
                    push(str(h["char"]), {"type": "hail", "result": "hailed", "froms": ["npc:%s" % h.get("npc")]})
            # ① 판단 — 엔진 순서대로: 관측(see) → 판단 세기(step). 작정 수는 관측이 없다(see 없음·궤적 유지)
            for c, dec in (rec.get("decisions") or {}).items():
                if not isinstance(dec, dict) or not dec.get("type"):
                    continue
                c = str(c)
                S = ch(c)
                S["dec"] += 1
                S["verbs"][dec["type"]] += 1
                key = RS.key_of(dec, c)
                lab = _label(key, fnames, names, depth) if key is not None else None
                if key is not None and key != RS.WAIT:
                    S["keys"][lab] += 1
                S["seq"].append((t, dec["type"], key, lab))
                if depth == 0 and dec.get("say"):
                    to = str(dec.get("to") or "")
                    if to.startswith("npc:"):
                        S["npc"][to[4:]] += 1
                        S["acts"][SAY_NPC] += 1
                    elif to:
                        S["acts"][SAY_ALLY] += 1
                        if to == "all":
                            S["say_all"] += 1
                        elif to != c:
                            S["ally"][names.get(to, to)] += 1
                if "todo" in dec:
                    S["todo_dec"] += 1
                bot = rs_bots.setdefault(c, {"char": c})
                bot2 = rs_nogap.setdefault(c, {"char": c})
                if dec.get("src") == "plan":
                    S["plan"] += 1
                    obs = obs2 = None
                else:
                    real = dec.get("obs")
                    if isinstance(real, dict):        # 관측 동봉 판 — 진짜 관측으로 재생하고 실제 신호와 맞댄다
                        if "repeat" in real:
                            sig_real.append((t, c, real["repeat"]))
                        obs = {kk: copy.deepcopy(v) for kk, v in real.items() if kk != "repeat"}
                    else:
                        obs = _pseudo_obs(prev_snap.get(c) or {}, buf.get(c, []), gap.get(c, 0), inbox.get(c) or [], c, world)
                    obs2 = dict(obs, trail=[e for e in obs.get("trail") or [] if not (isinstance(e, dict) and e.get("type") in ("gap", "said"))])
                    RS.see(bot, obs)
                    RS.see(bot2, obs2)
                    if "repeat" in obs and cur.get(c):
                        rp = obs["repeat"]
                        s = {"turn": t, "n": rp.get("n"), "same": bool(rp.get("same")), "same_quiet": bool((obs2.get("repeat") or {}).get("same"))}
                        cur[c]["sig"].append(s)
                        S["signals"].append(dict(s, key=cur[c]["key"]))
                        if isinstance(real, dict):
                            sig_check["match"] += int(real.get("repeat") == rp)
                    buf[c], gap[c] = [], 0
                # 연속 구간 — repeat_signal.step 과 같은 묶음(같은 열쇠면 잇고, 다르면 새로, 열쇠가 없으면 끊는다)
                if key is None:
                    cur[c] = None
                elif cur.get(c) and cur[c]["key"] == key:
                    cur[c]["n"] += 1
                    cur[c]["t1"] = t
                    cur[c]["verbs"][dec["type"]] += 1
                else:
                    cur[c] = {"key": key, "label": lab, "n": 1, "t0": t, "t1": t, "verbs": collections.Counter([dec["type"]]), "sig": []}
                    S["groups"].append(cur[c])
                RS.step(bot, dec, obs)
                RS.step(bot2, dec, obs2)
                rch = bot.get("repeat")
                if (rch and rch.get("n")) != (cur[c] and cur[c]["n"]):
                    sig_check["group_mismatch"] += 1    # 내 묶음과 repeat_signal 의 연속 수가 어긋남(0 이어야 한다)
            # ② 사건 — 궤적 버퍼·마을 활동·NPC 대화 단계·골드
            for e in rec.get("events") or []:
                c = e.get("char")
                if c is None or str(c) not in C:
                    continue
                c = str(c)
                S = C[c]
                push(c, {kk: v for kk, v in e.items() if kk not in ("char", "reason")})
                res = e.get("resolution") or {}
                if res.get("phase") == "resolved":
                    S["status"][res.get("status")] += 1
                verb = res.get("type") or e.get("type")
                result = e.get("result") or res.get("reason")
                done = res.get("phase") == "resolved" if res else result not in (None, "approaching", "walking", "pathed", "arrived")
                if result in ("npc_talk", "npc_gift", "npc_report"):
                    S["npc"][e.get("npc") or "?"] += 1
                    S["talk"][TALK.get(e.get("talk"), e.get("talk"))] += 1
                npc_brain += e.get("line_src") == "brain"
                if depth == 0 and done and verb not in MOVES:
                    S["acts"][ACT.get((verb, result)) or ACT_VERB.get(verb) or "%s/%s" % (verb, result)] += 1
                if result in ("bought", "sold", "too_poor") or (result == "lodged" and e.get("paid")) \
                        or (result == "npc_report" and e.get("reward")) or (result == "given" and e.get("item") == "gold"):
                    S["goldev"][result] += 1
                    S["goldsum"][result] += int(e.get("price") if result == "bought" else e.get("got") if result == "sold" else
                                                e.get("paid") if result == "lodged" else e.get("reward") if result == "npc_report" else
                                                e.get("amount") if result == "given" else 0) or 0
            for c, dec in (rec.get("decisions") or {}).items():   # 배달 단계 — 지목한 말의 궤적 칸(show_runner 배달, 혼잣말·미실행은 없다)
                if isinstance(dec, dict) and dec.get("say") and dec.get("to") and not dec.get("skipped") and str(c) in C:
                    push(str(c), {"type": "said", "to": dec["to"], "kind": dec.get("say_kind") or "잡담", "text": str(dec["say"])[:40]})
            for c, froms in (rec.get("hails") or {}).items():   # 말 걸림 정지 — 다음 틱에 판단한다(사교 채널 판이면 'heard')
                if str(c) in C:
                    push(str(c), {"type": "hail", "result": "heard" if meta.get("social") else "hailed", "froms": list(froms)})
            for r in rec.get("npc_replies") or []:
                npc_replies += 1
                npc_brain += r.get("line_src") == "brain"
                if r.get("talk") and str(r.get("char")) in C:
                    C[str(r.get("char"))]["talk"]["되받기 " + TALK.get(r["talk"], r["talk"])] += 1
            npc_brain += sum(h.get("line_src") == "brain" for h in rec.get("npc_hails") or [])
            for op in rec.get("todo_ops") or []:
                if str(op.get("char")) in C:
                    C[str(op.get("char"))]["todo"].append({"turn": t, "text": op.get("text", "")})
            # ③ 몸 스냅샷 — 구역·깊이·골드·전원 함께
            here, xy = [], []
            for b in rec.get("bots") or []:
                c = str(b.get("char"))
                if c not in C:
                    continue
                S = C[c]
                prev_snap[c] = b
                if b.get("gold") is not None:
                    g = S["gold"]
                    g["start"] = b["gold"] if g["start"] is None else g["start"]
                    g["end"] = b["gold"]
                    g["min"] = b["gold"] if g["min"] is None else min(g["min"], b["gold"])
                if not b.get("alive") or b.get("won"):
                    continue
                S["depths"].add(depth)
                z = zone_of(b.get("x"), b.get("y")) if (depth == 0 and zone_of and b.get("x") is not None) else None
                if z:
                    S["zones"].add(z)
                here.append(z)
                if b.get("x") is not None:
                    xy.append((b["x"], b["y"]))
            if depth == 0 and zone_of and len(here) >= 2:
                _together(zone_t, t, len(set(here)) == 1 and here[0] is not None)
            if len(xy) >= 2:
                _together(near_t, t, all(max(abs(a[0] - b[0]), abs(a[1] - b[1])) <= NEAR for a in xy for b in xy))
            world =(rec.get("features") or world[0], rec.get("bots") or [], rec.get("monsters") or [])
        elif k == "descend" and first_dungeon is None:
            first_dungeon = rec.get("turn")

    sig_check["real"] = len(sig_real)
    out_chars = {}
    for c in sorted(C, key=lambda x: (len(x), x)):
        S = C[c]
        n = S["dec"]
        if not n and not S["depths"]:
            continue
        H = _entropy(S["verbs"])
        top = S["keys"].most_common(1)
        keyed = sum(S["keys"].values())
        vt = 0                                   # (동사, 대상) 같은 판단 연속 최댓값 — 벤치 v2 지표 1·손 숫자 대조용
        vt_best, run, last = None, 0, None
        for t, verb, key, lab in S["seq"]:
            cur_k = (verb, lab) if key is not None else None
            run = run + 1 if (cur_k is not None and cur_k == last) else (1 if cur_k is not None else 0)
            if cur_k is not None and run == 1:
                t_start = t
            if run > vt:
                vt, vt_best = run, {"verb": verb, "key": key, "label": lab, "n": run, "t0": t_start, "t1": t}
            last = cur_k
        groups = [{"key": g["key"], "label": g["label"], "n": g["n"], "t0": g["t0"], "t1": g["t1"],
                   "verbs": dict(g["verbs"].most_common()), "signals": g["sig"]}
                  for g in S["groups"] if g["n"] >= LOOP_MIN]
        tgt_groups = [g for g in groups if g["key"] != RS.WAIT]
        wait_groups = [g for g in groups if g["key"] == RS.WAIT]
        allw = [g for g in S["groups"] if g["key"] == RS.WAIT]
        wmax = max(allw, key=lambda g: g["n"]) if allw else None
        resolved = sum(S["status"].values())
        out_chars[c] = {
            "name": names.get(c, c), "persona": persona.get(c, ""),
            "decisions": n, "plan": S["plan"],
            "verbs": dict(S["verbs"].most_common()), "verb_entropy": round(H, 3), "verb_effective": round(2 ** H, 2),
            "targets": len(S["keys"]),
            "top_target": ({"label": top[0][0], "n": top[0][1], "share": round(top[0][1] / keyed, 3)} if top else None),
            "zones": sorted(S["zones"]), "depths": sorted(S["depths"]),
            "talked_npc": dict(S["npc"].most_common()), "talked_ally": dict(S["ally"].most_common()), "say_all": S["say_all"],
            "town_acts": dict(S["acts"].most_common()), "town_act_kinds": len(S["acts"]),
            "npc_talk_stage": dict(S["talk"].most_common()),
            "no_effect": {"n": S["status"].get("no_effect", 0), "resolved": resolved,
                          "share": round(S["status"].get("no_effect", 0) / resolved, 3) if resolved else None},
            "loops": tgt_groups, "waits": wait_groups,
            "longest_target": max(tgt_groups, key=lambda g: g["n"]) if tgt_groups else None,
            "longest_wait": ({"n": wmax["n"], "t0": wmax["t0"], "t1": wmax["t1"]} if wmax else None),
            "longest_verb_target": vt_best,
            "signals": {"n5": sum(1 for s in S["signals"] if s["n"] == 5), "n10": sum(1 for s in S["signals"] if s["n"] == 10),
                        "same": sum(1 for s in S["signals"] if s["same"]),
                        "same_quiet": sum(1 for s in S["signals"] if s["same_quiet"])},
            "gold": S["gold"], "gold_events": dict(S["goldev"]), "gold_sums": dict(S["goldsum"]),
            "todo_ops": S["todo"], "todo_decisions": S["todo_dec"],
        }
    tot = sum(v["decisions"] for v in out_chars.values())
    return {
        "file": path, "game_version": meta.get("game_version"), "seed": meta.get("seed"), "model": meta.get("model") or meta.get("backend"),
        "stream_obs": bool(meta.get("stream_obs")), "ticks": n_ticks, "last_turn": last_turn, "ticks_limit": ticks,
        "decisions": tot, "zone_src": zone_src,
        "dungeon": {"first_entry": first_dungeon, "max_depth": max_depth},
        "together_zone": _together_out(zone_t), "together_near": _together_out(near_t),
        "npc_replies": npc_replies, "npc_brain_lines": npc_brain,
        "signal_check": sig_check,
        "chars": out_chars,
    }


# ── 표 ─────────────────────────────────────────────────────────────────────────────

def _pct(x):
    return "-" if x is None else "%d%%" % round(100 * x)


def _top(d, k=6):
    items = list(d.items())
    s = " · ".join("%s %s" % (a, b) for a, b in items[:k])
    return (s + (" · …%d" % (len(items) - k) if len(items) > k else "")) or "-"


def _sig(g):
    word = lambda same: "변화 없음" if same else "달라짐"
    return " · ".join("%d번째 %s(t%d)%s" % (s["n"], word(s["same"]), s["turn"],
                                          "" if s["same"] == s["same_quiet"] else " → gap·said 빼면 %s" % word(s["same_quiet"]))
                      for s in g["signals"]) or "-"


def _sigsum(v):
    s = v["signals"]
    return "%d · 변화 없음 %d (gap·said 빼면 %d)" % (s["n5"] + s["n10"], s["same"], s["same_quiet"])


def _tog(t):
    return "%s (%d/%d틱) · 최장 갈라짐 %d틱%s" % (_pct(t["share"]), t["same"], t["ticks"], t["apart_max"],
                                             " t%s–%s" % tuple(t["apart_t"]) if t["apart_t"] else "")


def _span(g):
    return "t%s–%s" % (g["t0"], g["t1"]) if g else "-"


def render(m):
    L = []
    cs = list(m["chars"].items())
    head = ["%s(%s)" % (v["name"], c) for c, v in cs]
    L.append("## %s" % os.path.basename(m["file"]))
    L.append("")
    L.append("%s · 시드 %s · %s · %d틱%s · 결정 %d · 구역 판정: %s%s" % (
        m["game_version"] or "버전?", m["seed"], m["model"], m["ticks"],
        " (--ticks %d)" % m["ticks_limit"] if m["ticks_limit"] else "", m["decisions"], m["zone_src"],
        " · 관측 동봉" if m["stream_obs"] else ""))
    L.append("")
    L.append("| 지표 | " + " | ".join(head) + " |")
    L.append("|---" * (len(head) + 1) + "|")

    def row(label, f):
        L.append("| %s | %s |" % (label, " | ".join(f(v) for _, v in cs)))
    row("결정(작정)", lambda v: "%d%s" % (v["decisions"], " (%d)" % v["plan"] if v["plan"] else ""))
    row("동사 분포", lambda v: _top(v["verbs"], 9))
    row("동사 엔트로피 H / 유효 동사 수", lambda v: "%.2f / %.1f" % (v["verb_entropy"], v["verb_effective"]))
    row("서로 다른 대상", lambda v: str(v["targets"]))
    row("최다 대상(몫)", lambda v: "%s %d (%s)" % (v["top_target"]["label"], v["top_target"]["n"], _pct(v["top_target"]["share"]))
        if v["top_target"] else "-")
    row("마을 구역", lambda v: "%d (%s)" % (len(v["zones"]), "·".join(v["zones"])) if v["zones"] else "0")
    row("층", lambda v: ",".join(map(str, v["depths"])) or "-")
    row("말 건 NPC", lambda v: "%d — %s" % (len(v["talked_npc"]), _top(v["talked_npc"], 4)) if v["talked_npc"] else "0")
    row("말 건 동료(+모두에게)", lambda v: "%d — %s (+%d)" % (len(v["talked_ally"]), _top(v["talked_ally"], 3), v["say_all"])
        if v["talked_ally"] else "0 (+%d)" % v["say_all"])
    row("마을 활동 종류", lambda v: str(v["town_act_kinds"]))
    row("마을 활동", lambda v: _top(v["town_acts"], 8))
    row("NPC 대화 단계", lambda v: _top(v["npc_talk_stage"], 6))
    row("판정 변화 없음(no_effect)", lambda v: "%s (%d/%d)" % (_pct(v["no_effect"]["share"]), v["no_effect"]["n"], v["no_effect"]["resolved"]))
    row("같은 대상 %d회+ 구간 수 / 최장" % LOOP_MIN, lambda v: "%d / %s" % (len(v["loops"]), "%d %s %s" % (
        v["longest_target"]["n"], v["longest_target"]["label"], _span(v["longest_target"])) if v["longest_target"] else "-"))
    row("(동사, 대상) 최장", lambda v: "%d %s %s %s" % (v["longest_verb_target"]["n"], v["longest_verb_target"]["verb"],
                                                   v["longest_verb_target"]["label"], _span(v["longest_verb_target"]))
        if v["longest_verb_target"] else "-")
    row("기다리기 최장", lambda v: "%d %s" % (v["longest_wait"]["n"], _span(v["longest_wait"])) if v["longest_wait"] else "-")
    row("반복 신호 재생(5·10번째 합)", _sigsum)
    row("골드 시작→끝 (최저)", lambda v: "%s→%s (%s)" % (v["gold"]["start"], v["gold"]["end"], v["gold"]["min"])
        if v["gold"]["start"] is not None else "- (골드 칸 없는 판)")
    row("골드 사건(합)", lambda v: " · ".join("%s %d(%d)" % (k, n, v["gold_sums"].get(k, 0)) for k, n in v["gold_events"].items()) or "0")
    row("할 일 적음(판단 칸) / 바뀜", lambda v: "%d / %d" % (v["todo_decisions"], len(v["todo_ops"])))
    L.append("")
    L.append("- 던전 진입 %s · 최대 깊이 %d · NPC 되받기 %d · NPC 두뇌 대사 %d" % (
        ("t%s" % m["dungeon"]["first_entry"]) if m["dungeon"]["first_entry"] is not None else "없음", m["dungeon"]["max_depth"],
        m["npc_replies"], m["npc_brain_lines"]))
    L.append("- 전원 같은 마을 구역: %s" % _tog(m["together_zone"]))
    L.append("- 전원 서로 %d칸 안: %s" % (NEAR, _tog(m["together_near"])))
    sc = m["signal_check"]
    L.append("- 반복 신호 재생 점검: 묶음 어긋남 %d (0 이어야 한다)%s" % (
        sc["group_mismatch"], " · 실제 신호 %d 중 재생 일치 %d" % (sc["real"], sc["match"]) if m["stream_obs"] else " · 관측 동봉 판이 아니라 실제 신호와 맞댈 수 없다(근사)"))
    loops = [(v["name"], g) for _, v in cs for g in v["loops"] + v["waits"]]
    if loops:
        L.append("")
        L.append("### 같은 대상·기다리기 %d회 이상 구간" % LOOP_MIN)
        L.append("")
        L.append("| 사람 | 대상 | 길이 | 틱 | 동사 | 반복 신호 재생 |")
        L.append("|---|---|---|---|---|---|")
        for who, g in sorted(loops, key=lambda x: (x[1]["t0"], x[0])):
            L.append("| %s | %s | %d | %s | %s | %s |" % (who, g["label"], g["n"], _span(g), _top(g["verbs"], 4), _sig(g)))
    todos = [(v["name"], o) for _, v in cs for o in v["todo_ops"]]
    if todos:
        L.append("")
        L.append("### 할 일 칸 바뀜")
        L.append("")
        for who, o in sorted(todos, key=lambda x: x[1]["turn"]):
            L.append("- t%s %s: %s" % (o["turn"], who, o["text"] or "(비움)"))
    L.append("")
    return "\n".join(L)


def render_compare(ms):
    """판이 둘 이상이면 핵심 숫자만 나란히 — 사람별 값은 '/' 로 잇는다(run_meta.party 순)."""
    L = ["## 판 비교", ""]
    L.append("| 지표 | " + " | ".join("%s (%s)" % (os.path.basename(m["file"]), m["game_version"]) for m in ms) + " |")
    L.append("|---" * (len(ms) + 1) + "|")

    def per(m, f):
        return " / ".join(f(v) for v in m["chars"].values())

    rows = [
        ("사람", lambda m: per(m, lambda v: v["name"])),
        ("틱 · 결정", lambda m: "%d · %d" % (m["ticks"], m["decisions"])),
        ("결정", lambda m: per(m, lambda v: str(v["decisions"]))),
        ("유효 동사 수(2^H)", lambda m: per(m, lambda v: "%.1f" % v["verb_effective"])),
        ("서로 다른 대상", lambda m: per(m, lambda v: str(v["targets"]))),
        ("최다 대상 몫", lambda m: per(m, lambda v: _pct(v["top_target"]["share"]) if v["top_target"] else "-")),
        ("마을 구역", lambda m: per(m, lambda v: str(len(v["zones"])))),
        ("말 건 NPC", lambda m: per(m, lambda v: str(len(v["talked_npc"])))),
        ("마을 활동 종류", lambda m: per(m, lambda v: str(v["town_act_kinds"]))),
        ("같은 대상 최장", lambda m: per(m, lambda v: str(v["longest_target"]["n"]) if v["longest_target"] else "-")),
        ("기다리기 최장", lambda m: per(m, lambda v: str(v["longest_wait"]["n"]) if v["longest_wait"] else "-")),
        ("같은 대상 5회+ 구간", lambda m: per(m, lambda v: str(len(v["loops"])))),
        ("반복 신호 재생 · 변화 없음(gap·said 빼면)", lambda m: per(m, lambda v: "%d·%d(%d)" % (
            v["signals"]["n5"] + v["signals"]["n10"], v["signals"]["same"], v["signals"]["same_quiet"]))),
        ("판정 변화 없음", lambda m: per(m, lambda v: _pct(v["no_effect"]["share"]))),
        ("골드 사건", lambda m: per(m, lambda v: str(sum(v["gold_events"].values())))),
        ("던전 진입 · 최대 깊이", lambda m: "%s · %d" % (("t%s" % m["dungeon"]["first_entry"]) if m["dungeon"]["first_entry"] is not None
                                                     else "없음", m["dungeon"]["max_depth"])),
        ("전원 같은 구역 · 최장 갈라짐", lambda m: "%s · %d틱" % (_pct(m["together_zone"]["share"]), m["together_zone"]["apart_max"])),
        ("전원 %d칸 안 · 최장 갈라짐" % NEAR, lambda m: "%s · %d틱" % (_pct(m["together_near"]["share"]), m["together_near"]["apart_max"])),
    ]
    for label, f in rows:
        L.append("| %s | %s |" % (label, " | ".join(f(m) for m in ms)))
    L.append("")
    return "\n".join(L)


def main(argv):
    ticks, as_json = None, False
    if "--ticks" in argv:
        i = argv.index("--ticks")
        ticks = int(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    if "--json" in argv:
        as_json = True
        argv = [a for a in argv if a != "--json"]
    if not argv:
        print(__doc__)
        return 1
    ms = [measure(p, ticks) for p in argv]
    if as_json:
        print(json.dumps(ms if len(ms) > 1 else ms[0], ensure_ascii=False, indent=1))
        return 0
    for m in ms:
        print(render(m))
    if len(ms) > 1:
        print(render_compare(ms))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    raise SystemExit(main(sys.argv[1:]))

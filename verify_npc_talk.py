# -*- coding: utf-8 -*-
"""p0.5.10 신원 ID-2 — NPC 대화 한 길(설계 identity_design_v2 §3 · DECISIONS 2026-10-12 'NPC 대화 피로' · 10-13 순서 변경). 실 LLM 0콜.
같은 모험가-NPC 쌍의 대화 장부 하나(bot['npc_talk']['npc:<이름>'])를 대화 세 길(use 말 걸기 · 자동 접근 도착 · 되받기)이 함께 센다.
상한(G.NPC_REPLY_MAX = 3)의 마지막 대답 = 닫는 말(한 번) · 그 뒤 말을 걸면 고정 거절(0콜) · 다음 마을 방문(새 봇 dict)에 풀린다 · use 의 판정은 막지 않는다.
약속 문제(10-12 은퇴한 모험자 "곧 들려주지", 10-13 장비 상인 "골라 줄 테니 기다려요"): NPC 쪽에서 막는다 — 말이 접근에 실리면 도착 때 판정과 함께 한 번 답한다 ·
멀리서 되받을 때는 '와서 말을 걸면 그 자리에서 무엇이 오가나'(Dungeon.npc_offer — 선물 판정과 한 원천)를 사실로 · NPC 지침에 '나중을 약속하지 않는다'.
게이트:
  ① 엔진 운반: 말 건 결과에 결정의 말(said) — 즉시 실행·자동 접근 도착이 같은 칸 · 말의 상대가 다른 사람이면 싣지 않는다 · 저장 사본(last·trail)엔 없다 ·
     접근 대기(approach)에 say·to · 결과 머리(CA.fields)·_active_action 에는 없다 · say 없는 옛 대기 dict 도 도착한다(said 없음 → '말없이 다가와 섰다')
  ② 말 건 사람의 직전 결과에 대사가 없다(설계 X10 — NPC 말은 들은 말로만) · 꼬리표에도 없다
  ③ npc_turn: 보통 대답 → 닫는 말(한 번, 장면 한 줄 · 두뇌 꺼짐/실패 = 정의 line_close → 공통 문장) → 고정 거절(0콜 · 정의 line_busy → 공통 문장) ·
     상한 뒤 use 의 선물·보고 판정은 그대로(대사는 그 용건의 고정 대사, 0콜) · 보고로 원정이 끝난다
  ④ 선물 단일 원천: Dungeon.npc_offer == _interact 의 실제 판정(NPC 넷 × 빈손·무장·만난 뒤·축복 받음 · 귀환 뒤 보고)
  ⑤ 약속 문제 회귀: 접근에 실린 말은 그 틱에 되받지 않는다(도착 때 한 번) · 되받기 장면 = 와서 말을 걸면 오갈 것('(지금은 아니다)' 없음) · NPC 지침의 '나중을 약속하지 않는다'
  ⑥ 방문 경계·인사: 새 몸(spawn)·층 이월(_carry)에 장부 없음 · NPC 먼저 인사(npc_hailed)는 세지 않는다
  ⑦ 저장 판 4: npc_replies{이름} → npc_talk{'npc:'+이름}(bots·worlds·waiting) · 한 번만
  ⑧ 러너 풀런(스텁 — 0콜): 10-13 장비 상인 장면 재연 — 멀리서 'use + 단검 청' → 결정 틱 되받기 없음 → 도착 틱 두뇌 1콜(그 말 + 단검 건넴 판정)·다음 틱 편지함 →
     바로 다시 use(2) → 지목(3 = 닫는 말) → use(거절 0콜) → 지목(거절 0콜) · 두뇌 콜 3 · 스트림 이벤트에 said 없음
  ⑩ (p0510b · Codex p0510r 필수 ①) 거절은 NPC 두뇌 차례(한 틱 한 콜)와 따로: 정상 응답자 먼저/상한 도달자 먼저 두 순서 모두 '대답 + 거절' ·
     다른 사람의 use 와 같은 틱에도 거절은 나간다(보통 지목은 차례가 없어 말 없음) · 같은 쌍은 한 틱 한 번 — 함수와 러너 풀런 둘 다
  ⑪ (p0510b · 필수 ②) 고정 대사 경로의 약속: NPC 15명의 대사·재방문·인사·보고(끈 판·마을 생활 판) + 공물 판 대사 + 공통 닫는 말·거절에 나중 약속 꼴 없음 ·
     바꾼 9칸이 엔진까지 · 리뷰 재현 경로(장비 상인 두 번째 use — 두뇌 꺼짐·실패·두뇌 힌트)
(기존 게이트는 별도 실행.)
"""
import contextlib
import inspect
import io
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = tempfile.mkdtemp(prefix="wl_npctalk_")
STATE = os.path.join(ROOT, "state")
os.makedirs(STATE, exist_ok=True)
BASE_ENV = dict(DUNGEON_GM="0", DUNGEON_STEP_DELAY="0", DUNGEON_TURNS="9", DUNGEON_W="40", DUNGEON_H="16",
                DUNGEON_DEPTHS="2", DUNGEON_SEED="7", DUNGEON_MONSTERS="0", DUNGEON_TRAPS="0", DUNGEON_LURKERS="0",
                DUNGEON_BESTIARY_FILE="", DUNGEON_PARTY_FILE=os.path.join(HERE, "party.json"), DUNGEON_STATE_DIR=STATE,
                DUNGEON_TOWN="1", DUNGEON_BRAIN_BACKEND="dummy", DUNGEON_BOSS="0", DUNGEON_RUNS_DIR=os.path.join(ROOT, "runs"),
                DUNGEON_ACTION_MODE="compose", DUNGEON_TOWN_LIFE="1")   # 마을 생활 = 10-13 실판 구성(장비 상인이 있는 마을)
os.environ.update(BASE_ENV)
for k in ("DUNGEON_QUESTS", "DUNGEON_TOWN_APART", "DUNGEON_NPC_BRAIN", "DUNGEON_SOLO", "DUNGEON_START", "DUNGEON_MENU", "DUNGEON_RESUME",
          "DUNGEON_PARTYFORM", "DUNGEON_STRANGERS", "DUNGEON_TOWN_SIGHT", "DUNGEON_NPC_REPLY", "DUNGEON_NPC_HAIL_BRAIN",
          "DUNGEON_API_CALL_LIMIT", "DUNGEON_BRAIN_FALLBACK", "DUNGEON_BRAIN_LOG", "DUNGEON_NPC_HAIL", "DUNGEON_NPC_HAIL_STOP"):
    os.environ.pop(k, None)

import brains                                        # noqa: E402
brains._call_claude = lambda prompt, model="haiku": ""   # LLM 무력화 → dummy 폴백(결정론)


def _no_real_backend(prompt, model):                 # 이중 안전핀: 어떤 길로도 진짜 백엔드는 안 부른다(⑧ 은 백엔드 이름만 claude_cli 로 돌린다)
    raise AssertionError("real backend must not be called in a gate")


brains._call_cli = brains._call_anthropic = brains._call_gemini = brains._call_openai = _no_real_backend
import composed_actions as CA                        # noqa: E402
import dungeon_gm as G                               # noqa: E402
import info_guard as IG                              # noqa: E402
import show_runner as R                              # noqa: E402
import snapshot as SN                                # noqa: E402
import time as _time                                 # noqa: E402
_time.sleep = lambda s: None
R.STEP_DELAY = 0


class C:
    failed = 0
    n = 0


def check(name, ok, detail=""):
    C.n += 1
    print("  %s %s%s" % ("OK  " if ok else "FAIL", name, (" — " + str(detail)) if (detail and not ok) else ""))
    if not ok:
        C.failed += 1


def src(*p):
    with open(os.path.join(HERE, *p), encoding="utf-8") as f:
        return f.read()


SHEETS = R.load_party(os.path.join(HERE, "party.json"))
NAMES = {c: SHEETS[c]["name"] for c in SHEETS}
GEAR, RECEPTION, ITEMS, PRIEST, KEEPER = "장비 상인", "길드 접수원", "아이템 상인", "성직자", "주점 주인"
S1 = "장비 상인님, 던전에 갈 건데 단검 하나 받을 수 있을까요?"   # 10-13 실판 t139 봇1 의 말 그대로


def town(quests=None):
    d, _ = R.build_town(apart=True, walkers=True, quests=quests)
    d.composed_actions = d.auto_approach = True
    d.npc_reply = True                               # 러너는 NPC 두뇌가 도는 판에만 건다
    bs = []
    for c in sorted(SHEETS):
        bs.append(G.spawn(d, c, bs, sheet=dict(SHEETS[c])))
    d.turn = 1
    return d, bs


def npc(d, name):
    return next(f for f in d.features.values() if f.type == "npc" and f.name == name)


def cells(d, f, lo, hi, taken=()):
    """NPC f 와 같은 구역의 빈 바닥 칸(거리 lo~hi, 가까운 순)."""
    z = d._town_zone(f.x, f.y)
    return [(x, y) for _, x, y in sorted((abs(x - f.x) + abs(y - f.y), x, y) for y in range(d.h) for x in range(d.w)
                                         if d.grid[y][x] == G.FLOOR and not d.feature_at(x, y) and d._town_zone(x, y) == z
                                         and lo <= abs(x - f.x) + abs(y - f.y) <= hi and (x, y) not in taken)]


def put(b, xy):
    b["x"], b["y"] = xy


def use(f, say=None, to=None):
    dec = {"type": "use", "target": "f%d" % f.id, "src": "haiku"}
    if say:
        dec["say"] = say
    if to:
        dec["to"] = to
    return dec


def act(d, b, dec, bots):
    """관측(참조표 _target_refs)을 만든 뒤 행동 — 조합형 entity() 는 관측에 나온 ID 만 해소한다(러너와 같은 순서)."""
    d.view(b, bots)
    return d.act(b, dec, bots)


def walk_until_done(d, b, bots, cap=120):
    """자동 접근을 도착까지 걷힌다(step_order) — 말 건 결과(또는 마지막 결과)를 돌려준다."""
    res = None
    for _ in range(cap):
        if not b.get("order"):
            break
        d.turn += 1
        res = d.step_order(b, bots)
        if res.get("result") in G.NPC_TALK_RESULTS:
            break
    return res


class Brain:
    """brains.npc_reply 스텁 — 부른 인자를 적고 정해 둔 문장(또는 None)을 돌려준다."""
    def __init__(self, line="그래, 잘 들었네."):
        self.calls, self.line = [], line

    def __call__(self, bot, res, said, facts, npc=None, roster=None, names=None):
        self.calls.append({"char": bot["char"], "res": dict(res), "said": said})
        return self.line


def turn_with(stub, d, b, name, said, res, brain_on=True):
    old = brains.npc_reply
    brains.npc_reply = stub
    try:
        return R.npc_turn(d, b, name, said, res, lambda nm_: ["사실 — " + nm_], brain_on, names=NAMES)
    finally:
        brains.npc_reply = old


print("── ① 엔진 운반: said · 접근 대기 · 저장 사본")
d, bots = town()
a, b2, b3 = bots
gm = npc(d, GEAR)
near = cells(d, gm, 1, 1)
put(a, near[0])
r1 = act(d, a, use(gm, S1, "npc:" + GEAR), bots)
check("① 곁에서 use + 말(상대 = 그 NPC) → 즉시 판정 결과에 said = 그 말(접근 없음) · 빈손이라 단검을 받았다",
      r1.get("result") == "npc_gift" and r1.get("item") == "단검" and r1.get("said") == S1 and "approach_status" not in r1, r1)
check("① 저장 사본(last·trail)에 said 가 없다(IG.DROP_KEYS) · 원본 결과에는 있다(러너가 걷는다)",
      "said" not in a["last"] and not any("said" in t for t in (a.get("trail") or [])) and "said" in IG.DROP_KEYS)
miss = []
for to_, want in (("2", False), ("all", True), (None, True), ("npc:" + KEEPER, False), ("npc:" + GEAR, True)):
    r_ = act(d, a, use(gm, "한 번 더요", to_), bots)
    if ("said" in r_) != want:
        miss.append((to_, r_.get("said")))
check("① 말의 상대가 다른 사람(동료 char · 다른 NPC)이면 싣지 않는다 · all·상대 없음·그 NPC 면 싣는다", not miss, miss)
r_q = act(d, a, use(gm), bots)
check("① 말 없는 use 는 said 칸 자체가 없다", r_q.get("result") in G.NPC_TALK_RESULTS and "said" not in r_q, r_q)

d1, bots1 = town()
a1 = bots1[0]
gm1 = npc(d1, GEAR)
put(a1, cells(d1, gm1, 6, 12)[0])
r0 = act(d1, a1, use(gm1, S1, "npc:" + GEAR), bots1)
ap = dict(a1.get("approach") or {})
check("① 멀리서 use + 말 → 접근 시작 · 대기 dict 에 say·to(설계 §3.2 보존) · _active_action 엔 없다 · 결과 머리(CA.fields)에 say·to 없음",
      r0.get("result") == "approaching" and ap.get("say") == S1 and ap.get("to") == "npc:" + GEAR
      and "say" not in (a1.get("_active_action") or {}) and not ({"say", "to"} & set(CA.fields())) and "say" not in r0, (r0, ap))
d1q, bots1q = town()
a1q = bots1q[0]
put(a1q, cells(d1q, npc(d1q, GEAR), 6, 12)[0])
act(d1q, a1q, {**use(npc(d1q, GEAR)), "say": "", "to": "2"}, bots1q)
check("① 말 없는(빈 say) 접근 대기에는 say·to 칸 자체가 없다(대기 dict·스냅샷 꼴이 옛 그대로)",
      a1q.get("approach") and not ({"say", "to"} & set(a1q["approach"])), a1q.get("approach"))
fin = walk_until_done(d1, a1, bots1)
check("① 도착 틱: 같은 실행 길(_execute_action)로 판정 — 단검 건넴 · said = 결정 때의 말 · approach_status completed · 저장 사본엔 없다",
      fin and fin.get("result") == "npc_gift" and fin.get("said") == S1 and fin.get("approach_status") == "completed"
      and "said" not in a1["last"], fin)
d1b, bots1b = town()
a1b = bots1b[0]
gm1b = npc(d1b, GEAR)
put(a1b, cells(d1b, gm1b, 6, 12)[0])
act(d1b, a1b, use(gm1b, S1, "npc:" + GEAR), bots1b)
for k_ in G.TALK_FIELDS:
    a1b["approach"].pop(k_, None)                    # 옛 저장의 대기 dict(say 없음)
fin_b = walk_until_done(d1b, a1b, bots1b)
seen = {}
brains._call_claude = lambda p, m="haiku": (seen.__setitem__("p", p), ('{"line": "어서 오게."}', None))[1]
brains.npc_reply(a1b, fin_b, fin_b.get("said"), [], npc=d1b.npc_defs.get(GEAR), names=NAMES)
brains._call_claude = lambda prompt, model="haiku": ""
check("① say 없는 옛 대기 dict 도 도착해 판정된다 · said 없음 → NPC 장면 '말없이 다가와 네 앞에 섰다'",
      fin_b and fin_b.get("result") == "npc_gift" and "said" not in fin_b and "말없이 다가와 네 앞에 섰다" in seen.get("p", ""), fin_b)

print("── ② 말 건 사람의 직전 결과에는 대사가 없다(설계 X10)")
p_gift = brains._last_prose(a1["last"], NAMES)
p_talk = brains._last_prose(a["last"], NAMES)
tags = G.event_tags(a["last"], NAMES)
check("② 선물: '장비 상인에게 말을 걸었다 — 단검을(를) 받아 걸쳤다'(대사 따옴표 없음) · 말만: '장비 상인에게 말을 걸었다'",
      p_gift == "%s에게 말을 걸었다 — 단검을(를) 받아 걸쳤다" % GEAR and p_talk == "%s에게 말을 걸었다" % GEAR
      and gm1.name and d1.npc_lines[GEAR] not in p_gift, (p_gift, p_talk))
check("② 궤적 꼬리표에도 대사가 없다(누구와 말했는지만)", tags and tags[0][2] == GEAR and '"' not in tags[0][2], tags)
dr_, _ = R.build_town(apart=True, walkers=True, quests=dict(G.new_quests(), returned=3))
dr_.composed_actions = dr_.auto_approach = True
dr_.expedition_returned = True
br_ = G.spawn(dr_, "1", [], sheet=dict(SHEETS["1"]))
rec_r = npc(dr_, RECEPTION)
put(br_, cells(dr_, rec_r, 1, 1)[0])
rr_ = act(dr_, br_, use(rec_r), [br_])
p_rep = brains._last_prose(br_["last"], NAMES)
check("② 보고: '길드 접수원에게 원정을 보고했다'(대사 없음)", rr_.get("result") == "npc_report" and p_rep.startswith("%s에게 원정을 보고했다" % RECEPTION)
      and rr_.get("line", "@") not in p_rep, (rr_.get("result"), p_rep))

print("── ③ npc_turn — 보통 대답 · 닫는 말 · 고정 거절")
d3, bots3 = town()
a3 = bots3[0]
st = Brain("그래, 잘 들었네.")
seq = [turn_with(st, d3, a3, GEAR, "말 %d" % i, {"result": "npc_say", "npc": GEAR, "offer": []}) for i in range(5)]
check("③ 같은 쌍 다섯 번: talk·talk·close·busy·busy · 두뇌 3콜(마지막 콜의 res.talk = 'close') · 장부 3에서 멈춘다",
      [s["stage"] for s in seq] == ["talk", "talk", "close", "busy", "busy"] and len(st.calls) == 3
      and [c.get("res", {}).get("talk") for c in st.calls] == [None, None, "close"] and a3["npc_talk"] == {"npc:" + GEAR: 3}, (seq, a3.get("npc_talk")))
check("③ 거절은 0콜 · 정의에 line_busy 가 없으면 공통 문장(G.NPC_LINE_BUSY) · src fixed",
      seq[3]["line"] == seq[4]["line"] == G.NPC_LINE_BUSY and seq[3]["src"] == "fixed")
seen3 = {}
brains._call_claude = lambda p, m="haiku": (seen3.__setitem__("p", p), ('{"line": "이제 그만 가 보게."}', None))[1]
a3b = bots3[1]
a3b["npc_talk"] = {"npc:" + GEAR: G.NPC_REPLY_MAX - 1}
real_close = R.npc_turn(d3, a3b, GEAR, "하나만 더요", {"result": "npc_say", "npc": GEAR, "offer": []}, lambda nm_: [], True, names=NAMES)
brains._call_claude = lambda prompt, model="haiku": ""
check("③ 닫는 말 차례의 NPC 장면에 '이번이 마지막 대답 — 귀찮다는 기색으로 대화를 끝낸다' 한 줄 · 두뇌 문장이 그대로 닫는 말",
      real_close == {"line": "이제 그만 가 보게.", "src": "brain", "stage": "close"} and "이번이 마지막 대답이다" in seen3.get("p", "")
      and "귀찮다는 기색" in seen3.get("p", ""), real_close)
a3c = bots3[2]
fail = [turn_with(Brain(None), d3, a3c, GEAR, "말", {"result": "npc_say", "npc": GEAR, "offer": []}) for _ in range(3)]
check("③ 두뇌 실패: 보통 대답은 말 없음(되받기 옛 규칙) · 닫는 말 차례는 공통 닫는 말(G.NPC_LINE_CLOSE)로 반드시 한 번",
      [f_["line"] for f_ in fail] == [None, None, G.NPC_LINE_CLOSE] and fail[2]["stage"] == "close")
d3o, bots3o = town()
d3o.npc_defs[GEAR] = {**d3o.npc_defs[GEAR], "line_close": "정의의 닫는 말.", "line_busy": "정의의 거절."}
off = [turn_with(Brain("x"), d3o, bots3o[0], GEAR, None, {"result": "npc_talk", "npc": GEAR, "line": "정해진 대사"}, brain_on=False) for _ in range(4)]
check("③ 두뇌가 꺼진 판(use): 정해진 대사·정해진 대사·정의 line_close·정의 line_busy(정의 칸이 공통 문장보다 먼저)",
      [o_["line"] for o_ in off] == ["정해진 대사", "정해진 대사", "정의의 닫는 말.", "정의의 거절."])
check("③ ENT.npc 가 선택 칸 line_close·line_busy 를 낸다(없으면 None — d.npc_defs 에는 실리지 않는다)",
      {"line_close", "line_busy"} <= set(G.ENT.npc("gear_merchant")) and "line_close" not in d3.npc_defs[GEAR])
Q = dict(G.new_quests(), returned=3)
d3r, _ = R.build_town(apart=True, walkers=True, quests=Q)
d3r.composed_actions = d3r.auto_approach = True
d3r.expedition_returned = True
b3r = G.spawn(d3r, "1", [], sheet=dict(SHEETS["1"]))
rec3 = npc(d3r, RECEPTION)
put(b3r, cells(d3r, rec3, 1, 1)[0])
b3r["npc_talk"] = {"npc:" + RECEPTION: G.NPC_REPLY_MAX}  # 이미 상한
rep = act(d3r, b3r, use(rec3, "보고하러 왔어요"), [b3r])
st3 = Brain("y")
got3 = turn_with(st3, d3r, b3r, RECEPTION, rep.pop("said", None), rep)
check("③ 상한 뒤에도 use 의 보고 판정은 그대로 — npc_report · 장부 reported(원정이 끝난다) · 대사는 그 용건의 고정 대사(0콜) · talk busy",
      rep.get("result") == "npc_report" and Q.get("reported") is not None and got3["line"] == rep.get("line") and got3["stage"] == "busy"
      and not st3.calls and rep.get("talk") == "busy", (rep.get("result"), Q.get("reported"), got3))
d3g, bots3g = town()
g3 = bots3g[0]
put(g3, cells(d3g, npc(d3g, GEAR), 1, 1)[0])
g3["npc_talk"] = {"npc:" + GEAR: G.NPC_REPLY_MAX}
gift3 = act(d3g, g3, use(npc(d3g, GEAR), "단검 주세요"), bots3g)
got3g = turn_with(Brain("z"), d3g, g3, GEAR, gift3.pop("said", None), gift3)
check("③ 상한 뒤에도 선물 판정은 그대로(빈손 → 단검) · 대사는 선물의 고정 대사(0콜)",
      gift3.get("result") == "npc_gift" and g3.get("weapon", {}).get("name") == "단검" and got3g["line"] == gift3.get("line") and got3g["src"] == "fixed")

print("── ④ 선물 단일 원천: npc_offer == _interact 판정 · 옛 판정 표 그대로")
bad = []
# 옛 판정(p0.5.9 _interact — D28 빈손일 때만 무기 · D32 개정 같은 방문 두 번째부터 선물 없음 · D95 공물 판 축복은 판당 한 번)을 표로 박는다.
#   미리보기와 판정이 한 함수라 '서로 같다'만으로는 둘이 같이 틀어지는 것(빨간불 M6)을 못 잡는다 — 표가 판정 자체를 묶는다.
OLD = {(RECEPTION, "빈손"): "물약·단검", (RECEPTION, "무장"): "물약", (RECEPTION, "축복 받음"): "물약·단검",
       (GEAR, "빈손"): "단검", (GEAR, "축복 받음"): "단검", (ITEMS, "빈손"): "물약", (ITEMS, "무장"): "물약", (ITEMS, "축복 받음"): "물약",
       (PRIEST, "빈손"): "축복의 물약", (PRIEST, "무장"): "축복의 물약"}   # 나머지 = 선물 없음(npc_talk)
for name in (RECEPTION, GEAR, ITEMS, PRIEST, KEEPER):
    for state in ("빈손", "무장", "만난 뒤", "축복 받음"):
        d4, bots4 = town()
        if state == "축복 받음":
            d4.offer_on = True
        b4 = bots4[0]
        f4 = npc(d4, name)
        put(b4, cells(d4, f4, 1, 1)[0])
        b4["weapon"] = {"id": 990, "name": "롱소드", "bonus": 2, "worn": [b4["char"]]} if state == "무장" else None
        if state == "만난 뒤":
            b4["npc_met"] = {name}
        if state == "축복 받음":
            b4["blessed"] = True
        want = [lbl for _k, lbl in d4.npc_offer(b4, name)]
        got = d4._interact(b4, "f%d" % f4.id, bots4)
        same = (got.get("result") == "npc_gift" and got.get("item") == "·".join(want)) if want else (got.get("result") == "npc_talk")
        old_ = OLD.get((name, state))
        same = same and (got.get("item") == old_ if old_ else got.get("result") == "npc_talk") and (
            state != "무장" or b4["weapon"]["name"] == "롱소드")   # 무장한 사람의 무기는 그대로(덮어쓰지 않는다)
        if not same:
            bad.append((name, state, want, got.get("result"), got.get("item")))
check("④ NPC 다섯(선물 넷 + 선물 없는 주점 주인) × 빈손·무장·만난 뒤·축복 받음(공물 판) — 미리보기 = 실제 판정 = 옛 판정 표 · 무장한 무기는 그대로", not bad, bad)
Qr = dict(G.new_quests(), returned=3)
d4r, _ = R.build_town(apart=True, walkers=True, quests=Qr)
b4r = G.spawn(d4r, "1", [], sheet=dict(SHEETS["1"]))
put(b4r, cells(d4r, npc(d4r, RECEPTION), 1, 1)[0])
pre = d4r.npc_offer(b4r, RECEPTION)
check("④ 귀환 뒤 보고 역할: 미리보기 [('report', '원정 보고')] → 실제 npc_report · 보고 뒤에는 다시 선물/대화",
      pre == [("report", G.NPC_OFFER_REPORT)] and d4r._interact(b4r, "f%d" % npc(d4r, RECEPTION).id, [b4r]).get("result") == "npc_report"
      and d4r.npc_offer(b4r, RECEPTION) != pre, pre)

print("── ⑤ 약속 문제 회귀")
d5, bots5 = town()
a5 = bots5[0]
gm5 = npc(d5, GEAR)
put(a5, cells(d5, gm5, 6, 12)[0])
dec5 = use(gm5, S1, "npc:" + GEAR)
act(d5, a5, dec5, bots5)
t5 = R.npc_say_targets(d5, bots5, {"1": dec5}, {})
check("⑤ 멀리서 'use + 단검 청'(10-13 t139): 말이 접근에 실렸으니 그 틱에 되받지 않는다(도착 때 판정과 함께 한 번) — 0명",
      a5.get("approach", {}).get("say") == S1 and d5.hears(a5, gm5.x, gm5.y) and t5 == [], t5)
a5.pop("approach")
a5["order"], a5["path"] = None, []
t5b = R.npc_say_targets(d5, bots5, {"1": dec5}, {})
check("⑤ 접근이 없으면(use 가 막혔다) 지목한 말은 그대로 되받는다(경로 to)", [(t["npc"], t["via"]) for t in t5b] == [(GEAR, "to")], t5b)
prompts5 = {}
brains._call_claude = lambda p, m="haiku": (prompts5.__setitem__(len(prompts5), p), ('{"line": "그래."}', None))[1]
for lbl_, offer_ in (("빈손", ["단검"]), ("만난 뒤", []), ("보고", [G.NPC_OFFER_REPORT]), ("모름", None)):
    res_ = {"result": "npc_say", "npc": GEAR, **({"offer": offer_} if offer_ is not None else {})}
    brains.npc_reply(a5, res_, S1, ["사실"], npc=d5.npc_defs.get(GEAR), names=NAMES)
brains._call_claude = lambda prompt, model="haiku": ""
p5 = [prompts5[i] for i in sorted(prompts5)]
check("⑤ 되받기 장면 = 와서 말을 걸면 그 자리에서 오갈 것: '단검을(를) 건넨다' / '줄 물건은 없다(대화만)' / '원정 보고를 받는다' / 모름 = '그 자리에서 판정된다'",
      "이 사람이 네 앞에 와서 말을 걸면 그 자리에서: 단검을(를) 건넨다" in p5[0] and "그 자리에서: 줄 물건은 없다(대화만)" in p5[1]
      and "그 자리에서: 원정 보고를 받는다" in p5[2] and "말을 걸 때 그 자리에서 판정된다" in p5[3], [p.split("## 방금 일어난 일")[1][:300] for p in p5])
check("⑤ 옛 장면 문장 '(지금은 아니다)'·'따로 처리된다'는 어디에도 없다 · 모든 NPC 프롬프트에 '나중을 약속하지 않는다' 줄",
      not any("(지금은 아니다)" in p or "따로 처리된다" in p for p in p5) and all("나중을 약속하지 않는다" in p for p in p5)
      and "기다려라·찾아보겠다·곧 들려주겠다" in src("prompts", "npc_prompt.md"))
check("⑤ 실판 장면의 판정: 빈손 모험가에게 장비 상인의 단검은 '실제로 줄 수 있는 물건'이었다(npc_offer · 도착 때 npc_gift 로 건넸다 — ①)",
      [lbl for _k, lbl in town()[0].npc_offer(town()[1][0], GEAR)] == ["단검"] and fin.get("item") == "단검")

print("── ⑥ 방문 경계 · 인사는 세지 않는다")
carry_src = inspect.getsource(R.main)
i0 = carry_src.find("def _carry(")
i1 = carry_src.find("\n    def ", i0 + 10)
body = carry_src[i0:i1]
check("⑥ 새 몸(G.spawn)에는 장부가 없다 · 층 이월(_carry)은 npc_talk 를 옮기지 않는다 = 다음 마을 방문에 풀린다",
      "npc_talk" not in G.spawn(d5, "7", [], sheet=dict(SHEETS["1"])) and i0 > 0 and "npc_talk" not in body and "npc_replies" not in body)
d6, bots6 = town()
a6 = bots6[0]
pr6 = npc(d6, PRIEST)
put(a6, cells(d6, pr6, 2, 4)[0])
hails = d6.npc_greetings(bots6)
hail_src = carry_src[carry_src.find("npc_hails = []"):carry_src.find("inbox_in = inbox")]
check("⑥ NPC 가 먼저 거는 인사는 대화 장부를 세지 않는다(인사 뒤 장부 없음 · 러너의 인사 블록은 npc_turn 을 부르지 않는다)",
      any(h[1] == "1" for h in hails) and "npc_talk" not in a6 and hail_src and "npc_turn" not in hail_src, hails[:2])

print("── ⑦ 저장 판 4 — npc_replies → npc_talk")
snap = {"version": 2, "state_version": 3,
        "bots": [{"char": "1", "npc_replies": {GEAR: 2, PRIEST: 3}}],
        "worlds": [{"bots": [{"char": "2", "npc_replies": {RECEPTION: 1}, "npc_talk": {"npc:" + RECEPTION: 2}}]}],
        "waiting": {"3": {"char": "3", "npc_replies": {}}}}
up = SN.upgrade(json.loads(json.dumps(snap)))
again = SN.upgrade(json.loads(json.dumps(up)))
check("⑦ STATE_VERSION 4 · MIGRATIONS 3 · 몸마다 npc_talk{'npc:'+이름} · 이미 있으면 큰 쪽 · 옛 칸 없음 · 빈 장부는 칸을 만들지 않는다 · 두 번 올려도 같다",
      SN.STATE_VERSION == 4 and 3 in SN.MIGRATIONS and up["state_version"] == 4
      and up["bots"][0] == {"char": "1", "npc_talk": {"npc:" + GEAR: 2, "npc:" + PRIEST: 3}}
      and up["worlds"][0]["bots"][0] == {"char": "2", "npc_talk": {"npc:" + RECEPTION: 2}}
      and up["waiting"]["3"] == {"char": "3"} and again == up, up)

print("── ⑧ 러너 풀런(스텁 — 0콜): 10-13 장비 상인 장면")
NPC_PROMPTS = []
SCRIPT = {"step": 0, "said": []}


def stub_call(prompt, model="haiku"):
    if prompt.lstrip().startswith("# 마을 사람"):
        NPC_PROMPTS.append(prompt)
        return '{"line": "상인의 말 %d"}' % len(NPC_PROMPTS), None
    return "", None


def stub_think(d, bots, inbox, on_error=None):
    """각본 두뇌(판단 대신) — 봇1 만 장비 상인과 말한다(멀리서 use+말 → 도착 → 곁에서 use → 지목(닫는 말) → use(거절) → 지목(거절)). 봇2·3 은 말이 없다."""
    out = {}
    gm_ = next((f for f in d.features.values() if f.type == "npc" and f.name == GEAR), None)
    for b in bots:
        if b.get("order") or not b["alive"] or b["won"] or gm_ is None:
            continue
        d.view(b, bots)                              # 두뇌처럼 먼저 본다(참조표 _target_refs — 조합형 entity() 는 관측에 나온 ID 만 해소한다)
        dec = {"type": "search", "reason": "게이트 각본", "src": "haiku"}
        if b["char"] == "1":
            if SCRIPT["step"] == 0 and not b.get("_npctalk_gate"):
                b["_npctalk_gate"] = True
                b["weapon"] = None                   # 10-13 실판의 봇1 처럼 빈손
            n = R.npc_talk_count(b, GEAR)
            st_ = SCRIPT["step"]
            if n == 0:
                dec = {**use(gm_, S1, "npc:" + GEAR), "say_kind": "제안", "reason": "단검을 청한다"}
            elif n == 1 and st_ < 1:
                SCRIPT["step"], dec = 1, {**use(gm_, "고맙습니다! 하나만 더 여쭤도 될까요?"), "reason": "곁에서 다시"}
            elif n == 2 and st_ < 2:
                SCRIPT["step"], dec = 2, {**dec, "say": "던전 1층엔 뭐가 있나요?", "to": "npc:" + GEAR}
            elif n == 3 and st_ < 3:
                SCRIPT["step"], dec = 3, {**use(gm_, "저기요, 또 여쭤볼게요"), "reason": "또 말을 건다"}
            elif st_ < 4:
                SCRIPT["step"], dec = 4, {**dec, "say": "상인님?", "to": "npc:" + GEAR}
            if dec.get("say"):
                SCRIPT["said"].append((d.turn, dec["say"]))
        out[b["char"]] = dec
    return out


def run(turns="70", think=None):
    st = tempfile.mkdtemp(prefix="run_", dir=ROOT)
    env = {"DUNGEON_BRAIN_BACKEND": "claude_cli"}
    old_env = {k_: os.environ.get(k_) for k_ in env}
    patch = {"NPC_REPLY_ON": True, "NPC_HAIL_ON": False}   # 인사(정지·편지함)는 ⑥ 에서 따로 — 각본의 차례를 흔들지 않게
    old_mod = {k_: getattr(R, k_) for k_ in patch}
    old = (R.STATE, R.MAX_TURNS, R.PAUSE_LIMIT_SEC, brains._call_claude, brains.think_all, brains.social_all)
    os.environ.update(env)
    for k_, v_ in patch.items():
        setattr(R, k_, v_)
    R.STATE, R.MAX_TURNS, R.PAUSE_LIMIT_SEC = st, int(turns), 2
    brains._call_claude, brains.think_all, brains.social_all = stub_call, (think or stub_think), (lambda d, bots, inbox: {})
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                R.main()
            except SystemExit:
                pass
    finally:
        R.STATE, R.MAX_TURNS, R.PAUSE_LIMIT_SEC, brains._call_claude, brains.think_all, brains.social_all = old
        for k_, v_ in old_mod.items():
            setattr(R, k_, v_)
        for k_, v_ in old_env.items():
            if v_ is None:
                os.environ.pop(k_, None)
            else:
                os.environ[k_] = v_
    with open(os.path.join(st, "stream.jsonl"), encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


rows = run()
ticks = [r for r in rows if r["kind"] == "tick"]
by_turn = {r["turn"]: r for r in ticks}
ev1 = [(r["turn"], e) for r in ticks for e in (r.get("events") or []) if str(e.get("char")) == "1"]
talk_ev = [(t, e) for t, e in ev1 if e.get("result") in G.NPC_TALK_RESULTS]
reps = [(r["turn"], x) for r in ticks for x in (r.get("npc_replies") or []) if x.get("char") == "1"]
first = next((t for t, e in ev1 if e.get("type") == "use" and e.get("result") == "approaching"), None)
check("⑧ 봇1 이 멀리서 use + 단검 청 → 접근 시작 · 그 틱(과 걷는 동안) 되받기 없음",
      first is not None and not any(t <= talk_ev[0][0] for t, _ in reps) if talk_ev else False, (first, reps[:2], talk_ev[:1]))
arr = talk_ev[0] if talk_ev else (None, {})
check("⑧ 도착 틱: 단검 건넴(npc_gift) · approach_status completed · 두뇌 문장(line_src brain · 원문은 line_fixed) · 이벤트에 said 없음",
      arr[1].get("result") == "npc_gift" and arr[1].get("item") == "단검" and arr[1].get("approach_status") == "completed"
      and arr[1].get("line_src") == "brain" and arr[1].get("line") == "상인의 말 1" and arr[1].get("line_fixed") and "said" not in arr[1], arr)
p1 = NPC_PROMPTS[0] if NPC_PROMPTS else ""
check("⑧ 도착 때 NPC 장면 = 결정 때의 그 말 + 단검을 건넨 판정(한 번에) — '기다려라'의 재료가 없다",
      ('네게 말을 걸었다: "%s"' % S1) in p1 and "에게 단검을(를) 건넸다" in p1 and "나중을 약속하지 않는다" in p1, p1.split("## 방금 일어난 일")[-1][:400])
nxt = by_turn.get(arr[0] + 1, {}) if arr[0] else {}
got_in = [m for m in ((nxt.get("inbox") or {}).get("1") or []) if m.get("from") == "npc:" + GEAR]
check("⑧ 그 대사는 다음 틱 편지함에 들은 말로(from 'npc:장비 상인' · to 봇1) — 말 건 사람의 직전 결과가 아니라",
      got_in and got_in[0]["text"] == "상인의 말 1" and got_in[0]["to"] == "1" and got_in[0]["turn"] == arr[0], got_in)
stages = [(e.get("result"), e.get("talk"), e.get("line_src")) for _, e in talk_ev]
check("⑧ use 길 셋: 도착(1, 두뇌) · 곁에서 다시(2, 두뇌 · npc_talk again) · 상한 뒤(거절 — talk busy · 공통 거절 문장 · 0콜)",
      len(talk_ev) == 3 and stages[0] == ("npc_gift", None, "brain") and stages[1] == ("npc_talk", None, "brain")
      and stages[2] == ("npc_talk", "busy", None) and talk_ev[2][1].get("line") == G.NPC_LINE_BUSY, stages)
check("⑧ 되받기 길 둘: 지목(3번째 = 닫는 말 talk close · 두뇌) · 상한 뒤 지목(talk busy · 0콜)",
      [(x.get("via"), x.get("talk")) for _, x in reps] == [("to", "close"), ("to", "busy")]
      and reps[0][1]["line"] == "상인의 말 3" and reps[1][1]["line"] == G.NPC_LINE_BUSY, reps)
check("⑧ 두뇌 콜 = 3(세 길이 한 장부 — 도착·곁에서·지목) · 세 번째 장면에 '이번이 마지막 대답' · 첫째·둘째엔 없다",
      len(NPC_PROMPTS) == 3 and "이번이 마지막 대답" in NPC_PROMPTS[2] and not any("이번이 마지막 대답" in p for p in NPC_PROMPTS[:2]), len(NPC_PROMPTS))
check("⑧ 둘째 장면(곁에서 다시) = 그때의 말 · '오늘 이미 만난 사람 — 새로 줄 물건은 없다' / 셋째(지목) = '와서 말을 걸면: 줄 물건은 없다(대화만)'",
      len(NPC_PROMPTS) == 3 and "하나만 더 여쭤도 될까요?" in NPC_PROMPTS[1] and "오늘 이미 만난 사람이다" in NPC_PROMPTS[1]
      and "그 자리에서: 줄 물건은 없다(대화만)" in NPC_PROMPTS[2])
late = []
for t_, line_ in [(t, e["line"]) for t, e in talk_ev] + [(t, x["line"]) for t, x in reps]:
    box = [m for m in (((by_turn.get(t_ + 1) or {}).get("inbox") or {}).get("1") or []) if m.get("text") == line_ and m.get("turn") == t_]
    if not box:
        late.append((t_, line_))
check("⑧ NPC 의 말 다섯(대답 셋·닫는 말·거절 둘 중 말이 있는 것 전부)이 모두 다음 틱 편지함에 들은 말로 왔다", not late and len(talk_ev) + len(reps) == 5, late)
check("⑧ 스트림 어디에도 said 칸이 없다(러너 전용 칸 — 결정 틱의 decisions.say 에 이미 있다)",
      not any("said" in e for r in ticks for e in (r.get("events") or [])), [e for r in ticks for e in (r.get("events") or []) if "said" in e][:1])

print("── ⑩ 거절은 NPC 두뇌 차례와 따로(p0510b — Codex p0510r 필수 ①)")
d10, bots10 = town()
a10, b10, c10 = bots10
gm10 = npc(d10, GEAR)
spots = cells(d10, gm10, 1, 3)
for b_, xy_ in zip(bots10, spots[:3]):
    put(b_, xy_)
to_gm = lambda s_: {"type": "search", "say": s_, "to": "npc:" + GEAR, "src": "haiku"}   # noqa: E731


def order(first_over):
    """둘이 같은 틱에 같은 NPC 를 지목 — 한 사람은 상한 도달. first_over = 앞 번호(봇1)가 상한 도달자."""
    a10["npc_talk"] = {"npc:" + GEAR: G.NPC_REPLY_MAX} if first_over else {}
    b10["npc_talk"] = {} if first_over else {"npc:" + GEAR: G.NPC_REPLY_MAX}
    st_ = Brain("대답")
    old_ = brains.npc_reply
    brains.npc_reply = st_
    try:
        out_ = R.npc_say_replies(d10, bots10, {"1": to_gm("저기요"), "2": to_gm("저도요")}, {}, lambda nm_: [])
    finally:
        brains.npc_reply = old_
    return [(o_["char"], o_.get("talk")) for o_ in out_], len(st_.calls)


o_n, c_n = order(first_over=False)
o_o, c_o = order(first_over=True)
check("⑩ 정상 응답자가 먼저(봇1 보통 · 봇2 상한): 봇1 대답(두뇌 1콜) + 봇2 고정 거절 — 거절이 사라지지 않는다",
      o_n == [("1", None), ("2", "busy")] and c_n == 1, (o_n, c_n))
check("⑩ 상한 도달자가 먼저(봇1 상한 · 봇2 보통): 봇1 고정 거절 + 봇2 대답(두뇌 1콜) — 순서와 상관없이 같은 결과",
      o_o == [("1", "busy"), ("2", None)] and c_o == 1, (o_o, c_o))
a10["npc_talk"], b10["npc_talk"] = {"npc:" + GEAR: G.NPC_REPLY_MAX}, {}
st10 = Brain("대답")
old10 = brains.npc_reply
brains.npc_reply = st10
try:
    o_u = R.npc_say_replies(d10, bots10, {"1": to_gm("저기요"), "2": to_gm("저도요")}, {}, lambda nm_: [],
                            spoke={GEAR}, pairs={("3", GEAR)})          # 봇3 이 이 틱에 use 로 장비 상인과 말했다(두뇌 차례를 썼다)
    o_p = R.npc_say_replies(d10, bots10, {"1": to_gm("저기요")}, {}, lambda nm_: [], spoke={GEAR}, pairs={("1", GEAR)})
finally:
    brains.npc_reply = old10
check("⑩ 다른 사람의 use 와 같은 틱: 상한 도달자(봇1)는 거절을 받고 · 보통(봇2)은 NPC 차례가 없어 말 없음(0콜, 장부 그대로)",
      [(o_["char"], o_.get("talk")) for o_ in o_u] == [("1", "busy")] and not st10.calls and "npc:" + GEAR not in (b10.get("npc_talk") or {}), o_u)
check("⑩ 같은 쌍은 한 틱에 한 번: 이 틱 use 길로 이미 처리된 쌍(봇1)의 지목은 다시 거절하지 않는다", o_p == [], o_p)
SCRIPT2 = {"step": 0, "turns": []}


def stub_think2(d, bots, inbox, on_error=None):
    """러너 풀런 각본 — 세 사람이 장비 상인 곁에서 같은 틱에 말한다(봇2 는 상한 도달로 시작).
    0: 봇1 use(두뇌 차례) · 봇2 지목(거절) · 봇3 지목(보통 — 차례 없음) / 1: 봇2 지목(거절) · 봇3 지목(대답) — 상한 도달자가 앞 번호 /
    2: 봇1 지목(대답) · 봇2 지목(거절) — 정상 응답자가 앞 번호 / 그 뒤: 말 없음."""
    gm_ = next(f for f in d.features.values() if f.type == "npc" and f.name == GEAR)
    live = [b for b in bots if not b.get("order") and b["alive"] and not b["won"]]
    if not live:
        return {}
    k = SCRIPT2["step"]
    if k == 0:
        taken_, near_ = set(), cells(d, gm_, 1, 1)
        for b_ in bots:                                  # 각본: 셋을 장비 상인 곁(같은 구역)에 세운다 — 봇1 은 바로 곁(즉시 use)
            xy_ = near_[0] if b_["char"] == "1" else [c for c in cells(d, gm_, 2, 4) if c not in taken_][0]
            taken_.add(xy_)
            put(b_, xy_)
            b_["order"], b_["path"] = None, []
        next(b_ for b_ in bots if b_["char"] == "2")["npc_talk"] = {"npc:" + GEAR: G.NPC_REPLY_MAX}
    SCRIPT2["step"] += 1
    SCRIPT2["turns"].append(d.turn)
    plan = {0: {"1": use(gm_, "안녕하세요"), "2": to_gm("저기요"), "3": to_gm("물건 좀 볼게요")},
            1: {"2": to_gm("저기요"), "3": to_gm("물건 좀 볼게요")},
            2: {"1": to_gm("하나 더요"), "2": to_gm("저기요")}}.get(k, {})
    out = {}
    for b_ in live:
        d.view(b_, bots)
        out[b_["char"]] = {**{"type": "search", "reason": "각본", "src": "haiku"}, **plan.get(b_["char"], {})}
    return out


NPC_PROMPTS[:] = []
rows2 = run(turns="8", think=stub_think2)
ticks2 = {r["turn"]: r for r in rows2 if r["kind"] == "tick"}
t0, t1, t2 = (SCRIPT2["turns"] + [None, None, None])[:3]
rp = lambda t_: [(x["char"], x.get("talk")) for x in ((ticks2.get(t_) or {}).get("npc_replies") or []) if x["npc"] == GEAR]   # noqa: E731
use0 = [e for e in ((ticks2.get(t0) or {}).get("events") or []) if str(e.get("char")) == "1" and e.get("result") in G.NPC_TALK_RESULTS]
check("⑩ 러너 풀런 · 다른 사람의 use 와 같은 틱: 봇1 use(두뇌) · 봇2 거절 · 봇3 은 말 없음",
      use0 and use0[0].get("line_src") == "brain" and rp(t0) == [("2", "busy")], (use0[:1], rp(t0)))
check("⑩ 러너 풀런 · 상한 도달자가 앞 번호: 봇2 거절 + 봇3 대답 / 정상 응답자가 앞 번호: 봇1 대답 + 봇2 거절",
      rp(t1) == [("2", "busy"), ("3", None)] and rp(t2) == [("1", None), ("2", "busy")], (rp(t1), rp(t2)))
check("⑩ 러너 풀런 · 두뇌 콜 3(틱마다 NPC 한 콜 — 거절은 0콜)", len(NPC_PROMPTS) == 3, len(NPC_PROMPTS))
check("⑩ 배선: 러너가 use 길의 단계로 두뇌 차례(spoke)·쌍(pairs)을 나눠 넘긴다",
      'spoke={n_ for n_, _c, st_ in npc_used if st_ != "busy"}' in src("show_runner.py")
      and "pairs={(c_, n_) for n_, c_, _st in npc_used}" in src("show_runner.py"))

print("── ⑪ 고정 대사 경로의 약속(p0510b — Codex p0510r 필수 ②)")
# NPC 가 자기 나중 행동을 약속하는 꼴(실판·리뷰에서 나온 꼴 + 같은 결). 상대에게 하는 권유('또 들르세요'·'게시판도 봐 주세요')는 약속이 아니다.
PROMISE = ("곧 열", "들여오는 중", "다음에 꼭", "또 하나 주지", "드릴게", "줄게", "챙겨 드릴", "또 봬요", "기다려", "찾아볼", "찾아 올",
           "나중에", "곧 들려", "골라 줄", "가져다", "가져올게")
fixed, hits = [], []
for e_ in sorted(x["id"] for x in G.ENT.by_kind("npc")):
    for life_ in (False, True):
        nd_ = G.ENT.npc(e_, life=life_)
        for k_, v_ in nd_.items():
            if isinstance(v_, str) and (k_.startswith("line") or k_.startswith("hail")):
                fixed.append((e_, life_, k_, v_))
fixed += [("OFFER_LINES", True, k_, v_) for k_, v_ in R.OFFER_LINES.items()]
fixed += [("엔진", None, "NPC_LINE_CLOSE", G.NPC_LINE_CLOSE), ("엔진", None, "NPC_LINE_BUSY", G.NPC_LINE_BUSY)]
for e_, life_, k_, v_ in fixed:
    if any(p_ in v_ for p_ in PROMISE):
        hits.append((e_, life_, k_, v_))
check("⑪ NPC 15명 고정 대사 전부(끈 판·마을 생활 판 · 대사·재방문·인사·보고) + 공물 판 대사 + 공통 닫는 말·거절에 나중 약속 꼴이 없다(%d칸)" % len(fixed),
      len(fixed) > 60 and not hits, hits)
NEW_LINES = {("gear_merchant", "line_again"): "아까 왔잖아. 이미 무장했으니 줄 건 없어 — 오늘 있는 건 이게 다야.",
             ("innkeeper", "line"): "빈 방은 많은데 아직 손님 받을 준비가 안 됐어.", ("innkeeper", "line_again"): "아까 왔잖아. 아직 준비가 안 됐다니까.",
             ("tavern_keeper", "line_again"): "아까 왔잖아. 아직 준비 중이라니까.", ("street_vendor", "line_again"): "아까 봤죠? 사고파는 건 아직이에요.",
             ("apprentice_adventurer", "line_again"): "저는 아직 심사가 안 끝나서 파티를 못 구해요.",
             ("item_merchant", "line_again"): "아까 왔잖아. 이번 원정 몫은 이미 줬어 — 물약은 한 원정에 한 병이야.",
             ("guild_receptionist", "line_again"): "아까 왔잖아요. 이번 원정 몫은 이미 드렸어요 — 원정 물품은 한 원정에 한 번이에요.",
             ("temple_attendant", "line_again"): "오늘 기도는 이미 드렸어요. 축복은 한 원정에 한 병이에요."}
check("⑪ 바꾼 9칸이 엔진까지 그 문장(말 파일 → 정의 합치기)", all(G.ENT.npc(e_)[k_] == v_ for (e_, k_), v_ in NEW_LINES.items()),
      [(e_, k_, G.ENT.npc(e_)[k_]) for (e_, k_) in NEW_LINES if G.ENT.npc(e_)[k_] != NEW_LINES[(e_, k_)]])
d11, bots11 = town()
a11 = bots11[0]
gm11 = npc(d11, GEAR)
put(a11, cells(d11, gm11, 1, 1)[0])
first11 = act(d11, a11, use(gm11), bots11)
second11 = act(d11, a11, use(gm11, "다른 건 없어요?"), bots11)
got_off = R.npc_turn(d11, a11, GEAR, second11.pop("said", None), dict(second11), lambda nm_: [], False)
a11["npc_talk"] = {"npc:" + GEAR: 1}
got_fail = turn_with(Brain(None), d11, a11, GEAR, "다른 건 없어요?", dict(second11))
seen11 = {}
brains._call_claude = lambda p, m="haiku": (seen11.__setitem__("p", p), ('{"line": "그게 다야."}', None))[1]
brains.npc_reply(a11, dict(second11), "다른 건 없어요?", [], npc=d11.npc_defs.get(GEAR), names=NAMES)
brains._call_claude = lambda prompt, model="haiku": ""
check("⑪ 리뷰 재현 경로: 장비 상인 두 번째 use — 두뇌 꺼짐·실패 모두 들은 말 = 새 재방문 대사(약속 없음) · 두뇌에 주는 '정해진 대사' 힌트에도 없다",
      first11.get("result") == "npc_gift" and second11.get("result") == "npc_talk"
      and got_off["line"] == got_fail["line"] == NEW_LINES[("gear_merchant", "line_again")]
      and "들여오는 중" not in seen11.get("p", "") and NEW_LINES[("gear_merchant", "line_again")] in seen11.get("p", ""), (got_off, got_fail))

print("── ⑨ 배선")
rs = src("show_runner.py")
check("⑨ 러너: NPC 블록이 두 가지(자동보행·즉시 실행) 뒤 공통 자리 — res.pop('said') → npc_turn · 옛 dec.get('say') 직접 읽기 없음",
      'said_ = res.pop("said", None)' in rs and "got_ = npc_turn(d, b, res[\"npc\"], said_, res," in rs
      and 'brains.npc_reply(b, res, dec.get("say")' not in rs)
check("⑨ 관측 안내의 '…번까지다' 꼬리 삭제 · 엔진 상수(MAX 3 · 닫는 말·거절 공통 문장)",
      "한 사람이 되받는 말은 네가" not in src("brains.py") and G.NPC_REPLY_MAX == 3 and G.NPC_LINE_CLOSE and G.NPC_LINE_BUSY)

print("=" * 44)
if C.failed:
    print("RESULT: %d FAIL" % C.failed)
    raise SystemExit(1)
print("ALL PASS — verify_npc_talk (p0.5.10 신원 ID-2 NPC 대화 한 길: 세 길 한 장부 · 닫는 말 한 번 · 고정 거절 0콜 · 방문마다 풀림 · use 판정 유지 · 약속 문제, %d checks, 실 LLM 0콜)" % C.n)

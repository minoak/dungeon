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
  ⑫ (p0.5.14 등 돌리기 · DECISIONS 2026-10-15) 닫는 말 뒤의 고정 거절('지금은 바쁘네.' — 0.5.13 실판 53회, '나중엔 된다'로 읽혀 기다리기 루프)을 등 돌림으로:
     등 돌린 쌍의 use = 대사 없는 결과 사실(직전 결과·꼬리표) · 0콜 · 다른 사람은 보통 · 목격 없음 · 관측 NPC 줄 꼬리(그 사람만, 풀리는 때 없음) ·
     지목한 말 = 되받은 말 없음 + 궤적 사실 한 칸 · reply 읽기 없음 · 200틱 쌍별 풀림(장부 다시) · 원정(새 몸) 풀림 · 인사 중단 · 가게 거래 유지 ·
     저장 판 6→7 이관·이어가기 · 정보 보호(SPECTATOR_KEYS) · NPC 두뇌 대사의 '다시 와라·기다려라' 0콜 걸러내기(실판 문장) · 러너 풀런(진입→등 돌림→풀림→다시)
(기존 게이트는 별도 실행.)
"""
import contextlib
import functools
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
# p0.5.13(경제 1a, DECISIONS 10-14 §10-6): 상인 둘의 선물(D32 — 장비 상인 단검·아이템 상인 물약)은 판매로 바뀌어 정의에서 걷혔다(지금 정의의 '선물 없음'은
#   verify_shop ⑨). 이 게이트는 10-13 실판 장면(빈손 모험가에게 장비 상인이 단검을 줬다)을 재연해 대화 한 길·선물 단일 원천·약속 문제의 **기계**를 보므로,
#   그 판의 선물을 이 게이트가 짓는 모든 마을(R.main 의 마을 포함)에 주입한다 — 판정 기계는 접수원·성직자가 그대로 쓰는 것과 같다.
D32_GIFTS = {GEAR: {"weapon": "단검"}, ITEMS: {"potions": 1}}
_build_town_now = R.build_town


@functools.wraps(_build_town_now)                    # 러너(town_for_run)가 시그니처를 본다 — wraps 가 원래 인자를 보인다
def _build_town_1013(*a, **k):
    d_, st_ = _build_town_now(*a, **k)
    for nm_, g_ in D32_GIFTS.items():
        if any(f.type == "npc" and f.name == nm_ for f in d_.features.values()):
            d_.npc_gifts.setdefault(nm_, dict(g_))
    return d_, st_


R.build_town = _build_town_1013


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

print("── ③ npc_turn — 보통 대답 · 닫는 말 · 등 돌림(p0.5.14 — 옛 고정 거절 자리)")
d3, bots3 = town()
a3 = bots3[0]
st = Brain("그래, 잘 들었네.")
seq = [turn_with(st, d3, a3, GEAR, "말 %d" % i, {"result": "npc_say", "npc": GEAR, "offer": []}) for i in range(5)]
check("③ 같은 쌍 다섯 번: talk·talk·close·away·away · 두뇌 3콜(마지막 콜의 res.talk = 'close') · 장부 3에서 멈춘다 · 닫는 말 틱부터 등 돌림(npc_away)",
      [s["stage"] for s in seq] == ["talk", "talk", "close", "away", "away"] and len(st.calls) == 3
      and [c.get("res", {}).get("talk") for c in st.calls] == [None, None, "close"] and a3["npc_talk"] == {"npc:" + GEAR: 3}
      and a3.get("npc_away") == {"npc:" + GEAR: d3.turn}, (seq, a3.get("npc_talk"), a3.get("npc_away")))
check("③ 등 돌림은 0콜 · 대사 없음(line None — 옛 고정 거절 문장 G.NPC_LINE_BUSY 는 거뒀다) · src fixed",
      seq[3]["line"] is None and seq[4]["line"] is None and seq[3]["src"] == "fixed" and not hasattr(G, "NPC_LINE_BUSY"))
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
d3o.npc_defs[GEAR] = {**d3o.npc_defs[GEAR], "line_close": "정의의 닫는 말."}
res3o = [{"result": "npc_talk", "npc": GEAR, "line": "정해진 대사"} for _ in range(4)]
off = [turn_with(Brain("x"), d3o, bots3o[0], GEAR, None, r_, brain_on=False) for r_ in res3o]
check("③ 두뇌가 꺼진 판(use): 정해진 대사·정해진 대사·정의 line_close(정의 칸이 공통 문장보다 먼저)·등 돌림(대사 없음 — res 의 line 을 걷고 talk away)",
      [o_["line"] for o_ in off] == ["정해진 대사", "정해진 대사", "정의의 닫는 말.", None]
      and "line" not in res3o[3] and res3o[3].get("talk") == "away" and res3o[2].get("talk") == "close", [o_["line"] for o_ in off])
check("③ ENT.npc 가 선택 칸 line_close 를 낸다(없으면 None — d.npc_defs 에는 실리지 않는다) · p0.5.14 고정 거절 칸 line_busy 는 거뒀다(정의·말 파일 설명)",
      "line_close" in set(G.ENT.npc("gear_merchant")) and "line_busy" not in set(G.ENT.npc("gear_merchant")) and "line_close" not in d3.npc_defs[GEAR]
      and "line_busy" not in src("words.py"))
Q = dict(G.new_quests(), returned=3)
d3r, _ = R.build_town(apart=True, walkers=True, quests=Q)
d3r.composed_actions = d3r.auto_approach = True
d3r.expedition_returned = True
b3r = G.spawn(d3r, "1", [], sheet=dict(SHEETS["1"]))
rec3 = npc(d3r, RECEPTION)
put(b3r, cells(d3r, rec3, 1, 1)[0])
b3r["npc_talk"] = {"npc:" + RECEPTION: G.NPC_REPLY_MAX}  # 이미 상한 — 닫는 말을 한 쌍(p0.5.14 등 돌림 표식과 함께)
b3r["npc_away"] = {"npc:" + RECEPTION: 1}
rep = act(d3r, b3r, use(rec3, "보고하러 왔어요"), [b3r])
st3 = Brain("y")
got3 = turn_with(st3, d3r, b3r, RECEPTION, rep.pop("said", None), rep)
check("③ 등 돌린 뒤에도 use 의 보고 판정은 그대로 — npc_report · 장부 reported(원정이 끝난다) · 대사 없음(엔진이 line 을 걷었다 · 0콜) · talk away",
      rep.get("result") == "npc_report" and Q.get("reported") is not None and got3["line"] is None and got3["stage"] == "away"
      and not st3.calls and rep.get("talk") == "away" and "line" not in rep and b3r["last"].get("talk") == "away", (rep, Q.get("reported"), got3))
d3g, bots3g = town()
g3 = bots3g[0]
put(g3, cells(d3g, npc(d3g, GEAR), 1, 1)[0])
g3["npc_talk"] = {"npc:" + GEAR: G.NPC_REPLY_MAX}
g3["npc_away"] = {"npc:" + GEAR: 1}
gift3 = act(d3g, g3, use(npc(d3g, GEAR), "단검 주세요"), bots3g)
got3g = turn_with(Brain("z"), d3g, g3, GEAR, gift3.pop("said", None), gift3)
check("③ 등 돌린 뒤에도 선물 판정은 그대로(빈손 → 단검) · 대사 없음(0콜) · 직전 결과 = 받은 것 + 결과 사실",
      gift3.get("result") == "npc_gift" and g3.get("weapon", {}).get("name") == "단검" and got3g["line"] is None and got3g["src"] == "fixed"
      and "line" not in gift3 and brains._last_prose(g3["last"], NAMES) == "%s에게 말을 걸었다 — 단검을(를) 받아 걸쳤다 — %s" % (GEAR, G.NPC_AWAY_FACT),
      (gift3, brains._last_prose(g3["last"], NAMES)))
d3h, bots3h = town()
h3 = bots3h[0]
put(h3, cells(d3h, npc(d3h, KEEPER), 1, 1)[0])
h3["npc_talk"] = {"npc:" + KEEPER: G.NPC_REPLY_MAX}  # 상한인데 표식이 없는 몸(저장 판 6 이하에서 이관 없이 들어온 꼴 — 이관은 ⑫)
r3h = {"result": "npc_talk", "npc": KEEPER, "line": "어서 와."}
got3h = turn_with(Brain("w"), d3h, h3, KEEPER, None, r3h)
check("③ 장부가 상한인데 등 돌림 표식이 없는 몸 → 그 차례부터 등 돌림(표식 = 그 틱) · 대사 걷음 · 0콜",
      got3h["stage"] == "away" and got3h["line"] is None and h3.get("npc_away") == {"npc:" + KEEPER: d3h.turn} and "line" not in r3h, (got3h, h3.get("npc_away")))

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
NEED9 = {"needs": {nid: sp["start"] for nid, sp in G.NE.live()}, "moods": [], "rations": 0}   # p0.5.16 8→9 이관: 욕구 시작값·빈 기분 조각·휴대식 0
check("⑦ STATE_VERSION ≥ 4(p0.5.11 = 5) · MIGRATIONS 3 · 몸마다 npc_talk{'npc:'+이름} · 이미 있으면 큰 쪽 · 옛 칸 없음 · 빈 장부는 칸을 만들지 않는다 · 두 번 올려도 같다",
      SN.STATE_VERSION >= 4 and 3 in SN.MIGRATIONS and up["state_version"] == SN.STATE_VERSION
      and up["bots"][0] == {"char": "1", "npc_talk": {"npc:" + GEAR: 2, "npc:" + PRIEST: 3}, "gold": G.START_GOLD,   # gold = p0.5.13 5→6 이관(시작 지갑)
                            "npc_away": {"npc:" + PRIEST: 0}, **NEED9}   # p0.5.14 6→7: 상한(3)인 쌍은 등 돌림(이어간 틱 = next_turn - 1 — 이 자료엔 next_turn 이 없어 0)
      and up["worlds"][0]["bots"][0] == {"char": "2", "npc_talk": {"npc:" + RECEPTION: 2}, "gold": G.START_GOLD, **NEED9}
      and up["waiting"]["3"] == {"char": "3", "gold": G.START_GOLD, **NEED9} and again == up, up)

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


def run(turns="70", think=None, st=None, resume=False):
    """러너 풀런(스텁). st·resume = p0514b 이어가기 시험 — 같은 state 폴더에서 그 스냅샷으로 이어 돈다(RESUME_PATH)."""
    st = st or tempfile.mkdtemp(prefix="run_", dir=ROOT)
    env = {"DUNGEON_BRAIN_BACKEND": "claude_cli"}
    old_env = {k_: os.environ.get(k_) for k_ in env}
    patch = {"NPC_REPLY_ON": True, "NPC_HAIL_ON": False,   # 인사(정지·편지함)는 ⑥ 에서 따로 — 각본의 차례를 흔들지 않게
             "RESUME_PATH": os.path.join(st, SN.PKL) if resume else ""}
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
    LAST_RUN["dir"] = st                             # p0.5.14: events.log(등 돌림 줄)를 읽는 검사용
    with open(os.path.join(st, "stream.jsonl"), encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


LAST_RUN = {"dir": None}


def run_events():
    """마지막 run() 의 events.log 줄들."""
    p = os.path.join(LAST_RUN["dir"] or "", "events.log")
    if not os.path.isfile(p):
        return []
    with open(p, encoding="utf-8") as f:
        return f.read().splitlines()


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
check("⑧ use 길 셋: 도착(1, 두뇌) · 곁에서 다시(2, 두뇌 · npc_talk again) · 닫는 말 뒤(p0.5.14 등 돌림 — talk away · line 칸 없음 · 0콜)",
      len(talk_ev) == 3 and stages[0] == ("npc_gift", None, "brain") and stages[1] == ("npc_talk", None, "brain")
      and stages[2] == ("npc_talk", "away", None) and "line" not in talk_ev[2][1], stages)
check("⑧ 되받기 길: 지목(3번째 = 닫는 말 talk close · 두뇌) 하나뿐 — 등 돌린 뒤 지목은 되받은 말(npc_replies)에 없다(말풍선 없음 · 0콜)",
      [(x.get("via"), x.get("talk")) for _, x in reps] == [("to", "close")] and reps[0][1]["line"] == "상인의 말 3"
      and len(SCRIPT["said"]) == 5, (reps, SCRIPT["said"]))
aw8 = [(r["turn"], e) for r in ticks for e in (r.get("npc_away") or [])]
check("⑧ 스트림 tick.npc_away: 닫는 말 틱에 start 한 줄({npc, char, ev}) · 70틱 판이라 풀림(end)은 없다(200틱)",
      [(t_, e) for t_, e in aw8] == [(reps[0][0], {"npc": GEAR, "char": "1", "ev": "start"})] if reps else False, aw8)
check("⑧ 두뇌 콜 = 3(세 길이 한 장부 — 도착·곁에서·지목) · 세 번째 장면에 '이번이 마지막 대답' · 첫째·둘째엔 없다",
      len(NPC_PROMPTS) == 3 and "이번이 마지막 대답" in NPC_PROMPTS[2] and not any("이번이 마지막 대답" in p for p in NPC_PROMPTS[:2]), len(NPC_PROMPTS))
check("⑧ 둘째 장면(곁에서 다시) = 그때의 말 · '오늘 이미 만난 사람 — 새로 줄 물건은 없다' / 셋째(지목) = '와서 말을 걸면: 줄 물건은 없다(대화만)'",
      len(NPC_PROMPTS) == 3 and "하나만 더 여쭤도 될까요?" in NPC_PROMPTS[1] and "오늘 이미 만난 사람이다" in NPC_PROMPTS[1]
      and "그 자리에서: 줄 물건은 없다(대화만)" in NPC_PROMPTS[2])
late = []
spoken8 = [(t, e["line"]) for t, e in talk_ev if e.get("line")] + [(t, x["line"]) for t, x in reps]
for t_, line_ in spoken8:
    box = [m for m in (((by_turn.get(t_ + 1) or {}).get("inbox") or {}).get("1") or []) if m.get("text") == line_ and m.get("turn") == t_]
    if not box:
        late.append((t_, line_))
quiet8 = [r["turn"] for r in ticks if r["turn"] > (reps[0][0] if reps else 10 ** 6)
          and any(str(m.get("from")) == "npc:" + GEAR for m in ((r.get("inbox") or {}).get("1") or []) if m.get("turn", 0) > reps[0][0])]
check("⑧ NPC 의 말 셋(대답 둘·닫는 말)이 모두 다음 틱 편지함에 들은 말로 왔다 · 등 돌린 뒤 장비 상인의 말은 한 줄도 없다(use·지목 모두)",
      not late and len(spoken8) == 3 and not quiet8, (late, spoken8, quiet8))
check("⑧ 스트림 어디에도 said 칸이 없다(러너 전용 칸 — 결정 틱의 decisions.say 에 이미 있다)",
      not any("said" in e for r in ticks for e in (r.get("events") or [])), [e for r in ticks for e in (r.get("events") or []) if "said" in e][:1])

print("── ⑩ 등 돌림(옛 거절)은 NPC 두뇌 차례와 따로(p0510b — Codex p0510r 필수 ① · p0.5.14 거절 → 등 돌림)")
d10, bots10 = town()
a10, b10, c10 = bots10
gm10 = npc(d10, GEAR)
spots = cells(d10, gm10, 1, 3)
for b_, xy_ in zip(bots10, spots[:3]):
    put(b_, xy_)
to_gm = lambda s_: {"type": "search", "say": s_, "to": "npc:" + GEAR, "src": "haiku"}   # noqa: E731


def turned(b_, name=GEAR):
    """닫는 말을 한 쌍의 몸(장부 상한 + p0.5.14 등 돌림 표식)."""
    b_["npc_talk"] = {"npc:" + name: G.NPC_REPLY_MAX}
    b_["npc_away"] = {"npc:" + name: 1}


def plain(b_):
    b_["npc_talk"] = {}
    b_.pop("npc_away", None)


def order(first_over):
    """둘이 같은 틱에 같은 NPC 를 지목 — 한 사람은 등 돌린 쌍. first_over = 앞 번호(봇1)가 등 돌린 쪽."""
    (turned if first_over else plain)(a10)
    (plain if first_over else turned)(b10)
    st_, aw_ = Brain("대답"), []
    old_ = brains.npc_reply
    brains.npc_reply = st_
    try:
        out_ = R.npc_say_replies(d10, bots10, {"1": to_gm("저기요"), "2": to_gm("저도요")}, {}, lambda nm_: [], away=aw_)
    finally:
        brains.npc_reply = old_
    return [(o_["char"], o_.get("talk")) for o_ in out_], len(st_.calls), [(b_["char"], n_) for b_, n_ in aw_]


o_n, c_n, w_n = order(first_over=False)
o_o, c_o, w_o = order(first_over=True)
check("⑩ 정상 응답자가 먼저(봇1 보통 · 봇2 등 돌림): 봇1 대답(두뇌 1콜) + 봇2 등 돌림(말 없음 — away 목록) — 등 돌림이 빠지지 않는다",
      o_n == [("1", None)] and c_n == 1 and w_n == [("2", GEAR)], (o_n, c_n, w_n))
check("⑩ 등 돌린 쪽이 먼저(봇1 등 돌림 · 봇2 보통): 봇1 등 돌림 + 봇2 대답(두뇌 1콜) — 순서와 상관없이 같은 결과",
      o_o == [("2", None)] and c_o == 1 and w_o == [("1", GEAR)], (o_o, c_o, w_o))
turned(a10)
plain(b10)
st10, aw10, aw10p = Brain("대답"), [], []
old10 = brains.npc_reply
brains.npc_reply = st10
try:
    o_u = R.npc_say_replies(d10, bots10, {"1": to_gm("저기요"), "2": to_gm("저도요")}, {}, lambda nm_: [],
                            spoke={GEAR}, pairs={("3", GEAR)}, away=aw10)   # 봇3 이 이 틱에 use 로 장비 상인과 말했다(두뇌 차례를 썼다)
    o_p = R.npc_say_replies(d10, bots10, {"1": to_gm("저기요")}, {}, lambda nm_: [], spoke={GEAR}, pairs={("1", GEAR)}, away=aw10p)
finally:
    brains.npc_reply = old10
check("⑩ 다른 사람의 use 와 같은 틱: 등 돌린 쌍(봇1)은 등 돌림 · 보통(봇2)은 NPC 차례가 없어 말 없음(0콜, 장부 그대로)",
      o_u == [] and [(b_["char"], n_) for b_, n_ in aw10] == [("1", GEAR)] and not st10.calls and "npc:" + GEAR not in (b10.get("npc_talk") or {}), (o_u, aw10))
check("⑩ 같은 쌍은 한 틱에 한 번: 이 틱 use 길로 이미 처리된 쌍(봇1)의 지목은 다시 다루지 않는다", o_p == [] and aw10p == [], (o_p, aw10p))
SCRIPT2 = {"step": 0, "turns": []}


def stub_think2(d, bots, inbox, on_error=None):
    """러너 풀런 각본 — 세 사람이 장비 상인 곁에서 같은 틱에 말한다(봇2 는 등 돌린 쌍으로 시작 — p0.5.14 옛 '상한 도달').
    0: 봇1 use(두뇌 차례) · 봇2 지목(등 돌림) · 봇3 지목(보통 — 차례 없음) / 1: 봇2 지목(등 돌림) · 봇3 지목(대답) — 등 돌린 쪽이 앞 번호 /
    2: 봇1 지목(대답) · 봇2 지목(등 돌림) — 정상 응답자가 앞 번호 / 그 뒤: 말 없음."""
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
        turned(next(b_ for b_ in bots if b_["char"] == "2"))
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
ev10 = run_events()
tick_at = {}                                         # 틱 머리 줄 → 그 틱의 줄들(events.log 는 틱마다 '-- tick N --' 머리로 시작)
cur_t = None
for ln in ev10:
    if ln.startswith("-- tick "):
        try:
            cur_t = int(ln.split()[2])
        except (IndexError, ValueError):
            cur_t = None
    if cur_t is not None:
        tick_at.setdefault(cur_t, []).append(ln)
away_log = lambda t_: [ln for ln in tick_at.get(t_, []) if "%s → 봇" % GEAR in ln and "등 돌림(대사 없음)" in ln]   # noqa: E731
check("⑩ 러너 풀런 · 다른 사람의 use 와 같은 틱: 봇1 use(두뇌) · 봇2 등 돌림(되받은 말 없음 · 로그 한 줄) · 봇3 은 말 없음",
      use0 and use0[0].get("line_src") == "brain" and rp(t0) == [] and len(away_log(t0)) == 1 and "봇2" in away_log(t0)[0], (use0[:1], rp(t0), away_log(t0)))
check("⑩ 러너 풀런 · 등 돌린 쪽이 앞 번호: 봇2 등 돌림 + 봇3 대답 / 정상 응답자가 앞 번호: 봇1 대답 + 봇2 등 돌림",
      rp(t1) == [("3", None)] and rp(t2) == [("1", None)] and len(away_log(t1)) == 1 and len(away_log(t2)) == 1, (rp(t1), rp(t2), away_log(t1), away_log(t2)))
check("⑩ 러너 풀런 · 두뇌 콜 3(틱마다 NPC 한 콜 — 등 돌림은 0콜)", len(NPC_PROMPTS) == 3, len(NPC_PROMPTS))
check("⑩ 배선: 러너가 use 길의 단계로 두뇌 차례(spoke)·쌍(pairs)을 나눠 넘긴다 · 등 돌린 지목 목록(away)",
      'spoke={n_ for n_, _c, st_ in npc_used if st_ != "away"}' in src("show_runner.py")
      and "pairs={(c_, n_) for n_, c_, _st in npc_used}, away=away_said)" in src("show_runner.py"))

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
fixed += [("엔진", None, "NPC_LINE_CLOSE", G.NPC_LINE_CLOSE),
          ("엔진", None, "NPC_AWAY_FACT", G.NPC_AWAY_FACT), ("엔진", None, "NPC_AWAY_MARK", G.NPC_AWAY_MARK)]   # p0.5.14 고정 거절 자리 = 등 돌림 사실·관측 꼬리
for e_, life_, k_, v_ in fixed:
    if any(p_ in v_ for p_ in PROMISE) or brains.npc_promise(v_):   # p0.5.14 두뇌 대사 걸러내기와 같은 꼴도
        hits.append((e_, life_, k_, v_))
check("⑪ NPC 15명 고정 대사 전부(끈 판·마을 생활 판 · 대사·재방문·인사·보고) + 공물 판 대사 + 공통 닫는 말 · 등 돌림 사실·꼬리에 나중 약속 꼴이 없다(%d칸 · brains.npc_promise 포함)" % len(fixed),
      len(fixed) > 60 and not hits, hits)
NEW_LINES = {("gear_merchant", "line_again"): "아까 왔잖아. 물건은 장비점 진열대에 있어 — 오늘 있는 건 그게 다야.",   # p0.5.13 선물 → 판매로 한 번 더 바뀐 칸(약속 꼴 없음 그대로)
             ("innkeeper", "line"): "빈 방은 많은데 아직 손님 받을 준비가 안 됐어.", ("innkeeper", "line_again"): "아까 왔잖아. 아직 준비가 안 됐다니까.",
             ("tavern_keeper", "line_again"): "아까 왔잖아. 아직 준비 중이라니까.", ("street_vendor", "line_again"): "아까 봤죠? 여기선 사고팔지 않아요.",   # p0.5.16 '사고파는 건 아직'이 마을의 가게와 어긋나 다시 바뀐 칸
             ("apprentice_adventurer", "line_again"): "저는 아직 심사가 안 끝나서 파티를 못 구해요.",
             ("item_merchant", "line_again"): "아까 왔잖아. 물건은 잡화점 진열대에 있어.",   # p0.5.13 선물 → 판매로 한 번 더 바뀐 칸
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

print("── ⑫ p0.5.14 등 돌리기(DECISIONS 2026-10-15) — 진입·대사 없는 결과 사실·관측 꼬리·풀림·인사·거래·저장·정보 보호·지목 길")
import interactables as IA                           # noqa: E402
d12, bots12 = town()
a12, b12, c12 = bots12
gm12 = npc(d12, GEAR)
near12 = cells(d12, gm12, 1, 1)
put(a12, near12[0])
put(b12, near12[1] if len(near12) > 1 else cells(d12, gm12, 2, 3)[0])
put(c12, cells(d12, gm12, 2, 4, taken={(a12["x"], a12["y"]), (b12["x"], b12["y"])})[0])
turned(a12)
a12["npc_met"] = {GEAR}                              # 닫는 말까지 간 쌍 = 이미 만난 사이(첫 만남 선물 판정은 ③ 에서 따로 봤다)
for o_ in bots12:
    o_.pop("witnessed", None)
r12 = act(d12, a12, use(gm12, "하나만 더요"), bots12)
st12 = Brain("x")
g12 = turn_with(st12, d12, a12, GEAR, r12.pop("said", None), r12)
check("⑫ 등 돌린 쌍의 use(곁): npc_talk · talk away · line 칸 없음 · 0콜 · 저장 사본(last)에도 talk away",
      r12.get("result") == "npc_talk" and r12.get("talk") == "away" and "line" not in r12 and g12 == {"line": None, "src": "fixed", "stage": "away"}
      and not st12.calls and a12["last"].get("talk") == "away" and "line" not in a12["last"], (r12, g12))
check("⑫ 말 건 사람의 다음 관측: 직전 결과 '<이름>에게 말을 걸었다 — <사실>' · 꼬리표 '[대화] <이름> — <사실>'(대사 따옴표 없음)",
      brains._last_prose(a12["last"], NAMES) == "%s에게 말을 걸었다 — %s" % (GEAR, G.NPC_AWAY_FACT)
      and G.event_tags(a12["last"], NAMES) == [("talk", "대화", "%s — %s" % (GEAR, G.NPC_AWAY_FACT))], (brains._last_prose(a12["last"], NAMES), G.event_tags(a12["last"], NAMES)))
r12b = act(d12, b12, use(gm12), bots12) if near12[1:] else {"result": "npc_gift", "line": "x"}
check("⑫ 같은 NPC 라도 다른 사람(봇2)의 말 걸기는 보통 그대로(talk 없음 · 대사 있음) — 등 돌림은 쌍별",
      r12b.get("result") in G.NPC_TALK_RESULTS and "talk" not in r12b and r12b.get("line"), r12b)
check("⑫ 곁의 사람에게 등 돌림 목격이 생기지 않는다(말 걸기는 목격 사건이 아니다 — 봇3 의 witnessed 에 talk 없음)",
      not any(isinstance(w_, dict) and (w_.get("talk") or w_.get("npc_away")) for w_ in (c12.get("witnessed") or [])), c12.get("witnessed"))
o12a, o12b = d12.view(a12, bots12), d12.view(b12, bots12)
fa12 = next((f_ for f_ in o12a["sights"]["features"] if f_.get("id") == "f%d" % gm12.id), {})
fb12 = next((f_ for f_ in o12b["sights"]["features"] if f_.get("id") == "f%d" % gm12.id), {})
w12a, w12b = brains._wire(o12a, NAMES, compose=True), brains._wire(o12b, NAMES, compose=True)
ln12 = [ln for ln in w12a.splitlines() if "%s f%d" % (GEAR, gm12.id) in ln and ln.startswith("- ")]
check("⑫ 관측: 등 돌린 사람의 그 NPC 줄에만 away(참 — 틱 숫자 없음) · 줄 꼬리 ' · %s' 한 번 · 다른 사람(봇2)의 관측·글엔 없다 · 관측 어디에도 npc_away 칸 없음" % G.NPC_AWAY_MARK,
      fa12.get("away") is True and "away" not in fb12 and len(ln12) == 1 and ln12[0].endswith(" · " + G.NPC_AWAY_MARK)
      and w12a.count(" · " + G.NPC_AWAY_MARK) == 1 and G.NPC_AWAY_MARK not in w12b and "npc_away" not in json.dumps(o12a, ensure_ascii=False, default=str),
      (fa12, ln12, w12a.count(" · " + G.NPC_AWAY_MARK), "npc_away" in json.dumps(o12a, ensure_ascii=False, default=str)))
check("⑫ 관측 글에 풀리는 때가 없다(등 돌림 틱 수·'풀린다'·남은 틱 문구 없음)",
      not any(x_ in w12a for x_ in ("%d틱" % G.NPC_AWAY_TICKS, "풀린", "남은 틱", "틱 뒤")), [x_ for x_ in ("%d틱" % G.NPC_AWAY_TICKS, "풀린", "남은 틱", "틱 뒤") if x_ in w12a])
menu12 = G._tagsfx({"tag": {"verb": "말 걸어 봄", "n": 3}, "away": True})
check("⑫ 리모컨 라벨·관측 줄의 단일 꼬리(_tagsfx): 태그 뒤에 ' · %s' · away 없으면 옛 글 그대로" % G.NPC_AWAY_MARK,
      menu12 == " — 말 걸어 봄 ×3 · " + G.NPC_AWAY_MARK and G._tagsfx({"tag": {"verb": "말 걸어 봄", "n": 3}}) == " — 말 걸어 봄 ×3"
      and G._tagsfx({"away": True}) == " · " + G.NPC_AWAY_MARK and G._tagsfx({}) == "", menu12)

print("── ⑫ 지목한 말(되받기 길) — 말 없음 · 말 건 사람의 다음 관측에 사실 한 번(궤적 설정과 무관 — p0514b)")
AWAY_LINE = "- 네가 %s에게 건넨 말 — %s" % (GEAR, G.NPC_AWAY_FACT)


def said_scene(trail_on):
    """등 돌린 쌍(봇1-장비 상인)이 지목해 말한 한 틱 — 되받기 → 말의 결과(D72) → 러너가 npc_away_said. 반환 (되받은 말, 두뇌 콜, away 목록, 편지함, 몸 사본, 직전 결과 전)."""
    d_, bs_ = town()
    a_ = bs_[0]
    put(a_, cells(d_, npc(d_, GEAR), 1, 1)[0])
    turned(a_)
    d_.trail_on = trail_on
    act(d_, a_, {"type": "search", "src": "haiku"}, bs_)          # 그 틱의 제 행동 결과(last) 하나
    a_["trail"], a_["trail_gap"] = [], 0
    if trail_on:
        d_._trail_add(a_, a_["last"])
    last0, aw_, st_ = dict(a_["last"]), [], Brain("대답")
    old_ = brains.npc_reply
    brains.npc_reply = st_
    try:
        o_ = R.npc_say_replies(d_, bs_, {"1": to_gm("저기요, 하나만요")}, {}, lambda nm_: [], away=aw_)
    finally:
        brains.npc_reply = old_
    ib_, _h = R.deliver_and_hail(d_, bs_, {"1": "저기요, 하나만요"}, {"1": "npc:" + GEAR})
    for b_, n_ in aw_:
        d_.npc_away_said(b_, n_)
    body_ = {k_: (list(v_) if isinstance(v_, list) else v_) for k_, v_ in a_.items() if k_ in ("npc_away_said", "trail", "last")}
    ob_ = d_.view(a_, bs_)
    w_ = brains._wire(ob_, NAMES, compose=True)
    ob2_ = d_.view(a_, bs_)
    return o_, st_.calls, aw_, ib_, body_, last0, ob_, w_, ob2_, a_


for tr_ in (True, False):
    o12, c12_, aw12, inbox12, body12, last0_, ob12_, w12_, ob12b_, a12x = said_scene(tr_)
    check("⑫ 지목(궤적 %s): 되받은 말 없음(0콜) · away 목록 (봇1, 장비 상인) · 몸의 한 번 칸 npc_away_said · 직전 결과(last)는 그대로 · 궤적에 등 돌림 칸 없음"
          % ("켬" if tr_ else "끔"),
          o12 == [] and not c12_ and [(b_["char"], n_) for b_, n_ in aw12] == [("1", GEAR)] and body12.get("npc_away_said") == [GEAR]
          and body12.get("last") == last0_ and not any(t_.get("talk") == "away" for t_ in (body12.get("trail") or [])), (o12, body12))
    check("⑫ 지목(궤적 %s): 다음 관측에 npc_away_said · 직전 판단 절에 '%s' 한 줄 · 한 번 내보내면 비운다(그다음 관측·몸에 없음)" % ("켬" if tr_ else "끔", AWAY_LINE[:20]),
          ob12_.get("npc_away_said") == [GEAR] and w12_.count(AWAY_LINE) == 1 and "npc_away_said" not in ob12b_ and "npc_away_said" not in a12x
          and "npc_away_said" in brains._WIRE_KEYS and not brains.unwired_keys(ob12_), (ob12_.get("npc_away_said"), [ln for ln in w12_.splitlines() if "건넨 말" in ln]))
    if tr_:
        prose12 = brains._trail_prose(ob12_.get("trail") or [], NAMES)
        check("⑫ 지목(궤적 켬): 궤적은 제 행동 → 말의 결과(들은 사람 장비 상인) 그대로 · 사실은 따로 한 줄(꼬리표에 겹치지 않는다)",
              "들은 사람" in prose12 and G.NPC_AWAY_FACT not in prose12 and w12_.index(AWAY_LINE) > w12_.index("## 네 직전 판단과 그 결과"), prose12)
check("⑫ 지목 뒤 그 NPC 의 말은 누구의 편지함에도 없다(봇1 의 말만 들린다)",
      not any(str(m_.get("from")).startswith("npc:") for box_ in inbox12.values() for m_ in box_), inbox12)
ob12 = R.npc_say_targets(d12, bots12, {"1": {"type": "wait", "say": "음, 그렇군", "src": "haiku"}},
                         {"1": [{"from": "npc:" + GEAR, "text": G.NPC_LINE_CLOSE, "turn": 1, "to": "1"}]})
check("⑫ 상대를 적지 않은 말을 등 돌린 NPC 에게 한 답으로 읽지 않는다(via reply 없음 — 사실도 남기지 않는다)", ob12 == [], ob12)

print("── ⑫ 풀림 — 200틱(쌍별 · 표시 없이 · 장부 다시) · 원정(새 몸)")
x12 = bots12[2]
x12["npc_talk"] = {"npc:" + GEAR: G.NPC_REPLY_MAX, "npc:" + KEEPER: G.NPC_REPLY_MAX, "npc:" + PRIEST: 1}
x12["npc_away"] = {"npc:" + GEAR: 50, "npc:" + KEEPER: 120}
e199 = R.npc_away_expire([x12], 50 + G.NPC_AWAY_TICKS - 1)
e200 = R.npc_away_expire([x12], 50 + G.NPC_AWAY_TICKS)
check("⑫ 닫는 말 틱 + 199 = 아직 · + 200 = 그 쌍만 풀림(장부의 그 칸도 지운다) · 다른 쌍(늦게 돌린 주점 주인)·다른 장부(성직자 1)는 그대로 · 반환 = 관전용 end 한 줄",
      e199 == [] and e200 == [{"npc": GEAR, "char": x12["char"], "ev": "end"}] and x12["npc_away"] == {"npc:" + KEEPER: 120}
      and x12["npc_talk"] == {"npc:" + KEEPER: G.NPC_REPLY_MAX, "npc:" + PRIEST: 1}, (e199, e200, x12.get("npc_away"), x12.get("npc_talk")))
e320 = R.npc_away_expire([x12], 120 + G.NPC_AWAY_TICKS)
check("⑫ 마지막 쌍이 풀리면 npc_away 칸 자체가 없다(등 돌린 적 없는 몸과 같은 꼴)", e320 == [{"npc": KEEPER, "char": x12["char"], "ev": "end"}] and "npc_away" not in x12, x12)
put(x12, cells(d12, gm12, 1, 2, taken={(a12["x"], a12["y"]), (b12["x"], b12["y"])})[0])
st12c = Brain("다시 왔구먼.")
again12 = turn_with(st12c, d12, x12, GEAR, "또 왔어요", {"result": "npc_say", "npc": GEAR, "offer": []})
check("⑫ 풀린 뒤에는 처음부터 다시 — 보통 대답(두뇌 1콜) · 장부 1 · 관측 꼬리 없음",
      again12 == {"line": "다시 왔구먼.", "src": "brain", "stage": "talk"} and len(st12c.calls) == 1 and x12["npc_talk"].get("npc:" + GEAR) == 1
      and G.NPC_AWAY_MARK not in brains._wire(d12.view(x12, bots12), NAMES, compose=True), (again12, x12.get("npc_talk")))
i0c = carry_src.find("def _carry(")
body12 = carry_src[i0c:carry_src.find("\n    def ", i0c + 10)]
check("⑫ 원정을 다녀오면 풀림: 새 몸(G.spawn)·층 이월(_carry — 부활 _wake 도 이 목록)은 npc_away 를 옮기지 않는다(npc_talk 와 같이)",
      "npc_away" not in G.spawn(d12, "7", [], sheet=dict(SHEETS["1"])) and i0c > 0 and "npc_away" not in body12 and "npc_talk" not in body12
      and "_carry(b, n, d, turn," in carry_src[carry_src.find("def _wake("):])

print("── ⑫ 인사 중단 · 가게 거래 유지")
d12h, bots12h = town()
pr12 = npc(d12h, PRIEST)
spot12h = cells(d12h, pr12, 2, 4)
put(bots12h[0], spot12h[0])
put(bots12h[1], spot12h[1])
put(bots12h[2], (0, 0) if d12h.grid[0][0] == G.FLOOR else cells(d12h, npc(d12h, KEEPER), 1, 2)[0])
bots12h[0]["npc_away"] = {"npc:" + PRIEST: 1}
h12 = [(h_[0], h_[1]) for h_ in d12h.npc_greetings(bots12h)]
check("⑫ NPC 가 먼저 거는 인사: 등 돌린 쌍(봇1-성직자)에는 없다 · 같은 자리의 봇2 는 받는다 · 봇1 의 인사 장부도 그대로(풀린 뒤 한 번은 남는다)",
      (PRIEST, "1") not in h12 and (PRIEST, "2") in h12 and PRIEST not in (bots12h[0].get("npc_hailed") or set()), h12)


def stand_by(d_, f_, bots_=()):
    taken_ = {(o_["x"], o_["y"]) for o_ in bots_}
    return next((f_.x + dx, f_.y + dy) for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0))
                if d_.grid[f_.y + dy][f_.x + dx] == G.FLOOR and d_.feature_at(f_.x + dx, f_.y + dy) is None and (f_.x + dx, f_.y + dy) not in taken_)


d12s, bots12s = town()
s12 = bots12s[0]
turned(s12, GEAR)
s12["npc_talk"]["npc:" + ITEMS] = G.NPC_REPLY_MAX
s12["npc_away"]["npc:" + ITEMS] = 1
goods12 = {g_["name"]: g_ for g_ in IA.goods(d12s)}
dag, pot = goods12.get("단검") or {}, goods12.get("회복 물약") or {}
EQ12, GS12 = d12s.features.get(dag.get("fid")), d12s.features.get(pot.get("fid"))
trade = []
if EQ12 is not None and GS12 is not None:
    put(s12, stand_by(d12s, EQ12, bots12s))
    s12["weapon"], s12["gold"], s12["bag"], s12["potions"] = None, 40, 2, 0
    trade.append(act(d12s, s12, {"type": "buy", "target": dag["gid"]}, bots12s))   # p0.5.29 사기 = buy · 팔기 = sell(전엔 둘 다 use)
    trade.append(act(d12s, s12, {"type": "sell", "target": "f%d" % EQ12.id, "item": "i8", "amount": 1}, bots12s))
    put(s12, stand_by(d12s, GS12, bots12s))
    trade.append(act(d12s, s12, {"type": "buy", "target": pot["gid"]}, bots12s))
check("⑫ 가게 거래는 등 돌림과 무관: 장비 상인·아이템 상인이 둘 다 등 돌린 몸이 장비점에서 단검 사기(bought) · 보물 팔기(sold) · 잡화점에서 물약 사기(bought) · 골드 40→32→38→28",
      [r_.get("result") for r_ in trade] == ["bought", "sold", "bought"] and s12["gold"] == 28 and (s12.get("weapon") or {}).get("name") == "단검"
      and s12["potions"] == 1 and s12["bag"] == 1 and not any(r_.get("talk") for r_ in trade) and set(s12["npc_away"]) == {"npc:" + GEAR, "npc:" + ITEMS},
      [(r_.get("result"), r_.get("gold")) for r_ in trade])

print("── ⑫ 저장 판 7 · 이어가기 · 정보 보호")
snap12 = {"version": 2, "state_version": 6, "next_turn": 41,
          "bots": [{"char": "1", "gold": 5, "npc_talk": {"npc:" + GEAR: G.NPC_REPLY_MAX, "npc:" + KEEPER: 2}}],
          "worlds": [{"bots": [{"char": "2", "gold": 5, "npc_talk": {"npc:" + PRIEST: G.NPC_REPLY_MAX},
                                "npc_away": {"npc:" + PRIEST: 7}}]}],
          "waiting": {"3": {"char": "3", "gold": 5, "npc_talk": {"npc:" + ITEMS: 1}}}}
up12 = SN.upgrade(json.loads(json.dumps(snap12)))
check("⑫ 6→7 이관: 장부가 상한인 쌍만 등 돌림(이어간 틱 = next_turn - 1 = 40) · 이미 있는 표식은 그대로(7) · 상한 아래·걸린 쌍 없는 몸은 칸 없음 · 두 번 올려도 같다",
      SN.STATE_VERSION >= 7 and 6 in SN.MIGRATIONS and up12["state_version"] == SN.STATE_VERSION   # p0.5.15: 판 8(반복 신호) — 6→7 이관은 그대로
      and up12["bots"][0].get("npc_away") == {"npc:" + GEAR: 40} and up12["worlds"][0]["bots"][0]["npc_away"] == {"npc:" + PRIEST: 7}
      and "npc_away" not in up12["waiting"]["3"] and SN.upgrade(json.loads(json.dumps(up12))) == up12, up12)
S12 = tempfile.mkdtemp(prefix="snap_", dir=ROOT)
a12["npc_away"] = {"npc:" + GEAR: 33}
SN.write(S12, {"run_id": "r12", "d": d12, "bots": bots12, "sheets": SHEETS, "next_turn": 77, "stream_pos": 0, "seed": 7, "started": "t"},
         {"run_id": "r12", "next_turn": 77})
back12, _m12 = SN.load(os.path.join(S12, SN.PKL))   # 이 게이트가 방금 쓴 자기 피클(이어가기와 같은 길)
check("⑫ 이어가기: 스냅샷을 쓰고 되읽어도 등 돌림 표식(쌍·시작 틱)이 그대로 · 판 7 이상(지금 판)",
      back12["state_version"] == SN.STATE_VERSION >= 7 and back12["bots"][0].get("npc_away") == {"npc:" + GEAR: 33}
      and back12["bots"][0].get("npc_talk", {}).get("npc:" + GEAR) == G.NPC_REPLY_MAX, back12["bots"][0].get("npc_away"))
leak12 = IG.public({"type": "wait", "result": "waited", "npc_away": [{"npc": GEAR, "char": "1", "ev": "start"}],
                    "deep": {"npc_away": {"npc:" + GEAR: 3}, "keep": 1}})
check("⑫ 정보 보호: npc_away 는 관전 전용 칸(IG.SPECTATOR_KEYS) — 결과·목격 사본 어디에 옮겨 적혀도 걷힌다(누가 누구에게 등 돌렸나는 그 사람의 몫만)",
      "npc_away" in IG.SPECTATOR_KEYS and leak12 == {"type": "wait", "result": "waited", "deep": {"keep": 1}}, leak12)

print("── ⑫ NPC 두뇌 대사 약속 걸러내기(0콜 후처리)")
POS12 = ["허허, 함정 얘기라... 그런데 오늘은 여기까지야. 더 들으려면 내일 다시 와. 나도 무릎이 쑤셔서 오래 앉아 있기 힘들거든.",   # 0.5.13 t40 은퇴한 모험자(닫는 말)
         "아저씨가 지금 바쁘니까 바깥 탁자에서 기다려.",                                                                # 0.5.13 분석의 주점 주인 꼴
         "단검 하나 드릴 테니 잠깐만 기다려요, 창고에서 제일 쓸 만한 걸로 찾아볼게요.",                                     # 10-13 t139 장비 상인
         "아이고, 금방 찾아 올게요, 기다리세요~",                                                                       # 10-13 t142
         "허허, 그래그래, 기다리게나. 그 녀석 얘기는 술 한잔 따라놓고 해야 제맛이거든.",                                      # 10-12 t85 은퇴한 모험자
         "다음에 또 와요~", "이따가 다시 오게.", "나중에 와.", "좀 있다 와!", "여기서 기다리고 있어라.", "자리에 앉아서 기다리고 계세요.",
         "잠깐 기다려 줘.", "내일 와 봐", "탁자에서 기다려"]
NEG12 = ["허허, 함정 얘기는 내일 또 와서 졸라도 소용없어. 오늘은 이만하고 술이나 식혀 마셔.",                                  # 0.5.13 t46(거절 — 다시 오라는 말이 아니다)
         "무사히 돌아오시길 기다리고 있을게요.",                                                                         # 10-12 t10 성직자(NPC 자신이 기다린다)
         "무릎 낫기만 기다리겠다니 참 싹싹한 아가씨구먼.",                                                                 # 10-14 t80
         "어, 미미 왔구나? 아까 왔잖아. 바깥 탁자는 그대로 있으니 편히 앉아.",                                              # 0.5.13 t138(탁자는 세계에 있다)
         "기다려도 소용없어, 오늘은 더 할 얘기가 없네.", "셋이 모일 때까지는 입구가 안 열리니 모여야 해.", "또 와요~",
         G.NPC_LINE_CLOSE, G.NPC_AWAY_FACT, "다시는 오지 마.",
         "기다려 줄 수는 없네.", "나는 여기서 친구를 기다리고 있어.", "내일 와 봤자 아무것도 없어.",   # p0514b(Codex p0514r 필수 ①) — 거절·지금 일·설명
         "기다려 봐도 소용없어.", "나중에 와 봐야 달라질 건 없네.", "내일 다시 와도 같은 얘기뿐이야.", "기다려 주는 사람은 없어."]
check("⑫ 걸러낼 꼴 %d개(실판 5 + 같은 결) 전부 · 남길 꼴 %d개(실판 4 + 거절·지금 일·규칙·공통 문장 · p0514b 리뷰 반례 3 — 명령꼴 뒤에 말이 이어지면 걸지 않는다) 전부" % (len(POS12), len(NEG12)),
      all(brains.npc_promise(x_) for x_ in POS12) and not any(brains.npc_promise(x_) for x_ in NEG12),
      ([x_ for x_ in POS12 if not brains.npc_promise(x_)], [x_ for x_ in NEG12 if brains.npc_promise(x_)]))
LOG12 = os.path.join(ROOT, "brain12.jsonl")
seen12 = {}
os.environ["DUNGEON_BRAIN_LOG"] = LOG12
brains._call_claude = lambda p, m="haiku": (seen12.__setitem__(len(seen12), p), ('{"line": "%s"}' % POS12[0], None))[1]
try:
    d12p, bots12p = town()
    p12 = bots12p[0]
    got_talk = R.npc_turn(d12p, p12, KEEPER, "소문 있어요?", {"result": "npc_talk", "npc": KEEPER, "line": "정해진 대사"}, lambda nm_: [], True, names=NAMES)
    got_say = R.npc_turn(d12p, p12, PRIEST, "안녕하세요", {"result": "npc_say", "npc": PRIEST, "offer": []}, lambda nm_: [], True, names=NAMES)
    p12["npc_talk"]["npc:" + GEAR] = G.NPC_REPLY_MAX - 1
    got_close = R.npc_turn(d12p, p12, GEAR, "또요", {"result": "npc_talk", "npc": GEAR, "line": "정해진 대사"}, lambda nm_: [], True, names=NAMES)
finally:
    brains._call_claude = lambda prompt, model="haiku": ""
    os.environ.pop("DUNGEON_BRAIN_LOG", None)
with open(LOG12, encoding="utf-8") as f:
    log12 = [json.loads(ln) for ln in f if ln.strip()]
check("⑫ 걸린 두뇌 대사 = 실패한 콜과 같은 폴백: use 보통 차례 → 정해진 대사 · 되받기 보통 차례 → 말 없음 · 닫는 말 차례 → 공통 닫는 말(그리고 등 돌림) · 콜은 셌다(장부 1·1·3)",
      got_talk == {"line": "정해진 대사", "src": "fixed", "stage": "talk"} and got_say == {"line": None, "src": "fixed", "stage": "talk"}
      and got_close == {"line": G.NPC_LINE_CLOSE, "src": "fixed", "stage": "close"} and len(seen12) == 3
      and p12["npc_talk"] == {"npc:" + KEEPER: 1, "npc:" + PRIEST: 1, "npc:" + GEAR: G.NPC_REPLY_MAX} and set(p12.get("npc_away") or {}) == {"npc:" + GEAR},
      (got_talk, got_say, got_close, p12.get("npc_talk")))
check("⑫ 두뇌 기록(DUNGEON_BRAIN_LOG 판): 걸린 줄마다 ok False · why 'promise' · dropped = 버린 문장",
      len(log12) == 3 and all(e_.get("why") == "promise" and e_.get("ok") is False and e_.get("dropped") == POS12[0] for e_ in log12), log12)
p12s = [seen12[i_] for i_ in sorted(seen12)]
check("⑫ NPC 지침: '다시 오라거나 기다리라고 하지도 않는다' 줄(모든 NPC 프롬프트) · 닫는 말 차례 장면에 '다시 오라거나 기다리라는 말은 하지 않는다'(그 차례만)",
      all("다시 오라거나 기다리라고 하지도 않는다" in p_ for p_ in p12s) and "다시 오라거나 기다리라는 말은 하지 않는다" in p12s[2]
      and not any("다시 오라거나 기다리라는 말은 하지 않는다" in p_ for p_ in p12s[:2]), [p_.split("## 방금 일어난 일")[-1][:200] for p_ in p12s])

print("── ⑫ 러너 풀런(스텁 — 0콜): 진입 → 등 돌림(use·지목) → 풀림(틱 수를 줄여서) → 다시 대답")
SCRIPT3 = {"step": 0, "obs": [], "start": None}


def stub_think3(d, bots, inbox, on_error=None):
    """봇1 만 장비 상인 곁에서: use·use·use(닫는 말) → use(등 돌림) → 지목(등 돌림) → 관측에 꼬리가 사라질 때까지 수색 → use(다시 대답). 봇2·3 은 말이 없다."""
    out = {}
    gm_ = next(f for f in d.features.values() if f.type == "npc" and f.name == GEAR)
    for b in bots:
        if b.get("order") or not b["alive"] or b["won"]:
            continue
        if b["char"] == "1" and SCRIPT3["start"] is None:
            SCRIPT3["start"] = d.turn
            put(b, cells(d, gm_, 1, 1, taken={(o["x"], o["y"]) for o in bots if o is not b})[0])
            b["order"], b["path"] = None, []
        obs_ = d.view(b, bots)
        dec = {"type": "search", "reason": "각본", "src": "haiku"}
        if b["char"] == "1":
            w_ = brains._wire(obs_, NAMES, compose=True)
            marked = G.NPC_AWAY_MARK in w_
            SCRIPT3["obs"].append((d.turn, marked, G.NPC_AWAY_FACT in w_))
            k = SCRIPT3["step"]
            if k < 4:
                dec = {**use(gm_, "말 %d" % k), "reason": "각본 %d" % k}
                SCRIPT3["step"] += 1
            elif k == 4:
                dec = {**dec, "say": "상인님, 하나만요", "to": "npc:" + GEAR}
                SCRIPT3["step"] += 1
            elif k == 5 and not marked:
                dec = {**use(gm_, "다시 왔어요"), "reason": "꼬리가 사라졌다"}
                SCRIPT3["step"] += 1
        out[b["char"]] = dec
    return out


NPC_PROMPTS[:] = []
old_away = G.NPC_AWAY_TICKS
G.NPC_AWAY_TICKS = 6                                 # 200 틱 판을 돌리지 않고 같은 길을 본다(풀림 = 닫는 말 틱 + 6)
try:
    rows3 = run(turns="16", think=stub_think3)
finally:
    G.NPC_AWAY_TICKS = old_away
ticks3 = [r for r in rows3 if r["kind"] == "tick"]
ev3 = [(r["turn"], e) for r in ticks3 for e in (r.get("events") or []) if str(e.get("char")) == "1" and e.get("result") in G.NPC_TALK_RESULTS]
st3_ = [(e.get("talk"), e.get("line_src"), "line" in e) for _, e in ev3]
aw3 = [(r["turn"], e) for r in ticks3 for e in (r.get("npc_away") or [])]
t_close = next((t_ for t_, e in ev3 if e.get("talk") == "close"), None)
check("⑫ 풀런: use 다섯 — 보통·보통·닫는 말(두뇌) · 등 돌림(대사 없음) · 풀린 뒤 보통(두뇌) · 두뇌 콜 4",
      st3_ == [(None, "brain", True), (None, "brain", True), ("close", "brain", True), ("away", None, False), (None, "brain", True)]
      and len(NPC_PROMPTS) == 4, (st3_, len(NPC_PROMPTS)))
check("⑫ 풀런: tick.npc_away = 닫는 말 틱의 start · 그 틱 + NPC_AWAY_TICKS 의 end(그 둘뿐)",
      t_close is not None and aw3 == [(t_close, {"npc": GEAR, "char": "1", "ev": "start"}), (t_close + 6, {"npc": GEAR, "char": "1", "ev": "end"})], aw3)
obs3 = {t_: (m_, f_) for t_, m_, f_ in SCRIPT3["obs"]}
t_use_away = next((t_ for t_, e in ev3 if e.get("talk") == "away"), None)
t_say = next((r["turn"] for r in ticks3 if (r["decisions"].get("1") or {}).get("to") == "npc:" + GEAR), None)
check("⑫ 풀런 관측(봇1): 닫는 말 다음 틱부터 풀림 전까지 꼬리 · 풀린 틱부터 꼬리 없음 · 등 돌린 use·지목의 다음 관측에 결과 사실",
      t_close is not None and all(obs3[t_][0] for t_ in obs3 if t_close < t_ < t_close + 6) and not any(obs3[t_][0] for t_ in obs3 if t_ >= t_close + 6 or t_ <= t_close)
      and t_use_away and obs3.get(t_use_away + 1, (0, 0))[1] and t_say and obs3.get(t_say + 1, (0, 0))[1], (t_close, t_use_away, t_say, SCRIPT3["obs"]))
check("⑫ 풀런: 지목한 말은 되받은 말이 없다 · 이벤트 로그에 '장비 상인 → 봇1 — 등 돌림(대사 없음)' 한 줄 · 등 돌린 동안 장비 상인의 말이 편지함에 없다",
      not any(x.get("char") == "1" for r in ticks3 for x in (r.get("npc_replies") or []))
      and sum(1 for ln in run_events() if "%s → 봇1 — 등 돌림(대사 없음)" % GEAR in ln) == 1
      and not any(str(m.get("from")) == "npc:" + GEAR and t_close < int(m.get("turn", 0)) < t_close + 6
                  for r in ticks3 for box in (r.get("inbox") or {}).values() for m in box), t_say)

print("── ⑫ (p0514b 권장) 자동 접근 도중의 풀림 · 저장 뒤 실제 러너 이어가기")
d12q, bots12q = town()
q12, q12b = bots12q[0], bots12q[1]
gmq = npc(d12q, GEAR)
far12 = cells(d12q, gmq, 6, 12)
for b_, xy_ in ((q12, far12[0]), (q12b, far12[1])):
    put(b_, xy_)
    turned(b_)                                       # 둘 다 틱 1 에 등 돌린 쌍
    b_["npc_met"] = {GEAR}
d12q.turn = 2
ap_q = act(d12q, q12, use(gmq, "하나만요"), bots12q)
ap_qb = act(d12q, q12b, use(gmq, "저도요"), bots12q)
fin_qb = walk_until_done(d12q, q12b, bots12q)        # 봇2: 등 돌림이 그대로인 채 도착
d12q.turn = 1 + G.NPC_AWAY_TICKS - 1
pre_q = R.npc_away_expire(bots12q, d12q.turn)
for _ in range(2):                                   # 봇1: 걷는 동안 풀림 틱이 지난다(러너처럼 틱 머리마다 풀림 → 걸음)
    d12q.turn += 1
    R.npc_away_expire(bots12q, d12q.turn)
    if q12.get("order"):
        d12q.step_order(q12, bots12q)
fin_q = walk_until_done(d12q, q12, bots12q)
st12q = Brain("다시 왔구먼.")
got_q = turn_with(st12q, d12q, q12, GEAR, (fin_q or {}).pop("said", None), fin_q or {})
check("⑫ 자동 접근: 등 돌린 채 출발해 등 돌린 채 도착하면 결과 사실(talk away · 대사 없음) · 걷는 동안 풀리면 도착 판정은 보통 대화(대사 · 두뇌 1콜 · 장부 1)",
      ap_q.get("result") == "approaching" and ap_qb.get("result") == "approaching"
      and fin_qb and fin_qb.get("result") == "npc_talk" and fin_qb.get("talk") == "away" and "line" not in fin_qb
      and pre_q == [] and "npc_away" not in q12 and fin_q and fin_q.get("result") == "npc_talk" and "talk" not in fin_q and fin_q.get("line")
      and got_q["stage"] == "talk" and got_q["src"] == "brain" and len(st12q.calls) == 1 and q12["npc_talk"].get("npc:" + GEAR) == 1,
      (ap_q.get("result"), fin_qb, pre_q, q12.get("npc_away"), fin_q, got_q))
SCRIPT4 = {"step": 0, "placed": False, "stop": None}


def stub_think4(d, bots, inbox, on_error=None):
    """봇1 만 장비 상인 곁에서: use 셋(닫는 말) → use(등 돌림) → 곱게 멈춤 요청 / (이어가기) → use(아직 등 돌림) → 꼬리가 사라지면 use(다시 대답)."""
    out = {}
    gm_ = next(f for f in d.features.values() if f.type == "npc" and f.name == GEAR)
    for b in bots:
        if b.get("order") or not b["alive"] or b["won"]:
            continue
        if b["char"] == "1" and not SCRIPT4["placed"]:
            SCRIPT4["placed"] = True
            put(b, cells(d, gm_, 1, 1, taken={(o["x"], o["y"]) for o in bots if o is not b})[0])
            b["order"], b["path"] = None, []
        obs_ = d.view(b, bots)
        dec = {"type": "search", "reason": "각본", "src": "haiku"}
        if b["char"] == "1":
            marked = G.NPC_AWAY_MARK in brains._wire(obs_, NAMES, compose=True)
            k = SCRIPT4["step"]
            if k < 4 or k == 5 or (k == 6 and not marked):
                dec = {**use(gm_, "말 %d" % k), "reason": "각본 %d" % k}
                SCRIPT4["step"] += 1
            elif k == 4:
                import run_control as RC                   # noqa: E402
                RC.request_stop(R.STATE, pages=False)       # 다음 틱 머리에서 곱게 멈춘다(스냅샷 = 그 틱 전)
                SCRIPT4["stop"] = d.turn
                SCRIPT4["step"] += 1
        out[b["char"]] = dec
    return out


NPC_PROMPTS[:] = []
st4 = tempfile.mkdtemp(prefix="run_resume_", dir=ROOT)
old_away4 = G.NPC_AWAY_TICKS
G.NPC_AWAY_TICKS = 6
try:
    rows4a = run(turns="14", think=stub_think4, st=st4)
    snap_ok = os.path.isfile(os.path.join(st4, SN.PKL))
    rows4 = run(turns="14", think=stub_think4, st=st4, resume=True)
finally:
    G.NPC_AWAY_TICKS = old_away4
ticks4 = [r for r in rows4 if r["kind"] == "tick"]
ev4 = [(r["turn"], e) for r in ticks4 for e in (r.get("events") or []) if str(e.get("char")) == "1" and e.get("result") in G.NPC_TALK_RESULTS]
aw4 = [(r["turn"], e.get("ev")) for r in ticks4 for e in (r.get("npc_away") or [])]
t4c = next((t_ for t_, e in ev4 if e.get("talk") == "close"), None)
res4 = next((r for r in rows4 if r["kind"] == "resume"), None)
check("⑫ 이어가기(실제 러너): 곱게 멈춘 판(stopped · 스냅샷)을 이어 돌면 — 이어간 뒤의 use 는 아직 등 돌림 · 풀림(end)은 닫는 말 틱 + NPC_AWAY_TICKS 그대로(시작 틱이 저장됐다) · 그 뒤 다시 대답(두뇌)",
      snap_ok and any(r["kind"] == "stopped" for r in rows4a) and res4 is not None and t4c is not None
      and [(e.get("talk"), e.get("line_src")) for t_, e in ev4] == [(None, "brain"), (None, "brain"), ("close", "brain"), ("away", None), ("away", None), (None, "brain")]
      and [t_ for t_, e in ev4 if e.get("talk") == "away"][1] >= res4["turn"] and aw4 == [(t4c, "start"), (t4c + 6, "end")]
      and len(NPC_PROMPTS) == 4, (snap_ok, res4, [(t_, e.get("talk"), e.get("line_src")) for t_, e in ev4], aw4, len(NPC_PROMPTS), SCRIPT4))

print("── ⑨ 배선")
rs = src("show_runner.py")
check("⑨ 러너: NPC 블록이 두 가지(자동보행·즉시 실행) 뒤 공통 자리 — res.pop('said') → npc_turn · 옛 dec.get('say') 직접 읽기 없음",
      'said_ = res.pop("said", None)' in rs and "got_ = npc_turn(d, b, res[\"npc\"], said_, res," in rs
      and 'brains.npc_reply(b, res, dec.get("say")' not in rs)
check("⑨ 관측 안내의 '…번까지다' 꼬리 삭제 · 엔진 상수(MAX 3 · 닫는 말 공통 문장 · p0.5.14 등 돌림 틱·사실·꼬리 — 옛 거절 문장 없음)",
      "한 사람이 되받는 말은 네가" not in src("brains.py") and G.NPC_REPLY_MAX == 3 and G.NPC_LINE_CLOSE
      and G.NPC_AWAY_TICKS == 200 and G.NPC_AWAY_FACT and G.NPC_AWAY_MARK and not hasattr(G, "NPC_LINE_BUSY")
      and "NPC_LINE_BUSY =" not in src("dungeon_gm.py") and "G.NPC_LINE_BUSY" not in src("show_runner.py") + src("brains.py"))
ev_ts = src("game", "src", "text", "evline.ts")
check("⑨ 관전 화면 사건 줄(정적): NPC 결과 셋이 talk 'away' 면 '(등 돌림 — 대사 없음)' — line 이 없는 결과에 빈 「」를 그리지 않는다",
      "const npcSaid = e.talk === 'away' ? '(등 돌림 — 대사 없음)'" in ev_ts and ev_ts.count("${npcSaid}") == 3
      and "「${esc(str(e.line))}」`);   // 마을 NPC" not in ev_ts)

print("=" * 44)
if C.failed:
    print("RESULT: %d FAIL" % C.failed)
    raise SystemExit(1)
print("ALL PASS — verify_npc_talk (p0.5.10 신원 ID-2 NPC 대화 한 길: 세 길 한 장부 · 닫는 말 한 번 · 방문마다 풀림 · use 판정 유지 · 약속 문제 · "
      "p0.5.14 등 돌리기: 대사 없는 결과 사실 · 관측 꼬리 · 200틱/원정 풀림 · 인사 중단 · 거래 유지 · 저장 판 7 · 약속 걸러내기, %d checks, 실 LLM 0콜)" % C.n)

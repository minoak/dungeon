# -*- coding: utf-8 -*-
"""D93 NPC 되받기 — 캐릭터가 마을 사람에게 **말로** 건네면 그 사람이 한 번 되받는다. 실 LLM 0콜(brains.npc_reply·_call_claude 스텁).
(2026-09-20 — D82 실측 결함 "캐릭터가 NPC 인사에 말로 답해도 NPC 는 되받지 않는다: NPC 두뇌는 use 대상일 때만 답한다"의 수선.
 파트너 완성 기준 "마을에서 교류하고 여러 상호작용을 하며 실제로 이 마을에서 캐릭터가 살아간다는 걸 보여 주고")
러너 스위치 DUNGEON_NPC_REPLY=1(러너 기본 0 — 론처가 켠다 · NPC 두뇌가 도는 판에만 · 더미 두뇌 판은 저절로 꺼진다).
게이트:
  ① 기본은 옛 그대로: 스위치 상수 0 · 마을에 npc_reply 속성 없음 · 관측에 npc_ears 없음 · `to` 에 NPC id 를 적어도 혼잣말(None) · 상한 상수 3
  ② 켠 마을의 관측·프롬프트: npc_ears = 지금 내 말이 들리는(hears) 마을 사람만 · 사실 한 줄 · '그 밖의 정보' 누수 없음 ·
     `to` 풀이(id·이름 → 'npc:<이름>' / 안 들리는 사람·모르는 id → None / 봇 번호·all 은 옛 그대로)
  ③ 발생 조건 (a) 지목: to='npc:<이름>' 인 말 → 그 NPC 가 되받는다(두뇌 1콜 — result 'npc_say'·한 말·세계의 사실·NPC 정의)
  ④ 발생 조건 (b) 답: 그 NPC 가 나에게 건넨 말(먼저 건 인사·앞선 답)을 읽은 결정에서 상대 없이 한 말 → 되받는다(prev = 그 앞 줄) ·
     아닌 것: 모두에게·동료에게 한 말 / 상대 없는 제안(= 회의) / 남에게 건넨 NPC 의 말 / 말 없는 결정 / 작정 집행 / 건너뛴 결정
  ⑤ 상한: 같은 캐릭터-NPC 쌍은 방문당 3번(실패한 콜도 센다) · NPC 마다·캐릭터마다 따로 · 한 틱에 NPC 당 1콜(앞 번호 · use 로 이미 말한 NPC 는 건너뜀) ·
     연쇄 핑퐁 없음(캐릭터가 다시 말해야만 다시 답한다) · 실패(None)는 말이 없다(고정 대사로 메우지 않는다)
  ⑥ 들리는 거리 = Dungeon.hears: 다른 구역으로 간 사람의 말은 되받지 않는다 · 말의 결과(D72 궤적)에 그 NPC 가 들었는지가 실린다 · 문장
  ⑦ 배달: 같은 구역(또는 곁) 사람의 편지함에만 · from 'npc:<이름>' · to = 말을 건 사람 · 정지·뼈 없음
  ⑧ NPC 두뇌 프롬프트: 한 말·앞 줄·'말만 오갔다' 판정 · '줄 물건은 없다'(use 의 판정)는 없다 · 시트 없음
  ⑨ 끈 판·더미 판: 스위치를 켜도 더미 두뇌 판의 스트림은 끈 판과 (started 빼고) 바이트 동일 · 지문·run_meta 열쇠는 켠 판에만
  ⑩ 러너 풀런(스텁 두뇌 — 0콜): tick.npc_replies(to·reply 두 경로) · 그 말은 **다음 틱**의 편지함에 'npc:' 로 · 쌍마다 3번을 안 넘는다 · run_meta.npc_reply
  ⑪ 배선: 러너 소스 · 세계 지문(서브프로세스 — 기본/켬/마을 아님)
(기존 게이트는 별도 실행.)
"""
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = tempfile.mkdtemp(prefix="wl_npcreply_")
STATE = os.path.join(ROOT, "state")
os.makedirs(STATE, exist_ok=True)
BASE_ENV = dict(DUNGEON_GM="0", DUNGEON_STEP_DELAY="0", DUNGEON_TURNS="9", DUNGEON_W="40", DUNGEON_H="16",
                DUNGEON_DEPTHS="2", DUNGEON_SEED="7", DUNGEON_MONSTERS="0", DUNGEON_TRAPS="0", DUNGEON_LURKERS="0",
                DUNGEON_BESTIARY_FILE="", DUNGEON_PARTY_FILE=os.path.join(HERE, "party.json"), DUNGEON_STATE_DIR=STATE,
                DUNGEON_TOWN="1", DUNGEON_BRAIN_BACKEND="dummy", DUNGEON_BOSS="0", DUNGEON_RUNS_DIR=os.path.join(ROOT, "runs"),
                DUNGEON_ACTION_MODE="compose")
os.environ.update(BASE_ENV)
for k in ("DUNGEON_QUESTS", "DUNGEON_TOWN_APART", "DUNGEON_NPC_BRAIN", "DUNGEON_SOLO", "DUNGEON_START", "DUNGEON_MENU", "DUNGEON_RESUME",
          "DUNGEON_PARTYFORM", "DUNGEON_STRANGERS", "DUNGEON_TOWN_SIGHT", "DUNGEON_NPC_REPLY", "DUNGEON_TOWN_LIFE", "DUNGEON_NPC_HAIL_BRAIN",
          "DUNGEON_API_CALL_LIMIT", "DUNGEON_BRAIN_FALLBACK", "DUNGEON_BRAIN_LOG"):
    os.environ.pop(k, None)

import brains                                        # noqa: E402
brains._call_claude = lambda prompt, model="haiku": ""   # LLM 무력화 → dummy 폴백(결정론)


def _no_real_backend(prompt, model):                 # 이중 안전핀: 어떤 길로도 진짜 백엔드는 안 부른다(⑩ 은 백엔드 이름만 claude_cli 로 돌린다)
    raise AssertionError("real backend must not be called in a gate")


brains._call_cli = brains._call_anthropic = brains._call_gemini = brains._call_openai = _no_real_backend
import dungeon_gm as G                               # noqa: E402
import show_runner as R                              # noqa: E402
import time as _time                                 # noqa: E402
_time.sleep = lambda s: None
R.STEP_DELAY = 0


class C:
    failed = 0


def check(name, ok, detail=""):
    print("  %s %s%s" % ("OK  " if ok else "FAIL", name, (" — " + str(detail)) if (detail and not ok) else ""))
    if not ok:
        C.failed += 1


def src(*p):
    with open(os.path.join(HERE, *p), encoding="utf-8") as f:
        return f.read()


SHEETS = R.load_party(os.path.join(HERE, "party.json"))
NAMES = {c: SHEETS[c]["name"] for c in SHEETS}
RECEPTION, KEEPER = "길드 접수원", "주점 주인"


def town(on=True):
    d, _ = R.build_town(apart=True, walkers=True)
    d.composed_actions = d.auto_approach = True
    if on:
        d.npc_reply = True                           # 러너는 NPC 두뇌가 도는 판에만 건다(더미 백엔드의 build_town 은 안 건다 — ⑨)
    bs = []
    for c in sorted(SHEETS):
        bs.append(G.spawn(d, c, bs, sheet=dict(SHEETS[c])))
    d.turn = 1
    return d, bs


def npc(d, name):
    return next(f for f in d.features.values() if f.type == "npc" and f.name == name)


def beside(d, f, taken=()):
    """NPC f 와 같은 구역의 빈 바닥 칸 하나(가까운 순) — 거기 선 사람의 말은 그 NPC 에게 들린다."""
    z = d._town_zone(f.x, f.y)
    cells = sorted(((abs(x - f.x) + abs(y - f.y), x, y) for y in range(d.h) for x in range(d.w)
                    if d.grid[y][x] == G.FLOOR and not d.feature_at(x, y) and d._town_zone(x, y) == z and (x, y) not in taken))
    return cells[0][1], cells[0][2]


def put(b, xy):
    b["x"], b["y"] = xy


class Brain:
    """brains.npc_reply 스텁 — 부른 인자를 적고 정해 둔 문장(또는 None)을 돌려준다."""
    def __init__(self, line="그래요, 잘 들었어요."):
        self.calls, self.line = [], line

    def __call__(self, bot, res, said, facts, npc=None, roster=None):
        self.calls.append({"char": bot["char"], "res": dict(res), "said": said, "facts": list(facts or []), "npc": dict(npc or {})})
        return self.line


def facts_of(name):
    return ["사실 — %s" % name]


def replies(d, bs, decisions, inbox, spoke=(), line="그래요, 잘 들었어요."):
    stub, old = Brain(line), brains.npc_reply
    brains.npc_reply = stub
    try:
        out = R.npc_say_replies(d, bs, decisions, inbox, facts_of, spoke)
    finally:
        brains.npc_reply = old
    return out, stub.calls


print("── ① 기본은 옛 그대로")
d0, bots0 = town(on=False)
o0 = d0.view(bots0[0], bots0)
rec0 = npc(d0, RECEPTION)
check("① 러너 스위치 기본 0(NPC_REPLY_ON·TOWN_LIFE_ON) · 상한 상수 3", R.NPC_REPLY_ON is False and R.TOWN_LIFE_ON is False and G.NPC_REPLY_MAX == 3)
check("① 기본 마을: npc_reply 속성 없음 · 관측에 npc_ears 없음 · 되받기 장부 없음",
      not hasattr(d0, "npc_reply") and "npc_ears" not in o0 and all("npc_replies" not in b for b in bots0))
check("① 끈 판의 `to`: NPC id·이름을 적어도 혼잣말(None) — 옛 풀이 그대로",
      brains._parse_to("f%d" % rec0.id, "1", bots0, o0) is None and brains._parse_to(RECEPTION, "1", bots0, o0) is None
      and brains._parse_to("2", "1", bots0, o0) == "2" and brains._parse_to("all", "1", bots0, o0) == "all")

print("── ② 켠 마을의 관측·프롬프트")
d, bots = town()
a, b2, b3 = bots
rec, keep = npc(d, RECEPTION), npc(d, KEEPER)
put(a, beside(d, rec))
put(b2, beside(d, keep))
o = d.view(a, bots)
ears = {e["name"]: e["id"] for e in o.get("npc_ears") or []}
zone_a = d._town_zone(a["x"], a["y"])
want = {f.name for f in d.features.values() if f.type == "npc" and d.hears(a, f.x, f.y)}
check("② npc_ears = 지금 내 말이 들리는 마을 사람 전부(접수원 포함) · 다른 구역의 주점 주인은 없다 · id 는 피처 id",
      set(ears) == want and RECEPTION in ears and KEEPER not in ears and ears[RECEPTION] == "f%d" % rec.id
      and d._town_zone(keep.x, keep.y) != zone_a, (sorted(ears), sorted(want)))
w = brains._wire(o, NAMES, compose=True)
check("② 프롬프트: 사실 한 줄(들리는 사람·id·`to`·상한 3) · '그 밖의 정보' 누수 없음",
      ("지금 네 말이 들리는 마을 사람: " in w and "%s(f%d)" % (RECEPTION, rec.id) in w and "`to` 에 그 ID 를 적어 말하면" in w
       and "3번까지" in w and "## 그 밖의 정보" not in w))
check("② 끈 판 프롬프트에는 그 줄이 없다", "지금 네 말이 들리는 마을 사람" not in brains._wire(o0, NAMES, compose=True))
check("② `to` 풀이: id·이름 → 'npc:<이름>' · 안 들리는 사람(주점 주인)·모르는 id → None · 봇 번호·all 은 옛 그대로",
      brains._parse_to("f%d" % rec.id, "1", bots, o) == "npc:" + RECEPTION and brains._parse_to(RECEPTION, "1", bots, o) == "npc:" + RECEPTION
      and brains._parse_to("f%d" % keep.id, "1", bots, o) is None and brains._parse_to(KEEPER, "1", bots, o) is None
      and brains._parse_to("f999", "1", bots, o) is None and brains._parse_to("2", "1", bots, o) == "2" and brains._parse_to("모두", "1", bots, o) == "all")
fl = G.Dungeon(seed=7, w=40, h=16)
fl.npc_reply = True
check("② 던전 층은 스위치가 있어도 관측에 없다(마을만)", "npc_ears" not in fl.view(G.spawn(fl, "1", []), []))

print("── ③ 발생 조건 (a) 지목")
dec_a = {"1": {"type": "wait", "say": "의뢰가 어떤 게 있나요?", "to": "npc:" + RECEPTION, "src": "haiku"}}
out, calls = replies(d, bots, dec_a, {})
check("③ 지목한 말 → 그 NPC 가 한 번 되받는다(경로 to) · 두뇌 1콜: result 'npc_say'·한 말·세계의 사실·NPC 정의(역할)",
      out == [{"npc": RECEPTION, "char": "1", "line": "그래요, 잘 들었어요.", "via": "to"}] and len(calls) == 1
      and calls[0]["res"] == {"result": "npc_say", "npc": RECEPTION} and calls[0]["said"] == "의뢰가 어떤 게 있나요?"
      and calls[0]["facts"] == ["사실 — " + RECEPTION] and calls[0]["npc"].get("role"), (out, calls))
check("③ 되받기 장부: bot['npc_replies'][NPC 이름] = 1", a.get("npc_replies") == {RECEPTION: 1})

print("── ④ 발생 조건 (b) 답")
d4, bots4 = town()
a4, b4, c4 = bots4
rec4 = npc(d4, RECEPTION)
put(a4, beside(d4, rec4))
hail = {"from": "npc:" + RECEPTION, "text": "어서 와요. 게시판에 의뢰가 3건 있어요.", "turn": 1, "to": "1"}
out, calls = replies(d4, bots4, {"1": {"type": "wait", "say": "안녕하세요!", "src": "haiku"}}, {"1": [hail]})
check("④ NPC 가 내게 건넨 말을 읽은 결정에서 상대 없이 한 말 → 되받는다(경로 reply · prev = 그 인사)",
      [(r["npc"], r["char"], r["via"]) for r in out] == [(RECEPTION, "1", "reply")] and calls[0]["res"].get("prev") == hail["text"], (out, calls))
two = [hail, {"from": "npc:견습 모험자", "text": "저도 언젠가는…", "turn": 1, "to": "1"}]
app = next((f for f in d4.features.values() if f.type == "npc" and f.name == "견습 모험자"), None)
out2, _ = replies(d4, bots4, {"1": {"type": "wait", "say": "그래?", "src": "haiku"}}, {"1": two})
check("④ 둘이 말을 건넸으면 가장 최근에 건넨 사람이 제게 한 답으로 듣는다(그 사람이 들리는 자리일 때)",
      app is None or not d4.hears(a4, app.x, app.y) or [r["npc"] for r in out2] == ["견습 모험자"], out2)
neg = []
for label, dec, inbox in (
        ("모두에게", {"type": "wait", "say": "다들 들어 봐", "to": "all", "src": "haiku"}, {"1": [hail]}),
        ("동료에게", {"type": "wait", "say": "카야, 가자", "to": "2", "src": "haiku"}, {"1": [hail]}),
        ("상대 없는 제안(회의)", {"type": "wait", "say": "다 같이 내려가자", "say_kind": "제안", "src": "haiku"}, {"1": [hail]}),
        ("남에게 건넨 NPC 의 말", {"type": "wait", "say": "음", "src": "haiku"}, {"1": [{**hail, "to": "2"}]}),
        ("NPC 의 말이 없다", {"type": "wait", "say": "혼잣말이다", "src": "haiku"}, {"1": [{"from": "2", "text": "어이", "turn": 1, "to": "1"}]}),
        ("말 없는 결정", {"type": "wait", "say": "", "src": "haiku"}, {"1": [hail]}),
        ("작정 집행", {"type": "wait", "say": "안녕하세요!", "src": "plan"}, {"1": [hail]}),
        ("건너뛴 결정", {"type": "wait", "say": "안녕하세요!", "src": "haiku", "skipped": True}, {"1": [hail]})):
    a4.pop("npc_replies", None)
    o_, c_ = replies(d4, bots4, {"1": dec}, inbox)
    if o_ or c_:
        neg.append(label)
check("④ 아닌 것 여덟: 모두에게·동료에게·상대 없는 제안(회의)·남에게 건넨 말·NPC 말 없음·말 없는 결정·작정 집행·건너뛴 결정 → 0콜", not neg, neg)
out_p, _ = replies(d4, bots4, {"1": {"type": "wait", "say": "같이 가실래요?", "say_kind": "제안", "to": "npc:" + RECEPTION, "src": "haiku"}}, {})
check("④ 지목한 제안은 되받는다(종류 무관 — 지목이 곧 상대)", [r["via"] for r in out_p] == ["to"])

print("── ⑤ 상한 · 한 틱 NPC 당 1콜 · 연쇄 없음")
d5, bots5 = town()
a5, b5, c5 = bots5
rec5, keep5 = npc(d5, RECEPTION), npc(d5, KEEPER)
p1 = beside(d5, rec5)
put(a5, p1)
put(b5, beside(d5, rec5, taken={p1}))
say_to = lambda who: {"type": "wait", "say": "하나 더 물을게요", "to": "npc:" + who, "src": "haiku"}
n_calls, n_out = 0, 0
for _ in range(5):
    o_, c_ = replies(d5, bots5, {"1": say_to(RECEPTION)}, {})
    n_calls, n_out = n_calls + len(c_), n_out + len(o_)
check("⑤ 같은 쌍은 방문당 3번까지 — 다섯 번 말해도 3콜·3번", (n_calls, n_out, a5["npc_replies"]) == (3, 3, {RECEPTION: 3}), (n_calls, n_out, a5.get("npc_replies")))
o_, c_ = replies(d5, bots5, {"2": say_to(RECEPTION)}, {})
check("⑤ 캐릭터마다 따로 센다(봇2 는 같은 NPC 에게 아직 0번)", len(o_) == 1 and b5["npc_replies"] == {RECEPTION: 1})
put(a5, beside(d5, keep5))
o_, c_ = replies(d5, bots5, {"1": say_to(KEEPER)}, {})
check("⑤ NPC 마다 따로 센다(봇1 은 주점 주인에게 아직 0번)", len(o_) == 1 and a5["npc_replies"] == {RECEPTION: 3, KEEPER: 1})
d5b, bots5b = town()
a6, b6, c6 = bots5b
rec6 = npc(d5b, RECEPTION)
q1 = beside(d5b, rec6)
put(a6, q1)
put(b6, beside(d5b, rec6, taken={q1}))
both = {"1": say_to(RECEPTION), "2": say_to(RECEPTION)}
o_, c_ = replies(d5b, bots5b, both, {})
check("⑤ 한 틱에 NPC 당 1콜 — 둘이 같은 NPC 에게 말하면 앞 번호만(뒷사람은 장부도 안 는다)",
      [(r["char"]) for r in o_] == ["1"] and len(c_) == 1 and "npc_replies" not in b6, (o_, b6.get("npc_replies")))
o_, c_ = replies(d5b, bots5b, {"2": say_to(RECEPTION)}, {}, spoke={RECEPTION})
check("⑤ 이 틱에 use 로 이미 말한 NPC(spoke)는 건너뛴다 — 0콜", not o_ and not c_)
o_, c_ = replies(d5b, bots5b, {"2": {"type": "wait", "say": "", "src": "haiku"}}, {"2": [{"from": "npc:" + RECEPTION, "text": "되받은 말", "turn": 2, "to": "2"}]})
check("⑤ 연쇄 핑퐁 없음 — NPC 의 말을 받아도 캐릭터가 말하지 않으면 NPC 는 잇지 않는다", not o_ and not c_)
o_, c_ = replies(d5b, bots5b, {"2": say_to(RECEPTION)}, {}, line=None)
check("⑤ 두뇌 실패(None) = 말이 없다(고정 대사로 메우지 않는다) · 그 콜도 센다", o_ == [] and len(c_) == 1 and b6["npc_replies"] == {RECEPTION: 1})

print("── ⑥ 들리는 거리 = Dungeon.hears · 말의 결과(D72)")
d6, bots6 = town()
a7, b7, c7 = bots6
rec7, keep7 = npc(d6, RECEPTION), npc(d6, KEEPER)
put(a7, beside(d6, keep7))                           # 주점 주인 곁 = 접수원과 다른 구역
o_, c_ = replies(d6, bots6, {"1": say_to(RECEPTION)}, {})
check("⑥ 다른 구역으로 간 사람의 말은 그 NPC 가 못 듣는다 → 0콜(장부도 안 는다)",
      not d6.hears(a7, rec7.x, rec7.y) and not o_ and not c_ and "npc_replies" not in a7)
d6.trail_on = True
put(b7, (a7["x"] + 1, a7["y"]) if d6.grid[a7["y"]][a7["x"] + 1] == G.FLOOR else (a7["x"] - 1, a7["y"]))
R.deliver_and_hail(d6, bots6, {"1": "소문 좀 들려줘요"}, {"1": "npc:" + KEEPER})
said = [x for x in (a7.get("trail") or []) if x.get("type") == "said"]
check("⑥ 들은 말의 결과: 지목한 NPC 가 들었으면 heard 에 'npc:<이름>'(곁의 동료와 함께)",
      len(said) == 1 and said[0]["to"] == "npc:" + KEEPER and set(said[0]["heard"]) == {"2", "npc:" + KEEPER}, said)
a7["trail"] = []
R.deliver_and_hail(d6, bots6, {"1": "접수원님!"}, {"1": "npc:" + RECEPTION})
said2 = [x for x in (a7.get("trail") or []) if x.get("type") == "said"]
check("⑥ 못 들은 NPC 는 heard 에 없다", len(said2) == 1 and said2[0]["heard"] == ["2"], said2)
p_ok, p_far = brains._last_prose(said[0], NAMES), brains._last_prose(said2[0], NAMES)
check("⑥ 문장: '(주점 주인에게) — 카야·주점 주인이 들었다' / '길드 접수원은(는) 멀어서 못 들었고'",
      "(%s에게)" % KEEPER in p_ok and KEEPER in p_ok.split("—")[1] and "들었다" in p_ok and "동료" not in p_ok
      and "%s은(는) 멀어서 못 들었고" % RECEPTION in p_far, (p_ok, p_far))
tags = G.event_tags(said[0], NAMES)
check("⑥ 궤적 꼬리표: 들은 사람에 NPC 이름(접두 없이)", tags and KEEPER in tags[0][2] and "npc:" not in tags[0][2], tags)
msg = {"from": "1", "text": "소문 좀 들려줘요", "turn": 1, "to": "npc:" + KEEPER}
w6 = brains._wire({**d6.view(b7, bots6), "messages": [msg], "dialogue": [dict(msg)]}, NAMES, compose=True)
check("⑥ 곁의 동료에게는 '(주점 주인에게)' 로 들린다(봇 표기 아님) · 대화 기억 '→주점 주인'",
      '"소문 좀 들려줘요" (%s에게)' % KEEPER in w6 and "→%s" % KEEPER in w6 and "봇npc" not in w6, [ln for ln in w6.split("\n") if "소문" in ln])
check("⑥ 마을 사람에게 한 말은 동료를 세우지 않는다(지목도 회의도 아니다)",
      not G.addressed_to(msg, "2") and R.deliver_and_hail(d6, bots6, {"1": "같이 가실래요?"}, {"1": "npc:" + KEEPER}, {"1": "제안"}, {})[1] == {})

print("── ⑦ 배달")
d7, bots7 = town()
a8, b8, c8 = bots7
rec8, keep8 = npc(d7, RECEPTION), npc(d7, KEEPER)
r1 = beside(d7, rec8)
put(a8, r1)
put(b8, beside(d7, rec8, taken={r1}))
put(c8, beside(d7, keep8))
box = {}
R.deliver_npc_says(d7, bots7, box, [(RECEPTION, "되받은 말", "1")], 5)
check("⑦ 같은 구역 사람의 편지함에만(봇1·봇2) · 다른 구역(봇3)은 못 듣는다 · from 'npc:<이름>' · to = 말을 건 사람 · turn",
      box == {"1": [{"from": "npc:" + RECEPTION, "text": "되받은 말", "turn": 5, "to": "1"}],
              "2": [{"from": "npc:" + RECEPTION, "text": "되받은 말", "turn": 5, "to": "1"}]}, box)
check("⑦ 걷던 사람을 세우지 않는다(잡담) · 관계 뼈 없음", not any(b.get("hailed") for b in bots7) and all(not (b.get("relations") or {}).get("npc:" + RECEPTION) for b in bots7))

print("── ⑧ NPC 두뇌 프롬프트")
seen8 = {}
brains._call_claude = lambda p, m="haiku": (seen8.__setitem__("p", p), ('{"line": "고블린 소탕이 하나 있어요."}', None))[1]
line8 = brains.npc_reply(a8, {"result": "npc_say", "npc": RECEPTION, "prev": "어서 와요."}, "의뢰가 어떤 게 있나요?", ["게시판 의뢰: 고블린 소탕 — 게시 중"],
                         npc=(d7.npc_defs or {}).get(RECEPTION))
brains._call_claude = lambda prompt, model="haiku": ""
p8 = seen8.get("p", "")
check("⑧ 한 말 · 앞 줄 · '말만 오갔다' 판정 · 세계의 사실 · 역할", line8 == "고블린 소탕이 하나 있어요." and '네게 말을 걸었다: "의뢰가 어떤 게 있나요?"' in p8
      and '조금 전 네가 이 사람에게 한 말: "어서 와요."' in p8 and "세계의 판정: 말만 오갔다" in p8 and "게시판 의뢰: 고블린 소탕" in p8)
check("⑧ use 의 판정 문장('줄 물건은 없다')은 없다 · 시트(성격·말투)는 없다", "줄 물건은 없다" not in p8 and SHEETS["1"]["persona"][:12] not in p8)

print("── ⑨ 끈 판·더미 판")


def run(env, patch=None, brain=None, turns="9"):
    """러너 풀런(같은 프로세스) → 스트림 줄들. patch = 러너 모듈 상수 {이름: 값}, brain = _call_claude 스텁(없으면 더미 폴백)."""
    st = tempfile.mkdtemp(prefix="run_", dir=ROOT)
    old_env = {k_: os.environ.get(k_) for k_ in env}
    old_mod = {k_: getattr(R, k_) for k_ in (patch or {})}
    old_state, old_call, old_lim = R.STATE, brains._call_claude, (R.MAX_TURNS, R.PAUSE_LIMIT_SEC)
    os.environ.update(env)
    for k_, v_ in (patch or {}).items():
        setattr(R, k_, v_)
    R.STATE, R.MAX_TURNS, R.PAUSE_LIMIT_SEC = st, int(turns), 2   # 각본이 틀려 판단이 막혀도 게이트가 매달리지 않는다(2초 뒤 스스로 닫힌다 → 검사가 FAIL 로 말한다)
    if brain is not None:
        brains._call_claude = brain
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                R.main()
            except SystemExit:
                pass
    finally:
        brains._call_claude = old_call
        R.STATE, (R.MAX_TURNS, R.PAUSE_LIMIT_SEC) = old_state, old_lim
        for k_, v_ in old_mod.items():
            setattr(R, k_, v_)
        for k_, v_ in old_env.items():
            if v_ is None:
                os.environ.pop(k_, None)
            else:
                os.environ[k_] = v_
    with open(os.path.join(st, "stream.jsonl"), encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


def strip(rows):
    return [json.dumps({k_: v_ for k_, v_ in r.items() if k_ != "started"}, ensure_ascii=False, sort_keys=True) for r in rows]


rows_off = run({}, {"NPC_REPLY_ON": False})
rows_dummy = run({}, {"NPC_REPLY_ON": True})
check("⑨ 더미 두뇌 판: 스위치를 켜도 스트림이 끈 판과 (started 빼고) 바이트 동일 — 저절로 꺼진다(run_meta 열쇠·npc_replies 없음)",
      strip(rows_off) == strip(rows_dummy) and "npc_reply" not in rows_dummy[0]
      and not any("npc_replies" in r for r in rows_dummy if r["kind"] == "tick"), len(rows_off))
check("⑨ 끈 판의 스트림에 새 열쇠가 없다(npc_reply·town_life·npc_replies·overheard)",
      not any(k_ in r for r in rows_off for k_ in ("npc_reply", "town_life", "npc_replies", "overheard")))

print("── ⑩ 러너 풀런(스텁 두뇌 — 0콜)")
npc_prompts = []


def stub_brain(prompt, model="haiku"):
    """판단 요청·NPC 요청을 프롬프트 머리로 가른다. 봇1 = 들리는 첫 마을 사람을 `to` 로 지목 · 봇2 = 상대 없이 말한다(받은 인사에 답) · 봇3 = 말이 없다."""
    if prompt.lstrip().startswith("# 마을 사람"):
        npc_prompts.append(prompt)
        return '{"line": "되받은 말 %d"}' % len(npc_prompts), None
    m = re.search(r"- 번호 (\S+), 이름", prompt)
    who = m.group(1) if m else "?"
    ear = re.search(r"지금 네 말이 들리는 마을 사람: [^\n]*?\((f\d+)\)", prompt)
    dec = {"type": "search", "reason": "게이트 각본"}
    if who == "1" and ear:
        dec.update(say="여기 일은 요즘 어때요?", to=ear.group(1))
    elif who == "2":
        dec.update(say="아, 안녕하세요.")
    return json.dumps(dec, ensure_ascii=False), None


rows = run({"DUNGEON_BRAIN_BACKEND": "claude_cli"}, {"NPC_REPLY_ON": True}, brain=stub_brain, turns="9")
ticks = [r for r in rows if r["kind"] == "tick"]
reps = [(r["turn"], x) for r in ticks for x in (r.get("npc_replies") or [])]
vias = {x["via"] for _, x in reps}
check("⑩ run_meta.npc_reply · tick.npc_replies 에 두 경로(to = 봇1 의 지목 · reply = 봇2 가 받은 인사에 한 답)",
      rows[0].get("npc_reply") is True and vias == {"to", "reply"} and {x["char"] for _, x in reps if x["via"] == "to"} == {"1"}
      and {x["char"] for _, x in reps if x["via"] == "reply"} == {"2"}, reps[:4])
by_turn = {r["turn"]: r for r in ticks}
late = []
for t_, x in reps:
    nxt, cur = by_turn.get(t_ + 1), by_turn[t_]
    here = [m for m in (cur.get("inbox") or {}).get(x["char"], []) if m.get("text") == x["line"]]
    there = [m for m in ((nxt or {}).get("inbox") or {}).get(x["char"], []) if m.get("text") == x["line"]]
    if nxt is not None and (here or not there or there[0]["from"] != "npc:" + x["npc"] or there[0]["to"] != x["char"]):
        late.append((t_, x))
check("⑩ 되받은 말은 그 틱이 아니라 **다음 틱**의 편지함에 from 'npc:<이름>' · to = 말한 사람", reps and not late, late[:3])
pairs = {}
for _, x in reps:
    pairs[(x["char"], x["npc"])] = pairs.get((x["char"], x["npc"]), 0) + 1
check("⑩ 9틱 내내 말해도 쌍마다 3번에서 멎는다(상한에 닿은 쌍이 있다) · 두뇌 콜 수 = 되받은 말 수(실패 없음)",
      pairs and max(pairs.values()) == G.NPC_REPLY_MAX and len(npc_prompts) == len(reps), (pairs, len(npc_prompts)))
tos = {str((r["decisions"].get("1") or {}).get("to")) for r in ticks if (r["decisions"].get("1") or {}).get("say")}
check("⑩ 스트림의 decisions.to = 'npc:<이름>'(봇 번호와 같은 자리)", tos and all(t_.startswith("npc:") for t_ in tos), tos)
check("⑩ NPC 요청에 캐릭터가 한 말이 실린다", npc_prompts and all(("여기 일은 요즘 어때요?" in p_) or ("아, 안녕하세요." in p_) for p_ in npc_prompts))

print("── ⑪ 배선")
rs = src("show_runner.py")
check("⑪ 러너 소스: 스위치(기본 0)·되받기 호출·tick.npc_replies·배달 함수·run_meta·지문",
      'os.environ.get("DUNGEON_NPC_REPLY", "0") == "1" and NPC_BRAIN_ON' in rs and "npc_say_replies(d, bots, decisions, inbox_in," in rs
      and '"npc_replies": npc_replies' in rs and "deliver_npc_says(d, bots, inbox, npc_says, turn)" in rs
      and '{"npc_reply": True} if (NPC_REPLY_ON and npc_brain)' in rs and '{"npc_reply": True} if (NPC_REPLY_ON and TOWN_ON)' in rs)


def probe(env):
    e = {k_: v_ for k_, v_ in os.environ.items() if not k_.startswith("DUNGEON_")}
    e.update(PYTHONUTF8="1", **env)
    p = subprocess.run([sys.executable, "-c", "import json, show_runner as s; print(json.dumps({'on': s.NPC_REPLY_ON, 'fp': s._world_fingerprint().get('npc_reply')}))"],
                       cwd=HERE, env=e, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return json.loads(p.stdout.splitlines()[0]) if p.returncode == 0 and p.stdout.strip() else {"err": p.stderr[-300:]}


check("⑪ 세계 지문: 기본은 열쇠 없음 · 켠 마을 판에만 · 마을 판이 아니면 없음 · NPC 두뇌를 끄면 스위치도 꺼진다",
      probe(BASE_ENV) == {"on": False, "fp": None} and probe({**BASE_ENV, "DUNGEON_NPC_REPLY": "1"}) == {"on": True, "fp": True}
      and probe({**BASE_ENV, "DUNGEON_NPC_REPLY": "1", "DUNGEON_TOWN": "0"}) == {"on": True, "fp": None}
      and probe({**BASE_ENV, "DUNGEON_NPC_REPLY": "1", "DUNGEON_NPC_BRAIN": "0"}) == {"on": False, "fp": None})
check("⑪ 관측 열쇠 등록(brains._WIRE_KEYS) · 엔진 상수", "npc_ears" in brains._WIRE_KEYS and "NPC_REPLY_MAX = 3" in src("dungeon_gm.py"))

print("=" * 44)
if C.failed:
    print("RESULT: %d FAIL" % C.failed)
    raise SystemExit(1)
print("ALL PASS — verify_npcreply (D93 NPC 되받기: 지목·받은 말에 한 답·상한 3·틱당 1콜·hears·다음 틱 배달·끈 판 그대로)")

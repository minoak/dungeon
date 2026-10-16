# -*- coding: utf-8 -*-
"""p0.5.15 반복 신호 + 목표 칸(DECISIONS 2026-10-15 — 민옥 "같은 행동을 반복중이라면 트리거로 한번 환기" · 0.5.15 = 반복 신호 + 목표 칸). 실 LLM 0콜.
근거: 0.5.13 실판(Haiku · 시드 188663 · 600틱) — 몇 턴 전 계획을 잃고(t17 '보물 팔러 던전' 출발 → t28 상인 곁에서 이탈) 같은 대상에 머문다
(주점 주인 f3 90회 · search f25 26연속 · wait 18연속).
게이트:
  ① 연속 세기(repeat_signal 단위): 열쇠(동사 무관 · wait · 탐색·휴식·대상 없음 = 끊김) · 5·10번째 판단 뒤 다음 관측에 한 번씩(4 = 없음 · 11~15 = 없음) ·
     대상이 바뀌거나 다른 행동이 끼면 처음부터 · 작정 수가 이어 앞 신호를 실을 관측이 없었으면 늦게 싣지 않는다 · 사람 대상은 호칭이 바뀌어도 한 연속(열쇠 = ID)
  ② '달라진 것'(단위): 몸(골드·HP·물약·장비·상태·의뢰) · 대상의 상태(몬스터·사람 HP · 보이다 안 보임 · 등 돌림) · 같은 동사의 결과(결과 기록 원문 —
     읽은 글 뒷부분까지) · 한 번뿐인 결과(새 정보) · 대사 내용 · 발견 · 내게 한 남의 말 — 하나라도 있으면 SAME 없음 ·
     goto·use 를 섞어도 동사마다 같은 결과가 되풀이되면 SAME · 장부·자리 칸(틱·행동 번호·걸음 수·좌표)·걸음·행동 시작·도착 꼬리표·상태 남은 틱·
     피처의 오브젝트 태그 횟수·거리·내게 하지 않은 남의 말은 보지 않는다(p0515b — Codex p0515r 필수 ①) ·
     p0519: 궤적의 생략 표식(gap)·내가 한 말(said)·굴림 수치(빗나감·스킬 내성)·작정 표식·내 몸짓 서술도 보지 않는다(석상 장면 — 긴 접근 + 말하며 같은 search) ·
     그래도 결과 원문·성패·대상의 대답·남이 내게 한 몸짓은 맞댄다
  ③ 렌더: 관측 꼬리표 한 줄(무발견 신호와 같은 절) — p0515d 민옥 문구 '반복 중: <대상> ×N · 변화 없음'(대상/제자리/기다리기 · 곁 여부는 안 나온다) ·
     이름 층(아는 이름 · 낯선 사람) · 몬스터는 관측의 이름(도감이 가린 그대로) ·
     안 보이면 ID · 지시·권유 문장 없음(신호 문장·지침 두 줄) · _WIRE_KEYS 등록(미등록 관측 키 0)
  ④ 목표 칸: 파싱(80자 자름 · 한 줄로 · 빈 글 = 비움 · null·글 아님 = 그대로) · 저장 · 다음 판단부터 관측 맨 위 · 덮어쓰기 · 비우기 · 다시 적을 때까지 매 판단 ·
     엔진은 읽지 않는다(판정 무변화) · 글 속 ID 가 대상 절의 '자리 적힘'으로 읽히지 않는다 · 남에게 안 보임(남의 관측·프롬프트 · 봇 스냅샷 · 공개 투영이 todo_ops 를 걷는다)
  ⑤ think_all 미니 루프(손그림 장면 · 실제 엔진 판정): 자동 보행 틱은 세지 않는다 · 동사 섞임(goto·search) · 5·10번째 · 탐색이 끼면 끊김 · 걷다 본 계단(발견) = 달라짐
  ⑥ 러너 풀런(각본 두뇌): 스트림 tick.todo_ops(바뀐 틱만 — 같은 글 다시 적기는 없음) · decisions[].todo · events.log · 관측(스트림 obs)의 repeat · 남의 프롬프트에 없음 ·
     층 전이(마을 → 1층)에 목표 칸 이월·연속은 새 몸에서 처음부터 · 곱게 멈춤 → 이어가기 뒤에도 목표 칸·연속 그대로
  ⑦ 저장 판 8: 7→8 이관(최근 판단 장부로 연속을 다시 세움 — 지난 차례는 늦게 싣지 않고 변화는 모름) · 쓰기/되읽기 · 한 번만
  ⑧ 0콜: 진짜 백엔드는 부르면 실패하게 막고, 두뇌 응답은 전부 이 게이트의 각본
(기존 게이트는 별도 실행.)
"""
import contextlib
import io
import json
import os
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = tempfile.mkdtemp(prefix="wl_repeat_")
STATE = os.path.join(ROOT, "state")
os.makedirs(STATE, exist_ok=True)
BASE_ENV = dict(DUNGEON_GM="0", DUNGEON_STEP_DELAY="0", DUNGEON_TURNS="9", DUNGEON_W="40", DUNGEON_H="16",
                DUNGEON_DEPTHS="2", DUNGEON_SEED="7", DUNGEON_MONSTERS="0", DUNGEON_TRAPS="0", DUNGEON_LURKERS="0",
                DUNGEON_BESTIARY_FILE="", DUNGEON_PARTY_FILE=os.path.join(HERE, "party.json"), DUNGEON_STATE_DIR=STATE,
                DUNGEON_TOWN="1", DUNGEON_BRAIN_BACKEND="dummy", DUNGEON_BOSS="0", DUNGEON_RUNS_DIR=os.path.join(ROOT, "runs"),
                DUNGEON_ACTION_MODE="compose", DUNGEON_STREAM_OBS="1")
os.environ.update(BASE_ENV)
for k in ("DUNGEON_QUESTS", "DUNGEON_TOWN_APART", "DUNGEON_NPC_BRAIN", "DUNGEON_SOLO", "DUNGEON_START", "DUNGEON_MENU", "DUNGEON_RESUME",
          "DUNGEON_PARTYFORM", "DUNGEON_STRANGERS", "DUNGEON_TOWN_SIGHT", "DUNGEON_NPC_REPLY", "DUNGEON_NPC_HAIL_BRAIN",
          "DUNGEON_API_CALL_LIMIT", "DUNGEON_BRAIN_FALLBACK", "DUNGEON_BRAIN_LOG", "DUNGEON_NPC_HAIL", "DUNGEON_NPC_HAIL_STOP",
          "DUNGEON_TOWN_LIFE", "DUNGEON_TRAIL", "DUNGEON_HISTORY", "DUNGEON_NOTES"):
    os.environ.pop(k, None)

import brains                                        # noqa: E402


def _no_real_backend(prompt, model):                 # ⑧ 이중 안전핀: 어떤 길로도 진짜 백엔드는 안 부른다
    raise AssertionError("real backend must not be called in a gate")


brains._call_cli = brains._call_anthropic = brains._call_gemini = brains._call_openai = _no_real_backend
brains._call_claude = lambda prompt, model="haiku": ""   # 각본 밖 판단 = 더미 폴백(결정론)
import composed_actions as CA                        # noqa: E402
import dungeon_gm as G                               # noqa: E402
import info_guard as IG                              # noqa: E402
import repeat_signal as RS                           # noqa: E402
import scenario                                      # noqa: E402
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
    print("  %s %s%s" % ("OK  " if ok else "FAIL", name, (" — " + str(detail)[:400]) if (detail and not ok) else ""))
    if not ok:
        C.failed += 1


# ── 각본 두뇌: think_all·claude_brain·파싱·관측은 진짜 — 모델 응답 자리(_call_claude)만 각본이 채운다 ──
TL = threading.local()
LOG = {"prompts": [], "seen": [], "n": {}, "stub": 0}   # prompts [(char, n, prompt)] · seen [(char, n, depth, todo, repeat 사본, obs 사본)]
SCRIPT = {"fn": None}
_ORIG_BRAIN = brains.claude_brain


def _brain(obs, char="?", bot=None, roster=None, solo=False):
    TL.char, TL.obs, TL.bot = str(char), obs, bot
    return _ORIG_BRAIN(obs, char, bot, roster, solo)


def _call(prompt, model="haiku"):
    c = TL.char
    LOG["n"][c] = n = LOG["n"].get(c, 0) + 1
    LOG["stub"] += 1
    LOG["prompts"].append((c, n, prompt))
    rep = TL.bot.get("repeat")
    LOG["seen"].append((c, n, TL.obs.get("depth"), TL.bot.get("todo"), json.loads(json.dumps(rep)) if rep else None,
                        json.loads(json.dumps({k: TL.obs.get(k) for k in ("todo", "repeat") if k in TL.obs}))))
    return json.dumps({"reason": "게이트 각본", **SCRIPT["fn"](c, n, TL.obs, TL.bot)}, ensure_ascii=False)


@contextlib.contextmanager
def scripted(fn, fresh=True):
    if fresh:
        LOG["prompts"], LOG["seen"], LOG["n"] = [], [], {}
    old = (brains.claude_brain, brains._call_claude)
    SCRIPT["fn"] = fn
    brains.claude_brain, brains._call_claude = _brain, _call
    try:
        yield
    finally:
        brains.claude_brain, brains._call_claude = old


def prompts_of(c):
    return {n: p for c_, n, p in LOG["prompts"] if c_ == c}


def lines_with(p, frag):
    return [ln for ln in p.split("\n") if frag in ln]


# ── 단위 재료: 관측(그 몸이 보는 것) ──
NPC_F = {"id": "f3", "name": "주점 주인", "type": "npc", "dist": 1}


def ob(**kw):
    o = {"hp": 14, "maxhp": 14, "gold": 5, "inventory": 0, "potions": 0, "gear": {"weapon": None, "armor": None}, "messages": [],
         "sights": {"features": [dict(NPC_F)]}}
    o.update(kw)
    return o


GOTO = {"type": "goto", "target": "f3", "result": "arrived"}
GOTO_WALK = [{"type": "goto", "target": "f3", "result": "pathed", "len": 3}, {"type": "walk", "target": "f3", "result": "walking"},
             {"type": "walk", "target": "f3", "result": "arrived"}]
TALK = {"type": "interact", "target": "f3", "result": "npc_talk", "npc": "주점 주인", "talk": "away"}
MISS = {"type": "search", "target": "f3", "result": "no_effect", "found": []}
FOUND = {"type": "search", "target": "f3", "result": "searched", "found": [{"name": "숨은 문"}]}
SPOT = {"type": "walk", "target": "f3", "result": "encounter", "monsters": [{"kind": "고블린", "id": "m1"}]}
D_GOTO, D_USE, D_SEARCH = {"type": "goto", "target": "f3"}, {"type": "use", "target": "f3"}, {"type": "search", "target": "f3"}
LINE = lambda t, frm="npc:주점 주인", me=True: {"from": frm, "text": t, "to": "1", **({"to_me": True} if me else {})}


def chain(b):
    """몸의 연속 칸(없으면 빈 dict) — 변이로 칸이 없어져도 검사가 KeyError 로 죽지 않고 FAIL 로 남게."""
    return (b or {}).get("repeat") or {}


def drive(seq, first=None, bot=None):
    """[(판단, 그 판단 뒤의 관측)] 를 think_all 순서(관측을 보고 → 판단 → 다음 관측)로 돌린다. 반환 = 판단마다 그 직전 관측에 실린 repeat + 마지막 관측의 것."""
    b = bot if bot is not None else {"char": "1"}
    obs, reps = first or ob(last=None), []
    for dec, nxt in seq:
        RS.see(b, obs)
        reps.append(obs.get("repeat"))
        RS.step(b, dec, obs)
        obs = nxt
    RS.see(b, obs)
    reps.append(obs.get("repeat"))
    return reps, b


def stamp(rec, i):
    """결과 기록에 판단마다 갈리는 장부·자리 칸(틱·행동 번호·판정 요약·걸음 수·좌표)을 단다 — 비교에서 빠져야 하는 칸(RS._VOLATILE)."""
    return {**rec, "turn": 100 + i, "parent_action_id": "d1:t%d:a%d" % (100 + i, i), "resolution": {"phase": "resolved", "step": i},
            "len": i % 3, "to": [i, i + 1]}


def loop_seq(n, decs=(D_GOTO, D_USE), outs=None):
    """같은 대상(f3)에 동사를 돌려 가며 n 번 — 결과는 동사마다 늘 같다(goto = 도착 · use = 등 돌린 NPC 의 사실 · search = 허탕) — 장부·자리 칸만 판단마다 다르다."""
    outs = outs or {"goto": GOTO, "use": TALK, "search": MISS}
    return [(decs[i % len(decs)], ob(last=stamp(outs[decs[i % len(decs)]["type"]], i))) for i in range(n)]


print("── ① 연속 세기(열쇠·5·10번째·끊김)")
check("① 열쇠: 동사 무관 대상 ID · wait = WAIT · 탐색·휴식·대상 없는 행동 = 끊김(None)",
      [RS.key_of(x) for x in (D_GOTO, D_USE, D_SEARCH, {"type": "attack", "target": "m1"}, {"type": "give", "target": "b2", "item": "i1"},
                              {"type": "wait"}, {"type": "wait", "say": "누구 없소"}, {"type": "explore", "target": "w3_1"}, {"type": "rest"},
                              {"type": "party_leave"}, {"type": "use", "target": "self", "item": "i1"}, {"type": "goto", "target": "@3,4"})]
      == ["f3", "f3", "f3", "m1", "b2", RS.WAIT, RS.WAIT, None, None, None, "self", "@3,4"]
      and RS.key_of({"type": "search", "target": "b1"}, "1") == "self" and RS.key_of({"type": "goto", "target": "b2"}, "1") == "b2")
check("① 조합형이 self 를 행동자 ID(b1)로 풀어 둬도 자기 자신은 한 연속 'self'(사람 호칭으로 그리지 않는다)",
      drive([({"type": "search", "target": "b1" if i % 2 else "self"}, ob(last=dict(MISS))) for i in range(5)])[0][5] == {"n": 5, "target": "self", "same": True})
reps1, b1 = drive(loop_seq(15, (D_GOTO, D_USE, D_SEARCH)))
check("① goto·use·search 를 섞어도 같은 대상이면 한 연속 — 5번째·10번째 판단 뒤의 다음 관측에만(4번째 뒤 없음 · 11~15 없음 · 그 뒤 5회마다 없음) ·"
      " 5번째엔 search 결과가 한 번뿐(새 정보 — SAME 없음), 10번째엔 동사마다 같은 결과가 되풀이됐다(SAME)",
      [i for i, r in enumerate(reps1) if r] == [5, 10] and reps1[5] == {"n": 5, "target": "f3"}
      and reps1[10] == {"n": 10, "target": "f3", "same": True} and chain(b1).get("n") == 15, reps1)
b1o = {"char": "1"}
drive(loop_seq(4), bot=b1o)
RS.step(b1o, D_USE, ob(last=stamp(TALK, 4)))         # 5번째
o1a, o1b = ob(last=stamp(TALK, 5)), ob(last=stamp(TALK, 5))
RS.see(b1o, o1a)
RS.see(b1o, o1b)                                     # 판단 없이 관측이 한 번 더(다시 묻기 등)
check("① 한 번만 — 신호는 내보내고 비운다(판단 없이 다시 본 관측엔 다시 없다)",
      o1a.get("repeat") == {"n": 5, "target": "f3", "same": True} and "repeat" not in o1b and chain(b1o).get("n") == 5 and "due" not in chain(b1o),(o1a.get("repeat"), o1b.get("repeat")))
seq_b = loop_seq(3) + [({"type": "use", "target": "f4"}, ob(last=dict(MISS)))] + loop_seq(4)
reps_b, bb = drive(seq_b)
check("① 대상이 바뀌면 끊긴다: f3 ×3 → f4 → f3 ×4 = 4번째(신호 없음)", not any(reps_b) and (bb.get("repeat") or {}).get("n") == 4
      and (bb.get("repeat") or {}).get("key") == "f3", reps_b)
reps_b2, _ = drive(loop_seq(1), bot=bb, first=ob(last=stamp(TALK, 9)))
check("① …이어서 f3 한 번 더 = 새 연속의 5번째 → 신호", reps_b2[-1] == {"n": 5, "target": "f3", "same": True}, reps_b2)
for brk in ({"type": "explore", "target": "w9_1"}, {"type": "rest"}, {"type": "wait"}, {"type": "party_leave"}):
    rb, bx = drive(loop_seq(4) + [(brk, ob(last=None))] + loop_seq(4))
    check("① 다른 행동(%s)이 끼면 끊긴다 — 4 + 끼어듦 + 4 = 신호 없음" % brk["type"], not any(rb) and (bx.get("repeat") or {}).get("n") == 4, (rb, bx.get("repeat")))
W_OUT = ob(last={"type": "walk", "result": "wait_bored", "ticks": 5})
rw, bw = drive([({"type": "wait"}, ob(last={"type": "walk", "result": "wait_bored", "ticks": 5})) for _ in range(10)], first=W_OUT)
check("① 기다리기 연속을 따로 센다(대상 없음) — 5·10번째", [i for i, r in enumerate(rw) if r] == [5, 10] and rw[5] == {"n": 5, "wait": True, "same": True}, rw)
rwt, bwt = drive([({"type": "wait"}, ob(last=None)), ({"type": "wait"}, ob(last=None)), (D_GOTO, ob(last=dict(GOTO)))] + loop_seq(3))
check("① 기다리기와 대상 연속은 서로 다른 연속 — wait ×2 → f3 ×4 = 4번째", not any(rwt) and (bwt.get("repeat") or {}).get("key") == "f3"
      and (bwt.get("repeat") or {}).get("n") == 4, bwt.get("repeat"))
bp = {"char": "1"}
drive(loop_seq(4), bot=bp)
RS.step(bp, D_SEARCH, None)                          # 5번째(due 5)
RS.step(bp, D_SEARCH, None)                          # 작정 수가 이어졌다 — 관측 없이 6번째
op = ob(last=dict(MISS))
RS.see(bp, op)
check("① 작정 수가 이어 5번째 신호를 실을 관측이 없었으면 늦게 싣지 않는다(6번째 뒤 관측엔 없음)", "repeat" not in op and (bp.get("repeat") or {}).get("n") == 6,
      (op.get("repeat"), bp.get("repeat")))
rp, _ = drive(loop_seq(4), bot=bp, first=ob(last=dict(MISS)))
check("① …그 뒤 10번째는 그대로 뜬다", rp[-1] == {"n": 10, "target": "f3", "same": True}, rp)
bn = {"char": "1"}
seq_n = [({"type": "goto", "target": "b2"}, ob(last=None, people={}, sights={"bots": [{"id": "b2", "char": "2", "dist": 1}]}))
         for _ in range(4)] + [({"type": "bond", "target": "b2", "form": "어깨를 두드린다"},
                               ob(last=None, people={"b2": {"name": "카야"}}, sights={"bots": [{"id": "b2", "char": "2", "dist": 1}]}))]
rn, bn = drive(seq_n, first=ob(last=None, people={}, sights={"bots": [{"id": "b2", "char": "2", "dist": 1}]}))
check("① 사람 대상: 도중에 이름을 알게 돼도(호칭 낯선 사람 → 카야) 열쇠는 ID(b2) — 한 연속 5번째", rn[-1] == {"n": 5, "target": "b2", "same": True}, rn)

print("── ② '달라진 것' — 몸·같은 동사의 결과·대사·발견")


def fifth(mut_at=2, **change):
    """f3 연속 5번 — mut_at 번째 판단 뒤의 관측만 change 로 바꾼다. 5번째 신호를 돌려준다."""
    seq = loop_seq(5)
    d_, o_ = seq[mut_at - 1]
    o_ = dict(o_)
    for k_, v_ in change.items():
        o_[k_] = v_(o_) if callable(v_) else v_
    seq[mut_at - 1] = (d_, o_)
    return drive(seq)[0][5]


check("② 아무것도 안 바뀌면 SAME(골드·HP·물약·결과·말 그대로)", fifth() == {"n": 5, "target": "f3", "same": True}, fifth())
for nm_, ch_ in (("골드 5 → 6(판 것)", {"gold": 6}), ("HP 14 → 12", {"hp": 12}), ("물약 0 → 1", {"potions": 1}), ("보물 0 → 1", {"inventory": 1}),
                 ("장비(단검을 들었다)", {"gear": {"weapon": {"name": "단검", "bonus": 1}, "armor": None}}),
                 ("상태 태그(출혈)", {"status": [{"tag": "출혈", "n": 1, "by": "함정", "since": 3}]}),
                 ("맡은 의뢰 진행", {"quests": [{"title": "고블린 소탕", "n": 1, "need": 3}]}),
                 ("파티원", {"partyform": {"mine": ["2"], "here": True}})):
    r_ = fifth(**ch_)
    check("② 몸이 바뀌면 SAME 없음 — %s" % nm_, r_ == {"n": 5, "target": "f3"}, r_)
r_ = fifth(mut_at=5, gold=6)
check("② 5번째 판단의 결과(신호가 실리는 관측)에서 바뀌어도 SAME 없음", r_ == {"n": 5, "target": "f3"}, r_)
r_ = drive([(d_, ob(last=o_["last"], gold=6)) for d_, o_ in loop_seq(5)])[0][5]
check("② 첫 판단의 결과로 바뀐 몸이 그대로 이어져도(골드 5 → 6 → 6 …) 달라짐 — 연속 첫 판단 때의 관측과 맞댄다", r_ == {"n": 5, "target": "f3"}, r_)
st0 = [{"tag": "출혈", "n": 1, "by": "함정", "since": 3, "left": 4}]
seq_s = [(D_SEARCH, ob(last=dict(MISS), status=[{**st0[0], "left": 4 - i}])) for i in range(5)]
r_ = drive(seq_s, first=ob(last=None, status=st0))[0][5]
check("② 상태 태그의 이름·겹친 수만 본다(남은 틱이 줄어드는 것은 변화가 아니다)", r_ == {"n": 5, "target": "f3", "same": True}, r_)
r_ = drive([(D_SEARCH, ob(last=dict(MISS))) for _ in range(5)])[0][5]
check("② search 허탕 ×5 = SAME", r_ == {"n": 5, "target": "f3", "same": True}, r_)
r_ = drive([(D_SEARCH, ob(last=dict(FOUND if i == 0 else MISS))) for i in range(5)])[0][5]
check("② 첫 search 가 찾아냈다(그 뒤 허탕) — 발견 = 달라짐", r_ == {"n": 5, "target": "f3"}, r_)
r_ = drive([(D_SEARCH, ob(last=dict(FOUND if i == 3 else MISS))) for i in range(5)])[0][5]
check("② 넷째 search 가 찾아냈다 — 같은 동사의 결과가 바뀜", r_ == {"n": 5, "target": "f3"}, r_)
r_ = drive([(D_GOTO, ob(trail=[dict(x) for x in GOTO_WALK] + ([dict(SPOT)] if i == 2 else []), last=dict(GOTO_WALK[-1]))) for i in range(5)])[0][5]
check("② 걷다가 몬스터를 봤다(발견 꼬리표) — 달라짐", r_ == {"n": 5, "target": "f3"}, r_)
r_ = drive([(D_GOTO, ob(trail=[dict(x) for x in GOTO_WALK] + [dict(SPOT)], last=dict(GOTO_WALK[-1])))]
           + [(D_SEARCH, ob(last=dict(MISS))) for _ in range(4)])[0][5]
check("② 한 번뿐인 동사의 결과에 발견이 있어도 달라짐 — goto 1번(걷다 몬스터를 봄) + search 허탕 4번(맞댈 같은 동사가 없어도 발견은 변화)",
      r_ == {"n": 5, "target": "f3"}, r_)
r_ = drive([(D_SEARCH, ob(last=dict(FOUND)))] + [(D_GOTO, ob(last=dict(GOTO))) for _ in range(4)])[0][5]
check("② search 1번이 찾아내고 goto 4번 — 찾아낸 것 = 변화", r_ == {"n": 5, "target": "f3"}, r_)
r_ = drive([(D_GOTO, ob(trail=[dict(x) for x in GOTO_WALK] + [dict(SPOT)], last=dict(GOTO_WALK[-1]))) for _ in range(5)])[0][5]
check("② 갈 때마다 걷다가 몬스터를 본다(같은 발견이 되풀이돼도 발견은 변화 — 결과가 같아 보여도)", r_ == {"n": 5, "target": "f3"}, r_)
r_ = drive([(D_SEARCH, ob(last=dict(FOUND))) for _ in range(5)])[0][5]
check("② search 가 매번 같은 것을 찾아냈다고 한다 — 찾아낸 것 = 변화", r_ == {"n": 5, "target": "f3"}, r_)
r_ = drive([(D_GOTO, ob(trail=[dict(x) for x in GOTO_WALK] if i % 2 == 0 else [dict(GOTO)], last=dict(GOTO))) for i in range(5)])[0][5]
check("② 걸어서 닿음(걸음·이동 시작·'f3 곁')과 이미 곁('f3 — 이미 곁')은 같은 결과 — 걸음 수·시작·도착 꼬리표는 보지 않는다", r_ == {"n": 5, "target": "f3", "same": True}, r_)
r_ = drive([(D_USE, ob(last=dict(TALK), messages=[LINE("어서 오게")])) for _ in range(5)])[0][5]
check("② 대상이 같은 말을 되풀이 = SAME(대사 내용이 그대로)", r_ == {"n": 5, "target": "f3", "same": True}, r_)
r_ = drive([(D_USE, ob(last=dict(TALK), messages=[LINE("어서 오게" if i < 3 else "무엇을 찾나")])) for i in range(5)])[0][5]
check("② 대상의 말이 바뀌었다 — 대사 내용 변화", r_ == {"n": 5, "target": "f3"}, r_)
r_ = drive([(D_USE, ob(last=dict(TALK), messages=[LINE("어서 오게" if i < 3 else "무엇을 찾나", me=False)])) for i in range(5)])[0][5]
check("② 대상(마을 사람)이 한 말은 나를 지목하지 않아도 본다 — 바뀌면 달라짐", r_ == {"n": 5, "target": "f3"}, r_)
r_ = drive([(D_USE, ob(last=dict(TALK), messages=[LINE("같이 던전 가자", frm="2")] if i == 1 else [])) for i in range(5)])[0][5]
check("② 다른 사람이 내게 한 말(지목) — 달라짐", r_ == {"n": 5, "target": "f3"}, r_)
r_ = drive([(D_USE, ob(last=dict(TALK), messages=[LINE("오늘 날씨 좋네", frm="2", me=False)] if i == 1 else [])) for i in range(5)])[0][5]
check("② 내게 하지 않은 남의 잡담은 보지 않는다(대상도 아니다) — SAME", r_ == {"n": 5, "target": "f3", "same": True}, r_)
seq_b2 = [({"type": "goto", "target": "b2"}, ob(last=None, messages=[LINE("따라와" if i < 2 else "여기서 쉬자", frm="2", me=False)])) for i in range(5)]
r_ = drive(seq_b2)[0][5]
check("② 사람 대상: 그 사람이 한 말(나를 지목하지 않아도)이 바뀌면 달라짐", r_ == {"n": 5, "target": "b2"}, r_)
r_ = drive([({"type": "wait"}, ob(last={"type": "walk", "result": "wait_met" if i == 2 else "wait_bored", "allies": ["2"]})) for i in range(5)],
           first=W_OUT)[0][5]
check("② 기다리기: 기다리던 동료가 왔다(기다림 끝이 '아무도 안 옴'과 다르다) — 달라짐", r_ == {"n": 5, "wait": True}, r_)
# p0515b(Codex p0515r 필수 ①): 대상의 상태 · 한 번뿐인 결과 · 꼬리표 요약이 놓치는 결과 원문
HIT = {"type": "attack", "target": "고블린", "target_id": "m1", "result": "attack", "hit": True, "dmg": 3}
MISSED = {"type": "attack", "target": "고블린", "target_id": "m1", "result": "attack", "hit": False}
MON = lambda hp, dist=1: {"monsters": [{"id": "m1", "kind": "고블린", "hp": hp, "state": "HUNTING", "aware": True, "dist": dist, "bearing": "E"}]}
D_ATK = {"type": "attack", "target": "m1"}
r_ = drive([(D_ATK, ob(last=stamp(HIT, i), sights=MON(12 - 3 * (i + 1)))) for i in range(5)], first=ob(last=None, sights=MON(15)))[0][5]
check("② 나는 무사하고 대상(몬스터)에게 같은 피해를 이어 입힘 — 결과 기록은 같아도 대상 HP 가 준다 = 달라짐", r_ == {"n": 5, "target": "m1"}, r_)
r_ = drive([(D_ATK, ob(last=stamp(MISSED, i), sights=MON(15, 1 + i % 2))) for i in range(5)], first=ob(last=None, sights=MON(15)))[0][5]
check("② 대상에게 빗나가기만 했다(대상 HP·상태 그대로 · 거리만 1↔2) — SAME", r_ == {"n": 5, "target": "m1", "same": True}, r_)
SB2 = lambda vis: {"bots": [{"id": "b2", "char": "2", "dist": 2, "hp": 10, "maxhp": 10}]} if vis else {}
r_ = drive([({"type": "goto", "target": "b2"}, ob(last=None, sights=SB2(i < 3))) for i in range(5)], first=ob(last=None, sights=SB2(True)))[0][5]
check("② 사람 대상이 보이다가 안 보인다 — 달라짐", r_ == {"n": 5, "target": "b2"}, r_)
r_ = drive([({"type": "goto", "target": "b2"}, ob(last=None, sights={"bots": [{"id": "b2", "char": "2", "dist": 2, "hp": 10 - (i == 3), "maxhp": 10}]}))
            for i in range(5)], first=ob(last=None, sights=SB2(True)))[0][5]
check("② 사람 대상의 HP 가 바뀌었다 — 달라짐", r_ == {"n": 5, "target": "b2"}, r_)
FTAG = lambda n: {"features": [{**NPC_F, "dist": 1 + n % 2, "tag": {"verb": "말 걸어 봄", "n": n}}]}
r_ = drive([(D_USE, ob(last=stamp(TALK, i), sights=FTAG(i + 1))) for i in range(5)], first=ob(last=None, sights=FTAG(0)))[0][5]
check("② 피처 대상의 오브젝트 태그 횟수(말 걸어 봄 ×n)·거리는 보지 않는다 — 그 판단의 메아리 — SAME", r_ == {"n": 5, "target": "f3", "same": True}, r_)
r_ = drive([(D_USE, ob(last=stamp(TALK, i), sights={"features": [{**NPC_F, "away": i >= 2}]})) for i in range(5)])[0][5]
check("② 마을 사람이 등을 돌렸다(피처의 등 돌림 표시) — 달라짐", r_ == {"n": 5, "target": "f3"}, r_)
r_ = drive([(D_GOTO, ob(last=stamp(GOTO, i))) for i in range(4)] + [(D_USE, ob(last=stamp(TALK, 4)))])[0][5]
check("② goto 4번 뒤 첫 use 로 새 결과를 얻었다(한 번뿐인 결과 = 새 정보) — SAME 없음", r_ == {"n": 5, "target": "f3"}, r_)
r_ = drive([(D_GOTO, ob(last=stamp(GOTO, i))) for i in range(3)] + [(D_USE, ob(last=stamp(TALK, i))) for i in (3, 4)])[0][5]
check("② goto 3번 + use 2번(같은 결과가 되풀이) — SAME", r_ == {"n": 5, "target": "f3", "same": True}, r_)
r_ = drive([(D_GOTO, ob(last=stamp(GOTO, 0)))] + [(D_USE, ob(last=stamp(TALK, i))) for i in range(1, 5)])[0][5]
check("② goto 1번(도착뿐 — 빈 결과는 한 번이어도 새 정보가 아니다) + use 4번 — SAME", r_ == {"n": 5, "target": "f3", "same": True}, r_)
TXT = "오래된 석판이다. 첫 줄은 이 마을을 세운 사람들의 이름을 적어 두었고, 끝줄은 "
READ = lambda tail: {"type": "interact", "target": "f5", "result": "read", "what": "석판", "verb": "read", "text": TXT + tail}
D_READ = {"type": "use", "target": "f5"}
r_ = drive([(D_READ, ob(last=stamp(READ("북쪽 문을 가리킨다." if i != 3 else "남쪽 우물을 가리킨다."), i))) for i in range(5)])[0][5]
check("② 읽은 글이 앞 30자는 같고 뒷부분만 다르다 — 꼬리표 요약('읽음 석판 \"앞 30자\"')이 아니라 결과 원문을 맞댄다 = 달라짐",
      r_ == {"n": 5, "target": "f5"} and len(TXT) > 30, r_)
r_ = drive([(D_READ, ob(last=stamp(READ("북쪽 문을 가리킨다."), i))) for i in range(5)])[0][5]
check("② 같은 글을 다섯 번 읽었다(장부·자리 칸만 다르다) — SAME", r_ == {"n": 5, "target": "f5", "same": True}, r_)
# p0519(c16 run_metrics_v0 §5 — 0.5.13 수나 석상 search 26연속에 '변화 없음'이 한 번도 안 붙었다 · Codex p0515rr 권장): 결과가 아닌 궤적 칸
#   (생략 표식 gap · 내가 한 말 said) · 굴림 수치 · 작정 표식 · 내 몸짓 서술은 맞대지 않는다 — 실제 결과·대상의 말·남이 내게 한 몸짓은 그대로 본다
F25 = {"features": [{"id": "f25", "name": "석상", "type": "statue", "dist": 1}]}
MISS25 = {"type": "search", "target": "f25", "result": "no_effect", "found": [], "reason_code": "no_new_information"}
D_S25 = {"type": "search", "target": "f25"}
GAP = {"type": "gap", "n": 9}
CAME = {"type": "walk", "target": "f25", "result": "arrived"}
SAID = lambda t, to="all": {"type": "said", "to": to, "kind": "잡담", "heard": ["2"], "text": t[:40]}
TALKS = ("석상아, 무슨 비밀을 숨겼니?", "여기 뭔가 더 있을 것 같아요~", "한 번만 더 볼게요!", "이상하네, 분명 뭔가 있는데", "포기 못 해요",
         "다들 이리 와 봐요!", "석상 뒤쪽은요?", "손잡이 같은 건 없네", "조금만 더요", "역시 아무것도 없나")
r_ = drive([(D_S25, ob(trail=([GAP, dict(CAME)] if i == 0 else []) + [stamp(MISS25, i)], sights=F25)) for i in range(5)], first=ob(last=None, sights=F25))[0][5]
check("② 긴 접근 뒤 첫 결과에만 생략 표식(gap)이 붙고 같은 허탕이 이어진다 — 생략 표식은 결과가 아니다 = SAME",
      r_ == {"n": 5, "target": "f25", "same": True}, r_)
r_ = drive([(D_USE, ob(trail=[stamp(TALK, i), SAID(TALKS[i], "npc:주점 주인")], messages=[LINE("어서 오게")])) for i in range(5)])[0][5]
check("② 말만 바꿔 가며 같은 대상에 되풀이(내가 한 말 said 의 글이 매번 다르다 · 대상의 대답·결과는 그대로) — SAME",
      r_ == {"n": 5, "target": "f3", "same": True}, r_)
r_ = drive([(D_USE, ob(trail=[stamp(TALK, i), SAID(TALKS[i], "npc:주점 주인")], messages=[LINE("어서 오게" if i < 3 else "무엇을 찾나")])) for i in range(5)])[0][5]
check("② 말만 바꿔 되풀이해도 대상의 대답이 바뀌면 달라짐(내가 한 말만 뺀다)", r_ == {"n": 5, "target": "f3"}, r_)
reps_, _ = drive([(D_S25, ob(trail=([GAP, dict(CAME)] if i == 0 else []) + [stamp(MISS25, i), SAID(TALKS[i])], sights=F25)) for i in range(10)],
                 first=ob(last=None, sights=F25))
check("② 석상 장면(0.5.13 수나): 긴 접근 + 동료에게 말하며 같은 search 허탕 ×10 — 5번째·10번째 둘 다 SAME",
      [r for r in reps_ if r] == [{"n": 5, "target": "f25", "same": True}, {"n": 10, "target": "f25", "same": True}], reps_)
r_ = drive([(D_READ, ob(trail=([GAP] if i == 0 else []) + [stamp(READ("북쪽 문을 가리킨다." if i != 3 else "남쪽 우물을 가리킨다."), i), SAID(TALKS[i])]))
            for i in range(5)])[0][5]
check("② 생략 표식·내가 한 말이 붙어도 결과 원문은 맞댄다 — 넷째에 읽은 글 뒷부분이 다르다 = 달라짐", r_ == {"n": 5, "target": "f5"}, r_)
MISS_R = lambda i: {**MISSED, "roll": 2 + i, "mod": 3, "total": 5 + i, "ac": 13,
                    "combat_roll": {"rolls": [2 + i], "mode": "normal", "roll": 2 + i, "mod": 3, "total": 5 + i, "dc": 13, "success": False}}
r_ = drive([(D_ATK, ob(last=stamp(MISS_R(i), i), sights=MON(15))) for i in range(5)], first=ob(last=None, sights=MON(15)))[0][5]
check("② 굴림 수치(굴린 눈·합·굴림 기록)만 다른 빗나감 ×5 — 같은 빗나감 = SAME(Codex p0515rr 권장)", r_ == {"n": 5, "target": "m1", "same": True}, r_)
r_ = drive([(D_ATK, ob(last=stamp({**MISS_R(i), "hit": True} if i == 3 else MISS_R(i), i), sights=MON(15))) for i in range(5)],
           first=ob(last=None, sights=MON(15)))[0][5]
check("② 굴림 수치는 빼도 성패는 맞댄다 — 빗나감 사이에 한 번 명중(결과 기록의 성패 칸만 다르다 · 피해·대상 HP 는 그대로 둔 단위 사례) = 달라짐",
      r_ == {"n": 5, "target": "m1"}, r_)
SK_SAVED = lambda i: {"type": "s_fire", "target": "m1", "result": "skill", "skill_id": "s_fire", "skill_name": "불꽃", "skill_cost": 1, "hit": True,
                      "skill_dc": 12, "skill_roll": {"rolls": [9 + i], "mode": "normal", "roll": 9 + i, "mod": 0, "total": 9 + i, "dc": 12, "success": True},
                      "effects": [{"type": "damage", "save": {"rolls": [9 + i], "roll": 9 + i, "mod": 0, "total": 9 + i, "dc": 12, "success": True},
                                   "dice": "1d6", "rolls": [1 + i], "value": 1 + i, "mode": "dice", "applied": False, "reason": "saved"}],
                      "penalties": [], "skill_spent": True}
r_ = drive([({"type": "s_fire", "target": "m1"}, ob(last=stamp(SK_SAVED(i), i), sights=MON(15))) for i in range(5)], first=ob(last=None, sights=MON(15)))[0][5]
check("② 스킬: 대상이 매번 내성으로 버텼다 — 스킬 굴림·효과 칸의 내성 굴림·주사위 눈만 다르다 = SAME", r_ == {"n": 5, "target": "m1", "same": True}, r_)
r_ = drive([(D_S25, ob(trail=[stamp(MISS25, i)] + ([{**stamp(MISS25, i), "plan": True}] if i % 2 else []), sights=F25)) for i in range(5)],
           first=ob(last=None, sights=F25))[0][5]
check("② 작정 수로 한 같은 허탕(궤적의 plan 표식)도 같은 결과 = SAME", r_ == {"n": 5, "target": "f25", "same": True}, r_)
FORMS = ("어깨를 두드린다", "손을 흔든다", "하이파이브", "등을 토닥인다", "웃어 보인다")
BOND = lambda i: {"type": "bond", "target": "b2", "form": FORMS[i], "result": "done", "to": "2"}
D_BOND = {"type": "bond", "target": "b2"}
r_ = drive([(D_BOND, ob(last=None, trail=[stamp(BOND(i), i)], sights=SB2(True))) for i in range(5)], first=ob(last=None, sights=SB2(True)))[0][5]
check("② 같은 사람에게 몸짓만 바꿔 친목 ×5(내 몸짓 서술 = 판단의 메아리) — SAME", r_ == {"n": 5, "target": "b2", "same": True}, r_)
BONDED = lambda f: {"type": "bonded", "from": "2", "form": f}
r_ = drive([(D_BOND, ob(last=None, trail=[stamp(BOND(i), i), BONDED("손을 마주 잡는다")], sights=SB2(True))) for i in range(5)],
           first=ob(last=None, sights=SB2(True)))[0][5]
r2_ = drive([(D_BOND, ob(last=None, trail=[stamp(BOND(i), i), BONDED("손을 마주 잡는다" if i < 3 else "고개를 돌린다")], sights=SB2(True))) for i in range(5)],
            first=ob(last=None, sights=SB2(True)))[0][5]
check("② 상대가 내게 한 몸짓(bonded)의 글은 본다 — 같은 몸짓이 되풀이되면 SAME · 상대의 몸짓이 바뀌면 달라짐",
      r_ == {"n": 5, "target": "b2", "same": True} and r2_ == {"n": 5, "target": "b2"}, (r_, r2_))

print("── ③ 렌더 — 관측 꼬리표 한 줄(무발견 신호와 같은 절)")


REP_HEAD = "- 반복 중: "                             # p0515d 꼬리표(민옥 문구) — 관측 줄 머리(지침 줄은 '- `반복 중: …'이라 갈린다)


def rline(rep, names=None, **kw):
    w_ = brains._wire(ob(repeat=rep, **kw), names or {})
    got = [ln for ln in w_.split("\n") if ln.startswith(REP_HEAD)]
    return got[0] if len(got) == 1 else got, w_


def reps_in(p):
    """프롬프트의 반복 신호 줄들."""
    return [ln for ln in p.split("\n") if ln.startswith(REP_HEAD)]


R5 = {"n": 5, "target": "f3", "same": True}
check("③ 대상이 있으면 '반복 중: <이름> <ID> ×5 · 변화 없음'(p0515d 민옥 꼬리표 — 옛 문장·'다섯 번째' 없음)",
      rline(R5)[0] == "- 반복 중: 주점 주인 f3 ×5 · 변화 없음", rline(R5)[0])
check("③ 곁 여부는 꼬리표에 안 나온다(4칸 = 1칸과 같은 꼴) · ×10 · 달라짐이 있으면 ' · 변화 없음' 없음",
      rline({"n": 10, "target": "f3"}, sights={"features": [{**NPC_F, "dist": 4}]})[0] == "- 반복 중: 주점 주인 f3 ×10"
      and rline({"n": 10, "target": "f3"})[0] == "- 반복 중: 주점 주인 f3 ×10",
      rline({"n": 10, "target": "f3"}, sights={"features": [{**NPC_F, "dist": 4}]})[0])
check("③ 지금 안 보이는 대상 — ID 그대로", rline({"n": 5, "target": "f9"})[0] == "- 반복 중: f9 ×5", rline({"n": 5, "target": "f9"})[0])
SB = {"bots": [{"id": "b2", "char": "2", "dist": 1, "hp": 10, "maxhp": 10}]}
check("③ 사람(이름 층): 아는 이름 '카야(봇2)' — 다른 기억 줄과 같은 호칭",
      rline({"n": 5, "target": "b2"}, {"2": "카야"}, sights=SB)[0] == "- 반복 중: 카야(봇2) ×5", rline({"n": 5, "target": "b2"}, {"2": "카야"}, sights=SB)[0])
check("③ 사람(인물 기록 판, 이름 모름): '낯선 사람(봇2)' — 시트 실명이 새지 않는다",
      rline({"n": 5, "target": "b2"}, {}, sights=SB, people={})[0] == "- 반복 중: 낯선 사람(봇2) ×5",
      rline({"n": 5, "target": "b2"}, {}, sights=SB, people={})[0])
check("③ self — '반복 중: 제자리 ×5 · 변화 없음'", rline({"n": 5, "target": "self", "same": True})[0] == "- 반복 중: 제자리 ×5 · 변화 없음",
      rline({"n": 5, "target": "self", "same": True})[0])
check("③ 기다리기 — '반복 중: 기다리기 ×10 · 변화 없음'", rline({"n": 10, "wait": True, "same": True})[0] == "- 반복 중: 기다리기 ×10 · 변화 없음",
      rline({"n": 10, "wait": True, "same": True})[0])
check("③ 계단 — 출구 라벨(계단(exit) · 보스층 워프게이트(exit))",
      rline({"n": 5, "target": "exit"}, sights={"exit": {"dist": 0}})[0] == "- 반복 중: 계단(exit) ×5"
      and rline({"n": 5, "target": "exit"}, sights={"exit": {"dist": 6, "gate": True}})[0] == "- 반복 중: 워프게이트(exit) ×5")
check("③ 몬스터 — 관측의 이름(모르는 종은 도감이 가린 '낯선 짐승' 그대로)",
      rline({"n": 5, "target": "m1"}, sights={"monsters": [{"id": "m1", "kind": "낯선 짐승", "dist": 3, "bearing": "E", "state": "WANDERING", "hp": 5}]})[0]
      == "- 반복 중: 낯선 짐승 m1 ×5")
check("③ 조합형 대상 목록에만 있는 것(진열 상품 g1) — 목록의 이름 · '@x,y' = 마지막 본 자리",
      rline({"n": 5, "target": "g1"}, targets=[{"id": "g1", "name": "회복 물약", "kind": "good"}])[0] == "- 반복 중: 회복 물약 g1 ×5"
      and rline({"n": 5, "target": "@3,4"})[0] == "- 반복 중: 마지막 본 자리 ×5")
_l, w3 = rline(R5, dry=25, last=None)
L3 = w3.split("\n")
h3 = L3.index("## 네 직전 판단과 그 결과 (네 자신의 기억)") if "## 네 직전 판단과 그 결과 (네 자신의 기억)" in L3 else -1
dry3 = L3.index("- 한참을 걸었는데 새로 보이는 것이 없다 — 아는 자리만 이어진다") if "- 한참을 걸었는데 새로 보이는 것이 없다 — 아는 자리만 이어진다" in L3 else -1
check("③ 자리: '네 직전 판단과 그 결과' 절 — 무발견 신호 바로 다음 줄(같은 꼴의 사실 줄) · 직전 판단·결과가 없어도 절이 선다",
      h3 >= 0 and dry3 > h3 and L3[dry3 + 1] == _l and "# 기억 — 무엇을 기억하나" in L3, L3[h3:h3 + 4] if h3 >= 0 else w3[:300])
w3b = brains._wire(ob(last=None))
check("③ 신호가 없으면 줄도 없다", not reps_in(w3b) and "반복 중" not in w3b)
BAD = ("해라", "하라", "하지 마", "말라", "그만", "바꿔", "바꾸", "다른 일", "다른 걸", "다른 것을", "해 봐", "해보", "하자", "할 것", "해야", "멈춰", "?", "!")
words = list(RS.LINES.values()) + [RS.SAME]
GL_REP = "- `반복 중: 대상 ×N`은 같은 대상에 이어서 한 판단 수다. `변화 없음`은 그동안 결과가 달라지지 않았다는 뜻이다."   # p0515d 민옥 문구(DECISIONS 10-15) 글자 그대로
GL_TODO = "- `todo`: 지금 하려는 일(80자). 적으면 관측 맨 위 `할 일:`에 남는다. 빈 글이면 지운다."
gl = [ln for ln in brains.COMPOSE_PROMPT.split("\n") if ln.startswith("- `반복 중") or ln.startswith("- `todo`")]
check("③ 지시·권유 없음: 신호 꼬리표(LINES·SAME)와 지침 두 줄(반복 꼬리표 · todo)에 명령·권유 꼴이 없다 · 지침 두 줄 = 민옥 문구 글자 그대로(p0515d)",
      not [w_ for w_ in words + gl for b_ in BAD if b_ in w_] and gl == [GL_REP, GL_TODO]
      and RS.LINES == {"target": "반복 중: {what} ×{n}", "self": "반복 중: 제자리 ×{n}", "wait": "반복 중: 기다리기 ×{n}"} and RS.SAME == " · 변화 없음"
      and brains.TODO_HEAD == "할 일",
      ([w_ for w_ in words + gl for b_ in BAD if b_ in w_], gl))
check("③ 관측 키 등록: todo·repeat 가 _WIRE_KEYS — 미등록 관측 키 0(그리지 않는 칸 없음)",
      brains.unwired_keys(ob(todo="x", repeat=R5, last=None)) == [] and {"todo", "repeat"} <= brains._WIRE_KEYS)

print("── ④ 목표 칸 — 파싱·저장·노출·덮어쓰기·비우기·엔진 무관·남에게 안 보임")
TODO_A = "보물을 팔아 회복 물약을 사고 던전으로 간다"
TODO_B = "계단 앞에서 동료를 기다린다"
d4, bots4 = scenario.build({"map": ["#########", "#1.....>#", "#########"], "seed": 7})
P4 = {1: {"todo": TODO_A}, 4: {"todo": TODO_B}, 5: {"todo": ""}, 7: {"todo": "가" * 200}, 8: {"todo": "  줄을\n바꾼   할 일 \t"},
      9: {"todo": None}, 10: {"todo": 123}, 11: {"todo": ["목록"]}}
DEC4 = {}
with scripted(lambda c, n, obs, bot: {"type": "wait", **P4.get(n, {})}):
    for k_ in range(1, 13):
        DEC4[k_] = brains.think_all(d4, bots4)["1"]
pr4 = prompts_of("1")
TOP = "- %s: " % brains.TODO_HEAD


def top_todo(p):
    """프롬프트의 목표 칸 줄 — 관측 머리 바로 아래 줄일 때만 그 글(아니면 None)."""
    L_ = p.split("\n")
    hd = next((i for i, x in enumerate(L_) if x in ("# 판단 공간 — 지금 보고 듣는 것", "# 관측 — 지금 보고 듣는 것")), None)
    if hd is None or not L_[hd + 2].startswith(TOP):
        return None
    return L_[hd + 2][len(TOP):] if L_[hd + 1] == "" and L_[hd + 3] == "" and L_[hd + 4] == "## 네 상태" else "자리 어긋남"


check("④ 파싱: 글 = 결정의 todo · 200자 → TODO_LEN(80)에서 자름 · 공백·줄바꿈은 한 줄로 · 빈 글 = '' · null·숫자·목록 = 칸 없음(그대로)",
      DEC4[1].get("todo") == TODO_A and DEC4[4].get("todo") == TODO_B and DEC4[5].get("todo") == "" and DEC4[7].get("todo") == "가" * 80
      and brains.TODO_LEN == 80 and DEC4[8].get("todo") == "줄을 바꾼 할 일" and not any("todo" in DEC4[k_] for k_ in (2, 3, 6, 9, 10, 11, 12)),
      {k_: DEC4[k_].get("todo") for k_ in DEC4})
tops = {k_: top_todo(pr4[k_]) for k_ in pr4}
check("④ 노출: 적은 다음 판단부터 관측 맨 위 한 줄('- 할 일: …' — 관측 머리 바로 아래, '네 상태' 위) · 다시 적을 때까지 매 판단(2~4) ·"
      " 덮어쓰기(5) · 빈 글로 비움(6·7 없음) · 자른 글(8) · 한 줄로 편 글(9) · null·숫자·목록은 그대로(10~12)",
      tops == {1: None, 2: TODO_A, 3: TODO_A, 4: TODO_A, 5: TODO_B, 6: None, 7: None, 8: "가" * 80, 9: "줄을 바꾼 할 일", 10: "줄을 바꾼 할 일",
               11: "줄을 바꾼 할 일", 12: "줄을 바꾼 할 일"} and bots4[0].get("todo") == "줄을 바꾼 할 일", tops)
check("④ 할 일 줄은 관측 맨 위 한 번뿐(다른 자리에 되풀이되지 않는다)",
      all(sum(ln.startswith(TOP) for ln in pr4[k_].split("\n")) == (1 if tops[k_] else 0) for k_ in pr4))
d4a, b4a = scenario.build({"map": ["#########", "#1.....>#", "#########"], "seed": 7})
d4b, b4b = scenario.build({"map": ["#########", "#1.....>#", "#########"], "seed": 7})
d4a.view(b4a[0], b4a)
d4b.view(b4b[0], b4b)
ra = d4a.act(b4a[0], {"type": "wait", "todo": "이 글은 엔진이 읽으면 안 된다"}, b4a)
rb = d4b.act(b4b[0], {"type": "wait"}, b4b)
check("④ 엔진은 목표 칸을 읽지 않는다 — todo 가 실린 결정과 없는 결정의 판정이 같다 · 결과·몸에 todo 없음(완료 판정·자동 삭제 없음)",
      ra == rb and "todo" not in ra and "todo" not in b4a[0], (ra, rb))
TR = [{"id": "m7", "kind": "monster", "name": "고블린", "tags": ["agent", "living", "damageable", "movable"], "bearing": "북쪽", "dist": 3}]
w4 = brains._wire(ob(action_schema=CA.SCHEMA, targets=TR, todo="m7 고블린을 피해서 계단으로", last=None, sights={}), {}, compose=True)
check("④ 할 일 글 속의 ID(m7)가 대상 절의 '장소 절에 자리가 적힌 ID'(관측 글에서 f·d·m 번호를 고른다)로 읽히지 않는다 — 방위·거리 그대로",
      "- [m7] 고블린 (agent, living, damageable, movable) — 북쪽, 거리 3" in w4 and "- 할 일: m7 고블린을 피해서 계단으로" in w4,
      [ln for ln in w4.split("\n") if "m7" in ln])
d4c, bots4c = scenario.build({"map": ["#########", "#12....>#", "#########"], "seed": 7})
OBS4 = {"1": [], "2": []}


def s4(c, n, obs, bot):
    OBS4[c].append(json.loads(json.dumps({k: obs.get(k) for k in ("todo", "repeat") if k in obs})))
    if c == "1":
        return {"type": "wait", **({"todo": TODO_A} if n == 1 else {})}
    return {"type": "wait"} if n % 2 else {"type": "search", "target": "self"}


with scripted(s4):
    for _ in range(7):
        brains.think_all(d4c, bots4c)
p41, p42 = prompts_of("1"), prompts_of("2")
check("④ 남에게 안 보임: 봇1 의 할 일·반복 신호는 봇1 의 관측·프롬프트에만 — 봇2 의 관측 칸·프롬프트에 없다(봇2 는 연속이 끊겨 제 신호도 없다)",
      all(TODO_A in p41[k_] for k_ in range(2, 8)) and any(reps_in(p41[k_]) == ["- 반복 중: 기다리기 ×5 · 변화 없음"] for k_ in p41)
      and not any(TODO_A in p_ or reps_in(p_) for p_ in p42.values())
      and all(not x for x in OBS4["2"]) and any("repeat" in x for x in OBS4["1"]),
      (OBS4["2"], [(k_, reps_in(p41[k_])) for k_ in p41 if reps_in(p41[k_])]))
snap4 = G.bot_snapshot(bots4c[0])
check("④ 스트림 봇 스냅샷(관전·남의 관측 재료)에 todo·repeat 없음", "todo" not in snap4 and "repeat" not in snap4 and bots4c[0].get("todo") == TODO_A, sorted(snap4))
leak4 = IG.public({"type": "wait", "result": "waited", "todo_ops": [{"char": "1", "text": TODO_A}], "deep": {"todo_ops": [], "keep": 1}})
check("④ 정보 보호: 스트림 칸 todo_ops 는 관전 전용(IG.SPECTATOR_KEYS) — 결과·목격 사본 어디에 옮겨 적혀도 걷힌다",
      "todo_ops" in IG.SPECTATOR_KEYS and leak4 == {"type": "wait", "result": "waited", "deep": {"keep": 1}}, leak4)

print("── ⑤ think_all 미니 루프(손그림 장면 · 실제 엔진 판정)")
d5, bots5 = scenario.build({"map": ["##########", "#1...~...#", "#........#", "#.......>#", "##########"], "seed": 7})
PLAN5 = {1: "goto", 2: "search", 3: "goto", 4: "search"}
TURN5 = {}


def s5(c, n, obs, bot):
    TURN5[n] = d5.turn
    fid = next((f["id"] for f in obs["sights"]["features"] if f.get("type") == "fountain"), None)
    if n == 16:
        way = next((t["id"] for t in obs.get("targets") or [] if t.get("kind") == "way"), None)
        return {"type": "explore", "target": way} if way else {"type": "rest"}
    return {"type": "goto" if n > 16 else PLAN5.get(n, "search"), "target": fid}


with scripted(s5):
    for turn in range(1, 60):
        d5.turn = turn
        decs5 = brains.think_all(d5, bots5)
        for b_ in bots5:
            if b_.get("order"):
                d5.step_order(b_, bots5)
            elif b_["char"] in decs5:
                d5.act(b_, decs5[b_["char"]], bots5)
        d5.monster_turn(bots5)
        if LOG["n"].get("1", 0) >= 23:
            break
pr5 = prompts_of("1")
sig5 = {k_: reps_in(p_) for k_, p_ in pr5.items() if reps_in(p_)}
check("⑤ 샘 f0 에 goto·search 를 섞어 5번 → 6번째 판단 관측에 '×5' · 11번째에 '×10' · 그 밖(1~5·7~10·12~16)엔 없다",
      sorted(sig5) == [6, 11, 22] and sig5[6] == ["- 반복 중: 샘 f0 ×5"] and sig5[11] == ["- 반복 중: 샘 f0 ×10"], sig5)
check("⑤ 자동 보행 틱은 세지 않는다 — 첫 goto 가 여러 틱을 걸어 5번째 판단은 %s틱째(판단 수로만 센다)" % TURN5.get(5),
      TURN5.get(5, 0) > 5 and TURN5.get(2, 0) - TURN5.get(1, 0) >= 2, TURN5)
rep5 = {n_: rp_ for c_, n_, _dp, _td, rp_, _o in LOG["seen"] if c_ == "1"}
check("⑤ 첫 연속은 걷다가 계단을 새로 봤다(발견 꼬리표 — 달라짐) — SAME 없음 · 탐색이 끼면(16) 끊기고 새 연속(17~21 goto) 5번째 = SAME",
      "변화 없음" not in sig5.get(6, ["변화 없음"])[0] and (rep5.get(6) or {}).get("moved") is True and '\\"sighted\\"' in ((rep5.get(6) or {}).get("base") or {}).get("goto", "")
      and sig5.get(22) == ["- 반복 중: 샘 f0 ×5 · 변화 없음"] and rep5.get(17) is None, (sig5, rep5.get(6)))

print("── ⑥ 러너 풀런(각본 두뇌) — 스트림·로그·층 전이·이어가기")
TODO_C = "1층에서 계단 찾기"
TODOS6 = {1: TODO_A, 3: TODO_A, 6: TODO_B, 8: "", 12: TODO_C}


def s6(c, n, obs, bot):
    if n <= 12:
        return {"type": "search", "target": "self", **({"todo": TODOS6[n]} if (c == "1" and n in TODOS6) else {})}
    if any(t.get("id") == "exit" for t in obs.get("targets") or []):
        return {"type": "use", "target": "exit"}
    return {"type": "wait"}


LAST = {"dir": None}


def run(turns, st=None, resume=False):
    st = st or tempfile.mkdtemp(prefix="run_", dir=ROOT)
    patch = {"NPC_HAIL_ON": False, "RESUME_PATH": os.path.join(st, SN.PKL) if resume else ""}   # 인사(편지함)는 결과 비교를 흔들지 않게
    old_mod = {k_: getattr(R, k_) for k_ in patch}
    old = (R.STATE, R.MAX_TURNS, R.PAUSE_LIMIT_SEC, brains.social_all)
    for k_, v_ in patch.items():
        setattr(R, k_, v_)
    R.STATE, R.MAX_TURNS, R.PAUSE_LIMIT_SEC = st, int(turns), 2
    brains.social_all = lambda d, bots, inbox=None: {}
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                R.main()
            except SystemExit:
                pass
    finally:
        R.STATE, R.MAX_TURNS, R.PAUSE_LIMIT_SEC, brains.social_all = old
        for k_, v_ in old_mod.items():
            setattr(R, k_, v_)
    LAST["dir"] = st
    with open(os.path.join(st, "stream.jsonl"), encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


with scripted(s6):
    rows6 = run(160)                                 # 마을 → 던전 입구까지 걷는 틱이 길다(t13 출발)
ticks6 = [r for r in rows6 if r["kind"] == "tick"]
nth6, at6, todo_ev, dec_todo, obs_rep = {}, {}, [], [], []
for r in ticks6:
    for c_, dec_ in sorted((r.get("decisions") or {}).items()):
        nth6[c_] = nth6.get(c_, 0) + 1
        at6[(c_, nth6[c_])] = r["turn"]
        if "todo" in dec_:
            dec_todo.append((c_, nth6[c_], dec_["todo"]))
        if (dec_.get("obs") or {}).get("repeat"):
            obs_rep.append((c_, nth6[c_], dec_["obs"]["repeat"]))
    for o_ in r.get("todo_ops") or []:
        todo_ev.append((r["turn"], o_["char"], o_["text"]))
check("⑥ 스트림 decisions[].todo = 봇1 이 적은 판단(1·3·6·8·12)만 · 글 그대로(빈 글 포함)",
      dec_todo == [("1", 1, TODO_A), ("1", 3, TODO_A), ("1", 6, TODO_B), ("1", 8, ""), ("1", 12, TODO_C)], dec_todo)
check("⑥ 스트림 tick.todo_ops = 바뀐 틱만(적음 1 · 덮어씀 6 · 비움 8 · 다시 적음 12) — 같은 글을 다시 적은 3번째 판단엔 없다",
      todo_ev == [(at6[("1", 1)], "1", TODO_A), (at6[("1", 6)], "1", TODO_B), (at6[("1", 8)], "1", ""), (at6[("1", 12)], "1", TODO_C)], todo_ev)
with open(os.path.join(LAST["dir"], "events.log"), encoding="utf-8") as f:
    evl6 = [ln.strip() for ln in f if "할 일" in ln]
check("⑥ events.log: 할 일이 바뀐 때만 한 줄('봇1 할 일 적음: \"…\"' · '봇1 할 일 비움')",
      evl6 == ['봇1 할 일 적음: "%s"' % TODO_A, '봇1 할 일 적음: "%s"' % TODO_B, "봇1 할 일 비움", '봇1 할 일 적음: "%s"' % TODO_C], evl6)
SELF5 = "- 반복 중: 제자리 ×5 · 변화 없음"
SELF10 = "- 반복 중: 제자리 ×10 · 변화 없음"
check("⑥ 반복 신호: 셋 다 search self 12번 — 각자의 6·11번째 판단 관측(스트림 obs)에 n 5·10 · SAME(마을, 허탕, 몸 그대로)",
      sorted(x for x in obs_rep if x[1] <= 12) == sorted((c_, k_, {"n": n_, "target": "self", "same": True}) for c_ in ("1", "2", "3") for k_, n_ in ((6, 5), (11, 10)))
      and all(reps_in(prompts_of(c_)[6]) == [SELF5] and reps_in(prompts_of(c_)[11]) == [SELF10] for c_ in ("1", "2", "3")),
      obs_rep)
p61 = prompts_of("1")
exp61 = {k_: (None if k_ == 1 else TODO_A if k_ <= 6 else TODO_B if k_ <= 8 else None if k_ <= 12 else TODO_C) for k_ in p61}
got61 = {k_: top_todo(p_) for k_, p_ in p61.items()}
check("⑥ 봇1 프롬프트의 할 일 줄 = 적은 다음 판단부터 바꿀 때까지(2~6 A · 7~8 B · 9~12 없음 · 13~ C)", got61 == exp61,
      {k_: (got61[k_], exp61[k_]) for k_ in p61 if got61[k_] != exp61[k_]})
leak6 = [(c_, k_) for c_ in ("2", "3") for k_, p_ in prompts_of(c_).items() if any(t_ in p_ for t_ in (TODO_A, TODO_B, TODO_C))]
check("⑥ 남의 프롬프트(봇2·3)에 봇1 의 할 일 글이 한 번도 없다", not leak6 and len(prompts_of("2")) >= 12, leak6)
seen1 = [(n_, dp_, td_, rp_) for c_, n_, dp_, td_, rp_, _o in LOG["seen"] if c_ == "1"]
d0 = [x for x in seen1 if x[1] == 0]
d1 = [x for x in seen1 if x[1] == 1]
check("⑥ 층 전이(마을 → 1층 — 새 몸): 목표 칸은 이월(1층 첫 판단에 C) · 반복 연속은 옮기지 않는다(1층 첫 판단의 몸에 repeat 없음, 마을 마지막 판단엔 있었다)",
      bool(d0) and bool(d1) and d1[0][2] == TODO_C and d1[0][3] is None and d0[-1][3] is not None
      and top_todo(p61[d1[0][0]]) == TODO_C, ([x[:3] + ((x[3] or {}).get("key"), (x[3] or {}).get("n")) for x in d0[-2:] + d1[:2]]))
STOP7 = {"done": False}


def s7(c, n, obs, bot):
    if c == "1":
        if n == 3 and not STOP7["done"]:
            import run_control as RC                 # noqa: E402
            RC.request_stop(R.STATE, pages=False)    # 다음 틱 머리에서 곱게 멈춘다(스냅샷 = 그 틱 전)
            STOP7["done"] = True
        return {"type": "search", "target": "self", **({"todo": TODO_A} if n == 1 else {})}
    return {"type": "wait"}


st7 = tempfile.mkdtemp(prefix="run_", dir=ROOT)
with scripted(s7):
    rows7a = run(30, st=st7)
    snap7, _m7 = SN.load(os.path.join(st7, SN.PKL))  # 이 게이트가 방금 쓴 자기 피클(이어가기와 같은 길)
    rows7 = run(30, st=st7, resume=True)              # 같은 각본(판단 번호가 이어진다)
b7 = next(b_ for b_ in snap7["bots"] if b_["char"] == "1")
check("⑥ 곱게 멈춤의 스냅샷: 봇1 의 목표 칸·연속(search self 3번째)이 몸에 실려 있다 · 판 %d" % SN.STATE_VERSION,
      snap7["state_version"] == SN.STATE_VERSION and b7.get("todo") == TODO_A and (b7.get("repeat") or {}).get("key") == "self"
      and chain(b7).get("n") == 3, (b7.get("todo"), b7.get("repeat")))
p7 = prompts_of("1")
check("⑥ 이어가기: 이어간 뒤 4·5번째 판단을 더해 6번째 판단 관측에 '×5'(연속이 이어졌다) · 할 일 줄은 이어간 뒤에도 그대로",
      sorted(k_ for k_, p_ in p7.items() if any("×5" in ln for ln in reps_in(p_))) == [6] and reps_in(p7[6]) == [SELF5]
      and all(top_todo(p7[k_]) == TODO_A for k_ in range(2, 7)) and any(r.get("kind") == "resume" for r in rows7), sorted(p7))

print("── ⑦ 저장 판 8 — 7→8 이관 · 쓰기/되읽기")


def hist(seq):
    return [{"turn": i + 1, "type": t, "target": g, "src": "haiku"} for i, (t, g) in enumerate(seq)]


snap8 = {"version": 2, "state_version": 7, "next_turn": 30,
         "bots": [{"char": "1", "history": hist([("explore", "w1_1")] + [("goto", "f3"), ("use", "f3")] * 3 + [("use", "f3")])},
                  {"char": "4", "history": hist([("search", "f1"), ("wait", None), ("wait", None)])},
                  {"char": "5", "repeat": {"key": "m1", "n": 2, "verb": "attack", "body": None}, "history": hist([("goto", "f3")] * 6)},
                  {"char": "7", "history": hist([("goto", "f2"), ("search", "b7"), ("search", "self"), ("use", "b7")])}],
         "worlds": [{"bots": [{"char": "2", "history": hist([("search", "f1")] * 10)}]}],
         "waiting": {"3": {"char": "3", "history": hist([("goto", "f3"), ("explore", "w2_1")])}, "6": {"char": "6"}}}
up8 = SN.upgrade(json.loads(json.dumps(snap8)))
bs8 = {b_["char"]: b_ for b_ in up8["bots"] + up8["worlds"][0]["bots"] + list(up8["waiting"].values())}
check("⑦ 판 8 · 이관 등록부 0..7 · 7→8: 최근 판단 장부의 끝에서 같은 열쇠가 이어진 수(goto·use 섞임 7 · wait 2 · 장부 가득 10 · 자기 자신 b7/self 3)로 연속을 다시 세운다 ·"
      " 변화는 몰라 moved · 지난 차례는 싣지 않는다(due 없음) · 끝이 탐색·장부 없음 = 칸 없음 · 이미 칸이 있으면 그대로 · 목표 칸은 만들지 않는다 · 두 번 올려도 같다",
      SN.STATE_VERSION >= 8 and sorted(SN.MIGRATIONS) == list(range(SN.STATE_VERSION)) and up8["state_version"] == SN.STATE_VERSION   # p0.5.16: 판 9(욕구) — 8 이상
      and chain(bs8["1"]) == {"key": "f3", "n": 7, "verb": "use", "body": None, "moved": True}
      and chain(bs8["4"]) == {"key": RS.WAIT, "n": 2, "verb": "wait", "body": None, "moved": True}
      and chain(bs8["2"]).get("n") == 10 and "repeat" not in bs8["3"] and "repeat" not in bs8["6"]
      and chain(bs8["7"]) == {"key": "self", "n": 3, "verb": "use", "body": None, "moved": True}
      and chain(bs8["5"]) == {"key": "m1", "n": 2, "verb": "attack", "body": None} and not any("todo" in b_ for b_ in bs8.values())
      and SN.upgrade(json.loads(json.dumps(up8))) == up8, {c_: b_.get("repeat") for c_, b_ in bs8.items()})
r8, _ = drive(loop_seq(3), bot=bs8["1"])
r8b, _ = drive([({"type": "search", "target": "f1"}, ob(last=dict(MISS))) for _ in range(5)], bot=bs8["2"])
check("⑦ 이관한 연속에 이어서: 7 → 8·9·10 = 10번째 신호(SAME 없음 — 그 전의 변화는 모른다) · 장부 가득(10)은 그 뒤 신호 없음",
      [x for x in r8 if x] == [{"n": 10, "target": "f3"}] and not any(r8b) and chain(bs8["2"]).get("n") == 15, (r8, r8b))
d8, bots8 = scenario.build({"map": ["#######", "#12..>#", "#######"], "seed": 7})
bots8[0]["todo"] = TODO_B
RS.step(bots8[0], D_GOTO, ob(last=None))
S8 = tempfile.mkdtemp(prefix="snap_", dir=ROOT)
SN.write(S8, {"run_id": "r8", "d": d8, "bots": bots8, "sheets": {}, "next_turn": 9, "stream_pos": 0, "seed": 7, "started": "t"},
         {"run_id": "r8", "next_turn": 9})
back8, _m8 = SN.load(os.path.join(S8, SN.PKL))    # 이 게이트가 방금 쓴 자기 피클
check("⑦ 스냅샷 쓰기/되읽기: 목표 칸·연속 칸이 그대로 · 지금 판(8 이상)", back8["state_version"] == SN.STATE_VERSION and back8["bots"][0].get("todo") == TODO_B
      and back8["bots"][0].get("repeat") == bots8[0]["repeat"] and "todo" not in back8["bots"][1], back8["bots"][0].get("repeat"))

print("── ⑧ 0콜")
check("⑧ 진짜 백엔드(claude_cli·anthropic·gemini·openai)는 막혀 있고(부르면 AssertionError) 모든 판단 응답은 각본(%d번)" % LOG["stub"],
      all(getattr(brains, k_) is _no_real_backend for k_ in ("_call_cli", "_call_anthropic", "_call_gemini", "_call_openai")) and LOG["stub"] > 0)

print()
if C.failed:
    print("FAIL — %d/%d" % (C.failed, C.n))
    raise SystemExit(1)
print("ALL PASS — verify_repeat_goal (p0.5.15 반복 신호 + 목표 칸: 대상·기다리기 연속 · 5·10번째 한 번씩 · 달라진 것 · 관측 사실 한 줄 · 목표 칸 저장·노출·덮어쓰기·비우기 · "
      "남에게 안 보임 · 스트림 todo_ops · 층 이월 · 이어가기 · 저장 판 8, %d checks, 실 LLM 0콜)" % C.n)

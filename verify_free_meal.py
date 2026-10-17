# -*- coding: utf-8 -*-
"""p0.5.25 주점 무료 식사 → 길드 의뢰로 잇기(DECISIONS 10-17) — 헤들리스 검증. LLM 0콜.
판 시작 때 모험가마다 주점 무료 식사 2끼(정의 — 주점 sells 의 free · 임시) · 무료가 남으면 골드 없이 먹는다(배부름 거절 등 기존 규칙 그대로) ·
결과 문장 '주점에서 무료 식사를 받았다 (남은 무료 식사 N끼)'(말 파일) · 다 쓴 뒤엔 지금 문장 그대로 · 마지막 무료 끼니 때 주점 주인의 정해진 말이
들은 말(다음 틱 편지함 — NPC 의 답과 같은 길)로 그 모험가에게 닿는다(NPC 두뇌 무관) · 남은 횟수는 몸(free)에 — 층 이월·부활·스냅샷·이어가기 · 옛 판은 0끼.
게이트:
  ① 정의·검증기: 주점(마을 생활 판) 식사 free 2 · 무료 결과 문장·주인의 말 = 말 파일 글자 그대로 · 끈 판엔 없다 · 판 시작 무료 = 정의에서(시험 정의 free 3 → 3끼) · 검증기 거절 10종
  ② 무료 2끼: 첫 끼(골드 그대로 · 1끼 남음 · 문장·꼬리표·목격) · 둘째 끼(0끼 · 주인의 말 한 번) · 셋째부터 값(지금 문장 그대로) · 모자라면 too_poor · 빈 지갑도 무료
  ③ 배부름 거절: 무료가 남아도 배가 부르면 사지 않는다 — 횟수·골드 그대로(지금 문장) · 주인의 말 없음
  ④ 동료·NPC 무관: 몸마다 제 횟수 · 주인의 말은 정의의 문장(NPC 두뇌를 부르지 않는다) · 맡은 사람이 없는 세계엔 말도 없다 · 무료는 그 가게의 것 · NPC 두뇌 사실은 그대로
  ⑤ 숫자 누설: 관측 '네 상태'·관측 칸에 무료 횟수가 없다 · 남은 횟수는 결과 문장 한 곳(궤적 판에선 꼬리표가 그 문장 — 목격·층 집계엔 없다) · 남의 관측엔 없다 ·
     공개 투영은 결과의 free_left·free_line 을 남긴다
  ⑥ 저장·이어가기: 층 이월·부활(_carry 소스) · 이관 12→13(옛 몸 0끼 → 바로 값 · 이미 칸이 있으면 그대로 · 부활 대기 몸 · 다시 올려도 같다) · 피클 왕복
  ⑦ 러너 판(실제 러너 · 각본 두뇌 · NPC 두뇌 켬 — 스텁): 무료 1끼 → 곱게 멈춤 → 이어가기 → 둘째 끼(주인의 말이 다음 틱 편지함으로 그 사람에게 — 한 번) → 셋째 값 ·
     관측 '들은 말' · events.log · 스트림 need_fill 의 free_left · tick.bots[].gold · NPC 두뇌 0번 ·
     p0525b(Codex p0525r 권장) 1인 파티 판: 마지막 무료 끼니 + 같은 틱 주인에게 지목한 말 → 정해진 말과 두뇌의 되받은 말이 둘 다 닿는다 ·
     실제 층 이동(마을 → 지하 1층, 재스폰 + _carry) 뒤 무료 끼니 그대로
  ⑧ 배선: _run_gates.sh · STREAM_FORMAT · VERSION 0.5.25 · 저장 판 13
"""
import contextlib
import copy
import glob
import io
import json
import os
import pickle
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = tempfile.mkdtemp(prefix="wl_freemeal_")
STATE = os.path.join(ROOT, "state")
os.makedirs(STATE, exist_ok=True)
BASE_ENV = dict(DUNGEON_GM="0", DUNGEON_STEP_DELAY="0", DUNGEON_TURNS="14", DUNGEON_W="40", DUNGEON_H="16",
                DUNGEON_DEPTHS="2", DUNGEON_SEED="7", DUNGEON_MONSTERS="0", DUNGEON_TRAPS="0", DUNGEON_LURKERS="0",
                DUNGEON_BESTIARY_FILE="", DUNGEON_PARTY_FILE=os.path.join(HERE, "party.json"), DUNGEON_STATE_DIR=STATE,
                DUNGEON_TOWN="1", DUNGEON_BRAIN_BACKEND="dummy", DUNGEON_BOSS="0", DUNGEON_RUNS_DIR=os.path.join(ROOT, "runs"),
                DUNGEON_ACTION_MODE="compose", DUNGEON_TOWN_LIFE="1")   # 마을 생활 = 주점이 식사를 파는 판
os.environ.update(BASE_ENV)
for k in ("DUNGEON_QUESTS", "DUNGEON_TOWN_APART", "DUNGEON_NPC_BRAIN", "DUNGEON_SOLO", "DUNGEON_START", "DUNGEON_MENU", "DUNGEON_RESUME",
          "DUNGEON_PARTYFORM", "DUNGEON_STRANGERS", "DUNGEON_TOWN_SIGHT", "DUNGEON_NPC_REPLY", "DUNGEON_NPC_HAIL_BRAIN", "DUNGEON_NOTICES",
          "DUNGEON_TOWN_BUILDINGS", "DUNGEON_TOWN_WALKERS", "DUNGEON_ARCH", "DUNGEON_FLOOR_LIFE", "DUNGEON_BESTIARY_PLUS", "DUNGEON_OFFER",
          "DUNGEON_API_CALL_LIMIT", "DUNGEON_BRAIN_FALLBACK", "DUNGEON_BRAIN_LOG", "DUNGEON_NPC_HAIL", "DUNGEON_NPC_HAIL_STOP"):
    os.environ.pop(k, None)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import brains                                        # noqa: E402
brains._call_claude = lambda prompt, model="haiku": ""   # LLM 무력화(0콜)


def _no_real_backend(prompt, model):                 # 이중 안전핀: 어떤 길로도 진짜 백엔드는 안 부른다(⑦ 은 백엔드 이름만 claude_cli 로 돌린다)
    raise AssertionError("real backend must not be called in a gate")


brains._call_cli = brains._call_anthropic = brains._call_gemini = brains._call_openai = _no_real_backend
import dungeon_gm as G                               # noqa: E402
import entities as ENT                               # noqa: E402
import info_guard as IG                              # noqa: E402
import interactables as IA                           # noqa: E402
import run_control as RC                             # noqa: E402
import show_runner as R                              # noqa: E402
import snapshot as S                                 # noqa: E402
import words as WD                                   # noqa: E402
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
LINE_FREE = "주점에서 무료 식사를 받았다 (남은 무료 식사 {n}끼)"
LINE_END = "공짜로 주는 건 이게 끝이야. 다음부턴 길드에 가서 의뢰를 받아 돈이라도 벌어 와."
PAID = "주점에서 식사를 사 먹었다 — 3골드를 냈다(남은 골드 2)"


def town(on=True):
    """마을(마을 생활 켬/끔) + 파티 몸 셋(스폰 — 판 시작의 몸). 정의의 말·값은 리포의 것 그대로."""
    old = R.TOWN_LIFE_ON
    R.TOWN_LIFE_ON = on
    try:
        d, _starts = R.build_town(None, apart=True, walkers=False, guide=False, quests=None)
    finally:
        R.TOWN_LIFE_ON = old
    bs = []
    for c in sorted(SHEETS):
        bs.append(G.spawn(d, c, bs, sheet=dict(SHEETS[c])))
    d.turn = 1
    return d, bs


def by_name(d, name):
    return next(f for f in d.features.values() if f.name == name)


def stand_by(d, f, bots=(), skip=()):
    taken = {(o["x"], o["y"]) for o in bots} | set(skip)
    return next((f.x + dx, f.y + dy) for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (-1, 1), (1, -1), (-1, -1))
                if d.grid[f.y + dy][f.x + dx] == G.FLOOR and d.feature_at(f.x + dx, f.y + dy) is None and (f.x + dx, f.y + dy) not in taken)


def put(b, xy):
    b["x"], b["y"] = xy


def act(d, b, bots, action):
    d.view(b, bots)                                   # 관측 = 참조(_target_refs)를 새로 짓는다(실판과 같은 순서)
    return d.act(b, dict(action), bots)


def gid_of(d, name):
    return next(g["gid"] for g in IA.goods(d) if g["name"] == name)


def buy(d, b, bots, hunger=30):
    """배고픔을 맞춘 몸으로 주점 식사를 산다(use g<n>)."""
    b["needs"]["hunger"] = hunger
    return act(d, b, bots, {"type": "use", "target": gid_of(d, "식사")})


def seen_of(o, char):
    return [x.get("result") for x in (o.get("witnessed") or []) if x.get("kind") == "ally_use" and x.get("char") == char]


def status_section(wire):
    """완성 관측 글의 '## 네 상태' 절(다음 '## ' 머리 전까지)."""
    body = wire.split("## 네 상태", 1)[1]
    return body.split("\n## ", 1)[0]


# ─────────────────────────────────────────────────────────────────────────────
print("── ① 정의·검증기")
TAV_USE = ENT.comps_of("tavern", True).get("use") or {}
TK_LIFE = ENT.npc("tavern_keeper", life=True)
check("① 주점(마을 생활 판 life.use): 식사 3골드 · free 2(판 시작 때 모험가마다 — 임시) · 무료 결과 문장 = 말 파일 '주점에서 무료 식사를 받았다 (남은 무료 식사 {n}끼)' · 끈 판 주점엔 쓰임이 없다",
      TAV_USE.get("sells") == [{"item": "meal", "price": 3, "free": 2}] and TAV_USE.get("line_free") == LINE_FREE and not ENT.comps_of("tavern", False).get("use")
      and WD.parse(src("prompts", "world", "building", "tavern.md"))[0].get("life.use.line_free") == LINE_FREE, TAV_USE)
check("① 주점 주인(마을 생활 판 life.npc.line_free_end) = 민옥 문장 그대로(말 파일) · 끈 판엔 없다 · 맡은 가게 = 주점",
      TK_LIFE.get("line_free_end") == LINE_END and ENT.npc("tavern_keeper", life=False).get("line_free_end") is None and TK_LIFE.get("shop") == "tavern"
      and WD.parse(src("prompts", "world", "npc", "tavern_keeper.md"))[0].get("life.npc.line_free_end") == LINE_END, TK_LIFE.get("line_free_end"))
dA, botsA = town(on=True)
a1, a2, a3 = botsA
check("① 판 시작 무료 = 정의에서 센다(IA.free_start — 가게 sells 의 free) {meal: 2} · 스폰한 몸마다 같은 칸(서로 다른 사본) · 끈 판 마을에서 스폰한 몸도 같다(판 시작에 받는다)",
      IA.free_start() == {"meal": 2} and all(b_["free"] == {"meal": 2} for b_ in botsA) and botsA[0]["free"] is not botsA[1]["free"]
      and all(b_["free"] == {"meal": 2} for b_ in town(on=False)[1]), [b_.get("free") for b_ in botsA])


DEFS0 = ENT.load()
DEFS_3 = copy.deepcopy(DEFS0)                         # 시험용 정의 사전 — 주점 식사의 free 만 3(데이터만 바꾼다 · 코드 그대로)
DEFS_3["tavern"]["comps"]["life"]["use"]["sells"][0]["free"] = 3
ENT._DEFS = DEFS_3
try:
    fs3 = IA.free_start()
    d3, bots3 = town(on=True)
finally:
    ENT._DEFS = DEFS0
check("① 데이터만으로 횟수가 바뀐다 — 주점 식사 free 를 3 으로 둔 정의 사전이면 판 시작 무료 {meal: 3} · 스폰한 몸도 3끼(코드는 그대로)",
      fs3 == {"meal": 3} and all(b_["free"] == {"meal": 3} for b_ in bots3) and IA.free_start() == {"meal": 2}, (fs3, [b_.get("free") for b_ in bots3]))


def problems_with(edit):
    """정의 사본(임시 폴더)에 edit(폴더) 를 가하고 읽은 문제 목록(글) — 말 파일은 리포의 것을 합친다."""
    root = tempfile.mkdtemp(prefix="defs_", dir=ROOT)
    for p in glob.glob(os.path.join(ENT.ROOT, "*", "*.json")):
        dst = os.path.join(root, os.path.basename(os.path.dirname(p)))
        os.makedirs(dst, exist_ok=True)
        shutil.copy(p, dst)
    edit(root)
    try:
        ENT.read(root)
        return ""
    except ENT.EntityError as e:
        return str(e)


def jedit(root, kind, eid, fn):
    p = os.path.join(root, kind, eid + ".json")
    with open(p, encoding="utf-8") as f:
        dd = json.load(f)
    fn(dd)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(dd, f, ensure_ascii=False)


def tav(fn):
    return lambda r: jedit(r, "building", "tavern", lambda d_: fn(d_["comps"]["life"]["use"]))


BAD = [("free 0", tav(lambda u: u["sells"][0].update(free=0)), "free?: 정수≥1"),
       ("free 참거짓", tav(lambda u: u["sells"][0].update(free=True)), "free?: 정수≥1"),
       ("free 글", tav(lambda u: u["sells"][0].update(free="2")), "free?: 정수≥1"),
       ("sells 의 모르는 칸", tav(lambda u: u["sells"][0].update(gratis=1)), "free?: 정수≥1"),
       ("먹는 음식이 아닌 물건에 free", lambda r: jedit(r, "building", "general_store", lambda d_: d_["comps"]["life"]["use"]["sells"][0].update(free=1)),
        "무료는 그 자리에서 먹는 음식(type food)만"),
       ("free 인데 line_free 없음", tav(lambda u: u.pop("line_free")), "free 가 있으면 line_free"),
       ("line_free 인데 free 없음", tav(lambda u: u["sells"][0].pop("free")), "line_free 는 sells 에 free 가 있는 가게만"),
       ("line_free 에 {n} 없음", tav(lambda u: u.update(line_free="무료 식사를 받았다")), "free 가 있으면 line_free"),
       ("line_free 에 다른 자리", tav(lambda u: u.update(line_free="{what} 무료 (남은 {n}끼)")), "free 가 있으면 line_free"),
       ("가게를 맡지 않은 사람의 line_free_end", lambda r: jedit(r, "npc", "temple_attendant", lambda d_: d_["comps"]["npc"].update(line_free_end="끝이야")),
        "npc.line_free_end")]
errs = {nm_: problems_with(fn_) for nm_, fn_, _w in BAD}
check("① 검증기 거절 10종을 로드 단계에서 — free 0·참거짓·글 · sells 의 모르는 칸 · 먹는 음식이 아닌 물건의 free · free 인데 결과 문장 없음 · 결과 문장인데 free 없음 · "
      "결과 문장의 {n} 없음·다른 자리 · 가게를 맡지 않은 사람의 마지막 무료 끼니 말 — 리포 정의는 통과",
      all(w_ in errs[nm_] for nm_, _f, w_ in BAD) and problems_with(lambda r: None) == "",
      {nm_: errs[nm_][:90] for nm_, _f, w_ in BAD if w_ not in errs[nm_]})

# ─────────────────────────────────────────────────────────────────────────────
print("── ② 무료 2끼 → 그 뒤 값")
TAV, KEEPER = by_name(dA, "주점"), by_name(dA, "주점 주인")
put(a1, stand_by(dA, TAV, botsA))
put(a2, stand_by(dA, TAV, botsA, skip=[(a1["x"], a1["y"])]))
put(a3, (KEEPER.x, KEEPER.y + 1) if dA.grid[KEEPER.y + 1][KEEPER.x] == G.FLOOR and dA.feature_at(KEEPER.x, KEEPER.y + 1) is None else stand_by(dA, KEEPER, botsA))
for o in botsA:
    o["witnessed"] = []
r1 = buy(dA, a1, botsA)
check("② 첫 끼 = 무료 — need_fill{via buy · free_left 1} · 골드 그대로 5 · 배고픔 30 → 100 · 몸 free {meal: 1} · 성공 · "
      "문장 '주점에서 무료 식사를 받았다 (남은 무료 식사 1끼)' · 궤적 꼬리표도 같은 글 '[받아 먹음] 주점에서 무료 식사를 받았다 (남은 무료 식사 1끼)' · 곁의 사람 '식사를 받아 먹었다' · 주인의 말 없음",
      r1["result"] == "need_fill" and r1["via"] == "buy" and r1.get("free_left") == 1 and r1["gold"] == 5 and a1["gold"] == 5 and a1["needs"]["hunger"] == 100
      and a1["free"] == {"meal": 1} and (r1.get("resolution") or {}).get("status") == "success"
      and brains._last_prose(r1) == "주점에서 무료 식사를 받았다 (남은 무료 식사 1끼)"
      and G.event_tags(r1) == [("use", "받아 먹음", "주점에서 무료 식사를 받았다 (남은 무료 식사 1끼)")]
      and seen_of(a2, "1")[-1:] == ["식사를 받아 먹었다"] and R.free_end_says(dA, a1, r1) == [],
      (r1, brains._last_prose(r1), G.event_tags(r1), seen_of(a2, "1")))
r2 = buy(dA, a1, botsA)
check("② 둘째 끼 = 마지막 무료 — free_left 0 · 골드 그대로 5 · 몸 free {meal: 0} · 문장 '(남은 무료 식사 0끼)' · 주인의 말 한 줄 = (주점 주인, 정의의 문장 그대로, 산 사람)",
      r2["result"] == "need_fill" and r2.get("free_left") == 0 and a1["gold"] == 5 and a1["free"] == {"meal": 0}
      and brains._last_prose(r2) == "주점에서 무료 식사를 받았다 (남은 무료 식사 0끼)" and R.free_end_says(dA, a1, r2) == [("주점 주인", LINE_END, "1")],
      (r2, brains._last_prose(r2), R.free_end_says(dA, a1, r2)))
r3 = buy(dA, a1, botsA)
check("② 셋째 끼부터 = 값 — need_fill{via buy}(free_left·free_line 없음) · 골드 5 → 2 · 지금 문장 그대로 '주점에서 식사를 사 먹었다 — 3골드를 냈다(남은 골드 2)' · 꼬리표 '사 먹음' · "
      "곁의 사람 '식사를 사 먹었다' · 주인의 말은 다시 없다",
      r3["result"] == "need_fill" and "free_left" not in r3 and "free_line" not in r3 and a1["gold"] == 2 and r3["gold"] == 2 and a1["free"] == {"meal": 0}
      and brains._last_prose(r3) == PAID and G.event_tags(r3)[0][:2] == ("use", "사 먹음") and seen_of(a2, "1")[-1:] == ["식사를 사 먹었다"]
      and R.free_end_says(dA, a1, r3) == [], (r3, brains._last_prose(r3)))
r4 = buy(dA, a1, botsA)
check("② 다 쓴 뒤 골드가 모자라면 too_poor(값 3 · 지닌 2) — 배고픔·골드·횟수 그대로(p0.5.13 그대로)",
      r4["result"] == "too_poor" and a1["gold"] == 2 and a1["needs"]["hunger"] == 30 and a1["free"] == {"meal": 0}, r4)
a2["gold"] = 0
r5 = buy(dA, a2, botsA)
check("② 빈 지갑(골드 0)이어도 무료가 남았으면 먹는다 — need_fill · free_left 1 · 골드 0 그대로",
      r5["result"] == "need_fill" and r5.get("free_left") == 1 and a2["gold"] == 0 and a2["free"] == {"meal": 1}, r5)

# ─────────────────────────────────────────────────────────────────────────────
print("── ③ 배부름 거절")
r6 = buy(dA, a2, botsA, hunger=100)
check("③ 무료가 남아도 배가 부르면 사지 않는다 — need_none{why full · via buy} · 횟수 그대로 {meal: 1} · 골드 그대로 0 · 지금 문장 '주점에서 식사를 사지 않았다 — 배가 부르다' · 주인의 말 없음",
      r6["result"] == "need_none" and r6.get("via") == "buy" and "free_left" not in r6 and a2["free"] == {"meal": 1} and a2["gold"] == 0
      and brains._last_prose(r6) == "주점에서 식사를 사지 않았다 — 배가 부르다" and R.free_end_says(dA, a2, r6) == [], (r6, a2["free"]))
a2["free"] = {"meal": 0}
r7 = buy(dA, a2, botsA, hunger=100)
check("③ 다 쓴 몸도 배가 부르면 같은 거절(횟수 0 그대로 · 주인의 말 없음)",
      r7["result"] == "need_none" and a2["free"] == {"meal": 0} and R.free_end_says(dA, a2, r7) == [], r7)

# ─────────────────────────────────────────────────────────────────────────────
print("── ④ 동료·NPC 무관")
check("④ 몸마다 제 횟수 — 봇1 이 무료 2끼를 다 쓰고 봇2 가 1끼를 써도 봇3 은 2끼 그대로(남의 끼니를 쓰지 않는다)",
      a1["free"] == {"meal": 0} and a3["free"] == {"meal": 2}, [b_["free"] for b_ in botsA])
called = []
old_reply, old_call = brains.npc_reply, brains._call_claude
brains.npc_reply = lambda *a_, **k_: called.append("npc_reply")
brains._call_claude = lambda *a_, **k_: (called.append("call"), ("", None))[1]
try:
    says8 = R.free_end_says(dA, a1, r2)
finally:
    brains.npc_reply, brains._call_claude = old_reply, old_call
fes_src = src("show_runner.py").split("def free_end_says(")[1].split("\ndef ")[0]
check("④ 주인의 말은 정의의 문장 그대로 — NPC 두뇌(npc_reply·LLM)를 부르지 않는다(두뇌가 켜져 있어도) · 러너 함수 소스에 두뇌 길이 없다",
      says8 == [("주점 주인", LINE_END, "1")] and not called and "npc_reply" not in fes_src and "npc_turn" not in fes_src, (says8, called))
dN = copy.deepcopy(dA)
del dN.features[KEEPER.id]
check("④ 가게를 맡은 사람이 이 세계에 없으면 마지막 무료 끼니에도 말이 없다(누가 했는지 모르는 말을 지어내지 않는다) · 맡은 사람 찾기 = 정의 npc.shop",
      R.free_end_says(dN, a1, r2) == [] and IA.keeper_of(dA, "f%d" % TAV.id) == "주점 주인" and IA.keeper_of(dN, "f%d" % TAV.id) is None
      and IA.keeper_of(dA, "f%d" % by_name(dA, "주민의 집").id) is None)
dG, botsG = town(on=True)
GS = by_name(dG, "잡화점")
dG.use_over = {GS.id: {"kind": "shop", "sells": [{"item": "meal", "price": 3}]}}   # 세계의 쓰임 덮기(D92 — 피처마다 다른 쓰임): 같은 식사를 무료 없이 파는 다른 가게
g8 = botsG[0]
put(g8, stand_by(dG, GS, botsG))
g8["needs"]["hunger"] = 30
try:                                                 # 무료 길이 무료 없는 가게에 들어가면(그 가게엔 무료 결과 문장이 없다) 죽는다 — 죽음도 이 검사의 FAIL 로 적는다
    rG = act(dG, g8, botsG, {"type": "use", "target": next(g_["gid"] for g_ in IA.goods(dG) if g_["fid"] == GS.id and g_["item"] == "meal")})
except Exception as e_:                              # noqa: BLE001
    rG = {"result": "error", "error": repr(e_)}
check("④ 무료는 그 가게의 것 — 같은 식사를 무료 없이 파는 다른 가게에선 무료가 남아도 값을 낸다(골드 5 → 2 · 횟수 그대로 2끼)",
      rG["result"] == "need_fill" and "free_left" not in rG and g8["gold"] == 2 and g8["free"] == {"meal": 2}, (rG, g8.get("free")))
facts8 = R.npc_facts(dA, "주점 주인", botsA, [], None, 0, NAMES)
check("④ NPC 두뇌 사실(주점 주인)은 그대로 — 가게 값 '판다: 식사 3골드' · 손님마다 남은 무료 횟수는 없다(남의 몸 숫자)",
      any("판다: 식사 3골드" in f_ for f_ in facts8) and not any("무료" in f_ for f_ in facts8), facts8)

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑤ 숫자 누설")
dV, botsV = town(on=True)
v1, v2, v3 = botsV
put(v1, stand_by(dV, by_name(dV, "주점"), botsV))
put(v2, stand_by(dV, by_name(dV, "주점"), botsV, skip=[(v1["x"], v1["y"])]))
rV = buy(dV, v1, botsV)
oV = dV.view(v1, botsV)
wV = brains._wire(oV, NAMES, compose=True)
check("⑤ 관측 '네 상태' 절에 무료 횟수가 없다(지갑 줄은 그대로) · 관측 칸(최상위)에 free 가 없다 · 남은 횟수는 결과 문장 한 곳 — 궤적 판의 '그 결과: [받아 먹음] 주점에서 무료 식사를 받았다 (남은 무료 식사 1끼)'",
      "무료" not in status_section(wV) and "끼" not in status_section(wV) and not [k_ for k_ in oV if "free" in k_]
      and wV.count("남은 무료 식사") == 1 and "- 그 결과: [받아 먹음] 주점에서 무료 식사를 받았다 (남은 무료 식사 1끼)" in wV,
      [ln for ln in wV.split("\n") if "무료" in ln])
oV2 = dV.view(v2, botsV)
wV2 = brains._wire(oV2, NAMES, compose=True)
check("⑤ 곁의 사람(봇2)의 관측에는 봇1 의 남은 횟수가 없다 — 목격 '식사를 받아 먹었다'뿐(관측 글에 '남은 무료' 없음)",
      "남은 무료" not in wV2 and "식사를 받아 먹었다" in json.dumps(oV2.get("witnessed") or [], ensure_ascii=False), [ln for ln in wV2.split("\n") if "식사" in ln][:4])
pub = IG.public(rV)
check("⑤ 공개 투영은 결과의 free_left·free_line 을 남긴다(결과 문장의 재료 — 그 사람 자신의 결과) · 욕구 숫자(before·after·tol)는 지금처럼 걷는다 · 층 집계는 라벨만('받아 먹음' ×1 — 횟수 글 없음)",
      pub.get("free_left") == 1 and pub.get("free_line") == "주점에서 무료 식사를 받았다 (남은 무료 식사 1끼)" and not ({"before", "after", "tol"} & set(pub))
      and (v1.get("floor") or {}).get("n", {}).get("받아 먹음") == 1, (pub, (v1.get("floor") or {}).get("n")))

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑥ 저장·이어가기")
rsrc = src("show_runner.py")
carry_src = rsrc.split("def _carry(")[1].split("\n    def ")[0]
wake_src = rsrc.split("def _wake(")[1].split("\n    def ")[0]
check("⑥ 층 이월(_carry): 무료 끼니 칸이 그 몸을 따라간다(사본) · 부활(_wake)은 _carry 를 쓰고 무료를 되돌리지 않는다(판 시작에만 받는다 — G.NE.reset 은 욕구만)",
      'n["free"] = dict(b.get("free") or {})' in carry_src and "_carry(" in wake_src and 'n["free"]' not in wake_src
      and "free" not in src("needs.py").split("def reset(")[1].split("\ndef ")[0])
dS, botsS = town(on=True)
for b_ in botsS:
    b_.pop("free")
waitS = copy.deepcopy(botsS[2])
botsS[1]["free"] = {"meal": 1}                         # 이미 칸이 있는 몸(같은 판 안에서 한 번 이관된 것) — 그대로
snap12 = {"version": 2, "state_version": 12, "d": dS, "bots": botsS[:2], "sheets": SHEETS, "waiting": {"3": waitS}}
up = S.upgrade(pickle.loads(pickle.dumps(snap12)))   # 이 프로세스가 방금 만든 바이트만 되읽는다(피클 왕복 = 이어가기와 같은 길)
check("⑥ 이관 12→13: 판 13 · 옛 몸은 이미 시작한 판이라 0끼(free {}) · 이미 칸이 있는 몸은 그대로 · 부활 대기 몸도 · 다시 올려도 같다",
      S.STATE_VERSION == 13 and S.MIGRATIONS[12] is S._m12_free and up["state_version"] == 13
      and up["bots"][0].get("free") == {} and up["bots"][1].get("free") == {"meal": 1} and up["waiting"]["3"].get("free") == {}
      and S.upgrade(copy.deepcopy({**up, "state_version": 12}))["bots"] == up["bots"], ([b_.get("free") for b_ in up["bots"]], up["waiting"]["3"].get("free")))
dU, botsU = up["d"], up["bots"]
put(botsU[0], stand_by(dU, by_name(dU, "주점"), botsU))
rU = buy(dU, botsU[0], botsU)
check("⑥ 이관한 옛 몸(0끼)은 바로 값을 낸다 — 지금 문장 그대로 · 골드 5 → 2 · 주인의 말 없음(옛 판에서는 끝을 알릴 무료가 없었다)",
      rU["result"] == "need_fill" and "free_left" not in rU and botsU[0]["gold"] == 2 and brains._last_prose(rU) == PAID and R.free_end_says(dU, botsU[0], rU) == [], rU)
dP, botsP = town(on=True)
botsP[0]["free"] = {"meal": 1}
dP2, botsP2 = pickle.loads(pickle.dumps((dP, botsP)))   # 이 프로세스가 방금 만든 바이트만 되읽는다(스냅샷과 같은 길)
put(botsP2[0], stand_by(dP2, by_name(dP2, "주점"), botsP2))
rP = buy(dP2, botsP2[0], botsP2)
check("⑥ 피클 왕복(스냅샷) 뒤에도 남은 횟수 그대로 — 1끼 → 마지막 무료(0끼 · 주인의 말)",
      rP.get("free_left") == 0 and botsP2[0]["gold"] == 5 and R.free_end_says(dP2, botsP2[0], rP) == [("주점 주인", LINE_END, "1")], rP)

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑦ 러너 판(실제 러너 · 각본 두뇌 · NPC 두뇌 켬 — 스텁)")
NPC_PROMPTS = []


def stub_call(prompt, model="haiku"):
    if prompt.lstrip().startswith("# 마을 사람"):
        NPC_PROMPTS.append(prompt)
        return '{"line": "주인의 두뇌 문장"}', None
    return "", None


SCRIPT = {"placed": False, "step": 0, "inbox": {}, "wire": {}, "stop": None, "buys": []}


def stub_think(d, bots, inbox, on_error=None, **_kw):
    """각본 두뇌 — 봇1 만: 주점 곁으로 옮겨(처음 한 번) 식사 사기 → 곱게 멈춤 요청 → (이어가기) 사기 → 사기 → 기다림. 봇2·3 은 기다린다.
    봇1 의 편지함과 완성 관측 글을 틱마다 적어 둔다(들은 말 확인)."""
    out = {}
    tav_ = next(f for f in d.features.values() if f.name == "주점")
    for b in bots:
        if b.get("order") or not b["alive"] or b["won"]:
            continue
        dec = {"type": "wait", "reason": "각본", "src": "haiku"}
        if b["char"] == "1":
            if not SCRIPT["placed"]:
                SCRIPT["placed"] = True
                put(b, stand_by(d, tav_, [o for o in bots if o is not b]))
                b["order"], b["path"] = None, []
            msgs = list((inbox or {}).get("1") or [])
            o_ = d.view(b, bots)
            o_["messages"] = [{**brains._heard(m, "1", None), **({"to_me": True} if (G.addressed_to(m, "1") and m.get("to") != "all") else {})} for m in msgs]
            SCRIPT["inbox"][d.turn], SCRIPT["wire"][d.turn] = msgs, brains._wire(o_, NAMES, compose=True)
            k = SCRIPT["step"]
            if k in (0, 2, 3):
                b["needs"]["hunger"] = 30
                dec = {"type": "use", "target": gid_of(d, "식사"), "reason": "각본 %d" % k, "src": "haiku"}
                SCRIPT["buys"].append(d.turn)
                SCRIPT["step"] += 1
            elif k == 1:
                RC.request_stop(R.STATE, pages=False)   # 다음 틱 머리에서 곱게 멈춘다(스냅샷 = 그 틱 전)
                SCRIPT["stop"] = d.turn
                SCRIPT["step"] += 1
        out[b["char"]] = dec
    return out


def run(turns, st, resume=False, think=None, more=None):
    """러너 풀런(스텁 — NPC 두뇌가 켜진 판: 백엔드 이름만 claude_cli, 콜은 stub_call). st·resume = 같은 state 폴더에서 그 스냅샷으로 이어 돈다.
    think = 각본 두뇌(기본 stub_think) · more = 러너 모듈 값 더 덮기(예: 솔로 판)."""
    env = {"DUNGEON_BRAIN_BACKEND": "claude_cli"}
    old_env = {k_: os.environ.get(k_) for k_ in env}
    patch = {"NPC_REPLY_ON": True, "NPC_HAIL_ON": False, "RESUME_PATH": os.path.join(st, S.PKL) if resume else "", **(more or {})}
    old_mod = {k_: getattr(R, k_) for k_ in patch}
    old = (R.STATE, R.MAX_TURNS, R.PAUSE_LIMIT_SEC, brains._call_claude, brains.think_all, brains.social_all)
    os.environ.update(env)
    for k_, v_ in patch.items():
        setattr(R, k_, v_)
    R.STATE, R.MAX_TURNS, R.PAUSE_LIMIT_SEC = st, int(turns), 2
    brains._call_claude, brains.think_all, brains.social_all = stub_call, (think or stub_think), (lambda d, bots, inbox: {})
    log_ = io.StringIO()
    try:
        with contextlib.redirect_stdout(log_), contextlib.redirect_stderr(log_):
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
    if not os.path.isfile(os.path.join(st, "stream.jsonl")):     # 판이 열리지도 못했다 — 러너가 남긴 말을 붙여 죽는다(원인을 숨기지 않게)
        raise RuntimeError("러너 판이 기록을 남기지 않았다: " + log_.getvalue()[-1500:])
    with open(os.path.join(st, "stream.jsonl"), encoding="utf-8") as f:
        rows_ = [json.loads(ln) for ln in f if ln.strip()]
    with open(os.path.join(st, "events.log"), encoding="utf-8") as f:
        return rows_, f.read()


st7 = tempfile.mkdtemp(prefix="run_free_", dir=ROOT)
rows7a, _ev7a = run(14, st7)
snap_ok = os.path.isfile(os.path.join(st7, S.PKL))
rows7, ev7 = run(14, st7, resume=True)
ticks7 = [r_ for r_ in rows7 if r_["kind"] == "tick"]
buys7 = [(r_["turn"], e) for r_ in ticks7 for e in (r_.get("events") or []) if str(e.get("char")) == "1" and e.get("via") == "buy"]
gold7 = {r_["turn"]: next(b_ for b_ in r_["bots"] if b_["char"] == "1")["gold"] for r_ in ticks7}
res7 = next((r_ for r_ in rows7 if r_["kind"] == "resume"), None)
check("⑦ 판이 돈다 — 무료 1끼 → 곱게 멈춤(stopped · 스냅샷) → 이어가기(resume) → 둘째 끼 → 셋째 끼: 스트림 need_fill 의 free_left 1 · 0 · 없음(값) · 그 틱 tick.bots[].gold 5 · 5 · 2",
      snap_ok and any(r_["kind"] == "stopped" for r_ in rows7a) and res7 is not None and len(buys7) == 3
      and [(e["result"], e.get("free_left")) for _t, e in buys7] == [("need_fill", 1), ("need_fill", 0), ("need_fill", None)]
      and [gold7[t_] for t_, _e in buys7] == [5, 5, 2] and buys7[0][0] < res7["turn"] <= buys7[1][0],
      (snap_ok, res7 and res7.get("turn"), [(t_, e.get("result"), e.get("free_left"), gold7.get(t_)) for t_, e in buys7], SCRIPT["buys"]))
t_last = buys7[1][0] if len(buys7) > 1 else None
end_msgs = [(r_["turn"], m) for r_ in ticks7 for c_, ms in (r_.get("inbox") or {}).items() for m in ms if m.get("text") == LINE_END and c_ == "1"]
check("⑦ 마지막 무료 끼니 다음 틱 편지함(tick.inbox)에 주인의 말 — {from 'npc:주점 주인', text 정의의 문장, to 봇1} · 판 전체에서 봇1 에게 한 번 · 셋째 끼(값) 뒤엔 없다",
      t_last is not None and end_msgs == [(t_last + 1, {"from": "npc:주점 주인", "text": LINE_END, "turn": t_last, "to": "1"})],
      (t_last, end_msgs))
w7 = SCRIPT["wire"].get(t_last + 1, "") if t_last is not None else ""
heard7 = w7.split("## 들은 말", 1)[1].split("\n## ", 1)[0] if "## 들은 말" in w7 else (w7.split("## 동료가 한 말", 1)[1].split("\n## ", 1)[0] if "## 동료가 한 말" in w7 else "")
check("⑦ 그 틱 봇1 의 완성 관측 글: 들은 말 절에 주점 주인의 그 말 · 결과 '[받아 먹음] 주점에서 무료 식사를 받았다 (남은 무료 식사 0끼)' · '네 상태' 절엔 무료 횟수 없음",
      LINE_END in heard7 and "주점 주인" in heard7 and "[받아 먹음] 주점에서 무료 식사를 받았다 (남은 무료 식사 0끼)" in w7 and "무료" not in status_section(w7),
      [ln for ln in w7.split("\n") if "무료" in ln or "공짜" in ln or ln.startswith("## ")][:12])
check("⑦ NPC 두뇌가 켜진 판(스텁)에서도 주인의 말은 정의의 문장 — 두뇌 콜 0번 · 두뇌 문장('주인의 두뇌 문장')은 어디에도 없다 · events.log '주점 주인 💬 \"공짜로 …\"' 한 줄",
      not NPC_PROMPTS and "주인의 두뇌 문장" not in json.dumps(rows7, ensure_ascii=False) and ev7.count('주점 주인 \U0001f4ac "%s"' % LINE_END) == 1,
      (len(NPC_PROMPTS), ev7.count(LINE_END)))
lines7 = [ln for ln in ev7.split("\n") if "식사" in ln and "봇1" in ln]
check("⑦ 관전 로그(events.log): 무료 두 끼는 '주점에서 무료 식사를 받았다 (남은 무료 식사 1끼 · 0끼)' · 셋째는 지금 문장 그대로",
      any("주점에서 무료 식사를 받았다 (남은 무료 식사 1끼)" in ln for ln in lines7) and any("주점에서 무료 식사를 받았다 (남은 무료 식사 0끼)" in ln for ln in lines7)
      and any(PAID in ln for ln in lines7), lines7[:4])

SCRIPT2 = {"placed": False, "step": 0, "inbox": {}, "free": {}, "buys": [], "down": None}


def stub_think2(d, bots, inbox, on_error=None, **_kw):
    """각본 두뇌(1인 파티 — 혼자 마을에 선 모험가) — 봇1 만: 주점 곁으로(처음 한 번) → 무료 한 끼 → 마지막 무료 끼니 + 같은 틱 주인에게 지목한 말 →
    다음 틱 던전 입구 곁으로 옮겨 내려감 → 지하 1층에서 기다림. 틱마다 봇1 의 편지함·무료 칸을 (층, 틱)으로 적어 둔다."""
    out = {}
    for b in bots:
        if b.get("order") or not b["alive"] or b["won"]:
            continue
        dec = {"type": "wait", "reason": "각본", "src": "haiku"}
        if b["char"] == "1":
            SCRIPT2["inbox"][d.turn] = list((inbox or {}).get("1") or [])
            SCRIPT2["free"][(d.depth, d.turn)] = dict(b.get("free") or {})
            k = SCRIPT2["step"]
            if getattr(d, "town", False) and k <= 2:
                if not SCRIPT2["placed"]:
                    SCRIPT2["placed"] = True
                    put(b, stand_by(d, by_name(d, "주점"), [o for o in bots if o is not b]))
                    b["order"], b["path"] = None, []
                if k < 2:
                    b["needs"]["hunger"] = 30
                    d.view(b, bots)
                    dec = {"type": "use", "target": gid_of(d, "식사"), "reason": "각본 %d" % k, "src": "haiku",
                           **({"say": "내일도 공짜예요?", "to": "npc:주점 주인"} if k == 1 else {})}
                    SCRIPT2["buys"].append(d.turn)
                else:
                    ex = next(f for f in d.features.values() if f.type == "exit")
                    put(b, stand_by(d, ex, [o for o in bots if o is not b]))
                    b["order"], b["path"] = None, []
                    d.view(b, bots)
                    dec = {"type": "use", "target": "exit", "reason": "각본 내려감", "src": "haiku"}   # 계단은 관측 ID exit
                    SCRIPT2["down"] = d.turn
                SCRIPT2["step"] += 1
        out[b["char"]] = dec
    return out


NPC_PROMPTS[:] = []
st8 = tempfile.mkdtemp(prefix="run_free_one_", dir=ROOT)
P1 = os.path.join(ROOT, "party_one.json")             # 1인 파티(혼자 마을에 선 모험가) — 솔로 판(DUNGEON_SOLO)은 러너가 마을과 함께 쓰지 않는다(주점이 없는 판)
with open(os.path.join(HERE, "party.json"), encoding="utf-8") as f_:
    PJ1 = json.load(f_)
with open(P1, "w", encoding="utf-8") as f_:
    json.dump({"1": PJ1["1"]}, f_, ensure_ascii=False)
rows8, ev8 = run(12, st8, think=stub_think2, more={"PARTY_FILE": P1})
tb8 = SCRIPT2["buys"][1] if len(SCRIPT2["buys"]) > 1 else None
in8 = SCRIPT2["inbox"].get(tb8 + 1, []) if tb8 is not None else []
end8 = [m for m in in8 if m.get("from") == "npc:주점 주인" and m.get("text") == LINE_END]
brain8 = [m for m in in8 if m.get("from") == "npc:주점 주인" and m.get("text") == "주인의 두뇌 문장"]
rep8 = [r_ for r_ in rows8 if r_["kind"] == "tick" and r_["turn"] == tb8 for r_ in (r_.get("npc_replies") or [])] if tb8 is not None else []
check("⑦ 1인 파티(혼자 선 모험가): 마지막 무료 끼니 다음 틱 봇1 편지함에 주인의 정해진 말 한 번(to 봇1) · 같은 틱 주인에게 지목한 말엔 두뇌가 따로 되받는다 — "
      "두 말이 다 닿는다(되받기 두뇌 콜 1번 · 정해진 말은 두뇌를 안 거친다)",
      rows8[0].get("kind") == "run_meta" and SCRIPT2["buys"] and len(end8) == 1 and end8[0].get("to") == "1" and len(brain8) == 1
      and [(r_.get("npc"), str(r_.get("char")), r_.get("line")) for r_ in rep8] == [("주점 주인", "1", "주인의 두뇌 문장")] and len(NPC_PROMPTS) == 1,
      (SCRIPT2["buys"], in8, rep8, len(NPC_PROMPTS)))
low8 = sorted((t_, f_) for (dep_, t_), f_ in SCRIPT2["free"].items() if dep_ == 1)
check("⑦ 실제 층 이동(마을 → 지하 1층 — 러너 재스폰 + _carry): 내려간 몸의 무료 끼니는 내려가기 전 그대로 {meal: 0}(스폰 값 2끼가 아니다)",
      SCRIPT2["down"] is not None and low8 and all(f_ == {"meal": 0} for _t, f_ in low8) and low8[0][0] > SCRIPT2["down"],
      (SCRIPT2["down"], low8[:3], sorted(SCRIPT2["free"])[-4:],
       [(r_["turn"], e.get("type"), e.get("result"), e.get("target")) for r_ in rows8 if r_["kind"] == "tick" and r_["turn"] in (SCRIPT2["down"] or 0, (SCRIPT2["down"] or 0) + 1)
        for e in (r_.get("events") or []) if str(e.get("char")) == "1"]))

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑧ 배선")
sf = src("STREAM_FORMAT.md")
check("⑧ STREAM_FORMAT: 주점 무료 식사 절(정의 free·line_free · 몸 free · need_fill 의 free_left·free_line · line_free_end 다음 틱 inbox · 저장 판 12 → 13 _m12_free)",
      "## 주점 무료 식사" in sf and all(k_ in sf for k_ in ("`free`", "`line_free`", "free_left", "free_line", "`line_free_end`", "_m12_free", "12 → 13")))
check("⑧ _run_gates.sh 에 verify_free_meal 등록 · VERSION 0.5.25 이상 · 문서(PATCH_NOTES·CHANGELOG)에 0.5.25",
      "verify_free_meal" in src("_run_gates.sh") and tuple(int(x) for x in src("VERSION").strip().split(".")) >= (0, 5, 25)
      and "0.5.25" in src("docs", "PATCH_NOTES.md") and "p0.5.25" in src("docs", "CHANGELOG.md"))

shutil.rmtree(ROOT, ignore_errors=True)
print()
if C.failed:
    print("FAIL — %d/%d" % (C.failed, C.n))
    sys.exit(1)
print("ALL PASS — verify_free_meal (p0.5.25 주점 무료 식사 → 길드 의뢰로 잇기: %d checks · 정의·검증기 · 무료 2끼·그 뒤 값 · 배부름 거절 · 동료·NPC 무관 · 숫자 누설 · 이관·이어가기 · 러너 판 · 배선, 실 LLM 0콜)" % C.n)

# -*- coding: utf-8 -*-
"""p0.5.27 무료 식사 걷어내기 → 시작 골드 10 · 돈이 모자랄 때 주점 주인이 길드로 안내(DECISIONS 10-17) — 헤들리스 검증. LLM 0콜.
0.5.25 의 주점 무료 식사(정의 free·결과 문장·몸의 칸·주인의 마지막 끼니 말)는 전부 걷었다. 새 몸은 골드 10(⚠️임시)으로 시작하고 주점 식사는 늘 3골드 —
세 끼를 사 먹으면 1골드가 남아 네 번째 끼니는 사지 못한다(기존 거절 결과 too_poor 그대로). 그때 주점 주인의 정해진 말(말 파일 — 문장 임시)이
들은 말(다음 틱 편지함 — NPC 의 답과 같은 길)로 그 손님과 곁에서 듣는 사람에게 닿는다(NPC 두뇌 무관 · 거절될 때마다).
게이트:
  ① 정의·검증기: 주점(마을 생활 판) 식사 3골드 — 옛 칸 없음 · 주인의 말 = 말 파일 글자 그대로(끈 판엔 없다) · 검증기 거절 4종(가게를 맡지 않은 사람의 말 · 옛 칸 셋)
  ② 시작 골드: 상수 10 · 스폰한 몸 골드 10 · 몸에 옛 무료 칸 없음
  ③ 주점 세 끼 → 네 번째 거절: 10 → 7 → 4 → 1 · 넷째 too_poor(지금 문장 그대로) + 주인의 말 한 줄 · 그 손님과 곁의 사람에게(멀리 선 사람은 못 듣는다) · 다섯째도 말
  ④ 대사 없음: 배부름 거절(골드가 모자라도) · 다른 가게(잡화점 물약·휴대식)의 돈 부족 · 묵기 값 부족 · 맡은 사람이 없는 세계 — NPC 두뇌를 부르지 않는다 ·
     데이터만으로: 다른 가게 주인의 정의에 같은 칸을 두면 그 사람이 말한다(묵기는 사기가 아니라 여전히 없다)
  ⑤ 이관 13→14: 옛 몸의 무료 칸을 버린다(지금 세계·다른 세계·부활 대기) · 골드 그대로 · 주인의 말 다시 읽기 · 12 판도 · 다시 올려도 같다 · 실제 로더(피클 파일)
  ⑥ 러너 판(실제 러너 · 각본 두뇌 · NPC 두뇌 켬 — 스텁): 첫 틱 골드 10 · 세 끼 → 거절 두 번 → 다음 틱 편지함(산 사람·곁의 사람)에 주인의 말 · 관측 '들은 말' ·
     events.log · NPC 두뇌 0번 · 스트림·로그에 옛 무료 칸·문장 없음 · p0527b 1인 파티 실제 층 이동 뒤 시작값과 다른 지갑(7) 그대로(부활은 _carry 소스)
  ⑦ 잔재: 코드·정의·말 파일·게이트 목록에 옛 무료 식사의 칸·문장·함수가 남지 않는다(스냅샷 이관의 버리는 자리만)
  ⑧ 배선: _run_gates.sh · STREAM_FORMAT · VERSION 0.5.27 · 문서 · 저장 판 14
"""
import ast
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
ROOT = tempfile.mkdtemp(prefix="wl_startgold_")
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


def _no_real_backend(prompt, model):                 # 이중 안전핀: 어떤 길로도 진짜 백엔드는 안 부른다(⑥ 은 백엔드 이름만 claude_cli 로 돌린다)
    raise AssertionError("real backend must not be called in a gate")


brains._call_cli = brains._call_anthropic = brains._call_gemini = brains._call_openai = _no_real_backend
import dungeon_gm as G                               # noqa: E402
import entities as ENT                               # noqa: E402
import interactables as IA                           # noqa: E402
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
LINE = "돈 떨어졌으면 길드 가서 의뢰라도 받아 와."
POOR = "주점에서 식사를 사려 했다 — 값이 3골드인데 지닌 골드가 1다"
KEEPER_NAME = "주점 주인"


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


def far_from(d, f, bots):
    """f(주점 주인)의 말이 들리지 않는 바닥 칸 하나 — 멀리 선 사람(d.hears 가 거짓 · 결정론 순서: 먼 칸부터)."""
    taken = {(o["x"], o["y"]) for o in bots}
    cells = sorted(((x, y) for y in range(len(d.grid)) for x in range(len(d.grid[0]))
                    if d.grid[y][x] == G.FLOOR and d.feature_at(x, y) is None and (x, y) not in taken),
                   key=lambda c: (-max(abs(c[0] - f.x), abs(c[1] - f.y)), c[1], c[0]))
    return next(c for c in cells if not d.hears({"x": c[0], "y": c[1]}, f.x, f.y))


def act(d, b, bots, action):
    d.view(b, bots)                                   # 관측 = 참조(_target_refs)를 새로 짓는다(실판과 같은 순서)
    return d.act(b, dict(action), bots)


def gid_of(d, name, shop=None):
    return next(g["gid"] for g in IA.goods(d) if g["name"] == name and (shop is None or g["fid"] == shop.id))


def buy(d, b, bots, name="식사", hunger=30, shop=None):
    """배고픔을 맞춘 몸으로 상품을 산다(buy g<n> — p0.5.29 전엔 use g<n>)."""
    b["needs"]["hunger"] = hunger
    return act(d, b, bots, {"type": "buy", "target": gid_of(d, name, shop)})


# ─────────────────────────────────────────────────────────────────────────────
print("── ① 정의·검증기")
TAV_USE = ENT.comps_of("tavern", True).get("use") or {}
TK_LIFE = ENT.npc("tavern_keeper", life=True)
check("① 주점(마을 생활 판 life.use) = 식사 3골드 그대로 — sells [{item meal, price 3}] · 옛 칸(free·line_free) 없음 · 가게 쓰임 칸 = sells·buys · 끈 판 주점엔 쓰임이 없다",
      TAV_USE == {"kind": "shop", "sells": [{"item": "meal", "price": 3}]} and ENT.USE_KINDS["shop"] == ("sells", "buys")
      and not ENT.comps_of("tavern", False).get("use"), TAV_USE)
check("① 주점 주인(마을 생활 판 life.npc.line_too_poor) = 말 파일 글자 그대로 '돈 떨어졌으면 길드 가서 의뢰라도 받아 와.' · 끈 판엔 없다 · 맡은 가게 = 주점 · "
      "말 파일에 옛 칸(life.npc.line_free_end · 주점 life.use.line_free) 없음 · 칸 설명(words.DESC)",
      TK_LIFE.get("line_too_poor") == LINE and ENT.npc("tavern_keeper", life=False).get("line_too_poor") is None and TK_LIFE.get("shop") == "tavern"
      and WD.parse(src("prompts", "world", "npc", "tavern_keeper.md"))[0].get("life.npc.line_too_poor") == LINE
      and "line_free_end" not in TK_LIFE and "life.npc.line_free_end" not in WD.parse(src("prompts", "world", "npc", "tavern_keeper.md"))[0]
      and "life.use.line_free" not in WD.parse(src("prompts", "world", "building", "tavern.md"))[0]
      and WD.describe("npc", "life.npc.line_too_poor").startswith("돈이 모자랄 때 — "), TK_LIFE.get("line_too_poor"))
check("① 맡은 가게의 말 칸을 가진 사람은 주점 주인 하나뿐(잡화점·장비점·여관 주인은 없다 — 다른 가게의 돈 부족엔 말이 없다)",
      sorted(e["id"] for e in ENT.by_kind("npc") for life in (False, True) if ENT.npc(e["id"], life=life).get("line_too_poor")) == ["tavern_keeper"]
      and all(ENT.npc(n, life=True).get("shop") for n in ("item_merchant", "gear_merchant", "innkeeper")))


def problems_with(edit, words_edit=None):
    """정의 사본(임시 폴더)에 edit(폴더) 를 가하고 읽은 문제 목록(글) — 말 파일은 리포의 것을 복사해 words_edit(폴더)를 가한 사본으로 합친다
    (말 칸을 더하는 시험은 JSON 자리('@prompts')와 말 파일 칸을 같이 — 합치기가 성공한 채로 그 칸의 문제만 나오게)."""
    root = tempfile.mkdtemp(prefix="defs_", dir=ROOT)
    for p in glob.glob(os.path.join(ENT.ROOT, "*", "*.json")):
        dst = os.path.join(root, os.path.basename(os.path.dirname(p)))
        os.makedirs(dst, exist_ok=True)
        shutil.copy(p, dst)
    edit(root)
    wroot = os.path.join(tempfile.mkdtemp(prefix="words_", dir=ROOT), "world")
    shutil.copytree(os.path.join(HERE, "prompts", "world"), wroot)
    if words_edit:
        words_edit(wroot)
    try:
        ENT.read(root, words_root=wroot)
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


def wadd(kind, eid, path, text):
    """말 파일 사본에 칸 하나(## `path` + 글)를 덧붙이는 편집."""
    def go(wroot):
        with open(os.path.join(wroot, kind, eid + ".md"), "a", encoding="utf-8") as f:
            f.write("\n## `%s` — 시험\n%s\n" % (path, text))
    return go


BAD = [("가게를 맡지 않은 사람의 line_too_poor",
        lambda r: jedit(r, "npc", "temple_attendant", lambda d_: d_["comps"]["npc"].update(line_too_poor="@prompts")),
        wadd("npc", "temple_attendant", "npc.line_too_poor", "돈이 없으면 돌아가."), "npc.line_too_poor(손님의 돈이 모자랄 때의 말)는 가게를 맡은 사람(npc.shop)만"),
       ("주점 식사에 옛 칸 free", lambda r: jedit(r, "building", "tavern", lambda d_: d_["comps"]["life"]["use"]["sells"][0].update(free=2)), None,
        "use(shop).sells 는 [{item: 오브젝트 정의 id, price: 정수≥1}] 목록"),
       ("주점 쓰임에 옛 칸 line_free", lambda r: jedit(r, "building", "tavern", lambda d_: d_["comps"]["life"]["use"].update(line_free="@prompts")),
        wadd("building", "tavern", "life.use.line_free", "주점에서 받았다 ({n})"), "use(shop) 가 모르는 칸 ['line_free']"),
       ("주인에게 옛 칸 line_free_end", lambda r: jedit(r, "npc", "tavern_keeper", lambda d_: d_["comps"]["life"]["npc"].update(line_free_end="@prompts")),
        wadd("npc", "tavern_keeper", "life.npc.line_free_end", "끝이야."), "life.npc 는 문장 칸")]
errs = {nm_: problems_with(fn_, wf_) for nm_, fn_, wf_, _w in BAD}
check("① 검증기 거절 4종을 로드 단계에서 — 가게를 맡지 않은 사람의 돈 부족 말 · 옛 칸 셋(주점 식사의 free · 주점 쓰임의 line_free · 주인의 line_free_end) — "
      "말 파일 합치기는 성공한 채로 그 문제 한 줄만 · 리포 정의는 통과",
      all(w_ in errs[nm_] and "\n" not in errs[nm_] and ".md" not in errs[nm_] for nm_, _f, _wf, w_ in BAD) and problems_with(lambda r: None) == "",
      {nm_: errs[nm_][:120] for nm_, _f, _wf, w_ in BAD if not (w_ in errs[nm_] and "\n" not in errs[nm_] and ".md" not in errs[nm_])})

# ─────────────────────────────────────────────────────────────────────────────
print("── ② 시작 골드")
dA, botsA = town(on=True)
a1, a2, a3 = botsA
check("② 시작 골드 상수 START_GOLD = 10(⚠️임시) · 스폰한 몸마다 골드 10 · 끈 판 마을에서 스폰한 몸도 10 · 몸에 옛 무료 칸(free)이 없다",
      G.START_GOLD == 10 and all(b_["gold"] == 10 for b_ in botsA) and all(b_["gold"] == 10 for b_ in town(on=False)[1])
      and not any("free" in b_ for b_ in botsA), [(b_["gold"], sorted(k_ for k_ in b_ if "free" in k_)) for b_ in botsA])
gm_src = src("dungeon_gm.py")
check("② 시작 골드의 자리 = dungeon_gm.START_GOLD 한 곳(스폰 'gold': START_GOLD · 옛 판 이관 5→6 도 이 값) · 주석이 지금 값의 뜻(세 끼 뒤 1골드)을 말한다",
      "'gold': START_GOLD," in gm_src.split("def spawn(")[1].split("\ndef ")[0] and 'b.setdefault("gold", G.START_GOLD)' in src("snapshot.py")
      and "START_GOLD = 10 " in gm_src and "세 끼 사 먹으면 1골드가 남아" in gm_src and "첫 끼니를 먹으면 다음 끼니 값이 모자란 크기" not in gm_src)

# ─────────────────────────────────────────────────────────────────────────────
print("── ③ 주점 세 끼 → 네 번째 거절")
TAV, KEEPER = by_name(dA, "주점"), by_name(dA, KEEPER_NAME)
put(a1, stand_by(dA, TAV, botsA))
put(a2, (KEEPER.x, KEEPER.y + 1) if dA.grid[KEEPER.y + 1][KEEPER.x] == G.FLOOR and dA.feature_at(KEEPER.x, KEEPER.y + 1) is None
    else stand_by(dA, KEEPER, botsA, skip=[(a1["x"], a1["y"])]))
put(a3, far_from(dA, KEEPER, botsA))
rs = [buy(dA, a1, botsA) for _ in range(3)]
check("③ 세 끼 = 값 3골드씩 — need_fill{via buy, price 3} · 골드 10 → 7 → 4 → 1 · 문장 '주점에서 식사를 사 먹었다 — 3골드를 냈다(남은 골드 N)' · 꼬리표 '사 먹음' · 주인의 말 없음",
      [(r_["result"], r_.get("via"), r_.get("price"), r_.get("gold")) for r_ in rs] == [("need_fill", "buy", 3, 7), ("need_fill", "buy", 3, 4), ("need_fill", "buy", 3, 1)]
      and a1["gold"] == 1 and [brains._last_prose(r_) for r_ in rs] == ["주점에서 식사를 사 먹었다 — 3골드를 냈다(남은 골드 %d)" % g_ for g_ in (7, 4, 1)]
      and all(G.event_tags(r_)[0][:2] == ("use", "사 먹음") for r_ in rs) and not any(R.too_poor_says(dA, a1, r_) for r_ in rs)
      and not any(k_ in r_ for r_ in rs for k_ in ("free_left", "free_line")), [(r_["result"], r_.get("gold"), brains._last_prose(r_)) for r_ in rs])
r4 = buy(dA, a1, botsA)
says4 = R.too_poor_says(dA, a1, r4)
check("③ 네 번째 = 거절(기존 too_poor 그대로 — 값 3 · 지닌 1 · 배고픔·골드 그대로) · 문장 '주점에서 식사를 사려 했다 — 값이 3골드인데 지닌 골드가 1다' · 꼬리표 '[헛손질] 식사 — 3골드 · 지닌 1' · "
      "결과에 새 칸 없음 · 주인의 말 한 줄 = (주점 주인, 정의의 문장 그대로, 못 산 사람)",
      r4["result"] == "too_poor" and r4["use_kind"] == "shop" and r4["price"] == 3 and r4["gold"] == 1 and a1["gold"] == 1 and a1["needs"]["hunger"] == 30
      and brains._last_prose(r4) == POOR and G.event_tags(r4) == [("misc", "헛손질", "식사 — 3골드 · 지닌 1")]
      and not any("free" in k_ or "line" in k_ for k_ in r4) and says4 == [(KEEPER_NAME, LINE, "1")], (r4, says4))
inbox4 = {}
R.deliver_npc_says(dA, botsA, inbox4, says4, dA.turn)
MSG = {"from": "npc:" + KEEPER_NAME, "text": LINE, "turn": dA.turn, "to": "1"}
check("③ 배달(NPC 의 답과 같은 길 deliver_npc_says) — 다음 틱 편지함: 못 산 사람(봇1)과 곁에서 듣는 사람(봇2)에게 같은 말 {from 'npc:주점 주인', text, to 봇1} · 멀리 선 사람(봇3 — 주인의 말이 안 들리는 칸)은 없다",
      inbox4.get("1") == [MSG] and inbox4.get("2") == [MSG] and "3" not in inbox4 and dA.hears(a2, KEEPER.x, KEEPER.y) and not dA.hears(a3, KEEPER.x, KEEPER.y),
      inbox4)
r5 = buy(dA, a1, botsA)
check("③ 다섯 번째도 거절이면 주인은 또 말한다(거절될 때마다 — 몸에 남기는 칸 없음)",
      r5["result"] == "too_poor" and R.too_poor_says(dA, a1, r5) == [(KEEPER_NAME, LINE, "1")] and not any("too_poor" in k_ or "free" in k_ for k_ in a1), r5)

# ─────────────────────────────────────────────────────────────────────────────
print("── ④ 대사 없음")
r6 = buy(dA, a1, botsA, hunger=100)
a2["gold"] = 0
put(a2, stand_by(dA, TAV, botsA))
r6b = buy(dA, a2, botsA, hunger=100)
check("④ 배가 부르면 사지 않는다(need_none{why full} — 값을 보기 전에 몸이 거절) · 골드 1 · 0 이어도 같은 거절 · 주인의 말 없음",
      r6["result"] == "need_none" and r6.get("via") == "buy" and r6b["result"] == "need_none" and a1["gold"] == 1 and a2["gold"] == 0
      and R.too_poor_says(dA, a1, r6) == [] and R.too_poor_says(dA, a2, r6b) == [], (r6, r6b))
GS = by_name(dA, "잡화점")
put(a1, stand_by(dA, GS, botsA))
r7, r7b = buy(dA, a1, botsA, name="회복 물약", shop=GS), buy(dA, a1, botsA, name="휴대식", shop=GS)
check("④ 다른 가게의 돈 부족(잡화점 물약 10 · 휴대식 2 — 지닌 1) = too_poor 그대로 · 주인의 말 없음(잡화점 주인 정의에 그 칸이 없다)",
      r7["result"] == "too_poor" and r7["price"] == 10 and r7b["result"] == "too_poor" and r7b["price"] == 2
      and R.too_poor_says(dA, a1, r7) == [] and R.too_poor_says(dA, a1, r7b) == [], (r7, r7b))
INN = by_name(dA, "일반 여관")
put(a1, stand_by(dA, INN, botsA))
r8 = act(dA, a1, botsA, {"type": "use", "target": "f%d" % INN.id})
check("④ 묵기 값 부족(일반 여관 4 — 지닌 1) = too_poor{use_kind lodge} 그대로 · 말 없음",
      r8["result"] == "too_poor" and r8["use_kind"] == "lodge" and R.too_poor_says(dA, a1, r8) == [], r8)
dX = copy.deepcopy(dA)
item_seller, inn_keeper = IA.keeper_of(dA, "f%d" % GS.id), IA.keeper_of(dA, "f%d" % INN.id)
for nm_ in (item_seller, inn_keeper):                 # 세계의 정의 사본(npc_defs)에만 칸을 더한다 — 데이터만 바꾼다(코드 그대로)
    if nm_:
        dX.npc_defs[nm_] = dict(dX.npc_defs[nm_], line_too_poor="시험 문장")
r8s = dict(r8, shop_id="f%d" % INN.id)                # 묵기 결과엔 가게 번호가 없다 — 붙여도(맡은 사람을 찾을 수 있어도) 사기가 아니라 말이 없어야 한다
check("④ 데이터만으로 — 잡화점을 맡은 사람(아이템 상인)의 정의(npc_defs)에 같은 칸을 두면 그 가게의 돈 부족에 그 사람이 그 말을 한다(코드 그대로) · "
      "여관 주인에게 두어도 묵기 값 부족은 사기가 아니라 여전히 없다(결과에 그 숙소 번호를 붙여도)",
      item_seller == "아이템 상인" and inn_keeper == "여관주인" and R.too_poor_says(dX, a1, r7) == [(item_seller, "시험 문장", "1")]
      and R.too_poor_says(dX, a1, r8) == [] and IA.keeper_of(dX, r8s["shop_id"]) == inn_keeper and R.too_poor_says(dX, a1, r8s) == []
      and R.too_poor_says(dA, a1, r7) == [], (item_seller, inn_keeper, R.too_poor_says(dX, a1, r7), R.too_poor_says(dX, a1, r8s)))
dN = copy.deepcopy(dA)
del dN.features[KEEPER.id]
check("④ 가게를 맡은 사람이 이 세계에 없으면 돈이 모자라도 말이 없다(누가 했는지 모르는 말을 지어내지 않는다) · 맡은 사람 찾기 = 정의 npc.shop",
      R.too_poor_says(dN, a1, r4) == [] and IA.keeper_of(dA, "f%d" % TAV.id) == KEEPER_NAME and IA.keeper_of(dN, "f%d" % TAV.id) is None)
called = []
old_reply, old_call = brains.npc_reply, brains._call_claude
brains.npc_reply = lambda *a_, **k_: called.append("npc_reply")
brains._call_claude = lambda *a_, **k_: (called.append("call"), ("", None))[1]
try:
    says9 = R.too_poor_says(dA, a1, r4)
finally:
    brains.npc_reply, brains._call_claude = old_reply, old_call
tps_src = src("show_runner.py").split("def too_poor_says(")[1].split("\ndef ")[0]
facts9 = R.npc_facts(dA, KEEPER_NAME, botsA, [], None, 0, NAMES)
check("④ 주인의 말은 정의의 문장 그대로 — NPC 두뇌(npc_reply·LLM)를 부르지 않는다 · 러너 함수 소스에 두뇌 길이 없다 · NPC 두뇌 사실(주점 주인)은 가게 값 '판다: 식사 3골드' 그대로(무료 없음)",
      says9 == [(KEEPER_NAME, LINE, "1")] and not called and "npc_reply" not in tps_src and "npc_turn" not in tps_src
      and any("판다: 식사 3골드" in f_ for f_ in facts9) and not any("무료" in f_ for f_ in facts9), (says9, called, facts9))

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑤ 이관 13→14")
dS, botsS = town(on=True)
dS.npc_defs[KEEPER_NAME] = {k_: v_ for k_, v_ in dS.npc_defs[KEEPER_NAME].items() if k_ != "line_too_poor"}
dS.npc_defs[KEEPER_NAME]["line_free_end"] = "공짜로 주는 건 이게 끝이야. 다음부턴 길드에 가서 의뢰를 받아 돈이라도 벌어 와."   # 0.5.25 판의 피클에 얼어 있던 정의 사본
for b_, (fr_, g_) in zip(botsS, (({"meal": 1}, 7), ({"meal": 0}, 0), ({}, 5))):
    b_["free"], b_["gold"] = fr_, g_
dW, botsW = town(on=True)
botsW[0]["free"], botsW[0]["gold"] = {"meal": 2}, 10
waitS = copy.deepcopy(botsS[2])
waitS["free"], waitS["gold"] = {"meal": 2}, 3
snap13 = {"version": 2, "state_version": 13, "d": dS, "bots": botsS[:2], "sheets": SHEETS, "waiting": {"3": waitS},
          "worlds": [{"d": dW, "bots": botsW[:1]}]}
up = S.upgrade(pickle.loads(pickle.dumps(snap13)))   # 이 프로세스가 방금 만든 바이트만 되읽는다(피클 왕복 = 이어가기와 같은 길)
bodies_up = S._bodies(up)
check("⑤ 이관 13→14: 판 14 · 옛 몸의 무료 칸(free)을 버린다 — 지금 세계·다른 세계·부활 대기 전부 · 골드는 그대로(7 · 0 · 10 · 3 — 옛 시작 값도 올리지 않는다)",
      S.STATE_VERSION == 14 and S.MIGRATIONS[13] is S._m13_meal and up["state_version"] == 14 and len(bodies_up) == 4
      and not any("free" in b_ for b_ in bodies_up) and [b_["gold"] for b_ in bodies_up] == [7, 0, 10, 3],
      [(b_.get("gold"), b_.get("free")) for b_ in bodies_up])
kd_up = up["d"].npc_defs.get(KEEPER_NAME) or {}
check("⑤ 이관 13→14: 마을 던전의 주점 주인 말을 지금 정의로 다시 읽는다 — 얼어 있던 line_free_end 가 빠지고 line_too_poor(말 파일 그대로)가 든다 · 다른 세계의 마을도 · 다시 올려도 같다",
      "line_free_end" not in kd_up and kd_up.get("line_too_poor") == LINE and (up["worlds"][0]["d"].npc_defs.get(KEEPER_NAME) or {}).get("line_too_poor") == LINE
      and S.upgrade(copy.deepcopy({**up, "state_version": 13}))["bots"] == up["bots"], kd_up)
dU, botsU = up["d"], up["bots"]
put(botsU[0], stand_by(dU, by_name(dU, "주점"), botsU))
rU = [buy(dU, botsU[0], botsU) for _ in range(3)]
check("⑤ 이관한 옛 몸(골드 7)은 바로 값을 낸다 — 7 → 4 → 1 → 거절 · 주인의 말(이관이 다시 읽은 정의의 문장)",
      [(r_["result"], r_.get("gold")) for r_ in rU] == [("need_fill", 4), ("need_fill", 1), ("too_poor", 1)]
      and R.too_poor_says(dU, botsU[0], rU[2]) == [(KEEPER_NAME, LINE, "1")], [(r_["result"], r_.get("gold")) for r_ in rU])
d12, bots12 = town(on=True)
bots12[0]["gold"] = 6
snap12 = {"version": 2, "state_version": 12, "d": d12, "bots": bots12[:1], "sheets": SHEETS}
up12 = S.upgrade(pickle.loads(pickle.dumps(snap12)))
check("⑤ 판 12 스냅샷(0.5.24 — 무료 칸이 생기기 전)도 12→13(할 일 없음)·13→14 를 지나 판 14 · 몸에 무료 칸 없음 · 골드 그대로 6",
      up12["state_version"] == 14 and S.MIGRATIONS[12] is S._m12_pass and "free" not in up12["bots"][0] and up12["bots"][0]["gold"] == 6,
      (up12["state_version"], up12["bots"][0].get("gold"), up12["bots"][0].get("free")))
SD13 = os.path.join(ROOT, "snap13")                   # 이 프로세스가 방금 쓴 피클 파일만 되읽는다(임시 폴더 — 남이 준 파일 아님)
os.makedirs(SD13)
with open(os.path.join(SD13, S.PKL), "wb") as f_:
    pickle.dump({**snap13, "run_id": "13@x", "next_turn": 9, "stream_pos": 0, "seed": 7, "started": "x"}, f_)
S.write_meta(SD13, {"run_id": "13@x"})
up13f, _m13 = S.load(os.path.join(SD13, S.PKL))
check("⑤ 실제 로더(snapshot.load — 피클 파일): 0.5.25 판(내용 판 13)이 판 14 로 읽히고 몸에 무료 칸이 없다 · 골드 그대로",
      up13f["state_version"] == 14 and not any("free" in b_ for b_ in S._bodies(up13f)) and [b_["gold"] for b_ in S._bodies(up13f)] == [7, 0, 10, 3],
      (up13f.get("state_version"), [(b_.get("gold"), b_.get("free")) for b_ in S._bodies(up13f)]))

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑥ 러너 판(실제 러너 · 각본 두뇌 · NPC 두뇌 켬 — 스텁)")
NPC_PROMPTS = []


def stub_call(prompt, model="haiku"):
    if prompt.lstrip().startswith("# 마을 사람"):
        NPC_PROMPTS.append(prompt)
        return '{"line": "주인의 두뇌 문장"}', None
    return "", None


SCRIPT = {"placed": False, "step": 0, "inbox": {}, "wire": {}, "buys": []}


def stub_think(d, bots, inbox, on_error=None, **_kw):
    """각본 두뇌 — 봇1: 주점 곁으로(처음 한 번) → 식사 사기 다섯 번(세 끼 + 거절 두 번) → 기다림. 봇2: 주점 주인 곁에서 기다린다(곁에서 듣는 사람).
    봇3: 기다린다. 봇1·2 의 편지함과 봇1 의 완성 관측 글을 틱마다 적어 둔다(들은 말 확인)."""
    out = {}
    tav_ = next(f for f in d.features.values() if f.name == "주점")
    kp_ = next(f for f in d.features.values() if f.name == KEEPER_NAME)
    for b in bots:
        if b.get("order") or not b["alive"] or b["won"]:
            continue
        dec = {"type": "wait", "reason": "각본", "src": "haiku"}
        if not SCRIPT["placed"] and b["char"] == "1":
            SCRIPT["placed"] = True
            two = next(o for o in bots if o["char"] == "2")
            put(b, stand_by(d, tav_, [o for o in bots if o is not b]))
            put(two, stand_by(d, kp_, [o for o in bots if o is not two]))
            for o in (b, two):
                o["order"], o["path"] = None, []
        if b["char"] in ("1", "2"):
            SCRIPT["inbox"][(b["char"], d.turn)] = list((inbox or {}).get(b["char"]) or [])
        if b["char"] == "1":
            msgs = list((inbox or {}).get("1") or [])
            o_ = d.view(b, bots)
            o_["messages"] = [{**brains._heard(m, "1", None), **({"to_me": True} if (G.addressed_to(m, "1") and m.get("to") != "all") else {})} for m in msgs]
            SCRIPT["wire"][d.turn] = brains._wire(o_, NAMES, compose=True)
            if SCRIPT["step"] < 5:
                b["needs"]["hunger"] = 30
                dec = {"type": "buy", "target": gid_of(d, "식사"), "reason": "각본 %d" % SCRIPT["step"], "src": "haiku"}   # p0.5.29 사기는 buy
                SCRIPT["buys"].append(d.turn)
                SCRIPT["step"] += 1
        out[b["char"]] = dec
    return out


def run(turns, st, think=None, more=None):
    """러너 풀런(스텁 — NPC 두뇌가 켜진 판: 백엔드 이름만 claude_cli, 콜은 stub_call). think = 각본 두뇌(기본 stub_think) · more = 러너 모듈 값 더 덮기(예: 1인 파티)."""
    env = {"DUNGEON_BRAIN_BACKEND": "claude_cli"}
    old_env = {k_: os.environ.get(k_) for k_ in env}
    patch = {"NPC_REPLY_ON": True, "NPC_HAIL_ON": False, "RESUME_PATH": "", **(more or {})}
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
        text_ = f.read()
    with open(os.path.join(st, "events.log"), encoding="utf-8") as f:
        return text_, [json.loads(ln) for ln in text_.splitlines() if ln.strip()], f.read()


st6 = tempfile.mkdtemp(prefix="run_gold_", dir=ROOT)
text6, rows6, ev6 = run(14, st6)
ticks6 = [r_ for r_ in rows6 if r_["kind"] == "tick"]
lvl6 = next((r_ for r_ in rows6 if r_["kind"] == "level"), {})
buys6 = [(r_["turn"], e) for r_ in ticks6 for e in (r_.get("events") or []) if str(e.get("char")) == "1" and e.get("use_kind") == "shop"]
gold6 = {r_["turn"]: next(b_ for b_ in r_["bots"] if b_["char"] == "1")["gold"] for r_ in ticks6}
check("⑥ 판이 돈다 — 판 시작(level.party[]) 골드 모두 10 · 봇1 식사 다섯 번: need_fill 셋(price 3) → too_poor 둘 · 그 틱 골드 7 · 4 · 1 · 1 · 1",
      [b_.get("gold") for b_ in lvl6.get("party") or []] == [10, 10, 10] and len(buys6) == 5
      and [e["result"] for _t, e in buys6] == ["need_fill"] * 3 + ["too_poor"] * 2 and [gold6[t_] for t_, _e in buys6] == [7, 4, 1, 1, 1],
      ([b_.get("gold") for b_ in lvl6.get("party") or []], [(t_, e.get("result"), gold6.get(t_)) for t_, e in buys6], SCRIPT["buys"]))
poor_t = [t_ for t_, e in buys6 if e["result"] == "too_poor"]
first6 = {}                                          # (말의 틱, 받은 봇) → 그 말이 편지함에 처음 보인 틱(기다리는 봇2 는 읽을 때까지 보관함에 남는다 — D47)
for r_ in ticks6:
    for c_, ms in (r_.get("inbox") or {}).items():
        for m in ms:
            if m.get("text") == LINE:
                first6.setdefault((m["turn"], c_), (r_["turn"], m))
check("⑥ 거절한 틱마다 다음 틱 편지함(tick.inbox)에 주인의 말이 처음 닿는다 — 산 사람(봇1)과 곁에서 듣는 사람(봇2)에게 {from 'npc:주점 주인', text 정의의 문장, turn 그 틱, to 봇1} · "
      "거절 두 번 = 두 말 · 세 끼(값) 뒤엔 없다 · 봇1 은 그 틱 판단에서 그 말 하나를 읽는다",
      len(poor_t) == 2 and sorted(first6) == sorted((t_, c_) for t_ in poor_t for c_ in ("1", "2"))
      and all(seen_ == t_ + 1 and m == {"from": "npc:" + KEEPER_NAME, "text": LINE, "turn": t_, "to": "1"} for (t_, _c), (seen_, m) in first6.items())
      and all(SCRIPT["inbox"].get(("1", t_ + 1)) == [first6[(t_, "1")][1]] for t_ in poor_t), (poor_t, first6))
w6 = SCRIPT["wire"].get(poor_t[0] + 1, "") if poor_t else ""
heard6 = w6.split("## 들은 말", 1)[1].split("\n## ", 1)[0] if "## 들은 말" in w6 else (w6.split("## 동료가 한 말", 1)[1].split("\n## ", 1)[0] if "## 동료가 한 말" in w6 else "")
check("⑥ 첫 거절 다음 틱 봇1 의 완성 관측 글: 들은 말 절에 주점 주인의 그 말 · 결과 꼬리표 '[헛손질] 식사 — 3골드 · 지닌 1' · '네 상태' 첫 줄 골드 1",
      LINE in heard6 and KEEPER_NAME in heard6 and "[헛손질] 식사 — 3골드 · 지닌 1" in w6 and "골드 1," in w6.split("## 네 상태", 1)[-1].split("\n## ", 1)[0],
      [ln for ln in w6.split("\n") if "골드" in ln or LINE in ln or ln.startswith("## ")][:14])
check("⑥ NPC 두뇌가 켜진 판(스텁)에서도 주인의 말은 정의의 문장 — 두뇌 콜 0번 · 두뇌 문장은 어디에도 없다 · events.log '주점 주인 💬 \"돈 떨어졌으면 …\"' 두 줄(거절마다)",
      not NPC_PROMPTS and "주인의 두뇌 문장" not in text6 and ev6.count('%s \U0001f4ac "%s"' % (KEEPER_NAME, LINE)) == 2, (len(NPC_PROMPTS), ev6.count(LINE)))
GONE_STREAM = ("free_left", "free_line", "line_free", '"free"', "무료", "공짜로 주는 건", "받아 먹")
check("⑥ 스트림·관전 로그에 옛 무료 식사가 없다 — 칸(free · free_left · free_line · line_free…)·문장('무료' · '받아 먹') 0 · 모든 틱의 몸에 free 칸 없음",
      not [k_ for k_ in GONE_STREAM if k_ in text6 or k_ in ev6] and not any("free" in b_ for r_ in ticks6 for b_ in r_["bots"]),
      [k_ for k_ in GONE_STREAM if k_ in text6 or k_ in ev6])

SCRIPT2 = {"placed": False, "step": 0, "gold": {}, "down": None}


def stub_think2(d, bots, inbox, on_error=None, **_kw):
    """각본 두뇌(1인 파티 — 혼자 마을에 선 모험가) — 봇1 만: 주점 곁으로(처음 한 번) 식사 한 끼(골드 10 → 7) → 다음 틱 던전 입구 곁으로 옮겨 내려감 →
    지하 1층에서 기다림. 틱마다 봇1 의 골드를 (층, 틱)으로 적어 둔다(p0527b — Codex p0527r 권장: 시작값과 다른 지갑이 층 이동 뒤에도 그대로인가)."""
    out = {}
    for b in bots:
        if b.get("order") or not b["alive"] or b["won"]:
            continue
        dec = {"type": "wait", "reason": "각본", "src": "haiku"}
        if b["char"] == "1":
            SCRIPT2["gold"][(d.depth, d.turn)] = b.get("gold")
            k = SCRIPT2["step"]
            if getattr(d, "town", False) and k <= 1:
                if not SCRIPT2["placed"]:
                    SCRIPT2["placed"] = True
                    put(b, stand_by(d, by_name(d, "주점"), [o for o in bots if o is not b]))
                    b["order"], b["path"] = None, []
                if k == 0:
                    b["needs"]["hunger"] = 30
                    d.view(b, bots)
                    dec = {"type": "buy", "target": gid_of(d, "식사"), "reason": "각본 식사", "src": "haiku"}
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


st7 = tempfile.mkdtemp(prefix="run_gold_down_", dir=ROOT)
P1 = os.path.join(ROOT, "party_one.json")             # 1인 파티(혼자 마을에 선 모험가) — 솔로 판(DUNGEON_SOLO)은 러너가 마을과 함께 쓰지 않는다(주점이 없는 판)
with open(os.path.join(HERE, "party.json"), encoding="utf-8") as f_:
    PJ1 = json.load(f_)
with open(P1, "w", encoding="utf-8") as f_:
    json.dump({"1": PJ1["1"]}, f_, ensure_ascii=False)
text7, rows7, _ev7 = run(10, st7, think=stub_think2, more={"PARTY_FILE": P1})
low7 = sorted((t_, g_) for (dep_, t_), g_ in SCRIPT2["gold"].items() if dep_ == 1)
ticks7 = [(r_["turn"], next((b_["gold"] for b_ in r_["bots"] if b_["char"] == "1"), None)) for r_ in rows7 if r_["kind"] == "tick"]
rsrc = src("show_runner.py")
carry_src = rsrc.split("def _carry(")[1].split("\n    def ")[0]
wake_src = rsrc.split("def _wake(")[1].split("\n    def ")[0]
SG7 = G.START_GOLD - 3                                # 식사 한 끼(3골드) 뒤의 지갑 — 시작값과 다르다
check("⑥ p0527b 실제 층 이동(마을 → 지하 1층 — 러너 재스폰 + _carry): 시작값과 다른 지갑(식사 한 끼 뒤 7)이 그대로 내려간다(스폰 값 10 이 아니다) · 스트림 마지막 틱도 7 · "
      "부활(_wake)은 같은 _carry 를 쓴다(소스)",
      SCRIPT2["down"] is not None and low7 and low7[0][0] > SCRIPT2["down"] and all(g_ == SG7 for _t, g_ in low7) and SG7 != G.START_GOLD
      and ticks7 and ticks7[-1][1] == SG7 and 'n["gold"] = b.get("gold", 0)' in carry_src and "_carry(" in wake_src,
      (SCRIPT2["down"], low7[:3], ticks7[-3:]))

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑦ 잔재")
GONE = ("free_start", "free_left", "free_line", "line_free", "free_end_says", "_m12_free", "verify_free_meal",
        "무료 식사", "무료 끼니", "무료로 받", "받아 먹", "공짜로 주는 건")
ME = os.path.abspath(__file__)
scan = sorted(set(glob.glob(os.path.join(HERE, "*.py")) + glob.glob(os.path.join(HERE, "tools", "*.py"))
                  + glob.glob(os.path.join(HERE, "entities", "*", "*.json")) + glob.glob(os.path.join(HERE, "prompts", "**", "*.md"), recursive=True)
                  + [os.path.join(HERE, "_run_gates.sh")]) - {ME, os.path.join(HERE, "snapshot.py")})
left = {}
for p_ in scan:
    with open(p_, encoding="utf-8", errors="replace") as f_:
        t_ = f_.read()
    hit = [k_ for k_ in GONE if k_ in t_]
    if hit:
        left[os.path.relpath(p_, HERE)] = hit
check("⑦ 코드(리포 루트·tools 의 .py — 게이트 포함)·정의(entities)·말 파일(prompts)·게이트 목록에 옛 무료 식사의 함수·칸·문장이 없다(%d개 파일)" % len(scan),
      not left and len(scan) > 300, left)
sn_text = src("snapshot.py")
sn_tree = ast.parse(sn_text)
cut = [(n.lineno, n.end_lineno) for n in sn_tree.body if isinstance(n, ast.FunctionDef) and n.name in ("_m12_pass", "_m13_meal")]
cut.append((sn_tree.body[0].lineno, sn_tree.body[0].end_lineno))        # 모듈 머리글(이관 이력)
sn_lines = sn_text.splitlines()
sn_rest = "\n".join(ln for i, ln in enumerate(sn_lines, 1) if not any(a <= i <= b for a, b in cut))
m13_src = ast.get_source_segment(sn_text, next(n for n in sn_tree.body if isinstance(n, ast.FunctionDef) and n.name == "_m13_meal"))
check("⑦ 스냅샷(snapshot.py)은 옛 칸을 버리는 자리에만 그 이름이 있다 — 머리글의 이관 이력·_m12_pass·_m13_meal 밖엔 없다 · _m13_meal 이 몸의 free 를 버린다",
      len(cut) == 3 and not [k_ for k_ in GONE + ('"free"', "'free'") if k_ in sn_rest] and 'b.pop("free", None)' in m13_src,
      [k_ for k_ in GONE + ('"free"', "'free'") if k_ in sn_rest])
spawn_src = gm_src.split("def spawn(")[1].split("\ndef ")[0]
carry_src = src("show_runner.py").split("def _carry(")[1].split("\n    def ")[0]
buy_src = src("interactables.py").split("def buy(")[1].split("\ndef ")[0]
check("⑦ 몸의 칸·길이 없다 — 스폰에 'free' 칸 없음 · 층 이월(_carry)이 옮기지 않는다 · 사기(IA.buy)에 무료 길 없음 · 옛 함수(IA.free_start·free_left · R.free_end_says) 없음 · 옛 게이트 파일 없음",
      "'free'" not in spawn_src and 'n["free"]' not in carry_src and "free" not in buy_src
      and not any(hasattr(IA, x_) for x_ in ("free_start", "free_left")) and not hasattr(R, "free_end_says")
      and not os.path.exists(os.path.join(HERE, "verify_free_meal.py")) and "_TRADE_SEEN" in src("interactables.py") and "free" not in IA._TRADE_SEEN)

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑧ 배선")
sf = src("STREAM_FORMAT.md")
sec = sf.split("## 시작 골드 10 · 돈이 모자랄 때 주점 주인의 말", 1)[1].split("\n## ", 1)[0] if "## 시작 골드 10 · 돈이 모자랄 때 주점 주인의 말" in sf else ""
check("⑧ STREAM_FORMAT: 새 절(시작 골드 10 · line_too_poor · 다음 틱 inbox · 저장 판 13 → 14 _m13_meal) · 골드 절의 START_GOLD(10) · 옛 무료 식사 절은 걷은 기록 한 줄로",
      sec and all(k_ in sec for k_ in ("`line_too_poor`", "too_poor", "inbox", "13 → 14", "_m13_meal", "START_GOLD"))
      and "`START_GOLD`(10)" in sf and "`START_GOLD`(5)" not in sf and "free_left: 남은 횟수" not in sf and "## 주점 무료 식사 — 2026-10-17 p0.5.25 additive" not in sf)
check("⑧ _run_gates.sh 에 verify_start_gold 등록(옛 verify_free_meal 없음) · VERSION 0.5.27 이상 · 문서(PATCH_NOTES·CHANGELOG)에 0.5.27 · 저장 판 14",
      "verify_start_gold" in src("_run_gates.sh") and "verify_free_meal" not in src("_run_gates.sh")
      and tuple(int(x) for x in src("VERSION").strip().split(".")) >= (0, 5, 27)
      and "## 0.5.27" in src("docs", "PATCH_NOTES.md") and "p0.5.27" in src("docs", "CHANGELOG.md") and S.STATE_VERSION >= 14)

shutil.rmtree(ROOT, ignore_errors=True)
print()
if C.failed:
    print("FAIL — %d/%d" % (C.failed, C.n))
    sys.exit(1)
print("ALL PASS — verify_start_gold (p0.5.27 무료 식사 걷기 → 시작 골드 10 · 돈이 모자랄 때 주점 주인의 말: %d checks · 정의·검증기 · 시작 골드 · 세 끼 → 거절 · 대사 없음 · 이관 13→14 · 러너 판 · 잔재 · 배선, 실 LLM 0콜)" % C.n)

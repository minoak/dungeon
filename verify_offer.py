# -*- coding: utf-8 -*-
"""D95 공물(2026-09-20) — 신전에 모은 보물을 바치면 신이 몸의 한 칸을 올린다 — 헤들리스 검증. LLM 0콜.
(파트너 "원정을 돌고 나서 보물이나 특정 재물을 신에게 바치면 신이 모험가의 능력치를 올려줄수 있어야 한다고 생각해.
 캐릭터를 관리하는건 신의 몫으로 두는거지" · "결산을 통해서 얻은 자원들로 캐릭터 성장에 이용해야 한다".
 새 동사 없음 — D89 쓰임 부품의 kind 하나(use/interact 밑). 돈·가격·매매 없음: 쓰는 것은 이미 세계에 있던 보물(bot['bag'])이다.)
게이트:
  ① 정의·검증기: 신전 정의에 use{kind offer} · USE_KINDS 에 offer(읽는 칸 없음) · once 거절(상한 없음) · 스위치 뒤 kind 목록이 처리기와 같다
  ② 끈 판 = 옛 판: 러너 스위치 기본 0 · 신전에 use 칸 없음·문턱 메뉴 줄 없음·써도 nothing · 축복은 옛대로 방문마다 · 러너 스트림이 켜기 전과 글자까지 같다
  ③ 메뉴형: 줄 머리 '바치기: 신전 fN (문턱) — …' · 보물 -3 · 힘|민첩|최대 HP 중 하나가 +1(최대 HP 면 지금 HP 도) · 피처 존속 · 판정 rng 무접촉 · 곁의 사람이 본다
  ④ 모자람: 보물이 3 미만이면 offer_short — 사실만(보물·능력치 무변화) · 조합형에서 실패로 기록된다
  ⑤ 신이 고른다(결정론): 같은 세계·같은 몸 = 같은 차례 · 세 칸이 다 나온다 · 판정 rng 를 쓰지 않는다
  ⑥ 자리: 신전 문턱 곁에서만(멀면 too_far) · 쓰임 없는 다른 건물엔 바치기 줄이 없다
  ⑦ 축복(D74)은 켠 판에서 판당 한 번: 방문 장부를 비워도 다시 주지 않는다 · 성직자는 그 사실을 말한다(line_blessed·hail_blessed) · 끈 판은 옛 동작
  ⑧ 이월: 층·원정을 넘는다 — 러너 왕복 판(마을 → 1층 → 마을)에서 오른 능력치·최대 HP·축복 표식이 그대로 · 이월 줄은 기존 목록 안에
  ⑨ 조합형(실판 기본): 대상 태그(interactable·offering) · '대상의 현재 사실' 줄 · use → result + effect_type interact · '그 밖의 정보' 누출 없음
  ⑩ 표현: _last_prose·event_tags·act_summary 가 JSON 폴백·'기타' 가 아니다(메뉴형·조합형 둘 다)
  ⑪ 피클 왕복(D79): 표식(offer_on)·몸의 표식(blessed)이 건넌다 · 속성이 없는 옛 스냅샷도 그대로 돈다(getattr)
  ⑫ 배선: run_meta·세계 지문은 켠 판에만(additive) · decorate 의 offer_short · 러너 생성 세 자리 무접촉 · _run_gates.sh 등록
  ⑬ 켠 판의 문장(09-20 리뷰 발견): 신전·성직자의 소개·첫 선물 대사·마을 안내(D81)가 '원정마다 한 병'을 말하지 않는다 ·
     갈아 끼우는 자리는 그 둘뿐이고 정의 JSON 원문·끈 판은 옛 글자 · NPC 두뇌가 받는 '세계의 판정' 한 줄도 사실 ·
     '한 번뿐' 표식은 축복을 실제로 준 그 한 번에만(접수원의 원정 물품엔 안 붙는다)
  ⑭ 고리 판(D94, 09-20 리뷰 발견): 보물을 들고 돌아와 접수원보다 신전을 먼저 고르는 각본 한 판(0콜) —
     'offered' 가 러너를 통과해 실제로 일어나고 그중 하나는 첫 결산 뒤(2차 원정의 마을) · 오른 것이 원정을 넘는다
"""
import contextlib
import io
import json
import os
import pickle
import tempfile

ROOT = tempfile.mkdtemp(prefix="wl_offer_")
STATE = os.path.join(ROOT, "state")
os.makedirs(STATE, exist_ok=True)
PARTY1 = os.path.join(ROOT, "party_one.json")      # 한 사람 판 — 계단 모임 규칙(EXIT_GATHER)이 뜻을 잃어 왕복이 짧다(⑧)
HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "party.json"), encoding="utf-8") as _f:
    _p = json.load(_f)
with open(PARTY1, "w", encoding="utf-8") as _f:
    json.dump({"1": _p["1"]}, _f, ensure_ascii=False)
os.environ.update(DUNGEON_GM="0", DUNGEON_BESTIARY_FILE="", DUNGEON_STATE_DIR=STATE, DUNGEON_BRAIN_BACKEND="dummy",
                  DUNGEON_ACTION_MODE="compose",   # 조합형 게이트 — _run_gates.sh 의 menu 기본을 파일 안에서 덮는다(verify_use 선례)
                  DUNGEON_STEP_DELAY="0", DUNGEON_TOWN="1", DUNGEON_BOSS="0", DUNGEON_DEPTHS="1",
                  DUNGEON_TURNS="280", DUNGEON_MONSTERS="0", DUNGEON_TRAPS="0", DUNGEON_LURKERS="0",
                  DUNGEON_PARTY_FILE=PARTY1)       # ⑧ 왕복 판의 세계 — 몹·함정 없음(공물이 보이게 하는 판이지 싸움을 보는 판이 아니다)
for k in ("DUNGEON_MENU", "DUNGEON_SCAN", "DUNGEON_OFFER", "DUNGEON_TOWN_LIFE"):
    os.environ.pop(k, None)

import brains                                      # noqa: E402
brains._call_claude = lambda prompt, model="haiku": ""   # LLM 무력화(0콜)
import composed_actions as CA                      # noqa: E402
import dungeon_gm as G                             # noqa: E402
import entities as ENT                             # noqa: E402
import interactables as IA                         # noqa: E402
import show_runner as R                            # noqa: E402

SHEETS = R.load_party(os.path.join(HERE, "party.json"))
NAMES = {c: SHEETS[c]["name"] for c in SHEETS}


class C:
    failed = 0


def check(name, cond, extra=None):
    print(("  OK   " if cond else " FAIL  ") + name + ("" if cond or extra is None else "  << %r" % (extra,)))
    if not cond:
        C.failed += 1


def src(*parts):
    with open(os.path.join(HERE, *parts), encoding="utf-8") as fh:
        return fh.read()


def town(offer=True, spawn=True, quests=False, guide=False):
    """마을 한 판(0콜) — offer=러너 스위치. 몸은 party.json 의 셋. guide=D81 마을 안내 줄(⑬ 이 읽는다)."""
    old = R.OFFER_ON
    R.OFFER_ON = offer
    try:
        d, starts = R.build_town(quests=(G.new_quests() if quests else None), guide=guide)
    finally:
        R.OFFER_ON = old
    bs = []
    if spawn:
        for c in sorted(SHEETS):
            bs.append(G.spawn(d, c, bs, sheet=dict(SHEETS[c])))
    d.turn = 1
    return d, bs


def by_name(d, nm):
    return [f for f in d.features.values() if f.name == nm][0]


def stand_by(d, f):
    """피처 곁(직교)의 걸을 수 있는 빈 칸."""
    return next((f.x + dx, f.y + dy) for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0))
                if d.grid[f.y + dy][f.x + dx] == G.FLOOR and d.feature_at(f.x + dx, f.y + dy) is None)


def labels(d, b, bots, fid):
    return [o["label"] for o in d.view(b, bots).get("options", []) if o.get("target") == "f%d" % fid]


def at(d, b, f):
    b["x"], b["y"] = f.x, f.y          # 건물 문턱·오브젝트는 몸을 막지 않는다 — 그 칸에 선다
    return "f%d" % f.id


print("── ① 정의·검증기")
temple_use = (ENT.get("temple")["comps"] or {}).get("use")
check("① 신전 정의(entities/building/temple.json)에 use{kind offer} — 읽는 칸 없음(값은 코드의 상수 한 곳) · note 에 D95",
      temple_use and temple_use.get("kind") == "offer" and set(temple_use) <= {"kind", "note"}
      and "D95" in (temple_use.get("note") or ""), temple_use)
check("① 어휘 — USE_KINDS[offer] 는 읽는 칸이 없다 · 스위치 뒤 kind 목록이 검증기(ENT.USE_GATED_KINDS) = 처리기(IA._GATE_ATTR) · 상수 OFFER_COST 3 · 후보 셋",
      ENT.USE_KINDS["offer"] == () and set(ENT.USE_GATED_KINDS) == set(IA._GATE_ATTR) == {"offer"}
      and IA.OFFER_COST == 3 and IA.OFFER_STATS == ("str", "dex", "maxhp")
      and set(IA.RESULTS) >= {"offered", "offer_short"})
check("① 검증기가 once 를 거절한다(파트너 '상한도 두지 마라 — 보물이 곧 상한이다') · 모르는 칸도 거절",
      ENT._use_problems("t", {"kind": "offer", "once": True})
      and ENT._use_problems("t", {"kind": "offer", "cost": 5})
      and not ENT._use_problems("t", {"kind": "offer"}))

print("── ② 끈 판 = 옛 판")
check("② 러너 스위치 기본 0(론처가 켠다) · 엔진 기본도 0(클래스 속성 — from_ascii __new__ 경유·옛 피클 호환)",
      R.OFFER_ON is False and G.Dungeon.offer_on is False)
d0, bots0 = town(offer=False)
t0 = by_name(d0, "신전")
b0 = bots0[0]
tid0 = at(d0, b0, t0)
b0["bag"] = 9
obs0 = d0.view(b0, bots0)
fe0 = next(f for f in obs0["sights"]["features"] if f["id"] == tid0)
r0 = d0._interact(b0, tid0, bots0)
check("② 끈 마을의 신전 — 관측에 use 칸 없음 · 문턱에 상호작용 줄 없음(D60 옛 줄) · 써도 옛 'nothing' · 보물 그대로 · 표식(offer_on) 없음",
      "use" not in fe0 and labels(d0, b0, bots0, t0.id) == [] and r0["result"] == "nothing"
      and b0["bag"] == 9 and "offer_on" not in d0.__dict__ and IA.use_of(d0, t0) is None)   # 클래스 속성 False 뿐 — 켠 판에만 인스턴스에 적힌다
att0 = by_name(d0, "성직자")
b0["x"], b0["y"] = stand_by(d0, att0)
g0a = d0._interact(b0, "f%d" % att0.id, bots0)
b0.pop("npc_met"), b0.pop("shop_served")           # 원정을 돌고 온 새 몸의 흉내(방문 장부는 재스폰에 비워진다)
g0b = d0._interact(b0, "f%d" % att0.id, bots0)
check("② 끈 판의 축복은 옛대로 — 방문마다 한 병(원정 고리에서 되풀이되던 그대로) · 몸에 표식(blessed)을 적지 않는다",
      g0a["result"] == "npc_gift" and g0b["result"] == "npc_gift" and b0.get("boons") == 2 and b0.get("blessed") is None)


def run(offer, brain=None, **over):
    """러너 한 판(더미 두뇌 · 임시 state) → 스트림 행들. 0콜.
    over = 러너 모듈 상수 덮어쓰기(⑭ 의 LOOP_ON·MAX_TURNS — env 는 import 때 이미 읽혔다)."""
    st = tempfile.mkdtemp(prefix="run_", dir=ROOT)
    old = (R.STATE, R.OFFER_ON, G.dummy_brain)
    was = {k: getattr(R, k) for k in over}
    R.STATE, R.OFFER_ON = st, offer
    for k, v in over.items():
        setattr(R, k, v)
    if brain:
        G.dummy_brain = brain
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                R.main()
            except SystemExit:
                pass
    finally:
        R.STATE, R.OFFER_ON, G.dummy_brain = old
        for k, v in was.items():
            setattr(R, k, v)
    with open(os.path.join(st, "stream.jsonl"), encoding="utf-8") as fh:
        return [json.loads(ln) for ln in fh if ln.strip()]


def strip(rows):
    return [json.dumps({k: v for k, v in r.items() if k != "started"}, ensure_ascii=False, sort_keys=True) for r in rows]


rows_off_a = run(False)
rows_off_b = run(False)
check("② 러너 스트림: 끈 판 두 번이 (started 빼고) 글자까지 같다 · run_meta 에 offer 없음(켠 판에만 적는다)",
      strip(rows_off_a) == strip(rows_off_b) and "offer" not in rows_off_a[0], len(rows_off_a))

print("── ③ 메뉴형 — 바치기")
d3, bots3 = town()
d3.composed_actions = d3.auto_approach = False      # 메뉴형 경로(게이트·메뉴형 판). 조합형은 ⑨
a3, w3 = bots3[0], bots3[1]
t3 = by_name(d3, "신전")
tid3 = at(d3, a3, t3)
w3["x"], w3["y"] = stand_by(d3, t3)
w3["witnessed"] = []
a3["bag"] = 5
rng3, n_feat3 = d3.rng.getstate(), len(d3.features)
before3 = {s: a3[s] for s in IA.OFFER_STATS}
lab3 = labels(d3, a3, bots3, t3.id)
r3 = d3.act(a3, {"type": "interact", "target": tid3}, bots3)
up3 = [s for s in IA.OFFER_STATS if a3[s] == before3[s] + 1]
check("③ 문턱의 줄 — '바치기: 신전 fN (문턱) — 모은 보물 3개를 바치면 힘·민첩·최대 HP 중 하나가 1 오른다(무엇이 오를지는 신이 정한다)'",
      lab3 == ["바치기: %s %s (문턱) — 모은 보물 %d개를 바치면 힘·민첩·최대 HP 중 하나가 1 오른다(무엇이 오를지는 신이 정한다)"
               % (t3.name, tid3, IA.OFFER_COST)], lab3)
check("③ 결과 — offered · 보물 5 → 2 · 힘|민첩|최대 HP 중 **하나만** +1 · 결과 칸(cost·bag·stat·value)",
      r3["result"] == "offered" and r3["type"] == "interact" and r3["what"] == "신전" and r3["use_kind"] == "offer"
      and a3["bag"] == 2 and r3["bag"] == 2 and r3["cost"] == IA.OFFER_COST
      and len(up3) == 1 and r3["stat"] == up3[0] and r3["value"] == a3[up3[0]],
      (r3.get("result"), a3["bag"], up3))
check("③ 최대 HP 가 오르면 지금 HP 도 같이 오른다(없던 상처가 생기지 않는다) · 그 밖의 칸은 몸만 바뀐다",
      (r3["stat"] != "maxhp") or (r3.get("hp") == a3["hp"] and a3["hp"] == a3["maxhp"]), (r3.get("stat"), a3["hp"], a3["maxhp"]))
check("③ 신전은 사라지지 않는다(쓰고도 남는다) · 판정 rng 무접촉(굴림 없음) · 곁의 사람이 본다(ally_use — 기존 목격 어휘)",
      len(d3.features) == n_feat3 and d3.rng.getstate() == rng3
      and any(x.get("kind") == "ally_use" and x.get("id") == tid3 and x.get("result") == "신전에 보물을 바쳤다"
              for x in (w3.get("witnessed") or [])), w3.get("witnessed"))

print("── ④ 바칠 보물이 모자람")
a3["bag"] = IA.OFFER_COST - 1
before4 = {s: a3[s] for s in IA.OFFER_STATS}
r4 = d3.act(a3, {"type": "interact", "target": tid3}, bots3)
check("④ 보물 2 — offer_short(사실만: 지금 보물·드는 보물) · 보물도 능력치도 그대로 · 권유·조언 없음",
      r4["result"] == "offer_short" and r4["bag"] == IA.OFFER_COST - 1 and r4["cost"] == IA.OFFER_COST
      and a3["bag"] == IA.OFFER_COST - 1 and all(a3[s] == before4[s] for s in IA.OFFER_STATS)
      and brains._last_prose(r4) == "신전에 바치려 했다 — 모은 보물이 2개다(한 번 바치는 데 보물 3개가 든다)",
      (r4.get("result"), brains._last_prose(r4)))

print("── ⑤ 신이 고른다(결정론)")
seqs = []
for _ in range(2):
    d5, bots5 = town()
    d5.composed_actions = d5.auto_approach = False
    a5 = bots5[0]
    t5 = by_name(d5, "신전")
    tid5 = at(d5, a5, t5)
    a5["bag"] = 30
    seqs.append([d5.act(a5, {"type": "interact", "target": tid5}, bots5)["stat"] for _ in range(10)])
picked = set()
for c in sorted(SHEETS):
    d5b, bots5b = town()
    d5b.composed_actions = d5b.auto_approach = False
    bb = next(b for b in bots5b if b["char"] == c)
    t5b = by_name(d5b, "신전")
    tid5b = at(d5b, bb, t5b)
    bb["bag"] = 30
    picked |= {d5b.act(bb, {"type": "interact", "target": tid5b}, bots5b)["stat"] for _ in range(10)}
check("⑤ 같은 세계·같은 몸이면 같은 차례(판정 rng 가 아니라 세계 시드·이름·지금 수치의 해시)", seqs[0] == seqs[1], seqs)
check("⑤ 세 칸이 다 나온다 — 신이 한 칸만 편애하지 않는다(힘·민첩·최대 HP)", picked == set(IA.OFFER_STATS), sorted(picked))

print("── ⑥ 자리 — 신전 문턱에서만")
d6, bots6 = town()
d6.composed_actions = d6.auto_approach = False
a6 = bots6[0]
t6 = by_name(d6, "신전")
a6["bag"] = 9
far6 = next((x, y) for y in range(d6.h) for x in range(d6.w)
            if d6.grid[y][x] == G.FLOOR and not d6.feature_at(x, y) and abs(x - t6.x) + abs(y - t6.y) > 1)
a6["x"], a6["y"] = far6
r6far = d6._interact(a6, "f%d" % t6.id, bots6)
tav6 = by_name(d6, "주점")
at(d6, a6, tav6)
r6tav = d6._interact(a6, "f%d" % tav6.id, bots6)
check("⑥ 문턱에서 떨어져 있으면 too_far(보물 무변화) · 쓰임 없는 건물(주점)은 옛 그대로 nothing·줄 없음",
      r6far["result"] == "too_far" and a6["bag"] == 9 and r6tav["result"] == "nothing"
      and labels(d6, a6, bots6, tav6.id) == [], (r6far.get("result"), r6tav.get("result")))

print("── ⑦ 축복은 판당 한 번(켠 판)")
d7, bots7 = town()
d7.composed_actions = d7.auto_approach = False
a7 = bots7[0]
att7 = by_name(d7, "성직자")
a7["x"], a7["y"] = stand_by(d7, att7)
g7a = d7._interact(a7, "f%d" % att7.id, bots7)
a7.pop("npc_met"), a7.pop("shop_served"), a7.pop("npc_hailed", None)   # 원정을 돌고 온 새 몸의 흉내
g7b = d7._interact(a7, "f%d" % att7.id, bots7)
hail7 = [(h[0], h[5]) for h in d7.npc_greetings([a7])]
a7.pop("npc_met"), a7.pop("shop_served"), a7.pop("npc_hailed", None)
hail7b = [(h[0], h[5], h[2]) for h in d7.npc_greetings([a7])]
check("⑦ 켠 판 — 첫 기도는 축복 한 병(몸에 표식) · 방문 장부를 비워도 두 번째는 주지 않는다(npc_talk) · 보물 소비도 없다",
      g7a["result"] == "npc_gift" and a7.get("blessed") is True and g7b["result"] == "npc_talk"
      and g7b.get("blessed") is True and a7.get("boons") == 1, (g7a.get("result"), g7b.get("result"), a7.get("boons")))
check("⑦ 성직자가 그 사실을 말한다 — 옛 두 대사('한 병 드릴게요'·'살아 돌아오면 또')가 아니라 정의의 line_blessed·hail_blessed",
      g7b["line"].startswith(ENT.npc("temple_attendant")["line_blessed"][:10])
      and hail7 == [] and hail7b and hail7b[0][1] == "hail_blessed"
      and hail7b[0][2].startswith(ENT.npc("temple_attendant")["hail_blessed"][:6].replace("{name}", "")[:1] or "")
      and "축복은 이미" in hail7b[0][2], (g7b.get("line", "")[:20], hail7b))

print("── ⑧ 이월 — 층·원정을 넘는다(러너 왕복 판)")
sr = src("show_runner.py")
carry = sr[sr.index('n["boons"] = b.get("boons", 0)'):sr.index('n["weapon"] = b.get("weapon")')]
check("⑧ 이월 줄은 기존 목록 안에(새 이월 목록을 만들지 않는다) — 최대 HP·축복 표식이 축복의 물약·힘/민첩 줄 곁에",
      'n["maxhp"] = b["maxhp"]' in carry and 'n["blessed"] = True' in carry and 'if b.get("blessed"):' in carry)

real_dummy, real_spawn = G.dummy_brain, G.spawn
trace8 = {"met": False, "went": False, "again": False}
spawned8 = []


def rec_spawn(d, char, others=(), **kw):
    """판을 시작하는 몸에만 보물을 쥐여 준다(원정에서 모아 온 몫의 대역 — 던전을 헤매는 대신 공물만 본다).
    층 전이의 재스폰은 바로 뒤에서 이월이 bag 을 덮어쓰므로 여기서 더한 것이 남지 않는다 = 이월을 가리지 않는다."""
    b = real_spawn(d, char, others, **kw)
    b["bag"] = b.get("bag", 0) + 2 * IA.OFFER_COST
    spawned8.append(b)
    return b


def scripted(obs, char="?"):
    """0콜 각본(조합형) — 마을: 성직자(축복) → 신전에 바치기(보물이 있는 동안) → 던전 입구.
    던전: 바로 '위로 오르는 계단'. 돌아온 마을: 성직자에게 한 번 더(축복이 판당 한 번인지) → 제자리."""
    feats = sorted((obs.get("sights") or {}).get("features") or [], key=lambda x: (x.get("dist", 99), x["id"]))
    bag = int(obs.get("inventory") or 0)

    def go(f):
        return {"type": "use" if f.get("adj") else "goto", "target": f["id"]}
    if not obs.get("town"):
        trace8["went"] = True
        up = next((f for f in feats if f.get("type") == "stairs_up"), None)
        return go(up) if up else real_dummy(obs, char)
    att = next((f for f in feats if f.get("name") == "성직자"), None)
    tem = next((f for f in feats if f.get("name") == "신전"), None)
    phase_att = trace8["went"] and not trace8["again"]           # 돌아온 마을의 두 번째 기도
    if att is not None and (not trace8["met"] or phase_att):
        if att.get("adj"):
            trace8["met" if not trace8["went"] else "again"] = True
        return go(att)
    if tem is not None and bag >= IA.OFFER_COST and not trace8["went"]:
        return go(tem)
    if trace8["went"]:
        return {"type": "wait"}                                  # 원정 하나로 끝 — 오르내림을 되풀이하지 않는다(판을 짧게)
    ex = (obs.get("sights") or {}).get("exit")
    return go(ex) if ex else real_dummy(obs, char)


G.spawn = rec_spawn
try:
    rows8 = run(True, brain=scripted)
finally:
    G.spawn = real_spawn
ev8 = [e for r in rows8 for e in (r.get("events") if isinstance(r.get("events"), list) else [])]
gift8 = [e for e in ev8 if e.get("result") == "npc_gift"]
talk8 = [e for e in ev8 if e.get("result") == "npc_talk" and e.get("npc") == "성직자"]
off8 = [e for e in ev8 if e.get("result") == "offered"]
depths8 = [r.get("depth") for r in rows8 if r["kind"] == "level"]
body8 = spawned8[-1] if spawned8 else {}
base8 = SHEETS["1"]
check("⑧ 왕복 판이 예외 없이 돈다 — 마을 → 1층 → 마을(level 줄의 층) · run_meta.offer · 신전에 실제로 바쳤다",
      rows8[-1]["kind"] in ("end", "timeout") and rows8[0].get("offer") is True and depths8[:3] == [0, 1, 0] and off8,
      (rows8[-1].get("kind"), depths8, len(off8)))
grew8 = sum(1 for _ in off8)
now8 = sum(int(body8.get(s) or 0) for s in IA.OFFER_STATS)
was8 = int(base8["str"]) + int(base8["dex"]) + int(base8["hp"])
check("⑧ 바쳐서 오른 것이 층·원정을 넘는다 — 돌아온 몸의 힘+민첩+최대 HP = 시트 + 바친 횟수(시트 값으로 되돌지 않는다)",
      len(spawned8) >= 2 and now8 == was8 + grew8, (now8, was8, grew8, len(spawned8)))
check("⑧ 축복 표식도 넘는다 — 돌아온 몸은 blessed · 성직자의 선물은 판을 통틀어 한 번, 두 번째는 말뿐(npc_talk)",
      body8.get("blessed") is True and len(gift8) == 1 and talk8 and talk8[-1].get("blessed") is True,
      (body8.get("blessed"), len(gift8), len(talk8)))

print("── ⑨ 조합형(실판 기본)")
d9, bots9 = town()
a9 = bots9[0]
t9 = by_name(d9, "신전")
tid9 = at(d9, a9, t9)
a9["bag"] = 4
o9 = d9.view(a9, bots9)
tg9 = {t["id"]: t["tags"] for t in o9["targets"] if t["kind"] == "feature"}
w9 = brains._wire(o9, NAMES, compose=True)
act9, err9 = CA.parse({"type": "use", "target": tid9}, o9)
r9 = d9.act(a9, act9, bots9)
o9b = d9.view(a9, bots9)
r9b = d9.act(a9, CA.parse({"type": "use", "target": tid9}, o9b)[0], bots9)
check("⑨ 대상 태그 — 신전 [object, interactable, offering] · '대상의 현재 사실'에 바치는 값 한 줄 · '그 밖의 정보' 누출 없음",
      d9.composed_actions is True and tg9[tid9] == ["object", "interactable", "offering"]
      and ("- %s 신전: 모은 보물 %d개를 바치면" % (tid9, IA.OFFER_COST)) in w9 and "## 그 밖의 정보" not in w9,
      (tg9.get(tid9), [l for l in w9.splitlines() if "신전" in l][:3]))
check("⑨ use 신전 → type use · effect_type interact · offered · 보물 4 → 1 · 다음엔 모자라 offer_short 이고 실패로 기록된다(resolution)",
      err9 is None and r9["type"] == "use" and r9.get("effect_type") == "interact" and r9["result"] == "offered"
      and a9["bag"] == 1 and r9b["result"] == "offer_short" and r9b["resolution"]["status"] == "failed",
      (r9.get("result"), a9["bag"], r9b.get("result"), r9b.get("resolution")))

print("── ⑩ 표현")
prose9, prose9b = brains._last_prose(r9, NAMES), brains._last_prose(r9b, NAMES)
tags9 = G.event_tags(r9, NAMES)
tags9b = G.event_tags(r9b, NAMES)
check("⑩ 조합형 결과도 1인칭 사실 문장 — JSON 폴백이 아니다(effect_type 재귀) · 관전 한 줄도 같은 소스",
      prose9.startswith("신전에 보물 %d개를 바쳤다 — 신이 " % IA.OFFER_COST) and "{" not in prose9
      and prose9b.startswith("신전에 바치려 했다 — ") and R.act_summary(r9) == IA.prose(r9), (prose9, prose9b))
check("⑩ 궤적 꼬리표 — 새 키를 만들지 않는다(use·misc 재사용) · '기타' 폴백이 아니다 · 전부 EVENT_KINDS 안",
      [k for k, _, _ in tags9] == ["use"] and tags9[0][1] == "바침" and [k for k, _, _ in tags9b] == ["misc"]
      and tags9b[0][1] == "헛손질" and all(k in G.EVENT_KINDS for k, _, _ in tags9 + tags9b), (tags9, tags9b))
check("⑩ D39 오브젝트 태그 — 쓰고도 남는 것이라 '바쳐 봄 ×N (…)'",
      IA.tried(d9, t9) == "바쳐 봄" and IA.obj_note(r9) == "%s +1" % {"str": "힘", "dex": "민첩", "maxhp": "최대 HP"}[r9["stat"]]
      and IA.obj_note(r9b) == "보물 모자람")

print("── ⑪ 피클 왕복(D79)")
blob = pickle.dumps((d7, bots7))                    # 이어가기가 세계를 피클로 얼린다(방금 이 프로세스가 만든 바이트만 읽는다)
d11, bots11 = pickle.loads(blob)
a11 = bots11[0]
t11 = by_name(d11, "신전")
tid11 = at(d11, a11, t11)
a11["bag"] = 3
r11 = d11._interact(a11, tid11, bots11)
att11 = by_name(d11, "성직자")
a11["x"], a11["y"] = stand_by(d11, att11)
a11.pop("npc_met", None), a11.pop("shop_served", None)
g11 = d11._interact(a11, "f%d" % att11.id, bots11)
old_world = pickle.loads(pickle.dumps(d0))          # 속성이 아예 없는 옛 스냅샷(끈 판) — getattr 기본으로 돈다
b_old = dict(bots0[0])
b_old["x"], b_old["y"] = by_name(old_world, "신전").x, by_name(old_world, "신전").y
check("⑪ 되살린 세계에서도 바쳐진다(표식 offer_on) · 몸의 표식(blessed)이 건너 축복을 다시 주지 않는다 · 속성 없는 옛 세계는 옛 길 그대로",
      d11.offer_on is True and r11["result"] == "offered" and g11["result"] == "npc_talk"
      and old_world._interact(b_old, "f%d" % by_name(old_world, "신전").id, [b_old])["result"] == "nothing",
      (getattr(d11, "offer_on", None), r11.get("result"), g11.get("result")))

print("── ⑫ 배선")
gm, ca = src("dungeon_gm.py"), src("composed_actions.py")
check("⑫ run_meta·세계 지문은 켠 판에만(additive) · 러너 스위치는 env 한 곳",
      sr.count('**({"offer": True} if (OFFER_ON and TOWN_ON) else {})') == 2
      and sr.count('OFFER_ON = os.environ.get("DUNGEON_OFFER", "0") == "1"') == 1)
check("⑫ 엔진 훅 — 쓰임은 D89 의 한 자리 그대로(IA.handle 한 곳) · 축복 좁힘은 offer_on 한 조건 · decorate 의 offer_short",
      gm.count("IA.handle(") == 1 and gm.count("blessed_done = bool(self.offer_on and bot.get('blessed'))") == 1
      and "'offer_short'" in ca)
check("⑫ 러너의 Dungeon( 생성 세 자리는 무접촉(다른 게이트의 글자 검사) · interactables 는 엔진을 import 하지 않는다(순환 없음)",
      sr.count("give_verb=GIVE_ON, bond_verb=BOND_ON") == 2 and "import dungeon_gm" not in src("interactables.py"))
check("⑫ _run_gates.sh 등록", "verify_offer" in src("_run_gates.sh"))

print("── ⑬ 켠 판의 문장 — 세계가 제 하지 않는 것을 말하지 않는다(09-20 리뷰 발견)")
# 켠 판의 축복은 '한 사람에게 한 번'이라(⑦) 정의의 옛 약속 셋이 그 판에서 거짓이 된다: 성직자의 특징 '(원정마다 한 병)' ·
#   신전의 특징 '기도하면 축복의 물약을 한 병 받는다' · 성직자의 첫 선물 대사 '던전에서 돌아오면 또 들르세요'(그 판에서 반드시 한 번 나온다).
OLD_PROMISE = ("원정마다 한 병", "기도하면 축복의 물약을 한 병 받는다", "던전에서 돌아오면 또 들르세요")
d13, _b13 = town(guide=True)
d13off, _b13off = town(offer=False, guide=True)


def town_text(dd):
    return [s for st in dd.place_story.values() for s in st.values()] + list(dd.npc_lines.values()) \
        + [g["about"] for g in (getattr(dd, "town_guide", None) or [])]


att13, tem13 = by_name(d13, "성직자"), by_name(d13, "신전")
att13o, tem13o = by_name(d13off, "성직자"), by_name(d13off, "신전")
bad13 = [s for s in town_text(d13) if any(w in s for w in OLD_PROMISE)]
check("⑬ 켠 판의 소개·첫 선물 대사·마을 안내(D81) 어디에도 옛 약속 셋이 없다", not bad13, bad13)
check("⑬ 갈아 끼운 자리는 신전·성직자 둘뿐 — 마을 안내도 같은 문장을 읽는다(안내를 짓기 전에 바꾼다) · 정의 JSON 원문·끈 판은 옛 글자 그대로",
      d13.place_story[att13.id]["trait"] == R.OFFER_STORY["temple_attendant"]
      and d13.place_story[tem13.id]["trait"] == R.OFFER_STORY["temple"]
      and d13.npc_lines["성직자"] == R.OFFER_LINES["temple_attendant"]
      and next(g["about"] for g in d13.town_guide if g["name"] == "신전") == R.OFFER_STORY["temple"]
      and all(any(w in s for w in OLD_PROMISE)
              for s in (d13off.place_story[att13o.id]["trait"], d13off.place_story[tem13o.id]["trait"], d13off.npc_lines["성직자"]))
      and ENT.get("temple")["comps"]["story"]["trait"].startswith("성직자에게 기도하면")
      and ENT.npc("temple_attendant")["line"].endswith("던전에서 돌아오면 또 들르세요."))
check("⑬ 바뀌는 것은 그 두 소개의 trait 와 성직자의 line 뿐 — 소개 수·history·역할 한 줄·다른 NPC 대사는 끈 판과 같다",
      len(d13.place_story) == len(d13off.place_story) and d13.feature_roles == d13off.feature_roles
      and d13.place_story[tem13.id]["history"] == d13off.place_story[tem13o.id]["history"]
      and d13.npc_lines_again == d13off.npc_lines_again
      and {k: v for k, v in d13.npc_lines.items() if k != "성직자"} == {k: v for k, v in d13off.npc_lines.items() if k != "성직자"})

seen13 = []
_old_call = brains._call_claude
brains._call_claude = lambda prompt, model="haiku": seen13.append(prompt) or "네."   # 프롬프트만 보는 대역(0콜)
try:
    brains.npc_reply(bots7[0], g7a, "기도합니다", ["파티: 셋"], npc=d7.npc_defs["성직자"])       # 켠 판의 축복 선물
    brains.npc_reply(bots0[0], g0a, "기도합니다", ["파티: 셋"], npc=d0.npc_defs["성직자"])       # 끈 판의 같은 자리
finally:
    brains._call_claude = _old_call
check("⑬ NPC 두뇌가 받는 '세계의 판정' 한 줄도 사실 — 켠 판은 '이 한 번뿐이다', 끈 판은 옛 '이번 원정 몫' 그대로",
      g7a.get("blessed") is True and g0a.get("blessed") is None and len(seen13) == 2
      and "이 한 번뿐이다" in seen13[0] and "이번 원정 몫" not in seen13[0] and "이번 원정 몫" in seen13[1],
      [l for p in seen13 for l in p.splitlines() if "건넸다" in l])
d13b, bots13b = town()
d13b.composed_actions = d13b.auto_approach = False
rec13, bb13 = by_name(d13b, "길드 접수원"), bots13b[0]
bb13["blessed"] = True                              # 이미 축복을 받은 몸이 접수원에게 원정 물품을 받는다
bb13["x"], bb13["y"] = stand_by(d13b, rec13)
r13b = d13b._interact(bb13, "f%d" % rec13.id, bots13b)
check("⑬ '한 번뿐' 표식은 축복을 실제로 준 그 한 번에만 — 접수원의 원정 물품에는 붙지 않는다(엉뚱한 선물이 '한 번뿐'이 되지 않게)",
      r13b["result"] == "npc_gift" and "blessed" not in r13b, r13b)

print("── ⑭ 고리 판(D94)에서 실제로 바쳐지는가 — 귀환 → 신전 → 접수원 보고(09-20 리뷰 발견)")
# 왜: ⑧ 은 원정 한 번짜리 왕복이라 '돌아온 마을에서 바친다'는 장면이 러너를 통과해 실제로 일어나는지는 안 봤다
#   (리뷰의 0콜 풀게임에서 offer_short 3 · offered 0 — 시험대 두뇌가 피처마다 한 번씩만 써 보기 때문). 공물은 원정 고리
#   국면의 일이므로, 고리 판에서 '보물을 들고 돌아와 접수원보다 신전을 먼저 고르는' 각본을 한 판 돌려 눈으로 센다.
spawned14 = []


def loot_spawn(d, char, others=(), **kw):
    """원정에서 모아 온 몫의 대역 — 판을 시작하는 몸에만(층 전이 재스폰은 바로 뒤 이월이 bag 을 덮어쓴다)."""
    b = real_spawn(d, char, others, **kw)
    b["bag"] = b.get("bag", 0) + 4 * IA.OFFER_COST
    spawned14.append(b)
    return b


def loop_scripted(obs, char="?"):
    """0콜 각본(조합형) — 마을에선 던전 입구 → 던전에선 보스를 치고 워프게이트 →
    돌아온 마을: 보물이 있으면 **접수원보다 신전이 먼저**, 그 다음 보고(= 그 원정의 결산)."""
    s = obs.get("sights") or {}

    def go(f):
        return {"type": "use" if f.get("adj") else "goto", "target": f["id"]}
    if not obs.get("town"):                   # 던전: 보이는 몹(보스)을 치고 나가는 길로 — 원정은 워프 귀환으로만 끝난다
        for m in s.get("monsters") or []:
            if m.get("adj"):
                return {"type": "attack", "target": m["id"]}
        if s.get("monsters"):
            return {"type": "goto", "target": min(s["monsters"], key=lambda m: m["dist"])["id"]}
        ex = s.get("exit")
        return go(ex) if ex else real_dummy(obs, char)
    if obs.get("expedition_returned"):
        feats = sorted(s.get("features") or [], key=lambda x: (x.get("dist", 99), x["id"]))
        tem = next((f for f in feats if f.get("name") == "신전"), None)
        rec = next((f for f in feats if f.get("name") == "길드 접수원"), None)
        if tem is not None and int(obs.get("inventory") or 0) >= IA.OFFER_COST:
            return go(tem)                    # 접수원보다 신전이 먼저다(이 각본의 요점)
        if rec is not None:
            return go(rec)
    ex = s.get("exit")
    return go(ex) if ex else real_dummy(obs, char)


real_stats = G.ENT.monster_stats
G.ENT.monster_stats = lambda kind: {**real_stats(kind), "hp": 1, "atk": 0, "dmg": 0, "ac": 5}   # 보스도 한 대에(verify_loop 선례) — 싸움을 보는 판이 아니다
G.spawn = loot_spawn
try:                                          # 워프 귀환이 서는 판(보스·작은 층) — 계단으로 오르기만 해서는 원정이 끝나지 않는다
    rows14 = run(True, brain=loop_scripted, LOOP_ON=True, BOSS_ON=True, MAX_TURNS=600, DUNGEON_W=40, DUNGEON_H=16)
finally:
    G.spawn, G.ENT.monster_stats = real_spawn, real_stats
ev14 = [(int(r.get("turn") or 0), e) for r in rows14 for e in (r.get("events") if isinstance(r.get("events"), list) else [])]
settle14 = [r for r in rows14 if r.get("kind") == "expedition"]
off14 = [(t, e) for t, e in ev14 if e.get("result") == "offered"]
rep14 = [e for t, e in ev14 if e.get("result") == "npc_report"]
gift14 = [e for t, e in ev14 if e.get("result") == "npc_gift" and e.get("npc") == "성직자"]
body14 = spawned14[-1] if spawned14 else {}
check("⑭ 고리 판이 예외 없이 돈다 — 원정 결산 2회 이상 · 접수원 보고 2회 이상 · run_meta 에 loop 와 offer 둘 다",
      rows14[-1]["kind"] in ("end", "timeout") and rows14[0].get("loop") is True and rows14[0].get("offer") is True
      and len(settle14) >= 2 and len(rep14) >= 2, (rows14[-1].get("kind"), len(settle14), len(rep14)))
check("⑭ 돌아온 마을에서 실제로 바친다 — 'offered' 가 러너를 통과해 2회 이상 일어나고, 그중 하나는 첫 결산 뒤다(2차 원정의 마을)",
      len(off14) >= 2 and settle14 and any(t > int(settle14[0].get("turn") or 0) for t, _ in off14),
      ([t for t, _ in off14], [int(r.get("turn") or 0) for r in settle14]))
check("⑭ 바쳐서 오른 것이 원정을 넘는다 — 마지막 몸의 힘+민첩+최대 HP = 시트 + 바친 횟수 · 성직자의 선물은 판을 통틀어 한 번뿐(고리가 방문 장부를 비워도)",
      len(gift14) <= 1 and body14 and sum(int(body14.get(s) or 0) for s in IA.OFFER_STATS)
      == int(base8["str"]) + int(base8["dex"]) + int(base8["hp"]) + len(off14),
      (len(gift14), len(off14), {s: body14.get(s) for s in IA.OFFER_STATS}))

if C.failed:
    print("FAILED %d" % C.failed)
    raise SystemExit(1)
print("ALL PASS — verify_offer (D95 공물: 끈 판 동일·바치기·모자람·결정론·자리·축복 판당 1회·이월·조합형·표현·피클·배선, 실 LLM 0콜)")

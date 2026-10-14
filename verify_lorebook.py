# -*- coding: utf-8 -*-
"""p0.5.11 개인 로어북 — 에이전트가 직접 쓰는 기록 사전(설계 .orch/drafts/personal_lorebook_design.md v3 §6.6 · DECISIONS 2026-10-13 87·89 · 10-14). LLM 0콜.
응답 칸 `lore_note` 하나로 관측에 나온 무엇이든 적는다(target = 그것 하나 · kind = 그 종류 전부). 엔진은 안쪽 열쇠로 보관하고 관측을 만들 때 지금 화면 번호로 잇는다.
  ① 받는 조건 — 대상마다 받기·버리기(길·자기 자신·빈 소지 칸·사람 이름을 kind 에·둘 다 씀·둘 다 빔) · 버린 것마다 lore_drop.why
  ② 함정 t<n> — 같은 층에서 다시 보면 뜬다 · 밟힌 함정은 대상에서 빠져 안 뜬다 · 새 원정의 같은 깊이 층의 t0 엔 안 뜬다 · 함정 종류는 로어북 장부(kind:)
  ③ 칸 병합(c02r 회귀) — 이름만 쓰면 글 유지 · 글만 쓰면 이름 유지 · 다른 칸 유지 · 둘 다 빈 쓰기는 무변화
  ④ 같은 이름 둘 — '주민의 집' 두 채에 각자의 개별 기록 + 종류 기록은 가까운 집 아래 한 번 · 이름을 들으면 셋이 다 후보(열쇠 순) · 관측에 안쪽 열쇠·uid 없음
  ⑤ 덮어쓰기 보장 — 쓸 수 있는 대상 ⊆ 뜨는 대상(상한 전) · 시야 밖에서 내게 말한 사람의 기록은 말 속에 이름이 없어도 뜬다
  ⑥ 도감 칸 — 몬스터 종류 기록 = 원장 note · 한 결정에 book_line·lore_note 같은 종이면 lore_note 가 이긴다(다른 종이면 둘 다) · 도감 밖 이름은 로어북에 두었다가
     도감 쪽에 같은 종이 쓰이면 merge · 오프라인 소급도 같은 원장 · 인물 기록 판은 '네 생각' 줄 대신 '네 기록(종류: …)'
  ⑦ 번호 안정성 — 같은 층에서 관측을 여러 번 만들어도 같은 기록 · 다른 층에 갔다 와도 그대로
  ⑧ 장비 따라가기 — 줍기 → 층 이월(번호가 바뀐다) → 건네기(발밑에 놓임) → 다시 줍기를 지나도 내 기록 · 받은 사람에겐 안 뜬다
  ⑨ 쓸어내기 — 사라진 층의 기록만 지운다(사람·장소·의뢰·종류·장비는 남는다) · 러너가 모든 몸에서 지우고 sweep 로그
  ⑩ 뜨기·상한·순서 — 보임·서 있는 곳·말한 사람·이름 들림·소지품 · 기록 9개면 6줄(거리순)·lore_cut 3 · 겹치는 이름('고블린 대장'/'고블린') 순서 · 도감 절은 6줄 밖 · 결정론
  ⑪ 길이 — 81자 씨앗·81자 글이 저장에서 80 · 그릴 때도 80을 넘지 않는다
  ⑫ 총량 — 101번째 기록에서 층 기록부터 바래고(fade), 층 기록이 없으면 가장 오래전에 고친 것
  ⑬ 이관·복원 — 내용 판 4 스냅샷 → 5(lore·scope·lore_ids) · 망가진 lore_ids 에도 겹치지 않는다 · 이어가기 전에 쓴 층 기록이 보존 층에서 그대로 뜬다
  ⑭ 정보 보호 — 두 몸이 같은 대상에 다른 기록 → 각자 제 것만 · NPC 두뇌 입력에 기록 글 0 · 안쪽 열쇠·관전 칸이 프롬프트·관측에 없다
  ⑮ 따라가기 — 러너 판의 층 이월에서 lore 는 같은 객체 · 이월 목록(_carry)이 lore 를 옮긴다(부활·귀환도 같은 목록) · 피클 왕복
  ⑯ 로그 — 러너 판 스트림: run_meta.lore · level.scope · decisions.lore_note(key 채움)·lore_drop·lore_shown·lore_cut · tick.lore_ops(set·sweep) — 이것만으로 기록률·오기율·잘림률을 센다
  ⑰ 옛 판 바이트 불변 — 인물 기록이 꺼진 몸: 관측 lore 없음 · RECORD·lore_note 없음 · '네 생각'·도감/관계 초대 문장 그대로 · 피처·층 기록에 uid·scope 없음
(기존 verify 는 별도 실행.)
"""
import contextlib
import copy
import io
import json
import os
import pickle                                         # 이 게이트가 방금 만든 객체만 왕복한다(스냅샷 D79 과 같은 전제 — 남이 준 피클은 읽지 않는다)
import random
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = tempfile.mkdtemp(prefix="wl_lorebook_")
STATE = os.path.join(ROOT, "state")
os.makedirs(STATE, exist_ok=True)
BASE_ENV = dict(DUNGEON_GM="0", DUNGEON_STEP_DELAY="0", DUNGEON_TURNS="160", DUNGEON_W="40", DUNGEON_H="16",
                DUNGEON_DEPTHS="2", DUNGEON_SEED="7", DUNGEON_MONSTERS="0", DUNGEON_TRAPS="0", DUNGEON_LURKERS="0",
                DUNGEON_BESTIARY_FILE="", DUNGEON_PARTY_FILE=os.path.join(HERE, "party.json"), DUNGEON_STATE_DIR=STATE,
                DUNGEON_TOWN="1", DUNGEON_BRAIN_BACKEND="dummy", DUNGEON_BOSS="0", DUNGEON_RUNS_DIR=os.path.join(ROOT, "runs"),
                DUNGEON_ACTION_MODE="compose", DUNGEON_PARTYFORM="1", DUNGEON_STRANGERS="1", DUNGEON_STREAM_OBS="1")
os.environ.update(BASE_ENV)
for k in ("DUNGEON_QUESTS", "DUNGEON_TOWN_APART", "DUNGEON_NPC_BRAIN", "DUNGEON_SOLO", "DUNGEON_START", "DUNGEON_MENU", "DUNGEON_RESUME"):
    os.environ.pop(k, None)

import brains                                        # noqa: E402
brains._call_claude = lambda prompt, model="haiku": ""   # LLM 무력화(결정론)
import bestiary                                      # noqa: E402
import dungeon_gm as G                               # noqa: E402
import lorebook as LB                                # noqa: E402
import sheetkit                                      # noqa: E402
import show_runner                                   # noqa: E402
import snapshot                                      # noqa: E402
import time as _time                                 # noqa: E402
_time.sleep = lambda s: None
show_runner.STEP_DELAY = 0


class C:
    failed = 0


def check(name, ok, detail=""):
    print("  %s %s%s" % ("OK  " if ok else "FAIL", name, (" — " + str(detail)[:400]) if (detail and not ok) else ""))
    if not ok:
        C.failed += 1


SHEETS = show_runner.load_party(os.path.join(HERE, "party.json"))
IDS = {"scope": 1, "uid": 1}                         # 이 게이트의 판 하나 — 층마다 같은 발급 상태(러너처럼)


def prompt(d, bots, b, msgs=(), reply=None):
    """그 캐릭터가 실제로 받는 글 전체 — _call_claude 를 가로채 본다(실 콜 없음). reply(JSON dict)를 주면 그 응답으로 결정까지."""
    seen = {}

    def stub(p, model="haiku"):
        seen["p"] = p
        return json.dumps(reply or {"type": "wait"}, ensure_ascii=False)
    old_call, old_env = brains._call_claude, os.environ.get("DUNGEON_BRAIN_BACKEND")
    brains._call_claude, os.environ["DUNGEON_BRAIN_BACKEND"] = stub, "claude_cli"
    try:
        o = d.view(b, bots)
        o["messages"] = [dict(m) for m in msgs]
        dec = brains.claude_brain(o, b["char"], b, bots)
    finally:
        brains._call_claude = old_call
        os.environ["DUNGEON_BRAIN_BACKEND"] = old_env or "dummy"
    return seen.get("p", ""), dec, o


def write(d, bots, b, ln, msgs=()):
    """응답 칸 → 파서 → 러너 쓰기(think_all 과 같은 apply) — (결정, 변화 목록)."""
    _, dec, _ = prompt(d, bots, b, msgs, {"type": "wait", "lore_note": ln})
    ops = LB.apply(d, b, dec["lore_note"], d.turn) if dec.get("lore_note") else []
    return dec, ops


def drop_why(d, bots, b, ln, msgs=()):
    _, dec, _ = prompt(d, bots, b, msgs, {"type": "wait", "lore_note": ln})
    return (dec.get("lore_drop") or {}).get("why"), dec


def under(p, head, n=3):
    """프롬프트에서 head 로 시작하는 줄 바로 아래 줄들(n 줄)."""
    L = p.splitlines()
    i = next((i for i, ln in enumerate(L) if ln.startswith(head)), None)
    return [] if i is None else L[i + 1:i + 1 + n]


def body(d, c, bs, people=True):
    b = G.spawn(d, c, bs, sheet=dict(SHEETS[c]))
    if people:
        b["people"], b["lore"] = {}, {}
    return b


def free(d, x, y):
    return d.grid[y][x] == G.FLOOR and not d.feature_at(x, y) and not d.monster_at(x, y)


def floor(seed=37, people=True, stamp=True):
    """던전 한 층(scan) — 방 하나(6,25 7×4)에 나(1)·고블린 둘·가시 함정·장검을 세운다. 2 는 같은 방 구석, 3 은 멀리."""
    d = G.Dungeon(seed=seed, w=42, h=34, n_monsters=2, n_traps=1, n_lurkers=0, scan=True, n_gear=0)
    d.composed_actions = d.auto_approach = True
    d.give_verb = True
    d.turn = 9
    if stamp:
        LB.stamp(d, IDS)
    bs = []
    for c in ("1", "2", "3"):
        bs.append(body(d, c, bs, people))
    b1, b2, b3 = bs
    b1["x"], b1["y"] = 7, 26
    b2["x"], b2["y"] = 6, 25
    b3["x"], b3["y"] = 30, 20
    m0, m1 = d.monsters[0], d.monsters[1]
    m0.x, m0.y = 9, 26
    m1.x, m1.y = 11, 27
    for m in (m0, m1):
        m.state = "SLEEPING"
    t = d.traps[0]
    t.x, t.y, t.hidden = 7, 28, False
    for f in list(d.features.values()):
        if 6 <= f.x <= 12 and 25 <= f.y <= 28:
            f.x, f.y = 1, 1                          # 방 안의 다른 피처는 치운다(장면을 고정)
    gid = d._add_feature("weapon", "장검", 8, 26)
    return d, bs, gid


def town(people=True):
    d, _ = show_runner.build_town(apart=True)
    d.composed_actions = d.auto_approach = True
    d.parties = G.new_parties()
    LB.stamp(d, IDS)
    bs = []
    for c in sorted(SHEETS):
        sh = dict(SHEETS[c])
        sh["look"] = sheetkit.random_look(random.Random("look:7:%s" % c), sh["sex"])
        b = G.spawn(d, c, bs, sheet=sh)
        if people:
            b["people"], b["lore"] = {}, {}
        bs.append(b)
    d.turn = 5
    return d, bs


# ── ① 받는 조건 ─────────────────────────────────────────────────────────────
print("── ① 받는 조건(파서 — 설계 §3.2)")
d, bots, gid = floor()
b1, b2, b3 = bots
o1 = d.view(b1, bots)
way = next((t["id"] for t in o1["targets"] if t["kind"] == "way"), None)
anc_ids = {a["id"] for a in LB.anchors(o1)}
check("① 장면: 방 r? · 고블린 m0·m1 · 가시 함정 t0 · 장검 f%d · 2 가 보인다(b2) · 길 w… 은 대상이 아니다" % gid,
      {"m0", "m1", "t0", "f%d" % gid, "b2"} <= anc_ids and str(o1["zone"]["id"]) in anc_ids and way and way not in anc_ids, sorted(anc_ids))
cases = [({"target": way, "text": "x"}, "no_target", "길(관측마다 새 이름)"), ({"target": "self", "text": "x"}, "self", "self"),
         ({"target": "b1", "text": "x"}, "self", "자기 번호"), ({"target": "i3", "text": "x"}, "no_target", "빈 소지 칸"),
         ({"target": "f99", "text": "x"}, "no_target", "관측에 없는 번호"), ({"target": "b3", "name": "피른", "text": "x"}, "no_target", "안 보이고 말도 안 한 사람"),
         ({"kind": "낯선 사람", "text": "x"}, "person_kind", "'낯선 사람'을 kind 에"), ({"kind": "주점 주인", "text": "x"}, "no_kind", "안 보이는 이름"),
         ({"kind": "슬라임", "text": "x"}, "no_kind", "안 보이는 종류"), ({"target": "t0", "text": "  ", "name": " "}, "empty", "둘 다 빔"),
         ({"target": "t0", "name": "가시"}, "empty", "사람 아닌 것에 name 만(name 은 사람에게만)"), ("고블린은 겁이 많다", "no_target", "객체가 아님")]
bad = [(w, y, drop_why(d, bots, b1, ln)) for ln, y, w in cases]
check("① 버림 사유: " + " · ".join("%s→%s" % (w, y) for w, y, _ in bad),
      all(got[0] == y and "lore_note" not in got[1] for _, y, got in bad), [(w, got[0]) for w, y, got in bad if got[0] != y])
_, dec_b = drop_why(d, bots, b1, {"target": "t0", "kind": "가시 함정", "text": "둘 다 썼다"})
check("① 둘 다 쓰면 target 을 따르고 kind 는 버린다(lore_note + lore_drop both)",
      (dec_b.get("lore_note") or {}).get("at") == "t0" and dec_b["lore_note"]["of"] == "one" and (dec_b.get("lore_drop") or {}).get("why") == "both", dec_b)
pre = copy.deepcopy(b1["lore"])
check("① 버린 쓰기는 장부를 건드리지 않는다", b1["lore"] == pre == {})
q_obs = {"people": {}, "sights": {"features": [], "monsters": [], "bots": []},
         "notices": [{"kind": "board", "quests": [{"tid": "q1", "title": "고블린 퇴치", "id": "Q7"}]}]}
qn, qd = LB.parse({"target": "q1", "text": "보상이 짜다"}, q_obs, "1")
check("① 게시판 의뢰(q1) → quest:<의뢰 id> · 의뢰 제목을 kind 에 쓰면 person_kind(의뢰에는 종류가 없다)",
      (qn or {}).get("key") == "quest:Q7" and qd is None and LB.parse({"kind": "고블린 퇴치", "text": "x"}, q_obs, "1")[1]["why"] == "person_kind", qn)

# ── ② 함정 t<n> ─────────────────────────────────────────────────────────────
print("── ② 함정 t<n>(리뷰 필수 1)")
trap_name = d.traps[0].name
dec2, ops2 = write(d, bots, b1, {"target": "t0", "text": "가시가 튀어나온다"})
k_t0 = "obj:%s:t0" % d.scope
check("② 보이는 함정에 개별 기록 → 안쪽 열쇠 obj:<층 일련>:t0 · 결정 칸에도 key", dec2["lore_note"]["key"] == k_t0 and k_t0 in b1["lore"]
      and ops2 and ops2[0]["op"] == "set" and ops2[0]["key"] == k_t0, (dec2.get("lore_note"), ops2))
p2, _, o2 = prompt(d, bots, b1)
check("② 같은 층에서 다시 보면 대상 목록의 [t0] 아래 '  · 네 기록(t0): 「…」'",
      "  · 네 기록(t0): 「가시가 튀어나온다」" in under(p2, "- [t0]", 3), under(p2, "- [t0]", 3))
d.traps[0].sprung = True
p2b, _, o2b = prompt(d, bots, b1)
check("② 밟힌(sprung) 함정은 대상에서 빠져 안 뜬다(기록은 장부에 남는다 — 층과 함께 지워진다)",
      "t0" not in {t["id"] for t in o2b["targets"]} and "가시가 튀어나온다" not in p2b and k_t0 in b1["lore"])
d.traps[0].sprung = False
dec2k, _ = write(d, bots, b1, {"kind": trap_name, "text": "밟으면 따끔하다"})
check("② 함정 종류 기록은 로어북 장부(kind:%s — 도감 note 가 아니다)" % trap_name,
      dec2k["lore_note"]["key"] == "kind:%s" % trap_name and ("kind:%s" % trap_name) in b1["lore"], dec2k.get("lore_note"))
dn, botsn, _ = floor()                                # 새 원정의 같은 깊이 층(같은 시드 · 다른 층 인스턴스)
botsn[0]["lore"], botsn[0]["people"] = b1["lore"], b1["people"]
pn_, _, on_ = prompt(dn, botsn, botsn[0])
check("② 새 원정의 같은 깊이 층의 t0 엔 개별 기록이 안 뜬다(일련이 다르다) · 종류 기록은 뜬다",
      dn.scope != d.scope and "t0" in {t["id"] for t in on_["targets"]} and "가시가 튀어나온다" not in pn_
      and "네 기록(종류: %s): 「밟으면 따끔하다」" % trap_name in pn_, (dn.scope, d.scope))

# ── ③ 칸 병합 ───────────────────────────────────────────────────────────────
print("── ③ 칸 단위 병합(c02r 회귀 — 옛 person_note 는 항목을 통째로 바꿔 이름·글을 지웠다)")
write(d, bots, b1, {"target": "b2", "name": "카야", "text": "도적이라고 했다"})
b1["people"]["b2"]["etc"] = "엔진이 둔 칸"
write(d, bots, b1, {"target": "b2", "name": "카야 누나"})
e3 = dict(b1["people"]["b2"])
check("③ 이름만 쓰면 글은 그대로", e3.get("name") == "카야 누나" and e3.get("text") == "도적이라고 했다", e3)
write(d, bots, b1, {"target": "b2", "text": "궁수였다"})
e3 = dict(b1["people"]["b2"])
check("③ 글만 쓰면 이름은 그대로(옛 파서는 이름 없는 쓰기를 통째로 버렸다)", e3.get("name") == "카야 누나" and e3.get("text") == "궁수였다", e3)
check("③ 다른 칸은 그대로(dict 교체 금지) · 세계 칸 turn·depth·src 만 갱신", e3.get("etc") == "엔진이 둔 칸" and e3.get("src") == "self" and e3.get("turn") == d.turn)
snap3 = copy.deepcopy(b1["people"])
why3, _ = drop_why(d, bots, b1, {"target": "b2", "name": "", "text": ""})
check("③ 둘 다 빈 쓰기는 무변화(빈 칸 = 안 바꿈 — 지우기는 없다)", why3 == "empty" and b1["people"] == snap3)
write(d, bots, b1, {"target": "t0", "text": "두 번째로 고쳐 씀"})
check("③ 사람 밖 기록도 같은 규칙(글을 고쳐도 쓸 때 본 이름 label 은 남는다)", b1["lore"][k_t0].get("label") == trap_name and b1["lore"][k_t0]["text"] == "두 번째로 고쳐 씀")

# ── ④ 같은 이름 둘 ─────────────────────────────────────────────────────────
print("── ④ 같은 이름 둘(리뷰 필수 2 — '주민의 집')")
dt, tb = town()
t1, t2 = tb[0], tb[1]
ot = dt.view(t1, tb)
homes = sorted((f for f in ot["sights"]["features"] if f["name"] == "주민의 집"), key=lambda f: f["dist"])
check("④ 장면: '주민의 집' 피처 둘(같은 이름·다른 공간) · 공간 id 가 갈린다",
      len(homes) == 2 and len({dt.building_ids.get(int(h["id"][1:])) for h in homes}) == 2, [(h["id"], h["dist"]) for h in homes])
near_h, far_h = homes[0]["id"], homes[1]["id"]
write(dt, tb, t1, {"target": near_h, "text": "가까운 집 — 개가 짖는다"})
write(dt, tb, t1, {"target": far_h, "text": "먼 집 — 할머니가 산다"})
dk4, _ = write(dt, tb, t1, {"kind": "주민의 집", "text": "주민의 집엔 들어갈 수 없다"})
p4, _, o4 = prompt(dt, tb, t1)
check("④ 각 집 아래 제 기록 · 종류 기록은 가까운 집 아래 한 번",
      under(p4, "- 주민의 집 %s" % near_h, 2) == ["  · 네 기록(%s): 「가까운 집 — 개가 짖는다」" % near_h, "  · 네 기록(종류: 주민의 집): 「주민의 집엔 들어갈 수 없다」"]
      and under(p4, "- 주민의 집 %s" % far_h, 1) == ["  · 네 기록(%s): 「먼 집 — 할머니가 산다」" % far_h] and p4.count("주민의 집엔 들어갈 수 없다") == 1,
      (under(p4, "- 주민의 집 %s" % near_h, 2), under(p4, "- 주민의 집 %s" % far_h, 2)))
flat = json.dumps(o4.get("lore"), ensure_ascii=False)
check("④ obs.lore 는 목록 {of, at, name, text} — 안쪽 열쇠·uid·공간 id 가 없다",
      isinstance(o4.get("lore"), list) and all(set(r) == {"of", "at", "name", "text"} for r in o4["lore"])
      and not re.search(r"(place|obj|gear|kind|zone|quest|monster):", flat) and "z_home" not in flat and "uid" not in flat, flat[:300])
o4b = copy.deepcopy(o4)                               # 두 집이 안 보이는 자리(같은 관측에서 피처만 뺀다) — 이름 들림만 남는다
o4b["sights"]["features"] = [f for f in o4b["sights"]["features"] if f["name"] != "주민의 집"]
o4b["lore"], refs4 = LB.observe(dt, t1, o4b)
o4b["messages"] = [{"from": "2", "text": "주민의 집 쪽으로 가 볼까", "turn": 5}]
ch4, cut4 = LB.pick(o4b, cap=99)
keys4 = [refs4[r[1]] for r, at in ch4 if r[0] == "l"]
check("④ 안 보일 때 '주민의 집'을 들으면 셋이 다 후보(같은 자리·같은 길이 → 안쪽 열쇠 순 — 거리는 안 본다) · 자리는 떠오른 기록 절",
      keys4 == sorted(["kind:주민의 집", "place:%s" % dt.building_ids[int(near_h[1:])], "place:%s" % dt.building_ids[int(far_h[1:])]])
      and all(at is None for r, at in ch4 if r[0] == "l"), (keys4, ch4))

# ── ⑤ 덮어쓰기 보장 ─────────────────────────────────────────────────────────
print("── ⑤ 쓸 수 있는 대상 ⊆ 뜨는 대상(리뷰 필수 3)")
d5, b5, g5 = floor()
c1 = b5[0]
o5 = d5.view(c1, b5)
targets5 = [a for a in LB.anchors(o5)]
miss = []
for a in targets5:
    ln = {"target": a["id"], "text": "기록 %s" % a["id"], **({"name": "이름%s" % a["id"]} if a.get("person") else {})}
    dec5, _ = write(d5, b5, c1, ln)
    if not dec5.get("lore_note"):
        miss.append(("받지 않음", a["id"], dec5.get("lore_drop")))
o5b = d5.view(c1, b5)
ch5, _ = LB.pick(o5b, cap=99)
seen5 = {(r[1] if r[0] == "p" else o5b["lore"][r[1]]["text"]) for r, _ in ch5}
for a in targets5:
    want = a["person"] if a.get("person") else ("기록 %s" % a["id"])
    if a.get("count"):
        want = "기록 %s" % a["id"]                     # 물약 칸은 종류로 받는다 — 같은 글이 종류 기록으로 뜬다
    if want not in seen5:
        miss.append(("안 뜸", a["id"]))
check("⑤ 지금 보이는 것·서 있는 곳·소지품·사람 — 쓴 것은 전부 같은 관측에서 뜬다(상한 전) · 대상 %d개" % len(targets5), not miss and len(targets5) >= 6, miss)
check("⑤ (위 장면은 걸린 기록이 6을 넘는다 — 상한에 잘린 것만이 보장 밖이다: 측정은 lore_cut)", len(ch5) > LB.SHOW_MAX and len(LB.pick(o5b)[1]) == len(ch5) - LB.SHOW_MAX)
d5, b5, g5 = floor()                                    # 상한에 안 걸리는 새 장면 — 사람 기록 하나
c1 = b5[0]
write(d5, b5, c1, {"target": "b2", "name": "이름b2", "text": "기록 b2"})
b5[1]["x"], b5[1]["y"] = 30, 21                        # 2 를 시야 밖으로
spoke = [{"from": "2", "text": "어디야? 나 길을 잃었어", "turn": 9, "to": "1", "to_me": True}]
p5, _, o5c = prompt(d5, b5, c1, spoke)
check("⑤ 시야 밖에서 내게 말한 사람의 기록 — 말 속에 그 이름이 없어도 '## 떠오른 기록'에(말한 사람 활성화)",
      "b2" not in {"b%s" % x["char"] for x in o5c["sights"]["bots"]} and "## 떠오른 기록 (들은 말·말한 사람)" in p5
      and "- 이름b2: 「기록 b2」" in p5.split("## 떠오른 기록")[1], p5.split("## 들은 말")[-1][:300])
dec5s, _ = write(d5, b5, c1, {"target": "b2", "text": "길을 잃었다고 했다"}, spoke)
check("⑤ 안 보이는 화자에게도 쓸 수 있다(at null — 그 사람이 다시 말하거나 보이면 뜬다)", (dec5s.get("lore_note") or {}).get("key") == "b2"
      and dec5s["lore_note"]["at"] is None and c1["people"]["b2"]["text"] == "길을 잃었다고 했다", dec5s.get("lore_note"))

# ── ⑥ 도감 칸 ──────────────────────────────────────────────────────────────
print("── ⑥ 몬스터 종류 = 도감 원장 note(리뷰 필수 3)")
d6, b6, _ = floor()
iss = bestiary.Issuer({"1": "두란"})
k6 = "monster:" + d6.monsters[0].kind
gob = d6.monsters[0].kind
iss.known("두란").update({k6, "monster:박쥐"})
iss.record("두란").update({k6: {"turn": 1, "depth": 1, "n": 3}, "monster:박쥐": {"turn": 1, "depth": 1, "n": 1}})
b6[0]["known"], b6[0]["book"] = iss.known("두란"), iss.record("두란")
dec6, ops6 = write(d6, b6, b6[0], {"kind": gob, "text": "겁이 많다"})
check("⑥ 보이는 몬스터의 종 이름 → monster:<종> · 로어북 장부엔 안 둔다(set 로그는 남긴다)",
      dec6["lore_note"]["key"] == k6 and not any(k.endswith(gob) for k in b6[0]["lore"]) and ops6 and ops6[0]["key"] == k6, (dec6.get("lore_note"), b6[0]["lore"]))
iss.consume("tick", {"turn": 9, "decisions": {"1": dec6}})
check("⑥ 발급기가 결정의 lore_note 를 원장 note 로 접는다", (iss.record("두란")[k6].get("note") or {}).get("text") == "겁이 많다")
p6, _, _ = prompt(d6, b6, b6[0])
check("⑥ 인물 기록 판: 몬스터 줄 아래 '네 생각' 대신 '네 기록(종류: %s)' 한 번(가까운 쪽)" % gob,
      p6.count("네 기록(종류: %s): 「겁이 많다」" % gob) == 1 and "  · %s m0 — 네 기록(종류: %s): 「겁이 많다」" % (gob, gob) in p6
      and "네 생각(네가 적어 둔 것)" not in p6, [ln for ln in p6.splitlines() if gob in ln][:6])
iss.consume("tick", {"turn": 10, "decisions": {"1": {"src": "haiku", "book_line": {"key": k6, "text": "책 한 줄"},
                                                     "lore_note": {"key": k6, "of": "kind", "at": "m0", "text": "로어북이 이긴다"}}}})
iss.consume("tick", {"turn": 11, "decisions": {"1": {"src": "haiku", "book_line": {"key": "monster:박쥐", "text": "박쥐는 시끄럽다"},
                                                     "lore_note": {"key": k6, "of": "kind", "at": "m0", "text": "둘 다 남는다"}}}})
r6 = iss.record("두란")
check("⑥ 한 결정에 book_line·lore_note 같은 종 → lore_note 가 이긴다(book_line 먼저 접고 lore_note 나중) · 다른 종이면 둘 다",
      (r6[k6].get("note") or {}).get("text") == "둘 다 남는다" and (r6["monster:박쥐"].get("note") or {}).get("text") == "박쥐는 시끄럽다")
iss2 = bestiary.Issuer({"1": "두란"})
iss2.known("두란").update({k6, "monster:박쥐"})
iss2.record("두란").update({k6: {"turn": 1, "depth": 1, "n": 3}, "monster:박쥐": {"turn": 1, "depth": 1, "n": 1}})
iss2.consume("tick", {"turn": 10, "decisions": {"1": {"src": "haiku", "book_line": {"key": k6, "text": "책 한 줄"},
                                                      "lore_note": {"key": k6, "of": "kind", "at": "m0", "text": "로어북이 이긴다"}}}})
check("⑥ 같은 결정 → 같은 note(발급기 = 스트림 투영 · 순서만으로 정해진다)", (iss2.record("두란")[k6].get("note") or {}).get("text") == "로어북이 이긴다")
sp6 = os.path.join(ROOT, "stream6.jsonl")
recs6 = [{"kind": "run_meta", "party": [{"char": "1", "name": "두란"}], "bestiary": {"두란": [k6]}, "bestiary_progress": {"두란": {k6: {"n": 3}}}},
         {"kind": "level", "turn": 0, "depth": 1, "monsters": []},
         {"kind": "tick", "turn": 9, "decisions": {"1": dec6}, "bots": [], "events": [], "monsters": []}]
with open(sp6, "w", encoding="utf-8") as f:
    f.write("\n".join(json.dumps(r, ensure_ascii=False) for r in recs6) + "\n")
iss3, _ = bestiary.replay(sp6)
check("⑥ 같은 스트림을 오프라인 소급해도 같은 원장 note", (iss3.record("두란").get(k6, {}).get("note") or {}).get("text") == "겁이 많다")
b6[0]["book"] = {"monster:박쥐": {"n": 1}}            # 어긋난 상태: 보이는 종(이름이 보인다)이 내 원장에 없다
dec6m, ops6m = write(d6, b6, b6[0], {"kind": gob, "text": "원장 밖에서 쓴 기록"})
check("⑥ 원장에 없는 종(어긋남)은 로어북 kind:<이름> 에 둔다 — 결정 칸 key 도 그 열쇠",
      dec6m["lore_note"]["key"] == "kind:" + gob and b6[0]["lore"].get("kind:" + gob, {}).get("text") == "원장 밖에서 쓴 기록", dec6m.get("lore_note"))
b6[0]["book"] = {k6: {"n": 1, "note": {"text": "도감 쪽 기록"}}}
p6m, _, _ = prompt(d6, b6, b6[0])
check("⑥ 도감 note 가 있으면 그것을 띄운다(같은 이름 로어북 기록은 안 띄운다)", "도감 쪽 기록" in p6m and "원장 밖에서 쓴 기록" not in p6m)
ops6g = LB.merge(b6[0], k6)
check("⑥ 도감 쪽에 같은 종이 쓰이면 merge 로 합류(로어북에서 지운다)", ops6g == [{"op": "merge", "key": "kind:" + gob, "into": k6}] and ("kind:" + gob) not in b6[0]["lore"])
ub = d6.view(b6[0], b6)
b6[0]["known"] = set()                                 # 모르는 종 = '낯선 짐승'
o6u = d6.view(b6[0], b6)
dec6u, _ = write(d6, b6, b6[0], {"kind": LB.UNKNOWN_BEAST, "text": "모르는 짐승은 피한다"})
check("⑥ 모르는 짐승은 보이는 이름 그대로 kind:낯선 짐승(도감과 합류하지 않는다) · 엔진의 이름과 같은 글자",
      LB.UNKNOWN_BEAST == G.UNKNOWN_BEAST and o6u["sights"]["monsters"][0]["kind"] == G.UNKNOWN_BEAST
      and dec6u["lore_note"]["key"] == "kind:" + G.UNKNOWN_BEAST, dec6u.get("lore_note"))

# ── ⑦ 번호 안정성 ───────────────────────────────────────────────────────────
print("── ⑦ 번호 안정성")
pa, _, oa = prompt(d, bots, b1)
pb, _, ob = prompt(d, bots, b1)
check("⑦ 같은 층에서 관측을 여러 번 만들어도 같은 기록·같은 줄", oa.get("lore") == ob.get("lore") and
      [ln for ln in pa.splitlines() if "네 기록" in ln] == [ln for ln in pb.splitlines() if "네 기록" in ln] and oa.get("lore"))
_ = dn.view(botsn[0], botsn)                           # 다른 층에 갔다가(같은 장부)
pc, _, oc = prompt(d, bots, b1)                        # 보존된 층으로 돌아오면(같은 층 인스턴스)
check("⑦ 다른 층에 갔다 돌아와도(보존 층 = 같은 인스턴스) 그대로", oc.get("lore") == oa.get("lore") and "두 번째로 고쳐 씀" in pc)

# ── ⑧ 장비 따라가기 ─────────────────────────────────────────────────────────
print("── ⑧ 장비 따라가기(gear:<고유 번호>)")
d8, b8, g8 = floor()
e1, e2, e3_ = b8
dec8, _ = write(d8, b8, e1, {"target": "f%d" % g8, "text": "녹슨 장검 — 손잡이가 헐겁다"})
k8 = dec8["lore_note"]["key"]
uid8 = d8.features[g8].uid
check("⑧ 바닥 장비에 기록 → gear:<uid> · 기록할 때 피처에 uid 가 붙는다(다른 피처엔 없다)",
      k8 == "gear:%d" % uid8 and sum(1 for f in d8.features.values() if getattr(f, "uid", None)) == 1, (k8, uid8))
r8 = d8._interact(e1, "f%d" % g8, b8)
p8a, _, _ = prompt(d8, b8, e1)
check("⑧ 줍기 → 몸의 장비 칸에 uid · 대상 목록 [i2] 아래 내 기록",
      r8.get("result") == "equip" and e1["weapon"].get("uid") == uid8 and "  · 네 기록(i2): 「녹슨 장검 — 손잡이가 헐겁다」" in under(p8a, "- [i2]", 3),
      (r8.get("result"), e1.get("weapon")))
d8b, b8b, _ = floor()                                   # 다음 층(층 이월 — 개체 번호는 층-로컬이라 새 번호)
old_id = e1["weapon"]["id"]
b8b[0]["lore"], b8b[0]["people"], b8b[0]["weapon"] = e1["lore"], e1["people"], e1["weapon"]
d8b.adopt_gear(b8b[0])
p8b, _, _ = prompt(d8b, b8b, b8b[0])
check("⑧ 층 이월 — 번호가 바뀌어도(f%s→f%s) 같은 장비라 내 기록이 뜬다" % (old_id, b8b[0]["weapon"]["id"]),
      b8b[0]["weapon"]["id"] != old_id and "  · 네 기록(i2): 「녹슨 장검 — 손잡이가 헐겁다」" in under(p8b, "- [i2]", 3))
h1, h2 = b8b[0], b8b[1]
h2["weapon"] = {"id": d8b._alloc_fid(), "name": "단검", "bonus": 1, "worn": ["2"]}
rg = d8b._give(h1, "b2", "weapon", b8b)
fg = next((f for f in d8b.features.values() if getattr(f, "uid", None) == uid8), None)
p8c, _, o8c = prompt(d8b, b8b, h1)
check("⑧ 건네기(상대 손이 차 있어 발밑에 놓임) → 바닥 피처가 uid 를 이어받고 그 줄 아래 내 기록",
      rg.get("result") == "given" and rg.get("placed") is True and fg is not None and h1.get("weapon") is None, rg)
check("⑧ … 놓인 장비 f%s — 방위 줄 아래 '  · 장검 f… — 네 기록: 「…」'(방위 줄 판은 대상 이름을 앞에)" % (fg.id if fg else "?"),
      fg is not None and "  · 장검 f%d — 네 기록: 「녹슨 장검 — 손잡이가 헐겁다」" % fg.id in p8c, [ln for ln in p8c.splitlines() if "녹슨" in ln])
p8d, _, _ = prompt(d8b, b8b, h2)
check("⑧ 받은 사람(2)에겐 안 뜬다 — 기록은 쓴 사람의 장부에, 장비엔 번호만", "녹슨 장검" not in p8d)
h2["weapon"] = None
r8e = {}
if fg is not None:
    fg.x, fg.y = h2["x"], h2["y"]
    r8e = d8b._interact(h2, "f%d" % fg.id, b8b)
p8e, _, _ = prompt(d8b, b8b, h2)
check("⑧ 2 가 주워 들어도(uid 그대로) 2 의 글에는 내 기록이 없다", r8e.get("result") == "equip" and (h2.get("weapon") or {}).get("uid") == uid8 and "녹슨 장검" not in p8e)
h2["weapon"], h1["weapon"] = None, None
d8b._put_gear("weapon", {"id": None, "name": "장검", "bonus": 2, "worn": ["2"], "uid": uid8}, h1["x"], h1["y"], "2")   # 2 가 내 발밑에 내려놓았다
fz = next(f for f in d8b.features.values() if getattr(f, "uid", None) == uid8)
r8f = d8b._interact(h1, "f%d" % fz.id, b8b)
p8f, _, _ = prompt(d8b, b8b, h1)
check("⑧ 다시 줍기 → 다시 [i2] 아래 내 기록(줍기·이월·건네기·내려놓기를 지나도 같은 장비)",
      r8f.get("result") == "equip" and "  · 네 기록(i2): 「녹슨 장검 — 손잡이가 헐겁다」" in under(p8f, "- [i2]", 3))

# ── ⑨ 쓸어내기 ─────────────────────────────────────────────────────────────
print("── ⑨ 쓸어내기")
bsw = {"people": {"b2": {"name": "카야", "text": "x", "turn": 1}},
       "lore": {"obj:3:m1": {"text": "a"}, "obj:4:r2": {"text": "b"}, "place:z_home_1": {"text": "c"}, "zone:번화가": {"text": "d"},
                "quest:Q1": {"text": "e"}, "kind:고블린": {"text": "f"}, "gear:2": {"text": "g"}}}
ops9 = LB.sweep(bsw, {"4", "1"})
check("⑨ 사라진 층(일련 3)의 기록만 지운다 — 남은 층·사람·장소·구역·의뢰·종류·장비는 남는다 · sweep 로그",
      ops9 == [{"op": "sweep", "key": "obj:3:m1"}] and sorted(bsw["lore"]) == ["gear:2", "kind:고블린", "obj:4:r2", "place:z_home_1", "quest:Q1", "zone:번화가"]
      and "b2" in bsw["people"], (ops9, sorted(bsw["lore"])))
with open(os.path.join(HERE, "show_runner.py"), encoding="utf-8") as f:
    SR_SRC = f.read()
blk = SR_SRC[SR_SRC.index("사라진 층 인스턴스(원정 결산의 층 버리기"):][:900]
check("⑨ 러너: 틱마다 모든 몸(다른 세계 _everyone · 부활 대기 waiting)에서 — 살아 있는 일련 = 세계들·보존 층·지금 층",
      "_everyone()" in blk and "waiting.values()" in blk and "saved.values()" in blk and "for x_ in worlds" in blk and "LB.sweep" in blk)

# ── ⑩ 뜨기·상한·순서 ─────────────────────────────────────────────────────────
print("── ⑩ 뜨기·상한·순서(리뷰 필수 4)")
d10, b10, g10 = floor()
k1 = b10[0]
k1["potions"] = 1
zid = str(d10.view(k1, b10)["zone"]["id"])
write(d10, b10, k1, {"target": zid, "text": "샘이 있던 방"})
write(d10, b10, k1, {"target": "i1", "text": "물약은 아껴 쓴다"})
p10, _, o10 = prompt(d10, b10, k1)
check("⑩ 서 있는 곳 — 장소 머리 줄 바로 아래 '네 기록(%s)'" % zid, under(p10, "- 던전 1층 > 방 %s" % zid, 1) == ["  · 네 기록(%s): 「샘이 있던 방」" % zid], under(p10, "- 던전 1층 >", 2))
check("⑩ 소지품 — 물약 칸(i1)에 쓴 기록은 종류(회복 물약)로 그 줄 아래", "  · 네 기록(종류: 회복 물약): 「물약은 아껴 쓴다」" in under(p10, "- [i1]", 3))
write(d10, b10, k1, {"target": "m0", "text": "이 녀석은 느리다"})
write(d10, b10, k1, {"target": "m1", "text": "저 녀석은 빠르다"})
write(d10, b10, k1, {"target": "t0", "text": "가시"})
write(d10, b10, k1, {"target": "f%d" % g10, "text": "장검이 놓여 있다"})
write(d10, b10, k1, {"target": "b2", "name": "카야", "text": "곁에 있다"})
write(d10, b10, k1, {"kind": d10.monsters[0].kind, "text": "종류 기록"})
write(d10, b10, k1, {"target": "exit", "text": "계단"} if "exit" in {a["id"] for a in LB.anchors(d10.view(k1, b10))} else {"kind": "가시 함정", "text": "함정 종류"})
p10b, dec10, o10b = prompt(d10, b10, k1)
ch10, cut10 = LB.pick(o10b)
alln, _ = LB.pick(o10b, cap=99)
check("⑩ 걸린 기록 %d개 → 프롬프트에 6줄 · 나머지는 lore_cut(스트림만, 프롬프트에 '잘렸다' 표시 없음)" % len(alln),
      len(alln) >= 9 and len(ch10) == 6 and len(cut10) == len(alln) - 6 and sum(1 for ln in p10b.splitlines() if "네 기록" in ln) == 6
      and "잘" not in "".join(ln for ln in p10b.splitlines() if "네 기록" in ln), (len(alln), len(ch10)))
dist10 = {a["id"]: (a["dist"] if isinstance(a["dist"], int) else 99) for a in LB.anchors(o10b)}
seq = [dist10.get(at, 999) for _, at in alln if at is not None and at in dist10 and not at.startswith("i")]
check("⑩ 고르는 순서 = 보이는 대상의 거리 가까운 순(서 있는 곳 0 · 사람 1 · 장검 1 · …) → 소지품은 맨 뒤",
      seq == sorted(seq) and alln[0][1] == zid and alln[-1][1] == "i1", alln)
lshown, lcut = LB.logged(o10b, k1.get("_lore_refs") or [])
check("⑩ 결정 칸 lore_shown 6 · lore_cut %d — 안쪽 열쇠(층 일련·사람 열쇠)" % len(cut10),
      len(lshown) == 6 and len(lcut) == len(cut10) and lshown[0] == "obj:%s:%s" % (d10.scope, zid) and "b2" in lshown, (lshown, lcut))
ord_obs = {"people": {"b7": {"name": "고블린 대장", "text": "사람 기록"}}, "sights": {"monsters": [], "features": [], "bots": []},
           "lore": [{"of": "kind", "at": None, "name": "고블린", "text": "종류"}, {"of": "one", "at": None, "name": "대장간", "text": "장소"},
                    {"of": "kind", "at": None, "name": "고블린 대장", "text": "대장 종류"}],
           "messages": [{"from": "npc:주점 주인", "text": "대장간 옆에서 고블린 대장이 고블린을 끌고 갔다", "turn": 3}]}
ord_obs["people"]["npc:주점 주인"] = {"name": "", "text": "소문을 판다"}
co, _ = LB.pick(ord_obs, cap=99)
check("⑩ 한 말에 이름 셋(겹치는 '고블린 대장'/'고블린') — 말한 사람 → 처음 나온 자리 → 같은 자리면 긴 이름 먼저 → 사람·로어북 열쇠 순",
      co == [(("p", "npc:주점 주인"), None), (("l", 1), None), (("p", "b7"), None), (("l", 2), None), (("l", 0), None)], co)
tie_refs = sorted(["gear:5", "kind:대장간", "monster:대장간", "place:z_smith_1"])   # 엔진이 obs.lore 를 싣는 순서 = 안쪽 열쇠 순
tie_rows = {"gear:5": {"of": "one", "at": "i2", "name": "대장간", "text": "소지 장비"}, "kind:대장간": {"of": "kind", "at": None, "name": "대장간", "text": "종류"},
            "monster:대장간": {"of": "kind", "at": None, "name": "대장간", "text": "몬스터 종류"},
            "place:z_smith_1": {"of": "one", "at": None, "name": "대장간", "text": "건물"}}
tie_obs = {"people": {"b7": {"name": "대장간", "text": "사람"}, "npc:주점 주인": {"name": "대장간", "text": "NPC"}},
           "sights": {"monsters": [], "features": [], "bots": []}, "items": [{"id": "i2", "name": "장검", "slot": "weapon"}],
           "lore": [tie_rows[k] for k in tie_refs], "messages": [{"from": "3", "text": "대장간 가자", "turn": 3}]}
ct, _ = LB.pick(tie_obs, cap=99)
ct_keys = [r[1] if r[0] == "p" else tie_refs[r[1]] for r, _ in ct]
check("⑩ (p0511b) 이름 들림 동률 = 안쪽 열쇠 순(사람 b·종류 kind·monster·NPC npc·건물 place — 실제 열쇠 정렬과 같다) · 소지 장비의 개별 기록은 이름 들림이 아니라 소지품 순서([i2] 아래)",
      ct_keys == sorted(["b7", "npc:주점 주인", "kind:대장간", "monster:대장간", "place:z_smith_1"]) + ["gear:5"]
      and dict(ct)[("l", tie_refs.index("gear:5"))] == "i2", ct)
o10b["book_invite"] = {"key": "monster:x", "name": "고블린", "why": "deep", "n": 3}
p10c = brains._wire(o10b, {"?": brains.STRANGER}, compose=True)
check("⑩ 도감 절은 6줄에 안 센다(인물 기록 판은 사실 한 줄 — 초대 문장 없음)",
      "## 도감" in p10c and "고블린의 심층 정보가 열렸다(지금까지 3번 겪음)." in p10c and "book_line" not in p10c
      and sum(1 for ln in p10c.splitlines() if "네 기록" in ln) == 6)
check("⑩ 같은 입력 → 같은 줄(결정론)", brains._wire(copy.deepcopy(o10b), {"?": brains.STRANGER}, compose=True) == p10c)
rec_blk = p10c[p10c.index("RECORD:\n"):].split("\n\n")[0]
check("⑩ RECORD 블록은 기능 설명서(무엇이 되는지만) — 쓰라는 권유 낱말이 없다('좋다'·'해 보'·'남겨 두'·'권한'·'하라') · 상한 숫자는 lorebook 상수",
      not re.search(r"좋다|해 보|남겨 두|권한|하라", rec_blk) and ("%d개까지" % LB.SHOW_MAX) in rec_blk and ("%d개까지" % LB.KEEP_MAX) in rec_blk
      and ("한 줄(%d자)" % LB.TEXT_LEN) in rec_blk, rec_blk)

# ── ⑪ 길이 ─────────────────────────────────────────────────────────────────
print("── ⑪ 길이(이름 %d · 글 %d)" % (LB.NAME_LEN, LB.TEXT_LEN))
sh11 = {"1": {"name": "가" * 30, "relationships": {"2": "나" * 81}}, "2": {"name": "다" * 30, "relationships": {}}}
sd11 = LB.seed(sh11, "1")
check("⑪ 시트 씨앗 81자 → 저장에서 80 · 이름 30자 → 20", len(sd11["b2"]["text"]) == 80 and len(sd11["b2"]["name"]) == 20)
dec11, _ = write(d10, b10, k1, {"target": "t0", "text": "글" * 81})
check("⑪ 81자 글 → 결정·장부에서 80", len(dec11["lore_note"]["text"]) == 80 and len(k1["lore"]["obj:%s:t0" % d10.scope]["text"]) == 80)
d11, b11, _ = floor()                                  # 상한에 안 걸리는 새 장면
b11[0]["people"]["b3"] = {"name": "피른", "text": "긴" * 300, "turn": 1, "src": "sheet"}
p11, _, _ = prompt(d11, b11, b11[0], [{"from": "2", "text": "피른은 어디 갔지?", "turn": 9}])
ln11 = next((ln for ln in p11.splitlines() if ln.startswith("- 피른: ")), "")
check("⑪ 이름 들림 절에서도 80을 넘지 않는다(그릴 때도 같은 자르기)", ln11 == "- 피른: 「%s」" % ("긴" * 80), ln11[:120])

# ── ⑫ 총량 ─────────────────────────────────────────────────────────────────
print("── ⑫ 총량(한 몸 %d개)" % LB.KEEP_MAX)
b12 = {"people": {"b%d" % i: {"name": "사람%d" % i, "text": "x", "turn": i} for i in range(2, 12)},
       "lore": {**{"kind:종류%02d" % i: {"text": "x", "turn": 50 + i} for i in range(85)}, **{"obj:1:m%d" % i: {"text": "x", "turn": 200 + i} for i in range(5)}}}
d12 = G.Dungeon(seed=3, w=30, h=14, n_monsters=0, n_traps=0, n_lurkers=0)
d12.scope = 1
ops12 = LB.apply(d12, b12, {"key": "kind:새 기록", "of": "kind", "at": "f1", "label": "새", "text": "백한 번째"}, 300)
check("⑫ 101번째 기록 → 층 기록(obj:)부터 바랜다 — 층 기록 중 가장 오래전에 고친 것(turn 200) · fade 로그",
      ops12[-1] == {"op": "fade", "key": "obj:1:m0"} and "obj:1:m0" not in b12["lore"] and len(b12["people"]) + len(b12["lore"]) == 100, ops12[-2:])
for k in [k for k in b12["lore"] if k.startswith("obj:")]:
    del b12["lore"][k]
for i in range(4):
    b12["lore"]["kind:채움%d" % i] = {"text": "x", "turn": 260 + i}
ops12b = LB.apply(d12, b12, {"key": "kind:또 새 기록", "of": "kind", "at": "f1", "label": "또", "text": "또 넘침"}, 301)
check("⑫ 층 기록이 없으면 가장 오래전에 고쳐 쓴 것(사람 turn 2)부터 — 사람도 같은 줄에 선다(설계 §3.4)",
      ops12b[-1] == {"op": "fade", "key": "b2"} and "b2" not in b12["people"], ops12b[-2:])

# ── ⑬ 이관·복원 ─────────────────────────────────────────────────────────────
print("── ⑬ 저장 판 4 → 5 이관 · 발급 상태 복원(리뷰 필수 5)")
dA, bA, gA = floor(stamp=False)
dB, _, _ = floor(seed=41, stamp=False)
dT = G.Dungeon(seed=5, w=30, h=14, n_monsters=0, n_traps=0, n_lurkers=0)
for x_ in (dA, dB, dT):
    if hasattr(x_, "scope"):
        del x_.scope
bA[0].pop("lore")
bA[0]["people"] = {"b2": {"name": "이" * 25, "text": "옛" * 120, "turn": 0, "src": "sheet"}}
for b_ in bA[1:]:
    b_.pop("lore")
dA.depth = 2
snap13 = {"version": 2, "state_version": 4, "run_id": "x", "d": dA, "bots": bA, "saved": {1: {"d": dB, "mem": {}}, 0: {"d": dT, "mem": {}}},
          "worlds": [{"d": dA, "bots": bA}], "waiting": {}, "sheets": SHEETS}
up = snapshot.upgrade(pickle.loads(pickle.dumps(snap13)))
uA, uB, uT = up["d"], up["saved"][1]["d"], up["saved"][0]["d"]
check("⑬ 내용 판 4 → 5: 몸에 lore{} · 사람 기록 이름 20·글 80 · 던전마다 scope(보존 층 깊이 순 → 세계 → 지금 층) · lore_ids",
      up["state_version"] == snapshot.STATE_VERSION == 5 and all(b_.get("lore") == {} for b_ in up["bots"])
      and len(up["bots"][0]["people"]["b2"]["name"]) == 20 and len(up["bots"][0]["people"]["b2"]["text"]) == 80
      and (uT.scope, uB.scope, uA.scope) == (1, 2, 3) and up["lore_ids"] == {"scope": 4, "uid": 1},
      ((getattr(uT, "scope", None), getattr(uB, "scope", None), getattr(uA, "scope", None)), up.get("lore_ids")))
plain = {"version": 2, "state_version": 4, "run_id": "y", "d": dT, "bots": [body(dT, "1", [], people=False)], "saved": {}, "sheets": SHEETS}
upp = snapshot.upgrade(plain)
check("⑬ 인물 기록이 꺼진 판의 스냅샷은 손대지 않는다(lore·scope·lore_ids 없음)", "lore_ids" not in upp and "lore" not in upp["bots"][0] and getattr(dT, "scope", None) is None)
ub0 = up["bots"][0]
ub0["x"], ub0["y"] = 7, 26
dec13, _ = write(uB, up["bots"], ub0, {"target": "t0", "text": "보존 층의 함정"})
again = snapshot.upgrade(pickle.loads(pickle.dumps(up)))
ag0 = again["bots"][0]
p13, _, _ = prompt(again["saved"][1]["d"], again["bots"], ag0)
check("⑬ 이어가기 전에 쓴 층 기록이 보존 층에서 그대로 뜬다(피클 왕복 · 이미 5 인 스냅샷은 그대로)",
      dec13["lore_note"]["key"] == "obj:2:t0" and "보존 층의 함정" in p13 and again["lore_ids"] == up["lore_ids"], dec13.get("lore_note"))
ub0["lore"]["gear:9"] = {"text": "x"}
uA.features[gA].uid = 7
ids13 = LB.restore_ids({"scope": 1, "uid": 1}, snapshot.dungeons(up), snapshot._bodies(up))
nd13 = G.Dungeon(seed=99, w=30, h=14, n_monsters=0, n_traps=0, n_lurkers=0)
LB.stamp(nd13, ids13)
nf = nd13._add_feature("weapon", "단검", 3, 3)
u13 = LB.gear_uid(nd13, nd13.features[nf])
check("⑬ lore_ids 를 일부러 작게 망가뜨려도 — 새 층 일련·새 장비 번호가 쓰인 것과 겹치지 않는다(실제로 쓰인 가장 큰 번호 + 1)",
      nd13.scope not in {1, 2, 3} and nd13.scope >= 4 and u13 not in {7, 9} and u13 >= 10, (nd13.scope, u13, ids13))
dV, bV = town()                                         # p0511b(Codex p0511r 필수 ①) 옛 마을 — 0.5.10 판에는 건물 피처 → 공간 id 가 없었다
want_bids = dict(dV.building_ids)
check("⑬ 러너가 지을 때 다는 짝 = layout 문턱 칸으로 다시 이은 짝(lorebook.town_building_ids)", LB.town_building_ids(dV) == want_bids and len(want_bids) >= 10, want_bids)
del dV.building_ids
del dV.scope
bV[0].pop("lore")
snapV = {"version": 2, "state_version": 4, "run_id": "v", "d": dV, "bots": bV, "saved": {0: {"d": dV, "mem": {}}}, "sheets": SHEETS}
upV = snapshot.upgrade(pickle.loads(pickle.dumps(snapV)))
uV, ubV = upV["d"], upV["bots"][0]
homeV = next(f["id"] for f in uV.view(ubV, upV["bots"])["sights"]["features"] if f["name"] == "주민의 집")
decV, _ = write(uV, upV["bots"], ubV, {"target": homeV, "text": "이어간 판의 집"})
check("⑬ 옛 마을 스냅샷 4 → 5: 건물 피처 → 공간 id 를 다시 단다 — 이어간 판의 집 기록이 place:<공간>(층 기록 obj: 아님)",
      getattr(uV, "building_ids", None) == want_bids and decV["lore_note"]["key"] == "place:%s" % want_bids[int(homeV[1:])], (decV.get("lore_note"), getattr(uV, "building_ids", None)))
with open(os.path.join(HERE, "snapshot.py"), encoding="utf-8") as f:
    SNAP_SRC = f.read()
check("⑬ 이관 체인 0..4 전부 · 러너가 이어갈 때 restore_ids 로 잇는다", sorted(snapshot.MIGRATIONS) == list(range(snapshot.STATE_VERSION))
      and "LB.restore_ids(snap.get(\"lore_ids\")" in SR_SRC and "4→5(p0.5.11" in SNAP_SRC)

# ── ⑭ 정보 보호 ─────────────────────────────────────────────────────────────
print("── ⑭ 정보 보호")
d14, b14 = town()
x1, x2 = b14[0], b14[1]
o14 = d14.view(x1, b14)
smith = next(f["id"] for f in o14["sights"]["features"] if f["name"] == "대장간")
write(d14, b14, x1, {"target": smith, "text": "두란의 기록 — 망치 소리"})
write(d14, b14, x2, {"target": smith, "text": "카야의 기록 — 칼을 판다더라"})
p14a, _, _ = prompt(d14, b14, x1)
p14b, _, _ = prompt(d14, b14, x2)
check("⑭ 두 몸이 같은 대상에 다른 기록 → 각자 프롬프트엔 제 것만",
      "두란의 기록" in p14a and "카야의 기록" not in p14a and "카야의 기록" in p14b and "두란의 기록" not in p14b)
seen14 = {}
_cc = brains._call_claude
brains._call_claude = lambda pr, model="haiku": (seen14.__setitem__("p", pr), '{"line": "어서 와요."}')[1]
os.environ["DUNGEON_BRAIN_BACKEND"] = "claude_cli"
try:
    brains.npc_reply(x1, {"result": "npc_talk", "npc": "길드 접수원", "line": "모험가 길드예요."}, "안녕하세요", [], npc={"name": "길드 접수원"})
finally:
    brains._call_claude = _cc
    os.environ["DUNGEON_BRAIN_BACKEND"] = "dummy"
check("⑭ NPC 두뇌 입력에 모험가의 기록 글이 없다", seen14.get("p") and "두란의 기록" not in seen14["p"] and "망치 소리" not in seen14["p"])
o8g = d8.view(e1, b8)
check("⑭ (p0511b) 기록된 장비를 들고 있어도 관측 obs.gear 엔 uid 가 없다(안쪽 열쇠) · 관전 스트림의 몸 스냅샷엔 있다",
      "uid" not in (o8g["gear"].get("weapon") or {"uid": 1}) and (G.bot_snapshot(e1).get("weapon") or {}).get("uid") == uid8
      and G._no_uid(o8g["gear"]) is o8g["gear"], o8g["gear"])
import info_guard as IG                                # noqa: E402
pub = IG.public({"type": "use", "result": "x", "lore_note": {"key": "obj:1:t0"}, "lore_ops": {"1": []}, "lore_shown": ["b2"],
                 "nested": {"uid": 3, "scope": 2, "space": "z_home_1", "keep": 1}, "items": [{"lore_ids": {"scope": 1}, "a": 2}]})
check("⑭ (p0511b) 공개 투영 IG.public 이 관전 전용 칸(lore_*·uid·scope·space·lore_ids)을 어느 깊이든 걷는다 — 다른 칸은 그대로",
      pub == {"type": "use", "result": "x", "nested": {"keep": 1}, "items": [{"a": 2}]}, pub)
allp = p14a + p14b + p10b + p4 + p8a
check("⑭ 프롬프트·관측에 안쪽 열쇠(obj:·gear:·place:·kind:·zone:·quest:)·관전 칸(lore_ops·lore_shown·lore_cut·lore_ids)이 없다",
      not re.search(r"\b(obj|gear|place|zone|quest):", allp) and "kind:" not in allp
      and not any(k in o for o in (o14, o10b, o4) for k in ("lore_ops", "lore_shown", "lore_cut", "lore_ids", "_lore_refs")))

# ── ⑮⑯ 러너 판(0콜) ─────────────────────────────────────────────────────────
print("── ⑮⑯ 러너 판 — 따라가기·로그(스텁 두뇌: 1 은 건물 종류를 차례로 적고, 2 는 틀린 대상, 3 은 NPC 를 이름으로 적는다)")
KINDS = ["주민의 집", "신전", "주점", "대장간", "공방", "장비점", "잡화점", "모험가 길드"]


def stub16(p, model="haiku"):
    m = re.search(r"- 번호 (\d+), 이름", p)
    c = m.group(1) if m else "?"
    if c == "1":                                        # 아직 프롬프트에 안 뜬 종류를 하나씩 — 일곱째부터는 상한(6)에 잘린다
        done = re.findall(r"네 기록\(종류: ([^)]+)\)", p)
        k = next((x for x in KINDS if x not in done), KINDS[-1])
        return json.dumps({"type": "wait", "lore_note": {"kind": k, "text": "%s 기록" % k}}, ensure_ascii=False)
    if c == "2":
        return json.dumps({"type": "wait", "lore_note": {"target": "w9_9", "text": "길에 적기"}}, ensure_ascii=False)
    return json.dumps({"type": "wait", "lore_note": {"target": "길드 접수원", "name": "접수원", "text": "물약을 준다"}}, ensure_ascii=False)


env16 = {"DUNGEON_BRAIN_BACKEND": "claude_cli"}         # 두뇌 이름만 실제 백엔드로(호출은 스텁 — 0콜). 판 모양(틱 상한 등)은 러너가 import 때 읽은 BASE_ENV 그대로
old_env16 = {k: os.environ.get(k) for k in env16}
os.environ.update(env16)
STATE16 = os.path.join(ROOT, "state16")
os.makedirs(STATE16, exist_ok=True)
show_runner.STATE = STATE16
_cc16, _ta16 = brains._call_claude, brains.think_all
brains._call_claude = stub16


def think16(d_, bots_, inbox=None, on_error=None, lore_ops=None):
    if d_.turn in (1, show_runner.MAX_TURNS):             # 첫 틱 · 마지막 틱(다음 틱이 없다 — p0511b: end 줄로 나가야 한다)
        for b_ in bots_:
            if b_.get("lore") is not None:
                b_["lore"]["obj:%d:m1" % (999 - (d_.turn > 1))] = {"text": "사라진 층의 기록", "turn": 0, "depth": 1, "src": "self"}
    return _ta16(d_, bots_, inbox, on_error=on_error, lore_ops=lore_ops)


brains.think_all = think16
cap16 = []
_spawn16 = G.spawn


def spawn16(dd, char, bs, **k):
    b = _spawn16(dd, char, bs, **k)
    cap16.append((dd.depth, b))
    return b


G.spawn = spawn16
try:
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            show_runner.main()
        except SystemExit:
            pass
finally:
    brains._call_claude, brains.think_all, G.spawn = _cc16, _ta16, _spawn16
    for k, v in old_env16.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
with open(os.path.join(STATE16, "stream.jsonl"), encoding="utf-8") as f:
    rows16 = [json.loads(ln) for ln in f if ln.strip()]
rm = rows16[0]
lv = next(r for r in rows16 if r["kind"] == "level")
ticks = [r for r in rows16 if r["kind"] == "tick"]
decs = [(r["turn"], c, dd) for r in ticks for c, dd in sorted((r.get("decisions") or {}).items()) if dd.get("src") != "plan"]
check("⑯ run_meta.lore = 시작 원장(시트 씨앗 — 이름 20·글 80) · level.scope · 마을 건물 피처 space",
      sorted(rm.get("lore") or {}) == sorted(SHEETS) and all(len(e.get("text", "")) <= 80 for v in rm["lore"].values() for e in v.values())
      and isinstance(lv.get("scope"), int) and any(f.get("space") for f in lv["features"]), (sorted(rm.get("lore") or {}), lv.get("scope")))
n1 = [dd["lore_note"] for t, c, dd in decs if c == "1" and dd.get("lore_note")]
check("⑯ decisions.lore_note — 러너가 key 를 채운다(종류 kind:<이름>) · at = 쓸 때의 화면 번호",
      n1 and all(x["key"] == "kind:" + x["label"] and x["of"] == "kind" and re.fullmatch(r"f\d+", str(x["at"])) for x in n1), n1[:2])
d2_ = [dd.get("lore_drop") for t, c, dd in decs if c == "2"]
check("⑯ decisions.lore_drop {said, why} — 틀린 대상은 버리고 사유를 남긴다(프롬프트엔 알리지 않는다)",
      d2_ and all(x == {"said": {"target": "w9_9", "text": "길에 적기"}, "why": "no_target"} for x in d2_), d2_[:2])
n3 = [dd.get("lore_note") for t, c, dd in decs if c == "3"]
check("⑯ 사람 기록(3 → 보이는 NPC '길드 접수원' — 이름으로 적음)도 같은 칸 — key npc:<이름> · at 은 그 피처 · target_said 원문",
      n3 and all((x or {}).get("key") == "npc:길드 접수원" and x.get("name") == "접수원" and re.fullmatch(r"f\d+", str(x.get("at")))
                 and x.get("target_said") == "길드 접수원" for x in n3), n3[:1])
sh1 = [dd.get("lore_shown") or [] for t, c, dd in decs if c == "1"]
cut1 = [dd.get("lore_cut") or [] for t, c, dd in decs if c == "1"]
check("⑯ decisions.lore_shown(뜬 것)이 판단마다 늘다가 6에서 멈추고 lore_cut(잘린 것)이 생긴다",
      max(len(x) for x in sh1) == 6 and any(cut1) and all(len(x) <= 6 for x in sh1), [len(x) for x in sh1])
ops16 = [(r["turn"], c, o) for r in ticks for c, os_ in (r.get("lore_ops") or {}).items() for o in os_]
check("⑯ tick.lore_ops — set(쓰기·병합 결과 전체) · sweep(사라진 층 obj:999 — 다음 틱) · 원장이 바뀐 틱에만",
      any(o["op"] == "set" and o["key"] == "kind:주민의 집" and o["entry"]["text"] == "주민의 집 기록" for _, c, o in ops16)
      and any(o == {"op": "sweep", "key": "obj:999:m1"} and t == 2 for t, c, o in ops16)
      and all(r.get("lore_ops") for r in ticks if "lore_ops" in r), [(t, c, o["op"], o["key"]) for t, c, o in ops16][:8])
end16 = next((r for r in rows16 if r["kind"] == "end"), {})
check("⑯ (p0511b) 마지막 틱 끝에 남은 변화(쓸어냄 obj:998 — 다음 틱이 없다)는 end 줄 lore_ops 로",
      sorted(o["key"] for v in (end16.get("lore_ops") or {}).values() for o in v) == ["obj:998:m1"] * 3
      and all(o["op"] == "sweep" for v in end16["lore_ops"].values() for o in v), end16.get("lore_ops"))
import run_control                                     # noqa: E402


def stop_run(how):
    """멈춤 네 길을 러너 판으로 실제로 돈다(0콜 — 더미 두뇌·메모리 대역): 1틱에 사라진 층 기록을 심고(그 틱 끝에 쓸어낸다 → 다음 틱으로 넘길 변화),
    2틱 머리(곱게 멈춤 — stop.json) 또는 2틱 판단(호출 한도·판단 정지 제한 시간·판단 정지 중 멈춤 — 예외)에서 멈춘다. → (스트림 줄들, 요약의 멈춤 사유)."""
    st = os.path.join(ROOT, "state_stop_" + how)
    os.makedirs(st, exist_ok=True)
    show_runner.STATE = st
    exc = {"budget": run_control.BudgetExhausted, "pause_timeout": run_control.PauseTimeout, "user_paused": run_control.StopRequested}.get(how)

    def think(d_, bots_, inbox=None, on_error=None, lore_ops=None):
        if d_.turn == 1:
            for b_ in bots_:
                if b_.get("lore") is not None:
                    b_["lore"]["obj:997:m1"] = {"text": "사라진 층의 기록", "turn": 0, "depth": 1, "src": "self"}
            out_ = _ta16(d_, bots_, inbox, on_error=on_error, lore_ops=lore_ops)
            if how == "user":
                run_control.request_stop(st, pages=False)     # 론처의 '멈춤'(수첩 없이) — 러너가 다음 틱 머리에서 읽는다
            return out_
        if exc is not None:
            raise exc()
        return _ta16(d_, bots_, inbox, on_error=on_error, lore_ops=lore_ops)
    brains.think_all = think
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                show_runner.main()
            except SystemExit:
                pass
    finally:
        brains.think_all = _ta16
    with open(os.path.join(st, "stream.jsonl"), encoding="utf-8") as f:
        rows_ = [json.loads(ln) for ln in f if ln.strip()]
    return rows_, ((snapshot.read_meta(st) or {}).get("stop") or {}).get("reason")


for how in ("user", "budget", "pause_timeout", "user_paused"):
    rows_s, why_s = stop_run(how)
    last = rows_s[-1] if rows_s else {}
    ops_s = sorted((o["op"], o["key"]) for v in (last.get("lore_ops") or {}).values() for o in v)
    check("⑯ (p0511c) 멈춤 '%s' 길: 마지막 줄 = stopped(reason %s · turn 1) — 앞 틱 끝에 쓸어낸 obj:997 가 그 줄 lore_ops 로(관전 로그에서 안 빠진다) · end 없음"
          % (how, how), last.get("kind") == "stopped" and last.get("reason") == how and why_s == how and last.get("turn") == 1
          and ops_s == [("sweep", "obj:997:m1")] * 3 and not any(r["kind"] == "end" for r in rows_s)
          and sum(r["kind"] == "stopped" for r in rows_s) == 1, (last.get("kind"), last.get("reason"), why_s, ops_s))
show_runner.STATE = STATE16
real = len(decs)
rate = sum(1 for _, _, dd in decs if dd.get("lore_note")) / float(real or 1)
miss_rate = sum(1 for _, _, dd in decs if dd.get("lore_drop")) / float(sum(1 for _, _, dd in decs if dd.get("lore_note") or dd.get("lore_drop")) or 1)
cut_rate = sum(1 for _, _, dd in decs if dd.get("lore_cut")) / float(real or 1)
check("⑯ 스트림 칸만으로 기록률·오기율·잘림률을 센다(0콜 — 집계 도구는 자유도 벤치 v2 몫) · 이 판: %.2f · %.2f · %.2f" % (rate, miss_rate, cut_rate),
      real >= 9 and 0 < rate < 1 and 0 < miss_rate < 1 and 0 < cut_rate < 1)
mine16 = [b for dep, b in cap16 if b["char"] == "1"]
check("⑮ 판 시작 몸에 lore{} · 이월 목록(_carry)이 lore 를 같은 객체로 옮긴다(층 이월·부활 _wake·귀환이 같은 목록)",
      mine16 and mine16[0].get("lore") is not None and 'n["lore"] = b["lore"]' in SR_SRC[SR_SRC.index("def _carry("):SR_SRC.index("def _temple_cells(")]
      and "_carry(b, n, d, turn" in SR_SRC[SR_SRC.index("def _wake("):SR_SRC.index("def _wake_waiting(")])
rt = pickle.loads(pickle.dumps(e1))
check("⑮ 피클 왕복(이어하기)에도 lore·장비 uid 그대로", rt["lore"] == e1["lore"] and (rt.get("weapon") or {}).get("uid") == (e1.get("weapon") or {}).get("uid"))

# ── ⑰ 옛 판 바이트 불변 ─────────────────────────────────────────────────────
print("── ⑰ 옛 판(인물 기록 꺼짐) 그대로")
d17, b17, g17 = floor(people=False, stamp=False)
iss17 = bestiary.Issuer({"1": "두란"})
k17 = "monster:" + d17.monsters[0].kind
iss17.known("두란").add(k17)
iss17.record("두란")[k17] = {"n": 3, "note": {"text": "옛 판의 생각"}, "deep": {"n": 3}, "due": "review", "asked_n": 1}
b17[0]["known"], b17[0]["book"] = iss17.known("두란"), iss17.record("두란")
p17, dec17, o17 = prompt(d17, b17, b17[0], reply={"type": "wait", "lore_note": {"target": "t0", "text": "x"}})
check("⑰ 관측에 lore 없음 · 몸에 _lore_refs 없음 · RECORD·lore_note 없음 · 응답의 lore_note 는 받지 않는다",
      "lore" not in o17 and "_lore_refs" not in b17[0] and "RECORD:" not in p17 and "lore_note" not in p17 and "lore_note" not in dec17 and "lore_drop" not in dec17)
check("⑰ 몬스터 '네 생각' 줄 · 도감 초대 문장(book_line) 그대로",
      "에 대한 네 생각(네가 적어 둔 것): 옛 판의 생각" in p17 and "고쳐 쓰려면 응답 JSON 의 `book_line` 필드" in p17)
inv17 = {**o17, "relations": [{"char": "2", "bones": [], "invite": "rescued"}]}
w17 = brains._wire(inv17, {"2": "카야"}, compose=True)
pw = brains._wire({**inv17, "people": {}}, {"?": brains.STRANGER}, compose=True)
check("⑰ 관계 한 줄 초대: 옛 판은 relation_line 문장 그대로 · 인물 기록 판은 사실 한 줄만(민옥 결정 5)",
      "`relation_line` 필드" in w17 and "relation_line" not in pw and "## 방금 있었던 일" in pw and "방금 너를 구했다." in pw)
check("⑰ 기록되지 않은 장비·일련 없는 층: 피처 as_dict·level 에 uid·scope·space 없음",
      all("uid" not in f.as_dict() for f in d17.features.values()) and "scope" not in d17.level_snapshot()
      and not any("space" in f for f in d17.level_snapshot()["features"]))
with open(os.path.join(HERE, "brains.py"), encoding="utf-8") as f:
    BR = f.read()
check("⑰ 옛 칸 person_note 를 읽는 곳이 없다(두뇌 — 주석 밖에 그 낱말이 없다) · 관측 키 lore 등록(_WIRE_KEYS)",
      not re.search(r"""["']person_note["']""", BR) and "lore" in brains._WIRE_KEYS)
with open(os.path.join(HERE, "_run_gates.sh"), encoding="utf-8") as f:
    check("⑰ _run_gates.sh 에 verify_lorebook 등록", "verify_lorebook" in f.read())

print("=" * 44)
print("ALL PASS — verify_lorebook (p0.5.11 개인 로어북: 받는 조건 · 함정 · 칸 병합 · 같은 이름 둘 · 쓸 수 있는 것 ⊆ 뜨는 것 · 도감 칸 · 번호 안정 · 장비 따라가기 · "
      "쓸어내기 · 6줄 상한·순서 · 길이 · 100개 · 저장 판 5 · 정보 보호 · 러너 로그 · 옛 판 그대로, 실 LLM 0콜)"
      if not C.failed else "FAILED %d" % C.failed)
sys.exit(1 if C.failed else 0)

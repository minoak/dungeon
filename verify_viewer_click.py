# -*- coding: utf-8 -*-
"""p0.5.12 관전 클릭 보기 — 게임 화면(game/src)의 클릭 창이 쓰는 재료·규칙(설계 .orch/drafts/viewer_click_design.md v1 §6.1 · DECISIONS 2026-10-14 99·100행). LLM 0콜.
러너 판 하나(인물 기록·파티 결성 판 · 각본 두뇌: 더미 걸음 + 세 판단에 한 번 보이는 것에 lore_note · 멈춤 → 이어가기)를 돌려 스트림과 본 스트림 틱마다의
엔진 장부를 함께 얻고, TS 쪽은 node --experimental-strip-types 로 game/src/stream/parse.ts(StreamParser)·game/src/inspect/model.ts 를 직접 불러 맞대 본다.
  ① 접기 = 엔진 장부 — 파이썬 기준 접기(lorebook.fold_stream)가 매 본 스트림 틱의 bot['people']·bot['lore']·도감 note 와 같다(쓰기·바램·쓸어냄·합류·이어가기)
  ② TS 접기 = 파이썬 접기 — 모든 프레임·사람마다 장부·종 앎
  ③ 대상 → 열쇠 — 판의 모든 lore_note(쓸 때의 화면 번호)를 TS keysFor 가 같은 열쇠로(화면과 같은 그 틱 프레임) · 기록한 바닥 장비를 주운 뒤 프레임도 gear:<uid>(p0512b) ·
     level.zones·doors = 엔진 스캐너 구역·생성기 방·마을 구역·문(모든 칸) · 함정 자리 = 엔진 d.traps 자리 · 층 일련이 다르면 같은 번호라도 다른 열쇠 · 이름 같은 집 둘은 다른 place:
  ④ 겹침 순서 — 사람 > 몬스터(산 것 → 시체) > 물건·설비 > 함정 > 문·계단 > 장소 · 같은 무리는 실제 그리기 깊이(같은 줄의 NPC 는 모험가 뒤 — p0512b) → 아래 줄 → 번호 · 입력 순서와 무관
  ⑤ 부르는 이름 = 관측 이름 — 관측 동봉 판의 obs(사람 호칭 identity.call · 몬스터 kind · 묘 이름 grave_label)와 TS 이름이 같다(사람마다·틱마다)
  ⑥ 시스템 설명 — run_meta.item_info = entities.item_desc(중립)·item_rule · TS 물건 설명 고르기 = entities.item_def · TS 겉모습 잇기 = sheetkit.looks_line
  ⑦ 되감기 — 앞부분만 먹인 색인(라이브 성장 꼴)의 k 프레임 = 끝까지 먹인 색인의 k 프레임(이어가기 뒤도) · 이어 먹여도 같다
  ⑧ 정보 보호 — 새 칸이 관측·프롬프트에 없다 · 끈 판 스트림에 새 칸 0 · 공개 투영 IG.public 이 새 관전 칸을 걷고 이름이 겹치는 공개 칸은 남긴다(p0512b)
  ⑨ 창 모형 — 기록 없는 사람 '모름' · 비교 = 파티 순서 전원·시점 사람 표시 · 자기 자신 '너' · 옛 판 = 시스템 칸만
  ⑩ 종 앎 — known_ops 접기 = 매 본 스트림 틱 bot['known'] · 본 스트림 밖에서 안 종(옆 세계 획득을 지식 집합에 직접 넣어 흉내)도 다음 본 스트림 틱에
화면(그림 맞음·점선 고리·DOM)은 관리자 브라우저 확인 몫이다(설계 §6.2). (기존 verify 는 별도 실행.)
"""
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = tempfile.mkdtemp(prefix="wl_viewclick_")
STATE = os.path.join(ROOT, "state")
os.makedirs(STATE, exist_ok=True)
BASE_ENV = dict(DUNGEON_GM="0", DUNGEON_STEP_DELAY="0", DUNGEON_TURNS="170", DUNGEON_W="40", DUNGEON_H="16",
                DUNGEON_DEPTHS="2", DUNGEON_SEED="7", DUNGEON_MONSTERS="3", DUNGEON_TRAPS="4", DUNGEON_LURKERS="0",
                DUNGEON_BESTIARY_FILE="", DUNGEON_PARTY_FILE=os.path.join(HERE, "party.json"), DUNGEON_STATE_DIR=STATE,
                DUNGEON_TOWN="1", DUNGEON_BRAIN_BACKEND="claude_cli", DUNGEON_BOSS="0", DUNGEON_RUNS_DIR=os.path.join(ROOT, "runs"),
                DUNGEON_ACTION_MODE="compose", DUNGEON_PARTYFORM="1", DUNGEON_STRANGERS="1", DUNGEON_STREAM_OBS="1", DUNGEON_NPC_BRAIN="0")
os.environ.update(BASE_ENV)
for k in ("DUNGEON_QUESTS", "DUNGEON_TOWN_APART", "DUNGEON_SOLO", "DUNGEON_START", "DUNGEON_MENU", "DUNGEON_RESUME", "DUNGEON_LOOP"):
    os.environ.pop(k, None)

import brains                                        # noqa: E402
brains._call_claude = lambda prompt, model="haiku": ""   # LLM 무력화(아래 각본이 다시 건다)
import bestiary                                      # noqa: E402
import dungeon_gm as G                               # noqa: E402
import identity as ID                                # noqa: E402
import lorebook as LB                                # noqa: E402
import run_control                                   # noqa: E402
import sheetkit                                      # noqa: E402
import show_runner                                   # noqa: E402
import snapshot                                      # noqa: E402
import stream                                        # noqa: E402
import time as _time                                 # noqa: E402
_time.sleep = lambda s: None
show_runner.STEP_DELAY = 0
GAME_SRC = os.path.join(HERE, "game", "src")


class C:
    failed = 0


def check(name, ok, detail=""):
    print("  %s %s%s" % ("OK  " if ok else "FAIL", name, (" — " + str(detail)[:500]) if (detail and not ok) else ""))
    if not ok:
        C.failed += 1


def canon(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True)


# ── 각본 판 ────────────────────────────────────────────────────────────────
# 두뇌: 더미 규칙 두뇌가 걷고(파티는 미리 셋이 맺어 둔다 — 입구 3명 규칙), 사람마다 두 판단에 한 번 지금 보이는 것 하나에 lore_note 를 쓴다
#   (그 사람이 아직 안 적은 분류부터, 드문 것 먼저 — NPC·건물(개별·종류)·함정·마을 구역·장비·몬스터(개별·종류)·문·계단·사람(별명)·방 — 다 적었으면 차례로 고쳐 쓴다).
#   기록 쓰기는 실제 두뇌 길(claude_brain → lorebook.parse → think_all 의 apply)을 탄다 — 응답 JSON 만 각본이 준다(_call_claude 스텁).
# 엔진 장부 쪽 장치(실제 러너 길을 타게): t4 모든 몸에 사라진 층 기록 obj:999:m1(같은 틱 set 으로 싣는다 → 러너가 그 틱 끝에 쓸어낸다 = sweep) ·
#   1 이 아는 종을 처음 볼 때 kind:<종>(set) 을 심고 그 종에 종류 기록 → 도감 note → 러너 합류(merge) · 한 몸 상한을 10 으로(fade) ·
#   t6 2 의 지식 집합에 본 스트림이 모르는 종(옆 세계 획득 흉내) · t140 머리에서 곱게 멈춤 → 이어가기(던전에서 — 도감 note 가 있는 채로) ·
#   던전 함정은 드러내 둔다(장면 고정).
LB.KEEP_MAX = 10
K_SWEEP, K_SIDE, K_STOP = 4, 6, 140
SIDE_KEY = "monster:그림자거미"
REPLY = threading.local()
REG, DUNG, CAP, NOTES, PENDING, CUR_OPS = {}, {}, {}, {}, {"turn": None}, {"v": None}
DONE, NTH, MERGE, PROMPTS = {}, {}, {"done": None}, []
_real_cb, _think, _new_parties = brains.claude_brain, brains.think_all, G.new_parties


def stub_call(prompt, model="haiku"):
    PROMPTS.append(prompt)
    return getattr(REPLY, "v", None) or '{"type": "wait"}'


def cat_of(a, obs):
    i = str(a["id"])
    if a.get("inv"):
        return "inv_gear" if i in ("i2", "i3") else None
    if a.get("person"):
        return "npc" if a["person"].startswith("npc:") else "bot"
    if a.get("quest"):
        return "quest"
    if i == "zone":
        return "region"
    if i == "exit":
        return "exit"
    for pat, cat in ((r"[rc]\d+", "room"), (r"m\d+", "mob"), (r"t\d+", "trap"), (r"d\d+", "door")):
        if re.fullmatch(pat, i):
            return cat
    if re.fullmatch(r"f\d+", i):
        ft = next((f for f in (obs.get("sights") or {}).get("features") or [] if f.get("id") == i), {})
        return {"building": "building", "weapon": "gear", "armor": "gear", "grave": "grave"}.get(ft.get("type"), "feat")
    return None


def plan_note(obs, char, bot):
    """이 판단에 쓸 lore_note(없으면 None — 걷는다)."""
    if obs.get("people") is None:
        return None
    anc = LB.anchors(obs)
    turn = obs.get("turn")
    if char == "1" and MERGE["done"] is None and CUR_OPS["v"] is not None:   # 합류 장면: 아는 종을 처음 보면 kind:<종> 을 심고 그 종에 종류 기록
        known_mob = next((a for a in anc if re.fullmatch(r"m\d+", str(a["id"])) and a.get("name") not in (None, LB.UNKNOWN_BEAST)), None)
        if known_mob:
            k = "kind:" + known_mob["name"]
            e = {"text": "심은 종류 기록", "turn": turn, "depth": 1, "src": "self", "label": known_mob["name"]}
            bot["lore"][k] = dict(e)
            CUR_OPS["v"].setdefault(char, []).append({"op": "set", "key": k, "entry": dict(e)})
            MERGE["done"] = known_mob["name"]
            return {"kind": known_mob["name"], "text": "도감으로 합류할 기록"}
    n = NTH[char] = NTH.get(char, 0) + 1
    if n % 2 != 1:
        return None
    opts = []
    for a in anc:
        cat = cat_of(a, obs)
        if not cat:
            continue
        tg = a["name"] if a["id"] == "zone" else a["id"]
        if cat == "bot":
            opts.append((cat, {"target": tg, "name": "별명%s" % a["id"][1:], "text": "%s가 본 %s t%s" % (char, a["id"], turn)}))
        else:
            opts.append((cat, {"target": tg, "text": "%s의 기록 %s t%s" % (char, a["id"], turn)}))
        if a.get("kind") and a.get("name") and not a.get("inv"):
            kc = cat + ("_kind_unknown" if a["name"] == LB.UNKNOWN_BEAST else "_kind")
            opts.append((kc, {"kind": a["name"], "text": "%s의 종류 기록 %s t%s" % (char, a["name"], turn)}))
    done = DONE.setdefault(char, set())
    first = {"1": "npc", "2": "building", "3": "region"}.get(char)   # 마을의 첫 판단은 사람마다 다른 분류(마을에선 판단이 드물다)
    for cat, note in sorted(opts, key=lambda o: -1 if o[0] == first else PRIO.index(o[0]) if o[0] in PRIO else len(PRIO)):   # 드문 분류부터
        if cat not in done:
            done.add(cat)
            return note
    return opts[(n // 2) % len(opts)][1] if opts else None


PRIO = ["npc", "region", "exit", "building", "trap", "building_kind", "trap_kind", "inv_gear", "gear", "gear_kind", "mob", "mob_kind_unknown", "mob_kind",
        "door", "door_kind", "exit_kind", "bot", "grave", "grave_kind", "quest", "feat", "feat_kind", "room"]


def scripted_brain(obs, char="?", bot=None, roster=None, solo=False):
    note = plan_note(obs, char, bot) if bot is not None else None
    if note is None:
        fb = dict(G.dummy_brain(obs, char))
        if obs.get("action_schema") == G.CA.SCHEMA:
            fb = G.CA.fallback(fb, obs)
        fb.update(say="", reason="[각본] 걷는다", src="fallback")
        return fb
    REPLY.v = json.dumps({"type": "wait", "reason": "기록", "lore_note": note}, ensure_ascii=False)
    try:
        return _real_cb(obs, char, bot, roster, solo)
    finally:
        REPLY.v = None


def think(d_, bots_, inbox=None, on_error=None, lore_ops=None, **kw):
    for b_ in bots_:
        REG[b_["char"]] = b_
    if getattr(d_, "scope", None) is not None:
        DUNG[d_.scope] = d_
    t = d_.turn
    if lore_ops is not None and t in (K_SWEEP, K_STOP - 1):   # t34 것은 그 틱 끝에 쓸어내 다음 틱이 없는 자리(멈춤 줄 stopped.lore_ops)로 나간다
        k_ = "obj:%d:m1" % (999 if t == K_SWEEP else 998)
        for b_ in bots_:
            e = {"text": "사라진 층의 기록", "turn": t, "depth": 1, "src": "self", "label": "고블린"}
            b_["lore"][k_] = dict(e)
            lore_ops.setdefault(b_["char"], []).append({"op": "set", "key": k_, "entry": dict(e)})
    if t == K_SIDE and "2" in REG:
        REG["2"]["known"].add(SIDE_KEY)               # 옆 세계에서 안 종(흉내) — 본 스트림 틱 내용(aware_of·사건)으로는 소급되지 않는다
    if d_.depth >= 1:
        for tr in d_.traps:                           # 장면 고정: 던전 함정을 드러내 둔다(수색 운에 기대지 않고 함정 기록 t<n> 을 덮는다)
            tr.hidden = False
    CUR_OPS["v"] = lore_ops
    try:
        out = _think(d_, bots_, inbox, on_error=on_error, lore_ops=lore_ops, **kw)
    finally:
        CUR_OPS["v"] = None
    if t == K_STOP - 1 and STOP["on"]:
        run_control.request_stop(show_runner.STATE, pages=False)   # 다음 틱 머리에서 곱게 멈춘다(수첩 없이)
    return out


STOP = {"on": True}
_emit = stream.StreamWriter.emit
_consume = bestiary.Issuer.consume


def emit_hook(self, kind, **fields):
    _emit(self, kind, **fields)
    if kind == "tick" and "world" not in fields and os.path.basename(self.f.name) == "stream.jsonl" and CAP_ON["on"]:
        CAP[fields["turn"]] = {c: {"lore": LB.dump(b), "known": sorted(b.get("known") or [])} for c, b in REG.items() if b.get("people") is not None}
        PENDING["turn"] = fields["turn"]


def consume_hook(self, kind, rec):
    out = _consume(self, kind, rec)
    if kind == "tick" and PENDING["turn"] is not None and rec.get("turn") == PENDING["turn"]:
        NOTES[rec["turn"]] = {c: {k: r["note"]["text"] for k, r in (b.get("book") or {}).items()
                                  if isinstance(r, dict) and isinstance(r.get("note"), dict) and r["note"].get("text")}
                              for c, b in REG.items() if b.get("people") is not None}
        PENDING["turn"] = None
    return out


CAP_ON = {"on": True}


def preset():
    p = _new_parties()
    G.party_join(p, ["1", "2", "3"])                  # 셋이 미리 맺은 파티(입구 3명 규칙) — 함께 내려간다
    return p


def run_main(state, resume=False):
    show_runner.STATE = state
    show_runner.RESUME_PATH = snapshot.paths(state)[0] if resume else ""
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            show_runner.main()
        except SystemExit:
            pass
    show_runner.RESUME_PATH = ""
    with open(os.path.join(state, "stream.jsonl"), encoding="utf-8") as f:
        return f.read()


brains._call_claude, brains.claude_brain, brains.think_all, G.new_parties = stub_call, scripted_brain, think, preset
stream.StreamWriter.emit, bestiary.Issuer.consume = emit_hook, consume_hook
try:
    run_main(STATE)                                   # t1 ~ t34 → 곱게 멈춤(stopped)
    STOP["on"] = False
    TEXT = run_main(STATE, resume=True)               # 이어가기(resume) → 판 끝
    OFF = os.path.join(ROOT, "off")
    os.makedirs(OFF, exist_ok=True)
    CAP_ON["on"] = False
    show_runner.STRANGERS_ON, mt = False, show_runner.MAX_TURNS
    show_runner.MAX_TURNS = 30
    try:
        OFF_TEXT = run_main(OFF)                      # 끈 판(인물 기록 없음) — 옛 판 꼴
    finally:
        show_runner.STRANGERS_ON, show_runner.MAX_TURNS = True, mt
finally:
    brains._call_claude, brains.claude_brain, brains.think_all, G.new_parties = (lambda prompt, model="haiku": ""), _real_cb, _think, _new_parties
    stream.StreamWriter.emit, bestiary.Issuer.consume = _emit, _consume

KEEP = os.environ.get("WL_VIEWCLICK_KEEP")             # p0512c 스트림 남기기 — game/verify/lore_click_fixture.py 가 브라우저 검사(inspect.mjs) 픽스처로 다듬는다
if KEEP:
    with io.open(KEEP, "w", encoding="utf-8", newline="\n") as f:
        f.write(TEXT)
ROWS = [json.loads(ln) for ln in TEXT.splitlines() if ln.strip()]
OFF_ROWS =[json.loads(ln) for ln in OFF_TEXT.splitlines() if ln.strip()]
META = ROWS[0]
TICKS = [r for r in ROWS if r["kind"] == "tick"]
FOLD = LB.fold_stream(ROWS)
FR_TICK = {fr["turn"]: i for i, fr in enumerate(FOLD) if fr["kind"] == "tick"}
CHARS = [p["char"] for p in META["party"]]
OPS = [(r["turn"], c, o) for r in ROWS for c, os_ in (r.get("lore_ops") or {}).items() for o in os_]
NOTES_ALL = [(r["turn"], c, dd["lore_note"]) for r in TICKS for c, dd in sorted((r.get("decisions") or {}).items()) if dd.get("lore_note")]
print("── 판: 틱 %d · 층 줄 %s · 기록 쓰기 %d · 도감 note 쓰기 %s · 원장 변화 %s · 멈춤 %d · 이어가기 %d · 끝 %s" % (
    len(TICKS), [(r["turn"], r["depth"]) for r in ROWS if r["kind"] == "level"], len(NOTES_ALL),
    [(t, c) for t, c, o in OPS if o["key"].startswith("monster:")],
    {op: sum(o["op"] == op for _, _, o in OPS) for op in ("set", "fade", "sweep", "merge")},
    sum(r["kind"] == "stopped" for r in ROWS), sum(r["kind"] == "resume" for r in ROWS),
    next((r.get("outcome") for r in ROWS if r["kind"] == "end"), "-")))
check("준비: 판이 멈춤 → 이어가기를 지나 끝까지 돌았고 쓰기·바램·쓸어냄·합류가 다 있다 · 던전 층(scope 둘 이상)에 내려갔다",
      any(r["kind"] == "stopped" for r in ROWS) and any(r["kind"] == "resume" for r in ROWS) and len(TICKS) >= 60
      and all(any(o["op"] == op for _, _, o in OPS) for op in ("set", "fade", "sweep", "merge"))
      and len({r.get("scope") for r in ROWS if r["kind"] == "level"}) >= 2 and MERGE["done"]
      and any(k.startswith("monster:") for t, c, o in OPS if t < K_STOP for k in [o["key"]]),   # 이어가기가 도감 note 를 지나간다
      ([r["kind"] for r in ROWS if r["kind"] not in ("tick",)][:20], MERGE["done"]))


def book_keys(k):
    return k.startswith(("monster:", "trap:", "feature:"))


# ── ① 접기 = 엔진 장부 ─────────────────────────────────────────────────────
print("── ① 파이썬 기준 접기(lorebook.fold_stream) = 엔진 장부(본 스트림 틱마다)")
bad1, badn, badk = [], [], []
PRE_TAIL = {}                                         # 다음 틱이 없는 자리(stopped·end)의 남은 변화는 그 틱 '끝'의 일 — 틱 기록 순간의 엔진과는 그 줄 앞까지 접은 것으로 맞댄다
for k_, r_ in enumerate(ROWS):
    if r_["kind"] in ("stopped", "end") and r_.get("lore_ops"):
        PRE_TAIL[LB.fold_stream(ROWS[:k_])[-1]["turn"]] = LB.fold_stream(ROWS[:k_])[-1]
for t, cap in sorted(CAP.items()):
    fr = PRE_TAIL.get(t) or FOLD[FR_TICK[t]]
    for c, st in cap.items():
        mine = {k: e for k, e in fr["lore"].get(c, {}).items() if not book_keys(k)}
        if canon(mine) != canon(st["lore"]):
            bad1.append((t, c, sorted(set(mine) ^ set(st["lore"]))[:4]))
        if sorted(fr["known"].get(c, set())) != st["known"]:
            badk.append((t, c))
    for c, notes in NOTES.get(t, {}).items():
        mine = {k: e.get("text") for k, e in fr["lore"].get(c, {}).items() if book_keys(k)}
        if mine != notes:
            badn.append((t, c, mine, notes))
check("① 사람·로어북 장부(LB.dump) = 접기 — 매 본 스트림 틱 %d번 · 사람 %d" % (len(CAP), len(CHARS)), CAP and not bad1, bad1[:3])
check("① 도감 note(발급기가 그 틱에 접은 뒤) = 접기의 monster: 칸", NOTES and not badn, badn[:2])
fold_end = FOLD[-1]["lore"]
stop_row = next(r for r in ROWS if r["kind"] == "stopped")
check("① 멈춤 줄(stopped)이 남은 변화(t%d 끝에 쓸어낸 obj:998)를 싣고, 접기는 그것을 멈추기 직전 프레임에 적용한다 — 그 틱의 기록 순간엔 있었다" % (K_STOP - 1),
      sorted((o["op"], o["key"]) for v in (stop_row.get("lore_ops") or {}).values() for o in v) == [("sweep", "obj:998:m1")] * len(CHARS)
      and all("obj:998:m1" not in b for b in FOLD[FR_TICK[K_STOP - 1]]["lore"].values())
      and all("obj:998:m1" in b for b in (PRE_TAIL.get(K_STOP - 1) or {"lore": {}})["lore"].values()) and len(PRE_TAIL.get(K_STOP - 1, {}).get("lore", {})) == len(CHARS),
      stop_row.get("lore_ops"))
check("① 쓸어낸 obj:999 · 합류한 kind:<종> 은 접기에서도 지워졌다 · 합류된 종은 monster: note 로 남았다",
      all("obj:999:m1" not in b for b in fold_end.values()) and "kind:" + str(MERGE["done"]) not in fold_end.get("1", {})
      and "monster:" + str(MERGE["done"]) in fold_end.get("1", {}), (MERGE["done"], sorted(fold_end.get("1", {}))))
res_row = next(r for r in ROWS if r["kind"] == "resume")
res_i = next(i for i, r in enumerate(ROWS) if r["kind"] == "resume")
before = LB.fold_stream(ROWS[:res_i])[-1]["lore"]
check("① 이어가기: resume.lore(그 순간의 모든 몸) = 멈추기 전까지 접은 장부(도감 note 빼고) — 검산",
      all(canon({k: e for k, e in before.get(c, {}).items() if not book_keys(k)}) == canon(res_row["lore"].get(c, {})) for c in CHARS),
      [c for c in CHARS if canon({k: e for k, e in before.get(c, {}).items() if not book_keys(k)}) != canon(res_row["lore"].get(c, {}))])
# 꼬리를 잃은 스트림(끊김 뒤 이어가기의 꼴 — 스냅샷 때 러너 버퍼에 있던 변화는 스트림에 못 나간다): 멈춤 줄의 남은 변화를 걷어 낸 변형
LOST = [{k: v for k, v in r.items() if k != "lore_ops"} if r["kind"] == "stopped" else r for r in ROWS]
LOST_PATH = os.path.join(ROOT, "lost.jsonl")
with io.open(LOST_PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write("".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n" for r in LOST))
FOLD_LOST = LB.fold_stream(LOST)
RES_F = FR_TICK[min(t for t in FR_TICK if t >= K_STOP)]
check("① 이어가기 갈아 끼우기: 꼬리를 잃은 스트림도 resume 프레임부터는 원래 접기와 같다(잃은 쪽은 멈추기 직전까지만 다르다)",
      canon(FOLD_LOST[RES_F - 1]["lore"]) != canon(FOLD[RES_F - 1]["lore"])
      and all(canon(FOLD_LOST[i]["lore"]) == canon(FOLD[i]["lore"]) for i in range(RES_F, len(FOLD))))

# ── TS 쪽(node) ─────────────────────────────────────────────────────────────
NODE = os.environ.get("WL_NODE") or shutil.which("node")
check("준비: node 가 있다(WL_NODE 로 바꿀 수 있다)", bool(NODE))
HOOK = r"""
export async function resolve(spec, ctx, next) {
  if ((spec.startsWith('./') || spec.startsWith('../')) && !/\.[a-z]+$/.test(spec)) return next(spec + '.ts', ctx);
  return next(spec, ctx);
}"""
HARNESS = r"""
import { register } from 'node:module';
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
register('data:text/javascript,' + encodeURIComponent(%(hook)s));
const job = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const src = job.src;
const { StreamParser } = await import(pathToFileURL(src + '/stream/parse.ts').href);
const M = await import(pathToFileURL(src + '/inspect/model.ts').href);
const load = text => { const p = new StreamParser(); p.feed(text); return p; };
const text = readFileSync(job.stream, 'utf8');
const run = load(text).run;
const ix = M.buildIndex(run);
const chars = run.party.map(p => p.char);
const out = {};
const tgt = (at, label) => {
  if (/^b\d+$/.test(at)) return { t: 'bot', char: at.slice(1) };
  if (/^m\d+$/.test(at)) return { t: 'mob', id: +at.slice(1) };
  if (/^f\d+$/.test(at)) return { t: 'feat', id: +at.slice(1) };
  if (/^t\d+$/.test(at)) return { t: 'trap', idx: +at.slice(1) };
  if (/^d\d+$/.test(at)) return { t: 'door', id: at };
  if (/^[rc]\d+$/.test(at)) return { t: 'zone', id: at };
  if (at === 'exit') return { t: 'exit' };
  if (at === 'zone') return { t: 'region', name: label };
  return null;
};
out.frames = run.frames.length;
const foldOf = (r2, ix2) => r2.frames.map((f, i) => ({ kind: f.kind, turn: f.turn,
  lore: Object.fromEntries(chars.map(c => [c, M.ledgerAt(ix2, c, i)])), known: Object.fromEntries(chars.map(c => [c, M.knownAt(ix2, c, i)])) }));
out.fold = foldOf(run, ix);
const lost = load(readFileSync(job.lost, 'utf8')).run;
out.foldLost = foldOf(lost, M.buildIndex(lost));
out.keys = job.keys.map(q => { const t = tgt(q.at, q.label);   // 화면과 같은 호출 — 그 틱 프레임(대상이 그 틱에 사라졌으면 모형이 같은 층 앞 프레임을 거슬러 찾는다)
  return t ? M.keysFor(ix, q.viewer, t, run.frames[q.i], q.i) : null; });
// p0512b 줍기 장면(Codex p0512r): 기록한 바닥 장비가 뒤 프레임에서 사라져도(주웠다) 그 프레임의 열쇠는 gear:<uid> 그대로 — 판에 그 장면이 없으면 사라진 프레임을 꾸며 본다
out.pickup = job.pickup.map(q => {
  const id = +q.at.slice(1), fr = run.frames;
  let j = q.i + 1;
  while (j < fr.length && fr[j].levelIdx === fr[q.i].levelIdx && fr[j].features.some(x => x.id === id)) j++;
  const real = j < fr.length && fr[j].levelIdx === fr[q.i].levelIdx;
  const gone = real ? fr[j] : { ...fr[q.i], idx: q.i + 1, features: fr[q.i].features.filter(x => x.id !== id) };
  return [real, M.present(gone, { t: 'feat', id }), M.keysFor(ix, q.viewer, { t: 'feat', id }, gone, gone.idx).one];
});
out.names = job.names.map(q => ({
  mobs: q.mobs.map(([id]) => { const m = run.frames[q.prev].monsters.find(x => x.id === id); return m ? M.monsterName(ix, q.viewer, m.kind, q.i) : null; }),
  bots: q.bots.map(o => [M.callWith(q.people, q.viewer, o, run.names[o]), M.callBot(ix, q.viewer, o, q.prev)]),
  graves: q.graves.map(([id, own]) => { const ft = run.frames[q.prev].features.find(x => x.id === id);
    return ft ? [M.graveWith(q.people, q.viewer, ft.of, own, ft.name), M.featName(ix, q.viewer, ft, q.prev)] : null; }),
}));
out.pure = job.pure.map(q => q.grave ? M.graveWith(q.people, q.viewer, q.owner, q.own, q.fname) : M.callWith(q.people, q.viewer, q.target, q.real));
out.order = job.order.map(ps => M.orderPicks(ps).map(p => M.targetId(p.target)));
out.prefix = job.prefix.map(([k, cut]) => {
  const p = load(text.slice(0, cut)), a = M.buildIndex(p.run);
  const same = ix2 => chars.every(c => JSON.stringify(M.ledgerAt(ix2, c, k)) === JSON.stringify(M.ledgerAt(ix, c, k))
    && JSON.stringify(M.knownAt(ix2, c, k)) === JSON.stringify(M.knownAt(ix, c, k)));
  const c0 = M.loreIndex(p.run), r = [p.run.frames.length, same(a) && same(c0)];
  p.feed(text);                                   // 라이브 성장 — 앞부분 그대로 이어 먹인다
  const b = M.loreIndex(p.run);
  r.push(p.run.frames.length === run.frames.length, same(b), b !== c0 && b.sig !== c0.sig);
  return r;
});
const levels = []; let li = -1;
run.frames.forEach((f, i) => { if (f.levelIdx !== li) { li = f.levelIdx; levels.push(i); } });
out.cells = levels.map(i => { const L = run.frames[i].level, cells = [];
  for (let y = 0; y < L.h; y++) for (let x = 0; x < L.w; x++) if (L.grid[y][x] !== '#')
    cells.push([x, y, M.cellRun(L.zones, x, y), M.cellRun(L.zones?.town, x, y), L.grid[y][x] === '+' ? M.doorAt(L, x, y) : null]);
  const houses = L.features.filter(f => f.space).map(f => [f.id, f.name, M.keysFor(ix, chars[0], { t: 'feat', id: f.id }, run.frames[i], i)]);
  const traps = L.traps.map((t, n) => M.keysFor(ix, chars[0], { t: 'trap', idx: n }, run.frames[i], i));
  const other = { ...run.frames[i], level: { ...L, scope: (L.scope || 0) + 1000 } };
  const scoped = L.monsters.length ? [M.keysFor(ix, chars[0], { t: 'mob', id: L.monsters[0].id }, run.frames[i], i).one,
                                       M.keysFor(ix, chars[0], { t: 'mob', id: L.monsters[0].id }, other, i).one] : null;
  return { i, scope: L.scope, depth: L.depth, cells, houses, traps, scoped }; });
out.looks = job.looks.map(([i, c]) => { const b = run.frames[i].bots.find(x => x.char === c); return M.looksLine(run.party.find(p => p.char === c), b); });
out.items = job.items.map(([t, n]) => M.itemInfo(run, t, n));
const win = (ix2, q) => { const m = M.windowModel(ix2, q.target, ix2.run.frames[q.i], q.i, q.viewer, q.compare);
  return { call: m.call, real: m.real, present: m.present, facts: m.facts.length, mine: m.mine && { state: m.mine.state, texts: m.mine.lines.map(l => l.text) },
           rows: m.rows && m.rows.map(r => [r.char, r.me, r.call, r.rec.state]) }; };
out.window = job.window.map(q => win(ix, q));
const off = load(readFileSync(job.off, 'utf8')).run, oix = M.buildIndex(off);
out.offWindow = job.offWindow.map(q => win(oix, q));
out.offPeople = oix.people;
out.ledgerRows = chars.map(c => M.ledgerRows(ix, c, run.frames.length - 1, run.frames[run.frames.length - 1].level.scope).map(r => [r.group, r.key]));
console.log(JSON.stringify(out));
"""


def frame_of_turn(t):
    return FR_TICK[t]


JOB = {"src": GAME_SRC.replace("\\", "/"), "stream": os.path.join(STATE, "stream.jsonl"), "off": os.path.join(ROOT, "off", "stream.jsonl"), "lost": LOST_PATH,
       "keys": [], "names": [], "pure": [], "order": [], "prefix": [], "looks": [], "items": [], "window": [], "offWindow": [], "pickup": []}
KEYQ = []                                          # (turn, char, note)
for t, c, nt in NOTES_ALL:
    if nt.get("at") and nt.get("key") and not re.fullmatch(r"[iq]\d+", str(nt["at"])):
        i = frame_of_turn(t)
        JOB["keys"].append({"i": i, "prev": i - 1, "viewer": c, "at": nt["at"], "label": nt.get("label")})
        KEYQ.append((t, c, nt))
        if nt["key"].startswith("gear:") and re.fullmatch(r"f\d+", str(nt["at"])):
            JOB["pickup"].append({"i": i, "viewer": c, "at": nt["at"], "key": nt["key"]})
NAMEQ = []
for r in TICKS:
    i = frame_of_turn(r["turn"])
    for c, dd in sorted((r.get("decisions") or {}).items()):
        ob = dd.get("obs")
        if not ob or ob.get("people") is None:
            continue
        s = ob.get("sights") or {}
        q = {"i": i, "prev": i - 1, "viewer": c, "people": ob["people"],
             "mobs": [[int(m["id"][1:]), m["kind"]] for m in s.get("monsters") or []],
             "bots": [str(b["char"]) for b in s.get("bots") or []],
             "graves": [[int(f["id"][1:]), (next((p for p in META["party"] if p["char"] == c), {}).get("name") or ""), f["name"]]
                        for f in s.get("features") or [] if f.get("type") == "grave"]}
        JOB["names"].append({k: (v if k != "graves" else [g[:2] for g in v]) for k, v in q.items()})
        NAMEQ.append(q)
# ⑤ 순수 규칙 — 같은 장부로 identity.call · grave_label 과 맞댄다(지금 판에 없는 경우까지: 이름 적음·안 적음·'낯선 사람'이라 적음·내 묘)
PEO = [{}, {"b2": {"name": "카야", "text": "x"}}, {"b2": {"text": "이름 없이 글만"}}, {"b2": {"name": ID.STRANGER}}, {"npc:대장장이": {"name": "망치"}}]
PURE_REF = []
for pp in PEO:
    for viewer, target in (("1", "2"), ("1", "1"), ("1", "3")):
        JOB["pure"].append({"people": pp, "viewer": viewer, "target": target, "real": "실명%s" % target})
        PURE_REF.append(ID.call({"people": pp, "char": viewer}, "b" + target))
        JOB["pure"].append({"grave": True, "people": pp, "viewer": viewer, "owner": target, "own": "두란", "fname": "실명%s의 묘" % target})
        PURE_REF.append(ID.grave_label({"people": pp, "char": viewer, "name": "두란"}, target, "실명%s의 묘" % target))
JOB["pure"].append({"people": None, "viewer": "1", "target": "2", "real": "카야"})      # 옛 판 — 실명
PURE_REF.append(ID.call({"char": "1"}, "b2", {"2": "카야"}))
JOB["pure"].append({"grave": True, "people": None, "viewer": "1", "owner": "2", "own": "두란", "fname": "카야의 묘"})
PURE_REF.append(ID.grave_label({"char": "1"}, "2", "카야의 묘"))
# ④ 겹침 순서
DS_SRC = io.open(os.path.join(GAME_SRC, "scene", "DungeonScene.ts"), encoding="utf-8").read()
STAND = float(re.search(r"stand: (\d+)", DS_SRC).group(1))
FEAT_D = float(re.search(r"feature: (\d+)", DS_SRC).group(1))
P = lambda t, g, d, y, n, dead=False: {"target": t, "group": g, "depth": d, "y": y, "n": n, **({"dead": True} if dead else {})}   # noqa: E731
# 깊이 = 씬의 실제 값(DEPTH.stand + y·0.01 · NPC·몹은 −0.005 · 바닥 물건은 DEPTH.feature) — 같은 줄(y 4)의 NPC f1 이 모험가 b3 보다 뒤에 그려진다.
# 시체 m2 는 일부러 산 m5 보다 깊이를 높게 둔다(씬에선 늘 DEPTH.corpse 로 낮다) — '산 것 먼저' 규칙이 깊이와 따로 서는지 본다
CELL = [P({"t": "zone", "id": "r3"}, 5, 0, 4, 0), P({"t": "trap", "idx": 0}, 3, 12, 4, 0), P({"t": "feat", "id": 12}, 2, FEAT_D, 4, 12),
        P({"t": "mob", "id": 2}, 1, STAND + .06, 4, 2, dead=True), P({"t": "bot", "char": "2"}, 0, STAND + .04, 4, 2), P({"t": "door", "id": "d1"}, 4, FEAT_D, 4, 1),
        P({"t": "mob", "id": 5}, 1, STAND + .04 - .005, 4, 5), P({"t": "feat", "id": 3}, 0, STAND + .03 - .005, 3, 3), P({"t": "region", "name": "번화가"}, 5, 0, 4, 1),
        P({"t": "bot", "char": "1"}, 0, STAND + .05, 5, 1), P({"t": "exit"}, 4, FEAT_D, 4, 0), P({"t": "feat", "id": 7}, 2, FEAT_D, 5, 7),
        P({"t": "feat", "id": 1}, 0, STAND + .04 - .005, 4, 1), P({"t": "bot", "char": "3"}, 0, STAND + .04, 4, 3)]
ORDER_WANT = ["b1", "b2", "b3", "f1", "f3", "m5", "m2", "f7", "f12", "t0", "exit", "d1", "zone:r3", "region:번화가"]
JOB["order"] = [CELL, list(reversed(CELL)), CELL[5:] + CELL[:5]]
# ⑦ 되감기 — 앞부분 자르기: k 프레임 다음 프레임 줄의 머리(그 사이의 resume·멈춤 줄은 앞부분에 든다)
line_starts, frame_line, pos = [], [], 0
for ln in TEXT.splitlines(keepends=True):
    kd = json.loads(ln).get("kind") if ln.strip() else None
    if kd in ("level", "tick"):
        frame_line.append(pos)
    pos += len(ln)
NF = len(frame_line)
ks = sorted({NF // 4, NF // 2, FR_TICK[min(t for t in FR_TICK if t >= K_STOP)], FR_TICK[min(t for t in FR_TICK if t >= K_STOP)] - 1, NF - 2})
JOB["prefix"] = [[k, frame_line[k + 1]] for k in ks if k + 1 < NF]
# ⑥ 겉모습 · 물건 설명
LOOKQ = [(frame_of_turn(r["turn"]), b["char"], b) for r in TICKS[::15] for b in r["bots"]]
JOB["looks"] = [[i, c] for i, c, _ in LOOKQ]
ITEMQ = sorted({(f["type"], f["name"]) for r in ROWS if r["kind"] in ("level", "tick") for f in r["features"] if f["type"] in G.ENT.ITEM_TYPES}
               | {("potion", "없는 물약"), ("boon", "축복의 물약"), ("treasure", "숨은 보물")})
JOB["items"] = [list(x) for x in ITEMQ]
# ⑨ 창 모형 — 마지막 프레임: 기록 없는 장소('모름') · 기록 있는 사람(시트 씨앗·별명) · 자기 자신 · 비교
last_i = NF - 1
LAST_LV = [r for r in ROWS if r["kind"] == "level"][-1]
v0 = CHARS[0]
no_rec = next((z for z in (LAST_LV.get("zones") or {}).get("ids") or []
               if "obj:%s:%s" % (LAST_LV.get("scope"), z) not in FOLD[last_i]["lore"].get(v0, {})), None)
has_rec = next((o for o in CHARS if o != v0 and "b" + o in FOLD[last_i]["lore"].get(v0, {})), None)
WQ = [("none", {"i": last_i, "viewer": v0, "target": {"t": "zone", "id": no_rec}, "compare": False}),
      ("list", {"i": last_i, "viewer": v0, "target": {"t": "bot", "char": has_rec}, "compare": False}),
      ("self", {"i": last_i, "viewer": v0, "target": {"t": "bot", "char": v0}, "compare": False}),
      ("cmp", {"i": last_i, "viewer": CHARS[1], "target": {"t": "bot", "char": v0}, "compare": True})]
JOB["window"] = [q for _, q in WQ]
off_last = sum(r["kind"] in ("level", "tick") for r in OFF_ROWS) - 1
JOB["offWindow"] = [{"i": off_last, "viewer": "1", "target": {"t": "bot", "char": "2"}, "compare": False}]

TS = {}
if NODE:
    path, jpath = os.path.join(ROOT, "harness.mjs"), os.path.join(ROOT, "job.json")
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(HARNESS % {"hook": json.dumps(HOOK)})
    with io.open(jpath, "w", encoding="utf-8") as f:
        json.dump(JOB, f, ensure_ascii=False)
    run = subprocess.run([NODE, "--experimental-strip-types", "--no-warnings", path, jpath], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=300, cwd=ROOT)
    try:
        TS = json.loads(run.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        TS = {}
    check("준비: node 가 parse.ts·model.ts 를 직접 읽어 돈다(--experimental-strip-types · import type 만)", run.returncode == 0 and bool(TS),
          (run.stdout[-300:] + run.stderr[-900:]))

# ── ② TS 접기 = 파이썬 접기 ─────────────────────────────────────────────────
print("── ② TS 접기(model.buildIndex) = 파이썬 접기")
tsf = TS.get("fold") or []
bad2 = [(i, fr["turn"]) for i, fr in enumerate(FOLD)
        if i >= len(tsf) or tsf[i]["turn"] != fr["turn"] or canon(tsf[i]["lore"]) != canon({c: fr["lore"].get(c, {}) for c in CHARS})
        or tsf[i]["known"] != {c: sorted(fr["known"].get(c, set())) for c in CHARS}]
check("② 모든 프레임(%d)·사람마다 장부·종 앎이 같다(이어가기·멈춤 줄의 남은 변화 포함)" % len(FOLD), tsf and len(tsf) == len(FOLD) and not bad2, bad2[:5])
tsl = TS.get("foldLost") or []
check("② 꼬리를 잃은 스트림도 TS 접기 = 파이썬 접기(resume 갈아 끼우기가 두 쪽에서 같다)",
      len(tsl) == len(FOLD_LOST) and all(canon(a["lore"]) == canon({c: b["lore"].get(c, {}) for c in CHARS}) for a, b in zip(tsl, FOLD_LOST)),
      [i for i, (a, b) in enumerate(zip(tsl, FOLD_LOST)) if canon(a["lore"]) != canon({c: b["lore"].get(c, {}) for c in CHARS})][:5])

# ── ③ 대상 → 열쇠 ─────────────────────────────────────────────────────────
print("── ③ 대상 → 열쇠 · 칸 → 장소 번호")
tk = TS.get("keys") or []
bad3 = [(t, c, nt["at"], nt["key"], k) for (t, c, nt), k in zip(KEYQ, tk)
        if not k or (k.get("one") if nt.get("of") == "one" else k.get("kind")) != nt["key"]]
cats = sorted({nt["key"].split(":")[0] if not re.fullmatch(r"b\d+", nt["key"]) else "b" for _, _, nt in KEYQ}
              | {"obj:" + re.sub(r"\d+", "", nt["key"].split(":")[2]) for _, _, nt in KEYQ if nt["key"].startswith("obj:")})
check("③ 판의 모든 lore_note %d개(쓸 때의 화면 번호) → TS keysFor 가 러너가 채운 열쇠와 같다 · 덮은 꼴 %s" % (len(KEYQ), cats),
      len(tk) == len(KEYQ) and len(KEYQ) >= 20 and not bad3, bad3[:4])
need = {"b", "npc", "place", "zone", "kind", "obj:m", "obj:t", "obj:d", "obj:r", "obj:exit"}
check("③ 덮은 꼴: 사람·NPC·건물(place)·마을 구역·종류·몬스터·함정·문·방·계단", need <= set(cats),
      (sorted(need - set(cats)), [(t, c, nt["key"]) for t, c, nt in NOTES_ALL]))
pk = TS.get("pickup") or []
check("③ 기록한 바닥 장비가 뒤 프레임에서 사라져도(주웠다 — 판의 실제 장면 %d · 꾸민 장면 %d) 그 프레임의 열쇠는 gear:<uid> 그대로(층 줄로 돌아가 obj: 로 찾지 않는다)"
      % (sum(1 for r in pk if r[0]), sum(1 for r in pk if not r[0])),
      len(pk) == len(JOB["pickup"]) and pk and all(r[1] is False and r[2] == q["key"] for q, r in zip(JOB["pickup"], pk)), list(zip(JOB["pickup"], pk))[:3])
gear_ok = [(t, c, nt["key"]) for t, c, nt in NOTES_ALL if nt["key"].startswith("gear:")]
check("③ 장비 기록(gear:<uid>)이 있으면 '기록' 탭 장부(ledgerRows)의 장비 무리에 있다", all(
    any(g == "장비" and k == key for g, k in (TS.get("ledgerRows") or [[]])[CHARS.index(c)]) or key not in FOLD[-1]["lore"].get(c, {})
    for _, c, key in gear_ok), gear_ok[:3])
bad_cells, n_cells, bad_traps, houses, scoped = [], 0, [], [], []
for lv in TS.get("cells") or []:
    d = DUNG.get(lv["scope"])
    if d is None:
        bad_cells.append(("층 없음", lv["scope"]))
        continue
    door_at = {dd.cell: did for did, dd in (d.doors or {}).items() if dd.cell} if d.scan else {}
    for x, y, z, rg, dr in lv["cells"]:
        n_cells += 1
        want = (d.zone_at.get((x, y)) if d.scan else (("r%d" % d._room_id_at(x, y)) if d._room_id_at(x, y) is not None else None),
                d._town_zone(x, y) if d.town else None, door_at.get((x, y)))
        if (z, rg, dr) != want:
            bad_cells.append((lv["scope"], x, y, (z, rg, dr), want))
    for n, k in enumerate(lv["traps"]):
        if k["one"] != "obj:%s:t%d" % (lv["scope"], n) or n >= len(d.traps) or k["kind"] != "kind:" + d.traps[n].name:
            bad_traps.append((lv["scope"], n, k))
    houses += lv["houses"]
    if lv["scoped"]:
        scoped.append(lv["scoped"])
check("③ level.zones·doors(엔진이 내보낸 구간) → TS cellRun·doorAt = 엔진 칸마다의 obs.zone.id(스캐너 구역·생성기 방)·obs.town_zone·문 칸 — 모든 바닥 칸 %d" % n_cells,
      n_cells > 500 and not bad_cells, bad_cells[:4])
check("③ 마을 바닥 칸의 구역 이름이 있다(마을 줄에 zones.town) · 던전 줄에 문 번호가 있다",
      any(c[3] for lv in TS.get("cells") or [] for c in lv["cells"]) and any(c[4] for lv in TS.get("cells") or [] for c in lv["cells"]))
check("③ 함정 자리 = 엔진 d.traps 자리(obj:<일련>:t<n> · 종류는 함정 이름)", not bad_traps, bad_traps[:3])
same_name = {}
for fid, nm, k in houses:
    same_name.setdefault(nm, set()).add(k["one"])
check("③ 건물 문턱 → place:<공간> · 이름 같은 집 둘은 다른 place:(종류는 같은 kind:<이름>)",
      houses and all(k["one"].startswith("place:") and k["kind"] == "kind:" + nm for _, nm, k in houses)
      and any(len(v) >= 2 for v in same_name.values()), sorted((n, sorted(v)) for n, v in same_name.items())[:4])
check("③ 층 일련이 다르면(새 원정의 같은 깊이 층) 같은 m 번호라도 다른 열쇠", scoped and all(a != b for a, b in scoped), scoped[:2])

# ── ④ 겹침 순서 ───────────────────────────────────────────────────────────
print("── ④ 겹침 순서")
od = TS.get("order") or []
check("④ 사람(앞에 그려진 것 먼저 — 같은 줄의 NPC f1 은 모험가 b2·b3 뒤) > 몬스터(산 것 → 시체) > 물건·설비(깊이 → 아래 줄 → 번호) > 함정 > 문·계단 > 장소 — %s"
      % " · ".join(ORDER_WANT), bool(od) and od[0] == ORDER_WANT, od[:1])
check("④ 같은 입력이면 들어온 순서와 무관하게 같은 순서", bool(od) and all(x == od[0] for x in od), od)
DS = DS_SRC
check("④ 씬 pickAt 이 같은 순서 함수(orderPicks)로 돌려준다 · 무리 번호는 모형의 GROUP · 깊이는 그 그림의 실제 깊이(모험가·몹·피처·함정·계단 스프라이트)",
      "return orderPicks([...out.values()]);" in DS and "group: GROUP.person" in DS and "group: GROUP.place" in DS
      and all(s in DS for s in ("depth: a.sprite.depth", "depth: s.depth, y: m.y", "depth: sprite ? s!.depth : DEPTH.feature", "depth: s.depth, y: tr.y",
                                "depth: this.exitObj.depth")))

# ── ⑤ 부르는 이름 = 관측 이름 ───────────────────────────────────────────────
print("── ⑤ 부르는 이름 = 관측 이름(엔진과 같은 규칙)")
tn = TS.get("names") or []
bad_m, bad_b, bad_g, n_m, n_b, n_g = [], [], [], 0, 0, 0
for q, got in zip(NAMEQ, tn):
    for (mid, okind), name in zip(q["mobs"], got["mobs"]):
        n_m += 1
        if name != okind:
            bad_m.append((q["i"], q["viewer"], mid, okind, name))
    for o, (pure_, folded) in zip(q["bots"], got["bots"]):
        n_b += 1
        want = ID.call({"people": q["people"], "char": q["viewer"]}, "b" + o)
        if not (pure_ == want == folded):
            bad_b.append((q["i"], q["viewer"], o, want, pure_, folded))
    for (fid, own, oname), pair in zip(q["graves"], got["graves"]):
        n_g += 1
        if not pair or not (pair[0] == oname == pair[1]):
            bad_g.append((q["i"], q["viewer"], fid, oname, pair))
check("⑤ 몬스터: 관측 kind(아는 종 이름 | '낯선 짐승') = TS monsterName(종 앎 접기) — %d번" % n_m, n_m >= 5 and not bad_m, bad_m[:3])
check("⑤ 사람: identity.call(관측 people) = TS callWith(같은 장부) = TS callBot(접은 장부) — %d번" % n_b, n_b >= 20 and not bad_b, bad_b[:3])
check("⑤ 묘(판에 있으면): 관측 이름 = TS graveWith = TS featName — %d번" % n_g, not bad_g, bad_g[:3])
check("⑤ 규칙 표: identity.call·grave_label(이름 적음·글만·'낯선 사람'이라 적음·NPC 기록·자기 자신·내 묘·옛 판) = TS callWith·graveWith — %d칸" % len(PURE_REF),
      TS.get("pure") == PURE_REF, list(zip(PURE_REF, TS.get("pure") or []))[:4])
check("⑤ 몬스터 이름이 판 안에서 '낯선 짐승' → 종 이름으로 바뀌는 장면이 있다(아는 종이 생겼다)",
      any(name == LB.UNKNOWN_BEAST for q, g in zip(NAMEQ, tn) for name in g["mobs"]) and any(name not in (None, LB.UNKNOWN_BEAST) for q, g in zip(NAMEQ, tn) for name in g["mobs"]))

# ── ⑥ 시스템 설명 ─────────────────────────────────────────────────────────
print("── ⑥ 시스템 설명")
want_info = {}
for df in sorted(G.ENT.by_kind("object"), key=lambda v: v["id"]):
    if (df.get("comps") or {}).get("item") and df.get("type") in G.ENT.ITEM_TYPES:
        want_info.setdefault("%s:%s" % (df["type"], df["name"]), {"desc": G.ENT.item_desc(df, gain=G.Dungeon.BLESS_GAIN), "rule": G.ENT.item_rule(df["type"])})
check("⑥ run_meta.item_info = 아이템 정의 전부의 entities.item_desc(중립 — '공격에 쓰는 능력치')·item_rule", META.get("item_info") == want_info
      and "공격에 쓰는 능력치" in canon(META["item_info"]) and len(want_info) >= 5, sorted(set(META.get("item_info") or {}) ^ set(want_info)))
bad6 = []
for (t_, n_), got in zip(ITEMQ, TS.get("items") or []):
    df = G.ENT.item_def(t_, n_)
    want = {"desc": G.ENT.item_desc(df, gain=G.Dungeon.BLESS_GAIN), "rule": G.ENT.item_rule(t_)} if df else None
    if got != want:
        bad6.append((t_, n_, got, want))
check("⑥ TS itemInfo 고르기 = entities.item_def(이름 → 그 type 의 정의가 하나면 그것 → 없음) — %d가지" % len(ITEMQ), not bad6 and len(ITEMQ) >= 4, bad6[:3])
bad_lk = []
party = {p["char"]: p for p in META["party"]}
for (i, c, b), got in zip(LOOKQ, TS.get("looks") or []):
    want = sheetkit.looks_line({"look": party[c].get("look"), "weapon": b.get("weapon"), "armor": b.get("armor")})
    if got != want:
        bad_lk.append((i, c, got, want))
check("⑥ run_meta.party[].looks(그림) + 틱의 무기·갑옷 = sheetkit.looks_line(그 몸) — %d번" % len(LOOKQ),
      LOOKQ and not bad_lk and all(p.get("looks") for p in META["party"]), bad_lk[:3])

# ── ⑦ 되감기 ────────────────────────────────────────────────────────────────
print("── ⑦ 되감기·라이브 성장")
pf = TS.get("prefix") or []
check("⑦ 앞부분만 먹인 색인의 k 프레임 = 끝까지 먹인 색인의 k 프레임 — k = %s(멈춤 직전·이어가기 첫 프레임 포함)" % ks,
      len(pf) == len(JOB["prefix"]) and all(r[0] == k + 1 and r[1] for (k, _), r in zip(JOB["prefix"], pf)), pf)
check("⑦ 같은 파서에 이어 먹이면(라이브 성장) 프레임 수·k 값이 같고 색인은 새로 만든다(판 모양 서명이 바뀜)",
      bool(pf) and all(r[2] and r[3] and r[4] for r in pf), pf)

# ── ⑧ 정보 보호 ──────────────────────────────────────────────────────────
print("── ⑧ 정보 보호")
NEW = ("known_ops", "item_info", "zones", "doors")


def has_key(x, keys):
    if isinstance(x, dict):
        return any(k in keys for k in x) or any(has_key(v, keys) for v in x.values())
    if isinstance(x, list):
        return any(has_key(v, keys) for v in x)
    return False


obs_all = [dd["obs"] for r in TICKS for dd in (r.get("decisions") or {}).values() if dd.get("obs")]
check("⑧ 관측(decisions.obs %d개)에 새 칸(known_ops·item_info · 층 줄 구간 rows·ids)이 없고 관측 피처에 묘 주인 of 가 없다(관측의 zone.doors·known.zones 는 옛 칸)" % len(obs_all),
      obs_all and not any(has_key(o, ("known_ops", "item_info", "rows", "ids")) for o in obs_all)
      and not any("of" in f for o in obs_all for f in (o.get("sights") or {}).get("features") or []))
check("⑧ 프롬프트(각본이 받은 %d개)에 새 칸 이름·안쪽 열쇠가 없다" % len(PROMPTS),
      PROMPTS and not any(k in p for p in PROMPTS for k in ("known_ops", "item_info", '"of"', '"looks"'))
      and not any(re.search(r"\b(obj|gear|place|zone|quest):", p) for p in PROMPTS))
import info_guard as IG                               # noqa: E402
lv_any = next((r for r in ROWS if r["kind"] == "level" and r.get("doors")), {"zones": {"ids": ["r0"], "rows": [[0, 2, 0]]}, "doors": [[1, 0, "d0"]]})
ob_any = next((o for o in obs_all if (o.get("zone") or {}).get("doors") and (o.get("known") or {}).get("zones")),   # 판의 실제 관측 꼴(없으면 같은 꼴을 꾸민다)
              {"zone": {"id": "r1", "kind": "방", "doors": [{"id": "d1", "dist": 2, "seen": True}]}, "known": {"zones": {"r1": {"turn": 3}}}})
leak = {"type": "use", "result": "x", "nested": {"known_ops": {"1": ["monster:고블린"]}, "item_info": META["item_info"], "keep": 1},
        "level": {"zones": lv_any["zones"], "doors": lv_any["doors"], "w": 3},
        "feats": [{"id": 7, "type": "grave", "name": "누군가의 묘", "of": "2"}, {"id": 8, "type": "chest", "name": "상자"}]}
pub = IG.public(leak)
keep = IG.public({"type": "wait", "obs": {"zone": ob_any["zone"], "known": ob_any["known"],
                                          "lore": [{"of": "kind", "at": None, "name": "고블린", "text": "x"}], "sights": {"bots": [{"char": "2", "looks": "남자 · 장검"}]}}})
check("⑧ (p0512b) 공개 투영 IG.public 이 관전 클릭 칸을 걷는다 — known_ops·item_info(이름) · 묘의 of · 층 줄 꼴의 zones{ids, rows}·doors[[x, y, id]](자리) — 다른 칸은 그대로",
      pub == {"type": "use", "result": "x", "nested": {"keep": 1}, "level": {"w": 3},
              "feats": [{"id": 7, "type": "grave", "name": "누군가의 묘"}, {"id": 8, "type": "chest", "name": "상자"}]}, pub)
check("⑧ (p0512b) 이름이 겹치는 공개 칸은 남는다 — 관측 zone.doors(dict 목록)·known.zones·lore[].of·sights.bots[].looks",
      keep["obs"]["zone"] == ob_any["zone"] and keep["obs"]["known"] == ob_any["known"] and keep["obs"]["lore"][0]["of"] == "kind"
      and keep["obs"]["sights"]["bots"][0]["looks"] == "남자 · 장검", keep)
check("⑧ 켠 판에는 새 칸이 다 있다(run_meta.item_info · party[].looks · tick.known_ops · level.zones·doors)",
      META.get("item_info") and all(p.get("looks") for p in META["party"]) and any(r.get("known_ops") for r in TICKS)
      and all("zones" in r and "doors" in r for r in ROWS if r["kind"] == "level"))
def off_bad(r):
    """줄의 맨 위 칸 · run_meta.party[] · 피처의 새 칸(관측·도감 정의 속의 옛 낱말 lore·doors 와 헷갈리지 않게 자리를 짚는다)."""
    return ([k for k in NEW + ("lore", "lore_ops", "scope") if k in r] + ["looks" for p in r.get("party") or [] if isinstance(p, dict) and "looks" in p]
            + ["of" for f in r.get("features") or [] if "of" in f])


check("⑧ 끈 판(인물 기록 없음) 스트림에 새 칸이 하나도 없다(run_meta.item_info·lore · party[].looks · known_ops·lore_ops · level.scope·zones·doors · 묘 of)",
      len(OFF_ROWS) > 10 and not any(off_bad(r) for r in OFF_ROWS), [(r["kind"], off_bad(r)) for r in OFF_ROWS if off_bad(r)][:3])

# ── ⑨ 창 모형 ────────────────────────────────────────────────────────────
print("── ⑨ 창 모형")
wv = TS.get("window") or []
want9 = []
for (what, q), w in zip(WQ, wv):
    c, tg = q["viewer"], q["target"]
    if what == "cmp":
        o = tg["char"]
        want9.append(bool(w["rows"]) and [r[0] for r in w["rows"]] == CHARS and [r[1] for r in w["rows"]] == [x == c for x in CHARS]
                     and w["call"] == w["real"] == party[o].get("name") and w["mine"] is None
                     and [r[2] for r in w["rows"]] == [ID.SELF if x == o else (FOLD[q["i"]]["lore"][x].get("b" + o) or {}).get("name") or ID.STRANGER
                                                       for x in CHARS])
    elif what == "self":
        want9.append(w["call"] == ID.SELF and w["mine"]["state"] == "self")
    elif what == "list":
        e = FOLD[q["i"]]["lore"][c]["b" + tg["char"]]
        want9.append(w["mine"]["state"] == "list" and w["mine"]["texts"][0] == e.get("text", "") and w["call"] == (e.get("name") or ID.STRANGER)
                     and w["real"] == party[tg["char"]].get("name"))
    else:
        want9.append(w["mine"]["state"] == "none" and w["mine"]["texts"] == [] and w["facts"] >= 1)
check("⑨ 기록 없는 대상 → '모름' 한 줄 · 기록 있는 사람 → 그 글·적어 둔 이름(관전자 이름은 실명 나란히) · 자기 자신 → '너'·대상 기록 없음 · "
      "비교 → 파티 순서 전원·시점 사람 표시·사람마다의 호칭(자기 자신은 '너')",
      len(wv) == len(WQ) and all(want9) and no_rec is not None and has_rec is not None, list(zip(want9, wv)))
ow = TS.get("offWindow") or [{}]
check("⑨ 옛 판(인물 기록 꺼짐) → 기록 칸 대신 '기록 기능이 없던 판'·시스템 칸은 그대로·이름은 실명",
      TS.get("offPeople") is False and ow[0].get("mine", {}).get("state") == "old" and ow[0].get("facts", 0) >= 3 and ow[0].get("call") == ow[0].get("real"), ow)
PN = io.open(os.path.join(GAME_SRC, "inspect", "Panel.ts"), encoding="utf-8").read()
MD = io.open(os.path.join(GAME_SRC, "inspect", "model.ts"), encoding="utf-8").read()
check("⑨ 모형은 런타임 import 가 없다(import type 만 — node 가 그대로 읽는다) · 창은 액자 모드에서 설치하지 않는다 · 재생을 멈추지 않는다",
      not re.search(r"^import (?!type )", MD, re.M) and "get('embed') === '1') return;" in PN and "playback.pause" not in PN)

# ── ⑩ 종 앎 ────────────────────────────────────────────────────────────────
print("── ⑩ 종 앎(known_ops)")
side_t = [r["turn"] for r in TICKS if r["turn"] < K_STOP and SIDE_KEY in (r.get("known_ops") or {}).get("2", [])]
side_src = any(SIDE_KEY[len("monster:"):] in canon(r.get("monsters")) or SIDE_KEY in canon(r.get("events")) for r in TICKS if r["turn"] <= K_SIDE)
check("⑩ known_ops 접기 = 매 본 스트림 틱 bot['known'](①에서 함께 봤다) — 다른 틱 %d" % len(badk), CAP and not badk, badk[:3])
check("⑩ 본 스트림 밖에서 안 종(t%d 에 2 의 지식 집합에 직접) → 그 틱 known_ops 에 실리고 TS 접기도 그 프레임부터 안다(본 스트림 내용엔 그 종이 없다)" % K_SIDE,
      side_t == [K_SIDE] and not side_src and SIDE_KEY in (tsf[FR_TICK[K_SIDE]]["known"]["2"] if tsf else [])
      and SIDE_KEY not in (tsf[FR_TICK[K_SIDE] - 1]["known"]["2"] if tsf else [SIDE_KEY]), (side_t, side_src))
first_res = min(t for t in FR_TICK if t >= K_STOP)
check("⑩ 이어가기의 첫 본 스트림 틱은 그 순간의 종 앎 전부를 다시 싣는다(합집합이라 접기는 그대로 — 잘린 꼬리의 획득도 잃지 않는다)",
      sorted(next(r for r in TICKS if r["turn"] == first_res).get("known_ops", {}).get("2", [])) == sorted(CAP[first_res]["2"]["known"]),
      (first_res, next(r for r in TICKS if r["turn"] == first_res).get("known_ops")))

# ── 등록 ──────────────────────────────────────────────────────────────────
with open(os.path.join(HERE, "_run_gates.sh"), encoding="utf-8") as f:
    check("_run_gates.sh 에 verify_viewer_click 등록", "verify_viewer_click" in f.read())

shutil.rmtree(ROOT, ignore_errors=True)
print("=" * 44)
print("ALL PASS — verify_viewer_click (p0.5.12 관전 클릭 보기: 접기 = 엔진 장부 · TS = 파이썬 · 대상 → 열쇠 · 칸 → 장소 · 겹침 순서 · 부르는 이름 · "
      "시스템 설명 · 되감기 · 정보 보호 · 창 모형 · 종 앎, 실 LLM 0콜)"
      if not C.failed else "FAILED %d" % C.failed)
sys.exit(1 if C.failed else 0)

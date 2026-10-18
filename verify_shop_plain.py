# -*- coding: utf-8 -*-
"""p0.5.30 가게 주인은 두뇌 없이 · buy 설명 · 거절 사실 · 말로 오가지 않음 — 헤들리스 검증. LLM 0콜.
근거: 실판 10-18(trade1) — 산 횟수 0 · buy 1번이 가게(f13)를 대상(설명 "`target`의 상품을 산다"가 가게로 읽힘 · 결과는 '변화 없음 (not_for_sale)' 뿐) ·
말로 "3골드" 22번 · 주점 주인(NPC 두뇌)이 "3골드 받았네! 바로 차려 줄게"라고 거래를 지어내 수나가 국밥을 기다렸다.
민옥 10-18 "상인 npc는 그냥 두뇌를 빼고 기계적으로 하는걸로 돌리자" · "복잡하게 구현할 생각하지마" — 보통 게임의 상점 NPC: 진열된 상품을 buy 로 산다.
원칙: 사실만 · 데이터 주도(NPC 정의 한 칸 npc.brain) · 기능 플래그 없음 · 새 저장 상태 없음(저장 판 그대로).
게이트:
  ① 정의·검증기: 두뇌를 쓰지 않는 사람 = 정의 npc.brain false 넷(주점 주인·아이템 상인·장비 상인·여관주인 — 지금 가게를 맡은 사람 전부) · 다른 정의엔 그 칸이 없다 ·
     ENT.npc_brain(넷 false · 다른 마을 사람 true · 모르는 이름 true) · 피클에 얼는 정의 사본(npc_defs)·ENT.npc 에 새 칸 없음 · 검증기가 true|false 밖의 값을 거절
  ② 대화 한 길(R.npc_turn — 판의 두뇌 켬): 가게 주인 넷 = 0콜 · 말 걸기 = 정의의 대사 그대로 · 되받기 = 말 없음 · 닫는 차례 = 정해진 닫는 말 · 그 뒤 등 돌림 /
     다른 마을 사람(대장장이·성직자·길드 접수원) = 두뇌 1콜 그대로
  ③ 러너 풀런(스텁 두뇌 — 0콜 · 마을 생활 · 되받기·인사 두뇌 켬): 장비 상인에게 다가가 말 걸기 → 곁에서 지목한 말 넷 / 대장장이 같은 길 —
     가게 주인 넷의 NPC 요청 0 · 장비 상인의 인사 = 정의의 문장(line_src 없음) · 말 걸기 = 정의의 대사(line_src 없음 · 다음 틱 편지함) · 되받은 말 = 닫는 말 하나 · 등 돌림 ·
     대장장이는 두뇌(요청·line_src brain) 그대로 · 판단 요청마다 buy 설명·'말로 오가지 않는다' 줄
  ④ buy 설명·지침: 행동 사전 buy 줄(파티·혼자) · '네가 아는 세계' 절의 '- 돈과 물건은 말로 오가지 않는다.'(파티·혼자 · 마을 안팎 같은 절)
  ⑤ buy 거절 사실: 가게(주점 · 장비점) = '<이름> f…은(는) 상품이 아니다 — 파는 것: [g…] 이름 값골드 · …' · 사람(NPC·동료)·다른 피처 = '…은(는) 상품이 아니다' ·
     1인칭 문장 = 꼬리표 = 관측 '그 결과' = 공개 사본(last)에서 같은 문장 · 골드 그대로 · 무엇을 하라는 말 없음 · 말 파일 칸 셋과 검증기
  ⑥ 그대로인 길: buy 식사(그 자리에서 먹음) · 돈 부족 too_poor → 주점 주인의 정해진 말 · 상품 사기는 결과 칸이 그대로(shop·goods 없음)
  ⑦ 배선: _run_gates.sh · VERSION 0.5.30 이상 · PATCH_NOTES · CHANGELOG · STREAM_FORMAT · prompts/README · 저장 판·행동 계약 그대로
"""
import contextlib
import glob
import io
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = tempfile.mkdtemp(prefix="wl_shopplain_")
STATE = os.path.join(ROOT, "state")
os.makedirs(STATE, exist_ok=True)
BASE_ENV = dict(DUNGEON_GM="0", DUNGEON_STEP_DELAY="0", DUNGEON_TURNS="40", DUNGEON_W="40", DUNGEON_H="16",
                DUNGEON_DEPTHS="2", DUNGEON_SEED="7", DUNGEON_MONSTERS="0", DUNGEON_TRAPS="0", DUNGEON_LURKERS="0",
                DUNGEON_BESTIARY_FILE="", DUNGEON_PARTY_FILE=os.path.join(HERE, "party.json"), DUNGEON_STATE_DIR=STATE,
                DUNGEON_TOWN="1", DUNGEON_BRAIN_BACKEND="dummy", DUNGEON_BOSS="0", DUNGEON_RUNS_DIR=os.path.join(ROOT, "runs"),
                DUNGEON_ACTION_MODE="compose")
os.environ.update(BASE_ENV)
for k in ("DUNGEON_QUESTS", "DUNGEON_TOWN_APART", "DUNGEON_NPC_BRAIN", "DUNGEON_SOLO", "DUNGEON_START", "DUNGEON_MENU", "DUNGEON_RESUME",
          "DUNGEON_PARTYFORM", "DUNGEON_STRANGERS", "DUNGEON_TOWN_SIGHT", "DUNGEON_NPC_REPLY", "DUNGEON_TOWN_LIFE", "DUNGEON_NOTICES",
          "DUNGEON_TOWN_BUILDINGS", "DUNGEON_TOWN_WALKERS", "DUNGEON_ARCH", "DUNGEON_FLOOR_LIFE", "DUNGEON_BESTIARY_PLUS", "DUNGEON_OFFER",
          "DUNGEON_NPC_HAIL_BRAIN", "DUNGEON_API_CALL_LIMIT", "DUNGEON_BRAIN_FALLBACK", "DUNGEON_BRAIN_LOG"):
    os.environ.pop(k, None)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import brains                                        # noqa: E402
brains._call_claude = lambda prompt, model="haiku": ""   # LLM 무력화(0콜)


def _no_real_backend(prompt, model):                 # 이중 안전핀: 어떤 길로도 진짜 백엔드는 안 부른다(③ 은 백엔드 이름만 claude_cli 로 돌린다)
    raise AssertionError("real backend must not be called in a gate")


brains._call_cli = brains._call_anthropic = brains._call_gemini = brains._call_openai = _no_real_backend
import composed_actions as CA                        # noqa: E402
import dungeon_gm as G                               # noqa: E402
import entities as ENT                               # noqa: E402
import interactables as IA                           # noqa: E402
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
    print("  %s %s%s" % ("OK  " if ok else "FAIL", name, (" — " + str(detail)[:700]) if (detail and not ok) else ""))
    if not ok:
        C.failed += 1


def src(*p):
    with open(os.path.join(HERE, *p), encoding="utf-8") as f:
        return f.read()


SHEETS = R.load_party(os.path.join(HERE, "party.json"))
NAMES = {c: SHEETS[c]["name"] for c in SHEETS}
KEEPERS = {"tavern_keeper": "주점 주인", "item_merchant": "아이템 상인", "gear_merchant": "장비 상인", "innkeeper": "여관주인"}   # 가게를 맡은 사람(정의 id → 이름)
GEAR, TK, SMITH, PRIEST, RECEPTION = "장비 상인", "주점 주인", "대장장이", "성직자", "길드 접수원"
OTHERS = (SMITH, PRIEST, RECEPTION)                  # 두뇌를 쓰는 마을 사람(마을 생활 판에 서 있다)
BUY_DESC = "상품을 산다. `target`은 상품 ID(`g...`)다. 값은 골드로 낸다."
NO_TALK = "- 돈과 물건은 말로 오가지 않는다."
ORDER = ("하라", "해라", "써라", "사려면", "buy", "가라", "가 봐")   # 결과 문장에 없어야 하는 지시 꼴


def town(on=True):
    """마을(마을 생활 켬/끔) + 파티 몸 셋. 정의의 말·값은 리포의 것 그대로(verify_trade 와 같은 꼴)."""
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


def by_name(d, name, typ=None):
    return next(f for f in d.features.values() if f.name == name and (typ is None or f.type == typ))


def stand_by(d, f, bots=(), skip=()):
    """피처 곁(직교)의 걸을 수 있는 빈 칸(다른 몸이 없는)."""
    taken = {(o["x"], o["y"]) for o in bots} | set(skip)
    return next((f.x + dx, f.y + dy) for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0))
                if d.grid[f.y + dy][f.x + dx] == G.FLOOR and d.feature_at(f.x + dx, f.y + dy) is None and (f.x + dx, f.y + dy) not in taken)


def put(b, xy):
    b["x"], b["y"] = xy


def act(d, b, bots, action):
    d.view(b, bots)                                   # 관측 = 참조(_target_refs)를 새로 짓는다(실판과 같은 순서)
    return d.act(b, dict(action), bots)


def gid_of(d, name):
    return next(g["gid"] for g in IA.goods(d) if g["name"] == name)


def npc_comp(e):
    return (e.get("comps") or {}).get("npc") or {}


# ─────────────────────────────────────────────────────────────────────────────
print("── ① 정의·검증기")
NPCS = ENT.by_kind("npc")
raw = {eid: json.loads(src("entities", "npc", eid + ".json")) for eid in KEEPERS}
no_brain = sorted(e["name"] for e in NPCS if npc_comp(e).get("brain") is False)
shop_holders = sorted(e["name"] for e in NPCS if npc_comp(e).get("shop"))
check("① 두뇌를 쓰지 않는 사람 = 정의 npc.brain false 넷(%s — 리포 JSON 그대로) · 지금 가게를 맡은 사람(npc.shop) 전부와 같다 · 다른 마을 사람 %d명의 정의엔 그 칸이 없다"
      % ("·".join(sorted(KEEPERS.values())), len(NPCS) - len(KEEPERS)),
      no_brain == sorted(KEEPERS.values()) == shop_holders and all(raw[eid]["comps"]["npc"].get("brain") is False for eid in KEEPERS)
      and not [e["id"] for e in NPCS if e["id"] not in KEEPERS and "brain" in npc_comp(e)], (no_brain, shop_holders))
check("① ENT.npc_brain(이름): 가게 주인 넷 false · 다른 마을 사람 전부 true · 정의가 없는 이름 true",
      all(ENT.npc_brain(n) is False for n in KEEPERS.values())
      and all(ENT.npc_brain(e["name"]) is True for e in NPCS if e["name"] not in KEEPERS.values()) and ENT.npc_brain("정의 없는 사람") is True,
      [(e["name"], ENT.npc_brain(e["name"])) for e in NPCS])
d1, bots1 = town(True)
check("① 새 저장 상태 없음 — 피클에 얼는 정의 사본(d.npc_defs)·ENT.npc(두 판)에 새 칸(brain)이 없다(러너는 그때그때 정의를 읽는다) · 넷 다 마을 생활 판에 서 있다",
      all(n in d1.npc_defs and "brain" not in d1.npc_defs[n] for n in KEEPERS.values())
      and all("brain" not in ENT.npc(eid, life=lf) for eid in KEEPERS for lf in (False, True)),
      {n: sorted(d1.npc_defs.get(n) or {}) for n in KEEPERS.values()})


def problems_with(edit):
    """정의 사본(임시 폴더)에 edit(폴더)를 가하고 읽은 문제 목록(글) — 말 파일은 리포 사본(verify_start_gold 와 같은 꼴)."""
    root = tempfile.mkdtemp(prefix="defs_", dir=ROOT)
    for p in glob.glob(os.path.join(ENT.ROOT, "*", "*.json")):
        dst = os.path.join(root, os.path.basename(os.path.dirname(p)))
        os.makedirs(dst, exist_ok=True)
        shutil.copy(p, dst)
    edit(root)
    wroot = os.path.join(tempfile.mkdtemp(prefix="words_", dir=ROOT), "world")
    shutil.copytree(os.path.join(HERE, "prompts", "world"), wroot)
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


BRAIN_ERR = "npc.brain 은 true|false"
bad1 = problems_with(lambda r: jedit(r, "npc", "smith", lambda d_: d_["comps"]["npc"].update(brain="no")))
bad1b = problems_with(lambda r: jedit(r, "npc", "tavern_keeper", lambda d_: d_["comps"]["npc"].update(brain=0)))
ok1 = problems_with(lambda r: jedit(r, "npc", "smith", lambda d_: d_["comps"]["npc"].update(brain=True)))
check("① 검증기: npc.brain 이 true|false 밖(\"no\" · 0)이면 로드 단계에서 그 문제 한 줄 · true 는 통과 · 리포 정의는 통과",
      BRAIN_ERR in bad1 and "\n" not in bad1 and BRAIN_ERR in bad1b and "\n" not in bad1b and ok1 == "" and problems_with(lambda r: None) == "",
      (bad1[:200], bad1b[:200], ok1[:200]))

# ─────────────────────────────────────────────────────────────────────────────
print("── ② 대화 한 길(npc_turn — 판의 두뇌 켬)")
calls2 = []


def stub_reply(bot, res, said, facts, npc=None, roster=None, names=None):
    """brains.npc_reply 스텁 — 부른 NPC 를 적고 정해 둔 문장을 돌려준다(0콜)."""
    calls2.append(res.get("npc"))
    return "두뇌가 쓴 말"


d2, bots2 = town(True)
a2 = bots2[0]
old_reply, brains.npc_reply = brains.npc_reply, stub_reply
got2, lines2 = {}, {}
try:
    for eid, nm in sorted(KEEPERS.items()):
        f = by_name(d2, nm, "npc")
        put(a2, stand_by(d2, f, bots2))
        r_ = act(d2, a2, bots2, {"type": "use", "target": "f%d" % f.id})
        lines2[nm] = (r_.get("result"), r_.get("line"))
        seq = [R.npc_turn(d2, a2, nm, "3골드 드릴게요", r_, lambda n_: ["사실"], True, names=NAMES)]
        for _ in range(3):
            seq.append(R.npc_turn(d2, a2, nm, "3골드 드릴게요", {"result": "npc_say", "npc": nm, "offer": []}, lambda n_: ["사실"], True, names=NAMES))
        got2[nm] = seq
    keeper_calls = list(calls2)
    others2 = {}
    for nm in OTHERS:
        f = by_name(d2, nm, "npc")
        put(a2, stand_by(d2, f, bots2))
        r_ = act(d2, a2, bots2, {"type": "use", "target": "f%d" % f.id})
        others2[nm] = (r_.get("result"), R.npc_turn(d2, a2, nm, "안녕하세요", r_, lambda n_: ["사실"], True, names=NAMES),
                       R.npc_turn(d2, a2, nm, "또 여쭤요", {"result": "npc_say", "npc": nm, "offer": []}, lambda n_: ["사실"], True, names=NAMES))
finally:
    brains.npc_reply = old_reply
LIFE_LINE = {nm: ENT.npc(eid, life=True)["line"] for eid, nm in KEEPERS.items()}
check("② 가게 주인 넷에게 말 걸기(use · 판의 두뇌 켬) = npc_talk · 정의의 대사 그대로(마을 생활 판 life.npc.line — 예: 장비 상인 '%s') · src fixed · 0콜"
      % LIFE_LINE[GEAR],
      not keeper_calls and all(lines2[nm] == ("npc_talk", LIFE_LINE[nm]) and got2[nm][0] == {"line": LIFE_LINE[nm], "src": "fixed", "stage": "talk"}
                               for nm in KEEPERS.values()), (keeper_calls, lines2, {nm: s[0] for nm, s in got2.items()}))
check("② 같은 쌍의 되받기(npc_say) = 말 없음 → 닫는 차례 = 정해진 닫는 말('%s') → 등 돌림(말 없음) · 장부 3에서 멈춘다 · 0콜" % G.NPC_LINE_CLOSE,
      not keeper_calls and all([(s["line"], s["src"], s["stage"]) for s in got2[nm][1:]]
                               == [(None, "fixed", "talk"), (G.NPC_LINE_CLOSE, "fixed", "close"), (None, "fixed", "away")]
                               and a2["npc_talk"].get("npc:" + nm) == 3 and "npc:" + nm in (a2.get("npc_away") or {}) for nm in KEEPERS.values()),
      ({nm: [(s["line"], s["stage"]) for s in got2[nm][1:]] for nm in got2}, a2.get("npc_talk")))
check("② 다른 마을 사람(%s) = 두뇌 그대로 — 말 걸기·되받기 각 1콜 · src brain · 두뇌가 쓴 말" % "·".join(OTHERS),
      calls2[len(keeper_calls):] == [nm for nm in OTHERS for _ in (0, 1)]
      and all(o_[0] in G.NPC_TALK_RESULTS and o_[1] == {"line": "두뇌가 쓴 말", "src": "brain", "stage": "talk"}
              and o_[2] == {"line": "두뇌가 쓴 말", "src": "brain", "stage": "talk"} for o_ in others2.values()),
      (calls2, others2))

# ─────────────────────────────────────────────────────────────────────────────
print("── ③ 러너 풀런(스텁 두뇌 — 0콜 · 마을 생활 · 되받기·인사 두뇌 켬)")
npc_prompts, adv_prompts, plan3 = [], [], {}
GO = {"1": GEAR, "2": SMITH}                          # 봇1 = 장비 상인 · 봇2 = 대장장이(출발점에서 둘 다 가깝다) · 봇3 = 기다린다
SAY3 = {"1": "단검 값 8골드 드릴게요", "2": "화덕 구경해도 돼요?"}


def stub_brain(prompt, model="haiku"):
    """판단 요청·NPC 요청을 프롬프트 머리로 가른다. 봇1·봇2: 맡은 사람이 멀면 use(다가가 말 걸기) · 곁이면 그 사람을 `to` 로 지목해 말한다."""
    if prompt.lstrip().startswith("# 마을 사람"):
        npc_prompts.append(prompt)
        return '{"line": "두뇌가 쓴 말 %d"}' % len(npc_prompts), None
    adv_prompts.append(prompt)
    m = re.search(r"- 번호 (\S+), 이름", prompt)
    who = m.group(1) if m else "?"
    dec = {"type": "wait", "reason": "게이트 각본"}
    nm = GO.get(who)
    fm = re.search(r"\n- %s (f\d+) \([^\n]*?\) — \S+, 거리 (\d+)" % re.escape(nm), prompt) if nm else None
    if fm:
        st = plan3.setdefault(who, {})
        if int(fm.group(2)) > 1 and not st.get("near"):
            dec = {"type": "use", "target": fm.group(1), "reason": "게이트 각본"}
        else:
            st["near"] = True
            dec = {"type": "wait", "say": SAY3[who], "to": fm.group(1), "reason": "게이트 각본"}
    return json.dumps(dec, ensure_ascii=False), None


st3 = tempfile.mkdtemp(prefix="run_", dir=ROOT)
patch3 = {"STATE": st3, "TOWN_LIFE_ON": True, "NPC_REPLY_ON": True, "NPC_HAIL_BRAIN_ON": True, "MAX_TURNS": 72, "PAUSE_LIMIT_SEC": 2}   # 도착 ≈ t51·t55(걷는 길)
old3 = {k_: getattr(R, k_) for k_ in patch3}
old_env3, old_call3 = os.environ.get("DUNGEON_BRAIN_BACKEND"), brains._call_claude
os.environ["DUNGEON_BRAIN_BACKEND"] = "claude_cli"
for k_, v_ in patch3.items():
    setattr(R, k_, v_)
brains._call_claude = stub_brain
try:
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            R.main()
        except SystemExit:
            pass
finally:
    brains._call_claude = old_call3
    os.environ["DUNGEON_BRAIN_BACKEND"] = old_env3
    for k_, v_ in old3.items():
        setattr(R, k_, v_)
with open(os.path.join(st3, "stream.jsonl"), encoding="utf-8") as fh:
    rows3 = [json.loads(ln) for ln in fh if ln.strip()]
ticks3 = [r_ for r_ in rows3 if r_["kind"] == "tick"]
asked = sorted({re.match(r"# 마을 사람 — 너는 (.+?)이다", p.lstrip()).group(1) for p in npc_prompts if re.match(r"# 마을 사람 — 너는 (.+?)이다", p.lstrip())})
hails3 = [(r_["turn"], h) for r_ in ticks3 for h in (r_.get("npc_hails") or [])]
reps3 = [(r_["turn"], x) for r_ in ticks3 for x in (r_.get("npc_replies") or [])]
evs3 = [(r_["turn"], e) for r_ in ticks3 for e in r_.get("events") or [] if e.get("result") in G.NPC_TALK_RESULTS]
gear_talk = [(t_, e) for t_, e in evs3 if e.get("npc") == GEAR]
smith_talk = [(t_, e) for t_, e in evs3 if e.get("npc") == SMITH]
check("③ 판이 끝까지 돈다 · NPC 두뇌 판(run_meta.npc_brain · npc_reply) · NPC 요청을 받은 사람에 가게 주인 넷이 없다 · 대장장이는 있다",
      rows3[-1]["kind"] == "end" and rows3[0].get("npc_brain") is True and rows3[0].get("npc_reply") is True
      and SMITH in asked and not set(asked) & set(KEEPERS.values()), (rows3[-1]["kind"], asked))
HAIL = {nm: ENT.npc(eid, life=True)["hail"] for eid, nm in KEEPERS.items()}
kh3 = [h for _t, h in hails3 if h["npc"] in KEEPERS.values()]
check("③ 가게 주인의 인사(인사 두뇌 켬) = 정의의 문장 그대로({name} = 들은 사람 — 예: 주점 주인 '%s') · line_src 없음 · 두뇌 인사(line_src brain)는 다른 사람에게서 나온다" % HAIL[TK],
      kh3 and all(h["line"] == HAIL[h["npc"]].replace("{name}", NAMES[str(h["char"])]) and "line_src" not in h for h in kh3)
      and any(h.get("line_src") == "brain" and h["npc"] not in KEEPERS.values() for _t, h in hails3),
      [(t_, h["npc"], h["char"], h.get("line_src"), h["line"][:30]) for t_, h in hails3][:10])
by_turn3 = {r_["turn"]: r_ for r_ in ticks3}
gt = gear_talk[0] if gear_talk else (None, {})
inbox_next = ((by_turn3.get((gt[0] or 0) + 1) or {}).get("inbox") or {}).get("1") or []
check("③ 장비 상인에게 다가가 말 걸기(자동 접근 도착) = npc_talk · 정의의 대사 그대로 · line_src·line_fixed 없음 · 그 대사가 다음 틱 봇1 편지함에 from 'npc:장비 상인'",
      len(gear_talk) == 1 and gt[1].get("result") == "npc_talk" and gt[1].get("line") == LIFE_LINE[GEAR] and "line_src" not in gt[1] and "line_fixed" not in gt[1]
      and any(m_.get("from") == "npc:" + GEAR and m_.get("text") == LIFE_LINE[GEAR] and str(m_.get("to")) == "1" for m_ in inbox_next),
      (gear_talk, inbox_next))
gr3 = [(t_, x) for t_, x in reps3 if x["npc"] == GEAR]
said1 = [r_["turn"] for r_ in ticks3 if ((r_.get("decisions") or {}).get("1") or {}).get("say")]
away3 = [(r_["turn"], e) for r_ in ticks3 for e in (r_.get("npc_away") or []) if e.get("npc") == GEAR and str(e.get("char")) == "1"]
check("③ 곁에서 장비 상인을 지목한 말 넷 → 되받은 말은 닫는 말 하나(talk close · '%s' · 두 번째 지목) · 첫 지목은 말 없음 · 그 뒤 등 돌림(tick.npc_away start)" % G.NPC_LINE_CLOSE,
      len(said1) >= 4 and [(x["line"], x.get("talk"), x["via"]) for _t, x in gr3] == [(G.NPC_LINE_CLOSE, "close", "to")]
      and gr3[0][0] == said1[1] and away3 and away3[0][1].get("ev") == "start" and away3[0][0] == gr3[0][0],
      (said1, gr3, away3))
sr3 = [(t_, x) for t_, x in reps3 if x["npc"] == SMITH]
check("③ 대장장이(두뇌를 쓰는 사람)는 그대로 — 말 걸기 = 두뇌 문장(line_src brain · 원문 line_fixed) · 되받은 말도 두뇌 문장",
      len(smith_talk) == 1 and smith_talk[0][1].get("line_src") == "brain" and str(smith_talk[0][1].get("line", "")).startswith("두뇌가 쓴 말")
      and smith_talk[0][1].get("line_fixed") == ENT.npc("smith", life=True)["line"]
      and sr3 and all(str(x["line"]).startswith("두뇌가 쓴 말") or x.get("talk") == "close" for _t, x in sr3),
      (smith_talk, sr3))
check("③ 판단 요청(%d개)마다 buy 설명 줄 '- `buy`: %s' 과 '%s' 이 한 번씩" % (len(adv_prompts), BUY_DESC, NO_TALK),
      adv_prompts and all(p.split("\n").count("- `buy`: " + BUY_DESC) == 1 and p.split("\n").count(NO_TALK) == 1 for p in adv_prompts), len(adv_prompts))

# ─────────────────────────────────────────────────────────────────────────────
print("── ④ buy 설명·지침")
GUIDES = (brains.COMPOSE_PROMPT, brains.COMPOSE_PROMPT_SOLO)


def world_section(text):
    ls = text.split("\n")
    i = ls.index("## 네가 아는 세계")
    j = next(k for k in range(i + 1, len(ls)) if ls[k].startswith("## "))
    return ls[i + 1:j]


check("④ 동사 정의의 설명(말 파일 prompts/world/verb/buy.md) = '%s' · 지침 행동 사전(파티·혼자)의 buy 줄 · 옛 설명('`target`의 상품을 산다') 없음" % BUY_DESC,
      CA.VERBS["buy"]["desc"] == BUY_DESC and all(g.split("\n").count("- `buy`: " + BUY_DESC) == 1 and "`target`의 상품을 산다" not in g for g in GUIDES),
      CA.VERBS["buy"]["desc"])
check("④ '네가 아는 세계' 절(파티·혼자)에 '%s' 한 줄 — 이동 줄 바로 다음 · 마을 규칙 줄(마을 안 판단에만 붙는다)과 따로 · 지침 파일의 그 절" % NO_TALK,
      all(world_section(g).count(NO_TALK) == 1 and world_section(g)[world_section(g).index(NO_TALK) - 1].startswith("- 이동은 세계가 대신 걷는다.") for g in GUIDES)
      and NO_TALK in "\n".join(world_section(src("prompts", "adventurer_prompt.md"))) and not re.search(r"<!--TOWN:\w+-->[^<]*돈과 물건", src("prompts", "adventurer_prompt.md")),
      [world_section(g)[:4] for g in GUIDES])

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑤ buy 거절 사실")
d5, bots5 = town(True)
a5, b5, c5 = bots5
TAV, EQ = by_name(d5, "주점", "building"), by_name(d5, "장비점", "building")
TKF, TABLE = by_name(d5, TK, "npc"), by_name(d5, "주점 바깥 탁자")
TW = CA.trade_words()


def reject(target, at, who_names=NAMES):
    """at 곁에 서서 buy target → (결과, 1인칭 문장, 꼬리표, 공개 사본의 문장, 관측의 '그 결과' 줄들, 골드 전·후)."""
    put(a5, stand_by(d5, at, bots5))
    g0 = a5["gold"]
    r_ = act(d5, a5, bots5, {"type": "buy", "target": target})
    w_ = brains._wire(d5.view(a5, bots5), who_names, compose=True)
    return (r_, brains._last_prose(r_, who_names), G.event_tags(r_, who_names), brains._last_prose(a5.get("last") or {}, who_names),
            [ln for ln in w_.split("\n") if ln.startswith("- 그 결과: ")], (g0, a5["gold"]))


r5, p5, t5, l5, w5, gold5 = reject("f%d" % TAV.id, TAV)
S_TAV = "주점 f%d은(는) 상품이 아니다 — 파는 것: [%s] 식사 3골드" % (TAV.id, gid_of(d5, "식사"))
check("⑤ 가게(주점 f%d)에 buy = no_effect(not_for_sale) · 사실 칸 shop '주점' · goods [{tid, name, price}] · 골드 그대로 · 문장 '%s'" % (TAV.id, S_TAV),
      r5["result"] == "no_effect" and r5.get("reason_code") == "not_for_sale" and r5.get("shop") == "주점"
      and r5.get("goods") == [{"tid": gid_of(d5, "식사"), "name": "식사", "price": 3}] and gold5[0] == gold5[1] and p5 == S_TAV, (r5, p5))
check("⑤ 같은 문장이 꼬리표('변화 없음')·공개 사본(last)·관측 '그 결과' 줄에 · 무엇을 하라는 말 없음",
      t5 == [("misc", "변화 없음", S_TAV)] and l5 == S_TAV and a5["last"].get("goods") == r5["goods"]
      and len(w5) == 1 and w5[0].endswith(S_TAV) and not any(o_ in S_TAV for o_ in ORDER), (t5, l5, w5))
EQ_SELLS = json.loads(src("entities", "building", "equipment_store.json"))["comps"]["life"]["use"]["sells"]
S_EQ = "장비점 f%d은(는) 상품이 아니다 — 파는 것: %s" % (EQ.id, " · ".join("[%s] %s %d골드" % (gid_of(d5, ENT.get(s_["item"])["name"]), ENT.get(s_["item"])["name"], s_["price"])
                                                                      for s_ in EQ_SELLS))
r5e, p5e, t5e, _l, _w, gold5e = reject("f%d" % EQ.id, EQ)
check("⑤ 상품이 여럿인 가게(장비점 f%d — 정의의 진열 순서 %d개) = '%s'" % (EQ.id, len(EQ_SELLS), S_EQ),
      p5e == S_EQ and t5e == [("misc", "변화 없음", S_EQ)] and len(r5e.get("goods") or []) == len(EQ_SELLS) == 4 and gold5e[0] == gold5e[1], (p5e, r5e.get("goods")))
r5n, p5n, t5n, _l, _w, _g = reject("f%d" % TKF.id, TKF)
r5o, p5o, t5o, _l, _w, _g = reject("f%d" % TABLE.id, TABLE)
put(b5, stand_by(d5, TABLE, bots5, skip={(a5["x"], a5["y"])}))
r5b = act(d5, a5, bots5, {"type": "buy", "target": "b2"})
S_NPC, S_OBJ, S_BOT = "주점 주인 f%d은(는) 상품이 아니다" % TKF.id, "주점 바깥 탁자 f%d은(는) 상품이 아니다" % TABLE.id, "%s은(는) 상품이 아니다" % NAMES["2"]
check("⑤ 가게가 아닌 대상 = '…은(는) 상품이 아니다' — 마을 사람(%s) · 다른 피처(%s) · 동료(%s — 이름으로) · 1인칭 문장 = 꼬리표 · 사실 칸 what(피처만) · goods 없음"
      % (S_NPC, S_OBJ, S_BOT),
      (p5n, p5o, brains._last_prose(r5b, NAMES)) == (S_NPC, S_OBJ, S_BOT)
      and (t5n, t5o, G.event_tags(r5b, NAMES)) == ([("misc", "변화 없음", S_NPC)], [("misc", "변화 없음", S_OBJ)], [("misc", "변화 없음", S_BOT)])
      and r5n.get("what") == TK and r5o.get("what") == "주점 바깥 탁자" and "what" not in r5b and not any("goods" in x or "shop" in x for x in (r5n, r5o, r5b))
      and all(x["result"] == "no_effect" and x.get("reason_code") == "not_for_sale" for x in (r5n, r5o, r5b)),
      (p5n, p5o, brains._last_prose(r5b, NAMES), r5b))
check("⑤ 말 파일(prompts/actions/trade.md ⚠️임시) 세 칸 그대로 — buy_shop '{target}은(는) 상품이 아니다 — 파는 것: {goods}' · buy_other '{target}은(는) 상품이 아니다' · "
      "good '[{id}] {name} {price}골드' · 검증기가 그 칸의 모르는 자리·빠진 칸을 거절",
      (TW.get("buy_shop"), TW.get("buy_other"), TW.get("good")) == ("{target}은(는) 상품이 아니다 — 파는 것: {goods}", "{target}은(는) 상품이 아니다", "[{id}] {name} {price}골드")
      and CA.TRADE_FILLS["buy_shop"] == ("target", "goods") and CA.TRADE_FILLS["buy_other"] == ("target",) and CA.TRADE_FILLS["good"] == ("id", "name", "price")
      and CA.trade_problems({**TW, "buy_other": "{target} {goods}"}) == ["prompts/actions/trade.md: `buy_other` 칸의 {goods} 는 모르는 자리다(쓸 수 있는 자리: {target})"]
      and any("칸 `good` 가 없다" in p_ for p_ in CA.trade_problems({k_: v_ for k_, v_ in TW.items() if k_ != "good"})),
      (TW.get("buy_shop"), TW.get("buy_other"), TW.get("good")))

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑥ 그대로인 길")
put(a5, stand_by(d5, TAV, bots5))
a5["gold"], a5["needs"]["hunger"] = 10, 30
r6 = act(d5, a5, bots5, {"type": "buy", "target": gid_of(d5, "식사")})
check("⑥ buy 식사(주점 · 3골드) = 그 자리에서 먹는다(need_fill via buy · 골드 10 → 7) · 문장 그대로 · 결과에 가게 상품 목록(goods) 없음",
      r6["result"] == "need_fill" and r6.get("via") == "buy" and a5["gold"] == 7 and brains._last_prose(r6) == "주점에서 식사를 사 먹었다 — 3골드를 냈다(남은 골드 7)"
      and "goods" not in r6, r6)
a5["gold"], a5["needs"]["hunger"] = 1, 30
r6b = act(d5, a5, bots5, {"type": "buy", "target": gid_of(d5, "식사")})
LINE_POOR = ENT.npc("tavern_keeper", life=True)["line_too_poor"]
check("⑥ 돈이 모자라면 too_poor(골드 그대로) → 주점 주인의 정해진 말 그대로 '%s'(R.too_poor_says — 두뇌 무관)" % LINE_POOR,
      r6b["result"] == "too_poor" and a5["gold"] == 1 and R.too_poor_says(d5, a5, r6b) == [(TK, LINE_POOR, a5["char"])], r6b)

# ─────────────────────────────────────────────────────────────────────────────
print("── ⑦ 배선")
sf = src("STREAM_FORMAT.md")
check("⑦ _run_gates.sh 등록(낱말 경계) · VERSION 0.5.30 이상 · PATCH_NOTES 0.5.30 · CHANGELOG p0.5.30 · STREAM_FORMAT(not_for_sale 의 shop·goods·what · npc.brain) · "
      "prompts/README(trade.md 의 buy_shop)",
      re.search(r"(?<![\w])verify_shop_plain(?![\w])", src("_run_gates.sh")) is not None
      and tuple(int(x) for x in src("VERSION").strip().split(".")) >= (0, 5, 30) and "## 0.5.30" in src("docs", "PATCH_NOTES.md")
      and "p0.5.30" in src("docs", "CHANGELOG.md") and "not_for_sale" in sf and "`goods`" in sf and "`npc.brain:false`" in sf
      and "buy_shop" in src("prompts", "README.md"))
check("⑦ 저장 판 그대로(STATE_VERSION 14 — 새 저장 상태 없음) · 행동·관측 계약 compose-v0.6 그대로(동사 세트가 그대로다)",
      SN.STATE_VERSION == 14 and CA.PROFILE == CA.SCHEMA == "compose-v0.6", (SN.STATE_VERSION, CA.PROFILE, CA.SCHEMA))

shutil.rmtree(ROOT, ignore_errors=True)
print()
if C.failed:
    print("FAIL — %d/%d" % (C.failed, C.n))
    sys.exit(1)
print("ALL PASS — verify_shop_plain (p0.5.30 가게 주인은 두뇌 없이 · buy 설명·거절 사실·말로 오가지 않음: %d checks · 정의·검증기 · 대화 한 길 · 러너 풀런 · "
      "지침 · 거절 문장 · 그대로인 길 · 배선, 실 LLM 0콜)" % C.n)

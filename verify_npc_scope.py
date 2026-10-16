# -*- coding: utf-8 -*-
"""p0.5.17 마을 NPC 는 마을 이야기만 — 던전 층의 실측(몬스터 종별 수·함정 수…)이 마을 NPC 에게 가는 길이 없다. 실 LLM 0콜(_call_claude 스텁).
(2026-10-16 민옥 결정 "마을 NPC 는 마을에 대한 이야기를 한다. 던전 상세 정보는 아예 없앤다" · 단 NPC 자신의 과거사는 괜찮다.
 근거: 0.5.15 Haiku 판 — 주점 주인의 '1층 고블린 4·그림자거미 1·함정 3개'를 듣고 마을 길에서 함정을 찾아 헤맸다.)
게이트:
  ① 정의·말: 어느 NPC 정의(마을 생활 두 판)에도 소문 인사 칸 hail_rumor·숫자 자리({monsters}{traps}{treasure})·'N층' 이 없다 ·
     주점 주인·떠돌이 모험자·주점 건물의 역할·성격·대사·특징·이야기에 '소문'·'2층 거미'·'던전 얘기는 정확하게' 가 없다 · 키 목록·말 설명표에 hail_rumor 없음 ·
     과거사 글은 남는다(은퇴한 모험자의 옛이야기·'지금 던전 안은 모른다')
  ② NPC 지침: 'NPC 의 앎의 범위' 한 줄(지금 던전 안이 어떤지는 모른다)이 NPC 프롬프트에 실린다 · 모험가 지침에는 없다
  ③ 엔진 인사: 마을의 NPC 마다 곁에 선 사람에게 거는 인사 — hail_rumor 없음·숫자 없음 · 옛 피클의 소문 재료(d.rumor)와 정의 사본의 hail_rumor 가
     남아 있어도 엔진은 읽지 않는다(기본 hail)
  ④ 러너 사실(npc_facts): 마을의 모든 NPC 의 사실 묶음에 소문·몬스터 수·함정·'지하 N층' 이 없다 · 의뢰 사실은 남는다(접수원 게시판 ·
     주점 주인 '네가 낸 의뢰를 이 파티가 맡았다' — 소문 분기 밖) · 맡지 않았으면 그 줄 없음
  ⑤ 러너 풀런(스텁 두뇌 — 0콜, 1층에 몬스터·함정이 있는 판): 인사(두뇌)·되받기의 NPC 요청 전부에 그 1층의 실측(종별 수·함정 수)이 없다 ·
     주점 주인의 요청이 실제로 있었다 · 앎의 범위 줄 · tick.npc_hails 에 hail_rumor·숫자 없음 · 스냅샷의 세계에 소문 재료 칸 없음
  ⑥ 저장 판 10(snapshot._m9_rumor): 옛 판 9 의 세계 — 소문 재료 칸을 걷고 주점 주인·떠돌이 모험자·주점의 말을 지금 정의로(행인의 걷는 자리는 그대로) ·
     다른 NPC 의 말은 손대지 않는다 · 제자리·한 번 · 이관한 세계의 인사
  ⑦ 배선: 러너·엔진 소스에 소문 재료 경로 없음 · _run_gates.sh 등록 · STREAM_FORMAT·PATCH_NOTES·CHANGELOG
(기존 게이트는 별도 실행.)
"""
import contextlib
import copy
import io
import json
import os
import pickle
import re
import shutil
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = tempfile.mkdtemp(prefix="wl_npcscope_")
STATE = os.path.join(ROOT, "state")
os.makedirs(STATE, exist_ok=True)
BASE_ENV = dict(DUNGEON_GM="0", DUNGEON_STEP_DELAY="0", DUNGEON_TURNS="6", DUNGEON_DEPTHS="2", DUNGEON_SEED="7",
                DUNGEON_MONSTERS="3", DUNGEON_TRAPS="3", DUNGEON_LURKERS="1",   # 1층에 몬스터·함정이 있는 판 — 옛 소문이라면 숫자를 말했을 세계
                DUNGEON_BESTIARY_FILE="", DUNGEON_PARTY_FILE=os.path.join(HERE, "party.json"), DUNGEON_STATE_DIR=STATE,
                DUNGEON_TOWN="1", DUNGEON_BRAIN_BACKEND="dummy", DUNGEON_BOSS="0", DUNGEON_RUNS_DIR=os.path.join(ROOT, "runs"),
                DUNGEON_ACTION_MODE="compose")
os.environ.update(BASE_ENV)
for k in ("DUNGEON_W", "DUNGEON_H", "DUNGEON_QUESTS", "DUNGEON_TOWN_APART", "DUNGEON_NPC_BRAIN", "DUNGEON_SOLO", "DUNGEON_START", "DUNGEON_MENU",
          "DUNGEON_RESUME", "DUNGEON_PARTYFORM", "DUNGEON_STRANGERS", "DUNGEON_TOWN_SIGHT", "DUNGEON_NPC_REPLY", "DUNGEON_TOWN_LIFE",
          "DUNGEON_NPC_HAIL_BRAIN", "DUNGEON_API_CALL_LIMIT", "DUNGEON_BRAIN_FALLBACK", "DUNGEON_BRAIN_LOG", "DUNGEON_ARCH"):
    os.environ.pop(k, None)

import brains                                        # noqa: E402
brains._call_claude = lambda prompt, model="haiku": ""   # LLM 무력화 → dummy 폴백(결정론)


def _no_real_backend(prompt, model):                 # 이중 안전핀: 어떤 길로도 진짜 백엔드는 안 부른다(⑤ 는 백엔드 이름만 claude_cli 로 돌린다)
    raise AssertionError("real backend must not be called in a gate")


brains._call_cli = brains._call_anthropic = brains._call_gemini = brains._call_openai = _no_real_backend
import dungeon_gm as G                               # noqa: E402
import entities as ENT                               # noqa: E402
import show_runner as R                              # noqa: E402
import snapshot as S                                 # noqa: E402
import words as W                                    # noqa: E402
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


def floor_words(s):
    """층 이름(숫자+층) — '1층'…'9층'. 넓은 정규식 대신 글자 그대로."""
    return [w for w in ("%d층" % n for n in range(1, 10)) if w in str(s)]


def mkbot(char, x, y, job="전사"):
    return {"char": char, "x": x, "y": y, "hp": 14, "maxhp": 14, "str": 3, "dex": 0, "wdmg": 4, "stealth": 0,
            "search_r": 1, "job": job, "sex": "남", "persona": "", "bag": 0, "potions": 1, "weapon": None, "armor": None,
            "alive": True, "won": False, "order": None, "path": [], "aware_of": set(), "name": "두란" if char == "1" else "카야"}


def beside(d, f):
    """그 피처 곁(상하좌우 한 칸)의 빈 바닥."""
    return next(((f.x + dx, f.y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                 if d.grid[f.y + dy][f.x + dx] == G.FLOOR and d.feature_at(f.x + dx, f.y + dy) is None), None)


def npc_feat(d, name):
    return next(f for f in d.features.values() if f.type == "npc" and f.name == name)


TK, WA, TAVERN = "주점 주인", "떠돌이 모험자", "주점"
OLD_RUMOR = {"depth": 1, "monsters": {"고블린": 4, "그림자거미": 1}, "traps": 3, "features": {"treasure": 2}}   # 옛 판이 지었을 소문 재료(0.5.15 실판의 숫자)
OLD_HAIL = "{name}, 소문 하나 들을래? 요즘 던전 1층엔 {monsters}가 돈대. 함정도 {traps}개쯤 있다더라."          # 옛 정의의 소문 인사 — 옛 피클의 정의 사본에 얼어 있다
TEXT_KEYS = ("line", "line_again", "role", "persona", "hail", "hail_no_potion", "hail_board", "hail_return", "hail_oracle", "hail_party",
             "line_party", "hail_blessed", "line_blessed", "line_close", "line_report", "line_report_failed", "line_report_empty")

FL1 = R.new_floor(1, {})                              # 이 게이트 판의 지하 1층(같은 시드·같은 인자 — 옛 소문 미리보기가 세던 층)
KINDS1 = {}
for m_ in FL1.monsters:
    KINDS1[m_.kind] = KINDS1.get(m_.kind, 0) + 1
PROBES1 = (["%s %d" % (k, n) for k, n in KINDS1.items()] + ["%s %d마리" % (k, n) for k, n in KINDS1.items()]
           + ["함정 %d개" % len(FL1.traps), "함정도 %d개" % len(FL1.traps)])   # 그 층의 실측이 말로 새면 나올 글자(종별 수·함정 수)


def leaks(s):
    """글 하나에 든 1층 실측 글자."""
    return [p for p in PROBES1 if p in str(s)]


print("── ① 정의·말")
npc_ids = sorted(e for e, dd in ENT.load().items() if dd["kind"] == "npc")
texts = []                                           # (정의 id, 판, 칸, 글)
for eid in npc_ids:
    for life in (False, True):
        spec = ENT.npc(eid, life=life)
        texts += [(eid, life, k, spec[k]) for k in TEXT_KEYS if isinstance(spec.get(k), str)]
        texts += [(eid, life, "story." + k, v) for k, v in ((ENT.comps_of(eid, life) or {}).get("story") or {}).items() if isinstance(v, str)]
check("① 어느 NPC 정의(마을 생활 두 판)에도 소문 인사 칸이 없다 — ENT.npc 가 내는 칸에 hail_rumor 없음 · 키 목록·말 설명표에도 없음",
      len(npc_ids) >= 10 and not any("hail_rumor" in ENT.npc(e, life=lf) for e in npc_ids for lf in (False, True))
      and "hail_rumor" not in ENT.LIFE_NPC_KEYS and not any(k == "hail_rumor" for k, _ in W.DESC), len(npc_ids))
bad1 = [(e, lf, k, v) for e, lf, k, v in texts if any(p in v for p in ("{monsters}", "{traps}", "{treasure}")) or floor_words(v)]
check("① 마을 NPC 의 말·성격·소개 어디에도 층 실측 자리({monsters}{traps}{treasure})와 'N층' 이 없다", texts and not bad1, bad1[:3])
mine = [(e, lf, k, v) for e, lf, k, v in texts if e in ("tavern_keeper", "wandering_adventurer")]
bad1b = [(e, k, v) for e, lf, k, v in mine if any(p in v for p in ("소문", "거미", "정확하게", "몬스터", "함정"))]
tv_texts = [ENT.comps_of("tavern", lf)["building"]["role"] for lf in (False, True)] + \
           [v for lf in (False, True) for v in ENT.comps_of("tavern", lf)["story"].values()]
check("① 주점 주인·떠돌이 모험자의 역할·성격·대사·특징·이야기 · 주점 건물의 역할·특징·이야기(두 판)에 소문·거미·'정확하게'·몬스터·함정이 없다",
      mine and not bad1b and not any(p in v for v in tv_texts for p in ("소문", "몬스터", "함정")) and len(tv_texts) == 6, bad1b[:3])
RA = ENT.npc("retired_adventurer")
check("① 과거사는 남는다: 은퇴한 모험자의 성격 = 자기 옛이야기(같이 다니던 동료…)는 하되 지금 던전 안은 모른다 · 이야기 = '아는 건 제 옛이야기뿐'",
      "자기 옛이야기(같이 다니던 동료" in RA["persona"] and "지금 던전 안이 어떤지는 모른다" in RA["persona"]
      and "아는 건 제 옛이야기뿐이다" in ENT.comps_of("retired_adventurer", False)["story"]["history"])

print("── ② NPC 지침 — 앎의 범위 한 줄")
KNOW = "- 지금 던전 안이 어떤지(어느 층에 무엇이 얼마나 있는지)는 모른다."
seen2 = {}
brains._call_claude = lambda p, m="haiku": (seen2.__setitem__("p", p), ('{"line": "어서 와."}', None))[1]
brains.npc_reply(mkbot("1", 0, 0), {"result": "npc_talk", "npc": TK, "line": "정해진 대사"}, "요즘 던전은 어때요?", ["파티: 두란"], npc=ENT.npc("tavern_keeper"))
brains._call_claude = lambda prompt, model="haiku": ""
check("② NPC 프롬프트(npc_prompt.md — 주석은 빠진다)에 앎의 범위 한 줄 · 모험가 지침 파일에는 없다(모험가 쪽은 건드리지 않는다)",
      KNOW in brains._npc_prompt_raw() and KNOW in seen2.get("p", "") and "p0.5.17" not in seen2.get("p", "")
      and "지금 던전 안이 어떤지" not in src("prompts", "adventurer_prompt.md"))

print("── ③ 엔진 인사")
Q3 = G.new_quests()
d3, _s3 = R.build_town(quests=Q3, apart=True, walkers=True)
for qid in d3.quest_ids.values():                    # 게시판 인사(hail_board)가 아니라 각 NPC 의 기본·상황 인사가 나오게
    Q3["accepted"][qid] = {"turn": 1, "by": "1"}
names3 = sorted(f.name for f in d3.features.values() if f.type == "npc")
hails3 = {}
for i, nm in enumerate(names3):
    p_ = beside(d3, npc_feat(d3, nm))
    if p_ is not None:
        for g in d3.npc_greetings([mkbot(str(i + 1), *p_)]):
            hails3[g[0]] = g
bad3 = [g for g in hails3.values() if g[5] == "hail_rumor" or "마리" in g[2] or "함정" in g[2] or floor_words(g[2]) or leaks(g[2])]
check("③ 마을의 NPC 마다 곁에서 받는 인사 — hail_rumor 없음 · 몬스터 수·함정·'N층' 없음 · 주점 주인·떠돌이 모험자도 인사한다",
      {TK, WA} <= set(hails3) and len(hails3) >= 5 and not bad3, (sorted(hails3), bad3[:2]))
d3.rumor = dict(OLD_RUMOR)                           # 옛 피클의 세계(이관 전): 소문 재료 칸 + 정의 사본의 소문 인사
d3.npc_defs[TK] = {**d3.npc_defs[TK], "hail_rumor": OLD_HAIL}
tkb = mkbot("2", *beside(d3, npc_feat(d3, TK)))
g3o = d3.npc_greetings([tkb])
check("③ 옛 소문 재료(d.rumor)와 정의 사본의 hail_rumor 가 남아 있어도 엔진은 읽지 않는다 — 주점 주인은 기본 hail(이름만 채움)",
      len(g3o) == 1 and g3o[0][5] == "hail" and g3o[0][2] == ENT.npc("tavern_keeper")["hail"].replace("{name}", "카야").strip()
      and "소문" not in g3o[0][2], g3o)

print("── ④ 러너 사실(npc_facts)")
Q4 = G.new_quests()
d4, s4 = R.build_town(quests=Q4, apart=True, walkers=True)
b4 = mkbot("1", *s4["1"])
names4 = sorted(d4.npc_defs)
MARK = ("소문", "마리", "함정", "지하 ")
facts_off = {nm: R.npc_facts(d4, nm, [b4], [], Q4) for nm in names4}
Q4["accepted"]["lost_trinket"] = {"turn": 2, "by": "1"}
Q4["accepted"]["goblin_cull"] = {"turn": 2, "by": "1"}
facts_on = {nm: R.npc_facts(d4, nm, [b4], ["2"], Q4) for nm in names4}
_life0 = R.TOWN_LIFE_ON
R.TOWN_LIFE_ON = True                                # 마을 생활 판의 마을(새 주민·가게 값 사실까지)
try:
    d4L, s4L = R.build_town(quests=Q4, apart=True, walkers=True)
finally:
    R.TOWN_LIFE_ON = _life0
facts_life = {nm: R.npc_facts(d4L, nm, [mkbot("1", *s4L["1"])], [], Q4) for nm in sorted(d4L.npc_defs)}
bad4 = [(nm, s) for fx in (facts_off, facts_on, facts_life) for nm, ls in fx.items() for s in ls if any(m in s for m in MARK) or leaks(s)]
check("④ 마을의 모든 NPC(옛 판 %d · 마을 생활 판 %d) 사실 묶음에 소문·몬스터 수('마리')·함정·'지하 N층' · 이 판 1층의 실측(%s · 함정 %d)이 없다 — 의뢰를 맡기 전·후 모두"
      % (len(names4), len(facts_life), KINDS1, len(FL1.traps)),
      {TK, WA, "길드 접수원"} <= set(names4) and len(facts_life) > len(names4) and "은퇴한 모험자" in facts_life
      and any("골드" in s for s in facts_life[TK]) and not bad4, bad4[:3])
check("④ 의뢰 사실은 남는다: 주점 주인 = '네가 낸 의뢰를 이 파티가 맡았다: 잃어버린 장신구'(소문 분기 밖 — 역할에 '소문'이 없어도) · 맡기 전엔 없다 · "
      "접수원 게시판 = 맡은 의뢰 진행 · 다른 NPC 에게는 남의 의뢰 줄이 없다",
      "네가 낸 의뢰를 이 파티가 맡았다: 잃어버린 장신구" in facts_on[TK] and not any("네가 낸 의뢰" in s for s in facts_off[TK])
      and any(s.startswith("게시판 의뢰:") and "잃어버린 장신구" in s and "맡음 0/1" in s and "고블린 소탕" in s for s in facts_on["길드 접수원"])
      and not any("네가 낸 의뢰" in s for nm, ls in facts_on.items() if nm != TK for s in ls), facts_on[TK])

print("── ⑤ 러너 풀런(스텁 두뇌 — 0콜)")


def run(env, patch=None, brain=None, turns="6"):
    """러너 풀런(같은 프로세스) → (스트림 줄들, 상태 폴더). patch = 러너 모듈 상수 {이름: 값}, brain = _call_claude 스텁."""
    st = tempfile.mkdtemp(prefix="run_", dir=ROOT)
    old_env = {k_: os.environ.get(k_) for k_ in env}
    old_mod = {k_: getattr(R, k_) for k_ in (patch or {})}
    old_state, old_call, old_lim = R.STATE, brains._call_claude, (R.MAX_TURNS, R.PAUSE_LIMIT_SEC)
    os.environ.update(env)
    for k_, v_ in (patch or {}).items():
        setattr(R, k_, v_)
    R.STATE, R.MAX_TURNS, R.PAUSE_LIMIT_SEC = st, int(turns), 2   # 판단이 막혀도 게이트가 매달리지 않는다(2초 뒤 스스로 닫힌다 → 검사가 FAIL 로 말한다)
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
        return [json.loads(ln) for ln in f if ln.strip()], st


npc_prompts = []


def stub_brain(prompt, model="haiku"):
    """NPC 요청은 프롬프트 머리('# 마을 사람')로 가른다. 모험가: 들리는 마을 사람 중 주점 주인을 먼저 지목해 말한다(숫자 없는 말)."""
    if prompt.lstrip().startswith("# 마을 사람"):
        npc_prompts.append(prompt)
        return '{"line": "그래, 앉았다 가."}', None
    ears = re.search(r"지금 네 말이 들리는 마을 사람: ([^\n]*)", prompt)
    pick = None
    if ears:
        pick = re.search(r"주점 주인\((f\d+)\)", ears.group(1)) or re.search(r"\((f\d+)\)", ears.group(1))
    dec = {"type": "search", "reason": "게이트 각본"}
    if pick:
        dec.update(say="요즘 던전은 어때요?", to=pick.group(1))
    return json.dumps(dec, ensure_ascii=False), None


last_pkl = {}
_take0 = R._take_snapshot


def _take_keep(sw, core, meta):
    """루프 머리의 스냅샷을 쓰고 그 바이트를 쥔다 — 판이 곱게 끝나면 러너가 스냅샷 파일을 지운다(D79)."""
    n_ = _take0(sw, core, meta)
    with open(os.path.join(R.STATE, S.PKL), "rb") as f_:
        last_pkl["b"] = f_.read()
    return n_


R._take_snapshot = _take_keep
rows5, st5 = run({"DUNGEON_BRAIN_BACKEND": "claude_cli", "DUNGEON_TOWN_APART": "1"},
                 {"NPC_REPLY_ON": True, "NPC_HAIL_BRAIN_ON": True, "TOWN_APART_ON": True}, brain=stub_brain)
R._take_snapshot = _take0
tk5 = [p for p in npc_prompts if p.lstrip().startswith("# 마을 사람 — 너는 %s이다" % TK)]
bad5 = [(i, pr) for i, p in enumerate(npc_prompts) for pr in leaks(p) + [w for w in ("소문", "마리") if w in p]]
check("⑤ 1층에 몬스터·함정이 있는 판(%s · 함정 %d) — 인사(두뇌)·되받기의 NPC 요청 %d개 전부에 그 1층의 실측(종별 수·함정 수)·소문이 없다"
      % (KINDS1, len(FL1.traps), len(npc_prompts)),
      sum(KINDS1.values()) >= 2 and len(FL1.traps) >= 1 and npc_prompts and not bad5, bad5[:3])
hails5 = [h for r in rows5 if r["kind"] == "tick" for h in (r.get("npc_hails") or [])]
reps5 = [x for r in rows5 if r["kind"] == "tick" for x in (r.get("npc_replies") or [])]
check("⑤ 주점 주인의 요청이 실제로 있었다(인사·되받기) · 요청마다 앎의 범위 한 줄 · 되받은 말이 스트림에",
      len(tk5) >= 2 and all(KNOW in p for p in npc_prompts) and any(x["npc"] == TK for x in reps5)
      and any(h["npc"] == TK and h.get("line_src") == "brain" for h in hails5), (len(tk5), [x.get("npc") for x in reps5][:4]))
check("⑤ tick.npc_hails — hail_rumor 없음 · 숫자 인사 없음",
      hails5 and not any(h.get("key") == "hail_rumor" or "마리" in h["line"] or "함정" in h["line"] for h in hails5), hails5[:3])
snap5 = pickle.loads(last_pkl["b"]) if last_pkl else {}   # 이 게이트의 러너가 방금 쓴 자기 피클 바이트(밖에서 온 파일이 아니다)
check("⑤ 스냅샷(마지막 루프 머리): 내용 판 = 지금 판 · 마을 세계(와 스냅샷의 모든 층)에 소문 재료 칸이 없다",
      snap5.get("state_version") == S.STATE_VERSION and getattr(snap5.get("d"), "town", False)
      and all("rumor" not in vars(x) for x in S.dungeons(snap5)), (snap5.get("state_version"), S.STATE_VERSION))

print("── ⑥ 저장 판 10(_m9_rumor)")
SHEETS = R.load_party(os.path.join(HERE, "party.json"))
d6, s6 = R.build_town(quests=G.new_quests(), apart=True, walkers=True, guide=True)
bots6 = [mkbot(c, *s6[c]) for c in sorted(s6)]
tkf, waf = npc_feat(d6, TK), npc_feat(d6, WA)
tvf = next(f for f in d6.features.values() if f.type == "building" and f.name == TAVERN)
OLD = {"tk_role": "소문 · 쉬어 가는 자리", "tk_persona": "말이 많고 정이 많다. 던전에서 올라온 소문을 모으는 게 낙이다. 손님이 뭘 물으면 아는 만큼만 말한다.",
       "tk_trait": "1층 몬스터·함정 수를 소문으로 알려준다", "wa_line": "던전에서 막 올라온 참이야. 2층 계단 옆에 거미가 매복하더라 — 조심해.",
       "wa_again": "아까 말했잖아, 2층 거미. 그것만 기억해.", "wa_role": "다른 파티의 모험자 · 던전 소문", "tv_trait": "주인이 던전 1층 소문을 안다. 쉬어 가는 자리"}
RECT = [1, 2, 3, 4]                                   # 지을 때 layout 이 덮은 걷는 자리(walker_rects)라 치고 — 이관이 정의의 것으로 되돌리면 안 된다
d6.rumor = dict(OLD_RUMOR)
d6.npc_defs[TK] = {**d6.npc_defs[TK], "hail_rumor": OLD_HAIL, "role": OLD["tk_role"], "persona": OLD["tk_persona"]}
d6.feature_roles[tkf.id] = OLD["tk_role"]
d6.place_story[tkf.id] = {**d6.place_story[tkf.id], "trait": OLD["tk_trait"]}
d6.npc_defs[WA] = {**d6.npc_defs[WA], "line": OLD["wa_line"], "role": OLD["wa_role"], "walk": {**d6.npc_defs[WA]["walk"], "rect": list(RECT)}}
d6.npc_lines[WA], d6.npc_lines_again[WA], d6.feature_roles[waf.id] = OLD["wa_line"], OLD["wa_again"], OLD["wa_role"]
d6.feature_roles[tvf.id] = OLD["tk_role"]
d6.place_story[tvf.id] = {**d6.place_story[tvf.id], "trait": OLD["tv_trait"]}
for p_ in d6.town_guide or []:
    if p_["name"] == TAVERN:
        p_["about"] = OLD["tv_trait"]
d6.npc_lines["길드 접수원"] = "옛 피클의 접수원 말"   # 이관 대상이 아닌 NPC — 손대지 않아야 한다
snap6 = {"version": 2, "state_version": 9, "d": d6, "bots": bots6, "sheets": SHEETS}
up6 = S.upgrade(pickle.loads(pickle.dumps(snap6)))   # 이 프로세스가 방금 만든 바이트만 되읽는다(피클 왕복 = 이어가기와 같은 길)
u6 = up6["d"]
TKd, WAd = ENT.npc("tavern_keeper"), ENT.npc("wandering_adventurer")
tvc = ENT.comps_of("tavern", False)
check("⑥ 판 10 이상(p0.5.18: 판 11 — 기분 조각 꼴) · 이관 9→10 등록 · 옛 세계의 소문 재료 칸을 걷는다",
      S.STATE_VERSION >= 10 and S.MIGRATIONS[9] is S._m9_rumor and up6["state_version"] == S.STATE_VERSION and "rumor" not in vars(u6))
check("⑥ 주점 주인: 정의 사본에서 hail_rumor 가 빠지고 역할·성격이 지금 정의로 · 피처 역할 줄·특징도",
      "hail_rumor" not in u6.npc_defs[TK] and u6.npc_defs[TK]["role"] == TKd["role"] and u6.npc_defs[TK]["persona"] == TKd["persona"]
      and u6.feature_roles[tkf.id] == TKd["role"] and u6.place_story[tkf.id]["trait"] == ENT.comps_of("tavern_keeper", False)["story"]["trait"]
      and u6.npc_defs[TK].get("shop") == "tavern", u6.npc_defs[TK])
check("⑥ 떠돌이 모험자: 대사·재방문 대사·역할이 지금 정의로 — 걷는 자리(layout 이 덮은 rect)는 그대로",
      u6.npc_lines[WA] == WAd["line"] and u6.npc_lines_again[WA] == WAd["line_again"] and u6.feature_roles[waf.id] == WAd["role"]
      and u6.npc_defs[WA]["line"] == WAd["line"] and u6.npc_defs[WA]["walk"]["rect"] == RECT and "거미" not in u6.npc_lines[WA],
      (u6.npc_lines[WA], u6.npc_defs[WA].get("walk")))
check("⑥ 주점 건물: 역할 줄·특징이 지금 정의로 · 마을 안내의 장소 줄도 따라간다 · 이관 대상이 아닌 접수원의 옛 말은 그대로",
      u6.feature_roles[tvf.id] == tvc["building"]["role"] and u6.place_story[tvf.id]["trait"] == tvc["story"]["trait"]
      and any(p_["name"] == TAVERN and p_["about"] == tvc["story"]["trait"] for p_ in (u6.town_guide or []))
      and u6.npc_lines["길드 접수원"] == "옛 피클의 접수원 말", [p_ for p_ in (u6.town_guide or []) if p_["name"] == TAVERN])
again6 = S.upgrade(copy.deepcopy({**up6, "state_version": 9}))
check("⑥ 이관은 제자리·한 번 — 다시 올려도 같은 말·같은 걷는 자리",
      again6["d"].npc_defs[TK] == u6.npc_defs[TK] and again6["d"].npc_defs[WA] == u6.npc_defs[WA] and "rumor" not in vars(again6["d"]))
tk6 = mkbot("2", *beside(u6, tkf))
g6 = u6.npc_greetings([tk6])
check("⑥ 이관한 세계에서 주점 주인 곁 — 기본 hail(소문 인사 없음)",
      len(g6) == 1 and g6[0][5] == "hail" and "소문" not in g6[0][2], g6)

print("── ⑦ 배선")
rs, gs = src("show_runner.py"), src("dungeon_gm.py")
check("⑦ 러너: 소문 재료를 짓는 함수·세계 칸·원정 재계산이 없다(floor_rumor 정의·d.rumor 대입 없음) · 사실 묶음에 '지하 %d층 소문' 줄 없음",
      not hasattr(R, "floor_rumor") and "def floor_rumor" not in rs and "d.rumor =" not in rs and "rumor = floor_rumor" not in rs
      and '"지하 %d층 소문' not in rs and "facts.append(\"네가 낸 의뢰를 이 파티가 맡았다: \"" in rs)
check("⑦ 엔진: 소문 칸 초기화·소문 인사 고르기·숫자 자리 채우기가 없다",
      "self.rumor" not in gs and "d.rumor" not in gs and "'hail_rumor'" not in gs and "'{monsters}'" not in gs and "'{traps}'" not in gs
      and "'{treasure}'" not in gs and not hasattr(G.Dungeon, "rumor"))
gates = src("_run_gates.sh")
check("⑦ _run_gates.sh 에 등록(낱말 경계)", re.search(r"(?<![\w])verify_npc_scope(?![\w])", gates) is not None)
check("⑦ 문서: STREAM_FORMAT(hail_rumor 거둠) · PATCH_NOTES 0.5.17 · CHANGELOG p0.5.17 · VERSION 0.5.17 이상(p0.5.18: 다음 판에서 깨지지 않게)",
      "p0.5.17" in src("STREAM_FORMAT.md") and "## 0.5.17" in src("docs", "PATCH_NOTES.md") and "p0.5.17" in src("docs", "CHANGELOG.md")
      and tuple(int(x) for x in src("VERSION").strip().split(".")) >= (0, 5, 17))

shutil.rmtree(ROOT, ignore_errors=True)   # p0.5.18(게시판 10-16 codex): 임시 폴더를 남기지 않는다(반복 실행 산출)
print("ALL PASS — verify_npc_scope (p0.5.17 마을 NPC 는 마을 이야기만: 층 실측 경로 없음·의뢰 사실 유지·과거사 유지·앎의 범위 한 줄·저장 판 10, 실 LLM 0콜)"
      if C.failed == 0 else "FAIL %d" % C.failed)
raise SystemExit(1 if C.failed else 0)

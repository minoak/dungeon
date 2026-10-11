# -*- coding: utf-8 -*-
"""직업 토대(p0.5.3 = master_plan 0단계) 헤들리스 검증 — 90번째 게이트. LLM 0콜(러너는 dummy 두뇌).
0단계는 칸·접근자·이관 틀만 놓는다 — 행동(스킬 배정·판정·관측·프롬프트)은 그대로여야 한다(그 확인은 tools/baseline.py 차이 보고서).
게이트:
  ① 직업표(traits.json): 4직업 · 몸 수치 = master_plan §2.1 · 정신·숙련 = §2.2 · 시작 스킬 = 기본 파티가 지금 번호로 받는 묶음
     (재편안 §2.3 은 승인 대기라 넣지 않았다) · 마법사 스킬 비움 · 기본값 ⊆ 목록 ⊆ 등록 스킬
  ② 숙련 접근자 judge.prof: 시트 값 → 직업 기본값 → 0 · 모르는 직업 0 · 몹(dict 아님) 0 · 참거짓·문자열·None 은 없는 것 · 모르는 칸은 KeyError
  ③ build_sheet 가 기본값을 복사하지 않는다: 4직업 조립 시트·동료 프리셋·build_party 에 정신·숙련·스킬 칸이 없다 · 몸 수치 7칸 = 직업표
  ④ 손 시트 범위(load_party): 새 칸은 있을 때만 싣는다 · 정신 = 힘·민첩 규칙(정수, 범위 없음) · 숙련 0~6 ·
     참거짓·문자열·소수·범위 밖 = 폴백 · None = 없는 것 · 새 칸 없는 옛 손 시트의 결과 dict 그대로
  ⑤ 스폰: 몸에 정신·숙련(기본 파티 3직업·마법사·손 시트 값·모르는 직업) · 스킬 배정은 번호 묶음 그대로(시트 skills > 번호, 직업 기본값은 아직 안 읽음) ·
     러너 판: run_meta.party·level.party(bot_snapshot)에 새 칸 없음 · 스냅샷 = 판형 2·내용 판 1·몸에 새 칸
  ⑥ SK·SS: ability 'mind'(봇 = 몸, 몹 = 0, 힘·민첩 그대로) · validate 가 'mind' 를 굴림·내성·효과 내성에 허용(모르는 능력치는 거절) ·
     등록 스킬 4개·랜덤 생성기 1000시드 = v0.5.2 고정 해시(생성기 풀 그대로)
  ⑦ 옛 프리셋 왕복: v0.5.2 꼴 프리셋 파일을 읽고·저장하고·다시 읽어도 슬롯 그대로(새 칸 없음) · 그 슬롯의 시트·load_party 에도 새 칸 없음 · 마법사 슬롯 저장·복원
  ⑧ 옛 스냅샷 이관(실제 옛 꼴 = fixtures/snapshot_v052, v0.5.2 코드가 쓴 그대로): 옛 꼴 확인 · 새 로더가 내용 판 0 → 1(몸마다 직업 기본값, 다른 칸 그대로) ·
     러너가 이어간다(resume 줄 · resume_failed 없음 · 틱 연속 · end) · 새 스냅샷 → 옛 로더(fixtures 의 v0.5.2 snapshot.py)가 거절 ·
     더 새 내용 판 → 새 로더도 거절 · 이관 등록부 완결 · (있으면) 루트 state/snapshot.pkl 을 복사본으로 읽어 이관
  ⑨ 문장·뼈대·론처: "직업 = 몸 수치만" 이 traits.json·sheetkit 에서 고쳐졌다 · judge 는 난수를 쓰지 않는다 · /api/presets 의 jobs = 직업표(덧붙이기)·skill_alpha 그대로
"""
import ast
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
import pickle
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="wl_classfound_")
FIX = os.path.join(HERE, "fixtures", "snapshot_v052")
os.environ.update(DUNGEON_GM="0", DUNGEON_TURNS="6", DUNGEON_W="40", DUNGEON_H="16", DUNGEON_SEED="11",
                  DUNGEON_MONSTERS="1", DUNGEON_TRAPS="1", DUNGEON_LURKERS="0", DUNGEON_DEPTHS="1",
                  DUNGEON_BESTIARY_FILE="", DUNGEON_STEP_DELAY="0",
                  DUNGEON_PARTY_FILE=os.path.join(TMP, "party_run.json"), DUNGEON_STATE_DIR=os.path.join(TMP, "state"))
for k in ("DUNGEON_RESUME", "DUNGEON_RUNS_DIR", "DUNGEON_STREAM_OBS", "DUNGEON_TOWN", "DUNGEON_BOSS", "DUNGEON_START"):
    os.environ.pop(k, None)
os.environ.update(DUNGEON_BRAIN_BACKEND="dummy", DUNGEON_ACTION_MODE="menu",   # _run_gates.sh 와 같은 판(혼자 돌려도 같게)
                  DUNGEON_SKILLS="0", DUNGEON_TRPG_COMBAT="0", DUNGEON_RANDOM_SKILL="0")

import brains                                        # noqa: E402
brains._call_claude = lambda prompt, model="haiku": ("", None)   # 0콜 안전핀(더미 두뇌라 원래도 안 나간다)
import dungeon_gm as G                               # noqa: E402
import judge                                         # noqa: E402
import sheetkit                                      # noqa: E402
import skill_core as SK                              # noqa: E402
import skill_schema as SS                            # noqa: E402
import snapshot                                      # noqa: E402
import show_runner                                   # noqa: E402
import launcher                                      # noqa: E402
from character_presets import PresetStore            # noqa: E402

show_runner.STEP_DELAY = 0
fails = []


def check(name, ok, detail=""):
    print(("  ok  " if ok else "  FAIL") + " " + name + (("  — " + str(detail)[:300]) if detail and not ok else ""))
    if not ok:
        fails.append(name)


def jdump(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)


def jsonl(path):
    with io.open(path, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


BODY7 = ("hp", "str", "dex", "wdmg", "stealth", "search_r", "atk_range")
NEW = judge.PROF_KEYS + ("skills", "skill_list")      # 시트에 생기면 안 되는 칸(직업표에서 읽는 것)
PK = judge.PROF_KEYS                                  # 몸에만 생기는 칸(스트림 꼴에는 안 실린다 — 'skills' 는 스킬 판의 옛 몸 칸이라 따로)
DATA = sheetkit.load_traits()
JOBS = DATA["jobs"]

print("── ① 직업표(traits.json)")
TABLE = {   # master_plan §2.1(몸·정신) + §2.2(숙련)
    "전사": dict(hp=14, str=3, dex=0, mind=0, wdmg=4, stealth=0, search_r=1, atk_range=1, search_prof=0, steal_prof=0),
    "도적": dict(hp=10, str=0, dex=3, mind=0, wdmg=3, stealth=4, search_r=2, atk_range=1, search_prof=4, steal_prof=4),
    "궁수": dict(hp=11, str=1, dex=3, mind=0, wdmg=2, stealth=2, search_r=1, atk_range=2, search_prof=2, steal_prof=0),
    "마법사": dict(hp=8, str=0, dex=1, mind=3, wdmg=2, stealth=0, search_r=1, atk_range=1, search_prof=2, steal_prof=0),
}
check("① 직업 넷(전사·도적·궁수·마법사, 이 순서) · 몸 수치·정신·숙련 = master_plan §2.1·§2.2 표",
      list(JOBS) == list(TABLE) and all(JOBS[j][k] == v for j, t in TABLE.items() for k, v in t.items()),
      {j: {k: JOBS.get(j, {}).get(k) for k in t} for j, t in TABLE.items()})
party_json = json.load(io.open(os.path.join(HERE, "party.json"), encoding="utf-8"))
by_number = {s["job"]: list(SS.DEFAULT_SETS[(int(c) - 1) % len(SS.DEFAULT_SETS)]) for c, s in party_json.items() if not c.startswith("_")}
check("① 시작 스킬 = 기본 파티(party.json)의 그 직업이 지금 번호 묶음으로 받는 스킬(재편안 아님 — §12.1-1 승인 대기) · 마법사는 비움",
      all(JOBS[j]["skills"] == by_number[j] for j in by_number) and JOBS["마법사"]["skills"] == [] and sorted(by_number) == ["궁수", "도적", "전사"],
      {j: (JOBS[j].get("skills"), by_number.get(j)) for j in JOBS})
check("① 시작 스킬 ⊆ 직업 스킬 목록 ⊆ 등록 스킬(PRESETS) — 새 스킬 id 없음",
      all(set(v["skills"]) <= set(v["skill_list"]) <= set(SS.PRESETS) for v in JOBS.values()))
bad = copy.deepcopy(DATA)
bad["jobs"]["마법사"]["mind"] = "3"
tp = os.path.join(TMP, "traits_bad.json")
jdump(tp, bad)
try:
    sheetkit.load_traits(tp)
    rejected = False
except ValueError:
    rejected = True
bad2 = copy.deepcopy(DATA)
bad2["jobs"]["전사"]["skills"] = ["push_slash", "first_aid"]       # 목록 밖 기본값
jdump(tp, bad2)
try:
    sheetkit.load_traits(tp)
    rejected2 = False
except ValueError:
    rejected2 = True
old_t = {k: v for k, v in DATA.items()}
old_t["jobs"] = {j: {k: v for k, v in b.items() if k in BODY7} for j, b in DATA["jobs"].items()}
jdump(tp, old_t)
check("① load_traits: 정신 비정수·목록 밖 시작 스킬은 거절 · 새 칸 없는 옛 직업표는 그대로 읽힌다",
      rejected and rejected2 and list(sheetkit.load_traits(tp)["jobs"]["전사"]) == list(BODY7))

print("── ② 숙련 접근자 judge.prof")
check("② 직업 기본값(시트에 값 없음)", [judge.prof({"job": j}, "mind") for j in TABLE] == [0, 0, 0, 3]
      and [judge.prof({"job": j}, "search_prof") for j in TABLE] == [0, 4, 2, 2]
      and [judge.prof({"job": j}, "steal_prof") for j in TABLE] == [0, 4, 0, 0])
check("② 시트(몸) 값이 있으면 그 값 — 0 도 값이다", judge.prof({"job": "마법사", "mind": 1}, "mind") == 1
      and judge.prof({"job": "도적", "search_prof": 0}, "search_prof") == 0 and judge.prof({"job": "전사", "mind": -2}, "mind") == -2)
check("② 모르는 직업(손 시트 '성기사')·직업 없음 = 0 · 몹·NPC(dict 아님) = 0",
      judge.prof({"job": "성기사"}, "mind") == 0 and judge.prof({}, "search_prof") == 0
      and judge.prof(G.Monster(1, 1, "고블린"), "mind") == 0 and judge.prof(None, "steal_prof") == 0)
check("② 참거짓·문자열·None 은 없는 것으로(직업 기본값)", judge.prof({"job": "마법사", "mind": True}, "mind") == 3
      and judge.prof({"job": "마법사", "mind": "5"}, "mind") == 3 and judge.prof({"job": "도적", "steal_prof": None}, "steal_prof") == 4)
try:
    judge.prof({"job": "전사"}, "stealth")
    kerr = False
except KeyError:
    kerr = True
check("② 모르는 칸(은신 등 기존 몸 칸)은 KeyError — 은신은 몸 칸 그대로 읽는다", kerr)
check("② body_fields = 세 칸", judge.body_fields({"job": "궁수"}) == {"mind": 0, "search_prof": 2, "steal_prof": 0})

print("── ③ build_sheet 가 기본값을 복사하지 않는다")
sheets4 = {j: sheetkit.build_sheet(j, ["신중한"], "시험" + str(i), "여") for i, j in enumerate(JOBS)}
check("③ 4직업 조립 시트: 정신·숙련·스킬 칸 없음 · 몸 수치 7칸 = 직업표",
      all(not (set(s) & set(NEW)) for s in sheets4.values())
      and all(s[k] == JOBS[j][k] for j, s in sheets4.items() for k in BODY7), {j: sorted(s) for j, s in sheets4.items()})
party = sheetkit.build_party([{"job": "마법사", "traits": ["과묵한"], "name": "메이", "sex": "여"},
                              {"job": "도적", "traits": ["신중한"], "name": "카야2", "sex": "여"}], data=DATA)
comps = {}
try:
    import entities
    comps = {cid: sheetkit.build_companion_sheet(d, data=DATA) for cid, d in entities.companions().items()}
except Exception as e:                                # 동료 정의가 깨졌으면 그 게이트(verify_companion)가 말한다
    comps = {"_err": {"error": str(e)}}
check("③ build_party·동료 프리셋 시트에도 새 칸 없음", all(not (set(s) & set(NEW)) for s in list(party.values()) + list(comps.values()))
      and "_err" not in comps and len(comps) >= 1, sorted(comps))

print("── ④ 손 시트 범위(load_party)")
HAND = {"job": "전사", "sex": "남", "hp": 14, "str": 3, "dex": 0, "wdmg": 4, "stealth": 0, "search_r": 1, "persona": "손으로 쓴 전사"}


def load_one(extra, job=None):
    s = dict(HAND, **extra)
    if job:
        s["job"] = job
    p = os.path.join(TMP, "hand.json")
    jdump(p, {"1": s})
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        out = show_runner.load_party(p)
    return out, "폴백" in err.getvalue()


base_out, fb0 = load_one({})
check("④ 새 칸 없는 옛 손 시트: 폴백 없음 · 결과 dict 키 = v0.5.2 그대로(새 칸을 써 넣지 않는다)",
      not fb0 and sorted(base_out["1"]) == sorted(list(HAND) + ["atk_range"]), sorted(base_out["1"]))
o1, f1 = load_one({"mind": 2, "search_prof": 6, "steal_prof": 0})
o2, f2 = load_one({"mind": -3, "str": -3})
o3, f3 = load_one({"mind": 40})
check("④ 있을 때만 싣는다 · 정신은 힘·민첩과 같은 규칙(정수면 음수·큰 값도 통과 — 힘·민첩도 범위가 없다) · 숙련 0~6",
      not (f1 or f2 or f3) and o1["1"].get("mind") == 2 and o1["1"].get("search_prof") == 6 and o1["1"].get("steal_prof") == 0
      and o2["1"].get("mind") == -3 and o2["1"]["str"] == -3 and o3["1"].get("mind") == 40, (f1, f2, f3))
rej = {repr(x): load_one(x)[1] for x in ({"mind": True}, {"mind": "3"}, {"mind": 1.5}, {"search_prof": 7}, {"search_prof": -1},
                                          {"steal_prof": "4"}, {"steal_prof": False})}
check("④ 참거짓·문자열·소수·범위 밖 숙련 → 폴백(내장 2인)", all(rej.values()), rej)
on, fn = load_one({"mind": None, "search_prof": None})
check("④ None 은 없는 것(칸을 안 싣는다 · 폴백 아님)", not fn and "mind" not in on["1"] and "search_prof" not in on["1"])
ow, fw = load_one({}, job="마법사")
check("④ 손 시트의 직업 이름이 마법사여도 시트 수치를 그대로(직업표로 덮지 않는다) · 정신 칸 없음", not fw and ow["1"]["hp"] == 14 and "mind" not in ow["1"])

print("── ⑤ 스폰")
d5 = G.Dungeon(seed=5, w=30, h=12, n_monsters=1, n_traps=0, n_lurkers=0, skills=True, composed_actions=True, auto_approach=True)
bots5 = []
for c in ("1", "2", "3"):
    bots5.append(G.spawn(d5, c, bots5, sheet=show_runner.load_party(os.path.join(HERE, "party.json"))[c]))
check("⑤ 기본 파티 몸: 전사 0/0/0 · 도적 0/4/4 · 궁수 0/2/0 (정신/수색/손재주)",
      [tuple(b.get(k) for k in judge.PROF_KEYS) for b in bots5] == [(0, 0, 0), (0, 4, 4), (0, 2, 0)], [tuple(b.get(k) for k in judge.PROF_KEYS) for b in bots5])
check("⑤ 스킬 배정 = 번호 묶음 그대로(직업 기본값은 아직 안 읽는다)", [b["skills"] for b in bots5] == [list(x) for x in SS.DEFAULT_SETS])
wiz = G.spawn(d5, "1", [], sheet=sheets4["마법사"])
hand = G.spawn(d5, "2", [], sheet=dict(HAND, mind=2))
odd = G.spawn(d5, "3", [], sheet=dict(HAND, job="성기사"))
heroes = G.spawn(d5, "2", [])                         # 시트 없이(내장 HEROES — 옛 게이트의 spawn(d,'2',[]))
check("⑤ 마법사 3/2/0 · 손 시트 정신 2 · 모르는 직업 0/0/0 · 내장 도적 0/4/4 · 마법사 슬롯 1 은 번호 묶음 1",
      tuple(wiz.get(k) for k in PK) == (3, 2, 0) and hand.get("mind") == 2 and hand.get("search_prof") == 0
      and (odd.get("mind"), odd.get("search_prof")) == (0, 0) and tuple(heroes.get(k) for k in PK) == (0, 4, 4)
      and wiz["skills"] == list(SS.DEFAULT_SETS[0]))
check("⑤ 스트림 스냅샷(bot_snapshot)에 새 칸 없음(화이트리스트)", not (set(G.bot_snapshot(wiz)) & set(PK)))
jdump(os.environ["DUNGEON_PARTY_FILE"], {"1": dict(sheets4["마법사"]), "2": dict(HAND, mind=2, name="손전사")})
real_remove = snapshot.remove
snapshot.remove = lambda state_dir: None              # 판이 끝나도 마지막 스냅샷을 남긴다(⑤·⑧ 재료)
try:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        show_runner.main()
finally:
    snapshot.remove = real_remove
recs5 = jsonl(os.path.join(show_runner.STATE, "stream.jsonl"))
meta5 = recs5[0]
lvl5 = next(r for r in recs5 if r.get("kind") == "level")
check("⑤ 러너 판(마법사 + 정신 적은 손 시트): run_meta.party · level.party 에 새 칸 없음 · 끝까지",
      recs5[-1].get("kind") == "end" and all(not (set(p) & set(NEW)) for p in meta5["party"] + lvl5["party"])   # 스킬 끈 판이라 'skills' 도 없다
      and [p["job"] for p in meta5["party"]] == ["마법사", "전사"], [sorted(p) for p in meta5["party"]])
with open(snapshot.paths(show_runner.STATE)[0], "rb") as f:
    snap5 = pickle.load(f)                            # 방금 이 프로세스의 러너가 쓴 파일
check("⑤ 새 스냅샷: 판형 2 · 내용 판 1 · 몸에 정신·숙련(마법사 3/2/0 · 손 시트 정신 2) · 요약도 판형 2",
      snap5["version"] == snapshot.VERSION == 2 and snap5["state_version"] == snapshot.STATE_VERSION == 1
      and [tuple(b.get(k) for k in PK) for b in snap5["bots"]] == [(3, 2, 0), (2, 0, 0)]
      and (snapshot.read_meta(show_runner.STATE) or {}).get("version") == 2,
      [(b.get("mind"), b.get("search_prof")) for b in snap5["bots"]])

print("── ⑥ SK·SS")
mon = G.Monster(2, 2, "고블린")
tb = ("bot", (1, 1), wiz)
check("⑥ SK.ability: 봇 정신 = 몸 칸 · 몸에 칸이 없으면 직업 기본값 · 몹 정신 0 · 힘·민첩은 그대로",
      SK.ability(tb, "mind") == 3 and SK.ability(("bot", (1, 1), {k: v for k, v in wiz.items() if k != "mind"}), "mind") == 3
      and SK.ability(("monster", (2, 2), mon), "mind") == 0 and SK.ability(("monster", (2, 2), mon), "str") == mon.atk
      and SK.ability(("monster", (2, 2), mon), "dex") == max(0, mon.ac - 10) and SK.ability(tb, "dex") == wiz["dex"])
s_att = SS.make("t_mind_bolt", "시험 정신 명중", [{"type": "damage", "dice": "1d6"}], ability="mind")
s_save = SS.make("t_mind_save", "시험 정신 내성", [{"type": "status", "status": "bleed"}], ability="mind")
s_save["roll"].update(type="save", save_ability="mind")
s_save["cost"] = SS.skill_cost(s_save)
s_eff = SS.make("t_mind_push", "시험 효과 내성", [{"type": "damage", "dice": "1d4"}, {"type": "push", "distance": 1, "save": "mind"}])
s_bad = SS.make("t_bad", "시험", [{"type": "damage", "dice": "1d4"}])
s_bad["roll"]["ability"] = "int"
check("⑥ SS.validate: 'mind' 를 굴림·내성·효과 내성에 허용 · 모르는 능력치('int')는 invalid_roll",
      SS.validate(s_att) == [] and SS.validate(s_save) == [] and SS.validate(s_eff) == [] and SS.validate(s_bad) == ["invalid_roll"])
gen = [SS.generate("%d:%s:floor3" % (i, c), budget=5) for i in range(334) for c in "123"][:1000]
gh = hashlib.sha256(json.dumps(gen, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
ph = hashlib.sha256(json.dumps(SS.PRESETS, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
check("⑥ 랜덤 생성기 1000시드·등록 스킬 4개 = v0.5.2 고정 해시(검증만 넓히고 생성기 풀은 그대로 — 3층 스킬 불변)",
      gh == "b70cfd4220155993ef30fb5b446ba9fe138a4133c9dffd51739bff97ccadf587"
      and ph == "398d082b8c71876d61d930e62ead14cf984a8a630fd70bf79d5d4845c37a50f8", (gh, ph))

print("── ⑦ 옛 프리셋 왕복")
SLOT_KEYS = ["background", "job", "look", "name", "persona", "sex", "traits"]
old_slot = {"name": "카야", "sex": "여", "job": "도적", "traits": ["신중한"], "persona": "말수가 적다", "background": "광산 마을", "look": None}
PR = os.path.join(TMP, "character_presets.json")
jdump(PR, {"_schema_version": 1, "version": 1, "presets": [{"id": "pid1", "label": "카야", "slot": old_slot}]})   # v0.5.2 가 쓰는 꼴
store = PresetStore(PR, DATA)
l1 = store.list()
store.save(l1[0]["slot"], l1[0]["label"], "pid1")
l2 = store.list()
check("⑦ v0.5.2 꼴 프리셋: 읽기 → 저장 → 다시 읽기에서 슬롯 그대로 · 슬롯 칸 = 생성 입력 7칸(새 칸 없음)",
      l1 == l2 and sorted(l2[0]["slot"]) == SLOT_KEYS and l2[0]["slot"] == old_slot, (l1, l2))
pp = os.path.join(TMP, "preset_party.json")
sheetkit.write_party(sheetkit.build_party([l2[0]["slot"]], data=DATA), pp)
with contextlib.redirect_stderr(io.StringIO()) as err7:
    lp = show_runner.load_party(pp)
check("⑦ 그 슬롯의 시트 → party 파일 → load_party: 폴백 없음 · 새 칸 없음",
      "폴백" not in err7.getvalue() and not (set(lp["1"]) & set(NEW)) and lp["1"]["job"] == "도적")
store.save(dict(old_slot, name="메이", job="마법사"), "메이")
l3 = store.list()
check("⑦ 마법사 슬롯 저장·복원", [e["slot"]["job"] for e in l3] == ["도적", "마법사"] and sorted(l3[1]["slot"]) == SLOT_KEYS)

print("── ⑧ 옛 스냅샷 이관(fixtures/snapshot_v052 — v0.5.2 코드가 쓴 그대로)")


def load_old_module():
    spec = importlib.util.spec_from_file_location("snapshot_v052", os.path.join(FIX, "snapshot_v052.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


OLD = load_old_module()
S8 = os.path.join(TMP, "s8", "state")
shutil.copytree(FIX, S8)
with open(os.path.join(S8, "snapshot.pkl"), "rb") as f:
    raw8 = pickle.load(f)                             # 리포 고정 자료(코드와 같은 신뢰 급 — fixtures README)
meta8 = json.load(io.open(os.path.join(S8, "snapshot.json"), encoding="utf-8"))
check("⑧ 자료는 정말 옛 꼴: 판형 1 · state_version 없음 · 몸에 정신·숙련 없음 · 옛 로더가 읽는다",
      raw8.get("version") == 1 and "state_version" not in raw8 and "state_version" not in meta8
      and all(not (set(b) & set(judge.PROF_KEYS)) for b in snapshot._bodies(raw8)) and OLD.load(os.path.join(S8, "snapshot.pkl"))[0]["version"] == 1)
new8, m8 = snapshot.load(os.path.join(S8, "snapshot.pkl"))
bodies8, bodies_raw = snapshot._bodies(new8), snapshot._bodies(raw8)
same_rest = all(set(nb) - set(judge.PROF_KEYS) == set(rb) and all(nb[k] == rb[k] for k in rb if isinstance(rb[k], (int, str, float, bool, type(None), list, dict, set, tuple)))
                for nb, rb in zip(bodies8, bodies_raw))
check("⑧ 새 로더: 내용 판 0 → %d · 판형 %d · 몸마다 직업 기본값(전사 0/0/0 · 도적 0/4/4 · 궁수 0/2/0) · 다른 칸 그대로" % (snapshot.STATE_VERSION, snapshot.VERSION),
      new8["state_version"] == snapshot.STATE_VERSION and new8["version"] == snapshot.VERSION and len(bodies8) == len(bodies_raw) == 3
      and [(b.get("job"), b.get("mind"), b.get("search_prof"), b.get("steal_prof")) for b in bodies8] == [("전사", 0, 0, 0), ("도적", 0, 4, 4), ("궁수", 0, 2, 0)]
      and same_rest, [(b.get("job"), b.get("mind"), b.get("search_prof")) for b in bodies8])
check("⑧ 새 요약 읽기(론처의 '이어가기' 판단)가 옛 요약을 받는다", (snapshot.read_meta(S8) or {}).get("run_id") == meta8["run_id"])
S8b = os.path.join(TMP, "s8b", "state")
shutil.copytree(FIX, S8b)
env8 = {k: v for k, v in os.environ.items() if not k.startswith("DUNGEON_")}
env8.update(json.load(io.open(os.path.join(FIX, "env.json"), encoding="utf-8")))
env8.update(PYTHONUTF8="1", DUNGEON_STATE_DIR=S8b, DUNGEON_PARTY_FILE=os.path.join(HERE, "party.json"),
            DUNGEON_RESUME=os.path.join(S8b, "snapshot.pkl"), DUNGEON_RUNS_DIR=os.path.join(TMP, "s8b", "runs"))
DRIVER = ("import sys; sys.path.insert(0, %r); import brains; brains._call_claude = lambda p, m='haiku': ('', None); "
          "import show_runner; show_runner.STEP_DELAY = 0; show_runner.main()" % HERE)   # __main__ 을 밟지 않는다(.env 무접촉)
p8 = subprocess.run([sys.executable, "-c", DRIVER], cwd=HERE, env=env8, capture_output=True, timeout=600)
recs8 = jsonl(os.path.join(S8b, "stream.jsonl"))
ticks8 = [r["turn"] for r in recs8 if r.get("kind") == "tick"]
res8 = [r for r in recs8 if r.get("kind") == "resume"]
check("⑧ 러너가 옛 스냅샷을 이어간다: resume 줄 하나(turn 6) · run_meta 그대로(resume_failed 없음) · 틱 1..%s 연속 · end" % (ticks8[-1] if ticks8 else "?"),
      p8.returncode == 0 and len(res8) == 1 and res8[0]["turn"] == 6 and "resume_failed" not in recs8[0]
      and recs8[0]["started"] == meta8["started"] and ticks8 == list(range(1, int(env8["DUNGEON_TURNS"]) + 1)) and recs8[-1].get("kind") == "end",
      (p8.returncode, p8.stderr.decode("utf-8", "replace")[-400:], len(res8), ticks8[-3:]))
check("⑧ 이어간 판의 스트림 꼴은 그대로(level·tick 의 몸에 정신·숙련 칸 없음)",
      all(not (set(b) & set(PK)) for r in recs8 if r.get("kind") in ("tick", "level") for b in (r.get("party") or r.get("bots") or [])
          if isinstance(b, dict)))
S8c = os.path.join(TMP, "s8c")
shutil.copytree(show_runner.STATE, S8c)               # ⑤ 판이 남긴 새 스냅샷
try:
    OLD.load(os.path.join(S8c, "snapshot.pkl"))
    old_rejects = False
except OLD.SnapshotError:
    old_rejects = True
check("⑧ 새 스냅샷 → 옛 로더(v0.5.2 snapshot.py)가 거절 · 옛 요약 읽기도 None(옛 론처는 이어가기를 내밀지 않는다)",
      old_rejects and OLD.read_meta(S8c) is None and OLD.VERSION == 1)
with open(os.path.join(S8c, "snapshot.pkl"), "rb") as f:
    future = pickle.load(f)                           # ⑤ 판이 방금 쓴 파일
future["state_version"] = snapshot.STATE_VERSION + 1
with open(os.path.join(S8c, "snapshot.pkl"), "wb") as f:
    pickle.dump(future, f)
fmeta = json.load(io.open(os.path.join(S8c, "snapshot.json"), encoding="utf-8"))
jdump(os.path.join(S8c, "snapshot.json"), dict(fmeta, state_version=snapshot.STATE_VERSION + 1))
try:
    snapshot.load(os.path.join(S8c, "snapshot.pkl"))
    new_rejects = False
except snapshot.SnapshotError as e:
    new_rejects = "더 새" in str(e) or "요약" in str(e)
check("⑧ 더 새 내용 판(되돌린 코드가 새 스냅샷을 만남) → 새 로더도 거절 · 요약 None", new_rejects and snapshot.read_meta(S8c) is None)
check("⑧ 이관 등록부 완결(0..STATE_VERSION-1) · 판형 읽기 목록 = (1, 2)",
      sorted(snapshot.MIGRATIONS) == list(range(snapshot.STATE_VERSION)) and snapshot.READS == (1, 2))
check("⑧ 이관은 제자리·한 번: 이미 올린 스냅샷을 다시 올려도 같다", snapshot.upgrade(copy.deepcopy(new8))["state_version"] == snapshot.STATE_VERSION
      and [b.get("mind") for b in snapshot._bodies(snapshot.upgrade(new8))] == [0, 0, 0])
LIVE = os.path.join(HERE, "state")
if os.path.exists(os.path.join(LIVE, "snapshot.pkl")) and os.path.exists(os.path.join(LIVE, "snapshot.json")):
    L = os.path.join(TMP, "live", "state")
    os.makedirs(L)
    for n in ("snapshot.pkl", "snapshot.json"):       # 읽기만 — 복사본에서
        shutil.copyfile(os.path.join(LIVE, n), os.path.join(L, n))
    try:
        lv, lm = snapshot.load(os.path.join(L, "snapshot.pkl"))
        ok_live = lv["state_version"] == snapshot.STATE_VERSION and all(all(k in b for k in judge.PROF_KEYS) for b in snapshot._bodies(lv))
        why = "%s t%s 판형 %s" % (lm.get("run_id"), lm.get("turn_last"), lm.get("version"))
    except snapshot.SnapshotError as e:
        ok_live, why = False, str(e)
    check("⑧ 루트 state/ 의 실판 스냅샷(복사본): 새 로더가 읽고 몸마다 정신·숙련 — %s" % why, ok_live, why)
else:
    print("  --   루트 state/ 에 실판 스냅샷 없음 — 건너뜀")

print("── ⑨ 문장·뼈대·론처")
traits_raw = io.open(sheetkit.TRAITS_FILE, encoding="utf-8").read()
sk_raw = io.open(os.path.join(HERE, "sheetkit.py"), encoding="utf-8").read()
check("⑨ '직업 = 몸 수치만' 문장이 고쳐졌다(traits.json _readme · sheetkit 주석)",
      "몸 수치(party.json 세트 그대로)만" not in traits_raw and "직업은 몸 수치만 정한다" not in sk_raw
      and "mind·search_prof·steal_prof" in json.loads(traits_raw)["_readme"])
tree = ast.parse(io.open(os.path.join(HERE, "judge.py"), encoding="utf-8").read())
names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
mods = {a.name for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names} | \
       {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
check("⑨ judge.py 뼈대: 난수를 쓰지 않는다(random·rng 없음) · 엔진을 import 하지 않는다 · 0.5 함수 자리(notice·contest·own_check·mind_save)",
      not ({"random", "rng"} & (names | mods)) and "dungeon_gm" not in mods
      and all(callable(getattr(judge, f, None)) for f in ("notice", "contest", "own_check", "mind_save")))
ctx = launcher.Ctx(HERE, os.path.join(TMP, "lc", "party_custom.json"), os.path.join(TMP, "lc", "state"), os.path.join(TMP, "lc", "runs"))
pl = launcher.presets_payload(ctx)
check("⑨ /api/presets: jobs = 직업표(마법사·정신·숙련·스킬 칸 덧붙이기) · skill_alpha 그대로(등록 스킬·번호 묶음)",
      pl["jobs"] == JOBS and pl["skill_alpha"] == {"presets": SS.PRESETS, "default_sets": SS.DEFAULT_SETS}
      and json.loads(json.dumps(pl, ensure_ascii=False))["jobs"]["마법사"]["mind"] == 3)

shutil.rmtree(TMP, ignore_errors=True)
print()
if fails:
    print("FAIL %d — %s" % (len(fails), "; ".join(fails)))
    sys.exit(1)
print("ALL PASS — verify_class_foundation (p0.5.3 직업 토대: 직업표·숙련 접근자·시트 비복사·손 시트 범위·스폰·옛 프리셋 왕복·옛 스냅샷 이관, 실 LLM 0콜)")

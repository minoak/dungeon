# -*- coding: utf-8 -*-
"""구조화 스트림(JSONL) 헤들리스 검증 — Part A(스트림+GM 강등) 게이트.
게이트:
  ① 라인 위생: 전 라인 valid JSON / kind 5종만 / 첫=run_meta / 끝=end
  ② 구조 불변식: run_meta 1개 / level 수 = 1+descend 수 / descend 직전=같은 turn 의 tick·직후=level
     / tick turn 1부터 연속 / end = 마지막 스냅샷
  ③ 스키마 스팟체크: 스냅샷 필드 전수(봇/몹/함정/피처/방), grid h×w·raw 지형, outcome 3종,
     room_id 해소 가능, inbox 형태(전 봇 키), stream_obs 플래그
  ④ 원장 감사(audit): hp/bag/몹hp = 직전 스냅샷 ± 이벤트 델타 / killed→몹 alive:false /
     down→봇 alive:false / exit party↔won 전이 / 고아 decision ↔ skipped 마커
  ⑤ 결정론: 2회 실행 → started 제외 라인 단위 완전 동일 (시드+decisions=리플레이의 토대)
  ⑥ 기존 소비자 교차: events.log 의 강하·종료 문구와 스트림 descend/end 대응(무손상)
  ⑦ 크기 sanity ⑧ DUNGEON_STREAM_OBS=1 → decisions 에 obs 동봉(기본은 없음) ⑨ timeout 분기
  ⑩ 다중 시드 원장 스윕 + 커버리지: seed7 이 안 밟는 원장 규칙(함정피해·상자·샘…)까지 전부 실발화
(기존 verify_stage1/2/2b/3 은 별도 실행 — 게이트 명령이 연쇄한다.)
"""
import io
import os
import json
import contextlib


class C:
    failed = 0


def check(name, cond):
    print(("  OK   " if cond else " FAIL  ") + name)
    if not cond:
        C.failed += 1


os.environ.update(DUNGEON_GM="0", DUNGEON_TURNS="400", DUNGEON_W="40", DUNGEON_H="16",
                  DUNGEON_SEED="7", DUNGEON_MONSTERS="2", DUNGEON_TRAPS="3",
                  DUNGEON_LURKERS="1", DUNGEON_DEPTHS="2",
                  DUNGEON_PARTY_FILE="/nonexistent",   # 시트 외부화(Part B) 무시 → 내장 2인 고정(회귀 그물)
                  DUNGEON_STATE_DIR=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                 "state_streamverify"))
# ⚠️ STATE 격리 필수 — 기본 state/ 로 돌리면 마지막 관전 판의 stream.jsonl 을 truncate 한다
#    (2026-07-05 아침판 소실 사고의 주 경로. 관전 판 보존은 runs/ + 이 격리 두 겹)
os.environ.pop("DUNGEON_STREAM_OBS", None)
import brains
brains._call_claude = lambda prompt, model="haiku": ""   # LLM 무력화 → dummy 폴백(결정론)
os.environ["DUNGEON_BESTIARY_FILE"] = ""   # 도감 영속 차단(리뷰 픽스) — 셸/tmux env 잔재가 라이브 원장을 읽고 쓰는 오염 방지
import show_runner
show_runner.STEP_DELAY = 0
import time as _time
_time.sleep = lambda s: None                             # 러너 고정 sleep 제거(검증 속도)

SPATH = os.path.join(show_runner.STATE, "stream.jsonl")
KINDS = {"run_meta", "level", "tick", "descend", "end"}
BOT_FIELDS = {"char", "job", "sex", "x", "y", "hp", "maxhp", "bag",
              "alive", "won", "order", "aware_of"}
MON_FIELDS = {"id", "kind", "x", "y", "hp", "maxhp", "ac", "atk", "dmg",
              "alive", "state", "concealed", "target", "desperate"}
TRAP_FIELDS = {"x", "y", "kind", "name", "dc", "dmg", "hidden", "sprung"}
FEAT_FIELDS = {"id", "type", "name", "x", "y", "room_id", "concealed", "perception_gate"}
ROOM_FIELDS = {"id", "x", "y", "w", "h", "type", "neighbours"}
SHEET_FIELDS = {"char", "job", "sex", "maxhp", "str", "dex", "wdmg",
                "stealth", "search_r", "persona"}


def run_once():
    with contextlib.redirect_stdout(io.StringIO()), \
         contextlib.redirect_stderr(io.StringIO()):   # 2인 폴백 경고(의도된 것) 소음 제거
        show_runner.main()
    return open(SPATH, encoding="utf-8").read()


def audit(recs):
    """원장·전이 감사 — (위반 수, 발화 카운터) 반환. STREAM_FORMAT 의 델타 규칙 전수를 재계산."""
    viol = 0
    cov = {"trap_dmg": 0, "chest_trap": 0, "chest_loot": 0, "fountain_heal": 0,
           "fountain_harm": 0, "mon_dmg": 0, "walk_treasure": 0, "interact_treasure": 0,
           "down": 0, "killed": 0, "exit_party": 0, "skipped": 0}
    prev, mon_prev = {}, {}
    for r in recs:
        if r["kind"] == "level":
            prev = {b["char"]: (b["hp"], b["bag"]) for b in r["party"]}
            mon_prev = {m["id"]: m["hp"] for m in r["monsters"]}
        elif r["kind"] == "tick":
            dhp = {c: 0 for c in prev}
            dbag = {c: 0 for c in prev}
            dmon = {}
            for e in r["events"]:
                t = e.get("type")
                if t == "walk":
                    tr = e.get("trap") or {}
                    if "dmg" in tr:
                        dhp[e["char"]] -= tr["dmg"]; cov["trap_dmg"] += 1
                    if e.get("result") == "treasure" or e.get("treasure"):
                        dbag[e["char"]] += 1; cov["walk_treasure"] += 1
                elif t == "interact":
                    res = e.get("result")
                    if res in ("chest_trap", "fountain_harm"):
                        dhp[e["char"]] -= e["dmg"]; cov[res] += 1
                    elif res == "fountain_heal":
                        dhp[e["char"]] += e["heal"]; cov["fountain_heal"] += 1
                    elif res == "treasure":
                        dbag[e["char"]] += 1; cov["interact_treasure"] += 1
                    elif res == "chest_loot":
                        dbag[e["char"]] += e["loot"]; cov["chest_loot"] += 1
                elif t == "monster_attack" and e.get("dmg"):
                    dhp[e["target"]] -= e["dmg"]; cov["mon_dmg"] += 1
                elif t == "attack" and e.get("result") == "attack" and e.get("dmg"):
                    mid = int(e["target_id"][1:])
                    dmon[mid] = dmon.get(mid, 0) - e["dmg"]
            snap = {b["char"]: b for b in r["bots"]}
            msnap = {m["id"]: m for m in r["monsters"]}
            for c in prev:
                if snap[c]["hp"] != prev[c][0] + dhp[c]:
                    viol += 1
                if snap[c]["bag"] != prev[c][1] + dbag[c]:
                    viol += 1
            for mid, hp0 in mon_prev.items():
                if msnap[mid]["hp"] != hp0 + dmon.get(mid, 0):
                    viol += 1
            for e in r["events"]:
                t = e.get("type")
                if t == "attack" and e.get("killed"):
                    cov["killed"] += 1
                    if msnap[int(e["target_id"][1:])]["alive"]:
                        viol += 1
                down_char = None                      # down 위치는 이벤트마다 다르다(walk 는 trap 안)
                if t == "monster_attack" and e.get("down"):
                    down_char = e["target"]
                elif t == "interact" and e.get("down"):
                    down_char = e["char"]
                elif t == "walk" and (e.get("trap") or {}).get("down"):
                    down_char = e["char"]
                if down_char is not None:
                    cov["down"] += 1
                    if snap[down_char]["alive"]:
                        viol += 1
                if t == "interact" and e.get("result") == "exit":
                    cov["exit_party"] += 1
                    if not all(snap[c]["won"] for c in e["party"]):
                        viol += 1
            ev_chars = {e["char"] for e in r["events"] if "char" in e}
            for c, dec in r["decisions"].items():     # 고아 decision(미실행) ↔ skipped 마커 항등
                if dec.get("skipped"):
                    cov["skipped"] += 1
                    if c in ev_chars:
                        viol += 1
                elif c not in ev_chars:
                    viol += 1
            prev = {b["char"]: (b["hp"], b["bag"]) for b in r["bots"]}
            mon_prev = {m["id"]: m["hp"] for m in r["monsters"]}
    return viol, cov


raw = run_once()
lines = raw.splitlines()
recs, bad = [], 0
for ln in lines:
    try:
        recs.append(json.loads(ln))
    except Exception:
        bad += 1

# ── ① 라인 위생 ──
check("전 라인 valid JSON", bad == 0 and len(recs) == len(lines) and recs)
check("kind 5종만", all(r.get("kind") in KINDS for r in recs))
check("첫 라인 = run_meta / 끝 라인 = end",
      recs[0]["kind"] == "run_meta" and recs[-1]["kind"] == "end")
check("파일이 개행으로 끝난다(유효 prefix 계약)", raw.endswith("\n"))

# ── ② 구조 불변식 ──
n_meta = sum(1 for r in recs if r["kind"] == "run_meta")
levels = [r for r in recs if r["kind"] == "level"]
descends = [r for r in recs if r["kind"] == "descend"]
ticks = [r for r in recs if r["kind"] == "tick"]
end = recs[-1]
check("run_meta 정확히 1개", n_meta == 1)
check("level 수 = 1 + descend 수", len(levels) == 1 + len(descends))
check("이 시드(7)는 2층 강하 포함(descend 1회 = 회귀 그물)", len(descends) == 1)
check("descend 직전 = 같은 turn 의 tick(옛 층 스냅샷) / 직후 = level(같은 turn·to_depth)",
      all(recs[i - 1]["kind"] == "tick" and recs[i - 1]["turn"] == r["turn"]
          and recs[i + 1]["kind"] == "level"
          and recs[i + 1]["turn"] == r["turn"]
          and recs[i + 1]["depth"] == r["to_depth"]
          for i, r in enumerate(recs) if r["kind"] == "descend"))
check("tick turn = 1부터 연속(빈 틱 포함 불변식)",
      [t["turn"] for t in ticks] == list(range(1, len(ticks) + 1)))
check("end.turn = 마지막 tick turn", ticks and end["turn"] == ticks[-1]["turn"])
check("첫 level 은 turn 0·depth 1", levels[0]["turn"] == 0 and levels[0]["depth"] == 1)
last_snap = None
for r in recs:                                       # end.bots = 파일상 마지막 파티 스냅샷과 동일
    if r["kind"] == "tick":
        last_snap = r["bots"]
    elif r["kind"] == "level":
        last_snap = r["party"]
check("end.bots = 마지막 스냅샷(tick/level)과 동일", end["bots"] == last_snap)

# ── ③ 스키마 스팟체크 ──
meta = recs[0]
check("run_meta: v=1 + 실행 파라미터 + stream_obs=false", meta.get("v") == 1
      and meta["seed"] == 7 and meta["w"] == 40 and meta["h"] == 16
      and meta["depths"] == 2 and meta["max_turns"] == 400
      and meta["gm"] is False and meta["stream_obs"] is False)
check("run_meta: party 시트 필드 전수(스폰 봇에서 파생)",
      len(meta["party"]) == 2
      and all(set(p) == SHEET_FIELDS for p in meta["party"]))
check("level: grid = h개의 w폭 raw 지형('#'/'.')",
      all(len(lv["grid"]) == lv["h"]
          and all(len(row) == lv["w"] for row in lv["grid"])
          and set("".join(lv["grid"])) <= {"#", "."} for lv in levels))
check("level: 시드 필드(master/level 파생) + exit 좌표",
      all(lv["master_seed"] == 7 and isinstance(lv["level_seed"], int)
          and len(lv["exit"]) == 2 for lv in levels))
check("level: rooms 필드 전수 + feature.room_id 해소 가능(dangling 없음)",
      all(all(set(rm) == ROOM_FIELDS for rm in lv["rooms"])
          and all(f["room_id"] is None or f["room_id"] in {rm["id"] for rm in lv["rooms"]}
                  for f in lv["features"]) for lv in levels))
check("level: 매복몹(concealed) 포함 전수 노출(관전자 등급 진실)",
      all(any(m["concealed"] for m in lv["monsters"]) for lv in levels))
check("봇 스냅샷 필드 전수(level.party + tick.bots + end.bots)",
      all(set(b) == BOT_FIELDS
          for r in levels + ticks + [end]
          for b in r.get("party", r.get("bots", []))))
check("몹/함정/피처 스냅샷 필드 전수(level·tick 양쪽)",
      all(set(m) == MON_FIELDS for r in levels + ticks for m in r["monsters"])
      and all(set(t) == TRAP_FIELDS for r in levels + ticks for t in r["traps"])
      and all(set(f) == FEAT_FIELDS for r in ticks for f in r["features"])
      and all(set(f) == FEAT_FIELDS for r in levels for f in r["features"]))
check("tick: decisions 는 결정 봇만·type 보유 / 기본 실행엔 obs 없음",
      all(all(c in ("1", "2") and "type" in dec and "obs" not in dec
              for c, dec in t["decisions"].items()) for t in ticks))
check("tick: inbox 형태 고정 — 키 = 그 틱 파티 전원(첫 틱·강하 직후 포함)",
      all(set(t["inbox"]) == {b["char"] for b in t["bots"]} for t in ticks))
check("tick: 재결정 봇 이벤트에 reason·job 부착(속내 보존)",
      any("reason" in e and "job" in e for t in ticks for e in t["events"]))
check("몹 이벤트에 id 존재+바인딩(m<n>) — 기본값 우회 없는 존재 검사",
      all("id" in e and str(e["id"]).startswith("m")
          for t in ticks for e in t["events"]
          if str(e.get("type", "")).startswith("monster_")))
check("end: outcome 3종 + 명단 필드",
      end["outcome"] in ("escaped", "wiped", "timeout")
      and all(k in end for k in ("depth", "survivors", "fallen", "remaining", "bots")))

# ── ④ 원장 감사(base run) ──
viol, cov_base = audit(recs)
check("원장 감사(base): hp/bag/몹hp/전이/고아결정 위반 0", viol == 0)

# ── ⑥ 기존 소비자 교차(events.log 무손상) — 재실행으로 덮이기 전에 확인 ──
evlog = open(os.path.join(show_runner.STATE, "events.log"), encoding="utf-8").read()
check("교차: 강하 수 = events.log '계단을 내려선다' 수",
      evlog.count("일행은 어둠 속 계단을 내려선다") == len(descends))
marker = {"escaped": "돌파·탈출!!", "wiped": "파티 전멸", "timeout": "시간 종료"}
check("교차: end.outcome ↔ events.log 종료 문구 1:1", marker[end["outcome"]] in evlog)

# ── ⑤ 결정론: 2회 실행 → started 제외 완전 동일 ──
def normalized(text):
    ls = text.splitlines()
    head = json.loads(ls[0])
    head.pop("started", None)
    return [json.dumps(head, ensure_ascii=False, sort_keys=True)] + ls[1:]

raw2 = run_once()
check("결정론: 재실행 스트림 = 원본(started 제외, 라인 단위)",
      normalized(raw) == normalized(raw2))

# ── ⑦ 크기 sanity ──
check("크기 sanity(1KB < 스트림 < 5MB)", 1024 < len(raw.encode("utf-8")) < 5 * 1024 * 1024)
print("        (스트림 %d 라인, %.1f KB, tick %d개, outcome=%s)"
      % (len(lines), len(raw.encode("utf-8")) / 1024, len(ticks), end["outcome"]))

# ── ⑧ obs opt-in(DUNGEON_STREAM_OBS=1) — think 시점 캡처 동봉 ──
os.environ["DUNGEON_STREAM_OBS"] = "1"
raw3 = run_once()
os.environ.pop("DUNGEON_STREAM_OBS", None)
recs3 = [json.loads(l) for l in raw3.splitlines()]
ticks3 = [r for r in recs3 if r["kind"] == "tick"]
decs3 = [dec for t in ticks3 for dec in t["decisions"].values()]
check("obs opt-in: 모든 결정에 obs 동봉(pos·sights 보유) + run_meta.stream_obs=true",
      decs3 and all("obs" in d and "pos" in d["obs"] and "sights" in d["obs"]
                    for d in decs3)
      and recs3[0]["stream_obs"] is True)

# ── ⑨ timeout 분기 — end 3분기 중 seed7(escaped)이 안 밟는 가지를 짧은 한도로 강제 ──
show_runner.MAX_TURNS = 5
raw4 = run_once()
show_runner.MAX_TURNS = 400
recs4 = [json.loads(l) for l in raw4.splitlines()]
end4, t4 = recs4[-1], [r for r in recs4 if r["kind"] == "tick"]
check("timeout 분기: 한도 도달 → outcome=timeout·turn=한도·remaining 잔류",
      end4["kind"] == "end" and end4["outcome"] == "timeout"
      and end4["turn"] == 5 and len(t4) == 5 and end4["remaining"]
      and recs4[0]["max_turns"] == 5)

# ── ⑩ 다중 시드 원장 스윕 + 커버리지 — seed7 이 못 밟는 규칙(함정피해·상자·샘·전멸)까지 실발화 ──
agg = dict(cov_base)
sweep_viol, outcomes = 0, []
show_runner.N_MON, show_runner.N_TRAP = 6, 6      # 콘텐츠 밀도 ↑ → 피해·도박·전멸이 실제로 나온다
for s in range(1, 15):
    show_runner.DUNGEON_SEED = s
    recs_s = [json.loads(l) for l in run_once().splitlines()]
    v, cov_s = audit(recs_s)
    sweep_viol += v
    outcomes.append(recs_s[-1]["outcome"])
    for k, n in cov_s.items():
        agg[k] = agg.get(k, 0) + n
show_runner.DUNGEON_SEED, show_runner.N_MON, show_runner.N_TRAP = 7, 2, 3
REQUIRED = ["trap_dmg", "chest_trap", "chest_loot", "fountain_heal", "fountain_harm",
            "mon_dmg", "walk_treasure", "interact_treasure", "down", "killed", "exit_party"]
check("원장 스윕(시드 1..14·몹6·함정6): 위반 0", sweep_viol == 0)
check("커버리지: 원장 델타 규칙 전부 ≥1회 실발화(죽은 규칙 없음)",
      all(agg.get(k, 0) > 0 for k in REQUIRED))
check("스윕이 wiped(전멸) 결말도 커버", "wiped" in outcomes)
print("        (커버리지: " + ", ".join("%s=%d" % (k, agg.get(k, 0)) for k in REQUIRED)
      + " / skipped=%d)" % agg.get("skipped", 0))
print("        (스윕 outcomes: %s)" % sorted(set(outcomes)))

print()
if C.failed:
    print("FAILED: %d개 게이트 실패" % C.failed)
    raise SystemExit(1)
print("ALL PASS — 스트림(JSONL) 계약 건전. STREAM_FORMAT.md 가 데이터 계약.")

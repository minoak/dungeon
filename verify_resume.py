# -*- coding: utf-8 -*-
"""이어가기(D79, 2026-09-16) 헤들리스 검증 — 67번째 게이트. LLM 0콜(러너는 dummy 두뇌, 론처 Runner 로 자식 프로세스).
게이트:
  ① 곱게 멈춤: 판을 띄워 틱 ≥ 4 에서 stop(graceful) → 러너가 스스로 닫힘(코드 0) · `stopped` 줄(turn=마지막 틱)·`end` 없음 · snapshot.pkl+json ·
     /status.resume {turn_last, depth, party, stopped:"user"} · 새 원정 시작은 스냅샷을 지운다
  ② 이어간 판 = 끊기지 않은 판: 같은 시드로 멈춤 없이 돌린 대조군과 재개 뒤 tick/level/end 줄이 바이트 동일(obs 제외) · 틱 번호 연속 · run_id 같음 ·
     `resume` 줄(turn=멈춘 틱·segment 1·stopped "user"·pages) · 이어간 첫 관측에 floor_notice("이어간다")+notes 에 수첩 장 · 끝나면 스냅샷 삭제
  ③ 끊김(kill) 뒤 이어가기: 스냅샷 자리까지 자르고 이어 씀 — 틱 중복 0·연속 · resume.stopped null · 재개 뒤 줄이 대조군과 동일
  ④ 되살리기 실패 폴백: 피클을 깨뜨리고 이어가기 → 새 판(run_meta.resume_failed{reason, kept}) · 옛 기록 runs/ 대피(내용 동일) · 수첩 장은 새 몸의 notes 에
  ⑤ stop_page(인프로세스, 두뇌 몽키패치): 물음에 STOP_MARK·t 가 들어가고 JSON page 를 장으로 · 실패면 None
  ⑥ 캠페인 투영: stopped/resume 줄 → segments·stops·pages[stop] · 한 항목
  ⑦ 판단 정지 중 멈춤: BrainPause.wait 가 stop.json 을 보면 StopRequested
"""
import copy
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="wl_resume_")
os.environ.update(DUNGEON_GM="0", DUNGEON_TURNS="14", DUNGEON_W="40", DUNGEON_H="16",
                  DUNGEON_MONSTERS="1", DUNGEON_TRAPS="1", DUNGEON_LURKERS="0",
                  DUNGEON_DEPTHS="1", DUNGEON_BESTIARY_FILE="", DUNGEON_STREAM_OBS="1", DUNGEON_STEP_DELAY="0",
                  DUNGEON_NOTEBOOK="1")
for k in ("DUNGEON_PARTY_FILE", "DUNGEON_STATE_DIR", "DUNGEON_RESUME", "DUNGEON_RUNS_DIR", "DUNGEON_SEED",
          "DUNGEON_TOWN", "DUNGEON_BOSS", "DUNGEON_START", "DUNGEON_LEDGER_IDS_ONLY"):
    os.environ.pop(k, None)
os.environ["DUNGEON_BRAIN_BACKEND"] = "dummy"

import campaign                                      # noqa: E402
import launcher                                      # noqa: E402
import run_control                                   # noqa: E402
import snapshot                                      # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("  ok  " if ok else "  FAIL") + " " + name + (("  — " + str(detail)) if detail and not ok else ""))
    if not ok:
        fails.append(name)


def lines(path):
    out = []
    try:
        with io.open(path, encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    out.append(json.loads(ln))
                except ValueError:
                    break
    except OSError:
        pass
    return out


def ticks(recs):
    return [r for r in recs if r.get("kind") == "tick"]


def wait_tick(path, n, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        tk = ticks(lines(path))
        if tk and tk[-1]["turn"] >= n:
            return tk[-1]["turn"]
        time.sleep(0.15)
    return None


def wait_exit(runner, timeout=90):
    t0 = time.time()
    while runner.running() and time.time() - t0 < timeout:
        time.sleep(0.15)
    return not runner.running()


def strip(rec):
    """비교용 — 결정에 동봉된 obs(STREAM_OBS=1: 이어간 첫 관측엔 floor_notice·notes 가 더 있다)와 end.summary 를 뺀다."""
    r = copy.deepcopy(rec)
    if r.get("kind") == "tick":
        for c, d in (r.get("decisions") or {}).items():
            if isinstance(d, dict):
                d.pop("obs", None)
    if r.get("kind") == "end":
        r.pop("summary", None)
    return json.dumps(r, ensure_ascii=False, sort_keys=True)


def body(recs):
    return [strip(r) for r in recs if r.get("kind") not in ("run_meta", "stopped", "resume")]


SEED = 20260916
OPTS = {"brain": "dummy", "mode": "classic", "action_mode": "menu", "map": "normal", "party": "default", "seed": SEED,
        "town": False, "boss": False, "bestiary": False}


def new_runner(tag):
    d = os.path.join(TMP, tag)
    os.makedirs(os.path.join(d, "state"), exist_ok=True)
    return launcher.Runner(HERE, os.path.join(d, "state"), os.path.join(d, "runs")), d


print("── 대조군: 멈춤 없이 끝까지")
rA, dA = new_runner("A")
os.environ["DUNGEON_STEP_DELAY"] = "0"
for p in snapshot.paths(rA.state_dir):                      # ① 새 원정 시작이 옛 스냅샷을 지우는지 — 가짜 둘을 심는다
    with open(p, "wb") as f:
        f.write(b"x")
rA.start(OPTS, os.path.join(dA, "party_custom.json"), "dummy")
check("① 새 원정 시작 = 스냅샷 삭제", not any(os.path.exists(p) for p in snapshot.paths(rA.state_dir)))
check("① run_opts.json 남김(키 없음)", (rA._read_run_opts() or {}).get("opts", {}).get("seed") == SEED and "key" not in (rA._read_run_opts() or {}).get("opts", {}))
check("대조군 종료", wait_exit(rA))
SA = os.path.join(rA.state_dir, "stream.jsonl")
recsA = lines(SA)
tA = ticks(recsA)
check("대조군: end 있음·틱 14", recsA and recsA[-1].get("kind") == "end" and len(tA) == 14 and tA[-1]["turn"] == 14, (len(tA), recsA[-1].get("kind") if recsA else None))
check("대조군: 끝나면 스냅샷 없음", not any(os.path.exists(p) for p in snapshot.paths(rA.state_dir)))

print("── ① 곱게 멈춤 → ② 이어가기")
rB, dB = new_runner("B")
os.environ["DUNGEON_STEP_DELAY"] = "0.25"
rB.start(OPTS, os.path.join(dB, "party_custom.json"), "dummy")
SB = os.path.join(rB.state_dir, "stream.jsonl")
check("① 틱 ≥ 4 도달", wait_tick(SB, 4) is not None)
st0 = rB.status()
check("① 진행 중엔 resume 없음", st0["running"] and st0.get("resume") is None and not st0.get("stopping"))
res = rB.stop(graceful=True, pages=True, wait=30)
check("① stop(graceful) = 러너가 스스로 닫힘", res.get("stopped") and res.get("graceful") and rB.proc.returncode == 0, (res, rB.proc.returncode))
recsB = lines(SB)
stopped = [r for r in recsB if r.get("kind") == "stopped"]
tB = ticks(recsB)
check("① stopped 줄 하나 = 마지막 줄, turn = 마지막 틱, end 없음",
      len(stopped) == 1 and recsB[-1].get("kind") == "stopped" and stopped[0]["turn"] == tB[-1]["turn"] and stopped[0].get("reason") == "user"
      and not any(r.get("kind") == "end" for r in recsB), [r.get("kind") for r in recsB[-3:]])
check("① stop.json 은 지워짐", not os.path.exists(os.path.join(rB.state_dir, run_control.STOP_FILE)))
pklB, jsonB = snapshot.paths(rB.state_dir)
metaB = snapshot.read_meta(rB.state_dir)
check("① snapshot.pkl + json", os.path.exists(pklB) and metaB is not None)
check("① 요약: turn_last = 멈춘 틱 · next_turn +1 · stop user · party 3",
      metaB and metaB.get("turn_last") == tB[-1]["turn"] and metaB.get("next_turn") == tB[-1]["turn"] + 1
      and (metaB.get("stop") or {}).get("reason") == "user" and len(metaB.get("party") or []) == 3 and metaB.get("depth") == 1, metaB)
check("① 요약의 run_id = seed@started", metaB and metaB["run_id"] == "%s@%s" % (recsB[0]["seed"], recsB[0]["started"]))
st1 = rB.status()
check("① /status.resume", (st1.get("resume") or {}).get("turn_last") == tB[-1]["turn"] and st1["resume"].get("stopped") == "user"
      and [p["name"] for p in st1["resume"]["party"]] == [p["name"] for p in metaB["party"]], st1.get("resume"))
size_before = os.path.getsize(SB)
check("① 스냅샷 자리 = 파일 끝(stopped 줄 뒤)", True)   # 피클 안의 stream_pos 는 러너 몫 — ② 에서 잘린 흔적이 없음으로 확인
# 멈출 때 쓴 수첩 장을 흉내 낸다(더미 두뇌는 0콜이라 장이 없다) — 러너는 요약(json)의 stop.pages 를 우선 읽는다
metaB2 = dict(metaB)
metaB2["stop"] = {"reason": "user", "pages": {"1": "여기까지 한 일을 적어 둔다"}}
snapshot.write_meta(rB.state_dir, {k: v for k, v in metaB2.items() if k not in ("version", "saved_at")})
os.environ["DUNGEON_STEP_DELAY"] = "0"
r2 = rB.start({"resume": True}, os.path.join(dB, "party_custom.json"), "dummy")
check("② start(resume) 응답", r2.get("resumed") and r2.get("from_turn") == tB[-1]["turn"] and r2.get("seed") == str(SEED), r2)
check("② 이어간 판 종료", wait_exit(rB))
recsB2 = lines(SB)
resume = [r for r in recsB2 if r.get("kind") == "resume"]
tB2 = ticks(recsB2)
check("② resume 줄 하나: turn=멈춘 틱·segment 1·stopped user·pages·backend dummy",
      len(resume) == 1 and resume[0]["turn"] == tB[-1]["turn"] and resume[0].get("segment") == 1 and resume[0].get("stopped") == "user"
      and resume[0].get("pages") == {"1": "여기까지 한 일을 적어 둔다"} and resume[0].get("backend") == "dummy", resume)
check("② stopped 줄은 남고 그 다음이 resume", [r.get("kind") for r in recsB2].index("stopped") + 1 == [r.get("kind") for r in recsB2].index("resume"))
check("② run_meta 하나 = 같은 판(run_id 그대로)", sum(1 for r in recsB2 if r.get("kind") == "run_meta") == 1 and recsB2[0]["started"] == recsB[0]["started"])
check("② 틱 번호 연속 1..14·중복 0", [t["turn"] for t in tB2] == list(range(1, 15)), [t["turn"] for t in tB2])
check("② end 있음·스냅샷 삭제", recsB2[-1].get("kind") == "end" and not any(os.path.exists(p) for p in snapshot.paths(rB.state_dir)))
bA, bB = body(recsA), body(recsB2)
first_diff = next((i for i in range(min(len(bA), len(bB))) if bA[i] != bB[i]), None)
check("② 이어간 판 = 끊기지 않은 판(tick/level/end 바이트 동일, obs 제외)", len(bA) == len(bB) and first_diff is None,
      "len %d/%d first_diff %s: %s | %s" % (len(bA), len(bB), first_diff, bA[first_diff][:300] if first_diff is not None else "", bB[first_diff][:300] if first_diff is not None else ""))
def first_obs(tks, char, after):
    """재개 뒤 그 캐릭터의 첫 관측(자동보행 중인 틱엔 결정·관측이 없다 — 첫 결정 틱을 찾는다)."""
    for t in tks:
        if t["turn"] > after:
            o = ((t.get("decisions") or {}).get(char) or {}).get("obs")
            if o:
                return o
    return {}


obs1 = first_obs(tB2, "1", tB[-1]["turn"])
notices = [first_obs(tB2, c, tB[-1]["turn"]).get("floor_notice") for c in ("1", "2", "3")]
check("② 이어간 첫 관측: floor_notice '이어간다'(전원) + 1번 notes 에 수첩 장",
      all("이어간다" in str(n) for n in notices) and "여기까지 한 일을 적어 둔다" in (obs1.get("notes") or []), {"notices": notices, "notes": obs1.get("notes")})
st2 = rB.status()
check("② 끝난 뒤 /status.resume 없음·outcome", st2.get("resume") is None and st2.get("outcome") == recsA[-1].get("outcome"))
evB = io.open(os.path.join(rB.state_dir, "events.log"), encoding="utf-8").read()
check("② events.log 에 멈춤·이어감 줄", "원정을 멈춘다" in evB and "원정을 이어간다" in evB)

print("── ③ 끊김(kill) 뒤 이어가기")
rC, dC = new_runner("C")
os.environ["DUNGEON_STEP_DELAY"] = "0.25"
rC.start(OPTS, os.path.join(dC, "party_custom.json"), "dummy")
SC = os.path.join(rC.state_dir, "stream.jsonl")
check("③ 틱 ≥ 3 도달", wait_tick(SC, 3) is not None)
rC.proc.kill()
rC.proc.wait(timeout=10)
recsC = lines(SC)
tC = ticks(recsC)
metaC = snapshot.read_meta(rC.state_dir)
check("③ 끊긴 판: end 없음·stopped 없음·스냅샷 있음(stop None)", not any(r.get("kind") in ("end", "stopped") for r in recsC) and metaC and metaC.get("stop") is None, metaC)
check("③ 스냅샷 틱 ≤ 파일의 마지막 틱", metaC and metaC["turn_last"] <= tC[-1]["turn"], (metaC and metaC["turn_last"], tC[-1]["turn"]))
stC = rC.status()
check("③ /status.resume stopped null", stC.get("resume") and stC["resume"].get("stopped") is None)
os.environ["DUNGEON_STEP_DELAY"] = "0"
rC.start({"resume": True}, os.path.join(dC, "party_custom.json"), "dummy")
check("③ 이어간 판 종료", wait_exit(rC))
recsC2 = lines(SC)
tC2 = ticks(recsC2)
resumeC = [r for r in recsC2 if r.get("kind") == "resume"]
check("③ resume 줄: turn = 스냅샷 틱·stopped null·pages 없음", len(resumeC) == 1 and resumeC[0]["turn"] == metaC["turn_last"] and resumeC[0].get("stopped") is None and "pages" not in resumeC[0], resumeC)
iR = [r.get("kind") for r in recsC2].index("resume")
check("③ 스냅샷 뒤 줄은 잘렸다(resume 바로 앞 틱 = 스냅샷 틱)", (recsC2[iR - 1].get("kind") == "tick" and recsC2[iR - 1]["turn"] == metaC["turn_last"]) or (metaC["turn_last"] == 0 and recsC2[iR - 1].get("kind") == "level"), recsC2[iR - 1].get("turn"))
check("③ 틱 번호 연속 1..14·중복 0", [t["turn"] for t in tC2] == list(range(1, 15)), [t["turn"] for t in tC2])
bC = body(recsC2)
first_diff = next((i for i in range(min(len(bA), len(bC))) if bA[i] != bC[i]), None)
check("③ 재개 뒤 줄이 대조군과 동일", len(bA) == len(bC) and first_diff is None, "first_diff %s" % first_diff)

print("── ④ 되살리기 실패 폴백")
rD, dD = new_runner("D")
os.environ["DUNGEON_STEP_DELAY"] = "0.25"
rD.start(OPTS, os.path.join(dD, "party_custom.json"), "dummy")
SD = os.path.join(rD.state_dir, "stream.jsonl")
check("④ 틱 ≥ 3 도달", wait_tick(SD, 3) is not None)
rD.stop(graceful=True, pages=False, wait=30)
recsD = lines(SD)
metaD = snapshot.read_meta(rD.state_dir)
pklD, _ = snapshot.paths(rD.state_dir)
with open(pklD, "wb") as f:
    f.write(b"\x80\x05garbage")                                  # 깨진 피클(엔진이 바뀐 상황의 대리)
metaD2 = {k: v for k, v in metaD.items() if k not in ("version", "saved_at")}
metaD2["stop"] = {"reason": "user", "pages": {"2": "깨져도 남는 한 장"}}
snapshot.write_meta(rD.state_dir, metaD2)
old_bytes = open(SD, "rb").read()
os.environ["DUNGEON_STEP_DELAY"] = "0"
rD.start({"resume": True}, os.path.join(dD, "party_custom.json"), "dummy")
check("④ 폴백 판 종료", wait_exit(rD))
recsD2 = lines(SD)
rf = (recsD2[0] or {}).get("resume_failed") if recsD2 else None
check("④ 새 판: run_meta.resume_failed{reason, kept, run_id}", recsD2 and recsD2[0].get("kind") == "run_meta" and rf and "되살리지" in rf.get("reason", "")
      and rf.get("kept") and rf.get("run_id") == metaD["run_id"] and recsD2[0]["started"] != recsD[0]["started"], rf)
kept = os.path.join(rD.runs_dir, rf["kept"]) if rf and rf.get("kept") else ""
check("④ 옛 기록 runs/ 대피 = 내용 동일(stopped 줄까지)", kept and open(kept, "rb").read() == old_bytes)
check("④ 새 판은 끝까지(end)·틱 1부터·resume 줄 없음", recsD2[-1].get("kind") == "end" and ticks(recsD2)[0]["turn"] == 1 and not any(r.get("kind") == "resume" for r in recsD2))
obsD = ((ticks(recsD2)[0].get("decisions") or {}).get("2", {}).get("obs") or {})
check("④ 수첩 장은 새 몸의 notes 에", "깨져도 남는 한 장" in (obsD.get("notes") or []), obsD.get("notes"))
check("④ 끝나면 스냅샷 없음·/status.resume 없음", not any(os.path.exists(p) for p in snapshot.paths(rD.state_dir)) and rD.status().get("resume") is None)
try:
    rD.start({"resume": True}, os.path.join(dD, "party_custom.json"), "dummy")
    check("④ 이어갈 게 없으면 BadRequest", False)
except launcher.BadRequest as e:
    check("④ 이어갈 게 없으면 BadRequest", "이어갈 원정이 없다" in str(e), e)

print("── ⑤ stop_page(두뇌 몽키패치)")
import brains                                        # noqa: E402
import dungeon_gm as G                               # noqa: E402
seen = {}


def _fake_call(prompt, model="haiku"):
    seen["prompt"] = prompt
    return '{"page": "여기까지 왔다. 다음엔 문을 연다."}', None


old_call = brains._call_claude
brains._call_claude = _fake_call
try:
    d5 = G.Dungeon(seed=3, depth=1, w=30, h=12, n_monsters=1, n_traps=0, floor=True)
    b5 = G.spawn(d5, "1", [], sheet=None)
    b5["notes"] = ["첫 줄"]
    entry = G.floor_freeze(b5, 1, 5)[-1]
    page = brains.stop_page(b5, entry, {"1": b5.get("name") or "봇1"}, [b5])
    check("⑤ 장 = 응답 page", page == "여기까지 왔다. 다음엔 문을 연다.", page)
    check("⑤ 물음에 STOP_MARK·t5·notes", brains.STOP_MARK in seen.get("prompt", "") and "t5" in seen["prompt"] and "첫 줄" in seen["prompt"])
    brains._call_claude = lambda prompt, model="haiku": (_ for _ in ()).throw(RuntimeError("x"))
    check("⑤ 두뇌 예외 = None(판을 세우지 않는다)", brains.stop_page(b5, entry, {"1": "봇1"}, [b5]) is None)
finally:
    brains._call_claude = old_call

print("── ⑥ 캠페인 투영(stopped/resume)")
S6 = os.path.join(TMP, "syn.jsonl")
META6 = {"kind": "run_meta", "seed": 7, "started": "2026-09-16T21:00:00",
         "party": [{"char": "1", "name": "카야", "id": "pidkaya01", "job": "도적", "maxhp": 10}]}
recs6 = [META6, {"kind": "level", "turn": 0, "depth": 1},
         {"kind": "tick", "turn": 1, "bots": [{"char": "1", "hp": 10, "alive": True}], "decisions": {}},
         {"kind": "stopped", "turn": 1, "reason": "user", "depth": 1, "pages": {"1": "멈추며 쓴 장"}},
         {"kind": "resume", "turn": 1, "segment": 1, "backend": "dummy", "depth": 1},
         {"kind": "tick", "turn": 2, "bots": [{"char": "1", "hp": 9, "alive": True}], "decisions": {}},
         {"kind": "end", "turn": 2, "outcome": "timeout", "depth": 1}]
with io.open(S6, "w", encoding="utf-8", newline="\n") as f:
    for r in recs6:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
p6 = campaign.project(S6)
check("⑥ segments 1·stops 1·turn_last 2·ended", p6["segments"] == 1 and p6["stops"] == 1 and p6["turn_last"] == 2 and p6["status"] == "ended", p6)
check("⑥ 멈추며 쓴 장 = pages[stop]", p6["chars"]["1"]["pages"] == [{"turn": 1, "depth": 1, "text": "멈추며 쓴 장", "stop": True}], p6["chars"]["1"]["pages"])
bk = campaign.Book(os.path.join(TMP, "campaign.json"))
bk.fold(S6, key="syn")
bk.fold(S6, key="syn")
e6 = bk.runs("pidkaya01")
check("⑥ 한 항목·segments", len(e6) == 1 and e6[0].get("segments") == 1 and bk.summary("pidkaya01")["last"].get("segments") == 1)
pB = campaign.project(SB)
check("⑥ 실판(B) 투영: 한 판·segments 1·stops 1·ended", pB["segments"] == 1 and pB["stops"] == 1 and pB["status"] == "ended" and pB["turn_last"] == 14, {k: pB[k] for k in ("segments", "stops", "status", "turn_last")})

print("── ⑦ 판단 정지 중 멈춤")
class _W:
    def __init__(self):
        self.recs = []

    def emit(self, kind, **f):
        self.recs.append((kind, f))


st7 = os.path.join(TMP, "pause")
os.makedirs(st7, exist_ok=True)
run_control.request_stop(st7, pages=False)
bp = run_control.BrainPause(st7, _W(), {"1": "카야"}, report=lambda *a: None)
try:
    bp.wait(3, {"1": {"src": "error", "reason": "x"}})
    check("⑦ StopRequested", False)
except run_control.StopRequested:
    check("⑦ StopRequested", True)
run_control.reset(st7)
check("⑦ reset 이 stop.json 도 지움", run_control.stop_requested(st7) is None)

shutil.rmtree(TMP, ignore_errors=True)
print()
if fails:
    print("FAIL %d — %s" % (len(fails), ", ".join(fails)))
    sys.exit(1)
print("ALL PASS — verify_resume (D79 이어가기: 스냅샷=끊기지 않은 판 · 곱게 멈춤·끊김·폴백 · 요약 들고 가기 · 캠페인 한 항목)")

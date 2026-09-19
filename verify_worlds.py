# -*- coding: utf-8 -*-
"""D84 조각 2 — 세계마다 제 시계: 계단을 쓴 무리만 옮기고, 남은 사람의 세계는 계속 흐른다 — 71번째 게이트. LLM 0콜.
(2026-09-18 파트너 "세계의 시간은 다중 접속인원이 생길 때 완전히 달라지지 않아? 차라리 마을/던전 이렇게 나누는 편이 좋지 않아?" →
 "마을은 마을의 시계로, 던전은 던전의 시계로 — 사람이 있는 세계는 다 흐른다" · 09-19 러너 틱 루프 수술)
러너 스위치 DUNGEON_PARTYFORM(기본 0, 마을 판만). 스위치 0 = 세계 하나 = 옛 판과 비트까지 같다(같은 틱 몸통을 세계 하나로 도는 것 —
기존 게이트 70종이 그 몸통 위에서 돈다). 여기는 스위치 1 의 새 길을 본다. 각본 = 더미 두뇌 + 파티 장부를 미리 맺어 둔 판(맺는 동사는 조각 3).
게이트:
  ① 스위치: 기본은 꺼짐 · 마을 판이 아니면 켜도 꺼짐 · 끈 판엔 옆 파일·run_meta.partyform·지문 열쇠가 없다(서브프로세스)
  ② 내 캐릭터의 파티가 먼저 내려가는 판(파티 {1,2} + 혼자인 3): 본 스트림이 파티를 따라간다(descend+level) · 마을은 3 혼자 남은 채
     계속 틱(옆 파일 world=0 — 판단도 계속 받는다) · 3 이 혼자 내려오면 같은 1층에 합류(arrive, 새 level 없음 · 다음 틱부터 tick.bots) ·
     합류는 그 세계의 편지함을 지우지 않는다 · 3 이 먼저 2층으로(depart · 옆 파일에 level world=2) · 파티가 2층에서 다시 합류(level.party 에 셋) ·
     비어 버린 세계는 멈춘다
  ③ 불변식: 본 스트림 틱은 1..N 연속·틱당 하나 · 산 사람은 매 틱 정확히 한 세계에(두 번 움직이는 사람 없음 · 빠지는 사람 없음) ·
     합류한 자리는 서로 다른 칸 · 판 끝 집계는 모든 세계의 사람을 센다
  ④ 내 캐릭터가 마을에 남는 판(파티 {2,3} + 혼자인 1): 본 스트림은 마을에 남는다(depart · tick.bots = [1]) · 떠난 파티는 옆 파일에
     (descend·level world=1·tick) · 1 이 내려가면 본 스트림이 1층으로 옮겨 가 셋이 다시 보인다
  ⑤ 끊김 → 이어가기: 세계가 둘일 때(본·옆 파일이 둘 다 스냅샷보다 한 틱 앞선 채) 죽은 러너를 스냅샷에서 되살리면 끊기지 않은 판과 같은 길을 간다
     (본·옆 파일의 틱별 위치가 같다 · 옆 파일에 같은 틱이 두 번 적히지 않는다 · 끝이 같다)
  ⑥ 배선(소스·문서): 스위치·옆 파일·additive 줄(depart/arrive)·스냅샷 열쇠가 문서에 있다
  ⑦ 층을 옮겨도 도감 지식은 발급기와 같은 객체(09-19 수선 — 전이가 이름으로 묶어 저장 캐릭터(id)가 첫 계단에서 지식을 잃던 것)
  ⑧ 조각 3 — 미리 맺지 않은 판: 각본이 길드 구역에 가서 파티 결성을 청하고 맞받아 맺은 뒤 내려간다(party_asked → party_formed →
     둘만 하강 · 3 은 마을에 남는다 · 명단 = 내 파티원만: 파티 밖의 3 에게는 떠난 둘의 이름·행방이 자동으로 실리지 않는다)
(기존 verify 70종은 별도 실행.)
"""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = tempfile.mkdtemp(prefix="wl_worlds_")
STATE = os.path.join(ROOT, "state")
os.makedirs(STATE, exist_ok=True)
BASE_ENV = dict(DUNGEON_GM="0", DUNGEON_STEP_DELAY="0", DUNGEON_TURNS="420", DUNGEON_W="40", DUNGEON_H="16",
                DUNGEON_DEPTHS="2", DUNGEON_SEED="7", DUNGEON_MONSTERS="0", DUNGEON_TRAPS="0", DUNGEON_LURKERS="0",
                DUNGEON_BESTIARY_FILE="", DUNGEON_PARTY_FILE=os.path.join(HERE, "party.json"), DUNGEON_STATE_DIR=STATE,
                DUNGEON_TOWN="1", DUNGEON_BRAIN_BACKEND="dummy", DUNGEON_BOSS="0", DUNGEON_RUNS_DIR=os.path.join(ROOT, "runs"),
                DUNGEON_ACTION_MODE="compose", DUNGEON_PARTYFORM="1", DUNGEON_STREAM_OBS="1")
os.environ.update(BASE_ENV)
for k in ("DUNGEON_QUESTS", "DUNGEON_TOWN_APART", "DUNGEON_NPC_BRAIN", "DUNGEON_SOLO", "DUNGEON_START", "DUNGEON_MENU", "DUNGEON_RESUME"):
    os.environ.pop(k, None)

import brains                                        # noqa: E402
brains._call_claude = lambda prompt, model="haiku": ""   # LLM 무력화 → dummy 폴백(결정론)
import dungeon_gm as G                               # noqa: E402
import show_runner                                   # noqa: E402
import snapshot                                      # noqa: E402
import time as _time                                 # noqa: E402
_time.sleep = lambda s: None
show_runner.STEP_DELAY = 0


class C:
    failed = 0


def check(name, ok, detail=""):
    print("  %s %s%s" % ("OK  " if ok else "FAIL", name, (" — " + str(detail)) if (detail and not ok) else ""))
    if not ok:
        C.failed += 1


def rows(name):
    p = os.path.join(STATE, name)
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


_new_parties, _dummy = G.new_parties, G.dummy_brain


def play(party, crash_at=None, resume=False, say_at=None, form=False):
    """각본 판 하나 — party(미리 맺어 둔 파티)와 혼자인 한 사람. 혼자인 사람은 t120 까지 마을에 머물고, 파티는 1층에서 그 사람이
    보일 때까지(늦어도 t260) 머문다 — 세계가 갈라졌다 합쳐지는 장면을 만든다. 각본은 관측만 읽는다(이어가기에도 같은 길)."""
    loner = next(c for c in ("1", "2", "3") if c not in party)

    def preset():
        p = _new_parties()
        if not form:                                 # form=True 면 빈 장부 — 각본이 길드에서 직접 맺는다(조각 3)
            G.party_join(p, party)
            G.party_join(p, [loner])                 # 조각 4: 던전 입구는 파티를 맺은 사람만 — 혼자인 사람은 '한 사람짜리 무리'로 세워 둔다(세계가 갈라졌다 합쳐지는 장면용 장치)
        return p

    def scripted(obs, char="?"):
        t = obs.get("turn", 0)
        pf = obs.get("partyform") or {}
        if form and char in party and obs.get("town") and not pf.get("mine"):   # 아직 파티가 없다 — 길드 구역으로 가서 청하고 맞받는다
            mate = next(c for c in party if c != char)
            if pf.get("here") and obs.get("town_zone") == "모험가 길드 지구":   # 조각 4 부터 주점도 맺는 곳 — 각본은 길드에서 만나기로 한다(주점에서 시작한 사람이 거기서 기다리면 엇갈린다)
                seen = any(b.get("char") == mate for b in obs["sights"].get("bots") or [])
                if seen and mate not in (pf.get("asks_out") or []):
                    return {"type": "party_form", "target": "b" + mate}
                return {"type": "search"}
            guild = next((f for f in obs["sights"]["features"] if f["type"] == "building" and f["name"] == "모험가 길드"), None)
            if guild:
                return {"type": "goto", "target": guild["id"]}
        if char == loner and obs.get("town") and t < 120:
            return {"type": "search"}
        if (char in party and obs.get("depth") == 1 and t < 260
                and not any(b.get("char") == loner for b in obs["sights"].get("bots") or [])):
            return {"type": "search"}
        return _dummy(obs, char)

    real_dd = brains._dummy_decision

    def talking(obs, char, why="테스트"):            # 더미 결정은 say 를 비운다 — 합류 틱의 한마디는 그 뒤에 얹는다(둘 다 제자리 search 중이라 길은 안 바뀐다)
        fb = real_dd(obs, char, why)
        if say_at is not None and obs.get("turn") == say_at and char == party[0]:
            fb.update(say="여기 뭔가 있다", to=party[1])
        return fb

    real_snap = show_runner._take_snapshot

    def crashing(sw, core, meta):                    # 다음 틱 머리의 스냅샷 직전에 죽는다 — 본·옆 파일 둘 다 마지막 스냅샷보다 한 틱 앞서 있다
        if crash_at is not None and core["next_turn"] == crash_at + 1:
            raise RuntimeError("crash")
        return real_snap(sw, core, meta)

    G.new_parties, G.dummy_brain, show_runner._take_snapshot, brains._dummy_decision = preset, scripted, crashing, talking
    show_runner.RESUME_PATH = snapshot.paths(STATE)[0] if resume else ""
    crashed = False
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                show_runner.main()
            except SystemExit:
                pass
            except RuntimeError as e:
                crashed = str(e) == "crash"
    finally:
        G.new_parties, G.dummy_brain, show_runner._take_snapshot, brains._dummy_decision = _new_parties, _dummy, real_snap, real_dd
        show_runner.RESUME_PATH = ""
    return rows("stream.jsonl"), rows("stream_side.jsonl"), crashed


def ticks(rs, world="any"):
    return [r for r in rs if r["kind"] == "tick" and (world == "any" or r.get("world") == world)]


def chars(rec):
    return sorted(b["char"] for b in rec["bots"])


def trace(rs):
    """틱별 위치 — 끊긴 판과 끊기지 않은 판이 같은 길을 갔나(관측 문장·resume 줄은 빼고 몸만)."""
    return [(r["turn"], r.get("world"), [(b["char"], b["x"], b["y"], b["hp"], b["alive"], b["won"]) for b in r["bots"]])
            for r in rs if r["kind"] == "tick"]


print("── ① 스위치")
def probe(env):
    e = {k: v for k, v in os.environ.items() if not k.startswith("DUNGEON_")}
    e.update(PYTHONUTF8="1", **env)
    code = ("import json, os, show_runner as s; s.time.sleep = lambda x: None; print(json.dumps({'on': s.PARTYFORM_ON, 'fp': 'partyform' in s._world_fingerprint()}));"
            "\nif os.environ.get('RUN'): s.main()")
    p = subprocess.run([sys.executable, "-c", code], cwd=HERE, env=e, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return json.loads(p.stdout.splitlines()[0]) if p.returncode == 0 and p.stdout.strip() else {"err": p.stderr[-300:]}
off_dir = os.path.join(ROOT, "off")
os.makedirs(off_dir)
off_env = {k: v for k, v in BASE_ENV.items() if k != "DUNGEON_PARTYFORM"}
p_off = probe({**off_env, "DUNGEON_STATE_DIR": off_dir, "DUNGEON_TURNS": "40", "RUN": "1"})
p_notown = probe({**BASE_ENV, "DUNGEON_TOWN": "0", "DUNGEON_STATE_DIR": off_dir})
p_on = probe({**BASE_ENV, "DUNGEON_STATE_DIR": off_dir})
check("① 기본은 꺼짐(지문 열쇠도 없음) · 마을 판이 아니면 켜도 꺼짐 · 마을 판에서 켜면 켜짐(지문 열쇠 있음)",
      p_off == {"on": False, "fp": False} and p_notown == {"on": False, "fp": False} and p_on == {"on": True, "fp": True},
      (p_off, p_notown, p_on))
with open(os.path.join(off_dir, "stream.jsonl"), encoding="utf-8") as f:
    off_meta = json.loads(f.readline())
check("① 끈 판: 옆 파일이 안 생긴다 · run_meta 에 partyform 열쇠가 없다",
      not os.path.exists(os.path.join(off_dir, "stream_side.jsonl")) and "partyform" not in off_meta and off_meta.get("town") is True)

print("── ② 내 캐릭터의 파티가 먼저 내려가는 판(파티 {1,2} + 혼자인 3)")
main, side, _ = play(["1", "2"])
meta, end = main[0], main[-1]
desc = [r for r in main if r["kind"] == "descend"]
lvls = [r for r in main if r["kind"] == "level"]
arr = [r for r in main if r["kind"] == "arrive"]
dep = [r for r in main if r["kind"] == "depart"]
check("② run_meta.partyform True · 첫 하강은 파티 둘만(본 스트림 descend → level depth 1, party = [1,2])",
      meta.get("partyform") is True and desc and [p["char"] for p in desc[0]["party"]] == ["1", "2"]
      and lvls[1]["depth"] == 1 and sorted(p["char"] for p in lvls[1]["party"]) == ["1", "2"])
t_down = desc[0]["turn"]
town_after = [r for r in ticks(side, 0) if r["turn"] > t_down]
check("② 마을은 3 혼자 남은 채 계속 흐른다 — 옆 파일 world=0 틱이 하강 다음 틱부터 끊김 없이 · 3 은 그동안 판단을 계속 받는다",
      town_after and [r["turn"] for r in town_after] == list(range(t_down + 1, t_down + 1 + len(town_after)))
      and all(chars(r) == ["3"] for r in town_after) and sum(1 for r in town_after if "3" in (r.get("decisions") or {})) >= len(town_after) // 2,
      (t_down, len(town_after)))
s_desc = [r for r in side if r["kind"] == "descend"]
check("② 3 이 혼자 내려온다(옆 파일 descend world=0, party=[3]) → 같은 1층에 합류: 본 스트림 arrive(from_depth 0, [3]) · 그 틱에 새 level 없음 · 다음 틱부터 tick.bots 에 셋",
      s_desc and s_desc[0]["world"] == 0 and [p["char"] for p in s_desc[0]["party"]] == ["3"]
      and arr and arr[0]["turn"] == s_desc[0]["turn"] and arr[0]["from_depth"] == 0 and [p["char"] for p in arr[0]["party"]] == ["3"]
      and not any(r["turn"] == arr[0]["turn"] for r in lvls)
      and chars(next(r for r in ticks(main) if r["turn"] == arr[0]["turn"] + 1)) == ["1", "2", "3"])
check("② 3 이 떠난 뒤 마을은 멈춘다(비어 버린 세계 — 그 뒤 world=0 틱 없음)", not any(r["turn"] > s_desc[0]["turn"] for r in ticks(side, 0)))
main_s, _side_s, _ = play(["1", "2"], say_at=arr[0]["turn"])
arr_s = [r for r in main_s if r["kind"] == "arrive"]
heard = next((r for r in ticks(main_s) if arr_s and r["turn"] == arr_s[0]["turn"] + 1), {}).get("inbox") or {}
check("② 합류는 그 세계의 편지함을 지우지 않는다 — 합류 틱에 1 이 2 에게 한 말이 다음 틱 2 의 편지함에 · 온 사람(3) 몫은 빈 채로 생긴다",
      arr_s and arr_s[0]["turn"] == arr[0]["turn"] and any(m.get("from") == "1" and m.get("text") == "여기 뭔가 있다" for m in heard.get("2") or [])
      and heard.get("3") == [], {k: v for k, v in heard.items()})
joined = next(r for r in ticks(main) if r["turn"] == arr[0]["turn"] + 1)
check("② 합류한 자리는 서로 다른 칸", len({(b["x"], b["y"]) for b in joined["bots"]}) == 3)
side_lv = [r for r in side if r["kind"] == "level"]
check("② 3 이 먼저 2층으로: 본 스트림 depart(to_depth 2, down, [3]) · 옆 파일에 level world=2 · 그 뒤 2층 틱은 옆 파일에, 본 스트림엔 [1,2]",
      dep and dep[0]["to_depth"] == 2 and dep[0]["dir"] == "down" and dep[0]["party"] == ["3"]
      and side_lv and side_lv[0]["world"] == 2 and side_lv[0]["depth"] == 2 and [p["char"] for p in side_lv[0]["party"]] == ["3"]
      and chars(next(r for r in ticks(main) if r["turn"] == dep[0]["turn"] + 1)) == ["1", "2"]
      and any(r["turn"] == dep[0]["turn"] + 1 and chars(r) == ["3"] for r in ticks(side, 2)))
check("② 파티가 2층에서 다시 합류: 본 스트림 level depth 2 의 party 에 셋(그 세계에 있는 사람 전부)",
      lvls[-1]["depth"] == 2 and sorted(p["char"] for p in lvls[-1]["party"]) == ["1", "2", "3"])

print("── ③ 불변식")
mt = [r["turn"] for r in ticks(main)]
check("③ 본 스트림 틱은 1..N 연속 · 틱당 하나", mt == list(range(1, len(mt) + 1)) and len(mt) == end["turn"], (len(mt), end.get("turn")))
where = {}
for r in ticks(main) + ticks(side):
    for b in r["bots"]:
        where.setdefault((r["turn"], b["char"]), []).append(r.get("world"))
check("③ 산 사람은 매 틱 정확히 한 세계에 — 두 번 움직인 사람 없음 · 빠진 사람 없음",
      all(len(v) == 1 for v in where.values()) and all((t, c) in where for t in mt for c in ("1", "2", "3")),
      [k for k, v in where.items() if len(v) != 1][:5])
check("③ 판 끝 집계는 모든 세계의 사람을 센다(survivors + remaining + fallen = 셋)",
      sorted((end.get("survivors") or []) + (end.get("remaining") or []) + (end.get("fallen") or [])) == ["1", "2", "3"], end)

print("── ④ 내 캐릭터가 마을에 남는 판(파티 {2,3} + 혼자인 1)")
main4, side4, _ = play(["2", "3"])
dep4 = [r for r in main4 if r["kind"] == "depart"]
desc4 = [r for r in main4 if r["kind"] == "descend"]
lv4 = [r for r in main4 if r["kind"] == "level"]
check("④ 파티가 떠나도 본 스트림은 마을에 남는다: depart([2,3], to_depth 1) · 그 틱에 본 스트림 descend·level 없음 · 다음 틱 tick.bots = [1]",
      dep4 and dep4[0]["party"] == ["2", "3"] and dep4[0]["to_depth"] == 1
      and not any(r["turn"] == dep4[0]["turn"] for r in desc4 + lv4)
      and chars(next(r for r in ticks(main4) if r["turn"] == dep4[0]["turn"] + 1)) == ["1"])
s4_desc = [r for r in side4 if r["kind"] == "descend"]
s4_lv = [r for r in side4 if r["kind"] == "level"]
check("④ 떠난 파티는 옆 파일에: descend(world 0) → level(world 1, party [2,3]) → 1층 틱이 다음 틱부터",
      s4_desc and s4_desc[0]["world"] == 0 and s4_lv and s4_lv[0]["world"] == 1 and sorted(p["char"] for p in s4_lv[0]["party"]) == ["2", "3"]
      and any(r["turn"] == dep4[0]["turn"] + 1 and chars(r) == ["2", "3"] for r in ticks(side4, 1)))
check("④ 1 이 내려가면 본 스트림이 1층으로 옮겨 간다: descend([1]) → level depth 1 의 party 에 셋 · 그 뒤 1층 틱은 본 스트림에만",
      desc4 and [p["char"] for p in desc4[0]["party"]] == ["1"] and lv4[1]["depth"] == 1
      and sorted(p["char"] for p in lv4[1]["party"]) == ["1", "2", "3"]
      and not any(r["turn"] > desc4[0]["turn"] and r["turn"] <= desc4[0]["turn"] + 5 for r in ticks(side4, 1)))
mt4 = [r["turn"] for r in ticks(main4)]
check("④ 본 스트림 틱 연속", mt4 == list(range(1, len(mt4) + 1)))

print("── ⑤ 끊김 → 이어가기(세계가 둘일 때)")
CRASH = t_down + 40                                  # 파티는 1층, 3 은 마을 — 세계가 둘
main_c, side_c, crashed = play(["1", "2"], crash_at=CRASH)
check("⑤ 각본대로 죽었다 — 본·옆 파일 둘 다 그 틱까지 적혔다(스냅샷은 그 틱 머리의 것) · 스냅샷이 남았다",
      crashed and ticks(main_c)[-1]["turn"] == CRASH and ticks(side_c)[-1]["turn"] == CRASH
      and snapshot.read_meta(STATE).get("next_turn") == CRASH
      and os.path.exists(snapshot.paths(STATE)[0]), (crashed, ticks(main_c)[-1]["turn"] if ticks(main_c) else None))
main_r, side_r, _ = play(["1", "2"], resume=True)
res = [r for r in main_r if r["kind"] == "resume"]
check("⑤ 되살아났다(resume 줄 · 폴백 아님) · 끊긴 틱부터 다시",
      len(res) == 1 and res[0]["turn"] == CRASH - 1 and "resume_failed" not in main_r[0], res[:1])
check("⑤ 끊기지 않은 판과 같은 길: 본 스트림의 틱별 위치가 같다", trace(main_r) == trace(main))
check("⑤ 옆 파일도 같다 — 같은 틱이 두 번 적히지 않는다", trace(side_r) == trace(side)
      and len({(r["turn"], r["world"]) for r in ticks(side_r)}) == len(ticks(side_r)))
check("⑤ 끝이 같다", {k: main_r[-1].get(k) for k in ("kind", "turn", "outcome", "depth", "survivors", "remaining", "fallen")}
      == {k: end.get(k) for k in ("kind", "turn", "outcome", "depth", "survivors", "remaining", "fallen")})

print("── ⑦ 층을 옮겨도 도감 지식은 발급기와 같은 객체(저장 캐릭터 — 09-19 수선)")
import bestiary                                      # noqa: E402
with open(os.path.join(HERE, "party.json"), encoding="utf-8") as f:
    party7 = json.load(f)
party7["1"]["id"] = "hero7saved"                     # 1번만 저장 캐릭터(D78 원장 키 = id) — 나머지는 이름이 키
pf7 = os.path.join(ROOT, "party7.json")
with open(pf7, "w", encoding="utf-8") as f:
    json.dump(party7, f, ensure_ascii=False)
cap = {"iss": None, "bots": []}
_init7, _spawn7, _pf7 = bestiary.Issuer.__init__, G.spawn, show_runner.PARTY_FILE
def init7(self, *a, **k):
    _init7(self, *a, **k)
    cap["iss"] = self
def spawn7(d, char, bots, **k):
    b = _spawn7(d, char, bots, **k)
    cap["bots"].append((d.depth, b))
    return b
bestiary.Issuer.__init__, G.spawn, show_runner.PARTY_FILE = init7, spawn7, pf7
try:
    play(["1", "2"])
finally:
    bestiary.Issuer.__init__, G.spawn, show_runner.PARTY_FILE = _init7, _spawn7, _pf7
iss7 = cap["iss"]
mine = [(dep, b) for dep, b in cap["bots"] if b["char"] == "1"]
check("⑦ 1번(id 있음)은 마을·1층·2층 어느 몸이든 known·book 이 발급기의 id 키 객체 그대로 · 이름 키로 새 장부가 생기지 않는다",
      iss7 is not None and sorted({dep for dep, _ in mine}) == [0, 1, 2]
      and all(b.get("known") is iss7.known("hero7saved") and b.get("book") is iss7.record("hero7saved") for _, b in mine)
      and party7["1"]["name"] not in iss7.book, (sorted(iss7.book) if iss7 else None))
other = [(dep, b) for dep, b in cap["bots"] if b["char"] == "3"]
check("⑦ id 없는 3번은 이름 키 그대로(동작 무변화)", other and all(b.get("known") is iss7.known(party7["3"]["name"]) for _, b in other))

print("── ⑧ 조각 3: 각본이 길드에서 직접 맺고 내려가는 판")
main8, side8, _ = play(["1", "2"], form=True)
ev8 = [(r["turn"], e) for r in ticks(main8) + ticks(side8) for e in (r.get("events") or [])]
asked = [(t, e) for t, e in ev8 if e.get("result") == "party_asked"]
formed = [(t, e) for t, e in ev8 if e.get("result") == "party_formed"]
desc8 = [r for r in main8 if r["kind"] == "descend"]
check("⑧ 길드 구역에서 청(party_asked) → 맞받아 맺음(party_formed, members [1,2]) → 그 뒤에 첫 하강 · 하강은 둘만",
      asked and formed and asked[0][0] <= formed[0][0] and formed[0][1].get("members") == ["1", "2"]
      and desc8 and formed[0][0] < desc8[0]["turn"] and [p["char"] for p in desc8[0]["party"]] == ["1", "2"],
      (asked[:1], formed[:1], desc8[:1]))
check("⑧ 맺기 전에는 아무도 '네 파티원'이 아니다 — 맺은 다음 틱의 관측 명단에 mate",
      formed and (lambda tk: tk is not None and any((tk["decisions"].get(c) or {}).get("obs") for c in ("1", "2")) and all(
          any(p.get("mate") for p in ((tk["decisions"].get(c) or {}).get("obs") or {}).get("party") or [])
          for c in ("1", "2") if (tk["decisions"].get(c) or {}).get("obs")))(
          next((r for r in ticks(main8) if r["turn"] == formed[0][0] + 1), None)))
gate8 = [f.get("about") for r in ticks(main8)[:3] for d_ in (r.get("decisions") or {}).values()
         for f in [((d_.get("obs") or {}).get("sights") or {}).get("exit") or {}] if f.get("about")]
guide8 = [g_.get("about") for r in ticks(main8)[:3] for d_ in (r.get("decisions") or {}).values()
          for g_ in (((d_.get("obs") or {}).get("town_guide") or {}).get("places") or []) if g_.get("name") == "던전 입구"]
check("⑧ 세계가 하는 말도 그 판의 규칙대로: 던전 입구의 특징 문장이 '파티를 맺은 사람만 내려갈 수 있고 …' — 옛 문장('일행이 3칸 안에 모여야 내려간다')이 어디에도 없다",
      (gate8 or guide8) and all(a == show_runner.PARTYFORM_GATE_TRAIT for a in gate8 + guide8)
      and not any("일행이 3칸 안에 모여야 내려간다" in json.dumps(r, ensure_ascii=False) for r in ticks(main8)[:5]), (gate8[:1], guide8[:1]))
town8 = [r for r in ticks(side8, 0) if desc8 and r["turn"] > desc8[0]["turn"]]
obs3 = [o for r in town8 for o in [(((r.get("decisions") or {}).get("3") or {}).get("obs"))] if o]
np8 = [(t_, e) for t_, e in ev8 if e.get("result") == "need_party"]
check("⑧ 조각 4: 파티가 없는 3 은 던전 입구에서 need_party — 끝까지 마을에 남는다(어느 층 기록에도 3 의 하강이 없다)",
      np8 and all(e.get("char") == "3" for _, e in np8)
      and not any("3" in [p_["char"] if isinstance(p_, dict) else p_ for p_ in (r.get("party") or [])] for r in main8 + side8 if r["kind"] == "descend"),
      np8[:1])
check("⑧ 3 은 마을에 남아 계속 흐른다 · 파티 밖의 3 에게는 떠난 둘이 자동으로 실리지 않는다(명단 없음) · 파티원 둘의 명단엔 서로만",
      town8 and obs3 and all(o.get("party") == [] for o in obs3)
      and (lambda tk: tk is not None and all(
          [p["char"] for p in (((tk["decisions"].get(c) or {}).get("obs") or {}).get("party") or [])] == [m]
          for c, m in (("1", "2"), ("2", "1")) if (tk["decisions"].get(c) or {}).get("obs")))(
          next((r for r in ticks(main8) if formed and r["turn"] == formed[0][0] + 1), None)),
      (len(town8), len(obs3)))

print("── ⑥ 배선(소스·문서)")
def text(*p):
    with open(os.path.join(HERE, *p), encoding="utf-8") as f:
        return f.read()
src = text("show_runner.py")
check("⑥ 러너: 스위치·틱 몸통 둘(_tick_world·_shift_world)·옆 파일·스냅샷 열쇠",
      'os.environ.get("DUNGEON_PARTYFORM", "0") == "1" and TOWN_ON' in src and "def _tick_world(w, turn):" in src
      and "def _shift_world(w, turn):" in src and "stream_side.jsonl" in src and '"worlds": worlds, "parties": parties' in src)
lp, lh = text("launcher.py"), text("launcher", "index.html")
check("⑥ 론처: 고급 설정의 체크박스(기본 끔)·옵션·러너 환경변수 — 옵션이 없으면 끈다",
      'id="partyform">' in lh and 'id="partyform" checked' not in lh and "partyform: $('partyform').checked" in lh
      and 'env["DUNGEON_PARTYFORM"] = "1" if opts.get("partyform") is True else "0"' in lp)
fmt = text("STREAM_FORMAT.md")
check("⑥ STREAM_FORMAT: partyform · depart · arrive · stream_side.jsonl", all(s in fmt for s in ("partyform", "depart", "arrive", "stream_side.jsonl")))
hd = text("design", "HARNESS_DESIGN.md")
check("⑥ HARNESS D84: 조각 2 · DUNGEON_PARTYFORM · '사람이 있는 세계는 다 흐른다'", "DUNGEON_PARTYFORM" in hd and "사람이 있는 세계는 다 흐른다" in hd)

print("=" * 44)
print("ALL PASS — verify_worlds (D84 조각 2: 세계마다 제 시계 — 계단을 쓴 무리만 옮기고 남은 세계는 흐른다 · 합류·복원 · 본/옆 스트림 · 이어가기)"
      if not C.failed else "FAILED %d" % C.failed)
sys.exit(1 if C.failed else 0)

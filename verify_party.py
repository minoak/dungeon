# -*- coding: utf-8 -*-
"""Part B(시트 외부화 + N인 파티) 헤들리스 검증.
게이트:
  ① load_party: 기본 party.json = 3인(두란·카야·피른), 필수 9필드, 관계 교차, 메타 키 무시
  ② 폴백/방어: 파일 없음·필드 누락·char 키 위반·수치형 위반 → 내장 2인 + 경고 / 300자 절단 / 5인 초과 경고만
  ③ spawn: sheet= 복사(선택 필드 포함) / sheet=None 하위호환(HEROES) / 3인 군집 스폰
  ④ N인 하강 gather: wait_allies(missing 정렬) → 전원 모임 = 동반 하강
  ⑤ 프롬프트 층: brains._sheet(이름·관계·roster 밖 무해) / gm.set_party(_CAST) / obs.party / render
  ⑥ 러너 3인 통합: run_meta 3인·botlog 동적·배너 로스터·맵 이름·스트림 무수정(bot 스냅샷에 name 없음)
     + exit party↔won 전이 + 2인 폴백 스모크 + 3인 결정론(2회 동일)
(기존 verify_stage1/2/2b/3 + verify_stream 은 별도 실행 — 게이트 명령이 연쇄한다.)
"""
import io
import os
import json
import tempfile
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
                  DUNGEON_STATE_DIR=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                 "state_partyverify"))  # 격리 — state/ 관전 판 truncate 방지
os.environ.pop("DUNGEON_PARTY_FILE", None)     # 기본 party.json 경로 사용(3인)
os.environ.pop("DUNGEON_STREAM_OBS", None)
import brains
brains._call_claude = lambda prompt, model="haiku": ""   # LLM 무력화 → dummy 폴백(결정론)
import gm
import dungeon_gm as G
os.environ["DUNGEON_BESTIARY_FILE"] = ""   # 도감 영속 차단(리뷰 픽스) — 셸/tmux env 잔재가 라이브 원장을 읽고 쓰는 오염 방지
import show_runner
show_runner.STEP_DELAY = 0
import time as _time
_time.sleep = lambda s: None

# ── ① load_party: 기본 party.json ──
sheets = show_runner.load_party(show_runner.PARTY_FILE)
check("load_party: 기본 party.json = 3인('1','2','3')", sorted(sheets) == ["1", "2", "3"])
check("load_party: 필수 9필드 전원 보유",
      all(set(show_runner.SHEET_REQ) <= set(s) for s in sheets.values()))
check("load_party: 3번 = 음유시인 피른(hp11·str1·dex2·은신2·수색1 — 계획 파라미터)",
      sheets["3"]["job"] == "음유시인" and sheets["3"]["name"] == "피른"
      and sheets["3"]["hp"] == 11 and sheets["3"]["str"] == 1 and sheets["3"]["dex"] == 2
      and sheets["3"]["stealth"] == 2 and sheets["3"]["search_r"] == 1)
check("load_party: 관계 3인 교차(각자 나머지 둘을 서술)",
      all(set(sheets[c].get("relationships", {})) == {o for o in sheets if o != c}
          for c in sheets))
check("load_party: 메타 키('_readme')는 시트가 아니다", "_readme" not in sheets)

# ── ② 폴백/방어 ──
def try_load(obj, path=None):
    if path is None:
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)
    with contextlib.redirect_stderr(io.StringIO()) as err:
        s = show_runner.load_party(path)
    return s, err.getvalue()

fb, e = try_load(None, path="/nonexistent/party.json")
check("폴백: 파일 없음 → 내장 2인(전사·도적) + 경고 1줄",
      sorted(fb) == ["1", "2"] and fb["1"]["job"] == "전사" and "폴백" in e)
fb, e = try_load({"1": {"job": "전사"}})
check("폴백: 필수 필드 누락 → 내장 2인", sorted(fb) == ["1", "2"] and "누락" in e)
fb, e = try_load({"10": dict(G.HEROES["1"])})
check("폴백: char 키 위반('10') → 내장 2인", sorted(fb) == ["1", "2"])
fb, e = try_load({"1": {**G.HEROES["1"], "hp": "14"}})
check("폴백: 수치형 위반(hp='14' 문자열) → 내장 2인", sorted(fb) == ["1", "2"])
ok1, e = try_load({"1": {**G.HEROES["1"], "persona": "가" * 999, "goal": "나" * 999}})
check("자유서술 300자 절단(persona·goal)",
      len(ok1["1"]["persona"]) == 300 and len(ok1["1"]["goal"]) == 300)
ok6, e = try_load({str(i): dict(G.HEROES["1"]) for i in range(1, 7)})
check("5인 초과: 경고만 내고 6인 그대로 통과",
      sorted(ok6) == [str(i) for i in range(1, 7)] and "초과" in e)

# ── ③ spawn: sheet 복사 / 하위호환 / 군집 ──
d1 = G.Dungeon(seed=11, w=40, h=16)
b1 = G.spawn(d1, "1", [])                     # sheet 없이 = 내장 HEROES(기존 verify 계약)
check("spawn 하위호환: sheet=None → HEROES(전사 hp14, name 없음)",
      b1["job"] == "전사" and b1["maxhp"] == 14 and b1["name"] is None)
d2 = G.Dungeon(seed=11, w=40, h=16)
party = []
for c in ("1", "2", "3"):
    party.append(G.spawn(d2, c, party, sheet=sheets[c]))
b3 = party[2]
check("spawn+sheet: 시트 값 복사(피른 hp11·이름·목표·관계 '1','2')",
      b3["maxhp"] == 11 and b3["name"] == "피른" and b3["goal"]
      and set(b3["relationships"]) == {"1", "2"})
check("3인 군집 스폰(첫 봇 기준 맨해튼 ≤ 4, 서로 딴 칸)",
      all(abs(b["x"] - party[0]["x"]) + abs(b["y"] - party[0]["y"]) <= 4 for b in party[1:])
      and len({(b["x"], b["y"]) for b in party}) == 3)

# ── ④ N인 하강 gather ──
def arena(seed=13, w=20, h=12):
    d = G.Dungeon(seed=seed, w=w, h=h, n_monsters=0, n_traps=0, n_lurkers=0)
    for y in range(h):
        for x in range(w):
            d.grid[y][x] = '.' if (1 <= x < w - 1 and 1 <= y < h - 1) else '#'
    ef = d.features[d._exit_fid]
    ef.x, ef.y = w - 2, h - 2
    d.features = {d._exit_fid: ef}
    d.monsters, d.traps = [], []
    d.visited = set()
    return d


def mkbot(char, x, y):
    return {'char': char, 'x': x, 'y': y, 'hp': 10, 'maxhp': 10,
            'str': 1, 'dex': 1, 'wdmg': 2, 'stealth': 0, 'search_r': 1,
            'job': '모험가', 'sex': '-', 'persona': '', 'bag': 0,
            'alive': True, 'won': False, 'order': None, 'path': [],
            'aware_of': set()}

da = arena()
ex, ey = da.exit
p1, p2, p3 = mkbot('1', ex, ey), mkbot('2', 2, 2), mkbot('3', 3, 2)
r = da._interact(p1, 'exit', [p1, p2, p3])
check("하강 gather: 2명이 멀다 → wait_allies missing=['2','3'](정렬)",
      r["result"] == "wait_allies" and r["missing"] == ["2", "3"])
p2["x"], p2["y"] = ex - 1, ey
r = da._interact(p1, 'exit', [p1, p2, p3])
check("하강 gather: 아직 1명 밖 → missing=['3']",
      r["result"] == "wait_allies" and r["missing"] == ["3"])
p3["x"], p3["y"] = ex, ey - 2
r = da._interact(p1, 'exit', [p1, p2, p3])
check("하강 gather: 전원 반경 내 → 동반 하강 party=['1','2','3'] + 전원 won",
      r["result"] == "exit" and r["party"] == ["1", "2", "3"]
      and all(b["won"] for b in (p1, p2, p3)))

# ── ⑤ 프롬프트 층 ──
txt3 = brains._sheet(b3, party)
check("_sheet: 이름·직업·말투·목표·관계(동료 이름 표기) 포함",
      "피른" in txt3 and "음유시인" in txt3 and "말투" in txt3
      and "두란(봇1)" in txt3 and "카야(봇2)" in txt3)
bx = dict(b3)
bx["relationships"] = {**b3["relationships"], "9": "유령과의 오랜 우정"}
check("_sheet: roster 밖 관계 대상은 침묵(무해 처리)", "유령" not in brains._sheet(bx, party))
check("_sheet: 하위호환(bot=None 경로) — HEROES 로 시트 구성",
      "전사" in brains._sheet({**G.HEROES["1"], "char": "1", "maxhp": 14}, None))
gm.set_party(sheets)
check("gm._CAST: 등장인물 3인 이름 전부 + 창작금지 문구",
      all(n in gm._CAST for n in ("두란", "카야", "피른")) and "창작 금지" in gm._CAST)
obs = d2.view(party[0], party)
check("obs.party: 나 제외 동료 2명", len(obs["party"]) == 2
      and {p["char"] for p in obs["party"]} == {"2", "3"})
rmap = d2.render(party)
check("render: 3 글리프 표시", all(ch in rmap for ch in "123"))
party[2]["won"] = True
check("render: won 봇 글리프 소멸", "3" not in d2.render(party))
party[2]["won"] = False

# ── ⑥ 러너 3인 통합 + 결정론 ──
def run_once():
    with contextlib.redirect_stdout(io.StringIO()), \
         contextlib.redirect_stderr(io.StringIO()):
        show_runner.main()
    return open(os.path.join(show_runner.STATE, "stream.jsonl"), encoding="utf-8").read()


raw = run_once()
recs = [json.loads(l) for l in raw.splitlines()]
meta, end = recs[0], recs[-1]
ticks = [r for r in recs if r["kind"] == "tick"]
check("러너: run_meta.party = 3인(음유시인 포함)",
      len(meta["party"]) == 3 and any(p["job"] == "음유시인" for p in meta["party"]))
check("러너: 게임 종결(end·outcome 유효)",
      end["kind"] == "end" and end["outcome"] in ("escaped", "wiped", "timeout"))
check("러너: 스트림 무수정 — 봇 스냅샷에 name 없음(Part B 계약)",
      all("name" not in b for t in ticks for b in t["bots"]))
ok_won = True
for t in ticks:                                # 3인 exit party ↔ won 전이(스트림 위에서)
    snap = {b["char"]: b for b in t["bots"]}
    for e in t["events"]:
        if e.get("type") == "interact" and e.get("result") == "exit":
            if not all(snap[c]["won"] for c in e["party"]):
                ok_won = False
check("러너: interact exit.party ↔ 같은 틱 won 전이 정합", ok_won)
check("러너: botlog 동적(bot3.log 생성)",
      os.path.exists(os.path.join(show_runner.STATE, "bot3.log")))
evlog = open(os.path.join(show_runner.STATE, "events.log"), encoding="utf-8").read()
check("러너: 배너에 이름 로스터(두란·카야·피른)", "두란·카야·피른" in evlog)
mapf = open(os.path.join(show_runner.STATE, "gm_map.txt"), encoding="utf-8").read()
check("러너: 맵 상태줄에 이름 표기", any(n in mapf for n in ("두란", "카야", "피른")))

show_runner.PARTY_FILE = "/nonexistent"        # 폴백 스모크: 시트 없이도 게임은 돈다(2인)
raw_fb = run_once()
show_runner.PARTY_FILE = os.path.join(show_runner.HERE, "party.json")
check("러너 폴백: 파티 파일 없음 → 2인 게임 + 종결",
      len(json.loads(raw_fb.splitlines()[0])["party"]) == 2
      and json.loads(raw_fb.splitlines()[-1])["kind"] == "end")


def normalized(text):
    ls = text.splitlines()
    head = json.loads(ls[0])
    head.pop("started", None)
    return [json.dumps(head, ensure_ascii=False, sort_keys=True)] + ls[1:]


raw2 = run_once()
check("결정론: 3인 러너 2회 = 동일 스트림(started 제외)", normalized(raw) == normalized(raw2))
print("        (3인 판: %d틱, outcome=%s, 생존 %s / 쓰러짐 %s)"
      % (len(ticks), end["outcome"], end["survivors"], end["fallen"]))

print()
if C.failed:
    print("FAILED: %d개 게이트 실패" % C.failed)
    raise SystemExit(1)
print("ALL PASS — 시트 외부화(party.json)·N인 파티 건전. 시트=사용자 저작물의 원형.")

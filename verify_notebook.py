# -*- coding: utf-8 -*-
"""수첩(D59, 2026-09-12) 헤들리스 검증 — 57번째 게이트. 실 LLM 0콜.
게이트:
  ① notebook_page: 프롬프트 재료(시트·뼈·목격·남긴 한 줄·최근 대화·판단 장부·지난 장·맥락 한 줄) · 응답 파싱(JSON page / 문장만 /
     빈 응답=None / 300자 상한) · 예외도 None(판을 세우지 않음) · 스위치 끔=None·콜 0
  ② _wire: '# 수첩 — 지난 층들' 갈래가 지침 뒤·'# 기억' 앞 · 뼈 줄 + '수첩: "…"' · 장이 있으면 floor_line 초대 없음, 없으면 초대
  ③ 헤들리스 2층 판(격리 STATE, 가짜 두뇌: 판단=빈 응답→더미, 수첩=JSON): descend.pages · 다음 층 프롬프트에 장 · notes 층에서 닫힘 ·
     run_meta.notebook · 판 정상 종료
  ④ 수첩 끔(DUNGEON_NOTEBOOK=0): pages 없음 · notes 이월(D26 그대로) · run_meta.notebook=false
"""
import contextlib
import io
import json
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state_notebookverify")
os.environ.update(DUNGEON_GM="0", DUNGEON_TURNS="260", DUNGEON_W="24", DUNGEON_H="10",
                  DUNGEON_SEED="3", DUNGEON_MONSTERS="0", DUNGEON_TRAPS="0",
                  DUNGEON_LURKERS="0", DUNGEON_DEPTHS="2", DUNGEON_POTIONS="0",
                  DUNGEON_PARTY_FILE="/nonexistent", DUNGEON_STATE_DIR=STATE,
                  DUNGEON_BESTIARY_FILE="", DUNGEON_NOTEBOOK="1")
os.environ.pop("DUNGEON_STREAM_OBS", None)

import brains  # noqa: E402
import dungeon_gm as G  # noqa: E402


class C:
    failed = 0


def check(name, cond):
    print(("  OK   " if cond else " FAIL  ") + name)
    if not cond:
        C.failed += 1


NAMES = {"1": "두란", "2": "카야"}


def mkbot():
    return {"char": "1", "name": "두란", "job": "전사", "sex": "남", "hp": 9, "maxhp": 14, "str": 3, "dex": 0,
            "stealth": 0, "search_r": 1, "persona": "무뚝뚝", "x": 1, "y": 1, "bag": 2, "alive": True, "won": True,
            "notes": ["고블린은 둘이 함께 온다", "카야가 다쳤다"],
            "dialogue": [{"from": "2", "to": "1", "turn": 20, "text": "두란, 조심해", "kind": "제안"},
                         {"from": "1", "to": "2", "turn": 21, "text": "알았다"}],
            "history": [{"type": "explore", "target": "N", "turn": 18}, {"type": "attack", "target": "m1", "turn": 22}],
            "floors": [{"depth": 0, "t0": 0, "t1": 9, "n": {"대화": 3}, "w": {}, "line": None, "invite": False, "page": "마을에서 물약을 받았다."}]}


entry = {"depth": 1, "t0": 10, "t1": 40, "n": {"발견": 2, "처치": 1}, "w": {"동료 피격": 1}, "line": None, "invite": True}

# ── ① notebook_page ──
captured = []


def fake_ok(prompt, model="haiku"):
    captured.append(prompt)
    return '{"page": "1층은 고블린 둘로 험했다. 카야가 다쳤고 내가 하나를 베었다."}'


brains._call_claude = fake_ok
page = brains.notebook_page(mkbot(), entry, NAMES, roster=[])
p = captured[-1]
check("① 응답 JSON page → 한 장 문자열", page == "1층은 고블린 둘로 험했다. 카야가 다쳤고 내가 하나를 베었다.")
check("① 프롬프트 재료: 맥락 한 줄 맨 앞 · 시트 · 수첩 머리 · 뼈([발견] ×2 · [처치] ×1) · 목격 · 남긴 한 줄 · 최근 대화 · 판단 장부 · 지난 장 · JSON 지시",
      p.startswith(brains.CONTEXT_LINE) and "# 시트" in p and brains.NOTEBOOK_MARK in p and "[발견] ×2" in p and "[처치] ×1" in p
      and "목격: [동료 피격] ×1" in p and '"고블린은 둘이 함께 온다"' in p and '두란, 조심해' in p and ("탐색" in p or "explore" in p)
      and '"마을에서 물약을 받았다."' in p and '{"page"' in p and "1층을(를) 떠난다" in p)
brains._call_claude = lambda prompt, model="haiku": "그냥 문장으로만 답한다. 험한 층이었다."
check("① JSON 없이 문장만 오면 그대로 받는다(살은 내용을 안 읽는다)",
      brains.notebook_page(mkbot(), entry, NAMES) == "그냥 문장으로만 답한다. 험한 층이었다.")
brains._call_claude = lambda prompt, model="haiku": ""
check("① 빈 응답 = None(재시도 없음)", brains.notebook_page(mkbot(), entry, NAMES) is None)
brains._call_claude = lambda prompt, model="haiku": '{"page": "%s"}' % ("가" * 500)
check("① 300자 상한", len(brains.notebook_page(mkbot(), entry, NAMES)) == brains.NOTEBOOK_LEN)


def boom(prompt, model="haiku"):
    raise RuntimeError("두뇌 폭발")


brains._call_claude = boom
check("① 두뇌 예외도 None — 판을 세우지 않는다", brains.notebook_page(mkbot(), entry, NAMES) is None)
brains.NOTEBOOK_ON = False
captured.clear()
brains._call_claude = fake_ok
check("① 스위치 끔 = None · 콜 0", brains.notebook_page(mkbot(), entry, NAMES) is None and not captured)
brains.NOTEBOOK_ON = True

# ── ② _wire 수첩 갈래 ──
obs_base = {"pos": [1, 1], "hp": 9, "maxhp": 14, "depth": 2, "turn": 41, "job": "전사", "sex": "남", "str": 3, "dex": 0,
            "sights": {"exit": None, "features": [], "monsters": [], "ways": [], "bots": []}, "party": [], "options": [],
            "legend": {}, "ascii_view": [], "inventory": 1, "potions": 0, "notes": ["이 층은 조용하다"]}
fl_page = [dict(entry, page="1층은 고블린 둘로 험했다.", invite=False)]
txt = brains._wire({**obs_base, "floors": fl_page}, NAMES)
i_nb, i_mem, i_obs = txt.find("# 수첩 — 지난 층들"), txt.find("# 기억 — 무엇을 기억하나"), txt.find("# 관측")
check("② '# 수첩 — 지난 층들' 갈래가 맨 앞(지침 뒤) · '# 기억' 앞 · 뼈 줄 + '수첩: \"…\"' · floor_line 초대 없음",
      i_nb == 0 and 0 < i_mem < i_obs and "- 1층 (t10~t40, 30틱): [발견] ×2 · [처치] ×1 — 목격: [동료 피격] ×1" in txt
      and '수첩: "1층은 고블린 둘로 험했다."' in txt and "`floor_line`" not in txt)
txt2 = brains._wire({**obs_base, "floors": [dict(entry)]}, NAMES)
check("② 장이 없으면(실패) 뼈 줄 + 옛 한 줄 초대(floor_line) 그대로 — 수첩 갈래 아래",
      "# 수첩 — 지난 층들" in txt2 and "`floor_line`" in txt2 and "- 1층 (t10~t40, 30틱): [발견] ×2" in txt2)
brains.NOTEBOOK_ON = False
txt3 = brains._wire({**obs_base, "floors": fl_page}, NAMES)
check("② 스위치 끔 = 옛 자리('# 기억' 안의 '## 지난 층')", "# 수첩" not in txt3 and "## 지난 층" in txt3
      and txt3.find("# 기억") < txt3.find("## 지난 층"))
brains.NOTEBOOK_ON = True

# ── ③ 헤들리스 2층 판 ──
shutil.rmtree(STATE, ignore_errors=True)
os.makedirs(STATE, exist_ok=True)
os.environ["DUNGEON_BRAIN_BACKEND"] = "dummy"
pages_written = []


def fake_brain(prompt, model="haiku"):
    if brains.NOTEBOOK_MARK in prompt:
        pages_written.append(prompt)
        return '{"page": "이 층을 지나왔다. 조용했고 아무도 다치지 않았다."}'
    return ""                                  # 판단은 빈 응답 → 더미 폴백(결정론)


brains._call_claude = fake_brain
import show_runner  # noqa: E402
show_runner.STEP_DELAY = 0
import time as _time  # noqa: E402
_time.sleep = lambda s: None


def run_once():
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        show_runner.main()
    with open(os.path.join(STATE, "stream.jsonl"), encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


recs = run_once()
meta = recs[0]
desc = [r for r in recs if r.get("kind") == "descend"]
end = recs[-1]
check("③ run_meta.notebook=true · 판이 2층으로 내려갔고 정상 종료(end)", meta.get("notebook") is True and len(desc) >= 1 and end.get("kind") == "end")
if desc:
    d0 = desc[0]
    party = [p["char"] for p in d0.get("party") or []]
    check("③ descend.pages 에 생존자 전원의 수첩 한 장(가짜 두뇌 응답)",
          d0.get("pages") and sorted(d0["pages"]) == sorted(party) and all("이 층을 지나왔다" in v for v in d0["pages"].values()))
    check("③ 수첩 콜 = 생존자 수(층당 캐릭터당 1콜)", len(pages_written) == len(party))
    # 다음 층 첫 판단의 프롬프트에 장이 실리는지 — 2층 bots 로 _wire 를 직접 그린다(러너의 floors 이월 = level.party 스냅샷엔 없음)
    check("③ 수첩 프롬프트 재료에 그 층의 뼈가 들어갔다(세계가 센 횟수 절)", all("## 세계가 센 횟수" in p for p in pages_written))
else:
    check("③ (하강 없음 — 시드/맵 조정 필요)", False)
with open(os.path.join(STATE, "events.log"), encoding="utf-8") as f:
    evlog = f.read()
check("③ events.log 에 '수첩 한 장' 줄(캐릭터별)", evlog.count("수첩 한 장") >= 1 and "이 층을 지나왔다" in evlog)

# ── ④ 수첩 끔 ──
shutil.rmtree(STATE, ignore_errors=True)
os.makedirs(STATE, exist_ok=True)
brains.NOTEBOOK_ON = False
pages_written.clear()
recs2 = run_once()
desc2 = [r for r in recs2 if r.get("kind") == "descend"]
check("④ 수첩 끔: run_meta.notebook=false · descend 에 pages 없음 · 수첩 콜 0",
      recs2[0].get("notebook") is False and desc2 and "pages" not in desc2[0] and not pages_written)
brains.NOTEBOOK_ON = True

print("=" * 44)
print("RESULT: " + ("ALL PASS — verify_notebook (D59 수첩: 재료·파싱·실패 무정지·갈래 자리·2층 판 pages·끔)"
                    if C.failed == 0 else "%d FAILED" % C.failed))
raise SystemExit(1 if C.failed else 0)

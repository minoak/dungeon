# -*- coding: utf-8 -*-
"""판 결산(D58, 2026-09-12) 헤들리스 검증 — 56번째 게이트. 실 LLM 0콜.
게이트:
  ① 합성 스트림 정확 계수: 같은 (행동, 대상) 최장 연속·재선택 / 판단 정지 코드·안전 차단·사람 재시도 / 입력 무효 재판단 코드 /
     전원 3칸 안 %·최장 이산 / 연속 착용·같은 개체 되집기 / 말 종류·정지(제안)·친목·건네기·반응 / 작정 분리 / flags 문장
  ② 헤들리스 판(show_runner, 격리 STATE, dummy): end.summary 존재 · 오프라인 소급(run_summary.replay)과 dict 일치(투영 순수성) ·
     Tap 이 파일 내용을 바꾸지 않음(라인 종류·개수 계약 그대로) · events.log 끝에 '=== 판 결산' 표
  ③ render: 한 줄에 한 갈래 · 눈길 없음 문장
"""
import contextlib
import io
import json
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state_summaryverify")
os.environ.update(DUNGEON_GM="0", DUNGEON_TURNS="60", DUNGEON_W="40", DUNGEON_H="16",
                  DUNGEON_SEED="7", DUNGEON_MONSTERS="2", DUNGEON_TRAPS="2",
                  DUNGEON_LURKERS="0", DUNGEON_DEPTHS="1",
                  DUNGEON_PARTY_FILE="/nonexistent", DUNGEON_STATE_DIR=STATE,
                  DUNGEON_BESTIARY_FILE="")
os.environ.pop("DUNGEON_STREAM_OBS", None)

import run_summary as RS  # noqa: E402


class C:
    failed = 0


def check(name, cond):
    print(("  OK   " if cond else " FAIL  ") + name)
    if not cond:
        C.failed += 1


def bot(c, x, y, alive=True):
    return {'char': c, 'x': x, 'y': y, 'alive': alive, 'won': False}


# ── ① 합성 스트림 ──
col = RS.Collector()
col.consume('run_meta', {'seed': 1, 'party': [{'char': '1', 'name': '유나'}, {'char': '2', 'name': '미나'}]})
col.consume('level', {'depth': 1})
recs = []
# t1~t6: 유나 use f8 연속 6(그중 t3 은 작정) · 미나 goto b1 → 이미 곁 재판단 2회 · 둘 다 함께(1칸)
for t in range(1, 7):
    dec = {'1': {'type': 'use', 'target': 'f8', 'src': 'plan' if t == 3 else 'haiku', 'say': '또 단검!', 'say_kind': '잡담'}}
    if t in (2, 4):
        dec['2'] = {'type': 'goto', 'target': 'b1', 'src': 'haiku',
                    'brain_retries': [{'code': 'already_beside', 'reason': 'x'}]}
    ev = [{'char': '1', 'type': 'use', 'target': 'f8', 'result': 'equip', 'id': 'f8', 'dropped_id': 'f9'}]
    recs.append({'turn': t, 'decisions': dec, 'events': ev, 'bots': [bot('1', 5, 5), bot('2', 6, 5)],
                 'hails': ['2'] if t == 2 else []})
# t7~t10: 흩어짐(6칸) · 미나 제안·친목·건네기 · 반응 · lost
for t in range(7, 11):
    dec = {'2': {'type': 'bond', 'target': 'b1', 'src': 'haiku', 'say': '같이 가자', 'say_kind': '제안', 'book_line': {'key': 'monster:고블린', 'text': 'x'}}}
    ev = [{'char': '2', 'type': 'bond', 'result': 'done', 'to': '1'}] if t == 7 else \
         [{'char': '2', 'type': 'give', 'result': 'given', 'to': '1'}] if t == 8 else \
         [{'char': '1', 'type': 'walk', 'result': 'lost'}] if t == 9 else []
    recs.append({'turn': t, 'decisions': dec, 'events': ev, 'bots': [bot('1', 5, 5), bot('2', 11, 5)],
                 'reactions': [{'value': 'like'}] if t == 8 else []})
for r in recs:
    col.consume('tick', r)
col.consume('brain_pause', {'turn': 10, 'errors': [{'char': '2', 'input_error': 'already_beside',
                                                    'attempt_errors': [{'code': 'invalid_target'}, {'code': 'already_beside'}]}]})
col.consume('brain_retry', {'turn': 10})
col.consume('brain_pause', {'turn': 10, 'errors': [{'char': '1', 'input_error': 'invalid_response',
                                                    'reason': '빈 응답 rc=200 | PROHIBITED_CONTENT'}]})
s = col.result(outcome='timeout', depth=1, survivors=[], fallen=[])
a1, a2 = s['actions']['1'], s['actions']['2']
check("① 유나: 실결정 5 + 작정 1 · 최장 연속 use f8 ×6 (t1~t6, 작정 포함) · 재선택 4",
      a1['n'] == 5 and a1['plan'] == 1 and a1['longest_run'] == {'n': 6, 'type': 'use', 'target': 'f8', 't0': 1, 't1': 6}
      and a1['repeat'] == 4 and a1['types'] == {'use': 5})
check("① 미나: 아군 goto 2 · 입력 무효 재판단 already_beside 2 · 최장 연속 bond b1 ×4",
      a2['goto_ally'] == 2 and s['decisions']['input_retries'] == {'already_beside': 2}
      and a2['longest_run']['n'] == 4 and a2['longest_run']['type'] == 'bond')
check("① 판단: 실결정 11 (1.10/틱) · 출처 haiku 11 · 도감 생각 한 줄 4",
      s['decisions']['real'] == 11 and s['decisions']['per_tick'] == 1.1 and s['decisions']['src'] == {'haiku': 11}
      and s['bestiary']['book_lines'] == 4)
check("① 정지 2회(already_beside 1·invalid_response 1) · 안전 차단 1 · 사람 재시도 1",
      s['pauses'] == {'n': 2, 'by_code': {'already_beside': 1, 'invalid_response': 1}, 'blocked': 1, 'retries': 1})
check("① 파티: 전원 3칸 안 60% (6/10) · 최장 이산 4 · lost 1",
      s['party'] == {'together_pct': 60, 'multi_ticks': 10, 'split_max': 4, 'lost': 1})
check("① 사회: 잡담 5 제안 4 · 정지 1 · 친목 1 · 건네기 1 · 반응 like 1",
      s['social'] == {'say': {'잡담': 5, '제안': 4}, 'hails': 1, 'give': 1, 'bond': 1, 'reactions': {'like': 1}})
check("① 장비: 착용 유나 6 · 되집기 f8 ×6 · 연속 착용 6 (t1~t6)",
      s['gear']['equip'] == {'1': 6} and s['gear']['rewear'] == {'1': {'f8': 6}}
      and s['gear']['streak'] == {'1': {'n': 6, 't0': 1, 't1': 6}})
fl = ' / '.join(s['flags'])
check("① flags: 같은 대상 연속(유나 6·미나 없음<5? 미나 4) · 판단 정지 · 함께 60%>30% 아님 · 되집기 · 연속 착용 — 이름으로",
      '유나 같은 대상 연속 6회 — use f8 (t1~t6)' in fl and '미나 같은 대상 연속' not in fl
      and '판단 정지 2회' in fl and '안전 차단 1' in fl and '전원 함께' not in fl
      and '유나 같은 장비 되집기 — f8 ×6' in fl and '유나 연속 착용 6회 (t1~t6)' in fl)
lines = RS.render(s, col.names)
check("③ render: 머리 '=== 판 결산' · 행동 줄에 이름·최장 반복 · 눈길 줄", lines[0].startswith('=== 판 결산')
      and any(ln.startswith('  행동 유나:') and 'use f8 ×6 (t1~t6)' in ln for ln in lines)
      and any(ln.startswith('  ⚠️ 눈길') for ln in lines))
s0 = RS.Collector().result()
check("③ 빈 판 결산도 죽지 않는다(0/틱·눈길 없음 문장)", s0['decisions']['per_tick'] == 0.0 and s0['flags'] == []
      and any('눈길: 문턱 넘는 항목 없음' in ln for ln in RS.render(s0)))

# ── ② 헤들리스 판(격리 STATE·dummy) ──
shutil.rmtree(STATE, ignore_errors=True)
os.makedirs(STATE, exist_ok=True)
import brains  # noqa: E402
os.environ["DUNGEON_BRAIN_BACKEND"] = "dummy"
brains._call_claude = lambda prompt, model="haiku": ""
import show_runner  # noqa: E402
show_runner.STEP_DELAY = 0
import time as _time  # noqa: E402
_time.sleep = lambda s: None
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    show_runner.main()
path = os.path.join(STATE, "stream.jsonl")
with open(path, encoding="utf-8") as f:
    recs2 = [json.loads(ln) for ln in f if ln.strip()]
end = recs2[-1]
check("② 마지막 라인 end 에 summary(v1) · ticks = tick 라인 수 · outcome 일치",
      end.get("kind") == "end" and isinstance(end.get("summary"), dict) and end["summary"].get("v") == 1
      and end["summary"]["ticks"] == sum(1 for r in recs2 if r.get("kind") == "tick")
      and end["summary"]["outcome"] == end.get("outcome"))
col2, end2 = RS.replay(path)
check("② 오프라인 소급 = 라이브 end.summary (dict 완전 일치 — 투영 순수성)", col2.result() == end["summary"])
kinds = [r.get("kind") for r in recs2]
check("② Tap 이 스트림 계약을 안 바꾼다: run_meta 첫 줄·level·tick·end 마지막 줄",
      kinds[0] == "run_meta" and "level" in kinds and kinds.count("end") == 1 and kinds[-1] == "end")
with open(os.path.join(STATE, "events.log"), encoding="utf-8") as f:
    ev = f.read()
check("② events.log 끝에 '=== 판 결산' 표(판·판단·정지·행동·파티·사회·장비·도감 줄)",
      "=== 판 결산" in ev and all(k in ev.split("=== 판 결산")[-1] for k in ("  판:", "  판단:", "  정지:", "  행동", "  파티:", "  사회:", "  장비:", "  도감:")))

print("=" * 44)
print("RESULT: " + ("ALL PASS — verify_summary (D58 판 결산: 합성 계수·라이브=소급·Tap 무접촉·events.log 표)"
                    if C.failed == 0 else "%d FAILED" % C.failed))
raise SystemExit(1 if C.failed else 0)

# -*- coding: utf-8 -*-
"""자기 행동 궤적(D38, 2026-09-06 파트너 확정 "자기 행동에 대한 정보가 많이 부족했던 거네 — 확장하자") 검증 — 37번째 게이트. LLM 0콜.
마지막 view() 이후 그 봇에게 일어난 결과를 순서대로 보존해 다음 결정에 보여준다. last 는 한 칸이라 작정(D16)이 붙은
결정은 다음 틱의 plan goto·걸음이 상인 대사·전투 결과를 덮었다(09-06 마을 판 seed 726984: 미나가 상인의 '이미 줬어'를
결정 시점에 0/7 봄). 기록자는 _note_last/_trail_add 한 곳. 엔진 판정 무접촉(자기 경험의 기록·노출뿐).
게이트:
  ① 스위치: 엔진 기본 0 / from_ascii 기본 0 / 꺼진 판 = trail 안 쌓임·obs 에 trail 키 없음·last 구동작
  ② 단일 기록자: _note_last(plan 표식)·자동보행 걸음·plan_broken·말 걸림(hail)·피격(hurt, status 병기) 전부 trail 에 —
     last 는 마지막 항목과 동일(turn/plan 제외)
  ③ 순서·표식: goto(pathed) → 걸음 → 보물 → 작정 goto(plan 표식) → 걸음 순, turn 스탬프 단조
  ④ view() 가 노출 후 소거 — 작정 집행 틱(view 없음)엔 누적 / 두 번째 view 엔 키 없음
  ⑤ 상한 TRAIL_MAX: 넘치면 앞을 버리고 gap 표식 한 칸(n 누적)
  ⑥ 렌더: 1건 = 구판 "- 그 결과: …" 문자열 동일 / 다건 = "- 그 뒤 일어난 일: A → B → C", "N걸음 걸었다", "작정대로 ",
     "…(n건 생략)", 직전 판단 "(tN)", 출혈 줄 — JSON 폴백 0
  ⑦ think_all: 작정 수 뒤에도 intent = 마지막 실 결정(궤적 판) / 궤적 끈 판은 작정 수가 덮는다(구동작)
  ⑧ 결정론: 같은 시드·같은 수순 두 번 = 같은 궤적
(기존 verify 36종은 별도 실행.)
"""
import copy
import brains
import dungeon_gm as G
from dungeon_gm import Dungeon

brains._call_claude = lambda prompt, model="haiku": ""   # LLM 무력화 → dummy 폴백(결정론)


class C:
    failed = 0


def check(name, cond):
    print(("  OK   " if cond else " FAIL  ") + name)
    if not cond:
        C.failed += 1


def mkbot(char, x, y, hp=14):
    return {'char': char, 'x': x, 'y': y, 'hp': hp, 'maxhp': hp,
            'str': 3, 'dex': 0, 'wdmg': 4, 'stealth': 0,
            'search_r': 1, 'job': '전사', 'sex': '남', 'persona': '', 'bag': 0,
            'alive': True, 'won': False, 'order': None, 'path': [],
            'aware_of': set(), 'plan': [], 'last': None}


ROWS = ["############",
        "#1...$....>#",
        "############"]


def scene(trail=True):
    d, st = Dungeon.from_ascii(ROWS, seed=7)
    d.trail_on = trail
    b = mkbot('1', *st['1'])
    return d, b, [b]


def run_seq(d, b, bots):
    """goto 보물(then goto exit) → 걸음 → 보물 → 작정 goto exit(plan) → 걸음 2 — view() 없이 진행(작정 집행 틱 재현)."""
    fid = next('f%d' % f.id for f in d.features.values() if f.type == 'treasure')
    d.turn = 5
    d.act(b, {'type': 'goto', 'target': fid, 'then': [{'type': 'goto', 'target': 'exit'}], 'src': 'haiku'}, bots)
    t = 6
    while b.get('order') and t < 30:
        d.turn = t
        d.step_order(b, bots)
        t += 1
    step = d.plan_step(b, bots)
    assert step, "작정 다음 수가 있어야 한다"
    d.turn = t
    d.act(b, {**step, 'src': 'plan'}, bots)
    for _ in range(2):
        t += 1
        d.turn = t
        d.step_order(b, bots)
    return fid


print("── ① 스위치")
check("① 엔진 기본 trail_on=False · from_ascii 기본 False",
      Dungeon(seed=7).trail_on is False and Dungeon.from_ascii(["####", "#1>#", "####"])[0].trail_on is False)
d0, b0, bots0 = scene(trail=False)
run_seq(d0, b0, bots0)
o0 = d0.view(b0, bots0)
check("① 꺼진 판: trail 안 쌓임 · obs 에 trail 키 없음 · last 는 구동작",
      not b0.get('trail') and 'trail' not in o0 and o0['last'] and o0['last'].get('type') == 'walk')

print("── ②③ 기록자·순서")
d, b, bots = scene()
fid = run_seq(d, b, bots)
tr = b['trail']
types = [(e['type'], e.get('result'), bool(e.get('plan'))) for e in tr]
check("③ 순서: goto pathed → 걸음… → 보물 → 작정 goto exit(plan 표식) → 걸음 2",
      types[0] == ('goto', 'pathed', False)
      and ('walk', 'treasure', False) in types
      and ('goto', 'pathed', True) in types
      and types.index(('goto', 'pathed', True)) > types.index(('walk', 'treasure', False))
      and types[-1] == ('walk', 'walking', False))
turns = [e['turn'] for e in tr]
check("③ turn 스탬프 단조 증가 · 시작 5", turns == sorted(turns) and turns[0] == 5)
check("② last = 궤적 마지막 항목(turn/plan 제외)",
      b['last'] == {k: v for k, v in tr[-1].items() if k not in ('turn', 'plan')})
d.turn = 40
d._note_last(b, {'char': '1', 'type': 'goto', 'result': 'pathed', 'target': 'exit'}, plan=True)
check("② _note_last(plan=True): last 엔 plan 없음 · trail 엔 plan·turn",
      'plan' not in b['last'] and b['trail'][-1].get('plan') is True and b['trail'][-1]['turn'] == 40)
d.hail = True
b['order'], b['path'] = 'exit', [(9, 1)]
d.hail_stop(b, ['2'])
check("② 말 걸림(hail) 도 궤적에", b['trail'][-1]['type'] == 'hail' and b['last']['type'] == 'hail')
b['plan'] = [{'type': 'goto', 'target': 'zzz'}]
check("② plan_broken 도 궤적에", d.plan_step(b, bots) is None and b['trail'][-1]['type'] == 'plan_broken')
# 피격(status 병기) — 그림자거미 명중=둔화(D34) 재현(verify_status 문법)
SPIDER = ["#########",
          "#1...s.>#",
          "#########"]
ds, sts = Dungeon.from_ascii(SPIDER, seed=7,
                             monsters={'s': {'kind': '그림자거미', 'state': 'HUNTING', 'target': '1'}})
ds.trail_on, ds.status = True, True
bs = mkbot('1', *sts['1'], hp=30)
bs['x'] = ds.monsters[0].x - 1
ds.monsters[0].last_seen = (bs['x'], bs['y'])
bs['aware_of'].add(ds.monsters[0].id)
ds.d20 = lambda: 20
ds.turn = 3
ds.monster_turn([bs])
hurt = [e for e in (bs.get('trail') or []) if e.get('type') == 'hurt']
check("② 피격(hurt) 도 궤적에 — status(둔화) 병기까지 실린 한 항목",
      len(hurt) == 1 and hurt[0].get('status') == '둔화' and hurt[0]['turn'] == 3
      and bs['last'].get('status') == '둔화')

print("── ④ 노출·소거")
o = d.view(b, bots)
n_before = len(o.get('trail') or [])
check("④ view: obs.trail 노출(다건) · 봇 trail 비움 · gap 0",
      n_before >= 5 and b['trail'] == [] and not b.get('trail_gap'))
o2 = d.view(b, bots)
check("④ 두 번째 view 엔 trail 키 없음(1회 노출) · last 는 남는다", 'trail' not in o2 and o2['last'] is not None)

print("── ⑤ 상한")
for i in range(G.TRAIL_MAX + 3):
    d.turn = 100 + i
    d._trail_add(b, {'type': 'walk', 'result': 'walking'})
check("⑤ TRAIL_MAX 초과 → 앞 3건 버리고 gap=3", len(b['trail']) == G.TRAIL_MAX and b.get('trail_gap') == 3)
o3 = d.view(b, bots)
check("⑤ view: gap 표식이 첫 칸 · 나머지 TRAIL_MAX",
      o3['trail'][0] == {'type': 'gap', 'n': 3} and len(o3['trail']) == G.TRAIL_MAX + 1)

print("── ⑥ 렌더")
NAMES = {'1': '두란', '2': '카야'}
base = {"job": "전사", "sex": "남", "hp": 9, "maxhp": 14, "str": 3, "dex": 1,
        "inventory": 1, "depth": 1, "pos": [5, 5],
        "sights": {"exit": None, "features": [], "monsters": [], "ways": [], "bots": []},
        "party": [], "options": [], "ascii_view": ["@"], "legend": {},
        "intent": {"type": "goto", "target": "f3", "reason": "보물부터", "say": "간다"},
        "last": {"type": "walk", "result": "arrived", "target": "f3"}}
txt_a = brains._wire(copy.deepcopy(base), NAMES)
one = {**copy.deepcopy(base), "trail": [{"type": "walk", "result": "arrived", "target": "f3", "turn": 9}]}
txt_b = brains._wire(one, NAMES)
check("⑥ 1건 궤적 = 구판 렌더와 문자열 동일(핀 보호)", txt_a == txt_b and "- 그 결과: f3 곁에 도착했다" in txt_a)
multi = {**copy.deepcopy(base),
         "intent": {"type": "interact", "target": "f2", "reason": "물자부터", "turn": 25},
         "trail": [{"type": "gap", "n": 2},
                   {"type": "interact", "target": "f2", "result": "npc_gift", "npc": "아이템 상인", "item": "물약",
                    "line": "물약 하나 가져가게.", "turn": 25},
                   {"type": "goto", "target": "f1", "result": "pathed", "plan": True, "turn": 26},
                   {"type": "walk", "result": "walking", "target": "f1", "turn": 27},
                   {"type": "walk", "result": "walking", "target": "f1", "turn": 28, "treasure": True},
                   {"type": "walk", "result": "walking", "target": "f1", "turn": 29},
                   {"type": "walk", "result": "arrived", "target": "f1", "turn": 30, "bleed": {"hp": 7}}]}
txt_c = brains._wire(multi, NAMES)
line = next((l for l in txt_c.splitlines() if l.startswith("- 그 뒤 일어난 일: ")), "")
check("⑥ 다건 렌더: 직전 판단(t25) · ' → ' 체인 · '작정대로 ' · '3걸음 걸었다 — 길에서 보물' · gap · 출혈 줄 · '그 결과' 없음",
      "- 직전 판단(t25): interact f2" in txt_c
      and line.startswith("- 그 뒤 일어난 일: …(2건 생략) → 아이템 상인에게 말을 걸었다 — 물약을 받았다")
      and " → 작정대로 f1 쪽으로 걷기 시작했다 → 3걸음 걸었다 — 길에서 보물을 주웠다 → f1 곁에 도착했다" in line
      and "- 그 결과:" not in txt_c and "{" not in line
      and "걷는 동안 출혈로 피를 흘렸다 — 남은 HP 7" in txt_c)
check("⑥ 실전 궤적(②③의 것) 항목 전부 문장 — JSON 폴백 0", "{" not in brains._trail_prose(o['trail'], NAMES))

print("── ⑦ think_all intent")


def _think(trail_on):
    dt, stt = Dungeon.from_ascii(ROWS, seed=7)
    dt.trail_on = trail_on
    bt = mkbot('1', *stt['1'])
    bt['intent'] = {'type': 'interact', 'target': 'f2', 'reason': '물자부터', 'turn': 3}
    bt['plan'] = [{'type': 'goto', 'target': 'exit'}]
    dt.turn = 7
    out = brains.think_all(dt, [bt])
    return out, bt


out_on, bt_on = _think(True)
out_off, bt_off = _think(False)
check("⑦ 궤적 판: 작정 수(src=plan) 집행돼도 intent 는 마지막 실 결정 그대로",
      out_on['1']['src'] == 'plan' and bt_on['intent']['type'] == 'interact' and bt_on['intent']['turn'] == 3)
check("⑦ 궤적 끈 판: 작정 수가 intent 를 덮는다(구동작 보존)",
      out_off['1']['src'] == 'plan' and bt_off['intent']['type'] == 'goto' and 'turn' not in bt_off['intent'])
dt2, stt2 = Dungeon.from_ascii(ROWS, seed=7)
dt2.trail_on = True
bt2 = mkbot('1', *stt2['1'])
dt2.turn = 11
out2 = brains.think_all(dt2, [bt2])
check("⑦ 궤적 판의 실 결정엔 intent.turn 스탬프", out2['1']['src'] != 'plan' and bt2['intent'].get('turn') == 11)

print("── ⑧ 결정론")
da, ba, botsa = scene()
run_seq(da, ba, botsa)
db, bb, botsb = scene()
run_seq(db, bb, botsb)
check("⑧ 같은 시드·같은 수순 = 같은 궤적", ba['trail'] == bb['trail'])

print()
if C.failed:
    print("FAIL — %d개 실패" % C.failed)
    raise SystemExit(1)
print("ALL PASS — verify_trail (D38 자기 행동 궤적: 기록자 하나·순서·노출 1회·상한·렌더·intent 유지·결정론)")

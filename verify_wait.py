# -*- coding: utf-8 -*-
"""wait(D25, 2026-07-24 파트너 확정 "그대로 가자") 헤들리스 검증 — 23번째 게이트.
숫자 없는 사건 기반 대기: 제자리 유지·대기 중 LLM 0콜(order 유지=think_all 스킵 구조).
깨어남 4종 = 말 걸림(D24)/시야 새 존재(새 몹=인카운터·새 오브젝트=sighted·동료 진입=wait_met)/
피격(기존 인터럽트)/지루함 상한(WAIT_MAX=15 — "아무도 오지 않는다"). 셔틀의 고정점 —
한 명이 서면 나머지 goto 가 움직이지 않는 목표를 얻는다. D21 맴돎·무발견 창과 자연 배타.
게이트:
  ① 스위치: 엔진 기본 0 / from_ascii 기본 0 / 꺼진 판 act wait=탐색 폴백(환각 방어)·메뉴 미노출
  ② 개시: act wait → order='wait'+waiting, 메뉴에 '기다린다' 옵션, then 은 못 잇는다(열린 결말)
  ③ 지루함 상한: WAIT_MAX 틱 waiting 지속 → wait_bored+order·plan 파기(재결정)
  ④ 깨어남(동료): 시야 밖 동료가 시야에 들어오면 wait_met(allies) — 떠났다 돌아와도 새 존재
  ⑤ 깨어남(새 몹): 몹이 시야에 들어오면 encounter(인카운터 문법 그대로)
  ⑥ 깨어남(말 걸림): hail_stop 이 wait order 를 끊는다(D24 합류)
  ⑦ 창 배타: 대기 틱은 맴돎(wander)·무발견(dry) 어느 창에도 안 쌓인다
  ⑧ 문장: wait_bored/wait_met 렌더 — 물음표 0(관찰 사실만)
  ⑨ 작정: plan_step 의 wait 수 유효("계단 가서 기다려" 저작 가능)
(기존 verify 22종은 별도 실행.)
"""
import brains
import dungeon_gm as G
from dungeon_gm import Dungeon


class C:
    failed = 0


def check(name, cond):
    print(("  OK   " if cond else " FAIL  ") + name)
    if not cond:
        C.failed += 1


def mkbot(char, x, y):
    return {'char': char, 'x': x, 'y': y, 'hp': 14, 'maxhp': 14,
            'str': 3, 'dex': 0, 'wdmg': 4, 'stealth': 0,
            'search_r': 1, 'job': '전사', 'sex': '남', 'persona': '', 'bag': 0,
            'alive': True, 'won': False, 'order': None, 'path': [],
            'aware_of': set(), 'plan': []}


ROWS = ["##############",
        "#1...........#",
        "#............#",
        "#####>########"]


def stage(wait_verb=True, ally_far=True):
    d, _ = Dungeon.from_ascii(ROWS, scan=True)
    d.wait_verb = wait_verb
    b1 = mkbot('1', 1, 1)
    b2 = mkbot('2', 12, 2 if ally_far else 1)      # (12,2)=시야 5 밖
    bots = [b1, b2]
    for b in bots:
        d.view(b, bots)
    return d, b1, b2, bots


print("── ① 스위치")
check("① 엔진 직생성 기본 wait_verb=0", Dungeon(seed=7).wait_verb is False)
d0, _ = Dungeon.from_ascii(ROWS, scan=True)
check("① from_ascii 기본 wait_verb=0", d0.wait_verb is False)
d1, b1, _, bots1 = stage(wait_verb=False)
r1 = d1.act(b1, {'type': 'wait'}, bots1)
check("① 꺼진 판 act wait = 탐색 폴백(환각 방어)", r1.get('type') == 'explore')
o1 = d1.view(b1, bots1)
check("① 꺼진 판 메뉴에 '기다린다' 없음",
      not any(op.get('type') == 'wait' for op in o1.get('options') or []))

print("── ② 개시")
d2, b2a, _, bots2 = stage()
r2 = d2.act(b2a, {'type': 'wait', 'then': [{'type': 'search'}]}, bots2)
check("② act wait → order='wait'+waiting", r2.get('result') == 'waiting'
      and b2a.get('order') == 'wait')
check("② then 은 wait 뒤에 못 잇는다(열린 결말 — 동행 선례)", b2a.get('plan') == [])
o2 = d2.view(b2a, bots2)
check("② 메뉴에 '기다린다' 옵션",
      any(op.get('type') == 'wait' for op in o2.get('options') or []))

print("── ③ 지루함 상한")
res3 = []
for _ in range(G.WAIT_MAX + 3):
    if not b2a.get('order'):
        break
    res3.append(d2.step_order(b2a, bots2))
check("③ WAIT_MAX-1 틱 waiting 지속(대기 중 재결정 없음=LLM 0콜 구조)",
      len(res3) == G.WAIT_MAX
      and all(r.get('result') == 'waiting' for r in res3[:-1]))
check("③ 상한 도달 = wait_bored + order 파기(재결정)",
      res3[-1].get('result') == 'wait_bored' and not b2a.get('order')
      and res3[-1].get('ticks') == G.WAIT_MAX)

print("── ④ 깨어남 — 동료 시야 진입")
d4, b4, c4, bots4 = stage()
d4.act(b4, {'type': 'wait'}, bots4)
r4a = d4.step_order(b4, bots4)
c4['x'], c4['y'] = 4, 1                            # 동료가 시야 안으로 걸어 들어왔다
r4b = d4.step_order(b4, bots4)
check("④ 동료 진입 = wait_met(allies)+order 파기",
      r4a.get('result') == 'waiting' and r4b.get('result') == 'wait_met'
      and r4b.get('allies') == ['2'] and not b4.get('order'))

print("── ⑤ 깨어남 — 새 몹")
d5, b5, _, bots5 = stage()
m = G.Monster(12, 1, mid=0)
d5.monsters.append(m)
d5.act(b5, {'type': 'wait'}, bots5)
r5a = d5.step_order(b5, bots5)
m.x, m.y = 4, 1                                    # 몹이 시야에 들어왔다
r5b = d5.step_order(b5, bots5)
check("⑤ 새 몹 = encounter(인카운터 문법)+order 파기",
      r5a.get('result') == 'waiting' and r5b.get('result') == 'encounter'
      and r5b.get('monsters') and not b5.get('order'))

print("── ⑥ 깨어남 — 말 걸림(D24 합류)")
d6, b6, _, bots6 = stage()
d6.hail = True
d6.turn = 5
d6.act(b6, {'type': 'wait'}, bots6)
check("⑥ hail_stop 이 wait 를 끊는다", d6.hail_stop(b6, ['2']) == ['2']
      and not b6.get('order') and (b6.get('last') or {}).get('type') == 'hail')

print("── ⑦ 창 배타")
d7, b7, _, bots7 = stage()
d7.selfstop = True
d7.dry_signal = True
d7.act(b7, {'type': 'wait'}, bots7)
b7['dry'] = 4
b7['wander'] = {'cells': set(), 'n': 2}
d7.step_order(b7, bots7)
d7.step_order(b7, bots7)
check("⑦ 대기 틱 = 맴돎·무발견 창 무증가(자연 배타)",
      b7.get('dry') == 4 and (b7.get('wander') or {}).get('n') == 2)

print("── ⑧ 문장")
p_bored = brains._last_prose({'type': 'walk', 'result': 'wait_bored', 'ticks': 15})
p_met = brains._last_prose({'type': 'walk', 'result': 'wait_met', 'allies': ['2']}, {'2': '카야'})
check("⑧ bored/met 렌더 + 물음표 0(관찰 사실만)",
      '기다렸다' in p_bored and '?' not in p_bored
      and '카야' in p_met and '?' not in p_met)

print("── ⑨ 작정 수 유효")
d9, b9, _, bots9 = stage()
b9['plan'] = [{'type': 'wait'}]
step9 = d9.plan_step(b9, bots9)
check("⑨ plan_step 의 wait 수 = 유효(열린 동사 — '계단 가서 기다려')",
      step9 is not None and step9.get('type') == 'wait'
      and (b9.get('last') or {}).get('type') != 'plan_broken')

print()
if C.failed:
    print("FAIL — %d개 실패" % C.failed)
    raise SystemExit(1)
print("ALL PASS — verify_wait (D25 제자리 대기: 사건이 깨운다·숫자 없음·셔틀의 고정점)")

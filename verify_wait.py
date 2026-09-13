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
  ⑩ 동료 관측(D25 개정 2026-09-12): 기다리는 동료 항목에 waiting=true → 동료 줄 "(대기중)" · 대기 틱에도 유지 ·
     깨면(hail_stop) 사라짐 · 꺼진 판(wait_verb=0)엔 없음 — 파트너 "대기중이라는 걸 추가해볼까? 하나씩"
(기존 verify 22종은 별도 실행.)
"""
import brains
import show_runner   # ⑫ act_summary
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
print("── ⑩ 동료 관측 — 대기중 태그(D25 개정 2026-09-12)")
names10 = {'1': '두란', '2': '카야'}
d10, b10, c10, bots10 = stage()
c10['x'], c10['y'] = 4, 1                                      # 동료(2)를 시야 안(④와 같은 자리)에 — 기다리는 몸이 보인다
d10.act(b10, {'type': 'wait'}, bots10)
o10 = d10.view(c10, bots10)
a10 = next(a for a in o10['sights']['bots'] if a['char'] == '1')
check("⑩ 동료 항목 waiting=True(기다리는 몸이 보인다)", a10.get('waiting') is True and a10.get('resting') is None)
check("⑩ 동료 줄 '(대기중)'", "(대기중)" in brains._wire(o10, names10))
d10.step_order(b10, bots10)                                    # 대기 틱(아직 아무 일 없음)
o10b = d10.view(c10, bots10)
check("⑩ 대기 틱에도 유지", next(a for a in o10b['sights']['bots'] if a['char'] == '1').get('waiting') is True)
d10.hail = True; d10.turn = 5                                  # 말 걸림 스위치(⑥과 같은 전제)
d10.hail_stop(b10, ['2'])                                      # 말 걸림이 대기를 끊는다(⑥) → 태그도 사라진다
o10c = d10.view(c10, bots10)
check("⑩ 깨면(hail_stop) 태그 사라짐",
      not next(a for a in o10c['sights']['bots'] if a['char'] == '1').get('waiting') and "(대기중)" not in brains._wire(o10c, names10))
d10x, b10x, c10x, bots10x = stage(wait_verb=False)
c10x['x'], c10x['y'] = 4, 1
d10x.act(b10x, {'type': 'wait'}, bots10x)                      # 꺼진 판 = 탐색 폴백 → order 는 wait 가 아니다
o10x = d10x.view(c10x, bots10x)
check("⑩ 꺼진 판(wait_verb=0) 동료 항목에 waiting 없음",
      'waiting' not in next(a for a in o10x['sights']['bots'] if a['char'] == '1'))

print("── ⑪ 깨어남 — 보이던 동료가 곁에 닿음(D25 개정 3, 2026-09-13)")
d11, b11, c11, bots11 = stage(ally_far=False)
c11['x'], c11['y'] = 5, 1                               # 시야 안(거리 4)·곁은 아님 — '보이던 동료'
d11.view(b11, bots11)
d11.relations = True                                    # 관계 장부(D36) — '나를 기다려 줌' 뼈를 잰다
d11.act(b11, {'type': 'wait'}, bots11)
r11a = d11.step_order(b11, bots11)
check("⑪ 보이는 동료가 그대로면 waiting(첫 틱 곁=도착 아님)", r11a.get('result') == 'waiting' and b11.get('order') == 'wait')
c11['x'], c11['y'] = 2, 1                               # 곁(체비셰프 1)으로
r11b = d11.step_order(b11, bots11)
check("⑪ 곁 도착 → wait_met{beside} + order 파기 + 상대 장부 '나를 기다려 줌'",
      r11b.get('result') == 'wait_met' and r11b.get('beside') is True and r11b.get('allies') == ['2'] and not b11.get('order')
      and (((c11.get('relations') or {}).get('1') or {}).get('bones') or {}).get('waited', {}).get('n', 0) >= 1)

print("── ⑫ 깨어남 — 기다리던 동료가 시야를 떠남")
d12, b12, c12, bots12 = stage(ally_far=False)
c12['x'], c12['y'] = 5, 1                               # 시야 안 — 기다리던(보이던) 동료
d12.view(b12, bots12)
d12.act(b12, {'type': 'wait'}, bots12)
d12.step_order(b12, bots12)
c12['x'], c12['y'] = 12, 2                              # 시야 밖으로
r12 = d12.step_order(b12, bots12)
check("⑫ 시야 이탈 → wait_left{allies} + order 파기", r12.get('result') == 'wait_left' and r12.get('allies') == ['2'] and not b12.get('order'))
check("⑫ 문장·꼬리표·러너 요약", "시야에서 사라졌다" in brains._last_prose(dict(r12), {'2': '카야'})
      and any(k == 'lost' for k, _, _ in G.event_tags(dict(r12, char='1')))
      and "시야 이탈" in show_runner.act_summary(dict(r12, type='walk')))
check("⑫ 상한 5틱(15→5, 파트너 '계획하고 나서 한참 서 있는다')", G.WAIT_MAX == 5)

print("── ⑬ 모임 규칙을 관측에 미리(D66) · 계단 대기 문장은 규칙을 말한다")
d13, b13, c13, bots13 = stage(ally_far=True)           # 동료 시야 밖·계단 먼 곳
d13.trail_on = True                                     # 궤적 판(D40) — ⑬ 마지막 검사가 꼬리표 경로를 탄다
o13 = d13.view(b13, bots13)
ex13 = o13['sights'].get('exit')
check("⑬ 계단이 보이고 exit.gather{missing[{char, seen}]}", bool(ex13) and (ex13.get('gather') or {}).get('missing') == [{'char': '2', 'seen': False}])
w13 = brains._wire(o13, {'1': '두란', '2': '카야'}, compose=False)
check("⑬ 프롬프트 계단 줄: '함께 내려가려면 카야도 곁에 와야 한다(카야 시야 밖)' + '일행 전원'", "함께 내려가려면 카야도 곁에 와야 한다(카야 시야 밖)" in w13 and "일행 전원이 곁(3칸 안)에 모여야 한다" in w13)
c13['x'], c13['y'] = 4, 2                               # 계단 곁(3칸 안)·시야 안 → gather 없음
o13b = d13.view(b13, bots13)
check("⑬ 다 모이면 gather 없음", 'gather' not in (o13b['sights'].get('exit') or {}))
r13 = {'type': 'interact', 'target': 'exit', 'result': 'wait_allies', 'dir': 'down', 'missing': ['2'], 'busy': []}
p13 = brains._last_prose(r13, {'1': '두란', '2': '카야'})
check("⑬ wait_allies 문장 = 규칙 + 이름", "살아 있는 일행 전원이 곁(3칸 안)에 모이고 하던 일을 마쳐야 함께 쓴다" in p13 and "빠진 동료: 카야" in p13 and "봇2" not in p13)
b13['trail'] = [{'kind': 'wait_allies', 'turn': 3}]
b13['last'] = r13
o13c = d13.view(b13, bots13)
w13c = brains._wire(o13c, {'1': '두란', '2': '카야'}, compose=False)
check("⑬ 궤적 판에서도 '왜 안 됐나' 줄이 닿는다(D40 사각지대 수선)", "왜 안 됐나" in w13c and "일행 전원" in w13c)

if C.failed:                                                   # 09-12: 검사 실패가 있으면 ALL PASS 를 찍지 않는다(게이트 러너는 그 문자열로 판정)
    print("FAILED — verify_wait: %d 검사 실패" % C.failed)
    raise SystemExit(1)
print("ALL PASS — verify_wait (D25 제자리 대기: 사건이 깨운다·숫자 없음·셔틀의 고정점 · ⑩ 대기중 태그 · ⑪⑫ 곁 도착·이탈 깨움·상한 5 · ⑬ 모임 규칙 관측·문장 D66)")

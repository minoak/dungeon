# -*- coding: utf-8 -*-
"""이동중 표시(D27, 2026-07-24 파트너 발제·간소화 교정 "간단히 (이동중) 하나만") 검증 — 25번째 게이트.
몸짓도 시야를 탄다(D18 '상처도 시야를 탄다'의 연장): 보이는 동료가 걷는 중이면 상태에 moving
깃발 하나. 방향·목적지·경로 비노출(마음이 아니라 몸짓만 — 그건 say 의 몫). 큰 판 2차 부검의
군집 가설(파트너: "동료가 뭘 하는지 몰라서 붙어 다니는 걸 수도") 검증 재료.
게이트:
  ① 스위치: 엔진 기본 0 / from_ascii 기본 0 / 꺼진 판 = moving 키 자체가 없음
  ② 걷는 동료(order+path) = moving:true / 서 있는 동료 = 키 없음(추가 상태 어휘 없음)
  ③ wait 동료 = 키 없음(겉보기 '서 있음'과 동일 — 마음 비노출)
  ④ 경로 비노출: 동료 항목에 heading/path/목적지 필드 없음
  ⑤ wire 렌더: 걷는 동료만 "(이동중)" 접미 — 두 렌더 경로(스캔 트리·플랫)
  ⑥ 고른 행동(D27 개정 2026-09-12, 파트너 "동료의 현재 어떤 행동을 선택했는지에 대한 상태를 보여주면"):
     스위치 ally_doing(엔진 기본 0·from_ascii 0) 켠 판만 동료 항목에 doing{act,target?,name?} — 탐색(@좌표는 'explore'뿐)·
     계단 goto(이름)·동료 goto(chase, char)·wait — 서 있는 동료(order 없음)엔 키 없음 · 렌더 "(탐색 중)"·"(이동 중 → 출구)"·
     "(두란에게 가는 중)"·"(기다리는 중)"이 몸짓 깃발 대신 · 꺼진 판엔 doing 없음(⑤ 문안 불변)
(기존 verify 24종은 별도 실행.)
"""
import brains
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


ROWS = ["##########",
        "#1.2..3..#",
        "#........#",
        "####>#####"]


def stage(motion=True, wait_verb=False):
    d, _ = Dungeon.from_ascii(ROWS, scan=True)
    d.motion = motion
    d.wait_verb = wait_verb
    a, b, c = mkbot('1', 1, 1), mkbot('2', 3, 1), mkbot('3', 6, 1)
    bots = [a, b, c]
    for x in bots:
        d.view(x, bots)
    d.act(b, {'type': 'goto', 'target': '@8,2'}, bots)     # 봇2 = 걷는 중
    return d, a, b, c, bots


def ally(obs, char):
    return next((x for x in (obs.get('sights') or {}).get('bots', [])
                 if x.get('char') == char), None)


print("── ① 스위치")
check("① 엔진 직생성 기본 motion=0", Dungeon(seed=7).motion is False)
d0, _ = Dungeon.from_ascii(ROWS, scan=True)
check("① from_ascii 기본 motion=0", d0.motion is False)
d1, a1, b1, c1, bots1 = stage(motion=False)
o1 = d1.view(a1, bots1)
check("① 꺼진 판 = moving 키 자체가 없음",
      ally(o1, '2') is not None and 'moving' not in ally(o1, '2'))

print("── ② 걷는 동료 / 서 있는 동료")
d2, a2, b2, c2, bots2 = stage()
o2 = d2.view(a2, bots2)
check("② 걷는 동료(order+path) = moving:true", (ally(o2, '2') or {}).get('moving') is True)
check("② 서 있는 동료 = 키 없음(상태 어휘 추가 없음)",
      ally(o2, '3') is not None and 'moving' not in ally(o2, '3'))

print("── ③ wait 동료")
d3, a3, b3, c3, bots3 = stage(wait_verb=True)
d3.act(c3, {'type': 'wait'}, bots3)
o3 = d3.view(a3, bots3)
check("③ wait 동료 = 키 없음(겉보기 '서 있음' — 마음 비노출)",
      ally(o3, '3') is not None and 'moving' not in ally(o3, '3'))

print("── ④ 경로 비노출")
a2m = ally(o2, '2')
check("④ 동료 항목에 heading/path/목적지 없음(깃발 하나뿐)",
      not any(k in a2m for k in ('heading', 'path', 'target', 'order')))

print("── ⑤ wire 렌더")
w5 = brains._wire(o2)
# 트리 렌더는 같은 방위 동료를 한 줄에 합친다 — 항목(거리 접미) 단위로 판정
check("⑤ 걷는 동료만 '(이동중)' 접미(스캔 트리 경로 — 봇2 2m만, 봇3 5m엔 없음)",
      '2m (이동중)' in w5 and '5m (이동중)' not in w5)
d5, _ = Dungeon.from_ascii(ROWS)               # scan=0 → 플랫 렌더 경로
d5.motion = True
a5, b5 = mkbot('1', 1, 1), mkbot('2', 3, 1)
bots5 = [a5, b5]
for x in bots5:
    d5.view(x, bots5)
d5.act(b5, {'type': 'goto', 'target': '@8,2'}, bots5)
w5b = brains._wire(d5.view(a5, bots5), {'1': '두란', '2': '카야'})
# ⚠️ names 를 넘기는 이유(2026-07-29 솔로 판 도입 때 드러남): 이름을 모르는 사람은 이제
# '동료 카야'가 아니라 '낯선 사람(봇2)'으로 렌더된다(솔로 판=로스터 없음). 프로덕션은
# claude_brain 이 늘 names 를 넘기므로, 여기서도 같은 입력을 줘야 파티 문안을 시험한다.
check("⑤ 플랫 렌더 경로에도 '(이동중)'",
      any('동료' in ln and '(이동중)' in ln for ln in w5b.splitlines()))

print("── ⑥ 고른 행동(D27 개정 2026-09-12)")
check("⑥ 엔진 직생성 기본 ally_doing=0 / from_ascii 기본 0",
      Dungeon(seed=7).ally_doing is False and Dungeon.from_ascii(ROWS, scan=True)[0].ally_doing is False)
d6, a6, b6, c6, bots6 = stage(wait_verb=True)          # 봇2 = @8,2 로 걷는 중
d6.ally_doing = True
o6 = d6.view(a6, bots6)
check("⑥ 탐색 중인 동료 = doing{act:explore}(좌표 비노출) · 서 있는 동료 = 키 없음",
      (ally(o6, '2') or {}).get('doing') == {'act': 'explore'} and 'doing' not in (ally(o6, '3') or {}))
d6.act(c6, {'type': 'goto', 'target': 'exit'}, bots6)   # 봇3 = 계단으로
o6b = d6.view(a6, bots6)
check("⑥ 계단 goto = doing{act:goto, target:exit, name:출구}",
      (ally(o6b, '3') or {}).get('doing') == {'act': 'goto', 'target': 'exit', 'name': '출구'})
names6 = {'1': '두란', '2': '카야', '3': '피른'}
w6 = brains._wire(o6b, names6)
check("⑥ 렌더: '(탐색 중)' · '(이동 중 → 출구)' 가 몸짓 깃발 대신(이동중 표기 없음)",
      any('카야' in ln and '(탐색 중)' in ln for ln in w6.splitlines())
      and any('피른' in ln and '(이동 중 → 출구)' in ln for ln in w6.splitlines()) and '(이동중)' not in w6)
d6.act(c6, {'type': 'goto', 'target': 'b1'}, bots6)     # 봇3 = 두란에게(D48 추적)
o6c = d6.view(a6, bots6)
check("⑥ 동료 goto = doing{act:chase, target:'1'} → '(두란에게 가는 중)'",
      (ally(o6c, '3') or {}).get('doing') == {'act': 'chase', 'target': '1'}
      and any('피른' in ln and '두란' in ln and '에게 가는 중)' in ln for ln in brains._wire(o6c, names6).splitlines()))   # who()='동료 두란(봇1)'
d6.act(c6, {'type': 'wait'}, bots6)                     # 봇3 = 대기
o6d = d6.view(a6, bots6)
check("⑥ wait = doing{act:wait} + waiting 깃발 공존 → 렌더는 '(기다리는 중)' 하나",
      (ally(o6d, '3') or {}).get('doing') == {'act': 'wait'} and (ally(o6d, '3') or {}).get('waiting') is True
      and any('피른' in ln and '(기다리는 중)' in ln and '(대기중)' not in ln for ln in brains._wire(o6d, names6).splitlines()))
d6.ally_doing = False
o6e = d6.view(a6, bots6)
check("⑥ 꺼진 판 = doing 키 없음(몸짓 깃발 문안 불변)",
      all('doing' not in x for x in o6e['sights']['bots']) and '(이동중)' in brains._wire(o6e, names6))

print()
if C.failed:
    print("FAIL — %d개 실패" % C.failed)
    raise SystemExit(1)
print("ALL PASS — verify_motion (D27 이동중 표시: 깃발 하나·방향 비노출·몸짓만 · ⑥ 고른 행동 D27 개정)")

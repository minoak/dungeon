# -*- coding: utf-8 -*-
"""말 걸림 정지(D24, 2026-07-24 파트너 확정) 헤들리스 검증 — 22번째 게이트.
여섯 번째 정지 신호: 시야 안 동료의 말이 들리면(배달=러너 inbox 기존 규칙) 걷던 작정을 멈추고
결정권을 받는다 — 강제 응답 아님(관찰 제시+판단 위임, 처방 사다리 ③). 들리는 전원이 멈춘다
(이름 파싱=뒷문 기각). 수다 루프 방어=같은 발화자 쿨다운(HAIL_CD, 쌍 단위·구조) — 쿨다운 중엔
정지만 없고 메시지는 그대로 배달. 부속: 인스턴스 던전=현 단계 공식 가정(신뢰 전제 문법).
게이트:
  ① 스위치: 엔진 기본 0 / from_ascii 기본 0 / 꺼짐이면 무정지([] 반환·작정 무손상)
  ② 정지: 걷던(order) 봇 hail → order·path·plan 파기 + last=hailed(froms) + froms 반환
  ③ order 없는 봇 = 무정지(이미 다음 틱 결정 예정 — 앞당길 것이 없다)
  ④ 쿨다운: 성사 직후 같은 발화자 = 무정지(HAIL_CD 턴), 경과 후 재정지, 다른 발화자는 즉시
  ⑤ 죽은/탈출 봇 = 무정지(엔진 자체 가드)
  ⑥ 문장: last=hailed 렌더 — 발화자 이름 실림 + 물음표 0(관찰 사실만)
(기존 verify 21종은 별도 실행.)
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


ROWS = ["##########",
        "#1.......#",
        "#........#",
        "####>#####"]


def stage(hail=True):
    d, _ = Dungeon.from_ascii(ROWS, scan=True)
    d.hail = hail
    d.turn = 10
    b = mkbot('1', 1, 1)
    d.view(b, [b])
    d.act(b, {'type': 'goto', 'target': '@8,1'}, [b])   # 걷는 중
    b['plan'] = [{'type': 'search'}]                    # 작정 보유(파기 검증용 프리셋)
    return d, b


print("── ① 스위치")
check("① 엔진 직생성 기본 hail=0", Dungeon(seed=7).hail is False)
d0, _ = Dungeon.from_ascii(ROWS, scan=True)
check("① from_ascii 기본 hail=0", d0.hail is False)
d1, b1 = stage(hail=False)
check("① 꺼짐 = 무정지·작정 무손상",
      d1.hail_stop(b1, ['2']) == [] and b1.get('order') and b1.get('plan'))

print("── ② 정지(작정 파기+자기 관측)")
d2, b2 = stage()
got2 = d2.hail_stop(b2, ['2'])
check("② 성사: froms 반환 + order·path·plan 파기",
      got2 == ['2'] and not b2.get('order') and not b2.get('path') and not b2.get('plan'))
check("② 자기 관측: last=hailed(froms)",
      (b2.get('last') or {}).get('type') == 'hail'
      and (b2.get('last') or {}).get('froms') == ['2'])

print("── ③ order 없는 봇")
d3, b3 = stage()
b3['order'], b3['path'], b3['plan'] = None, [], []
check("③ 이미 결정 예정 = 무정지([])", d3.hail_stop(b3, ['2']) == [])

print("── ④ 쿨다운(쌍 단위·구조)")
d4, b4 = stage()
d4.hail_stop(b4, ['2'])                                     # t10 성사 → 쿨다운 t10+3
d4.act(b4, {'type': 'goto', 'target': '@8,1'}, [b4])   # 다시 걷는다
d4.turn = 11
check("④ 같은 발화자 즉시 재hail = 무정지", d4.hail_stop(b4, ['2']) == [] and b4.get('order'))
check("④ 다른 발화자는 즉시 정지(쌍 단위)", d4.hail_stop(b4, ['3']) == ['3'])
d4.act(b4, {'type': 'goto', 'target': '@8,1'}, [b4])
d4.turn = 13                                           # t10+3 경과
check("④ 쿨다운 경과 후 같은 발화자 재정지", d4.hail_stop(b4, ['2']) == ['2'])

print("── ⑤ 죽은/탈출 봇")
d5, b5 = stage()
b5['alive'] = False
check("⑤ 죽은 봇 = 무정지", d5.hail_stop(b5, ['2']) == [])
d5b, b5b = stage()
b5b['won'] = True
check("⑤ 탈출 봇 = 무정지", d5b.hail_stop(b5b, ['2']) == [])

print("── ⑥ 문장")
p = brains._last_prose({'type': 'hail', 'result': 'hailed', 'froms': ['2']}, {'2': '카야'})
check("⑥ 발화자 이름 렌더 + 물음표 0(관찰 사실만)", '카야' in p and '?' not in p)

print()
if C.failed:
    print("FAIL — %d개 실패" % C.failed)
    raise SystemExit(1)
print("ALL PASS — verify_hail (D24 말 걸림 정지: 들리는 전원·쿨다운=구조·판단은 두뇌 몫)")

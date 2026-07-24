# -*- coding: utf-8 -*-
"""무발견 신호(층 1, 07-24 합의 — 파트너 발제) 헤들리스 검증 — 21번째 게이트.
"마지막 새 목격 이후 K걸음" 카운터. 임계 도달 '시점'에만: ①그 걸음 결과 이벤트에 dry(계측 열)
②다음 결정 obs 에 dry 1회(배달 후 비움 — witnessed 문법). 관찰 사실만(질문·조향 금지),
상시 노출 금지(소음 방지 — 파트너 확정). 탐색 커버리지 문제라 걸음만 센다 — 제자리 틱은
탐색이 아니다(맴돎 D21의 박자와 다른 자). 결정(act)은 리셋 안 함("마지막 새 목격 이후"가
자의 전부). 새 목격=리셋+미배달 신호 파기(낡은 사실 배달 금지). 셔틀(결정 0 구간)엔 안 닿는
보완층(그쪽 그물=D21 맴돎).
게이트:
  ① 스위치: 엔진 기본 0 / from_ascii 기본 0 / dry_signal 켜도 scan 없으면 무부기
  ② 도달 시점: K걸음 무증분 → 그 걸음 이벤트에 dry=K, 이후 걸음엔 없음(연사 없음) —
     act(결정) 사이를 건너 누적(리셋 없음)
  ③ 배달: 다음 view() 에 dry 1회 실리고 비워진다
  ④ 리셋·파기: 새 목격 → 카운터 0 + 미배달 신호 파기
  ⑤ 재무장: 리셋 뒤 다시 K걸음 → 재발화
  ⑥ 문장: wire 렌더에 신호 문장 — 물음표 0(질문형 금지)
  ⑦ 제자리 틱(follow 곁 대기)은 걸음이 아니다 — dry 무증가
(기존 verify 20종은 별도 실행.)
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


def walk(d, b, bots, tx, ty, cap=80):
    """@x,y 핑 → 걸음 결과 목록(도달 or 정지까지)."""
    d.act(b, {'type': 'goto', 'target': '@%d,%d' % (tx, ty)}, bots)
    out = []
    for _ in range(cap):
        if not b.get('order'):
            break
        out.append(d.step_order(b, bots))
    return out


# 무대: 윗줄 복도(x1~8) + 오른끝 세로 통로 + 아랫줄 포켓(윗줄에서 LOS 불가) + 봉인 계단
ROWS = ["##########",
        "#1.......#",
        "########.#",
        "########.#",
        "#........#",
        "#>########",
        "##########"]

print("── ① 스위치 기본값")
check("① 엔진 직생성 기본 dry_signal=0", Dungeon(seed=7).dry_signal is False)
d0, _ = Dungeon.from_ascii(ROWS, scan=True)
check("① from_ascii 기본 dry_signal=0", d0.dry_signal is False)
d0.dry_signal = True
d0.scan = False                       # scan 없으면 장부(seen_cells)가 없다 — 무부기
b0 = mkbot('1', 1, 1)
d0.view(b0, [b0])
walk(d0, b0, [b0], 8, 1)
check("① scan=0 이면 무부기(dry 키 자체가 없다)", 'dry' not in b0)

print("── ② 도달 시점(연사 없음·결정 무리셋)")
d1, _ = Dungeon.from_ascii(ROWS, scan=True)
d1.dry_signal = True
b1 = mkbot('1', 1, 1)
bots1 = [b1]
d1.view(b1, bots1)
legs = [walk(d1, b1, bots1, 8, 1)]        # 첫 주파 — 새 칸 계속 → dry 리셋 반복
# 아는 복도 왕복(결정 4번 사이를 건너 누적 — K=25 도달)
for tx in (1, 8, 1, 8):
    legs.append(walk(d1, b1, bots1, tx, 1))
res = [r for leg in legs for r in leg]
dry_ev = [r for r in res if 'dry' in r]
check("② 도달 시점의 걸음 이벤트 정확히 1개 — dry=%d" % G.DRY_K,
      len(dry_ev) == 1 and dry_ev[0]['dry'] == G.DRY_K)
check("② 도달 이후 걸음(dry>K)엔 재발화 없음 + 카운터는 계속 는다",
      b1.get('dry', 0) > G.DRY_K)

print("── ③ 배달(1회성 — witnessed 문법)")
o1 = d1.view(b1, bots1)
check("③ 다음 view 에 dry 실림(도달 이후 현재 걸음 수)", o1.get('dry', 0) >= G.DRY_K)
o2 = d1.view(b1, bots1)
check("③ 두 번째 view 엔 없음(배달 후 비움)", 'dry' not in o2)

print("── ④ 리셋·파기(새 목격)")
b1['dry_hit'] = True                  # 미배달 신호 상태 재현
walk(d1, b1, bots1, 8, 4)             # 세로 통로 → 아랫줄 — 새 칸이 드러난다(포켓은 LOS 불가였다)
check("④ 새 목격 = 카운터 0 리셋 + 미배달 신호 파기",
      b1.get('dry', 99) < G.DRY_K and not b1.get('dry_hit'))
check("④ 파기 후 view 에 dry 없음(낡은 사실 배달 금지)", 'dry' not in d1.view(b1, bots1))

print("── ⑤ 재무장(리셋 뒤 다시 K걸음)")
for tx, ty in ((8, 4), (1, 4)) * 5:   # 다 본 아랫줄 왕복 — 끝칸에서만 보이는 벽 모서리·계단이
                                      #   초반 왕복까지 리셋을 만든다(실측: 4번째 왕복부터 무증분)
    walk(d1, b1, bots1, tx, ty)
o5 = d1.view(b1, bots1)
check("⑤ 리셋 뒤 K걸음 재누적 → 재발화·재배달", o5.get('dry', 0) >= G.DRY_K)

print("── ⑥ 문장(wire)")
w = brains._wire({'job': '전사', 'sex': '남', 'hp': 14, 'maxhp': 14, 'str': 3, 'dex': 0,
                  'inventory': 0, 'depth': 1, 'dry': G.DRY_K, 'last': None})
line6 = next((ln for ln in w.splitlines() if '새로 보이는' in ln), '')
check("⑥ 신호 문장 렌더 + 물음표 0(관찰 사실만)", line6 != '' and '?' not in line6)

print("── ⑦ 제자리 틱은 걸음이 아니다")
d7, _ = Dungeon.from_ascii(["#####", "#...#", "##>##", "#####"], scan=True)
d7.dry_signal = True
a7, b7 = mkbot('1', 1, 1), mkbot('2', 2, 1)
bots7 = [a7, b7]
for x in bots7:
    d7.view(x, bots7)
a7['dry'] = 5
d7.act(a7, {'type': 'follow', 'target': 'b2'}, bots7)   # 곁 — 대기 틱만 발생
d7.step_order(a7, bots7)
d7.step_order(a7, bots7)
check("⑦ follow 곁 대기 2틱 = dry 무증가(걸음만 센다)", a7.get('dry') == 5)

print()
if C.failed:
    print("FAIL — %d개 실패" % C.failed)
    raise SystemExit(1)
print("ALL PASS — verify_dry (무발견 신호: K걸음 도달 1회·배달 1회·새 목격 파기)")

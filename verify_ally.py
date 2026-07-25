# -*- coding: utf-8 -*-
"""동료 시야 면제(2026-07-26 파트너 발제) 검증 — 27번째 게이트.

왜: 2026-07-26 큰 판 부검에서 파티가 서로를 못 보는 시간이 **44%**였고, 그중 압도적
다수가 거리 2칸이었다(문·벽 모퉁이 하나 차이). 문 낀 이동의 시야 단절률은 28% vs 그 외
2% — 14배. 선두가 문을 넘는 순간 후미의 시야에서 증발하고, follow 가 마지막 본 자리로
유령 추적을 하다 lost 를 내고, 서로를 되찾으러 문턱을 되넘는 셔틀이 돌았다.
처방: **동료만** 시야 반경 안에서 장애물을 무시한다. 사람은 벽 하나 돌아섰다고 일행을
통째로 잃지 않는다(발소리·기척·직전 기억). 몹·피처·구조는 LOS 그대로다.

⚠️ 왜 게이트인가 — 장면 A/B 로는 판정이 안 된다(2026-07-26 실측 4회):
  · 실 LLM 판: 같은 시드여도 응답이 달라 lost 가 0~2회로 흔들린다(스위치 효과보다 큰 노이즈)
  · 규칙두뇌 판: 결정론이지만 dummy_brain 이 follow 를 안 골라 증상 자체가 안 난다
  시야와 lost 는 물리다 — 판을 돌려 관찰할 게 아니라 여기서 직접 찌른다.

게이트:
  ① 스위치 기본 꺼짐(엔진·from_ascii 양쪽) — 기존 판 비트 동일
  ② 문 너머 동료: 끄면 안 보이고 켜면 보인다
  ③ sights.bots 와 party.visible 이 **같은 판정**(모순 금지)
  ④ 반경 밖은 켜도 안 보인다 — '흩어짐의 비용'은 거리로 남는다
  ⑤ **몹은 면제 아님** — 문 뒤 몹은 켜도 안 보인다(D19 문 광학·매복·인식 대칭 무손상)
  ⑥ **follow 재경로도 같은 눈을 쓴다** — 눈에는 보이는데 발이 못 따라가면 옛 자리로 걸어가
     lost 가 난다(A/B 3차가 드러낸 실제 버그의 회귀 그물)
  ⑦ D27 (이동중) 깃발이 면제된 동료에게도 붙는다
(기존 verify 26종은 별도 실행.)
"""
import os

os.environ["DUNGEON_BESTIARY_FILE"] = ""            # 도감 영속 차단(게이트 격리 원칙)

import dungeon_gm as G                               # noqa: E402
from dungeon_gm import Dungeon                        # noqa: E402


class C:
    failed = 0


def check(name, cond):
    print(("  OK   " if cond else " FAIL  ") + name)
    if not cond:
        C.failed += 1


def mkbot(char, x, y, job="전사"):
    return {'char': char, 'x': x, 'y': y, 'hp': 14, 'maxhp': 14, 'str': 3, 'dex': 0,
            'wdmg': 4, 'stealth': 0, 'search_r': 1, 'job': job, 'sex': '남',
            'persona': '', 'bag': 0, 'alive': True, 'won': False, 'order': None,
            'path': [], 'aware_of': set(), 'plan': [], 'name': {'1': '두란', '2': '카야'}.get(char)}


# 문(+)을 사이에 둔 두 방. 봇1(2,2) · 봇2(7,2) — 체비셰프 5 = **반경 딱 안쪽**이라
# '안 보이는 이유'가 거리가 아니라 오직 문 하나로 격리된다(첫 판 6칸으로 짰다 반경 밖이라
# 실패 — 거리와 차단을 안 가르면 이 게이트는 아무것도 증명하지 못한다).
ROWS = ["############",
        "#....#.....#",
        "#.1..+.2...#",
        "#....#....>#",
        "############"]


def stage(ally_sight, b2=(7, 2)):
    d, _ = Dungeon.from_ascii(ROWS, scan=True)
    d.ally_sight = ally_sight
    bots = [mkbot('1', 2, 2), mkbot('2', b2[0], b2[1], job="도적")]
    for b in bots:
        d.view(b, bots)
    return d, bots


print("== 동료 시야 면제 검증 ==")

# ───────────────────── ① 스위치 기본 꺼짐 ─────────────────────
d0 = Dungeon(w=20, h=10, seed=7, n_monsters=0, n_traps=0, n_lurkers=0)
check("① 엔진 직생성 기본 꺼짐(기존 판 비트 동일)", d0.ally_sight is False)
d1, _ = Dungeon.from_ascii(ROWS, scan=True)
check("① from_ascii 기본 꺼짐 — __new__ 경유라 명시 초기화가 필수(D21·D22 때 밟은 함정)",
      d1.ally_sight is False)

# ───────────────────── ② 문 너머 동료 ─────────────────────
d, bots = stage(False)
off_ids = [a['id'] for a in d.view(bots[0], bots)['sights']['bots']]
d, bots = stage(True)
on_ids = [a['id'] for a in d.view(bots[0], bots)['sights']['bots']]
check("② 끄면 문 너머 동료가 안 보인다(현행 D19 문 광학)", off_ids == [])
check("② 켜면 보인다(반경 안 · 장애물 무관)", on_ids == ['b2'])

# ───────────────────── ③ 두 표현의 일관 ─────────────────────
ok3 = True
for flag in (False, True):
    d, bots = stage(flag)
    o = d.view(bots[0], bots)
    in_sights = any(a['id'] == 'b2' for a in o['sights']['bots'])
    in_party = next(p['visible'] for p in o['party'] if p['char'] == '2')
    ok3 = ok3 and (in_sights == in_party)
check("③ sights.bots 와 party.visible 이 같은 판정 —"
      " 갈리면 '목록엔 있는데 명단엔 안 보임'이 obs 에 실린다", ok3)

# ───────────────────── ④ 반경 밖은 여전히 잃는다 ─────────────────────
far = G.SIGHT + 3
ROWS_FAR = ["#" * (far + 6),
            "#" + "." * (far + 4) + "#",
            "#.1" + "." * (far) + "2.#"[:3],
            "#" + "." * (far + 2) + ">#",
            "#" * (far + 6)]
d = Dungeon.from_ascii(ROWS_FAR, scan=False)[0]
d.ally_sight = True
bots = [mkbot('1', 2, 2), mkbot('2', 2 + far + 1, 2)]
for b in bots:
    d.view(b, bots)
o = d.view(bots[0], bots)
check("④ 반경 밖은 켜도 안 보인다 — '흩어짐의 비용'은 거리로 남는다",
      not any(a['id'] == 'b2' for a in o['sights']['bots']))

# ───────────────────── ⑤ 몹은 면제 아님 ─────────────────────
ROWS_M = ["############",
          "#....#.....#",
          "#.1..+..g..#",
          "#....#....>#",
          "############"]
d, _ = Dungeon.from_ascii(ROWS_M, scan=True,
                          monsters={'g': {'kind': '고블린', 'state': 'WANDERING'}})
d.ally_sight = True
bots = [mkbot('1', 2, 2)]
d.view(bots[0], bots)
o = d.view(bots[0], bots)
check("⑤ 문 뒤 몹은 켜도 안 보인다 — 동료 한정 면제(D19 문 광학·매복·인식 대칭 무손상)",
      not o['sights']['monsters'])

# ───────────────────── ⑥ follow 재경로도 같은 눈 ─────────────────────
# 봇2 가 봇1 을 follow 하는 중에 봇1 이 문 너머로 이동 → 끄면 옛 자리로 걸어가 lost,
# 켜면 실좌표로 재조준해 계속 따라간다. (A/B 3차가 드러낸 실제 버그의 회귀 그물)
res = {}
for flag in (False, True):
    d, bots = stage(flag, b2=(6, 2))          # 봇2 를 문 위(6,2)에 두고 시작
    a, b = bots[0], bots[1]
    b['x'], b['y'] = 4, 2                     # 봇2 = 추적자(왼쪽 방)
    a['x'], a['y'] = 8, 2                     # 봇1 = 목표(오른쪽 방, 문 너머)
    for x in bots:
        d.view(x, bots)
    b['order'] = 'follow:b1'
    b['path'] = [(5, 2)]                      # 낡은 경로 — 마지막 본 자리로 향한다
    out = []
    for _ in range(8):
        r = d.step_order(b, bots)
        out.append(r.get('result'))
        if r.get('result') in ('lost', 'blocked', 'arrived'):
            break
    res[flag] = out
check("⑥ 끄면 유령 추적 끝에 lost 가 난다(현행 증상 재현)", 'lost' in res[False])
check("⑥ 켜면 실좌표로 재조준해 lost 가 안 난다 —"
      " obs 는 보이는데 재경로만 옛 눈을 보면 발이 못 따라간다",
      'lost' not in res[True])

# ───────────────────── ⑦ D27 깃발 동행 ─────────────────────
d, bots = stage(True)
bots[1]['order'] = 'goto:exit'
bots[1]['path'] = [(9, 2)]
d.motion = True
o = d.view(bots[0], bots)
ally = next((a for a in o['sights']['bots'] if a['id'] == 'b2'), None)
check("⑦ 면제로 보이는 동료에게도 (이동중) 깃발이 붙는다(D27 과 결합)",
      bool(ally) and ally.get('moving') is True)

print()
if C.failed:
    print("FAIL — %d개 실패" % C.failed)
    raise SystemExit(1)
print("ALL PASS — verify_ally (동료 시야 면제: 동료 한정·반경 유지·재경로 동행)")

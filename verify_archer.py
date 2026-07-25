# -*- coding: utf-8 -*-
"""공격 사거리(2026-07-26 파트너 발제: 음유시인→궁수) 검증 — 28번째 게이트.

왜: 파티 셋이 전부 근접이라 대형이라는 게 의미가 없었다. 좁은 통로에서 서로 길을 막고,
다친 캐릭터는 뒤로 빠지면 아예 할 일이 없어진다(큰 판 실측: 카야가 hp2 로 60틱 이탈).
궁수가 들어가면 '뒤에 서는 것'이 후퇴가 아니라 **포지션**이 된다.

설계(파트너 확정):
  · 사거리 2칸, 동료 뒤에서 쏴도 된다
  · 사거리는 시트 atk_range(선택 수치 필드, 기본 1) — 근접 캐릭터는 종전 그대로
  · 명중은 원거리면 DEX(활은 힘이 아니라 겨눔) — 근접은 STR 그대로
  · 몹은 이번엔 근접 유지(활 쓰는 몹은 콘텐츠로 나중에) — 인식 매트릭스 대칭은 재론 대상

게이트:
  ① 기본 1 — atk_range 없는 시트는 종전과 동일(하위호환)
  ② 사거리 — 궁수 1·2칸 O / 3칸 X, 전사 2칸 X
  ③ 사선 — 2칸부터 벽·문이 막는다 / 인접(1칸)은 사선을 안 본다
  ④ **동료는 사선을 막지 않는다**(파트너 확정 — 동료 뒤에서 사격)
  ⑤ 명중 능력치 — 원거리 DEX / 근접 STR
  ⑥ **단일 진실원천** — obs 의 in_range 와 실제 공격 결과가 항상 일치(메뉴에 떴는데
     too_far 가 나오면 캐릭터에게 거짓말이 간다)
  ⑦ 사거리 밖 지목 = too_far (다른 적 몰래치기 금지 — 기존 계약 유지)
  ⑧ 몹은 근접만 — 2칸에서 봇을 못 때린다
(기존 verify 27종은 별도 실행.)
"""
import os

os.environ["DUNGEON_BESTIARY_FILE"] = ""

import dungeon_gm as G                               # noqa: E402
from dungeon_gm import Dungeon                        # noqa: E402


class C:
    failed = 0


def check(name, cond):
    print(("  OK   " if cond else " FAIL  ") + name)
    if not cond:
        C.failed += 1


ARCHER = {'job': '궁수', 'sex': '여', 'hp': 11, 'str': 1, 'dex': 3, 'wdmg': 2,
          'stealth': 2, 'search_r': 1, 'persona': '', 'atk_range': 2}
MELEE = {'job': '전사', 'sex': '남', 'hp': 14, 'str': 3, 'dex': 0, 'wdmg': 4,
         'stealth': 0, 'search_r': 1, 'persona': ''}          # atk_range 없음 = 기본 1


def arena(rows, mons=None):
    d, _ = Dungeon.from_ascii(rows, scan=True, monsters=mons or {})
    return d


def put(d, sheet, char, x, y, bots=None):
    b = G.spawn(d, char, bots or [], sheet=sheet)
    b['x'], b['y'] = x, y
    return b


print("== 공격 사거리(궁수) 검증 ==")

# ───────────────────── ① 기본값 ─────────────────────
d = arena(["##########", "#1......>#", "##########"])
b = put(d, MELEE, '1', 1, 1)
check("① atk_range 없는 시트 = 기본 1(하위호환 — 기존 판 비트 동일)",
      b['atk_range'] == 1)
a = put(d, ARCHER, '3', 1, 1)
check("① 궁수 시트 = 2", a['atk_range'] == 2)

# ───────────────────── ②③ 사거리·사선 ─────────────────────
d = arena(["############", "#3.g......>#", "############"],
          {'g': {'kind': '고블린', 'state': 'WANDERING'}})
ar = put(d, ARCHER, '3', 1, 1)
mon = d.monsters[0]
got = {}
for dist in (1, 2, 3):
    mon.x, mon.y = 1 + dist, 1
    got[dist] = d._can_hit(ar, mon)
check("② 궁수: 1칸 O · 2칸 O · 3칸 X", got == {1: True, 2: True, 3: False})

me = put(d, MELEE, '1', 1, 1)
mon.x, mon.y = 3, 1
check("② 전사: 2칸 X (근접만)", not d._can_hit(me, mon))
mon.x, mon.y = 2, 1
check("② 전사: 1칸 O", d._can_hit(me, mon))

# 벽 너머
dw = arena(["############", "#3#g......>#", "############"],
           {'g': {'kind': '고블린', 'state': 'WANDERING'}})
aw = put(dw, ARCHER, '3', 1, 1)
check("③ 2칸이라도 벽이 막으면 못 쏜다(문 뒤 몹 저격 금지 — D19 광학과 같은 눈)",
      not dw._can_hit(aw, dw.monsters[0]))

# 문 너머
dd = arena(["############", "#3+g......>#", "############"],
           {'g': {'kind': '고블린', 'state': 'WANDERING'}})
ad = put(dd, ARCHER, '3', 1, 1)
check("③ 문도 사선을 막는다", not dd._can_hit(ad, dd.monsters[0]))

# 인접은 사선 무관 — 벽에 바짝 붙은 대각 상황을 만들 수 없으므로 규칙 자체를 확인
dn = arena(["##########", "#3g.....>#", "##########"],
           {'g': {'kind': '고블린', 'state': 'WANDERING'}})
an = put(dn, ARCHER, '3', 1, 1)
check("③ 인접(1칸)은 사선을 안 본다 — 붙어 있는데 벽이 가릴 수는 없다",
      dn._can_hit(an, dn.monsters[0]))

# ───────────────────── ④ 동료는 사선을 안 막는다 ─────────────────────
df = arena(["############", "#3.g......>#", "############"],
           {'g': {'kind': '고블린', 'state': 'WANDERING'}})
af = put(df, ARCHER, '3', 1, 1)
mate = put(df, MELEE, '1', 2, 1, [af])       # 동료가 정확히 사이에 선다
mate['x'], mate['y'] = 2, 1
check("④ 동료가 사선 한가운데 있어도 쏠 수 있다(파트너 확정: 동료 뒤에서 공격)",
      df._can_hit(af, df.monsters[0]))

# ───────────────────── ⑤ 명중 능력치 ─────────────────────
dm = arena(["############", "#3.g......>#", "############"],
           {'g': {'kind': '고블린', 'state': 'HUNTING'}})
am = put(dm, ARCHER, '3', 1, 1)
dm.monsters[0].state = 'HUNTING'             # 기습 유리굴림 배제(굴림 수 고정)
r = dm._attack(am, 'm%d' % dm.monsters[0].id, [am])
check("⑤ 원거리 명중은 DEX 로 굴린다(활은 힘이 아니라 겨눔) — mod=%s, 궁수 dex=%d"
      % (r.get('mod'), am['dex']), r.get('mod') == am['dex'])

dz = arena(["##########", "#1g.....>#", "##########"],
           {'g': {'kind': '고블린', 'state': 'HUNTING'}})
mz = put(dz, MELEE, '1', 1, 1)
dz.monsters[0].state = 'HUNTING'
rz = dz._attack(mz, 'm%d' % dz.monsters[0].id, [mz])
check("⑤ 근접 명중은 STR 그대로(기존 계약 무변경) — mod=%s, 전사 str=%d"
      % (rz.get('mod'), mz['str']), rz.get('mod') == mz['str'])

# ───────────────────── ⑥ 단일 진실원천 ─────────────────────
# obs 에 in_range 로 뜬 몹은 반드시 칠 수 있어야 하고, 안 뜬 몹은 too_far 여야 한다.
ds = arena(["##############",
            "#3...g.......#",
            "#....#.......#",
            "#...g.......>#",
            "##############"],
           {'g': {'kind': '고블린', 'state': 'WANDERING'}})
bs = put(ds, ARCHER, '3', 1, 1)
mismatch = []
for mx in range(1, 12):
    for my in range(1, 4):
        if ds.grid[my][mx] != G.FLOOR:
            continue
        m0 = ds.monsters[0]
        m0.x, m0.y = mx, my
        ds.view(bs, [bs])
        o = ds.view(bs, [bs])
        shown = any(mm.get('in_range') for mm in o['sights']['monsters']
                    if mm['id'] == 'm%d' % m0.id)
        r2 = ds._attack(bs, 'm%d' % m0.id, [bs])
        hittable = r2.get('result') == 'attack'
        seen = (m0.x, m0.y) in ds.visible_cells(bs['x'], bs['y'])
        if seen and shown != hittable:
            mismatch.append((mx, my, shown, hittable))
check("⑥ obs 의 in_range 와 실제 공격 가부가 항상 일치 — 어긋난 칸 %d개"
      " (메뉴에 떴는데 too_far 면 캐릭터에게 거짓말이 간다)" % len(mismatch),
      not mismatch)

# ───────────────────── ⑦ 사거리 밖 지목 ─────────────────────
dt = arena(["############", "#3....g...>#", "############"],
           {'g': {'kind': '고블린', 'state': 'WANDERING'}})
bt = put(dt, ARCHER, '3', 1, 1)
rt = dt._attack(bt, 'm%d' % dt.monsters[0].id, [bt])
check("⑦ 사거리 밖 몹을 지목하면 too_far — 다른 적으로 몰래 폴백하지 않는다",
      rt.get('result') == 'too_far')

# ───────────────────── ⑧ 몹은 근접만 ─────────────────────
dq = arena(["############", "#3..g.....>#", "############"],
           {'g': {'kind': '고블린', 'state': 'HUNTING', 'target': '3'}})
bq = put(dq, ARCHER, '3', 1, 1)
mq = dq.monsters[0]
mq.x, mq.y = 3, 1                      # 봇에서 2칸
mq.state, mq.target = 'HUNTING', '3'
hp0 = bq['hp']
for _ in range(1):
    dq.monster_turn([bq])
check("⑧ 몹은 2칸에서 봇을 못 때린다(몹 근접 유지 — 활 쓰는 몹은 콘텐츠로 나중에)",
      bq['hp'] == hp0 or mq.x != 3)     # 다가왔으면 위치가 바뀐다(때린 게 아님)

print()
if C.failed:
    print("FAIL — %d개 실패" % C.failed)
    raise SystemExit(1)
print("ALL PASS — verify_archer (사거리·사선·동료 통과·DEX 명중·단일 진실원천)")

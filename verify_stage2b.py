# -*- coding: utf-8 -*-
"""Stage 2b 헤들리스 검증 — 인식 매트릭스·LOS 발각굴림·대칭 기습·상태기계.
설계 검토(3렌즈) 합성이 못박은 필수 게이트:
  ① [300시드] 몹·함정 풀게임 항상 종료 = 동결-봉쇄 livelock 0 (SLEEPING 표류 회귀 가드)
  ② LOS 대칭 (_sight_blocked 양방향 동일 — 매트릭스 공정성 토대, 2.53% 비대칭 회귀 가드)
  ③ 양방향 기습 관측 (we-ambush=봇이 자는 몹 급습 / they-ambush=몹이 봇 매복)
+ 사분면 결정론 단언, 벽뚫기 금지(LOS 게이팅), 발각=굴림(자동 아님), 강등, skip_turns."""
from dungeon_gm import (Dungeon, spawn, dummy_brain, Monster,
                        MON_SIGHT, DETECT_DC_BASE, LOSE_GRACE)


class C:
    failed = 0


def check(name, cond):
    print(("  OK   " if cond else " FAIL  ") + name)
    if not cond:
        C.failed += 1


def mkbot(char, x, y, str_=3, dex=0, wdmg=4, stealth=0, aware=None):
    """검증용 봇 dict(spawn 안 거치고 직접 — 시나리오 좌표 고정). aware_of = 감쇠 dict."""
    return {'char': char, 'x': x, 'y': y, 'hp': 14, 'maxhp': 14,
            'str': str_, 'dex': dex, 'wdmg': wdmg, 'stealth': stealth,
            'job': '전사', 'sex': '남', 'persona': '', 'bag': 0,
            'alive': True, 'won': False, 'order': None, 'path': [],
            'aware_of': set(aware or set())}


def open_map(seed=1, w=20, h=12):
    """가장자리만 벽인 빈 방(LOS 차폐 없음) — 매트릭스 사분면 분리 테스트용."""
    d = Dungeon(seed=seed, w=w, h=h, n_monsters=0, n_traps=0)
    for y in range(h):
        for x in range(w):
            d.grid[y][x] = '.' if (1 <= x < w - 1 and 1 <= y < h - 1) else '#'
    return d


# ── 1) obs 스키마: 몹에 state·aware (매트릭스 신호) ─────────────
d = open_map()
b1 = mkbot('1', 5, 5)
m = Monster(6, 5, mid=0)                      # 인접 자는 몹
d.monsters = [m]
o = d.view(b1, [b1])
ms = o['sights']['monsters']
check("자는 인접 몹이 obs에 보임", len(ms) == 1)
check("몹 obs에 state·aware 필드", all('state' in x and 'aware' in x for x in ms))
check("자는 몹(미추적) aware=False", ms[0]['aware'] is False and ms[0]['state'] == 'SLEEPING')

# ── 2) LOS 대칭 (_sight_blocked 양방향 동일) ───────────────────
asym = total = 0
for s in (7, 11, 3, 5, 9):
    dd = Dungeon(seed=s)
    floors = [(x, y) for y in range(dd.h) for x in range(dd.w) if dd.grid[y][x] == '.']
    for ax, ay in floors:
        for bx, by in floors:
            if max(abs(ax - bx), abs(ay - by)) <= 6:
                total += 1
                if dd._sight_blocked(ax, ay, bx, by) != dd._sight_blocked(bx, by, ax, ay):
                    asym += 1
check("[5시드] LOS 대칭 — _sight_blocked(a,b)==_sight_blocked(b,a) (비대칭 0)", asym == 0)
print("        (검사 쌍 %d, 비대칭 %d)" % (total, asym))

# ── 3) 결정론 — 같은 시드 → 동일 게임 ─────────────────────────
def play_sig(seed, ticks=80):
    dd = Dungeon(seed=seed)
    bb = [spawn(dd, '1', [])]
    bb.append(spawn(dd, '2', bb))
    for _ in range(ticks):
        for b in bb:
            if not b['alive'] or b['won']:
                continue
            if b.get('order'):
                dd.step_order(b, bb)
            else:
                dd.act(b, dummy_brain(dd.view(b, bb), b['char']), bb)
        dd.monster_turn(bb)
        if all(b['won'] or not b['alive'] for b in bb):
            break
    return (tuple((b['x'], b['y'], b['hp'], b['won'], b['bag']) for b in bb),
            tuple((mo.x, mo.y, mo.hp, mo.alive, mo.state, mo.target) for mo in dd.monsters))
bad_det = sum(1 for s in range(0, 30) if play_sig(s) != play_sig(s))
check("[30시드] 같은 시드 → 동일 게임(결정론, 발각·유리·표류 모두 self.rng)", bad_det == 0)

# ── 4) 벽뚫기 금지 — 벽 너머 봇(맨해튼4)은 발각 못함(LOS 게이팅) ─
d = open_map(w=12, h=7)
for y in range(d.h):
    for x in range(d.w):
        d.grid[y][x] = '#'
for x in range(1, 11):
    d.grid[3][x] = '.'                        # 1폭 통로
d.grid[3][5] = '#'                            # 한가운데 벽 = LOS 차단
b = mkbot('1', 3, 3)
mm = Monster(7, 3, mid=0)                     # 맨해튼 4지만 벽 너머
d.monsters = [mm]
woke = False
for _ in range(60):
    d.monster_turn([b])
    if mm.state == 'HUNTING':
        woke = True
        break
check("벽 너머 봇(맨해튼4) → 몹 발각 불가(SLEEPING 유지, 벽뚫기 추격 없음)",
      not woke and mm.state != 'HUNTING')

# ── 5) 발각 = 굴림(자동 아님) + 자는 인접몹은 그 턴 공격 안 함(we-ambush 창) ─
d = open_map()
b = mkbot('1', 5, 5)
mm = Monster(6, 5, mid=0)                     # 자는 몹 바로 옆
d.monsters = [mm]
ev = d.monster_turn([b])                      # 첫 몹턴
check("자는 인접 몹은 그 턴 공격 안 함(발각굴림만 = 봇 we-ambush 창)",
      not any(e['type'] == 'monster_attack' for e in ev))
# 여러 시드 평균: 인접(prox2) 전사(DC13)는 굴림으로 깸 — 자동도 영원불면도 아님
woke_cnt = 0
for s in range(0, 40):
    dd = open_map(seed=s)
    bb = mkbot('1', 5, 5)
    mx = Monster(6, 5, mid=0)
    dd.monsters = [mx]
    dd.monster_turn([bb])
    if mx.state == 'HUNTING':
        woke_cnt += 1
check("발각은 확률(굴림) — 인접 자는 몹이 한 턴에 늘 깨지도/안 깨지도 않음(0<n<40)",
      0 < woke_cnt < 40)
print("        (인접 전사 1턴 발각 %d/40)" % woke_cnt)

# ── 6) 매트릭스 사분면 (결정론 단언) ──────────────────────────
# (we-ambush) 봇이 자는 몹 공격 = surprise + skip_turns(반격 1턴 스킵)
d = open_map()
b = mkbot('1', 5, 5, str_=0, wdmg=3, stealth=4)   # 도적
mm = Monster(6, 5, hp=30, mid=0)                   # 탱키(한 방에 안 죽게)
d.monsters = [mm]
res = d._attack(b, 'm0', [b])
check("(we-ambush) 자는 몹 공격 → surprise 플래그", res.get('surprise') is True)
check("(we-ambush) 기습 후 몹 HUNTING 각성 + skip_turns=1", mm.state == 'HUNTING' and mm.skip_turns == 1)
ev = d.monster_turn([b])
check("(we-ambush) 기습당한 몹 = 다음 몹턴 반격 스킵", not any(e['type'] == 'monster_attack' for e in ev) and mm.skip_turns == 0)
ev2 = d.monster_turn([b])
check("(we-ambush) 스킵 후 다음 턴 정상 반격(인접)", any(e['type'] == 'monster_attack' for e in ev2))

# (they-ambush) HUNTING 몹이 미인지 봇 인접공격 = surprise
d = open_map()
b = mkbot('1', 5, 5, aware=set())                  # 봇은 아무 몹도 모름
mm = Monster(6, 5, mid=0)
mm.state = 'HUNTING'; mm.target = '1'; mm.last_seen = (5, 5)
d.monsters = [mm]
ev = d.monster_turn([b])
atk = [e for e in ev if e['type'] == 'monster_attack']
check("(they-ambush) HUNTING 몹이 미인지 봇 인접공격 → surprise", bool(atk) and atk[0].get('surprise') is True)
check("(they-ambush) 매복 후 봇이 그 몹 인지(연속 매복 차단)", mm.id in b['aware_of'])

# (face-to-face) 봇이 인지한 HUNTING 몹의 공격 = surprise 없음
d = open_map()
b = mkbot('1', 5, 5, aware={0})                    # 봇이 이미 그 몹 인지
mm = Monster(6, 5, mid=0)
mm.state = 'HUNTING'; mm.target = '1'; mm.last_seen = (5, 5)
d.monsters = [mm]
ev = d.monster_turn([b])
atk = [e for e in ev if e['type'] == 'monster_attack']
check("(face-to-face) 봇이 인지한 몹 공격 → surprise 없음", bool(atk) and not atk[0].get('surprise'))

# (they-ambush 솔기) 진짜 매복 = concealed(투명/매복몹·Stage3). 봇은 concealed 몹을 영영 못 봄 → 자동 매복.
# (비은닉 몹은 봇이 시야로 늘 먼저 봐서 실전 매복 ~0이 정상 — '트인 곳에선 다 보인다'. 매복엔 새 상태가 필요.)
d = open_map()
b = mkbot('1', 5, 5)
mm = Monster(6, 5, mid=0)
mm.concealed = True; mm.state = 'HUNTING'; mm.target = '1'; mm.last_seen = (5, 5)
d.monsters = [mm]
d.view(b, [b])                                     # 봇이 둘러봐도 concealed라 aware_of에 안 들어감
check("concealed(투명) 몹은 봇 aware_of에 안 잡힌다", 0 not in b['aware_of'])
ev = d.monster_turn([b])
atk = [e for e in ev if e['type'] == 'monster_attack']
check("(they-ambush 솔기) concealed 몹의 일격 = 매복(surprise) — Stage3서 발화", bool(atk) and atk[0].get('surprise') is True)

# ── 7) 강등 HUNTING→WANDERING (LOS 상실) ──────────────────────
d = open_map(w=30, h=14)
b = mkbot('1', 2, 2)                                # 봇 멀리(LOS 밖)
mm = Monster(20, 10, mid=0)
mm.state = 'HUNTING'; mm.target = '1'; mm.last_seen = (20, 10); mm.lost = 0
d.monsters = [mm]
d.monster_turn([b])                                # last_seen 도달 + LOS 상실 → 즉시 강등
check("HUNTING 몹 last_seen 도달+LOS상실 → WANDERING 강등", mm.state == 'WANDERING' and mm.target is None)
# grace 경로: last_seen 다른 곳, 끝내 강등
mm2 = Monster(20, 10, mid=1)
mm2.state = 'HUNTING'; mm2.target = '1'; mm2.last_seen = (25, 10); mm2.lost = 0
d.monsters = [mm2]
for _ in range(LOSE_GRACE + 8):
    d.monster_turn([b])
check("HUNTING 몹 LOS 오래 상실 → 결국 WANDERING(grace 경로)", mm2.state == 'WANDERING')

# ── 8) [필수 게이트] 300시드 풀게임 종료 + 양방향 기습 관측 ────
done = we = they = 0
notice = 0
T = 300
for s in range(0, T):
    dd = Dungeon(seed=s)
    bb = [spawn(dd, '1', [])]
    bb.append(spawn(dd, '2', bb))
    for _ in range(500):
        for b in bb:
            if not b['alive'] or b['won']:
                continue
            if b.get('order'):
                dd.step_order(b, bb)
            else:
                r = dd.act(b, dummy_brain(dd.view(b, bb), b['char']), bb)
                if r.get('surprise'):
                    we += 1
        for e in dd.monster_turn(bb):
            if e.get('type') == 'monster_attack' and e.get('surprise'):
                they += 1
            if e.get('type') == 'monster_notice':
                notice += 1
        if all(b['won'] or not b['alive'] for b in bb):
            break
    if all(b['won'] or not b['alive'] for b in bb):
        done += 1
check("[300시드] 몹·함정 풀게임 항상 종료 = 동결-봉쇄 livelock 0", done == T)
check("[300시드] we-ambush(봇이 자는 몹 급습) 실제 발생", we > 0)
check("[300시드] monster_notice(발각) 실제 발생", notice > 0)
# they-ambush(비은닉): 2b 시점엔 ~0이 정상이었으나 Stage3부터 경보 함정(원거리 각성 몹의 코너 습격)이
# 정당하게 만든다 — 정보 출력만, 단언 아님. concealed 매복은 별도(from_hiding, verify_stage3).
print("        (종료 %d/%d · we-ambush %d · 발각 %d · 비은닉 they-ambush %d[Stage3부턴 경보로 >0 정상])"
      % (done, T, we, notice, they))

print("\n" + "=" * 44)
print("RESULT: " + ("ALL PASS" if C.failed == 0 else f"{C.failed} FAILED"))
import sys
sys.exit(1 if C.failed else 0)

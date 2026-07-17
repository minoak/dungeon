# -*- coding: utf-8 -*-
"""회복 물약(07-17) 헤들리스 검증 — 17번째 게이트.
PD 문법: 주워 들고 다니는 확정 완전 회복 — 샘(그 자리 d20 도박)과 대비되는 '보험'.
게이트:
  ① 배치: 엔진 기본 0(기존 verify 비트 동일) / n_potions=N 정확 배치 / 같은 시드 기존 배치 불변
  ② 줍기: 밟으면 소지(walk potion 플래그·자기 소비 완결) / 곁에서 interact(result=potion)
  ③ 마시기: 확정 완전 회복·병 소모·한 턴 / 빈 손=no_potion / 만피 복용도 소모(낭비는 세계가 안 말림)
  ④ 리모컨: 소지 중일 때만 drink 옵션 + 만피 사실 주석 / 빈 손이면 옵션 없음
  ⑤ 계약: obs.potions·bot_snapshot.potions / plan_step drink=열린 동사 / brains 메뉴·자유서술 통과
  ⑥ 더미 정책: 다침+소지=drink 우선(샘보다) / 보이는 물약=보물처럼 줍기 핑
  ⑦ [30시드] 물약 켠 풀게임 항상 종료 + 결정론
(기존 verify 16종은 별도 실행.)
"""
import os

os.environ["DUNGEON_BESTIARY_FILE"] = ""   # 도감 영속 차단(게이트 격리 원칙)

import brains
import dungeon_gm as G
from dungeon_gm import Dungeon, spawn, dummy_brain


class C:
    failed = 0


def check(name, cond):
    print(("  OK   " if cond else " FAIL  ") + name)
    if not cond:
        C.failed += 1


def mkbot(char, x, y, hp=14, job='전사'):
    return {'char': char, 'x': x, 'y': y, 'hp': hp, 'maxhp': 14,
            'str': 3, 'dex': 0, 'wdmg': 4, 'stealth': 0,
            'search_r': 1, 'job': job, 'sex': '남', 'persona': '', 'bag': 0,
            'potions': 0, 'alive': True, 'won': False, 'order': None, 'path': [],
            'aware_of': set()}


def sig(d):
    return tuple(sorted((f.type, f.x, f.y) for f in d.features.values()
                        if f.type != 'potion')) + \
           tuple(sorted((m.kind, m.x, m.y) for m in d.monsters)) + \
           tuple(sorted((t.kind, t.x, t.y) for t in d.traps))


# ───────────────────── ① 배치 ─────────────────────
print("── ① 배치")
d0 = Dungeon(seed=7)
check("① 엔진 기본 0 — 물약 미배치(기존 verify 판 비트 동일)",
      not any(f.type == 'potion' for f in d0.features.values()))
d2 = Dungeon(seed=7, n_potions=2)
pots = [f for f in d2.features.values() if f.type == 'potion']
check("① n_potions=2 → 정확히 2병, 바닥 위·비은닉",
      len(pots) == 2 and all(not f.concealed for f in pots)
      and all(d2.grid[f.y][f.x] == G.FLOOR for f in pots))
check("① 같은 시드 = 기존 배치(출구·보물·몹·함정·상자·샘) 완전 불변(additive 재현성)",
      sig(d0) == sig(d2))
rows = ['#######',
        '#1.!.>#',
        '#######']
da, sta = G.Dungeon.from_ascii(rows, seed=7)
check("① from_ascii '!' = 회복 물약 피처", any(f.type == 'potion' for f in da.features.values()))
check("① tile 글리프 '!'(비은닉 물약)",
      da.tile(3, 1) == G.POTION)

# ───────────────────── ② 줍기 ─────────────────────
print("── ② 줍기")
da, sta = G.Dungeon.from_ascii(rows, seed=7)
b1 = mkbot('1', *sta['1'])
bots = [b1]
da.view(b1, bots)                              # seen_keys 씨딩(sighted 정지 배제)
pid = next('f%d' % f.id for f in da.features.values() if f.type == 'potion')
da.act(b1, {'type': 'goto', 'target': pid}, bots)
r = da.step_order(b1, bots)
r = da.step_order(b1, bots)
check("② 밟으면 줍는다 — result=potion·소지 1·피처 소멸·order 자기 소비 완결",
      r['result'] == 'potion' and b1['potions'] == 1
      and not any(f.type == 'potion' for f in da.features.values())
      and b1['order'] is None)
db, stb = G.Dungeon.from_ascii(['#####', '#1!>#', '#####'], seed=7)
b1 = mkbot('1', *stb['1'])
db.view(b1, [b1])
pid = next('f%d' % f.id for f in db.features.values() if f.type == 'potion')
r = db.act(b1, {'type': 'interact', 'target': pid}, [b1])
check("② 곁에서 집기 — interact result=potion(병 수 병기)",
      r['result'] == 'potion' and r.get('potions') == 1 and b1['potions'] == 1)

# ───────────────────── ③ 마시기 ─────────────────────
print("── ③ 마시기")
b1['hp'] = 5
r = db.act(b1, {'type': 'drink'}, [b1])
check("③ 확정 완전 회복 — heal=9·HP 만피·병 소모",
      r['result'] == 'drink_heal' and r['heal'] == 9 and b1['hp'] == 14
      and b1['potions'] == 0 and r['potions'] == 0)
r = db.act(b1, {'type': 'drink'}, [b1])
check("③ 빈 손 = no_potion 정직 보고", r['result'] == 'no_potion')
b1['potions'] = 1
r = db.act(b1, {'type': 'drink'}, [b1])
check("③ 만피 복용 = heal 0·병은 소모(세계는 낭비를 안 말린다)",
      r['result'] == 'drink_heal' and r['heal'] == 0 and b1['potions'] == 0)

# ───────────────────── ④ 리모컨 ─────────────────────
print("── ④ 리모컨")
dc, stc = G.Dungeon.from_ascii(['#####', '#1.>#', '#####'], seed=7)
b1 = mkbot('1', *stc['1'])
obs = dc.view(b1, [b1])
check("④ 빈 손 = drink 옵션 없음",
      not any(o['type'] == 'drink' for o in obs['options']))
b1['potions'] = 2
b1['hp'] = 7
obs = dc.view(b1, [b1])
op = next((o for o in obs['options'] if o['type'] == 'drink'), None)
check("④ 소지+다침 = drink 옵션(병 수 병기·주석 없음)",
      op is not None and '2병' in op['label'] and '상처가 없다' not in op['label'])
b1['hp'] = 14
obs = dc.view(b1, [b1])
op = next((o for o in obs['options'] if o['type'] == 'drink'), None)
check("④ 만피 = 사실 주석 '지금은 상처가 없다'(큐레이션 아닌 사실)",
      op is not None and '상처가 없다' in op['label'])
check("④ obs.potions 노출(자기 몸의 사실)", obs.get('potions') == 2)

# ───────────────────── ⑤ 계약 ─────────────────────
print("── ⑤ 계약")
snap = G.bot_snapshot(b1)
check("⑤ bot_snapshot.potions(스트림 additive)", snap.get('potions') == 2)
b1['plan'] = [{'type': 'drink'}]
step = dc.plan_step(b1, [b1])
check("⑤ plan_step drink = 열린 동사(작정 유효)",
      step is not None and step['type'] == 'drink')
act = brains._pick({'choice': op['n']}, obs)
check("⑤ brains 메뉴: drink 선택 = 행동 해석", act is not None and act['type'] == 'drink')
check("⑤ brains 자유서술: drink 동사 등록(_TYPES)", 'drink' in brains._TYPES)

# ───────────────────── ⑥ 더미 정책 ─────────────────────
print("── ⑥ 더미 정책")
dd, std = G.Dungeon.from_ascii(['######', '#1.~>#', '######'], seed=7)
b1 = mkbot('1', *std['1'], hp=5)
b1['potions'] = 1
a = dummy_brain(dd.view(b1, [b1]), '1')
check("⑥ 다침+소지 = drink 우선(샘 도박보다 확정 회복)", a == {'type': 'drink'})
b1['potions'] = 0
a = dummy_brain(dd.view(b1, [b1]), '1')
check("⑥ 다침+빈 손 = 샘 폴백(기존 정책 유지)",
      a.get('type') in ('goto', 'interact'))
de, ste = G.Dungeon.from_ascii(['######', '#1.!>#', '######'], seed=7)
b1 = mkbot('1', *ste['1'])
a = dummy_brain(de.view(b1, [b1]), '1')
pid = next('f%d' % f.id for f in de.features.values() if f.type == 'potion')
check("⑥ 보이는 물약 = 보물처럼 줍기 핑", a == {'type': 'goto', 'target': pid})

# ───────────────────── ⑦ [30시드] 종결·결정론 ─────────────────────
print("── ⑦ [30시드] 종결·결정론")


def play(seed, ticks=600, sig_out=False):
    dd = Dungeon(seed=seed, n_potions=2)
    bb = [spawn(dd, '1', [])]
    bb.append(spawn(dd, '2', bb))
    done = False
    drank = got = 0
    for t in range(ticks):
        for b in bb:
            if not b['alive'] or b['won']:
                continue
            if b.get('order'):
                r = dd.step_order(b, bb)
            else:
                r = dd.act(b, dummy_brain(dd.view(b, bb), b['char']), bb)
            if r.get('result') == 'drink_heal':
                drank += 1
            if r.get('potion') or r.get('result') == 'potion':
                got += 1
        for e in dd.monster_turn(bb):
            pass
        if all(b['won'] or not b['alive'] for b in bb):
            done = True
            break
    if sig_out:
        return (tuple((b['x'], b['y'], b['hp'], b['won'], b['bag'],
                       b.get('potions', 0)) for b in bb),
                tuple((m.x, m.y, m.hp, m.alive) for m in dd.monsters))
    return done, got, drank


done_n = got_tot = drank_tot = 0
for s in range(30):
    ok, g, dr = play(s)
    done_n += ok
    got_tot += g
    drank_tot += dr
check("⑦ [30시드] 물약 2병 판 항상 종료", done_n == 30)
check("⑦ [30시드] 줍기 실발화(획득 %d회)" % got_tot, got_tot > 0)
check("⑦ [30시드] 복용 실발화(drink %d회 — 더미 다침 정책)" % drank_tot, drank_tot > 0)
bad = sum(1 for s in range(8) if play(s, sig_out=True) != play(s, sig_out=True))
check("⑦ [8시드] 결정론 — 같은 시드 = 같은 판", bad == 0)

print("=" * 44)
if C.failed:
    print("RESULT: %d FAIL" % C.failed)
    raise SystemExit(1)
print("RESULT: ALL PASS — 회복 물약(줍기·소지·확정 회복) 계약 건전")

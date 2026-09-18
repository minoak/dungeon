# -*- coding: utf-8 -*-
"""파티 장부(D84, 2026-09-18) 검증 — 70번째 게이트.

왜: 지금까지 '일행'은 론처가 출발 전에 정했고, 계단은 **이 층에 살아 있는 전원**이 모여야 열렸다. 그래서
던전이 내키지 않는 캐릭터의 "안 갈래"는 개인의 선택이 아니라 일행 전체를 세우는 거부권이 되거나, 계단 곁에
작정 없이 서 있기만 해도 동의로 세어져 끌려 내려갔다(_gather_busy). 파트너(09-18): "던전을 가려면 파티를
모험가 길드에서 결성할수 있게 해야해 … 파티는 함께 계단을 오르내릴수 있어". 누가 같이 가나는 세계 안에서
캐릭터가 정한다 — 이 게이트는 그 바닥(장부 + 계단이 세는 사람)만 본다. 맺고 푸는 동사는 다음 조각.

⚠️ 왜 게이트인가 — 이건 물리다(누가 끌려가고 누가 막히나). 0콜로 직접 찌른다.

게이트:
  ① 기본 없음 — 장부를 안 건 판(생성 층·손그림 장면)은 옛 동작과 같다(전원이 모여야, 모이면 전원이 함께)
  ② 장부 순수 함수 — 맺기·합류·두 파티 합치기·풀기·명단
  ③ 파티가 없는 캐릭터는 혼자 내려간다 — 곁에 작정 없이 서 있던 남을 데려가지 않는다
  ④ 계단은 내 파티원만 센다 — 파티 밖 사람이 멀어도 안 막히고, 파티원이 멀면 막힌다
  ⑤ 관측의 모임 사실(exit.gather)도 같은 자 — 파티 밖 사람은 빠진 동료로 나오지 않는다
  ⑥ 오르는 계단도 같은 규칙
  ⑦ 죽은 파티원은 세지 않는다
(기존 verify 69종은 별도 실행.)
"""
import os

os.environ["DUNGEON_BESTIARY_FILE"] = ""            # 도감 영속 차단(게이트 격리 원칙)

import dungeon_gm as G                               # noqa: E402


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
            'potions': 0, 'weapon': None, 'armor': None,
            'alive': True, 'won': False, 'order': None, 'path': [],
            'aware_of': set()}


ROWS = ['############',
        '#..<.......#',
        '#..........#',
        '#.....>....#',
        '#..........#',
        '############']
EXIT = (6, 3)


def scene(parties=None):
    """계단 곁에 1·2, 멀리 3 — 같은 장면에 장부만 갈아 끼운다."""
    d, _ = G.Dungeon.from_ascii(ROWS, seed=7)
    d.parties = parties
    b1, b2, b3 = mkbot('1', 6, 3), mkbot('2', 7, 3), mkbot('3', 1, 1)
    return d, [b1, b2, b3]


print("=== 파티 장부(D84) 검증 — 70번째 게이트 ===\n")

# ── ① 기본 없음 ────────────────────────────────────────────────────────────
print("① 기본 없음 — 옛 판 그대로")
check("① 생성 층의 장부 기본 None", G.Dungeon(seed=7, w=40, h=16).parties is None)
d, bots = scene()
check("① 손그림 장면의 장부 기본 None(__new__ 경유 명시 초기화)", d.parties is None)
r = d._interact(bots[0], 'exit', bots)
check("① 장부 없는 판 — 한 명이라도 멀면 wait_allies(빠진 동료 3)",
      r['result'] == 'wait_allies' and r['missing'] == ['3'])
bots[2]['x'], bots[2]['y'] = 5, 3
r = d._interact(bots[0], 'exit', bots)
check("① 장부 없는 판 — 다 모이면 전원이 함께 내려간다",
      r['result'] == 'exit' and r['party'] == ['1', '2', '3'] and all(b['won'] for b in bots))

# ── ② 장부 순수 함수 ───────────────────────────────────────────────────────
print("\n② 장부 순수 함수")
ps = G.new_parties()
check("② 새 장부의 모양", ps == {'of': {}, 'next': 1, 'asks': {}})
check("② 파티 없는 사람의 명단은 비어 있다", G.party_members(ps, '1') == [])
p = G.party_join(ps, ['2', '1'])
check("② 둘이 맺으면 같은 번호 · 명단은 번호순",
      p == 1 and ps['of'] == {'1': 1, '2': 1} and G.party_members(ps, '2') == ['1', '2'])
p = G.party_join(ps, ['1', '3'])
check("② 파티가 있는 사람과 맺으면 그 파티에 든다(합류)",
      p == 1 and G.party_members(ps, '3') == ['1', '2', '3'] and ps['next'] == 2)
ps2 = G.new_parties()
G.party_join(ps2, ['1', '2'])
G.party_join(ps2, ['3', '4'])
check("② 서로 다른 파티 둘", ps2['of'] == {'1': 1, '2': 1, '3': 2, '4': 2})
p = G.party_join(ps2, ['2', '3'])
check("② 두 파티의 사람이 맺으면 작은 번호로 합친다",
      p == 1 and G.party_members(ps2, '4') == ['1', '2', '3', '4'])
ps3 = G.new_parties()
ps3['asks'] = {'1': {'2': 5}, '2': {'1': 6, '3': 7}}
G.party_join(ps3, ['1', '2'])
check("② 맺어진 사람들 사이의 열린 청은 닫힌다(남을 향한 청은 그대로)",
      ps3['asks'] == {'1': {}, '2': {'3': 7}})
gone = G.party_disband(ps3, '2')
check("② 풀면 전원이 파티 없는 사람으로 · 풀린 사람들의 청도 지운다",
      gone == ['1', '2'] and ps3['of'] == {} and ps3['asks'] == {})
check("② 파티 없는 사람이 풀면 아무 일도 없다", G.party_disband(ps3, '9') == [])

# ── ③ 파티가 없는 캐릭터는 혼자 ─────────────────────────────────────────────
print("\n③ 파티가 없는 캐릭터는 혼자 내려간다")
d, bots = scene(G.new_parties())
r = d._interact(bots[0], 'exit', bots)
check("③ 혼자 내려간다 — 하강 보고의 party 는 자기 하나",
      r['result'] == 'exit' and r['party'] == ['1'])
check("③ 곁에 작정 없이 서 있던 2 는 안 끌려간다(옛 판은 동의로 세어 데려갔다)",
      [b['won'] for b in bots] == [True, False, False])

# ── ④ 계단은 내 파티원만 센다 ───────────────────────────────────────────────
print("\n④ 계단은 내 파티원만 센다")
ps = G.new_parties()
G.party_join(ps, ['1', '2'])
d, bots = scene(ps)
r = d._interact(bots[0], 'exit', bots)
check("④ 파티 밖의 3 이 멀어도 안 막힌다 — 1·2 만 함께",
      r['result'] == 'exit' and r['party'] == ['1', '2']
      and [b['won'] for b in bots] == [True, True, False])
ps = G.new_parties()
G.party_join(ps, ['1', '3'])
d, bots = scene(ps)
r = d._interact(bots[0], 'exit', bots)
check("④ 파티원 3 이 멀면 막힌다 — 빠진 동료는 3 뿐(곁의 2 는 남이다)",
      r['result'] == 'wait_allies' and r['missing'] == ['3'] and r['busy'] == []
      and not any(b['won'] for b in bots))
bots[2]['x'], bots[2]['y'] = 5, 3
bots[2]['order'], bots[2]['path'] = '@1,1', [(4, 3)]
r = d._interact(bots[0], 'exit', bots)
check("④ 곁에 와도 딴 작정이 살아 있으면 안 모인 것(의사 존중은 그대로)",
      r['result'] == 'wait_allies' and r['busy'] == ['3'])
bots[2]['order'], bots[2]['path'] = None, []
r = d._interact(bots[0], 'exit', bots)
check("④ 모이면 파티만 함께 — 곁의 2 는 남는다",
      r['result'] == 'exit' and r['party'] == ['1', '3']
      and [b['won'] for b in bots] == [True, False, True])

# ── ⑤ 관측의 모임 사실 ─────────────────────────────────────────────────────
print("\n⑤ 관측의 모임 사실도 같은 자")
ps = G.new_parties()
G.party_join(ps, ['1', '3'])
d, bots = scene(ps)
g1 = (d.view(bots[0], bots).get('sights', {}).get('exit') or {}).get('gather')
check("⑤ 파티원 1 의 관측 — 빠진 동료는 3 뿐",
      g1 is not None and [m['char'] for m in g1['missing']] == ['3'] and g1['busy'] == [])
g2 = (d.view(bots[1], bots).get('sights', {}).get('exit') or {})
check("⑤ 파티 없는 2 의 관측 — 출구는 보이고 모임 사실은 없다(기다릴 사람이 없다)",
      g2.get('type') == 'exit' and 'gather' not in g2)
d0, bots0 = scene()
g0 = (d0.view(bots0[0], bots0).get('sights', {}).get('exit') or {}).get('gather')
check("⑤ 장부 없는 판의 관측은 옛 그대로 — 빠진 동료 3",
      g0 is not None and [m['char'] for m in g0['missing']] == ['3'])

# ── ⑥ 오르는 계단도 같은 규칙 ───────────────────────────────────────────────
print("\n⑥ 오르는 계단도 같은 규칙")
ps = G.new_parties()
G.party_join(ps, ['1', '2'])
d, bots = scene(ps)
uid = next('f%d' % f.id for f in d.features.values() if f.type == 'stairs_up')
bots[0]['x'], bots[0]['y'] = 3, 2
r = d._interact(bots[0], uid, bots)
check("⑥ 파티원 2 가 멀면 wait_allies(위)", r['result'] == 'wait_allies' and r['dir'] == 'up' and r['missing'] == ['2'])
bots[1]['x'], bots[1]['y'] = 4, 2
r = d._interact(bots[0], uid, bots)
check("⑥ 모이면 파티만 함께 오른다 — 3 은 남는다",
      r['result'] == 'ascend' and r['party'] == ['1', '2']
      and [b.get('went') for b in bots] == ['up', 'up', None])
d, bots = scene(G.new_parties())
uid = next('f%d' % f.id for f in d.features.values() if f.type == 'stairs_up')
bots[2]['x'], bots[2]['y'] = 3, 2
r = d._interact(bots[2], uid, bots)
check("⑥ 파티 없는 3 은 혼자 오른다", r['result'] == 'ascend' and r['party'] == ['3'])

# ── ⑦ 죽은 파티원 ──────────────────────────────────────────────────────────
print("\n⑦ 죽은 파티원은 세지 않는다")
ps = G.new_parties()
G.party_join(ps, ['1', '3'])
d, bots = scene(ps)
bots[2]['alive'] = False
r = d._interact(bots[0], 'exit', bots)
check("⑦ 파티원이 죽었으면 산 사람끼리 내려간다",
      r['result'] == 'exit' and r['party'] == ['1'])

print("\n" + ("ALL PASS" if not C.failed else "FAILED: %d" % C.failed))
raise SystemExit(1 if C.failed else 0)

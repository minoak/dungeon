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
  ── 조각 3(2026-09-19 파트너 "조각 3은 (나) 가 맞고 파티를 맺을 때에는 모두 길드 구역에 있어야 해" · "탈퇴를 모두 하면 자연스럽게
     해체가 되는거니까 … 오히려 탈퇴가 더 맞을지도?") 파티 결성·탈퇴 — 실제 마을(layout 구역)에서 엔진을 직접 찌른다 ──
  ⑧ 장부 순수 함수 party_leave — 혼자 떠난다 · 둘이던 파티는 남은 사람도 풀린다(해체는 탈퇴의 결과) · 셋이면 둘은 남는다
  ⑨ 파티 결성 = 길드 구역에서 청하고 맞받기: 안 보이는 사람은 대상이 아니다 · 청(party_asked) → 받은 쪽의 자기 사건·관측(asks_in) ·
     다시 청하면 party_asked_already · 맞받으면 party_formed(장부·양쪽 사건) · 길드 구역 밖이면 party_need_guild(누가 밖인지)
  ⑩ 맺는 순간 파티에 들 사람이 모두 길드 구역에: 기존 파티원이 구역 밖이면 party_not_gathered(missing) → 모이면 맺어진다 ·
     열린 청은 한쪽이 구역을 떠나면 닫힌다 · 던전 층의 관측은 마을 사람들의 청을 지우지 않는다
  ⑪ 파티 탈퇴: 어디서나 혼자(⚠️임시 가정 PARTY_LEAVE_ANYWHERE) · 남은 사람의 자기 사건 · 파티가 없으면 party_none
  ⑫ 관측·프롬프트(09-19 파트너 "이제 동료에 대한 정보를 자동으로 줄 필요가 없을것 같은데 … 파티 결성이 되면 … 그 캐릭터에 대한 정보가
     추가되는게 맞지 않나"): 명단 = 내 파티원만(맺는 순간이 소개다 — 파티 밖 사람은 명단에 없다 · 다른 층의 파티원은 away) · 시트에
     '- 동료:' 줄 없음 · '## 파티 결성' 절(열린 청)·PARTY 동사 블록은 길드 구역에 섰을 때/파티가 있을 때만 · 계단 문장이 '네 파티원'
  ⑬ 장부가 없는 판에는 흔적이 없다(obs.partyform·mate·away·mates_only 없음 · 명단 머리 '## 파티 명단' · 파서 invalid_type)
(기존 verify 69종은 별도 실행.)
"""
import os

os.environ["DUNGEON_BESTIARY_FILE"] = ""            # 도감 영속 차단(게이트 격리 원칙)
os.environ.setdefault("DUNGEON_BRAIN_BACKEND", "dummy")

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

# ── ⑧ party_leave ────────────────────────────────────────────────────────────
print("\n⑧ 장부 순수 함수 party_leave")
ps = G.new_parties()
G.party_join(ps, ['1', '2'])
check("⑧ 둘이던 파티에서 하나가 떠나면 남은 사람도 풀린다(해체는 탈퇴의 결과)",
      G.party_leave(ps, '1') == (['1', '2'], ['2']) and ps['of'] == {})
G.party_join(ps, ['1', '2', '3'])
check("⑧ 셋이면 떠난 사람만 빠지고 둘은 남는다 · 파티가 없는 사람의 탈퇴는 빈 결과",
      G.party_leave(ps, '3') == (['1', '2', '3'], []) and G.party_members(ps, '1') == ['1', '2']
      and G.party_leave(ps, '3') == ([], []))

# ── 실제 마을 ──────────────────────────────────────────────────────────────────
import brains                                        # noqa: E402
brains._call_claude = lambda prompt, model="haiku": ""
import show_runner                                   # noqa: E402


def town(parties):
    d, _ = show_runner.build_town(apart=True)
    d.composed_actions = d.auto_approach = True
    d.parties = parties
    sheets = show_runner.load_party(os.path.join(os.path.dirname(os.path.abspath(__file__)), "party.json"))
    bs = []
    for c in sorted(sheets):
        bs.append(G.spawn(d, c, bs, sheet=sheets[c]))
    d.turn = 1
    return d, bs, {c: sheets[c]["name"] for c in sheets}


def zone_cells(d, zid, n):
    out = [(x, y) for y in range(d.h) for x in range(d.w)
           if d._zone_id(x, y) == zid and d.grid[y][x] == G.FLOOR and not d.feature_at(x, y)]
    mid = len(out) // 2
    return out[mid:mid + n]


def put(b, xy):
    b['x'], b['y'] = xy


def act(d, bots, b, a):
    dec, err = G.CA.parse(a, d.view(b, bots))
    return {'parse_error': err} if err else d.act(b, dec, bots)


def by_exit(d):
    ex_x, ex_y = d.exit
    return next((x, y) for x, y in ((ex_x, ex_y + 1), (ex_x, ex_y - 1), (ex_x - 1, ex_y), (ex_x + 1, ex_y))
                if 0 <= y < d.h and 0 <= x < d.w and d.grid[y][x] == G.FLOOR and not d.feature_at(x, y))


print("\n⑨ 파티 결성 = 길드 구역에서 청하고 맞받기")
d, bots, names = town(G.new_parties())
b1, b2, b3 = bots
g, t = zone_cells(d, 'guild_district', 3), zone_cells(d, 'tavern_district', 3)
put(b1, g[0]); put(b2, t[0]); put(b3, t[1])
check("⑨ 다른 구역의 사람은 대상이 아니다(D70 — 안 보인다)", act(d, bots, b1, {'type': 'party_form', 'target': 'b2'}) == {'parse_error': 'invalid_target'})
r = d._party_form(b2, 'b3', bots)
check("⑨ 길드 구역 밖에서는 맺을 수 없다(party_need_guild — 나)", r['result'] == 'party_need_guild' and 'who' not in r)
put(b2, g[1])
r = act(d, bots, b1, {'type': 'party_form', 'target': 'b2'})
o2 = d.view(b2, bots)
check("⑨ 청 → party_asked · 받은 쪽의 자기 사건(party_asked_by)과 관측 asks_in · 장부에 열린 청",
      r['result'] == 'party_asked' and r['to'] == '2' and o2['last']['type'] == 'party_asked_by' and o2['last']['from'] == '1'
      and o2['partyform'] == {'mine': [], 'here': True, 'asks_in': ['1'], 'asks_out': []} and d.parties['asks'] == {'1': {'2': 1}})
check("⑨ 다시 청하면 party_asked_already(장부 그대로)", act(d, bots, b1, {'type': 'party_form', 'target': 'b2'})['result'] == 'party_asked_already')
r = act(d, bots, b2, {'type': 'party_form', 'target': 'b1'})
check("⑨ 맞받으면 party_formed — 장부·계단이 세는 사람·청한 쪽의 자기 사건(party_joined)",
      r['result'] == 'party_formed' and r['members'] == ['1', '2'] and G.party_members(d.parties, '1') == ['1', '2']
      and [o['char'] for o in d._stair_mates(b1, bots)] == ['2'] and b1['last']['type'] == 'party_joined'
      and not any(d.parties['asks'].values()))
check("⑨ 이미 같은 파티면 party_already", act(d, bots, b1, {'type': 'party_form', 'target': 'b2'})['result'] == 'party_already')

print("\n⑩ 맺는 순간 모두 길드 구역에")
put(b3, g[2]); put(b2, t[0])
r3 = act(d, bots, b3, {'type': 'party_form', 'target': 'b1'})
r1 = act(d, bots, b1, {'type': 'party_form', 'target': 'b3'})
check("⑩ 기존 파티원(2)이 구역 밖이면 맞받아도 party_not_gathered(missing = [2]) — 장부 그대로",
      r3['result'] == 'party_asked' and r1['result'] == 'party_not_gathered' and r1['missing'] == ['2']
      and G.party_members(d.parties, '3') == [])
put(b2, g[1])
r1 = act(d, bots, b1, {'type': 'party_form', 'target': 'b3'})
check("⑩ 전원이 길드 구역에 모이면 맺어진다(셋)", r1['result'] == 'party_formed' and r1['members'] == ['1', '2', '3'])
d, bots, names = town(G.new_parties())
b1, b2, b3 = bots
put(b1, g[0]); put(b2, g[1]); put(b3, t[1])
act(d, bots, b1, {'type': 'party_form', 'target': 'b2'})
put(b1, t[0])
check("⑩ 열린 청은 한쪽이 구역을 떠나면 닫힌다(관측에서도 사라진다)",
      d.view(b2, bots)['partyform']['asks_in'] == [] and not d.parties['asks'])
put(b1, g[0])
act(d, bots, b1, {'type': 'party_form', 'target': 'b2'})
floor = G.Dungeon(seed=7)
floor.parties = d.parties
fb = G.spawn(floor, '1', [])                        # 내장 시트(HEROES)의 아무나 — 던전 층에서 관측을 한 번 만든다
floor.view(fb, [fb])
check("⑩ 던전 층의 관측은 마을 사람들의 청을 지우지 않는다", d.parties['asks'] == {'1': {'2': 1}})

print("\n⑪ 파티 탈퇴")
d, bots, names = town(G.new_parties())
b1, b2, b3 = bots
G.party_join(d.parties, ['1', '2', '3'])
put(b1, g[0]); put(b2, g[1]); put(b3, t[1])
r = act(d, bots, b3, {'type': 'party_leave'})
check("⑪ 길드 구역 밖에서도 혼자 떠난다(임시 가정) — 남은 둘은 파티 그대로 · 남은 사람의 자기 사건(party_member_left)",
      G.PARTY_LEAVE_ANYWHERE and r['result'] == 'party_left' and r['freed'] == [] and G.party_members(d.parties, '1') == ['1', '2']
      and b1['last']['type'] == 'party_member_left' and b1['last']['from'] == '3' and b1['last']['freed'] is False)
r = act(d, bots, b2, {'type': 'party_leave'})
check("⑪ 둘이던 파티에서 떠나면 남은 사람도 파티 없는 사람 — 자기 사건에 freed · 계단은 혼자",
      r['result'] == 'party_left' and r['freed'] == ['1'] and d.parties['of'] == {} and b1['last']['freed'] is True
      and d._stair_mates(b1, bots) == [])
check("⑪ 파티가 없으면 party_none", d._party_leave(b1, bots)['result'] == 'party_none')

print("\n⑫ 관측·프롬프트")
G.party_join(d.parties, ['1', '2'])
d.elsewhere = [{'char': '3', 'job': '음유시인', 'depth': 1}]
o1 = d.view(b1, [b1, b2])
w1 = brains._wire(o1, names=names, compose=True)
pt = {p['char']: p for p in o1['party']}
check("⑫ 명단 = 내 파티원만: 파티원 2 는 있고(mate) 파티 밖의 3 은 다른 층에 있어도 명단에 없다", sorted(pt) == ['2'] and pt['2'].get('mate') is True)
d.elsewhere = [{'char': '2', 'job': '도적', 'depth': 1}]
o1b = d.view(b1, [b1])
w1b = brains._wire(o1b, names=names, compose=True)
check("⑫ 다른 층에 가 있는 파티원은 away(층) — '여기 없다 — 지하 1층에 있다'",
      [(p['char'], p.get('away')) for p in o1b['party']] == [('2', 1)] and "여기 없다 — 지하 1층에 있다" in w1b)
d.elsewhere = []
check("⑫ 프롬프트: '## 파티 명단'에 카야 한 줄 · 파티 밖의 피른은 명단 줄이 없다(겪은 일의 궤적에는 남는다) · 시트에 '- 동료:' 줄 없음(관계 문장은 작가의 것이라 그대로)",
      "## 파티 명단" in w1 and "- 카야(봇2), 도적" in w1 and "- 피른(봇3)," not in w1
      and "- 동료:" not in brains._sheet(b1, bots) and "와의 관계:" in brains._sheet(b1, bots))
check("⑫ PARTY 동사 블록: 길드 구역에 서 있으면 party_form · 파티가 있으면 party_leave", "PARTY:" in w1 and "- party_form + target" in w1 and "- party_leave:" in w1)
put(b3, t[1])
d.elsewhere = []
G.party_leave(d.parties, '3')
w3 = brains._wire(d.view(b3, bots), names=names, compose=True)
check("⑫ 길드 구역 밖·파티 없음 = PARTY 블록도 '## 파티 결성' 절도 '## 파티 명단'도 없다(닿아야 규칙이 붙는다 · 아는 사람이 없다)",
      "PARTY:" not in w3 and "## 파티 결성" not in w3 and "## 파티 명단" not in w3)
put(b3, g[2]); put(b1, g[0])
d._party_form(b3, 'b1', bots)
w1c = brains._wire(d.view(b1, bots), names=names, compose=True)
check("⑫ 열린 청은 '## 파티 결성' 절에 — 청한 사람의 이름이 실린다", "## 파티 결성" in w1c and "피른(봇3)가 너에게 파티 결성을 청해 두었다" in w1c)
d.parties['asks'].clear()
put(b2, t[0])
put(b1, by_exit(d))
r = d._interact(b1, 'exit', bots)
check("⑫ 계단 문장이 '네 파티원'이라 말한다(wait_allies.mates_only · exit.gather.mates_only)",
      r['result'] == 'wait_allies' and r.get('mates_only') is True and "네 파티원 전원" in brains._last_prose(r, names)
      and "일행 전원" not in brains._last_prose(r, names)
      and (d.view(b1, bots)['sights']['exit'].get('gather') or {}).get('mates_only') is True
      and "네 파티원 전원이 곁" in brains._wire(d.view(b1, bots), names=names, compose=True))

print("\n⑬ 장부가 없는 판에는 흔적이 없다")
d0, bots0, names0 = town(None)
o0 = d0.view(bots0[0], bots0)
w0 = brains._wire(o0, names=names0, compose=True)
check("⑬ obs.partyform 없음 · 명단에 mate/away 없음 · '## 파티 명단' 그대로 · PARTY 블록 없음 · 파서는 invalid_type",
      'partyform' not in o0 and not any(('mate' in p or 'away' in p) for p in o0['party']) and "## 파티 명단" in w0
      and sorted(p['char'] for p in o0['party']) == ['2', '3'] and "- 동료: 카야(봇2), 피른(봇3)" in brains._sheet(bots0[0], bots0)
      and "PARTY:" not in w0 and "## 파티 결성" not in w0
      and G.CA.parse({'type': 'party_form', 'target': 'b2'}, o0) == (None, 'invalid_type')
      and G.CA.parse({'type': 'party_leave'}, o0) == (None, 'invalid_type'))
put(bots0[0], by_exit(d0))
r0 = d0._interact(bots0[0], 'exit', bots0)
check("⑬ 계단 문장은 옛 그대로('일행 전원' · mates_only 없음)", r0['result'] == 'wait_allies' and 'mates_only' not in r0
      and "일행 전원" in brains._last_prose(r0, names0))

print("\n" + ("ALL PASS" if not C.failed else "FAILED: %d" % C.failed))
raise SystemExit(1 if C.failed else 0)

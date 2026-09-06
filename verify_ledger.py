# -*- coding: utf-8 -*-
"""공간 장부·구역 어휘(D17-1·2) 헤들리스 검증 — 14번째 게이트.
D17: "공간의 사실은 엔진이, 공간의 해석은 에이전트에게" — 좌표는 엔진이 보관, 봇은 id 지칭만.
게이트:
  ① 등재: 시야에 든 것만(벽 뒤·concealed 미등재) · 정적/몹/동료/방문구역 · 기본(None)=무동작
  ② 걷다 지나친 것도 등재(자동보행 스텝 훅 — "지나오면서 봤기 때문")
  ③ 귀환 핑: 시야 밖 statics → obs.known(좌표 없음)·돌아가기 옵션·_valid_targets → goto → arrived
  ④ 낡은 장부: 소비된 대상 귀환 = 기억의 좌표로 가서 lost(+장부 교정) / 자리를 다시 보면 잊는다
  ⑤ 시야-온리: obs 항목에 좌표 무노출 · 시야 밖 이동 비추적(월핵 금지) · 보이는 것과 중복 금지
  ⑥ 구역 어휘: 방/통로 라벨 · obs.zone · ways[].zone
  ⑦ 도감 마스킹: 모르는 종의 last_seen = 낯선 짐승(D9 정합)
  ⑧ 함정 항목: 드러난 함정 등재(id 없음=핑·돌아가기 불가) · 발동(소진)+재시야 = 교정
  ⑨ exit 귀환: 본 적 있어야 시야 밖 핑 허용(장부 없으면 불허 = beacon 폐기 회귀 방지)
  ⑩ 작정(D16 접점): 장부 목표 goto 작정은 착수 통과(가서 lost 로 확인) / 장부 밖 소멸 = 대상 소멸
  ⑪ 러너 통합: run_meta.ledger · 스냅샷 화이트리스트 밖 · 층 전이 리셋(descend 후 장부 turn)
  ⑫ [30시드] ledger-on 풀게임 항상 종료 + [8시드] 결정론(장부 서명 포함)
(기존 verify 13종은 별도 실행.)
"""
import os

os.environ["DUNGEON_BESTIARY_FILE"] = ""   # 도감 영속 차단(게이트 격리 원칙)

import brains
import dungeon_gm as G
from dungeon_gm import Dungeon, spawn, dummy_brain, new_ledger


class C:
    failed = 0


def check(name, cond):
    print(("  OK   " if cond else " FAIL  ") + name)
    if not cond:
        C.failed += 1


def mkbot(char, x, y, dex=0, search_r=1, job='전사'):
    return {'char': char, 'x': x, 'y': y, 'hp': 14, 'maxhp': 14,
            'str': 3, 'dex': dex, 'wdmg': 4, 'stealth': 0,
            'search_r': search_r, 'job': job, 'sex': '남', 'persona': '', 'bag': 0,
            'alive': True, 'won': False, 'order': None, 'path': [],
            'aware_of': set(), 'ledger': new_ledger()}


def fid_of(d, ftype):
    return next('f%d' % f.id for f in d.features.values() if f.type == ftype)


def walk_out(d, b, bots, limit=40):
    r = None
    for _ in range(limit):
        if not b.get('order'):
            break
        r = d.step_order(b, bots)
    return r


# ───────────────────── ① 등재 — 시야에 든 것만 ─────────────────────
print("── ① 등재(시야-온리의 기억판)")
rows = ['############',
        '#1..=..#.~.#',
        '#..g...#...#',
        '#.........>#',
        '############']
d, starts = G.Dungeon.from_ascii(rows, seed=7,
    monsters={'g': {'kind': '고블린', 'state': 'WANDERING'}})
d.turn = 3
b = mkbot('1', *starts['1'])
bots = [b]
obs = d.view(b, bots)
chest = fid_of(d, 'chest')
led = b['ledger']
check("① 보이는 상자 등재(최초 목격 turn·구역)",
      led['statics'].get(chest, {}).get('turn') == 3
      and led['statics'][chest]['zone'] == '방 r0')
check("① 벽 뒤 샘·먼 계단 미등재(안 본 건 모른다)",
      fid_of(d, 'fountain') not in led['statics'] and 'exit' not in led['statics'])
check("① 보이는 몹 last_seen + 방문 구역 기록",
      led['moving'].get('m0', {}).get('kind') == '고블린' and 0 in led['zones'])
check("① 보이는 것은 known 에 중복 없음(sights 소관)",
      obs['known']['statics'] == [] and obs['known']['last_seen'] == [])
b0 = mkbot('9', *starts['1'])
b0['ledger'] = None                        # 기본(스폰 기본값과 동일) — 하위호환 솔기
obs0 = d.view(b0, [b0])
check("① ledger=None → 무동작 + obs 에 known·zone·ways.zone 미노출(구판 obs 와 자구 동일)",
      'known' not in obs0 and 'zone' not in obs0 and b0['ledger'] is None
      and all(set(w) == {'bearing', 'dist', 'visited'} for w in obs0['sights']['ways']))

# ───────────────────── ② 걷다 지나친 것도 등재 ─────────────────────
print("── ② 자동보행 스텝 등재")
rows2 = ['##############',
         '#1..........>#',
         '#....=.......#',
         '##############']
d2, st2 = G.Dungeon.from_ascii(rows2, seed=7)
d2.turn = 1
b2 = mkbot('1', *st2['1'])
chest2 = fid_of(d2, 'chest')
check("② 출발 시점엔 상자가 시야 밖(테스트 전제)", chest2 not in b2['ledger']['statics'])
d2.act(b2, {'type': 'explore', 'target': 'E'}, [b2])
walk_out(d2, b2, [b2])
check("② 걷다 지나치며 본 상자가 장부에 적힘(결정 틱 없이 — 지나오면서 봤다)",
      chest2 in b2['ledger']['statics'])

# ───────────────────── ③ 귀환 핑 ─────────────────────
print("── ③ 귀환 핑(돌아가기)")
d3, st3 = G.Dungeon.from_ascii(rows, seed=7,
    monsters={'g': {'kind': '고블린', 'state': 'WANDERING'}})
d3.turn = 3
b3 = mkbot('1', *st3['1'])
bots3 = [b3]
d3.view(b3, bots3)                          # 상자 등재
chest3 = fid_of(d3, 'chest')
b3['x'], b3['y'] = 10, 3                    # 시야 밖으로(구석)
d3.turn = 9
obs3 = d3.view(b3, bots3)
ent = next((e for e in obs3['known']['statics'] if e.get('id') == chest3), None)
ret = [o for o in obs3['options'] if o['type'] == 'goto' and o.get('target') == chest3]
check("③ 시야 밖 상자 = known.statics 노출(구역·turn·방위·직선 거리 — 좌표 없음, 09-06 거리 추가)",
      ent is not None and set(ent) <= {'id', 'type', 'name', 'zone', 'turn', 'bearing', 'dist'}
      and 'x' not in ent and isinstance(ent.get('dist'), int) and ent['dist'] > 0 and ent.get('bearing'))
check("③ 돌아가기 옵션(사실 라벨: 어디서·언제 봤나·얼마나 먼지)",
      len(ret) == 1 and ret[0]['label'].startswith('돌아가기')
      and '6턴 전' in ret[0]['label'] and ('%s %d칸' % (ent['bearing'], ent['dist'])) in ret[0]['label'])
check("③ _valid_targets 가 장부 id 허용(brains 계약)",
      chest3 in brains._valid_targets(obs3))
r = d3.act(b3, {'type': 'goto', 'target': chest3}, bots3)
check("③ 귀환 goto = pathed(explore 강등 아님)",
      r['type'] == 'goto' and r['result'] == 'pathed')
r = walk_out(d3, b3, bots3)
check("③ 상자 실재 → 도착(arrived)", r is not None and r['result'] == 'arrived')

# ───────────────────── ④ 낡은 장부 — lost 드라마 + 교정 ─────────────────────
print("── ④ 낡은 장부(소비된 대상)")
d4, st4 = G.Dungeon.from_ascii(rows, seed=7)
d4.turn = 3
b4 = mkbot('1', *st4['1'])
bots4 = [b4]
d4.view(b4, bots4)
chest4 = fid_of(d4, 'chest')
cx4 = (d4.features[int(chest4[1:])].x, d4.features[int(chest4[1:])].y)
b4['x'], b4['y'] = 10, 3
del d4.features[int(chest4[1:])]            # 그 사이 동료가 상자를 소비(봇은 모른다)
r = d4.act(b4, {'type': 'goto', 'target': chest4}, bots4)
check("④ 소비된 대상 귀환 = 기억의 좌표로 pathed(안 본 소멸을 누설하지 않는다)",
      r['result'] == 'pathed')
r = walk_out(d4, b4, bots4)
check("④ 갔더니 없다 = lost(드라마) + 장부 교정(재유혹 방지)",
      r is not None and r['result'] == 'lost'
      and chest4 not in b4['ledger']['statics'] and b4['order'] is None)
d5, st5 = G.Dungeon.from_ascii(rows, seed=7)
d5.turn = 3
b5 = mkbot('1', *st5['1'])
d5.view(b5, [b5])
chest5 = fid_of(d5, 'chest')
loc5 = (d5.features[int(chest5[1:])].x, d5.features[int(chest5[1:])].y)
b5['x'], b5['y'] = 10, 3
del d5.features[int(chest5[1:])]
b5['x'], b5['y'] = loc5[0] - 1, loc5[1]     # 빈 자리를 다시 본다
d5.view(b5, [b5])
check("④ 자리가 보이는데 물건이 없다 → 장부에서 잊는다(경험 교정)",
      chest5 not in b5['ledger']['statics'])

# ───────────────────── ⑤ 시야-온리 유지 ─────────────────────
print("── ⑤ 시야-온리(월핵 금지)")
d6, st6 = G.Dungeon.from_ascii(rows, seed=7,
    monsters={'g': {'kind': '고블린', 'state': 'WANDERING'}})
d6.turn = 3
b6 = mkbot('1', *st6['1'])
d6.view(b6, [b6])
old = dict(b6['ledger']['moving']['m0'])
m6 = d6.monsters[0]
m6.x, m6.y = 10, 3                          # 시야 밖에서 몹이 이동
d6.turn = 8
obs6 = d6.view(b6, [b6])
ent6 = next((e for e in obs6['known']['last_seen'] if e['id'] == 'm0'), None)
check("⑤ 시야 밖 이동 비추적 — last_seen 은 '그때 거기'(zone·turn 불변)",
      b6['ledger']['moving']['m0'] == old
      and ent6 is not None and ent6['turn'] == old['turn'])
check("⑤ obs 항목에 좌표(x/y) 무노출 — 좌표 운전은 엔진 몫",
      all('x' not in e and 'y' not in e
          for e in obs6['known']['statics'] + obs6['known']['last_seen']
          + obs6['known']['zones']))
rows7 = ['#######',
         '#1.s.>#',
         '#######']
d7, st7 = G.Dungeon.from_ascii(rows7, seed=7,
    monsters={'s': {'kind': '그림자거미', 'concealed': True}})
b7 = mkbot('1', *st7['1'])
d7.view(b7, [b7])
check("⑤ concealed(매복) 몹은 장부에도 없다(안 보인 건 기억 못 한다)",
      'm0' not in b7['ledger']['moving'])

# ───────────────────── ⑥ 구역 어휘 ─────────────────────
print("── ⑥ 구역 어휘(D17-2)")
dz = Dungeon(seed=3, w=44, h=18, n_monsters=0, n_traps=0, n_lurkers=0)
room_cell = next(c for c, t in dz.tiletype.items() if t == 'room')
corr_cell = next(c for c, t in dz.tiletype.items() if t == 'corridor')
check("⑥ 라벨: 방=안정 id, 통로", dz._zone_label(*room_cell).startswith('방 r')
      and dz._zone_label(*corr_cell) == '통로')
bz = mkbot('1', *room_cell)
obsz = dz.view(bz, [bz])
check("⑥ obs.zone = 선 자리의 주소(방 id)", obsz['zone']['kind'] == '방'
      and obsz['zone']['id'] == 'r%d' % dz._room_id_at(*room_cell))
check("⑥ ways[].zone = 어느 구역으로 트였나(문자열 라벨)",
      all(isinstance(w.get('zone'), str) for w in obsz['sights']['ways']))

# ───────────────────── ⑦ 도감 마스킹 ─────────────────────
print("── ⑦ 도감 마스킹(D9 정합)")
d8, st8 = G.Dungeon.from_ascii(rows, seed=7,
    monsters={'g': {'kind': '고블린', 'state': 'WANDERING'}})
d8.turn = 2
b8 = mkbot('1', *st8['1'])
b8['known'] = set()                         # 도감 게이팅 켬 — 아무 종도 모른다
d8.view(b8, [b8])
d8.monsters[0].x, d8.monsters[0].y = 10, 3  # 시야 밖으로
obs8 = d8.view(b8, [b8])
ent8 = next(e for e in obs8['known']['last_seen'] if e['id'] == 'm0')
check("⑦ 모르는 종의 마지막 목격 = 낯선 짐승(장부 원본은 원명 유지)",
      ent8['kind'] == G.UNKNOWN_BEAST
      and b8['ledger']['moving']['m0']['kind'] == '고블린')
b8['known'] = {'monster:고블린'}
obs8 = d8.view(b8, [b8])
check("⑦ 아는 종은 원명(획득 즉시 소급)",
      next(e for e in obs8['known']['last_seen'] if e['id'] == 'm0')['kind'] == '고블린')

# ───────────────────── ⑧ 함정 항목 ─────────────────────
print("── ⑧ 드러난 함정(정보 항목)")
rows9 = ['##########',
         '#1..^...>#',
         '##########']
d9, st9 = G.Dungeon.from_ascii(rows9, seed=7, traps=[{'kind': 'spike', 'hidden': False}])
d9.turn = 2
b9 = mkbot('1', *st9['1'])
d9.view(b9, [b9])
tkey = next((k for k in b9['ledger']['statics'] if k.startswith('trap@')), None)
check("⑧ 드러난 함정 등재(id 없음 = 정보만)", tkey is not None
      and 'id' not in b9['ledger']['statics'][tkey])
b9['x'], b9['y'] = 8, 1                     # 함정이 시야 밖인 구석(dist 4)
obs9 = d9.view(b9, [b9])
check("⑧ known 엔 실리되 돌아가기 옵션은 없다(핑 대상 아님)",
      any(e['type'] == 'trap' for e in obs9['known']['statics'])
      and not any(o['label'].startswith('돌아가기') and '함정' in o['label']
                  for o in obs9['options']))
d9.traps[0].sprung = True
d9.traps[0].hidden = False
b9['x'], b9['y'] = st9['1']                 # 자리로 돌아와 다시 본다
d9.view(b9, [b9])
check("⑧ 발동(소진)된 함정 + 재시야 = 교정(잊는다)",
      not any(k.startswith('trap@') for k in b9['ledger']['statics']))

# ───────────────────── ⑨ exit 귀환(beacon 회귀 방지) ─────────────────────
print("── ⑨ exit 귀환")
rows10 = ['############',
          '#>.....#..1#',
          '#......#...#',
          '#..........#',
          '############']
d10, st10 = G.Dungeon.from_ascii(rows10, seed=7)
d10.turn = 1
b10 = mkbot('1', *st10['1'])
obs10 = d10.view(b10, [b10])
check("⑨ 안 본 계단은 장부에도 핑에도 없다(beacon 폐기 유지)",
      'exit' not in b10['ledger']['statics']
      and 'exit' not in brains._valid_targets(obs10))
b10['x'], b10['y'] = 2, 2                   # 계단 곁으로 — 본다
d10.view(b10, [b10])
b10['x'], b10['y'] = st10['1']              # 다시 멀리
d10.turn = 5
obs10 = d10.view(b10, [b10])
check("⑨ 본 적 있는 계단 = known + 돌아가기 + 핑 허용(기억이지 beacon 아님)",
      any(e.get('id') == 'exit' for e in obs10['known']['statics'])
      and any(o.get('target') == 'exit' and o['label'].startswith('돌아가기')
              for o in obs10['options'])
      and 'exit' in brains._valid_targets(obs10))
r = d10.act(b10, {'type': 'goto', 'target': 'exit'}, [b10])
check("⑨ 귀환 goto exit = pathed", r['result'] == 'pathed')

# ───────────────────── ⑩ 작정 접점(D16) ─────────────────────
print("── ⑩ 작정 착수 재검증")
d11, st11 = G.Dungeon.from_ascii(rows, seed=7)
d11.turn = 2
b11 = mkbot('1', *st11['1'])
d11.view(b11, [b11])
chest11 = fid_of(d11, 'chest')
b11['x'], b11['y'] = 10, 3
del d11.features[int(chest11[1:])]          # 소비 — 봇은 모른다
b11['plan'] = [{'type': 'goto', 'target': chest11}]
step = d11.plan_step(b11, [b11])
check("⑩ 장부 목표 goto 작정 = 착수 통과(소멸을 미리 누설하지 않는다)",
      step == {'type': 'goto', 'target': chest11})
b11['plan'] = [{'type': 'goto', 'target': 'f99'}]
step = d11.plan_step(b11, [b11])
check("⑩ 장부에도 없는 소멸 대상 = 대상 소멸(기존 규칙 유지)",
      step is None and b11['last']['type'] == 'plan_broken')

# ───────────────────── ⑬ 리뷰 픽스 회귀(어드버서리얼 3렌즈) ─────────────────────
print("── ⑬ 리뷰 픽스 회귀")
# (a) 귀환 핑은 goto 전용 — interact/attack 에 장부 id 를 주면 소멸 여부 원격 누설
d13, st13 = G.Dungeon.from_ascii(rows, seed=7)
d13.turn = 3
b13 = mkbot('1', *st13['1'])
d13.view(b13, [b13])
chest13 = fid_of(d13, 'chest')
b13['x'], b13['y'] = 10, 3
obs13 = d13.view(b13, [b13])
check("⑬ 장부 id: goto 유효 / interact·attack 무효(소멸 원격 탐지 차단)",
      chest13 in brains._valid_targets(obs13, 'goto')
      and chest13 not in brains._valid_targets(obs13, 'interact')
      and chest13 not in brains._valid_targets(obs13, 'attack'))
check("⑬ 작정 저작도 동사별 — goto 장부 id 통과, interact 장부 id 기각",
      brains._then({'then': [{'type': 'goto', 'target': chest13}]}, obs13)
      == [{'type': 'goto', 'target': chest13}]
      and brains._then({'then': [{'type': 'interact', 'target': chest13}]}, obs13) == [])
# (b) trap@ 정보 항목은 엔진 귀환 게이트도 기각(방어선 이중화 — BYO/프리셋 두뇌 대비)
d14, st14 = G.Dungeon.from_ascii(rows9, seed=7, traps=[{'kind': 'spike', 'hidden': False}])
d14.turn = 2
b14 = mkbot('1', *st14['1'])
d14.view(b14, [b14])
tkey14 = next(k for k in b14['ledger']['statics'] if k.startswith('trap@'))
b14['x'], b14['y'] = 8, 1
r = d14.act(b14, {'type': 'goto', 'target': tkey14}, [b14])
check("⑬ act goto trap@ = 탐색 폴백(함정 위로 행군 금지)", r['type'] == 'explore')
b14['plan'] = [{'type': 'goto', 'target': tkey14}]
check("⑬ plan_step goto trap@ = 대상 소멸(id 없는 항목은 핑 불가)",
      d14.plan_step(b14, [b14]) is None and b14['last']['why'] == '대상 소멸')
# (c) 소비된 대상 + 기억 칸 인접·도달불가 = 거짓 arrived 가 아니라 lost + 교정
rows15 = ['######',
          '#21=>#',
          '######']
d15, st15 = G.Dungeon.from_ascii(rows15, seed=7)
d15.turn = 1
b15a = mkbot('1', *st15['1'])                     # 상자 곁(직교 인접)
b15b = mkbot('2', *st15['2'], job='도적')
bots15 = [b15a, b15b]
d15.view(b15a, bots15)                            # 상자 등재
chest15 = fid_of(d15, 'chest')
loc15 = (d15.features[int(chest15[1:])].x, d15.features[int(chest15[1:])].y)
del d15.features[int(chest15[1:])]                # 같은 틱 동료 소비
b15b['x'], b15b['y'] = loc15                      # 소비한 동료가 그 칸 점유(도달불가)
r = d15.act(b15a, {'type': 'goto', 'target': chest15, 'then': [{'type': 'search'}]}, bots15)
check("⑬ 소비+인접+도달불가 = lost(거짓 arrived 회귀) + 장부·작정 정리",
      r['result'] == 'lost' and chest15 not in b15a['ledger']['statics']
      and b15a['plan'] == [] and b15a['order'] is None)
# (d) 목격한 죽음 = 장부 교정 / 안 본 죽음 = 존치(역누설 금지)
d16x, st16 = G.Dungeon.from_ascii(rows, seed=7,
    monsters={'g': {'kind': '고블린', 'state': 'WANDERING'}})
d16x.turn = 2
b16a = mkbot('1', *st16['1'])
b16b = mkbot('2', 9, 3, job='도적')               # 벽 너머(무목격)
bots16 = [b16a, b16b]
d16x.view(b16a, bots16)
m16 = d16x.monsters[0]
d16x.view(b16b, bots16)
b16b['ledger']['moving']['m0'] = {'id': 'm0', 'kind': '고블린', 'x': m16.x, 'y': m16.y,
                                  'zone': '방 r0', 'turn': 1}   # 과거에 봤다고 치자
b16a['x'], b16a['y'] = m16.x, m16.y - 1           # 인접 붙어 격살
m16.hp = 1
b16a['aware_of'].add(0)
r = d16x._attack(b16a, 'm0', bots16)
check("⑬ 명중·처치 보장(테스트 전제)", r.get('killed') is True)
check("⑬ 목격한 죽음 = 내 장부에서 교정 / 안 본 동료 장부는 존치",
      'm0' not in b16a['ledger']['moving'] and 'm0' in b16b['ledger']['moving'])
# (e) 죽은·하강한 동료는 last_seen 투영에서 제외(party 가 이미 아는 사실 — 모순 신호 제거)
d17x, st17 = G.Dungeon.from_ascii(rows, seed=7)
d17x.turn = 2
b17a = mkbot('1', *st17['1'])
b17b = mkbot('2', st17['1'][0] + 2, st17['1'][1], job='도적')
bots17 = [b17a, b17b]
d17x.view(b17a, bots17)                           # 동료 목격 → moving 등재
b17b['alive'] = False
b17b['x'], b17b['y'] = 10, 3                      # 시야 밖(vis_ids 필터 무관 확인)
obs17 = d17x.view(b17a, bots17)
check("⑬ 죽은 동료 = last_seen 투영 제외(장부 원본은 남되 obs 모순 신호 없음)",
      'b2' in b17a['ledger']['moving']
      and not any(e['id'] == 'b2' for e in obs17['known']['last_seen']))
# (f) 시야 안 함정은 known 에 유지(sights 에 함정 어휘가 없다 — 증발 방지)
d18x, st18 = G.Dungeon.from_ascii(rows9, seed=7, traps=[{'kind': 'spike', 'hidden': False}])
d18x.turn = 2
b18 = mkbot('1', *st18['1'])
obs18 = d18x.view(b18, [b18])                     # 함정이 시야 안
check("⑬ 시야 안 드러난 함정 = known.statics 유지(구조화 obs 증발 방지)",
      any(e['type'] == 'trap' for e in obs18['known']['statics']))

# ───────────────────── ⑪ 러너 통합(층 전이 리셋) ─────────────────────
print("── ⑪ 러너 통합")
import io
import json
import contextlib
import time as _time

os.environ.update(DUNGEON_GM="0", DUNGEON_TURNS="400", DUNGEON_W="40", DUNGEON_H="16",
                  DUNGEON_SEED="7", DUNGEON_MONSTERS="2", DUNGEON_TRAPS="3",
                  DUNGEON_LURKERS="1", DUNGEON_DEPTHS="2", DUNGEON_STEP_DELAY="0",
                  DUNGEON_STREAM_OBS="1",
                  DUNGEON_PARTY_FILE="/nonexistent",   # 내장 2인 고정(회귀 그물)
                  DUNGEON_STATE_DIR=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                 "state_ledgerverify"))
brains._call_claude = lambda prompt, model="haiku": ""   # LLM 무력화 → dummy 폴백(결정론)
_time.sleep = lambda s: None
import show_runner
show_runner.STEP_DELAY = 0
with contextlib.redirect_stdout(io.StringIO()):
    show_runner.main()
recs = [json.loads(l) for l in
        open(os.path.join(show_runner.STATE, "stream.jsonl"), encoding="utf-8")]
meta = recs[0]
check("⑪ run_meta.ledger=true(실행모드 메타)", meta.get("ledger") is True)
check("⑪ 봇 스냅샷 화이트리스트 밖(스트림 계약 불변)",
      all('ledger' not in b for r in recs if r['kind'] in ('tick', 'level', 'end')
          for b in r.get('bots', r.get('party', []))))
obs_ticks = [(r['turn'], dec['obs']) for r in recs if r['kind'] == 'tick'
             for dec in r['decisions'].values() if 'obs' in dec]
check("⑪ 결정 obs 에 known·zone 동봉(STREAM_OBS 판)",
      obs_ticks and all('known' in o and 'zone' in o for _, o in obs_ticks))
check("⑪ 장부 실발화(등재물이 실제로 쌓임)",
      any(o['known']['statics'] or o['known']['last_seen'] or o['known']['zones']
          for _, o in obs_ticks))
desc = [r['turn'] for r in recs if r['kind'] == 'descend']
after = [(t, o) for t, o in obs_ticks if desc and t > desc[0]]
check("⑪ 층 전이 = 새 원장(descend 후 장부 목격 turn 전부 > 강하 턴)",
      bool(desc) and bool(after)
      and all(e['turn'] > desc[0]
              for _, o in after
              for e in o['known']['statics'] + o['known']['last_seen']
              + o['known']['zones']))

# ───────────────────── ⑫ [30시드] 종결 + [8시드] 결정론 ─────────────────────
print("── ⑫ [30시드] 종결·결정론(장부 서명 포함)")


def play(seed, ticks=600, sig=False):
    dd = Dungeon(seed=seed)
    bb = [spawn(dd, '1', [])]
    bb.append(spawn(dd, '2', bb))
    for b in bb:
        b['ledger'] = new_ledger()          # 러너와 같은 조건(장부 켬)
    done = False
    for t in range(1, ticks + 1):
        dd.turn = t
        for b in bb:
            if not b['alive'] or b['won']:
                continue
            if b.get('order'):
                dd.step_order(b, bb)
            else:
                dd.act(b, dummy_brain(dd.view(b, bb), b['char']), bb)
        dd.monster_turn(bb)
        if all(b['won'] or not b['alive'] for b in bb):
            done = True
            break
    if sig:
        return (tuple((b['x'], b['y'], b['hp'], b['won'], b['bag']) for b in bb),
                tuple((m.x, m.y, m.hp, m.alive, m.state) for m in dd.monsters),
                tuple(sorted((f.type, f.x, f.y) for f in dd.features.values())),
                tuple(tuple(sorted((k, e['turn']) for k, e in b['ledger']['statics'].items()))
                      for b in bb))
    return done


done_n = sum(play(s) for s in range(30))
check("⑫ [30시드] ledger-on 풀게임 항상 종료", done_n == 30)
bad = sum(1 for s in range(8) if play(s, sig=True) != play(s, sig=True))
check("⑫ [8시드] 결정론 — 같은 시드 = 같은 판(장부 서명 포함)", bad == 0)

print("=" * 44)
if C.failed:
    print("RESULT: %d FAIL" % C.failed)
    raise SystemExit(1)
print("RESULT: ALL PASS — 공간 장부·구역 어휘(D17-1·2) 계약 건전")

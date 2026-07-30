# -*- coding: utf-8 -*-
"""장비 뼈대(2026-07-30) 헤들리스 검증 — 31번째 게이트.
슬롯 2(무기·방어구)+단순 보정. 착용=캐릭터 판단(interact — 자동 줍기 아님).
스왑=헌 장비를 그 자리에(인벤토리 없음). 착용 정보=시트 상주(캐싱), 비교=입수 메뉴 라벨만.
게이트:
  ① 배치: 엔진 기본 0(기존 verify 비트 동일) / n_gear=3 순환 배치 / 같은 시드 기존 배치 불변
  ② 착용: 밟아도 안 줍는다(자동 줍기 아님 — 결정만이 착용) / interact=equip(빈 슬롯)
  ③ 스왑: 상위 무기 착용 → 헌것이 그 자리 피처로 / 방어구 슬롯 독립
  ④ 전투: 피해=wdmg+무기 보정(크리=든 것째 배가) / 몹 명중 목표=10+DEX+방어구 보정
  ⑤ 표면: 메뉴 라벨=비교 사실(수치·지금 착용·스왑 물리) / 시트 차림 줄 / 구판 봇=줄 없음
  ⑥ 전달층: equip 목격=ally_loot(챙기는 걸 본 사람은 안다) / obs.gear·snapshot / wire 무누출
  ⑦ 더미: 엄격 상위만 착용(헌 장비 되집기 왕복 금지)
  ⑧ [30시드] gear 3 판 항상 종료 + 결정론 + 착용 실발화
(기존 verify 30종은 별도 실행.)
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


def mkbot(char, x, y, hp=14, dex=0):
    return {'char': char, 'x': x, 'y': y, 'hp': hp, 'maxhp': 14,
            'str': 3, 'dex': dex, 'wdmg': 4, 'stealth': 0,
            'search_r': 1, 'job': '전사', 'sex': '남', 'persona': '', 'bag': 0,
            'potions': 0, 'weapon': None, 'armor': None,
            'alive': True, 'won': False, 'order': None, 'path': [],
            'aware_of': set()}


def sig(d):
    return tuple(sorted((f.type, f.x, f.y) for f in d.features.values()
                        if f.type not in ('weapon', 'armor'))) + \
           tuple(sorted((m.kind, m.x, m.y) for m in d.monsters)) + \
           tuple(sorted((t.kind, t.x, t.y) for t in d.traps))


# ───────────────────── ① 배치 ─────────────────────
print("── ① 배치")
d0 = Dungeon(seed=7)
check("① 엔진 기본 0 — 장비 미배치(기존 verify 판 비트 동일)",
      not any(f.type in ('weapon', 'armor') for f in d0.features.values()))
d3 = Dungeon(seed=7, n_gear=3)
gear = sorted((f.type, f.name) for f in d3.features.values()
              if f.type in ('weapon', 'armor'))
check("① n_gear=3 → 순환 배치(단검·가죽 갑옷·장검), 바닥 위·비은닉",
      gear == [('armor', '가죽 갑옷'), ('weapon', '단검'), ('weapon', '장검')]
      and all(d3.grid[f.y][f.x] == G.FLOOR and not f.concealed
              for f in d3.features.values() if f.type in ('weapon', 'armor')))
check("① 같은 시드 = 기존 배치(출구·보물·몹·함정·상자·샘) 완전 불변(additive 재현성)",
      sig(d0) == sig(d3))
rows = ['#######',
        '#1.).[#',
        '#..>..#',
        '#######']
da, sta = G.Dungeon.from_ascii(rows, seed=7)
check("① from_ascii ')'=무기(단검) / '['=방어구(가죽 갑옷)",
      any(f.type == 'weapon' and f.name == '단검' for f in da.features.values())
      and any(f.type == 'armor' and f.name == '가죽 갑옷' for f in da.features.values()))
check("① tile 글리프 ')'/'['", da.tile(3, 1) == G.WEAPON and da.tile(5, 1) == G.ARMOR)

# ───────────────────── ② 착용 ─────────────────────
print("── ② 착용")
da, sta = G.Dungeon.from_ascii(rows, seed=7)
b1 = mkbot('1', *sta['1'])
bots = [b1]
da.view(b1, bots)                              # seen_keys 씨딩(sighted 정지 배제)
wid = next('f%d' % f.id for f in da.features.values() if f.type == 'weapon')
da.act(b1, {'type': 'goto', 'target': wid}, bots)
r = da.step_order(b1, bots)
while b1.get('order'):
    r = da.step_order(b1, bots)
check("② 밟아도 안 줍는다 — 피처 잔존·슬롯 빈손(착용은 결정이지 발걸음이 아니다)",
      any(f.type == 'weapon' for f in da.features.values()) and b1['weapon'] is None)
r = da.act(b1, {'type': 'interact', 'target': wid}, bots)
check("② interact=equip — 슬롯 착용·보정 1·피처 소멸·dropped 없음",
      r['result'] == 'equip' and r['slot'] == 'weapon' and r['bonus'] == 1
      and b1['weapon'] == {'name': '단검', 'bonus': 1}
      and not any(f.type == 'weapon' for f in da.features.values())
      and 'dropped' not in r)
aid = next('f%d' % f.id for f in da.features.values() if f.type == 'armor')
da.act(b1, {'type': 'goto', 'target': aid}, bots)
while b1.get('order'):
    da.step_order(b1, bots)
r = da.act(b1, {'type': 'interact', 'target': aid}, bots)
check("② 방어구 슬롯도 같은 문법 — equip·막기 +1",
      r['result'] == 'equip' and r['slot'] == 'armor'
      and b1['armor'] == {'name': '가죽 갑옷', 'bonus': 1})

# ───────────────────── ③ 스왑 ─────────────────────
print("── ③ 스왑")
rows2 = ['#######',
         '#1.).>#',
         '#######']
rows3 = ['#######',                                # 스왑 전용 장면 — 바닥에 장검만(바닥 단검이
         '#1...>#',                                #   있으면 dropped 개수 검사가 그걸 같이 센다)
         '#######']
db, stb = G.Dungeon.from_ascii(rows3, seed=7)
lid = db._add_feature('weapon', '장검', 4, 1)      # 착용 단검(시트) vs 바닥 장검 — 상위 무기 장면
b2 = mkbot('1', *stb['1'])
b2['weapon'] = {'name': '단검', 'bonus': 1}
b2['armor'] = {'name': '가죽 갑옷', 'bonus': 1}
db.view(b2, [b2])
r = db.act(b2, {'type': 'goto', 'target': 'f%d' % lid}, [b2])
while b2.get('order'):
    db.step_order(b2, [b2])
r = db.act(b2, {'type': 'interact', 'target': 'f%d' % lid}, [b2])
dropped = [f for f in db.features.values() if f.type == 'weapon']
check("③ 스왑 — 장검 착용·dropped=단검·헌것이 그 자리(4,1) 피처로",
      r['result'] == 'equip' and r.get('dropped') == '단검'
      and b2['weapon'] == {'name': '장검', 'bonus': 2}
      and len(dropped) == 1 and dropped[0].name == '단검'
      and (dropped[0].x, dropped[0].y) == (4, 1))
check("③ 방어구 슬롯 독립 — 무기 스왑이 갑옷을 안 건드린다",
      b2['armor'] == {'name': '가죽 갑옷', 'bonus': 1})

# ───────────────────── ④ 전투 보정 ─────────────────────
print("── ④ 전투")
mrows = ['#####',
         '#1g>#',
         '#####']
dm, stm = G.Dungeon.from_ascii(mrows, seed=7,
                               monsters={'g': {'kind': '고블린', 'hp': 20, 'atk': 2,
                                               'dmg': 2, 'ac': 12, 'state': 'HUNTING'}})
bm = mkbot('1', *stm['1'])
mon = dm.monsters[0]
mon.target, mon.last_seen = '1', (bm['x'], bm['y'])
bm['aware_of'] = {mon.id}                      # 서로 완전 인지(기습·유리굴림 배제)
mon.state = 'HUNTING'
dm.d20 = lambda: 15                            # 굴림 고정 — 수식만 잰다
bm['weapon'] = {'name': '장검', 'bonus': 2}
r = dm._attack(bm, 'm%d' % mon.id, [bm])
check("④ 무기 보정 — 피해 = wdmg 4 + 장검 2 = 6",
      r['hit'] and r['dmg'] == 6)
dm.d20 = lambda: 20                            # 크리 — 든 것째 배가
mon.hp = 30
r = dm._attack(bm, 'm%d' % mon.id, [bm])
check("④ 크리 = (wdmg+보정)×2 = 12", r['dmg'] == 12)
bm['armor'] = {'name': '사슬 갑옷', 'bonus': 2}
dm.d20 = lambda: 9                             # 총합 9+atk2=11: 맨몸 목표 10엔 명중, 갑옷 12엔 빗나감
ev = dm._monster_attack(mon, bm, [bm])
check("④ 방어구 보정 — 목표값 10+DEX+2, 총합 11 = 빗나감",
      ev['ac'] == 12 and not ev['hit'])
bm['armor'] = None
ev = dm._monster_attack(mon, bm, [bm])
check("④ 맨몸이면 같은 총합이 명중(대조)", ev['ac'] == 10 and ev['hit'])

# ───────────────────── ⑤ 표면(메뉴·시트) ─────────────────────
print("── ⑤ 표면")
db2, stb2 = G.Dungeon.from_ascii(rows2, seed=7)
lid2 = db2._add_feature('weapon', '장검', 4, 1)
b5 = mkbot('1', 3, 1)                          # 단검 발밑 — 장검 인접
b5['weapon'] = {'name': '단검', 'bonus': 1}
obs = db2.view(b5, [b5])
labels = [o['label'] for o in obs['options'] if o.get('target') == 'f%d' % lid2
          and o['type'] == 'interact']
check("⑤ 메뉴 비교 라벨 — 수치·지금 착용·스왑 물리(입수 시점에만 비교)",
      len(labels) == 1 and '장검' in labels[0] and '피해 +2' in labels[0]
      and '지금: 단검' in labels[0] and '그 자리에 놓는다' in labels[0])
b5e = mkbot('1', 3, 1)                         # 빈손 대조
obs_e = db2.view(b5e, [b5e])
lab_e = [o['label'] for o in obs_e['options'] if o.get('target') == 'f%d' % lid2
         and o['type'] == 'interact']
check("⑤ 빈 슬롯 라벨 — '지금: 기본 무장'", len(lab_e) == 1 and '기본 무장' in lab_e[0])
sheet = brains._sheet({**mkbot('1', 1, 1), 'name': '두란',
                       'weapon': {'name': '장검', 'bonus': 2}, 'armor': None})
check("⑤ 시트 차림 줄 — 무기 이름·수치, 빈 슬롯=기본 무장(불변 프리픽스=캐싱 자리)",
      '차림' in sheet and '장검(피해 +2)' in sheet and '방어구 기본 무장' in sheet)
old = {k: v for k, v in mkbot('1', 1, 1).items() if k not in ('weapon', 'armor')}
check("⑤ 구판 봇(키 없음) = 차림 줄 없음(기존 프롬프트 게이트 무접촉)",
      '차림' not in brains._sheet(old))

# ───────────────────── ⑥ 계약(전달층·obs·스트림·wire) ─────────────────────
print("── ⑥ 계약")
db3, stb3 = G.Dungeon.from_ascii(rows2, seed=7)
db3.events = True                              # 전달층 스위치(D22 규율 — 장면에서 명시로 켠다)
b6 = mkbot('1', 3, 1)
w6 = mkbot('2', 2, 1)                          # 곁의 목격자
wid3 = next('f%d' % f.id for f in db3.features.values() if f.type == 'weapon')
db3.act(b6, {'type': 'interact', 'target': wid3}, [b6, w6])
check("⑥ equip 목격 = ally_loot(챙기는 걸 본 사람은 안다)",
      any(w.get('kind') == 'ally_loot' and w.get('what') == '단검'
          for w in w6.get('witnessed', [])))
obs6 = db3.view(b6, [b6, w6])
check("⑥ obs.gear = 자기 몸의 사실(더미·BYO 데이터)",
      obs6['gear']['weapon'] == {'name': '단검', 'bonus': 1}
      and obs6['gear']['armor'] is None)
snap = G.bot_snapshot(b6)
check("⑥ bot_snapshot.weapon/armor (additive)",
      snap['weapon'] == {'name': '단검', 'bonus': 1} and snap['armor'] is None)
wire = brains._wire(obs6)
check("⑥ wire 무누출 — 착용 정보는 시트 소유(상시 가변부 미노출 계약)",
      '그 밖의 정보' not in wire or 'gear' not in wire)

# ───────────────────── ⑦ 더미 정책 ─────────────────────
print("── ⑦ 더미")
db4, stb4 = G.Dungeon.from_ascii(rows2, seed=7)
b7 = mkbot('1', 2, 1)                          # 단검(3,1) 인접·빈손
act = dummy_brain(db4.view(b7, [b7]), '1')
wid4 = next('f%d' % f.id for f in db4.features.values() if f.type == 'weapon')
check("⑦ 빈손 곁 단검 = 착용", act == {'type': 'interact', 'target': wid4})
b7['weapon'] = {'name': '장검', 'bonus': 2}    # 이미 상위 무기 — 되집기 금지
act = dummy_brain(db4.view(b7, [b7]), '1')
check("⑦ 하위 장비는 무시(스왑 낙수 되집기 왕복 방지)",
      act != {'type': 'interact', 'target': wid4})

# ───────────────────── ⑧ [30시드] 풀게임 ─────────────────────
print("── ⑧ 풀게임")


def play(seed, ticks=600, sig_out=False):
    dd = Dungeon(seed=seed, n_gear=3)
    bb = [spawn(dd, '1', [])]
    bb.append(spawn(dd, '2', bb))
    done = False
    equips = 0
    for t in range(ticks):
        for b in bb:
            if not b['alive'] or b['won']:
                continue
            if b.get('order'):
                r = dd.step_order(b, bb)
            else:
                r = dd.act(b, dummy_brain(dd.view(b, bb), b['char']), bb)
            if r.get('result') == 'equip':
                equips += 1
        for e in dd.monster_turn(bb):
            pass
        if all(b['won'] or not b['alive'] for b in bb):
            done = True
            break
    if sig_out:
        return (tuple((b['x'], b['y'], b['hp'], b['won'], b['bag'],
                       b.get('weapon'), b.get('armor')) for b in bb),
                tuple((m.x, m.y, m.hp, m.alive) for m in dd.monsters))
    return done, equips


done_n = eq_tot = 0
for s in range(30):
    ok, eq = play(s)
    done_n += ok
    eq_tot += eq
check("⑧ [30시드] 장비 3점 판 항상 종료", done_n == 30)
check("⑧ [30시드] 착용 실발화(equip %d회 — 더미 정책)" % eq_tot, eq_tot > 0)
bad = sum(1 for s in range(8) if play(s, sig_out=True) != play(s, sig_out=True))
check("⑧ [8시드] 결정론 — 같은 시드 = 같은 판", bad == 0)

print("=" * 44)
if C.failed:
    print("RESULT: %d FAIL" % C.failed)
    raise SystemExit(1)
print("RESULT: ALL PASS — 장비 뼈대(슬롯 2·보정·스왑·비교 라벨·시트 캐싱) 계약 건전")

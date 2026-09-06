# -*- coding: utf-8 -*-
"""오브젝트 태그(D39, 2026-09-06 파트너 발제 "태그 시스템에 궤적을 쌓자" → 합의 "궤적의 짝: 태그=지금 참인 사실과 횟수")
검증 — 38번째 게이트. LLM 0콜.
봇이 오브젝트와 상호작용한 횟수·마지막 사실 한 마디를 기계가 세서 시야 줄과 리모컨 라벨에 접미로 붙인다 —
"아이템 상인 f2 — 말 걸어 봄 ×2 (물약 받음)". 몸 태그(D34)는 몸 상태로 남고, 이건 나↔오브젝트 사이의 사실(D36 뼈의 오브젝트판).
수명=봇 dict(층 재스폰이면 초기화 — shop_served 리듬). 엔진 판정 무접촉.
게이트:
  ① 스위치: 엔진 기본 0 / from_ascii 기본 0 / 꺼진 판 = 장부 안 쌓임·obs 에 tag 없음·라벨 구판 그대로
  ② NPC: 1회 → n=1·note '물약 받음' / 2회(npc_talk) → n=2·note 유지 / obs sights.features[].tag {verb,n,note}
  ③ 샘은 마시면 사라진다 — 태그 대상 아님(장부 없음·오브젝트 소멸): "쓰고도 남아 있는 오브젝트만"
  ④ 대상 밖 타입(계단 exit)엔 태그 없음
  ⑤ 라벨: 곁 '말 걸기'·원거리 '이동' 접미('상호작용' 접미 코드는 있으나 지금 대상이 없다)
  ⑥ 렌더(brains._wire): 시야 줄 접미 — 두 경로(스캔 트리·플랫)
  ⑦ 재스폰(새 봇 dict)엔 장부 없음(비어 있음)
  ⑧ 결정론: 같은 수순 두 번 = 같은 장부
(기존 verify 37종은 별도 실행.)
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


def mkbot(char, x, y, hp=14):
    return {'char': char, 'x': x, 'y': y, 'hp': hp, 'maxhp': hp,
            'str': 3, 'dex': 0, 'wdmg': 4, 'stealth': 0,
            'search_r': 1, 'job': '전사', 'sex': '남', 'persona': '', 'bag': 0,
            'alive': True, 'won': False, 'order': None, 'path': [],
            'aware_of': set(), 'plan': [], 'last': None}


ROWS = ["##########",
        "#1.......#",
        "#.~.....>#",
        "##########"]


def scene(on=True, scan=False):
    d, st = Dungeon.from_ascii(ROWS, seed=7, scan=scan)
    d.objtags = on
    d._add_feature('npc', '아이템 상인', 3, 1)
    d.npc_lines['아이템 상인'] = "물약 하나 가져가게."
    d.npc_gifts['아이템 상인'] = {'potions': 1}
    d.npc_lines_again['아이템 상인'] = "아까 왔잖아."
    npc = next(f for f in d.features.values() if f.type == 'npc')
    fnt = next(f for f in d.features.values() if f.type == 'fountain')
    b = mkbot('1', 2, 1)          # NPC(3,1) 곁 · 샘(2,2) 곁
    return d, b, [b], npc, fnt


def labels(d, b, bots):
    return [o['label'] for o in d.view(b, bots)['options']]


print("── ① 스위치")
check("① 엔진 기본 objtags=False · from_ascii 기본 False",
      Dungeon(seed=7).objtags is False and Dungeon.from_ascii(["####", "#1>#", "####"])[0].objtags is False)
d0, b0, bots0, npc0, fnt0 = scene(on=False)
d0.act(b0, {'type': 'interact', 'target': 'f%d' % npc0.id}, bots0)
d0.act(b0, {'type': 'interact', 'target': 'f%d' % npc0.id}, bots0)
o0 = d0.view(b0, bots0)
check("① 꺼진 판: 장부 안 쌓임 · obs 피처에 tag 없음 · 라벨 구판 그대로",
      not b0.get('obj_tags') and all('tag' not in f for f in o0['sights']['features'])
      and any(l == '말 걸기: 아이템 상인 f%d (곁)' % npc0.id for l in labels(d0, b0, bots0)))

print("── ② NPC")
d, b, bots, npc, fnt = scene()
r1 = d.act(b, {'type': 'interact', 'target': 'f%d' % npc.id}, bots)
t1 = dict(b['obj_tags'][npc.id])
r2 = d.act(b, {'type': 'interact', 'target': 'f%d' % npc.id}, bots)
t2 = dict(b['obj_tags'][npc.id])
check("② 1회(npc_gift) → n=1·note '물약 받음' / 2회(npc_talk) → n=2·note 유지",
      r1['result'] == 'npc_gift' and t1 == {'n': 1, 'note': '물약 받음'}
      and r2['result'] == 'npc_talk' and t2 == {'n': 2, 'note': '물약 받음'})
o = d.view(b, bots)
fo = next(f for f in o['sights']['features'] if f['id'] == 'f%d' % npc.id)
check("② obs sights.features[].tag = {verb:'말 걸어 봄', n:2, note:'물약 받음'}",
      fo.get('tag') == {'verb': '말 걸어 봄', 'n': 2, 'note': '물약 받음'})

print("── ③ 샘(소멸 오브젝트)")
d.d20 = lambda: 20
r3 = d.act(b, {'type': 'interact', 'target': 'f%d' % fnt.id}, bots)
check("③ 샘은 마시면 사라진다 — 장부에 안 오르고(태그 대상 아님) 피처도 소멸",
      r3['result'] == 'fountain_heal' and fnt.id not in b['obj_tags'] and fnt.id not in d.features)

print("── ④ 대상 밖")
bx = mkbot('9', 8, 1)          # 계단(8,2) 곁
d.act(bx, {'type': 'interact', 'target': 'exit'}, [bx])
check("④ 계단(exit) 상호작용엔 태그 없음", not bx.get('obj_tags'))

print("── ⑤ 라벨")
labs = labels(d, b, bots)
check("⑤ 곁 '말 걸기' 라벨 접미 — ' — 말 걸어 봄 ×2 (물약 받음)'",
      any(l == '말 걸기: 아이템 상인 f%d (곁) — 말 걸어 봄 ×2 (물약 받음)' % npc.id for l in labs))
b['x'], b['y'] = 7, 1          # 멀리 — 원거리 '이동' 라벨
labs2 = labels(d, b, bots)
check("⑤ 원거리 '이동' 라벨 접미", any(l.startswith('이동: 아이템 상인 f%d — ' % npc.id) and l.endswith(' — 말 걸어 봄 ×2 (물약 받음)') for l in labs2))

print("── ⑥ 렌더")
NAMES = {'1': '두란'}
o_flat = d.view(b, bots)
txt_flat = brains._wire(o_flat, NAMES)
ds, bs, botss, npcs, fnts = scene(scan=True)
ds.act(bs, {'type': 'interact', 'target': 'f%d' % npcs.id}, botss)
o_tree = ds.view(bs, botss)
txt_tree = brains._wire(o_tree, NAMES)
check("⑥ 시야 줄 접미 — 플랫 경로 '말 걸어 봄 ×2 (물약 받음)' · 스캔 트리 경로 '말 걸어 봄 ×1 (물약 받음)'",
      "아이템 상인 f%d" % npc.id in txt_flat and "말 걸어 봄 ×2 (물약 받음)" in txt_flat
      and "말 걸어 봄 ×1 (물약 받음)" in txt_tree)
check("⑥ 태그 없는 피처(샘) 줄은 구판과 동일(접미 없음)",
      any("샘" in ln for ln in txt_tree.splitlines())
      and not any(("샘" in ln and "×" in ln) for ln in txt_tree.splitlines()))

print("── ⑦ 재스폰")
check("⑦ 새 봇 dict 엔 장부가 비어 있다(층 재스폰=초기화)", G.spawn(d, '2', [], sheet=G.HEROES['1']).get('obj_tags') == {})

print("── ⑧ 결정론")
def _seq():
    dd, bb, bots_, n_, f_ = scene()
    dd.act(bb, {'type': 'interact', 'target': 'f%d' % n_.id}, bots_)
    dd.act(bb, {'type': 'interact', 'target': 'f%d' % n_.id}, bots_)
    return bb['obj_tags']
check("⑧ 같은 수순 두 번 = 같은 장부", _seq() == _seq())

print()
if C.failed:
    print("FAIL — %d개 실패" % C.failed)
    raise SystemExit(1)
print("ALL PASS — verify_objtags (D39 오브젝트 태그: 횟수·마지막 사실·시야/라벨 접미·소멸 오브젝트 제외·꺼진 판 불변·재스폰 초기화)")

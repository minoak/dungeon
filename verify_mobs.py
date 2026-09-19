# -*- coding: utf-8 -*-
"""D92 새 몬스터(스위치 DUNGEON_BESTIARY_PLUS · 엔진 Dungeon(bestiary_plus=)) — 76번째 게이트. 실 LLM 0콜, 라이브 데이터 무접촉.
(2026-09-20 파트너 "던전은 사실 거의 완성된 거라 던전에 추가 오브젝트나 몬스터 혹은 이벤트를 넣는 것만 하면 될 것 같아" ·
 메모 WONDERLAND_CHANGES_2026-09-11 §4-3 "요구하는 대응이 다른 종류 — 원거리형·무리형·상태형")
새 종 셋(정의 entities/monster): 독칼 고블린(상태형 — 명중=중독) · 새끼거미(무리형 — 셋이 한 묶음) · 고블린 중갑병(단단한 종 — AC·HP 높고 걸음 박자 2).
게이트:
  ① 끈 판 = 옛 판: 인자 생략 == bestiary_plus=False (층 스냅샷·난수 상태·더미 판 궤적) · 엔진·손그림 장면 기본 꺼짐 (고정 기준선은 verify_skill_off)
  ② 1층 불변: 켜도 1층은 끈 판과 스냅샷·난수·궤적이 같다(의뢰 goblin_cull·주점 소문의 실측)
  ③ 켠 판 2층+: 지형·피처·함정·매복자·보스는 그대로, 고블린의 절반(올림, 하나는 남김)이 같은 칸·같은 번호로 새 종 · 번호 연속·칸 안 겹침 · 세 종 전부 등장
  ④ 묶음: 새끼거미는 층당 한 묶음(3마리) · 첫 개체에서 PACK_REACH 안 · 첫 개체가 방 안이면 전부 같은 방 · 피처·함정·문 위에 안 놓임
  ⑤ 상태: 독칼 고블린 명중 = 중독(사건·직전 결과·목격) · 상태 스위치가 꺼진 판은 무태그 · 새끼거미·중갑병은 무태그
  ⑥ 걸음 박자: 중갑병은 쫓을 때 한 칸 걷고 한 틱 선다(고블린은 매 틱) · 붙으면 매 틱 친다 · 옛 피클의 몹(pace 없음)도 안 죽는다
  ⑦ 도감·문장: 모르는 종=낯선 짐승 → 등재 한 줄 → 심층 · 발급기 조우 5 · 직전 결과 문장·꼬리표·관전 요약이 새 종을 그대로 말한다(JSON 폴백·misc 0)
  ⑧ 더미 풀판: 시드×층×행동 모드(메뉴·조합) 예외 0 · 새 종과의 교전·처치·중독이 실제로 난다
  ⑨ 결정론: 같은 시드 = 같은 배치·같은 궤적   ⑩ 피클 왕복: 판 도중 얼렸다 녹여도 같은 궤적
  ⑪ 러너: 스위치 기본 0(지문·run_meta 열쇠 없음, 사전에 새 종 없음) · 켜면 열쇠·사전·2층 배치 · 생성 세 자리 배선 · 클라이언트 그림 매핑 · 게이트 등록
"""
import collections
import hashlib
import json
import os
import pickle
import re
import subprocess
import sys
import tempfile

os.environ.setdefault('DUNGEON_BRAIN_BACKEND', 'dummy')
HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(tempfile.mkdtemp(prefix='wl_mobs_'), 'state')
os.makedirs(STATE, exist_ok=True)
os.environ.update(DUNGEON_STATE_DIR=STATE, DUNGEON_BESTIARY_FILE='', DUNGEON_PARTY_FILE='/nonexistent')
os.environ.pop('DUNGEON_BESTIARY_PLUS', None)          # 러너 기본(0)을 본다 — 켠 러너는 자식 프로세스로만

import bestiary                                        # noqa: E402
import brains                                          # noqa: E402
import dungeon_gm as G                                 # noqa: E402
import show_runner                                     # noqa: E402  (act_summary·소스 검사 — 판은 자식 프로세스로만 돌린다)
from dungeon_gm import Dungeon                         # noqa: E402

POISON, SWARM, HEAVY = '독칼 고블린', '새끼거미', '고블린 중갑병'
PLUS = {POISON, SWARM, HEAVY}
GOBLIN, SPIDER = '고블린', '그림자거미'
RUNNER_KW = dict(n_traps=3, n_lurkers=1, scan=True, n_potions=1, loops=True, selfstop=True, graves=True, events=True,
                 dry_signal=True, hail=True, wait_verb=True, motion=True, ally_doing=True, ally_sight=True, n_gear=3,
                 status=True, rest_verb=True, relations=True, trail=True, objtags=True, floor=True, explore_dirs=True,
                 give_verb=True, bond_verb=True, plan_max=0)   # 러너가 층을 지을 때의 스위치(기본값)와 같은 모양


class C:
    failed = 0
    n = 0


def check(name, cond, note=''):
    C.n += 1
    print(('  OK   ' if cond else ' FAIL  ') + name + (('  ← %s' % (note,)) if (note and not cond) else ''))
    if not cond:
        C.failed += 1


def src(path):
    with open(os.path.join(HERE, path), encoding='utf-8') as f:
        return f.read()


def build(seed, depth, plus=None, w=56, h=20, compose=False, boss=False, **over):
    kw = dict(RUNNER_KW, **over)
    if plus is not None:
        kw['bestiary_plus'] = plus
    return Dungeon(seed=seed, depth=depth, w=w, h=h, n_monsters=2 + depth - 1, boss=boss,
                   auto_approach=compose, composed_actions=compose, **kw)


def fp(d):
    return hashlib.sha256(json.dumps({'level': d.level_snapshot(), 'rng': repr(d.rng.getstate())},
                                     ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


def party(d):
    bots = []
    for c in ('1', '2'):
        bots.append(G.spawn(d, c, bots, sheet=G.HEROES[c]))
    return bots


def tick(d, bots, turn, log, compose):
    """러너 틱의 뼈대(verify_skill_off.trace 와 같은 꼴) — 결정 없는 봇은 더미 두뇌, 작정 중이면 자동보행, 끝에 몹 턴."""
    d.turn = turn
    evs = []
    for b in bots:
        if not b['alive'] or b['won']:
            continue
        if b.get('order'):
            evs.append(d.step_order(b, bots))
        else:
            obs = d.view(b, bots)
            act = G.dummy_brain(obs, b['char'])
            evs.append(d.act(b, G.CA.fallback(act, obs) if compose else act, bots))
    evs.extend(d.monster_turn(bots))
    log.append({'turn': turn, 'events': evs, 'bots': [G.bot_snapshot(b) for b in bots],
                'monsters': [m.as_dict() for m in d.monsters]})
    return evs


def sim(d, bots, ticks, compose=False, start=1):
    log = []
    for t in range(start, start + ticks):
        tick(d, bots, t, log, compose)
    return log


def digest(log, d):
    return hashlib.sha256(json.dumps([log, repr(d.rng.getstate())], ensure_ascii=False, sort_keys=True, default=sorted)
                          .encode('utf-8')).hexdigest()


def mkbot(char, x, y, hp=14):
    return {'char': char, 'x': x, 'y': y, 'hp': hp, 'maxhp': 14, 'str': 3, 'dex': 0, 'wdmg': 4, 'stealth': 0,
            'search_r': 1, 'job': '전사', 'sex': '남', 'persona': '', 'bag': 0, 'alive': True, 'won': False,
            'order': None, 'path': [], 'aware_of': set(), 'plan': [], 'status': {}, 'bleed_steps': 0, 'slow_beat': 0,
            'witnessed': [], 'memories': []}


# ────────────────────────────────────────────────────────────────
print('── ① 끈 판 = 옛 판')
check('① 엔진 기본 꺼짐 · 손그림 장면 기본 꺼짐 · 러너 기본 0',
      Dungeon(seed=7).bestiary_plus is False and Dungeon.from_ascii(['####', '#1>#', '####'])[0].bestiary_plus is False
      and show_runner.BESTIARY_PLUS_ON is False)
same = all(fp(build(s, dp)) == fp(build(s, dp, plus=False)) for s in range(1, 9) for dp in range(1, 6))
check('① 인자 생략 == bestiary_plus=False — 8시드 × 1~5층 스냅샷·난수 상태', same)
off_kinds = {m.kind for s in range(1, 9) for dp in range(1, 6) for m in build(s, dp, boss=(dp == 5)).monsters}
check('① 끈 판의 몹 = 옛 세 종뿐(고블린·그림자거미·고블린 대장)', off_kinds == {GOBLIN, SPIDER, G.BOSS_KIND}, off_kinds)
tr = []
for plus in (None, False):
    d = build(11, 2, plus=plus)
    tr.append(digest(sim(d, party(d), 60), d))
check('① 더미 판 60틱 궤적·난수 — 인자 생략 == False', tr[0] == tr[1])

# ────────────────────────────────────────────────────────────────
print('── ② 1층 불변(켜도)')
check('② 1층 스냅샷·난수 상태 — 켠 판 == 끈 판 (12시드 × 두 크기)',
      all(fp(build(s, 1, plus=True, w=w, h=h)) == fp(build(s, 1, w=w, h=h)) for s in range(1, 13) for (w, h) in ((56, 20), (40, 16))))
tr = []
for plus in (True, False):
    d = build(5, 1, plus=plus)
    tr.append(digest(sim(d, party(d), 80), d))
check('② 1층 더미 판 80틱 궤적·난수 — 켠 판 == 끈 판', tr[0] == tr[1])

# ────────────────────────────────────────────────────────────────
print('── ③ 켠 판 2층+ 배치')
bad, seen_by_depth, floors, packs_seen = [], collections.defaultdict(collections.Counter), 0, 0
pack_bad = []
for (w, h) in ((56, 20), (40, 16)):
    for dp in (2, 3, 4, 5):
        for s in range(1, 26):
            off, on = build(s, dp, w=w, h=h, boss=(dp == 5)), build(s, dp, plus=True, w=w, h=h, boss=(dp == 5))
            floors += 1
            tag = (w, dp, s)
            so, sn = off.level_snapshot(), on.level_snapshot()
            if so['grid'] != sn['grid'] or so['traps'] != sn['traps']:
                bad.append((tag, '지형·함정이 달라졌다'))
            fo = [f for f in so['features']]
            fn = [f for f in sn['features']]
            if dp < 5 and fo != fn:                            # 보스층은 보스 곁 상자 자리가 묶음에 밀릴 수 있다 — 아래에서 따로 본다
                bad.append((tag, '피처가 달라졌다'))
            base = [m for m in off.monsters if not m.boss]
            gob = [m for m in base if m.kind == GOBLIN and not m.concealed]
            want = min((len(gob) + 1) // 2, len(gob) - 1)
            now = {m.id: m for m in on.monsters}
            swapped = 0
            for m in base:
                k = now.get(m.id)
                if k is None or (k.x, k.y) != (m.x, m.y) or k.concealed != m.concealed:
                    bad.append((tag, 'm%d 자리·은닉이 달라졌다' % m.id))
                elif k.kind != m.kind:
                    swapped += 1
                    if m.kind != GOBLIN or m.concealed or k.kind not in PLUS:
                        bad.append((tag, 'm%d: %s → %s (고블린만 새 종으로 바뀐다)' % (m.id, m.kind, k.kind)))
            if swapped != want:
                bad.append((tag, '바뀐 수 %d ≠ %d' % (swapped, want)))
            if not any(m.kind == GOBLIN for m in on.monsters):
                bad.append((tag, '고블린이 하나도 안 남았다'))
            extras = [m for m in on.monsters if m.id >= len(base) and not m.boss]
            if any(m.kind != SWARM for m in extras) or len(extras) not in (0, 2):
                bad.append((tag, '늘어난 개체는 묶음의 나머지(새끼거미 2)뿐이어야 한다: %s' % [m.kind for m in extras]))
            ids = sorted(m.id for m in on.monsters)
            cells = [(m.x, m.y) for m in on.monsters]
            if ids != list(range(len(ids))) or len(set(cells)) != len(cells) or any(on.grid[y][x] != G.FLOOR for x, y in cells):
                bad.append((tag, '번호 불연속·칸 겹침·바닥 아님'))
            if dp == 5:
                bs = [m for m in on.monsters if m.boss]
                if len(bs) != 1 or bs[0] is not on.boss or bs[0].kind != G.BOSS_KIND or not on.sealed \
                        or max(abs(bs[0].x - on.exit[0]), abs(bs[0].y - on.exit[1])) > 2:
                    bad.append((tag, '보스 배치가 흐트러졌다'))
            seen_by_depth[dp].update(m.kind for m in on.monsters)
            # ④ 묶음
            pk = sorted((m for m in on.monsters if m.kind == SWARM), key=lambda m: m.id)
            if pk:
                packs_seen += 1
                lead = pk[0]
                taken = {(f.x, f.y) for f in on.features.values()} | {(t.x, t.y) for t in on.traps}
                rid = on._room_id_at(lead.x, lead.y)
                if len(pk) != 3:
                    pack_bad.append((tag, '묶음 크기 %d' % len(pk)))
                if any(max(abs(m.x - lead.x), abs(m.y - lead.y)) > G.PACK_REACH for m in pk):
                    pack_bad.append((tag, '묶음이 흩어졌다'))
                if rid is not None and any(on._room_id_at(m.x, m.y) != rid for m in pk):
                    pack_bad.append((tag, '첫 개체가 방 안인데 묶음이 다른 곳에 있다'))
                if any((m.x, m.y) in taken for m in pk[1:]):
                    pack_bad.append((tag, '묶음이 피처·함정 위에 놓였다'))
check('③ %d개 층(두 크기 × 2~5층 × 25시드): 지형·피처·함정·매복자·보스 그대로 · 고블린의 절반(올림, 하나 남김)만 같은 칸·번호로 새 종 · 번호 연속·칸 안 겹침' % floors,
      not bad, bad[:3])
check('③ 2층부터 모든 층에 새 종이 있다 · 세 종이 2층에서 이미 전부 나온다',
      all(PLUS & set(seen_by_depth[dp]) for dp in (2, 3, 4, 5)) and PLUS <= set(seen_by_depth[2]), dict(seen_by_depth[2]))
print('── ④ 무리형 묶음')
check('④ 묶음이 실제로 놓인 층 %d개 — 전부 3마리 · PACK_REACH(%d) 안 · 방 안이면 같은 방 · 피처·함정 위 아님' % (packs_seen, G.PACK_REACH),
      packs_seen >= 20 and not pack_bad, pack_bad[:3])
try:                                                   # D88 던전 생성 프로필(concept, 42×34 · 큰 홀·폭 2~3 통로·기둥)이 있는 나무에서는 그 층에서도 같은 규칙인지 본다
    import dungeon_concept
except ImportError:
    dungeon_concept = None
if dungeon_concept is not None:
    cbad, cpacks, cerr = [], 0, []
    for dp in (1, 2, 3, 5):
        for s in range(1, 13):
            kw = dict(RUNNER_KW, seed=s, depth=dp, n_monsters=2 + dp - 1, boss=(dp == 5))
            off, on = dungeon_concept.ConceptDungeon(**kw), dungeon_concept.ConceptDungeon(bestiary_plus=True, **kw)
            if dp == 1:
                if fp(off) != fp(on):
                    cbad.append((dp, s, '1층이 달라졌다'))
                continue
            if off.level_snapshot()['grid'] != on.level_snapshot()['grid']:
                cbad.append((dp, s, '지형이 달라졌다'))
            if not (PLUS & {m.kind for m in on.monsters}) or not any(m.kind == GOBLIN for m in on.monsters):
                cbad.append((dp, s, '새 종이 없거나 고블린이 안 남았다'))
            cells = [(m.x, m.y) for m in on.monsters]
            if sorted(m.id for m in on.monsters) != list(range(len(cells))) or len(set(cells)) != len(cells) \
                    or any(on.grid[y][x] != G.FLOOR for x, y in cells):
                cbad.append((dp, s, '번호 불연속·칸 겹침·바닥 아님(기둥·문 위)'))
            pk = sorted((m for m in on.monsters if m.kind == SWARM), key=lambda m: m.id)
            if pk:
                cpacks += 1
                if len(pk) != 3 or any(max(abs(m.x - pk[0].x), abs(m.y - pk[0].y)) > G.PACK_REACH for m in pk):
                    cbad.append((dp, s, '묶음이 흐트러졌다'))
            if s <= 3:
                try:
                    sim(on, party(on), 120)
                except Exception as ex:                # noqa: BLE001
                    cerr.append((dp, s, repr(ex)[:160]))
    check('④ 생성 프로필 concept(D88) 층에서도 같은 규칙 — 1층 불변 · 2층+ 새 종·고블린 하나 남김 · 기둥·문 위에 안 놓임 · 묶음 %d개 · 더미 판 예외 0' % cpacks,
          not cbad and not cerr and cpacks >= 8, (cbad[:2], cerr[:2]))
tiny = Dungeon(seed=3, depth=2, w=44, h=18, n_monsters=1, n_traps=0, n_lurkers=0, bestiary_plus=True)
none_ = Dungeon(seed=3, depth=2, w=44, h=18, n_monsters=0, n_traps=0, n_lurkers=0, bestiary_plus=True)
check('④ 고블린이 하나뿐인 층·몹이 없는 층은 그대로(하나는 남긴다)', [m.kind for m in tiny.monsters] == [GOBLIN] and none_.monsters == [])

# ────────────────────────────────────────────────────────────────
print('── ⑤ 상태형: 독칼 고블린 명중 = 중독')
FIGHT = ['#######',
         '#1p.2>#',
         '#######']


def fight(kind, status=True):
    d, st = Dungeon.from_ascii(FIGHT, seed=7, monsters={'p': {'kind': kind, 'state': 'HUNTING', 'target': '1'}})
    d.status = status
    d.events = True
    bots = [mkbot('1', *st['1']), mkbot('2', *st['2'])]
    m = d.monsters[0]
    m.last_seen = (bots[0]['x'], bots[0]['y'])
    bots[0]['aware_of'].add(m.id)
    d.d20 = lambda: 20
    return d, bots, d.monster_turn(bots)


d, bots, evs = fight(POISON)
ev = next(e for e in evs if e.get('type') == 'monster_attack')
check('⑤ 명중 사건에 status 중독 · 피해 1(고블린보다 얕다) · 몸에 중독{by 독칼 고블린} · 직전 결과에 status',
      ev.get('hit') and ev.get('status') == '중독' and ev.get('dmg') == 1 and ev.get('monster') == POISON
      and (bots[0]['status'].get('중독') or {}).get('by') == POISON and bots[0]['last'].get('status') == '중독')
check('⑤ 곁의 동료가 본다 — ally_status{tag 중독, by 독칼 고블린}',
      any(w.get('kind') == 'ally_status' and w.get('tag') == '중독' and w.get('by') == POISON for w in bots[1].get('witnessed') or []))
d, bots, evs = fight(POISON, status=False)
check('⑤ 상태 스위치가 꺼진 판 = 무태그(피해만)', not bots[0]['status'] and 'status' not in next(e for e in evs if e.get('type') == 'monster_attack'))
ok = True
for kind in (SWARM, HEAVY):
    d, bots, evs = fight(kind)
    e = next(e for e in evs if e.get('type') == 'monster_attack')
    ok = ok and e.get('hit') and 'status' not in e and not bots[0]['status']
check('⑤ 새끼거미·고블린 중갑병은 상태를 안 건다', ok)

# ────────────────────────────────────────────────────────────────
print('── ⑥ 걸음 박자(단단한 종은 느리다)')
LANE = ['##########',
        '#1....m.>#',
        '##########']


def chase(kind, ticks, drop_pace=False):
    d, st = Dungeon.from_ascii(LANE, seed=7, monsters={'m': {'kind': kind, 'state': 'HUNTING', 'target': '1'}})
    b = mkbot('1', *st['1'])
    m = d.monsters[0]
    m.last_seen = (b['x'], b['y'])
    b['aware_of'].add(m.id)
    if drop_pace:
        del m.pace                                     # 옛 피클에서 되살아난 몹 — 이 속성이 없다
    d.d20 = lambda: 1                                  # 공격은 전부 빗나간다(자리·박자만 본다)
    xs, kinds = [], []
    for t in range(ticks):
        d.turn = t + 1
        evs = d.monster_turn([b])
        xs.append(m.x)
        kinds.append([e.get('type') for e in evs])
    return xs, kinds


xs_h, ev_h = chase(HEAVY, 10)
xs_g, ev_g = chase(GOBLIN, 6)
check('⑥ 고블린은 매 틱 한 칸(6→2, 4틱) · 중갑병은 한 칸 걷고 한 틱 선다(같은 길에 7틱)', xs_g[:4] == [5, 4, 3, 2] and xs_h[:7] == [5, 5, 4, 4, 3, 3, 2],
      (xs_g, xs_h))
check('⑥ 서 있는 틱엔 사건이 없다 · 붙은 뒤엔 선 틱 하나 다음부터 매 틱 친다',
      ev_h[1] == [] and ev_h[3] == [] and ev_h[7] == [] and ev_h[8] == ['monster_attack'] and ev_h[9] == ['monster_attack'], ev_h)
xs_old, _ = chase(HEAVY, 4, drop_pace=True)
check('⑥ pace 속성이 없는 몹(옛 스냅샷)도 죽지 않는다 — 매 틱 걷는다', xs_old == [5, 4, 3, 2], xs_old)

# ────────────────────────────────────────────────────────────────
print('── ⑦ 도감·문장')
lore = G.ENT.lore()
d, st = Dungeon.from_ascii(['#######', '#1.p.>#', '#######'], seed=7, monsters={'p': {'kind': POISON, 'state': 'SLEEPING'}})
d.lore = lore
b = mkbot('1', *st['1'])
b['known'] = set()
o0 = d.view(b, [b])['sights']['monsters'][0]
b['known'] = {'monster:' + POISON}
o1 = d.view(b, [b])['sights']['monsters'][0]
b['book'] = {'monster:' + POISON: {'n': 2}}
o2 = d.view(b, [b])['sights']['monsters'][0]
b['book'] = {'monster:' + POISON: {'n': 5, 'deep': {'turn': 1, 'depth': 2, 'n': 5}}}
o3 = d.view(b, [b])['sights']['monsters'][0]
check('⑦ 모르는 종 = 낯선 짐승 → 옛 2층(원장 없음)은 본문 → 등재 한 줄 + 진행도(2/5) → 심층 본문',
      o0['kind'] == G.UNKNOWN_BEAST and 'lore' not in o0 and o1['kind'] == POISON and o1['lore'] == lore['monster:' + POISON]['lore']
      and o2['lore'] == lore['monster:' + POISON]['brief'] and o2['deep_progress'] == {'event': 'encounter', 'n': 2, 'need': 5}
      and o3['lore'] == lore['monster:' + POISON]['lore'] and 'deep_progress' not in o3)
iss = bestiary.Issuer({'1': '두란'})
iss.consume('level', {'depth': 2, 'monsters': [{'id': i, 'kind': SWARM} for i in range(5)]})
got = []
for i in range(5):
    got.append(iss.consume('tick', {'turn': i + 1, 'bots': [{'char': '1', 'aware_of': list(range(i + 1))}], 'monsters': [], 'events': []}))
check('⑦ 발급기: 첫 조우 = 등재(brief) · 다섯째 조우 = 심층(deep)+인식 초대 — 새 종도 정의의 해금 조건을 탄다',
      got[0] == [('두란', 'monster:' + SWARM, 'brief')] and ('두란', 'monster:' + SWARM, 'deep') in got[4]
      and 'monster:' + SWARM in iss.known('두란') and all(('monster:' + k) in iss.rules for k in PLUS))
hurt = {'type': 'hurt', 'by': POISON, 'by_id': 'm2', 'dmg': 1, 'hp': 13, 'status': '중독'}
kill = {'char': '1', 'type': 'attack', 'result': 'attack', 'target': HEAVY, 'target_id': 'm1', 'roll': 15, 'mod': 3, 'total': 18, 'ac': 14,
        'hit': True, 'crit': False, 'dmg': 4, 'monster_hp': 0, 'killed': True}
matk = {'type': 'monster_attack', 'id': 'm3', 'monster': SWARM, 'target': '1', 'roll': 12, 'mod': 1, 'total': 13, 'ac': 10, 'hit': True, 'dmg': 1, 'hp': 12}
p_h, p_k = brains._last_prose(hurt), brains._last_prose(kill)
tags = G.event_tags(hurt) + G.event_tags(kill)
check('⑦ 직전 결과 문장이 새 종을 그대로 말한다(JSON 폴백 없음) · 꼬리표 misc 0 · 관전 요약에 종 이름',
      POISON in p_h and '중독' in p_h and HEAVY in p_k and '{' not in p_h + p_k
      and all(k != 'misc' for k, _, _ in tags) and ('status', '중독', '걸림') in tags
      and SWARM in (show_runner.mon_summary(matk) or '') and '[중독]' in show_runner.mon_summary(dict(matk, monster=POISON, status='중독'))
      and HEAVY in (show_runner.act_summary(kill) or ''))

# ────────────────────────────────────────────────────────────────
print('── ⑧ 더미 풀판(예외 0)')
tally, errs, runs = collections.Counter(), [], 0
for compose in (False, True):
    for dp in (2, 3, 5):
        for s in range(1, 9):
            runs += 1
            try:
                d = build(s, dp, plus=True, compose=compose, boss=(dp == 5))
                for evs in (r['events'] for r in sim(d, party(d), 150, compose=compose)):
                    for e in evs:
                        if e.get('type') == 'monster_attack' and e.get('monster') in PLUS:
                            tally['attack:' + e['monster']] += 1
                            if e.get('status'):
                                tally['status:' + e['status']] += 1
                        if e.get('killed') and e.get('target') in PLUS:
                            tally['kill:' + e['target']] += 1
                        if e.get('type') == 'monster_move' and e.get('monster') == HEAVY:
                            tally['move:' + HEAVY] += 1
            except Exception as ex:                    # noqa: BLE001 — 게이트는 어떤 예외든 센다
                errs.append((compose, dp, s, repr(ex)[:160]))
check('⑧ %d판(메뉴·조합 × 2·3·5층 × 8시드 × 150틱) 예외 0' % runs, not errs, errs[:2])
check('⑧ 새 종과 실제로 부딪친다 — 세 종 모두의 공격 · 세 종 모두의 처치 · 중독 걸림 · 중갑병의 걸음',
      all(tally['attack:' + k] > 0 and tally['kill:' + k] > 0 for k in PLUS) and tally['status:중독'] > 0 and tally['move:' + HEAVY] > 0,
      dict(tally))

# ────────────────────────────────────────────────────────────────
print('── ⑨ 결정론 · ⑩ 피클 왕복')
sig = []
for _ in range(2):
    d = build(9, 3, plus=True, compose=True)
    sig.append((fp(d), digest(sim(d, party(d), 100, compose=True), d)))
check('⑨ 같은 시드 = 같은 배치·같은 100틱 궤적·같은 난수 상태', sig[0] == sig[1])
check('⑨ 다른 시드 = 다른 배치', fp(build(9, 3, plus=True)) != fp(build(10, 3, plus=True)))
d = build(4, 3, plus=True, compose=True)
bots = party(d)
sim(d, bots, 40, compose=True)
d2, bots2 = pickle.loads(pickle.dumps((d, bots)))   # 방금 이 프로세스가 만든 객체의 왕복(D79 이어가기와 같은 길) — 밖에서 온 피클을 읽지 않는다
a = digest(sim(d, bots, 60, compose=True, start=41), d)
b_ = digest(sim(d2, bots2, 60, compose=True, start=41), d2)
check('⑩ 40틱에서 얼렸다 녹인 판이 이어서 60틱을 같은 궤적으로 간다 · 되살아난 층도 켠 판', a == b_ and d2.bestiary_plus is True
      and {m.kind for m in d2.monsters} == {m.kind for m in d.monsters})

# ────────────────────────────────────────────────────────────────
print('── ⑪ 러너')


def probe(env, run=False):
    e = {k: v for k, v in os.environ.items() if not k.startswith('DUNGEON_')}
    e.update(PYTHONUTF8='1', DUNGEON_BRAIN_BACKEND='dummy', DUNGEON_ACTION_MODE='menu', DUNGEON_SKILLS='0', DUNGEON_TRPG_COMBAT='0',
             DUNGEON_RANDOM_SKILL='0', DUNGEON_GM='0', DUNGEON_STEP_DELAY='0', DUNGEON_W='40', DUNGEON_H='16', DUNGEON_SEED='7',
             DUNGEON_BESTIARY_FILE='', DUNGEON_PARTY_FILE='/nonexistent', **env)
    code = ("import json, show_runner as s; s.time.sleep = lambda x: None; "
            "print(json.dumps({'on': s.BESTIARY_PLUS_ON, 'fp': s._world_fingerprint().get('bestiary_plus')}))"
            + ("\ns.main()" if run else ""))
    p = subprocess.run([sys.executable, '-c', code], cwd=HERE, env=e, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600)
    head = json.loads(p.stdout.splitlines()[0]) if p.stdout.strip() else {}
    return p.returncode, head, p.stderr[-400:]


def rows_of(state):
    with open(os.path.join(state, 'stream.jsonl'), encoding='utf-8') as f:
        return [json.loads(ln) for ln in f if ln.strip()]


out = {}
for name, extra in (('off', {}), ('on', {'DUNGEON_BESTIARY_PLUS': '1'})):
    sd = os.path.join(tempfile.mkdtemp(prefix='wl_mobs_%s_' % name), 'state')
    os.makedirs(sd, exist_ok=True)
    rc, head, err = probe(dict(DUNGEON_STATE_DIR=sd, DUNGEON_START='boss', DUNGEON_DEPTHS='2', DUNGEON_TURNS='80', **extra), run=True)
    out[name] = (rc, head, err, rows_of(sd) if rc == 0 else [])
rc0, h0, e0, r0 = out['off']
rc1, h1, e1, r1 = out['on']
check('⑪ 러너 기본 0 — 지문·run_meta 에 열쇠가 없고 사전(bestiary_defs)에 새 종이 없고 2층에도 옛 종뿐',
      rc0 == 0 and h0 == {'on': False, 'fp': None} and r0 and 'bestiary_plus' not in r0[0]
      and not any(('monster:' + k) in (r0[0].get('bestiary_defs') or {}) for k in PLUS)
      and not any(m['kind'] in PLUS for r in r0 if r.get('kind') == 'level' for m in r['monsters']), (rc0, h0, e0))
lv1 = next((r for r in r1 if r.get('kind') == 'level'), {})
check('⑪ 켠 러너(2층에서 시작하는 프리셋) — 지문·run_meta 열쇠 · 사전에 세 종 · 첫 level 에 새 종 · 보스 그대로 · 80틱 예외 없이 끝',
      rc1 == 0 and h1 == {'on': True, 'fp': True} and r1 and r1[0].get('bestiary_plus') is True
      and all(('monster:' + k) in (r1[0].get('bestiary_defs') or {}) for k in PLUS)
      and lv1.get('depth') == 2 and any(m['kind'] in PLUS for m in lv1.get('monsters') or [])
      and sum(1 for m in lv1.get('monsters') or [] if m.get('boss')) == 1 and r1[-1].get('kind') == 'end', (rc1, h1, e1))
check('⑪ 끈 판과 켠 판의 run_meta 차이는 열쇠 하나와 사전뿐',
      bool(r0 and r1) and {k: v for k, v in r0[0].items() if k not in ('started', 'bestiary_defs')}
      == {k: v for k, v in r1[0].items() if k not in ('started', 'bestiary_defs', 'bestiary_plus')})
rsrc = src('show_runner.py')
check('⑪ 배선(소스): 러너 스위치 · 생성 세 자리에 같은 인자 · 지문·run_meta 는 켠 판에만 · 사전은 스위치를 따른다',
      'DUNGEON_BESTIARY_PLUS", "0") == "1"' in rsrc and rsrc.count('bestiary_plus=BESTIARY_PLUS_ON,') == 3
      and rsrc.count('**({"bestiary_plus": True} if BESTIARY_PLUS_ON else {})') == 2 and 'G.ENT.lore(plus=BESTIARY_PLUS_ON)' in rsrc)
wsrc = src(os.path.join('game', 'src', 'assets', 'world.ts'))
check('⑪ 클라이언트 그림 매핑 — 세 종 전부 world.ts 에(모르는 종 폴백 타일로 안 샌다) · 정의의 스프라이트는 기존 시트',
      all(("'%s'" % k) in wsrc for k in PLUS)
      and {G.ENT.monster(k)['sprite'] for k in PLUS} <= {'wl-goblin', 'wl-spider'})
check('⑪ 게이트 등록(_run_gates.sh)', re.search(r'\bverify_mobs\b', src('_run_gates.sh')) is not None)

print('=' * 44)
if C.failed:
    print('RESULT: %d FAILED / %d' % (C.failed, C.n))
    raise SystemExit(1)
print('ALL PASS — verify_mobs (D92 새 몬스터: 끈 판 동일·1층 불변·2층+ 배치·묶음·중독·걸음 박자·도감·더미 풀판·결정론·피클·러너, %d checks, 실 LLM 0콜)' % C.n)

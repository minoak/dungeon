# -*- coding: utf-8 -*-
"""사건층 2겹+묘(D22, 07-20) 헤들리스 검증 — 20번째 게이트.
전달층="시야 내 그 틱 사건은 전부 한 줄 목격(휘발=다음 결정 1회)" — A-3 어휘 확장(명중·처치·
함정·회복·비몬스터 전사). 기억층="목격한 전사는 지속 기억(fallen) — 매 결정 재제시(휘발 0)".
묘="쓰러진 자리의 표지판(시체 아님 — D4 불가침)" — 광학(sights·글리프 T)·조회·goto 앵커.
발단: seed 7 미니 판 부검 — 카야가 대각 1칸에서 목격한 두란 전사를 40틱 뒤 "뭐에 당했어?"
(1회 노출 후 소거가 유일한 채널 = 보존의 구멍) + "두란을 찾아야"가 원리적 불가(공간 표현 부재).
게이트:
  ① 스위치: 엔진 기본 0 / from_ascii 기본 0, events=0 이면 새 어휘·기억·묘 전부 무발화
     (몹 사망의 기존 A-3 ally_down 1회는 그대로 — 기존 비트 보존)
  ② 묘: 함정 사망 → 그 칸에 '~의 묘' 피처 + 글리프 T + sights 노출 + goto 옵션 + 장부 등재
  ③ 전달층 처치: 몹 처치 → 시야 내 동료 ally_kill(시야 밖 무주입·당사자 제외)
  ④ 전달층 함정·회복: 생존 함정 → ally_trap(safe·dmg), 물약 → ally_heal(how=물약)
  ⑤ 휘발: witnessed = view 1회 노출 후 소거 / memories = view 반복에도 지속(휘발 0)
  ⑥ 기억: 사망 목격 → fallen {char, by, zone, turn} — 몹·함정 경로 모두, ally_down 중복 없음
  ⑦ 도감 게이트: 모르는 종 = 낯선 짐승(mon·by), 비몬스터 사인(by_kind)은 면제
  ⑧ 렌더: brains 프롬프트에 목격 문장·"잊지 못할 일" 섹션
  ⑨ 결정론: 같은 장면 2회 = 같은 목격·기억 열
(기존 verify 19종은 별도 실행.)
"""
import json

import brains
import dungeon_gm as G
from dungeon_gm import Dungeon, new_ledger


class C:
    failed = 0


def check(name, cond):
    print(("  OK   " if cond else " FAIL  ") + name)
    if not cond:
        C.failed += 1


def mkbot(char, x, y, dex=0, job='전사', hp=14):
    return {'char': char, 'x': x, 'y': y, 'hp': hp, 'maxhp': 14,
            'str': 3, 'dex': dex, 'wdmg': 4, 'stealth': 0,
            'search_r': 1, 'job': job, 'sex': '남', 'persona': '', 'bag': 0,
            'alive': True, 'won': False, 'order': None, 'path': [],
            'aware_of': set(), 'plan': []}


# ── 무대: 한 방(봇1·몹 g·봇2·함정) + 벽 너머 골방(봇3 = 시야 밖 대조군) ──
ROWS = [
    "###########",
    "#..1g.2.#.#",
    "#.^.....#3#",
    "#.......#.#",
    "#......>#.#",
    "###########",
]


def scene(graves=False, events=False, scan=False, ledger=False, known=None):
    """장면 조립 — 몹 g: hp1·ac1(첫 타 확정 처치), 함정: dc99·dmg20(밟으면 확정 전사)."""
    d, starts = Dungeon.from_ascii(ROWS, seed=7, scan=scan,
                                   monsters={'g': {'kind': '고블린', 'hp': 1, 'ac': 1,
                                                   'state': 'WANDERING'}})
    d.graves, d.events = graves, events
    d.traps[0].dc, d.traps[0].dmg = 99, 20
    b1 = mkbot('1', *starts['1'], job='전사')
    b2 = mkbot('2', *starts['2'], job='도적')
    b3 = mkbot('3', *starts['3'], job='음유시인')
    bots = [b1, b2, b3]
    if ledger:
        b2['ledger'] = new_ledger()
    if known is not None:
        for b in bots:
            b['known'] = set(known)
    return d, b1, b2, b3, bots


def wit_of(b, kind=None):
    ws = b.get('witnessed') or []
    return [w for w in ws if kind is None or w.get('kind') == kind]


# ───────────────────── ① 스위치 격리 ─────────────────────
print("── ① 스위치 격리 (엔진 기본 0 · 기존 비트 보존)")
d0 = Dungeon(seed=7)
check("① 엔진 직생성 기본: graves=False, events=False",
      d0.graves is False and d0.events is False)
d0f, _ = Dungeon.from_ascii(ROWS, seed=7)
check("① from_ascii 기본: graves=False, events=False",
      d0f.graves is False and d0f.events is False)

d, b1, b2, b3, bots = scene()                     # 전부 꺼짐
d._attack(b1, 'm0', bots)                          # 몹 처치
check("① events=0: 처치 목격(ally_kill) 무주입", not wit_of(b2, 'ally_kill'))
d._enter_cell(b1, 2, 2, bots)                      # 함정 확정 전사
check("① events=0: 함정 전사에 witnessed·memories 무주입",
      not b2.get('witnessed') and not b2.get('memories'))
check("① graves=0: 묘 미생성",
      not [f for f in d.features.values() if f.type == 'grave'])

d, b1, b2, b3, bots = scene()                     # 기존 A-3(몹 공격 전사)는 스위치 무관 보존
b1['hp'] = 1
m = d.monsters[0]
for _ in range(40):
    if not b1['alive']:
        break
    d._monster_attack(m, b1, bots)
check("① 몹 공격 전사 성립(장면 전제)", not b1['alive'])
check("① events=0: 기존 A-3 ally_down 정확히 1회(비트 보존)",
      len(wit_of(b2, 'ally_down')) == 1 and not b2.get('memories'))

# ───────────────────── ② 묘 ─────────────────────
print("── ② 묘 — 쓰러진 자리의 표지판")
d, b1, b2, b3, bots = scene(graves=True, events=True)
d._enter_cell(b1, 2, 2, bots)
graves = [f for f in d.features.values() if f.type == 'grave']
check("② 함정 전사 → 그 칸에 묘 1기", len(graves) == 1
      and (graves[0].x, graves[0].y) == (2, 2))
check("② 이름 '전사의 묘'(시트 이름 없으면 직업)", graves and graves[0].name == '전사의 묘')
obs2 = d.view(b2, bots)
check("② sights 노출: 시야 내 동료 눈에 묘가 보인다",
      any(f['type'] == 'grave' for f in obs2['sights']['features']))
check("② ascii_view 글리프 T", any('T' in row for row in obs2['ascii_view']))
check("② legend 등재", obs2['legend'].get('T') == 'grave')
check("② goto 앵커: '이동: 전사의 묘' 옵션",
      any(o.get('type') == 'goto' and '전사의 묘' in o.get('label', '')
          for o in obs2['options']))
d, b1, b2, b3, bots = scene(graves=True, events=True, ledger=True)
d._enter_cell(b1, 2, 2, bots)
d.view(b2, bots)
check("② 장부 등재: 묘가 statics(돌아가기 앵커)에 남는다",
      any(e.get('type') == 'grave' for e in b2['ledger']['statics'].values()))
d, b1, b2, b3, bots = scene(graves=True, events=True)
b1['hp'] = 1
m = d.monsters[0]
mx, my = m.x, m.y
for _ in range(40):
    if not b1['alive']:
        break
    ev = d._monster_attack(m, b1, bots)
check("② 몹 사망 경로도 묘 + 이벤트에 grave 병기(스트림 additive)",
      [f for f in d.features.values() if f.type == 'grave']
      and ev.get('grave', {}).get('name') == '전사의 묘')

# ───────────────────── ③ 전달층: 처치 목격 ─────────────────────
print("── ③ 전달층 — \"카야가 공격했다!\" \"고블린이 쓰러졌다!\"")
d, b1, b2, b3, bots = scene(events=True)
res = d._attack(b1, 'm0', bots)
check("③ 처치 성립(장면 전제)", res.get('killed') is True)
kills = wit_of(b2, 'ally_kill')
check("③ 시야 내 동료: ally_kill {char, mon}",
      len(kills) == 1 and kills[0]['char'] == '1' and kills[0]['mon'] == '고블린')
check("③ 시야 밖(벽 너머) 동료: 무주입", not b3.get('witnessed'))
check("③ 당사자 제외(자기 경험은 last 소관)", not b1.get('witnessed'))

# ───────────────────── ④ 전달층: 함정·회복 ─────────────────────
print("── ④ 전달층 — 함정 장면·회복 장면")
d, b1, b2, b3, bots = scene(events=True)
d.traps[0].dmg = 3                                 # 아프지만 안 죽는다
d._enter_cell(b1, 2, 2, bots)
traps = wit_of(b2, 'ally_trap')
check("④ 함정 장면: ally_trap {trap, safe, dmg}",
      len(traps) == 1 and traps[0]['safe'] is False and traps[0].get('dmg') == 3
      and traps[0].get('trap'))
check("④ 생존 함정엔 ally_down 없음(전사만 전사다)", not wit_of(b2, 'ally_down'))
d, b1, b2, b3, bots = scene(events=True)
b1['hp'], b1['potions'] = 5, 1
d._drink(b1, bots)
heals = wit_of(b2, 'ally_heal')
check("④ 회복 장면: ally_heal {how=물약}",
      len(heals) == 1 and heals[0]['how'] == '물약')

# ───────────────────── ⑤ 휘발 — 전달은 1회, 기억은 영속 ─────────────────────
print("── ⑤ 휘발 — 전달층=다음 결정 1회, 기억층=휘발 0")
d, b1, b2, b3, bots = scene(graves=True, events=True)
d._enter_cell(b1, 2, 2, bots)                      # 전사
o1 = d.view(b2, bots)
o2 = d.view(b2, bots)
check("⑤ witnessed: 첫 view 에 실리고", bool(o1.get('witnessed')))
check("⑤ witnessed: 다음 view 엔 소거(휘발=다음 결정 1회)", not o2.get('witnessed'))
check("⑤ memories: 두 view 모두 재제시(휘발 0)",
      bool(o1.get('memories')) and bool(o2.get('memories')))

# ───────────────────── ⑥ 기억층 — fallen ─────────────────────
print("── ⑥ 기억층 — 목격한 전사는 잊지 않는다")
d, b1, b2, b3, bots = scene(graves=True, events=True, scan=True)
d.turn = 45
d._enter_cell(b1, 2, 2, bots)
mem = (b2.get('memories') or [])
check("⑥ fallen {char, by, zone, turn}",
      len(mem) == 1 and mem[0]['kind'] == 'fallen' and mem[0]['char'] == '1'
      and mem[0]['by'] and mem[0]['turn'] == 45)
check("⑥ 장소는 사람말 구역 이름 — 좌표·번호 없음(scan 판)",
      mem and isinstance(mem[0].get('zone'), str) and mem[0]['zone']
      and not any(ch.isdigit() for ch in mem[0]['zone']))
check("⑥ 시야 밖 동료는 기억도 없다(전지 주입 금지)", not b3.get('memories'))
check("⑥ 비몬스터 사인 by_kind 병기", mem and mem[0].get('by_kind') == 'trap')
d, b1, b2, b3, bots = scene(graves=True, events=True)
b1['hp'] = 1
m = d.monsters[0]
for _ in range(40):
    if not b1['alive']:
        break
    d._monster_attack(m, b1, bots)
check("⑥ 몹 사망 경로: fallen 등재 + ally_down 중복 없음(A-3 1회 그대로)",
      len(b2.get('memories') or []) == 1
      and len(wit_of(b2, 'ally_down')) == 1)

# ───────────────────── ⑦ 도감 게이트 ─────────────────────
print("── ⑦ 도감 게이트 — 모르는 종은 낯선 짐승, 함정 사인은 면제")
d, b1, b2, b3, bots = scene(events=True, known=set())   # 빈 도감
d._attack(b1, 'm0', bots)
o = d.view(b2, bots)
kills = [w for w in (o.get('witnessed') or []) if w['kind'] == 'ally_kill']
check("⑦ 모르는 종 처치 목격 = 낯선 짐승", kills and kills[0]['mon'] == G.UNKNOWN_BEAST)
d, b1, b2, b3, bots = scene(graves=True, events=True, known=set())
d._enter_cell(b1, 2, 2, bots)
o = d.view(b2, bots)
downs = [w for w in (o.get('witnessed') or []) if w['kind'] == 'ally_down']
mem = o.get('memories') or []
check("⑦ 함정 사인(by_kind)은 도감 게이트 면제 — 함정 이름 그대로",
      downs and downs[0]['by'] != G.UNKNOWN_BEAST
      and mem and mem[0]['by'] != G.UNKNOWN_BEAST)

# ───────────────────── ⑧ 렌더 — brains 프롬프트 ─────────────────────
print("── ⑧ 렌더 — 두뇌가 읽는 문장")
d, b1, b2, b3, bots = scene(graves=True, events=True, scan=True)
d._attack(b1, 'm0', bots)
d._enter_cell(b1, 2, 2, bots)
o = d.view(b2, bots)
wire = brains._wire(o)
check("⑧ 처치 목격 문장(\"쓰러뜨리는 것을\")", '쓰러뜨리는 것을' in wire)
check("⑧ 전사 목격 문장(\"쓰러지는 것을\")", '쓰러지는 것을' in wire)
check("⑧ 기억 섹션 '잊지 못할 일' + '쓰러졌다'",
      '잊지 못할 일' in wire and '쓰러졌다' in wire)
o2 = d.view(b2, bots)
wire2 = brains._wire(o2)
check("⑧ 다음 결정: 목격은 사라지고 기억은 남는다",
      '쓰러뜨리는 것을' not in wire2 and '잊지 못할 일' in wire2)
check("⑧ obs JSON 직렬화 가능(스트림 계약)", bool(json.dumps(o, ensure_ascii=False)))

# ───────────────────── ⑨ 결정론 ─────────────────────
print("── ⑨ 결정론")


def run_once():
    d, b1, b2, b3, bots = scene(graves=True, events=True, scan=True)
    d._attack(b1, 'm0', bots)
    d._enter_cell(b1, 2, 2, bots)
    return ([(w.get('kind'), w.get('char'), w.get('by'), w.get('mon'))
             for w in (b2.get('witnessed') or [])],
            [(e.get('kind'), e.get('char'), e.get('by'), e.get('zone'), e.get('turn'))
             for e in (b2.get('memories') or [])],
            sorted((f.type, f.x, f.y, f.name) for f in d.features.values()))


check("⑨ 같은 장면 2회 = 같은 목격·기억·피처 열", run_once() == run_once())

print()
if C.failed:
    print("FAIL — %d개 실패" % C.failed)
    raise SystemExit(1)
print("ALL PASS — verify_events (D22 사건층 2겹+묘)")

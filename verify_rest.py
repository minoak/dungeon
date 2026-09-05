# -*- coding: utf-8 -*-
"""휴식(D35, 2026-09-06 파트너 확정 "지우는 조건은 캐릭터 선택지 — 휴식으로 지울 수 있게. 덤으로 피가
차고 캐릭터 간 상호작용도 가능") 헤들리스 검증 — 35번째 게이트.
휴식 = 회복이 붙은 wait(D25). 틱마다 HP +REST_HP, 완료 = 만피 && REST_MIN 틱 → 상태 태그(D34) 전부
소거. 깨어남 = 사건(새 몹·새 오브젝트·동료 진입·말 걸림·피격) — 지루함 상한 대신 완료가 있다. 깨면
진행 리셋. 어디서나·안전 보장 없음. 대기 중 LLM 0콜(order 유지=think_all 스킵 구조 그대로).
게이트:
  ① 스위치: 엔진 기본 0 / from_ascii 기본 0 / 꺼진 판 act rest=대기(또는 탐색) 폴백·메뉴 미노출
  ② 개시: act rest → order='rest'+resting, 옵션 노출 조건(HP<최대 또는 상태 태그), then 못 잇는다
  ③ 회복·완료: 틱마다 HP 1 → 만피&&REST_MIN 에 rested{ticks,healed,cleared} → status 비움·order 파기
  ④ 깨어남: 새 몹(encounter, woke=rest) / 동료 진입(rest_met) / 말 걸림(hail 이 order 를 끊고, 다시
     rest 를 고를 수 있다 — 진행 리셋) / 피격(기존 인터럽트)
  ⑤ 창 배타: 휴식 틱은 맴돎·무발견 어느 창에도 안 쌓인다
  ⑥ 출혈 중 휴식 = 피 안 남(걸음이 아니다) · 완료 시 bleed_steps·slow_beat 리셋
  ⑦ 렌더: 라벨=사실만(회복량·완료 조건·깨는 사건, 물음표 0) · 개시/틱/완료/중단 문장 · 동료 "(휴식중)"
  ⑧ 작정·모임: plan_step 의 rest 수 유효 / _gather_busy 가 쉬는 동료를 '딴 작정'으로 센다
  ⑨ 결정론 · 러너 스위치/메타/요약 코드 존재
(기존 verify 34종은 별도 실행.)
"""
import io
import json
import os

import brains
import dungeon_gm as G
from dungeon_gm import Dungeon

HERE = os.path.dirname(os.path.abspath(__file__))


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
            'alive': True, 'won': False, 'order': None, 'path': [],
            'aware_of': set(), 'plan': [], 'status': {}, 'bleed_steps': 0, 'slow_beat': 0,
            'rest': None, 'witnessed': [], 'memories': []}


ROOM = ["##############",
        "#1...........#",
        "#............#",
        "#####>########"]


def scene(rest=True, hp=10, status=True, wait=True):
    d, st = Dungeon.from_ascii(ROOM, seed=7)
    d.rest_verb, d.status, d.wait_verb = rest, status, wait
    b = mkbot('1', *st['1'], hp=hp)
    return d, b, [b]


def opt(obs, typ):
    return next((o for o in obs.get('options', []) if o['type'] == typ), None)


# ────────────────────────────────────────────────────────────────
print("① 스위치 격리")
check("엔진 기본 rest_verb=0", Dungeon(seed=7).rest_verb is False)
d0, _ = Dungeon.from_ascii(["####", "#1>#", "####"])
check("from_ascii 기본 rest_verb=0", d0.rest_verb is False)
d, b, bots = scene(rest=False)
check("꺼진 판: 메뉴에 rest 없음", opt(d.view(b, bots), 'rest') is None)
r = d.act(b, {'type': 'rest'}, bots)
check("꺼진 판: act rest = 대기 폴백(환각 방어)", r.get('type') == 'wait' and b['order'] == 'wait')
d, b, bots = scene(rest=False, wait=False)
r = d.act(b, {'type': 'rest'}, bots)
check("꺼진 판(wait 도 꺼짐): act rest = 탐색 폴백", r.get('type') == 'explore')

# ────────────────────────────────────────────────────────────────
print("② 개시·옵션 노출")
d, b, bots = scene()
o = opt(d.view(b, bots), 'rest')
check("다친 몸: 메뉴에 '쉰다' 옵션", o is not None and o['label'].startswith('쉰다'))
check("라벨=사실만(회복량·완료·깨는 사건, 물음표 0)",
      o is not None and ('HP %d 회복' % G.REST_HP) in o['label']
      and '다 나으면' in o['label'] and '깬다' in o['label'] and '?' not in o['label'])
r = d.act(b, {'type': 'rest', 'then': [{'type': 'explore'}]}, bots)
check("act rest → order='rest'·resting·then 못 잇는다(열린 결말)",
      r.get('result') == 'resting' and b['order'] == 'rest' and b['plan'] == []
      and b['rest'] is not None and b['rest']['n'] == 0)
d, b, bots = scene(hp=14)
check("성한 몸·무태그: rest 옵션 없음('기다린다'가 서 있기를 담당)",
      opt(d.view(b, bots), 'rest') is None and opt(d.view(b, bots), 'wait') is not None)
b['status']['출혈'] = {'n': 1, 'by': '가시 함정', 'since': 0}
check("성한 몸이라도 상태 태그가 있으면 rest 옵션", opt(d.view(b, bots), 'rest') is not None)

# ────────────────────────────────────────────────────────────────
print("③ 회복·완료")
d, b, bots = scene(hp=10)
b['status']['출혈'] = {'n': 1, 'by': '가시 함정', 'since': 0}
b['status']['중독'] = {'n': 1, 'by': '독침 함정', 'since': 0}
d.act(b, {'type': 'rest'}, bots)
seq = []
for _ in range(4):
    r = d.step_order(b, bots)
    seq.append((r['result'], b['hp']))
check("틱마다 HP +1 (10→14), 4틱은 아직 resting",
      seq == [('resting', 11), ('resting', 12), ('resting', 13), ('resting', 14)])
check("만피여도 REST_MIN 전엔 상태 유지", '출혈' in b['status'] and b['order'] == 'rest')
r = d.step_order(b, bots)
check("5틱째 rested{ticks=5, healed=4, cleared=[중독,출혈]} → status 비움·order 파기",
      r['result'] == 'rested' and r['ticks'] == 5 and r['healed'] == 4
      and r['cleared'] == ['중독', '출혈'] and b['status'] == {} and b['order'] is None
      and b['rest'] is None)
d, b, bots = scene(hp=14)
b['status']['둔화'] = {'n': 1, 'by': '그림자거미', 'since': 0}
b['slow_beat'] = 1
d.act(b, {'type': 'rest'}, bots)
rs = [d.step_order(b, bots)['result'] for _ in range(G.REST_MIN)]
check("만피+상태만: REST_MIN 틱에 완료(healed 0)·slow_beat 리셋",
      rs[-1] == 'rested' and all(x == 'resting' for x in rs[:-1]) and b['status'] == {}
      and b['slow_beat'] == 0)
d, b, bots = scene(hp=2)
d.act(b, {'type': 'rest'}, bots)
n = 0
while b['order'] == 'rest' and n < 30:
    r = d.step_order(b, bots); n += 1
check("hp 2 → 만피는 12틱(REST_HP=1) — 완료", n == 12 and r['result'] == 'rested' and b['hp'] == 14)

# ────────────────────────────────────────────────────────────────
print("④ 깨어남")
MONROOM = ["##############",
           "#1...........#",
           "#...........g#",
           "#####>########"]
d, st = Dungeon.from_ascii(MONROOM, seed=7,
                           monsters={'g': {'kind': '고블린', 'state': 'SLEEPING'}})
d.rest_verb, d.status = True, True
b = mkbot('1', *st['1'], hp=10)
bots = [b]
m = d.monsters[0]
d.act(b, {'type': 'rest'}, bots)
r = d.step_order(b, bots)
check("멀리 있는(시야 밖) 몹은 안 깨운다", r['result'] == 'resting')
m.x = b['x'] + 3                                  # 몹이 시야에 든다(배회로 다가온 장면)
r = d.step_order(b, bots)
check("새 몹 → encounter(woke=rest)·order 파기", r['result'] == 'encounter'
      and r.get('woke') == 'rest' and b['order'] is None and b['rest'] is None)

d, b, bots = scene(hp=10)
b2 = mkbot('2', 12, 2, job='도적')
b2['x'], b2['y'] = 12, 1                          # 오른쪽 끝(거리 11 — 시야 밖)
bots = [b, b2]
d.act(b, {'type': 'rest'}, bots)
r = d.step_order(b, bots)
check("시야 밖 동료는 안 깨운다", r['result'] == 'resting')
b2['x'] = b['x'] + 2                              # 동료가 걸어와 시야에 든다
r = d.step_order(b, bots)
check("동료 진입 → rest_met{allies=[2]}·order 파기",
      r['result'] == 'rest_met' and r.get('allies') == ['2'] and b['order'] is None)

d, b, bots = scene(hp=10)
b2 = mkbot('2', b['x'] + 1, b['y'], job='도적')
bots = [b, b2]
d.hail = True
d.act(b, {'type': 'rest'}, bots)
for _ in range(3):
    d.step_order(b, bots)
check("3틱 쉬어 HP 13", b['hp'] == 13 and b['rest']['n'] == 3)
got = d.hail_stop(b, ['2'])
check("말 걸림 → hail 이 휴식을 끊는다(재결정)", got == ['2'] and b['order'] is None
      and b['last'].get('type') == 'hail')
r = d.act(b, {'type': 'rest'}, bots)
check("대답한 뒤 다시 '쉰다' — 진행은 처음부터", b['order'] == 'rest' and b['rest']['n'] == 0)

d, st = Dungeon.from_ascii(["#######", "#1g..>#", "#######"], seed=7,
                           monsters={'g': {'kind': '고블린', 'state': 'HUNTING', 'target': '1'}})
d.rest_verb, d.status = True, True
b = mkbot('1', *st['1'], hp=10)
bots = [b]
b['aware_of'].add(d.monsters[0].id)
d.monsters[0].last_seen = (b['x'], b['y'])
d.act(b, {'type': 'rest'}, bots)
d.d20 = lambda: 20
ev = d._monster_attack(d.monsters[0], b, bots)
check("피격 → 기존 인터럽트가 휴식을 끊는다", ev['hit'] and b['order'] is None)

# ────────────────────────────────────────────────────────────────
print("⑤ 창 배타 · ⑥ 출혈 중 휴식")
d, b, bots = scene(hp=10)
b['dry'], b['wander'] = 3, None
b['status']['출혈'] = {'n': 2, 'by': '가시 함정', 'since': 0}
b['bleed_steps'] = 2
d.act(b, {'type': 'rest'}, bots)
for _ in range(3):
    d.step_order(b, bots)
check("휴식 틱은 무발견 걸음·맴돎 박자에 안 쌓인다", b['dry'] == 3 and b.get('wander') is None)
check("출혈 중 휴식: 피 안 나고 차기만 한다(bleed_steps 그대로)",
      b['hp'] == 13 and b['bleed_steps'] == 2)
for _ in range(2):
    r = d.step_order(b, bots)
check("완료 시 출혈 소거·bleed_steps 0", r['result'] == 'rested' and b['status'] == {}
      and b['bleed_steps'] == 0)

# ────────────────────────────────────────────────────────────────
print("⑦ 렌더")
names = {'1': '두란', '2': '카야'}
check("개시 문장", "쉬기로 했다" in brains._last_prose({'type': 'rest', 'result': 'resting', 'hp': 10}))
check("틱 문장", brains._last_prose({'type': 'walk', 'result': 'resting', 'hp': 12}) == "쉬는 중이다 (HP 12)")
check("완료 문장(나은 상태 명기)", brains._last_prose(
    {'type': 'walk', 'result': 'rested', 'ticks': 5, 'healed': 4, 'cleared': ['출혈']})
      == "푹 쉬었다 — HP 4 회복, 몸 상태가 나았다: 출혈")
check("동료 진입 문장", brains._last_prose(
    {'type': 'walk', 'result': 'rest_met', 'allies': ['2']}, names) == "쉬다 눈을 떴다 — 카야가 시야에 들어왔다")
check("새 몹 문장(쉬다 눈을 떴다)", brains._last_prose(
    {'type': 'walk', 'result': 'encounter', 'woke': 'rest',
     'monsters': [{'kind': '고블린'}]}).startswith("쉬다 눈을 떴다 — 처음 보는 적: 고블린"))
check("걷다 만난 문장은 불변", brains._last_prose(
    {'type': 'walk', 'result': 'encounter', 'monsters': [{'kind': '고블린'}]}).startswith("걷다 멈췄다"))
d, b, bots = scene(hp=10)
b2 = mkbot('2', b['x'] + 2, b['y'], job='도적')
bots = [b, b2]
d.act(b, {'type': 'rest'}, bots)
o2 = d.view(b2, bots)
ally = next(a for a in o2['sights']['bots'] if a['char'] == '1')
check("동료 항목 resting=True", ally.get('resting') is True)
check("동료 줄 '(휴식중)'", "(휴식중)" in brains._wire(o2, names))
check("_TYPES 에 rest", "rest" in brains._TYPES)

# ────────────────────────────────────────────────────────────────
print("⑧ 작정·모임")
d, b, bots = scene(hp=10)
b['plan'] = [{'type': 'rest'}]
step = d.plan_step(b, bots)
check("plan_step 의 rest 수 유효(열린 동사)", step is not None and step.get('type') == 'rest')
d, b, bots = scene(hp=10)
b2 = mkbot('2', b['x'] + 1, b['y'], job='도적')
bots = [b, b2]
d.act(b2, {'type': 'rest'}, bots)
busy = d._gather_busy(b, [b2], 'exit')
check("_gather_busy: 쉬는 동료는 '딴 작정'(끌려 하강 안 함)", [o['char'] for o in busy] == ['2'])

# ────────────────────────────────────────────────────────────────
print("⑨ 결정론·러너")


def run():
    d, b, bots = scene(hp=9)
    b['status']['출혈'] = {'n': 1, 'by': '가시 함정', 'since': 0}
    d.act(b, {'type': 'rest'}, bots)
    out = []
    while b['order'] == 'rest':
        r = d.step_order(b, bots)
        out.append((r['result'], b['hp']))
    return json.dumps(out) + json.dumps(b['status'])


check("같은 장면 2회 = 같은 열", run() == run())
src = io.open(os.path.join(HERE, "show_runner.py"), encoding="utf-8").read()
check("러너 스위치·메타·요약 코드 존재",
      'DUNGEON_REST' in src and 'rest=REST_ON' in src and 'rest_verb=REST_ON' in src
      and '휴식 끝' in src)
lab = io.open(os.path.join(HERE, "adventurer_prompt_menu.md"), encoding="utf-8").read()
check("프롬프트 물리 절에 휴식 사실 문장", "휴식뿐이다" in lab and "말을 걸어오면 깬다" in lab)

print()
print(("RESULT: ALL PASS" if not C.failed else "RESULT: %d FAIL" % C.failed)
      + " — verify_rest (D35 휴식: 개시·회복·완료·깨어남·렌더·작정·결정론)")
raise SystemExit(1 if C.failed else 0)

# -*- coding: utf-8 -*-
"""스킬 스키마·비용·랜덤 결정론 검증. 외부 호출 0회."""
import copy
import json
import random
from types import SimpleNamespace

import skill_schema as S
import skill_combat as C

checks = 0


def check(label, value):
    global checks
    assert value, label
    checks += 1
    print('  OK ' + label)


check('프리셋 네 개는 동일한 스키마·비용 계산 사용', len(S.PRESETS) == 4 and all(
    not S.validate(s) and s['cost'] == S.skill_cost(s) for s in S.PRESETS.values()))
original = copy.deepcopy(S.PRESETS['push_slash'])
for key, value in [('id', 'attack'), ('range', -1), ('range', True), ('roll', {'type': 'unknown'}),
                   ('effects', []), ('effects', [{'type': 'damage', 'dice': '999d999'}]),
                   ('penalties', [{'type': 'hp_cost', 'value': -4}]), ('cost', 0)]:
    invalid = {**original, key: value}
    check('잘못된 %s=%r 거절' % (key, value), bool(S.validate(invalid)))
for invalid in [None, [], 4, {}, {'id': []}, {'id': 'x', 'name': []}]:
    check('임의 JSON 입력도 예외 없이 오류 반환 %r' % invalid, bool(S.validate(invalid)))
mix = copy.deepcopy(original)
mix['effects'][0] = {'type': 'heal', 'dice': '1d6'}
check('회복+밀침 금지', S.validate(mix) == ['incompatible_effects'])
strong = copy.deepcopy(original)
strong['effects'][0]['dice'] = '2d6'
far = {**original, 'range': 5}
constrained = {**original, 'penalties': original['penalties'] + [{'type': 'hp_cost', 'value': 2}]}
check('강한 효과와 긴 사거리는 비싸고 실제 패널티는 환급',
      S.skill_cost(strong) > S.skill_cost(original) and S.skill_cost(far) > S.skill_cost(original)
      and S.skill_cost(constrained) < S.skill_cost(original))
for seed in range(1000):
    skill = S.generate(seed, 5)
    assert not S.validate(skill) and skill['cost'] <= 5
    assert skill == S.generate(seed, 5)
check('1000개 시드 유효성·예산·재현', True)
check('구성요소 풀 순서에 무관', S.generate('order', allowed_effects=['push', 'damage']) ==
      S.generate('order', allowed_effects=['damage', 'push']))
for effect in S.COMPONENTS:
    for seed in range(20):
        skill = S.generate(seed, 8, [effect], ['cooldown'])
        assert all(S.effect_key(e) == effect for e in skill['effects'])
        assert all(p['type'] == 'cooldown' for p in skill['penalties'])
check('제한된 효과·패널티 풀 존중', True)
for args in [dict(budget=0), dict(allowed_effects=[]), dict(allowed_effects=['teleport']),
             dict(budget=1, allowed_effects=['heal'], allowed_penalties=[])]:
    try:
        S.generate(7, **args)
    except ValueError:
        pass
    else:
        raise AssertionError(args)
check('불가능한 생성은 유한 횟수 뒤 명확한 오류', True)
check('반환값을 고쳐도 프리셋이 오염되지 않음', S.PRESETS['push_slash'] == original)


def rolls(values):
    source = iter(values)
    return SimpleNamespace(d20=lambda: next(source), rng=random.Random(7))


check('유리굴림은 큰 눈', C.check(rolls([2, 18]), 0, 10, advantage=True, attack=True)['roll'] == 18)
check('불리굴림은 작은 눈', C.check(rolls([2, 18]), 0, 10, disadvantage=True, attack=True)['roll'] == 2)
check('유리+불리 상쇄는 한 번만 굴림', C.check(rolls([10]), 2, 12, True, True)['rolls'] == [10])
check('공격 자연1 실패·자연20 명중', not C.check(rolls([1]), 99, 1, attack=True)['success']
      and C.check(rolls([20]), -99, 99, attack=True)['success'])
check('내성 동률 성공, 자연20 자동성공 없음', C.check(rolls([10]), 3, 13)['success']
      and not C.check(rolls([20]), 0, 30)['success'])
check('치명타는 주사위 개수 두 배', len(C.damage(rolls([]), '2d6+1', critical=True)['rolls']) == 4)
check('TRPG OFF 스킬 수치는 고정 평균 반올림', C.damage(rolls([]), '1d6', rolled=False)['value'] == 4)
check('모든 결과 JSON 직렬화 가능', bool(json.dumps(S.generate(15))))
print('ALL PASS — verify_skill_schema (%d checks)' % checks)

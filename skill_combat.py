# -*- coding: utf-8 -*-
"""알파 전투의 작은 판정 함수. 전역 난수를 쓰지 않고 던전의 RNG만 사용한다."""
import re


def dice_parts(text):
    match = re.fullmatch(r'([1-8])d([2-9]|1[0-9]|20)([+-](?:[0-9]|1[0-6]))?', str(text))
    if not match:
        raise ValueError('주사위는 1~8d2~20, 보정은 -16~16이어야 한다')
    return int(match[1]), int(match[2]), int(match[3] or 0)


def expected_damage(text):
    n, sides, bonus = dice_parts(text)
    return max(0, n * (sides + 1) / 2 + bonus)


def damage(d, text, critical=False, rolled=True):
    n, sides, bonus = dice_parts(text)
    if not rolled:
        value = int(expected_damage(text) + 0.5) * (2 if critical else 1)
        return {'dice': text, 'rolls': [], 'value': value, 'mode': 'fixed'}
    rolls = [d.rng.randint(1, sides) for _ in range(n * (2 if critical else 1))]
    return {'dice': text, 'rolls': rolls, 'value': max(0, sum(rolls) + bonus), 'mode': 'dice'}


def check(d, modifier, dc, advantage=False, disadvantage=False, attack=False):
    # 유리와 불리가 동시에 있으면 상쇄한다. 내성은 자연 1/20 특례가 없다.
    mode = 'normal' if bool(advantage) == bool(disadvantage) else ('advantage' if advantage else 'disadvantage')
    rolls = [d.d20() for _ in range(1 if mode == 'normal' else 2)]
    roll = min(rolls) if mode == 'disadvantage' else max(rolls)
    success = roll + modifier >= dc
    if attack:
        success = roll == 20 or (roll != 1 and success)
    return {'rolls': rolls, 'mode': mode, 'roll': roll, 'mod': modifier,
            'total': roll + modifier, 'dc': dc, 'success': success,
            'critical': bool(attack and roll == 20)}


def weapon_dice(base):
    """기존 피해에 가까운 평균(+0.5)의 주사위: 피해 4 → 1d6+1, 피해 3 → 1d4+1."""
    base = max(1, int(base))
    sides = min(20, max(2, 2 * base - 2))
    bonus = base - (sides + 1) // 2
    return '1d%d%+d' % (sides, bonus)


def weapon_damage(d, base, critical=False):
    # 기존 시트의 wdmg에는 알파 스키마의 제한이 없다. 큰 사용자 수치도 파서 오류를 내지 않는다.
    base = max(1, int(base))
    sides = min(20, max(2, 2 * base - 2))
    bonus = base - (sides + 1) // 2
    rolls = [d.rng.randint(1, sides) for _ in range(2 if critical else 1)]
    return {'dice': weapon_dice(base), 'rolls': rolls, 'value': sum(rolls) + bonus, 'mode': 'dice'}

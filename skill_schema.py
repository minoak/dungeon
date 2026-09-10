# -*- coding: utf-8 -*-
"""수동 프리셋과 랜덤 생성기가 공유하는 스킬 구성 규칙. LLM은 이 수치를 만들지 않는다."""
import copy
import hashlib
import json
import math
import random
import re

import skill_combat as combat

VERSION = 'skills-alpha-v0.1'
COMMON = {'goto', 'follow', 'explore', 'search', 'attack', 'use', 'give', 'bond', 'wait', 'rest'}
COMPONENTS = {
    'damage': {'requires': ['living'], 'forbids': ['healing'], 'tags': ['hostile'], 'cost': 1},
    'heal': {'requires': ['living'], 'forbids': ['hostile'], 'tags': ['healing'], 'cost': 1.2},
    'push': {'requires': ['living', 'movable'], 'forbids': ['self', 'healing'], 'tags': ['hostile'], 'cost': 2},
    'bleed': {'requires': ['living'], 'forbids': ['healing'], 'tags': ['hostile'], 'cost': 2},
}
PENALTIES = ('hp_cost', 'cooldown', 'self_status', 'condition')


def effect_key(effect):
    return effect.get('status') if effect.get('type') == 'status' else effect.get('type')


def skill_cost(skill):
    """설계 예산이다. MP처럼 사용 시 소모하는 자원이 아니다. 환급은 총 효과값의 절반까지만."""
    base = 0
    for effect in skill['effects']:
        key = effect_key(effect)
        base += (combat.expected_damage(effect['dice']) * COMPONENTS[key]['cost']
                 if key in ('damage', 'heal') else COMPONENTS[key]['cost'])
    base *= 1 + max(0, skill['range'] - 1) * 0.25
    base *= {'attack': 1, 'save': 0.9, 'none': 1.2}[skill['roll']['type']]
    refund = 0
    for penalty in skill.get('penalties', []):
        kind = penalty['type']
        refund += (penalty['value'] * 0.5 if kind == 'hp_cost' else
                   penalty['turns'] * 0.5 if kind == 'cooldown' else 1)
    refund += len(skill.get('conditions', []))
    return max(1, math.ceil(base - min(base * 0.5, refund)))


def validate(skill):
    """저작/생성 경계에서 거른다. 잘못된 조합은 엔진에 들어가기 전에 이유를 돌려준다."""
    try:
        if not isinstance(skill, dict):
            return ['skill_not_object']
        sid = skill.get('id')
        if not isinstance(sid, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', sid) or sid in COMMON:
            return ['invalid_id']
        if not isinstance(skill.get('name'), str) or not 1 <= len(skill['name']) <= 40:
            return ['invalid_name']
        if type(skill.get('range')) is not int or not 0 <= skill['range'] <= 5:
            return ['invalid_range']
        if skill.get('target') not in ('living', 'self'):
            return ['invalid_target_mode']
        roll = skill['roll']
        if roll['type'] not in ('none', 'attack', 'save') or roll.get('ability') not in ('str', 'dex'):
            return ['invalid_roll']
        if roll['type'] == 'save' and roll.get('save_ability') not in ('str', 'dex'):
            return ['invalid_save']
        effects = skill['effects']
        if not isinstance(effects, list) or not 1 <= len(effects) <= 2:
            return ['invalid_effect_count']
        keys = [effect_key(e) for e in effects]
        if any(k not in COMPONENTS for k in keys) or len(set(keys)) != len(keys):
            return ['invalid_effects']
        tags = {'living', 'movable'} | ({'self'} if skill['target'] == 'self' else set())
        for key in keys:
            tags.update(COMPONENTS[key]['tags'])
        for key in keys:
            rule = COMPONENTS[key]
            if not set(rule['requires']) <= tags or set(rule['forbids']) & tags:
                return ['incompatible_effects']
        if (skill['range'] == 0) != (skill['target'] == 'self'):
            return ['invalid_self_range']
        if 'hostile' in tags and (roll['type'] == 'none' or skill['target'] == 'self'):
            return ['hostile_requires_roll']
        if 'healing' in tags and roll['type'] != 'none':
            return ['heal_requires_no_roll']
        for effect in effects:
            key = effect_key(effect)
            if key in ('damage', 'heal'):
                combat.dice_parts(effect['dice'])
            if key == 'push' and (type(effect.get('distance')) is not int or effect['distance'] != 1):
                return ['invalid_push']
            if key == 'bleed' and effect.get('type') != 'status':
                return ['invalid_status']
            if effect.get('save') not in (None, 'str', 'dex'):
                return ['invalid_effect_save']
        penalties = skill.get('penalties', [])
        if not isinstance(penalties, list) or len(penalties) > 4:
            return ['invalid_penalties']
        types = [p['type'] for p in penalties]
        if len(set(types)) != len(types) or any(t not in PENALTIES for t in types):
            return ['invalid_penalties']
        conditions = skill.get('conditions', [])
        if not isinstance(conditions, list) or len(conditions) > 1 or any(c != 'target_bleeding' for c in conditions):
            return ['invalid_conditions']
        for penalty in penalties:
            typ = penalty['type']
            if typ == 'hp_cost' and (type(penalty.get('value')) is not int or not 1 <= penalty['value'] <= 4):
                return ['invalid_hp_cost']
            if typ == 'cooldown' and (type(penalty.get('turns')) is not int or not 1 <= penalty['turns'] <= 4):
                return ['invalid_cooldown']
            if typ == 'self_status' and penalty.get('status') != 'slow':
                return ['invalid_self_status']
            if typ == 'condition':
                if penalty.get('condition') != 'target_bleeding' or conditions:
                    return ['invalid_condition_penalty']
        if 'heal' in keys and (conditions or 'condition' in types):
            return ['healing_condition_not_supported']
        if keys == ['bleed'] and (conditions or 'condition' in types):
            return ['bleed_only_requires_new_target']
        if 'cost' in skill and (type(skill['cost']) is not int or skill['cost'] != skill_cost(skill)):
            return ['cost_mismatch']
    except (KeyError, TypeError, ValueError, AttributeError):
        return ['malformed_skill']
    return []


def make(sid, name, effects, ability='str', range_=1, penalties=None, roll='attack'):
    skill = {'id': sid, 'name': name, 'tags': ['alpha'], 'target': 'living', 'range': range_,
             'roll': {'type': roll, 'ability': ability}, 'effects': effects,
             'conditions': [], 'penalties': penalties or []}
    skill['cost'] = skill_cost(skill)
    errors = validate(skill)
    if errors:
        raise ValueError(errors)
    return skill


PRESETS = {s['id']: s for s in [
    make('push_slash', '밀어베기', [{'type': 'damage', 'dice': '1d6'},
                                   {'type': 'push', 'distance': 1, 'save': 'str'}],
         penalties=[{'type': 'cooldown', 'turns': 2}]),
    make('heavy_strike', '강타', [{'type': 'damage', 'dice': '2d6'}],
         penalties=[{'type': 'hp_cost', 'value': 2}, {'type': 'cooldown', 'turns': 2}]),
    make('first_aid', '응급처치', [{'type': 'heal', 'dice': '1d6'}], roll='none',
         penalties=[{'type': 'cooldown', 'turns': 2}]),
    make('bleeding_cut', '출혈베기', [{'type': 'damage', 'dice': '1d4'},
                                    {'type': 'status', 'status': 'bleed', 'save': 'dex'}], ability='dex',
         penalties=[{'type': 'cooldown', 'turns': 2}]),
]}
DEFAULT_SETS = (('push_slash', 'heavy_strike'), ('bleeding_cut', 'first_aid'), ('first_aid', 'push_slash'))


def generate(seed, budget=5, allowed_effects=None, allowed_penalties=None):
    """동일한 시드·예산·구성요소 풀은 항상 같은 스킬. 무한 재시도 대신 후보 128개 상한."""
    if type(budget) is not int or not 1 <= budget <= 30:
        raise ValueError('budget은 1~30 정수')
    effects = sorted(set(COMPONENTS if allowed_effects is None else allowed_effects))
    penalties = sorted(set(PENALTIES if allowed_penalties is None else allowed_penalties))
    if not effects or any(e not in COMPONENTS for e in effects) or any(p not in PENALTIES for p in penalties):
        raise ValueError('알 수 없거나 빈 구성요소 풀')
    material = json.dumps([VERSION, seed, budget, effects, penalties], ensure_ascii=False, sort_keys=True)
    rng = random.Random(hashlib.sha256(material.encode('utf-8')).hexdigest())
    for attempt in range(128):
        primary = rng.choice(effects)
        chosen = [primary]
        secondary = [e for e in effects if e != primary and e != 'heal']
        if primary != 'heal' and secondary and rng.random() < 0.5:
            chosen.append(rng.choice(secondary))
        parts = []
        for kind in chosen:
            if kind in ('damage', 'heal'):
                parts.append({'type': kind, 'dice': rng.choice(['1d4', '1d6', '1d8'])})
            elif kind == 'push':
                parts.append({'type': 'push', 'distance': 1, 'save': 'str'})
            else:
                parts.append({'type': 'status', 'status': 'bleed', 'save': 'dex'})
        skill = make('candidate', '생성 후보', parts, ability=rng.choice(['str', 'dex']),
                     range_=rng.choice([1, 1, 2, 3]), roll='none' if primary == 'heal' else 'attack')
        if primary != 'heal' and 'damage' not in chosen and rng.random() < 0.5:
            skill['roll'].update(type='save', save_ability=rng.choice(['str', 'dex']))
            for part in parts:
                part.pop('save', None)  # 주 내성에 더해 같은 효과의 내성을 중복 요구하지 않는다.
        pool = list(penalties)
        rng.shuffle(pool)
        while skill_cost(skill) > budget and pool:
            p = pool.pop()
            if p == 'condition' and primary == 'heal':
                continue
            skill['penalties'].append({'type': p, **(
                {'turns': rng.choice([2, 3, 4])} if p == 'cooldown' else
                {'value': rng.choice([1, 2, 3])} if p == 'hp_cost' else
                {'status': 'slow'} if p == 'self_status' else {'condition': 'target_bleeding'})})
        skill['cost'] = skill_cost(skill)
        if skill['cost'] > budget or validate(skill):
            continue
        fingerprint = hashlib.sha256((material + json.dumps(skill, sort_keys=True)).encode('utf-8')).hexdigest()[:12]
        skill['id'] = 'random_' + fingerprint
        skill['name'] = ' · '.join({'damage': '상처', 'heal': '회복', 'push': '밀침', 'bleed': '출혈'}[k] for k in chosen)
        skill['generated'] = {'seed': seed, 'budget': budget, 'effects': effects, 'penalties': penalties, 'version': VERSION}
        return copy.deepcopy(skill)
    raise ValueError('이 예산과 구성요소 풀에서 유효한 스킬을 생성하지 못함')

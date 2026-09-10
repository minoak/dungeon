# -*- coding: utf-8 -*-
"""기존 조합형 행동에 붙는 알파 스킬. 거리·접근·피격·목격은 기존 엔진을 경유한다."""
import copy

import skill_combat as combat
import skill_schema as schema


def spawn_fields(d, sheet, char):
    if not d.skills:
        return {}
    skills = sheet.get('skills', schema.DEFAULT_SETS[(int(char) - 1) % len(schema.DEFAULT_SETS)])
    return {'skills': list(skills), 'skill_cooldowns': {}, 'generated_skills': {}, 'skill_acquisitions': []}


def lookup(d, bot, sid):
    if not d.skills or not d.composed_actions or sid not in bot.get('skills', []):
        return None
    skill = schema.PRESETS.get(sid) or bot.get('generated_skills', {}).get(sid)
    return skill if skill and not schema.validate(skill) else None


def inherit(d, previous, current):
    if d.skills:
        for key in ('skills', 'skill_cooldowns', 'generated_skills', 'skill_acquisitions'):
            current[key] = copy.deepcopy(previous.get(key, current.get(key)))


def acquire(d, bots):
    """3층 첫 입장에 인당 하나. 캐릭터별 파생 시드라 배치·전투 RNG를 소모하지 않는다."""
    acquired = []
    if not d.skills or not d.random_skill or d.depth != 3:
        return acquired
    for bot in bots:
        if not bot['alive'] or bot.get('skill_acquisitions'):
            continue
        skill = schema.generate('%s:%s:floor3' % (d.master_seed, bot['char']), budget=5)
        bot.setdefault('generated_skills', {})[skill['id']] = skill
        bot.setdefault('skills', []).append(skill['id'])
        record = {'char': bot['char'], 'depth': d.depth, 'turn': d.turn,
                  'generated_skill_id': skill['id'], 'skill': copy.deepcopy(skill)}
        bot.setdefault('skill_acquisitions', []).append(record)
        acquired.append(record)
    return acquired


def snapshot(bot):
    if 'skills' not in bot:
        return {}
    return {key: copy.deepcopy(bot.get(key, {} if key != 'skills' else []))
            for key in ('skills', 'skill_cooldowns', 'generated_skills')}


def description(skill, trpg):
    parts = []
    for effect in skill['effects']:
        key = schema.effect_key(effect)
        if key in ('damage', 'heal'):
            amount = effect['dice'] if trpg else str(int(combat.expected_damage(effect['dice']) + 0.5))
            parts.append('%s %s' % ('피해' if key == 'damage' else '회복', amount))
        else:
            parts.append('1칸 밀침' if key == 'push' else '출혈(걸을 때 HP 감소)')
        if effect.get('save') and trpg:
            parts[-1] += '·대상 %s 내성' % effect['save'].upper()
    parts.append('자신' if skill['target'] == 'self' else '사거리 %d·사선 필요' % skill['range'])
    if skill['roll']['type'] != 'none':
        parts.append('%s %s' % (skill['roll']['ability'].upper(),
                     '명중 판정' if skill['roll']['type'] == 'attack' or not trpg else '대상 내성 판정'))
    for p in skill['penalties']:
        parts.append('재사용 %d행동' % p['turns'] if p['type'] == 'cooldown' else
                     'HP %d 지불(생존 필요)' % p['value'] if p['type'] == 'hp_cost' else
                     '자신 둔화(휴식으로 해제)' if p['type'] == 'self_status' else '출혈 대상만')
    if skill.get('conditions'):
        parts.append('출혈 대상만')
    return ', '.join(parts)


def observe(d, bot, obs):
    if not d.skills:
        return obs
    obs['skills'] = [{'id': sid, 'name': skill['name'], 'range': skill['range'],
                      'description': description(skill, d.trpg_combat),
                      'cooldown': bot.get('skill_cooldowns', {}).get(sid, 0)}
                     for sid in bot.get('skills', []) if (skill := lookup(d, bot, sid))]
    return obs


def required_range(d, bot, action):
    skill = lookup(d, bot, action.get('type'))
    return skill['range'] if skill else (int(bot.get('atk_range') or 1) if action['type'] == 'attack' else 1)


def in_range(d, bot, skill, target, at=None):
    x, y = at if at is not None else (bot['x'], bot['y'])
    tx, ty = target[1]
    if skill['target'] == 'self':
        return target[0] == 'bot' and target[2] is bot
    distance = abs(x - tx) + abs(y - ty)
    return distance <= skill['range'] and (distance <= 1 or not d._sight_blocked(x, y, tx, ty))


def target_status(target):
    return (target[2].get('status', {}) if target[0] == 'bot' else getattr(target[2], 'skill_status', {}))


def preflight(d, bot, skill, target):
    if not skill:
        return 'invalid_skill'
    if bot.get('skill_cooldowns', {}).get(skill['id'], 0) > 0:
        return 'cooldown'
    if not target:
        return 'lost'
    if target[0] not in ('bot', 'monster'):
        return 'not_living'
    if skill['target'] == 'self' and target[2] is not bot:
        return 'self_only'
    if target[2] is bot and any(schema.effect_key(e) != 'heal' for e in skill['effects']):
        return 'hostile_self'
    conditions = list(skill.get('conditions', []))
    for p in skill['penalties']:
        if p['type'] == 'hp_cost' and bot['hp'] <= p['value']:
            return 'insufficient_hp'
        if p['type'] == 'condition':
            conditions.append(p['condition'])
    if 'target_bleeding' in conditions and '출혈' not in target_status(target):
        return 'target_not_bleeding'
    return None


def failure(bot, action, why):
    return {'char': bot['char'], 'type': action['type'], 'target': action.get('target'),
            'skill_id': action['type'], 'result': 'skill_failed', 'reason_code': why}


def ability(target, name):
    # 몬스터에 6능력치를 도입하지 않는다. 기존 atk/AC에서 알파용 STR/DEX 보정만 유도한다.
    if target[0] == 'bot':
        return target[2][name]
    return target[2].atk if name == 'str' else max(0, target[2].ac - 10)


def saving_throw(d, bot, skill, target, name):
    dc = 10 + bot[skill['roll']['ability']]
    record = combat.check(d, ability(target, name), dc,
                          disadvantage='중독' in target_status(target))
    return {**record, 'ability': name, 'kind': 'save'}


def push(d, bot, target, bots):
    kind, (x, y), obj = target
    dx, dy = x - bot['x'], y - bot['y']
    # 동률은 X축으로 고정. 경로 찾기와 좌표계를 새로 만들지 않는다.
    step = ((1 if dx > 0 else -1, 0) if abs(dx) >= abs(dy) else (0, 1 if dy > 0 else -1))
    nx, ny = x + step[0], y + step[1]
    free = d.walkable(nx, ny, bots) if kind == 'bot' else d._monster_walkable(nx, ny, bots)
    if not free:
        return {'type': 'push', 'applied': False, 'reason': 'blocked'}
    extra = {}
    if kind == 'bot':
        extra.update(d._cancel_approach(obj))
        obj['order'], obj['path'], obj['plan'] = None, [], []
        extra['entered'] = d._enter_cell(obj, nx, ny, bots)
        d._note_last(obj, {'type': 'pushed', 'by': bot['char'], 'to': [nx, ny], **extra})
    else:
        obj.x, obj.y = nx, ny
        door = d._mon_door(obj, bots)
        if door:
            extra['door'] = door
    return {'type': 'push', 'applied': True, 'from': [x, y], 'to': [nx, ny], **extra}


def execute(d, bot, action, bots):
    import composed_actions as CA
    skill = lookup(d, bot, action['type'])
    target = CA.entity(d, bot, action.get('target'), bots)
    why = preflight(d, bot, skill, target)
    if why:
        return failure(bot, action, why)
    if not in_range(d, bot, skill, target):
        return failure(bot, action, 'too_far')
    kind, xy, obj = target
    res = {'char': bot['char'], 'type': skill['id'], 'target': action.get('target'),
           'skill_id': skill['id'], 'skill_name': skill['name'], 'skill_cost': skill['cost'],
           'result': 'skill', 'effects': [], 'penalties': [], 'skill_spent': True,
           'cooldown_before': bot.get('skill_cooldowns', {}).get(skill['id'], 0)}
    surprise = kind == 'monster' and (obj.state in ('SLEEPING', 'WANDERING') or obj.waking > 0)
    hostile = any(schema.effect_key(e) != 'heal' for e in skill['effects'])
    hit, critical = True, False
    if skill['roll']['type'] == 'save' and d.trpg_combat:
        res['skill_roll'] = saving_throw(d, bot, skill, target, skill['roll']['save_ability'])
        res['skill_dc'] = res['skill_roll']['dc']
        hit = not res['skill_roll']['success']
    elif skill['roll']['type'] != 'none':
        import dungeon_gm as G
        ac = obj.ac if kind == 'monster' else 10 + obj['dex'] + G.gear_bonus(obj, 'armor')
        if kind == 'bot' and d.status and '중독' in obj.get('status', {}):
            ac -= G.POISON_MOD
        mod = bot[skill['roll']['ability']]
        if not d.trpg_combat:
            mod -= G.POISON_MOD if (d.status or d.skills) and '중독' in bot.get('status', {}) else 0
        record = combat.check(d, mod, ac, advantage=surprise,
                              disadvantage=d.trpg_combat and '중독' in bot.get('status', {}), attack=d.trpg_combat)
        if not d.trpg_combat and record['roll'] == 20:
            record.update(success=True, critical=True)
        res['skill_roll'] = {**record, 'kind': 'attack', 'ac': ac, 'ability': skill['roll']['ability']}
        hit, critical = record['success'], record['critical']
    res['hit'] = hit
    for effect in skill['effects'] if hit else []:
        alive = obj['alive'] if kind == 'bot' else obj.alive
        if not alive:
            break
        er = {'type': schema.effect_key(effect)}
        if d.trpg_combat and effect.get('save'):
            er['save'] = saving_throw(d, bot, skill, target, effect['save'])
            res['skill_dc'] = er['save']['dc']
            if er['save']['success']:
                res['effects'].append({**er, 'applied': False, 'reason': 'saved'})
                continue
        typ = er['type']
        if typ in ('damage', 'heal'):
            roll = combat.damage(d, effect['dice'], critical and typ == 'damage', rolled=d.trpg_combat)
            er.update(roll, applied=roll['value'] > 0)
            if typ == 'damage':
                if kind == 'monster':
                    er.update(d._damage_monster(bot, obj, roll['value'], bots, critical))
                else:
                    er.update(CA.damage_actor(d, bot, obj, roll['value'], bots))
                res['dmg'] = res.get('dmg', 0) + roll['value']
            else:
                hp, maxhp = (obj['hp'], obj['maxhp']) if kind == 'bot' else (obj.hp, obj.maxhp)
                heal = max(0, min(maxhp - hp, roll['value']))
                if kind == 'bot':
                    obj['hp'] += heal
                    if obj is not bot:
                        d._receive(obj, {'type': 'healed', 'char': obj['char'], 'from': bot['char'],
                                         'heal': heal, 'hp': obj['hp'], 'skill_id': skill['id']}, bots)
                    if heal:
                        d._witness(bots, *xy, {'kind': 'ally_heal', 'char': obj['char'], 'how': skill['name']},
                                   exclude=(bot['char'], obj['char']))
                else:
                    obj.hp += heal
                er.update(heal=heal, hp=hp + heal, applied=heal > 0)
                res['heal'] = heal
        elif typ == 'push':
            er.update(push(d, bot, target, bots))
        elif typ == 'bleed':
            if kind == 'bot':
                applied = bool(d._apply_status(obj, '출혈', skill['name'], bots, by_kind='skill', force=True))
            else:
                obj.skill_status = getattr(obj, 'skill_status', {})
                applied = '출혈' not in obj.skill_status
                obj.skill_status['출혈'] = {'by': bot['char'], 'since': d.turn}
            er.update(applied=applied, status='출혈')
        res['effects'].append(er)
    if hostile and kind == 'monster':
        d._wake_attacked_monster(bot, obj, surprise)
    for penalty in skill['penalties']:
        p = dict(penalty)
        if p['type'] == 'hp_cost':
            bot['hp'] -= p['value']
            p['hp'] = bot['hp']
        elif p['type'] == 'cooldown':
            bot.setdefault('skill_cooldowns', {})[skill['id']] = p['turns']
        elif p['type'] == 'self_status':
            d._apply_status(bot, '둔화', skill['name'], bots, by_kind='skill', force=True)
        res['penalties'].append(p)
    res['cooldown_after'] = bot.get('skill_cooldowns', {}).get(skill['id'], 0)
    if not hit:
        res['result'] = 'skill_missed'
    elif not any(e.get('applied') for e in res['effects']):
        res['result'] = 'no_effect'
    return res


def complete(d, bot, action, result):
    """접근의 걸음은 세지 않는다. 실제 실행·완료된 다른 행동마다 대기시간을 1 낮춘다."""
    if not d.skills or result.get('resolution', {}).get('phase') != 'resolved':
        return
    valid = (result.get('skill_spent') or result.get('resolution', {}).get('status') == 'success'
             or result.get('result') == 'attack'
             or (action.get('type') == 'search' and result.get('found') is not None))
    if not valid or bot.get('_skill_completed_action') == action.get('action_id'):
        return
    bot['_skill_completed_action'] = action.get('action_id')
    before = dict(bot.get('skill_cooldowns', {}))
    for sid, turns in before.items():
        if sid != result.get('skill_id'):
            bot['skill_cooldowns'][sid] = max(0, turns - 1)
    if before:
        result.update(skill_cooldowns_before=before, skill_cooldowns_after=dict(bot['skill_cooldowns']))


def monster_status_after_move(d, bot_list, starts):
    import dungeon_gm as G
    events = []
    for mon in d.monsters:
        if not mon.alive or '출혈' not in getattr(mon, 'skill_status', {}) or starts.get(mon.id) == (mon.x, mon.y):
            continue
        mon.skill_bleed_steps = getattr(mon, 'skill_bleed_steps', 0) + 1
        if mon.skill_bleed_steps % G.BLEED_STEPS:
            continue
        source = mon.skill_status['출혈']['by']
        actor = next((b for b in bot_list if b['char'] == source), {'char': source})
        result = d._damage_monster(actor, mon, 1, bot_list, False)
        events.append({'type': 'monster_status', 'id': 'm%d' % mon.id, 'monster': mon.kind,
                       'status': '출혈', 'source_char': source, **result})
    return events


def stream_records(results):
    out = []
    for result in results:
        if not result.get('skill_id'):
            continue
        base = {k: result.get(k) for k in ('char', 'skill_id', 'parent_action_id')}
        if result.get('skill_roll'):
            out.append({**base, 'type': 'skill_roll', 'roll': copy.deepcopy(result['skill_roll'])})
        for effect in result.get('effects', []):
            out.append({**base, 'type': 'skill_effect', 'effect': copy.deepcopy(effect)})
        out.append({**base, **copy.deepcopy(result.get('resolution', {})),
                    'action_type': result.get('type'), 'type': 'resolution'})
    return out


def summary(result):
    if result.get('type') == 'healed':
        name = schema.PRESETS.get(result.get('skill_id'), {}).get('name', result.get('skill_id', '스킬'))
        return '%s로 HP %d 회복 (HP %d)' % (name, result.get('heal', 0), result.get('hp', 0))
    if result.get('result') == 'skill_failed':
        why = {'cooldown': '재사용 대기 중', 'invalid_skill': '보유하지 않은 스킬',
               'insufficient_hp': '지불할 HP 부족', 'target_not_bleeding': '대상에게 출혈 없음',
               'lost': '대상 소실', 'not_living': '살아있는 대상이 아님', 'too_far': '범위 밖',
               'self_only': '자신에게만 가능', 'hostile_self': '자해 스킬이 아님'}.get(result['reason_code'], result['reason_code'])
        return '%s 실패 — %s' % (result['skill_id'], why)
    bits = []
    for effect in result.get('effects', []):
        if not effect.get('applied'):
            bits.append('%s 변화 없음(%s)' % (effect['type'], effect.get('reason', 'no_change')))
        elif effect['type'] == 'damage':
            bits.append('%d 피해%s' % (effect['value'], '·처치' if effect.get('killed') else ''))
        elif effect['type'] == 'heal':
            bits.append('HP %d 회복' % effect['heal'])
        else:
            bits.append('1칸 밀침' if effect['type'] == 'push' else '출혈')
    if not result.get('hit', True):
        bits.append('빗나감/저항')
    return '%s → %s: %s (재사용 %d행동)' % (result.get('skill_name', result['skill_id']),
             result.get('target', '?'), ', '.join(bits), result.get('cooldown_after', 0))

# -*- coding: utf-8 -*-
"""조합형 행동의 관측·입력·효과 계약. 기존 엔진의 시야와 물리 함수를 재사용한다.

대상 태그는 효과를 정하는 사실이다. 행동별 허용 대상 목록으로 사용하지 않는다.
좌표/실물 참조는 봇 내부에만 보관하고 모델에는 기존 방위·거리 표현을 보낸다.
"""
import copy
import skill_core as SK
import skill_combat as SC

SCHEMA = 'compose-v0.4'    # 관측 계약(obs.action_schema) — ID 문법·대상 목록은 v0.4 그대로(verify_skill_off 의 78fbe84 기준선 해시에 포함)
PROFILE = 'compose-v0.5'   # 행동 계약(run_meta.compose_profile) — D48(2026-09-11): COMMON 에서 follow 제거
# D48 follow 폐지(파트너 결정 09-11) — 동행은 `goto b<char>`(보이는 동료에게 한 번 걷고, 곁에 닿으면 다시 판단)로만.
# 엔진의 follow order(D18 A-5)는 메뉴형(비교용 옛 규칙)·구판 리플레이용으로 남는다 — 조합형 파서만 모르는 동사가 된다.
COMMON = ('goto', 'explore', 'search', 'attack', 'use', 'give', 'bond', 'wait', 'rest')
DISTANCE_ACTIONS = ('search', 'attack', 'use', 'give', 'bond')
ITEM_SLOTS = {'i1': 'potion', 'i2': 'weapon', 'i3': 'armor'}


def item_value(bot, slot):
    return bot.get('potions', 0) if slot == 'potion' else bot.get(slot)


def observe(d, bot, bots, obs):
    """현재 관측에 ID를 붙인다. way는 관측마다 새 이름을 주어 오래된 계획의 오지정을 막는다."""
    actor = 'b' + bot['char']
    refs = {actor: {'kind': 'bot', 'char': bot['char']}}
    targets = [{'id': 'self', 'kind': 'self', 'name': '나', 'tags': ['agent', 'living', 'damageable', 'inventory_holder']}]
    sights = obs['sights']
    for label, kind in (('bots', 'bot'), ('monsters', 'monster'), ('features', 'feature')):
        for obj in sights.get(label, []):
            rid = obj['id']
            refs[rid] = {'kind': kind, 'key': rid, **({'char': rid[1:]} if kind == 'bot' else {})}
            tags = (['agent', 'living', 'damageable', 'movable'] if kind in ('bot', 'monster') else ['object'])
            if kind == 'bot':
                tags += ['inventory_holder']
            if obj.get('type') in ('weapon', 'armor', 'potion'):
                tags += ['item']
            targets.append({'id': rid, 'kind': kind, 'tags': tags,
                            **{k: obj[k] for k in ('name', 'dist', 'bearing') if k in obj}})
    if sights.get('exit'):
        refs['exit'] = {'kind': 'exit', 'key': 'exit'}
        targets.append({'id': 'exit', 'kind': 'exit', 'name': '계단', 'tags': ['object', 'interactable']})
    seen = d.visible_cells(bot['x'], bot['y'])
    for rid, door in sorted(d.doors.items()):
        visible = door.cell in seen if door.cell else any(p in seen for p in door.sides.values())
        if visible:
            refs[rid] = {'kind': 'door', 'key': rid}
            targets.append({'id': rid, 'kind': 'door', 'name': '문', 'tags': ['object', 'passage']})
    for index, trap in enumerate(d.traps):
        if not trap.hidden and not trap.sprung and (trap.x, trap.y) in seen:
            rid = 't%d' % index
            refs[rid] = {'kind': 'trap', 'index': index}
            targets.append({'id': rid, 'kind': 'trap', 'name': trap.name, 'tags': ['object', 'hazard'],
                            'bearing': d._bearing(trap.x - bot['x'], trap.y - bot['y']),
                            'dist': max(abs(trap.x - bot['x']), abs(trap.y - bot['y']))})
    items = []
    for rid, slot in ITEM_SLOTS.items():
        value = item_value(bot, slot)
        if not value:
            continue
        refs[rid] = {'kind': 'item', 'slot': slot, 'value': copy.deepcopy(value)}
        entry = {'id': rid, 'kind': 'item', 'slot': slot,
                 'name': '회복 물약' if slot == 'potion' else value['name'],
                 'tags': ['item', 'consumable', 'healing'] if slot == 'potion' else ['item', 'equipment']}
        if slot == 'potion':
            entry['count'] = value
        else:
            entry['bonus'] = value.get('bonus', 0)
        items.append(entry)
        targets.append(dict(entry))
    epoch = bot.get('_way_epoch', 0) + 1
    bot['_way_epoch'] = epoch
    candidates = []
    # 기존 탐색의 명사 종점·방위별 길·기억 귀환을 모두 같은 경로 생성기로 해석한다.
    plans = [d._explore_plan(bot, None, bots)]
    plans += [d._explore_plan(bot, w['bearing'], bots) for w in sights.get('ways', [])]
    endpoints = set()
    for plan in plans:
        if not plan or not plan[1]:
            continue
        order, path, result = plan
        end = tuple(path[-1])
        # scan 없는 구판의 전지적 출구 폴백은 새 관측의 way로 승격하지 않는다.
        if result.get('to_exit') and not (d._remembers_exit(bot) or d.exit in seen):
            continue
        if end in endpoints:
            continue
        endpoints.add(end)
        rid = 'w%d_%d' % (epoch, len(candidates) + 1)
        bearing = result.get('bearing') or d._bearing(end[0] - bot['x'], end[1] - bot['y'])
        name = ('기억의 계단' if result.get('remembered') else '문 너머' if result.get('door')
                else '기억의 미탐색 경계' if result.get('frontier') else '탐색할 길')
        refs[rid] = {'kind': 'way', 'xy': end, 'order': order, 'epoch': epoch, 'origin': (bot['x'], bot['y']),
                     'depth': d.depth, 'result': {k: v for k, v in result.items() if k not in ('char', 'type', 'target', 'len', 'result')}}
        entry = {'id': rid, 'kind': 'way', 'name': name, 'bearing': bearing,
                 'dist': max(abs(end[0] - bot['x']), abs(end[1] - bot['y'])), 'tags': ['way']}
        candidates.append(entry)
        targets.append(dict(entry))
    bot['_target_refs'] = refs
    obs.update(action_schema=SCHEMA, actor=actor, targets=targets, items=items, ways=candidates)
    return SK.observe(d, bot, obs)


def normalize(bot, action):
    """규칙 두뇌와 구형 호출자의 별칭을 정규 행동으로 바꾼다. 모델 입력은 parse가 먼저 검사한다."""
    if action.get('type') == 'interact':
        action['type'] = 'use'
    elif action.get('type') == 'drink':
        action.update(type='use', target='self', item='i1')
    if action.get('type') == 'search' and not action.get('target'):
        action['target'] = 'self'
    if action.get('target') == 'self':
        action['target'] = 'b' + bot['char']
    if action.get('item') in ITEM_SLOTS.values():
        action['item'] = next(k for k, v in ITEM_SLOTS.items() if v == action['item'])


def fallback(action, obs):
    """기존 결정론적 규칙 두뇌의 선택을 현재 관측 계약으로 옮긴다."""
    out = dict(action)
    normalize({'char': obs['actor'][1:]}, out)
    if out['type'] == 'explore':
        ways = obs.get('ways', [])
        if ways:
            out['target'] = ways[0]['id']
        else:
            out = {'type': 'search', 'target': obs['actor']}
    return out


def plan_step(d, bot, step, bots):
    """저작 때의 참조가 여전히 유효하면 실행하고, 소실되면 같은 틱에 재판단한다."""
    normalize(bot, step)
    typ, rid = step['type'], step.get('target')
    remembered = typ == 'goto' and rid in (bot.get('ledger') or {}).get('statics', {})
    refs = bot.get('_plan_refs', bot.get('_target_refs', {}))
    valid = typ in ('wait', 'rest') or remembered or entity(d, bot, rid, bots, refs)
    if step.get('item'):
        valid = valid and entity(d, bot, step['item'], bots, refs)
    if valid:
        return step
    bot['plan'] = []
    d._note_last(bot, {'char': bot['char'], 'type': 'plan_broken', 'step': dict(step),
                       'why': '대상 또는 소지품 참조가 더는 유효하지 않음'})
    return None


def parse(obj, obs):
    """스키마와 참조만 검사한다. 알려진 대상에 대한 어색한 행동 조합은 그대로 통과한다."""
    typ = str(obj.get('type') or '').strip().lower()
    target = str(obj.get('target') or '').strip()
    item = str(obj.get('item') or '').strip()
    if typ == 'interact':
        typ = 'use'
    elif typ == 'drink':
        typ, target, item = 'use', 'self', 'i1'
    if typ not in COMMON and typ not in {s['id'] for s in obs.get('skills', [])}:
        return None, 'invalid_type'
    out = {'type': typ}
    if not target and typ == 'search':             # 주변 조사라는 기존 문법의 호환 별칭
        target = 'self'
    if typ not in ('wait', 'rest') and not target:
        return None, 'missing_target'
    ids = {t['id'] for t in obs.get('targets', [])} | {obs.get('actor'), 'self'}
    if typ == 'goto':
        ids |= {e['id'] for e in obs.get('known', {}).get('statics', []) if e.get('id')}
    if target:
        if target not in ids:
            return None, 'invalid_target'
        out['target'] = obs['actor'] if target == 'self' else target
    if item:
        item = next((k for k, v in ITEM_SLOTS.items() if v == item), item)
        if typ not in ('give', 'use'):
            return None, 'unexpected_item'
        if item not in {e['id'] for e in obs.get('items', [])}:
            return None, 'invalid_item'
        out['item'] = item
    elif typ == 'give':
        return None, 'missing_item'
    if typ == 'bond':
        out['form'] = ' '.join(str(obj.get('form') or '').replace('"', '').replace("'", '').split())[:120]
    return out, None


def error_detail(obj, obs, error):
    """실패를 다시 분석할 수 있도록 원래 요청과 참조 가능한 ID를 보존한다."""
    target = str(obj.get('target') or '')
    ids = sorted({e['id'] for e in obs.get('targets', [])} | {obs.get('actor', 'self')})
    known = sorted(e['id'] for e in obs.get('known', {}).get('statics', []) if e.get('id'))
    subtype = ('missing_target' if not target else 'way_not_current' if target.startswith('w')
               else 'memory_only' if target in known and target not in ids else 'not_observed')
    return {'code': error, 'target_detail': subtype if error in ('invalid_target', 'missing_target') else None,
            'attempted_action': copy.deepcopy(obj), 'target_ids': ids, 'known_goto_ids': known,
            'item_ids': [e['id'] for e in obs.get('items', [])]}


def entity(d, bot, target, bots, refs=None):
    """참조를 실물로 해소하며 소실·시야·장비 교체를 다시 확인한다."""
    if target == 'self':
        target = 'b' + bot['char']
    ref = (refs if refs is not None else bot.get('_execution_refs', bot.get('_target_refs', {}))).get(target)
    if not ref:
        return None
    kind = ref['kind']
    seen = d.visible_cells(bot['x'], bot['y'])
    if kind == 'bot':
        obj = next((b for b in bots if b['char'] == ref['char'] and b['alive'] and not b['won']), None)
        if not obj or (obj is not bot and not d._ally_seen(bot, obj, seen)):
            return None
        return kind, (obj['x'], obj['y']), obj
    if kind == 'monster':
        obj = next((m for m in d.monsters if 'm%d' % m.id == target and m.alive and not m.concealed), None)
        return (kind, (obj.x, obj.y), obj) if obj and (obj.x, obj.y) in seen else None
    if kind in ('feature', 'exit'):
        obj = d.features.get(d._exit_fid) if kind == 'exit' else d._feature_by_target(target)
        return (kind, (obj.x, obj.y), obj) if obj and not obj.concealed and (obj.x, obj.y) in seen else None
    if kind == 'door':
        door = d.doors.get(target)
        if not door:
            return None
        points = [door.cell] if door.cell else list(door.sides.values())
        points = [p for p in points if p in seen]
        return (kind, min(points, key=lambda p: (max(abs(p[0]-bot['x']), abs(p[1]-bot['y'])), p)), door) if points else None
    if kind == 'trap':
        obj = d.traps[ref['index']]
        return (kind, (obj.x, obj.y), obj) if not obj.hidden and not obj.sprung and (obj.x, obj.y) in seen else None
    if kind == 'item':
        value = item_value(bot, ref['slot'])
        if not value or (ref['slot'] != 'potion' and value != ref['value']):
            return None
        return kind, (bot['x'], bot['y']), ref
    if kind == 'way' and ref['depth'] == d.depth and ((ref['epoch'] == bot.get('_way_epoch') and tuple(ref['origin']) == (bot['x'], bot['y']))
            or (bot.get('approach') or {}).get('target') == target):
        return kind, tuple(ref['xy']), ref
    return None


def in_range(d, bot, action, target, at=None):
    skill = SK.lookup(d, bot, action['type'])
    if skill:
        return SK.in_range(d, bot, skill, target, at)
    x, y = at if at is not None else (bot['x'], bot['y'])
    tx, ty = target[1]
    if target[0] == 'item' or (target[0] == 'bot' and target[2] is bot):
        return True
    distance = abs(x - tx) + abs(y - ty)
    if action['type'] == 'attack':
        return 1 <= distance <= int(bot.get('atk_range') or 1) and (distance == 1 or not d._sight_blocked(x, y, tx, ty))
    if action['type'] in ('give', 'bond') and target[0] in ('bot', 'monster'):
        return max(abs(x - tx), abs(y - ty)) <= 1
    return distance <= 1


def _base(bot, action, result, **extra):
    return {'char': bot['char'], **{k: action[k] for k in ('type', 'target', 'item', 'form') if k in action},
            'result': result, **extra}


def execute(d, bot, action, bots):
    """효과를 판정한다. 거리는 Dungeon의 공통 진입점에서 처리한다."""
    typ, rid = action['type'], action.get('target')
    target = entity(d, bot, rid, bots) if rid else None
    if typ in ('wait', 'rest'):
        return d._execute_legacy_action(bot, action, bots)
    if not target:
        if typ == 'goto' and rid in (bot.get('ledger') or {}).get('statics', {}):
            return d._execute_legacy_action(bot, action, bots)
        return _base(bot, action, 'lost')
    kind, xy, obj = target
    if typ in DISTANCE_ACTIONS and not in_range(d, bot, action, target):
        return _base(bot, action, 'too_far')
    if typ in ('goto', 'explore'):
        if typ == 'explore' and kind != 'way':
            return _base(bot, action, 'no_effect', reason_code='not_a_way')
        if kind in ('way', 'trap', 'item') or (kind == 'bot' and obj is bot):
            path = d.path_to(bot['x'], bot['y'], *xy, bots)
            if not path:
                return _base(bot, action, 'arrived' if xy == (bot['x'], bot['y']) else 'no_path')
            bot['order'], bot['path'] = '@%d,%d' % xy, path
            return _base(bot, action, 'pathed', len=len(path), **(obj['result'] if kind == 'way' else {}))
        return d._execute_legacy_action(bot, action, bots)
    if typ == 'search':
        if kind == 'bot' and obj is bot:
            return {**d._search(bot, bots), 'target': rid}
        return _base(bot, action, 'no_effect', reason_code='no_new_information', found=[])
    if typ == 'attack':
        if kind == 'monster':
            return d._attack(bot, rid, bots)
        if kind == 'bot':
            return attack_actor(d, bot, obj, bots)
        return _base(bot, action, 'no_effect', reason_code='not_damageable')
    if typ == 'give':
        item = entity(d, bot, action.get('item'), bots)
        if not item or item[0] != 'item':
            return _base(bot, action, 'nothing', reason_code='item_not_owned')
        if kind == 'bot' and obj is not bot:
            return d._give(bot, rid, item[2]['slot'], bots)
        return _base(bot, action, 'no_effect', reason_code='no_inventory_transfer')
    if typ == 'bond':
        if kind == 'bot' and obj is not bot:
            return d._bond(bot, rid, action.get('form'), bots)
        return _base(bot, action, 'no_effect', reason_code='gesture_recorded')
    if typ == 'use':
        item_id = action.get('item') or (rid if kind == 'item' else None)
        item = entity(d, bot, item_id, bots) if item_id else None
        if item_id:
            if not item or item[0] != 'item':
                return _base(bot, action, 'nothing', reason_code='item_not_owned')
            if item[2]['slot'] != 'potion' or kind not in ('bot', 'monster', 'item') or (kind == 'item' and obj['slot'] != 'potion'):
                return _base(bot, action, 'no_effect', reason_code='no_item_effect')
            recipient = bot if kind == 'item' else obj
            if kind == 'monster':
                heal = max(0, recipient.maxhp - recipient.hp)
                recipient.hp = recipient.maxhp
            else:
                heal = max(0, recipient['maxhp'] - recipient['hp'])
                recipient['hp'] = recipient['maxhp']
            bot['potions'] -= 1
            hp = recipient.hp if kind == 'monster' else recipient['hp']
            if kind == 'bot' and recipient is not bot:
                d._receive(recipient, {'char': recipient['char'], 'type': 'healed', 'from': bot['char'],
                                      'heal': heal, 'hp': hp}, bots)
            if kind != 'monster':
                d._witness(bots, recipient['x'], recipient['y'],
                           {'kind': 'ally_heal', 'char': recipient['char'], 'how': '물약'},
                           exclude=(bot['char'], recipient['char']))
            return _base(bot, action, 'healed', heal=heal, hp=hp, potions=bot['potions'], item_used=item_id)
        if kind == 'door':
            res = d._set_order(bot, rid, bots)
            return {**res, 'type': 'use', 'effect_type': 'goto'}
        if kind in ('feature', 'exit'):
            res = d._interact(bot, rid, bots)
            d._obj_tag(bot, obj, res)
            if res.get('result') == 'nothing':
                return _base(bot, action, 'no_effect', reason_code='no_intrinsic_use')
            return {**res, 'type': 'use', 'effect_type': 'interact'}
        return _base(bot, action, 'no_effect', reason_code='no_intrinsic_use')
    return _base(bot, action, 'no_effect')


def attack_actor(d, bot, recipient, bots):
    """사람도 같은 명중·장비·피격 중단 규칙을 따른다. 관계의 감정 평가는 만들지 않는다."""
    import dungeon_gm as G
    mod = bot['dex'] if int(bot.get('atk_range') or 1) > 1 else bot['str']
    ac = 10 + recipient['dex'] + G.gear_bonus(recipient, 'armor')
    if d.status:
        mod -= G.POISON_MOD if not d.trpg_combat and '중독' in (bot.get('status') or {}) else 0
        ac -= G.POISON_MOD if '중독' in (recipient.get('status') or {}) else 0
    if d.trpg_combat:
        combat_roll = SC.check(d, mod, ac, disadvantage=d.status and '중독' in (bot.get('status') or {}), attack=True)
        roll, hit = combat_roll['roll'], combat_roll['success']
    else:
        roll = d.d20()
        hit = roll == 20 or roll + mod >= ac
    res = {'char': bot['char'], 'type': 'attack', 'result': 'attack', 'target_id': 'b' + recipient['char'],
           'target': recipient.get('name') or recipient['job'], 'roll': roll, 'mod': mod,
           'total': roll + mod, 'ac': ac, 'hit': hit}
    if d.trpg_combat:
        res['combat_roll'] = combat_roll
    if hit:
        damage = (bot['wdmg'] + G.gear_bonus(bot, 'weapon')) * (2 if roll == 20 else 1)
        if d.trpg_combat:
            damage_roll = SC.weapon_damage(d, bot['wdmg'], roll == 20)
            damage = damage_roll['value'] + G.gear_bonus(bot, 'weapon')
            res['damage_roll'] = damage_roll
        res.update(damage_actor(d, bot, recipient, damage, bots, roll == 20))
    return res


def damage_actor(d, bot, recipient, damage, bots, critical=False):
    """사람 대상 피해의 피격 중단·쓰러짐·목격을 스킬과 공유한다."""
    res = {}
    recipient['hp'] -= damage
    interrupted = d._cancel_approach(recipient)
    recipient['order'], recipient['path'], recipient['plan'] = None, [], []
    res.update(dmg=damage, hp=max(0, recipient['hp']), monster_hp=max(0, recipient['hp']),
               target_kind='bot', crit=critical)
    d._note_last(recipient, {'type': 'hurt', 'by': bot.get('name') or bot['job'],
                            'by_id': 'b' + bot['char'], 'by_kind': 'bot',
                            'dmg': damage, 'hp': max(0, recipient['hp']), **interrupted})
    if recipient['hp'] <= 0:
        recipient['alive'] = False
        res['killed'] = True
        grave = d._on_down(recipient, bots, by=bot.get('name') or bot['job'], by_kind='bot')
        if grave:
            res['grave'] = grave
    else:
        d._witness(bots, recipient['x'], recipient['y'],
                   {'kind': 'ally_hurt', 'char': recipient['char'],
                    'by': bot.get('name') or bot['job'], 'by_kind': 'bot', 'dmg': damage},
                   exclude=(bot['char'], recipient['char']))
    return res


def decorate(bot, action, result):
    """기존 이벤트의 상태 태그와 result를 유지하며 공통 결과를 resolution에 추가한다."""
    r = result.get('result')
    pending = bool(bot.get('order')) and (r in ('approaching', 'pathed', 'walking', 'following', 'resting', 'waiting') or result.get('approach_status') == 'ready')
    if pending:
        status = None
    elif r in ('lost', 'no_target', 'too_far', 'no_path', 'blocked', 'nothing', 'no_potion', 'no_room', 'wait_allies', 'disabled', 'skill_failed', 'skill_missed'):
        status = 'failed'
    elif r == 'no_effect' or (action['type'] == 'search' and not result.get('found')):
        status = 'no_effect'
    elif r == 'attack' and not result.get('hit'):
        status = 'failed'
    elif result.get('approach_status') == 'interrupted':
        status = 'failed'
    elif result.get('type') == 'walk' and r in ('encounter', 'sighted', 'at_exit', 'trap', 'dry', 'loop', 'room'):
        status = 'failed'
    else:
        status = 'success'
    result['resolution'] = {'actor': 'b' + bot['char'], 'type': action['type'], 'target': action.get('target'),
                            'phase': 'pending' if pending else 'resolved', 'status': status,
                            'reason': result.get('reason_code') or r or ('found' if result.get('found') else 'no_change')}
    return result

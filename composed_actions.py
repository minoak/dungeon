# -*- coding: utf-8 -*-
"""조합형 행동의 관측·입력·효과 계약. 기존 엔진의 시야와 물리 함수를 재사용한다.

대상 태그는 효과를 정하는 사실이다. 행동별 허용 대상 목록으로 사용하지 않는다.
좌표/실물 참조는 봇 내부에만 보관하고 모델에는 기존 방위·거리 표현을 보낸다.
"""
import copy
import entities as ENT
import interactables as IA
import skill_core as SK
import skill_combat as SC

SCHEMA = 'compose-v0.5'    # 관측 계약(obs.action_schema) — p0.5.5(master_plan §4.3·§7.1): 행동 등록부·'추가 행동' 블록·새 입력 칸 자리가 생긴 계약.
                           #   ID 문법·대상 목록은 v0.4 그대로라 등록부가 빈 지금은 관측 꼴도 v0.4 와 같다(이 문자열만 다름 — verify_skill_off 기준선 이력).
                           #   분석 도구·--rescore 는 이 값으로 옛(~p0.5.4) 기록과 새 기록을 가른다.
PROFILE = 'compose-v0.5'   # 행동 계약(run_meta.compose_profile) — D48(2026-09-11): COMMON 에서 follow 제거
# D48 follow 폐지(파트너 결정 09-11) — 동행은 `goto b<char>`(보이는 동료에게 한 번 걷고, 곁에 닿으면 다시 판단)로만.
# 엔진의 follow order(D18 A-5)는 메뉴형(비교용 옛 규칙)·구판 리플레이용으로 남는다 — 조합형 파서만 모르는 동사가 된다.
COMMON = ('goto', 'explore', 'search', 'attack', 'use', 'give', 'bond', 'wait', 'rest')
DISTANCE_ACTIONS = ('search', 'attack', 'use', 'give', 'bond')
PARTY = ('party_form', 'party_leave')   # D84 조각 3(2026-09-19): 파티 장부가 걸린 판(obs.partyform)에서만 읽는 동사 — COMMON 밖(옛 판의 행동 계약은 그대로).
#   party_form + target(b<번호>) = 파티 결성(길드 구역에서 청하고 맞받는다 — 거리 무관) · party_leave(대상 없음) = 파티 탈퇴
ITEM_SLOTS = {'i1': 'potion', 'i2': 'weapon', 'i3': 'armor', 'i4': 'boon'}   # i4=축복의 물약(D74, 09-15) — 병 단위, 있을 때만 관측에

# ── 행동 등록부(p0.5.5, master_plan §7.1) — COMMON 옆의 '추가 행동' ─────────────────────────────────────────────
# 공용 행동(steal·hide·help …)은 단계가 들어갈 때마다 여기에 한 동사씩 는다(그 단계 커밋에). 지금은 비어 있다.
# 상시 9개(COMMON)와 달리 '추가 행동' 블록에는 그 판단의 상황에 맞는 동사만 나타난다(DECISIONS 29행 — 지침 분량 관리).
# 노출은 안내일 뿐 허가가 아니다: 등록된 동사는 노출 밖이어도 parse 가 받는다(알려진 동사를 시도할 자유 — CA §3.2-4).
# 동사 하나 = {
#   'expose': view → bool  — 이번 판단에 보일까. view 는 EXPOSE_KEYS 칸만 담은 관측 사본이다(세계·봇 dict 는 받지 않는다:
#                            숨은 것 때문에 목록이 바뀌면 목록 자체가 누출이다 — §6.3 경로 13). 노출 조건은 그 동사 단계가 정한다.
#   'run': (d, bot, action, target, bots) → 결과 dict — 효과 판정(거리 확인 뒤). target = entity() 의 (종류, 칸, 실물) | None
#   'target': True(기본 — 대상 필수) | False(대상 없음 — 적어 와도 버린다, party_leave 꼴)
#   'range': (d, bot, action, target) → bool — 지금 자리에서 닿나(없으면 in_range). 밖이면 자동 접근 없이 too_far(§6.3 경로 7)
#   'fields': {칸: 허용 값 튜플 | None(자유 문구, FIELD_LEN 자)} — parse 가 검사하는 새 입력 칸(loot·mode·request …)
#   'required': (칸, …) — 빠지면 missing_<칸>
#   'results': (결과 코드, …) — run 이 내는 result 전부(too_far·lost 는 라우터 몫이라 빼도 된다). 코드마다 직전 결과 문장(B._last_prose)과
#              꼬리표(G.event_tags)를 그 단계가 등록한다 — 최소 기록 {type, result, target}로도 폴백 없이 그려져야 한다(verify_common_registry ⑨)
# }  문장(관측 '추가 행동' 블록의 한 줄) = prompts/actions/common_extra.md 의 `동사` 칸(D100 말 파일 — tools/check_words.py 가 등록부와 대조).
COMMON_EXT = {}
EXPOSE_KEYS = ('actor', 'targets', 'items', 'sights', 'status')   # 노출 조건이 읽는 관측 칸 — 전부 행동자 프롬프트에 그려지는 칸(verify_common_registry ①)
BASE_FIELDS = ('type', 'target', 'item', 'form')
FIELD_LEN = 40
EXTRA_WORDS = 'common_extra'          # prompts/actions/<이것>.md — '추가 행동' 블록의 문장
_EXTRA_LINES = None


def fields():
    """행동 dict 가 들고 다니는 입력 칸(결과 머리·접근 대기·_active_action 이 보존하는 칸) — 기본 4칸 + 등록부 동사의 새 칸.
    등록부가 비면 기본 4칸 그대로(p0.5.4 와 같은 dict)."""
    extra = sorted({f for spec in COMMON_EXT.values() for f in (spec.get('fields') or {})} - set(BASE_FIELDS))
    return BASE_FIELDS + tuple(extra)


def known_types():
    """parse 가 공용 행동으로 받는 동사 전부 = 상시 9개 + 등록부 전체(노출과 무관)."""
    return COMMON + tuple(COMMON_EXT)


def extra_types(obs):
    """이번 판단의 '추가 행동' — 등록부 동사 중 노출 조건이 맞는 것(등록 순서). 행동자에게 그려지는 관측 칸만 읽는다."""
    if not COMMON_EXT:
        return []
    view = {k: obs[k] for k in EXPOSE_KEYS if k in obs}
    return [v for v, spec in COMMON_EXT.items() if spec['expose'](copy.deepcopy(view))]   # 동사마다 새 사본 — 한 조건이 다음 조건의 입력을 못 바꾼다


def common_types(obs):
    """이번 판단에 제시되는 공용 행동 = 상시 9개 + 노출된 추가 행동(§7.1 common_types)."""
    return COMMON + tuple(obs.get('common_extra') or ())


def route(d, typ):
    """조합형 행동의 갈래(§6.3 경로 7 — 라우터 세 곳이 이 한 함수를 본다). 등록부를 스킬보다 먼저 본다:
    'common'(상시 9개 — DISTANCE_ACTIONS 만 자동 접근) · 'ext'(등록부 — 자동 접근 없음) · 'party' · 'skill'(스킬 켠 판의 그 밖 동사) · None."""
    if typ in COMMON:
        return 'common'
    if typ in COMMON_EXT:
        return 'ext'
    if typ in PARTY:
        return 'party'
    return 'skill' if getattr(d, 'skills', False) else None


def extra_lines(obs):
    """관측 '추가 행동' 블록(B._wire 의 COMMON 줄 아래) — 노출된 동사가 있을 때만: 머리 한 줄 + 동사마다 한 줄. 없으면 [].
    문장은 말 파일(prompts/actions/common_extra.md)에서 — 지침 파일(prompts/adventurer_prompt.md)이 아니라 관측에 붙인다(§7.2):
    벤치 변형이 지침의 '## 행동 사전' 절을 통째로 바꿔도 모든 변형이 같은 블록을 받는다."""
    extra = obs.get('common_extra') or []
    if not extra:
        return []
    words = _extra_words()
    return [words['header']] + ['- %s: %s' % (v, words[v]) for v in extra]


def _extra_words():
    global _EXTRA_LINES
    if _EXTRA_LINES is None:
        import words as W
        _EXTRA_LINES = W.action_words(EXTRA_WORDS)
    return _EXTRA_LINES


def item_value(bot, slot):
    return bot.get('potions', 0) if slot == 'potion' else bot.get('boons', 0) if slot == 'boon' else bot.get(slot)


def item_text(d, bot, ftype, name):
    """p0.5.6 아이템 설명 두 겹 — {'desc': 물건 설명(정의 item.desc, 중괄호는 채움), 'rule': type 의 다루는 규칙} | {}(아이템이 아니거나 정의를
    못 찾음 — 거짓 설명보다 빈칸). 캐릭터가 ID 로 집을 수 있는 자리(바닥 f… · 소지 i…)만 부른다(item_desc_design §4.1).
    관측 dict 에는 줄마다 싣고, 같은 글을 한 번만 찍는 것은 그리는 쪽(brains._wire)의 일이다(자기 두뇌는 줄마다 받는다)."""
    if ftype not in ENT.ITEM_TYPES:
        return {}
    df = ENT.item_def(ftype, name)
    if df is None:
        return {}
    return {'desc': ENT.item_desc(df, **(d.bless_fill(bot) if ftype == 'boon' else {})), 'rule': ENT.item_rule(ftype)}


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
            tags = (['agent', 'living', 'damageable', 'movable'] if kind in ('bot', 'monster')
                    else ENT.feature_tags(obj.get('type')))     # 오브젝트 태그 = 정의(D50): 장비·물약 = object+item
            if kind == 'bot':
                tags += ['inventory_holder']
            if kind == 'feature' and obj.get('use'):            # D89(09-20) 쓰임 부품 — 정의에 use 가 있는 오브젝트·건물만 사실 태그가 붙는다
                tags += [t for t in IA.tags(obj['use']) if t not in tags]   #   (interactable + readable·seat·lodging …). 없는 피처는 옛 목록 그대로
            targets.append({'id': rid, 'kind': kind, 'tags': tags,
                            **{k: obj[k] for k in ('name', 'dist', 'bearing') if k in obj},
                            **(item_text(d, bot, obj.get('type'), obj.get('name')) if kind == 'feature' else {})})   # p0.5.6 바닥 아이템의 설명(아이템만)
    if sights.get('exit'):
        refs['exit'] = {'kind': 'exit', 'key': 'exit'}
        targets.append({'id': 'exit', 'kind': 'exit', 'name': '계단', 'tags': ['object', 'interactable']})
    for n in obs.get('notices') or []:               # D69(09-14) 게시판의 의뢰 — 문턱 근처에 섰을 때만 대상이 된다(use=맡기, goto=게시판으로)
        if n.get('kind') != 'board':
            continue
        for q in n.get('quests') or []:
            tid = q.get('tid')
            if not tid:
                continue
            refs[tid] = {'kind': 'quest', 'qid': q.get('id'), 'building': n.get('building')}
            targets.append({'id': tid, 'kind': 'quest', 'name': '의뢰 「%s」' % q.get('title', '?'),
                            'tags': ['object', 'quest'] + (['accepted'] if q.get('accepted') else []),
                            **{k: q[k] for k in ('goal', 'reward', 'client') if q.get(k)}})
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
                 'name': '회복 물약' if slot == 'potion' else '축복의 물약' if slot == 'boon' else value['name'],
                 'tags': (['item', 'consumable', 'healing'] if slot == 'potion'
                          else ['item', 'consumable', 'blessing'] if slot == 'boon' else ['item', 'equipment'])}
        if slot in ('potion', 'boon'):
            entry['count'] = value
        else:
            entry['bonus'] = value.get('bonus', 0)
        entry.update(item_text(d, bot, slot, entry['name']))   # p0.5.6 소지품 설명(매 판단) — 축복 물약의 옛 effect('마시면 힘 +1', D74)는 설명이 흡수했다
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
    extra = extra_types(obs)
    if extra:                                       # 있을 때만 — 노출된 추가 행동이 없으면 관측 꼴이 v0.4 와 같다(§4.3 '없으면 안 나온다' 원칙)
        obs['common_extra'] = extra
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
    targetless = typ in ('wait', 'rest', 'party_leave') or (typ in COMMON_EXT and not COMMON_EXT[typ].get('target', True))
    valid = targetless or remembered or entity(d, bot, rid, bots, refs)   # 새 입력 칸(loot·mode …)은 step 에 그대로 실려 간다 — 값의 뜻은 실행(run)이 그때 세계로 다시 본다
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
    ext = COMMON_EXT.get(typ)                      # p0.5.5 등록부 동사 — 이번 판단에 노출됐는지는 보지 않는다(알려진 동사를 시도할 자유)
    if (typ not in COMMON and ext is None and typ not in {s['id'] for s in obs.get('skills', [])}
            and not (typ in PARTY and obs.get('partyform') is not None)):
        return None, 'invalid_type'
    out = {'type': typ}
    if typ == 'party_leave':                       # 대상 없는 동사(wait·rest 와 같은 꼴) — 대상을 적어 와도 버린다
        return out, None
    no_target = ext is not None and not ext.get('target', True)
    if no_target:
        target = ''                                # 대상 없는 등록부 동사 — party_leave 처럼 버린다(새 입력 칸은 아래에서 본다)
    if not target and typ == 'search':             # 주변 조사라는 기존 문법의 호환 별칭
        target = 'self'
    if typ not in ('wait', 'rest') and not target and not no_target:
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
    if ext is not None:                            # 새 입력 칸 — 꼴만 본다(허용 값·길이). 소유·동의·효과는 실행(run)이 판정한다(CA §3.2-4)
        for name, allowed in (ext.get('fields') or {}).items():
            raw = obj.get(name)
            value = ' '.join(str(raw).replace('"', '').replace("'", '').split())[:FIELD_LEN] if raw is not None else ''
            if not value:
                if name in (ext.get('required') or ()):
                    return None, 'missing_' + name
                continue
            if allowed is not None:
                value = value.lower()
                if value not in allowed:
                    return None, 'invalid_' + name
            out[name] = value
    return out, None


def error_detail(obj, obs, error):
    """실패를 다시 분석할 수 있도록 원래 요청과 참조 가능한 ID를 보존한다."""
    target = str(obj.get('target') or '')
    ids = sorted({e['id'] for e in obs.get('targets', [])} | {obs.get('actor', 'self')})
    known = sorted(e['id'] for e in obs.get('known', {}).get('statics', []) if e.get('id'))
    subtype = ('missing_target' if not target else 'way_not_current' if target.startswith('w')
               else 'memory_only' if target in known and target not in ids else 'not_observed')
    ext = COMMON_EXT.get(str(obj.get('type') or '').strip().lower())   # p0.5.5 등록부 동사의 칸 오류 — 받는 값을 함께 돌려준다(있을 때만)
    field = error.split('_', 1)[1] if ext and error.startswith(('invalid_', 'missing_')) else None
    allowed = (ext.get('fields') or {}).get(field) if field else None
    return {'code': error, 'target_detail': subtype if error in ('invalid_target', 'missing_target') else None,
            'attempted_action': copy.deepcopy(obj), 'target_ids': ids, 'known_goto_ids': known,
            'item_ids': [e['id'] for e in obs.get('items', [])],
            **({'field_values': list(allowed)} if allowed else {})}


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
    if kind == 'quest':                                  # D69 의뢰 — 그 게시판 건물 문턱의 range 안에 서 있을 때만 실물(글)이다
        fid, rng = (getattr(d, 'quest_boards', None) or {}).get(ref.get('qid'), (None, 2))
        f = d.features.get(fid) if fid is not None else None
        if not f or max(abs(f.x - bot['x']), abs(f.y - bot['y'])) > rng:
            return None
        return kind, (f.x, f.y), ref
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
        if not value or (ref['slot'] not in ('potion', 'boon') and value != ref['value']):   # 병 단위 슬롯은 수만 본다
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
    if target[0] == 'quest':                              # D69 게시판의 글 — 대상이 된 시점에 이미 range 안(entity 가 재확인)
        return True
    distance = abs(x - tx) + abs(y - ty)
    if action['type'] == 'attack':
        return 1 <= distance <= int(bot.get('atk_range') or 1) and (distance == 1 or not d._sight_blocked(x, y, tx, ty))
    if action['type'] in ('give', 'bond') and target[0] in ('bot', 'monster'):
        return max(abs(x - tx), abs(y - ty)) <= 1
    return distance <= 1


def _base(bot, action, result, **extra):
    return {'char': bot['char'], **{k: action[k] for k in fields() if k in action},
            'result': result, **extra}


def execute(d, bot, action, bots):
    """효과를 판정한다. 거리는 Dungeon의 공통 진입점에서 처리한다."""
    typ, rid = action['type'], action.get('target')
    target = entity(d, bot, rid, bots) if rid else None
    if typ in ('wait', 'rest', 'party_leave'):
        return d._execute_legacy_action(bot, action, bots)
    ext = COMMON_EXT.get(typ)
    if ext is not None:                            # p0.5.5 등록부 동사 — 자동 접근을 타지 않는다(라우터 route='ext'): 닿지 않으면 too_far(§6.3 경로 7)
        if ext.get('target', True):
            if not target:
                return _base(bot, action, 'lost')
            if not (ext.get('range') or in_range)(d, bot, action, target):
                return _base(bot, action, 'too_far')
        return ext['run'](d, bot, action, target if ext.get('target', True) else None, bots)
    if typ == 'party_form':                        # D84 조각 3: 사람만 대상 — 판정(길드 구역·맞받기·전원 모임)은 엔진 한 곳에서
        if target and target[0] == 'bot' and target[2] is not bot:
            return d._party_form(bot, rid, bots)
        return _base(bot, action, 'no_target')
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
        if typ == 'goto' and kind == 'bot' and obj is not bot:   # D48 개정(09-11 메모 §2-4): 사람에게 goto = 추적(곁+정지면 해제)
            return d._set_follow(bot, rid, bots, chase=True)
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
            if item[2]['slot'] == 'boon':                        # D74(09-15) 축복의 물약 — 자기에게만(남에게 넘기려면 give)
                if not ((kind == 'item' and obj['slot'] == 'boon') or (kind == 'bot' and obj is bot)):
                    return _base(bot, action, 'no_effect', reason_code='no_item_effect')
                eff = d._bless(bot, bots)
                return (_base(bot, action, 'drink_boon', **eff, item_used=item_id) if eff
                        else _base(bot, action, 'nothing', reason_code='item_not_owned'))
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
        if kind == 'quest':                               # D69 의뢰 맡기 — 게시판 글의 '기능'은 맡는 것이다
            res = d._interact(bot, rid, bots)
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
           'attack_mode': 'ranged' if int(bot.get('atk_range') or 1) > 1 else 'melee',
           'source_xy': [bot['x'], bot['y']], 'target_xy': [recipient['x'], recipient['y']],
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
    pending = bool(bot.get('order')) and (r in ('approaching', 'pathed', 'walking', 'following', 'beside', 'resting', 'waiting') or result.get('approach_status') == 'ready')
    if pending:
        status = None
    elif r in ('lost', 'no_target', 'too_far', 'no_path', 'blocked', 'nothing', 'no_potion', 'no_boon', 'no_room', 'wait_allies', 'disabled', 'skill_failed', 'skill_missed',
               'offer_short'):                             # offer_short = D95 바칠 보물이 모자람(청했으나 못 한 일 — no_potion 과 같은 급)
        status = 'failed'
    elif r in ('no_effect', 'already_beside', 'used_up') or (action['type'] == 'search' and not result.get('found')):
        status = 'no_effect'                                   # used_up = D89 once 로 다 쓴 오브젝트를 다시 씀(실패가 아니라 변화 없음)
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

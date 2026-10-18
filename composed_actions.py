# -*- coding: utf-8 -*-
"""조합형 행동의 관측·입력·효과 계약. 기존 엔진의 시야와 물리 함수를 재사용한다.

대상 태그는 효과를 정하는 사실이다. 행동별 허용 대상 목록으로 사용하지 않는다.
좌표/실물 참조는 봇 내부에만 보관하고 모델에는 기존 방위·거리 표현을 보낸다.
"""
import copy
import json
import os
import re
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
# p0.5.28 동사 = 데이터(DECISIONS 10-18 동사 작업 순서 ①): 동사 정의는 entities/verb/<id>.json(설명은 말 파일 prompts/world/verb/<id>.md),
#   이 판에 쓰는 동사와 순서는 동사 세트 파일(VERB_SET) 하나다. 아래 넷은 세트에서 짓는다(use_set — 모듈 끝에서 한 번 · 시험은 임시 세트로):
#   VERBS {동사: comps.verb} · COMMON(세트 순서 — 관측 COMMON 줄·지침 '행동 사전' 줄) · DISTANCE_ACTIONS(approach — 자동 접근, 닿지 않으면 too_far) ·
#   OPEN_END(open_end — 이어질 작정을 받지 않는다). 엔진에는 처리기(HANDLERS — 처리기 열쇠 → 효과 판정 함수)만 있다.
VERB_SET = os.path.join(ENT.ROOT, 'verb_set.json')
VERB_MARK = '<!--VERBS-->'   # 지침 파일에서 동사 줄이 들어갈 자리(brains._load_prompt 가 guide_lines 로 채운다)
VERB_LIST = re.compile(r'<!--VERBS:([a-z_]+):([^<>]*?)-->')   # 지침 문장 안의 동사 목록 자리 <!--VERBS:칸:잇는 말--> — guide_list 가 채운다
LIST_FIELDS = ('approach', 'item', 'open_end', 'memory_target', 'default_target', 'form')   # 목록 자리에 쓸 수 있는 동사 정의 칸
VERBS, COMMON, DISTANCE_ACTIONS, OPEN_END = {}, (), (), ()
PARTY = ('party_form', 'party_leave')   # D84 조각 3(2026-09-19): 파티 장부가 걸린 판(obs.partyform)에서만 읽는 동사 — COMMON 밖(옛 판의 행동 계약은 그대로).
#   party_form + target(b<번호>) = 파티 결성(길드 구역에서 청하고 맞받는다 — 거리 무관) · party_leave(대상 없음) = 파티 탈퇴
ITEM_SLOTS = {'i1': 'potion', 'i2': 'weapon', 'i3': 'armor', 'i4': 'boon',   # i4=축복의 물약(D74, 09-15) — 병 단위, 있을 때만 관측에
              'i7': 'gold', 'i8': 'treasure',   # p0.5.13(경제 1a) 골드(액수)·보물(개수) — 있을 때만 관측에. i5·i6 은 master_plan §4.3(돌·두건)
              'i9': 'ration'}                   # p0.5.16(경제 1b) 휴대식(개수) — use = 먹는다(자기만) · give = 하나씩
ITEM_NAMES = {'potion': '회복 물약', 'boon': '축복의 물약', 'gold': '골드', 'treasure': '보물', 'ration': '휴대식'}   # 세는 소지의 이름(장비는 든 것의 이름)
ITEM_TAGS = {'potion': ['item', 'consumable', 'healing'], 'boon': ['item', 'consumable', 'blessing'],
             'gold': ['item', 'currency'], 'treasure': ['item', 'valuable'], 'ration': ['item', 'consumable', 'food']}
AMOUNT_MAX = 9999          # p0.5.13 amount(골드 액수·보물 개수) 칸의 상한 — 꼴만 본다(지닌 것보다 많은지는 실행이 판정한다)

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
BASE_FIELDS = ('type', 'target', 'item', 'form', 'amount')   # amount = p0.5.13 골드 액수·보물 개수(give·팔기 — 있을 때만 행동 dict 에 실린다)
FIELD_LEN = 40
EXTRA_WORDS = 'common_extra'          # prompts/actions/<이것>.md — '추가 행동' 블록의 문장
_EXTRA_LINES = None
ALIASES = ('interact', 'drink')       # 옛 동사 별칭(normalize·parse 가 use 로 바꾼다) — 파티 동사(PARTY)와 함께 세트의 동사 이름으로 못 쓴다


class VerbError(ValueError):
    """동사 세트·정의를 쓸 수 없다(없는 동사·처리기 없음·중복 …) — 정의 오류와 같은 급(게임이 뜨지 않는다). 문제를 전부 나열한다."""


def read_set(path=VERB_SET, defs=None):
    """동사 세트 파일 → (동사 이름 튜플, {동사: comps.verb 사본}). defs = {id: 동사 정의}(기본 = entities 저장소의 kind verb — 꼴은 entities 가 이미 봤다).
    거절(전부 나열): 파일·꼴 · 정의가 없는 동사 · 처리기 열쇠가 엔진(HANDLERS)에 없음 · 같은 동사 두 번 · 엔진이 따로 읽는 이름(ALIASES·PARTY)."""
    repo = os.path.dirname(os.path.abspath(ENT.ROOT))
    full = os.path.abspath(path)
    rel = (os.path.relpath(full, repo) if full.startswith(repo + os.sep) else full).replace(os.sep, '/')
    try:
        with open(path, encoding='utf-8') as f:
            doc = json.load(f)
    except (OSError, ValueError) as e:
        raise VerbError('%s: 동사 세트를 못 읽는다 — %s' % (rel, type(e).__name__))
    names = doc.get('verbs') if isinstance(doc, dict) else None
    if not (isinstance(names, list) and names and all(isinstance(v, str) for v in names)):
        raise VerbError('%s: verbs 는 동사 이름(문자열)의 비지 않은 목록이어야 한다' % rel)
    defs = {d['id']: d for d in ENT.by_kind('verb')} if defs is None else defs
    problems, seen, specs = [], set(), {}
    for v in names:
        d = defs.get(v)
        vb = (d.get('comps') or {}).get('verb') if isinstance(d, dict) else None
        if v in seen:
            problems.append('%s: 동사 %r 가 두 번 나온다' % (rel, v))
        elif v in ALIASES + PARTY:
            problems.append('%s: 동사 %r 는 엔진이 따로 읽는 이름이다(%s)' % (rel, v, ' · '.join(ALIASES + PARTY)))
        elif not isinstance(vb, dict) or d.get('kind') != 'verb':
            problems.append('%s: 동사 %r 의 정의가 없다(entities/verb/%s.json)' % (rel, v, v))
        elif vb.get('handler') not in HANDLERS:
            problems.append('%s: 동사 %r 의 처리기 %r 가 엔진에 없다(처리기: %s)' % (rel, v, vb.get('handler'), ' · '.join(HANDLERS)))
        else:
            specs[v] = copy.deepcopy(vb)
        seen.add(v)
    if problems:
        raise VerbError('\n'.join(problems))
    return tuple(names), specs


def use_set(path=VERB_SET, defs=None):
    """세트를 읽어 이 모듈의 동사 이름들(VERBS·COMMON·DISTANCE_ACTIONS·OPEN_END)을 짓는다 — 엔진·지침·관측이 읽는 동사 목록은 이것 하나.
    모듈을 읽을 때 기본 세트로 한 번 부른다. 시험은 임시 세트로 불렀다가 기본 세트로 되돌린다. 거절이면 VerbError(이름들은 그대로)."""
    global VERBS, COMMON, DISTANCE_ACTIONS, OPEN_END
    names, specs = read_set(path, defs)
    VERBS = {v: specs[v] for v in names}
    COMMON = names
    DISTANCE_ACTIONS = tuple(v for v in names if specs[v].get('approach'))
    OPEN_END = tuple(v for v in names if specs[v].get('open_end'))
    return names


def handler_of(typ):
    """행동 type → 처리기 열쇠(세트의 동사). 세트 밖 이름(스킬·파티·등록부·옛 판 동사)은 그대로 — 동사별 규칙(사거리·접근 조건)은 이 열쇠로 본다."""
    spec = VERBS.get(typ)
    return spec['handler'] if spec else typ


def guide_lines():
    """지침 '행동 사전'의 COMMON 동사 줄 — 세트 순서대로 '- `동사`: 설명'(설명 = 말 파일의 verb.desc). 지침 파일의 VERB_MARK 자리에 들어간다."""
    return ['- `%s`: %s' % (v, VERBS[v]['desc']) for v in COMMON]


def guide_list(field, joiner):
    """지침 문장 안의 동사 목록(VERB_LIST 자리) — 그 칸(field)이 있는 세트 동사를 세트 순서대로 joiner 로 잇는다(approach '·' → 'search·attack·use·give·bond' ·
    item '와 ' → 'use와 give'). 목록 뒤 조사는 지침의 글이다. 모르는 칸이면 VerbError(지침이 틀렸다 — 게임이 뜨지 않는다)."""
    if field not in LIST_FIELDS:
        raise VerbError('지침의 동사 목록 자리 <!--VERBS:%s:…--> — 모르는 칸(쓸 수 있는 칸: %s)' % (field, ' · '.join(LIST_FIELDS)))
    return joiner.join(v for v in COMMON if VERBS[v].get(field))


def fields():
    """행동 dict 가 들고 다니는 입력 칸(결과 머리·접근 대기·_active_action 이 보존하는 칸) — 기본 4칸 + 등록부 동사의 새 칸.
    등록부가 비면 기본 4칸 그대로(p0.5.4 와 같은 dict)."""
    extra = sorted({f for spec in COMMON_EXT.values() for f in (spec.get('fields') or {})} - set(BASE_FIELDS))
    return BASE_FIELDS + tuple(extra)


def known_types():
    """parse 가 공용 행동으로 받는 동사 전부 = 상시 동사(세트) + 등록부 전체(노출과 무관)."""
    return COMMON + tuple(COMMON_EXT)


def extra_types(obs):
    """이번 판단의 '추가 행동' — 등록부 동사 중 노출 조건이 맞는 것(등록 순서). 행동자에게 그려지는 관측 칸만 읽는다."""
    if not COMMON_EXT:
        return []
    view = {k: obs[k] for k in EXPOSE_KEYS if k in obs}
    return [v for v, spec in COMMON_EXT.items() if spec['expose'](copy.deepcopy(view))]   # 동사마다 새 사본 — 한 조건이 다음 조건의 입력을 못 바꾼다


def common_types(obs):
    """이번 판단에 제시되는 공용 행동 = 상시 동사(세트) + 노출된 추가 행동(§7.1 common_types)."""
    return COMMON + tuple(obs.get('common_extra') or ())


def route(d, typ):
    """조합형 행동의 갈래(§6.3 경로 7 — 라우터 세 곳이 이 한 함수를 본다). 등록부를 스킬보다 먼저 본다:
    'common'(상시 동사 = 세트 — DISTANCE_ACTIONS 만 자동 접근) · 'ext'(등록부 — 자동 접근 없음) · 'party' · 'skill'(스킬 켠 판의 그 밖 동사) · None."""
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
    if slot in IA.COUNTED:                         # 몸의 정수로 세는 소지(물약·축복·골드·보물 — p0.5.13 골드·보물이 더해졌다)
        return bot.get(IA.COUNTED[slot], 0)
    return bot.get(slot)


def item_text(d, bot, ftype, name):
    """p0.5.6 아이템 설명 두 겹 — {'desc': 물건 설명(정의 item.desc, 중괄호는 채움), 'rule': type 의 다루는 규칙} | {}(아이템이 아니거나 정의를
    못 찾음 — 거짓 설명보다 빈칸). 캐릭터가 ID 로 집을 수 있는 자리(바닥 f… · 소지 i…)만 부른다(item_desc_design §4.1).
    관측 dict 에는 줄마다 싣고, 같은 글을 한 번만 찍는 것은 그리는 쪽(brains._wire)의 일이다(자기 두뇌는 줄마다 받는다)."""
    if ftype not in ENT.ITEM_TYPES:
        return {}
    df = ENT.item_def(ftype, name)
    if df is None:
        return {}
    taste = list(df['comps'].get('taste') or [])   # p0.5.16 먹을 것의 취향 꼬리표(있을 때만 — '[g3] 식사 — 고기·따뜻한 것')
    return {'desc': ENT.item_desc(df, **(d.bless_fill(bot) if ftype == 'boon' else {})), 'rule': ENT.item_rule(ftype),
            **({'taste': taste} if taste else {})}


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
    for n in obs.get('notices') or []:               # p0.5.13 가게의 상품 — 문턱 SHOP_RANGE 칸 안에 섰을 때만 대상이 된다(use = 사기). 설명은 물건 설명·다루는 규칙 그대로
        if n.get('kind') != 'shop':
            continue
        for g in n.get('goods') or []:
            refs[g['tid']] = {'kind': 'good', 'gid': g['tid'], 'shop': n.get('id')}
            targets.append({'id': g['tid'], 'kind': 'good', 'name': g['name'], 'tags': ['item', 'good'], 'price': g['price'],
                            'shop': n.get('name'), **item_text(d, bot, g.get('type'), g['name'])})
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
                 'name': ITEM_NAMES.get(slot) or value['name'],
                 'tags': list(ITEM_TAGS.get(slot) or ['item', 'equipment'])}
        if slot in IA.COUNTED:
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
    spec = VERBS.get(action.get('type'))
    if spec and spec.get('default_target') and not action.get('target'):   # p0.5.28 동사 정의의 기본 대상(search = self)
        action['target'] = spec['default_target']
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
    spec = VERBS.get(typ)                          # p0.5.28 세트의 동사 — 기억 속 장소를 받나(memory_target) · 대상을 적지 않는 동사인가(target optional)
    remembered = bool(spec and spec.get('memory_target')) and rid in (bot.get('ledger') or {}).get('statics', {})
    refs = bot.get('_plan_refs', bot.get('_target_refs', {}))
    targetless = ((spec is not None and spec['target'] == 'optional') or typ == 'party_leave'
                  or (typ in COMMON_EXT and not COMMON_EXT[typ].get('target', True)))
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
    spec = VERBS.get(typ)                          # p0.5.28 세트의 동사 — 입력 칸 규칙(대상·기본 대상·기억 속 장소·소지품·몸짓)은 동사 정의가 정한다
    if (spec is None and ext is None and typ not in {s['id'] for s in obs.get('skills', [])}
            and not (typ in PARTY and obs.get('partyform') is not None)):
        return None, 'invalid_type'
    out = {'type': typ}
    if typ == 'party_leave':                       # 대상 없는 동사(wait·rest 와 같은 꼴) — 대상을 적어 와도 버린다
        return out, None
    no_target = ext is not None and not ext.get('target', True)
    if no_target:
        target = ''                                # 대상 없는 등록부 동사 — party_leave 처럼 버린다(새 입력 칸은 아래에서 본다)
    if not target and spec is not None and spec.get('default_target'):   # 기본 대상(search = self — 주변 조사라는 기존 문법의 호환 별칭)
        target = spec['default_target']
    if not target and not no_target and (spec is None or spec['target'] == 'required'):
        return None, 'missing_target'
    ids = {t['id'] for t in obs.get('targets', [])} | {obs.get('actor'), 'self'}
    if spec is not None and spec.get('memory_target'):   # 기억에 적힌 장소 ID(goto)
        ids |= {e['id'] for e in obs.get('known', {}).get('statics', []) if e.get('id')}
    if target:
        if target not in ids:
            return None, 'invalid_target'
        out['target'] = obs['actor'] if target == 'self' else target
    if item:
        item = next((k for k, v in ITEM_SLOTS.items() if v == item), item)
        if spec is None or not spec.get('item'):
            return None, 'unexpected_item'
        if item not in {e['id'] for e in obs.get('items', [])}:
            return None, 'invalid_item'
        out['item'] = item
        raw = obj.get('amount')                    # p0.5.13 골드 액수·보물 개수 — 그 둘에만 실린다(물약·축복·장비는 한 번에 하나라 버린다). 지닌 것보다 많은지는 실행이 본다
        if ITEM_SLOTS.get(item) in IA.AMOUNT_SLOTS and raw is not None and str(raw).strip() != '':
            try:
                n = int(raw) if (isinstance(raw, float) and raw.is_integer()) else int(str(raw).strip())
            except ValueError:
                return None, 'invalid_amount'
            if isinstance(raw, bool) or not 1 <= n <= AMOUNT_MAX:
                return None, 'invalid_amount'
            out['amount'] = n
    elif spec is not None and spec.get('item') == 'required':
        return None, 'missing_item'
    if spec is not None and spec.get('form'):       # 몸짓 서술(bond 120자)
        out['form'] = ' '.join(str(obj.get('form') or '').replace('"', '').replace("'", '').split())[:spec['form']]
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
    if kind == 'good':                                   # p0.5.13 가게의 상품 — 그 가게 문턱의 SHOP_RANGE 안에 서 있을 때만 실물(게시판 의뢰와 같은 꼴)
        g = IA.good(d, ref.get('gid'))
        f = d.features.get(g['fid']) if g else None
        if IA.shop_at(d, f) is None or max(abs(f.x - bot['x']), abs(f.y - bot['y'])) > IA.SHOP_RANGE or (f.x, f.y) not in seen:
            return None                                  #   p0513b(Codex 리뷰 P2): 가까워도 그 가게가 안 보이면 실물이 아니다(벽 너머·다른 구역)
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
        if not value or (ref['slot'] not in IA.COUNTED and value != ref['value']):   # 병 단위 슬롯은 수만 본다 · p0513b(리뷰 권장): 골드·보물도 수량형 — 액수가 바뀌어도 같은 소지품
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
    if target[0] in ('quest', 'good'):                    # D69 게시판의 글 · p0.5.13 가게의 상품 — 대상이 된 시점에 이미 range 안(entity 가 재확인)
        return True
    distance = abs(x - tx) + abs(y - ty)
    handler = handler_of(action['type'])            # p0.5.28 닿는 거리는 처리기의 규칙(동사 이름이 아니라)
    if handler == 'attack':
        return 1 <= distance <= int(bot.get('atk_range') or 1) and (distance == 1 or not d._sight_blocked(x, y, tx, ty))
    if handler in ('give', 'bond') and target[0] in ('bot', 'monster'):
        return max(abs(x - tx), abs(y - ty)) <= 1
    return distance <= 1


def _base(bot, action, result, **extra):
    return {'char': bot['char'], **{k: action[k] for k in fields() if k in action},
            'result': result, **extra}


def execute(d, bot, action, bots):
    """효과를 판정한다. 거리는 Dungeon의 공통 진입점에서 처리한다.
    p0.5.28: 세트의 동사는 동사 정의대로 거른 뒤(대상을 꼭 적는 동사 = 지금 못 찾으면 lost · 자동 접근 동사 = 닿지 않으면 too_far)
    그 처리기 열쇠의 함수(HANDLERS)가 판정한다. 대상을 적지 않는 동사(target optional)는 거르지 않고 처리기로 간다."""
    typ, rid = action['type'], action.get('target')
    target = entity(d, bot, rid, bots) if rid else None
    spec = VERBS.get(typ)
    if typ == 'party_leave':
        return d._execute_legacy_action(bot, action, bots)
    if spec is not None and spec['target'] == 'optional':
        return HANDLERS[spec['handler']](d, bot, action, target, bots)
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
        if spec is not None and spec.get('memory_target') and rid in (bot.get('ledger') or {}).get('statics', {}):
            return HANDLERS[spec['handler']](d, bot, action, None, bots)   # 기억 속 장소 — 지금 안 보여도 처리기가 기억대로 판정한다
        return _base(bot, action, 'lost')
    if spec is None:
        return _base(bot, action, 'no_effect')
    if spec.get('approach') and not in_range(d, bot, action, target):
        return _base(bot, action, 'too_far')
    return HANDLERS[spec['handler']](d, bot, action, target, bots)


# ── 처리기(p0.5.28) — 처리기 열쇠 → 효과 판정. (d, bot, action, target, bots) → 결과 dict. target = entity() 의 (종류, 칸, 실물) |
#   None(대상을 적지 않는 동사 · 기억 속 장소). 대상 거르기(lost·too_far)는 execute 가 동사 정의대로 먼저 했다.
#   새 동사는 이미 있는 처리기면 데이터만으로 든다(동사 정의 + 말 파일 + 세트 한 줄) — 새 효과는 여기에 처리기 하나를 더한다.

def _walk_to(d, bot, action, target, bots):
    """길·함정·소지품·자기 자신 — 그 칸까지 길을 낸다(goto·explore 공용)."""
    kind, xy, obj = target
    path = d.path_to(bot['x'], bot['y'], *xy, bots)
    if not path:
        return _base(bot, action, 'arrived' if xy == (bot['x'], bot['y']) else 'no_path')
    bot['order'], bot['path'] = '@%d,%d' % xy, path
    return _base(bot, action, 'pathed', len=len(path), **(obj['result'] if kind == 'way' else {}))


def _goto(d, bot, action, target, bots):
    rid = action.get('target')
    if target is None:                             # 기억 속 장소(memory_target) — 가 봐야 안다
        return d._set_order(bot, rid, bots)
    kind, xy, obj = target
    if kind in ('way', 'trap', 'item') or (kind == 'bot' and obj is bot):
        return _walk_to(d, bot, action, target, bots)
    if kind == 'bot':                              # D48 개정(09-11 메모 §2-4): 사람에게 goto = 추적(곁+정지면 해제)
        return d._set_follow(bot, rid, bots, chase=True)
    return d._set_order(bot, rid, bots)


def _explore(d, bot, action, target, bots):
    if target[0] != 'way':
        return _base(bot, action, 'no_effect', reason_code='not_a_way')
    return _walk_to(d, bot, action, target, bots)


def _search(d, bot, action, target, bots):
    kind, xy, obj = target
    if kind == 'bot' and obj is bot:
        return {**d._search(bot, bots), 'target': action.get('target')}
    return _base(bot, action, 'no_effect', reason_code='no_new_information', found=[])


def _attack(d, bot, action, target, bots):
    kind, xy, obj = target
    if kind == 'monster':
        return d._attack(bot, action.get('target'), bots)
    if kind == 'bot':
        return attack_actor(d, bot, obj, bots)
    return _base(bot, action, 'no_effect', reason_code='not_damageable')


def _give(d, bot, action, target, bots):
    kind, xy, obj = target
    item = entity(d, bot, action.get('item'), bots)
    if not item or item[0] != 'item':
        return _base(bot, action, 'nothing', reason_code='item_not_owned')
    if kind == 'bot' and obj is not bot:
        return d._give(bot, action.get('target'), item[2]['slot'], bots, amount=action.get('amount'))   # p0.5.13 골드 액수·보물 개수(없으면 1)
    return _base(bot, action, 'no_effect', reason_code='no_inventory_transfer')


def _bond(d, bot, action, target, bots):
    kind, xy, obj = target
    if kind == 'bot' and obj is not bot:
        return d._bond(bot, action.get('target'), action.get('form'), bots)
    return _base(bot, action, 'no_effect', reason_code='gesture_recorded')


def _use(d, bot, action, target, bots):
    rid = action.get('target')
    kind, xy, obj = target
    item_id = action.get('item') or (rid if kind == 'item' else None)
    item = entity(d, bot, item_id, bots) if item_id else None
    if item_id:
        if not item or item[0] != 'item':
            return _base(bot, action, 'nothing', reason_code='item_not_owned')
        if kind == 'feature' and IA.shop_at(d, obj) is not None:   # p0.5.13 팔기 — 가게에 소지품을 쓴다 = 판다(값은 가게가 정한다 · 사들이지 않으면 no_deal)
            res = IA.sell(d, bot, obj, item[2]['slot'], action.get('amount'), bots, rid, item_id)
            d._obj_tag(bot, obj, res)
            return {**res, 'type': 'use', 'effect_type': 'interact'}
        if kind == 'good' and item[2]['slot'] == 'gold':           # p0.5.13 골드를 상품에 쓴다 = 산다(값은 가게가 정한다 — 적은 액수는 보지 않는다)
            res = d._interact(bot, rid, bots)
            return {**res, 'type': 'use', 'effect_type': 'interact'}
        if item[2]['slot'] == 'ration':                      # p0.5.16 휴대식 — 자기만 먹는다(남에게 넘기려면 give). 가게에 쓰면 위의 팔기
            if not ((kind == 'item' and obj['slot'] == 'ration') or (kind == 'bot' and obj is bot)):
                return _base(bot, action, 'no_effect', reason_code='no_item_effect')
            return d._eat_ration(bot, bots, base=_base(bot, action, 'nothing'), item_used=item_id)
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
    if kind in ('quest', 'good'):                     # D69 의뢰 맡기 — 게시판 글의 '기능'은 맡는 것이다 · p0.5.13 상품의 기능은 사는 것이다
        res = d._interact(bot, rid, bots)
        return {**res, 'type': 'use', 'effect_type': 'interact'}
    return _base(bot, action, 'no_effect', reason_code='no_intrinsic_use')


def _wait(d, bot, action, target, bots):
    return d._set_wait(bot, bots)                  # 제자리 대기(D25)


def _rest(d, bot, action, target, bots):
    return d._set_rest(bot, bots)                  # 휴식(D35) — 회복이 붙은 wait


HANDLERS = {'goto': _goto, 'explore': _explore, 'search': _search, 'attack': _attack, 'use': _use,
            'give': _give, 'bond': _bond, 'wait': _wait, 'rest': _rest}


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
        grave = d._on_down(recipient, bots, by=bot.get('name') or bot['job'], by_kind='bot', by_id='b' + bot['char'])
        if grave:
            res['grave'] = grave
    else:
        d._witness(bots, recipient['x'], recipient['y'],
                   {'kind': 'ally_hurt', 'char': recipient['char'],
                    'by': bot.get('name') or bot['job'], 'by_kind': 'bot', 'by_id': 'b' + bot['char'], 'dmg': damage},   # p0.5.9 ID-1: 열쇠(by_id) — 실명 칸은 본 사람 몫 사본에서 걷힌다(IG.public ⑤)
                   exclude=(bot['char'], recipient['char']))
    return res


def decorate(bot, action, result):
    """기존 이벤트의 상태 태그와 result를 유지하며 공통 결과를 resolution에 추가한다."""
    r = result.get('result')
    pending = bool(bot.get('order')) and (r in ('approaching', 'pathed', 'walking', 'following', 'beside', 'resting', 'waiting') or result.get('approach_status') == 'ready')
    if pending:
        status = None
    elif r in ('lost', 'no_target', 'too_far', 'no_path', 'blocked', 'nothing', 'no_potion', 'no_boon', 'no_room', 'wait_allies', 'disabled', 'skill_failed', 'skill_missed',
               'offer_short',                              # offer_short = D95 바칠 보물이 모자람(청했으나 못 한 일 — no_potion 과 같은 급)
               'too_poor', 'no_deal', 'not_enough',        # p0.5.13 골드가 모자람 · 가게가 사들이지 않음 · 지닌 것보다 많이 팔거나 건네려 함
               'need_none'):                               # p0.5.16 배가 불러 먹지 못함(청했으나 몸이 거절 — too_poor 와 같은 급)
        status = 'failed'
    elif r in ('no_effect', 'already_beside', 'used_up', 'no_regen') or (handler_of(action['type']) == 'search' and not result.get('found')):   # p0.5.16 no_regen = 굶주린 몸이 쉬려 함(변화 없음)
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


use_set()   # p0.5.28 기본 동사 세트(VERB_SET) — 못 읽으면 VerbError 로 게임이 뜨지 않는다(정의 오류와 같은 급)

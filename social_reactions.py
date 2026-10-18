# -*- coding: utf-8 -*-
"""받은 사회 사건과 자발적인 반응. 집계는 관전 전용이며 봇의 기억·관계 점수에 쓰지 않는다.

사건 번호(p0.5.4 — master_plan §6.2 C·D, 누출 경로 4·5·6):
  · 원장(events)과 관전 스트림은 원정 전체 일련번호 social_N 을 그대로 쓴다(사건 줄을 이어 붙이는 열쇠).
  · 받는 사람에게는 **그 사람이 받은 순서의 번호**(alias)를 준다. 꼴은 같은 social_N 이다(모험가 지침의 '`social_...` ID' 그대로).
    전역 번호를 주면 번호 틈으로 '내가 모르는 사건이 몇 개 있었나'가 샌다. 반응(reaction_to)은 받은 번호로 받고 consume 이 원장 번호로 되돌린다.
    남의 번호로 반응하면 내 번호표에 없으므로 거절된다.
  · offer 는 recipients·source_action_id·parent_action_id·private 를 빼고, 결과에서 옮겨 온 칸은 공개 투영(info_guard.public)을 거친다.
  · 비공개 사건(record(..., private=True)): 행동자 결과에 사건 id 를 붙이지 않는다(붙일 곳은 결과의 audit). 받는 사람에게는 보통 사건처럼 간다.
    앞으로의 목록: 들킨 살핌·들킨 절도(피해자)·매혹 시도·매혹 풀림.
"""
import copy

import composed_actions as CA   # p0.5.28 동사 → 처리기 열쇠(handler_of)
import info_guard as IG
import identity as ID       # p0.5.9 사람 열쇠 판정(설계 X6)

PENDING_MAX = 32
OFFER_DROP = ('recipients', 'source_action_id', 'parent_action_id', 'private')   # 받는 사람에게 보내지 않는 칸


def parse(obj, obs):
    """반응 오류는 본 행동을 바꾸지 않는다. 현재 판단에 제공한 실제 사건만 허용한다."""
    if 'reaction' not in obj and 'reaction_to' not in obj and 'reactions' not in obj:
        return {}
    value, target = obj.get('reaction'), obj.get('reaction_to')
    if 'reactions' in obj:
        why = 'multiple_reactions_not_supported'
    elif value not in ('like', 'dislike'):
        why = 'invalid_reaction'
    elif not isinstance(target, str) or target not in {e['id'] for e in obs.get('social_events', [])}:
        why = 'reaction_not_received'
    else:
        return {'reaction': value, 'reaction_to': target}
    return {'reaction_error': {'code': why, 'value': value, 'target': target}}


def describe(event):
    if event.get('skill_id'):
        return '%s: HP +%d' % (event.get('skill_name', event['skill_id']), event.get('heal', 0))
    if event['type'] == 'say':
        return '%s: %s' % (event.get('say_kind', '잡담'), event.get('text', ''))
    if event['type'] == 'bond':
        return '친목: ' + event.get('form', '몸짓')
    if event['type'] == 'give':
        return '건네기: ' + event.get('what', event.get('item', '물건'))
    if event['type'] == 'use':
        return '물약 사용: HP +%d' % event.get('heal', 0)
    return '상호작용'   # 모르는 type(p0.5.4, §10.3) — '물약 사용'으로 지어내지 않는다. 새 사건 type 은 위에 가지를 더한다


class ReactionBook:
    """원정 수명의 원장. 사회 사건은 1회 기록하고 수신자별 다음 행동 판단에서 반응 기회를 준다."""
    def __init__(self, depth, turn=0):
        self.events = {}
        self.reactions = []
        self.pending = {}
        self.offered = {}
        self.responded = set()
        self.new_events = []
        self.new_reactions = []
        self.floors = []
        self.floor = None
        self.alias = {}          # 받는 사람 → {원장 id: 그 사람의 번호}(p0.5.4). 옛 스냅샷의 원장은 snapshot 이관이 rebuild_alias 로 매긴다
        self.start_floor(depth, turn)

    def start_floor(self, depth, turn):
        # 층 전이에서 기존 대화와 같이 미응답 기회를 닫는다. 묵시적인 neutral은 만들지 않는다.
        self.pending.clear()
        self.offered.clear()
        self.floor = {'id': 'floor_%d' % (len(self.floors) + 1), 'depth': depth, 'since': turn}

    def local(self, char, eid):
        """원장 사건 eid 의 char 쪽 번호 — record 가 받는 순간 매긴다(받은 순서 = 원장 순서). 늘 성립: alias[char] = char 가 받은 사건을 원장 순서로 social_1..n."""
        book = self.alias.setdefault(str(char), {})
        if eid not in book:
            book[eid] = 'social_%d' % (len(book) + 1)
        return book[eid]

    def rebuild_alias(self):
        """번호표를 원장에서 다시 매긴다 — 옛 스냅샷(번호표 없는 원장)을 이관할 때. 지나간 사건·대기 사건 모두 받은 순서대로 번호를 받아,
        이어간 뒤 새 사건이 옛 대기 사건보다 앞 번호를 받지 않는다(p0.5.4b, Codex 리뷰)."""
        self.alias = {}
        for eid, event in self.events.items():
            for char in event.get('recipients') or ():
                self.local(char, eid)

    def record(self, typ, actor, recipients, turn, private=False, **details):
        recipients = sorted({str(c) for c in recipients if str(c) != str(actor)})
        if not recipients:
            return None
        event = {'id': 'social_%d' % (len(self.events) + 1), 'type': typ, 'actor': str(actor),
                 'recipients': recipients, 'turn': turn, 'depth': self.floor['depth'],
                 'floor_id': self.floor['id'], **details, **({'private': True} if private else {})}
        self.events[event['id']] = event
        self.new_events.append(copy.deepcopy(event))
        for char in recipients:
            self.local(char, event['id'])
            queue = self.pending.setdefault(char, [])
            queue.append(event['id'])
            del queue[:-PENDING_MAX]
        return event['id']

    def offer(self, char):
        ids = self.pending.pop(char, [])
        self.offered[char] = set(ids)
        # 집계·다른 수신자·과거 반응·원장 번호를 노출하지 않고, 자신이 받은 사건의 사실만 자기 번호로 보낸다.
        return [{**IG.public({k: v for k, v in self.events[rid].items() if k not in OFFER_DROP}), 'id': self.local(char, rid)}
                for rid in ids]

    def consume(self, char, decision, turn):
        offered = self.offered.pop(char, set())
        value, target = decision.get('reaction'), decision.get('reaction_to')
        if value is None and target is None:
            return None
        mine = self.alias.get(str(char), {})
        source_id = next((eid for eid in offered if mine.get(eid) == target), None) if isinstance(target, str) else None
        valid = (value in ('like', 'dislike') and source_id is not None
                 and (char, source_id) not in self.responded and not decision.get('skipped')
                 and decision.get('src') != 'plan')
        if not valid:
            decision.pop('reaction', None)
            decision.pop('reaction_to', None)
            decision['reaction_error'] = {'code': 'reaction_not_eligible', 'value': value, 'target': target}
            return None
        source = self.events[source_id]
        reaction = {'id': 'reaction_%d' % (len(self.reactions) + 1), 'actor': char,
                    'to': source['actor'], 'value': value, 'reaction_to': source_id,
                    'turn': turn, 'depth': source['depth'], 'floor_id': source['floor_id'],
                    'source': copy.deepcopy(source)}
        self.responded.add((char, source_id))
        self.reactions.append(reaction)
        self.new_reactions.append(copy.deepcopy(reaction))
        return reaction

    def summary(self, floor_id=None):
        events = [e for e in self.events.values() if floor_id is None or e['floor_id'] == floor_id]
        reactions = [r for r in self.reactions if floor_id is None or r['floor_id'] == floor_id]
        total = {'like': 0, 'dislike': 0}
        actors, pairs = {}, {}
        for r in reactions:
            total[r['value']] += 1
            actors.setdefault(r['actor'], {'like': 0, 'dislike': 0})[r['value']] += 1
            pairs.setdefault((r['actor'], r['to']), {'like': 0, 'dislike': 0})[r['value']] += 1
        opportunities = sum(len(e['recipients']) for e in events)
        return {'total': total, 'by_actor': actors,
                'pairs': [{'from': a, 'to': b, **counts} for (a, b), counts in sorted(pairs.items())],
                'events': len(events), 'opportunities': opportunities, 'unrated': opportunities - len(reactions)}

    def snapshot(self):
        return {'run': self.summary(), 'floor': {**self.floor, **self.summary(self.floor['id'])}}

    def close_floor(self, turn):
        result = {**self.floor, 'until': turn, **self.summary(self.floor['id'])}
        self.floors.append(copy.deepcopy(result))
        return result

    def drain(self):
        out = {'social_events': self.new_events, 'reactions': self.new_reactions,
               'reaction_stats': self.snapshot()}
        self.new_events, self.new_reactions = [], []
        return out


def book(d):
    if not getattr(d, 'composed_actions', False):
        return None
    if not hasattr(d, 'reaction_book'):
        d.reaction_book = ReactionBook(d.depth, d.turn)
    return d.reaction_book


def physical(d, bot, action, result, bots):
    ledger = book(d)
    if ledger is None:
        return
    typ, outcome = CA.handler_of(action['type']), result.get('result')   # p0.5.28 동사가 아니라 처리기 열쇠로 본다(세트 밖 이름은 그대로)
    recipient = None
    details = {}
    if (typ, outcome) in (('give', 'given'), ('bond', 'done')):
        recipient = result.get('to')
        details = {k: result[k] for k in ('item', 'what', 'form', 'placed') if k in result}
    elif typ == 'use' and outcome == 'healed' and ID.is_bot_key(action.get('target')):   # p0.5.9: 사람 열쇠 판정은 identity 한 곳(설계 X6)
        recipient = ID.char_of(action['target'])
        details = {'heal': result.get('heal', 0), 'item': action.get('item', 'i1')}
    elif result.get('skill_id') and result.get('heal', 0) > 0 and ID.is_bot_key(action.get('target')):
        typ = 'skill'
        recipient = ID.char_of(action['target'])
        details = {k: result[k] for k in ('heal', 'skill_id', 'skill_name')}
    if recipient and any(b['char'] == recipient and b['alive'] and not b['won'] for b in bots):
        rid = ledger.record(typ, bot['char'], [recipient], d.turn,
                            source_action_id=action.get('action_id'), **details)
        if rid:
            result['social_event_id'] = rid

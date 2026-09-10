# -*- coding: utf-8 -*-
"""받은 사회 사건과 자발적인 반응. 집계는 관전 전용이며 봇의 기억·관계 점수에 쓰지 않는다."""
import copy

PENDING_MAX = 32


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
    return '물약 사용: HP +%d' % event.get('heal', 0)


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
        self.start_floor(depth, turn)

    def start_floor(self, depth, turn):
        # 층 전이에서 기존 대화와 같이 미응답 기회를 닫는다. 묵시적인 neutral은 만들지 않는다.
        self.pending.clear()
        self.offered.clear()
        self.floor = {'id': 'floor_%d' % (len(self.floors) + 1), 'depth': depth, 'since': turn}

    def record(self, typ, actor, recipients, turn, **details):
        recipients = sorted({str(c) for c in recipients if str(c) != str(actor)})
        if not recipients:
            return None
        event = {'id': 'social_%d' % (len(self.events) + 1), 'type': typ, 'actor': str(actor),
                 'recipients': recipients, 'turn': turn, 'depth': self.floor['depth'],
                 'floor_id': self.floor['id'], **details}
        self.events[event['id']] = event
        self.new_events.append(copy.deepcopy(event))
        for char in recipients:
            queue = self.pending.setdefault(char, [])
            queue.append(event['id'])
            del queue[:-PENDING_MAX]
        return event['id']

    def offer(self, char):
        ids = self.pending.pop(char, [])
        self.offered[char] = set(ids)
        # 집계·다른 수신자·과거 반응을 노출하지 않고 자신이 받은 사건의 사실만 보낸다.
        return [{k: copy.deepcopy(v) for k, v in self.events[rid].items() if k != 'recipients'} for rid in ids]

    def consume(self, char, decision, turn):
        offered = self.offered.pop(char, set())
        value, target = decision.get('reaction'), decision.get('reaction_to')
        if value is None and target is None:
            return None
        valid = (value in ('like', 'dislike') and isinstance(target, str) and target in offered
                 and (char, target) not in self.responded and not decision.get('skipped')
                 and decision.get('src') != 'plan')
        if not valid:
            decision.pop('reaction', None)
            decision.pop('reaction_to', None)
            decision['reaction_error'] = {'code': 'reaction_not_eligible', 'value': value, 'target': target}
            return None
        source = self.events[target]
        reaction = {'id': 'reaction_%d' % (len(self.reactions) + 1), 'actor': char,
                    'to': source['actor'], 'value': value, 'reaction_to': target,
                    'turn': turn, 'depth': source['depth'], 'floor_id': source['floor_id'],
                    'source': copy.deepcopy(source)}
        self.responded.add((char, target))
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
    typ, outcome = action['type'], result.get('result')
    recipient = None
    details = {}
    if (typ, outcome) in (('give', 'given'), ('bond', 'done')):
        recipient = result.get('to')
        details = {k: result[k] for k in ('item', 'what', 'form', 'placed') if k in result}
    elif typ == 'use' and outcome == 'healed' and str(action.get('target', '')).startswith('b'):
        recipient = action['target'][1:]
        details = {'heal': result.get('heal', 0), 'item': action.get('item', 'i1')}
    elif result.get('skill_id') and result.get('heal', 0) > 0 and str(action.get('target', '')).startswith('b'):
        typ = 'skill'
        recipient = action['target'][1:]
        details = {k: result[k] for k in ('heal', 'skill_id', 'skill_name')}
    if recipient and any(b['char'] == recipient and b['alive'] and not b['won'] for b in bots):
        rid = ledger.record(typ, bot['char'], [recipient], d.turn,
                            source_action_id=action.get('action_id'), **details)
        if rid:
            result['social_event_id'] = rid

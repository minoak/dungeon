# -*- coding: utf-8 -*-
"""사회 사건 → 실제 관측 → 선택적 반응 → 원정/층 기록. 모델 호출은 모두 가짜 응답이다."""
import contextlib
import copy
import io
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

TMP = tempfile.TemporaryDirectory(prefix='wl_reactions_')
os.environ.update(DUNGEON_ACTION_MODE='compose', DUNGEON_BRAIN_BACKEND='dummy', DUNGEON_GM='0',
                  DUNGEON_STEP_DELAY='0', DUNGEON_TURNS='12', DUNGEON_TOWN='1', DUNGEON_BESTIARY_FILE='',
                  DUNGEON_SEED='7', DUNGEON_STATE_DIR=TMP.name)
os.environ.pop('DUNGEON_PARTY_FILE', None)
import brains
import composed_actions as CA
import dungeon_gm as G
import scenario
import show_runner
import social_reactions as SR

checks = 0


def check(label, ok):
    global checks
    assert ok, label
    checks += 1
    print('  OK ' + label)


def scene(rows=None):
    return scenario.build({'map': rows or ['##############', '#1....2.....>#', '#............#', '##############'],
                           'seed': 7, 'bots': {'1': {'potions': 2}, '2': {'potions': 0}}})


def finish(d, bots):
    out = []
    for _ in range(30):
        if not bots[0].get('order'):
            return out
        d.turn += 1
        out.append(d.step_order(bots[0], bots))
    raise AssertionError('접근 미종료')


book = SR.ReactionBook(1)
a = book.record('bond', '1', ['2'], 1, form='손을 흔든다')
b = book.record('give', '1', ['2'], 1, what='물약')
offered = book.offer('2')
check('같은 사람의 같은 틱 두 사건을 서로 다른 ID로 구분', a != b and len(offered) == 2)
check('제삼자는 받지 않은 사건을 볼 수 없음', book.offer('3') == [])
obs = {'social_events': offered}
valid = SR.parse({'reaction': 'like', 'reaction_to': b}, obs)
reaction = book.consume('2', {**valid, 'type': 'wait', 'src': 'haiku'}, 2)
check('반응은 선택 행동과 독립이고 원래 사건 원문에 연결', reaction['source']['what'] == '물약'
      and reaction['reaction_to'] == b and reaction['actor'] == '2' and reaction['to'] == '1')
check('한 판단 뒤 선택하지 않은 사건을 neutral로 만들지 않음', len(book.reactions) == 1 and book.summary()['unrated'] == 1)
check('같은 사건의 반응을 다시 제출해도 집계하지 않음', book.consume('2', dict(valid), 3) is None
      and book.summary()['total'] == {'like': 1, 'dislike': 0})
for payload in ({'reaction': 'neutral', 'reaction_to': a}, {'reaction': 'like', 'reaction_to': '1'},
                {'reaction': 'like', 'reaction_to': 'social_999'}, {'reaction': 'like'},
                {'reactions': [{'to': a, 'value': 'like'}]}):
    check('잘못된 반응 형식·참조를 분리 기록: ' + str(payload), 'reaction_error' in SR.parse(payload, obs))
check('생략은 오류도 neutral도 아님', SR.parse({}, obs) == {})

for flags in ({'skipped': True}, {'src': 'plan'}):
    guarded = SR.ReactionBook(1)
    target = guarded.record('bond', '1', ['2'], 1, form='손을 흔든다')
    guarded.offer('2')
    check('미실행 결정·미리 정한 계획은 새 반응을 기록하지 않음: ' + str(flags),
          guarded.consume('2', {'reaction': 'like', 'reaction_to': target, **flags}, 2) is None
          and guarded.summary()['total'] == {'like': 0, 'dislike': 0})
bounded = SR.ReactionBook(1)
for i in range(SR.PENDING_MAX + 1):
    bounded.record('say', '1', ['2'], i, text=str(i))
received = bounded.offer('2')
bounded.consume('2', {'type': 'wait'}, 40)
check('보관 상한·다음 판단 1회 기회·미평가 보존', len(received) == SR.PENDING_MAX
      and received[0]['id'] == 'social_2' and bounded.offer('2') == []
      and bounded.summary()['unrated'] == SR.PENDING_MAX + 1)

book = SR.ReactionBook(0)
rid = book.record('say', '1', ['2', '3'], 1, text='함께 가자')
for char, value in [('2', 'like'), ('3', 'dislike')]:
    book.offer(char)
    assert book.consume(char, {'reaction': value, 'reaction_to': rid}, 2)
check('방송 한 사건에 수신자별로 각자 반응 가능', book.summary()['total'] == {'like': 1, 'dislike': 1})
first = book.close_floor(3)
book.start_floor(1, 3)
rid2 = book.record('bond', '2', ['3'], 4, form='등을 두드린다')
book.offer('3'); book.consume('3', {'reaction': 'like', 'reaction_to': rid2}, 5)
second = book.close_floor(6)
book.start_floor(0, 6)
check('마을 재방문도 방문별 층 집계를 분리하고 원정 합은 유지', first['id'] != second['id'] != book.floor['id']
      and first['total'] == {'like': 1, 'dislike': 1} and second['total'] == {'like': 1, 'dislike': 0}
      and book.summary()['total'] == {'like': 2, 'dislike': 1})

d, bots = scene()
o = d.view(bots[0], bots)
a, _ = CA.parse({'type': 'give', 'target': 'b2', 'item': 'i1'}, o)
start = d.act(bots[0], a, bots)
book = SR.book(d)
check('자동 접근 시작에는 사회 사건이 없음', start['result'] == 'approaching' and not book.events)
evs = finish(d, bots)
check('실제 건네기가 완료된 틱에 한 사건만 생성', len(book.events) == 1 and evs[-1]['social_event_id'] in book.events
      and next(iter(book.events.values()))['source_action_id'] == a['action_id'])
d, bots = scene()
o = d.view(bots[0], bots)
a, _ = CA.parse({'type': 'give', 'target': 'b2', 'item': 'i1'}, o)
d.act(bots[0], a, bots); bots[0]['potions'] = 0
finish(d, bots)
check('실패한 접근·건네기는 받은 사건으로 만들지 않음', not SR.book(d).events)

d, bots = scene(['########', '#12...>#', '#......#', '########'])
bots[1]['hp'] = 1
o = d.view(bots[0], bots)
potion, _ = CA.parse({'type': 'use', 'target': 'b2', 'item': 'i1'}, o)
healed = d.act(bots[0], potion, bots)
check('동료에게 실제 물약을 사용한 사건도 회복량과 연결', healed['result'] == 'healed'
      and SR.book(d).events[healed['social_event_id']]['heal'] == bots[1]['maxhp'] - 1)

d, bots = scene(['##################', '#12............3>#', '#................#', '##################'])
inbox, _ = show_runner.deliver_and_hail(d, bots, {'1': '이야기 <script>'}, {'1': '2'})
source = next(iter(SR.book(d).events.values()))
check('말의 사건 ID는 실제 시야 배달을 따름', source['recipients'] == ['2']
      and inbox['2'][0]['social_event_id'] == source['id'] and not inbox['3'])

d, bots = scene(['########', '#12...>#', '#......#', '########'])
o = d.view(bots[1], bots)
o['social_events'] = offered
payload = {'type': 'wait', 'reason': '검증용 판단', 'reaction': 'dislike', 'reaction_to': a['target']}
with patch.object(brains, '_call_claude', return_value=json.dumps(payload)):
    dec = brains.claude_brain(o, '2', bots[1], bots)
check('반응 오류 때문에 올바른 본 행동을 폴백하지 않음', dec['type'] == 'wait' and dec['src'] == 'haiku'
      and dec['reaction_error']['code'] == 'reaction_not_received')
payload.update(type='attack', target='m999', reaction='like', reaction_to=offered[0]['id'])
with patch.object(brains, '_call_claude', return_value=json.dumps(payload)):
    dec = brains.claude_brain(o, '2', bots[1], bots)
check('행동 입력이 불량이어도 실제 모델의 유효 반응은 보존', dec['src'] == 'fallback' and dec['reaction'] == 'like')
wire = brains._wire(o, {'1': '유나', '2': '미나'}, compose=True)
check('관측에는 받은 사건 ID와 내용만 제공', '[social_' in wire and '건네기: 물약' in wire
      and 'reaction_stats' not in wire and 'recipients' not in wire)


def runner():
    captured = []
    state = {'bonded': False}
    original_spawn = G.spawn
    def spawn(d, char, bots, **kwargs):
        bot = original_spawn(d, char, bots, **kwargs)
        bot['potions'] = 2 if char == '1' else 0
        return bot
    def town():
        d, bots = scene()
        d.town, d.depth = True, 0
        return d, {b['char']: (b['x'], b['y']) for b in bots}

    def decide(obs, char, bot=None, roster=None, solo=False):
        captured.append(copy.deepcopy(obs))
        p = {'type': 'search', 'target': 'self'}
        if char == '1' and obs['turn'] == 1:
            p = {'type': 'give', 'target': 'b2', 'item': 'i1', 'say': '필요하면 이걸 써.', 'to': '2', 'say_kind': '잡담'}
        elif char == '1' and not state['bonded']:
            p = {'type': 'bond', 'target': 'b2', 'form': '머리를 거칠게 쓰다듬는다'}
            state['bonded'] = True
        events = obs.get('social_events', [])
        if events:
            source = events[-1]
            p.update(reaction='dislike' if source['type'] == 'bond' else 'like', reaction_to=source['id'])
        act, error = CA.parse(p, obs)
        assert error is None, (p, error)
        return {**act, **SR.parse(p, obs), **{k: p[k] for k in ('say', 'to', 'say_kind') if k in p},
                'reason': '반응 검증용 판단', 'src': 'fixture'}

    with patch.object(show_runner, 'load_party', return_value={c: dict(G.HEROES[c]) for c in ('1', '2')}), \
         patch.object(show_runner, 'TOWN_ON', True), patch.object(show_runner, 'MAX_TURNS', 12), \
         patch.object(show_runner, 'build_town', town), patch.object(brains, 'claude_brain', decide), \
         patch.object(G, 'spawn', spawn), \
         patch.object(brains, '_call_claude', side_effect=AssertionError('실제 모델 호출 금지')), \
         contextlib.redirect_stdout(io.StringIO()):
        show_runner.main()
    text = (Path(TMP.name) / 'stream.jsonl').read_text(encoding='utf-8')
    return [json.loads(line) for line in text.splitlines()], captured


rows, observations = runner()
sources = [e for r in rows for e in r.get('social_events', [])]
reactions = [e for r in rows for e in r.get('reactions', [])]
check('러너에서 말·건네기·친목 세 사건과 세 반응 연결', [e['type'] for e in sources] == ['say', 'give', 'bond']
      and [e['value'] for e in reactions] == ['like', 'like', 'dislike'])
check('반응은 사건 이후 판단에서만 기록', all(r['turn'] > r['source']['turn'] for r in reactions))
check('스트림에 원정 및 층 결산 기록', rows[0]['reaction'] and rows[-1]['reaction_summary']['total'] == {'like': 2, 'dislike': 1}
      and rows[-1]['reaction_floors'][0]['total'] == {'like': 2, 'dislike': 1})
check('봇 스냅샷·기억·관측에 집계와 과거 반응을 되먹이지 않음', all(
    not any(key in json.dumps(o, ensure_ascii=False) for key in ('reaction_stats', 'reaction_summary', '"reaction":', '"reaction_to":'))
    for o in observations))
before = copy.deepcopy(rows)
after, _ = runner()
for data in (before, after):
    data[0].pop('started', None)
check('같은 입력이면 사회 사건 ID·반응·집계까지 결정론', before == after)


def roundtrip_runner():
    """실제 러너의 새 던전·저장된 마을·재입장 경로에서 같은 원장을 이어 쓰는지 검사한다."""
    original_think = brains.think_all
    current = {}
    def think(d, bots, inbox=None, on_error=None):
        current['d'] = d
        return original_think(d, bots, inbox, on_error=on_error)
    def decide(obs, char, bot=None, roster=None, solo=False):
        ledger = SR.book(current['d'])
        floor = ledger.floor
        events = obs.get('social_events', [])
        # 각 방문 첫 두 판단은 말과 반응. 그 뒤 기존 규칙 두뇌로 계단을 이용한다.
        if obs['turn'] <= floor['since'] + 2:
            p = {'type': 'search', 'target': 'self'}
        elif floor['id'] == 'floor_2':
            up = next((f for f in obs['sights']['features'] if f['type'] == 'stairs_up'), None)
            p = ({'type': 'use', 'target': up['id']} if up else {'type': 'goto', 'target': 'b1'})
        else:
            p = CA.fallback(G.dummy_brain(obs, char), obs)
        if obs['turn'] == floor['since'] + 1:
            p.update(say='이번 층에서도 함께 가자.', to='all', say_kind='잡담')
        if events:
            p.update(reaction='like', reaction_to=events[-1]['id'])
        act, error = CA.parse(p, obs)
        assert error is None, (p, error)
        return {**act, **SR.parse(p, obs), **{k: p[k] for k in ('say', 'to', 'say_kind') if k in p},
                'reason': '층 왕복 검증', 'src': 'fixture'}
    with patch.object(show_runner, 'load_party', return_value={c: dict(G.HEROES[c]) for c in ('1', '2')}), \
         patch.multiple(show_runner, TOWN_ON=True, MAX_TURNS=400, DUNGEON_W=40, DUNGEON_H=16,
                        DEPTHS=1, N_MON=0, N_TRAP=0, N_LURK=0), \
         patch.object(brains, 'think_all', think), patch.object(brains, 'claude_brain', decide), \
         patch.object(brains, '_call_claude', side_effect=AssertionError('실제 모델 호출 금지')), \
         patch.object(show_runner.time, 'sleep', lambda _: None), \
         contextlib.redirect_stdout(io.StringIO()):
        show_runner.main()
    return [json.loads(line) for line in (Path(TMP.name) / 'stream.jsonl').read_text(encoding='utf-8').splitlines()]


trip = roundtrip_runner()
levels = [r for r in trip if r['kind'] == 'level']
floors = trip[-1]['reaction_floors']
check('실제 러너 마을→던전→마을→던전 왕복과 종료', [r['depth'] for r in levels] == [0, 1, 0, 1]
      and trip[-1]['outcome'] == 'escaped')
check('새 층 프레임은 0부터, 원정 집계는 이전 층에서 이월', all(
    r['reaction_stats']['floor']['total'] == {'like': 0, 'dislike': 0} for r in levels)
    and levels[-1]['reaction_stats']['run']['total']['like'] > 0)
check('방문별 결산 합과 원정 총합 일치, ID 중복 없음', len({f['id'] for f in floors}) == 4
      and sum(f['total']['like'] for f in floors) == trip[-1]['reaction_summary']['total']['like']
      and all(f['total']['like'] > 0 for f in floors))

if os.environ.get('WL_REACTION_FIXTURE'):
    dest = Path(os.environ['WL_REACTION_FIXTURE'])
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in rows) + '\n', encoding='utf-8')
TMP.cleanup()
print('ALL PASS — verify_reactions (%d checks, 실 LLM 0콜)' % checks)

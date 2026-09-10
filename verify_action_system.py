# -*- coding: utf-8 -*-
"""조합형 본 구현: 실제 세계·모델 파서·계획·자동 접근을 검증한다. 실 LLM 0콜."""
import copy
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

TMP = tempfile.TemporaryDirectory(prefix='wl_actions_')
os.environ.update(DUNGEON_ACTION_MODE='compose', DUNGEON_BRAIN_BACKEND='dummy',
                  DUNGEON_GM='0', DUNGEON_BESTIARY_FILE='', DUNGEON_STATE_DIR=TMP.name)
import brains
import composed_actions as CA
import dungeon_gm as G
import scenario
import show_runner

checks = 0


def check(label, value):
    global checks
    assert value, label
    checks += 1
    print('  OK ' + label)


def scene(rows=None):
    d, bots = scenario.build({'map': rows or [
        '##############', '#1....2.....>#', '#..=..g......#', '#............#', '##############'],
        'seed': 7, 'bots': {'1': {'potions': 3}, '2': {'potions': 0}}})
    return d, bots, d.view(bots[0], bots)


def run(d, bots, obs, payload):
    action, error = CA.parse(payload, obs)
    assert error is None, (payload, error)
    return action, d.act(bots[0], action, bots)


def finish(d, bots, limit=30):
    events = []
    for _ in range(limit):
        if not bots[0].get('order'):
            return events
        d.turn += 1
        events.append(d.step_order(bots[0], bots))
    raise AssertionError('행동이 끝나지 않았다')


d, b, obs = scene()
check('현재 관측에 self·소지품·길을 분리하여 노출', obs['action_schema'] == CA.PROFILE
      and obs['targets'][0]['id'] == 'self' and obs['items'][0]['id'] == 'i1' and obs['ways'])
check('새 참조 목록에 좌표·실물 참조가 새지 않음', all(
    not ({'x', 'y', 'xy', 'origin', 'value'} & set(t)) for t in obs['targets']))
wire = brains._wire(obs, compose=True)
check('동사 10개와 대상 ID를 제시하고 번호 메뉴는 숨김', 'COMMON: ' + ' / '.join(CA.COMMON) in wire
      and '[self]' in wire and '[i1]' in wire and '[w1_1]' in wire and '# 선택지' not in wire)

# 모든 관측 대상과 COMMON의 조합은 문법으로 접수한다. 가능 여부는 실제 세계의 결과다.
matrix = 0
for rid in [t['id'] for t in obs['targets']]:
    for typ in CA.COMMON:
        d, bots, o = scene()
        payload = {'type': typ, 'target': rid, **({'item': 'i1'} if typ == 'give' else {})}
        action, error = CA.parse(payload, o)
        assert error is None, (payload, error)
        result = d.act(bots[0], action, bots)
        assert result['resolution']['type'] == typ, result
        assert result['resolution']['status'] in (None, 'success', 'failed', 'no_effect'), result
        show_runner.act_summary(result)
        brains._last_prose(result)
        G.event_tags(result)
        matrix += 1
check('행동 × 관측 대상 %d조합을 파싱·실행·표시' % matrix, matrix >= 60)

for kind, rows in [('door', ['############', '#1..+..2..>#', '#...#......#', '############']),
                   ('trap', ['########', '#12.^.>#', '#......#', '########'])]:
    for typ in CA.COMMON:
        d, bots, _ = scene(rows)
        for trap in d.traps:
            trap.hidden = False
        o = d.view(bots[0], bots)
        rid = next(t['id'] for t in o['targets'] if t['kind'] == kind)
        a, r = run(d, bots, o, {'type': typ, 'target': rid, **({'item': 'i1'} if typ == 'give' else {})})
        if typ not in ('follow', 'wait', 'rest'):
            events = finish(d, bots)
            r = events[-1] if events else r
        assert r['resolution']['type'] == typ, r
    check(kind + ': 모든 COMMON 조합 접수·실행 및 접근 종료', True)

for recipient in ('self', 'b2', 'm0'):
    d, bots, o = scene(['########', '#12g..>#', '#......#', '########'])
    if recipient == 'm0':
        bots[0]['x'] = 2
        d.monsters[0].hp = 1
    else:
        bots[0 if recipient == 'self' else 1]['hp'] = 1
    o = d.view(bots[0], bots)
    a, r = run(d, bots, o, {'type': 'use', 'target': recipient, 'item': 'i1'})
    check(recipient + ': 물약이 해당 대상에게만 적용되고 한 병 소모', r['result'] == 'healed'
          and r['heal'] > 0 and bots[0]['potions'] == 2 and r['resolution']['status'] == 'success')

d, bots, o = scene(['########', '#12=..>#', '#......#', '########'])
bots[0]['x'], bots[0]['y'] = 3, 2
o = d.view(bots[0], bots)
chest = next(t['id'] for t in o['targets'] if t.get('name') == '상자')
_, r = run(d, bots, o, {'type': 'use', 'target': chest, 'item': 'i1'})
check('물약을 상자에 쓰면 변화 없음·소유권 보존', r['resolution']['status'] == 'no_effect' and bots[0]['potions'] == 3)
_, r = run(d, bots, o, {'type': 'attack', 'target': chest})
check('파괴 기능 없는 사물 공격은 입력 오류가 아님', r['resolution']['status'] == 'no_effect')

d, bots, o = scene()
bots[1]['hp'] = 1
a, r = run(d, bots, o, {'type': 'use', 'target': 'b2', 'item': 'i1'})
events = finish(d, bots)
check('use 자동 접근은 도착 뒤 한 번만 소비·실행', r['result'] == 'approaching' and bots[0]['potions'] == 2
      and sum(e.get('result') == 'healed' for e in events) == 1)
check('접근의 각 틱과 결과가 같은 결정 및 정규 대상에 연결', all(
    e['parent_action_id'] == a['action_id'] and e['resolution']['target'] == 'b2' for e in events)
      and events[-1]['resolution']['status'] == 'success')

d, bots, o = scene()
_, r = run(d, bots, o, {'type': 'search', 'target': 'b2'})
events = finish(d, bots)
check('대상 조사도 접근 후 정보 없음으로 판정', r['result'] == 'approaching'
      and events[-1]['resolution']['status'] == 'no_effect')

d, bots, o = scene()
run(d, bots, o, {'type': 'give', 'target': 'b2', 'item': 'i1'})
bots[0]['potions'] = 0
events = finish(d, bots)
check('접근 중 사라진 소지품은 실행 때 다시 검사', events[-1]['resolution']['status'] == 'failed' and bots[1]['potions'] == 0)

d, bots, o = scene()
way = o['ways'][0]['id']
old_endpoint = bots[0]['_target_refs'][way]['xy']
a, r = run(d, bots, o, {'type': 'explore', 'target': way})
check('길 ID는 선택 당시의 종점을 그대로 사용', tuple(bots[0]['path'][-1]) == old_endpoint)
o2 = d.view(bots[0], bots)
check('새 관측에서 옛 길 ID는 입력 참조 오류', CA.parse({'type': 'explore', 'target': way}, o2)[1] == 'invalid_target')

d, bots, o = scene()
way = o['ways'][0]['id']
bots[0]['plan'] = [{'type': 'explore', 'target': way}]
bots[0]['_plan_refs'] = copy.deepcopy(bots[0]['_target_refs'])
bots[0]['x'] += 1
check('이동 전 길을 then으로 실행하면 계획 파기·재판단', d.plan_step(bots[0], bots) is None
      and bots[0]['last']['type'] == 'plan_broken')

d, bots, o = scene()
bots[0]['plan'] = [{'type': 'explore', 'target': o['ways'][0]['id']}]
bots[0]['_plan_refs'] = copy.deepcopy(bots[0]['_target_refs'])
d.view(bots[0], bots)
check('제자리라도 새 관측에서 옛 길 계획은 만료', d.plan_step(bots[0], bots) is None)

d, bots, o = scene(['########', '#12...>#', '#......#', '########'])
steps = brains._then({'then': [{'type': 'give', 'target': 'b2', 'item': 'i1'},
                             {'type': 'bond', 'target': 'b2', 'form': '손을 흔든다'}]}, o)
check('then도 COMMON 문법과 item·form을 보존', len(steps) == 2 and steps[0]['item'] == 'i1'
      and steps[1]['form'] == '손을 흔든다')
run(d, bots, o, {'type': 'search', 'target': 'self'})
action = {'type': 'search', 'target': 'b1', 'then': steps}
d.act(bots[0], action, bots)
step = d.plan_step(bots[0], bots)
r = d.act(bots[0], {**step, 'src': 'plan'}, bots)
check('then의 건네기가 실제 소유권으로 이어짐', r['result'] == 'given' and bots[1]['potions'] == 1)

d, bots, o = scene(['########', '#12...>#', '#......#', '########'])
with patch.object(d, 'd20', return_value=20):
    _, r = run(d, bots, o, {'type': 'attack', 'target': 'b2'})
check('동료 공격도 실제 피해와 피해자의 경험을 남김', r['hit'] and r['dmg'] > 0
      and bots[1]['last']['type'] == 'hurt' and r['resolution']['target'] == 'b2')

d, bots, o = scene()
payload = {'reason': '긴 이유 ' * 60, 'type': 'give', 'target': 'b999', 'item': 'i1'}
with patch.dict(os.environ, DUNGEON_BRAIN_BACKEND='gemini_api'), \
        patch.object(brains, '_call_claude', return_value=json.dumps(payload, ensure_ascii=False)):
    decision = brains.claude_brain(o, '1', bots[0], bots)
check('참조 오류 원문과 당시 ID를 생략 없이 보존', decision['input_error_detail']['attempted_action'] == payload
      and 'b2' in decision['input_error_detail']['target_ids'])
check('실플레이 입력 오류는 행동을 만들지 않고 보류', decision['src'] == 'error'
      and 'type' not in decision and len(decision['attempt_errors']) == 2)
with patch.object(brains, '_call_claude', return_value='{"reason":"끊긴 JSON'):
    decision = brains.claude_brain(o, '1', bots[0], bots)
check('JSON 자체가 불량인 경우도 실제 원문 보존', decision['input_error_detail']['raw_response'] == '{"reason":"끊긴 JSON')

# 이동 중 별도 대화 관측이 생겨도 접수 당시 장비 참조를 새 장비로 바꾸지 않는다.
d, bots, o = scene()
bots[0]['weapon'] = {'name': '검', 'bonus': 1}
o = d.view(bots[0], bots)
run(d, bots, o, {'type': 'give', 'target': 'b2', 'item': 'i2'})
bots[0]['weapon'] = {'name': '다른 검', 'bonus': 2}
d.view(bots[0], bots)
events = finish(d, bots)
check('이동 중 새 관측이 와도 요청한 장비의 정체를 보존', events[-1]['resolution']['status'] == 'failed'
      and bots[0]['weapon']['name'] == '다른 검')

TMP.cleanup()
print('ALL PASS — verify_action_system (%d checks, 실 LLM 0콜)' % checks)

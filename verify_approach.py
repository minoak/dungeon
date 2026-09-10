# -*- coding: utf-8 -*-
"""자동 접근 검증: 실제 보행/거리/중단/상대 반응/기록 재생. 실 LLM 0콜."""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

TMP = tempfile.TemporaryDirectory(prefix='wl_approach_')
os.environ.update(DUNGEON_ACTION_MODE='compose', DUNGEON_BRAIN_BACKEND='dummy',
                  DUNGEON_GM='0', DUNGEON_STEP_DELAY='0', DUNGEON_TURNS='12',
                  DUNGEON_SEED='7', DUNGEON_BESTIARY_FILE='', DUNGEON_TOWN='1',
                  DUNGEON_STATE_DIR=str(Path(TMP.name) / 'state'))
os.environ.pop('DUNGEON_PARTY_FILE', None)
import dungeon_gm as G
import brains
import show_runner

checks = 0


def check(label, value):
    global checks
    assert value, label
    checks += 1
    print('  OK ' + label)


def scene(rows=None, scan=False):
    d, starts = G.Dungeon.from_ascii(rows or [
        '##############', '#1....2.....>#', '#............#', '##############'], seed=7, scan=scan)
    d.auto_approach = d.give_verb = d.bond_verb = True
    d.relations = d.events = d.trail_on = d.floor_on = True
    bots = []
    for c, xy in sorted(starts.items()):
        b = G.spawn(d, c, bots, sheet=G.HEROES.get(c, G.HEROES['1']))
        b['x'], b['y'] = xy
        bots.append(b)
    for b in bots:
        d.view(b, bots)
    return d, bots


def bone(bot, other, kind):
    return bot.get('relations', {}).get(other, {}).get('bones', {}).get(kind, {}).get('n', 0)


def walk(d, bots, limit=40):
    out = []
    for _ in range(limit):
        if not bots[0].get('order'):
            return out
        d.turn += 1
        out.append(d.step_order(bots[0], bots))
    raise AssertionError('접근이 끝나지 않았다: %r' % out)


d, bots = scene()
a = {'type': 'bond', 'target': 'b2', 'form': '어깨를 가볍게 두드린다'}
r = d.act(bots[0], a, bots)
check('접근 시작은 친목 성공도 순간이동도 아니다', r['result'] == 'approaching'
      and bots[0]['x'] == 1 and bone(bots[0], '2', 'bond') == 0)
check('관전 스냅샷에 원래 의도를 보존', G.bot_snapshot(bots[0])['approach']['action_id'] == a['action_id'])
events = walk(d, bots)
check('결정 한 번으로 4걸음 접근 뒤 친목 한 번', len(events) == 5 and events[-1]['result'] == 'done'
      and all(e['type'] == 'walk' for e in events[:-1]) and bone(bots[0], '2', 'bond') == 1
      and bone(bots[1], '1', 'bond') == 1 and not bots[0].get('approach'))
check('접근 보행과 결과가 원래 결정에 연결', all(e['parent_action_id'] == a['action_id'] for e in events))
check('친목 수신에 자유 서술 원문 유지', bots[1]['last']['form'] == a['form'])
check('접근 시작을 헛손질/친목 횟수로 세지 않음', G.event_tags(r)[0][0] == 'start'
      and bots[0]['floor']['n'].get('친목', 0) == 1)
check('로그와 봇 관측이 접근 시작을 설명', '접근' in show_runner.act_summary(r)
      and '접근' in brains._last_prose(r))

d, bots = scene()
bots[1]['x'], bots[1]['y'] = 2, 2
r = d.act(bots[0], {'type': 'bond', 'target': 'b2'}, bots)
check('대각 한 칸 친목은 이동 없이 즉시 실행', r['result'] == 'done' and not bots[0].get('order'))

d, bots = scene()
bots[0]['potions'] = 1
a = {'type': 'give', 'target': 'b2', 'item': 'potion'}
d.act(bots[0], a, bots)
events = walk(d, bots)
check('물약은 도착 후 한 번만 이동', events[-1]['result'] == 'given'
      and bots[0]['potions'] == 0 and bots[1]['potions'] == 1
      and bone(bots[0], '2', 'gave') == 1)

d, bots = scene()
bots[0]['potions'] = 1
d.act(bots[0], {'type': 'give', 'target': 'b2', 'item': 'potion'}, bots)
bots[0]['potions'] = 0
events = walk(d, bots)
check('실행 직전에 소지품을 다시 확인', events[-1]['result'] == 'nothing'
      and bots[1]['potions'] == 0 and bone(bots[0], '2', 'gave') == 0)

d, bots = scene()
d.act(bots[0], {'type': 'bond', 'target': 'b2'}, bots)
d.turn += 1
d.step_order(bots[0], bots)
bots[1]['x'] = 7
events = walk(d, bots)
check('보이는 동료가 이동하면 새 위치의 곁으로 접근', events[-1]['result'] == 'done'
      and bots[0]['x'] == 6)

for loss in ('dead', 'out_of_sight'):
    d, bots = scene(['########################', '#1...2................>#', '########################'])
    d.act(bots[0], {'type': 'bond', 'target': 'b2'}, bots)
    if loss == 'dead':
        bots[1]['alive'] = False
    else:
        bots[1]['x'] = 20
    events = walk(d, bots)
    check(loss + ': 대상을 잃으면 원래 행동을 취소', events[-1]['result'] == 'lost'
          and bots[0]['x'] == 1 and not bots[0].get('approach') and bone(bots[0], '2', 'bond') == 0)

d, bots = scene(['########################', '#1..................2.>#', '########################'])
r = d.act(bots[0], {'type': 'bond', 'target': 'b2'}, bots)
check('모르는 실재 ID로 접근 불가', r['result'] == 'no_target' and not bots[0].get('order'))

d, bots = scene(['##############', '#1....=.....>#', '#............#', '##############'])
chest = next(f for f in d.features.values() if f.type == 'chest')
d.act(bots[0], {'type': 'interact', 'target': 'f%d' % chest.id}, bots)
events = walk(d, bots)
check('사물 사용도 인접까지만 접근 후 실행', events[-1]['type'] == 'interact'
      and events[-1]['result'] in ('chest_loot', 'chest_trap')
      and abs(bots[0]['x'] - chest.x) + abs(bots[0]['y'] - chest.y) == 1)

d, bots = scene(['##############', '#1....=.....>#', '#............#', '##############'])
chest = next(f for f in d.features.values() if f.type == 'chest')
d.act(bots[0], {'type': 'interact', 'target': 'f%d' % chest.id}, bots)
del d.features[chest.id]
check('사물이 먼저 소비되면 사용하지 않음', walk(d, bots)[-1]['result'] == 'lost')

d, bots = scene(['##########', '#1....>..#', '##########'])
d.solo = True
d.act(bots[0], {'type': 'interact', 'target': 'exit'}, bots)
events = walk(d, bots)
check('계단에 접근한 뒤 기존 하강 조건으로 판정', events[-1]['result'] == 'exit' and bots[0]['won'])

for radius in (1, 3):
    d, bots = scene(['##############', '#1....g.....>#', '#............#', '##############'])
    bots[0]['atk_range'] = radius
    d.act(bots[0], {'type': 'attack', 'target': 'm0'}, bots)
    events = walk(d, bots)
    mon = d.monsters[0]
    check('공격 사거리 %d까지만 접근 후 공격' % radius, events[-1]['result'] == 'attack'
          and abs(mon.x - bots[0]['x']) + abs(mon.y - bots[0]['y']) == radius)

d, bots = scene()
d.hail = True
a = {'type': 'bond', 'target': 'b2', 'then': [{'type': 'search'}]}
d.act(bots[0], a, bots)
d.hail_stop(bots[0], ['2'])
check('제안으로 멈추면 접근과 뒤의 계획을 취소', not bots[0].get('approach')
      and not bots[0]['order'] and not bots[0]['plan']
      and bots[0]['last']['interrupted_action_id'] == a['action_id'])
d.act(bots[0], {'type': 'search'}, bots)
check('중단 뒤 다른 행동에서 옛 친목이 살아나지 않음', bone(bots[0], '2', 'bond') == 0)

d, bots = scene(['##############', '#1...2......>#', '#g...........#', '##############'])
a = {'type': 'bond', 'target': 'b2'}
d.act(bots[0], a, bots)
with patch.object(d, 'd20', return_value=20):
    hit = d._monster_attack(d.monsters[0], bots[0], bots)
check('피격이 접근을 취소하고 원래 의도와 연결', not bots[0].get('approach')
      and not bots[0]['order'] and hit['interrupted_action_id'] == a['action_id'])

d, bots = scene(['##############', '#1...2..=...>#', '##############'], scan=True)
d.act(bots[0], {'type': 'bond', 'target': 'b2'}, bots)
events = walk(d, bots)
check('접근 중 새 사물 발견이면 접촉 전에 재판단', events[-1]['result'] == 'sighted'
      and events[-1]['approach_status'] == 'interrupted' and bone(bots[0], '2', 'bond') == 0)

d, bots = scene(['##########', '#1.#2...>#', '##########'])
d.ally_sight = True
r = d.act(bots[0], {'type': 'bond', 'target': 'b2'}, bots)
check('벽으로 막힌 대상에게 탐색으로 바꿔 걷지 않음', r['result'] == 'no_path'
      and not bots[0].get('order') and '길이 없다' in show_runner.act_summary(r))

d, bots = scene()
d.auto_approach = False
r = d.act(bots[0], {'type': 'bond', 'target': 'b2'}, bots)
check('기존 모드는 거리 실패 계약 유지', r['result'] == 'too_far' and 'parent_action_id' not in r)

# 입력 결정 + 엔진 자동보행으로 스트림을 다시 만들 수 있어야 한다.
def replay():
    d, bots = scene()
    a = {'type': 'bond', 'target': 'b2', 'form': '어깨를 두드린다'}
    events = [d.act(bots[0], a, bots)] + walk(d, bots)
    return a, events, [G.bot_snapshot(b) for b in bots]

check('같은 시드·결정으로 접근 ID와 결과까지 재현', replay() == replay())

# 실제 러너 경로: 접근 종료 시 open_acts에 등록하고 다음 결정의 반응을 기록하는지 확인.
def run_runner():
    captured = {}
    def town():
        d, bots = scene()
        d.town = True
        captured['d'] = d
        return d, {b['char']: (b['x'], b['y']) for b in bots}

    def decide(d, bots, inbox=None, on_error=None):
        out = {}
        for b in bots:
            if b.get('order') or not b['alive'] or b['won']:
                continue
            if b['char'] == '1' and d.turn == 1:
                out['1'] = {'type': 'bond', 'target': 'b2', 'form': '어깨를 두드린다', 'src': 'haiku'}
            elif b['char'] == '2':
                out['2'] = {'type': 'search', 'say': '고마워!', 'to': '1', 'say_kind': '잡담', 'src': 'haiku'}
            else:
                out[b['char']] = {'type': 'search', 'src': 'haiku'}
        return out

    sheets = {c: dict(G.HEROES[c]) for c in ('1', '2')}
    with patch.object(show_runner, 'load_party', return_value=sheets), patch.object(show_runner, 'TOWN_ON', True), \
         patch.object(show_runner, 'MAX_TURNS', 9), patch.object(show_runner, 'build_town', town), \
         patch.object(brains, 'think_all', decide), contextlib.redirect_stdout(io.StringIO()):
        show_runner.main()
    return [json.loads(s) for s in (Path(show_runner.STATE) / 'stream.jsonl').read_text(encoding='utf-8').splitlines()]

rows = run_runner()
evs = [(r['turn'], e) for r in rows if r.get('kind') == 'tick' for e in r.get('events', [])]
done = [(t, e) for t, e in evs if e.get('type') == 'bond' and e.get('result') == 'done']
replies = [(r['turn'], x) for r in rows for x in r.get('replies', []) if x.get('kind') == '친목']
check('러너의 자동 접근 완료도 친목 반응으로 기록', len(done) == 1 and len(replies) == 1
      and replies[0][0] > done[0][0] and replies[0][1]['how'] == '말')
decs = [d for r in rows for d in r.get('decisions', {}).values() if d.get('type') == 'bond']
check('러너 스트림에서 친목 결정 1회와 보행을 구분', len(decs) == 1
      and done[0][1]['parent_action_id'] == decs[0]['action_id']
      and not any(d.get('type') == 'goto' for r in rows for d in r.get('decisions', {}).values()))

TMP.cleanup()
print('ALL PASS — verify_approach (%d checks, 실 LLM 0콜)' % checks)

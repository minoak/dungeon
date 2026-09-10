# -*- coding: utf-8 -*-
"""실제 엔진 경로로 거리·상태·비용·중단·획득·파싱 검사. LLM 0콜."""
import copy
import json
import os
from unittest.mock import patch

os.environ.update(DUNGEON_ACTION_MODE='compose', DUNGEON_BRAIN_BACKEND='dummy')
import dungeon_gm as G
import brains
import skill_schema as S

checks = 0


def check(label, value):
    global checks
    assert value, label
    checks += 1
    print('  OK ' + label)


def scene(rows=None, trpg=False, skills=True):
    d, starts = G.Dungeon.from_ascii(rows or ['############', '#12a......>#', '#..........#', '############'],
                                    monsters={'a': {'hp': 40, 'state': 'HUNTING', 'atk': 0, 'ac': 10}})
    d.composed_actions = d.auto_approach = True
    d.skills, d.trpg_combat = skills, trpg
    d.rest_verb = d.wait_verb = d.events = d.relations = d.graves = True
    bots = []
    for char, xy in starts.items():
        b = G.spawn(d, char, bots)
        b['x'], b['y'] = xy
        if skills:
            b['skills'] = list(S.PRESETS)
        bots.append(b)
    for b in bots:
        d.view(b, bots)
    d.d20 = lambda: 18
    return d, bots


def act(d, bots, typ, target='self', who=0):
    b = bots[who]
    d.view(b, bots)
    d.turn += 1
    return d.act(b, {'type': typ, 'target': target}, bots)


def finish(d, bots, who=0):
    out = []
    for _ in range(40):
        if not bots[who].get('order'):
            return out
        d.turn += 1
        out.append(d.step_order(bots[who], bots))
    raise AssertionError('접근/대기 미완료')


d, bots = scene()
obs = d.view(bots[0], bots)
check('보유 스킬 type+target 파싱', G.CA.parse({'type': 'push_slash', 'target': 'm0'}, obs)[1] is None)
check('존재하지 않는 스킬 거절', G.CA.parse({'type': 'fireball', 'target': 'm0'}, obs)[1] == 'invalid_type')
check('관측의 SKILL만 짧게 노출', 'SKILL:' in brains._wire(obs, compose=True) and 'cost' not in brains._wire(obs, compose=True))
with patch.object(brains, '_call_claude', return_value='{"reason":"검증","type":"push_slash","target":"m0"}') as model:
    decision = brains.claude_brain(obs, '1', bot=bots[0], roster=bots)
    prompt = model.call_args.args[0]
check('실제 두뇌 파서와 프롬프트 COMMON/SKILL 허용', decision['type'] == 'push_slash'
      and 'COMMON 또는 SKILL' in prompt)
bots[0]['skills'] = ['first_aid']
r = act(d, bots, 'push_slash', 'm0')
check('직접 엔진 호출도 보유 여부 검사', r['reason_code'] == 'invalid_skill' and not bots[0]['order'])
d, bots = scene(skills=False)
check('OFF 관측·스냅샷에 스킬 없음', 'skills' not in d.view(bots[0], bots) and 'skills' not in G.bot_snapshot(bots[0]))

d, bots = scene(['############', '#1...a....>#', '#2.........#', '############'])
a = {'type': 'push_slash', 'target': 'm0'}
r = d.act(bots[0], a, bots)
check('스킬 사거리까지 접근만 시작', r['result'] == 'approaching' and r['required_range'] == 1
      and not bots[0]['skill_cooldowns'])
steps = finish(d, bots)
check('접근 보행은 비용·대기시간을 소비하지 않고 마지막에 한 번 실행',
      sum(e.get('skill_spent', False) for e in steps) == 1 and bots[0]['skill_cooldowns']['push_slash'] == 2
      and d.monsters[0].hp == 36 and d.monsters[0].x == 6)
check('모든 보행과 결과에 원래 결정 ID', all(e['parent_action_id'] == a['action_id'] for e in steps))
r = act(d, bots, 'push_slash', 'm0')
check('대기 중 재시도는 RNG·HP·대기시간 변경 없음', r['reason_code'] == 'cooldown'
      and bots[0]['skill_cooldowns']['push_slash'] == 2)
act(d, bots, 'search')
check('유효한 다른 행동 완료마다 1 감소', bots[0]['skill_cooldowns']['push_slash'] == 1)
act(d, bots, 'search')
check('두 행동 완료 뒤 다시 사용 가능', bots[0]['skill_cooldowns']['push_slash'] == 0)

for lost in ('dead', 'hidden', 'out_of_sight'):
    d, bots = scene(['#####################', '#1...a............>.#', '#2..................#', '#####################'])
    act(d, bots, 'push_slash', 'm0')
    if lost == 'dead': d.monsters[0].alive = False
    if lost == 'hidden': d.monsters[0].concealed = True
    if lost == 'out_of_sight': d.monsters[0].x = 18
    r = finish(d, bots)[-1]
    check(lost + ' 접근 취소·비용 미소비', r['result'] == 'lost' and not bots[0]['skill_cooldowns'])

d, bots = scene(['##########', '#1..a...>#', '#2.......#', '##########'])
act(d, bots, 'push_slash', 'm0')
d._monster_attack(d.monsters[0], bots[0], bots)
check('피격이 스킬 접근 중단', not bots[0].get('approach') and not bots[0]['order'] and not bots[0]['skill_cooldowns'])

d, bots = scene(['##########', '#1a#....>#', '#2.......#', '##########'])
r = act(d, bots, 'push_slash', 'm0')
check('벽 뒤로 밀지 않으며 피해는 보존', r['effects'][1]['reason'] == 'blocked' and d.monsters[0].hp == 36)
d, bots = scene(['##########', '#1a2....>#', '##########'])
r = act(d, bots, 'push_slash', 'm0')
check('다른 사람 위로 밀지 않음', r['effects'][1]['reason'] == 'blocked')

d, bots = scene(['##########', '#12.....>#', '#........#', '##########'])
act(d, bots, 'push_slash', 'b2')
check('밀린 사람의 관측·궤적에 절대 좌표를 출력하지 않음',
      brains._last_prose(bots[1]['last']) == '스킬에 의해 한 칸 밀려났다'
      and G.event_tags(bots[1]['last']) == [('hurt', '밀림', '스킬에 의해 한 칸 밀려났다')])

d, bots = scene(['##########', '#1a.....>#', '#2.......#', '##########'])
bots[0]['hp'] = 2
state = d.rng.getstate()
r = act(d, bots, 'heavy_strike', 'm0')
check('HP 비용으로 자살하지 않음·실패 때 무소비', r['reason_code'] == 'insufficient_hp' and state == d.rng.getstate())
bots[0]['hp'] = 10
d.d20 = lambda: 1
r = act(d, bots, 'heavy_strike', 'm0')
check('유효한 빗나감도 HP·대기시간 지불', r['result'] == 'skill_missed' and bots[0]['hp'] == 8
      and bots[0]['skill_cooldowns']['heavy_strike'] == 2)

d, bots = scene()
bots[1]['hp'] = bots[1]['maxhp'] - 2
r = act(d, bots, 'first_aid', 'b2')
check('치유는 최대 HP까지만', r['heal'] == 2 and bots[1]['hp'] == bots[1]['maxhp'])
check('치유받은 사람의 다음 반응 기회 연결', r.get('social_event_id') and
      G.SR.book(d).offer('2')[0]['skill_id'] == 'first_aid')
check('회복 관측은 물약으로 잘못 부르지 않음', '응급처치' in brains._last_prose(bots[1]['last']))

d, bots = scene(['##########', '#1a.....>#', '#2.......#', '##########'])
r = act(d, bots, 'bleeding_cut', 'm0')
check('출혈 부착·보이는 몬스터 상태 노출', '출혈' in d.monsters[0].skill_status
      and d.view(bots[0], bots)['sights']['monsters'][0]['status'] == ['출혈'])
mon = d.monsters[0]
hp = mon.hp
for _ in range(G.BLEED_STEPS):
    mon.x += 1
    G.SK.monster_status_after_move(d, bots, {mon.id: (mon.x - 1, mon.y)})
check('몬스터 출혈도 기존 걸음 주기당 HP1', mon.hp == hp - 1)
d, bots = scene()
act(d, bots, 'bleeding_cut', 'b2')
check('사람에게도 기존 출혈 태그 사용', '출혈' in bots[1]['status'])

d, bots = scene(['##########', '#1a.....>#', '#2.......#', '##########'], trpg=True)
with patch.object(d, 'd20', side_effect=[18, 20]):
    r = act(d, bots, 'push_slash', 'm0')
check('명중과 밀침 내성은 독립 판정', r['hit'] and r['effects'][1]['reason'] == 'saved'
      and r['effects'][1]['save']['dc'] == 13)
check('TRPG ON 피해 주사위 실측 기록', r['effects'][0]['rolls'] and r['effects'][0]['mode'] == 'dice')
check('내성/효과도 부모 결정에 연결', all(e['parent_action_id'] == r['parent_action_id']
      for e in G.SK.stream_records([r])))

d, bots = scene(['##########', '#1a.....>#', '#2.......#', '##########'], trpg=True, skills=False)
r = act(d, bots, 'attack', 'm0')
check('TRPG 단독 ON 가능', 'combat_roll' in r and 'damage_roll' in r and 'skills' not in bots[0])

d, bots = scene()
special = copy.deepcopy(S.PRESETS['bleeding_cut'])
special.update(id='conditional_cut', conditions=['target_bleeding'], penalties=[{'type': 'self_status', 'status': 'slow'}])
special['cost'] = S.skill_cost(special)
bots[0]['generated_skills'][special['id']] = special
bots[0]['skills'].append(special['id'])
r = act(d, bots, special['id'], 'b2')
check('발동 조건을 실행 전 검사', r['reason_code'] == 'target_not_bleeding' and not bots[0]['status'])
act(d, bots, 'bleeding_cut', 'b2')
r = act(d, bots, special['id'], 'b2')
check('조건 충족 후 self_status 패널티', r.get('skill_spent') and '둔화' in bots[0]['status'])

d, bots = scene()
far = copy.deepcopy(S.PRESETS['first_aid'])
far.update(id='ranged_aid', range=5)
far['cost'] = S.skill_cost(far)
bots[0]['generated_skills'][far['id']] = far
bots[0]['skills'].append(far['id'])
bots[1]['x'] = 6
bots[1]['hp'] -= 4
r = act(d, bots, far['id'], 'b2')
check('스킬 고유 사거리 사용', r.get('heal') == 4 and not bots[0]['order'])

d, bots = scene()
d.random_skill = True
d.depth = 2
check('2층에서는 획득하지 않음', not G.SK.acquire(d, bots))
d.depth = 3
first = G.SK.acquire(d, bots)
check('3층에서 인당 한 번, 전투 RNG 불변', len(first) == 2 and not G.SK.acquire(d, bots))
d.depth = 4
next_bot = G.spawn(d, '1', [])
G.SK.inherit(d, bots[0], next_bot)
check('층 전이에 보유·생성 규칙·대기시간 보존', G.SK.snapshot(bots[0]) == G.SK.snapshot(next_bot))
check('스냅샷은 독립 사본', G.SK.snapshot(bots[0])['skills'] is not bots[0]['skills'])
print('ALL PASS — verify_skill_effects (%d checks)' % checks)

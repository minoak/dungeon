# -*- coding: utf-8 -*-
"""알파 OFF의 행동·관측·상태·RNG를 compose-v0.4 기준선(78fbe84)의 해시와 대조한다."""
import hashlib
import json
import os

os.environ['DUNGEON_SIGHT'] = '5'
import dungeon_gm as G


def trace(seed):
    d = G.Dungeon(seed=seed, w=44, h=18, n_monsters=2, n_traps=3, n_lurkers=1,
                  scan=True, loops=True, status=True, rest_verb=True, events=True, relations=True,
                  auto_approach=True, composed_actions=True)
    bots = []
    for char in ('1', '2'):
        bots.append(G.spawn(d, char, bots))
    records = [{'level': d.level_snapshot(), 'bots': [G.bot_snapshot(b) for b in bots]}]
    for turn in range(1, 81):
        d.turn = turn
        results, observations = [], []
        for b in bots:
            if not b['alive'] or b['won']:
                continue
            if b.get('order'):
                results.append(d.step_order(b, bots))
            else:
                obs = d.view(b, bots)
                observations.append(obs)
                action = G.CA.fallback(G.dummy_brain(obs, b['char']), obs)
                results.append(d.act(b, action, bots))
        results.extend(d.monster_turn(bots))
        records.append({'turn': turn, 'observations': observations, 'events': results,
                        'bots': [G.bot_snapshot(b) for b in bots], 'monsters': [m.as_dict() for m in d.monsters]})
    records.append({'rng_state': d.rng.getstate()})
    return hashlib.sha256(json.dumps(records, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


EXPECTED = {
    7: '3f990af78965b011453bfe379e9c25d87f1dd518b05873cb2f4b6233d78e3b7c',
    37: 'f84670885c17aab6b650bae743fd89b5d40e7a5282da8855c62a0aeaf63ce6cf',
    217: 'c0e2631329c3e00b859f15a849e4882e69ea69fd4e5c31c658c22be8e162cb80',
}


if __name__ == '__main__':
    for seed in (7, 37, 217):
        actual = trace(seed)
        assert actual == EXPECTED[seed], (seed, actual, EXPECTED[seed])
        print('  OK seed=%d: 기준선과 관측·결과·난수 상태 일치' % seed)
    print('ALL PASS — verify_skill_off (3 seeds × 80 ticks, 78fbe84 기준선)')

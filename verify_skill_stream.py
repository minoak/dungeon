# -*- coding: utf-8 -*-
"""러너 1~5층·스위치 조합·기록한 결정 재생. 고정 장면/가짜 판단이며 재미·밸런스 실험이 아니다."""
import contextlib
import copy
import io
import itertools
import json
import os
import sys
from pathlib import Path
import tempfile
from unittest.mock import patch

TMP = tempfile.TemporaryDirectory(prefix='wl_skill_stream_')
os.environ.update(DUNGEON_ACTION_MODE='compose', DUNGEON_BRAIN_BACKEND='dummy',
                  DUNGEON_GM='0', DUNGEON_STEP_DELAY='0', DUNGEON_BESTIARY_FILE='',
                  DUNGEON_STATE_DIR=TMP.name, DUNGEON_SKILLS='0', DUNGEON_TRPG_COMBAT='0',
                  DUNGEON_RANDOM_SKILL='0')
import dungeon_gm as G
import brains
import show_runner as R
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools"))   # 2026-09-13 정리: 도구는 tools/
import analyze_skills

checks = 0


def check(label, value):
    global checks
    assert value, label
    checks += 1
    print('  OK ' + label)


def run(flags=(True, True, True), replay=None):
    original_spawn = G.spawn
    counts, observations = {}, []
    sheets = {c: {**copy.deepcopy(G.HEROES[c]), 'hp': 80,
                  'skills': ['push_slash', 'first_aid', 'bleeding_cut']} for c in ('1', '2')}

    def authored_init(self, **kwargs):
        d, starts = G.Dungeon.from_ascii(['############', '#12.a....>.#', '#..........#', '############'],
                                        seed=kwargs['seed'], depth=kwargs.get('depth', 1),
                                        monsters={'a': {'hp': 8, 'atk': 0, 'dmg': 1, 'ac': 8, 'state': 'HUNTING'}})
        self.__dict__.update(d.__dict__)
        for key, value in kwargs.items():
            if key in ('composed_actions', 'auto_approach', 'skills', 'trpg_combat', 'random_skill',
                       'events', 'graves', 'status', 'rest_verb', 'relations', 'wait_verb'):
                setattr(self, key, value)
        self._fixture_starts = starts

    def spawn(d, char, bots, **kwargs):
        b = original_spawn(d, char, bots, **kwargs)
        b['x'], b['y'] = d._fixture_starts[char]
        b['hp'] -= 5
        return b

    def decide(obs, char, bot=None, roster=None, solo=False):
        observations.append(copy.deepcopy(obs))
        if replay is not None:
            return copy.deepcopy(replay[obs['turn']][char])
        key = (obs['depth'], char)
        count = counts.get(key, 0)
        counts[key] = count + 1
        skills = {s['id']: s for s in obs.get('skills', [])}
        monsters = obs['sights']['monsters']
        if count == 0 and skills:
            p = {'type': 'first_aid', 'target': 'self'}
        elif count == 1 and skills and monsters:
            p = {'type': 'push_slash' if char == '1' else 'bleeding_cut', 'target': monsters[0]['id']}
        elif count == 2 and any(s.startswith('random_') for s in skills):
            sid = next(s for s in skills if s.startswith('random_'))
            spec = bot['generated_skills'][sid]
            healing = spec['effects'][0]['type'] == 'heal'
            p = ({'type': sid, 'target': 'self' if healing else monsters[0]['id']}
                 if healing or monsters else G.CA.fallback(G.dummy_brain(obs, char), obs))
        else:
            p = G.CA.fallback(G.dummy_brain(obs, char), obs)
        parsed, error = G.CA.parse(p, obs)
        assert not error, (p, error)
        return {**parsed, 'reason': '기술 검증용 고정 판단', 'src': 'fixture'}

    with patch.multiple(R, TOWN_ON=False, SOLO_ON=False, MAX_TURNS=400, DEPTHS=5,
                        SKILLS_ON=flags[0], TRPG_COMBAT_ON=flags[1], RANDOM_SKILL_ON=flags[2],
                        DUNGEON_SEED=37, STEP_DELAY=0, GM_ON=False), \
         patch.object(R, 'load_party', return_value=copy.deepcopy(sheets)), \
         patch.object(G.Dungeon, '__init__', authored_init), patch.object(G, 'spawn', spawn), \
         patch.object(brains, 'claude_brain', decide), \
         patch.object(brains, '_call_claude', side_effect=AssertionError('실제 LLM 호출 금지')), \
         patch.object(R.time, 'sleep', lambda _: None), contextlib.redirect_stdout(io.StringIO()):
        R.main()
    rows = [json.loads(line) for line in (Path(TMP.name) / 'stream.jsonl').read_text(encoding='utf-8').splitlines()]
    rows[0].pop('started', None)
    return rows, observations


rows, observations = run()
levels = [r for r in rows if r['kind'] == 'level']
check('실제 러너의 1~5층 전이 및 탈출', [r['depth'] for r in levels] == [1, 2, 3, 4, 5]
      and rows[-1]['outcome'] == 'escaped')
acquisitions = [a for level in levels for a in level.get('skill_acquisitions', [])]
check('3층에서만 인당 한 개 획득', len(acquisitions) == 2 and all(a['depth'] == 3 for a in acquisitions))
check('4·5층에 생성 스킬 이월', all(len(p['generated_skills']) == 1 for level in levels[3:] for p in level['party']))
check('획득 이후 관측에 생성 스킬 노출', any(any(s['id'].startswith('random_') for s in o.get('skills', [])) for o in observations))
stats = analyze_skills.summarize(Path(TMP.name) / 'stream.jsonl')
expected = sum(len([d for d in r.get('decisions', {}).values() if not d.get('skipped')]) for r in rows)
check('분석기는 접근 걸음을 추가 결정으로 세지 않음', stats['overall']['decisions'] == expected
      and stats['overall']['skill_ratio'] > 0 and len(stats['acquisition']) == 2)
ids = {d['action_id'] for r in rows for d in r.get('decisions', {}).values() if d.get('action_id')}
records = [e for r in rows for e in r.get('skill_events', [])]
check('굴림·효과·최종 판정 모두 기존 결정 ID 참조', records and all(e['parent_action_id'] in ids for e in records))
check('스트림에 세 단계 기록', {'skill_roll', 'skill_effect', 'resolution'} <= {e['type'] for e in records})
for r in rows:
    if r['kind'] != 'tick':
        continue
    for e in r.get('events', []):
        if e.get('skill_spent'):
            assert e['resolution']['phase'] == 'resolved'
check('미완료 접근을 스킬 실행으로 세지 않음', True)
replay = {r['turn']: r['decisions'] for r in rows if r['kind'] == 'tick'}
again, _ = run(replay=replay)
check('시드+저장된 결정으로 스트림 전체 재현', json.dumps(rows, ensure_ascii=False) == json.dumps(again, ensure_ascii=False))
for flags in itertools.product((False, True), repeat=3):
    data, obs = run(flags)
    check('스위치 %s 조합 완주' % (flags,), data[-1]['outcome'] == 'escaped')
    assert all(('skills' in o) == flags[0] for o in obs)
    grants = [a for r in data for a in r.get('skill_acquisitions', [])]
    assert bool(grants) == (flags[0] and flags[2])
    if not any(flags):
        assert 'alpha' not in data[0] and not any('skill_events' in r for r in data)
check('모든 플래그 조합의 실제 노출·획득·OFF 무필드 확인', True)
if os.environ.get('WL_SKILL_FIXTURE'):
    dest = Path(os.environ['WL_SKILL_FIXTURE'])
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in rows) + '\n', encoding='utf-8')
TMP.cleanup()
print('ALL PASS — verify_skill_stream (%d checks, 실 LLM 0콜)' % checks)

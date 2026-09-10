# -*- coding: utf-8 -*-
"""실 LLM 0콜: 재판단 한도·의도 보존·세계 정지·HTTP 재시도·같은 원정 재개를 검증한다."""
import json
import copy
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parent


def run_fixture(state):
    """브라우저/통합 검증용 실제 러너. allow-brain 파일이 생길 때까지 1번만 잘못된 물건을 고른다."""
    state = Path(state)
    os.environ.update(DUNGEON_STATE_DIR=str(state), DUNGEON_ACTION_MODE='compose',
                      DUNGEON_BRAIN_BACKEND='gemini_api', DUNGEON_GM='0', DUNGEON_TURNS='2',
                      DUNGEON_W='40', DUNGEON_H='16', DUNGEON_DEPTHS='1', DUNGEON_SEED='7',
                      DUNGEON_MONSTERS='1', DUNGEON_TRAPS='0', DUNGEON_LURKERS='0',
                      DUNGEON_STEP_DELAY='0', DUNGEON_BESTIARY_FILE='',
                      DUNGEON_SKILLS='1', DUNGEON_TRPG_COMBAT='1', DUNGEON_RANDOM_SKILL='1',
                      DUNGEON_PARTY_FILE=str(ROOT / 'party.json'))
    import brains
    local = threading.local()
    original = brains.claude_brain
    counts = {}

    def decide(obs, char='?', bot=None, roster=None, solo=False):
        local.char = char
        return original(obs, char, bot, roster, solo)

    def call(prompt, model='haiku'):
        char = local.char
        counts[char] = counts.get(char, 0) + 1
        (state / ('calls-' + char)).write_text(str(counts[char]), encoding='utf-8')
        if char == '1' and not (state / 'allow-brain').exists():
            return json.dumps({'type': 'use', 'target': 'self', 'item': 'missing',
                               'reason': '치료할 생각', 'say': '실패한 발화', 'note': '실패한 기억'})
        return '{"type":"search","target":"self","reason":"살핀다","note":"수락된 기억"}'

    brains.claude_brain = decide
    brains._call_claude = call
    # 모킹 솔기를 우회한 구현은 실제 백엔드까지 가지 못한다.
    def tripwire(*args, **kwargs):
        raise AssertionError('검증 중 실제 백엔드 호출 금지')
    brains._call_gemini = brains._call_cli = brains._call_anthropic = tripwire
    import show_runner
    show_runner.main()


if __name__ == '__main__' and len(sys.argv) == 3 and sys.argv[1] == '--fixture':
    run_fixture(sys.argv[2])
    raise SystemExit(0)

os.environ['DUNGEON_ACTION_MODE'] = 'compose'
import brains
import scenario
import launcher
import run_control


def scene():
    d, bots = scenario.build({'map': ['############', '#12.g.....>#', '#..........#', '############'],
                             'seed': 7, 'bots': {'1': {'potions': 0}, '2': {'potions': 0}}})
    d.composed_actions = d.auto_approach = True
    return d, bots, d.view(bots[0], bots)


class BrainPauseTests(unittest.TestCase):
    def test_invalid_intents_retry_with_same_observation_without_rule_brain(self):
        for action, code in [({'type': 'attack', 'target': 'm999'}, 'invalid_target'),
                             ({'type': 'use', 'target': 'b2', 'item': 'potion'}, 'invalid_item')]:
            with self.subTest(code=code):
                d, bots, obs = scene()
                replies = [json.dumps({**action, 'reason': '동료를 돕겠다'}),
                           '{"type":"search","target":"self","reason":"다른 방법을 찾겠다"}']
                with patch.dict(os.environ, DUNGEON_BRAIN_BACKEND='gemini_api'), \
                        patch.object(brains, '_call_claude', side_effect=replies) as call, \
                        patch.object(brains.G, 'dummy_brain', side_effect=AssertionError('자동 대행 금지')):
                    dec = brains.claude_brain(obs, '1', bots[0], bots)
                self.assertEqual(call.call_count, 2)
                self.assertEqual(dec['type'], 'search')
                self.assertEqual(dec['brain_retries'][0]['code'], code)
                self.assertEqual(dec['brain_retries'][0]['detail']['attempted_action']['reason'], '동료를 돕겠다')
                self.assertTrue(call.call_args_list[1].args[0].startswith(call.call_args_list[0].args[0]))
                self.assertIn(code, call.call_args.args[0])
                self.assertIsNone(bots[0].get('order'))

    def test_failed_response_is_not_an_action_in_any_real_backend(self):
        _, bots, obs = scene()
        for backend in ('gemini_api', 'anthropic_api', 'claude_cli'):
            for reply in ('{"type":', ('', '타임아웃 60s')):
                with self.subTest(backend=backend, reply=reply), \
                        patch.dict(os.environ, DUNGEON_BRAIN_BACKEND=backend), \
                        patch.object(brains, '_call_claude', return_value=reply) as call, \
                        patch.object(brains.G, 'dummy_brain', side_effect=AssertionError('자동 대행 금지')):
                    dec = brains.claude_brain(obs, '1', bots[0], bots)
                    self.assertEqual(call.call_count, 2)
                    self.assertEqual(dec['src'], 'error')
                    self.assertNotIn('type', dec)
                    self.assertEqual(len(dec['attempt_errors']), 2)

    def test_explicit_dummy_still_runs_without_retry(self):
        _, bots, obs = scene()
        with patch.dict(os.environ, DUNGEON_BRAIN_BACKEND='dummy'), \
                patch.object(brains, '_call_claude', return_value='') as call:
            dec = brains.claude_brain(obs, '1', bots[0], bots)
        self.assertEqual(call.call_count, 1)
        self.assertIn('type', dec)
        self.assertEqual(dec['src'], 'fallback')

    def test_no_handler_raises_before_decision_memory_is_written(self):
        d, bots, _ = scene()
        with patch.dict(os.environ, DUNGEON_BRAIN_BACKEND='gemini_api'), \
                patch.object(brains, '_call_claude', return_value=''), \
                self.assertRaises(brains.DecisionBlocked):
            brains.think_all(d, bots)
        self.assertTrue(all(not b.get('history') and not b.get('intent') and not b.get('order') for b in bots))

    def test_retry_keeps_observation_and_planned_action_without_duplicate_memory(self):
        d, bots, _ = scene()
        d.view(bots[1], bots)
        bots[1]['plan'] = [{'type': 'search', 'target': 'self'}, {'type': 'wait'}]
        bots[0]['skill_cooldowns'] = {'first_aid': 2}
        bots[0]['status'] = {'출혈': {'left': 3}}
        states, observations = [], []
        def decide(obs, char, bot, roster, solo):
            self.assertEqual(char, '1')  # 동료는 이미 세운 계획을 쓴다.
            observations.append(obs)
            if len(observations) <= 2:
                return {'src': 'error', 'input_error': 'invalid_item', 'reason': '물약 없음'}
            return {'src': 'haiku', 'type': 'search', 'target': 'b1', 'note': '내가 정했다', 'say': '살펴볼게'}
        def paused(errors):
            state = copy.deepcopy((bots, d.rng.getstate()))
            if states:
                self.assertEqual(state, states[0])  # HP·경로·상태·대기시간·기억·난수까지 그대로.
            states.append(state)
            self.assertFalse(bots[0].get('history'))
        with patch.object(brains, 'claude_brain', side_effect=decide), \
                patch.object(d, 'view', wraps=d.view) as view:
            decisions = brains.think_all(d, bots, on_error=paused)
        self.assertEqual(len(states), 2)
        self.assertEqual(view.call_count, 1)
        self.assertTrue(all(obs is observations[0] for obs in observations))
        self.assertEqual(decisions['2']['src'], 'plan')
        self.assertEqual(decisions['2']['type'], 'search')
        self.assertEqual(bots[1]['plan'], [{'type': 'wait'}])
        self.assertEqual(bots[0]['notes'], ['내가 정했다'])
        self.assertEqual(len(bots[0]['history']), 1)
        self.assertEqual(len(bots[0]['dialogue']), 1)

    def test_world_freezes_and_http_retry_resumes_same_run(self):
        with tempfile.TemporaryDirectory(prefix='wl_brain_pause_') as temp:
            state = Path(temp) / 'state'
            state.mkdir()
            server = launcher.make_server('127.0.0.1', 0, state_dir=str(state), runs_dir=str(Path(temp) / 'runs'))
            runner = server.ctx.runner
            with (state / 'runner.out').open('w', encoding='utf-8') as log:
                runner.proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--fixture', str(state)],
                                               cwd=ROOT, env={**os.environ, 'PYTHONUTF8': '1'}, stdout=log, stderr=log)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = 'http://127.0.0.1:%d' % server.server_address[1]

            def api(path, body=None):
                req = Request(base + path, data=None if body is None else json.dumps(body).encode(),
                              headers={'Content-Type': 'application/json'})
                with urlopen(req, timeout=3) as response:
                    return json.load(response)

            def wait_for(predicate):
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    value = predicate()
                    if value:
                        return value
                    time.sleep(.05)
                self.fail('대기 시간 초과: ' + (state / 'runner.out').read_text(encoding='utf-8'))

            try:
                paused = wait_for(lambda: api('/api/status').get('brain_pause'))
                self.assertEqual(paused['turn'], 1)
                self.assertEqual([e['char'] for e in paused['errors']], ['1'])
                before = (state / 'stream.jsonl').read_bytes()
                time.sleep(.7)
                self.assertEqual((state / 'stream.jsonl').read_bytes(), before)
                self.assertFalse(any(json.loads(line)['kind'] == 'tick' for line in before.splitlines()))
                self.assertEqual((state / 'calls-1').read_text(), '2')
                self.assertEqual((state / 'calls-2').read_text(), '1')
                with self.assertRaises(HTTPError) as stale:
                    api('/api/retry', {'pause_id': 'old-run'})
                self.assertEqual(stale.exception.code, 409)
                api('/api/retry', {'pause_id': paused['id']})
                next_pause = wait_for(lambda: (p if (p := api('/api/status').get('brain_pause'))
                                                and p['id'] != paused['id'] else None))
                self.assertEqual(next_pause['turn'], 1)
                self.assertEqual((state / 'calls-1').read_text(), '4')
                self.assertEqual((state / 'calls-2').read_text(), '1')
                with self.assertRaises(HTTPError):
                    api('/api/retry', {'pause_id': paused['id']})
                (state / 'allow-brain').touch()
                api('/api/retry', {'pause_id': next_pause['id']})
                self.assertEqual(runner.proc.wait(timeout=15), 0)
                records = [json.loads(line) for line in (state / 'stream.jsonl').read_text(encoding='utf-8').splitlines()]
                self.assertEqual([r['turn'] for r in records if r['kind'] == 'tick'], [1, 2])
                self.assertEqual(sum(r['kind'] == 'run_meta' for r in records), 1)
                self.assertEqual(sum(r['kind'] == 'brain_pause' for r in records), 2)
                self.assertEqual(sum(r['kind'] == 'brain_resumed' for r in records), 1)
                self.assertTrue(all(d['src'] == 'haiku' and d['type'] == 'search'
                                    for r in records if r['kind'] == 'tick' for d in r['decisions'].values()))
                self.assertFalse((state / run_control.PAUSE_FILE).exists())
                self.assertIsNone(api('/api/status')['brain_pause'])
            finally:
                runner.stop()
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--serve':
        from verify_skill_launcher import serve_for_browser
        serve_for_browser(sys.argv[2], int(sys.argv[3]), brain_fixture=True)
        raise SystemExit(0)
    result = unittest.main(verbosity=2, exit=False).result
    if result.wasSuccessful():
        print('ALL PASS — verify_brain_pause (자동 대행 금지·재판단·정지·HTTP 재시도·재개)')
    raise SystemExit(0 if result.wasSuccessful() else 1)

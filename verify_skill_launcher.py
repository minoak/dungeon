# -*- coding: utf-8 -*-
"""알파 런처의 설정 경계와 브라우저용 격리 서버. 기존 state와 실제 LLM을 사용하지 않는다."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import launcher


class AlphaLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='wl_alpha_launcher_')
        self.addCleanup(self.temp.cleanup)
        self.runner = launcher.Runner(launcher.HERE, self.temp.name, self.temp.name + '/runs')

    def launch_env(self, opts):
        child = Mock(pid=123)
        child.poll.return_value = 0
        with patch('launcher.subprocess.Popen', return_value=child) as popen:
            result = self.runner.start({'party': 'default', 'brain': 'dummy', **opts}, 'unused')
        return result, popen.call_args.kwargs['env']

    def test_alpha_overrides_map_and_inherited_options(self):
        with patch.dict(os.environ, {'DUNGEON_DEPTHS': '1', 'DUNGEON_SOLO': '1'}):
            result, env = self.launch_env({'mode': 'alpha', 'map': 'big'})
        self.assertEqual(result['mode'], 'alpha')
        self.assertEqual([env[k] for k in ('DUNGEON_SKILLS', 'DUNGEON_TRPG_COMBAT', 'DUNGEON_RANDOM_SKILL')], ['1'] * 3)
        self.assertEqual([env[k] for k in ('DUNGEON_DEPTHS', 'DUNGEON_TURNS', 'DUNGEON_SOLO')], ['5', '600', '0'])
        self.assertEqual(env['DUNGEON_BESTIARY_FILE'], '')
        self.assertEqual(env['DUNGEON_ACTION_MODE'], 'compose')
        self.assertEqual(env['DUNGEON_STATE_DIR'], self.temp.name)

    def test_standard_switches_off_inherited_alpha(self):
        with patch.dict(os.environ, {k: '1' for k in ('DUNGEON_SKILLS', 'DUNGEON_TRPG_COMBAT', 'DUNGEON_RANDOM_SKILL')}):
            _, env = self.launch_env({})
        self.assertEqual([env[k] for k in ('DUNGEON_SKILLS', 'DUNGEON_TRPG_COMBAT', 'DUNGEON_RANDOM_SKILL')], ['0'] * 3)

    def test_invalid_mode_or_alpha_combination_does_not_start(self):
        for opts in ({'mode': 'wrong'}, {'mode': 'alpha', 'town': True}, {'mode': 'alpha', 'action_mode': 'menu'}):
            with self.subTest(opts=opts), self.assertRaises(launcher.BadRequest):
                self.launch_env(opts)

    def test_status_reads_mode_from_record(self):
        file = Path(self.temp.name) / 'stream.jsonl'
        for alpha in (None, {'skills': True}):
            file.write_text(json.dumps({'kind': 'run_meta', 'seed': 7, 'alpha': alpha}) + '\n', encoding='utf-8')
            self.assertEqual(self.runner.status()['mode'], 'alpha' if alpha else 'standard')

    def test_server_rejects_duplicate_port(self):
        first = launcher.make_server('127.0.0.1', 0, state_dir=self.temp.name)
        self.addCleanup(first.server_close)
        with self.assertRaises(OSError):
            second = launcher.make_server('127.0.0.1', first.server_address[1], state_dir=self.temp.name)
            second.server_close()

    def test_menu_reuses_existing_launcher_before_binding(self):
        with patch.object(sys, 'argv', ['launcher.py', '--alpha']), patch('launcher.urlopen') as opened, \
                patch('launcher.json.load', return_value={'skill_alpha': {}}), \
                patch('launcher.make_server') as make, patch('launcher.webbrowser.open') as browser:
            self.assertEqual(launcher.main(), 0)
            make.assert_not_called()
            browser.assert_called_once_with('http://127.0.0.1:8000/launcher/?mode=alpha')


def serve_for_browser(root, port):
    """실제와 같은 API·정적 서빙을 쓰되 출력만 임시 폴더로 격리한다."""
    root = Path(root).resolve()
    state = root / 'state'
    state.mkdir(parents=True, exist_ok=True)
    os.environ.update(DUNGEON_STEP_DELAY='0.05', DUNGEON_GM='0', DUNGEON_BESTIARY_FILE='')
    original = launcher.Handler.translate_path

    def translate(self, path):
        # 브라우저에는 실제와 같은 /state/ URL을 쓰되, 검증이 사용자 판을 읽거나 쓰지 않게 한다.
        from urllib.parse import urlparse, unquote
        route = unquote(urlparse(path).path)
        if route.startswith('/state/'):
            target = (state / route[len('/state/'):]).resolve()
            if target.is_relative_to(state):
                return str(target)
        return original(self, path)

    launcher.Handler.translate_path = translate
    srv = launcher.make_server('127.0.0.1', port, party_path=str(root / 'party.json'),
                               state_dir=str(state), runs_dir=str(root / 'runs'), brain='dummy')
    try:
        srv.serve_forever()
    finally:
        srv.ctx.runner.stop()
        srv.server_close()


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--serve':
        serve_for_browser(sys.argv[2], int(sys.argv[3]))
    else:
        result = unittest.main(verbosity=2, exit=False).result
        if result.wasSuccessful():
            print('ALL PASS — verify_skill_launcher (알파 설정·일반판 격리·조합 거부·상태 표시)')
        raise SystemExit(0 if result.wasSuccessful() else 1)

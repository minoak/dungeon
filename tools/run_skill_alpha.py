# -*- coding: utf-8 -*-
"""알파 실험 러너. 매 실행을 새 폴더에 저장하며 기존 라이브 판과 도감을 건드리지 않는다."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))   # tools/ 로 이동(2026-09-13 정리) — 리포 루트 모듈 import 용
import argparse
from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys

ARMS = {'baseline': (0, 0, 0), 'combat': (0, 1, 0), 'skills': (1, 0, 0),
        'preset': (1, 1, 0), 'full': (1, 1, 1)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arm', choices=ARMS, default='full')
    parser.add_argument('--backend', choices=('dummy', 'claude_cli', 'anthropic_api', 'gemini_api'), default='dummy')
    parser.add_argument('--seed', type=int, default=7)
    parser.add_argument('--turns', type=int, default=600)
    parser.add_argument('--party', type=Path)
    parser.add_argument('--output', type=Path, help='새로 만들 출력 폴더. 기존 폴더는 덮어쓰지 않는다.')
    args = parser.parse_args()
    if args.turns < 1 or (args.party and not args.party.is_file()):
        parser.error('turns는 양수, party는 존재하는 JSON 파일이어야 한다')
    root = Path(__file__).resolve().parent.parent   # 리포 루트(tools/ 이동, 2026-09-13)
    output = (args.output or root / 'state_alpha' / (
        datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '-%s-%s' % (args.arm, args.seed))).resolve()
    output.mkdir(parents=True, exist_ok=False)
    flags = ARMS[args.arm]
    env = {**os.environ, 'PYTHONUTF8': '1', 'DUNGEON_ACTION_MODE': 'compose',
           'DUNGEON_SKILLS': str(flags[0]), 'DUNGEON_TRPG_COMBAT': str(flags[1]),
           'DUNGEON_RANDOM_SKILL': str(flags[2]), 'DUNGEON_BRAIN_BACKEND': args.backend,
           'DUNGEON_DEPTHS': '5', 'DUNGEON_TURNS': str(args.turns), 'DUNGEON_SEED': str(args.seed),
           'DUNGEON_STATE_DIR': str(output), 'DUNGEON_BESTIARY_FILE': '', 'DUNGEON_GM': '0',
           'DUNGEON_TOWN': '0', 'DUNGEON_SOLO': '0', 'DUNGEON_STEP_DELAY': '0'}
    if args.party:
        env['DUNGEON_PARTY_FILE'] = str(args.party.resolve())
    print('알파 %s / %s / seed %d → %s' % (args.arm, args.backend, args.seed, output), flush=True)
    if args.backend == 'dummy':
        print('dummy는 기존 규칙 두뇌다. 스킬 사용률·재미를 평가하는 LLM 실험이 아니다.', flush=True)
    return subprocess.run([sys.executable, str(root / 'show_runner.py')], cwd=root, env=env).returncode


if __name__ == '__main__':
    raise SystemExit(main())

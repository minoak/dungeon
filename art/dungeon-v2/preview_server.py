"""Local visual laboratory. Actual Dungeon generator, synthetic snapshots, zero brain calls.

Run after npm --prefix game run build:
    python art/dungeon-v2/preview_server.py --port 4228
"""
from __future__ import annotations

import argparse
from collections import deque
from functools import lru_cache
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
import dungeon_gm as G
from concept_dungeon import ConceptDungeon


def dungeon(seed: int, profile: str = 'original') -> G.Dungeon:
    if profile == 'concept':
        return ConceptDungeon(seed=seed, depth=1, w=42, h=34, scan=True, loops=True,
                              n_monsters=2, n_traps=3, n_lurkers=1, n_potions=2)
    # Runner's current default dimensions and topology, using the production generator.
    return G.Dungeon(seed=seed, depth=1, w=56, h=20, scan=True, loops=True,
                     n_monsters=2, n_traps=3, n_lurkers=1, n_potions=2)


@lru_cache(maxsize=32)
def stream(seed: int, profile: str = 'original') -> bytes:
    d = dungeon(seed, profile)
    bots = []
    for char, name, job, sprite in [('1', '시각 검토 1', '전사', 'sd-warrior'),
                                   ('2', '시각 검토 2', '도적', 'sd-rogue'),
                                   ('3', '시각 검토 3', '궁수', 'sd-archer')]:
        sheet = dict(name=name, job=job, sex='여', persona='', look={'sprite': sprite},
                     hp=14, str=3, dex=1, wdmg=4, stealth=0, search_r=1)
        bots.append(G.spawn(d, char, bots, sheet=sheet))
    party = [{**G.bot_snapshot(b), 'name': b['name'], 'look': b['look']} for b in bots]
    level = d.level_snapshot()
    rows = [dict(kind='run_meta', v=1, seed=seed, started='visual-preview', w=d.w, h=d.h,
                 depths=1, sight=8, town=False, backend='dummy', preview=True, art_profile=profile, party=party),
            dict(kind='level', turn=0, **level, party=party),
            dict(kind='tick', turn=1, decisions={}, events=[], bots=party,
                 features=level['features'], monsters=level['monsters'], traps=level['traps'])]
    return ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows).encode('utf-8')


def verify() -> None:
    signatures = set()
    for seed in range(100):
        a = dungeon(seed).level_snapshot()
        assert a == dungeon(seed).level_snapshot(), f'Non-deterministic seed {seed}'
        cells = {(x, y) for y, row in enumerate(a['grid']) for x, c in enumerate(row) if c in '.+'}
        start = next(iter(cells))
        seen, todo = {start}, deque([start])
        while todo:
            x, y = todo.popleft()
            for p in ((x-1, y), (x+1, y), (x, y-1), (x, y+1)):
                if p in cells and p not in seen:
                    seen.add(p)
                    todo.append(p)
        assert seen == cells and tuple(a['exit']) in seen, f'Disconnected seed {seed}'
        data = [json.loads(line) for line in stream(seed).decode('utf-8').splitlines()]
        assert data[1]['grid'] == a['grid'], 'Preview mutated the engine topology'
        assert all((b['x'], b['y']) in cells for b in data[1]['party'])
        signatures.add(tuple(a['grid']))
    assert len(signatures) == 100
    assert 'brains' not in sys.modules, 'Visual lab must not load brain backends'
    report = dict(passed=True, seeds=100, uniqueGrids=len(signatures), connected=True,
                  deterministic=True, previewMatchesEngine=True, brainImported=False, llmCalls=0)
    (HERE / 'verification' / 'engine.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == '/api/dungeon-preview.jsonl':
            try:
                raw = parse_qs(url.query).get('seed', ['7'])[0]
                if not raw.isascii() or not raw.isdigit() or len(raw) > 10:
                    raise ValueError('invalid seed')
                seed = int(raw)
                if not 0 <= seed <= 2147483647:
                    raise ValueError('seed out of range')
            except ValueError:
                self.send_error(400, 'Seed must be an integer from 0 to 2147483647')
                return
            profile = parse_qs(url.query).get('profile', ['original'])[0]
            if profile not in ('original', 'concept'):
                self.send_error(400, 'Unknown art profile')
                return
            self.reply(stream(seed, profile), 'application/x-ndjson; charset=utf-8')
            return
        if url.path == '/api/status':
            self.reply(b'{"running":false,"dev":true,"preview":true}', 'application/json')
            return
        if url.path == '/':
            self.send_response(302)
            self.send_header('Location', '/art/dungeon-v2/compare.html')
            self.end_headers()
            return
        if not url.path.startswith(('/art/dungeon-v2/', '/game/', '/viewer/')):
            self.send_error(404)
            return
        # Resolved containment, including encoded traversal and symlinks, before serving.
        candidate = Path(self.translate_path(self.path)).resolve()
        allowed = [HERE, ROOT / 'game' / 'dist', ROOT / 'viewer']
        if not any(candidate.is_relative_to(p.resolve()) for p in allowed):
            self.send_error(404)
            return
        super().do_GET()

    def translate_path(self, path):
        result = Path(super().translate_path(path))
        if result.is_relative_to(ROOT / 'game'):
            result = ROOT / 'game' / 'dist' / result.relative_to(ROOT / 'game')
        return str(result)

    def list_directory(self, path):
        self.send_error(404)
        return None

    def reply(self, body, mime):
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=4228)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    if args.verify:
        verify()
    else:
        if not (ROOT / 'game/dist/index.html').exists():
            raise SystemExit('Build first: npm --prefix game run build')
        print(f'http://127.0.0.1:{args.port}/art/dungeon-v2/compare.html', flush=True)
        ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()

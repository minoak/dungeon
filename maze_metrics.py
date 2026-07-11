#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""미로탈출 장면 지표 판독 — 사전등록 design/EXP_D19_MAZE.md 의 계측기.
사용: python3 maze_metrics.py <stream.jsonl> [...]
지표: 탈출 여부·틱 / 재방문율(이미 밟은 칸으로의 걸음 비율) / 공동 진입→탈출 틱 /
결정 src 분포(llm·plan·폴백). 여러 파일을 주면 한 줄씩 표로."""
import json
import sys
from collections import Counter

CAVERN = (31, 45, 3, 19)   # 미로탈출.json 공동 사각형(x0,x1,y0,y1) — 지도와 한 몸


def read(path):
    ticks, end = [], None
    with open(path, encoding='utf-8') as f:
        for line in f:
            r = json.loads(line)
            if r.get('kind') == 'tick':
                ticks.append(r)
            elif r.get('kind') == 'end':
                end = r
    return ticks, end


def metrics(path, char='1'):
    ticks, end = read(path)
    trail, seenpos = [], set()
    steps = revisit = 0
    cav_in = None
    srcs = Counter()
    for t in ticks:
        b = next((bb for bb in t.get('bots', []) if bb.get('char') == char), None)
        if not b:
            continue
        p = (b['x'], b['y'])
        if trail and p != trail[-1]:
            steps += 1
            if p in seenpos:
                revisit += 1
        trail.append(p)
        seenpos.add(p)
        x0, x1, y0, y1 = CAVERN
        if cav_in is None and x0 <= p[0] <= x1 and y0 <= p[1] <= y1:
            cav_in = t['turn']
        d = (t.get('decisions') or {}).get(char)
        if d and not d.get('skipped'):
            srcs[d.get('src', 'llm?')] += 1
    out = end.get('outcome') if end else '?'
    endturn = end.get('turn') if end else None
    cav_ticks = (endturn - cav_in + 1) if (cav_in is not None and out == 'escaped'
                                           and endturn is not None) else None
    return {'outcome': out, 'escape_turn': endturn if out == 'escaped' else None,
            'steps': steps, 'revisit': revisit,
            'revisit_rate': round(revisit / steps, 3) if steps else None,
            'cavern_in': cav_in, 'cavern_ticks': cav_ticks,
            'srcs': dict(srcs)}


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for p in sys.argv[1:]:
        m = metrics(p)
        print(p)
        print('  결과=%(outcome)s 탈출틱=%(escape_turn)s 걸음=%(steps)s '
              '재방문=%(revisit)s 재방문율=%(revisit_rate)s '
              '공동진입=%(cavern_in)s 공동소요=%(cavern_ticks)s' % m)
        print('  결정 src: %s' % m['srcs'])

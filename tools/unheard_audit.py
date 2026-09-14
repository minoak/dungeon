# -*- coding: utf-8 -*-
"""D72(2026-09-14) 효과 측정(0콜, 스트림 소비자 — 판정 없음): 던전 구간에서 '동료를 지목한 말 가운데 상대가 못 들은 비율'.
배달 사실은 다음 틱 inbox 로 판정한다(상대의 다음 틱 받은편지함에 그 말이 없으면 못 들은 것).
사용: python tools/unheard_audit.py [스트림 파일 …]   (기본: runs/ 최신 6 + state/stream.jsonl)
"""
import glob
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 리포 루트(tools/ 의 부모)


def audit(path):
    rows = [json.loads(l) for l in io.open(path, encoding='utf-8') if l.strip()]
    if not rows or rows[0].get('kind') != 'run_meta':
        return None
    meta = rows[0]
    names = {x['char']: x.get('name') or x['job'] for x in meta['party']}
    depth = None
    tot = unheard = 0
    ex = []
    for i, r in enumerate(rows):
        if r['kind'] == 'level':
            depth = r['depth']
            continue
        if r['kind'] != 'tick' or not depth:          # 던전 층만(마을 0층 제외)
            continue
        nxt = next((x for x in rows[i + 1:] if x['kind'] == 'tick'), None)
        for c, d in (r.get('decisions') or {}).items():
            to, say = d.get('to'), d.get('say')
            if not say or not to or to == 'all':
                continue
            tot += 1
            got = nxt and any(m.get('from') == c and m.get('text') == say for m in (nxt.get('inbox') or {}).get(str(to), []))
            if not got:
                unheard += 1
                if len(ex) < 3:
                    ex.append((r['turn'], names.get(c), names.get(str(to)), say[:50]))
    return meta['seed'], tot, unheard, ex


def main(argv):
    files = argv or (sorted(glob.glob(os.path.join(ROOT, 'runs', 'stream-2026*.jsonl')), key=os.path.getmtime)[-6:]
                     + [os.path.join(ROOT, 'state', 'stream.jsonl')])
    for p in files:
        try:
            res = audit(p)
        except Exception as e:
            print('%s: 읽기 실패 (%s)' % (os.path.basename(p), e))
            continue
        if not res:
            continue
        seed, tot, unheard, ex = res
        print('%s seed %s | 던전 지목 말 %d | 못 들음 %d (%d%%)' % (os.path.basename(p), seed, tot, unheard, 100 * unheard / tot if tot else 0))
        for e in ex:
            print('    t%d %s→%s: %s' % e)
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))

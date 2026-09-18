# -*- coding: utf-8 -*-
"""마을 체류 부검(2026-09-17, 0콜, 스트림 소비자 — 판정 없음): 마을에서 시작한 판이 첫 하강까지 마을에 몇 틱 머물렀고,
그동안 무슨 행동을 누구에게 골랐고, 판단 이유(decisions[char].reason)에 어떤 말을 적었나.

왜: 파트너 질문 "캐릭터들이 하나같이 바로 던전으로 간다 — 강하게 목적을 준 거야?"(09-17). 체류 틱은 짧지 않았지만(41~145틱)
이유의 66%에 던전 준비 말이 들어 있었고, 사람·구경만을 이유로 든 판단은 2%였다 = 마을이 '떠나기 전 점검표'로만 읽힌다.
중앙 광장·마을 시계 같은 변경의 앞뒤를 같은 잣대로 재려고 남긴다(docs/town_plaza_2026-09-17.md).

⚠️ 단어 세기라 거칠다 — 이유 문장에 그 말이 '들어 있나'만 본다(뜻을 읽지 않는다). 서로 다른 조건의 판을 비교하는 점수가 아니라,
같은 세계를 고치기 전과 뒤에 같은 잣대를 대 보는 용도다. 표본 문장(--show)을 함께 읽어라.

사용: python tools/town_stay_audit.py [--show N] [--until T] [스트림 파일 …]   (기본: runs/ 의 최근 14판 + state/stream.jsonl)
  --until T(2026-09-18): T 틱까지의 판단만 센다 — 짧게 끊은 시험 판(예: 45틱)과 옛 판을 같은 구간끼리 견주려고.
"""
import collections
import glob
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 리포 루트(tools/ 의 부모)
PREP = re.compile('던전|원정|내려|출발|진입|계단|입구')              # 던전 준비 말
SOCIAL = re.compile('친해|이야기|수다|놀|쉬|구경|궁금|반갑|인사')     # 사람·구경 말(던전 준비 말이 같이 있으면 안 센다)
UNTIL = None                                                          # --until T: 이 틱까지의 판단만(없으면 첫 하강까지 전부)


def audit(path):
    """스트림 하나 → 부검 dict. 마을 시작·실 LLM·보스 프리셋 아님인 판만(아니면 None). 쓰는 중인 마지막 반 줄은 거기서 멈춘다."""
    meta, first_descend, last_turn = None, None, 0
    acts, targets, reasons = collections.Counter(), collections.Counter(), []
    names, fname = {}, {}
    try:
        for ln in io.open(path, encoding='utf-8'):
            try:
                o = json.loads(ln)
            except ValueError:
                break
            k = o.get('kind')
            if k == 'run_meta':
                meta = o
                names = {str(q.get('char')): q.get('name') or q.get('job') for q in o.get('party') or []}
            elif k == 'level' and o.get('depth') == 0:
                fname = {('f%s' % f.get('id')): f.get('name') for f in o.get('features') or []}
            elif k == 'descend' and first_descend is None:
                first_descend = o.get('turn')
            elif k == 'tick':
                last_turn = o.get('turn') or last_turn
                if first_descend is not None or not (meta and meta.get('town')):
                    continue
                if UNTIL and (o.get('turn') or 0) > UNTIL:
                    continue
                dec = o.get('decisions') or {}
                for ch, d in (dec.items() if isinstance(dec, dict) else []):
                    if not isinstance(d, dict) or not d.get('type'):
                        continue
                    tg = str(d.get('target'))
                    label = fname.get(tg) or ('동료' if tg.startswith('b') else '계단' if tg == 'exit' else '의뢰' if tg.startswith('q') else
                                              '(대상 없음)' if tg == 'None' else tg)
                    acts[d['type']] += 1
                    targets[label] += 1
                    if d.get('reason'):
                        reasons.append((o.get('turn'), names.get(str(ch), ch), d['type'], label, d['reason']))
    except OSError:
        return None
    if not meta or not meta.get('town') or meta.get('backend') == 'dummy' or meta.get('start') == 'boss':
        return None
    prep = [r for r in reasons if PREP.search(r[4])]
    social = [r for r in reasons if SOCIAL.search(r[4]) and not PREP.search(r[4])]
    return {'file': os.path.basename(path), 'seed': meta.get('seed'), 'backend': meta.get('backend'),
            'party': '·'.join(names[c] for c in sorted(names)), 'stay': first_descend, 'turns': last_turn,
            'acts': acts, 'targets': targets, 'reasons': reasons, 'prep': prep, 'social': social}


def main(argv):
    global UNTIL
    show = 0
    if '--show' in argv:
        i = argv.index('--show')
        show = int(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    if '--until' in argv:
        i = argv.index('--until')
        UNTIL = int(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    paths = argv or (sorted(glob.glob(os.path.join(ROOT, 'runs', 'stream-*.jsonl')))[-14:] + [os.path.join(ROOT, 'state', 'stream.jsonl')])
    rows = [r for r in (audit(p) for p in paths) if r]
    print('마을에서 시작한 실 LLM 판 %d개' % len(rows))
    tot = prep = social = 0
    for r in rows:
        n = len(r['reasons'])
        tot, prep, social = tot + n, prep + len(r['prep']), social + len(r['social'])
        print('\n== %s seed %s [%s] %s' % (r['file'], r['seed'], r['backend'], r['party']))
        print('   마을 체류 %s / 전체 %s틱 · 마을 판단 %d회 · 이유에 던전 준비 말 %d(%d%%) · 사람·구경 말만 %d'
              % (('%d틱' % r['stay']) if r['stay'] is not None else '(안 내려감)', r['turns'], n, len(r['prep']),
                 round(100 * len(r['prep']) / max(1, n)), len(r['social'])))
        print('   행동: %s' % dict(r['acts'].most_common()))
        print('   대상: %s' % dict(r['targets'].most_common(8)))
        for turn, who, t, label, why in (r['reasons'][:show] if show else []):
            print('     t%-3s %s %s→%s | %s' % (turn, who, t, label, why[:150]))
    print('\n합계: 마을 판단 %d회 · 이유에 던전 준비 말 %d(%d%%) · 사람·구경 말만 %d(%d%%)'
          % (tot, prep, round(100 * prep / max(1, tot)), social, round(100 * social / max(1, tot))))
    return 0


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        pass
    raise SystemExit(main(sys.argv[1:]))

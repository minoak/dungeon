# -*- coding: utf-8 -*-
"""스킬 A/B의 관측 통계. 접근 걸음 대신 접수된 결정/실제 스킬 실행만 센다."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))   # tools/ 로 이동(2026-09-13 정리) — 리포 루트 모듈 import 용
import argparse
from collections import Counter, defaultdict
import json
import math

from analyze_run import load
from composed_actions import COMMON

LEGACY_COMMON = COMMON + ('follow',)   # D48(2026-09-11) 이전 판(compose-v0.4)의 follow 결정도 COMMON 으로 센다 — 구판 분석 호환


def distribution(counts, skill_ids):
    total = sum(counts.values())
    skills = sum(n for typ, n in counts.items() if typ in skill_ids)
    return {'decisions': total, 'counts': dict(sorted(counts.items())),
            'attack_ratio': counts.get('attack', 0) / total if total else 0,
            'skill_ratio': skills / total if total else 0,
            'common_ratio': sum(n for typ, n in counts.items() if typ in LEGACY_COMMON) / total if total else 0,
            'unique_actions': len(counts),
            'entropy_bits': -sum((n / total) * math.log2(n / total) for n in counts.values()) if total else 0}


def summarize(path):
    rows = load(path)
    meta = next((r for r in rows if r.get('kind') == 'run_meta'), {})
    ticks = [r for r in rows if r.get('kind') == 'tick']
    end = next((r for r in rows if r.get('kind') == 'end'), {})
    skill_ids = set(meta.get('alpha', {}).get('presets', {}))
    acquired = {}
    for row in rows:
        for p in row.get('party', []) if row.get('kind') in ('run_meta', 'level') else []:
            skill_ids.update(p.get('skills', []))
        for record in row.get('skill_acquisitions', []):
            skill_ids.add(record['generated_skill_id'])
            acquired[record['char']] = record['turn']
    counts, before, after = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
    sources, outcomes = Counter(), Counter()
    seen, executed = set(), set()
    hp_cost = healed = potion_uses = 0
    combat_turns = []
    for tick in ticks:
        for char, decision in tick.get('decisions', {}).items():
            if decision.get('skipped'):
                continue
            identity = decision.get('action_id') or (tick['turn'], char)
            if identity in seen:
                continue
            seen.add(identity)
            typ = decision.get('type', 'unknown')
            counts[char][typ] += 1
            sources[decision.get('src', 'unknown')] += 1
            if char in acquired:
                (before if tick['turn'] <= acquired[char] else after)[char][typ] += 1
        combat = False
        for event in tick.get('events', []):
            if event.get('type') in ('attack', 'monster_attack') or (event.get('skill_spent') and event.get('skill_roll')):
                combat = True
            if event.get('item_used') == 'i1' or event.get('type') == 'drink' and event.get('result') == 'healed':
                potion_uses += 1
            if event.get('skill_id') and event.get('resolution', {}).get('phase') == 'resolved':
                identity = event.get('parent_action_id')
                if identity not in executed:
                    executed.add(identity)
                    outcomes[event.get('result', 'unknown')] += 1
                    hp_cost += sum(p.get('value', 0) for p in event.get('penalties', []) if p['type'] == 'hp_cost')
                    healed += event.get('heal', 0)
        if combat:
            combat_turns.append(tick['turn'])
    bouts = []
    for turn in combat_turns:
        if not bouts or turn > bouts[-1][-1] + 1:
            bouts.append([turn])
        else:
            bouts[-1].append(turn)
    final_by_char = {}
    for row in rows:
        for bot in row.get('bots', []) if row.get('kind') in ('tick', 'end') else []:
            final_by_char[bot['char']] = bot
    final = list(final_by_char.values())
    total = Counter()
    for c in counts.values():
        total.update(c)
    return {'file': str(path), 'seed': meta.get('seed'), 'backend': meta.get('backend'),
            'alpha': {k: v for k, v in meta.get('alpha', {}).items() if k != 'presets'},
            'outcome': end.get('outcome', 'incomplete'), 'depth': end.get('depth'),
            'ticks': len(ticks), 'sources': dict(sources),
            'overall': distribution(total, skill_ids),
            'by_character': {c: distribution(n, skill_ids) for c, n in sorted(counts.items())},
            'acquisition': {c: {'turn': turn, 'before': distribution(before[c], skill_ids),
                                'after': distribution(after[c], skill_ids)} for c, turn in acquired.items()},
            'skill_resolutions': dict(outcomes), 'hp_cost': hp_cost, 'skill_healing': healed,
            'potion_uses': potion_uses, 'combat_ticks': len(combat_turns),
            'consecutive_combat_lengths': [len(b) for b in bouts],
            'survival_ratio': sum(bool(b.get('alive')) for b in final) / len(final) if final else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('streams', nargs='+')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    reports = [summarize(p) for p in args.streams]
    if args.json:
        print(json.dumps(reports, ensure_ascii=False, indent=2))
        return
    for r in reports:
        n = r['overall']
        print('%s\n  seed=%s · %s · %s · %s층 · %s틱' % (r['file'], r['seed'], r['backend'], r['outcome'], r['depth'], r['ticks']))
        print('  결정 %d · attack %.1f%% · SKILL %.1f%% · 행동 %d종 · 엔트로피 %.2f bits' % (
            n['decisions'], n['attack_ratio'] * 100, n['skill_ratio'] * 100, n['unique_actions'], n['entropy_bits']))
        print('  스킬 결과 %s · HP 비용 %d · 스킬 회복 %d' % (r['skill_resolutions'], r['hp_cost'], r['skill_healing']))
        for char, row in r['by_character'].items():
            print('  봇%s: %s' % (char, row['counts']))
        for char, row in r['acquisition'].items():
            print('  봇%s 획득 전/후: %d/%d결정 · SKILL %.1f%%/%.1f%%' % (
                char, row['before']['decisions'], row['after']['decisions'],
                row['before']['skill_ratio'] * 100, row['after']['skill_ratio'] * 100))
        print('  판단 출처: %s\n' % r['sources'])
    print('전투 길이는 전투 이벤트가 연속된 틱 수다. 재미·전술·인과관계는 자동 판정하지 않는다.')


if __name__ == '__main__':
    main()

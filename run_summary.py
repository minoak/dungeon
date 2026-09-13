#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""판 결산(D58, 2026-09-12 파트너 "로깅 부검도 시스템 결산을 통해 1차 확인 — 이러려고 결산 기능을 만든 거잖아") —
스트림 소비자. **기계가 센 숫자만**(LLM 0콜), 판정은 사람이. D40 층 결산(캐릭터·층 단위 사건 횟수)의 판 단위 짝.

왜: 09-12 부검마다 같은 숫자를 손으로 다시 셌다 — 콜/틱, 같은 대상 연속 반복(단검 52턴), 판단 정지와 그 원인,
입력 무효 재판단(already_beside), 파티 밀집도, 되집기. 그 숫자는 판이 끝날 때 러너가 스스로 내놓아야 한다.

두 자리, 같은 계산:
  · 라이브: 러너가 스트림에 쓰는 모든 레코드를 Tap 으로 흘려 Collector 가 세고, 마지막 `end` 레코드에 `summary` 로 싣고
    events.log 끝에 표를 찍는다.
  · 오프라인: `python run_summary.py runs/xxx.jsonl` — 같은 Collector 로 소급. 옛 판도 읽힌다. `end.summary` 가 있으면
    라이브와 같은지 대조한다(발급기·반응 장부와 같은 "스트림의 결정론 투영" 규율).

⚠️ 눈길 표식(flags)은 판정이 아니라 "여기부터 보라"는 문턱이고, 문턱값은 임시 가정(FLAGS) — 판을 보며 고친다.
"""
import collections
import json
import sys
from movement_summary import MovementSummary, render as render_movement

TOGETHER = 3          # 전원 '함께' = 살아 있는 전원이 서로 체비셰프 이 칸 안(⚠️임시 — 09-12 부검에서 쓴 자)
FLAGS = {             # ⚠️임시 가정 — 눈길 표식 문턱
    'same_target_run': 5,    # 같은 (행동, 대상)을 연속 이만큼 이상 고름
    'already_beside': 5,     # 입력 무효 재판단 already_beside 횟수
    'calls_per_tick': 1.2,   # 실결정/틱
    'together_pct': 30,      # 전원 함께 비율(%) 미만
    'rewear': 2,             # 같은 장비 개체를 두 번 이상 걸침(캐릭터당 개체 수)
    'split_max': 60,         # 전원 함께가 아닌 최장 연속 틱
    'equip_streak': 5,       # 같은 캐릭터가 인접 틱에 연속으로 장비를 걸침(대상 번호와 무관 — 판 51828 의 되집기 자)
}


def _cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


class Collector:
    """스트림 레코드를 순서대로 consume() → result() 가 결산 dict. 상태는 전부 카운터(투영 순수성)."""

    def __init__(self):
        self.movement = MovementSummary()
        self.meta = {}
        self.names = {}
        self.ticks = 0
        self.levels = 0
        self.depth_max = 0
        self.dec = collections.defaultdict(collections.Counter)    # char -> {type: n} (실결정만)
        self.plan = collections.Counter()                          # char -> 작정 수
        self.src = collections.Counter()
        self.say = collections.Counter()                           # 잡담/제안
        self.goto_ally = collections.Counter()
        self.retry_codes = collections.Counter()                   # 입력 무효 재판단 코드(decisions.brain_retries)
        self.fallback = 0                                          # 대체 두뇌가 답한 결정
        self.pauses = 0
        self.pause_codes = collections.Counter()
        self.blocked = 0                                           # 안전 차단(PROHIBITED_CONTENT)이 낀 정지
        self.retries = 0                                           # brain_retry(사람이 누른 재시도)
        self._run = {}                                             # char -> [key, t0, t1, n]
        self.longest = {}                                          # char -> (n, key, t0, t1)
        self._prev = {}
        self.repeat = collections.Counter()
        self.together = 0
        self.multi = 0
        self._split = 0
        self.split_max = 0
        self.events = collections.Counter()
        self.lost = 0
        self.hails = 0
        self.give = 0
        self.bond = 0
        self.reactions = collections.Counter()
        self.equip = collections.Counter()
        self._equip_ids = collections.defaultdict(collections.Counter)   # char -> {장비 개체 id: n}
        self._equip_run = {}                                        # char -> [t0, t1, n] (인접 틱 연속 착용)
        self.equip_streak = {}                                      # char -> (n, t0, t1)
        self.book_lines = 0
        self.end = {}

    # ── 소비 ──
    def consume(self, kind, rec):
        self.movement.consume(kind, rec)
        if kind == 'run_meta':
            self.meta = rec
            for p in rec.get('party') or []:
                if isinstance(p, dict) and p.get('char') is not None:
                    self.names[str(p['char'])] = p.get('name') or ('봇%s' % p['char'])
        elif kind == 'level':
            self.levels += 1
            self.depth_max = max(self.depth_max, int(rec.get('depth') or 0))
        elif kind == 'tick':
            self._tick(rec)
        elif kind == 'brain_pause':
            self.pauses += 1
            for e in rec.get('errors') or []:
                self.pause_codes[str(e.get('input_error') or '?')] += 1
                if 'PROHIBITED' in json.dumps(e, ensure_ascii=False):
                    self.blocked += 1
        elif kind == 'brain_retry':
            self.retries += 1
        elif kind == 'end':
            self.end = {k: rec.get(k) for k in ('outcome', 'depth', 'survivors', 'fallen', 'turn')}

    def _tick(self, rec):
        self.ticks += 1
        turn = int(rec.get('turn') or 0)
        pos = [(b['x'], b['y']) for b in rec.get('bots') or []
               if b.get('alive') and not b.get('won') and b.get('x') is not None]
        if len(pos) >= 2:
            self.multi += 1
            if all(_cheb(pos[i], pos[j]) <= TOGETHER for i in range(len(pos)) for j in range(i + 1, len(pos))):
                self.together += 1
                self._split = 0
            else:
                self._split += 1
                self.split_max = max(self.split_max, self._split)
        for c, d in sorted((rec.get('decisions') or {}).items()):
            c = str(c)
            typ, tgt = d.get('type'), d.get('target')
            key = (typ, tgt)
            run = self._run.get(c)
            if run and run[0] == key:
                run[2], run[3] = turn, run[3] + 1
            else:
                run = self._run[c] = [key, turn, turn, 1]
            best = self.longest.get(c)
            if best is None or run[3] > best[0]:
                self.longest[c] = (run[3], key, run[1], run[2])
            if d.get('src') == 'plan':
                self.plan[c] += 1
                continue
            self.dec[c][str(typ)] += 1
            self.src[str(d.get('src') or '?')] += 1
            if (d.get('say') or '').strip():
                self.say[str(d.get('say_kind') or '잡담')] += 1
            if typ == 'goto' and str(tgt or '').startswith('b'):
                self.goto_ally[c] += 1
            for e in d.get('brain_retries') or []:
                self.retry_codes[str(e.get('code') or '?')] += 1
            if d.get('brain_fallback'):
                self.fallback += 1
            if d.get('book_line'):
                self.book_lines += 1
            if self._prev.get(c) == key:
                self.repeat[c] += 1
            self._prev[c] = key
        self.hails += len(rec.get('hails') or [])
        for r in rec.get('reactions') or []:
            self.reactions[str(r.get('value') or '?')] += 1
        for e in rec.get('events') or []:
            t, r = e.get('type'), e.get('result')
            self.events[str(r or t)] += 1
            if r == 'lost':
                self.lost += 1
            if t == 'give' and r == 'given':
                self.give += 1
            if t == 'bond' and r == 'done':
                self.bond += 1
            if r == 'equip':
                c = str(e.get('char'))
                self.equip[c] += 1
                if e.get('id'):
                    self._equip_ids[c][str(e['id'])] += 1
                run = self._equip_run.get(c)
                if run and turn - run[1] <= 1:
                    run[1], run[2] = turn, run[2] + 1
                else:
                    run = self._equip_run[c] = [turn, turn, 1]
                best = self.equip_streak.get(c)
                if best is None or run[2] > best[0]:
                    self.equip_streak[c] = (run[2], run[0], run[1])

    # ── 결산 ──
    def result(self, outcome=None, depth=None, survivors=None, fallen=None):
        end = dict(self.end)
        if outcome is not None:
            end.update({'outcome': outcome, 'depth': depth, 'survivors': survivors, 'fallen': fallen})
        real = sum(sum(v.values()) for v in self.dec.values())
        chars = sorted(set(self.dec) | set(self.plan) | set(self.names))
        actions = {}
        for c in chars:
            n = sum(self.dec[c].values())
            lg = self.longest.get(c)
            actions[c] = {
                'n': n, 'plan': int(self.plan[c]),
                'types': dict(self.dec[c].most_common(6)),
                'goto_ally': int(self.goto_ally[c]),
                'repeat': int(self.repeat[c]),
                'longest_run': ({'n': lg[0], 'type': lg[1][0], 'target': lg[1][1], 't0': lg[2], 't1': lg[3]}
                                if lg else None),
            }
        rewear = {c: {i: n for i, n in ids.items() if n >= 2} for c, ids in self._equip_ids.items()}
        rewear = {c: v for c, v in rewear.items() if v}
        s = {
            'v': 1,
            'seed': self.meta.get('seed'),
            'ticks': self.ticks, 'levels': self.levels, 'depth_max': self.depth_max,
            'outcome': end.get('outcome'), 'depth': end.get('depth'),
            'survivors': end.get('survivors'), 'fallen': end.get('fallen'),
            'decisions': {'real': real, 'plan': int(sum(self.plan.values())),
                          'per_tick': round(real / self.ticks, 2) if self.ticks else 0.0,
                          'src': dict(self.src), 'input_retries': dict(self.retry_codes),
                          'fallback': self.fallback},
            'pauses': {'n': self.pauses, 'by_code': dict(self.pause_codes), 'blocked': self.blocked,
                       'retries': self.retries},
            'actions': actions,
            'party': {'together_pct': (round(100.0 * self.together / self.multi) if self.multi else None),
                      'multi_ticks': self.multi, 'split_max': self.split_max, 'lost': self.lost},
            'social': {'say': dict(self.say), 'hails': self.hails, 'give': self.give, 'bond': self.bond,
                       'reactions': dict(self.reactions)},
            'gear': {'equip': dict(self.equip), 'rewear': rewear,
                     'streak': {c: {'n': v[0], 't0': v[1], 't1': v[2]} for c, v in self.equip_streak.items()}},
            'bestiary': {'book_lines': self.book_lines},
            'events': dict(self.events.most_common(12)),
            'movement': self.movement.result(),
        }
        s['flags'] = self.flags(s)
        return s

    def flags(self, s):
        """눈길 표식 — 문턱(FLAGS)은 ⚠️임시. 문장은 사실+문턱만(판정 없음)."""
        out = []
        nm = lambda c: self.names.get(c, '봇%s' % c)
        for c, a in s['actions'].items():
            lg = a.get('longest_run')
            if lg and lg['n'] >= FLAGS['same_target_run']:
                out.append('%s 같은 대상 연속 %d회 — %s %s (t%d~t%d) [문턱 %d]'
                           % (nm(c), lg['n'], lg['type'], lg['target'] or '', lg['t0'], lg['t1'], FLAGS['same_target_run']))
        ab = s['decisions']['input_retries'].get('already_beside', 0)
        if ab >= FLAGS['already_beside']:
            out.append('이미 곁 재판단 %d회 [문턱 %d]' % (ab, FLAGS['already_beside']))
        if s['decisions']['per_tick'] >= FLAGS['calls_per_tick']:
            out.append('실결정 %.2f/틱 [문턱 %.1f]' % (s['decisions']['per_tick'], FLAGS['calls_per_tick']))
        if s['pauses']['n']:
            out.append('판단 정지 %d회 (%s%s)' % (s['pauses']['n'],
                                              ' · '.join('%s %d' % kv for kv in sorted(s['pauses']['by_code'].items())),
                                              (' · 안전 차단 %d' % s['pauses']['blocked']) if s['pauses']['blocked'] else ''))
        tp = s['party']['together_pct']
        if tp is not None and tp < FLAGS['together_pct']:
            out.append('전원 함께 %d%% [문턱 %d%% 미만] · 최장 이산 %d틱' % (tp, FLAGS['together_pct'], s['party']['split_max']))
        elif s['party']['split_max'] >= FLAGS['split_max']:
            out.append('최장 이산 %d틱 [문턱 %d]' % (s['party']['split_max'], FLAGS['split_max']))
        for c, ids in s['gear']['rewear'].items():
            worst = max(ids.values())
            if len(ids) >= 1 and worst >= FLAGS['rewear']:
                out.append('%s 같은 장비 되집기 — %s [문턱 %d]' % (nm(c), ' · '.join('%s ×%d' % kv for kv in sorted(ids.items())), FLAGS['rewear']))
        for c, st in s['gear'].get('streak', {}).items():
            if st['n'] >= FLAGS['equip_streak']:
                out.append('%s 연속 착용 %d회 (t%d~t%d) [문턱 %d]' % (nm(c), st['n'], st['t0'], st['t1'], FLAGS['equip_streak']))
        return out


def render(s, names=None):
    """events.log·콘솔용 표 — 한 줄에 한 갈래. 숫자만, 판정 없음."""
    names = dict(names or {})
    nm = lambda c: names.get(c, '봇%s' % c)
    L = ['=== 판 결산 (기계가 센 숫자 — 판정은 사람이) ===']
    L.append('  판: %s틱 · 결과 %s · 층 %s(최대 %s) · 생존 %s · 쓰러짐 %s · 시드 %s'
             % (s['ticks'], s.get('outcome') or '(중단 — end 없음)', s.get('depth') if s.get('depth') is not None else '-', s['depth_max'],
                s.get('survivors') or [], s.get('fallen') or [], s.get('seed')))
    d = s['decisions']
    L.append('  판단: 실결정 %d (%.2f/틱) · 작정 %d · 출처 %s · 입력 무효 재판단 %s · 대체 두뇌 %d'
             % (d['real'], d['per_tick'], d['plan'],
                '/'.join('%s %d' % kv for kv in sorted(d['src'].items())) or '-',
                ' · '.join('%s %d' % kv for kv in sorted(d['input_retries'].items())) or '없음', d['fallback']))
    p = s['pauses']
    L.append('  정지: %d회 %s · 사람 재시도 %d · 안전 차단 %d'
             % (p['n'], ('(' + ' · '.join('%s %d' % kv for kv in sorted(p['by_code'].items())) + ')') if p['by_code'] else '',
                p['retries'], p['blocked']))
    for c, a in s['actions'].items():
        lg = a.get('longest_run')
        L.append('  행동 %s: %d결정(+작정 %d) · %s · 아군 goto %d · 재선택 %d · 최장 반복 %s'
                 % (nm(c), a['n'], a['plan'],
                    ' '.join('%s %d' % kv for kv in a['types'].items()) or '-',
                    a['goto_ally'], a['repeat'],
                    ('%s %s ×%d (t%d~t%d)' % (lg['type'], lg['target'] or '', lg['n'], lg['t0'], lg['t1'])) if lg else '-'))
    pt = s['party']
    if s.get('movement'):
        L.extend(render_movement(s['movement'], names))
    L.append('  파티: 전원 %d칸 안 %s · 최장 이산 %d틱 · lost %d'
             % (TOGETHER, ('%d%%' % pt['together_pct']) if pt['together_pct'] is not None else '(2인 미만)',
                pt['split_max'], pt['lost']))
    so = s['social']
    L.append('  사회: 말 %s · 정지(제안) %d · 친목 %d · 건네기 %d · 반응 %s'
             % (' '.join('%s %d' % kv for kv in sorted(so['say'].items())) or '-', so['hails'], so['bond'], so['give'],
                ' '.join('%s %d' % kv for kv in sorted(so['reactions'].items())) or '-'))
    g = s['gear']
    L.append('  장비: 착용 %s · 되집기 %s'
             % (' '.join('%s %d' % (nm(c), n) for c, n in sorted(g['equip'].items())) or '없음',
                ' · '.join('%s(%s)' % (nm(c), ' '.join('%s×%d' % kv for kv in sorted(ids.items()))) for c, ids in sorted(g['rewear'].items())) or '없음'))
    L.append('  도감: 생각 한 줄 %d · 사건 상위 %s'
             % (s['bestiary']['book_lines'], ' '.join('%s %d' % kv for kv in list(s['events'].items())[:8]) or '-'))
    if s['flags']:
        L.append('  ⚠️ 눈길(문턱=임시): ' + ' / '.join(s['flags']))
    else:
        L.append('  눈길: 문턱 넘는 항목 없음')
    return L


class Tap:
    """StreamWriter 앞의 분기 — 러너가 emit 하는 모든 레코드를 Collector 에도 흘린다(파일 내용은 그대로)."""

    def __init__(self, writer, collector):
        self.writer, self.collector = writer, collector

    def emit(self, kind, **fields):
        self.collector.consume(kind, fields)
        self.writer.emit(kind, **fields)

    def close(self):
        self.writer.close()


def replay(path):
    """스트림 파일 → (Collector, end 레코드) — 유효 prefix 규칙(깨진 꼬리 무시)."""
    col, end = Collector(), None
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            col.consume(rec.get('kind'), rec)
            if rec.get('kind') == 'end':
                end = rec
    return col, end


def main(argv):
    paths = [a for a in argv if not a.startswith('--')] or ['state/stream.jsonl']
    for p in paths:
        try:
            col, end = replay(p)
        except OSError as e:
            print('읽기 실패: %s (%s)' % (p, e))
            continue
        s = col.result()
        print('== %s' % p)
        for ln in render(s, col.names):
            print(ln)
        live = (end or {}).get('summary')
        if live is not None:
            # 옛 결산에 없던 추가 갈래는 비교 대상에서 제외한다.
            same = all(k in s and s[k] == v for k, v in live.items())
            print('  라이브 결산(end.summary)과 %s' % ('일치' if same else '불일치 ⚠️'))
        print()
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))

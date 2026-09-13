"""기존 스트림만 읽는 이동·대기 집계. 기다릴 의도나 교착 여부는 추측하지 않는다."""
from collections import Counter, defaultdict


class MovementSummary:
    def __init__(self):
        self.waits = {}
        self.wait_end = defaultdict(Counter)
        self.wait_durations = defaultdict(list)
        self.wait_pending = set()
        self.wait_next = defaultdict(Counter)
        self.wait_snapshot = Counter()
        self.multi_wait_ticks = 0
        self.gotos = {}
        self.goto_outcomes = defaultdict(Counter)
        self.goto_pending = {}
        self.goto_next = defaultdict(Counter)
        self.previous = {}
        self.steps = Counter()
        self.still = Counter()
        self.longest_still = Counter()
        self.turn = 0

    def _end_wait(self, c, reason):
        if c in self.waits:
            start = self.waits.pop(c)
            self.wait_end[c][reason] += 1
            self.wait_durations[c].append(max(0, self.turn-start))
            self.wait_pending.add(c)

    def _end_goto(self, c, reason):
        if c in self.gotos:
            req = self.gotos.pop(c)
            self.goto_outcomes[c][reason] += 1
            self.goto_pending[c] = req['target']

    def consume(self, kind, rec):
        if kind == 'level':
            # 층 전이를 보행 거리로 세지 않는다. 종료 이벤트가 없으면 별도로 표시한다.
            for c in list(self.waits): self._end_wait(c, 'level_change')
            for c in list(self.gotos): self._end_goto(c, 'level_change')
            self.previous.clear()
            self.still.clear()
            return
        if kind != 'tick': return
        self.turn = int(rec.get('turn') or 0)
        bots = {str(b['char']):b for b in rec.get('bots', [])}
        decisions = rec.get('decisions') or {}
        for c, d in decisions.items():
            c = str(c)
            typ, tgt = d.get('type'), str(d.get('target') or '')
            if c in self.waits:
                self._end_wait(c, 'new_decision')
            if c in self.gotos:
                self._end_goto(c, 'new_decision')
            if c in self.wait_pending:
                self.wait_next[c][typ or 'unknown'] += 1
                self.wait_pending.remove(c)
            if c in self.goto_pending:
                prev = self.goto_pending.pop(c)
                label = 'same_ally' if typ=='goto' and tgt==prev else 'other_ally' if typ=='goto' and tgt.startswith('b') else typ or 'unknown'
                self.goto_next[c][label] += 1
            if typ == 'goto' and tgt.startswith('b'):
                self.gotos[c] = {'target':tgt,'action_id':d.get('action_id')}
        # 실제로 대기를 시작한 판정만 센다.
        for e in rec.get('events') or []:
            c, result = str(e.get('char')), e.get('result')
            if e.get('type') == 'wait' and result == 'waiting' and c not in self.waits:
                self.waits[c] = self.turn
            if result in ('wait_met', 'wait_bored'):
                self._end_wait(c, result)
            res = e.get('resolution') or {}
            req = self.gotos.get(c)
            if req and res.get('phase') == 'resolved':
                parent = e.get('parent_action_id')
                if (req['action_id'] and parent == req['action_id']) or (not req['action_id'] and (res.get('type')=='goto' or str(e.get('target','')).startswith('chase:'))):
                    self._end_goto(c, res.get('reason') or result or 'unknown')
        for c in list(self.waits):
            b = bots.get(c)
            if b is not None and (not b.get('alive') or b.get('won')):
                self._end_wait(c, 'inactive')
            elif b is not None and b.get('order') != 'wait':
                # 피격·말 걸림 등의 이유가 이벤트에 없으면 종료 이유를 추측하지 않는다.
                self._end_wait(c, 'order_cleared')
        waiting = [c for c,b in bots.items() if b.get('alive') and b.get('order') == 'wait']
        self.wait_snapshot.update(waiting)
        if len(waiting) >= 2: self.multi_wait_ticks += 1
        for c,b in bots.items():
            if not b.get('alive') or b.get('won') or b.get('x') is None:
                self._end_goto(c, 'inactive')
                self.previous.pop(c, None); self.still[c] = 0
                continue
            now = (b['x'],b['y'])
            prev = self.previous.get(c)
            if prev is not None:
                if now != prev:
                    self.steps[c] += 1
                    self.still[c] = 0
                else:
                    self.still[c] += 1
                    self.longest_still[c] = max(self.longest_still[c], self.still[c])
            self.previous[c] = now

    def result(self):
        chars = sorted(set(self.previous)|set(self.waits)|set(self.wait_end)|set(self.goto_outcomes)|set(self.gotos)|set(self.steps)|set(self.longest_still))
        return {'v':1,'multi_wait_ticks':self.multi_wait_ticks,'by_actor':{
            c:{'moving_ticks':self.steps[c], 'stationary_max':self.longest_still[c],
               'wait':{'snapshot_ticks':self.wait_snapshot[c],'ended':dict(self.wait_end[c]),
                       'completed':len(self.wait_durations[c]),
                       'mean_ticks':round(sum(self.wait_durations[c])/len(self.wait_durations[c]),2) if self.wait_durations[c] else None,
                       'max_ticks':max(self.wait_durations[c],default=None),
                       'open_since':self.waits.get(c),'next_action':dict(self.wait_next[c])},
               'goto_ally':{'ended':dict(self.goto_outcomes[c]),'open':c in self.gotos,'next_action':dict(self.goto_next[c])}}
            for c in chars}}


def render(m, names):
    lines = ['  동시 대기: 2인 이상 %d틱 (교착 판정 아님)' % m['multi_wait_ticks']]
    for c,a in m['by_actor'].items():
        w, g = a['wait'], a['goto_ally']
        fmt = lambda counts: ' · '.join('%s %d' % kv for kv in sorted(counts.items())) or '-'
        lines.append('  이동·대기 %s: 이동 %d틱 · 제자리 최장 %d틱 · 대기 %s / 평균 %s틱·최장 %s틱%s'
                     % (names.get(c,'봇'+c),a['moving_ticks'],a['stationary_max'],fmt(w['ended']),w['mean_ticks'] if w['mean_ticks'] is not None else '-',w['max_ticks'] if w['max_ticks'] is not None else '-',
                        ' · 진행중(t%d~)' % w['open_since'] if w['open_since'] is not None else ''))
        lines.append('    대기 뒤 행동 %s / 아군 goto 종료 %s / 그 뒤 행동 %s%s'
                     % (fmt(w['next_action']),fmt(g['ended']),fmt(g['next_action']),' · goto 진행중' if g['open'] else ''))
    return lines

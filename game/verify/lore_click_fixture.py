"""verify/inspect.mjs 의 자료(p0512c) — 관전 클릭 창을 브라우저로 볼 인물 기록 판 하나와 그 판의 기대값.
사용: python game/verify/lore_click_fixture.py [--raw <남긴 스트림>]
  게이트 verify_viewer_click.py 를 _run_gates.sh 와 같은 환경으로 돌리며(LLM 0콜 · 각본 두뇌 · 임시 폴더 — state/·runs/ 무접촉)
  WL_VIEWCLICK_KEEP 로 그 판의 본 스트림을 받는다. 게이트가 ALL PASS 가 아니면 아무것도 쓰지 않는다(--raw 면 게이트를 건너뛰고 그 파일을 쓴다).
  fixtures/lore-click.jsonl         그 스트림에서 decisions[].obs(관측 동봉 — 화면은 안 읽는다, 크기 절반)만 뺀 것. 나머지는 엔진이 쓴 그대로
  fixtures/lore-click.scenes.json   inspect.mjs 가 화면과 맞댈 기대값 — 장부는 lorebook.fold_stream(파이썬 기준 접기, 게이트 ②가 TS 접기와 같음을 본다)
    notes        lore_note 를 쓴 틱 전부(틱·프레임·쓴 사람·화면 번호·열쇠·글) — 안 쓴 틱은 이 목록 밖의 틱
    rewind_none  열쇠 하나뿐인 대상(사람·NPC·장소·마을 구역)에 처음 쓴 틱 — 그 앞 프레임은 '모름', 그 프레임은 글
    rewind_edit  이미 있던 기록을 고쳐 쓴 틱 — 앞 프레임은 옛 글·옛 이름, 그 프레임은 새 글·새 이름(+ 이전 글)
    calls        사람 대상의 부르는 이름·기록이 시점마다 갈리는 프레임(초점 칩 전환 검사)
    mob_split    몹 이름('낯선 짐승'↔종 이름)이 시점마다 갈리는 프레임 — 없으면 null(inspect 가 그 부분을 SKIP)
    sweep        틱 줄의 쓸어냄(sweep) — 앞 프레임엔 있고 그 프레임엔 없는 층 기록 · 남는 사람·장소 기록
    ledgers      몇 프레임의 사람마다 장부 열쇠 전부('기록' 탭과 맞댄다)
    overlap      모험가가 문·물건·시체·함정과 한 칸에 선 프레임(겹침 순서 검사)
    live         라이브 꽁무니 검사 — 처음 줄 수·늘릴 줄 수 · 그 사이 HP 가 바뀌는 시점 사람
출력은 ASCII 만(Windows 콘솔).
"""
import io
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(HERE, 'fixtures')
sys.path.insert(0, ROOT)
import lorebook as LB  # noqa: E402

STRANGER, SELF, UNKNOWN_BEAST = '낯선 사람', '너', LB.UNKNOWN_BEAST   # identity.STRANGER·SELF (model.ts 와 같은 낱말)
GATE_ENV = dict(PYTHONUTF8='1', DUNGEON_ACTION_MODE='menu', DUNGEON_BRAIN_BACKEND='dummy',   # _run_gates.sh 머리와 같다
                DUNGEON_SKILLS='0', DUNGEON_TRPG_COMBAT='0', DUNGEON_RANDOM_SKILL='0')


def kept_stream():
    if '--raw' in sys.argv:
        return io.open(sys.argv[sys.argv.index('--raw') + 1], encoding='utf-8').read()
    tmp = tempfile.mkdtemp(prefix='wl_loreclick_')
    keep = os.path.join(tmp, 'stream.jsonl')
    r = subprocess.run([sys.executable, 'verify_viewer_click.py'], cwd=ROOT, env=dict(os.environ, WL_VIEWCLICK_KEEP=keep, **GATE_ENV),
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    last = (r.stdout.strip().splitlines() or ['(no stdout)'])[-1]
    if r.returncode != 0 or 'ALL PASS' not in last or not os.path.exists(keep):
        sys.exit('gate failed - fixture not written (rc %s): %s' % (r.returncode, last.encode('ascii', 'replace').decode()))
    text = io.open(keep, encoding='utf-8').read()
    os.remove(keep)
    os.rmdir(tmp)
    return text


def target_of(at, key):
    """lore_note 의 화면 번호 → 클릭 창의 대상 번호(model.targetId) — 지도에서 누를 수 없는 것(소지품 i·의뢰 q)은 None."""
    at = str(at or '')
    if re.fullmatch(r'[bmftd]\d+', at) or at == 'exit':
        return at
    if re.fullmatch(r'[rc]\d+', at):
        return 'zone:' + at
    if at == 'zone' and key.startswith('zone:'):
        return 'region:' + key[len('zone:'):]
    return None


def zone_at(zones, x, y):
    """level.zones 구간(rows[y] = [x0, 길이, 번호]…) → 장소 번호(model.cellRun)."""
    runs = (zones or {}).get('rows') or []
    row = runs[y] if 0 <= y < len(runs) else []
    for j in range(0, len(row) - 2, 3):
        if row[j] <= x < row[j] + row[j + 1]:
            return zones['ids'][row[j + 2]]
    return None


text = kept_stream()
rows = [json.loads(ln) for ln in text.splitlines() if ln.strip()]
for r in rows:
    for d in (r.get('decisions') or {}).values():
        d.pop('obs', None)
lines = [json.dumps(r, ensure_ascii=False, separators=(',', ':')) for r in rows]
meta = rows[0]
party = [p['char'] for p in meta['party']]
names = {p['char']: p.get('name') or p['char'] for p in meta['party']}
fold = LB.fold_stream(rows)
frame_row, frame_level, levels, lv = [], [], [], None      # 프레임 번호 → 줄 번호 · 그 프레임의 층 줄
for n, r in enumerate(rows):
    if r['kind'] == 'level':
        lv = r
        levels.append(dict(frame=len(frame_row), turn=r.get('turn'), depth=r.get('depth'), scope=r.get('scope'), town=r.get('depth') == 0,
                           art=bool((r.get('visual') or {}).get('art')), architecture=bool(r.get('architecture'))))
    if r['kind'] in ('level', 'tick'):
        frame_row.append(n)
        frame_level.append(lv)
assert len(frame_row) == len(fold), (len(frame_row), len(fold))
FR = {rows[n]['turn']: i for i, n in enumerate(frame_row) if rows[n]['kind'] == 'tick'}
book = lambda i, c: fold[i]['lore'].get(c, {})   # noqa: E731

notes = []
for i, n in enumerate(frame_row):
    r = rows[n]
    for c, d in sorted((r.get('decisions') or {}).items()) if r['kind'] == 'tick' else ():
        nt = d.get('lore_note')
        if nt:
            notes.append(dict(turn=r['turn'], frame=i, char=c, at=nt.get('at'), target=target_of(nt.get('at'), nt.get('key') or ''),
                              key=nt.get('key'), of=nt.get('of'), name=nt.get('name'), text=nt.get('text')))
single = re.compile(r'^(b\d+|npc:.+|zone:.+|obj:\d+:[rc]\d+)$')   # 열쇠 하나뿐인 대상(종류 열쇠가 없다 — model.keysFor)
rewind_none = [dict(frame=nt['frame'], before=nt['frame'] - 1, viewer=nt['char'], target=nt['target'], key=nt['key'], text=nt['text'])
               for nt in notes if nt['of'] == 'one' and nt['target'] and single.match(nt['key'] or '')
               and nt['key'] not in book(nt['frame'] - 1, nt['char']) and nt['key'] in book(nt['frame'], nt['char'])]
rewind_edit = []
for nt in notes:
    i, c, k = nt['frame'], nt['char'], nt['key']
    old, new = book(i - 1, c).get(k), book(i, c).get(k)
    if nt['target'] and nt['of'] == 'one' and old and new and old.get('text') != new.get('text'):
        rewind_edit.append(dict(frame=i, before=i - 1, viewer=c, target=nt['target'], key=k, prev=dict(name=old.get('name'), text=old.get('text')),
                                now=dict(name=new.get('name'), text=new.get('text'))))
calls = []
for nt in notes:
    if not re.fullmatch(r'b\d+', nt['target'] or ''):
        continue
    i, o = nt['frame'], nt['target'][1:]
    by = {c: dict(call=SELF, recs='self') if c == o else
          dict(call=(book(i, c).get('b' + o) or {}).get('name') or STRANGER,
               recs={'b' + o: book(i, c)['b' + o].get('text', '')} if 'b' + o in book(i, c) else {}) for c in party}
    if len({v['call'] for v in by.values()}) == len(party):   # writer = 그 틱에 대상을 본 사람(그 시점으로 열면 대상이 화면 안)
        calls.append(dict(frame=i, turn=nt['turn'], target=nt['target'], writer=nt['char'], real=names[o], by=by))
mob_split = None
for i, n in enumerate(frame_row):
    r = rows[n]
    if r['kind'] != 'tick' or mob_split:
        continue
    for m in r['monsters']:
        by = {c: m['kind'] if 'monster:' + m['kind'] in fold[i]['known'].get(c, set()) else UNKNOWN_BEAST for c in party}
        seers = [c for c in party if m['id'] in ((next((b for b in r['bots'] if b['char'] == c), {}).get('aware_of')) or [])]
        if len(set(by.values())) > 1 and seers:                # 그 몹을 아는(aware_of) 사람의 시점으로 연다
            mob_split = dict(frame=i, turn=r['turn'], target='m%d' % m['id'], writer=seers[0], by=by)
            break
sweep = None
for i, n in enumerate(frame_row):
    r = rows[n]
    sw = [(c, o['key']) for c, os_ in (r.get('lore_ops') or {}).items() for o in os_ if o['op'] == 'sweep'] if r['kind'] == 'tick' else []
    if sw and not sweep:
        key = sw[0][1]
        gone = [c for c in party if key in book(i - 1, c) and key not in book(i, c)]
        sweep = dict(frame=i - 1, after=i, turn=rows[frame_row[i - 1]]['turn'], key=key, gone_from=gone,
                     kept={c: sorted(k for k in book(i - 1, c) if k in book(i, c) and not k.startswith('obj:')) for c in party})
ledger_frames = sorted({x for x in ((sweep or {}).get('frame'), (sweep or {}).get('after'), len(fold) - 1) if x is not None}
                       | {s['frame'] for s in rewind_edit[:1]})
ledgers = [dict(frame=i, turn=fold[i]['turn'], by={c: sorted(book(i, c)) for c in party}) for i in ledger_frames]
overlap = []
for i, n in enumerate(frame_row):
    r, L = rows[n], frame_level[i]
    if r['kind'] != 'tick' or not L or L.get('depth', 0) < 1:
        continue
    for b in r['bots']:
        if not b['alive'] or b.get('won'):
            continue
        at = (b['x'], b['y'])
        mobs = sorted(((not m['alive']), 'm%d' % m['id']) for m in r['monsters'] if (m['x'], m['y']) == at and not m.get('concealed'))
        feats = ['f%d' % f['id'] for f in r['features'] if (f['x'], f['y']) == at and not f.get('concealed') and f['type'] not in ('exit', 'building')]
        traps = ['t%d' % k for k, tr in enumerate(r['traps']) if (tr['x'], tr['y']) == at and not tr.get('hidden')]
        passage = (['exit'] if list(L['exit']) == list(at) else []) + [d[2] for d in L.get('doors') or [] if (d[0], d[1]) == at]
        z = zone_at(L.get('zones'), *at)
        others = [x for _, x in mobs] + feats + traps + passage
        if others:
            want = ['b' + b['char']] + others + (['zone:' + z] if z else [])
            overlap.append(dict(frame=i, turn=r['turn'], focus=b['char'], x=at[0], y=at[1], want=want,
                                sig=''.join(sorted({x[0] for x in others})), groups=len({x[0] if x[0] != 'e' else 'd' for x in want})))
overlap.sort(key=lambda o: (-o['groups'], o['frame']))
overlap = [o for k, o in enumerate(overlap) if o['sig'] not in {p['sig'] for p in overlap[:k]}]   # 겹친 것의 꼴마다 첫 장면 하나(시체·물건·계단·문 …)
stop_turn = min([r['turn'] for r in rows if r['kind'] in ('stopped', 'end')] + [10 ** 9])
live = None
for i in range(1, len(frame_row)):
    a_, b_ = rows[frame_row[i - 1]], rows[frame_row[i]]
    if a_['kind'] != 'tick' or b_['kind'] != 'tick' or frame_level[i] is not frame_level[i - 1] or (frame_level[i].get('depth') or 0) < 1:
        continue
    for bb in b_['bots']:
        pb = next(x for x in a_['bots'] if x['char'] == bb['char'])
        if bb['alive'] and pb['hp'] != bb['hp'] and not live:
            live = dict(cut=frame_row[i - 1] + 1, grow=frame_row[i] + 1, focus=bb['char'], turn_cut=a_['turn'], turn_grow=b_['turn'],
                        hp_cut='%d/%d' % (max(0, pb['hp']), pb['maxhp']), hp_grow='%d/%d' % (max(0, bb['hp']), bb['maxhp']),
                        after_stop=a_['turn'] >= stop_turn)
assert not any(r['kind'] == 'end' for r in rows[:live['cut']]) if live else True
scenes = dict(v=1, made_by='game/verify/lore_click_fixture.py', party=party, names=names, frames=len(fold), levels=levels,
              notes=notes, rewind_none=rewind_none, rewind_edit=rewind_edit, calls=calls, mob_split=mob_split, sweep=sweep,
              ledgers=ledgers, overlap=overlap[:12], live=live)

os.makedirs(OUT, exist_ok=True)
with io.open(os.path.join(OUT, 'lore-click.jsonl'), 'w', encoding='utf-8', newline='\n') as f:
    f.write(''.join(ln + '\n' for ln in lines))
with io.open(os.path.join(OUT, 'lore-click.scenes.json'), 'w', encoding='utf-8', newline='\n') as f:
    json.dump(scenes, f, ensure_ascii=False, indent=1)
    f.write('\n')
print('ok frames=%d ticks=%d levels=%s notes=%d rewind_none=%d rewind_edit=%d calls=%d mob_split=%s sweep=%s overlap=%d live=%s bytes=%d' % (
    len(fold), sum(r['kind'] == 'tick' for r in rows), [(x['frame'], x['depth']) for x in levels], len(notes), len(rewind_none), len(rewind_edit),
    len(calls), bool(mob_split), bool(sweep), len(overlap), (live or {}).get('turn_cut'), sum(len(ln.encode('utf-8')) + 1 for ln in lines)))

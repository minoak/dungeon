# -*- coding: utf-8 -*-
"""마을 격자 검사기(0콜) — town.json 또는 후보 파일을 엔진 규격(docs/town-map-contract.md)으로 검사한다.
사용: python check_town.py town.json | art/town-v1/town-candidate.json | art/town-v1/layout.json(town-layout-v1 원본) | {"layout": 참조} town 파일
검사: 행 길이 동일 · 바깥 테두리 벽 · '>' 정확히 하나 · 출발 자리(1~9) 3개 이상 · NPC 좌표가 바닥 · NPC id 가 entities/npc 에 있음
     · 출발 자리 1에서 '>'와 모든 NPC 곁까지 길이 이어짐(BFS) · 엔진 from_ascii 로드."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))   # tools/ 로 이동(2026-09-13 정리) — 리포 루트 모듈 import 용
import json
import os
import sys

os.environ.setdefault('DUNGEON_BRAIN_BACKEND', 'dummy')
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 리포 루트(tools/ 이동, 2026-09-13)
sys.path.insert(0, HERE)
import dungeon_gm as G          # noqa: E402
import entities as ENT          # noqa: E402
import town_layout as TL        # noqa: E402


def load_spec(path):
    """town.json(map+npcs) · {"layout": 상대경로} 참조 · layout 원본(town-layout-v1) 전부 같은 꼴 {map, npcs}로."""
    spec = json.load(open(path, encoding='utf-8'))
    if spec.get('layout'):
        lpath = os.path.join(os.path.dirname(os.path.abspath(path)), spec['layout'])
        spec = json.load(open(lpath, encoding='utf-8'))
    if spec.get('schema') == 'town-layout-v1':
        res = TL.compile_layout(spec)                       # 제작자의 다섯 필드 → 격자(그림에서 추측 없음)
        return {'map': res['map'], 'npcs': res['npcs'], '_compiled': True}
    return spec


def check(path):
    spec = load_spec(path)
    rows, problems, notes = spec['map'], [], []
    if spec.get('_compiled'):
        notes.append('layout 원본(town-layout-v1)에서 컴파일한 격자')
    w = len(rows[0])
    if any(len(r) != w for r in rows):
        problems.append('행 길이가 다르다: %s' % sorted({len(r) for r in rows}))
    if not (all(c == '#' for c in rows[0]) and all(c == '#' for c in rows[-1]) and all(r[0] == '#' and r[-1] == '#' for r in rows)):
        problems.append("바깥 테두리가 전부 '#'가 아니다")
    exits = sum(r.count('>') for r in rows)
    if exits != 1:
        problems.append("'>'(던전 입구)가 %d개 — 정확히 하나여야 한다" % exits)
    starts = sorted(c for r in rows for c in r if c.isdigit())
    if len(starts) < 3:
        problems.append('출발 자리(1~9)가 %d개 — 파티 인원 3 이상 필요' % len(starts))
    bad = sorted({c for r in rows for c in r} - set('#.+>&0123456789'))
    if bad:
        problems.append('모르는 기호 %s' % bad)
    npc_defs = {d['id'] for d in ENT.by_kind('npc')}
    for n in spec.get('npcs', []):
        x, y = int(n['x']), int(n['y'])
        label = n.get('id') or n.get('name') or '?'
        if not (0 <= y < len(rows) and 0 <= x < w) or rows[y][x] not in '.&' and not rows[y][x].isdigit():
            problems.append('NPC %s 좌표 (%d,%d)가 바닥이 아니다' % (label, x, y))
        if n.get('id') and n['id'] not in npc_defs:
            problems.append('NPC id %r 가 entities/npc 에 없다' % n['id'])
        if not n.get('id'):
            notes.append('NPC %s 에 id 가 없다(옛 인라인 꼴 또는 후보) — 채택 전 entities/npc 정의와 id 필요' % label)
    if problems:
        return problems, notes
    try:
        d, st = G.Dungeon.from_ascii(rows, seed=1, depth=0)
    except Exception as e:                                      # 엔진이 못 읽으면 그 말을 그대로
        return ['엔진 from_ascii 실패: %s' % e], notes
    d.town = True
    sx, sy = st.get('1') or next(iter(st.values()))
    targets = [('던전 입구', d.exit)] + [(n.get('id') or n.get('name'), (int(n['x']), int(n['y']))) for n in spec.get('npcs', [])]
    for label, (tx, ty) in targets:
        if not d.path_to(sx, sy, tx, ty, []):
            problems.append('출발 자리 1(%d,%d)에서 %s(%d,%d)까지 길이 없다' % (sx, sy, label, tx, ty))
    floors = sum(r.count('.') + r.count('&') for r in rows)
    notes.append('격자 %d×%d · 바닥 %d칸 · 출발 %s · 입구 %s · NPC %d' % (w, len(rows), floors, ','.join(starts), d.exit, len(spec.get('npcs', []))))
    return problems, notes


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    ok = True
    for p in sys.argv[1:]:
        problems, notes = check(p)
        print('== %s' % p)
        for n in notes:
            print('  · ' + n)
        for pr in problems:
            print('  X ' + pr)
        print('  ' + ('OK' if not problems else '문제 %d건' % len(problems)))
        ok = ok and not problems
    sys.exit(0 if ok else 1)

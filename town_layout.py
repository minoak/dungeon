"""명시적인 마을 layout → 격자. 파일·엔진·LLM에 의존하지 않는 변환 규칙.

원본 좌표는 외곽벽을 제외한 0-based [x,y]. 반환 좌표는 border만큼 이동한다.
그림에서 충돌을 추측하지 않고 제작자가 적은 다섯 필드만 사용한다.
"""
from collections import deque


def compile_layout(layout):
    from town_spaces import resolve
    layout = resolve(layout)
    if layout.get('schema') != 'town-layout-v1':
        raise ValueError('지원하지 않는 layout schema')

    def integer(value, label, low=0):
        if type(value) is not int or value < low:
            raise ValueError('%s: %d 이상의 정수 필요' % (label, low))
        return value

    size = layout.get('size')
    if not isinstance(size, list) or len(size) != 2:
        raise ValueError('size는 [width,height]')
    w, h = (integer(v, 'size', 1) for v in size)
    pad = integer(layout.get('border', 1), 'border', 1)
    cells = [['.'] * w for _ in range(h)]

    def xy(value, label):
        if not isinstance(value, list) or len(value) != 2:
            raise ValueError('%s: [x,y] 필요' % label)
        x, y = (integer(v, label) for v in value)
        if x >= w or y >= h:
            raise ValueError('%s: 맵 밖 %s' % (label, value))
        return x, y

    def unique(items, label):
        ids = [item.get('id') for item in items]
        if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
            raise ValueError('%s: 비어 있거나 중복된 id' % label)

    rects = layout['blocked_rects']
    unique(rects, 'blocked_rects')
    for block in rects:
        rect = block.get('rect')
        if not isinstance(rect, list) or len(rect) != 4:
            raise ValueError('blocked_rects.rect는 [x,y,width,height]')
        x, y = xy(rect[:2], block['id'])
        rw, rh = (integer(v, block['id'], 1) for v in rect[2:])
        if x + rw > w or y + rh > h:
            raise ValueError('막힌 사각형이 맵 밖: ' + block['id'])
        for yy in range(y, y + rh):
            for xx in range(x, x + rw):
                cells[yy][xx] = '#'

    entrances = layout['entrances']
    unique(entrances, 'entrances')
    special = set()
    for door in entrances:
        x, y = xy(door['cell'], door['id'])
        if (x, y) in special:
            raise ValueError('출입구 칸 중복')
        special.add((x, y))
        if door.get('kind') not in ('threshold', 'door'):
            raise ValueError('출입구 kind는 threshold 또는 door')
        cells[y][x] = '+' if door['kind'] == 'door' else '.'

    def walkable(x, y):
        return 0 <= x < w and 0 <= y < h and cells[y][x] != '#'

    for door in entrances:
        x, y = door['cell']
        if door['kind'] == 'door' and not ((walkable(x-1,y) and walkable(x+1,y)) or (walkable(x,y-1) and walkable(x,y+1))):
            raise ValueError('문 양쪽에 통로가 없다: ' + door['id'])

    def place(value, symbol, label):
        x, y = xy(value, label)
        if not walkable(x, y) or (x, y) in special:
            raise ValueError('%s: 벽 또는 다른 배치와 겹친다 %s' % (label, value))
        special.add((x, y))
        cells[y][x] = symbol
        return [x + pad, y + pad]

    entry = place(layout['dungeon_entry']['cell'], '>', 'dungeon_entry')
    starts = layout['starts']
    if not isinstance(starts, dict) or len(starts) < 3 or '1' not in starts:
        raise ValueError('starts에는 1을 포함한 출발점 3개 이상 필요')
    shifted_starts = {}
    for char, pos in starts.items():
        if char not in '123456789' or len(char) != 1:
            raise ValueError('출발점 키는 1~9')
        shifted_starts[char] = place(pos, char, 'start:' + char)
    unique(layout['npcs'], 'npcs')
    npcs = []
    for npc in layout['npcs']:
        x, y = place(npc['cell'], '&', 'npc:' + npc['id'])
        npcs.append({'id': npc['id'], 'x': x, 'y': y})

    # 모든 출발점·문턱·NPC·던전 진입점이 같은 연결 성분에 속해야 한다.
    start = tuple(starts['1'])
    seen, queue = {start}, deque([start])
    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
            if walkable(nx, ny) and (nx, ny) not in seen:
                seen.add((nx, ny)); queue.append((nx, ny))
    targets = [('start:' + c, p) for c, p in starts.items()]
    targets += [('npc:' + n['id'], n['cell']) for n in layout['npcs']]
    targets += [('entrance:' + e['id'], e['cell']) for e in entrances]
    targets += [('dungeon_entry', layout['dungeon_entry']['cell'])]
    for label, pos in targets:
        if tuple(pos) not in seen:
            raise ValueError('출발점 1에서 도달할 수 없다: ' + label)
    spaces = layout.get('resolved_spaces')
    if spaces:
        for connection in spaces['connections']:
            if any(tuple(p) not in seen for p in connection['cells']):
                raise ValueError('구역 연결이 막혔다: %s → %s' % (connection['from'], connection['to']))
    # D90(2026-09-20) 마을 생활 배치(선택 필드) — 그림 속 고정물 곁의 오브젝트(life_objects)와 새 정착 주민(life_npcs).
    #   격자(map)에는 아무것도 찍지 않는다 — 끈 판의 격자·결과가 옛 판과 같아야 한다. 여기서는 검증만 하고 pad 적용 좌표를 결과에 싣는다.
    #   세우는 것은 러너(build_town)가 마을 생활 스위치를 켠 판에서만 한다. 검사: 바닥·다른 배치(문턱·출발·NPC·입구)와 안 겹침·서로 안 겹침·
    #   구역 연결 칸이 아님·출발점 1에서 도달. 주민은 통행을 막는 몸이므로 세운 뒤에도 남은 바닥이 전부 이어져 있어야 한다(외길을 막지 않는다).
    life = {}
    if layout.get('life_objects') is not None or layout.get('life_npcs') is not None:
        conn_cells = {tuple(p) for c in layout.get('connections', []) for p in c.get('cells', [])}
        taken = set(special)
        for key, need in (('life_objects', ('id', 'entity', 'cell')), ('life_npcs', ('id', 'cell'))):
            items = layout.get(key) or []
            unique(items, key)
            out = []
            for item in items:
                label = '%s:%s' % (key, item['id'])
                if any(k not in item for k in need) or (key == 'life_objects' and (not isinstance(item['entity'], str) or not item['entity'])):
                    raise ValueError('%s: %s 필요' % (label, '·'.join(need)))
                x, y = xy(item['cell'], label)
                if not walkable(x, y) or (x, y) in taken:
                    raise ValueError('%s: 벽 또는 다른 배치와 겹친다 %s' % (label, item['cell']))
                if (x, y) in conn_cells:
                    raise ValueError('%s: 구역 연결 칸에는 둘 수 없다 %s' % (label, item['cell']))
                if (x, y) not in seen:
                    raise ValueError('출발점 1에서 도달할 수 없다: ' + label)
                taken.add((x, y))
                out.append({'id': item['id'], **({'entity': item['entity']} if key == 'life_objects' else {}),
                            **({'row': int(item['row'])} if item.get('row') is not None else {}), 'x': x + pad, 'y': y + pad})
            life[key] = out

        def open_cells(blocked):
            if start in blocked:
                return set()
            got, todo = {start}, deque([start])
            while todo:
                cx, cy = todo.popleft()
                for nx, ny in ((cx-1,cy),(cx+1,cy),(cx,cy-1),(cx,cy+1)):
                    if walkable(nx, ny) and (nx, ny) not in got and (nx, ny) not in blocked:
                        got.add((nx, ny)); todo.append((nx, ny))
            return got
        bodies = {tuple(n['cell']) for n in layout['npcs']}
        more = {(n['x'] - pad, n['y'] - pad) for n in life.get('life_npcs', [])}
        if open_cells(bodies) - more != open_cells(bodies | more):
            raise ValueError('life_npcs: 새 주민이 길을 막는다(세운 뒤 닿지 못하는 바닥이 생긴다)')
    fullw = w + 2 * pad
    walker_rects = layout.get('walker_rects', {})
    for eid, rect in walker_rects.items():
        if not isinstance(rect, list) or len(rect) != 4 or any(type(v) is not int for v in rect):
            raise ValueError('walker_rects는 정수 [x,y,w,h]: ' + eid)
        x, y, rw, rh = rect
        if x < 0 or y < 0 or rw < 1 or rh < 1 or x+rw > w or y+rh > h:
            raise ValueError('walker_rects가 맵 밖: ' + eid)
    rows = ['#' * fullw] * pad + ['#' * pad + ''.join(r) + '#' * pad for r in cells] + ['#' * fullw] * pad
    return {'map': rows, 'size': [fullw, h + 2 * pad], 'pad': pad,
            'starts': shifted_starts, 'npcs': npcs, 'dungeon_entry': entry,
            'entrances': [{**e, 'cell': [e['cell'][0]+pad, e['cell'][1]+pad]} for e in entrances],
            'reachable_cells': len(seen), 'walker_rects': walker_rects,
            **life,                                    # D90 life_objects·life_npcs — layout 에 그 필드가 있을 때만(없는 layout 의 결과는 옛 그대로)
            **({'spaces': spaces} if spaces else {})}


def visual_layer(layout, compiled):
    """클라이언트가 그릴 시각 레이어(엔진은 무시) — layout 의 그림 정보 + 격자 오프셋(border). 좌표는 오프셋 전(클라이언트가 더한다).
    ground: 바닥 사각형(타일 이름) · buildings: 발 기준 앵커(x=중심 px, footY=정면 벽선 아래 px, width) · props: 발 좌표 px · npcs: 외형 행+칸."""
    pad = compiled['pad']
    out = {'schema': 'town-visual-v1', 'tileSize': layout['tileSize'], 'offset': [pad, pad],
           'ground': [dict(g) for g in layout.get('ground', [])],
           'buildings': [], 'props': [dict(p) for p in layout.get('props', [])],
           'npcs': [{'id': n['id'], 'row': int(n.get('row', 0)), 'cell': list(n['cell'])} for n in layout.get('npcs', [])]}
    if layout.get('paving'):
        from copy import deepcopy
        out['paving'] = deepcopy(layout['paving'])
    if layout.get('art'):
        from copy import deepcopy
        out['art'] = deepcopy(layout['art'])
    if layout.get('guild'):
        g = layout['guild']
        out['buildings'].append({'id': 'guild', 'texture': 'guild', 'x': g['x'], 'footY': g['footY'], 'width': g['width']})
    if compiled.get('spaces'):
        spaces = compiled['spaces']
        out['spaces'] = spaces
        out['buildings'].extend({k:b[k] for k in ('id','name','texture','x','footY','width')} for b in spaces['buildings'])
    return out


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
    fullw = w + 2 * pad
    rows = ['#' * fullw] * pad + ['#' * pad + ''.join(r) + '#' * pad for r in cells] + ['#' * fullw] * pad
    return {'map': rows, 'size': [fullw, h + 2 * pad], 'pad': pad,
            'starts': shifted_starts, 'npcs': npcs, 'dungeon_entry': entry,
            'entrances': [{**e, 'cell': [e['cell'][0]+pad, e['cell'][1]+pad]} for e in entrances],
            'reachable_cells': len(seen), **({'spaces': spaces} if spaces else {})}


def visual_layer(layout, compiled):
    """클라이언트가 그릴 시각 레이어(엔진은 무시) — layout 의 그림 정보 + 격자 오프셋(border). 좌표는 오프셋 전(클라이언트가 더한다).
    ground: 바닥 사각형(타일 이름) · buildings: 발 기준 앵커(x=중심 px, footY=정면 벽선 아래 px, width) · props: 발 좌표 px · npcs: 외형 행+칸."""
    pad = compiled['pad']
    out = {'schema': 'town-visual-v1', 'tileSize': layout['tileSize'], 'offset': [pad, pad],
           'ground': [dict(g) for g in layout.get('ground', [])],
           'buildings': [], 'props': [dict(p) for p in layout.get('props', [])],
           'npcs': [{'id': n['id'], 'row': int(n.get('row', 0)), 'cell': list(n['cell'])} for n in layout.get('npcs', [])]}
    if layout.get('guild'):
        g = layout['guild']
        out['buildings'].append({'id': 'guild', 'texture': 'guild', 'x': g['x'], 'footY': g['footY'], 'width': g['width']})
    if compiled.get('spaces'):
        spaces = compiled['spaces']
        out['spaces'] = spaces
        out['buildings'].extend({k:b[k] for k in ('id','name','texture','x','footY','width')} for b in spaces['buildings'])
    return out


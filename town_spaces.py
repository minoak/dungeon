"""구역·건물 정의를 배치 인스턴스와 결합한다. 원본은 엔티티 정의와 layout뿐이다.

엔진이 아는 다섯 필드로 내려주므로 오래된 layout과 엔진의 from_layout을 유지한다.
좌표는 layout 내부 기준이다. 건물의 충돌·문턱·그림 앵커는 같은 footprint에서 나온다.
"""
from copy import deepcopy


def resolve(layout, definitions=None):
    if not layout.get('space'):
        return layout
    if definitions is None:
        import entities
        definitions = entities.load()
    out = deepcopy(layout)
    w, h = layout['size']

    def definition(eid, kind):
        d = definitions.get(eid)
        if not d or d.get('kind') != kind:
            raise ValueError('공간 정의 없음 또는 종류 불일치: %s (%s)' % (eid, kind))
        return d

    town = definition(layout['space'], 'map')
    if town['comps']['space']['role'] != 'town':
        raise ValueError('space는 town 역할의 map 정의여야 한다')
    owners, regions, region_ids = {}, [], set()
    for region in layout.get('regions', []):
        rid = region['id']
        if rid in region_ids:
            raise ValueError('구역 배치 id 중복: ' + rid)
        region_ids.add(rid)
        d = definition(region['entity'], 'map')
        if d['comps']['space']['role'] == 'town':
            raise ValueError('구역에 마을 전체 정의를 놓을 수 없다')
        if not region.get('rects'):
            raise ValueError('구역 경계가 비었다: ' + rid)
        for rect in region['rects']:
            if not isinstance(rect, list) or len(rect) != 4 or any(type(v) is not int for v in rect):
                raise ValueError('구역 rect는 정수 [x,y,w,h]')
            x, y, rw, rh = rect
            if x < 0 or y < 0 or rw < 1 or rh < 1 or x+rw > w or y+rh > h:
                raise ValueError('구역 경계가 맵 밖: ' + rid)
            for yy in range(y, y+rh):
                for xx in range(x, x+rw):
                    if (xx, yy) in owners:
                        raise ValueError('구역 경계 중복: ' + rid)
                    owners[xx, yy] = rid
        regions.append({**region, 'name': d['name'], 'role': d['comps']['space']['role']})
    if len(owners) != w*h:
        raise ValueError('모든 마을 칸에 구역이 필요하다')
    buildings, instance_ids, occupied = [], set(region_ids), []
    for inst in layout.get('buildings', []):
        bid = inst['id']
        if bid in instance_ids:
            raise ValueError('공간 배치 id 중복: ' + bid)
        instance_ids.add(bid)
        d = definition(inst['entity'], 'building')
        b = d['comps']['building']
        pos = inst.get('cell')
        if not isinstance(pos, list) or len(pos) != 2 or any(type(v) is not int for v in pos):
            raise ValueError('건물 cell은 정수 [x,y]')
        x, y = pos
        bw, bh = b['size']
        rid = inst.get('region')
        footprint = {(xx, yy) for yy in range(y,y+bh) for xx in range(x,x+bw)}
        if rid not in region_ids or any(owners.get(p) != rid for p in footprint):
            raise ValueError('건물이 소속 구역 밖에 있다: ' + bid)
        if any(footprint & prev for prev in occupied):
            raise ValueError('건물 점유 영역 중복: ' + bid)
        occupied.append(footprint)
        ex, ey = x+b['entrance'][0], y+b['entrance'][1]
        out.setdefault('blocked_rects', []).append({'id': bid+':footprint', 'rect':[x,y,bw,bh]})
        out.setdefault('entrances', []).append({'id':bid+':entrance','kind':'threshold','cell':[ex,ey],'building':bid})
        tile = layout['tileSize']
        buildings.append({**inst, 'name':d['name'], 'rect':[x,y,bw,bh], 'entrance':[ex,ey],
                          'texture':b['texture'], 'x':(x+bw/2)*tile, 'footY':(y+bh)*tile, 'width':bw*tile})
    connections = layout.get('connections', [])
    graph = {rid:set() for rid in region_ids}
    for c in connections:
        a, b = c['cells']
        if owners.get(tuple(a)) != c['from'] or owners.get(tuple(b)) != c['to'] or sum(abs(a[i]-b[i]) for i in (0,1)) != 1:
            raise ValueError('구역 연결은 두 구역의 인접 칸이어야 한다: %s' % c)
        graph[c['from']].add(c['to'])
        graph[c['to']].add(c['from'])
    visited, queue = set(), list(region_ids)[:1]
    while queue:
        rid = queue.pop()
        if rid not in visited:
            visited.add(rid)
            queue.extend(graph[rid]-visited)
    if visited != region_ids:
        raise ValueError('구역 연결 그래프가 끊겼다')
    out['resolved_spaces'] = {'id':town['id'], 'name':town['name'], 'regions':regions, 'buildings':buildings, 'connections':connections}
    return out

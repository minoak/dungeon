"""Isolated town design: writes only beside this script; never activates the map."""
from collections import Counter, deque
from copy import deepcopy
import base64
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
import town_layout
import town_spaces
import entities


def write(name, value):
    path = HERE / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def rect_cells(rect):
    x, y, w, h = rect
    return {(xx, yy) for yy in range(y, y+h) for xx in range(x, x+w)}


def build():
    # Snapshot existing definitions for the draft. Production entities are read-only.
    definitions = deepcopy(entities.read())
    layout = dict(schema='town-layout-v1', id='town-six-districts-draft-v1',
                  space='town_wonderland', label='원더랜드 — 여섯 구역 초안',
                  size=[64, 48], tileSize=48, border=1, regions=[], buildings=[],
                  ground=[dict(tile='grass', rect=[0, 0, 64, 48])],
                  connections=[], blocked_rects=[], entrances=[],
                  starts={'1': [35, 13], '2': [10, 27], '3': [10, 13]},
                  dungeon_entry={'cell': [55, 42]},
                  npcs=[dict(id='guild_receptionist', cell=[37, 11], row=0),
                        dict(id='tavern_keeper', cell=[10, 26], row=1),
                        dict(id='temple_attendant', cell=[10, 12], row=2)],
                  props=[], interiors=False,
                  note='독립 초안. town.json 미연결. 새 시설·오브젝트는 배치만, 기능 미구현.')
    regions = [
        ('temple_district', 'town_temple', '신전 구역', [[0, 0, 20, 15]], 'district',
         '신전과 정원, 추모비가 있는 조용한 구역', '기도하는 사람과 이름을 읽는 사람이 앞뜰을 나누어 쓴다.'),
        ('guild_district', 'town_guild', '모험가 길드 구역', [[25, 0, 39, 15]], 'district',
         '길드 건물과 게시판, 모험자들이 모이는 앞마당', '여행에서 돌아온 사람과 동료를 찾는 사람이 앞마당에서 만난다.'),
        ('main_street', 'town_main_street', '번화가', [[20, 0, 5, 15], [0, 15, 40, 15]], 'street',
         '시장 노점과 잡화점, 주점이 큰길을 따라 있는 구역', '물건을 나르는 사람과 쉬어 가는 사람이 오간다. 서쪽 끝에는 마을 밖으로 향하는 길목이 있다.'),
        ('shop_district', 'town_shops', '상점가', [[40, 15, 24, 17]], 'district',
         '대장간과 공방, 장비점이 작업 마당을 둘러싼 구역', '큰길 쪽에는 진열대가, 건물 사이에는 작업장이 놓여 있다.'),
        ('residential_district', 'town_residential', '주거구역', [[0, 30, 40, 18]], 'district',
         '주민의 집과 공동 숙소, 여관들이 골목을 나누어 쓰는 구역', '작은 잠자리부터 마당 딸린 숙소까지 건물의 크기와 차림이 다르다.'),
        ('dungeon_district', 'town_dungeon', '던전 입구 구역', [[40, 32, 24, 16]], 'district',
         '던전으로 내려가는 입구와 출발 전 머무는 마당', '계단 앞의 돌바닥에는 오가는 이들의 발자국이 겹친다.'),
    ]
    for rid, eid, name, rects, role, trait, history in regions:
        definitions[eid] = dict(id=eid, name=name, kind='map', tags=['town'],
                                comps=dict(space=dict(role=role), story=dict(trait=trait, history=history)),
                                note='지도 초안 문구. 런타임 미적용.')
        layout['regions'].append(dict(id=rid, entity=eid, name=name, rects=rects))
    definitions['town_wonderland'] = dict(id='town_wonderland', name='원더랜드 마을', kind='map',
        tags=['town'], comps=dict(space=dict(role='town'), story=dict(
            trait='여섯 구역의 길과 마당이 이어지는 마을',
            history='일하는 자리와 쉬는 자리, 여행을 떠나는 자리가 함께 있다.')))

    def building(iid, eid, cell, region, name=None, size=None, use=None):
        if size:
            definitions[eid] = dict(id=eid, name=name, kind='building', tags=['town', 'building'],
                comps=dict(building=dict(size=size, entrance=[size[0]//2, size[1]-1], texture='draft_'+eid),
                           story=dict(trait=use, history='지도 초안에 마련한 공간. 세부 서비스는 아직 정하지 않았다.')),
                note='초안 전용 건물. draft_ 텍스처는 미리보기의 임시 도형이며 게임 에셋이 아니다.')
        b = dict(id=iid, entity=eid, cell=cell, region=region)
        layout['buildings'].append(b)
        return b

    building('temple_1', 'temple', [5, 5], 'temple_district')
    building('guild_1', 'guild_hall', [31, 4], 'guild_district')
    building('tavern_1', 'tavern', [3, 19], 'main_street')
    building('gate_1', 'dungeon_gate', [51, 37], 'dungeon_district')
    building('general_1', 'general_store', [27, 18], 'main_street', '잡화점', [9, 6], use='생활용품과 식료품을 진열할 가게')
    building('smith_1', 'blacksmith', [43, 17], 'shop_district', '대장간', [8, 6], use='화덕과 모루 작업장을 둔 건물')
    building('workshop_1', 'craft_workshop', [54, 17], 'shop_district', '공방', [8, 6], use='목재와 도구를 놓는 작업 건물')
    building('equipment_1', 'equipment_store', [49, 25], 'shop_district', '장비점', [9, 6], use='무기와 방어구를 진열할 가게')
    building('dorm_1', 'shared_lodging', [2, 33], 'residential_district', '공동 숙소', [8, 6], use='여럿이 잠자리를 나누는 작은 숙소')
    building('home_1', 'small_home', [13, 33], 'residential_district', '주민의 집', [6, 5], use='작은 현관과 생활 마당이 있는 집')
    building('inn_1', 'ordinary_inn', [22, 33], 'residential_district', '일반 여관', [9, 6], use='독립 객실을 둘 여관')
    building('home_2', 'small_home', [3, 42], 'residential_district')
    building('home_3', 'small_home', [13, 42], 'residential_district')
    building('garden_inn_1', 'garden_inn', [27, 41], 'residential_district', '정원 숙소', [10, 6], use='넓은 객실과 작은 정원을 둔 숙소')

    def ground(tile, *rects):
        layout['ground'].extend(dict(tile=tile, rect=list(r)) for r in rects)
    ground('plaza_a', [20, 0, 5, 30], [0, 26, 64, 4], [0, 15, 64, 2],
           [3, 11, 14, 4], [29, 10, 20, 5], [40, 23, 24, 2], [40, 15, 3, 33],
           [49, 41, 12, 5])
    ground('earth', [2, 26, 14, 3], [16, 18, 9, 8], [43, 23, 19, 2],
           [0, 30, 40, 3], [0, 39, 40, 3], [10, 30, 3, 18], [19, 30, 3, 18],
           [25, 39, 14, 9])
    ground('alley', [37, 30, 6, 18], [43, 32, 21, 3], [47, 33, 3, 15],
           [16, 7, 5, 8], [24, 12, 5, 5])
    for a, b, p, q in [
        ('temple_district','main_street',[19,12],[20,12]),
        ('guild_district','main_street',[25,13],[24,13]),
        ('guild_district','shop_district',[45,14],[45,15]),
        ('main_street','shop_district',[39,27],[40,27]),
        ('main_street','residential_district',[21,29],[21,30]),
        ('residential_district','shop_district',[39,31],[40,31]),
        ('residential_district','dungeon_district',[39,40],[40,40]),
        ('shop_district','dungeon_district',[47,31],[47,32]),
    ]:
        layout['connections'].append({'from':a, 'to':b, 'cells':[p,q]})

    objects=[]
    def obj(oid, name, cell, region, shape, use, solid=True, interaction=None):
        # Design-only objects; they are NOT Feature instances or executable actions.
        objects.append(dict(id=oid, name=name, cell=cell, region=region, shape=shape,
                            proposed_use=use, implemented=False, solid=solid,
                            interaction_cell=interaction or [cell[0],cell[1]+1]))
        if solid:
            layout['blocked_rects'].append(dict(id='draft:'+oid, rect=cell+[1,1]))
    obj('anvil','모루',[46,23],'shop_district','anvil','향후 장착 장비 손질·강화 후보. 수치·비용 미정.')
    obj('workbench','작업대',[59,23],'shop_district','table','향후 제작·수선 작업 후보')
    obj('display','장비 진열대',[60,28],'shop_district','rack','향후 장비 살펴보기·거래 후보')
    obj('produce','식료품 노점',[17,20],'main_street','stall','향후 식료품 거래 후보')
    obj('goods','잡화 노점',[22,22],'main_street','stall','향후 잡화 거래 후보', interaction=[23,22])
    obj('table','주점 바깥 탁자',[17,25],'main_street','table','향후 앉기·식사·대화 후보')
    obj('bench_market','길가 벤치',[25,25],'main_street','bench','향후 앉아서 쉬기 후보')
    obj('noticeboard','길드 게시판 자리',[28,10],'guild_district','board','기존 길드 게시판의 시각 표식. 새 의뢰 기능 없음', interaction=[28,11])
    obj('bench_guild','길드 벤치',[49,12],'guild_district','bench','향후 대기·대화 후보')
    obj('memorial','추모비',[3,6],'temple_district','stone','향후 새겨진 글 읽기 후보')
    obj('bench_temple','정원 벤치',[15,12],'temple_district','bench','향후 앉아서 쉬기 후보')
    obj('well','공동 우물',[15,40],'residential_district','well','향후 물 긷기 후보', interaction=[16,40])
    obj('laundry','빨랫줄',[4,31],'residential_district','laundry','생활 소품. 세탁 기능 미정')
    obj('storage','숙소 보관함',[33,39],'residential_district','crate','향후 물건 보관 후보')
    obj('bench_gate','출발 마당 벤치',[60,44],'dungeon_district','bench','향후 대기·대화 후보')
    exterior = dict(id='outside_reserved', name='마을 밖 출구 예정지', cell=[0,27],
                    region='main_street', implemented=False, runtime_feature=None,
                    note='경계 밖 전이 없음. dungeon_entry에 넣지 않는다. 바깥 맵 연결은 후속 작업.')

    # Resolve explicitly against draft definitions; avoid touching the global entity registry.
    resolved = town_spaces.resolve(layout, definitions)
    resolved.pop('space')
    compiled = town_layout.compile_layout(resolved)
    visual = town_layout.visual_layer(resolved, compiled)
    owners={}
    for r in layout['regions']:
        for rect in r['rects']:
            for p in rect_cells(rect):
                assert p not in owners, ('overlap',p)
                owners[p]=r['id']
    assert len(owners)==64*48
    pad=compiled['pad']
    floor={(x-pad,y-pad) for y,row in enumerate(compiled['map']) for x,v in enumerate(row) if v!='#'}
    assert floor <= owners.keys()
    start=tuple(layout['starts']['1'])
    reached={start}; queue=deque([start])
    while queue:
        x,y=queue.popleft()
        for n in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
            if n in floor and n not in reached:
                reached.add(n);queue.append(n)
    assert reached==floor, ('isolated floor',floor-reached)
    for o in objects:
        assert owners[tuple(o['cell'])]==o['region'], o['id']
        assert tuple(o['interaction_cell']) in reached, ('object approach',o['id'])
        assert sum(abs(a-b) for a,b in zip(o['cell'],o['interaction_cell']))==1
    assert tuple(exterior['cell']) in reached
    walkers=[]
    for eid in ('apprentice_adventurer','wandering_adventurer','street_vendor'):
        walk=definitions[eid]['comps']['npc']['walk']
        cells={p for p in floor if owners[p]==walk['region']}
        if walk.get('rect'):
            zone=rect_cells(walk['rect'])
            assert all(owners.get(p)==walk['region'] for p in zone), eid
            cells &= zone
        assert cells, ('no walker spawn',eid)
        walkers.append(dict(id=eid,region=walk['region'],rect=walk.get('rect'),candidate_cells=len(cells)))
    party_regions=sorted({b['region'] for b in layout['buildings'] if b['entity'] in ('guild_hall','tavern')})
    assert len(party_regions)==2
    for eid in ('guild_hall','tavern','dungeon_gate'):
        assert sum(b['entity']==eid for b in layout['buildings'])==1
    assert sum(row.count('>') for row in compiled['map'])==1
    gate=next(b for b in visual['spaces']['buildings'] if b['entity']=='dungeon_gate')
    assert tuple(layout['dungeon_entry']['cell']) in {(gate['entrance'][0],gate['entrance'][1]+1)}
    region_rows=[]
    for r in layout['regions']:
        region_rows.append(dict(id=r['id'],name=r['name'],rects=r['rects'],
            total_cells=sum(v==r['id'] for v in owners.values()),
            floor_cells=sum(owners[p]==r['id'] for p in floor)))
    inputs=['town_spaces.py','town_layout.py','entities/npc/apprentice_adventurer.json',
            'entities/npc/wandering_adventurer.json','entities/npc/street_vendor.json']
    report=dict(status='PASS',scope='공간 데이터만 검증. 게임·생산·강화 기능 검증 아님.',
        size=layout['size'],total_cells=len(owners),floor_cells=len(floor),reachable_floor_cells=len(reached),
        unowned_floor_cells=0,overlap_cells=0,regions=region_rows,buildings=len(layout['buildings']),
        dungeon_exit_features=1,party_regions=party_regions,walkers=walkers,
        object_approaches=len(objects),exterior_exit_reserved_only=True,
        source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in inputs})
    for r in layout['regions']:
        write('entities/map/'+r['entity']+'.json',definitions[r['entity']])
    write('entities/map/town_wonderland.json',definitions['town_wonderland'])
    for b in layout['buildings']:
        write('entities/building/'+b['entity']+'.json',definitions[b['entity']])
    write('layout.json',layout)
    write('design-objects.json',dict(objects=objects,reserved_exits=[exterior],
        lodging_tiers=[dict(building='dorm_1',tier='공동 잠자리',price=None),
                       dict(building='inn_1',tier='일반 객실',price=None),
                       dict(building='garden_inn_1',tier='넓은 객실·정원',price=None)]))
    write('compiled.json',dict(**compiled,visual=visual))
    write('validation.json',report)
    (HERE/'town-ascii.txt').write_text('\n'.join(compiled['map'])+'\n',encoding='utf-8')
    assets={}
    for key,path in dict(terrain='art/town-v1/runtime/terrain.png',guild='art/town-v1/runtime/guild.png',
                         temple='art/town-v2/runtime/temple.png',tavern='art/town-v2/runtime/tavern.png',
                         gate='art/town-v2/runtime/gate.png').items():
        assets[key]='data:image/png;base64,'+base64.b64encode((ROOT/path).read_bytes()).decode()
    data=dict(layout=layout,compiled=compiled,visual=visual,objects=objects,exterior=exterior,report=report,assets=assets)
    template=(HERE/'preview.template.html').read_text(encoding='utf-8')
    payload=json.dumps(data,ensure_ascii=False).replace('<','\\u003c')
    (HERE/'preview.html').write_text(template.replace('__DRAFT_DATA__',payload),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('status','total_cells','floor_cells','buildings','party_regions','object_approaches')},ensure_ascii=False))


if __name__=='__main__':
    build()

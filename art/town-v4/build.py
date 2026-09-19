"""Trace the approved 1536x1024 concept, at 16 source pixels per engine cell.

The image is authored art, never inferred collision. This file owns the explicit
walk polygons, physical footprints, occlusion silhouettes and region boundaries.
Run from any directory; does not touch runs or call an LLM.
"""
import json
import sys
from collections import deque
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from town_layout import compile_layout

def write(name, data):
    # newline='\n': Windows 의 기본 줄끝 변환(CRLF)으로 생성물이 통째로 바뀌지 않게(리포의 생성물은 LF — 09-20 재생성 때 실제로 밟았다)
    (HERE / name).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')

def rect(x, y, w, h):
    return [[x,y],[x+w,y],[x+w,y+h],[x,y+h]]

def inside(x, y, poly):
    hit = False
    for (ax,ay),(bx,by) in zip(poly,poly[1:]+poly[:1]):
        if (ay>y)!=(by>y) and x < (bx-ax)*(y-ay)/(by-ay)+ax:
            hit = not hit
    return hit

regions = [
    ('temple_district','town_temple',[[0,0,39,21]]),
    ('guild_district','town_guild',[[50,0,46,21]]),
    ('main_street','town_main_street',[[39,0,11,21],[0,21,59,16],[39,37,11,27],[50,37,9,1]]),
    ('shop_district','town_shops',[[59,21,37,17]]),
    ('residential_district','town_residential',[[0,37,39,27]]),
    ('dungeon_district','town_dungeon',[[50,38,46,26]]),
]
# All coordinates below are SOURCE IMAGE pixels. Curbs, walls, water, gardens
# remain solid. Rectangular ground filling would destroy the original geometry.
walk = [
    rect(654,0,129,333), rect(646,320,153,548), rect(640,868,159,156),
    [[0,464],[99,474],[125,500],[219,500],[234,541],[626,541],[650,523],[956,532],[964,586],[828,585],[795,603],[654,602],[610,588],[196,588],[124,574],[0,556]],
    rect(216,286,344,65), rect(508,181,49,147), rect(100,158,141,133),
    rect(153,122,83,64), rect(127,259,104,68), rect(221,322,28,205),
    rect(556,331,410,55), rect(484,374,471,168),
    rect(842,258,570,78), rect(1360,191,75,145),
    rect(1421,0,57,374), rect(1389,320,98,64),
    rect(938,535,543,63), rect(938,349,42,195), rect(1145,351,43,195),
    rect(1308,384,31,166), rect(1465,372,53,238),
    rect(940,590,70,230), rect(941,813,513,73),
    rect(1177,874,91,101), rect(1450,600,86,40),
    rect(241,736,400,111), rect(230,695,120,65), rect(341,749,125,103),
    rect(229,826,183,79), rect(97,755,150,16), rect(58,737,44,66), rect(58,766,190,20),
    rect(545,844,99,24), rect(121,869,140,27),
]
# Freestanding objects visible within the paving: fountain, stalls, well,
# tables, board, planters, lamps and training racks. Buildings are added below.
solids = [
    ('fountain', [670,379,96,86]), ('west_stall',[513,409,113,60]),
    ('east_stall',[813,408,113,66]), ('south_stall',[865,487,72,55]),
    ('well',[274,754,54,48]), ('tavern_table',[485,493,59,42]),
    ('statue',[163,182,48,51]), ('guild_board',[861,221,75,37]),
    ('training_rack',[1044,794,50,59]),('training_crate',[1105,846,30,32]),
    ('camp_tent',[1345,785,83,63]), ('flowerbed',[367,776,83,41]),
    ('temple_bench',[444,284,51,28]),('guild_bench',[866,303,59,25]),
    ('guild_bench_east',[1298,250,48,31]),
    ('forge',[1135,431,51,108]), ('fountain_pot_w',[658,475,27,21]),
    ('fountain_pot_e',[754,475,27,21]),
]
# D90(2026-09-20) 마을 생활 — 위 고정물(solids) 곁의 보행 바닥 칸에 서는 '쓸 수 있는 오브젝트'. id 는 고정물 id 와 같다(아래에서 곁 칸인지 검사).
# entity 는 entities/object 의 정의 id(쓰임 부품 use — 마시기·앉기·읽기·구경·불 쬐기·몸 풀기·뒤지기). 서쪽 좌판(west_stall)은 잡화점 건물과
# 같은 자리라 오브젝트를 따로 세우지 않는다(잡화점 문턱이 구경하는 자리다). 화분 둘(fountain_pot_*)은 장식으로 남긴다.
# 엔진은 이 필드를 마을 생활 스위치(DUNGEON_TOWN_LIFE=1)를 켠 판에서만 읽는다 — 끈 판의 마을은 옛 그대로다.
life_objects = [
    ('fountain','town_fountain',[44,29]), ('well','well',[20,48]), ('statue','town_statue',[11,15]),
    ('guild_board','guild_noticeboard',[55,16]), ('temple_bench','bench',[28,19]), ('guild_bench','bench',[56,18]),
    ('guild_bench_east','bench',[82,18]), ('tavern_table','tavern_table',[32,33]), ('east_stall','produce_stall',[50,27]),
    ('south_stall','sundries_stall',[55,34]), ('forge','forge_hearth',[72,34]), ('training_rack','training_rack',[66,53]),
    ('training_crate','training_crate',[71,53]), ('camp_tent','camp_tent',[86,53]), ('flowerbed','flowerbed',[25,51]),
]
# 새 정착 주민(entities/npc 의 정의 id · row = 관전 그림 wl-town-npcs 의 행, 새 그림이 생기기 전까지 기존 세 행을 빌린다).
life_npcs = [
    ('innkeeper',[30,51],2), ('gear_merchant',[83,35],2), ('item_merchant',[37,30],1), ('smith',[71,34],2),
    ('flower_elder',[22,49],0), ('fountain_child',[41,27],1), ('retired_adventurer',[34,32],2),
]
builds = [
    ('temple_1','temple','temple_district',[14,8,14,10],[7,9]),
    ('guild_1','guild_hall','guild_district',[61,7,22,10],[8,9]),
    ('tavern_1','tavern','main_street',[14,25,17,9],[7,8]),
    ('gate_1','dungeon_gate','dungeon_district',[72,45,9,7],[4,6]),
    ('z_smith_1','blacksmith','shop_district',[61,27,10,7],[5,6]),
    ('z_workshop_1','craft_workshop','shop_district',[74,26,9,8],[4,7]),
    ('z_equipment_1','equipment_store','shop_district',[84,29,9,7],[4,6]),
    ('z_general_1','general_store','main_street',[33,26,6,4],[3,3]),
    ('z_shared_1','shared_lodging','residential_district',[9,43,7,4],[3,3]),
    ('z_garden_1','garden_inn','residential_district',[22,42,7,5],[3,4]),
    ('z_ordinary_1','ordinary_inn','residential_district',[29,43,10,8],[2,7]),
    ('z_home_1','small_home','residential_district',[3,44,6,4],[2,3]),
    ('z_home_2','small_home','residential_district',[8,50,5,5],[3,4]),
]
floor = {(x,y) for y in range(64) for x in range(96)
         if any(inside(x*16+8,y*16+8,p) for p in walk)
         and not any(inside(x*16+8,y*16+8,rect(*r)) for _,r in solids)}
buildings=[]
for bid,eid,rid,(x,y,w,h),entrance in builds:
    buildings.append(dict(id=bid,entity=eid,region=rid,cell=[x,y],footprint=dict(size=[w,h],entrance=entrance)))
    floor -= {(xx,yy) for yy in range(y,y+h) for xx in range(x,x+w)}
    floor.add((x+entrance[0],y+entrance[1]))

# Reject isolated authored patches instead of presenting decorative floor as
# reachable. Door checks in compile_layout still fail if an approach is absent.
seen={(44,34)};q=deque(seen)
while q:
    x,y=q.popleft()
    for p in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
        if p in floor and p not in seen:seen.add(p);q.append(p)
floor &= seen
solid_cells = {i:{(x,y) for y in range(64) for x in range(96) if inside(x*16+8,y*16+8,rect(*r))} for i,r in solids}
for oid,_,(x,y) in life_objects:
    assert (x,y) in floor and any((x+dx,y+dy) in solid_cells[oid] for dx,dy in ((1,0),(-1,0),(0,1),(0,-1))), f'life object {oid} must stand on floor beside its solid'
blocked=[]
for y in range(64):
    x=0
    while x<96:
        if (x,y) in floor:x+=1;continue
        start=x
        while x<96 and (x,y) not in floor:x+=1
        blocked.append(dict(id=f'scenery-{y}-{start}',rect=[start,y,x-start,1]))

# Foreground silhouettes reuse the same art texture: dynamic actors can pass
# behind roofs; no second painted character or duplicated building sprite.
occluders = [
    ('temple',[[234,251],[241,130],[305,102],[306,59],[340,24],[371,67],[377,106],[431,131],[440,255],[472,284],[236,286]],288),
    ('guild',[[975,253],[977,101],[1002,35],[1091,37],[1120,17],[1180,37],[1254,29],[1294,98],[1317,197],[1312,256]],270),
    ('tavern',[[237,525],[239,398],[270,337],[344,342],[362,320],[410,344],[450,349],[480,410],[480,525]],536),
    ('smith',[[978,530],[977,436],[1001,360],[1095,359],[1139,434],[1137,530]],539),
    ('workshop',[[1187,529],[1193,386],[1304,384],[1330,461],[1324,534]],540),
    ('equipment',[[1340,567],[1340,463],[1382,395],[1443,415],[1466,474],[1464,571]],576),
    ('gate',[[1137,814],[1144,692],[1218,631],[1287,691],[1307,814]],827),
    ('home_left',[[48,749],[45,689],[143,678],[144,749]],757),
    ('home_red',[[139,755],[139,674],[173,613],[207,614],[250,676],[244,762]],768),
    ('home_blue',[[355,737],[354,659],[401,618],[434,647],[455,697],[446,742]],754),
    ('inn_red',[[468,801],[468,676],[531,668],[569,610],[622,667],[637,724],[630,802]],812),
    ('home_south',[[125,860],[124,775],[201,775],[211,819],[211,866]],880),
    ('fountain',[[665,446],[667,401],[690,382],[705,348],[724,344],[735,380],[766,402],[775,449],[746,470],[686,466]],470),
    ('well',[[274,792],[275,741],[299,724],[329,742],[329,793]],803),
    ('west_stall',rect(509,377,117,99),480),
    ('east_stall',rect(810,377,119,100),480),
    ('south_stall',rect(865,476,73,65),542),
    ('forge',[[1128,526],[1132,408],[1148,371],[1175,376],[1187,423],[1188,534]],539),
]
layout=dict(schema='town-layout-v1',id='town-concept-v4',space='town_wonderland',
    label='원더랜드 마을',size=[96,64],tileSize=48,border=1,
    regions=[dict(id=i,entity=e,rects=r) for i,e,r in regions],buildings=buildings,
    blocked_rects=blocked,entrances=[],ground=[],props=[],
    walker_rects={eid:[53,17,34,4] for eid in ('apprentice_adventurer','wandering_adventurer')},
    starts={'1':[44,34],'2':[40,34],'3':[31,19]},
    npcs=[dict(id='temple_attendant',cell=[22,18],row=0),
          dict(id='guild_receptionist',cell=[71,18],row=1),
          dict(id='tavern_keeper',cell=[23,34],row=2)],
    dungeon_entry=dict(cell=[76,52]),
    life_objects=[dict(id=i,entity=e,cell=c) for i,e,c in life_objects],
    life_npcs=[dict(id=i,cell=c,row=r) for i,c,r in life_npcs],
    connections=[dict(zip(('from','to','cells'),c)) for c in [
        ('temple_district','main_street',[[32,20],[32,21]]),
        ('guild_district','main_street',[[55,20],[55,21]]),
        ('main_street','shop_district',[[58,34],[59,34]]),
        ('main_street','residential_district',[[39,52],[38,52]]),
        ('shop_district','dungeon_district',[[60,37],[60,38]]),
    ]],
    art=dict(texture='town-concept',sourceSize=[1536,1024],size=[96,64],
        occluders=[dict(id=i,polygon=p,footY=y) for i,p,y in occluders],
        labels=[dict(name=n,x=x,y=y) for n,x,y in [
            ('신전',342,299),('모험가 길드',1130,290),('번화가',716,535),
            ('상점가',1267,566),('주거구역',333,854),('던전 입구',1219,891),('마을 밖',55,500)]]))
compiled=compile_layout(layout)
assert compiled['reachable_cells']==len(floor)
write('layout.json',layout)
write('navigation.json',dict(walk_polygons=walk,solid_objects=[dict(id=i,rect=r) for i,r in solids]))
write('town.json',{'layout':'layout.json'})
print(f"v4: {len(floor)} connected floor cells, {len(buildings)} buildings, 6 regions")

"""마을 전체 맵 1차 저작. 구역과 건물은 entities 정의를 참조한다."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


maps = [('town_wonderland','원더랜드 마을','town'),('town_temple','신전 지구','district'),
        ('town_guild','모험가 길드 지구','district'),('town_tavern','주점 지구','district'),
        ('town_dungeon','던전 입구 지구','district'),('town_main_street','번화가','street'),('town_alley','샛길','street')]
for eid,name,role in maps:
    write(ROOT/'entities/map'/f'{eid}.json', {'id':eid,'name':name,'kind':'map','tags':['town',role],'comps':{'space':{'role':role}}})
for eid,name,size,tex in [('temple','신전',[8,7],'temple'),('guild_hall','모험가 길드',[12,7],'guild'),
                          ('tavern','주점',[12,7],'tavern'),('dungeon_gate','던전 입구',[8,5],'gate')]:
    write(ROOT/'entities/building'/f'{eid}.json', {'id':eid,'name':name,'kind':'building','tags':['town','building'],
          'comps':{'building':{'size':size,'entrance':[size[0]//2,size[1]-1],'texture':tex}}})

layout={'schema':'town-layout-v1','id':'town-full-v2','space':'town_wonderland','label':'원더랜드 마을',
        'size':[51,37],'tileSize':48,'border':1,
        'regions':[
            {'id':'temple_district','entity':'town_temple','rects':[[0,0,20,15]]},
            {'id':'guild_district','entity':'town_guild','rects':[[25,0,26,15]]},
            {'id':'main_street','entity':'town_main_street','rects':[[0,15,51,5],[20,0,5,15]]},
            {'id':'tavern_district','entity':'town_tavern','rects':[[0,20,20,17]]},
            {'id':'alley','entity':'town_alley','rects':[[20,20,5,17],[25,32,26,5]]},
            {'id':'dungeon_district','entity':'town_dungeon','rects':[[25,20,26,12]]}],
        'buildings':[
            {'id':'temple_1','entity':'temple','cell':[5,5],'region':'temple_district'},
            {'id':'guild_1','entity':'guild_hall','cell':[31,4],'region':'guild_district'},
            {'id':'tavern_1','entity':'tavern','cell':[4,24],'region':'tavern_district'},
            {'id':'gate_1','entity':'dungeon_gate','cell':[36,24],'region':'dungeon_district'}],
        'ground':[{'tile':'grass','rect':[0,0,51,37]},
                  {'tile':'plaza_a','rect':[0,15,51,5]},{'tile':'plaza_a','rect':[20,0,5,20]},
                  {'tile':'plaza_a','rect':[3,10,13,5]},{'tile':'plaza_a','rect':[30,10,14,5]},
                  {'tile':'earth','rect':[2,20,17,13]},{'tile':'plaza_a','rect':[5,20,5,5]},
                  {'tile':'alley','rect':[20,20,5,17]},{'tile':'alley','rect':[10,32,41,3]},
                  {'tile':'alley','rect':[16,29,9,4]},
                  {'tile':'plaza_a','rect':[34,28,13,4]},{'tile':'alley','rect':[38,20,5,5]}],
        'connections':[
            {'from':'temple_district','to':'main_street','cells':[[9,14],[9,15]]},
            {'from':'guild_district','to':'main_street','cells':[[37,14],[37,15]]},
            {'from':'main_street','to':'tavern_district','cells':[[8,19],[8,20]]},
            {'from':'main_street','to':'alley','cells':[[22,19],[22,20]]},
            {'from':'tavern_district','to':'alley','cells':[[19,32],[20,32]]},
            {'from':'alley','to':'dungeon_district','cells':[[40,32],[40,31]]}],
        'blocked_rects':[], 'entrances':[],
        'starts':{'1':[23,17],'2':[22,18],'3':[24,18]},
        'dungeon_entry':{'cell':[40,29],'placeholder':False},
        'npcs':[{'id':'temple_attendant','cell':[10,13],'row':0},
                {'id':'guild_receptionist','cell':[38,12],'row':1},
                {'id':'tavern_keeper','cell':[13,31],'row':2}],
        'props':[],
        'interiors':False}
layout['note']='여섯 구역이 이어진 단일 마을 맵. 건물 정의가 점유·문턱·그림 앵커를 생성한다. 방문 순서·체류 상한 없음. 실내 기능은 별도 작업.'
# 길 가장자리 소품. 발이 놓이는 칸을 막아 그림과 통행이 일치하게 한다.
for i,(frame,x,y) in enumerate([(0,2,14),(0,18,14),(0,28,14),(0,46,14),(1,28,11),
                               (2,16,12),(2,45,12),(3,6,12),(3,12,12),(3,33,11),(3,41,11),
                               (7,17,29),(6,3,31),(6,45,30)]):
    layout['props'].append({'frame':frame,'x':(x+.5)*48,'y':(y+.5)*48})
    layout['blocked_rects'].append({'id':f'prop:{i}','rect':[x,y,1,1]})
write(HERE/'layout.json',layout)
print('정의 11개 · 여섯 구역 · 건물 4동 · 51×37 layout 생성')

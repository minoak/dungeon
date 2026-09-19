"""Active town v3 contract: full coverage, access, walkers and party locations. 0 LLM calls."""
from collections import deque
import json
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parent
os.environ['DUNGEON_BRAIN_BACKEND']='dummy'
os.environ['DUNGEON_BESTIARY_FILE']=''
import entities
import town_layout
import show_runner


def validate():
    layout=json.loads((ROOT/'art/town-v3/layout.json').read_text(encoding='utf-8'))
    compiled=town_layout.compile_layout(layout)
    w,h=layout['size'];pad=compiled['pad'];owners={}
    for region in layout['regions']:
        assert entities.get(region['entity'])['comps']['story']['trait']
        for x,y,rw,rh in region['rects']:
            for yy in range(y,y+rh):
                for xx in range(x,x+rw):
                    assert (xx,yy) not in owners, ('overlap',xx,yy)
                    owners[xx,yy]=region['id']
    assert len(owners)==w*h
    floor={(x-pad,y-pad) for y,row in enumerate(compiled['map']) for x,c in enumerate(row) if c!='#'}
    assert floor <= owners.keys()
    first=tuple(layout['starts']['1']);seen={first};queue=deque([first])
    while queue:
        x,y=queue.popleft()
        for p in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
            if p in floor and p not in seen:seen.add(p);queue.append(p)
    assert seen==floor, 'isolated floor'
    required=('guild_hall','tavern','dungeon_gate')
    for eid in required:assert sum(b['entity']==eid for b in layout['buildings'])==1
    assert sum(row.count('>') for row in compiled['map'])==1
    design=json.loads((ROOT/'art/town-v3/design-objects.json').read_text(encoding='utf-8'))
    for o in design['objects']:
        assert owners[tuple(o['cell'])]==o['region']
        assert tuple(o['interaction_cell']) in seen
        assert tuple(o['cell']) not in floor
        assert sum(abs(a-b) for a,b in zip(o['cell'],o['interaction_cell']))==1
    assert len(design['reserved_exits'])==1 and design['reserved_exits'][0]['runtime_feature'] is None
    assert tuple(design['reserved_exits'][0]['cell']) in seen
    landscape=ROOT/'art/town-v3/landscaping.json'
    if landscape.exists():
        for detail in json.loads(landscape.read_text(encoding='utf-8'))['details']:
            if detail['solid']:
                x,y,rw,rh=detail['rect']
                assert all((xx,yy) not in floor for xx in range(x,x+rw) for yy in range(y,y+rh)), detail['id']
    d,starts=show_runner.build_town(str(ROOT/'art/town-v3/town.json'),apart=True,walkers=True,guide=True)
    assert len({d._zone_id(*p) for p in starts.values()})==3, 'three starts in separate regions'
    assert d._party_zone_ids()==frozenset({'guild_district','main_street'})
    assert len([f for f in d.features.values() if f.type=='exit'])==1
    assert len([f for f in d.features.values() if f.type=='building'])==13
    assert len(d.zone_story)==6 and len(d.place_story)==20
    # Connected terrain alone cannot catch an NPC standing in the only doorway.
    sx,sy=compiled['starts']['1']
    for f in d.features.values():
        if f.type in ('building','npc','exit'):
            assert d.path_to(sx,sy,f.x,f.y,[]), ('occupied approach',f.name)
    assert {n['id']:n['row'] for n in layout['npcs']}=={
        'temple_attendant':0,'guild_receptionist':1,'tavern_keeper':2}
    walker_rows=[]
    for eid in ('apprentice_adventurer','wandering_adventurer','street_vendor'):
        nd=entities.get(eid);spec=nd['comps']['npc']['walk']
        f=next(f for f in d.features.values() if f.name==nd['name'])
        assert f.walker and d._zone_id(f.x,f.y)==spec['region']
        points={p for p in floor if owners[p]==spec['region']}
        if spec.get('rect'):
            x,y,rw,rh=spec['rect'];points={p for p in points if x<=p[0]<x+rw and y<=p[1]<y+rh}
        assert points
        walker_rows.append(dict(id=eid,region=spec['region'],candidate_cells=len(points)))
    # Inspect generated observations for all six zones under the actual D86 switch.
    import dungeon_gm as G
    d.town_sight='zone'
    b=G.spawn(d,'1',[])
    for rid in {r['id'] for r in layout['regions']}:
        p=next(p for p in floor if owners[p]==rid and not d.feature_at(p[0]+pad,p[1]+pad))
        b['x'],b['y']=p[0]+pad,p[1]+pad
        obs=d.view(b,[b])
        assert obs['town_zone'] and obs.get('town_sight')=='zone'
        for f in obs['sights']['features']:
            real=d.features[int(f['id'][1:])]
            assert d._zone_id(real.x,real.y)==rid
    report=dict(status='PASS',size=[w,h],total_cells=w*h,floor_cells=len(floor),reachable_floor_cells=len(seen),
                unowned_floor_cells=0,overlap_cells=0,buildings=len(layout['buildings']),
                object_approaches=len(design['objects']),party_regions=sorted(d._party_zone_ids()),
                walkers=walker_rows,dungeon_exit_features=1,zone_observations=6,
                regions=[dict(id=r['id'],name=entities.get(r['entity'])['name'],
                              floor_cells=sum(owners[p]==r['id'] for p in floor)) for r in layout['regions']])
    return report


if __name__=='__main__':
    report=validate()
    if '--export' in __import__('sys').argv:
        (ROOT/'art/town-v3/validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('ALL PASS — verify_town_v3: 6 regions, %d floor cells, 14 buildings, 15 object approaches, 3 walkers, zone sight and party locations (0 calls)' % report['floor_cells'])

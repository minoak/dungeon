"""Approved concept -> real engine map contract, no LLM calls or live runs."""
from collections import deque
from copy import deepcopy
import json
import os
from pathlib import Path

os.environ['DUNGEON_BRAIN_BACKEND']='dummy'
os.environ['DUNGEON_BESTIARY_FILE']=''
import entities
import town_layout
import show_runner
import dungeon_gm as G

ROOT=Path(__file__).resolve().parent

def validate():
    layout=json.loads((ROOT/'art/town-v4/layout.json').read_text(encoding='utf-8'))
    c=town_layout.compile_layout(layout)
    floor={(x-1,y-1) for y,row in enumerate(c['map']) for x,v in enumerate(row) if v!='#'}
    owners={}
    for r in c['spaces']['regions']:
        assert entities.get(r['entity'])['comps']['story']['trait']
        for x,y,w,h in r['rects']:
            for yy in range(y,y+h):
                for xx in range(x,x+w):
                    assert (xx,yy) not in owners
                    owners[xx,yy]=r['id']
    assert len(owners)==96*64 and floor<=owners.keys()
    seen={tuple(layout['starts']['1'])};q=deque(seen)
    while q:
        x,y=q.popleft()
        for p in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
            if p in floor and p not in seen:seen.add(p);q.append(p)
    assert seen==floor
    d,starts=show_runner.build_town(apart=True,walkers=True,guide=True)
    assert (d.w,d.h)==(98,66)
    assert len({d._zone_id(*p) for p in starts.values()})==3
    assert d._party_zone_ids()==frozenset({'guild_district','main_street'})
    assert len([f for f in d.features.values() if f.type=='exit'])==1
    assert len([f for f in d.features.values() if f.type=='building'])==12
    assert len(d.zone_story)==6 and len(d.place_story)==19
    for eid in ('guild_hall','tavern','dungeon_gate'):
        assert sum(b['entity']==eid for b in layout['buildings'])==1
    for f in d.features.values():
        assert d.path_to(*c['starts']['1'],f.x,f.y,[]), ('occupied approach',f.name)
    walkers=[]
    for eid in ('apprentice_adventurer','wandering_adventurer','street_vendor'):
        spec=entities.npc(eid)
        f=next(f for f in d.features.values() if f.name==spec['name'])
        assert f.walker and d._zone_id(f.x,f.y)==spec['walk']['region']
        rect=d.npc_defs[f.name]['walk'].get('rect')
        assert d._in_walk_rect(f.x,f.y,rect)
        walkers.append(eid)
    # Physical landmarks: both bridge ends are floor, river and fountain solid.
    for source in ((704,960),(704,1008),(976,784),(1216,944),(64,512)):
        assert (source[0]//16,source[1]//16) in floor, ('walk',source)
    for source in ((864,960),(480,960),(720,416),(1216,720),(880,160)):
        assert (source[0]//16,source[1]//16) not in floor, ('solid',source)
    # Art dimensions map exactly to the cell grid; old sprite defaults untouched.
    V=town_layout.visual_layer(layout,c)
    assert V['art']['sourceSize']==[1536,1024] and V['art']['size']==layout['size']
    assert len(V['art']['occluders'])==18
    for b in c['spaces']['buildings']:
        ex,ey=b['entrance']
        assert (ex,ey) in floor and owners[ex,ey]==b['region']
    original=deepcopy(entities.get('guild_hall'))
    town_layout.compile_layout(layout)
    assert entities.get('guild_hall')==original
    # All six zones retain their actual visibility/story semantics.
    d.town_sight='zone';bot=G.spawn(d,'1',[])
    for rid in {r['id'] for r in layout['regions']}:
        p=next(p for p in floor if owners[p]==rid and not d.feature_at(p[0]+1,p[1]+1))
        bot['x'],bot['y']=p[0]+1,p[1]+1
        obs=d.view(bot,[bot]);assert obs['town_zone'] and obs['town_sight']=='zone'
        for f in obs['sights']['features']:
            real=d.features[int(f['id'][1:])]
            assert d._zone_id(real.x,real.y)==rid
    return dict(status='PASS',floor_cells=len(floor),reachable_floor_cells=len(seen),
        unowned_floor_cells=0,overlap_cells=0,regions=6,buildings=13,walkers=walkers,
        party_regions=sorted(d._party_zone_ids()),exit_features=1,llm_calls=0)

if __name__=='__main__':
    result=validate()
    if '--export' in __import__('sys').argv:
        (ROOT/'art/town-v4/validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('ALL PASS — verify_town_v4: '+json.dumps(result,ensure_ascii=False))

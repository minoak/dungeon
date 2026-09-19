"""Rebuild concept-inspired landscaping; geometry remains the engine's authority."""
from collections import deque
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT))
import town_layout

layout=json.loads((HERE/'layout-base.json').read_text(encoding='utf-8'))
design=json.loads((HERE/'design-objects.json').read_text(encoding='utf-8'))
compiled=town_layout.compile_layout(layout)
floor={(x-1,y-1) for y,row in enumerate(compiled['map']) for x,c in enumerate(row) if c!='#'}
protected={tuple(p) for p in layout['starts'].values()}
for e in compiled['entrances']:
    x,y=e['cell'];x-=1;y-=1
    protected.update((x+dx,y+dy) for dx,dy in [(0,0),(0,1),(-1,1),(1,1),(0,2)])
for n in layout['npcs']:
    x,y=n['cell'];protected.update((x+dx,y+dy) for dx in range(-1,2) for dy in range(-1,2))
protected.update(tuple(o['interaction_cell']) for o in design['objects'])
protected.add(tuple(layout['dungeon_entry']['cell']))
protected.update(tuple(p) for c in layout['connections'] for p in c['cells'])
protected.update((x,y) for y in range(11,15) for x in range(29,46)) # existing walkers
manifest=json.loads((HERE/'runtime/detail-manifest.json').read_text(encoding='utf-8'))
details=[];skipped=[]

def connected(cells):
    first=next(iter(cells));seen={first};q=deque([first])
    while q:
        x,y=q.popleft()
        for p in [(x-1,y),(x+1,y),(x,y-1),(x,y+1)]:
            if p in cells and p not in seen:seen.add(p);q.append(p)
    return len(seen)==len(cells)

def add(kind,x,y,width,rect=None,solid=True):
    """x/y = foot tile; canopy may overhang, solid base has explicit footprint."""
    global floor
    rect=rect or [int(x),int(y),1,1]
    rx,ry,rw,rh=rect
    cells={(xx,yy) for yy in range(ry,ry+rh) for xx in range(rx,rx+rw)}
    if solid:
        if not cells<=floor or cells&protected or not connected(floor-cells):
            skipped.append([kind,x,y]);return
        floor-=cells
    did='detail:%s:%d'%(kind,len(details))
    p=dict(frame=manifest[kind]['frame'],x=(x+.5)*48,y=(y+1)*48,width=width)
    layout['props'].append(p)
    if solid:layout['blocked_rects'].append(dict(id=did,rect=rect))
    details.append(dict(id=did,kind=kind,cell=[x,y],rect=rect if solid else None,solid=solid))

def ground(tile,x,y,w,h):layout['ground'].append(dict(tile=tile,rect=[x,y,w,h]))

# Continuous pale stone plazas, with narrower domestic paths and planted setbacks.
ground('grass',0,30,40,18)
ground('plaza_a',1,10,18,5)
ground('plaza_a',15,17,24,12)
ground('plaza_a',2,25,13,4)
ground('plaza_a',28,10,22,5)
ground('alley',43,23,19,2)
ground('alley',1,38,35,3)
ground('plaza_a',10,30,3,18)
ground('plaza_a',19,30,3,18)
ground('plaza_a',22,39,5,9)
ground('plaza_a',1,46,18,2)
ground('alley',25,46,14,2)
ground('plaza_a',40,30,3,18)
ground('plaza_a',48,40,15,8)

# Larger market stalls and a central fountain: keep the original interaction cells.
for p in layout['props']:
    if p['frame'] in (11,12):
        p['frame']=manifest['market_red' if p['frame']==11 else 'market_blue']['frame'];p['width']=142
add('fountain',22,19,180,rect=[21,18,3,2])
add('market_red',26,27,128,rect=[25,27,3,1])
add('market_blue',18,23,120)
add('cart',28,25,104)
add('crates',15,21,78)
add('crates',24,23,70)

# Retaining walls outline gardens; interrupted runs leave several generous gates.
for x in [2,5,8,11,14,17]:add('stone_wall',x,1,156,rect=[x-1,1,3,1])
for x in [2,5,14,17]:add('stone_wall',x,14,156,rect=[x-1,14,3,1])
for y in [4,7,10]:add('stone_wall_vertical',18,y,122,rect=[18,y-2,1,3])
for x in [27,46,49,52,55,58,61]:add('stone_wall',x,14,150,rect=[x-1,14,3,1])
for x in [1,4,7,13,16,28,31,34,37]:add('stone_wall',x,30,146,rect=[max(0,x-1),30,3,1])
for x in [3,7,15,28,32,36]:add('fence',x,41,125,rect=[x-1,41,3,1])
for x in [3,7,15,18,28,32,36]:add('stone_wall',x,47,150,rect=[x-1,47,3,1])
for y in [34,37,40,43,46]:add('stone_wall_vertical',39,y,130,rect=[39,y-2,1,3])
for x in [45,48,51,54,57,60,63]:add('stone_wall',x,32,148,rect=[max(0,x-1),32,min(3,64-max(0,x-1)),1])
for x in [45,48,59,62]:add('stone_wall',x,47,145,rect=[x-1,47,3,1])

# Temple memorial garden, planted streets and house courtyards.
add('statue',2,8,100)
for x,y in [(3,3),(15,4),(15,7),(2,11),(16,13),(27,11),(46,11),(27,14),
            (15,18),(25,17),(38,25),(43,25),(61,25),(44,29),(62,29),
            (1,37),(13,38),(21,38),(31,39),(14,41),(1,45),(25,46),(37,46),(50,44),(60,42)]:
    add('flowers',x,y,102)
for x,y in [(3,4),(15,5),(16,9),(27,8),(46,8),(49,9),(52,10),(56,10),(59,10),
            (1,29),(15,29),(27,29),(30,30),(33,30),(36,30),(1,40),(14,40),(18,41),(26,41),
            (2,46),(16,46),(28,47),(36,47),(44,36),(45,42),(62,43)]:
    add('hedge',x,y,130)
for x,y in [(19,8),(25,8),(19,14),(25,14),(15,26),(27,26),(39,17),(39,28),
            (9,31),(23,31),(23,41),(43,33),(48,42),(61,42),(9,46)]:add('banner_lamp',x,y,112)
for x,y in [(26,13),(50,13),(14,28),(29,28),(11,40),(23,40),(46,34)]:
    add('stairs',x,y,142,solid=False) # walkable stair dressing, same elevation in engine

# Forested perimeter and guild's orchard: deliberately irregular spacing.
trees=[(1,2),(4,3),(15,2),(18,3),(26,2),(29,2),(44,3),(47,2),(51,3),(54,2),(58,3),(62,2),
       (1,6),(1,12),(1,18),(1,23),(1,31),(0,39),(0,46),(17,33),(17,36),
       (27,5),(27,9),(46,6),(49,5),(52,7),(55,5),(59,6),(62,5),
       (47,9),(50,8),(54,10),(57,9),(61,9),(62,13),(63,18),(63,23),(63,29),
       (34,33),(35,37),(24,34),(1,42),(10,43),(20,44),(24,46),(38,45),
       (45,35),(48,36),(45,39),(46,45),(63,39),(63,46)]
for i,(x,y) in enumerate(trees):add('pine' if i%3==0 else 'tree',x,y,184 if i%3==0 else 216)

# Mossy rock backdrop around the dungeon; the route in front remains open.
for x,y in [(46,35),(50,36),(53,35),(56,35),(59,36),(62,35),(47,40),(62,40),(44,45)]:
    add('cliff',x,y,184,rect=[x-1,y-1,2,2])
for x,y in [(48,34),(52,33),(57,33),(60,34),(45,38),(61,37)]:add('pine',x,y,184)
for x,y in [(44,22),(52,23),(61,24),(48,30),(26,38),(33,40),(49,44),(59,44)]:add('crates',x,y,76)
add('cart',35,32,110)

assert connected(floor)
layout['id']='town-full-v3-landscaped'
(HERE/'layout.json').write_text(json.dumps(layout,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(HERE/'landscaping.json').write_text(json.dumps(dict(details=details,skipped=skipped,floor_cells=len(floor)),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Landscaping: %d objects, %d connected floor cells, %d placements omitted to preserve access.'%(len(details),len(floor),len(skipped)))
import runpy
runpy.run_path(str(HERE/'pave.py'), run_name='__main__')

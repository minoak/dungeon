"""Dress the existing road surfaces without changing a single collision cell."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
p=HERE/'layout.json'
layout=json.loads(p.read_text(encoding='utf-8'))
w,h=layout['size']
# Generated entries are replaceable, so the pass is idempotent.
layout['ground']=[g for g in layout['ground'] if not g.get('paving')]
ground=[['grass']*w for _ in range(h)]
for g in layout['ground']:
    x,y,rw,rh=g['rect']
    for yy in range(y,y+rh):
        for xx in range(x,x+rw):ground[yy][xx]=g['tile']
materials={}
for y in range(h):
    for x in range(w):
        if ground[y][x] not in ('plaza_a','plaza_b','alley'):continue
        material=0 # limestone avenue
        if y>=30 and x<40:material=2 # domestic cobbles
        if y>=32 and x>=43:material=3 # old dungeon causeway
        if 43<=x and 17<=y<32:material=2 # working yards
        if 16<=x<=26 and 18<=y<=28:material=1 # inset herringbone market square
        materials[x,y]=material
        # Pick a variant per 2x2 motif, not per tile, to retain masonry joints.
        variant=material in (0,2) and ((x//2)*73+(y//2)*41+(x//2)*(y//2)*11)%7<2
        frame=8+(material*2+int(variant))*4+(y%2)*2+x%2
        layout['ground'].append(dict(tile=['limestone','market_brick','cobble','slate'][material],frame=frame,rect=[x,y,1,1],paving=True))

edges=[]
for (x,y),mat in materials.items():
    for dx,dy,side in [(0,-1,'n'),(1,0,'e'),(0,1,'s'),(-1,0,'w')]:
        other=materials.get((x+dx,y+dy))
        if other is None or mat<other:
            edges.append(dict(cell=[x,y],side=side,soft=other is None,material=mat))
# Small drain grates alongside the main avenue; medallions mark plaza intersections.
drains=[[20,y] for y in [5,13,26]]+[[x,28] for x in [5,14,34,43]]+[[41,36],[41,44],[11,41],[24,45]]
drains=[p for p in drains if tuple(p) in materials]
inlays=[dict(cell=[22,9],radius=1.15),dict(cell=[35,13],radius=.9),dict(cell=[9,13],radius=.8)]
layout['paving']=dict(edges=edges,drains=drains,inlays=inlays)
p.write_text(json.dumps(layout,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Paving: %d surface cells, %d curb segments, %d drains; collision unchanged.'%(len(materials),len(edges),len(drains)))

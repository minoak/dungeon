import sys,json
from collections import Counter,deque
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from preview_server import dungeon,stream
report={}
for profile in ('original','concept'):
    signatures=set();doors=0
    samples=1000 if profile=='concept' else 100
    room_counts,column_counts,room_styles=Counter(),Counter(),Counter()
    graphs,widths=set(),set()
    for seed in range(samples):
        d=dungeon(seed,profile); L=d.level_snapshot()
        assert L==dungeon(seed,profile).level_snapshot()
        cells={(x,y) for y,row in enumerate(L['grid']) for x,c in enumerate(row) if c in '.+'}
        seen={next(iter(cells))}; q=deque(seen)
        while q:
            x,y=q.popleft()
            for p in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                if p in cells and p not in seen: seen.add(p);q.append(p)
        assert seen==cells,(profile,seed,len(seen),len(cells))
        assert tuple(L['exit']) in seen
        data=[json.loads(s) for s in stream(seed,profile).decode().splitlines()]
        assert data[1]['grid']==L['grid']
        assert all((p['x'],p['y']) in cells for p in data[1]['party']+L['features']+L['monsters']+L['traps'])
        if profile=='concept':
            assert 5<=len(d.rooms)<=8
            for i,r in enumerate(d.rooms):
                assert r.x>0 and r.y>0 and r.x+r.w<d.w and r.y+r.h<d.h
                for other in d.rooms[i+1:]:
                    assert r.x+r.w<=other.x or other.x+other.w<=r.x or r.y+r.h<=other.y or other.y+other.h<=r.y
            assert all(not d.walkable(x,y,[]) and not d._monster_walkable(x,y,[]) for x,y in d.columns)
            isolated={(x,y) for y in range(1,d.h-1) for x in range(1,d.w-1)
                      if L['grid'][y][x]=='#' and all((xx,yy) in cells for xx,yy in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)))}
            assert isolated==set(d.columns),(seed,'unplanned isolated columns')
            reached={0}
            for _ in d.rooms:
                for a,b in d._edges:
                    if a in reached or b in reached: reached.update((a,b))
            assert len(reached)==len(d.rooms)
            assert len(d._edges)==len(d.rooms)-1+d.extra_connections
            room_counts[len(d.rooms)]+=1;column_counts[len(d.columns)]+=1
            room_styles.update(d.room_styles.values())
            graphs.add(tuple(sorted(d._edges)))
            widths.update(c['width'] for c in d.corridors)
        doors+=sum(row.count('+') for row in L['grid']);signatures.add(tuple(L['grid']))
    assert len(signatures)==samples
    report[profile]=dict(seeds=samples,uniqueGrids=len(signatures),doors=doors,connected=True,deterministic=True,
                         previewMatchesEngine=True,columnsBlockMovement=profile=='concept')
    if profile=='concept':
        assert set(room_counts)=={5,6,7,8} and 0 in column_counts and 4 in column_counts
        assert len(graphs)>samples*.8 and widths=={2,3}
        report[profile].update(roomCounts=dict(room_counts),columnCounts=dict(column_counts),
                               roomStyles=dict(room_styles),uniqueConnectionGraphs=len(graphs),passageWidths=sorted(widths))
    print(profile,samples,'connected deterministic distinct seeds; doors',doors)
assert 'brains' not in sys.modules
report.update(passed=True,brainImported=False,llmCalls=0)
(HERE/'verification'/'architecture.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')

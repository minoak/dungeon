"""Seeded architecture with varied room packing, circulation and optional columns."""
import dungeon_gm as G


class ConceptDungeon(G.Dungeon):
    """Keep the concept's scale and materials without fixing its composition."""

    def _carve_rooms(self, n=6):
        target = self.rng.randint(5, 8)
        self.room_styles = {}
        # Rejection sampling has no fixed sectors, central room, symmetry or required hall.
        for _ in range(12):
            rooms, styles = [], {}
            large = self.rng.choices([0, 1, 2], [3, 6, 1])[0]
            for attempt in range(1000):
                if len(rooms) >= target:
                    break
                if len(rooms) < large:
                    rw, rh = self.rng.randint(12, 15), self.rng.randint(9, 11)
                    style = self.rng.choice(['hall', 'pillared_hall'])
                elif self.rng.random() < .25:
                    rw, rh = self.rng.randint(10, 13), self.rng.randint(4, 5)
                    if self.rng.random() < .5:
                        rw, rh = rh, rw
                    style = 'gallery'
                else:
                    rw, rh = self.rng.randint(6, 10), self.rng.randint(5, 8)
                    style = 'two_columns' if rw >= 10 and rh >= 7 and self.rng.random() < .35 else 'chamber'
                x, y = self.rng.randint(2, self.w-rw-2), self.rng.randint(2, self.h-rh-2)
                if any(not (x+rw+2 <= r.x or r.x+r.w+2 <= x or y+rh+2 <= r.y or r.y+r.h+2 <= y) for r in rooms):
                    continue
                rid = len(rooms)
                rooms.append(G.Room(rid, x, y, rw, rh))
                styles[rid] = style
            if len(rooms) >= 5:
                self.room_styles = styles
                break
        else:
            raise RuntimeError('Could not fit five rooms in the architecture profile')
        for r in rooms:
            for y in range(r.y, r.y+r.h):
                for x in range(r.x, r.x+r.w):
                    self.grid[y][x] = G.FLOOR
        self._ring_target = len(rooms)
        return rooms

    def _connected_floor(self):
        cells = {(x, y) for y, row in enumerate(self.grid) for x, c in enumerate(row) if c in (G.FLOOR, G.DOOR)}
        start = next(iter(cells))
        seen, todo = {start}, [start]
        for x, y in todo:
            for p in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                if p in cells and p not in seen:
                    seen.add(p)
                    todo.append(p)
        return len(seen) == len(cells)

    def _connect(self, rooms):
        # A slightly jittered minimum spanning tree, followed by short optional loops.
        candidates = []
        for a in rooms:
            for b in rooms[a.id+1:]:
                dist = abs(a.center[0]-b.center[0])+abs(a.center[1]-b.center[1])
                candidates.append((dist*self.rng.uniform(.8, 1.2), a.id, b.id))
        candidates.sort()
        components = list(range(len(rooms)))
        self._edges = []
        for _, a, b in candidates:
            if components[a] == components[b]:
                continue
            old, new = components[b], components[a]
            components = [new if c == old else c for c in components]
            self._edges.append((a, b))
        unused = [(a, b) for _, a, b in candidates if (a, b) not in self._edges]
        self.extra_connections = self.rng.randint(0, min(2, len(unused))) if self.loops else 0
        for _ in range(self.extra_connections):
            pair = self.rng.choice(unused[:max(3, len(rooms)//2)])
            unused.remove(pair)
            self._edges.append(pair)
        self.corridors = []
        for a, b in self._edges:
            x1, y1 = rooms[a].center
            x2, y2 = rooms[b].center
            width = self.rng.choice([2, 3, 3])
            offsets = range(-(width//2), width-width//2)
            routes = []
            for horizontal_first in (False, True):
                y_mid, x_mid = (y1, x2) if horizontal_first else (y2, x1)
                cells = {(x, y_mid+o) for x in range(min(x1,x2),max(x1,x2)+1) for o in offsets}
                cells |= {(x_mid+o,y) for y in range(min(y1,y2),max(y1,y2)+1) for o in offsets}
                # Prefer elbows that do not slice through a third room.
                cost = sum(r.contains(x,y) for x,y in cells for r in rooms if r.id not in (a,b))
                routes.append((cost+self.rng.random(), cells, horizontal_first))
            _, cells, horizontal_first = min(routes, key=lambda route: route[0])
            for x,y in sorted(cells):
                self.grid[y][x] = G.FLOOR
            self.corridors.append(dict(rooms=[a,b], width=width, horizontal_first=horizontal_first))
        # Remove isolated rock pixels left by crossing corridors before adding deliberate columns.
        for y in range(1,self.h-1):
            for x in range(1,self.w-1):
                if self.grid[y][x] == G.WALL and all(self.grid[yy][xx] == G.FLOOR for xx,yy in ((x-1,y),(x+1,y),(x,y-1),(x,y+1))):
                    self.grid[y][x] = G.FLOOR
        self.columns = []
        for r in rooms:
            style = self.room_styles[r.id]
            if style == 'pillared_hall':
                columns = [(x,y) for x in (r.x+3,r.x+r.w-4) for y in (r.y+2,r.y+r.h-3)]
            elif style == 'two_columns':
                columns = [(r.x+3,r.y+r.h//2),(r.x+r.w-4,r.y+r.h//2)]
            else:
                continue
            for x,y in columns:
                self.grid[y][x] = G.WALL
            if self._connected_floor():
                self.columns.extend(columns)
            else:
                for x,y in columns:
                    self.grid[y][x] = G.FLOOR
                self.room_styles[r.id] = 'hall' if style == 'pillared_hall' else 'chamber'
        # Some rooms are open; others have narrow thresholds with a single door.
        for r in rooms:
            if self.rng.random() < .2:
                continue
            sides = [([(x,r.y-1) for x in range(r.x,r.x+r.w)],(0,-1)),
                     ([(x,r.y+r.h) for x in range(r.x,r.x+r.w)],(0,1)),
                     ([(r.x-1,y) for y in range(r.y,r.y+r.h)],(-1,0)),
                     ([(r.x+r.w,y) for y in range(r.y,r.y+r.h)],(1,0))]
            for edge,(dx,dy) in sides:
                runs, current = [], []
                for x,y in edge:
                    if self.grid[y][x] == G.FLOOR:
                        current.append((x,y))
                    elif current:
                        runs.append(current)
                        current=[]
                if current:
                    runs.append(current)
                for run in runs:
                    if len(run) not in (2,3) or not all(self.grid[y+dy][x+dx] == G.FLOOR for x,y in run):
                        continue
                    for j,(x,y) in enumerate(run):
                        self.grid[y][x] = G.DOOR if j == len(run)//2 else G.WALL
                    if not self._connected_floor():
                        for x,y in run:
                            self.grid[y][x] = G.FLOOR
        # Door shoulders can leave isolated pixels where corridors intersect.
        # Only the explicitly planned room columns should become freestanding pillars.
        planned = set(self.columns)
        for y in range(1, self.h-1):
            for x in range(1, self.w-1):
                if (x,y) not in planned and self.grid[y][x] == G.WALL and all(
                    self.grid[yy][xx] in (G.FLOOR,G.DOOR)
                    for xx,yy in ((x-1,y),(x+1,y),(x,y-1),(x,y+1))
                ):
                    self.grid[y][x] = G.FLOOR

    def level_snapshot(self):
        level = super().level_snapshot()
        for room in level['rooms']:
            room['art_style'] = self.room_styles[room['id']]
        level['architecture'] = dict(version=2, columns=self.columns, corridors=self.corridors,
                                     extra_connections=self.extra_connections)
        return level

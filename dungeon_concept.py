"""던전 생성 프로필 'concept'(D88, 2026-09-20) — 큰 홀·회랑·작은 방을 시드마다 다르게 짜고 폭 2~3 통로로 잇는다.

art/dungeon-v2/ 시제품(concept_dungeon.py)의 생성기를 리포 루트로 옮긴 것. 루트여야 하는 이유: 이어가기(D79)가
Dungeon 객체를 통째로 피클하고, 피클은 클래스를 '모듈명.클래스명'으로 되살린다 — 하이픈 폴더(sys.path 밖)에 두면
되살리기가 ModuleNotFoundError 로 실패해 조용히 새 판이 된다. art/dungeon-v2/concept_dungeon.py 는 재수출만 한다.

엔진(dungeon_gm.Dungeon)과의 계약 — 시제품이 지키던 것(Room id==인덱스 · _edges=(a,b) 튜플 · 굴림은 self.rng 한 줄기 ·
문은 배치 전에 찍는다)에 본편 통합으로 더한 것:
  ① ZONE_BLOCK=4 — 스캐너가 폭 2~3 통로를 '통로'로 읽게(기본 2 로 읽으면 방+통로가 한 구역으로 뭉친다).
  ② scan 강제 — 이 프로필은 문 타일(+)을 직접 찍는다. scan=0 이면 문이 빛만 막고 Door 명사가 없는 거짓 상태가 된다.
  ③ 최소 격자 가드 · 방 5개를 못 채울 때의 결정론적 완화 폴백 — 층 전이 중 예외 = 같은 시드로 영원히 재크래시.
  ④ level_snapshot getattr 가드 — from_ascii/from_layout(__new__ 경유) 인스턴스엔 건축 기록이 없다.
  ⑤ _stamp_doors 덮어쓰기 — 엔진의 정착 루프가 되돌린 생성기 문은 어깨 벽을 걷어 열린 아치로 되돌린다.
판정·시야·길찾기는 전부 부모 것 그대로(폭·직사각형 가정이 없는 층). 이 모듈은 지형만 짓는다 — 누가 어디로 갈지는 정하지 않는다."""
import dungeon_gm as G

ARCH_NAME = 'concept'     # 러너 DUNGEON_ARCH 값 · run_meta.arch
ARCH_VERSION = 2          # 생성 규칙 버전 — run_meta.arch_v · level.architecture.version(저장된 판을 새 규칙으로 다시 짓지 않기 위한 기록)
DEFAULT_W, DEFAULT_H = 42, 34   # 이 프로필이 검증된 격자(러너는 DUNGEON_W/H 를 안 줬을 때 이 값을 쓴다)
MIN_W, MIN_H = 26, 17     # 최소 격자: 가장 큰 방(15×11 · 돌린 회랑 5×13)+여백 2 의 randint 범위가 비지 않고(19×17),
                          #   마지막 폴백(6×5 방 격자 채우기 — 가로 3 × 세로 2 = 6칸)이 방 5개를 반드시 채우는 크기(26×16)


class ConceptDungeon(G.Dungeon):
    """Keep the concept's scale and materials without fixing its composition."""

    ZONE_BLOCK = 4            # D88: 방 = 4×4 바닥 블록(홀로 선 기둥 투과) — 폭 2~3 통로가 '통로' 구역으로 읽힌다
    # 구역의 사람말 이름 임계(_zone_name) — 0콜 실측(시드 200 · 42×34 · 방 구역 1241 · 통로 구역 1156)의 분포로 정한 값.
    #   옛 값(30/12/10)으로는 이 프로필의 방이 전부 '넓은 방'이 된다(가장 작은 방이 6×5=30). 방 bbox 면적의 십분위 =
    #   40·42·48·50·54·60·65·80·135 — 일반 방(최대 10×8=80)·회랑(최대 13×5=65)과 대홀(최소 12×9=108) 사이가 빈다.
    ZONE_BIG_ROOM = 100       # '넓은 방' = 대홀급(방 구역의 16.4% — 옛 생성기는 43.5%)
    ZONE_SMALL_ROOM = 42      # '작은 방' = 6×5~7×6 급(21.6% — 옛 생성기는 0%: 임계 12 가 최소 방 5×3=15 보다 작았다)
    ZONE_LONG_CORRIDOR = 8    # '긴 통로' = 긴 변 8칸 이상(10.3% — 옛 생성기 7.8% 와 같은 자릿수). 통로 긴 변 십분위 = 2·3·3·3·3·4·5·6·8

    def __init__(self, seed=7, depth=1, w=DEFAULT_W, h=DEFAULT_H, n_monsters=2, n_traps=3, n_lurkers=1,
                 scan=True, **kw):
        # 최소 격자 가드 — 작은 격자에서 randint 빈 범위(ValueError: empty range)로 죽지 않고 이유를 말한다.
        if w < MIN_W or h < MIN_H:
            raise ValueError('ConceptDungeon(던전 생성 프로필 concept)은 최소 %dx%d 격자가 필요하다 — 받은 값 %dx%d'
                             % (MIN_W, MIN_H, w, h))
        # scan 은 받은 값과 무관하게 켠다(위 ②). 부모 호출은 키워드로만 — verify_skill_stream 류의 __init__ 스텁(**kwargs) 호환.
        super().__init__(seed=seed, depth=depth, w=w, h=h, n_monsters=n_monsters, n_traps=n_traps,
                         n_lurkers=n_lurkers, scan=True, **kw)

    # ── 방 배치 ─────────────────────────────────────────────
    def _pack_rooms(self, target, large):
        """방 한 벌을 기각 표집으로 놓아 본다(고정 섹터·중앙 방·대칭 없음). 반환 (rooms, styles) — 굴림은 self.rng."""
        rooms, styles = [], {}
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
        return rooms, styles

    def _lattice_rooms(self, target):
        """마지막 폴백 — 6×5 방을 간격 2 의 격자 자리에 행 우선으로 채운다. 굴림 없음 · MIN_W×MIN_H 이상이면 6칸 이상 보장."""
        rooms, styles = [], {}
        for y in range(2, self.h - 5 - 1, 7):
            for x in range(2, self.w - 6 - 1, 8):
                if len(rooms) < max(5, target):
                    rid = len(rooms)
                    rooms.append(G.Room(rid, x, y, 6, 5))
                    styles[rid] = 'chamber'
        return rooms, styles

    def _carve_rooms(self, n=6):
        target = self.rng.randint(5, 8)
        self.room_styles = {}
        # Rejection sampling has no fixed sectors, central room, symmetry or required hall.
        for _ in range(12):
            large = self.rng.choices([0, 1, 2], [3, 6, 1])[0]
            rooms, styles = self._pack_rooms(target, large)
            if len(rooms) >= 5:
                break
        else:
            # D88 완화 폴백(결정론 — 같은 시드는 같은 길을 탄다): ① 대홀 없이 방 5개만 노려 12회 더 ② 그래도 안 되면
            #   격자 채우기. 예외를 던지면 층 전이 중 러너가 죽고, 이어가기도 같은 시드·같은 깊이라 같은 자리에서 다시 죽는다.
            for _ in range(12):
                rooms, styles = self._pack_rooms(5, 0)
                if len(rooms) >= 5:
                    break
            else:
                rooms, styles = self._lattice_rooms(target)
        self.room_styles = styles
        for r in rooms:
            for y in range(r.y, r.y+r.h):
                for x in range(r.x, r.x+r.w):
                    self.grid[y][x] = G.FLOOR
        self._ring_target = len(rooms)
        return rooms

    def _connected_floor(self):
        cells = {(x, y) for y, row in enumerate(self.grid) for x, c in enumerate(row) if c in (G.FLOOR, G.DOOR)}
        start = min(cells)
        seen, todo = {start}, [start]
        for x, y in todo:
            for p in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                if p in cells and p not in seen:
                    seen.add(p)
                    todo.append(p)
        return len(seen) == len(cells)

    def _clear_stray_walls(self, tiles=(G.FLOOR, G.DOOR)):
        """계획된 기둥이 아닌 '홀로 선 벽 한 칸'(직교 네 이웃이 전부 tiles)을 바닥으로 — 통로 교차·문 어깨가 남긴 돌 조각.
        바뀐 칸이 있었으면 True."""
        planned, changed = set(self.columns), False
        for y in range(1, self.h-1):
            for x in range(1, self.w-1):
                if (x,y) not in planned and self.grid[y][x] == G.WALL and all(
                    self.grid[yy][xx] in tiles for xx,yy in ((x-1,y),(x+1,y),(x,y-1),(x,y+1))
                ):
                    self.grid[y][x] = G.FLOOR
                    changed = True
        return changed

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
        self.columns = []
        self._clear_stray_walls(tiles=(G.FLOOR,))
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
        self._thresholds = {}     # 생성기가 좁힌 문턱: 문 칸 → 그 문턱의 칸들(문+어깨) — _stamp_doors 가 읽고 지운다
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
                    else:
                        self._thresholds[run[len(run)//2]] = list(run)
        # Door shoulders can leave isolated pixels where corridors intersect.
        # Only the explicitly planned room columns should become freestanding pillars.
        self._clear_stray_walls()

    RESTORE_ARCH = True       # ⑤ 스위치(측정용 — 끄면 시제품 그대로: 되돌려진 문 자리에 어깨 벽 사이 1칸 구멍이 남는다)

    def _shouldered(self, c, run):
        """문 칸 c 의 양 어깨(문턱이 뻗은 방향의 두 이웃)가 둘 다 벽인가 — 문턱 run 은 방의 한 변을 따라 뻗는다.
        어깨는 run 안의 칸(3칸 문턱의 양옆 · 2칸 문턱의 한 옆)일 수도, run 밖의 칸(2칸 문턱의 다른 옆 — 방 모서리 너머)일 수도 있다."""
        (x, y), flat = c, run[0][1] == run[-1][1]
        return all(self.grid[yy][xx] == G.WALL for xx, yy in (((x - 1, y), (x + 1, y)) if flat else ((x, y - 1), (x, y + 1))))

    def _flanked(self, x, y):
        """문 칸의 좌우 또는 위아래가 둘 다 벽인가(방향을 모르는 문 — 엔진 1단계가 찍은 것)."""
        g = self.grid
        return (g[y][x - 1] == G.WALL and g[y][x + 1] == G.WALL) or (g[y - 1][x] == G.WALL and g[y + 1][x] == G.WALL)

    def _settle_doors(self):
        """부모 _stamp_doors 의 정착 루프와 같은 눈 — 직교 이웃 구역이 정확히 둘이 아닌 문 타일을 바닥으로(되돌리기만 하므로 수렴).
        부모 것은 1단계 스탬프와 한 함수라 따로 못 부른다(부모를 부르면 방금 걷은 문을 다시 찍는다) — 그래서 여기 한 벌."""
        while True:
            comp_now = self._zone_components()[0]
            bad = [(x, y) for y in range(self.h) for x in range(self.w) if self.grid[y][x] == G.DOOR
                   and len({comp_now.get((x + dx, y + dy)) for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0))} - {None}) != 2]
            if not bad:
                return
            for x, y in bad:
                self.grid[y][x] = G.FLOOR

    def _stamp_doors(self):
        """엔진의 문 스탬프·정착 루프(부모) 뒤에, **되돌려진 생성기 문**을 열린 아치로 복원한다(D88 ⑤).
        부모의 정착 루프는 '직교 이웃 구역이 정확히 둘'이 아닌 문 타일을 바닥으로 되돌린다(스캐너에게 유효한 문만 남긴다).
        이 프로필의 문은 2~3칸 문턱을 문 한 칸+어깨 벽으로 좁힌 것이라, 문만 바닥이 되면 어깨 벽 사이 1칸 구멍이 남는다 —
        문도 아치도 아닌 모양. 그 문턱의 어깨를 다시 바닥으로 걷어 원래의 2~3칸 트임으로 되돌린다(바닥만 늘어 연결은 안 끊긴다).
        바닥이 늘면 구역 짜임이 달라질 수 있으니 부모를 다시 돌려 남은 문을 재검한다 — 복원은 문턱을 하나씩 없애므로 수렴.
        **어깨를 잃은 문**(09-20 리뷰 수선 — 0콜 실측 200시드 1499문 중 91 = 6.1%): ① '홀로 선 벽 제거'(_clear_stray_walls)가
        3칸 문턱의 어깨 한 칸을 걷어 간 자리 ② 2칸 문턱이 방 모서리에서 끝나 문의 다른 옆(모서리 너머)이 통로 바닥인 자리
        ③ 엔진 1단계가 넓은 공간의 한 칸 접점에 찍은 홀로 선 문. 문짝 옆으로 돌아 들어갈 수 있고 같은 구역쌍에 문 명사가
        둘(문 + 트임) 생긴다 — 문이 아닌 모양이니 같은 복원(문 칸까지 바닥 = 열린 아치)으로 되돌린다. 수선 뒤 실측 0/1408."""
        gen = dict(getattr(self, '_thresholds', None) or {})
        while True:
            super()._stamp_doors()
            if not self.RESTORE_ARCH:
                break
            # ③ 엔진이 찍은 문(생성기 문턱 밖) 가운데 어깨 쌍이 없는 것 — 부모는 돌 때마다 같은 자리에 다시 찍으므로 매 회차 걷고,
            #    걷은 뒤의 구역 짜임으로 남은 문을 재검한다(_settle_doors = 부모 정착 루프와 같은 눈).
            free = [(x, y) for y in range(1, self.h - 1) for x in range(1, self.w - 1)
                    if self.grid[y][x] == G.DOOR and (x, y) not in gen and not self._flanked(x, y)]
            for x, y in free:
                self.grid[y][x] = G.FLOOR
            if free:
                self._settle_doors()
            lost = [c for c in sorted(gen) if self.grid[c[1]][c[0]] != G.DOOR or not self._shouldered(c, gen[c])]
            for c in lost:                       # 되돌려진 문 · 어깨를 잃은 문(①②) → 그 문턱을 통째로 바닥으로(열린 아치)
                for x, y in gen.pop(c):
                    self.grid[y][x] = G.FLOOR
            stray = self._clear_stray_walls()
            if not lost and not stray:
                break
        self.doors_restored = len(getattr(self, '_thresholds', None) or {}) - len(gen) if self.RESTORE_ARCH else 0
        self._thresholds = None

    # ── 소품(D92, 2026-09-20) ──────────────────────────────────
    # 클라이언트 그림 어휘와 같은 낱말(game/src/scene/dungeonDecor.ts PROP_KINDS: barrel·crate·jar·rubble).
    # 앞 셋은 '뒤질 수 있는 것'의 후보이기도 하다(던전 살림 스위치 — dungeon_gm.Dungeon.LIFE_RUMMAGE_IDS).
    PROP_CYCLES = (('barrel', 'crate', 'barrel', 'jar'),
                   ('jar', 'barrel', 'jar', 'crate'),
                   ('rubble', 'rubble', 'jar', 'rubble'))

    def _place_props(self):
        """방 가장자리에 큰 소품을 놓는다 — 지시서 art/dungeon-v2/IMPLEMENTATION_GUIDE.md '소품 배치' 절 그대로
        (작은 방은 한 모서리 최대 4 · 큰 방은 대각 두 모서리, 면적 10%·12개 상한 · 큰 방은 모서리 곁 둘째 줄까지).
        비우는 칸: 문과 그 주변 8칸 · 열린 통로 입구 · 피처(출구·상자·보물…)와 그 직교 이웃 · 몹 주변 8칸 · 함정 칸.
        **굴림은 엔진 판정 rng 가 아니라 좌표·시드 해시**(지시서 6항) — 같은 시드는 같은 지형과 같은 소품이다.
        하나 채택할 때마다 '나머지 바닥이 전부 이어지나'를 엔진의 이동 규칙으로 확인한다: 8방향·대각 코너컷 금지는
        직교 연결과 같다(대각이 허용되려면 양 직교 칸이 열려 있어야 하므로 그 직교 경로가 이미 있다).
        격자(#/./+)는 한 글자도 안 바뀐다 — 스캐너·문·구역 분류·시야는 소품을 바닥으로 본다(막는 것은 발뿐)."""
        orth = ((0, -1), (0, 1), (1, 0), (-1, 0))
        floors = {(x, y) for y in range(self.h) for x in range(self.w) if self.grid[y][x] in (G.FLOOR, G.DOOR)}
        blocked = set()

        def connected():
            start = next((c for c in sorted(floors) if c not in blocked), None)
            if start is None:
                return False
            seen, todo = {start}, [start]
            for x, y in todo:                  # todo 는 돌면서 늘어난다(BFS)
                for p in ((x-1, y), (x+1, y), (x, y-1), (x, y+1)):
                    if p in floors and p not in blocked and p not in seen:
                        seen.add(p)
                        todo.append(p)
            return len(seen) == len(floors) - len(blocked)

        reserved = set()
        for f in self.features.values():       # 피처와 그 직교 이웃 — 상자·보물·계단 앞을 막지 않는다
            reserved.add((f.x, f.y))
            reserved.update((f.x+dx, f.y+dy) for dx, dy in orth)
        for m in self.monsters:                # 몹 주변 8칸(보스 포함) — 처음부터 갇혀 있는 몹을 만들지 않는다
            reserved.update((m.x+dx, m.y+dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1))
        reserved.update((t.x, t.y) for t in self.traps)

        def near_door(x, y):
            return any(self.grid[y+dy][x+dx] == G.DOOR for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                       if 0 <= x+dx < self.w and 0 <= y+dy < self.h)

        props = []
        for r in self.rooms:
            seed = self._life_roll('prop_room', r.id, r.x, r.y)
            spacious = r.w * r.h >= 60
            if not spacious and seed % 7 == 0:
                continue                       # 숨 쉴 자리가 필요한 작은 방도 있다
            corners = [(r.x, r.y), (r.x+r.w-1, r.y), (r.x, r.y+r.h-1), (r.x+r.w-1, r.y+r.h-1)]
            (ax, ay), (bx, by) = corners[seed % 4], corners[(seed % 4) ^ 3]

            def score(c, ax=ax, ay=ay, bx=bx, by=by, spacious=spacious):
                x, y = c
                near = abs(x-ax) + abs(y-ay)
                if spacious:                   # 큰 방은 대각 두 모서리에 모은다(둘째 모서리는 살짝 뒤)
                    near = min(near, abs(x-bx) + abs(y-by) + 0.8)
                return (near + self._life_roll('prop_jitter', x, y) % 7 / 10.0, y, x)

            cands = []
            for y in range(r.y, r.y+r.h):
                for x in range(r.x, r.x+r.w):
                    edge = min(x-r.x, r.x+r.w-1-x, y-r.y, r.y+r.h-1-y)
                    if edge == 0 or (spacious and edge == 1
                                     and min(abs(x-ax)+abs(y-ay), abs(x-bx)+abs(y-by)) <= 4):
                        cands.append((x, y))
            cands.sort(key=score)
            cycle = self.PROP_CYCLES[seed % len(self.PROP_CYCLES)]
            limit = min(12, r.w*r.h//10) if spacious else min(4, max(1, r.w*r.h*16//100))
            n = 0
            for x, y in cands:
                if n >= limit:
                    break
                if self.grid[y][x] != G.FLOOR or (x, y) in blocked or (x, y) in reserved or near_door(x, y):
                    continue
                if any(not r.contains(x+dx, y+dy) and 0 <= x+dx < self.w and 0 <= y+dy < self.h
                       and self.grid[y+dy][x+dx] == G.FLOOR for dx, dy in orth):
                    continue                   # 열린 통로 입구(문 타일 없는 트임) — 방의 목을 막지 않는다
                blocked.add((x, y))
                if not connected():
                    blocked.discard((x, y))
                    continue
                props.append({'id': len(props), 'kind': cycle[n % len(cycle)], 'x': x, 'y': y, 'blocks': True})
                n += 1
        self.props = props
        self.prop_cells = frozenset((p['x'], p['y']) for p in props if p['blocks'])

    def boss_front(self):
        """보스룸 앞 칸(D67) — 부모 규칙(테두리 관통 칸의 바로 바깥 바닥)이 답을 못 내는 지형의 폴백.
        이 프로필은 방 사이가 2칸일 수 있어, 관통 칸의 바깥이 곧 옆 방 문턱의 문·어깨 벽인 경우가 있다(0콜 스윕: 보스층
        300 중 12 에서 부모가 None). 그때는 방 밖으로 난 길을 따라(방 안으로는 안 들어간다) 테두리 다음으로 가까운 바닥 칸,
        그것도 없으면 테두리의 바닥 칸. 결정론(행 우선 출발 · 고정 이웃 순서 BFS)."""
        front = super().boss_front()
        if front is not None:
            return front
        ex, ey = self.exit
        rid = self._room_id_at(ex, ey)
        if rid is None:
            return None
        room = self.rooms[rid]
        ring = sorted(((x, y) for y in range(room.y - 1, room.y + room.h + 1)
                       for x in range(room.x - 1, room.x + room.w + 1)
                       if not room.contains(x, y) and 0 <= x < self.w and 0 <= y < self.h
                       and self.grid[y][x] in (G.FLOOR, G.DOOR) and not self.prop_at(x, y)),   # D92: 소품 칸에는 아무도 설 수 없다
                      key=lambda c: (c[1], c[0]))
        seen, todo = set(ring), list(ring)
        for x, y in todo:                      # todo 는 돌면서 늘어난다(BFS)
            for nx, ny in ((x, y-1), (x-1, y), (x+1, y), (x, y+1)):
                if ((nx, ny) in seen or not (0 <= nx < self.w and 0 <= ny < self.h) or room.contains(nx, ny)
                        or self.grid[ny][nx] not in (G.FLOOR, G.DOOR) or self.prop_at(nx, ny)):
                    continue
                if self.grid[ny][nx] == G.FLOOR:
                    return (nx, ny)
                seen.add((nx, ny))
                todo.append((nx, ny))
        return next((c for c in ring if self.grid[c[1]][c[0]] == G.FLOOR), None)

    def level_snapshot(self):
        level = super().level_snapshot()
        styles = getattr(self, 'room_styles', None)
        if styles is None:        # from_ascii/from_layout(__new__) 경유 인스턴스 — 건축 기록이 없다: 부모 스냅샷 그대로
            return level
        for room in level['rooms']:
            room['art_style'] = styles.get(room['id'], 'chamber')
        level['architecture'] = dict(version=ARCH_VERSION, columns=getattr(self, 'columns', []),
                                     corridors=getattr(self, 'corridors', []),
                                     extra_connections=getattr(self, 'extra_connections', 0))
        props = list(getattr(self, 'props', ()) or ())       # D92(09-20 additive) 엔진 소유 소품 — 있을 때만.
        if props:                                            #   클라이언트는 props 가 있으면 제 바닥 소품 추첨을 건너뛰고 이 목록을 그린다
            level['props'] = [dict(p) for p in props]        #   (game/src/scene/dungeonDecor.ts) = 충돌을 아는 쪽이 자리를 정한다
        return level

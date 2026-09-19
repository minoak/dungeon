# 마을 구역·건물 엔티티와 전체 맵

2026-09-19 갱신. 마을은 캐릭터별 자유 이동 공간이다. 방문 순서, 체류 상한, 파티 강제 제외는 추가하지 않았다.

`town.json`은 `art/town-v4/layout.json`을 가리킨다. 내부 96×64칸에 테두리 1칸을 더한 게임 격자는 98×66칸이다.
번화가·상점가·주거구역·신전·길드·던전 입구, 총 여섯 구역을 하나의 연속된 격자로 만들었다.
던전 입구는 내부 (76,52), 게임 좌표 (77,53)이다. NPC는 기존 세 정의와 기능을 유지한다.

## 정의와 배치

- `entities/map/*.json`: 마을 전체와 구역의 이름·역할. 길도 `map`이며 `space.role=street`다.
- `entities/building/*.json`: 건물 이름·점유 크기·남쪽 출입구·그림 참조.
- `layout.regions`: 구역 정의 id를 참조하고 경계 사각형들을 배치한다. 모든 칸은 정확히 하나의 구역에 속한다.
- `layout.buildings`: 건물 정의 id·왼쪽 위 칸·소속 구역. 원본 그림에 맞춘 배치는 선택 필드 `footprint: {size, entrance}`로 이 인스턴스의 크기·문턱을 지정한다. 엔티티 기본값은 바꾸지 않는다.
- `layout.connections`: 서로 맞닿은 두 구역의 통행 칸. 연결 그래프와 실제 보행 연결을 모두 검사한다.

`town_spaces.resolve`가 정의와 배치를 합쳐 건물의 막힌 사각형·문턱·그림 앵커를 만든다.
`town_layout.compile_layout → Dungeon.from_layout`의 기존 경로가 이것을 게임 격자로 읽는다.
v4는 최초 조감도를 바탕 그림으로 쓰고, `visual.art`의 전경 실루엣을 캐릭터와 발 높이 순으로 겹친다. 이전 지도는 기존 건물 스프라이트 방식을 유지한다.
프롬프트에 행동 지시를 넣지 않고, 엔진의 기존 NPC·입구 접근 동작을 사용한다.

현재 마을은 번화가·상점가·주거구역·신전 지구·모험가 길드 지구·던전 입구 지구의 6개 구역이다.
바닥 1,880칸에 빈틈과 중복이 없으며 전체가 연결된다. 건물 13채를 원본 조감도의 위치에 배치했다. 화덕·노점·우물 등 향후 상호작용 자리의 그림을 유지한다.
새 상점·공방·숙소는 외형과 문턱·이야기만 제공한다. 생산·강화·거래·숙박 효과는 아직 없다.

구역 이름과 이야기는 캐릭터의 관측에 연결된다. 구역은 사람·말의 범위이며, D86의 `DUNGEON_TOWN_SIGHT=zone`을 켜면
건물·NPC의 시야도 해당 구역을 따른다. 기존 신탁·의뢰·주점·신전 서비스는 유지한다.
길드와 주점이 놓인 구역을 파티 결성 장소로 찾으므로 현재는 길드 구역과 번화가 전체에서 결성한다.
던전 입구 피처는 하나만 둔다. 서쪽 외부 출구 예정지는 표식이며 전이 기능이 없다.
자세한 배치·제작 방법은 [마을 v4](../art/town-v4/README.md)를 참조한다.

## 확인

```powershell
python verify_town_v4.py --export
python art/town-v4/build.py
python art/town-v4/export.py
python tools/check_town.py town.json
python verify_town_spaces.py
node art/town-v4/verify-game.mjs
python art/town-v3/verify_isolated.py --all
```

`art/town-v4/compare.html`은 격자·충돌·구역 경계·출발점부터 목적지까지의 길을 확인하는 제작용 화면이다.
게임의 기존 마을↔던전 왕복도 그대로 사용한다.
새 원정부터 새 맵을 읽는다. 이미 진행 중인 판의 공간은 바뀌지 않는다.

이전 길드 앞 맵과 에셋은 `art/town-v1`과 `art/town-v2`에 보존했다. 일반 layout v1과 `from_ascii`도 계속 지원한다.

길드 행인 두 명의 새 앞마당 범위는 `layout.walker_rects`에서 지정한다. 구역 id와 정의 기본 rect는 보존하므로 이전 지도에서도 행인이 나온다.

# 마을 구역·건물 엔티티와 전체 맵

2026-09-12. 마을은 캐릭터별 자유 이동 공간이다. 방문 순서, 체류 상한, 파티 강제 제외는 추가하지 않았다.

`town.json`은 `art/town-v2/layout.json`을 가리킨다. 내부 51×37칸에 테두리 1칸을 더한 게임 격자는 53×39칸이다.
신전·길드·주점·던전 입구 지구와 번화가·샛길, 총 여섯 구역을 하나의 연속된 격자로 만들었다.
던전 입구는 내부 (40,29), 게임 좌표 (41,30)이다. NPC는 기존 세 정의와 기능을 유지한다.

## 정의와 배치

- `entities/map/*.json`: 마을 전체와 구역의 이름·역할. 길도 `map`이며 `space.role=street`다.
- `entities/building/*.json`: 건물 이름·점유 크기·남쪽 출입구·그림 참조.
- `layout.regions`: 구역 정의 id를 참조하고 경계 사각형들을 배치한다. 모든 칸은 정확히 하나의 구역에 속한다.
- `layout.buildings`: 건물 정의 id·왼쪽 위 칸·소속 구역. 여기에는 크기를 복제하지 않는다.
- `layout.connections`: 서로 맞닿은 두 구역의 통행 칸. 연결 그래프와 실제 보행 연결을 모두 검사한다.

`town_spaces.resolve`가 정의와 배치를 합쳐 건물의 막힌 사각형·문턱·그림 앵커를 만든다.
`town_layout.compile_layout → Dungeon.from_layout`의 기존 경로가 이것을 게임 격자로 읽는다.
건물 그림은 같은 점유 너비로 확대·축소되며, 지붕은 점유 영역 위로 뻗을 수 있다.
프롬프트에 행동 지시를 넣지 않고, 엔진의 기존 NPC·입구 접근 동작을 사용한다.

공간 정의는 **맵 저작·충돌·시각 레이어**에 연결됐다. 건물 자체를 `use`하는 새 동사나 실내 전환,
에이전트 관측에서 `r1` 대신 구역 이름을 말하는 배선은 이번 범위에 넣지 않았다.
세부 기능(신탁·의뢰·주점 서비스)도 아직 추가하지 않았다. 이 단계는 외부 전체 맵이다.

## 확인

```powershell
python art/town-v2/export.py
python check_town.py town.json
python verify_town_spaces.py
node art/town-v2/verify-browser.mjs
```

`art/town-v2/preview.html`은 격자·충돌·구역 경계·출발점부터 목적지까지의 길을 확인하는 제작용 화면이다.
아스키는 `town-ascii.txt`로 내보내며 독립 저작하지 않는다. 게임의 기존 마을↔던전 왕복도 그대로 사용한다.
새 원정부터 새 맵을 읽는다. 이미 진행 중인 판의 공간은 바뀌지 않는다.

이전 길드 앞 맵과 에셋은 `art/town-v1`에 보존했다. 일반 layout v1과 `from_ascii`도 계속 지원한다.

# 마을 맵이 지켜야 할 것 — 엔진·러너가 맵에 기대는 자리 (2026-09-19)

마을 맵을 다시 짜는 동안 엔진·러너 쪽 작업(D84 파티 결성 · D85 인물 기록 · D86 마을 시야)이 계속 돌려면 맵이 지켜야 하는 것들.
전부 코드에서 확인한 사실이다(`dungeon_gm.py` · `show_runner.build_town` · `entities/`). 파트너(09-19): "지금 마을 맵은 전체적으로 재구성 중이야" → "지켜야 할 부분만 말해줄래?"

## 1. 모든 바닥 칸은 어느 구역(region) 하나에 속한다

- 읽는 곳: `layout_result.spaces.regions[] = {id, name, rects[[x, y, w, h]], entity}` + `pad`.
- 구역은 세 규칙의 단위다 — 말이 들리고 사람이 보이는 범위(D70), 마을의 시야(D86, 스위치 판), 파티를 맺는 곳(D84).
- v3 적용 후 바닥 2,052칸 전부가 6구역 안에 있다(빈틈 0). 이전 v2는 1,613칸이었다. 빈틈이 생겨도 죽지는 않지만(빈틈끼리 한 구역처럼 센다) 그 위에 선 캐릭터는 주변이 안 보인다 — 없는 게 좋다.
- 구역 **이름**(번화가·모험가 길드 지구…)은 프롬프트에 그대로 나간다 = 캐릭터가 읽는 문장이다.

## 2. 길드 건물(`guild_hall`)과 주점 건물(`tavern`)이 어느 구역 안에 놓여 있다

- 읽는 곳: `layout_result.spaces.buildings[] = {id, entity, name, region}`.
- 파티를 맺는 곳은 구역 id 가 아니라 **이 두 건물 정의가 놓인 구역**으로 찾는다(`Dungeon._party_zone_ids` — 09-19 밤부터). 구역 이름·구성을 바꿔도 따라온다.
- 둘 다 없으면 옛 구역 id(`guild_district`·`tavern_district`)로 돌아가고, 그것도 없으면 아무도 파티를 못 맺는다 = 파티 결성 판에서 아무도 던전에 못 들어간다.

## 3. 던전 입구(`dungeon_gate`) — 출구 피처 하나와 그 건물 정의

- 입구 설명 문장, "3명이 맺은 파티만 지난다" 규칙, 도착 자리(입구 곁)가 여기에 붙는다.

## 4. 걷는 NPC 셋은 정의 파일에 구역 id 가 박혀 있다

- `entities/npc/apprentice_adventurer.json` · `wandering_adventurer.json` → `walk.region: "guild_district"` · `street_vendor.json` → `"main_street"`.
- 구역 id 를 바꾸면 이 세 파일도 같이 바꾼다. 안 바꾸면 **에러 없이 그 NPC 가 그냥 안 나온다**(`build_town` 이 모르는 구역은 건너뛴다).

## 5. 구역·건물의 이야기는 엔티티 id 로 연결된다

- 구역: `entities/map/town_*.json`(region 의 `entity`) · 건물: `entities/building/*.json`. 새 구역·건물에는 정의가 있어야 특징 문장(멀리서 한 줄 · 곁에서 내력)이 붙는다.

## 맵이 바뀌면 같이 손봐야 하는 게이트(지금 맵의 구역 id·이름·길이 검사에 적혀 있다)

`verify_guild` · `verify_town` · `verify_partyform` · `verify_people` · `verify_townsight` · `verify_worlds`
(예: `verify_townsight` 는 "길드 → 상점가 → 던전 입구 지구" 순으로 멈추는 것을, `verify_partyform` 은 신전 지구가 '맺는 곳이 아닌 구역'임을 본다.)
새 맵이 들어오면 이 여섯을 새 구역 id·이름에 맞춘다 — 엔진·러너 코드는 위 1~5 만 지켜지면 손댈 것이 없다.

## v3 적용 확인 (2026-09-19)

v3 배치는 `art/town-v3/layout.json`에 보존했다. `verify_town_v3.py`가 위 계약과 NPC를 포함한 건물 접근 가능 여부를 검사한다.
길드와 주점의 소속은 각각 `guild_district`, `main_street`다. NPC 아틀라스 행은 성직자 0·접수원 1·주점 주인 2를 유지한다.

## v4 적용 확인 (2026-09-19)

현행 배치는 `art/town-v4/layout.json`이다. 최초 조감도의 건물·길·물길에 보행 격자를 맞췄다.
`verify_town_v4.py`가 1,880 바닥칸의 연결·구역 소속, 건물 13채의 접근, 행인 셋과 파티 장소를 검사한다.
구역 id와 이야기 정의는 보존한다. 길드 행인의 앞마당 좌표만 배치의 `walker_rects`로 덮어쓰며 옛 지도에는 정의의 rect를 적용한다.

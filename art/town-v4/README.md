# Town v4 — 최초 조감도를 실제 맵으로

2026-09-19. v3의 별도 타일 조합을 더 장식하는 방식으로는 승인된 조감도의
비율·밀도·물길·단차를 재현하지 못했다. 이 버전은 **원본의 건축과 지형 자체를
게임 바탕 그림으로 사용하고 보행 격자를 그 위에 직접 맞춘다.**

## 비교

- 원본: `../town-v3-draft/concept-reference.png` (1536×1024).
- 이전 구현: `../town-v3/map-overview.png`.
- 정리한 그림: `source/town-clean.png`; 원본의 글자판과 정지 인물만 imagegen으로 제거.
- 런타임 사본: `../../game/src/assets/world/town-concept.png`.
- `compare.html`: 원본/이전 구현/현행 그림/겹쳐보기, 보행·구역 표시, 두 지점 경로 확인.
- `game-overview.png`, `game-preview.png`: 실제 Phaser 클라이언트의 0콜 스냅샷.

중앙 분수·양옆 노점·서쪽 주점, 북서 신전과 북동 길드, 동쪽 작업장,
남서의 조밀한 주거지, 남동 동굴과 중앙 다리를 원본 위치에 유지했다.
기존 구현의 붉은 벽돌 광장·별도 대형 잡화점·여분 주택은 원본 구도로 교체했다.
원본 시장의 서쪽 노점은 잡화점 문턱으로, 주거 건물 다섯 채는 공동 숙소·정원 숙소·
일반 여관·주민 집 두 채로 연결한다. 건물 엔티티의 기존 서비스는 변경하지 않는다.

## 실제 공간

내부 96×64, 테두리 포함 98×66. 원본 16px = 한 칸, 게임 한 칸 = 48px.
`build.py`가 직접 지정한 보행 다각형·고정물·건물 문턱을 격자로 만든다.
연결되지 않은 장식 영역은 통행 불가로 남기며 모든 문턱은 연결 검사에 통과해야 한다.
1,880칸의 바닥 전체가 연결되고 정확히 한 구역에 속한다. 여섯 region id는 보존한다.
건물은 13동, 던전 출구 피처는 하나(내부 76,52 / 엔진 77,53)다.
서쪽 출구와 그림의 바깥 다리는 예약 공간이며 외부 세계로 전이하지 않는다.

`footprint: {size, entrance}`는 이 배치의 건물 크기만 덮어쓴다. 엔티티 기본 크기는
보존되므로 옛 지도는 동일하다. `walker_rects`는 길드 앞마당의 이 배치 좌표를
제공하며 정의의 walk.region/rate는 유지한다. 옛 지도에는 정의의 rect가 계속 적용된다.

`TownVisual.art`는 바탕 이미지·원본 크기·지도 크기·전경 실루엣·지역 이름표다.
18개 실루엣이 동일한 텍스처를 마스크로 다시 그려 캐릭터와 발 높이 순으로 겹친다.
층 교체 시 마스크도 폐기한다. 바탕 그림의 인물은 제거했고 실제 NPC와 캐릭터만 그린다.
기본 배율은 0.5배, 0.25배에서 지역 이름표를 표시한다. 기존 맵과 던전으로 바뀌면
종전 기본 배율로 돌아간다. 작은 세부 소품의 충돌은 16px 단위 근사다.

모루·화덕·노점·우물 등의 그림은 향후 상호작용을 위한 자리다.
이번 변경은 제작·강화·거래·숙박 효과를 구현하지 않는다.

## 재현

```powershell
python art/town-v4/build.py
python art/town-v4/export.py
python art/town-v4/engine_preview.py
python verify_town_v4.py --export
node art/town-v4/verify-game.mjs
npm --prefix game run build
python art/town-v3/verify_isolated.py verify_town_v4 verify_town_v3 verify_town_spaces verify_town verify_guild verify_partyform verify_people verify_worlds verify_townsight verify_entities verify_companion verify_resume
```

`verify_isolated.py`는 소스만 임시 복사하여 실제 플레이 기록과 분리한다.
`verify-preview.mjs`는 로컬 Vite 4217에서 비교 페이지의 그림·경로·전환을 확인한다.
`preview-run.jsonl`은 엔진에서 만든 표시 검사용 더미 판이며 실제 AI 플레이가 아니다.
새 원정에 적용하며 이미 저장된 판의 격자·시각 레이어는 바꾸지 않는다.

회귀 게이트의 지도 의존 가정도 변경했다: 새 길드→입구 경로는 상점가를 먼저 지나고,
인물 기억 이월 검증의 이동 한도는 60→160틱이다. 다중 세계 검증은 기다리는 시간의
판단을 검사하며 긴 goto 중에 매 틱 새 판단을 요구하지 않는다.

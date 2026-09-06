# Wonderland character parts · v1

얼굴 수정본: 변환 과정에서 턱선·귀·머리 틈을 눈으로 오인하던 문제를 수정했습니다.
정면은 같은 높이의 눈 2픽셀, 측면은 눈 1픽셀, 후면은 눈 0픽셀을 검사합니다.
피부와 밝은 머리색의 분류도 분리했습니다. 데이터 형식 버전은 1을 유지합니다.

정면 확정 시안을 바탕으로 만든 **16×16, 4방향 정지 + 걷기 에셋**입니다.
원본보다 픽셀 수가 줄어들어 머리 모양·얼굴·옷의 세부는 단순화되었습니다.
생성한 방향별 원본을 색상 분류·격자 변환·접합 정리한 첫 게임용 제작본이며,
게임 실행 중의 가독성과 미세한 실루엣 조정은 실제 뷰어에서 확인할 단계입니다.
공격 애니메이션, 장비 외형, GitHub 반영은 포함하지 않습니다.

## 먼저 보기

`preview.html`을 브라우저에서 열면 됩니다. 설치·서버·네트워크 연결이 필요 없습니다.
머리 12종, 몸통 2종, 머리색·피부색·상의색·하의색을 조합할 수 있습니다.
현재 방향 PNG(16×16), 4방향 시트(64×16), 외형 설정 JSON을 내보냅니다.
걷기 모드에서는 현재 자세 PNG(16×16)와 4방향 걷기 시트(64×64)를 내보냅니다.
재생/일시정지, 속도 변경, 프레임 슬라이더를 지원합니다.
배경과 시각적인 바닥 그림자는 미리보기에서만 표시되며 PNG에는 포함되지 않습니다.

## 파일

- `assets/heads/{M1..M4,F1..F8}/{direction}_rear.png`: 뒷머리 레이어.
- `assets/heads/{id}/{direction}_front.png`: 얼굴·머리 앞쪽 레이어.
- `assets/bodies/{B1,B2}/{direction}.png`: 바지형 / 치마형 몸통.
- `assets/composed/{head}_{body}/{direction}.png`: 기본 색상의 조합 96프레임.
- `assets/characters-atlas.png`: 64×384 RGBA 시트.
- `assets/sprites.json`: 16×16 팔레트 인덱스 행렬·재질 매핑·파츠 메타데이터.
- `contact-sheet.png`: 모든 기본 조합을 확대해서 보는 검토용 이미지.
- `sources/`: 승인 정면 시안과 이미지 생성 도구로 확장한 방향별 원본.
- `tools/`: 변환·미리보기 패키징·검증 스크립트.
- `assets/walk/bodies/{B1,B2}/{direction}_{0..3}.png`: 걷기 몸통 32프레임.
- `assets/walk/composed/{head}_{body}/{direction}_{0..3}.png`: 걷기 조합 384프레임.
- `assets/walk/composed/{head}_{body}/sheet.png`: 각 조합의 64×64 걷기 시트, 총 24장.
- `walk-preview.gif`: 대표 조합의 4방향 걷기 미리보기.

## 걷기 조합

한 주기는 **발 A → 중간 자세 → 발 B → 중간 자세**의 4프레임이며 기본 140ms/프레임입니다.
머리 모양을 재사용하고 몸통의 팔·다리를 번갈아 움직입니다.
중간 자세는 정지 몸통을 재사용하며 머리 앞/뒤 레이어를 y 방향으로 1픽셀 내립니다.
긴 머리도 같은 오프셋을 받습니다. 머리카락의 별도 흔들림은 없습니다.
발바닥 기준은 프레임 하단이며, 게임 월드 좌표 이동은 기존 이동 로직이 담당합니다.
이번 수정에서 M1 정면의 화면 왼쪽 눈 바로 위 (x=6,y=5)를 피부 밝은색으로 고쳤습니다.

`sprites.json`의 정지 데이터 구조는 유지하고 다음 필드를 추가했습니다.

- `revision`: `idle-walk-1`
- `animations.walk.frame_ms`: 140
- `animations.walk.head_offset_y`: `[0,1,0,1]`
- `bodies[id].walk[direction][frame]`: 16×16 몸통 팔레트 행렬

걷기 시트의 **열은 프레임 0,1,2,3 / 행은 front,left,back,right**입니다.
정지 시트와 열/행 규칙이 다르므로 `animations.walk.sheet`를 참조하십시오.
걷기 중에는 경과 시간으로 프레임을 선택하고, 멈추면 기존 정지 프레임으로 돌아갑니다.

```js
const phase = Math.floor(elapsedMs / data.animations.walk.frame_ms) % 4;
const dy = data.animations.walk.head_offset_y[phase];
// rear at (0,dy), bodies[body].walk[direction][phase] at (0,0), front at (0,dy)
```

## 규격과 조합

모든 개별 PNG는 16×16 RGBA, 알파는 0 또는 255입니다.
열 순서: `front`, `left`, `back`, `right`. `front`는 화면 아래를 바라봅니다.
완성 시트의 행 순서: M1_B1, M1_B2, M2_B1, M2_B2, …, F8_B1, F8_B2.
왼쪽 위 (0,0), 공통 발 기준은 y=16, 몸통은 대략 y=8부터 시작합니다.
**rear → body → front** 순서로 동일한 (0,0)에 겹칩니다.
뒷모습의 긴 머리는 `front` 레이어에서 몸통을 덮습니다.
앞/옆모습에서 목 아래 중앙으로 내려온 뒷머리는 `rear`에 둡니다.
따라서 비어 있는 `rear` PNG도 정상입니다.

M/F 표시는 외형 목록의 기본 분류입니다. 모든 머리는 두 몸통에 교차 조합할 수 있습니다.
레이어 전체를 같은 색으로 칠하면 피부·의상이 함께 바뀌므로 재질 인덱스를 사용하십시오.

## 색상

`sprites.json`의 팔레트 인덱스:

| 인덱스 | 의미 |
|---|---|
| 0 | 투명 |
| 1 | 고정 윤곽선 |
| 2 | 고정 눈 |
| 3–5 | 피부: 그림자·기본·밝은색 |
| 6–8 | 머리 |
| 9–11 | 상의 |
| 12–14 | 하의 |
| 15–17 | 벨트·신발, 기본 고정 |

피부 매핑은 얼굴·손·다리에 함께 적용합니다. 재질별 3색을 한꺼번에 교체하십시오.
미리보기는 선택한 기본색에 맞춰 원래 음영 비율을 적용하고 0–255로 제한합니다.
아주 밝거나 어두운 사용자 지정 색에서는 음영 차이가 줄 수 있습니다.
게임에서는 검토한 3색 팔레트 묶음을 직접 지정해도 됩니다.

```js
const h = data.heads[preset.head].frames[direction];
const body = data.bodies[preset.body].frames[direction];
const index = h.front[y][x] || body[y][x] || h.rear[y][x];
// 0 -> transparent; otherwise selectedPalette[index]
```

Canvas: `ctx.imageSmoothingEnabled = false`.
CSS: `image-rendering: pixelated`. 정수 배율로 확대하는 것을 권장합니다.
논리적인 이동/시야/충돌 판정은 기존 타일 좌표를 유지하십시오.

## 재생성

Python + Pillow + NumPy + SciPy 환경에서:

```sh
python tools/build_assets.py
python tools/build_walk.py
python tools/package_preview.py
python tools/verify_assets.py
python tools/verify_walk.py
```

변환 스크립트의 크롭은 제공된 원본 이미지에 맞춰 작성됐습니다.
원본을 새 이미지로 교체하면 파츠 수와 매핑부터 재확인해야 합니다.
코드와 게임 저장소를 수정하거나 배포하지 않은 독립 전달 묶음입니다.

## 원더랜드 리포 안에서 (D37, 2026-09-06)

- 출처: 파트너 자작 묶음 v1(`revision: idle-walk-1`) — 정면 시안 승인 후 이미지 생성 도구로 방향을 확장하고
  스크립트로 격자 변환한 것. 외부 에셋이 아니다.
- 이 폴더에는 원본 시안(`sources/`)·변환 도구(`tools/`)·검토 이미지·`preview.html` 만 커밋한다.
  `assets/`(합성 PNG·`sprites.json` 재생성물)는 `.gitignore` — 게임은 PNG 를 쓰지 않는다.
- **런타임 유일본은 `viewer/assets/sprites/sprites.json`**(이 묶음 `assets/sprites.json` 의 사본).
  뷰어·론처가 팔레트 인덱스 행렬을 읽어 캔버스에서 합성한다(`viewer/assets/sprites/sprites.js`).
  도구로 재생성했으면 그 파일로 다시 복사할 것. 색 스와치·기본색은 리포 루트 `looks.json`.

# 원더랜드 월드 에셋 1차 교체

세밀한 SD 캐릭터와 16px 임시 몬스터·맵 사이의 표현 차이를 줄이기 위한 에셋 묶음.
새 Phaser 게임(`/game/`)에 적용한다. HTML 임시 뷰어의 타일 사전은 바꾸지 않는다.

| 파일 | 내용 | 런타임 규격 |
|---|---|---|
| `goblin-source.png` | 큰 귀·올리브색 피부·가죽 장비의 SD 고블린 | 96px 셀, 3열×4행 |
| `spider-source.png` | 남청색 외피·호박색 눈의 그림자거미 | 96px 셀, 3열×4행 |
| `terrain-source.png` | 돌바닥 4변형, 벽 앞면 2변형, 벽 윗면, 마을 포장 | 48px 타일, 4열×2행 |
| `props-source.png` | 문, 계단, 상자, 샘, 보물, 물약, 검, 방패 | 96px 셀, 4열×2행 |
| `traps-source.png` | 가시·다트·경보 함정, 비석 | 96px 셀, 2열×2행 |

몬스터 행 순서는 정면→오른쪽→뒷면→왼쪽, 열은 정지→걷기 A→걷기 B다.
몸 크기를 프레임별로 늘리지 않고 종 전체에 같은 배율을 적용한다. 셀 안 발바닥은 y=92,
고블린은 머리 중심으로 정렬한다. 거미는 캐릭터보다 낮고 넓게 표시한다.

생성 방식은 **내장 imagegen**. 기존 SD 검사 시트는 스타일 참조로만 사용했다.
정확한 프롬프트는 [고블린](goblin-prompt.txt), [배경 추출용 수정](goblin-key-prompt.txt),
[걷기 연속성 수정](goblin-fix-prompt.txt), [그림자거미](spider-prompt.txt),
[지형](terrain-prompt.txt), [오브젝트](props-prompt.txt), [함정·비석](traps-prompt.txt)에 남긴다.
첫 고블린 결과는 실제 알파 대신 체크무늬를 그렸으므로 최종본에 사용하지 않았다.
이미지 편집으로 배경을 단색 키 색으로 바꾼 뒤 게임 패킹 과정에서 알파를 추출했다.

`node art/world-v1/build-runtime.mjs`로 재생성한다. Node + sharp가 필요하며,
sharp가 프로젝트에 없으면 Codex 번들 라이브러리를 사용한다. 파이프라인은 원본의 키 배경 추출,
셀 분리, 최근접 축소, 위치 정렬만 수행한다. 픽셀 내용 자체를 새로 그리지 않는다.
프레임의 빈 셀·셀 경계 접촉·런타임 잘림은 오류로 처리한다. 세부 정렬 수치는 `build-report.json`에 남긴다.

최종 파일은 `game/src/assets/world/*.png`, 매핑·걷기는 `game/src/assets/world.ts`에 있다.
Vite 빌드가 해시 파일로 복사하므로 생성 도구나 `art/` 원본을 서비스에서 읽지 않는다.
종류가 등록되지 않은 개체와 마을 NPC는 기존 Kenney 타일로 표시한다.

검증: TypeScript + Vite 빌드, 기존 리플레이 스모크, 두 몬스터의 걷기/시킹,
숨은 몬스터·함정 비노출, 에셋 로드/프레임 수/종류 폴백을 확인한다.
`before.png`와 `after.png`는 같은 원정의 t179·초점 1, `spider-in-game.png`는 거미 조우 화면이다.

# 전투 이펙트 검증

적용 범위는 Phaser 관전 화면(`game/src`)이다. 서버의 표시용 선택 필드는
`STREAM_FORMAT.md`에 정의한다. 게임 판정과 구뷰어·오프라인 뷰어는 바꾸지 않는다.

## 브라우저 없이 끝나는 검증

저장소 루트에서 실행한다.

```powershell
python verify_combat_stream.py
python verify_skill_off.py
cd game
npm.cmd run typecheck
node verify/combat-unit.mjs
node --check verify/combat.mjs
```

`combat-unit.mjs`는 실제 Combat·Playback·StreamParser 코드와 Phaser의 순수
Tint·Shake 부품을 실행한다. 정수 픽셀, 생성·수명, 피격 색 복원, 치명타 흔들림,
네 스킬, 시야, 옛 기록, 시킹·층·초점·판·배속 변경, 중복 알림, 라이브 추가와 점프를
검사한다. 그래픽 생성은 최소 어댑터이므로 실제 렌더 결과를 증명하지 않는다.
기대 결과는 `ALL PASS — 전투 구성요소 30건`이다.

`combat-fixture.mjs`는 두 검증이 공유하는 픽스처 검사다. 실제 장면 생성이 요구하는
`level.exit=[x,y]`와 지형·배열을 검사한다. 파서가 필드를 보존한다고 장면 생성까지
성공한 것은 아니다. 구성요소 검사에서도 출구가 빠진 픽스처가 거절되는지 확인한다.

`verify_combat_stream.py`는 공격·스킬 필드를 검사하고 3시드 기록을 한 번씩 생성한다.
원본은 `verify_skill_off.EXPECTED`와 비교하고, 새 표시 필드 세 개만 지역 함수로
제거한 사본은 `PRE_FX_EXPECTED`와 비교한다. 직렬화 전역 패치나 파일 쓰기는 없다.
표시 필드 외 관측·이벤트·스냅샷·난수까지 동일해야 통과한다.
2026-10-11 관리자 승인 기준선 이력은 `verify_skill_off.py`에 있으며,
두 Python 검증 모두 `_run_gates.sh`에 등록되어 있다.

## 관리자 브라우저 검증

브라우저 금지 세션에서는 실행하지 않는다. `game/`에서 정상적인 Vite 빌드와
설치된 Edge/Chromium 실행이 가능한 환경에서 다음 한 줄을 사용한다.

```powershell
npm.cmd run build; if ($LASTEXITCODE -eq 0) { node verify/combat.mjs }
```

기대 결과는 `ALL PASS — 전투 브라우저 검증: 검사 28, 실패 0`이다.
고정 `verify/fixtures/combat.jsonl`로 실제 폴링과 재생을 검사하고 종료 시
검증용 서버·브라우저를 닫는다. 스크린샷은 만들지 않는다.
기존 회귀 명령은 `npm.cmd run smoke`, `node verify/alpha.mjs`다.
이미 실행 중인 별도 검증 환경을 쓰려면 `WL_GAME_ORIGIN`(`/game/`을 제공하는 원점)과
`WL_CDP`(검증용 Chromium 연결 주소)를 지정할 수 있다.

조건 검사가 실패해도 뒤 검사를 이어가며 마지막에 실패 항목과 비정상 종료 코드를
남긴다. 오류에는 팝업·투사체 수, 실제 대상 스프라이트 존재·가시성·피격 색,
흔들림 시간·강도, 표시 깊이, 프레임·층, 장면 갱신 여부, 렌더러와 콘솔 오류가 포함된다.
이벤트 버스가 잡아 콘솔에만 남긴 오류도 수집한다. 장면은 즉시 정지하는 `sys.pause()`로
멈추고, 전진과 관측은 같은 브라우저 작업에서 처리해 타이밍 차이를 줄인다.
부팅 실패나 폴링 시간 초과처럼 진행 자체가 불가능한 경우에는 중단 원인을 요약한다.

## 눈으로 확인할 위치

`game/`에서 고정 픽스처를 복사하고 미리보기를 실행한다.

```powershell
Copy-Item verify/fixtures/combat.jsonl ../runs/t13-combat.jsonl
npm.cmd run preview
```

`http://127.0.0.1:4173/game/?run=runs/t13-combat.jsonl`에서 캐릭터 1을 보고
한 틱 전진 또는 재생한다. 시킹만으로는 이펙트가 나오지 않는다.

- t1: 치명타 숫자·투사체·피격 색·약한 흔들림
- t2: 회복 십자·숫자·MISS
- t3~5: 밀어베기·강타와 처치·붉은 베기
- t6: 함정·중독 부착·봇과 몹의 출혈
- t7: 숨은 대상·시야 밖 대상·피한 함정·없는 상태 이벤트 모두 표시 없음
- t8: 새 필드 없는 공격·타인에게 사용한 물약
- t10: 쓰러짐

숫자와 MISS는 이름표보다 위, 공간 도형은 안개 아래에 놓인다.
둘 다 발동 지점과 현재 대상의 시야 검사를 통과해야 하며, 실제 대상 스프라이트가
없거나 장면 갱신이 실패했으면 생성하지 않는다. 1·4·16배속, 되감기, 층·초점 변경 뒤
연출이 남지 않는지 살핀다. `&combatFx=0`으로 꺼지는지도 확인한다.

이펙트 수명은 재생 속도에 따라 120~700ms이고 다음 프레임에서 정리된다.
동시 상한은 64개다. 라이브 다중 틱 점프에서는 중간 틱과 도착 틱의 연출을 생략하고
로그·최종 스냅샷은 유지한다. 다음 한 틱부터 연출을 재개한다.

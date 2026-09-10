# 조합형 기본 승격 전 프롬프트 백업

2026-09-10 사용자 요청으로 조합형을 메인으로 승격하면서 원본 바이트를 보존했다.

- `adventurer_prompt_menu.md`: 이전 기본 메뉴형 지침.
- `adventurer_prompt.md`: 이전 자유서술형 지침.
- `SHA256.json`: 백업 시 확인한 각 파일의 SHA-256 해시.

현재 실행 지침은 저장소 루트의 `adventurer_prompt.md`(조합형)다. 이전 방식은 일반 론처에서 선택하지 않는다. 과거 비교·회귀 검증에 한해 명시적인 `DUNGEON_ACTION_MODE=menu|free`로 이 백업을 읽는 경로를 유지한다.

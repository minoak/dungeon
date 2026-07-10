# 원더랜드 (Wonderland)

AI 에이전트 파티가 픽셀 던전풍 로그라이크를 **자율 플레이**하고, 사람은 관전하는 프로젝트.
정체성은 "게임이 딸린 멀티테넌트 에이전트 하네스" — 게임은 첫 번째 상연물이고,
본체는 무대(결정론 엔진 · JSONL 스트림 · obs→action 계약)다.

## 핵심 원칙

- **말·의지는 에이전트에게, 공간·계산은 엔진에게** — LLM은 의지(핑)와 목소리(say)만 낸다.
  세계 생성·규칙·주사위(d20)·경로 탐색은 전부 결정론 코드가 쥔다.
- **사실의 원장은 시스템이, 해석의 저작권은 에이전트에게** (설계 D15) —
  사건의 기록은 엔진이 보증하고, 그 의미 부여(reason·say·도감 한 줄)는 에이전트의 몫.
- **시야-온리** — 봇은 보이는 것만 안다. 지도 기억 없음, 전역 정보 없음.
  "목소리는 시야를 탄다": 말은 보이는 상대에게만 배달된다.
- **결정론 시드 + 스트림** — 같은 시드는 같은 세계. `stream.jsonl`만 있으면 판 전체를 리플레이할 수 있다.

## 빠른 시작

```bash
bash ~/dungeon/live.sh    # 진짜 판(헤들리스) + 웹 뷰어 → http://localhost:8000/viewer/
bash ~/dungeon/start.sh   # tmux 분할 관전(맵·GM·봇별 사고) — 나가기: Ctrl-b d
bash ~/dungeon/verify.sh  # 검증 게이트 일괄 실행(라이브 데이터와 격리된 경로 사용)
```

Windows에서는 저장소의 `wonderland.bat` 더블클릭 — 메뉴식 패스트 스타터
(라이브 판 / tmux 관전 / 뷰어만 열기 / 실험 배치 상태 확인).

주요 환경변수: `DUNGEON_SEED` `DUNGEON_TURNS` `DUNGEON_DEPTHS` `DUNGEON_W`/`DUNGEON_H`
`DUNGEON_MENU`(리모컨, 기본 1) `DUNGEON_GM`(내레이터) `DUNGEON_PARTY_FILE` 등 — `show_runner.py` 참고.

## 구성

| 파일 | 역할 |
| --- | --- |
| `dungeon_gm.py` | **엔진(심판)** — 던전 생성·시야·전투·함정·자동보행. 진실은 코드가 쥔다 |
| `brains.py` | **두뇌** — claude CLI(Haiku)로 매 결정. 리모컨(액션 메뉴) + 파싱 실패 시 규칙 폴백 |
| `show_runner.py` | **러너** — 틱 루프, 파티 로딩, JSONL 스트림 방출 |
| `gm.py` | **내레이터(옵션)** — 스트림 소비자. 비동기 후채움이라 게임을 안 막는다 |
| `stream.py` · `STREAM_FORMAT.md` | JSONL 스트림 계약 — 리플레이 레시피이자 BYO-agent 계약의 씨앗 |
| `bestiary.py` · `bestiary.json` | **도감** — 판을 넘어 이월되는 캐릭터별 몬스터 지식 (D11③) |
| `party.json` | **캐릭터 시트** — 몸(스탯)과 마음(persona·관계). 관전자의 유일한 조종간 |
| `viewer/` | 웹 타일 뷰어 — 라이브 관전 + 지난 판(`runs/`) 리플레이 |
| `design/HARNESS_DESIGN.md` | **설계 정본** (D1~D15) |
| `verify.sh` · `verify_*.py` | 검증 스위트 11종 — 스테이지 회귀·스트림 원장·파티·메뉴·도감·intent |
| `ab_menu.py` · `ab_persona.py` | A/B 실측 도구 — 같은 시드에서 암(arm)별 실LLM 판 비교 |

## 실행 데이터

`state/`(라이브 판) · `runs/`(지난 판 스트림 보존) · `ab_runs/`(A/B 실측 판) ·
`bestiary.json`(도감 원장)은 실LLM으로 얻은 원본 데이터라 **백업 목적으로 커밋한다.**
스크립트로 재생성되는 검증 산출물(`state_*`)만 `.gitignore`로 제외.

## 요구사항

- WSL2 / Linux, Python 3 (표준 라이브러리만), tmux
- claude CLI (`claude -p`, 구독 로그인) — 두뇌·내레이터 호출용. 없으면 규칙 폴백으로도 돈다
- 에셋은 CC0만 사용 (뷰어 타일 포함)

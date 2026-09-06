# 원더랜드 (Wonderland)

**LLM 에이전트 파티가 로그라이크 던전을 자율 플레이하고 사람은 관전한다.**
*LLM agents autonomously play a roguelike dungeon — a deterministic engine judges, agents only decide.*

> 🎬 **데모: [`replay_viewer.html`](replay_viewer.html)** — 다운로드해서 더블클릭하면
> 실제 판(솔로 3인, 239틱, 전원 탈출)이 브라우저에서 재생된다. 설치·서버 불필요.
> 매 결정의 속내(💭)와 대사(「」)가 이벤트 로그로 흐른다 — 전부 실제 LLM 판단 기록이다.

![리플레이 뷰어 — t112: 카야가 그림자거미를 처치하고 두란이 문을 발견하는 장면. 밝은 칸이 이번 판에서 본 영역이다.](docs/screenshot.png)

## 왜 이렇게 설계했는가

**1. 심판은 코드다 — LLM은 판정하지 않는다.**
던전 생성·시야·전투 주사위(d20)·경로 탐색·함정, 세계의 모든 판정은 결정론 엔진(`dungeon_gm.py`)이 한다.
LLM 내레이터(GM)는 스트림을 구독하는 *소비자*로 강등되어 있다(꺼도 판이 똑같이 돈다).
LLM에게 심판을 맡기면 환각이 규칙이 되고 재현이 죽는다 — 여기서는 그 문이 구조적으로 닫혀 있다.

**2. 상태는 코드에 산다 — 에이전트는 의지만 낸다.**
에이전트가 세계에 보내는 것은 `{type, target?, say?, reason?}` 한 줄뿐이다.
HP·좌표·인벤토리·몬스터 AI는 전부 엔진 소유라, LLM이 "HP가 100이다"라고 우겨도 세계는 흔들리지 않는다.
모든 굴림이 시드 파생 RNG를 지나므로 **시드 + 결정 기록 = 판 전체가 바이트 단위로 재현**된다
(`STREAM_FORMAT.md`의 리플레이 레시피).

**3. 판단 주권 — 몸의 일은 코드가, 마음의 일은 에이전트가.**
걷기·계산·주사위(몸의 일)는 코드가 가져갈수록 좋고, 싸울지 도망칠지(마음의 일)는
코드가 가져가는 순간 제품이 줄어든다(설계 D14). 그래서 "도주 버튼"은 없다 —
피격당하면 엔진이 걸음을 멈추고 *물어볼 뿐*, 도망은 에이전트가 마음먹는다.
층위는 둘: **숙고**(LLM이 매 결정) + **반사**(타임아웃·파싱 실패 시에만 작동하는 규칙 폴백 —
판단을 선점하지 않는 비상 브레이크).

**4. 시야-온리 — 봇은 보이는 것만 안다.**
전역 지도 없음, 벽 너머 없음. 말(say)도 시야를 탄다 — 보이는 상대에게만 배달된다.
관전자용 스트림에는 숨은 함정·매복이 다 실리지만(극적 아이러니), 봇의 관측(obs)에는 없다.

**5. 비용 구조 — 기본은 0원, API는 명시적으로만.**
두뇌 백엔드 어댑터(`DUNGEON_BRAIN_BACKEND`): `claude_cli`(기본, 구독 CLI — 추가 과금 0) /
`anthropic_api` / `gemini_api`(실행자 본인 키를 `.env`에 — 저장소는 키를 모른다) /
`dummy`(LLM 0콜, 배선 검증용). 검증 게이트는 일부러 `.env`를 읽지 않는다 —
키 없는 프로세스에선 실 API가 물리적으로 못 나가는 구조적 안전핀.

## 아키텍처

```
show_runner.py (틱 루프) ─→ dungeon_gm.py (결정론 엔진: 생성·시야·전투·보행)
        │                         │ obs (시야-온리 관측 + 행동 메뉴)
        │                         ▼
        │                    brains.py (두뇌: LLM 백엔드 어댑터 + 규칙 폴백)
        │                         │ {type, target?, say?, reason?}
        ▼
state/stream.jsonl (append-only JSONL 스트림 — 진실의 원장)
        ├─→ viewer/  웹 뷰어 (python -m http.server 8000 정적 서빙, 라이브 tail + 지난 판)
        ├─→ gm.py    LLM 내레이터 (옵션 — 스트림 소비자, 엔진 무접촉)
        └─→ make_replay_viewer.py → replay_viewer.html (단일 파일 리플레이)
```

- **관측 직렬화**: 좌표를 주지 않는다. 기하 스캐너가 격자를 방/통로/문으로 읽어
  "동쪽 문 너머 큰 방(다 봄)" 같은 사람의 공간 언어로 직렬화하고 이동은 엔진이 열거한
  **선택지 메뉴에서 번호를 고르는 방식**(리모컨) — 새 동사가 생겨도 메뉴에 자동 등장한다.
- **절차 생성 던전**: 시드 하나로 방·주 고리(원환)·가지 통로·문·몹·함정·보물 배치까지 결정.
- **사회층**: 파티 대화(say/inbox)·말 걸림 정지·사건 목격 전달·의미 기억(한 줄 노트)·묘.
  파티 판과 솔로 판(서로 모르는 3인이 흩어져 출발)을 스위치 하나로 오간다.
- 저장은 전부 파일이다(JSONL·JSON). DB·웹 프레임워크 의존성 없음.

## 현재 상태 (2026-08 기준, 진행 중)

**검증 완료** — 결정론 게이트 `verify_*.py` **32종**(LLM 0콜, `bash _run_gates.sh`로 일괄):
엔진 물리(시야·전투·함정·경로)·스트림 계약·파티/솔로·스캐너·자기 관찰 정지·사건층·
장비·마을 등 설계 D1~D29의 구현부 전부가 게이트 뒤에 있다.
실LLM 판 실측: 파티 판(80×30, 207틱 전원 탈출)·솔로 판(239틱 전원 탈출)·마을 왕복 판.
지난 판 스트림은 `runs/`에 보존되어 있고 전부 리플레이 가능하다.

**다음 단계** — 게임 루프 완성(회복·조우 밀도), 월드 러너(N파티 방치형), 캐릭터 시트 UGC
(프롬프트 인젝션 검증 포함). 설계 정본과 미결 목록은 [`design/HARNESS_DESIGN.md`](design/HARNESS_DESIGN.md).

## 실행

요구사항: **Windows + Python 3** (표준 라이브러리만 — API 백엔드를 켤 때만 `pip install requests`).
LLM 두뇌는 claude CLI 또는 API 키가 필요하고, 없어도 `dummy` 백엔드로 물리 판은 돈다.

```
git clone https://github.com/minoak/dungeon.git
cd dungeon
wonderland.bat        ← 더블클릭: 메뉴식 스타터 (라이브 판 / 뷰어 / 솔로 판 / 마을 판)
```

**가장 쉬운 시작(D31 웹 론처)**: `wonderland.bat` → **[L]** (또는 `python launcher.py`) → 브라우저에서
파티를 꾸미고(직업 · 외형=머리·몸통·색 미리보기와 랜덤(D37) · 성격 키워드 최대 3개 또는 자유 서술 · 배경 자유입력) 던전 옵션(맵 크기 · 마을 시작 · 두뇌 · 시드)을
고른 뒤 **원정 시작** → 관전 뷰어로 이어진다. 시드는 기본 랜덤(뽑힌 값은 판 기록에 남아 재현 가능).
콘솔 메뉴의 다른 항목은 개발·실험용이다.

관전: 판이 시작되면 http://localhost:8000/viewer/ 가 자동으로 열린다.

```bash
# 검증 게이트 일괄 (Git Bash, LLM 0콜 — 라이브 데이터와 격리)
bash _run_gates.sh

# 지난 판 → 단일 HTML 리플레이 만들기
python make_replay_viewer.py runs/stream-XXXX.jsonl -o replay_viewer.html

# 지난 판 0콜 부검(이동·전투·대화 통계) / 사회층 부검(정지·정체·동행·lost·저체력 결정)
python analyze_run.py runs/stream-XXXX.jsonl
python analyze_social.py runs/stream-XXXX.jsonl
```

주요 환경변수: `DUNGEON_SEED`(정수 또는 `random` — 데모 기본) `DUNGEON_SIGHT`(엔진 5 · 데모 6) `DUNGEON_ALLY_SIGHT`(동료는 반경 안에서 벽·문 무시, 기본 1) `DUNGEON_PARTY_FILE` `DUNGEON_W/H` `DUNGEON_DEPTHS` `DUNGEON_BRAIN_BACKEND`
`DUNGEON_SOLO` `DUNGEON_TOWN` 등 — `show_runner.py`와 `wonderland.bat` 참고.

## 데이터와 에셋

`runs/`(지난 판 스트림)·`bestiary.json`(판을 넘어 이월되는 캐릭터별 도감)은 실LLM으로 얻은
원본 데이터라 저장소에 보존한다. 뷰어 타일 등 에셋은 **CC0만** 사용(Kenney).
캐릭터 파츠 스프라이트(D37, 2026-09-06)는 파트너 자작 — 원본 시안·변환 도구는 `art/sprites-v1/`, 뷰어·론처가 읽는 런타임본은
`viewer/assets/sprites/sprites.json`(16×16 팔레트 인덱스 행렬, 캔버스에서 합성 — PNG 없음), 색 스와치는 `looks.json`.
외형은 시트 `look` 필드 또는 러너의 시드 랜덤으로 정해져 판 기록(run_meta)에 남는다 — 엔진·프롬프트는 읽지 않는다.

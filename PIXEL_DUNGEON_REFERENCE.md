# Pixel Dungeon → Our Engine: BORROW / SIMPLIFY / SKIP (조사 전문)

> 2026-06-29 조사 결과. Shattered Pixel Dungeon(SPD) 실제 소스 기준. 구현 레퍼런스.
> 실행 계획은 `~\.claude\plans\whimsical-shimmying-nebula.md` 참조.
> 원칙: **모든 굴림은 시드 RNG 스트림에서 — "확률적" ≠ "비결정". 같은 시드 → 동일 재생.**

---

## 1. Mob AI / awareness → Stage 2 & 3

**핵심: 우리 "인식 매트릭스" = SPD의 `enemySeen` 불값을 양방향으로 만든 것.** 모든 (actor, other) 쌍에 `aware` 불 하나. 매트릭스 = 그 교차곱:

| bot aware of mob | mob aware of bot | quadrant | 효과 |
|---|---|---|---|
| ✓ | ✗ | **we-ambush-them** | 봇 기습(자동명중/유리 + 보너스 주사위); 몹 이번 라운드 스킵 |
| ✗ | ✓ | **they-ambush-us** | 몹 선공, 봇 기습보너스 상실, 포위 가능 |
| ✓ | ✓ | **face-to-face** | 일반 이니셔티브, 기습 없음 |
| ✗ | ✗ | **mutually-unaware** | 아직 조우 아님 — 지나치거나 선제 기습 |

> **SPD와 의도적 분기:** SPD 기습은 *일방향*(`enemy == Dungeon.hero` 가드 — 영웅만 확정타). 우린 대칭: **인식한 쪽이 미인식 대상에게 기습.** "they-ambush-us"에 이빨을 주는 핵심. SPD 비대칭 복사 금지.

**채택 상태(5개 다 말고):**
- **Stage 2 (이진):** `SLEEPING` + `HUNTING`만. 인카운터-온-패스 점화엔 충분. PASSIVE = 비전투 플래그.
- **Stage 3 (전체):** `WANDERING`(독립시계 배회자) + `FLEEING`(저HP/Terror) 추가.

**전이(`Mob.act()` 그대로):**
- SLEEPING → HUNTING: 발각굴림 통과 **and** 봇이 몹 FOV 안.
- SLEEPING → WANDERING: 소음/피해로 깸 but 봇 FOV 밖 (→ `randomDestination()` 배회).
- WANDERING → HUNTING: `inFOV && (justAlerted || roll)`.
- HUNTING → WANDERING: 봇이 FOV 벗어남 → 마지막 위치까지 추적 후 배회. **유지** — 봇이 접촉 끊고 재은신하는 숨바꼭질의 심장.
- **`TIME_TO_WAKE_UP = 1`**: 막 깬 몹은 1턴 더 기습 가능. 싸고 맛깔남.

**발각(턴당 굴림, 자동 시야 아님):**
```
inFOV    = mob_alive && bot in mob.fov && bot.invisible == 0
notice   = inFOV && (justAlerted || seeded_rng() < chance)
chance   = 1 / (dist + stealth)        # SLEEPING
chance   = 1 / (dist/2 + stealth)      # WANDERING (≈2배 쉬움)
```
`justAlerted`(Alarm함정·시끄러운 전사·피격)는 굴림 우회. **봇은 자기 FOV 안은 무조건 봄(굴림X); 굴림은 몹이 봇을 알아채는 것만 관장.** 이 비대칭 유지 — 옳고, 관전자 방향감 유지.
> 우리 구현 메모: SPD `1/(dist+stealth)` 확률은 *모양만* 차용, 표현은 우리 d20+능력치 vs DC로 통일. 단 concealed(숨은 함정·매복몹·발판)는 봇도 인지 판정 필요(도적 radius2/d20).

**독립 시계:** 몹은 봇과 무관하게 글로벌 스케줄러로 act — 잠자면 idle, 배회하면 계속 이동. 봇 존재는 *발각굴림*만 바꿈, 턴 자체엔 영향 X. tmux 피드를 살아있게 만듦.

**인카운터-온-패스 인터럽트(Stage-2 접착제):** 자동보행 한 칸마다 엔진이 (a) FOV에 봇 든 몹 발각굴림 (b) 봇의 직업게이트 인지 스윕 (c) **`aware` 비트 뒤집힘 OR 봇이 몹/함정 드러내는 순간 BFS 보행 정지 + 인카운터 이벤트.** 정지 시점 quadrant가 d20 경로 결정. 여기서 주사위가 의미를 가짐.

---

## 2. Stealth & detection → Stage 3

**SPD의 모든 은신 소스를 클래스 숫자 하나(= 위 `stealth` 제수)로 압축.** 이 한 스탯이 전사/도적 대비 전부:

| | search 반경 | stealth(발각 제수) | "loud" | 바닥 규칙 |
|---|---|---|---|---|
| **도적** | **2** (5×5) | **높음** | 아니오 | *Silent Steps*: `N`칸 내 sleeping/wandering 몹 **알아챌 수 없음**(하드 `chance=0`) |
| **전사** | 1 (3×3) | **낮음/~0** | 예 → 더 먼 거리서 `justAlerted` | — |

SPD 영웅 기본 은신 ~0(전부 장비/글리프) — 우린 뒤집어 클래스 내재로. 도적 강점: **반경2 search**(함정/비밀/숨은몹) + **Cloak 투명**(단순 쿨다운/차지 자원으로, SPD `1차지/4턴` 경제는 생략).

**Search: SPD의 능동/수동 분리 채택 — 자동보행과 완벽:**
- **수동 search-on-move**(자동보행 칸마다): 반경 내 숨은 함정/비밀 드러내는 시드 굴림. 시작 플랫 상수: **함정 40%, 문 20%**(SPD 깊이스케일 생략). 도적 반경2+보너스 = 훨씬 많이 찾음 → 관전자에게 *보이는* 정보 우위.
- **능동 search**(봇이 고르는 액션): 반경 내 **항상 성공**, 턴 소모. GM이 뭔가 암시할 때.

**함정: 베이스 클래스 1개, SPD 라이프사이클, 작은 스타터셋.** `visible` 불 하나 → `hidden → trigger() → activate()`. 숨은 함정 밟으면 사전감지 없는 한 발동; **감지 = 도적 수동 search OR DEX/인지 d20** — 도적 인지가 주사위를 버는 곳. 스타터 ~5개(33개 아님):

| 함정 | MVP 이유 |
|---|---|
| **Alarm** | **#1 우선** — 주변 몹에 `justAlerted` → 함정↔인식 결합. 줄당 연출 최고. |
| PoisonDart/WornDart | 최단순 원거리 피해 증명 |
| Pitfall | 봇을 다음 깊이로 떨굼 — 극적, 강하와 연결 |
| Rockfall *or* Burning | AoE/상태 구역 |
| Gripping | 속박 → 나쁜 인카운터 강제, 주사위 긴장 |

---

## 3. Generation & descent

생성기는 작동함 — **건드릴 가치 있는 차용 3개만:**

1. **단일 `>` 선형 강하 (채택).** 깊이당 EntranceRoom(`<`) 1개, ExitRoom(`>`) 1개, 엄격 선형. 싸고 검증됨, 그리고 자율플레이에 결정적 — **ExitRoom이 봇의 기본 핑 타겟.** 단일 명확한 "내려가" 거시목표가 리더 없는 봇 파티를 관전 가능하게 응집시킴(아니면 방황). 고가치.
2. **타입드 룸 + 방 인접 그래프 (보유 확인).** Entrance/Exit/Standard/Special/Secret + `connect()/neighbours` 그래프. BFS 길찾기와 "보이는 방 핑" 둘 다 그래프 요구; room-id 작업은 이미 Stage 1. 생성기가 타일 격자만 내면 그래프 층 추가 — Stage 2 막는 유일한 구조 갭.
3. **마스터시드 → 깊이별 파생 시드 (패턴 채택).** SPD는 마스터에서 각 깊이 시드 파생(`push → N longs 버림 → derive → pop`). 재현 가능 다층 런 + "시드로 이 판 그대로 재생" — 관전 상품에 직접 유용.

**생략:** LoopBuilder/FigureEightBuilder 자유배치, region Painter/장식, 분기 깊이, 데일리시드 충돌 오프셋. 순수 변주/광택; 우리 생성기가 구조는 이미 커버.

---

## 4. BORROW / SIMPLIFY / SKIP (구조 우선)

| | item | note |
|---|---|---|
| **BORROW** | 양방향 `aware` 불 = 인식 매트릭스 | 키스톤; 대칭(SPD 영웅전용 아님) |
| | SLEEPING/WANDERING/HUNTING + `enemySeen` + HUNTING→WANDERING 강등 | 3상태, 5 아님 |
| | 턴당 발각굴림 `1/(dist+stealth)` 시드RNG | 모양 유지, stealth 숫자 하나 |
| | `justAlerted` 우회 + `TIME_TO_WAKE_UP=1` | loud/Alarm 강제 발각; 1턴 취약창 |
| | 기습 = 자동명중/유리 + 대상 턴 스킵 | 클래식 d20 기습라운드 |
| | 베이스 `Trap` 1개(`visible`/`trigger`/`activate`) | 전 패밀리 커버 |
| | 은신=클래스스탯 + search반경 1 vs 2 + 수동/능동 search | 전사↔도적 대비 전부 |
| | 단일 `>` 강하, 타입드룸 + 방그래프, 마스터→깊이별 시드 | 생성기 건드릴 가치 |
| **SIMPLIFY** | 5상태 → 3 (+FLEEING 나중; PASSIVE = 플래그) | |
| | 기습 *데미지*: 플랫 보너스 주사위, Dagger-75%/Assassin-Preparation 아님 | |
| | 발각: flying/glyph/talent 스택 버림 → 숫자 하나 | |
| | 33함정 → ~5; search 확률 = 플랫 40%/20%, 깊이스케일 없음 | |
| | 도적 투명 = 단순 쿨다운, Cloak 차지 경제 아님 | |
| **SKIP**(→콘텐츠/Stage4) | 군집 `beckon`(8타일 대량 깨움) | 훌륭한 연출 — 첫 Stage-4 추가 |
| | Terror/Dread/Amok 버프 오버라이드, 전체 FLEEING | |
| | 서브클래스, 방어구 능력, 탤런트 트리 | |
| | Builder/Painter/장식, Broken Seal & Cloak 경제 | |
| | 9×7 함정 시각 분류, 데일리시드 오프셋, 분기 | |

---

## 5. 라이선스
SPD = **GPLv3**, but 게임 *메커니즘·규칙·숫자·상태기계 설계는 저작권 대상 아님* — 리터럴 소스코드만. 자체 Python 클린룸 재구현(`.java` 복붙X)은 명백히 OK. 코드 읽고 설계 차용 = 그러라고 있는 것.

---

## 7. Stage 2b 구현 결과 (2026-06-30) — 인식 매트릭스·발각굴림·대칭기습

`dungeon_gm.py`+`brains.py`+`adventurer_prompt.md`+`show_runner.py`, 검증=`verify_stage2b.py`(ALL PASS).
- **몹 상태기계**: SLEEPING/WANDERING/HUNTING. monster_turn 처리순서(상호배타): ①skip_turns>0=턴스킵 ②HUNTING=인접봇 공격(없으면 last_seen 추격, LOS상실 LOSE_GRACE=3 넘으면 WANDERING 강등) ③SLEEPING/WANDERING=FOV봇에 발각굴림만(인접이어도 공격X=봇 we-ambush 창), 무FOV면 가끔 표류(2a 외길봉쇄 livelock 해약 — SLEEPING도 표류 *필수*).
- **발각굴림(d20 idiom)**: `d20 + prox + (WANDER+2) >= DETECT_DC_BASE(13) + stealth`. prox=MON_SIGHT(3)-chebyshev. stealth 전사0(DC13)/도적4(DC17). 전사 자는몹 dist1≈50%, 도적≈30% → we-ambush(봇이 자는 몹 급습) 살아남음.
- **대칭 기습**: we-ambush=`_attack`서 `mon.state!='HUNTING'`이면 유리(2d20max)+SURPRISE_DMG_BOT(3)+skip_turns=1(반격 1턴 스킵). they-ambush=`_monster_attack`서 `m.id not in bot.aware_of`면 유리+SURPRISE_DMG_MON(2).
- **LOS 대칭화**: `_sight_blocked` 끝점 정규화(2.53% 비대칭 제거 — 매트릭스 공정성 토대).
- **봇 인지 단일소스 `_perceive`**(시야 내 비은닉 몹→aware_of, view+step_order 공유). concealed 몹은 여기서 제외 → aware_of에 영영 없음.
- **⚠️ they-ambush(비은닉)는 트인 곳에서 ~0이 정상** — 봇이 매 턴 FOV 전체 인지+대칭LOS라 다가오는 몹을 늘 먼저 봄("트인 곳에선 다 보인다"). 실측 120시드 몹공격 563회 전부 face-to-face. **진짜 매복은 concealed(투명/매복몹)=Stage3 솔기가 있어야 발화**(concealed면 _perceive가 못 걸러 aware_of 없음 → _monster_attack이 자동 매복). 사용자 지적: "매복엔 새 상태 필요"(투명). 억지로 만들려던 감쇠인지·move-and-strike는 **되돌림**.
- 검증 게이트: 300시드 풀게임 종료(livelock0)·결정론·벽뚫기금지·LOS대칭·we-ambush 70회·발각 384회·concealed 매복 솔기.
- **잔존(다음 단계가 채움)**: gm_prompt 신규이벤트(monster_notice/surprise) 어휘는 Stage4(GM 견고해 안 깨짐). concealed/perception_gate·은신 search반경·함정 패밀리(Alarm)·방 콘텐츠=Stage3.
- **프로세스 교훈**: 2b they-ambush(주변부 희귀기능)에 워크플로+300시드 검증까지 과투자 → 사용자 "1~5 폭 우선" 교정. [[feedback-breadth-over-stage-polish]].

---

## 6. Top 5 구체 변경(임팩트 순)

1. **인식 매트릭스 = 봇↔몹 `aware` 불 두 개, 각자 시드 발각굴림으로 뒤집힘; 4 quadrant = 교차곱이 d20 경로 선택.** 최고 레버 — 주사위에 의미 주는 것. Stage2 이진, Stage3 전체 공식. **대칭**(몹이 봇 매복 가능), SPD와 달리.
2. **단일 `>` 선형 강하, ExitRoom = 기본 핑 타겟.** 리더 없는 봇 파티에 단일 명확 거시목표 → 자율플레이 응집. 작은 변경, 큰 응집 보상.
3. **`stealth` 클래스 숫자 하나가 발각 제수에 투입**(도적: 높음+반경2+Silent-Steps 바닥; 전사: 낮음+"loud"=일찍 justAlerted). 클래스 정체성 전부를 스탯 하나로.
4. **베이스 `Trap` 1개 + Alarm 함정 먼저.** Alarm이 함정을 인식 시스템에 결합(`justAlerted` 주변몹) — 줄당 연출 최고, §1 즉시 스트레스테스트.
5. **모든 굴림을 시드 RNG 스트림 하나 + 마스터→깊이별 시드 파생.** 결정론/재현 원칙 유지하며 SPD 확률 질감 살리고, 시드로 판 공유 가능 — 관전 상품 기능, 배관 아님.

---

## 8. Stage 3+4 구현 결과 (2026-07-02) — 게임 통째로 완성(폭 우선)

구현: `dungeon_gm.py`+`show_runner.py`+`brains.py`+양 프롬프트, 검증=`verify_stage3.py`(ALL PASS, 회귀 1/2/2b 전부 초록).
- **직업 인지(§2)**: `search_r`(도적2/전사1) + 수동 search-on-move(`_passive_search`, 칸마다 d20+DEX≥14, 매복몹 DC16) + 능동 `_search`(턴 소모=반경 내 확정). 실측: dist1 함정 전사 40%/도적 49%, dist2 전사 0(구조적)/도적 52%.
- **함정 패밀리(§2)**: spike/dart/**alarm**(층의 비은닉 몹 justAlerted, 매복몹 제외). 드러난 함정은 path_to가 우회(외길이면 경유+조심보너스 +3).
- **매복몹(concealed) 그림자거미**: 봇 시야 완전 은폐(관전자 렌더엔 m=극적 아이러니), 자동보행 무정지, 인접 일격=**they-ambush 발화**(300시드 78회 — 2b의 예언 실현). 도적 search로 사전 발각→역으로 we-ambush 가능.
- **FLEEING+desperate**: 저HP 도주 → 협공=궁지('보이는 모든 봇과의 최소거리 엄격 증가'만 이동, 진동 없음) → 탈진(FLEE_STAMINA=8턴)=필사 반전(desperate HUNTING, 재도주 금지). **livelock 버그 2개 실측·수정**: ①도주 기준이 '최근접 봇 1명'이면 협공 사이 위상잠금 셔틀 — 봇 결정 틱엔 거리2·자동보행 틱엔 인접(seed 156/157/176) ②`_terrain_dist_from`이 대각 코너컷을 허용해 벽 모서리 X자 틈으로 '가짜 가까움' → best_effort가 거짓 [](seed 242, 2a부터 잠복).
- **TIME_TO_WAKE_UP=1**: 발각으로 깬 몹 waking=1 → 1턴 더 기습 가능(취약창).
- **방 콘텐츠**: 상자(d20+DEX≥10: 보물2/독침2피해), 샘(d20≥8: 회복3/오염1), 숨은 보물(concealed, 도적 인지의 보상).
- **Stage4 하강**: 출구 밟기=at_exit(자동탈출 폐지), interact=살아있는 파티 전원 계단 반경 EXIT_GATHER(3) 내 모여야 동반 하강(아니면 wait_allies). show_runner가 층 전이(마스터시드→층별 파생 시드, 몬스터 +1/층, HP·보물 이월, 죽은 영웅은 fallen 기록). DUNGEON_DEPTHS(기본2)·DUNGEON_LURKERS(기본1). obs에 party(좌표 없는 명단, 안 보여도 goto b<char>=파티 감각)·depth. gm_prompt 이벤트 어휘 전면 갱신(goto/walk/interact/monster_flee/desperate/from_hiding/alarm…).
- **dummy 폴백 정책**: 계단에선 기다린다(양쪽 다 데리러 나서면 상호 fetch 진동 → 데리러 가기는 LLM 전용 선택지), HP≤절반이면 샘으로.
- **검증**: `verify_stage3.py` 48 체크 ALL PASS + 회귀(1/2/2b) 전부 초록. 300시드 전 콘텐츠 풀게임 종료 300/300·결정론 20시드. 실발화: 매복일격 78·경보 54·도주 476·필사 133·발각 692·we-ambush 170·수동발견 691·상자 113·샘 35.

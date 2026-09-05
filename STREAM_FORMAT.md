# STREAM_FORMAT — 구조화 스트림(JSONL) 데이터 계약 v1

엔진 진실의 기계 판본. 한 실행(run) = `state/stream.jsonl` 한 파일.
엔진 → 스트림 → **[맵뷰어 | 기계 크로니클 | GM(옵션·LLM) | 웹뷰어]** — 모든 소비자는 형제다.
GM(LLM 내레이터)도 이 진실의 한 소비자일 뿐, 스트림은 LLM 0콜로 만들어진다.

## 파일 규칙
- 위치: `state/stream.jsonl`. **실행 시작 때 truncate**(이전 판 기록은 사라진다 — 보존하려면 실행 후 복사).
- **단일 writer 가정**: 러너를 동시에 2개 띄우면 같은 파일을 서로 덮어써 계약이 깨진다(락 없음 — 로컬 관전 도구).
- 인코딩: UTF-8, `ensure_ascii=False`(한글 그대로), compact separators, 라인 종결 = `\n` 고정.
- 라인 = JSON 객체 1개, 공통 필드 **`kind`**(항상 첫 키). 라인마다 flush.
- **tail 소비 규칙**: `tail -F state/stream.jsonl` 라이브 구독 가능. 마지막 라인은 쓰다 만
  불완전 JSON일 수 있다 — 개행으로 끝나지 않은 라인은 완성될 때까지 무시하라.
  크래시가 나도 파일은 항상 '유효한 prefix'다.
- **버저닝: additive 만.** 필드 삭제·의미 변경 금지. 소비자는 **모르는 필드·모르는 kind 를
  조용히 무시**해야 한다(미래 확장 여지 — 던전 외 활동·마을 등이 새 kind 로 올 수 있다).
- ⚠️ 스트림은 **관전자 등급 진실**이다: 숨은 함정(hidden)·매복몹(concealed)·숨은 보물까지 다
  들어 있다(극적 아이러니의 원천). 봇에게 이 파일을 보여주면 시야-온리 계약이 깨진다.
  플레이어향 뷰를 만들 소비자는 스스로 필터링할 것.

## 라인 종류(kind) 5종 (+마을 판 한정 `ascend` — 2026-07-30 D29 additive)

### `run_meta` — 첫 라인, 실행당 1회
| 필드 | 내용 |
|---|---|
| `v` | 스키마 버전(현재 1) |
| `started` | 시작 시각 `YYYY-MM-DDTHH:MM:SS` — **파일에서 유일한 비결정 필드**(결정론 비교 시 이것만 빼면 라인 단위 동일) |
| `seed` | 마스터 시드(`DUNGEON_SEED`) |
| `w` `h` | 맵 크기 |
| `depths` | 총 층수 |
| `monsters` `traps` `lurkers` | 1층 기준 배치 수(몬스터는 층당 +1) |
| `potions` | 층당 회복 물약 배치 수(`DUNGEON_POTIONS`, 러너 기본 1 — 2026-07-17 additive. 엔진 직생성 기본 0) |
| `gear` | 층당 장비 배치 수(`DUNGEON_GEAR`, 러너 기본 3 — 2026-07-30 additive. 엔진 직생성 기본 0. 순환: 단검·가죽 갑옷·장검·사슬 갑옷) |
| `town` | 마을 판 여부(`DUNGEON_TOWN` — 2026-07-30 D29 additive). true 면 판 모양 자체가 다르다: depth 0=마을(손그림·전체 시야·NPC·몹 0), 왕복 전이(`ascend` 라인), DEPTHS 기본 1, 최심층 하강=관측 클리어(outcome 은 기존 escaped 유지) |
| `max_turns` | 틱 한도 (0이면 퇴화: tick 0개·end.turn=0) |
| `gm` | GM(LLM 내레이터) 사용 여부(bool) — 이 필드 자체를 제외하면 스트림 내용에 영향 없음(GM은 tick emit 뒤에 도는 소비자, 엔진·RNG 무접촉) |
| `stream_obs` | decisions 에 obs 동봉 여부(bool, `DUNGEON_STREAM_OBS=1`) — tick 스키마 판별용 |
| `menu` | 리모컨 모드 여부(bool, `DUNGEON_MENU`, 기본 true) — true 면 두뇌가 obs `options`(엔진 열거 유효 행동)에서 번호를 골랐고 decisions 에 `choice` 가 실릴 수 있다. gm 과 같은 실행모드 메타: **이 필드 자체를 제외하면 스트림 내용에 영향 없음**(리플레이는 type/target 만 쓴다). 라인 단위 리플레이 비교는 started·gm·menu 를 빼고 하거나 같은 env 로 돌릴 것 |
| `party[]` | 스폰된 파티의 시트: `char job sex maxhp str dex wdmg stealth search_r persona` (HEROES 하드코딩이 아니라 실제 스폰 봇에서 파생 — 시트 외부화(Part B)와 무관하게 유효). `name?` = 시트에 이름이 있으면 동봉(2026-07-05 additive — 보고서·웹의 호칭. 구판 스트림엔 없음: 소비자는 job 폴백) · `speech? goal? background? traits?` = 2026-09-05 D31 additive — 커스텀 시트 원문(성격 문장·말투·목표·배경 자유입력의 정제본)과 성격 키워드 원본(list), **있을 때만** |
| `status` | (2026-09-06 D34 additive) 상태 태그 여부(bool, `DUNGEON_STATUS` 러너 기본 1·엔진 기본 0). true 면 몹·함정의 특수가 태그를 붙인다 — 가시 함정→출혈(BLEED_STEPS=3 걸음마다 HP 1, 걸음 결과에 `bleed{hp,down?,grave?}`), 그림자거미 명중→둔화(SLOW_EVERY=2 틱에 한 칸 — 제자리 틱 `walking`+`slowed:true`, to 없음), 독침 함정·상자 독침·오염된 샘→중독(명중 mod·회피 ac −2 — 기존 mod/ac 필드에 그대로 반영). 원천 이벤트(walk.trap / interact chest_trap·fountain_harm / monster_attack)에 `status` 병기, 봇 스냅샷 `status[]`(있을 때만), witnessed `ally_status{char,tag,by,by_kind?}`. 지우기는 휴식(D35)뿐. **몸 물리(걸음·굴림)를 바꾸므로 리플레이·판 비교의 전제** |
| `rest` | (2026-09-06 D35 additive) 휴식 동사 여부(bool, `DUNGEON_REST` 러너 기본 1·엔진 기본 0). true 면 메뉴에 '쉰다'(다쳤거나 상태 태그가 있을 때만), 결정 `type:rest`(result resting) 뒤 walk 결과에 `resting(hp)`/`rested(ticks,healed,cleared[])`/`rest_met(allies[])`, 새 몹이면 `encounter`+`woke:'rest'`. 틱마다 HP +1, 만피&&5틱에 완료 → 상태 태그 소거. 동료 항목(obs sights.bots[])에 `resting:true`. 메뉴·회복 물리 메타(wait 와 같은 급) |
| `relations` | (2026-09-06 D36 additive) 관계 장부 여부(bool, `DUNGEON_RELATIONS` 러너 기본 1·엔진 기본 0). true 면 뼈 5종(talk/fought/waited/rescued/at_death)이 봇 장부에 쌓이고 봇 스냅샷에 `relations{other:{kind:n}}`(뼈 있을 때만·횟수만), obs 에 `relations[]`(뼈 횟수·살·초대 — 결정당 초대 1개), decisions 에 `relation{to,line}`(살 한 줄 — 초대 받은 결정만, ≤80자, 엔진 불가침). 시트 relationships 문장=살의 초기값. obs 를 바꾸므로 리플레이·A/B 의 전제(bestiary 와 같은 급). 솔로 판은 미노출 |
| `bestiary` | **판 시작 시점**의 캐릭터별 도감 `{이름: [종키…]}`(2026-07-05 additive — D9 도감). 도감은 obs(`monsters[].kind` 가 미등재면 `낯선 짐승`, 등재면 원명+`lore`)를 바꿔 LLM 결정에 영향을 주므로, **같은 시드라도 시작 도감이 다르면 다른 판**이다 — 리플레이·A/B 비교는 이 필드까지 맞춰야 한다. 획득 규칙=bestiary.py(스트림 소비자). 오프라인 소급(bestiary.replay/CLI)은 **이 필드를 시작 지식으로 시드**한 뒤 증분을 재생한다 — 그래야 이월 판에서도 '같은 스트림→같은 원장'(순수 투영)이 성립 |
| `bestiary_file` | 도감 원장 영속 여부(bool, `DUNGEON_BESTIARY_FILE`) — gm/menu 와 같은 실행모드 메타(스트림 내용엔 위 `bestiary` 초기값을 통해서만 영향) |
| `ledger` | 공간 장부(D17-1) 여부(bool, `DUNGEON_LEDGER`, 기본 true — 2026-07-11 additive). true 면 obs 에 `known`(장부 투영: statics/last_seen/zones — **좌표 없음**, 구역·목격 turn 만)과 '돌아가기' 옵션이 실려 LLM 결정에 영향 — bestiary 처럼 **리플레이·A/B 는 이 필드까지 맞춰야 한다**. 장부 자체는 봇 스냅샷 화이트리스트 밖(직전 틱들의 스냅샷·시야에서 파생 가능 = 새 원천 없음). 층 전이 때 새 원장(층의 기억) |
| `sight` | 시야 반경(`DUNGEON_SIGHT`, 엔진·게이트 기본 5 — 2026-07-11 additive, 구판 스트림은 3. **데모 경로(live.bat·launcher.py)는 6** — D33 2026-09-05). 봇 관측·봇 인지·몹 시야·목격이 전부 이 한 자(대칭) — **굴림 수를 바꾸는 세계 물리라 리플레이·판 비교는 seed 처럼 이 값까지 맞춰야 한다** |
| `selfstop` | (2026-07-20 D21 additive) 자기 관찰 정지 여부(bool, `DUNGEON_SELFSTOP` 러너 기본 1·엔진 기본 0). true(+scan)면 walk 에 `reunion`/`wander` 정지가 생기고 obs.zone.doors[] 의 been 문에 `to`(너머 이름)가 실린다 — **정지 물리를 바꾸므로 리플레이·판 비교의 전제**(scan 과 같은 급) |
| `dry_signal` | (2026-07-24 additive) 무발견 신호 여부(bool, `DUNGEON_DRY` 러너 기본 1·엔진 기본 0). true(+scan)면 마지막 새 목격 이후 25걸음(DRY_K) 도달 걸음 이벤트에 `dry`(계측), 그다음 결정 obs 에 `dry` 1회 배달 |
| `hail` | (2026-07-24 D24 additive) 말 걸림 정지 여부(bool, `DUNGEON_HAIL` 러너 기본 1·엔진 기본 0). true 면 inbox 배달이 걷던 봇을 멈춰 다음 틱 결정권을 준다(tick.hails 참조) — **정지 물리를 바꾸므로 리플레이·판 비교의 전제** |
| `wait` | (2026-07-24 D25 additive) wait 동사 여부(bool, `DUNGEON_WAIT` 러너 기본 1·엔진 기본 0). true 면 메뉴에 '기다린다', walk 결과에 waiting/wait_met(동료 시야 진입)/wait_bored(WAIT_MAX=15틱) — 정지 물리 메타 |
| `notes` | (2026-07-24 D26 additive) 의미 기억(남길 한 줄) 여부(bool, `DUNGEON_NOTES` 기본 1 — brains 표현층 스위치, 엔진 무관여). true 면 decisions 원본에 `note`(그 결정에서 남긴 한 줄, ≤80자, 선택)가 실릴 수 있고 봇은 최근 5줄(NOTE_MAX)을 매 결정 프롬프트에서 재제시받는다. 엔진 판정 불가침 — 캐릭터 주관(틀린 기억=그 캐릭터의 착각). obs.notes 는 그 봇의 직전 decisions.note 들에서 파생 가능=새 원천 없음 |
| `motion` | (2026-07-24 D27 additive) 이동중 표시 여부(bool, `DUNGEON_MOTION` 러너 기본 1·엔진 기본 0). true 면 obs 의 보이는 동료 항목(sights.bots[])에 걷는 중일 때만 `moving: true` 깃발 — 방향·목적지·경로는 비노출(마음이 아니라 몸짓만). 봇 위치 스냅샷에서 파생 가능=새 원천 없음 |
| `graves` | (2026-07-20 D22 additive) 묘 여부(bool, `DUNGEON_GRAVES` 러너 기본 1·엔진 기본 0). true면 봇 사망 이벤트에 `grave={id,name,x,y}` 가 병기되고 그 칸에 '~의 묘' 피처(글리프 `T`)가 생긴다 — 피처 셋을 바꾸는 세계 물리 메타 |
| `events` | (2026-07-20 D22 additive) 사건층 여부(bool, `DUNGEON_EVENTS` 러너 기본 1·엔진 기본 0). true면 obs 에 목격 어휘가 늘고(witnessed: ally_hit/kill/trap/heal + ally_loot/spot/mishap(07-29 — 상자 결과는 D30 확장으로 ally_use 이관) + ally_use{what,id,result?}(D30 09-05: 문 타일 밟기 · 계단 하강/상행·마을 입구(남는 사람만 본다) · 상자{result=보물을 꺼냈다/독침에 당했다}) + 비몬스터 ally_down) 목격한 전사가 memories(fallen, 휘발 0)로 재제시된다 — obs 를 바꾸는 실행모드 메타(스트림 이벤트 자체는 불변, `grave` 병기 제외) |
| `scan` | 스캐너(D19) 여부(bool, `DUNGEON_SCAN`, 기본 false — 2026-07-12 additive, 암 B 판정 전 실험 스위치). true 면 ①**격자에 문 타일 `+` 가 실재**(2026-07-15 정정 — 생성기가 방↔통로 관통점에 스탬프. 벽처럼 빛을 막고 바닥처럼 지나간다, 개폐 상태 없음) ②obs.zone 이 구조 조회로 확장(`{id,kind, checked{full,todo?}, doors[], size/at(다 본 방만), len(다 본 통로만)/ends(본 것만)}` — 전부 방위·거리·딱지뿐, **좌표 없음**. **시야·기억 제한**(2026-07-15 정정 "스캐너=시야에 들어온 격자의 번역기"): 문은 눈에 든 적 있는 것만 실리고, 크기·상대위치는 그 공간을 다 봤을 때만. 문턱(문 타일) 위=`kind:'문턱'`. id 는 기하 구역 `r<n>`/`c<n>` — level.rooms 와 조인 금지. **계단은 구조에 없다** — 내용물이라 광학(sights.exit)으로만) ③`sights.traps[]`(드러난 함정 시야 어휘) ④문 id(`d<n>`)가 goto 핑·옵션에 등장 ⑤**걸음 정지 물리가 달라진다**(walk `sighted` — 아래. `entered` 는 2026-07-15 폐지) ⑥장부 주소도 기하 구역 명의. 리플레이·판 비교는 이 필드까지 맞춰야 한다(ledger 와 같은 급) |
| `obs_ascii` / `obs_pos` | wire 직렬화 스위치(D17-4, 2026-07-11 additive — `DUNGEON_OBS_ASCII` 기본 0·`DUNGEON_OBS_POS` 기본 1). **obs dict 는 불변**(ascii_view·pos 는 스트림에 그대로) — LLM 프롬프트 표현에서 뺐는지의 실행모드 메타. 프롬프트 재현·프로브 비교 시 이 필드까지 맞춰야 한다 |
| `ally_sight` | (2026-07-26 additive) 동료 시야 면제 여부(bool, `DUNGEON_ALLY_SIGHT`, **러너 기본 1(D33 2026-09-05 승격 — 파트너 확정 '절대시야 범위는 일반시야와 같이')·엔진 기본 0**). true 면 **동료만** 시야 반경 안에서 장애물(벽·문)을 무시하고 보인다 — `sights.bots`·`party.visible`·follow 재경로가 같은 판정을 쓴다. 몹·피처·구조는 LOS 그대로(D19 문 광학·매복·인식 매트릭스 대칭 무손상), 반경 밖은 여전히 안 보인다. **시야 물리 메타**(scan 과 같은 급) — 켠 판은 obs·결정이 근본적으로 달라지므로 리플레이·판 대조의 전제. 근거: 07-26 부검에서 파티가 서로 못 보는 시간 44%, 그 다수가 거리 2칸, 문 낀 이동의 단절률 28% vs 그 외 2% |
| `solo` | (2026-07-29 additive) 솔로 판 여부(bool, `DUNGEON_SOLO`, 러너·엔진 **둘 다 기본 0**). true 면 **파티라는 전제가 빠진 판**이다 — ① 배치: 셋이 `SOLO_APART` 이상 흩어져 출발(`spawn(apart=True)`) ② obs: `party` 명단이 **빈 배열**이라 안 보이는 사람은 핑 불가(D18 '파티 감각' 무효. 보이는 사람은 `sights.bots` 로 여전히 핑 가능) ③ 승리 조건: `EXIT_GATHER` 면제 — 각자 계단에 닿으면 혼자 `interact exit`→`result:'exit'`, 이때 `party` 는 **자기 하나뿐인 배열**(파티 판은 모인 전원). 판은 전원 won/사망까지 계속된다. **판의 종류가 다른 메타** — 배치·obs·승리 조건이 전부 달라 파티 판과는 애초에 비교 대상이 아니다(대조군 고를 때 필수 확인 필드). 프롬프트 층에선 로스터가 비어 시트의 `- 동료:` 줄이 사라지고 시야에 든 사람이 `낯선 사람(봇N)` 으로 렌더된다(도감 '낯선 짐승' 문법) — 표현층이라 스트림 스키마엔 영향 없음. 통상 `DUNGEON_PARTY_FILE=party_solo.json`(= party.json − relationships)과 함께 쓴다. ⚠️ 캐릭터 간 공격은 아직 엔진에 없다(`_attack` 은 몹만 해소) — '마주치면 자유'의 범위에서 이것만 빠져 있다 |
| `backend` | (2026-07-25 additive) 두뇌 백엔드(문자열, `DUNGEON_BRAIN_BACKEND` 기본 `claude_cli`). `claude_cli`(claude.exe 서브프로세스·구독 과금 0) / `anthropic_api`(Messages API·종량) / `gemini_api` / `dummy`(콜 0 — 규칙두뇌 즉시 폴백). gm·menu 와 같은 급의 실행모드 메타: 같은 시드라도 모델 접점이 다르면 다른 판이므로 A/B 비교는 이 필드까지 맞춰야 한다. **스트림 스키마에 다른 영향 없음** — `decisions.src` 는 여전히 `haiku`/`fallback`/`plan` 이다(백엔드 이름은 절대 src 에 싣지 않는다: viewer·report·verify 다수가 그 세 어휘를 문자열로 매칭한다). 지연·토큰·요청 id 도 여기 없다 — 실행마다 변하는 값은 run_meta 결정론(라인 바이트 동일)을 깬다. 콜별 지연 계측이 필요하면 `DUNGEON_BRAIN_LOG=<경로>` 사이드카(스트림 밖) |

### `level` — 층(depth) 진입마다 (첫 층 포함. `descend` 직후엔 반드시 이 라인)
| 필드 | 내용 |
|---|---|
| `turn` | 이 층에 들어선 틱(첫 층=0) |
| `depth` `w` `h` | 층 번호·크기 |
| `master_seed` `level_seed` | 마스터 시드와 층별 파생 시드 |
| `grid[]` | h개의 w폭 문자열, **raw 지형만**: `#`(벽) `.`(바닥) `+`(문 타일 — D19 정정 2, 2026-07-15 SCAN 기본 1 승격부터 생성 층에 등장. 벽처럼 빛을 막고 바닥처럼 지나감). tile() 관전 글리프 아님 — 몹·피처·함정은 아래 배열로 별도(겹쳐 그리기는 소비자 몫). 웹이 엔진 없이 렌더 가능 |
| `exit` | `[x,y]` 계단 좌표 |
| `rooms[]` | 방 전수: `id x y w h type neighbours[]` (type ∈ entrance/exit/standard) — `feature.room_id` 의 해소처 |
| `features[]` | Feature 전수: `id type name x y room_id concealed perception_gate` (type ∈ exit/treasure/chest/fountain) |
| `traps[]` | Trap 전수: `x y kind name dc dmg hidden sprung` (kind ∈ spike/dart/alarm) |
| `monsters[]` | Monster 전수(아래 몹 스냅샷 스키마) |
| `party[]` | 봇 스냅샷(아래) — 강하 이월 hp/bag 포함한 이 층 개시 상태 |

### `tick` — 루프 반복마다(빈 틱 포함). **turn 은 1부터 연속** (불변식)
| 필드 | 내용 |
|---|---|
| `turn` | 틱 번호 |
| `inbox` | 이번 틱 **사고에 주입된** 받은편지함 `{char: [{from,text},…]}` — 현재 파티 전원이 키(빈 리스트 포함). 지난 틱 say 중 시야/근접 조건을 통과해 배달된 것. **층 전이(descend) 틱의 say 는 배달되지 않는다**(새 층에서 리셋) |
| `hails` | (2026-07-24 D24 additive, `run_meta.hail=true` 판만) 말 걸림 정지 성사 `{char: [from,…]}` — 방금 inbox 가 배달된 '걷던' 봇이 멈춰 다음 틱 결정권을 받은 기록(그 봇의 다음 obs.last=`{type:hail, froms}`). 같은 발화자 쿨다운(HAIL_CD=3턴, 쌍 단위)에 막히면 정지 없음 — 메시지는 그대로 배달. 성사 없는 틱엔 키 자체가 없다 |
| `decisions` | 이번 틱 재결정한 봇들의 **결정 원본** `{char: {type, target?, choice?, then?, say, reason, src, skipped?}}`. src ∈ haiku/fallback/**plan**. 자동보행 중인 봇은 키 없음(LLM 0콜). `choice` = 리모컨 모드(run_meta.menu)에서 고른 옵션 번호 — 표시/분석용이며 판정·리플레이는 type/target 만 쓴다. `skipped:true` = 접수됐지만 **미실행**(같은 틱 동료의 exit 하강이 이 봇의 won 을 선점 — say 도 발화 안 됨). **`then`(작정, 2026-07-10 D16 additive)** = 이 결정에 딸린 이어질 행동 최대 2수 `[{type, target?},…]` — 엔진이 봇에 계획으로 보관했다가 order 완결마다 한 수씩 집행한다. 집행된 수는 **별도 decisions 항목(src='plan', reason='[작정] …', say='')** 으로 기록된다(LLM 0콜·view() 미호출 — obs 미동봉). 인터럽트(피격·encounter·blocked·lost·no_path)가 남은 작정을 파기하며, 착수 재검증 실패(대상 소멸·인접 아님)는 이벤트가 아니라 그 봇의 다음 obs.last(`type:'plan_broken'`, why)로만 보고된다. `DUNGEON_STREAM_OBS=1`이면 각 결정에 `obs`(그 봇이 그 순간 본 것 — `options` 리모컨 열거 포함) 동봉 — **시드+decisions = 완전 리플레이의 마지막 조각**. ⚠️ obs 는 엔진 view() 원본이라 menu=false 실행에서도 `options` 가 실린다(그 판의 LLM 프롬프트에서는 brains 가 제거해 비노출 — 스트림 obs ≠ 프롬프트 원문). obs 에는 `last`(그 봇 직전 행동/피격 결과 — D1 개정 additive)와 `intent`(그 봇의 **직전 결정** `{type, target?, say?, reason?, src?}` — 판단 되먹임, 2026-07-05 D15① additive. brains.think_all 이 inbox 처럼 주입하는 자기 기억이라 **그 캐릭터의 직전 decisions 항목에서 파생 가능** = 스트림에 새 원천 없음. 층 전이 시 재스폰으로 리셋)도 실릴 수 있다. `witnessed[]`(2026-07-11 D18 A-3 additive) = 그 봇이 **눈으로 본 동료 사건** `{kind: ally_hurt/ally_down, char, name, by, by_id}` — 사건 칸이 관측자 시야 내일 때만 쌓이고 다음 view() 한 번에 노출·소거(1회성 — D22 명명: 휘발=다음 결정 1회). 종 표기 `by` 는 관측자 도감 기준(모르는 종=낯선 짐승). D22(2026-07-20, `DUNGEON_EVENTS` 판만) 어휘 확장: `ally_hit/ally_kill {char,mon,crit?}`(동료의 명중·처치), `ally_trap {char,trap,safe,dmg?}`(함정 장면), `ally_heal {char,how}`(샘·물약 회복), 비몬스터 사인 ally_down 은 `by_kind`(trap/hazard) 병기 — 도감 게이트 면제 표식. 07-29 확장(같은 스위치): `ally_loot {char,what=보물/물약/상자/장비 이름(단검 등 — 2026-07-30 D28)}`(획득 — 오브젝트가 눈앞에서 사라진 이유), `ally_spot {char,what|mon}`(발견 — 숨은 함정·매복·보물이 드러남. 판정 칸=**드러난 물건의 자리**, 몹은 `mon` 필드=도감 게이트 경유), `ally_mishap {char,what=상자 독침/오염된 샘,dmg}`(비몬스터 피해 — 전사면 ally_down 소관). 원칙: 변화가 일어난 칸이 시야에 들면 이유도 안다. `memories[]`(D22 기억층, events 판만) = 목격한 전사의 지속 기억 `{kind:fallen, char, name, by, by_kind?, zone, turn}` — **휘발 0**: 매 결정 재제시(비우지 않음), 좌표 없이 구역 이름만. 같은 틱 사망 이벤트에서 파생 가능 = 새 원천 없음. **2026-09-06 D22 개정**: `{kind:grave_found, char, name, grave, zone, turn}` = 죽음을 못 본 봇이 묘를 본 순간의 지속 기억(1회, 목격자 무중복) — 묘 피처 스냅샷+시야에서 파생 가능. 2026-09-06 D34 `ally_status{char,tag,by,by_kind?}`(동료에게 상태 태그가 붙는 장면). 2026-09-06 D30 확장 2차 `mon_use{mon,id,what:'문',door}`(몹이 문 타일을 밟는 순간 — 그 칸을 본 봇에게, 문턱은 양쪽에서 보이므로 나가는 몹·들어오는 몹 모두. 같은 틱 `monster_move.door` 에서 파생 가능. 매복 몹 제외). `relation`(2026-09-06 D36 additive, `run_meta.relations` 판만) = 결정 원본의 선택 필드 `{to, line}` — 초대 받은 결정에서 캐릭터가 남긴 관계 한 줄(≤80자, 엔진 불가침·brains 가 봇 장부에 겹쳐쓰기. 옛 줄은 여기에만 남는다). obs 의 `status[]`(자기 몸 태그 `{tag,n,by,since}`)·`relations[]`(`{char,name,bones[{kind,label,n,last}],line,line_turn,line_src,invite?}` — invite 는 결정당 하나)도 실릴 수 있다. 둘 다 봇 스냅샷(bots[]) 화이트리스트 밖. `zone`·`known`·`sights.ways[].zone`(2026-07-11 D17 additive, **run_meta.ledger=true 판만** — 끈 판의 obs 는 구판과 동일): `zone` = 그 봇이 선 구역 `{id: "r<n>"/null, kind: 방/통로}`(level.rooms 의 id 와 조인 가능), `known` = 공간 장부 투영 `{statics[], last_seen[], zones[]}` — 그 봇이 이 층에서 본 것의 기억(**좌표 없음** — 구역 라벨·목격 turn 만. 시야 밖 기억이라 sights 와 분리), ways 의 `zone` = 그 출입구가 어느 구역으로 트였나, `turn` = 그 시점의 턴 번호(2026-07-11 D17-3 additive — wire 직렬화가 장부 스탬프로 "N턴 전"을 셈. 역시 ledger 판만). 전부 직전 틱들의 스냅샷·시야에서 파생 가능 = 새 원천 없음 |
| `events[]` | 이 틱에 실제 일어난 일 전부, **순서 보존**(봇 행동 → 몬스터 턴). 아래 이벤트 어휘. 재결정 봇 행동엔 `reason`(속내)·`job` 부착, 자동보행 walk 엔 `reason` 없음 |
| `bots[]` `monsters[]` `features[]` `traps[]` | 이 틱 **종료 시점 전체 스냅샷(델타 아님)** — 임의 틱 시킹 가능. `visited`(발자국)만 제외: 파생 규칙 "각 level 의 party 좌표(스폰 칸) + 이후 각 tick 의 봇 좌표 누적" |

### `descend` — 층 전이(전원 won) 때. 직후 라인은 반드시 `level`
### `ascend` — 마을 판(D29) 상행 전이(전원 won·went=up) 때. 직후 라인은 반드시 `level`
필드는 `descend` 와 동일(`to_depth`=올라가는 층 — 마을이면 0). 마을 판의 `level` 은 같은 depth 가
여러 번 나올 수 있다(재입장 — **같은 층 보존**: level_seed·격자 동일, 세계 상태는 떠날 때 그대로).

| 필드 | 내용 |
|---|---|
| `turn` | 전이가 일어난 틱 |
| `to_depth` | 내려가는 층 번호 |
| `party[]` | 생존 이월자 `{char, hp, bag, potions}` (char 순 정렬. potions=2026-07-17 additive — 물약도 들고 내려간다. 장비는 여기 없음 — 이월 상태는 다음 level.party/tick.bots 의 weapon/armor 로 확인) |
| `fallen[]` | 지금까지 쓰러진 char 누적 |

### `end` — 마지막 라인, 실행당 1회
| 필드 | 내용 |
|---|---|
| `turn` | 종료 틱 |
| `outcome` | `escaped`(최심층 돌파·탈출) / `wiped`(전멸) / `timeout`(틱 한도) — 러너 종료 3분기와 1:1 |
| `depth` | 종료 시 층 |
| `survivors[]` `fallen[]` `remaining[]` | 탈출/사망/(timeout 시)던전 잔류 char 목록 — 셋이 전체 파티의 분할 |
| `bots[]` | **최종 층 파티만**의 스냅샷 — 이전 층 전사자의 마지막 모습은 그 층 마지막 `tick` 에서 찾을 것(fallen 명단에는 있음) |

## 스냅샷 스키마

- **봇**: `char job sex x y hp maxhp bag potions weapon armor alive won order aware_of[]`
  (`potions`=소지 회복 물약 병 수 — 2026-07-17 additive. `weapon`/`armor`=착용 장비 `{name, bonus}` 또는 null — 2026-07-30 D28 additive.
  `status[]`=붙은 상태 태그 이름 정렬 리스트, **있을 때만** — 2026-09-06 D34 additive. `relations{other:{kind:n}}`=관계 뼈 횟수(살은 안 나간다 — decisions.relation), **뼈가 있을 때만** — 2026-09-06 D36 additive)
  — `order` = 진행 중 핑(raw: `exit`/`f<n>`/`m<n>`/`b<char>`/`@x,y`(explore 목표칸), 없으면 null).
  스트림은 관전자 데이터라 obs 와 달리 생좌표를 가리지 않는다. `aware_of` = 인지한 몹 id 정렬 리스트.
  `path`(자동보행 잔여 경로)는 제외 — 핑 시점 BFS 고정이라 order+현재 스냅샷으로 재유도가
  일반적으로 안 된다(정확 복원 = 시드+decisions 리플레이. order 는 목표 표시용).
- **몹**: `id kind x y hp maxhp ac atk dmg alive state concealed target desperate`
  — state ∈ SLEEPING/WANDERING/HUNTING/FLEEING. AI 내부 장부(last_seen/lost/skip_turns/waking/flee_turns)는
  비공개 — 복원은 스냅샷이 아니라 시드+decisions 리플레이로 한다.
  ⚠️ **사망 몹의 스냅샷 hp 는 음수일 수 있다**(raw) — 원장 재계산은 이벤트의 `dmg` 를 쓰고,
  attack 이벤트의 `monster_hp`(0 클램프)는 표시용이다.
- **함정**: `x y kind name dc dmg hidden sprung`
- **피처**: `id type name x y room_id concealed perception_gate`

## 이벤트 어휘 전수 (`tick.events[]`)

봇 행동 이벤트는 공통으로 `char`(행위자)·`type`을 갖고, 러너가 `job`(전사/도적)과
재결정 틱엔 `reason`(속내)을 붙인다. 몹 이벤트는 `id`(`m<n>`)·`monster`(종류)를 갖는다.

| type | 필드 | 의미 |
|---|---|---|
| `goto` | `target`, `result=pathed(len)/arrived/blocked(allies[])` | 핑 → 자동보행 개시(pathed) / 이미 곁(arrived). 무효·도달불가 핑은 엔진이 explore 로 폴백하므로 **goto 의 no_path 는 나가지 않는다**(type 자체가 explore 로 바뀜). `blocked`(2026-07-11 D18 additive) = 동료가 길목을 점유해 경로가 대우회로 폭증(사회적 봉쇄) — 말없이 행군하지 않고 멈춰 보고, `allies[]` 에 막는 동료 명단. scan 판(D19)은 target 에 문 id(`d<n>`)도 온다 — 문 핑의 도착 칸은 **문 너머 쪽**(지나 들어서기). exit 핑은 scan 판에서도 '보일 때만'(계단=내용물, 2026-07-12 정정) |
| `explore` | `target`(방위 or `auto`), `result=pathed(len, bearing?, to_exit?, remembered?, door?)/no_path(exhausted?)` | 탐색: 시야 내 미지의 문으로(pathed+bearing). **D19 개정(2026-09-06)**: 더 볼 곳 없으면 ①**계단을 본 적 있을 때만** 기억의 계단 행군(pathed+to_exit+`remembered:true`) ②아니면 기억 속 '너머를 안 가 본 문'의 건너편으로(pathed+`door:'d<n>'`) ③그것도 없으면 기억 속 '안 본 가장자리'(본 바닥 칸 중 이웃에 못 본 칸이 있는 곳)로(pathed+`frontier:true`) ④전부 없으면 no_path+`exhausted:true`(obs 에도 `exhausted`, '탐색' 어휘 미노출). 구판의 '안 본 계단 행군'(to_exit 만, remembered 없음)은 scan 없는 판(평생 시야 장부 없음 — 러너는 scan 기본 1)에만 남는다 |
| `follow` | `target`(`b<char>`), `result=pathed(len)/following/blocked(allies[])` | 동행 개시(2026-07-11 D18 A-5 additive) — 동료 곁(체비셰프≤1)을 따라 걷는 **지속 order**(`follow:b<char>`, 도착 개념 없음·작정(then) 못 이음). pathed=곁으로 출발 / following=이미 곁(대기 시작) / blocked=동료發 대우회 보고. 무효·도달불가 대상은 goto 처럼 explore 폴백(type 이 바뀜) |
| `walk` | `target`(order), `to?=[x,y]`, `result=walking/arrived/lost/treasure/at_exit/blocked/encounter/following/idle/reunion/wander/waiting/wait_met/wait_bored/resting/rested/rest_met` | 자동보행 한 걸음. `following`(2026-07-11 D18 A-5 additive) = 동행 order(`follow:b<char>`)의 한 틱 — 곁이면 제자리(to 없음), 따라 걸었으면 to 있음; order 는 계속된다. 동행 대상 사망/하강/유령 좌표 허탕 = `lost`(기존 의미론 상속). `idle`(2026-07-11 additive, FOLLOW_IDLE=3) = 곁 대기 중 대상이 3틱 연속 제자리 → 동행 종료·재결정("아무도 안 걸으면 동행이 아니다" — 상호 동행 삼각 고착(fellowsmoke 실측)의 흡수 상태 제거). `to` 는 **실제로 이동한 틱에만** 있다 — blocked·경로 소진 arrived/lost(이동 없이 소진)·움직이는 목표(몹·동료) 곁 도달 arrived(target 만 있음) 엔 없다(마지막 한 걸음과 함께 소진되면 lost 에도 `to` 가 있다). `lost` = 움직이는 목표(`m<n>`/`b<char>`) 또는 소모성 피처(`f<n>` — 동료가 먼저 소비) 핑의 경로 소진 지점에 도착했으나 **대상이 그 자리에 없음**(이동·사망·하강·소비 — 2026-07-05 additive, 유령 좌표 보고 정직화. 구판 스트림은 이 경우를 arrived 로 기록. 의미는 '직교 곁에 없다'까지 — 대각 1칸 비껴섬 포함). `treasure` 는 그 칸이 order 목표(=path 소진)였다면 **그 자리에서 order 완결**(후속 arrived/lost 라인 없음 — 자기 소비와 동료 소비의 구분). treasure=길에서 보물 줍고 계속. at_exit=계단 앞 정지. **encounter = *새 정보*로 인한 보행 정지**(D1 개정 2026-07-04: 처음 보는 몹·함정·발견만 — 이미 알던 몹의 인접·지속으로는 멈추지 않는다. 구 pre_adj/adj_mon encounter 는 더 안 나간다). `blocked` 에 `monsters[]` 가 붙으면 보이는 몹이 다음 칸을 점거해 멈춰 보고한 것(경로 경합). 서브필드: |
| | ↳ ~~`entered`~~ | (2026-07-12 D19 additive → **2026-07-15 폐지**) '처음 방 무조건 정지'가 정지 신호 개정("새 오브젝트 목격 시")으로 대체되며 이벤트도 소멸. scan 실험층(채택 판정 전)이라 additive 원칙 내 삭제 — 07-12 실험 로그(runs/maze-d19-*)에만 남아 있다 |
| | ↳ `seen[]` | (2026-07-12 D19 additive, scan 판만. **2026-07-15 확장**) `result=sighted` — 걷는 중(**order 종류 무관** — goto·explore·follow) **새 오브젝트**(피처·계단·드러난 함정·**문**)가 시야에 들어 정지 `{kind,name,id?}` (문은 `{kind:'door',name:'문',id:'d<n>'}`). 기준=봇 평생 목격 장부(seen_keys) — 결정 시점에 보이던 것으로는 멈추지 않는다(에지 트리거). 정지 시 작정 파기(인카운터 동급) |
| | ↳ `monsters[]` | 마주친(encounter) / 길목 점거(blocked) 적 `{id,kind,state}` |
| | ↳ `allies[]` | 길목 점거(blocked) 동료 `{char,name}` — 재경로가 동료發 대우회일 때(2026-07-11 D18 additive. goto blocked 와 동형) |
| | ↳ `trap` | 함정 `{kind,name,roll,mod,total,dc,safe, dmg?,hp?,down?, alarm?}` — alarm=경보 함정이 깨운 몹 수 |
| | ↳ `treasure` | true — 같은 걸음에 보물도 주움 |
| | ↳ `potion` | true — 같은 걸음에 회복 물약도 주움(2026-07-17 additive — 보물 줍기 문법. `result:'potion'`=물약 칸이 order 목표여서 그 자리 완결) |
| | ↳ `found[]` | 걸으며 인지한 숨은 것 `{kind,name,bearing,id?}` |
| | ↳ `swap` | (2026-07-17 D18 개정 additive) `{char,name}` — 동료 칸으로 걸어 들어가 **서로 자리를 바꿈**(PD 교대 문법. path_to 가 동료를 통과 가능으로 계산, 실행 걸음에서 맞바꿈). 밀려난 쪽은 이벤트를 안 만들고 좌표 스냅샷+자기 last(`result:'swapped'`, `with`=민 쪽 이름)로만 남는다. 그 틱의 어떤 walk result 에도 병기될 수 있다 |
| | ↳ `paced` | (2026-07-17 D18 개정 additive) 동료 char — 같은 방향으로 행군 중인 동료에게 **한 박자 양보**(제자리, `to` 없음, `result:'walking'`). 맞교대 셔틀(밀린 쪽이 되밀어 무한 왕복 — 50시드 10판 비종결 실측)의 치료. 같은 상황이 두 틱 이어지면 교대 강행(끼인 동료 추월 보장) |
| | ↳ `name` | (2026-07-20 D21① additive, `DUNGEON_SELFSTOP` scan 판만) `result=reunion` — **아는 구역에 새 연결(무방향 구역쌍 에지 최초 통과)로 들어서 정지**("낯익은 곳이다"). name=그 봇의 기억으로 부른 사람말 이름(내용물 우선 "샘 있던 방", 없으면 크기, 좌표·번호 없음 — 봇마다 다를 수 있다: 장부가 다르니까). 같은 문 왕복은 첫 통과 때 에지가 적혀 재발화 없음(재방문 과제약 금지). 정지=재결정·작정 파기. treasure/potion 병기 가능 |
| | ↳ `steps` | (2026-07-20 D21② additive, `DUNGEON_SELFSTOP` scan 판만) `result=wander` — **결정 없이 걸음만 이었는데(≥WANDER_N=10) 새로 본 칸 0 + 밟았던 칸 되밟기** → 정지+관찰 보고(질문·조향 금지 — 판단은 두뇌 몫). steps=그 걸음 수. 직행 관통(출구 귀환·장부 goto)은 되밟기가 없어 안 울린다. 새 목격·새 결정(act)이 창을 접는다. 3인 회전 셔틀(07-20 큰 판, 결정 0 ~50틱 회전) 류의 그물이자 맞물림 계측의 "맴돎 경고" 열 |
| | ↳ `bleed` | (2026-09-06 D34 additive, `run_meta.status` 판만) `{hp, down?, grave?}` — 출혈 봇의 이 걸음이 BLEED_STEPS 번째라 HP 1 이 났다(걸음의 어떤 result 에도 병기). down 이면 `result=encounter` 로 정지(사망 — 묘·목격 문법 그대로) |
| | ↳ `slowed` | (2026-09-06 D34 additive) `true` — 둔화 봇의 제자리 틱(`result=walking`, to 없음). SLOW_EVERY=2 틱에 한 칸 |
| | ↳ `trap.status` | (2026-09-06 D34 additive) 함정의 특수 — 판정 실패·생존 시 붙은 태그 이름(spike=출혈, dart=중독) |
| | ↳ `woke` | (2026-09-06 D35 additive) `'rest'` — 쉬다 새 몹이 시야에 들어 `result=encounter` 로 깬 것(걷다 만난 것과 구분) |
| | ↳ (휴식 결과) | (2026-09-06 D35 additive) `resting{hp}` = 휴식 틱(HP +1) / `rested{ticks, healed, cleared[]}` = 완료(만피&&REST_MIN, 상태 태그 소거·order 파기) / `rest_met{allies[]}` = 쉬다 동료가 시야에 들어 깸(wait_met 문법) |
| `rest` | `result=resting(hp)` | (2026-09-06 D35 additive) 휴식 개시 — order='rest'(이후 틱은 walk 결과로). 꺼진 판(run_meta.rest=false)에선 type 이 wait/explore 로 바뀌어 나간다(폴백) |
| `interact` | `target`, `result=exit(party[])/wait_allies(missing[])/treasure/potion(potions — 2026-07-17 additive)/chest_loot(roll,mod,total,loot)/chest_trap(roll,mod,total,dmg,hp,down?,status? — 2026-09-06 D34: 생존 시 중독)/fountain_heal(roll,heal,hp)/fountain_harm(roll,dmg,hp,down?,status? — 2026-09-06 D34: 생존 시 중독)/equip(item,slot,bonus,dropped? — 2026-07-30 D28 additive)/ascend(party[] — 마을 복귀, D29 additive)/npc_talk(npc,line — 마을 NPC 말 걸기, D29 additive)/npc_gift(npc,item,line — 마을 상점 v0, D32 additive 2026-09-05: 아이템 상인=물약 1/방문·장비 상인=빈손이면 단검, 정해진 대사만. 받는 장면은 동료 witnessed 에 ally_loot)/nothing/too_far/no_target` | 계단(파티 동반 하강/대기)·줍기·상자·샘·물약 집기·장비 착용(스왑 시 dropped=그 자리에 놓은 헌 장비 이름 — 같은 칸에 새 피처로 실린다). exit 의 party=함께 내려간 char 명단 |
| `attack` | `result=attack/no_target/too_far`(**항상 존재**). `attack` 일 때만 `target`(몹 종류)·`target_id`(`m<n>`)·`roll mod total ac hit`·`surprise? crit? dmg? monster_hp? killed?` 존재 — 실패 2종은 `char/type/result` 뿐 | 봇의 공격. **result 로 분기하라.** surprise=우리 기습(we-ambush) |
| `search` | `radius`, `found[]` | 능동 수색(턴 소모, 반경 내 확정 발견). found 빈 배열=허탕 |
| `drink` | `result=drink_heal(heal,hp,potions)/no_potion` | (2026-07-17 additive) 회복 물약 마시기 — 굴림 없는 확정 완전 회복(샘=도박과 대비되는 '들고 다니는 보험'), 한 턴 소모. `potions`=남은 병 수. `no_potion`=빈 손 정직 보고. 만피에 마셔도 소모(heal=0 — 세계는 낭비를 말리지 않는다) |
| `monster_notice` | `id monster target` | 몹이 봇 발각(발각굴림 성공) — 추적 개시 |
| `monster_flee` | `id monster` | 저HP 도주 전환 |
| `monster_desperate` | `id monster` | 도주 탈진 → 필사 반전 |
| `monster_attack` | `id monster target roll mod total ac hit`, `surprise? from_hiding? dmg? hp? down? grave? status?` | 몹의 공격. surprise=몹 기습(they-ambush), from_hiding=매복자가 정체 드러내는 일격. **hit 이면 피격 인터럽트**(D1 개정): 당한 봇의 진행 중 order 가 그 자리에서 비워진다(다음 틱 스냅샷 `order:null` + 그 봇 재결정으로 관측 가능). 피격은 시드 RNG 결정론이므로 리플레이 무해. `status`(2026-09-06 D34 additive, `run_meta.status` 판만) = 몹의 특수로 붙은 태그(그림자거미=둔화, 생존 시). `ac` 는 중독이면 −2 된 값 그대로. `grave`(2026-07-20 D22 additive, `DUNGEON_GRAVES` 판만) = down 과 함께 `{id,name,x,y}` — 쓰러진 자리에 선 '~의 묘' 피처(글리프 `T`). trap/chest_trap/fountain_harm 의 down 에도 같은 문법으로 병기 |
| `monster_move` | `id monster to=[x,y]`, `fleeing?`, `door?` | 몹 이동 — **봇 시야에 들어온 이동만** 기록(시야 밖 배회는 무음. 전체 위치는 스냅샷 monsters 로 시킹) |

## 조인 규칙 — tick 은 turn 이 아니라 **파일 순서**로 층에 묶인다
tick 은 파일 순서상 **직전 level** 에 속한다. 강하 턴에는 `tick.turn == descend.turn == 새 level.turn`
이 모두 같으므로 **turn 으로 tick↔level 을 조인하면 안 된다** — 강하 턴의 tick 스냅샷은 옛 층의
좌표(전원 won)라, 새 층 grid 위에 그리면 벽 속 봇이 나온다. 항상 파일 순서로 스크럽하라.

## 파생 규칙 (스트림에 없는 것 = 계산으로 얻는 것)
- **visited(발자국)**: 각 `level` 라인의 `party[].x,y`(스폰 칸)에서 시작해, **파일 순서상** 그 뒤의
  각 `tick` 의 `bots[].x,y` 를 누적하면 그 층의 visited 집합.
- **says(대사)**: `decisions[char].say`(비어 있지 않고 **`skipped` 가 아닌 것**). 실행 여부가 궁금하면
  같은 틱 `events` 에 그 char 의 이벤트가 있는지로도 판별 가능(실행된 결정 = 이벤트 정확히 1개).
  배달 결과는 다음 틱 `inbox` 에 이미 기록(단, descend 틱의 say 는 미배달).
- **몹 사망 시점**: `attack.killed` / 스냅샷 `alive:false` 전이.

## 리플레이 레시피 — 시드 + decisions = 완전 재현
엔진의 모든 굴림은 층별 파생 시드 RNG 하나를 지나고, LLM 이 만드는 유일한 비결정은
decisions(+say) 뿐이다. 따라서:
1. `run_meta` 의 seed/w/h/depths/monsters/traps/lurkers/max_turns 로 같은 판을 만든다.
2. 매 틱, LLM 대신 기록된 `decisions` 를 그대로 공급한다(자동보행 틱은 엔진이 알아서).
   ⚠️ 이때 **decisions 에 키가 있는 봇마다, 행동 적용 전에 `d.view(bot, bots)` 를 호출해야 한다**
   (원본의 think_all 이 그랬듯). view 의 `_perceive` 부수효과(aware_of 등록)가 이후 기습 판정의
   주사위 소비 횟수를 바꾸므로, 생략하면 RNG 스트림이 원본과 영구 분기한다.
   decisions 의 키 집합 중 **src='plan'(작정 집행, D16)만 예외 — view() 없이 결정됐으므로
   리플레이에서도 view() 를 호출하면 안 된다**(호출하면 반대로 분기). 즉 view 호출 봇 집합 =
   decisions 키 중 src≠'plan'. 나머지는 항등이다.
3. 결과 스트림은 원본과 (started 및 실행모드 메타 gm·menu 제외 — 또는 같은 env 로 실행) 라인 단위로 동일하다.
이것이 **BYO-agent 계약의 전신**이다: 두뇌 = `obs → action(dict)` 함수이며, 기록된 decisions 는
'재생 가능한 두뇌'다. 외부 에이전트는 같은 계약(`{type, target?, say?, reason?}`)만 지키면 된다.
가장 단순한 구현 = **리모컨**: `obs['options']`(엔진이 열거한 이번 턴 유효 행동 전부, 사실 주석
포함)에서 번호 하나를 고르면 끝이다 — 옵션의 type/target 을 그대로 돌려주면 계약을 지킨 것.
새 동사가 추가돼도 options 에 자동 등장하므로 이 계약은 안 바뀐다(additive).

## 소비자 예시
- 기계 크로니클: `tick.events` 를 어휘 표대로 문장화(LLM 0콜 — events.log 요약이 원형).
- 하이라이트 배치(후순위): 게임 종료 후 스트림 전체를 LLM 1콜로 서사화.
- 웹 리플레이 뷰어: `level.grid` + 틱 스냅샷으로 임의 시점 렌더/스크럽.

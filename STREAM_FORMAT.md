# STREAM_FORMAT — 구조화 스트림(JSONL) 데이터 계약 v1

엔진 진실의 기계 판본. 한 실행(run) = `state/stream.jsonl` 한 파일.
엔진 → 스트림 → **[맵뷰어 | 기계 크로니클 | GM(옵션·LLM) | 웹뷰어]** — 모든 소비자는 형제다.
GM(LLM 내레이터)도 이 진실의 한 소비자일 뿐, 스트림은 LLM 0콜로 만들어진다.

## 판단 실패와 원정 정지 — 2026-09-11 additive

`run_meta.brain_failure_policy = "retry-pause-v1"`인 실플레이에서는 규칙 두뇌가 행동을 대체하지 않는다.
같은 관측으로 최대 2번 호출하고, 성공한 결정에 `brain_retries: [{code,reason,detail}]`로 첫 오류를 보존한다.
두 번 다 실패하면 실행 가능한 `type`을 만들지 않으며, 해당 틱의 행동·이동·몬스터 턴·대기시간을 진행하지 않는다.

- `brain_pause {turn,errors:[{char,name,src:"error",reason,input_error,input_error_detail,attempt_errors}]}`:
  아직 실행하지 않은 틱의 판단 오류. `attempt_errors`에는 두 응답의 오류와 원문·당시 참조 목록을 보존한다.
- **안전 차단 대체 두뇌(2026-09-11 additive)**: 첫 응답이 모델의 안전 차단(`빈 응답 rc=200 | PROHIBITED_CONTENT|SAFETY|BLOCKLIST|…`)이면
  두 번째 시도는 **같은 프롬프트를 다른 두뇌**(`DUNGEON_BRAIN_FALLBACK`, 기본=키 있는 Claude → claude_cli → gemini_api)에게 묻는다 — 오류 덧말 없이.
  성공한 결정에 `brain_fallback: "<backend>"`가 남는다(그 판단은 그 두뇌가 했다). 규칙 두뇌 대행은 여전히 없다. 대체 두뇌도 실패하면 위 정지.
  Gemini 요청에는 조절 가능한 4범주 `safetySettings: BLOCK_NONE`을 보낸다(전투·독설 대사의 SAFETY 차단 방지) — `PROHIBITED_CONTENT`는 조절 불가.
- **안전 차단 몸짓 접기(2026-09-13 D62 additive, `run_meta.block_degrade=true` 판)**: 첫 응답이 안전 차단이면 **대체 두뇌보다 먼저** 프롬프트의
  `· 최근 친목·건네기:` 줄(D47 ② 몸짓·건네기 서술)만 접고 같은 두뇌에게 다시 묻는다(횟수 줄·세계 장부는 그대로). 통과한 결정에
  `brain_degraded: {what:"gestures", key, sticky}`가 남고(`brain_retries`에 차단 오류), 그 줄들의 지문(key, sha1 12자)이 봇에 고정돼 다음 결정부터
  같은 줄들이면 처음부터 접어 1콜(`sticky:true`, 표식은 결정마다) — 줄이 바뀌면 전체 내용으로 돌아간다(전체가 통과하면 고정 해제).
  접어도 막히면 대체 두뇌(opt-in, 접은 채로) → 그래도 막히면 위 정지. 09-13 이분(t88): 시트 단어 ∧ 몸짓 서술이 다리, 하나만 빼도 통과.
- `brain_retry {turn,chars}`: 사용자가 재시도를 요청했다. 성공한 동료의 판단과 관측은 보관하고 실패한 봇만 다시 묻는다.
- `brain_resumed {turn}`: 모든 판단이 준비되어 실행 보류를 해제했다. 이후 동일한 `turn`의 `tick`이 기록된다.

이 세 종류는 게임 프레임이 아니다. 기존 소비자는 무시할 수 있으며 `tick.decisions`에는 수락된 행동만 들어간다.
현재 정지 여부는 `/api/status.brain_pause`로 읽는다. `POST /api/retry {pause_id}`는 그 정지에만 유효하다.
제어 파일 `state/brain_pause.json`, `state/brain_retry.json`은 임시 통신용이며 리플레이 원장은 스트림이다.
명시적인 `backend:dummy` 테스트와 과거 기록의 `src:fallback`은 호환을 위해 유지한다.

## 스킬 원정 — 2026-09-10 additive, 2026-09-11 기본 채택

모든 스킬 플래그가 OFF이면 기존 스트림과 동일하다. 활성 판은 `run_meta.alpha`로 식별한다.
2026-09-11 이후 러너는 활성 판에 `run_meta.ruleset = "skills-v1"`을 추가한다.
`alpha` 필드는 기존 분석기·뷰어와의 호환을 위해 유지한다. 과거 알파 기록에는 `ruleset`이 없다.
버전 `skills-alpha-v0.1`, `skills/trpg_combat/random_skill/random_skill_effective`,
프리셋 정의, 획득 층(3), 예산(5), 대기시간 기준(`completed_actions`)을 기록한다.

- 스킬 판단도 기존 `decisions[char].type + target + action_id`를 사용한다.
- 자동 접근은 기존 `approaching/walk` 이벤트와 동일하다. 스킬 접근 보행을 새 goto 결정으로 세지 않는다.
- 실행 결과는 `tick.events`에 `skill_id/skill_name/skill_cost/skill_spent/skill_roll/skill_dc/effects/penalties/
  cooldown_before/cooldown_after/resolution`을 추가한다. 필드는 해당할 때만 존재한다.
- `result`는 `skill`(효과 발생), `skill_missed`(빗나감/주 내성 저항), `skill_failed`(실행 조건 실패),
  `no_effect`(유효 시도였지만 변화 없음)다. `skill_spent:true`일 때만 사용 비용을 냈다.
- `tick.skill_events`는 `type:skill_roll | skill_effect | resolution`의 보조 기록이다.
  각각 원래 결정의 `parent_action_id`를 참조한다. resolution의 원래 행동은 `action_type`에 있다.
  주 내성 및 부가 내성의 눈·보정·DC·성공 여부도 기록한다.
- 스킬 ON의 봇 스냅샷에는 `skills/skill_cooldowns/generated_skills`가 있다.
  `level.skill_acquisitions[]`는 3층 입장 당시의 char/turn/depth/generated_skill_id/전체 skill 정의다.
- TRPG 기본 공격은 기존 필드에 `combat_roll`과 `damage_roll`을 추가한다.
  몬스터 스킬 출혈은 `monster_status` 이벤트와 몬스터 스냅샷 `status`를 사용한다.
- 타인을 치유한 스킬은 기존 사회 사건에 `type:skill`, `skill_id/skill_name/heal`을 남긴다.
  기존 reaction의 참조·평가 계약을 따른다.

과거 판에 스킬을 소급 생성하지 않는다. 무작위 스킬 재현은 같은 코드 버전과 기록된 생성 입력이 필요하며,
정확한 판정 재생은 기존처럼 시드와 decisions로 수행한다. 관전 seek는 스냅샷을 사용한다.
[실제 규칙과 검증 범위](docs/alpha-skills.md) 참고.

## 조합형 행동 — 2026-09-10 additive

`run_meta.action_mode`는 `menu | free | compose`다. 새 필드가 없는 구판은 기존 `menu` bool로 판별한다.
2026-09-10 조합형 기본 승격 이후 새 원정은 기본 `compose`다. 현재 지침은 `adventurer_prompt.md`, 이전 메뉴형·자유서술형은 `prompts/legacy/2026-09-10/`에 보존한다. 기존 기록의 action_mode 해석은 바꾸지 않는다.
compose는 `menu:false`와 `compose_profile`을 함께 기록한다. `legacy-v0.1`은 자동 접근 없는 첫 판, `legacy-v0.2`는 거리 행동의 자동 접근을 연결한 판이다. 두 프로필 모두 v0.4 전체 resolver·reaction 구현을 뜻하지 않는다.

현재 `compose-v0.4`는 본 구현 행동 계약이다. 선택적 반응 지원 여부는 별도의 `reaction` 메타로 구별한다. `Dungeon.composed_actions=True`와 `auto_approach=True`를 함께 사용한다. 아래 legacy 설명은 과거 기록의 해석용이며 새 프로필에는 다음 계약을 적용한다.

- COMMON: `goto/explore/search/attack/use/give/bond/wait/rest` — **`compose-v0.5`(2026-09-11 D48)부터 `follow` 없음**(`compose-v0.4` 판까지는 follow 포함 10종). `run_meta.compose_profile`이 행동 계약 판본이고 `obs.action_schema`는 관측 계약 판본으로 `compose-v0.4`를 유지한다(ID 문법 불변). `goto` 의 사람 대상은 **추적**(D48 개정 — 아래 `goto` 행). 새 프롬프트는 `interact/drink`를 제시하지 않지만 파서는 `use` 별칭으로 호환한다.
- `self`는 파싱 때 `b<char>`로 정규화한다. way는 `w<관측번호>_<순번>`이며 관측마다 만료한다. 내부 경로를 가진 관측 참조이며 영구 개체가 아니다.
- 소지품 `i1/i2/i3`은 **그 행위자의** 물약 묶음/착용 무기/착용 방어구 슬롯이다. 물약 한 병 단위의 영구 ID가 아니다. 실제 접수 시 장비 값을 보관하여 접근 중 교체된 장비를 대신 건네지 않는다.
- 관측은 `action_schema`, `actor`, `targets`, `items`, `ways`를 추가한다. 모델에 제공하는 대상 목록에는 실물 좌표나 내부 참조를 포함하지 않는다. `then`도 같은 행동 문법을 사용하며 착수 시 참조를 재검증한다.
- **모든 접수 행동**에 `action_id`, 그 결과와 진행 이벤트에 `parent_action_id`를 부여한다. `events.resolution = {actor,type,target,phase,status,reason}`은 원래 정규 행동을 보존한다. `phase:pending`이면 `status:null`, `phase:resolved`이면 `status:success|failed|no_effect`다. 몸에 붙은 상태를 나타내는 기존 `events.status`와 구별하기 위해 중첩했다.
- `use`의 사물 기능 결과에는 `effect_type:interact|goto`가 붙어 기존 결과 어휘를 재사용한다. 물약 사용은 `result:healed`, `heal/hp/potions/item_used`; 효과 없는 조합은 `result:no_effect`, `reason_code`다. 공격 대상이 사람인 경우 `target_kind:bot`, `target_id:b<char>`이며 `monster_hp`는 구 소비자를 위한 호환 HP 필드다.
- `search/attack/use/give/bond`는 자동 접근한다. 실행 조건이 깨지면 실패로 남기며 임의 탐색으로 바꾸지 않는다. 실행 전의 입력 오류와 구별한다.
- `input_error_detail`은 `{code,attempted_action,target_ids,known_goto_ids,item_ids,target_detail}`로 원문 객체와 그때의 참조 목록을 보존한다. `way_not_current`는 이번 관측에 없는 길이라는 뜻이며, 실제 과거에 존재한 ID라는 단정이 아니다. 추가 오류는 `missing_target/missing_item/invalid_response`; 응답 자체가 불량이면 `raw_response`와 호출·파싱 `reason`을 보존한다. `retry-pause-v1` 실플레이의 오류는 위 재판단·정지 기록에 들어간다. 이전 기록 및 명시적인 dummy 테스트에서는 규칙 행동(`src:fallback`)에 실린다.
- 선택적 reaction은 아래 별도 계약을 따른다. 기존 관계 기록과 replies는 유지한다. 시도 횟수는 decisions, 완료 결과는 resolution의 resolved 상태를 기준으로 읽고 pending을 중복 집계하지 않는다.

과거 legacy 프로브의 `decisions.input_error?`는 입력 오류를 구분한다: `invalid_type`, `invalid_target`, `invalid_item`, `unexpected_target`, `unexpected_item`.
이 결정의 실제 `type/target/item`은 같은 결정점에서 선택한 규칙두뇌의 대체 행동이고 `src:"fallback"`이다. 요청 원문 요약은 기존 `reason`의 폴백 이유에 남는다. JSON 파싱 실패·타임아웃은 기존 이유 라벨을 사용한다.
이미 아는 대상에 대한 `too_far` 같은 세계 판정은 입력 오류가 아니다. 직접 출력한 정상 행동은 `src:"haiku"`와 기존 이벤트 계약을 유지하며 choice가 없다.
v0.1은 방향 탐색과 현재 위치에서의 행동을 사용하므로 접근 보행 연결이나 social event ID가 없다. v0.2는 아래 접근 연결만 추가한다.

### 자동 접근 — legacy-v0.2, 2026-09-10 additive

- `run_meta.auto_approach:true`: `attack/interact/give/bond`의 실행 거리까지 자동 접근하는 물리 규칙. 없거나 false면 구판. 리플레이는 Dungeon의 `auto_approach`를 이 값으로 설정한다.
- `decisions[char].action_id`: 엔진 접수 시 생성한 결정 ID (`d<depth>:t<turn>:a<serial>`). 모델 출력이나 별도 goto 결정이 아니다. 이미 거리 안인 즉시 실행에도 붙는다.
- 시작 이벤트는 **원래 type/target/item/form**과 `result:"approaching"`, `len`, `required_range`, `parent_action_id`를 가진다. 성공·거리 실패·친목 횟수로 집계하지 않는다.
- 보행 이벤트는 기존 `type:"walk"`, target과 결과를 유지하며 `parent_action_id`, `action_type`으로 원래 의도를 가리킨다. 실행 거리까지의 경로 끝은 `result:"arrived", approach_status:"ready"`; 다음 틱에 재검증하고 원래 행동을 실행한다. 이동과 공격/건네기를 한 틱에 겹치지 않는다.
- 최종 실행 결과는 기존 type/result와 `parent_action_id`, `approach_status:"completed"`. completed는 실행 판정 완료이며 성공을 보장하지 않는다(예: 소지품이 사라져 `nothing`).
- 보행 도중 중단 결과에는 `approach_status:"interrupted"`. 대상이 보이지 않거나 소멸하면 `walk/lost`, 경로가 없거나 막히면 `no_path` 또는 `walk/blocked`; 임의 탐색으로 바꾸지 않는다.
- 봇 스냅샷의 선택 필드 `approach`는 `{action_id,type,target,item?,form?}`. 중단/완료하면 빠진다. 피격 이벤트에는 `interrupted_action_id`가 붙는다. 제안에 의한 정지는 기존 tick.hails와 직전 스냅샷의 approach로 연결되며 봇의 자기 관측에도 interrupted_action_id가 남는다.
- 친목·건네기의 수신 사건, 관계 횟수, replies 대기는 실제 `done/given`이 난 뒤에만 생긴다. 말은 기존처럼 최초 결정 시점에 발화하고 접근 중 반복 발화하지 않는다.

접근에 필요한 사거리: 공격=시트 atk_range와 사선, interact=맨해튼 거리 ≤1, give/bond=체비셰프 거리 ≤1. 시야·피격·함정·새 발견·교대 등 기존 보행 규칙을 적용한다. 사용 가능한 대상 종류와 기존 행동 효과는 각 resolver의 계약을 따른다.

### 선택적 반응 — social-v0.4, 2026-09-10 additive

- 새 조합형 원정의 `run_meta`에 `reaction:true`, `reaction_schema:"social-v0.4"`를 추가한다. 메타가 없는 과거 판은 미지원이며 0건으로 추정하지 않는다.
- `tick.social_events[]`: 이번 틱에 실제로 수신된 사회 사건. `{id:"social_N",type:"say|give|bond|use",actor,recipients:[char],turn,depth,floor_id,...}`. ID는 한 원정에서 단조 증가하며 층을 넘어 중복되지 않는다. `actor`와 `recipients`는 기존 스트림과 같은 봇 번호 문자열(`"1"`)이다. 말은 실제 시야 배달 수신자를 묶은 한 사건으로 `text/say_kind/addressed_to`를, 행동은 실제 성공 후 `source_action_id`와 `form`·`item/what/placed`·`heal` 등 원문 결과를 보관한다. 접근 시작·실패·자기 행동에는 받은 사회 사건이 생기지 않는다.
- 봇의 다음 **행동 판단** 관측에 `social_events[]`를 제공한다. 자신이 받은 사건 사실만 전달하며 `recipients`·반응·집계는 제외한다. 자동보행·계획 집행·별도 사교 콜은 기회를 소비하지 않는다. 수신자별 최근 32건까지 보관하고 그 판단 이후 또는 층 이동 때 기회를 닫는다. 생략·만료는 평가되지 않은 상태로 남는다.
- 응답의 선택 필드 `reaction:"like|dislike"`, `reaction_to:"social_N"`는 한 결정에 최대 한 사건이다. 현재 제공한 ID만 허용한다. 본 행동의 수락/거절과 독립이며, 생략을 `neutral`로 만들지 않는다. 같은 수신자의 중복 평가·미실행(`skipped`)·계획(`src:plan`) 반응은 집계하지 않는다.
- `decisions.reaction_error?={code,value,target}`: `invalid_reaction`, `reaction_not_received`, `multiple_reactions_not_supported`, 실행 시 재검증의 `reaction_not_eligible`. 반응 오류는 본 행동을 바꾸지 않는다. 본 행동이 입력 오류로 폴백해도 모델이 실제 출력한 유효 반응은 보존한다.
- `tick.reactions[]`: **검증된 반응의 원천**. `{id:"reaction_N",actor,to,value,reaction_to,turn,depth,floor_id,source}`. `actor`는 평가한 사람, `to`는 원래 행위자이며 `source`는 수신자 목록을 포함한 원사건 스냅샷이다. decisions는 제안된 응답, reactions는 승인된 기록이므로 통계는 reactions를 기준으로 읽는다. 한 발화를 들은 여러 사람은 각자 평가할 수 있다.
- 집계 형태는 `{total:{like,dislike},by_actor:{char:{like,dislike}},pairs:[{from,to,like,dislike}],events,opportunities,unrated}`. `from→to`는 평가자→원래 행위자 방향이다. `events`는 사회 사건 수, `opportunities`는 수신 건수(한 발화의 수신자가 둘이면 2), `unrated`는 아직 평가 기록이 없는 수신 건수이며 대기·생략·만료를 포함한다.
- `level.reaction_stats`와 `tick.reaction_stats`는 `{run:집계,floor:{id,depth,since,...집계}}` 전체 스냅샷이다. 임의 턴으로 돌아가도 그 프레임 당시 값을 읽는다. `descend/ascend.reaction_summary`는 떠나는 방문의 `{id,depth,since,until,...집계}`. `end.reaction_summary`는 원정 전체, `end.reaction_floors[]`는 방문별 결산이다. 마을 재방문도 새 `floor_N`으로 분리한다.
- 수치와 과거 like/dislike는 관전 전용이다. 봇의 intent·history·notes·relations·floor 관측에 자동 주입하거나 호감 점수로 환산하지 않는다. 기존 `replies`(말/행동/없음)와 관계 장부는 별개로 유지한다.

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
| `start` | (2026-09-13 D67 additive) 시작 지점 `"town"|"dungeon"|"boss"` — `boss` = 관찰용 프리셋(`DUNGEON_START=boss`, 론처 체크박스 '보스방 앞에서 시작'): 판을 **최심층(depth == depths)**에서 바로 시작하고 마을 없음·보스 켬(D65)·파티는 보스룸(출구 방) 앞 칸(`Dungeon.boss_front`: 방 테두리 관통 칸 바깥 바닥) 곁에 선다(도착 칸 BFS, 결정론). 첫 `level.depth` 가 depths 이고 몹 수는 층 전이 규칙(N_MON + depth − 1) 그대로. 판 모양을 바꾸는 실행모드 메타(town 급) |
| `max_turns` | 틱 한도 (0이면 퇴화: tick 0개·end.turn=0) |
| `gm` | GM(LLM 내레이터) 사용 여부(bool) — 이 필드 자체를 제외하면 스트림 내용에 영향 없음(GM은 tick emit 뒤에 도는 소비자, 엔진·RNG 무접촉) |
| `stream_obs` | decisions 에 obs 동봉 여부(bool, `DUNGEON_STREAM_OBS=1`) — tick 스키마 판별용 |
| `menu` | 리모컨 모드 여부(bool, `DUNGEON_MENU`, 기본 true) — true 면 두뇌가 obs `options`(엔진 열거 유효 행동)에서 번호를 골랐고 decisions 에 `choice` 가 실릴 수 있다. gm 과 같은 실행모드 메타: **이 필드 자체를 제외하면 스트림 내용에 영향 없음**(리플레이는 type/target 만 쓴다). 라인 단위 리플레이 비교는 started·gm·menu 를 빼고 하거나 같은 env 로 돌릴 것 |
| `party[]` | 스폰된 파티의 시트: `char job sex maxhp str dex wdmg stealth search_r persona` (HEROES 하드코딩이 아니라 실제 스폰 봇에서 파생 — 시트 외부화(Part B)와 무관하게 유효). `name?` = 시트에 이름이 있으면 동봉(2026-07-05 additive — 보고서·웹의 호칭. 구판 스트림엔 없음: 소비자는 job 폴백) · `speech? goal? background? traits?` = 2026-09-05 D31 additive — 커스텀 시트 원문(성격 문장·말투·목표·배경 자유입력의 정제본)과 성격 키워드 원본(list), **있을 때만** · 2026-09-12 D31 개정: 키워드는 문장으로 안 바뀌고 `persona` 앞에 그대로 들어간다(`"신중한, 겁 많은. <자유 서술>"`), 론처 시트엔 `speech` 없음(손 시트에만) · `look` = 2026-09-06 D37 additive — 외형 `{head, body, colors{hair,skin,top,bottom}}`(머리·몸통 id 는 `viewer/assets/sprites/sprites.json`, 색은 `#rrggbb`). 시트에 있으면 그것, 없으면 러너가 `random.Random("look:{seed}:{char}")` 로 뽑은 랜덤(던전 난수 무접촉 = 같은 시드면 같은 얼굴). **엔진·프롬프트 무접촉, 뷰어 전용** — 구판 스트림엔 없음(뷰어는 옛 그림으로 폴백) |
| `status` | (2026-09-06 D34 additive) 상태 태그 여부(bool, `DUNGEON_STATUS` 러너 기본 1·엔진 기본 0). true 면 몹·함정의 특수가 태그를 붙인다 — 가시 함정→출혈(BLEED_STEPS=3 걸음마다 HP 1, 걸음 결과에 `bleed{hp,down?,grave?}`), 그림자거미 명중→둔화(SLOW_EVERY=2 틱에 한 칸 — 제자리 틱 `walking`+`slowed:true`, to 없음), 독침 함정·상자 독침·오염된 샘→중독(명중 mod·회피 ac −2 — 기존 mod/ac 필드에 그대로 반영). 원천 이벤트(walk.trap / interact chest_trap·fountain_harm / monster_attack)에 `status` 병기, 봇 스냅샷 `status[]`(있을 때만), witnessed `ally_status{char,tag,by,by_kind?}`. 지우기는 휴식(D35)뿐. **몸 물리(걸음·굴림)를 바꾸므로 리플레이·판 비교의 전제** |
| `rest` | (2026-09-06 D35 additive) 휴식 동사 여부(bool, `DUNGEON_REST` 러너 기본 1·엔진 기본 0). true 면 메뉴에 '쉰다'(다쳤거나 상태 태그가 있을 때만), 결정 `type:rest`(result resting) 뒤 walk 결과에 `resting(hp)`/`rested(ticks,healed,cleared[])`/`rest_met(allies[])`, 새 몹이면 `encounter`+`woke:'rest'`. 틱마다 HP +1, 만피&&5틱에 완료 → 상태 태그 소거. 동료 항목(obs sights.bots[])에 `resting:true`. 메뉴·회복 물리 메타(wait 와 같은 급) |
| `trail` | (2026-09-06 D38 additive) 자기 행동 궤적 여부(bool, `DUNGEON_TRAIL` 러너 기본 1·엔진 기본 0). true 면 봇의 obs 에 `trail[]`(마지막 view() 이후 그 봇에게 일어난 결과의 순서 — act 결과·자동보행 걸음·plan_broken·교대·말 걸림·피격, 각 `{…res, turn, plan?}`, 상한 12 넘치면 첫 칸 `{type:gap,n}`)가 **다건일 때만** 실리고, `intent` 는 작정 수(src=plan)에 덮이지 않으며 `turn` 스탬프가 붙는다. **D40(같은 날, 파트너 확정 "꼬리표식")**: 궤적은 프롬프트에 사건 사전(`dungeon_gm.EVENT_KINDS`·`event_tags`)의 꼬리표로 찍힌다("[피격] 고블린(m1) −2 (HP 8) · [둔화] 걸림") — 문장형은 관전·목격 줄에만. 자기 결과에 `{type:'state', result:'critical'|'recovered', hp, maxhp}`(위급 = `hp*4 <= maxhp` 넘는 순간 1회, 해제 1회)가 궤적에만 끼어든다(스트림 이벤트 아님 — obs 파생). 프롬프트 표현층 메타(notes 와 같은 급) — 엔진 판정·스트림 스냅샷 무접촉. obs 는 `DUNGEON_STREAM_OBS=1` 에서만 스트림에 실린다 |
| `objtags` | (2026-09-06 D39 additive) 오브젝트 태그 여부(bool, `DUNGEON_OBJTAGS` 러너 기본 1·엔진 기본 0). true 면 봇이 상인(npc — 쓰고도 남아 있는 오브젝트만, 샘·상자는 쓰면 사라져 제외)과 상호작용한 횟수·마지막 사실 한 마디를 엔진이 세서(`bot['obj_tags']` — 스냅샷 화이트리스트 밖·층 재스폰 초기화) obs `sights.features[i].tag = {verb:'말 걸어 봄', n, note?:'물약 받음'|'단검 받음'}`(있을 때만)와 리모컨 라벨(곁 '말 걸기'·'상호작용'·원거리 '이동')·시야 줄에 접미 " — 말 걸어 봄 ×2 (물약 받음)"로 붙는다. 같은 층의 직전 interact 이벤트에서 파생 가능 = 새 원천 없음. 프롬프트 표현층 메타(trail 과 같은 급) — 엔진 판정 무접촉 |
| `sayto` | (2026-09-06 D41 additive) 지목 여부(bool, `DUNGEON_SAYTO` 러너 기본 1). true 면 결정의 `to`(봇 번호 | `all`)로 지목된 말만 말 걸림 정지(tick.hails)와 대화 뼈(D36 talk)를 만든다 — 대상 없는 말=혼잣말(배달은 되나 아무도 안 멈추고 뼈도 안 쌓임). **정지 물리를 바꾸므로 리플레이·판 비교의 전제**(hail 과 같은 급). false=구판(들리면 전원 정지·배달 쌍 전부 뼈) |
| `say_kind` | (2026-09-08 D47 additive) 말의 종류 여부(bool, `DUNGEON_SAYKIND` 러너 기본 1, sayto 가 꺼지면 무효). true 면 결정의 `say_kind`(잡담|제안 — 응답 JSON 정식 필드, 기본 잡담)로 정지를 가른다: **세우는 건 제안뿐** — `to: <번호>` 제안은 그 사람만, 대상 없음·`all` 제안은 **회의**(시야 안 전원 정지). 잡담은 종류 무관 들리기만(지목·방송 잡담은 D36 talk 뼈 그대로). 제안은 제 뼈(proposed/asked)로 따로 세고 상대의 **다음 결정**에서 닫힌다(그 결정에서 한 사람·모두에게 말했으면 answered/replied — 내용 무해석). 답하기 전 같은 사람의 재제안은 정지도 뼈도 없이 배달만(반복 방지). D24 쌍 쿨다운(HAIL_CD)은 제안 정지에도 그대로. 정지 물리 메타(sayto·hail 과 같은 급 — 리플레이·판 비교의 전제). false=D41 판(지목·방송이면 종류 무관 정지) |
| `pending` | (2026-09-08 D47 additive — 09-08 D46 시험(437987d, 롤백)의 배관 재사용) 들은 말 보관 여부(bool, `DUNGEON_PENDING` 러너 기본 1). true 면 걷는 동안 들린(안 세운) 말을 그 봇의 **다음 결정까지 보관**해 `tick.inbox` 에 함께 싣는다(상한 6, 오래된 것부터 바램) — 옛 판은 결정 없는 틱의 말이 증발했다. 작정 집행 틱(src=plan)은 view() 를 안 불러 못 읽으므로 보관 유지. `inbox[].turn`(말한 틱)이 같은 날 additive 로 붙어 보관된 말의 나이를 안다(wire " — N턴 전") |
| `give` | (2026-09-09 D47 ② additive) 건네기 여부(bool, `DUNGEON_GIVE` 러너 기본 1·엔진 기본 0). true 면 곁(체비셰프≤1)의 동료에게 물약·무기·방어구를 넘기는 즉시 동사가 메뉴(obs.options `type:give`, `item` 동봉)에 열리고 `give` 이벤트가 생긴다 — 소지품 이동 물리 메타(rest 와 같은 급). 승낙=이 줄을 고르는 것(엔진은 제안 내용을 안 읽는다) |
| `bond` | (2026-09-09 D47 ② additive) 친목 여부(bool, `DUNGEON_BOND` 러너 기본 1·엔진 기본 0). true 면 곁의 동료에게 하는 몸짓(메뉴 `type:bond`, 형태는 결정의 `form`)이 열리고 `bond` 이벤트·관계 뼈 `bond`(친목행위)·`tick.replies` 가 생긴다 — 사회층 메타(relations 와 같은 급) |
| `floor` | (2026-09-06 D40 ② additive) 층 집계·결산 여부(bool, `DUNGEON_FLOOR` 러너 기본 1·엔진 기본 0). true 면 사건 사전(`EVENT_KINDS`·`WITNESS_LABELS`)으로 자기 사건·목격 사건을 층 단위로 세어 obs `floor{since, turns, n{라벨:n}, w{라벨:n}, rooms}`("## 이 층에서 지금까지")로 보여주고, 층을 떠날 때 러너가 얼려(`floor_freeze`) obs `floors[{depth, t0, t1, n, w, line, invite}]`("## 지난 층")로 이월한다. 새 층 첫 결정에 `floor_line`(≤80자) 초대 1회 → `decisions.floor_line` additive(캐릭터의 결산 한 줄 — 엔진 불가침). 스트림 이벤트에서 파생 가능(같은 층의 자기 이벤트·목격을 사전으로 세면 됨) = 새 원천 없음. 표현층 메타 |
| `relations` | (2026-09-06 D36 additive) 관계 장부 여부(bool, `DUNGEON_RELATIONS` 러너 기본 1·엔진 기본 0). true 면 뼈 5종(talk/fought/waited/rescued/at_death — **2026-09-08 D47 additive 4종** proposed/asked/answered/replied: `run_meta.say_kind` 판에서 제안의 시도·반응, talk 는 잡담만; **2026-09-09 D47 ② additive 3종** gave/received=건네기의 방향·bond=친목행위(쌍이 같이 센다). 상세 기록 acts{turn,kind,what,mine,reply} 는 봇 dict 에만 있고 스냅샷엔 안 실린다 — 같은 판의 give/bond 이벤트+tick.replies 에서 파생 가능)이 봇 장부에 쌓이고 봇 스냅샷에 `relations{other:{kind:n}}`(뼈 있을 때만·횟수만), obs 에 `relations[]`(뼈 횟수·살·초대 — 결정당 초대 1개), decisions 에 `relation{to,line}`(살 한 줄 — 초대 받은 결정만, ≤80자, 엔진 불가침). 시트 relationships 문장=살의 초기값. obs 를 바꾸므로 리플레이·A/B 의 전제(bestiary 와 같은 급). 솔로 판은 미노출 |
| `explore_dirs` | (2026-09-07 D19 개정 4 additive) 방향 탐색 열거 여부(bool, `DUNGEON_EXPLORE_DIRS` 러너 기본 1·엔진 기본 0). true 면 scan 판 메뉴에 문장이 '트여 있다'고 말하는 방위마다 `탐색: <방위> — 트여 있다, 너머는 안 보인다 — 약 N칸`(type explore, target=방위)이 열거되고 그때 '엔진에 맡긴다' 한 줄은 빠진다(막다른 곳·보이는 문이 대표하는 방위는 제외 — 1:1). 갈 방향의 선택은 에이전트가(D19 ② 원문). **메뉴(options)를 바꾸는 표현층 메타**(rest 와 같은 급). false=구판(엔진이 고른 방위 한 줄) |
| `history` | (2026-09-07 D38 개정 2·2-b additive) 최근 판단 장부 여부(bool, `DUNGEON_HISTORY` 기본 1 — brains 표현층, notes 와 같은 급). true 면 결정마다(실 결정·작정 수·폴백) **선택 한 항목**(turn·type·target·src)을 접어 두고 최근 10개를 obs.history → wire 직전 판단 절의 한 줄 `최근 판단(오래된 것부터, 직전까지): 이동 f0 (t81) · 탐색 W (t85) · 이동 exit (t87, 작정) …`로 되돌려준다. 엔진이 걷고 멈춘 결과는 안 싣는다(파트너 2-b "캐릭터의 선택만"). 스트림 내용 무변(obs 미기록) — 프롬프트 표현 메타 |
| `prompt_context` | (2026-09-12 D54 additive) 판단 요청 맨 앞의 맥락 한 줄 여부(bool, `DUNGEON_PROMPT_CONTEXT` 기본 1 — brains 표현층, dialogue 와 같은 급). true 면 모든 판단 프롬프트(조합형·메뉴·자유·SOCIAL)가 `brains.CONTEXT_LINE`("성인 모험가의 판타지 던전 게임 판단 요청, 성적 내용 없음, 폭력은 전투 판정뿐")으로 시작한다 — 모델의 프롬프트 단계 안전 분류기(Gemini PROHIBITED_CONTENT, 조절 불가)가 재회의 포옹·쓰다듬 같은 몸짓 서술을 오독하던 것을 맥락으로 막는다(09-12 차단 원문 3건 3/3 통과). 스트림 스키마엔 영향 없음(프롬프트 원문은 스트림 밖) — 판단 접점이 다르므로 A/B 비교의 전제 |
| `block_degrade` | (2026-09-13 D62 additive) 안전 차단 때 몸짓 서술 줄 접기 여부(bool, `DUNGEON_BLOCK_DEGRADE` 기본 1 — brains 표현층, prompt_context 와 같은 급). true 면 차단된 판단을 `· 최근 친목·건네기:` 줄만 접은 프롬프트로 같은 두뇌에게 다시 묻고(대체 두뇌보다 먼저), 통과한 결정에 `brain_degraded{what,key,sticky}` · 봇에 지문 고정(다음 결정부터 같은 줄들이면 바로 접어 1콜, 줄이 바뀌면 전체 복귀). 세계 장부·봇 스냅샷 불변(지문은 봇 dict 에만) — 판단 접점이 다르므로 A/B 비교의 전제 |
| `dialogue` | (2026-09-07 D43 additive) 대화 기억 여부(bool, `DUNGEON_DIALOGUE` 기본 1 — brains 표현층, notes 와 같은 급). true 면 결정 때 지난 결정까지 읽은 말(인박스, turn−1, 나에게=to_me)과 내가 한 말(mine)을 최근 6마디까지 obs.dialogue → wire '## 최근 대화 (오래된 것부터)'로 되돌려준다("카야(봇2)→나 (t82): …" / "나→카야(봇2) …" / "→모두" / "(혼잣말)"). 이번 틱 인박스는 '동료가 한 말' 절에만(중복 없음). 스트림 내용 무변 — 프롬프트 표현 메타 |
| `bestiary` | **판 시작 시점**의 캐릭터별 도감 `{이름: [종키…]}`(2026-07-05 additive — D9 도감). 도감은 obs(`monsters[].kind` 가 미등재면 `낯선 짐승`, 등재면 원명+`lore`)를 바꿔 LLM 결정에 영향을 주므로, **같은 시드라도 시작 도감이 다르면 다른 판**이다 — 리플레이·A/B 비교는 이 필드까지 맞춰야 한다. 획득 규칙=bestiary.py(스트림 소비자). 오프라인 소급(bestiary.replay/CLI)은 **이 필드를 시작 지식으로 시드**한 뒤 증분을 재생한다 — 그래야 이월 판에서도 '같은 스트림→같은 원장'(순수 투영)이 성립 |
| `bestiary_progress` | (2026-09-12 D53 additive) **판 시작 시점**의 캐릭터별 도감 진행도 `{이름: {종키: {n, deep?}}}` — `n` = 조우 수(그 종의 개체 하나를 새로 인지한 횟수 = `aware_of` 증분, 층이 바뀌면 새 개체), `deep: true` = 심층 해금됨. 정의(`entities/*/*.json knowledge.unlock`, 지금은 몬스터 2종 `{event:"encounter", count:5}`)의 조건을 채운 종만 obs 에 본문(`lore`) 전체가 실리고, 그 전엔 `brief` 한 줄 + `deep_progress{event, n, need}` 가 실린다(프롬프트 접미 "(심층: 조우 3/5)"). 해금 시점이 obs 를 바꾸므로 `bestiary` 와 같은 급의 리플레이·비교 전제이고, 오프라인 소급(bestiary.replay)은 이 필드로 조우 수·해금 여부를 시드한다(없는 옛 판 = 등재 종은 조우 1). 해금 조건 자체는 스트림에 없다 — 정의 파일이 바뀌면 옛 판의 소급 결과(해금 시점)도 바뀐다. **2026-09-12 D55 additive**: 항목에 `deep_n`(해금 시점 조우 수)·`asked_n`(마지막 인식 초대 시점 조우 수)·`due`(대기 중 초대 `deep`|`review`)·`note{text, n}`(캐릭터가 남긴 인식 한 줄과 그때 조우 수)도 실린다 — 갱신 초대 문턱(asked_n + review count)이 obs `book_invite` 를 바꾸므로 같은 급의 전제. 갱신 조건도 정의(`knowledge.review`, 없으면 unlock 과 같음)에 있고 스트림엔 없다 |
| `bestiary_defs` | (2026-09-13 D63 additive) **판 시작 시점**의 지식 본문 정의 `{종키: {name, lore, brief?, unlock?{event,count}, review?{event,count}}}` = `entities.lore()`(knowledge.deep 이 있는 정의만 — 몬스터 2종·함정·상자·샘·NPC). 도감·수첩 창(관전 클라이언트)이 캐릭터의 상태(모름·등재·심층)만큼 본문을 보여 주는 데 쓴다 — 정적 배포·리플레이가 정의 파일 없이도, 정의가 뒤에 바뀌어도 **그 판이 알던 본문**을 그대로 쓴다. 판정·obs 무접촉(표현층 메타). 없는 옛 판은 창이 상태·도감평만 보여 준다 |
| `boss` | (2026-09-13 D65 additive) 보스층·워프게이트 여부(bool, `DUNGEON_BOSS` 러너 기본 0, 론처 옵션 '보스층·귀환' 화면 기본 켬). true 면 최심층(depth == depths)의 출구 방에 보스(종 '고블린 대장', `monsters[].boss: true`, 정의 entities/monster/goblin_chief.json)가 출구 곁에 서고 상자 하나가 곁에 놓이며 출구는 **봉인된 워프게이트**(`level.gate{sealed, boss}`, obs `exit.name` '워프게이트'·`gate`·`sealed`)가 된다 — `interact exit` 결과 `locked`(봉인) / 보스 처치 `attack` 결과 `unsealed: true` / 열린 뒤 사용 = `ascend`(`to_depth: 0, gate: true`, 모임 규칙 그대로) → 마을 `level`(마을 시작이 아닌 판은 새로 짓는다) → `end.outcome: 'returned'`(마을 도착 = 판 종료). 판 모양을 바꾸는 실행모드 메타(town 급) |
| `bestiary_file` | 도감 원장 영속 여부(bool, `DUNGEON_BESTIARY_FILE`) — **2026-09-13 D64 기본 false**(캐릭터 영속은 서빙부터, 론처 '도감 이월' 옵션을 켠 판만 true) — gm/menu 와 같은 실행모드 메타(스트림 내용엔 위 `bestiary` 초기값을 통해서만 영향) |
| `ledger` | 공간 장부(D17-1) 여부(bool, `DUNGEON_LEDGER`, 기본 true — 2026-07-11 additive). true 면 obs 에 `known`(장부 투영: statics/last_seen/zones — **좌표 없음**, 구역·목격 turn 만)과 '돌아가기' 옵션이 실려 LLM 결정에 영향 — bestiary 처럼 **리플레이·A/B 는 이 필드까지 맞춰야 한다**. 장부 자체는 봇 스냅샷 화이트리스트 밖(직전 틱들의 스냅샷·시야에서 파생 가능 = 새 원천 없음). 층 전이 때 새 원장(층의 기억) |
| `sight` | 시야 반경(`DUNGEON_SIGHT`, 엔진·게이트 기본 5 — 2026-07-11 additive, 구판 스트림은 3. **데모 경로(live.bat·launcher.py)는 6** — D33 2026-09-05). 봇 관측·봇 인지·몹 시야·목격이 전부 이 한 자(대칭) — **굴림 수를 바꾸는 세계 물리라 리플레이·판 비교는 seed 처럼 이 값까지 맞춰야 한다** |
| `selfstop` | (2026-07-20 D21 additive) 자기 관찰 정지 여부(bool, `DUNGEON_SELFSTOP` 러너 기본 1·엔진 기본 0). true(+scan)면 walk 에 `reunion`/`wander` 정지가 생기고 obs.zone.doors[] 의 been 문에 `to`(너머 이름)가 실린다 — **정지 물리를 바꾸므로 리플레이·판 비교의 전제**(scan 과 같은 급) |
| `dry_signal` | (2026-07-24 additive) 무발견 신호 여부(bool, `DUNGEON_DRY` 러너 기본 1·엔진 기본 0). true(+scan)면 마지막 새 목격 이후 25걸음(DRY_K) 도달 걸음 이벤트에 `dry`(계측), 그다음 결정 obs 에 `dry` 1회 배달 |
| `hail` | (2026-07-24 D24 additive) 말 걸림 정지 여부(bool, `DUNGEON_HAIL` 러너 기본 1·엔진 기본 0). true 면 inbox 배달이 걷던 봇을 멈춰 다음 틱 결정권을 준다(tick.hails 참조) — **정지 물리를 바꾸므로 리플레이·판 비교의 전제** |
| `wait` | (2026-07-24 D25 additive) wait 동사 여부(bool, `DUNGEON_WAIT` 러너 기본 1·엔진 기본 0). true 면 메뉴에 '기다린다', walk 결과에 waiting/wait_met(동료 시야 진입)/wait_bored(WAIT_MAX=15틱) — 정지 물리 메타 · 동료 항목(obs sights.bots[])에 `waiting:true`(2026-09-12 D25 개정 additive — 기다리는 몸도 보인다, `resting` 문법·wait_verb 판만)  **2026-09-13 D25 개정 3**: 상한 `WAIT_MAX` 15→5, 깨움에 곁 도착(`wait_met{beside:true}`)·시야 이탈(`wait_left{allies}`) 추가 |
| `plan` | (2026-09-13 D66 additive) 작정(D16 `then`) 여부(bool, `DUNGEON_PLAN` 러너 기본 0·엔진 `plan_max` 기본 PLAN_MAX=2). false 면 결정에 `then` 이 와도 작정을 만들지 않는다(`src: "plan"` 결정 없음, 매 결정이 실 판단) — 조합형 자동 접근이 '가서 한다'를 품어 작정의 주 용도가 사라졌고 작정 집행 틱은 관측·들은 말을 안 읽는다(오늘 판 집행 7~8%). 지침의 `then` 문단도 제거(파트너 문장 영역). 콜 수·판단 접점 메타(리플레이·비교의 전제) |
| `notes` | (2026-07-24 D26 additive) 의미 기억(남길 한 줄) 여부(bool, `DUNGEON_NOTES` 기본 1 — brains 표현층 스위치, 엔진 무관여). true 면 decisions 원본에 `note`(그 결정에서 남긴 한 줄, ≤80자, 선택)가 실릴 수 있고 봇은 최근 5줄(NOTE_MAX)을 매 결정 프롬프트에서 재제시받는다. 엔진 판정 불가침 — 캐릭터 주관(틀린 기억=그 캐릭터의 착각). obs.notes 는 그 봇의 직전 decisions.note 들에서 파생 가능=새 원천 없음 |
| `motion` | (2026-07-24 D27 additive) 이동중 표시 여부(bool, `DUNGEON_MOTION` 러너 기본 1·엔진 기본 0). true 면 obs 의 보이는 동료 항목(sights.bots[])에 걷는 중일 때만 `moving: true` 깃발 — 방향·목적지·경로는 비노출(마음이 아니라 몸짓만). 봇 위치 스냅샷에서 파생 가능=새 원천 없음 |
| `ally_doing` | (2026-09-12 D27 개정 additive) 동료 행동 표시 여부(bool, `DUNGEON_ALLY_DOING` 러너 기본 1·엔진 기본 0). true 면 보이는 동료 항목(sights.bots[])에 `doing{act, target?, name?}` — act=`wait`/`rest`/`explore`/`follow`/`chase`/`goto`, target=char(follow·chase) 또는 id(goto: exit·f<n>·d<n>·m<n>), name=사물·몹 이름(goto). 탐색 목표 좌표는 비노출(act 만). 프롬프트 동료 줄에 "(기다리는 중)·(쉬는 중)·(탐색 중)·(유나를 따라가는 중)·(유나에게 가는 중)·(이동 중 → 보물 f3)" — 있으면 몸짓 깃발(이동중·휴식중·대기중) 대신. 파트너 "동료의 현재 어떤 행동을 선택했는지에 대한 상태를 보여주면 될 것 같아"(재촉 발화 부검 뒤) |
| `town_buildings` | (2026-09-12 D60 additive) 마을 관측 여부(bool, `DUNGEON_TOWN_BUILDINGS` 러너 기본 1, build_town 만). true 면 layout 으로 지은 마을의 건물이 **문턱 칸의 피처**(`level.features[].type='building'`, name=정의 이름 — 신전·모험가 길드·주점; 던전 입구 건물은 문턱이 '>' 바로 곁이라 제외(입구 피처가 그 자리))로 실려 obs sights.features(이름·방위·거리)·goto 대상·목격이 기존 오브젝트 체계로 된다. 건물엔 interact 옵션 없음(use 는 nothing). 별도로 마을 obs 에 `town_zone`(지금 선 칸의 구역 이름, layout_result.spaces 에서 — 스위치 무관) → 프롬프트 "지금 있는 곳: 번화가". 파트너 "마을에서는 시야나 관측 정보를 느슨하게 줘도 될 것 같다" |
| `notices` | (2026-09-12 D61 additive) 건물 역할 부품 여부(bool, `DUNGEON_NOTICES` 러너 기본 1, build_town 만). true 면 마을에서 건물 문턱 근처(부품 `range`, 기본 2칸)에 선 봇의 obs 에 `notices[]` — `{kind:'board', building:'f<n>', name, quests[{id,title,goal,reward?,client?}]}`(길드 게시판 = entities/quest 정의, **정보만** — 맡음·완료·보상 판정 없음) / `{kind:'oracle', building, name, id, text, turn?, replied?}`(신전 신탁 = 론처 `POST /api/oracle {text}` → `state/oracle.json {id,text,at}` 를 러너가 틱마다 읽어 둔 사용자 한 줄, 정제 200자 — 요청이지 명령이 아니다; replied = 이 봇이 이미 남긴 답) · **2026-09-13 개정**: 신탁은 **어느 층에서나 모든 캐릭터에게** 들린다(`{kind:'oracle', where:'sky', id, text, turn?, replied?}` — building 없음; 신전 문턱 근처에선 건물 알림 그대로) — 파트너 "플레이 중에 신탁을 내릴 수 있게, 행동을 어느 정도는 사용자가 조작". decisions 에 `oracle_reply{id,text}`(응답 JSON 정식 필드, ≤120자, 안 답한 요청이 obs 에 있을 때만 받는다 — 러너가 봇 `oracle_replies[id]` 에 두고 events.log 🔮 줄). 봇 스냅샷 밖·파생 가능(oracle.json 은 판 밖 원천 — 스트림엔 notice 로 남는다) |
| `graves` | (2026-07-20 D22 additive) 묘 여부(bool, `DUNGEON_GRAVES` 러너 기본 1·엔진 기본 0). true면 봇 사망 이벤트에 `grave={id,name,x,y}` 가 병기되고 그 칸에 '~의 묘' 피처(글리프 `T`)가 생긴다 — 피처 셋을 바꾸는 세계 물리 메타 |
| `events` | (2026-07-20 D22 additive) 사건층 여부(bool, `DUNGEON_EVENTS` 러너 기본 1·엔진 기본 0). true면 obs 에 목격 어휘가 늘고(witnessed: ally_hit/kill/trap/heal + ally_loot/spot/mishap(07-29 — 상자 결과는 D30 확장으로 ally_use 이관) + ally_use{what,id,result?}(D30 09-05: 문 타일 밟기 · 계단 하강/상행·마을 입구(남는 사람만 본다) · 상자{result=보물을 꺼냈다/독침에 당했다}) + 비몬스터 ally_down) 목격한 전사가 memories(fallen, 휘발 0)로 재제시된다 — obs 를 바꾸는 실행모드 메타(스트림 이벤트 자체는 불변, `grave` 병기 제외) |
| `scan` | 스캐너(D19) 여부(bool, `DUNGEON_SCAN`, 기본 false — 2026-07-12 additive, 암 B 판정 전 실험 스위치). true 면 ①**격자에 문 타일 `+` 가 실재**(2026-07-15 정정 — 생성기가 방↔통로 관통점에 스탬프. 벽처럼 빛을 막고 바닥처럼 지나간다, 개폐 상태 없음) ②obs.zone 이 구조 조회로 확장(`{id,kind, checked{full,todo?}, doors[], size/at(다 본 방만), len(다 본 통로만)/ends(본 것만)}` — 전부 방위·거리·딱지뿐, **좌표 없음**. **시야·기억 제한**(2026-07-15 정정 "스캐너=시야에 들어온 격자의 번역기"): 문은 눈에 든 적 있는 것만 실리고, 크기·상대위치는 그 공간을 다 봤을 때만. 문턱(문 타일) 위=`kind:'문턱'`. id 는 기하 구역 `r<n>`/`c<n>` — level.rooms 와 조인 금지. **계단은 구조에 없다** — 내용물이라 광학(sights.exit)으로만) ③`sights.traps[]`(드러난 함정 시야 어휘) ④문 id(`d<n>`)가 goto 핑·옵션에 등장 ⑤**걸음 정지 물리가 달라진다**(walk `sighted` — 아래. `entered` 는 2026-07-15 폐지) ⑥장부 주소도 기하 구역 명의. 리플레이·판 비교는 이 필드까지 맞춰야 한다(ledger 와 같은 급) |
| `obs_ascii` / `obs_pos` | wire 직렬화 스위치(D17-4, 2026-07-11 additive — `DUNGEON_OBS_ASCII` 기본 0·`DUNGEON_OBS_POS` 기본 0. pos 는 2026-09-08 판정으로 1→0 — 그 전 판의 run_meta 는 `obs_pos:true`, 재현하려면 `DUNGEON_OBS_POS=1`). **obs dict 는 불변**(ascii_view·pos 는 스트림에 그대로) — LLM 프롬프트 표현에서 뺐는지의 실행모드 메타. 프롬프트 재현·프로브 비교 시 이 필드까지 맞춰야 한다. 같은 날부터 칸 핑 id `@x,y` 도 프롬프트엔 사람 말(`dungeon_gm.place_word`)로만 선다 — 스트림 target 은 그대로 `@x,y` · **2026-09-08 D44**: wire 는 obs.party(파티 명단)를 `# 기억` 갈래 첫 절로 그리고(폐지했다가 같은 날 파트너 정정으로 존치) 절을 `# 기억`→`# 관측` 갈래 머리글로 묶는다(시트·선택지 머리글은 `# 시트`·`# 선택지`) — 표현층, obs dict 무변경 |
| `ally_sight` | (2026-07-26 additive) 동료 시야 면제 여부(bool, `DUNGEON_ALLY_SIGHT`, **러너 기본 1(D33 2026-09-05 승격 — 파트너 확정 '절대시야 범위는 일반시야와 같이')·엔진 기본 0**). true 면 **동료만** 시야 반경 안에서 장애물(벽·문)을 무시하고 보인다 — `sights.bots`·`party.visible`·follow 재경로가 같은 판정을 쓴다. 몹·피처·구조는 LOS 그대로(D19 문 광학·매복·인식 매트릭스 대칭 무손상), 반경 밖은 여전히 안 보인다. **시야 물리 메타**(scan 과 같은 급) — 켠 판은 obs·결정이 근본적으로 달라지므로 리플레이·판 대조의 전제. 근거: 07-26 부검에서 파티가 서로 못 보는 시간 44%, 그 다수가 거리 2칸, 문 낀 이동의 단절률 28% vs 그 외 2% |
| `solo` | (2026-07-29 additive) 솔로 판 여부(bool, `DUNGEON_SOLO`, 러너·엔진 **둘 다 기본 0**). true 면 **파티라는 전제가 빠진 판**이다 — ① 배치: 셋이 `SOLO_APART` 이상 흩어져 출발(`spawn(apart=True)`) ② obs: `party` 명단이 **빈 배열**이라 안 보이는 사람은 핑 불가(D18 '파티 감각' 무효. 보이는 사람은 `sights.bots` 로 여전히 핑 가능) ③ 승리 조건: `EXIT_GATHER` 면제 — 각자 계단에 닿으면 혼자 `interact exit`→`result:'exit'`, 이때 `party` 는 **자기 하나뿐인 배열**(파티 판은 모인 전원). 판은 전원 won/사망까지 계속된다. **판의 종류가 다른 메타** — 배치·obs·승리 조건이 전부 달라 파티 판과는 애초에 비교 대상이 아니다(대조군 고를 때 필수 확인 필드). 프롬프트 층에선 로스터가 비어 시트의 `- 동료:` 줄이 사라지고 시야에 든 사람이 `낯선 사람(봇N)` 으로 렌더된다(도감 '낯선 짐승' 문법) — 표현층이라 스트림 스키마엔 영향 없음. 통상 `DUNGEON_PARTY_FILE=party_solo.json`(= party.json − relationships)과 함께 쓴다. ⚠️ 캐릭터 간 공격은 아직 엔진에 없다(`_attack` 은 몹만 해소) — '마주치면 자유'의 범위에서 이것만 빠져 있다 |
| `backend` | (2026-07-25 additive) 두뇌 백엔드(문자열, `DUNGEON_BRAIN_BACKEND` 기본 `claude_cli`). `claude_cli`(claude.exe 서브프로세스·구독 과금 0) / `anthropic_api`(Messages API·종량) / `gemini_api` / `dummy`(콜 0 — 규칙두뇌 즉시 폴백). gm·menu 와 같은 급의 실행모드 메타: 같은 시드라도 모델 접점이 다르면 다른 판이므로 A/B 비교는 이 필드까지 맞춰야 한다. **스트림 스키마에 다른 영향 없음** — `decisions.src` 는 여전히 `haiku`/`fallback`/`plan` 이다(백엔드 이름은 절대 src 에 싣지 않는다: viewer·report·verify 다수가 그 세 어휘를 문자열로 매칭한다). 지연·토큰·요청 id 도 여기 없다 — 실행마다 변하는 값은 run_meta 결정론(라인 바이트 동일)을 깬다. 콜별 지연 계측이 필요하면 `DUNGEON_BRAIN_LOG=<경로>` 사이드카(스트림 밖) |

### `level` — 층(depth) 진입마다 (첫 층 포함. `descend` 직후엔 반드시 이 라인)
| 필드 | 내용 |
|---|---|
| `turn` | 이 층에 들어선 틱(첫 층=0) |
| `depth` `w` `h` | 층 번호·크기 |
| `master_seed` `level_seed` | 마스터 시드와 층별 파생 시드 |
| `visual?` | (2026-09-11 마을 v1 additive) 마을 층의 시각 레이어 `{schema:'town-visual-v1', tileSize, offset:[x,y], ground[{tile,rect}], buildings[{id,texture,x,footY,width}], props[{frame,x,y}], npcs[{id,row,cell}]}` — `art/town-v1/layout.json` 유래(`town_layout.visual_layer`). 좌표는 오프셋 전(클라이언트가 더한다). 엔진·판정 무관, 던전 층엔 없다 |
| `grid[]` | h개의 w폭 문자열, **raw 지형만**: `#`(벽) `.`(바닥) `+`(문 타일 — D19 정정 2, 2026-07-15 SCAN 기본 1 승격부터 생성 층에 등장. 벽처럼 빛을 막고 바닥처럼 지나감). tile() 관전 글리프 아님 — 몹·피처·함정은 아래 배열로 별도(겹쳐 그리기는 소비자 몫). 웹이 엔진 없이 렌더 가능 |
| `exit` | `[x,y]` 계단 좌표 |
| `gate` | (2026-09-13 D65 additive, 보스층만) `{sealed, boss}` — 이 층의 출구는 워프게이트다: 층 시작 때 봉인 여부·보스 몹 id(`monsters[].boss: true`). 봉인은 틱 중 풀린다(보스 처치 `attack` 결과 `unsealed: true`) |
| `rooms[]` | 방 전수: `id x y w h type neighbours[]` (type ∈ entrance/exit/standard) — `feature.room_id` 의 해소처 |
| `features[]` | Feature 전수: `id type name x y room_id concealed perception_gate` (type ∈ exit/treasure/chest/fountain) |
| `traps[]` | Trap 전수: `x y kind name dc dmg hidden sprung` (kind ∈ spike/dart/alarm) |
| `monsters[]` | Monster 전수(아래 몹 스냅샷 스키마) |
| `party[]` | 봇 스냅샷(아래) — 강하 이월 hp/bag 포함한 이 층 개시 상태 |

### `tick` — 루프 반복마다(빈 틱 포함). **turn 은 1부터 연속** (불변식)
| 필드 | 내용 |
|---|---|
| `turn` | 틱 번호 |
| `inbox` | 이번 틱 **사고에 주입된** 받은편지함 `{char: [{from,text,turn,to?,kind?},…]}` — 현재 파티 전원이 키(빈 리스트 포함). `to?`(2026-09-06 D41 additive)=그 말의 상대(봇 번호 | `all`, 발화 결정의 `to` 그대로 — 지목 판에선 이것으로 정지·대화 뼈를 가른다). 지난 틱 say 중 시야/근접 조건을 통과해 배달된 것. **층 전이(descend) 틱의 say 는 배달되지 않는다**(새 층에서 리셋) |
| `oracle` | (2026-09-13 D61 개정 additive) 이 틱에 **새로 들린** 신의 요청 `{id, text}` — 러너가 `state/oracle.json` 의 id 가 바뀐 틱에 한 번만 싣는다(거둠은 events.log 줄만). 요청 본문은 판 밖 원천(사용자 입력, 정제 200자)이라 스트림엔 여기서만 보인다 — 관전 로그 '🔮 신의 요청' 줄·리플레이용. 캐릭터의 답은 `decisions[char].oracle_reply` |
| `hails` | (2026-07-24 D24 additive, `run_meta.hail=true` 판만) 말 걸림 정지 성사 `{char: [from,…]}` — 방금 inbox 가 배달된 '걷던' 봇이 멈춰 다음 틱 결정권을 받은 기록(그 봇의 다음 obs.last=`{type:hail, froms}`). 같은 발화자 쿨다운(HAIL_CD=3턴, 쌍 단위)에 막히면 정지 없음 — 메시지는 그대로 배달. 성사 없는 틱엔 키 자체가 없다. **2026-09-08 D47(`run_meta.say_kind=true` 판)**: 정지는 `kind:제안` 인 말만 만든다(잡담은 안 세움) — 같은 발화자의 재제안은 상대가 답하기 전엔 성사 없음 |
| `answers` | (2026-09-08 D47 additive, `run_meta.say_kind=true` 판만) 제안 반응 `{받은 봇: {한 봇: bool}}` — 제안을 받은 봇이 그 뒤 첫 결정을 내린 틱에 닫힌 제안들. true = 그 결정에서 한 사람(또는 all)에게 말했다(관계 뼈 answered/replied), false = 말 없이·다른 사람에게만 말하고 닫힘. 작정 집행 틱엔 안 닫힌다. 같은 틱 decisions(say·to)와 앞선 틱 inbox(kind=제안)에서 파생 가능 = 새 원천 없음. 없는 틱엔 키 없음 |
| `replies` | (2026-09-09 D47 ② additive, `run_meta.say_kind` 또는 `run_meta.give/bond` 판) 반응의 **형태** `[{from, to, kind, how}]` — 제안(kind=제안)·친목·건네기를 받은 봇(from)이 그 뒤 첫 결정(작정 집행 제외)을 내린 틱에, how ∈ `행동`(건네기·친목·동행·합류로 to 를 향함)|`말`(say 의 to 가 그 사람 또는 all)|`없음`. 내용(수락·거절)은 안 읽는다. `answers`(bool)는 그대로 — 행동으로 답해도 true. 같은 틱 decisions 와 앞선 틱 inbox(kind=제안)·give/bond 이벤트에서 파생 가능 = 새 원천 없음. 없는 틱엔 키 없음 |
| `decisions` | 이번 틱 재결정한 봇들의 **결정 원본** `{char: {type, target?, item?, form?, choice?, then?, say, to?, say_kind?, reason, src, skipped?}}`. `item?`/`form?`(2026-09-09 D47 ② additive) = 건네기(`type:give`)의 물건 `potion|weapon|armor`(메뉴 줄 obs.options[].item 에서 복사 — 응답 필드 아님) / 친목(`type:bond`)의 몸짓(응답 JSON 정식 필드 `form` 을 brains 가 한 줄·120자로 정제 — 비면 엔진이 `몸짓`). `say_kind`(2026-09-08 D47 additive) = 말의 종류 `잡담`|`제안`(응답 JSON 정식 필드를 brains 가 정규화 — 빈 값·모르는 값=잡담), say 가 있을 때만. 같은 틱 `inbox` 메시지의 `kind?`(제안일 때만) 로 배달된다. `to`(2026-09-06 D41 additive) = 말의 상대(봇 번호 | `all`) — 응답 JSON 정식 필드를 brains 가 로스터로 푼 것(자유 텍스트 이름 파싱 아님), say 가 있을 때만·자기 자신 지목은 버림. 없으면 혼잣말. 같은 틱 `inbox` 메시지의 `to?` 로 배달된다. src ∈ haiku/fallback/**plan**. 자동보행 중인 봇은 키 없음(LLM 0콜). `choice` = 리모컨 모드(run_meta.menu)에서 고른 옵션 번호 — 표시/분석용이며 판정·리플레이는 type/target 만 쓴다. `skipped:true` = 접수됐지만 **미실행**(같은 틱 동료의 exit 하강이 이 봇의 won 을 선점 — say 도 발화 안 됨). **`then`(작정, 2026-07-10 D16 additive)** = 이 결정에 딸린 이어질 행동 최대 2수 `[{type, target?},…]` — 엔진이 봇에 계획으로 보관했다가 order 완결마다 한 수씩 집행한다. 집행된 수는 **별도 decisions 항목(src='plan', reason='[작정] …', say='')** 으로 기록된다(LLM 0콜·view() 미호출 — obs 미동봉). 인터럽트(피격·encounter·blocked·lost·no_path)가 남은 작정을 파기하며, 착수 재검증 실패(대상 소멸·인접 아님)는 이벤트가 아니라 그 봇의 다음 obs.last(`type:'plan_broken'`, why)로만 보고된다. `DUNGEON_STREAM_OBS=1`이면 각 결정에 `obs`(그 봇이 그 순간 본 것 — `options` 리모컨 열거 포함) 동봉 — **시드+decisions = 완전 리플레이의 마지막 조각**. ⚠️ obs 는 엔진 view() 원본이라 menu=false 실행에서도 `options` 가 실린다(그 판의 LLM 프롬프트에서는 brains 가 제거해 비노출 — 스트림 obs ≠ 프롬프트 원문). obs 에는 `last`(그 봇 직전 행동/피격 결과 — D1 개정 additive)와 `intent`(그 봇의 **직전 결정** `{type, target?, say?, reason?, src?}` — 판단 되먹임, 2026-07-05 D15① additive. brains.think_all 이 inbox 처럼 주입하는 자기 기억이라 **그 캐릭터의 직전 decisions 항목에서 파생 가능** = 스트림에 새 원천 없음. 층 전이 시 재스폰으로 리셋)도 실릴 수 있다. **2026-09-06 D38(`run_meta.trail=true` 판)**: obs 에 `trail[]` = 마지막 view() 이후 그 봇에게 일어난 결과의 순서(`{…res, turn, plan?}` — act 결과·자동보행 걸음·plan_broken·교대·말 걸림·피격. 상한 12, 넘치면 첫 칸 `{type:gap,n}`) 가 **다건일 때만** 실리고(1건이면 `last` 와 같아 생략), `intent` 는 **작정 수(src=plan)에 덮이지 않고**(직전 **실** 결정 유지) `turn` 스탬프가 붙는다 — 둘 다 같은 층의 직전 decisions·events 에서 파생 가능 = 새 원천 없음. `witnessed[]`(2026-07-11 D18 A-3 additive) = 그 봇이 **눈으로 본 동료 사건** `{kind: ally_hurt/ally_down, char, name, by, by_id}` — 사건 칸이 관측자 시야 내일 때만 쌓이고 다음 view() 한 번에 노출·소거(1회성 — D22 명명: 휘발=다음 결정 1회). 종 표기 `by` 는 관측자 도감 기준(모르는 종=낯선 짐승). D22(2026-07-20, `DUNGEON_EVENTS` 판만) 어휘 확장: `ally_hit/ally_kill {char,mon,crit?}`(동료의 명중·처치), `ally_trap {char,trap,safe,dmg?}`(함정 장면), `ally_heal {char,how}`(샘·물약 회복), 비몬스터 사인 ally_down 은 `by_kind`(trap/hazard) 병기 — 도감 게이트 면제 표식. 07-29 확장(같은 스위치): `ally_loot {char,what=보물/물약/상자/장비 이름(단검 등 — 2026-07-30 D28)}`(획득 — 오브젝트가 눈앞에서 사라진 이유), `ally_spot {char,what|mon}`(발견 — 숨은 함정·매복·보물이 드러남. 판정 칸=**드러난 물건의 자리**, 몹은 `mon` 필드=도감 게이트 경유), `ally_mishap {char,what=상자 독침/오염된 샘,dmg}`(비몬스터 피해 — 전사면 ally_down 소관). 원칙: 변화가 일어난 칸이 시야에 들면 이유도 안다. `memories[]`(D22 기억층, events 판만) = 목격한 전사의 지속 기억 `{kind:fallen, char, name, by, by_kind?, zone, turn}` — **휘발 0**: 매 결정 재제시(비우지 않음), 좌표 없이 구역 이름만. 같은 틱 사망 이벤트에서 파생 가능 = 새 원천 없음. **2026-09-06 D22 개정**: `{kind:grave_found, char, name, grave, zone, turn}` = 죽음을 못 본 봇이 묘를 본 순간의 지속 기억(1회, 목격자 무중복) — 묘 피처 스냅샷+시야에서 파생 가능. 2026-09-06 D34 `ally_status{char,tag,by,by_kind?}`(동료에게 상태 태그가 붙는 장면). 2026-09-06 D30 확장 2차 `mon_use{mon,id,what:'문',door}`(몹이 문 타일을 밟는 순간 — 그 칸을 본 봇에게, 문턱은 양쪽에서 보이므로 나가는 몹·들어오는 몹 모두. 같은 틱 `monster_move.door` 에서 파생 가능. 매복 몹 제외). `floor_line`(2026-09-06 D40 ② additive, `run_meta.floor` 판만) = 새 층 첫 결정(초대)에서 캐릭터가 남긴 지난 층 한 줄(≤80자, 엔진 불가침 — brains 가 `floors[-1].line` 에 저장). `relation`(2026-09-06 D36 additive, `run_meta.relations` 판만) = 결정 원본의 선택 필드 `{to, line}` — 초대 받은 결정에서 캐릭터가 남긴 관계 한 줄(≤80자, 엔진 불가침·brains 가 봇 장부에 겹쳐쓰기. 옛 줄은 여기에만 남는다). `book_line`(2026-09-12 D55 additive) = 결정 원본의 선택 필드 `{key, text}` — obs 에 `book_invite`(도감 인식 초대)가 있던 결정에서 캐릭터가 남긴 그 종에 대한 생각 한 줄(≤80자, 엔진 불가침 — 발급기 bestiary.py 가 원장 `note` 로 남기고 내용은 안 읽는다). 초대는 그 캐릭터의 다음 실 결정(src≠plan) 1회로 닫힌다(답이 없어도). obs 의 `book_invite{key, name, why: deep|review, n, line?}`(D55 additive) = 대기 중 초대(결정당 하나) — 원장 `due` 에서 파생·해금 조우와 결정 순서에서 재현 가능 = 새 원천 없음. obs 의 `status[]`(자기 몸 태그 `{tag,n,by,since}`)·`relations[]`(`{char,name,bones[{kind,label,n,last}],line,line_turn,line_src,invite?}` — invite 는 결정당 하나)도 실릴 수 있다. 둘 다 봇 스냅샷(bots[]) 화이트리스트 밖. `zone`·`known`·`sights.ways[].zone`(2026-07-11 D17 additive, **run_meta.ledger=true 판만** — 끈 판의 obs 는 구판과 동일): `zone` = 그 봇이 선 구역 `{id: "r<n>"/null, kind: 방/통로}`(level.rooms 의 id 와 조인 가능), `known` = 공간 장부 투영 `{statics[], last_seen[], zones[]}` — 그 봇이 이 층에서 본 것의 기억(**좌표 없음** — 구역 라벨·목격 turn, **2026-09-06 D17 개정 additive**: `bearing`·`dist`=봇 기준 방위+직선 칸 — 문의 D19 문법과 같은 자, 경로 길이는 안 본 칸을 지나므로 안 준다. 시야 밖 기억이라 sights 와 분리), ways 의 `zone` = 그 출입구가 어느 구역으로 트였나, `turn` = 그 시점의 턴 번호(2026-07-11 D17-3 additive — wire 직렬화가 장부 스탬프로 "N턴 전"을 셈. 역시 ledger 판만). 전부 직전 틱들의 스냅샷·시야에서 파생 가능 = 새 원천 없음 |
| `events[]` | 이 틱에 실제 일어난 일 전부, **순서 보존**(봇 행동 → 몬스터 턴). 아래 이벤트 어휘. 재결정 봇 행동엔 `reason`(속내)·`job` 부착, 자동보행 walk 엔 `reason` 없음 |
| `bots[]` `monsters[]` `features[]` `traps[]` | 이 틱 **종료 시점 전체 스냅샷(델타 아님)** — 임의 틱 시킹 가능. `visited`(발자국)만 제외: 파생 규칙 "각 level 의 party 좌표(스폰 칸) + 이후 각 tick 의 봇 좌표 누적" |

### `descend` — 층 전이(전원 won) 때. 직후 라인은 반드시 `level`
(2026-09-12 D59 additive) `pages{char: 수첩 한 장}` — 층을 떠나는 순간 캐릭터가 쓴 장기기억(≤300자, 캐릭터당 1콜, 실패한 캐릭터는 키 없음). 다음 층부터 obs `floors[].page` 로 실려 프롬프트 "# 수첩" 갈래에 선다(엔진 불가침 — 내용은 기계가 안 읽는다). `run_meta.notebook`(bool) 이 스위치. 수첩이 켜진 판은 D26 `notes` 가 층에서 닫힌다(이월 없음). `ascend` 도 같다.
### `ascend` — 마을 판(D29) 상행 전이(전원 won·went=up) 때. 직후 라인은 반드시 `level`
필드는 `descend` 와 동일(`to_depth`=올라가는 층 — 마을이면 0; **2026-09-13 D65** 워프게이트 귀환이면 `gate: true` 이고 최심층에서 바로 0). 마을 판의 `level` 은 같은 depth 가
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
| `outcome` | `escaped`(최심층 돌파·탈출) / `wiped`(전멸) / `timeout`(틱 한도) / `returned`(2026-09-13 D65 — 보스를 잡고 워프게이트로 마을 귀환, 원정 완료) — 러너 종료 3분기와 1:1 |
| `depth` | 종료 시 층 |
| `survivors[]` `fallen[]` `remaining[]` | 탈출/사망/(timeout 시)던전 잔류 char 목록 — 셋이 전체 파티의 분할 |
| `bots[]` | **최종 층 파티만**의 스냅샷 — 이전 층 전사자의 마지막 모습은 그 층 마지막 `tick` 에서 찾을 것(fallen 명단에는 있음) |
| `summary` | (2026-09-12 D58 additive) **판 결산** — 러너가 `end` 직전까지의 모든 레코드를 `run_summary.Collector` 로 센 것 `{v, seed, ticks, levels, depth_max, outcome, depth, survivors, fallen, decisions{real, plan, per_tick, src{}, input_retries{코드:n}, fallback}, pauses{n, by_code{}, blocked, retries}, actions{char:{n, plan, types{}, goto_ally, repeat, longest_run{n,type,target,t0,t1}}}, party{together_pct, multi_ticks, split_max, lost}, social{say{}, hails, give, bond, reactions{}}, gear{equip{}, rewear{char:{id:n}}, streak{char:{n,t0,t1}}}, bestiary{book_lines}, events{상위 12}, flags[]}`. 기계가 센 숫자만(판정 없음) — `flags` 는 임시 문턱(`run_summary.FLAGS`)을 넘은 항목의 사실 문장. 같은 스트림을 `python run_summary.py <파일>` 로 소급하면 같은 dict 가 나온다(결정론 투영 — verify_summary ②). 파생 가능 = 새 원천 없음 |

## 스냅샷 스키마

- **봇**: `char job sex x y hp maxhp bag potions weapon armor alive won order aware_of[]`
  (`potions`=소지 회복 물약 병 수 — 2026-07-17 additive. `weapon`/`armor`=착용 장비 `{name, bonus}` 또는 null — 2026-07-30 D28 additive. **2026-09-12 D57 additive**: `id`(장비 개체 번호 = 피처 id, 층-로컬 — 내려놓으면 같은 번호의 피처로 돌아온다, 층 전이 때 새 번호)·`worn[]`(착용해 본 캐릭터). events `equip` 에 `id`·`dropped_id` additive.
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
| `goto` | `target`, `result=pathed(len)/arrived/blocked(allies[])`; 아군 대상(D48 개정 2, 2026-09-12) `beside`(CHASE_IDLE≥2 일 때 붙어 서는 틱)·`already_beside`(옛 판만) | 핑 → 자동보행 개시(pathed) / 이미 곁(arrived — 아군 대상이면 '곁에 선다' 0걸음 틱, 오류 아님). 무효·도달불가 핑은 엔진이 explore 로 폴백하므로 **goto 의 no_path 는 나가지 않는다**(type 자체가 explore 로 바뀜). `blocked`(2026-07-11 D18 additive) = 동료가 길목을 점유해 경로가 대우회로 폭증(사회적 봉쇄) — 말없이 행군하지 않고 멈춰 보고, `allies[]` 에 막는 동료 명단. scan 판(D19)은 target 에 문 id(`d<n>`)도 온다 — 문 핑의 도착 칸은 **문 너머 쪽**(지나 들어서기). exit 핑은 scan 판에서도 '보일 때만'(계단=내용물, 2026-07-12 정정). **compose-v0.5 D48 개정(2026-09-11 메모 §2-4)**: target 이 사람(`b<char>`)이면 **추적** — order `chase:b<char>`(walk.target), `result=pathed(len, 이미 곁이면 0)/already_beside(곁+정지: order 없음. 결정 시점에는 입력 오류 코드 `already_beside` 로 같은 틱 재판단)/no_target/no_path/blocked(allies[])`. 그 walk 결과는 `walking(to)/beside(곁 유지 틱, 이동 없음)/arrived(곁+대상 정지 → 해제·재결정)/lost(대상 소실)`. '멈춤' 판정 = 직전 완료 틱과 이번 틱에 자리를 안 옮김(`dungeon_gm.is_moving`, 틱 경계=`monster_turn` 진입 시 기록) |
| `explore` | `target`(방위 or `auto`), `result=pathed(len, bearing?, to_exit?, remembered?, door?)/no_path(exhausted?)` | 탐색: 시야 내 미지의 문으로(pathed+bearing). **D19 개정(2026-09-06)**: 더 볼 곳 없으면 ①**계단을 본 적 있을 때만** 기억의 계단 행군(pathed+to_exit+`remembered:true`) ②아니면 기억 속 '너머를 안 가 본 문'의 건너편으로(pathed+`door:'d<n>'`) ③그것도 없으면 기억 속 '안 본 가장자리'(본 바닥 칸 중 이웃에 못 본 칸이 있는 곳)로(pathed+`frontier:true`) ④전부 없으면 no_path+`exhausted:true`(obs 에도 `exhausted`, '탐색' 어휘 미노출). 구판의 '안 본 계단 행군'(to_exit 만, remembered 없음)은 scan 없는 판(평생 시야 장부 없음 — 러너는 scan 기본 1)에만 남는다 · **`bearing` 값은 2026-09-08 D45 부터 각도 기준**(45° 부채꼴·경계 22.5°, 북=−dy) — 그 전 스트림의 방위는 부호 기준(동쪽 10칸·북쪽 1칸도 NE). 같은 함수(`_bearing`)를 obs 시야·장부·문·목격 `found[].bearing` 이 함께 쓴다 |
| `follow` | `target`(`b<char>`), `result=pathed(len)/following/blocked(allies[])` | 동행 개시(2026-07-11 D18 A-5 additive) — 동료 곁(체비셰프≤1)을 따라 걷는 **지속 order**(`follow:b<char>`, 도착 개념 없음·작정(then) 못 이음). pathed=곁으로 출발 / following=이미 곁(대기 시작) / blocked=동료發 대우회 보고. 무효·도달불가 대상은 goto 처럼 explore 폴백(type 이 바뀜). **compose-v0.5(D48, 2026-09-11)부터 조합형 결정에는 없다** — 메뉴형·구판 기록 해석용 |
| `walk` | `target`(order), `to?=[x,y]`, `result=walking/arrived/lost/treasure/at_exit/blocked/encounter/following/beside/idle/reunion/wander/waiting/wait_met/wait_bored/wait_left(2026-09-13 D25 개정 3 — 기다리던 동료 시야 이탈)/resting/rested/rest_met` | 자동보행 한 걸음. `following`(2026-07-11 D18 A-5 additive) = 동행 order(`follow:b<char>`)의 한 틱 — 곁이면 제자리(to 없음), 따라 걸었으면 to 있음; order 는 계속된다. 동행 대상 사망/하강/유령 좌표 허탕 = `lost`(기존 의미론 상속). `idle`(2026-07-11 additive, FOLLOW_IDLE=3) = 곁 대기 중 대상이 3틱 연속 제자리 → 동행 종료·재결정("아무도 안 걸으면 동행이 아니다" — 상호 동행 삼각 고착(fellowsmoke 실측)의 흡수 상태 제거). `to` 는 **실제로 이동한 틱에만** 있다 — blocked·경로 소진 arrived/lost(이동 없이 소진)·움직이는 목표(몹·동료) 곁 도달 arrived(target 만 있음) 엔 없다(마지막 한 걸음과 함께 소진되면 lost 에도 `to` 가 있다). `lost` = 움직이는 목표(`m<n>`/`b<char>`) 또는 소모성 피처(`f<n>` — 동료가 먼저 소비) 핑의 경로 소진 지점에 도착했으나 **대상이 그 자리에 없음**(이동·사망·하강·소비 — 2026-07-05 additive, 유령 좌표 보고 정직화. 구판 스트림은 이 경우를 arrived 로 기록. 의미는 '직교 곁에 없다'까지 — 대각 1칸 비껴섬 포함). `treasure` 는 그 칸이 order 목표(=path 소진)였다면 **그 자리에서 order 완결**(후속 arrived/lost 라인 없음 — 자기 소비와 동료 소비의 구분). treasure=길에서 보물 줍고 계속. at_exit=계단 앞 정지. **encounter = *새 정보*로 인한 보행 정지**(D1 개정 2026-07-04: 처음 보는 몹·함정·발견만 — 이미 알던 몹의 인접·지속으로는 멈추지 않는다. 구 pre_adj/adj_mon encounter 는 더 안 나간다). `blocked` 에 `monsters[]` 가 붙으면 보이는 몹이 다음 칸을 점거해 멈춰 보고한 것(경로 경합). 서브필드: |
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
| | ↳ `door` | (2026-09-06 D40 additive, scan 판만) 이 걸음이 문 타일(+)을 밟았다 — `'d<n>'`. D30 동료 목격(`ally_use{what:'문'}`)과 같은 순간의 **자기 경험** 표식(궤적 꼬리표 "[문 사용] d3"·층 집계 재료). 어떤 result 에도 병기될 수 있다 |
| | ↳ (휴식 결과) | (2026-09-06 D35 additive) `resting{hp}` = 휴식 틱(HP +1) / `rested{ticks, healed, cleared[]}` = 완료(만피&&REST_MIN, 상태 태그 소거·order 파기) / `rest_met{allies[]}` = 쉬다 동료가 시야에 들어 깸(wait_met 문법) |
| `rest` | `result=resting(hp)` | (2026-09-06 D35 additive) 휴식 개시 — order='rest'(이후 틱은 walk 결과로). 꺼진 판(run_meta.rest=false)에선 type 이 wait/explore 로 바뀌어 나간다(폴백) |
| `interact` | `target`, `result=exit(party[])/wait_allies(missing[])/treasure/potion(potions — 2026-07-17 additive)/chest_loot(roll,mod,total,loot)/chest_trap(roll,mod,total,dmg,hp,down?,status? — 2026-09-06 D34: 생존 시 중독)/fountain_heal(roll,heal,hp)/fountain_harm(roll,dmg,hp,down?,status? — 2026-09-06 D34: 생존 시 중독)/equip(item,slot,bonus,dropped? — 2026-07-30 D28 additive)/ascend(party[] — 마을 복귀, D29 additive)/npc_talk(npc,line,again? — 마을 NPC 말 걸기, D29 additive. `again:true` = 2026-09-06 D32 개정 additive: 같은 방문에서 두 번째 이후 말 걸기(방문 장부 `npc_met`, 선물 여부와 무관) — 이때 line 은 town.json `line_again`("아까 왔잖아. …") 고정 대사)/npc_gift(npc,item,line — 마을 상점 v0, D32 additive 2026-09-05: 아이템 상인=물약 1/방문·장비 상인=빈손이면 단검, 정해진 대사만. 받는 장면은 동료 witnessed 에 ally_loot)/nothing/too_far/no_target` | 계단(파티 동반 하강/대기)·줍기·상자·샘·물약 집기·장비 착용(스왑 시 dropped=그 자리에 놓은 헌 장비 이름 — 같은 칸에 새 피처로 실린다). exit 의 party=함께 내려간 char 명단 |
| `attack` | `result=attack/no_target/too_far`(**항상 존재**). `attack` 일 때만 `target`(몹 종류)·`target_id`(`m<n>`)·`roll mod total ac hit`·`surprise? crit? dmg? monster_hp? killed?` 존재 — 실패 2종은 `char/type/result` 뿐 | 봇의 공격. **result 로 분기하라.** surprise=우리 기습(we-ambush) |
| `search` | `radius`, `found[]` | 능동 수색(턴 소모, 반경 내 확정 발견). found 빈 배열=허탕 |
| `drink` | `result=drink_heal(heal,hp,potions)/no_potion` | (2026-07-17 additive) 회복 물약 마시기 — 굴림 없는 확정 완전 회복(샘=도박과 대비되는 '들고 다니는 보험'), 한 턴 소모. `potions`=남은 병 수. `no_potion`=빈 손 정직 보고. 만피에 마셔도 소모(heal=0 — 세계는 낭비를 말리지 않는다) |
| `give` | `target(b<char>)`, `item(potion|weapon|armor)`, `result=given(to,what,potions?|equipped?|placed?)/too_far/no_target/nothing/no_room` | (2026-09-09 D47 ② additive, `run_meta.give` 판) 건네기 — 곁의 동료에게 소지품을 넘긴다(굴림 없음·한 턴). `what`=물약|장비 이름. potions=남은 병, equipped=상대가 바로 걸침, placed=상대 슬롯이 차 있어 발밑(상대 칸, 찼으면 내 칸)에 피처로 놓임 → 같은 틱 features 에 새 피처. 받은 쪽은 이벤트가 아니라 그 봇의 다음 obs.last/trail(`type:received{from,what,item,…}`)로 보고(걷는 중이면 안 선다, 대기·휴식이면 깬다). 둘을 뺀 시야 안 동료 witnessed 에 `ally_give{char,to,what}`. 관계 뼈 gave/received |
| `bond` | `target(b<char>)`, `form`, `result=done(to)/too_far/no_target/nothing` | (2026-09-09 D47 ② additive, `run_meta.bond` 판) 친목 — 곁의 동료에게 하는 몸짓 하나(`form`=캐릭터의 자유 문구 ≤120자, 엔진 무해석). 물리 없음. 받은 쪽은 다음 obs.last/trail(`type:bonded{from,form}`), 목격 `ally_bond{char,to,form}`, 관계 뼈 bond(양쪽 '친목행위'). 반응은 상대의 다음 결정에서 `tick.replies` 로 |
| `monster_notice` | `id monster target` | 몹이 봇 발각(발각굴림 성공) — 추적 개시 |
| `monster_flee` | `id monster` | 저HP 도주 전환 |
| `monster_desperate` | `id monster` | 도주 탈진 → 필사 반전 |
| `monster_join` | `id monster ally(m<n>) ally_kind state(HUNTING|WANDERING)` | (2026-09-11 D51 additive) 도주하던 몹이 근처 다른 몹 곁에 닿아 합류 — 보이는 봇이 있으면 함께 문다(HUNTING), 없으면 곁에서 진정. 합류 전 이동은 `monster_move`에 `fleeing:true, joining:true` |
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

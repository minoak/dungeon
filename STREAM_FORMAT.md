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

## 라인 종류(kind) 5종

### `run_meta` — 첫 라인, 실행당 1회
| 필드 | 내용 |
|---|---|
| `v` | 스키마 버전(현재 1) |
| `started` | 시작 시각 `YYYY-MM-DDTHH:MM:SS` — **파일에서 유일한 비결정 필드**(결정론 비교 시 이것만 빼면 라인 단위 동일) |
| `seed` | 마스터 시드(`DUNGEON_SEED`) |
| `w` `h` | 맵 크기 |
| `depths` | 총 층수 |
| `monsters` `traps` `lurkers` | 1층 기준 배치 수(몬스터는 층당 +1) |
| `max_turns` | 틱 한도 (0이면 퇴화: tick 0개·end.turn=0) |
| `gm` | GM(LLM 내레이터) 사용 여부(bool) — 이 필드 자체를 제외하면 스트림 내용에 영향 없음(GM은 tick emit 뒤에 도는 소비자, 엔진·RNG 무접촉) |
| `stream_obs` | decisions 에 obs 동봉 여부(bool, `DUNGEON_STREAM_OBS=1`) — tick 스키마 판별용 |
| `menu` | 리모컨 모드 여부(bool, `DUNGEON_MENU`, 기본 true) — true 면 두뇌가 obs `options`(엔진 열거 유효 행동)에서 번호를 골랐고 decisions 에 `choice` 가 실릴 수 있다. gm 과 같은 실행모드 메타: **이 필드 자체를 제외하면 스트림 내용에 영향 없음**(리플레이는 type/target 만 쓴다). 라인 단위 리플레이 비교는 started·gm·menu 를 빼고 하거나 같은 env 로 돌릴 것 |
| `party[]` | 스폰된 파티의 시트: `char job sex maxhp str dex wdmg stealth search_r persona` (HEROES 하드코딩이 아니라 실제 스폰 봇에서 파생 — 시트 외부화(Part B)와 무관하게 유효). `name?` = 시트에 이름이 있으면 동봉(2026-07-05 additive — 보고서·웹의 호칭. 구판 스트림엔 없음: 소비자는 job 폴백) |
| `bestiary` | **판 시작 시점**의 캐릭터별 도감 `{이름: [종키…]}`(2026-07-05 additive — D9 도감). 도감은 obs(`monsters[].kind` 가 미등재면 `낯선 짐승`, 등재면 원명+`lore`)를 바꿔 LLM 결정에 영향을 주므로, **같은 시드라도 시작 도감이 다르면 다른 판**이다 — 리플레이·A/B 비교는 이 필드까지 맞춰야 한다. 획득 규칙=bestiary.py(스트림 소비자). 오프라인 소급(bestiary.replay/CLI)은 **이 필드를 시작 지식으로 시드**한 뒤 증분을 재생한다 — 그래야 이월 판에서도 '같은 스트림→같은 원장'(순수 투영)이 성립 |
| `bestiary_file` | 도감 원장 영속 여부(bool, `DUNGEON_BESTIARY_FILE`) — gm/menu 와 같은 실행모드 메타(스트림 내용엔 위 `bestiary` 초기값을 통해서만 영향) |

### `level` — 층(depth) 진입마다 (첫 층 포함. `descend` 직후엔 반드시 이 라인)
| 필드 | 내용 |
|---|---|
| `turn` | 이 층에 들어선 틱(첫 층=0) |
| `depth` `w` `h` | 층 번호·크기 |
| `master_seed` `level_seed` | 마스터 시드와 층별 파생 시드 |
| `grid[]` | h개의 w폭 문자열, **raw 지형만**: `#`(벽) `.`(바닥). tile() 관전 글리프 아님 — 몹·피처·함정은 아래 배열로 별도(겹쳐 그리기는 소비자 몫). 웹이 엔진 없이 렌더 가능 |
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
| `decisions` | 이번 틱 재결정한 봇들의 **결정 원본** `{char: {type, target?, choice?, then?, say, reason, src, skipped?}}`. src ∈ haiku/fallback/**plan**. 자동보행 중인 봇은 키 없음(LLM 0콜). `choice` = 리모컨 모드(run_meta.menu)에서 고른 옵션 번호 — 표시/분석용이며 판정·리플레이는 type/target 만 쓴다. `skipped:true` = 접수됐지만 **미실행**(같은 틱 동료의 exit 하강이 이 봇의 won 을 선점 — say 도 발화 안 됨). **`then`(작정, 2026-07-10 D16 additive)** = 이 결정에 딸린 이어질 행동 최대 2수 `[{type, target?},…]` — 엔진이 봇에 계획으로 보관했다가 order 완결마다 한 수씩 집행한다. 집행된 수는 **별도 decisions 항목(src='plan', reason='[작정] …', say='')** 으로 기록된다(LLM 0콜·view() 미호출 — obs 미동봉). 인터럽트(피격·encounter·blocked·lost·no_path)가 남은 작정을 파기하며, 착수 재검증 실패(대상 소멸·인접 아님)는 이벤트가 아니라 그 봇의 다음 obs.last(`type:'plan_broken'`, why)로만 보고된다. `DUNGEON_STREAM_OBS=1`이면 각 결정에 `obs`(그 봇이 그 순간 본 것 — `options` 리모컨 열거 포함) 동봉 — **시드+decisions = 완전 리플레이의 마지막 조각**. ⚠️ obs 는 엔진 view() 원본이라 menu=false 실행에서도 `options` 가 실린다(그 판의 LLM 프롬프트에서는 brains 가 제거해 비노출 — 스트림 obs ≠ 프롬프트 원문). obs 에는 `last`(그 봇 직전 행동/피격 결과 — D1 개정 additive)와 `intent`(그 봇의 **직전 결정** `{type, target?, say?, reason?, src?}` — 판단 되먹임, 2026-07-05 D15① additive. brains.think_all 이 inbox 처럼 주입하는 자기 기억이라 **그 캐릭터의 직전 decisions 항목에서 파생 가능** = 스트림에 새 원천 없음. 층 전이 시 재스폰으로 리셋)도 실릴 수 있다. `witnessed[]`(2026-07-11 D18 A-3 additive) = 그 봇이 **눈으로 본 동료 피격/전사** `{kind: ally_hurt/ally_down, char, name, by, by_id}` — 피격 칸이 관측자 시야 내일 때만 쌓이고 다음 view() 한 번에 노출·소거(1회성). 종 표기 `by` 는 관측자 도감 기준(모르는 종=낯선 짐승). 같은 틱 monster_attack 이벤트에서 파생 가능 = 새 원천 없음. 봇 스냅샷(bots[]) 화이트리스트 밖 |
| `events[]` | 이 틱에 실제 일어난 일 전부, **순서 보존**(봇 행동 → 몬스터 턴). 아래 이벤트 어휘. 재결정 봇 행동엔 `reason`(속내)·`job` 부착, 자동보행 walk 엔 `reason` 없음 |
| `bots[]` `monsters[]` `features[]` `traps[]` | 이 틱 **종료 시점 전체 스냅샷(델타 아님)** — 임의 틱 시킹 가능. `visited`(발자국)만 제외: 파생 규칙 "각 level 의 party 좌표(스폰 칸) + 이후 각 tick 의 봇 좌표 누적" |

### `descend` — 층 전이(전원 won) 때. 직후 라인은 반드시 `level`
| 필드 | 내용 |
|---|---|
| `turn` | 전이가 일어난 틱 |
| `to_depth` | 내려가는 층 번호 |
| `party[]` | 생존 이월자 `{char, hp, bag}` (char 순 정렬) |
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

- **봇**: `char job sex x y hp maxhp bag alive won order aware_of[]`
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
| `goto` | `target`, `result=pathed(len)/arrived/blocked(allies[])` | 핑 → 자동보행 개시(pathed) / 이미 곁(arrived). 무효·도달불가 핑은 엔진이 explore 로 폴백하므로 **goto 의 no_path 는 나가지 않는다**(type 자체가 explore 로 바뀜). `blocked`(2026-07-11 D18 additive) = 동료가 길목을 점유해 경로가 대우회로 폭증(사회적 봉쇄) — 말없이 행군하지 않고 멈춰 보고, `allies[]` 에 막는 동료 명단 |
| `explore` | `target`(방위 or `auto`), `result=pathed(len, bearing?, to_exit?)/no_path` | 탐색: 시야 내 미지의 문으로(pathed+bearing). 더 볼 곳 없으면 출구 행군(pathed+to_exit:true). 갈 곳 자체가 없으면 no_path |
| `follow` | `target`(`b<char>`), `result=pathed(len)/following/blocked(allies[])` | 동행 개시(2026-07-11 D18 A-5 additive) — 동료 곁(체비셰프≤1)을 따라 걷는 **지속 order**(`follow:b<char>`, 도착 개념 없음·작정(then) 못 이음). pathed=곁으로 출발 / following=이미 곁(대기 시작) / blocked=동료發 대우회 보고. 무효·도달불가 대상은 goto 처럼 explore 폴백(type 이 바뀜) |
| `walk` | `target`(order), `to?=[x,y]`, `result=walking/arrived/lost/treasure/at_exit/blocked/encounter/following` | 자동보행 한 걸음. `following`(2026-07-11 D18 A-5 additive) = 동행 order(`follow:b<char>`)의 한 틱 — 곁이면 제자리(to 없음), 따라 걸었으면 to 있음; order 는 계속된다. 동행 대상 사망/하강/유령 좌표 허탕 = `lost`(기존 의미론 상속). `to` 는 **실제로 이동한 틱에만** 있다 — blocked·경로 소진 arrived/lost(이동 없이 소진)·움직이는 목표(몹·동료) 곁 도달 arrived(target 만 있음) 엔 없다(마지막 한 걸음과 함께 소진되면 lost 에도 `to` 가 있다). `lost` = 움직이는 목표(`m<n>`/`b<char>`) 또는 소모성 피처(`f<n>` — 동료가 먼저 소비) 핑의 경로 소진 지점에 도착했으나 **대상이 그 자리에 없음**(이동·사망·하강·소비 — 2026-07-05 additive, 유령 좌표 보고 정직화. 구판 스트림은 이 경우를 arrived 로 기록. 의미는 '직교 곁에 없다'까지 — 대각 1칸 비껴섬 포함). `treasure` 는 그 칸이 order 목표(=path 소진)였다면 **그 자리에서 order 완결**(후속 arrived/lost 라인 없음 — 자기 소비와 동료 소비의 구분). treasure=길에서 보물 줍고 계속. at_exit=계단 앞 정지. **encounter = *새 정보*로 인한 보행 정지**(D1 개정 2026-07-04: 처음 보는 몹·함정·발견만 — 이미 알던 몹의 인접·지속으로는 멈추지 않는다. 구 pre_adj/adj_mon encounter 는 더 안 나간다). `blocked` 에 `monsters[]` 가 붙으면 보이는 몹이 다음 칸을 점거해 멈춰 보고한 것(경로 경합). 서브필드: |
| | ↳ `monsters[]` | 마주친(encounter) / 길목 점거(blocked) 적 `{id,kind,state}` |
| | ↳ `allies[]` | 길목 점거(blocked) 동료 `{char,name}` — 재경로가 동료發 대우회일 때(2026-07-11 D18 additive. goto blocked 와 동형) |
| | ↳ `trap` | 함정 `{kind,name,roll,mod,total,dc,safe, dmg?,hp?,down?, alarm?}` — alarm=경보 함정이 깨운 몹 수 |
| | ↳ `treasure` | true — 같은 걸음에 보물도 주움 |
| | ↳ `found[]` | 걸으며 인지한 숨은 것 `{kind,name,bearing,id?}` |
| `interact` | `target`, `result=exit(party[])/wait_allies(missing[])/treasure/chest_loot(roll,mod,total,loot)/chest_trap(roll,mod,total,dmg,hp,down?)/fountain_heal(roll,heal,hp)/fountain_harm(roll,dmg,hp,down?)/nothing/too_far/no_target` | 계단(파티 동반 하강/대기)·줍기·상자·샘. exit 의 party=함께 내려간 char 명단 |
| `attack` | `result=attack/no_target/too_far`(**항상 존재**). `attack` 일 때만 `target`(몹 종류)·`target_id`(`m<n>`)·`roll mod total ac hit`·`surprise? crit? dmg? monster_hp? killed?` 존재 — 실패 2종은 `char/type/result` 뿐 | 봇의 공격. **result 로 분기하라.** surprise=우리 기습(we-ambush) |
| `search` | `radius`, `found[]` | 능동 수색(턴 소모, 반경 내 확정 발견). found 빈 배열=허탕 |
| `monster_notice` | `id monster target` | 몹이 봇 발각(발각굴림 성공) — 추적 개시 |
| `monster_flee` | `id monster` | 저HP 도주 전환 |
| `monster_desperate` | `id monster` | 도주 탈진 → 필사 반전 |
| `monster_attack` | `id monster target roll mod total ac hit`, `surprise? from_hiding? dmg? hp? down?` | 몹의 공격. surprise=몹 기습(they-ambush), from_hiding=매복자가 정체 드러내는 일격. **hit 이면 피격 인터럽트**(D1 개정): 당한 봇의 진행 중 order 가 그 자리에서 비워진다(다음 틱 스냅샷 `order:null` + 그 봇 재결정으로 관측 가능). 피격은 시드 RNG 결정론이므로 리플레이 무해 |
| `monster_move` | `id monster to=[x,y]`, `fleeing?` | 몹 이동 — **봇 시야에 들어온 이동만** 기록(시야 밖 배회는 무음. 전체 위치는 스냅샷 monsters 로 시킹) |

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

# 엔티티 저장소 (D50, 2026-09-11 — 1차: 틀 먼저, 동작은 그대로)

파트너 설계 메모 `WONDERLAND_CHANGES_2026-09-11.md` §4-1의 [제안] 구조(정의 + 부품, 림월드 Def 방식)를 1차로 들였다.
흩어져 있던 정의 — `lore.json`(지식 본문), `dungeon_gm.py`의 `TRAP_KINDS`·`GEAR_KINDS`·`MON_STATUS`·`Monster` 기본값·
매복몹 스폰 수치·피처 이름, `town.json`의 NPC 대사·선물 — 을 `entities/` 한 곳으로 옮겼다.
**이관 전후 같은 시드의 관측·결과·난수 상태가 해시까지 일치**한다(`verify_skill_off`, `verify_entities` ③④).

## 폴더와 파일

```
entities/
  monster/goblin.json  shadow_spider.json  goblin_chief.json(D65 보스)
  monster/poison_goblin.json  spiderling.json  goblin_heavy.json          (D92 새 몬스터 풀 — 스위치를 켠 판의 2층부터)
  trap/spike.json  dart.json  alarm.json
  object/exit.json  treasure.json  chest.json  fountain.json  potion.json  dagger.json  longsword.json  leather_armor.json  chain_mail.json
  npc/gear_merchant.json  item_merchant.json  innkeeper.json          (상점 v0 — town-v0.json)
  npc/temple_attendant.json  guild_receptionist.json  tavern_keeper.json   (마을 v1 — 대사는 임시 초안)
  map/town_wonderland.json  town_temple.json  town_guild.json  town_tavern.json  town_dungeon.json  town_main_street.json  town_alley.json
  building/temple.json  guild_hall.json  tavern.json  dungeon_gate.json
```

2026-09-12: 마을 전체와 여섯 구역, 건물 네 동이 추가됐다. 건물 정의의 점유 크기와 문턱을
`town_spaces`가 충돌 격자와 그림 배치로 함께 변환한다. 상세는 [마을 공간 계약](town-spaces.md).

파일 하나 = 정의 하나. `id`는 파일명과 같고 폴더는 `kind`와 같다. 로더는 `entities.py`(`load()` — 엔진 import 때 한 번).

```json
{
  "id": "goblin", "name": "고블린", "kind": "monster",
  "tags": ["monster", "small", "coward"], "sprite": "wl-goblin",
  "comps": {
    "health": { "max": 6 },
    "combat": { "atk": 2, "dmg": 2, "ac": 12 },
    "ai": { "start": "sleeping", "flee": { "hp_frac": 3, "stamina": 8 } },
    "knowledge": { "deep": "겁 많은 소형 마물. 잠들거나 배회할 땐 …" }
  }
}
```

- **정의(Def)** = 바뀌지 않는 것. **인스턴스**(좌표·현재 hp·상태)는 지금처럼 엔진의 `Monster`/`Trap`/`Feature`가 든다.
- `kind`: `monster` · `trap` · `object`(엔진 피처 — `type`이 엔진 피처 type) · `npc`.
- `sprite`: 클라이언트 텍스처 참조 `wl-<이름>[#프레임]`. 검증은 `game/src/assets/world/<이름>.png` 존재까지 —
  프레임 번호는 `game/src/assets/world.ts`가 소유하며 수동 동기다.

## 엔진이 지금 읽는 것

| 정의 | 엔진 | 비고 |
|---|---|---|
| monster `health.max`, `combat.atk·dmg·ac` | `Monster()` 기본값 | 명시 인자가 우선(장면 저작·게이트). 모르는 종은 기준선 몹(고블린)의 몸 |
| monster `combat.on_hit` | `MON_STATUS` | 그림자거미 명중 = 둔화 |
| monster `ai.pace` | `Monster.pace` → `_chase_step` | **D92(2026-09-20)**: 걸음 박자(정수≥1, 없으면 1). 2 면 쫓을 때 한 칸 걷고 한 틱을 선다(기존 `skip_turns` 장부) — 붙은 뒤의 공격은 매 틱. 고블린 중갑병만 2 |
| monster `ai.spawn{pool, min_depth, pack}` | `entities.plus_monsters()` → `Dungeon._place_plus` | **D92**: 새 몬스터 풀(`pool: "plus"`) — `Dungeon(bestiary_plus=True)`(러너 `DUNGEON_BESTIARY_PLUS=1`, 기본 0)인 층의 `min_depth`(≥2 — 1층은 안 바꾼다)부터 고블린의 절반(올림, 하나는 남김)이 같은 칸·같은 번호로 이 종들이 된다. `pack` = 한 묶음의 마릿수(새끼거미 3 — 층당 묶음 하나, 나머지 개체는 곁의 빈 바닥 칸). 풀의 종은 `entities.lore(plus=False)`(끈 판의 사전)에서 빠진다 |
| monster `ai.flee.hp_frac·stamina·to·join_range` | `Monster.flee_frac/flee_stamina/flee_to/flee_join_range` | **없으면 도주 안 함**. 고블린만 3·8(옛 전역값), 그림자거미는 없음(파트너 결정 2026-09-11 밤 "도주하는 건 고블린만"). `to: ally` = 근처(BFS `join_range` 걸음) 아무 다른 몹에게 붙어 같이 싸운다(D51) — `away` 는 옛 규칙(봇에게서 멀어짐) |
| trap `trap.dc·dmg·status` | `TRAP_KINDS` | |
| object `name` | `_add_feature` 이름 | `'숨은 보물'`은 `treasure`의 숨김 변형 이름(코드 리터럴) |
| object `equipment.bonus` | `GEAR_KINDS` | `GEAR_CYCLE`(배치 순환)은 코드 — 이름이 정의에 있는지 게이트가 본다 |
| object `tags` | 조합형 관측 태그(`composed_actions.observe`) | 장비·물약 = `object+item` |
| npc `npc.line·line_again·gift` | `show_runner.build_town` | 마을 v1: `town.json`이 layout 을 참조하고 배치는 `layout.npcs`(id·칸). 옛 마을 `town-v0.json`은 `{"id","x","y"}` 배치. `gift`에 `potions`와 `weapon`을 함께 두면 둘 다 준다(길드 기본 물품). **D74(2026-09-15)** `gift.boon`=축복의 물약 병 수(성직자 — 기도의 답, 방문당 한 번, 마시면 공격 능력치 +1) |
| npc `npc.role·persona·report·line_report·line_report_failed·line_report_empty` | `Dungeon.npc_defs`(build_town) · `_report_quests` · `brains.npc_reply` | **D69(2026-09-14)**: `role`=관측 한 줄("길드 접수원 (원정 물품 · 의뢰 접수와 귀환 보고)"), `report:true`=원정에서 돌아온 파티가 말을 걸면 보고(원정의 끝)를 받는 NPC, 보고 대사 3종은 `{done}`·`{undone}` 자리에 의뢰 제목이 들어간다. `persona`·`role` 은 NPC 두뇌 프롬프트 재료(캐릭터 시트는 안 들어간다). ⚠️문장 전부 임시(파트너 대기) |
| npc `npc.hail·hail_no_potion·hail_board·hail_return·hail_rumor·hail_oracle` | `Dungeon.npc_greetings/_npc_hail_line` → 러너가 잡담 배달 | **D71(2026-09-14)**: NPC 가 먼저 거는 인사(상황별, 전부 선택). 자리 채움 `{name}`(캐릭터 이름) `{quests}`(안 맡은 의뢰 수) `{monsters}`·`{traps}`·`{treasure}`(지하 1층 실측). 같은 구역·6칸 안·캐릭터당 NPC 당 방문당 1회. ⚠️문장 임시 |
| npc·building·map `story{trait, history}` | `show_runner.build_town` → `Dungeon.place_story/zone_story/town_notice` → `view()`(피처 `about` · `town_zone_about` · notices `place` · 첫 관측 `floor_notice`) | **D75(2026-09-15)**: 장소·사람 소개 — trait=특징 한 줄(멀리서도 보인다, 지금 실제로 되는 것만), history=역사·이야기(곁 2칸에서만 · 마을 전체는 진입 한마디). 도감 지식(knowledge)과 다른 층 — 해금 없음, 마을 사람은 다 아는 것. 문장은 SilenceBreaker 임시(파트너 교정 대기, `docs/wording_review_2026-09-15.md`) |
| npc `npc.walk{region, rate, rect?}` | `show_runner.build_town(walkers=True)` → `Dungeon.add_walker/walk_npcs` | **D73(2026-09-14)**: 마을 행인 — layout 구역 id(main_street·alley…)의 빈 칸에 서서 틱당 rate 확률로 한 걸음(전용 RNG). 배치는 layout 이 아니라 정의가 정한다. 행인은 구역 지각(D70)을 탄다. 도트 행이 없으면 관전은 기본 타일. **D82(2026-09-18)**: `rect` = 구역 안에서 걷는 자리(layout 좌표 정수 `[x,y,w,h]`, 선택) — 구역과 겹치는 칸에만 서고 거기서만 걷는다(길드 앞마당 = 모임 자리). 없으면 구역 전체 |
| building `building.role` | `Dungeon.feature_roles`(build_town) | D69: 건물 문턱 피처의 역할 한 줄 — 관측 "모험가 길드 (의뢰 게시판 · 원정 물품 · 귀환 보고)". 어디서 뭘 얻는지의 사실(캐릭터마다 갈 데가 갈리는 재료) |
| quest `quest.req{kind, n?, monster?, depth?, object?}` | `Dungeon._quest_event`(kill=`_damage_monster` 공용 지점 · reach=러너 level 방출 직전 · loot=treasure/chest 획득) | D69: 엔진이 세는 완료 조건. `kill`(monster=몬스터 정의 id, depth 옵션, n) · `reach`(depth) · `loot`(object=엔진 피처 type, n). 없으면 맡을 수는 있지만 완수가 없는 정보성 의뢰. 검증기가 kind 어휘·monster 존재·수치를 잡는다 |
| `knowledge.deep` | `Dungeon.lore[key].lore` | 키 = `monster:<name>` / `trap:<id>` / `feature:<type>`. 도감 원장(`bestiary.json`)의 종키와 같다 |
| `knowledge.brief` · `knowledge.unlock{event, count}` | `Dungeon.lore[key].brief/unlock` → `view()` 의 `_knowledge` + `bestiary.Issuer.rules` | **지식 3층(D53, 2026-09-12)**: 모름(`낯선 짐승`) → 등재(brief 한 줄 + 진행도 `deep_progress{event,n,need}`) → 심층(deep 본문). 카운트는 발급기(`bestiary.py`)가 스트림에서 센다(LLM 0콜). 지금 세는 사건은 `encounter`(개체 하나를 새로 인지 = `aware_of` 증분)뿐이고 프리셋은 몬스터 2종 공통 `{encounter, 5}`(파트너 "5번 조우하면 심층 — 공통으로, 일단 몬스터만"). `unlock` 이 없는 종(함정·상자·샘)은 옛 2층(등재 즉시 본문). `unlock` 이 있으면 `deep` 필수, `count` 정수≥1 |

자리만 있고 아직 안 읽는 것: `knowledge.unlock.event` 의 나머지 어휘(`kill / search_first / trap_avoid / trap_disarm / visit / talk` —
검증기만 안다, 발급기는 `encounter` 만 센다) · `ai.start`·`ai.concealed`(스폰 코드가 명시) ·
오브젝트의 `loot / container / heal / consumable / exit` 부품(메모 "부품은 필요할 때 하나씩"). 도주 규칙 밖의 몬스터 AI 상수
(`LOSE_GRACE`, 시야)는 전역 그대로.

## 새 정의를 넣으려면

1. `entities/<kind>/<id>.json`을 만든다(위 꼴). 스프라이트는 클라이언트에 텍스처를 먼저 넣고 참조한다.
2. `python verify_entities.py` — 로더가 모르는 부품·`id≠파일명`·없는 텍스처·없는 해금 사건·중복·수치 결손을 한 번에 나열한다.
3. 엔진이 그 종을 실제로 내려면 스폰 코드(`dungeon_gm.py` 생성 층·`from_ascii` 장면)가 그 kind 를 불러야 한다 — 정의만으로
   층에 나타나지 않는다(층별 배치 정책은 다음 단계).
4. `bash _run_gates.sh` — `verify_skill_off`가 기존 층의 결과 불변을, `verify_entities` ③④가 지식·NPC 본문 불변을 지킨다.
   본문을 **일부러** 바꿨으면 그 게이트의 정본 해시를 함께 갱신하고 커밋 메시지에 적는다.

## 파급

- `lore.json`은 제거됐다(본문은 각 정의의 `knowledge.deep`). `bestiary.json`의 `_readme`가 아직 `lore.json`을 가리키지만
  원장 파일은 실LLM 원본 데이터라 손대지 않았다(다음 라이브 저장 때 발급기가 새 `_readme`·`n` 필드로 다시 쓴다).
- D53 뒤 원장 항목은 `{turn, depth, n, deep?}` — 옛 항목(`n` 없음)은 조우 1로 읽는다(⚠️임시 가정). 조우 수만 올라도 저장한다.
- `verify_interrupt`의 그림자거미 장면은 이전엔 기본값(고블린 수치)으로 만들어졌다 — 이제 정의 수치(5/3/3/13)를 받는다.

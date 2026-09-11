# 엔티티 저장소 (D50, 2026-09-11 — 1차: 틀 먼저, 동작은 그대로)

파트너 설계 메모 `WONDERLAND_CHANGES_2026-09-11.md` §4-1의 [제안] 구조(정의 + 부품, 림월드 Def 방식)를 1차로 들였다.
흩어져 있던 정의 — `lore.json`(지식 본문), `dungeon_gm.py`의 `TRAP_KINDS`·`GEAR_KINDS`·`MON_STATUS`·`Monster` 기본값·
매복몹 스폰 수치·피처 이름, `town.json`의 NPC 대사·선물 — 을 `entities/` 한 곳으로 옮겼다.
**이관 전후 같은 시드의 관측·결과·난수 상태가 해시까지 일치**한다(`verify_skill_off`, `verify_entities` ③④).

## 폴더와 파일

```
entities/
  monster/goblin.json  shadow_spider.json
  trap/spike.json  dart.json  alarm.json
  object/exit.json  treasure.json  chest.json  fountain.json  potion.json  dagger.json  longsword.json  leather_armor.json  chain_mail.json
  npc/gear_merchant.json  item_merchant.json  innkeeper.json
```

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
| monster `ai.flee.hp_frac·stamina` | `Monster.flee_frac/flee_stamina` | **없으면 도주 안 함**. 고블린만 3·8(옛 전역값), 그림자거미는 없음(파트너 결정 2026-09-11 밤 "도주하는 건 고블린만") |
| trap `trap.dc·dmg·status` | `TRAP_KINDS` | |
| object `name` | `_add_feature` 이름 | `'숨은 보물'`은 `treasure`의 숨김 변형 이름(코드 리터럴) |
| object `equipment.bonus` | `GEAR_KINDS` | `GEAR_CYCLE`(배치 순환)은 코드 — 이름이 정의에 있는지 게이트가 본다 |
| object `tags` | 조합형 관측 태그(`composed_actions.observe`) | 장비·물약 = `object+item` |
| npc `npc.line·line_again·gift` | `show_runner.build_town` | `town.json`은 `{"id","x","y"}` 배치만(옛 인라인 꼴도 읽힘) |
| `knowledge.deep` | `Dungeon.lore` | 키 = `monster:<name>` / `trap:<id>` / `feature:<type>`. 도감 원장(`bestiary.json`)의 종키와 같다 |

자리만 있고 아직 안 읽는 것: `knowledge.brief`(첫 발견 한 줄, 메모 §2-2 [제안]) · `knowledge.unlock`(해금 조건, §2-5 — 검증기는
사건 어휘 `kill / search_first / trap_avoid / trap_disarm / visit / talk`만 확인) · `ai.start`·`ai.concealed`(스폰 코드가 명시) ·
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
  원장 파일은 실LLM 원본 데이터라 손대지 않았다.
- `verify_interrupt`의 그림자거미 장면은 이전엔 기본값(고블린 수치)으로 만들어졌다 — 이제 정의 수치(5/3/3/13)를 받는다.

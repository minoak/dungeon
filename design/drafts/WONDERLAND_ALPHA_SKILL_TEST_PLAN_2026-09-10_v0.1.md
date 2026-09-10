# Wonderland Alpha Skill Test Plan v0.1

- 작성일: 2026-09-10
- 대상 프로젝트: `minoak/dungeon`
- 기준선: `compose-v0.4`
- 상태: 알파 테스트용 작업지시서
- 목적: 미래 청사진 중 스킬/TRPG 전투/랜덤 스킬 일부를 현재 시스템과 충돌하지 않게 격리 구현하여 검증

---

## 1. 문서 목적

이 문서는 Wonderland의 장기 청사진 전체를 구현하기 위한 문서가 아니다.

현재 안정화된 `compose-v0.4`를 기준선으로 유지하면서, 다음 세 가지를 **알파 실험 계층**으로 추가한다.

```text
1. Skill Core v0.1
2. TRPG Combat Core v0.1
3. Random Skill v0.1
```

핵심 목표는 다음 질문에 답하는 것이다.

> 캐릭터에게 COMMON 외의 고유 스킬을 주었을 때 실제 행동 다양성과 관전 재미가 증가하는가?

---

## 2. 현재 기준선

현재 기준선은 `compose-v0.4`다.

```text
관측
+
대상 ID
+
COMMON
+
의사소통
↓
LLM
↓
type + target
↓
Action Resolver
↓
world state
```

현재 COMMON은 다음 10개다.

```text
goto
follow
explore
search
attack
use
give
bond
wait
rest
```

이번 작업에서는 기존 COMMON의 의미와 기본 조합형 행동 계약을 가능한 한 변경하지 않는다.

---

## 3. 가장 중요한 회귀 방지 원칙

알파 기능이 꺼져 있을 때 현재 게임 동작이 바뀌어서는 안 된다.

```text
Alpha OFF
→ 현재 compose-v0.4와 동일

Alpha ON
→ 스킬/TRPG/랜덤 스킬 기능만 additive
```

기존 시야 엔진, 관측 구조, 자동 접근, reaction, social event, COMMON, 스트림 해석을 스킬 기능 때문에 다시 설계하지 않는다.

---

## 4. 기능 플래그

권장 플래그:

```text
DUNGEON_SKILLS=0
DUNGEON_TRPG_COMBAT=0
DUNGEON_RANDOM_SKILL=0
```

기본값은 모두 `0`.

알파 실험 시:

```text
DUNGEON_SKILLS=1
DUNGEON_TRPG_COMBAT=1
DUNGEON_RANDOM_SKILL=1
```

로 켠다.

각 플래그는 가능한 한 독립적으로 켜고 끌 수 있어야 한다.

---

## 5. 이번 알파에 포함하는 범위

### 5.1 Skill Core v0.1

캐릭터가 COMMON 외의 추가 행동을 보유할 수 있게 한다.

```text
COMMON
goto / follow / explore / search / attack / use / give / bond / wait / rest

SKILL
push_slash
guard
first_aid
```

LLM은 COMMON과 SKILL을 같은 판단 공간에서 본다.

```json
{
  "reason": "적을 밀어내 동료와 거리를 벌려야 한다.",
  "type": "push_slash",
  "target": "m1"
}
```

스킬 역시 `type + target` 문법을 사용한다.

### 5.2 TRPG Combat Core v0.1

D&D 전체 규칙을 복제하지 않는다.

이번 알파에서는 다음 정도의 최소 판정 축만 사용한다.

```text
d20
Attack Roll
AC
DC
Saving Throw
Advantage / Disadvantage
Damage Dice
Range
Condition
```

기존 전투와 충돌하지 않도록 새 TRPG 판정은 기능 플래그 뒤에서만 활성화한다.

### 5.3 Random Skill v0.1

스킬을 완제품 목록으로 수작업하지 않고, 스킬 구성요소를 조합해서 만든다.

```text
효과 + 범위 + 판정 + 조건 + 패널티 + 코스트
```

랜덤 생성기는 이 구성요소를 동일한 스킬 스키마로 조립한다.

---

## 6. 이번 알파에서 제외하는 범위

```text
던전도시
멀티유저
텔레포트
여러 던전
행동 성향 파라미터
여러 LLM 혼합
모델 라우팅
스킬 제작 UI
스킬 포인트 UI
장기 성장 시스템
직업별 대규모 스킬 트리
경제 시스템
마을 확장
기존 시야 엔진 변경
벽/바닥 target화
compose-v0.4 COMMON 계약 변경
```

필요해 보여도 이번 알파 목적과 직접 관련 없으면 별도 문서로 보낸다.

---

## 7. Skill Schema v0.1

권장 기본 형태:

```json
{
  "id": "push_slash",
  "name": "밀어베기",
  "tags": ["combat", "melee"],
  "range": 1,
  "roll": {
    "type": "attack",
    "ability": "str"
  },
  "effects": [
    {"type": "damage", "dice": "1d6"},
    {"type": "push", "distance": 1}
  ],
  "penalties": [
    {"type": "cooldown", "turns": 2}
  ],
  "cost": 4
}
```

스키마 이름은 예시이며 실제 구현 편의에 따라 조정 가능하다.

중요한 것은 다음 요소를 분리하는 것이다.

```text
skill identity
roll
range
effects
conditions
penalties
cost
```

---

## 8. 최소 Effect 목록

알파 v0.1에서는 효과를 과도하게 늘리지 않는다.

```text
damage
heal
push
bleed
```

예:

```json
{"type":"damage","dice":"1d6"}
```

```json
{"type":"heal","dice":"1d6"}
```

```json
{"type":"push","distance":1}
```

```json
{"type":"status","status":"bleed"}
```

`bleed`는 가능하면 기존 상태 태그 시스템을 재사용한다.

---

## 9. 최소 Penalty 목록

```text
hp_cost
cooldown
self_status
condition
```

예:

```json
{"type":"hp_cost","value":2}
```

```json
{"type":"cooldown","turns":2}
```

```json
{"type":"self_status","status":"slow"}
```

```json
{"type":"condition","condition":"target_bleeding"}
```

---

## 10. 코스트 시스템

좋은 효과는 코스트를 소비하고 강한 제약이나 패널티는 코스트를 돌려준다.

```text
기본 예산
- 효과 비용
+ 패널티 환급
= 최종 비용
```

정확한 수치는 실험값이며 이번 문서에서 고정하지 않는다.

단순 합산만으로 밸런스를 잡지 않는다.

```text
base effect cost
× target modifier
× range modifier
× reliability modifier
+ secondary effect
- penalty/refund
```

v0.1에서는 최소 구성요소만 사용하고 복잡한 배율 시스템은 보류할 수 있다.

---

## 11. TRPG 판정 구조

### Attack Roll

```text
d20 + 능력 보정
vs
AC
```

성공하면 effect 적용.

### Saving Throw

```text
Skill DC
vs
target saving roll
```

초기 적용 후보:

```text
push
bleed
상태이상
```

### Advantage / Disadvantage

기존 상태/위치 조건을 활용한다.

```text
기습 → Advantage
불리한 상태 → Disadvantage
```

v0.1에서는 중첩 규칙을 복잡하게 만들지 않는다.

---

## 12. 능력치 범위

이번 알파 때문에 D&D의 6능력치를 전부 도입하지 않는다.

현재 Wonderland의 기존 능력치를 최대한 재사용한다.

```text
STR
DEX
```

추후 필요성이 확인되면 `CON / INT / WIS / CHA` 확장을 별도 작업으로 검토한다.

---

## 13. Skill Resolver

스킬 역시 일반 행동처럼 resolver를 통과한다.

```text
skill type
+
target
↓
skill lookup
↓
range 확인
↓
필요 시 기존 자동 접근
↓
roll
↓
effect 적용
↓
penalty 적용
↓
stream 기록
```

스킬용 별도 이동 시스템을 만들지 않는다.

`compose-v0.4`의 자동 접근과 `required_range` 구조를 재사용한다.

---

## 14. 스킬과 자동 접근

스킬은 각자 `range`를 가진다.

```text
push_slash  range=1
arrow_shot  range=5
first_aid   range=1
```

범위 밖 대상에게 스킬을 선택하면:

```text
skill intent 유지
↓
required_range까지 자동 접근
↓
대상 재검증
↓
스킬 실행
```

접근 중 기존 중단 규칙은 그대로 작동한다.

---

## 15. 캐릭터 Skill Set

캐릭터는 COMMON과 별도로 스킬셋을 가진다.

```json
{
  "skills": [
    "push_slash",
    "guard",
    "first_aid"
  ]
}
```

알파 v0.1에서는 캐릭터당 2~3개 정도로 시작한다.

스킬셋은 우선 코드/프리셋으로 주입하며 스킬 제작 UI는 만들지 않는다.

---

## 16. 프롬프트 노출

현재 판단 공간에 SKILL을 additive하게 추가한다.

```text
## 행동과 의사소통

COMMON:
goto / follow / explore / search / attack / use / give / bond / wait / rest

SKILL:
push_slash: 근접 공격 후 1칸 밀치기, 재사용 2턴
first_aid: 인접 대상 회복, 재사용 2턴

의사소통:
잡담 / 제안
```

스킬 설명은 가능한 한 짧게 유지한다.

```text
무엇을 하는가
어떤 범위인가
핵심 제약은 무엇인가
```

전략적 사용법은 넣지 않는다.

---

## 17. 스킬 이름과 연출

스킬의 판정과 효과는 코드가 가진다.

LLM은 필요하면 다음만 생성한다.

```text
이름
설명
연출
```

LLM이 수치나 판정 규칙을 임의 변경하지 않는다.

---

## 18. Random Skill Generator v0.1

입력:

```text
seed
budget
allowed effects
allowed penalties
compatibility rules
```

생성 순서:

```text
1. 효과 선택
2. 범위 선택
3. 판정 방식 선택
4. 비용 계산
5. 예산 초과 시 패널티/조건 추가
6. 호환성 검사
7. 유효 스킬 확정
8. 이름/설명 생성 또는 템플릿 적용
```

---

## 19. 호환성 규칙

완전 랜덤 조합은 모순 스킬을 만들 수 있으므로 구성요소마다 최소한 다음 정도를 둔다.

```text
requires
forbids
tags
cost
```

예:

```json
{
  "type":"push",
  "requires":["target","movable"],
  "forbids":["self"],
  "cost":2
}
```

이 규칙은 LLM에게 보여주는 행동 제한 목록이 아니라 **랜덤 스킬 생성기의 조합 유효성 검사**에 사용한다.

---

## 20. 랜덤 스킬의 결정론

같은:

```text
seed
budget
component pool
```

이면 같은 스킬이 생성되어야 한다.

랜덤 스킬 역시 게임의 재현 가능성 원칙을 따른다.

---

## 21. 스트림 기록

스킬 결정은 기존 `action_id / parent_action_id` 계약을 따른다.

```text
decision
action_id=A42
type=push_slash
target=m1

approach
parent_action_id=A42

skill_roll
parent_action_id=A42

skill_effect
parent_action_id=A42

resolution
parent_action_id=A42
status=success
```

A/B 행동 통계에서 접근 보행을 별도의 goto로 세지 않는다.

---

## 22. 신규 스트림 필드 후보

필요한 경우 additive하게 추가한다.

```text
skill_id
skill_roll
skill_dc
skill_cost
effects[]
penalties[]
cooldown_before
cooldown_after
generated_skill_id
```

기존 소비자가 모르는 필드는 무시할 수 있어야 한다.

---

## 23. Cooldown 상태

스킬별 남은 재사용 대기 시간을 캐릭터 상태에 둔다.

```json
{
  "skill_cooldowns": {
    "push_slash": 2
  }
}
```

매 틱 감소인지 캐릭터 행동 완료 기준 감소인지는 구현 전 하나로 확정한다.

권장안:

```text
해당 캐릭터의 유효 행동 완료 기준
```

---

## 24. 랜덤 스킬 획득

1~5층 알파에서 랜덤 스킬을 시험하려면 획득 지점을 최소화한다.

예:

```text
2~4층 중 특정 시점 1회
```

또는 특정 보상 오브젝트에서 캐릭터당 1개 정도만 제공한다.

초기 목표는 성장 시스템 구축이 아니라:

> 새 스킬을 얻은 뒤 에이전트의 행동이 실제로 달라지는가?

를 보는 것이다.

---

## 25. 구현 순서

### Phase 1 — TRPG 최소 판정

```text
d20
attack roll
AC
DC
saving throw
advantage/disadvantage
damage dice
```

기존 전투와 feature flag로 분리.

### Phase 2 — Skill Schema

```text
skill registry
effects
penalties
range
cost
conditions
```

### Phase 3 — 수동 프리셋 스킬 3~5개

예:

```text
push_slash
heavy_strike
first_aid
bleeding_cut
guard
```

실제 구조를 먼저 검증한다.

### Phase 4 — compose 연결

`COMMON + SKILL`을 같은 판단 공간에 노출하고 `type + target`으로 실행한다.

### Phase 5 — Random Skill Generator

동일한 스킬 구성요소를 랜덤 조합한다.

### Phase 6 — 1~5층 실제 판

캐릭터에게 서로 다른 스킬셋을 주고 실제 플레이를 관찰한다.

---

## 26. 신규 검증 제안

```text
verify_skill_schema.py
verify_skill_effects.py
verify_skill_cost.py
verify_skill_combat.py
verify_skill_random.py
verify_skill_stream.py
```

기존 공식 게이트에도 단계적으로 추가한다.

---

## 27. 필수 기술 검증

```text
Alpha OFF → 기존 compose-v0.4 회귀 없음

스킬 type 파싱
스킬 보유 여부 검사
range
자동 접근
대상 소실
cooldown
HP cost
상태 효과
damage/heal
push
seed 기반 랜덤 재현
스트림 parent linkage
잘못된 스킬 ID fallback
엔진 crash 없음
```

---

## 28. 플레이 품질 검증

기술적으로 통과해도 성공으로 보지 않는다.

```text
SKILL 사용률
기본 attack 편중 변화
캐릭터별 스킬 사용 차이
스킬 획득 전/후 행동 변화
스킬 때문에 생긴 새로운 전술
무의미한 스킬 사용 빈도
같은 스킬의 캐릭터별 사용 차이
5층까지 밸런스 붕괴 여부
```

---

## 29. A/B 실험

### A

```text
compose-v0.4
기존 전투
스킬 없음
```

### B

```text
compose-v0.4
TRPG Combat Core
스킬 있음
```

비교:

```text
attack 비율
COMMON/SKILL 비율
행동 다양성
생존률
전투 길이
자원 소모
캐릭터 간 행동 차이
관전상 인상적인 사건 수
```

---

## 30. 성공 기준

### 기술 성공

```text
기존 게이트 회귀 없음
스킬 관련 신규 게이트 통과
결정론 유지
스트림 재생 가능
잘못된 조합에도 엔진 crash 없음
```

### 플레이 성공

최소 다음 중 일부가 관찰되어야 한다.

```text
캐릭터가 스킬을 실제 사용한다.
기본 공격 반복이 감소한다.
캐릭터마다 같은 상황에서 다른 스킬을 선택한다.
랜덤 스킬 획득 후 행동이 변한다.
스킬이 새로운 사건이나 전술을 만든다.
```

---

## 31. 실패 신호

```text
LLM이 SKILL을 거의 사용하지 않음
스킬 설명이 너무 길어 프롬프트 비용 증가
스킬이 항상 COMMON attack보다 열등
랜덤 스킬 대부분이 무의미
코스트와 실제 성능이 크게 불일치
스킬 추가 후 캐릭터성이 오히려 약화
자동 접근과 스킬 range 충돌
기존 전투/시야/관계 시스템 회귀
```

---

## 32. 알파 이후 승격 조건

Skill Core를 본선으로 승격하기 전에 다음을 확인한다.

```text
1~5층 최소 여러 판에서 안정적으로 작동
행동 다양성 증가 확인
심각한 밸런스 붕괴 없음
프롬프트 비용 증가가 허용 범위
스트림/리플레이 호환
기존 시스템 회귀 없음
```

승격 전까지는 feature flag 뒤의 실험 기능으로 취급한다.

---

## 33. 이후 청사진으로 되돌릴 항목

이번 알파 결과가 좋아도 바로 다음을 구현하지 않는다.

```text
스킬 트리 UI
플레이어 커스텀 빌더
희귀도 체계
직업별 대규모 스킬 풀
원정 간 영구 성장
멀티유저 스킬 거래
```

이 항목들은 별도 작업지시서로 다시 승격한다.

---

## 34. 핵심 원칙

> **스킬을 직접 많이 만드는 것이 아니라 스킬이 만들어지는 규칙을 만든다.**

> **스킬은 기존 조합형 행동 시스템 위에 additive하게 올라가며, 기존 COMMON과 시야·자동 접근·관계 구조를 깨지 않는다.**

---

## 35. 한 문장 작업지시

**현재 compose-v0.4를 변경하지 않는 것을 기본 전제로, 기능 플래그 뒤에 최소 TRPG 판정과 구조화된 스킬 스키마를 추가하고, 동일한 구성요소를 수동 프리셋과 랜덤 생성 양쪽에서 사용하여 1~5층 플레이에서 행동 다양성이 실제로 증가하는지 검증한다.**

# **림월드(RimWorld)의 폰(Pawn) 시스템 아키텍처 및 메커니즘 심층 분석**

## **서론 및 엔진 아키텍처 개요**

루데온 스튜디오(Ludeon Studios)가 개발한 콜로니 시뮬레이션 게임 림월드(RimWorld)는 자체 커스텀 프레임워크인 'Verse' 엔진과 'RimWorld' 네임스페이스의 결합으로 구동된다. 이 시뮬레이션 생태계의 중심에는 게임 내 거의 모든 능동적 에이전트를 대변하는 '폰(Pawn)'이 존재한다. 폰은 단순한 렌더링용 스프라이트나 제한된 상태 기계(FSM)의 구현체가 아니다. 이들은 인체 해부학적 생리 시스템, 심리적 욕구와 감정의 누적, 다계층적 의사결정 인공지능(AI), 그리고 고도화된 관계 연산 알고리즘을 포괄하는 거대한 데이터 구조체이다.  
본 보고서는 게임 소프트웨어 아키텍처 및 시스템 설계 관점에서 폰 객체가 어떻게 구성되어 있는지 분석한다. 특히 폰의 행동(Behavior), 생각(Thought), 건강(Health), 그리고 상호작용(Interaction)이라는 네 가지 핵심 축을 중심으로, 저수준의 틱(Tick) 연산부터 고수준의 사회적 알고리즘까지 데이터를 종합하여 상세히 서술한다.

## **폰(Pawn) 데이터 구조의 코어 분리 설계**

림월드의 코드베이스에서 Pawn 클래스는 그 자체로 모든 로직을 처리하는 모놀리식(Monolithic) 클래스가 아니다. 대신, 객체 지향 프로그래밍(OOP)의 단일 책임 원칙(SRP)과 컴포넌트 기반 아키텍처(CBA)를 혼합한 위임(Delegation) 패턴을 채택하고 있다. 하나의 폰 객체는 자신을 구성하는 논리적 하위 시스템을 '트래커(Tracker)'라는 개별 인스턴스들에 위임하여 관리한다1.  
이러한 분리 설계는 인간, 동물, 메카노이드, 돌연변이 등 다양한 생명체가 동일한 C\# 기반 클래스를 공유하면서도, 종족 특성(RaceProps)에 따라 특정 트래커의 기능을 활성화하거나 억제할 수 있도록 극도의 유연성을 제공한다. 엔진의 메인 루프에서 호출되는 Tick() 메서드는 각 트래커의 틱 인터벌(Tick Interval) 메서드로 분기하여 폰의 상태를 병렬적으로 갱신한다2.

| 트래커 클래스 (Tracker Class) | 핵심 관리 영역 및 기능적 의의 |
| :---- | :---- |
| Pawn\_JobTracker | 작업 대기열(Job Queue)과 작업 드라이버(JobDriver)를 인스턴스화하고 관리하며, 폰의 물리적 행동을 직접적으로 통제한다4. |
| Pawn\_HealthTracker | 트리 구조의 신체 부위(BodyPartRecord)와 이에 부여된 건강 상태(Hediff)를 추적하고 능력치(Capacity)를 실시간 갱신한다6. |
| Pawn\_NeedsTracker | 허기, 수면, 재미 등의 기본 욕구와 기분(Mood)을 수치화하여 일정 해시 인터벌(Hash Interval)마다 갱신한다2. |
| Pawn\_MindState | 정신 붕괴, 영감(Inspiration), 소속된 임무(Duty) 등 폰의 현재 인지 상태를 정의하고 작업 트래커에 덮어씌울 권한을 가진다5. |
| Pawn\_RelationsTracker | 다른 폰과의 혈연 관계, 의견(Opinion), 호환성(Compatibility)을 데이터베이스화하여 사회적 상호작용의 확률 분포를 조율한다8. |

## **인공지능 프레임워크: 5계층 아키텍처**

전통적인 게임 AI가 상태 기계(FSM) 하나에 의존하는 것과 달리, 림월드의 NPC AI 시스템은 연산 부하를 분산시키고 창발적 행동을 유도하기 위해 5개의 상호 협력적인 계층으로 분할되어 있다5. 이는 게임 후반부 수백 명의 폰이 동시에 틱 연산을 수행할 때 발생하는 성능 저하(TPS 드롭)를 방지하기 위한 핵심 설계이다11.

1. **사고 의사결정 계층 (ThinkTree):** 폰이 현재 '무엇을 할 것인가'를 추상적으로 결정한다.  
2. **작업 실행 계층 (Job System):** 결정된 목표를 수행하기 위한 '구체적인 행동 절차'를 수립한다.  
3. **경로 탐색 계층 (Pathfinding):** 목적지까지 '어떻게 이동할 것인가'를 A\* 알고리즘 및 지역(Region) 최적화를 통해 계산한다5.  
4. **群体(군집) 협조 계층 (Lord System):** 습격, 상단 등 그룹 단위의 행동을 조율하며, 트리거(Trigger)를 통해 전체 집단의 상태를 전환한다5.  
5. **전투 결정 계층 (Combat AI):** 가시선, 엄폐율, 무기 사거리를 평가하여 '누구를 어떻게 공격할 것인가'를 산출한다5.

### **의사결정 계층: 사고 트리(ThinkTree)와 노드 평가**

사고 결정 계층의 뼈대를 이루는 '사고 트리(ThinkTree)'는 행동 트리(Behavior Tree) 구조의 변형으로, 루트 노드에서 시작해 하위 노드로 내려가며 작업을 탐색한다. 폰은 일상적인 행동 스케줄을 처리하는 '주 사고 트리(MainThinkTree)'와 화재 회피나 적대적 공격 등 즉각적인 반응이 필요한 '상수 사고 트리(ConstantThinkTree)'를 동시에 실행한다5.  
사고 트리는 ThinkNode라는 기본 단위를 결합하여 구축되며, 단락 평가(Short-circuit evaluation) 메커니즘을 엄격하게 적용한다. 즉, 최상단 노드부터 하향식으로 순회를 진행하다가 특정 노드가 유효한 작업(Job)을 반환하면, 그 즉시 순회를 중단하고 하위 연산을 생략하여 엔진의 연산 자원을 보존한다5.

| 사고 노드 유형 (ThinkNode Class) | 메커니즘 및 런타임 동작 |
| :---- | :---- |
| ThinkNode\_Priority | 자식 노드들을 우선순위에 따라 순차적으로 평가하며, 첫 번째로 유효한 결과를 반환하는 하위 로직을 채택한다5. |
| ThinkNode\_Conditional | 주변 적의 유무, 특정 욕구의 임계치 도달 여부 등 컨텍스트를 검사하여 참(True)일 경우에만 분기 진입을 허용한다5. |
| ThinkNode\_JobGiver | 추상적 의사결정을 구체적 객체로 변환하는 교량 역할을 하며, 최종적으로 Job 객체를 인스턴스화하여 반환한다5. |
| ThinkNode\_Subtree | 외부 XML에 정의된 거대 트리를 참조하여 삽입한다. 이는 메모리 로딩 최적화 및 모듈의 재사용성을 극대화한다5. |

모드(Mod) 개발자들은 종종 공통 사고 트리(Common Sense 모드 등)에 ThinkNode\_Conditional을 삽입하여, 폰이 작업을 시작하기 전에 작업 공간을 먼저 청소하도록 의사결정 흐름을 재설계하기도 한다13.

### **작업 실행 계층: 큐(Queue)와 JobDriver**

JobGiver에 의해 생성된 작업은 Pawn\_JobTracker의 작업 큐에 할당된다. 큐 시스템은 EnqueueFirst(높은 우선순위 작업 즉각 삽입), EnqueueLast(대기열 후순위 삽입), Dequeue(다음 작업 호출)의 구조를 지원하여 유동적인 행동 제어를 가능하게 한다5. 작업이 큐에서 활성화되면, 엔진은 해당 작업의 복잡한 절차를 실행하기 위해 JobDriver 인스턴스를 생성한다.  
디버그 로그를 분석해보면, JobDriver\_DoBill이나 JobDriver\_ConstructFinishFrame과 같은 작업 드라이버들은 종종 맵 상의 객체 소멸이나 모드 충돌로 인해 NullReferenceException 예외를 발생시키곤 한다14. 이는 작업 드라이버가 외부 객체(TargetA, TargetB 등)의 포인터를 강력하게 참조하고 있으며, 목표물이 사라졌을 때 예외 처리가 누락되면 폰의 AI 루프 자체가 정지(Idle)해버리는 취약점이 있음을 시사한다4.

### **최소 실행 단위: Toil의 상태 기계(State Machine)**

JobDriver는 단일 작업을 'Toil(수고/노역)'이라는 원자적 단계(Atomic operation)들의 시퀀스로 분할하여 실행한다. 예를 들어 "아이템 제작"이라는 단일 Job은 '재료가 있는 곳으로 이동', '재료 픽업', '작업대로 이동', '작업 수행'이라는 여러 Toil들로 쪼개어진다5.  
각 Toil은 익명 델리게이트(Delegate)를 활용하여 다음과 같은 핵심 액션과 조건을 정의한다:

* **initAction (초기화 단계):** Toil이 틱 연산을 시작하기 전, 단 한 번 호출된다. 작업에 필요한 자원의 최대치를 계산하거나, 폰이 이동할 정확한 타일을 확정하는 등 초기 상태를 구성한다5.  
* **tickAction (틱 연산 단계):** Toil이 활성화된 동안 매 틱마다 호출된다. 폰이 작업대를 사용할 때, tickAction 내에서 tableThing.UsedThisTick()을 호출하여 애니메이션과 이펙트를 발생시키고, 폰의 작업 속도 스탯(StatDefOf.WorkToMake)에 비례하여 작업 진행도(workCycleProgress)를 실시간으로 차감한다18.  
* **defaultCompleteMode (완료 모드):** Toil의 종료 조건을 엔진에 알린다.  
  * Instant: 실행 즉시 다음 Toil로 넘어간다.  
  * PatherArrival: 길찾기 알고리즘을 통해 폰이 목표 타일에 도달하면 완료된다.  
  * Delay: 지정된 지속 시간(defaultDuration)이 경과할 때까지 대기한다.  
  * Never: 조건이 코드(tickAction) 내부에서 수동으로 만족되어 EndCurrentJob이 호출될 때까지 무한정 지속된다5.

작업 수행 도중 대상 물체가 파괴되거나 작업대의 연료(refuelableComp)가 소진될 경우, 코드는 pawn.jobs.EndCurrentJob(JobCondition.Incompletable)을 즉각 호출하여 Toil을 파기하고 사고 트리로 제어권을 반환함으로써 데드락을 방지한다18.

### **경로 탐색 계층(Pathfinding)과 이동 비용 연산**

작업 실행 과정에서 이동이 발생하면 경로 탐색 계층이 호출된다. 림월드는 기본적으로 A\* 알고리즘을 사용하되, 지역(Region) 기반 캐싱을 통해 연산 비용을 획기적으로 낮춘다5. 이동 경로 상의 각 타일은 지형에 따라 고유의 이동 비용(Path Cost)을 가지며, 특수한 오브젝트들은 추가적인 페널티를 부여한다. 예를 들어 문(Door)은 폰이 직접 열 수 있는지, 아니면 부수고 지나가야(Breaching) 하는지에 따라 비용이 동적으로 재계산되며, 폭격이 쏟아지는 지역은 '피해야 할 그물망(Avoidance grid)'으로 분류되어 우회 경로를 산출하게 만든다5.  
폰의 이동 속도는 물리적 속성뿐 아니라 상태에 따른 승수(Multiplier)의 지배를 받는다.

* **Amble (만보):** 일상적인 배회 상태. 이동 비용이 3배로 증가하고 이동 간 최소 60틱을 보장하여 여유로운 애니메이션을 유출한다5.  
* **Walk (걷기):** 이동 비용 2배, 최소 50틱 소모5.  
* **Jog (달리기):** 일반적인 목적 기반 이동. 비용 승수는 1배이다5.  
* **Sprint (전력 질주):** 비용 승수를 0.75배로 낮추어 가장 빠르게 타일을 주파한다5.

## **신체와 생리 메커니즘: BodyPartRecord와 Hediff 시스템**

림월드 폰의 건강 시스템은 단일한 체력 막대(HP Bar)를 완전히 배제하고, 해부학에 기반한 국소적 손상 누적 시스템을 사용한다. 신체의 중심인 몸통(Torso)을 루트(Root) 노드로 삼고, 여기에 어깨, 팔, 손, 손가락이 트리 형태(BodyPartRecord)로 계층적으로 연결된다6.

### **그래프 기반 손상의 연쇄 작용**

DamageWorker\_AddInjury 클래스가 호출되어 외부의 물리적 충격이 폰에게 가해지면, 엔진은 피격 부위를 계산하고 해당 부위의 내구도를 차감한다21. 이 구조의 가장 큰 특징은 그래프 종속성으로 인한 연쇄 파괴(Cascading failure)이다. 만약 어깨 부위에 최대 내구도 이상의 피해가 누적되어 완전히 파괴(Destroyed)되면, 자식 노드인 팔, 손, 손가락 역시 물리적 상태와 무관하게 즉각적으로 '유실됨(Missing Part)' 처리된다23. 개발자나 모더가 디버그 모드로 다리(Leg)를 복원하려 할 때 하위 파트와의 종속성 충돌로 인해 오류가 발생하는 현상은 이 계층 구조의 엄격함을 잘 보여준다23.

### **Hediff (Health Difference) 아키텍처**

폰의 상태 이상은 모두 Hediff라는 다형성(Polymorphic) 클래스를 통해 구현된다. Pawn\_HealthTracker.AddHediff 함수는 부상, 질병, 마약 중독, 인공 신체 이식물 등 모든 형태의 생리적 변화를 폰에게 적용하는 진입점이다6.  
단순한 상처는 Hediff\_Injury로, 지속 연산이 필요한 질병이나 약물 투여는 HediffWithComps로 인스턴스화된다21. 각 Hediff는 틱마다 부가적인 연산을 수행하는 HediffComp를 가질 수 있다. 예를 들어 약물 투여 효과는 시간이 지남에 따라 심각도(Severity)가 줄어드는 컴포넌트를 가지며, 임플란트 장비는 폰에게 새로운 능력을 부여하는 HediffComp\_VerbGiver를 통해 특수 기술(Verb\_Shoot, Verb\_MeleeAttack 등)을 주입한다24.  
상태 이상이 추가될 때마다 엔진은 CheckForStateChange를 호출하여 폰의 생존 가능성을 실시간 평가한다6. 출혈률(BleedRate)이 과도하게 높아지면 폰의 혈액량이 감소하여 의식을 잃게 되며, 고통(Pain) 수치가 폰의 인내 한계를 초과하면 '고통으로 인한 쇼크(Pain Shock)' 상태가 발동하여 폰을 강제로 쓰러뜨린다(Downed)6.

### **능력치(Capacity)의 동적 재계산**

모든 Hediff의 최종 결괏값은 폰의 스탯과 작업 효율을 좌우하는 능력치(PawnCapacityDef)에 반영된다24. 조작(Manipulation), 의식(Consciousness), 이동(Moving), 시각(Sight)과 같은 기초 능력치는 폰이 가진 모든 긍정적/부정적 Hediff 데이터를 합산하여 동적으로 산출된다. 주목할 점은 이 능력치들이 상호 의존적이라는 것이다. 시력 저하는 무기 명중률 하락과 연구 속도 감소를 초래하며, 의식의 저하는 조작과 이동 등 타 능력치의 효율(Efficiency)에 2차 곱연산 페널티를 가한다. 이러한 연쇄적 스탯 저하 시스템은 림월드 특유의 처절한 생존 환경을 극대화한다.

## **심리와 감정: 욕구(Needs)와 생각(Thoughts) 모델**

신체 시스템(Pawn\_HealthTracker)이 하드웨어를 관장한다면, 소프트웨어적 동인은 Pawn\_NeedsTracker가 전담한다2. 폰의 틱 인터벌(NeedsTrackerTickInterval) 주기가 도래할 때마다, 엔진은 폰이 보유한 허기, 수면, 재미 등의 모든 욕구 객체에 대해 NeedInterval() 메서드를 차례로 호출하여 수치를 감소(Decay)시킨다2.  
욕구의 결핍이나 충족은 '생각(Thought)' 시스템을 거쳐 최종적으로 폰의 기분(Mood)으로 치환된다2. 림월드의 ThoughtHandler는 폰의 감정을 구성하는 두 가지 주요 정보 출처를 관리한다.

1. **기억 기반 생각 (Thought\_Memory):** 과거의 특정 사건으로부터 파생되며 메모리에 축적된 후 시간이 지남에 따라 자연 소멸하는 생각이다. "아군이 죽는 것을 목격함", "다른 폰과 멋진 대화를 나눔" 등이 이에 해당한다. MemoryThoughtHandler.RemoveExpiredMemories 메서드는 지정된 만료 시간(Age)을 초과한 기억들을 정기적으로 가비지 컬렉션(GC)하여 기분 산출 목록에서 제외시킨다1. 디버그 로그에서 볼 수 있듯, 간혹 모드 충돌이나 객체 강제 삭제로 인해 추방된 폰의 기억(Thought\_Banished)이 대상을 잃고 소멸 과정에서 NullReferenceException 예외를 뱉어내는 현상이 보고되기도 한다26.  
2. **상황 기반 생각 (Thought\_Situational):** 폰이 처한 즉각적인 환경에 기인하여 실시간으로 생성 및 소멸하는 생각이다. 방의 인테리어 수준(아름다움/추함), 현재 체감 온도, 고통의 유무 등이 여기에 속한다. SituationalThoughtHandler.TryCreateThought 메서드는 맵의 데이터를 쿼리하여 상황을 검증하며, 환경이 변하면 기존 생각 노드를 파기하고 기분을 즉시 갱신한다3. 이 과정에서 특정 모드(예: Individuality 모드)의 정의가 딕셔너리 키(KeyNotFoundException)를 유실하여 전체 UI 출력을 먹통으로 만드는 치명적 버그를 유발하기도 한다28.

두 시스템에 의해 수집된 긍정적/부정적 생각들은 가중치 연산을 거쳐 TotalMoodOffset으로 병합되며, 최종적으로 폰의 기분 막대(CurInstantLevel)를 상승시키거나 하락시킨다2.  
기분이 지속적으로 하락하여 '가벼운 정신 붕괴', '심각한 정신 붕괴', '극심한 정신 붕괴' 임계치 아래로 떨어지면, Pawn\_MindState의 MentalBreakerTick 함수가 활성화된다7. 정신 붕괴가 발동하면 플레이어의 조작 권한은 강제로 회수된다. 기존에 실행 중이던 작업 큐(Pawn\_JobTracker)는 즉각 폐기되며4, 주 사고 트리(MainThinkTree) 대신 '광란', '방화', '슬픈 배회' 등을 강제하는 특수 사고 트리가 폰의 행동을 탈취하여 예측 불가능한 서사를 낳게 된다.

## **관계 역학 및 소셜 상호작용 알고리즘**

폰들은 진공 상태에 고립된 객체가 아니며, Pawn\_RelationsTracker를 통해 끊임없이 타인과 관계를 맺는다8. 플레이어는 이들의 대화 내용이나 다툼을 우발적인 난수로 인식하기 쉽지만, 이면에 자리 잡은 코드는 결정론적(Deterministic) 상성 공식과 매우 복잡한 함수 곡선을 따르고 있다10.

### **호환성(Compatibility)과 태생적 상성**

두 폰이 일상적인 틱(Tick) 단위 마주침에서 긍정적(깊은 대화) 혹은 부정적(모욕, 무시) 상호작용을 할 확률의 기저에는 은닉된 '호환성(Compatibility)' 수치가 깔려 있다10. 중요한 점은 이 수치가 게임 내에서 변동하는 값이 아니라, 폰이 처음 생성될 때 부여받는 두 폰의 고유 식별자(thingIDNumber)를 바탕으로 한 의사 난수(Pseudo-random) 시드 연산을 통해 고정되는 태생적 상성이라는 것이다10.  
호환성이 높게 책정된 폰들은 약간의 관계 악화가 발생하더라도 '깊은 대화'의 발생 확률이 기하급수적으로 높아 관계를 스스로 회복하는 탄력성을 띠지만, 호환성이 마이너스(-) 대역에 놓인 폰들은 물리적 거리를 강제로 분리하지 않는 이상 지속적으로 '모욕' 상호작용을 발생시켜 결국 주먹다짐(Social Fight)으로 이어지는 악순환을 초래한다10. 나이 차이 역시 호환성에 페널티를 주어, 동일한 연령대에 속할 때 가장 높은 호환성 베이스라인이 부여된다10.

### **로맨스 알고리즘과 매력도(Attractiveness) 함수**

폰 간의 로맨스는 calculate\_attractiveness라는 매력도 산출 함수에 의해 평가되며, 반환된 0.0 \~ 1.0의 부동 소수점 값을 기초로 연인 관계 시작 시도 확률이 조율된다32. 이 로직에는 성별과 연령에 따른 고도의 비대칭적 설계가 적용되어 있다.

1. **성적 지향 필터와 확률의 비대칭성:** 이성애자 남성은 남성을 0.0의 매력도로 평가하며, 동성애자는 그 반대로 이성을 차단한다. 게임 내 로직에서 이성에게 로맨스를 시도(Romance Attempt)하는 확률은 남성이 여성보다 약 8배 높게 하드코딩되어 있다32.  
2. **연령차 선호도(Age Preference)의 성별 차이:** 매력 연산 시 적용되는 나이 상한과 하한은 성별에 따라 완전히 다르다.  
   * **남성 폰:** 16세를 최소 연령 하한으로 가지며, 자신보다 20살 이하인 파트너에게 가장 높은 매력을 느낀다. 자신보다 15살 이상 나이가 많은 상대에게는 매력도를 0으로 평가하여 로맨스를 시도하지 않는다32.  
   * **여성 폰:** 동갑이거나 자신보다 연상인 상대를 압도적으로 선호하며, 자신보다 10살 이상 연하인 상대는 매력이 없다고 평가한다. 반면 아무리 나이가 많은 상대(예: 40세 연상)라 할지라도 여성의 연산 로직에는 상한선(Cut-off) 페널티가 존재하지 않아 일정 수준의 매력도가 산출된다32.  
3. **육체적 매력과 장애의 영향:** 조작(Manipulation), 이동(Moving), 말하기 능력 중 하나라도 훼손된 폰은 신체 효율 곱연산을 통해 매력도에 극심한 페널티를 받는다32. 또한 '아름다움(+40)', '못생김(-40)' 등 외모 특성이 매력도를 직접 등락시키지만, 안면 상처 등으로 '신체적 훼손(Disfigured)' 상태에 놓인 폰은 \-15의 절대적 관계 페널티를 받음과 동시에 모든 긍정적 외모 버프 연산이 비활성화되는 치명적인 제약을 안게 된다31. 단, 폰이 '다정함(Kind)' 특성을 지닌 경우에는 이러한 상대방의 외모 매력도를 연산에서 완전히 무시하고 오직 선의의 상호작용만을 수행한다31.

이러한 로맨스와 호환성 기반 소셜 연산은 단순히 게임적 재미를 위해 삽입된 난수가 아니라, 사회학적 및 생물학적 경향성을 코드 레벨에 투영하여 미시적인 인간군상을 시뮬레이션하기 위한 설계 철학을 보여준다.

## **데이터 주도(Data-Driven) 아키텍처와 모딩(Modding) 생태계**

림월드는 설계 단계에서부터 C\# 런타임 코드와 콘텐츠 데이터를 극단적으로 분리하는 데이터 주도(Data-Driven) 설계를 고수하고 있다. 이는 게임 코어를 수정하지 않고도 외부 텍스트(XML) 파일의 수정만으로 새로운 종족, 질병, 시스템을 창조할 수 있도록 보장하며, 거대한 모딩(Modding) 커뮤니티가 번성하는 토대가 되었다33.

### **DirectXmlToObject 파싱 엔진**

게임 로딩 시 호출되는 DirectXmlLoader와 DirectXmlToObject 모듈은 단순히 XML을 읽어오는 것을 넘어, C\#의 리플렉션(Reflection)을 활용하여 XML 태그를 런타임 객체로 동적 변환(Deserialize)한다34. 예를 들어 XML에 \<hediffClass\>Hediff\_Class\</hediffClass\>라고 선언해두면, 엔진은 해당 문자열과 일치하는 C\# 클래스 인스턴스를 메모리에 할당한다24.  
이 과정에서 수백 개의 대형 오버홀 모드(예: Combat Extended, Vanilla Expanded 시리즈)가 XML 데이터를 덮어쓰거나(Patch) 새로운 Def를 주입하게 된다22. 만약 XML 구조가 손상되었거나 선언된 클래스가 C\# 어셈블리에 존재하지 않는 경우, 림월드의 DirectXmlToObject는 NullReferenceException이나 ListFromXml 에러를 뿜어내며 시스템 붕괴를 경고한다35. 디버그 로그 파일에 널리 찍히는 'Exception while executing PostLoad on null'과 같은 에러는 데이터 주도 설계에서 참조 무결성이 파괴되었을 때 나타나는 전형적 현상이다35.

### **Harmony 런타임 코드 인젝션**

단순한 데이터 추가(XML)를 넘어 행동 AI(ThinkTree), 경로 탐색 알고리즘, 혹은 하드코딩된 로맨스 계산식을 근본적으로 변경하고자 할 때, 모더들은 Harmony 프레임워크를 활용하여 C\# 런타임 코드에 직접 인젝션(Injection)을 수행한다1.

* **Prefix/Postfix 패치:** 게임 엔진의 핵심 메서드(Pawn\_HealthTracker.CheckForStateChange 또는 JobDriver.DriverTick 등)가 실행되기 전이나 후에 모더의 커스텀 코드를 실행하도록 강제한다. 이를 통해 특정 상태 이상의 틱 연산을 가로채 무적(Immortality) 메커니즘을 부여하거나43, 사회적 상호작용 확률을 재조정한다38.  
* **Transpiler 패치:** IL(Intermediate Language) 코드를 런타임에 직접 조작하여, 예를 들어 이성애 로맨스 알고리즘에 숨겨져 있던 성별 체크 로직을 변조하여 다원화된 관계가 발생하도록 함수 내부를 해킹한다25.

결과적으로, 'Pick Up And Haul'과 같은 삶의 질(QoL) 개선 모드는 폰의 인벤토리 및 JobDriver 운반 로직을 통째로 뜯어고쳐 AI 효율을 비약적으로 상승시키고13, 'Character Editor'나 'Numbers' 같은 모드들은 게임 내 은닉되어 있던 수만 가지의 Def, Hediff, 호환성 데이터들을 역설계하여 시각화된 인터페이스로 렌더링한다46. 폰 시스템이 이처럼 분리된 트래커 구조와 리플렉션 친화적 설계를 가지고 있었기에 이러한 폭넓은 인젝션과 확장성이 시스템 패닉 없이 수용될 수 있는 것이다.

## **결론**

림월드(RimWorld)의 폰(Pawn) 시스템은 전통적인 게임 개체(Entity) 아키텍처의 한계를 뛰어넘어, 모듈화된 하위 시스템(트래커)들의 유기적인 오케스트레이션으로 완성된 고도의 복합체다.  
Pawn\_JobTracker와 5계층 인공지능 프레임워크(ThinkTree 및 Toil 기반 구조)는 방대한 콜로니 내 수십, 수백 개체의 행동 연산을 단락 평가와 캐싱을 통해 효율적으로 통제한다. 신체 시스템인 BodyPartRecord와 Hediff는 단순히 숫자를 깎는 전투를 지양하고, 국소 부위 손상의 연쇄 작용과 능력치(Capacity)의 동적 재계산을 통해 해부학적 사실성을 구현해냈다. 나아가 욕구(Needs)와 다면적 기억(Thoughts) 체계는 Pawn\_MindState와 결합해 폰의 이성적 행동을 박탈하는 예측 불가의 정신 붕괴 상황을 시뮬레이션하며, 식별자(ID) 기반의 호환성 산출과 비대칭적 매력도 함수는 단순한 호감도를 넘어 인간 관계의 사회학적 기저를 코드 레벨에서 탁월하게 증명했다.  
이러한 모든 로직은 하드코딩된 블랙박스에 머물지 않고, DirectXmlToObject 파싱과 Harmony 코드 인젝션에 완전히 개방되어 있다. 요컨대, 림월드의 폰 시스템 설계는 단일 책임 원칙과 컴포넌트 패턴이 데이터 주도형 아키텍처와 만났을 때, 한 소프트웨어가 어떻게 무한히 확장 가능한 모딩 생태계의 샌드박스로 진화할 수 있는지를 보여주는 현대 게임 엔진 설계의 가장 모범적인 청사진이다.

#### **참고 자료**

1. Rimworld output log published using HugsLib \- GitHub Gist, [https://gist.github.com/30a97f0d73c8473568b251cff25d8f8d](https://gist.github.com/30a97f0d73c8473568b251cff25d8f8d)  
2. Vanilla Traits Expanded :: Discussions \- RimWorld \- Steam Community, [https://steamcommunity.com/workshop/filedetails/discussion/2296404655/600782777428842592/](https://steamcommunity.com/workshop/filedetails/discussion/2296404655/600782777428842592/)  
3. Help I cant find a way to solve my issue : r/RimWorld \- Reddit, [https://www.reddit.com/r/RimWorld/comments/1mkwrk1/help\_i\_cant\_find\_a\_way\_to\_solve\_my\_issue/](https://www.reddit.com/r/RimWorld/comments/1mkwrk1/help_i_cant_find_a_way_to_solve_my_issue/)  
4. so i might need some help here : r/RimWorld \- Reddit, [https://www.reddit.com/r/RimWorld/comments/ce2zv3/so\_i\_might\_need\_some\_help\_here/](https://www.reddit.com/r/RimWorld/comments/ce2zv3/so_i_might_need_some_help_here/)  
5. RimWorld NPC AI 系统深度解析- 躺椅可眷 \- SegmentFault 思否, [https://segmentfault.com/a/1190000047403431](https://segmentfault.com/a/1190000047403431)  
6. RW-Decompile/Verse/Pawn\_HealthTracker.cs at master \- GitHub, [https://github.com/josh-m/RW-Decompile/blob/master/Verse/Pawn\_HealthTracker.cs](https://github.com/josh-m/RW-Decompile/blob/master/Verse/Pawn_HealthTracker.cs)  
7. Anybody know how to fix this error? : r/RimWorld \- Reddit, [https://www.reddit.com/r/RimWorld/comments/lomg1l/anybody\_know\_how\_to\_fix\_this\_error/](https://www.reddit.com/r/RimWorld/comments/lomg1l/anybody_know_how_to_fix_this_error/)  
8. Relation between Pawns :: RimWorld General Discussions \- Steam Community, [https://steamcommunity.com/app/294100/discussions/0/1500126447400536815/?ctp=3](https://steamcommunity.com/app/294100/discussions/0/1500126447400536815/?ctp=3)  
9. No Random Relations \- Workshop \- Steam Community, [https://steamcommunity.com/sharedfiles/filedetails/?id=1754363066](https://steamcommunity.com/sharedfiles/filedetails/?id=1754363066)  
10. Analysis of the Social System, Compatibility, Attraction, Lovin MTB :: RimWorld General Discussions \- Steam Community, [https://steamcommunity.com/app/294100/discussions/0/1629663905418459148/](https://steamcommunity.com/app/294100/discussions/0/1629663905418459148/)  
11. A lot of pawns are just pink boxes, no idea why, all mods are current version, mods affecting body and face textures don't seem to have any effect on this : r/RimWorld \- Reddit, [https://www.reddit.com/r/RimWorld/comments/r72je3/a\_lot\_of\_pawns\_are\_just\_pink\_boxes\_no\_idea\_why/](https://www.reddit.com/r/RimWorld/comments/r72je3/a_lot_of_pawns_are_just_pink_boxes_no_idea_why/)  
12. Lag source found, need help to solve it. :: RimWorld General Discussions \- Steam Community, [https://steamcommunity.com/app/294100/discussions/0/3819669605968602020/](https://steamcommunity.com/app/294100/discussions/0/3819669605968602020/)  
13. What's your favorite quality of life mods? : r/RimWorld \- Reddit, [https://www.reddit.com/r/RimWorld/comments/1j8augk/whats\_your\_favorite\_quality\_of\_life\_mods/](https://www.reddit.com/r/RimWorld/comments/1j8augk/whats_your_favorite_quality_of_life_mods/)  
14. A bug that seemingly only happens about 30 hours in and not before : r/RimWorld \- Reddit, [https://www.reddit.com/r/RimWorld/comments/1mztajj/a\_bug\_that\_seemingly\_only\_happens\_about\_30\_hours/](https://www.reddit.com/r/RimWorld/comments/1mztajj/a_bug_that_seemingly_only_happens_about_30_hours/)  
15. Pawn wont constuct. Help pls : r/RimWorld \- Reddit, [https://www.reddit.com/r/RimWorld/comments/1cedahn/pawn\_wont\_constuct\_help\_pls/](https://www.reddit.com/r/RimWorld/comments/1cedahn/pawn_wont_constuct_help_pls/)  
16. JobDriver exception, pawn wont finish mech gestation : r/RimWorld \- Reddit, [https://www.reddit.com/r/RimWorld/comments/13uqn9s/jobdriver\_exception\_pawn\_wont\_finish\_mech/](https://www.reddit.com/r/RimWorld/comments/13uqn9s/jobdriver_exception_pawn_wont_finish_mech/)  
17. all pawns unable to do any job and idly stand around unless drafted : r/RimWorld \- Reddit, [https://www.reddit.com/r/RimWorld/comments/1g9msuc/all\_pawns\_unable\_to\_do\_any\_job\_and\_idly\_stand/](https://www.reddit.com/r/RimWorld/comments/1g9msuc/all_pawns_unable_to_do_any_job_and_idly_stand/)  
18. RimWorld-MendAndRecycle/Source/JobDriver\_Mend.cs at master \- GitHub, [https://github.com/notfood/RimWorld-MendAndRecycle/blob/master/Source/JobDriver\_Mend.cs](https://github.com/notfood/RimWorld-MendAndRecycle/blob/master/Source/JobDriver_Mend.cs)  
19. RimWorld-MendAndRecycle/Source/JobDriver\_Recycle.cs at, [https://github.com/notfood/RimWorld-MendAndRecycle/blob/master/Source/JobDriver\_Recycle.cs](https://github.com/notfood/RimWorld-MendAndRecycle/blob/master/Source/JobDriver_Recycle.cs)  
20. living cumbucket Error · Issue \#129 · vegapnk/RJW-Genes \- GitHub, [https://github.com/vegapnk/RJW-Genes/issues/129](https://github.com/vegapnk/RJW-Genes/issues/129)  
21. Hi, how can i fix this error? any help is so appreciated. : r/RimWorld \- Reddit, [https://www.reddit.com/r/RimWorld/comments/16cs14v/hi\_how\_can\_i\_fix\_this\_error\_any\_help\_is\_so/](https://www.reddit.com/r/RimWorld/comments/16cs14v/hi_how_can_i_fix_this_error_any_help_is_so/)  
22. Lots of "added injury to x but should be impossible to hit it" after installing Combat Extended : r/RimWorld \- Reddit, [https://www.reddit.com/r/RimWorld/comments/1ajdokw/lots\_of\_added\_injury\_to\_x\_but\_should\_be/](https://www.reddit.com/r/RimWorld/comments/1ajdokw/lots_of_added_injury_to_x_but_should_be/)  
23. can't install peg legs, even with dev mode : r/RimWorld \- Reddit, [https://www.reddit.com/r/RimWorld/comments/akog2d/cant\_install\_peg\_legs\_even\_with\_dev\_mode/](https://www.reddit.com/r/RimWorld/comments/akog2d/cant_install_peg_legs_even_with_dev_mode/)  
24. RimworldModdingFiles/Defs/HediffDefs/Hediffs.xml at master \- GitHub, [https://github.com/RimWorldMod/RimworldModdingFiles/blob/master/Defs/HediffDefs/Hediffs.xml](https://github.com/RimWorldMod/RimworldModdingFiles/blob/master/Defs/HediffDefs/Hediffs.xml)  
25. Rimworld output log published using HugsLib · GitHub \- Gist, [https://gist.github.com/HugsLibRecordKeeper/e363e5cd601c0a3145db0fc43180a9a7](https://gist.github.com/HugsLibRecordKeeper/e363e5cd601c0a3145db0fc43180a9a7)  
26. Help needed: Needs not decaying :: RimWorld General Discussions \- Steam Community, [https://steamcommunity.com/app/294100/discussions/0/3013438019106842618/](https://steamcommunity.com/app/294100/discussions/0/3013438019106842618/)  
27. Pawns needs aren't decreasing or increasing, getting this error every tick : r/RimWorld, [https://www.reddit.com/r/RimWorld/comments/pl5s9c/pawns\_needs\_arent\_decreasing\_or\_increasing/](https://www.reddit.com/r/RimWorld/comments/pl5s9c/pawns_needs_arent_decreasing_or_increasing/)  
28. thought error and hub disappearing :: RimWorld General Discussions \- Steam Community, [https://steamcommunity.com/app/294100/discussions/0/3764481749062939787/](https://steamcommunity.com/app/294100/discussions/0/3764481749062939787/)  
29. Trying to find which mod is making all pawn needs disappear : r/RimWorld \- Reddit, [https://www.reddit.com/r/RimWorld/comments/1hq7ouf/trying\_to\_find\_which\_mod\_is\_making\_all\_pawn\_needs/](https://www.reddit.com/r/RimWorld/comments/1hq7ouf/trying_to_find_which_mod_is_making_all_pawn_needs/)  
30. Relationships — RimWorld Alpha 17 Social System SCIENCE\!\!\! \- YouTube, [https://www.youtube.com/watch?v=kFikPmkoeS8](https://www.youtube.com/watch?v=kFikPmkoeS8)  
31. Improving Pawn Relations With Each Other : r/RimWorld \- Reddit, [https://www.reddit.com/r/RimWorld/comments/15ua943/improving\_pawn\_relations\_with\_each\_other/](https://www.reddit.com/r/RimWorld/comments/15ua943/improving_pawn_relations_with_each_other/)  
32. How RimWorld's Code Defines Strict Gender Roles | Rock Paper Shotgun, [https://www.rockpapershotgun.com/rimworld-code-analysis](https://www.rockpapershotgun.com/rimworld-code-analysis)  
33. Creating Your First RimWorld Mod | PDF | Computer File | Xml \- Scribd, [https://www.scribd.com/document/909521059/Let-s-Make-a-Rimworld-Mod](https://www.scribd.com/document/909521059/Let-s-Make-a-Rimworld-Mod)  
34. Rimworld output log published using HugsLib \- GitHub Gist, [https://gist.github.com/de8474ed496fa8f143eee35bcc4359b7](https://gist.github.com/de8474ed496fa8f143eee35bcc4359b7)  
35. Rimworld output log published using HugsLib \- GitHub Gist, [https://gist.github.com/9aeb6eec3c42755947c1e28f24dc679b](https://gist.github.com/9aeb6eec3c42755947c1e28f24dc679b)  
36. Rimworld output log published using HugsLib · GitHub, [https://gist.github.com/HugsLibRecordKeeper/a9ce18232e2ef1b450bd2226fa52b6b8](https://gist.github.com/HugsLibRecordKeeper/a9ce18232e2ef1b450bd2226fa52b6b8)  
37. Ultimate Storytelling Simulator \- RimWorld \- Steam Community, [https://steamcommunity.com/sharedfiles/filedetails/?id=3477374924](https://steamcommunity.com/sharedfiles/filedetails/?id=3477374924)  
38. Rimworld output log published using HugsLib Standalone Log Publisher \- Github-Gist, [https://gist.github.com/HugsLibRecordKeeper/da1f45e80bec0f0bab6f5718cc4f3aae](https://gist.github.com/HugsLibRecordKeeper/da1f45e80bec0f0bab6f5718cc4f3aae)  
39. Rimworld output log published using HugsLib \- GitHub Gist, [https://gist.github.com/0c2e816331dac5d2245be92a47ee35ba](https://gist.github.com/0c2e816331dac5d2245be92a47ee35ba)  
40. Rimworld output log published using HugsLib \- GitHub Gist, [https://gist.github.com/45d48f8feaec81e278a27038759ca617](https://gist.github.com/45d48f8feaec81e278a27038759ca617)  
41. Rimworld output log published using HugsLib \- GitHub Gist, [https://gist.github.com/9bd76722eb5c22cea16148d0359f0e9b](https://gist.github.com/9bd76722eb5c22cea16148d0359f0e9b)  
42. Android tiers :: Discussions \- RimWorld \- Steam Community, [https://steamcommunity.com/workshop/filedetails/discussion/1386412863/2828702373011092512/?l=english\&ctp=34](https://steamcommunity.com/workshop/filedetails/discussion/1386412863/2828702373011092512/?l=english&ctp=34)  
43. Immortals :: Discussions \- Steam Community, [https://steamcommunity.com/workshop/filedetails/discussion/1984905966/4015478340395656358/?ctp=2](https://steamcommunity.com/workshop/filedetails/discussion/1984905966/4015478340395656358/?ctp=2)  
44. Rimworld output log published using HugsLib · GitHub, [https://gist.github.com/HugsLibRecordKeeper/8371a3468e1ac67655e5904564112981](https://gist.github.com/HugsLibRecordKeeper/8371a3468e1ac67655e5904564112981)  
45. Rimworld output log published using HugsLib Standalone Log Publisher \- GitHub Gist, [https://gist.github.com/HugsLibRecordKeeper/c0396eb2d7a9c8935f495c97fc8eb798](https://gist.github.com/HugsLibRecordKeeper/c0396eb2d7a9c8935f495c97fc8eb798)  
46. Is there a way to see a chronological list of pawns? : r/RimWorld \- Reddit, [https://www.reddit.com/r/RimWorld/comments/1tmuxg0/is\_there\_a\_way\_to\_see\_a\_chronological\_list\_of/](https://www.reddit.com/r/RimWorld/comments/1tmuxg0/is_there_a_way_to_see_a_chronological_list_of/)  
47. Character Editor \- Steam Workshop, [https://steamcommunity.com/sharedfiles/filedetails/?id=1874644848](https://steamcommunity.com/sharedfiles/filedetails/?id=1874644848)
# 봇픽던 누적 5만 원 비용 중지 장치

## 기준

- 프로젝트: `botpikdun` (597832011642)
- 예산: `botpikdun-total-50000-krw`
- 예산 ID: `bffe184a-88d3-4f06-843b-b4725503bc45`
- 기간: 2026-09-13부터 종료일 없이 누적. 월초에 초기화하지 않는다.
- 금액: KRW 50,000. 모든 서비스 포함, 할인·크레딧 차감 전 금액.
- 이메일: 결제 관리자/사용자에게 60%, 80%, 100% (3만/4만/5만 원).
- Pub/Sub: `projects/botpikdun/topics/botpikdun-budget`
- 중지 대상: 서울 `asia-northeast3-a/b/c` 중 이름이 정확히 `botpikdun`인 VM.

## 동작

예산 통지 → Pub/Sub → 비공개 Cloud Run 함수 `botpikdun-budget-guard`.
예산 ID·이름·통화·예산 금액을 확인하고 누적 비용이 50,000원 이상이면 VM 중지 API를 호출한다.
프로젝트·VM 이름·서울 영역은 코드에 고정되어 있고 통지 본문으로 바꿀 수 없다.
런타임 서비스 계정 권한은 `compute.instances.get` / `compute.instances.stop`뿐이다.
별도 계정으로 빌드와 이벤트 전달을 수행한다. 함수 최소 인스턴스 0, 최대 1.

## 제한

**정확한 결제 상한이 아니다.** Billing 집계/통지 지연 중 추가 비용이 발생할 수 있다.
VM 중지는 디스크·고정 외부 IP·빌드 이미지 보관료 등을 없애지 않는다.
중지 뒤 VM을 수동 재시작하면 다음 예산 통지가 도착할 때까지 다시 실행될 수 있다.
이 장치는 트래픽 바이트 제한이나 서버의 동시 판 수 제한을 대신하지 않는다.
같은 결제 계정의 다른 프로젝트도 쿠폰을 사용하므로 봇픽던 예산만으로 쿠폰 잔액을 보장할 수 없다.
계정 전체 기존 월 30만 원 예산은 변경하지 않았다.

## 설치와 검증

Cloud Shell에서 이 폴더를 준비한 뒤 `bash install.sh`.
콘솔에서 예산과 Pub/Sub 주제를 먼저 생성해야 한다. 예산을 다시 만들면 ID도 갱신해야 한다.
로컬 검증: `python -m unittest discover -s scripts/vm/budget-guard -p test_guard.py -v`.

2026-09-13: 예산과 Pub/Sub 생성 확인, 로컬 4개 검사 통과. 함수 배포 `ACTIVE` 확인.
실제 Pub/Sub 시험 통지 처리도 확인:
- 49,999원: `BUDGET_GUARD: below threshold or unrelated notification` (14:00:53 UTC)
- 50,000원: `BUDGET_GUARD: stop requested []` (14:01:00 UTC, 현재 VM 없음)
- 초기 IAM 전파 중 403이 있었지만 재전송으로 두 메시지 모두 정상 처리됨.
- Cloud Run 호출 권한은 `budget-guard-events` 계정만 보유하며 `allUsers` 공개 권한 없음.
- 빌드 ID: `d3e04712-6f83-45bd-a411-c0f1222b5d01` (SUCCESS)

2026-09-13 실제 VM 시험도 완료:
- 시험 메시지 ID `21696555455679935` (실제 청구 금액 변경 없음).
- 14:29:07 UTC 함수 로그: `BUDGET_GUARD: stop requested ["asia-northeast3-a/botpikdun"]`.
- VM `STOPPING` → `TERMINATED` 확인 후 수동 재시작.
- 고정 IP `34.47.94.178` 유지, 앱/Caddy 자동 시작, 로컬 상태·화면 200 확인.

VM을 교체하거나 권한을 바꾸면 **시험 메시지로 실제 중지 및 TERMINATED 상태를 다시 확인한다.**
시험은 진행 중인 판이 없는 상태에서 수행한다. 시험용 Pub/Sub 메시지는 실제 청구 금액을 바꾸지 않는다.

```bash
gcloud pubsub topics publish botpikdun-budget --project=botpikdun \
  --attribute=budgetId=bffe184a-88d3-4f06-843b-b4725503bc45 \
  --message='{"budgetDisplayName":"botpikdun-total-50000-krw","currencyCode":"KRW","budgetAmount":50000,"costAmount":50000}'
gcloud compute instances list --project=botpikdun --filter='name=botpikdun' --format='table(name,zone,status)'
```

공식 문서: https://docs.cloud.google.com/billing/docs/how-to/control-usage

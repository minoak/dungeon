"""GCP 예산 통지로 봇픽던 VM만 중지한다. 금액 집계 지연은 제거하지 못한다."""
import base64
import json
import logging
import os
from decimal import Decimal, InvalidOperation

PROJECT = "botpikdun"
NAME = "botpikdun"
BUDGET = "botpikdun-total-50000-krw"
LIMIT = Decimal("50000")


def should_stop(payload):
    """다른 예산/통화/잘못된 금액은 중지 명령으로 받아들이지 않는다."""
    if payload.get("budgetDisplayName") != BUDGET or payload.get("currencyCode") != "KRW":
        return False
    try:
        amount = Decimal(str(payload["costAmount"]))
        budget = Decimal(str(payload["budgetAmount"]))
    except (KeyError, InvalidOperation, ValueError):
        return False
    return amount.is_finite() and budget == LIMIT and amount >= LIMIT


def stop_targets(session):
    """서울의 정확히 botpikdun이라는 VM만 대상. 삭제/재시작 권한은 쓰지 않는다."""
    root = f"https://compute.googleapis.com/compute/v1/projects/{PROJECT}"
    stopped = []
    for suffix in ("a", "b", "c"):
        zone = f"asia-northeast3-{suffix}"
        url = f"{root}/zones/{zone}/instances/{NAME}"
        response = session.get(url, timeout=20)
        if response.status_code == 404:
            continue
        response.raise_for_status()
        status = response.json()["status"]
        if status in ("TERMINATED", "STOPPING", "SUSPENDED"):
            continue
        response = session.post(url + "/stop", timeout=20)
        response.raise_for_status()
        stopped.append(f"{zone}/{NAME}")
    return stopped


def limit_use(event):
    """비공개 Pub/Sub CloudEvent 진입점. 통지 본문 전체는 로그에 남기지 않는다."""
    message = event.data["message"]
    expected_id = os.environ["BUDGET_ID"]
    if message.get("attributes", {}).get("budgetId") != expected_id:
        logging.warning("IGNORED: unexpected budgetId")
        return
    payload = json.loads(base64.b64decode(message["data"], validate=True))
    if not should_stop(payload):
        print("BUDGET_GUARD: below threshold or unrelated notification", flush=True)
        return
    import google.auth
    from google.auth.transport.requests import AuthorizedSession
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    with AuthorizedSession(credentials) as session:
        targets = stop_targets(session)
    print("BUDGET_GUARD: stop requested " + json.dumps(targets), flush=True)


# Functions Framework는 배포 환경에서만 필요하다. 판단 로직은 표준 라이브러리로 시험한다.
try:
    import functions_framework
except ImportError:
    pass
else:
    limit_use = functions_framework.cloud_event(limit_use)

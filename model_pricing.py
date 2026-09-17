# -*- coding: utf-8 -*-
"""공식 일반 텍스트 API 단가(USD / 100만 토큰). 계산용 공개 정보만, API 호출 없음."""
from datetime import date

CHECKED = "2026-09-17"
SOURCES = {
    "gemini_api": "https://ai.google.dev/gemini-api/docs/pricing",
    "anthropic_api": "https://platform.claude.com/docs/en/about-claude/pricing",
    "openai_api": "https://developers.openai.com/api/docs/pricing",
}
# (입력, 출력). 캐시 할인·무료 할당·배치·세금 제외. 확인 못 한 모델은 None.
RATES = {
    "gemini-3.8-flash": (0.75, 3.75),
    "gemini-3.7-flash": (0.75, 3.75),
    "gemini-3.6-flash": (0.75, 3.75),
    "gemini-3.5-flash": (1.5, 9),
    "gemini-3.5-flash-lite": (0.3, 2.5),
    "gemini-3.1-flash-lite": (0.25, 1.5),
    "gemini-3.1-pro-preview": (2, 12),
    "gemini-3-flash-preview": (0.5, 3),
    "gemini-2.5-flash": (0.3, 2.5),
    "claude-haiku-4-5-20251001": (1, 5),
    "claude-sonnet-5": (2, 10),
    "claude-opus-5": (5, 25),
    "claude-fable-5-1": (10, 50),
    "gpt-5.6-terra": (2, 12),
    "gpt-5.6-luna": (0.2, 1.2),
    "gpt-5.6-sol": (4, 20),
    "gpt-6-astra": (10, 50),
}


def price_info(provider, mid, today=None):
    """기한이 있는 할인은 날짜로 전환하고, 긴 입력의 별도 단가도 화면에 전달한다."""
    today = today or date.today()
    rate = RATES.get(mid)
    if rate is None:
        return None
    info = {"input": rate[0], "output": rate[1], "currency": "USD", "checked": CHECKED,
            "source": SOURCES[provider]}
    if mid in ("gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash"):
        if today >= date(2027, 1, 1):
            info.update(input=1.5, output=7.5)
        else:
            info["note"] = "2026-12-31까지 할인 단가"
    if mid == "gemini-3.1-pro-preview":
        info["long"] = {"above": 200000, "input": 4, "output": 18}
    if provider == "openai_api":
        info["long"] = {"above": 272000, "input": rate[0] * 2, "output": rate[1] * 1.5}
    if mid == "gpt-5.6-sol":
        info["note"] = "프로모션 단가 · 2026-11-21 이후 공식 가격 재확인"
        if today > date(2026, 11, 21):
            return None  # 후속 가격을 추측하지 않는다.
    return info

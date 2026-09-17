# -*- coding: utf-8 -*-
"""D80 모델 배선의 공통 설정. 엔진 import·키 로딩·네트워크 없이 론처에서도 읽는다."""
import os
import re
from urllib.parse import urlsplit

HTTP_BACKENDS = ("gemini_api", "anthropic_api", "openai_api")
BACKENDS = ("claude_cli", "anthropic_api", "gemini_api", "openai_api", "dummy")
KEY_ENV = {"gemini_api": "GEMINI_API_KEY", "anthropic_api": "ANTHROPIC_API_KEY",
           "openai_api": "OPENAI_API_KEY"}
# 2026-09-17 공식 문서 확인. 출처·실측 한계: docs/model_wiring_2026-09-17.md
MODEL_IDS = {
    "anthropic_api": {"haiku": "claude-haiku-4-5-20251001", "sonnet": "claude-sonnet-5"},
    "gemini_api": {"haiku": "gemini-3.8-flash", "sonnet": "gemini-3.1-pro-preview"},
    "openai_api": {"haiku": "gpt-5.6-terra", "sonnet": "gpt-5.6-sol"},
}
OPENAI_DEFAULT_BASE = "https://api.openai.com/v1"
MODEL_ENV = ("DUNGEON_MODEL_HAIKU", "DUNGEON_MODEL_SONNET")
LEGACY_MODEL_ENV = {"gemini_api": "DUNGEON_GEMINI_MODEL", "anthropic_api": "DUNGEON_ANTHROPIC_MODEL"}


def model_id(provider, alias):
    """별칭 번역은 이 한 곳. 공통 슬롯 설정 > 이전 회사별 설정 > 기본값."""
    if alias not in ("haiku", "sonnet"):
        return None
    return (os.environ.get("DUNGEON_MODEL_" + alias.upper(), "").strip()
            or os.environ.get(LEGACY_MODEL_ENV.get(provider, ""), "").strip()
            or MODEL_IDS.get(provider, {}).get(alias))


def clean_model(value):
    """모델 이름은 경로·쿼리 주입 없이 회사/모델 표기까지 허용한다."""
    if not isinstance(value, str) or len(value) > 200:
        raise ValueError("모델 ID는 200자 이내의 문자열이어야 한다")
    value = value.strip()
    if value and (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]*", value)
                  or ".." in value or "://" in value):
        raise ValueError("모델 ID에는 영문·숫자·점·밑줄·콜론·슬래시·하이픈만 쓸 수 있다")
    return value


def openai_base_url():
    """주소는 로컬 .env/서버 운영자 설정만. 브라우저 요청으로 받지 않는다."""
    base = (os.environ.get("OPENAI_BASE_URL") or OPENAI_DEFAULT_BASE).strip().rstrip("/")
    p = urlsplit(base)
    if (p.scheme not in ("http", "https") or not p.hostname or p.username or p.password
            or p.query or p.fragment or any(c.isspace() for c in base)):
        raise ValueError("InvalidBaseURL")
    return base


def provider_catalog():
    """비밀값 없이 화면에 기본 모델과 공개 API 목적지만 알린다."""
    return {p: {"models": dict(MODEL_IDS[p])} for p in HTTP_BACKENDS}

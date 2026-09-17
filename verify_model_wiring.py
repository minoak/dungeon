# -*- coding: utf-8 -*-
"""D80 68번째 게이트: HTTP는 전부 대역, API 0콜. 키·모델·계정·새 판·이어가기 계약."""
import contextlib
import http.client
import inspect
import io
import json
import os
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

import requests
import brain_config as C
import brains as B
import launcher as L
import server as S
import accounts as A
from datetime import date
from model_pricing import price_info


class Response:
    def __init__(self, status, body):
        self.status_code, self.body = status, body

    def json(self):
        return self.body


def run():
    calls = []
    reply = [200, {}]

    def post(url, **kw):
        calls.append((url, kw, json.loads(kw["data"])))
        return Response(*reply)

    def get(url, **kw):
        calls.append((url, kw))
        return Response(*reply)

    clean = {k: v for k, v in os.environ.items() if not k.startswith(("DUNGEON_", "OPENAI_", "ANTHROPIC_", "GEMINI_"))}
    with patch.dict(os.environ, clean, clear=True), patch.object(requests, "post", post), patch.object(requests, "get", get):
        for provider, choices in C.MODEL_CHOICES.items():
            for mid, _ in choices:
                price = price_info(provider, mid, date(2026, 9, 17))
                assert price["input"] > 0 and price["output"] > 0 and price["source"].startswith("https://")
        assert price_info("gemini_api", "gemini-3.8-flash", date(2026, 12, 31))["input"] == 0.75
        assert price_info("gemini_api", "gemini-3.8-flash", date(2027, 1, 1))["input"] == 1.5
        assert price_info("openai_api", "gpt-5.6-sol", date(2026, 11, 22)) is None
        assert price_info("openai_api", "custom") is None
        print("PASS 가격 17종·할인 기한·미확인 가격")
        assert list(inspect.signature(B._call_claude).parameters) == ["prompt", "model"]
        for provider in C.HTTP_BACKENDS:
            os.environ["DUNGEON_BRAIN_BACKEND"] = provider
            n = len(calls)
            assert B._call_claude("p", "haiku") == ("", "호출 실패 NoAPIKey")
            assert len(calls) == n
            key = "FAKE-" + provider + "-012345678901234567890"
            os.environ[C.KEY_ENV[provider]] = key
            expected = {
                "gemini_api": {"candidates": [{"content": {"parts": [{"text": " ok "}]}, "finishReason": "STOP"}], "usageMetadata": {"promptTokenCount": 7, "candidatesTokenCount": 3}},
                "anthropic_api": {"content": [{"type": "text", "text": " ok "}], "usage": {"input_tokens": 7, "output_tokens": 3}, "stop_reason": "end_turn"},
                "openai_api": {"choices": [{"message": {"content": " ok "}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 7, "completion_tokens": 3}},
            }[provider]
            reply[:] = [200, expected]
            assert B._call_claude("한글 프롬프트", "haiku") == ("ok", None)
            url, kw, body = calls[-1]
            assert kw["allow_redirects"] is False and kw["timeout"] == (5, 60)
            assert key not in url and key not in json.dumps(body)
            assert B._TLS.usage["in_tok"] == 7 and B._TLS.usage["out_tok"] == 3
            if provider == "gemini_api":
                assert url == B.API_URL_GEMINI % C.MODEL_IDS[provider]["haiku"]
                assert kw["headers"]["x-goog-api-key"] == key
                assert body["contents"] == [{"parts": [{"text": "한글 프롬프트"}]}]
                assert body["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "low"}
            else:
                assert body["model"] == C.MODEL_IDS[provider]["haiku"]
                assert body["messages"] == [{"role": "user", "content": "한글 프롬프트"}]
                if provider == "anthropic_api":
                    assert url == B.API_URL_ANTHROPIC and kw["headers"]["x-api-key"] == key
                    assert kw["headers"]["anthropic-version"] == "2023-06-01"
                else:
                    assert url == C.OPENAI_DEFAULT_BASE + "/chat/completions"
                    assert kw["headers"]["Authorization"] == "Bearer " + key
                    assert body["max_completion_tokens"] == 1024 and body["reasoning_effort"] == "none"
            if provider == "anthropic_api":
                assert B._call_claude("p", "sonnet") == ("ok", None)
                assert calls[-1][2]["thinking"] == {"type": "disabled"}
            choices = C.provider_catalog()[provider]["choices"]
            assert len({c["id"] for c in choices}) == len(choices)
            assert all(mid in [c["id"] for c in choices] for mid in C.MODEL_IDS[provider].values())
            for choice in choices:
                mid = choice["id"]
                assert C.clean_model(mid) == mid and choice["label"]
                with patch.dict(os.environ, {"DUNGEON_MODEL_HAIKU": mid}):
                    assert B._call_claude("p", "haiku") == ("ok", None)
                    url, _, body = calls[-1]
                    assert mid in url if provider == "gemini_api" else body["model"] == mid
                    if provider == "gemini_api":
                        think = body["generationConfig"]["thinkingConfig"]
                        assert think == ({"thinkingBudget": 0} if mid == "gemini-2.5-flash" else
                                         {"thinkingLevel": "minimal" if mid in ("gemini-3-flash-preview", "gemini-3.1-flash-lite") else "low"})
                    elif mid == "claude-fable-5-1":
                        assert body["thinking"] == {"type": "adaptive"}
                        assert body["output_config"] == {"effort": "low"} and body["max_tokens"] == 4096
                    elif mid == "claude-opus-5":
                        assert body["thinking"] == {"type": "disabled"}
                    elif provider == "openai_api":
                        assert body["reasoning_effort"] == ("low" if mid == "gpt-6-astra" else "none")
                        assert body["max_completion_tokens"] == (4096 if mid == "gpt-6-astra" else 1024)
                    with patch.dict(os.environ, {"DUNGEON_BRAIN_MAXTOK": "2048"}):
                        B._call_claude("p", "haiku")
                        body = calls[-1][2]
                        budget = body["generationConfig"]["maxOutputTokens"] if provider == "gemini_api" else body.get("max_completion_tokens", body.get("max_tokens"))
                        assert budget == 2048
            with patch.dict(os.environ, {"DUNGEON_MODEL_HAIKU": "my-model", "DUNGEON_MODEL_SONNET": "large-model"}):
                B._call_claude("p", "sonnet")
                url, kw, body = calls[-1]
                assert "large-model" in (url if provider == "gemini_api" else body["model"])
            reply[:] = [200, {}]
            assert B._call_claude("p", "haiku")[1].startswith("빈 응답 rc=200")
            reply[:] = [401, {"error": {"type": "authentication_error", "status": "UNAUTHENTICATED", "message": key}}]
            label = B._call_claude("p", "haiku")[1]
            assert label.startswith("빈 응답 rc=401") and key not in label
            with patch.object(requests, "post", side_effect=requests.exceptions.Timeout(key)):
                assert B._call_claude("p", "haiku")[1] == "타임아웃 60s"
            with patch.object(requests, "post", side_effect=requests.RequestException(key)):
                assert B._call_claude("p", "haiku")[1] == "호출 실패 RequestException"
            reply[:] = [200, {}]
            assert S.key_alive(key, provider)
            assert calls[-1][1]["allow_redirects"] is False
            if provider == "anthropic_api":
                assert calls[-1][0] == "https://api.anthropic.com/v1/models" and calls[-1][1]["headers"]["x-api-key"] == key
            elif provider == "gemini_api":
                assert calls[-1][0] == S.MODELS_URL and calls[-1][1]["headers"]["x-goog-api-key"] == key
            else:
                assert calls[-1][0] == C.OPENAI_DEFAULT_BASE + "/models" and calls[-1][1]["headers"]["Authorization"] == "Bearer " + key
            reply[0] = 403
            assert S.key_alive(key, provider) is False
            for code in (302, 429, 500):
                reply[0] = code
                try:
                    S.key_alive(key, provider)
                    raise AssertionError("unavailable must fail closed")
                except S.KeyCheckUnavailable:
                    pass
            os.environ.pop(C.KEY_ENV[provider])
        print("PASS HTTP 3회사 요청·파싱·빈 응답·4xx·타임아웃·인증 리다이렉트 차단")
        with patch.dict(os.environ, {"DUNGEON_BRAIN_BACKEND": "openai_api", "OPENAI_API_KEY": "local", "OPENAI_BASE_URL": "http://localhost:11434/v1/", "DUNGEON_MODEL_HAIKU": "org/model:tag"}):
            assert C.provider_catalog()["openai_api"]["choices"] == []
            reply[:] = [200, {"choices": [{"message": {"content": "yes"}}]}]
            assert B._call_claude("p", "haiku") == ("yes", None)
            assert calls[-1][0] == "http://localhost:11434/v1/chat/completions"
            assert calls[-1][2]["model"] == "org/model:tag" and "max_tokens" in calls[-1][2]
            with patch.dict(os.environ, {"DUNGEON_MODEL_HAIKU": "gpt-6-astra"}):
                B._call_claude("p", "haiku")
                assert "reasoning_effort" not in calls[-1][2] and calls[-1][2]["max_tokens"] == 1024
            for malformed in (None, [], {"choices": "bad"}, {"choices": [None]}, {"choices": [{"message": {"content": []}}]}):
                reply[1] = malformed
                assert B._call_claude("p", "haiku")[1].startswith("빈 응답 rc=200")
            reply[:] = [200, {}]
            assert S.key_alive("local", "openai_api")
            assert calls[-1][0] == "http://localhost:11434/v1/models"
            with patch.object(B, "API_CALL_LIMIT", 1), patch.object(B, "_api_call_count", 1):
                n = len(calls)
                assert B._call_claude("p", "haiku")[1] == "호출 실패 ApiCallLimit"
                assert len(calls) == n
        print("PASS 호환 주소·모델 덮어쓰기·불량 응답·전송 상한")
        with tempfile.TemporaryDirectory(prefix="wl_model_") as tmp:
            a = A.Accounts(tmp)
            old = a.create(a.fingerprint("legacy"))
            old["keys"][0].pop("provider")
            assert a.public(old)["keys"][0]["provider"] == "gemini_api"
            for p in C.HTTP_BACKENDS:
                data = a.link(old["id"], a.fingerprint(p), p)
                assert a.public(data)["keys"][-1]["provider"] == p
            assert "fp" not in a.public(data)["keys"][0]
        for provider in ("dummy", "claude_cli", [], None, "unknown"):
            try:
                S.Sessions.provider_name(provider)
                raise AssertionError("invalid provider accepted")
            except L.BadRequest:
                pass
        for model in ([], None, "../x", "x?key=secret", "https://evil", "x\nY", "x" * 201):
            try:
                C.clean_model(model)
                raise AssertionError("invalid model accepted")
            except ValueError:
                pass
        assert S.Sessions.key_shape("sk-" + "a" * 250, "openai_api")
        print("PASS 회사·모델 검증·긴 키·구형 계정 태그")
        # 공개 HTTP → 실제 Runner.start → Popen 직전의 env까지 검사(러너 실행·생성 API는 0).
        captured = []
        class Finished:
            pid = 123456
            def poll(self):
                return 0

        def popen(args, **kw):
            captured.append(kw["env"])
            return Finished()

        with tempfile.TemporaryDirectory(prefix="wl_model_local_") as tmp, patch.object(L.subprocess, "Popen", popen):
            runner = L.Runner(L.HERE, os.path.join(tmp, "state"), os.path.join(tmp, "runs"))
            party = os.path.join(L.HERE, "party.json")
            parent = {k: "local-parent-secret" for k in C.KEY_ENV.values()}
            with patch.dict(os.environ, parent):
                for provider in C.HTTP_BACKENDS:
                    key = "fake-local-screen-" + provider
                    opts = {"provider": provider, "key": key, "party": "default"}
                    runner.start(opts, party)
                    assert opts["key"] == key  # 호출자의 입력을 변경하지 않는다.
                    assert all(captured[-1][name] == (key if p == provider else "") for p, name in C.KEY_ENV.items())
                    assert captured[-1]["DUNGEON_BRAIN_FALLBACK"] == ""
                    assert all(os.environ[k] == v for k, v in parent.items())
                    meta = {"seed": 42, "turn_last": 5, "backend": provider}
                    with patch.object(L.Runner, "resumable", return_value=meta):
                        runner.start({"resume": True, "key": key + "-resume"}, party)
                        assert captured[-1][C.KEY_ENV[provider]] == key + "-resume"
                    assert "key" not in runner._read_run_opts()["opts"]
                    for path in Path(tmp).rglob("*"):
                        if path.is_file():
                            assert key.encode() not in path.read_bytes()
                runner.start({"provider": "gemini_api", "key": "", "party": "default"}, party)
                assert captured[-1]["GEMINI_API_KEY"] == parent["GEMINI_API_KEY"]
            for bad in (None, [], "with space", "x" * 1025):
                try:
                    runner.start({"provider": "gemini_api", "key": bad, "party": "default"}, party)
                    raise AssertionError("bad local key accepted")
                except L.BadRequest:
                    pass
            result = runner.start({"provider": "gemini_api", "model": "first-model", "party": "default"}, party)
            assert result["brain"] == "gemini_api"
            meta = {"seed": 42, "turn_last": 5, "backend": "gemini_api"}
            with patch.object(L.Runner, "resumable", return_value=meta):
                result = runner.start({"resume": True, "provider": "openai_api"}, party)
                assert result["brain"] == "openai_api"
                assert captured[-1]["DUNGEON_MODEL_HAIKU"] == ""   # 이전 회사 모델 제거
                result = runner.start({"resume": True, "brain": "anthropic_api", "model": "third-model"}, party)
                assert result["brain"] == "anthropic_api"
                assert runner._read_run_opts()["opts"]["provider"] == "anthropic_api"
                assert captured[-1]["DUNGEON_MODEL_HAIKU"] == "third-model"
        print("PASS 로컬 provider/brain 요청·이어가기 회사 변경·모델 보관")

        with tempfile.TemporaryDirectory(prefix="wl_byok_") as tmp, patch.object(L.subprocess, "Popen", popen), contextlib.redirect_stderr(io.StringIO()):
            srv = S.make_public_server("127.0.0.1", 0, data_dir=tmp, starts_per_hour=100, key_check=lambda key, provider: True)
            thread = threading.Thread(target=srv.serve_forever, daemon=True)
            thread.start()
            cookie = ""
            def request(path, body=None):
                nonlocal cookie
                conn = http.client.HTTPConnection("127.0.0.1", srv.server_port, timeout=10)
                conn.request("POST" if body is not None else "GET", path,
                             json.dumps(body) if body is not None else None,
                             {"Content-Type": "application/json", "Cookie": cookie})
                response = conn.getresponse()
                cookie = (response.getheader("Set-Cookie") or cookie).split(";", 1)[0]
                raw = response.read()
                conn.close()
                return response.status, json.loads(raw)
            try:
                _, presets = request("/api/presets")
                assert set(presets["providers"]) == set(C.HTTP_BACKENDS)
                assert sum(len(p["choices"]) for p in presets["providers"].values()) == 17
                parent = {k: "parent-secret" for k in C.KEY_ENV.values()}
                parent.update({k: "parent-model" for k in (*C.MODEL_ENV, *C.LEGACY_MODEL_ENV.values())})
                parent["DUNGEON_BRAIN_FALLBACK"] = "anthropic_api"
                with patch.dict(os.environ, parent):
                    for provider in C.HTTP_BACKENDS:
                        key = "fake-key-" + provider + "-12345678901234567890"
                        status, account = request("/api/login", {"provider": provider, "key": key})
                        assert status == 200 and account["provider"] == provider
                        assert account["account"]["keys"][0]["provider"] == provider
                        assert request("/api/me")[1]["account"]["keys"][0]["provider"] == provider
                        status, linked = request("/api/keys/link", {"provider": provider, "key": key + "linked"})
                        assert status == 200 and linked["account"]["keys"][-1]["provider"] == provider
                        opts = {"provider": provider, "key": key, "model": "chosen-model", "party": "default", "mode": "classic"}
                        status, result = request("/api/start", opts)
                        assert status == 200 and result["brain"] == provider, result
                        env = captured[-1]
                        assert env["DUNGEON_BRAIN_BACKEND"] == provider
                        assert env["DUNGEON_MODEL_HAIKU"] == env["DUNGEON_MODEL_SONNET"] == "chosen-model"
                        assert env["DUNGEON_BRAIN_FALLBACK"] == ""
                        assert env["OPENAI_BASE_URL"] == C.OPENAI_DEFAULT_BASE   # 자식 .env가 목적지를 바꿀 수 없음
                        assert all(env[name] == (key if p == provider else "") for p, name in C.KEY_ENV.items())
                        assert all(env[name] == "" for name in C.LEGACY_MODEL_ENV.values())
                        assert all(os.environ[k] == value for k, value in parent.items())
                        for path in Path(tmp).rglob("*"):
                            if path.is_file():
                                assert key.encode() not in path.read_bytes(), path
                        meta = {"seed": 42, "turn_last": 5, "backend": provider}
                        with patch.object(L.Runner, "resumable", return_value=meta):
                            status, result = request("/api/start", {"resume": True, "key": key})
                            assert status == 200 and result["resumed"], result
                            assert captured[-1]["DUNGEON_BRAIN_BACKEND"] == provider
                            assert captured[-1]["DUNGEON_MODEL_HAIKU"] == "chosen-model"
                            status, result = request("/api/start", {"resume": True, "provider": "openai_api", "model": "other-model", "key": key})
                            assert status == 200 and captured[-1]["DUNGEON_MODEL_HAIKU"] == "other-model", result
                            status, result = request("/api/start", {"resume": True, "key": key})
                            assert status == 200 and captured[-1]["DUNGEON_BRAIN_BACKEND"] == "openai_api", result
                            assert captured[-1]["DUNGEON_MODEL_HAIKU"] == "other-model"
                    for invalid in ({"provider": "dummy"}, {"provider": []}, {"provider": "unknown"}, {"model": []}, {"base_url": "http://localhost"}):
                        status, _ = request("/api/start", {"key": "fake-key-123456789012345", **invalid})
                        assert status == 400
            finally:
                srv.shutdown()
                srv.server_close()
                thread.join(timeout=3)
        print("PASS 공개 API 회사별 로그인·연결·me·러너 키 격리·모델 전달·이어가기·부모 환경/파일 키 미기록")
    print("ALL PASS model wiring (API 0 calls)")


if __name__ == "__main__":
    run()

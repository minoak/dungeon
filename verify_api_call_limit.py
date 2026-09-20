# -*- coding: utf-8 -*-
"""실 API 0콜: 러너 프로세스당 전송 시도 상한과, 한도에 닿은 판이 어떻게 멈추고 어떻게 이어지는지(D96)를 본다.
  ① 전송 상한 — 동시 호출·실패한 시도도 한 예산을 나눠 쓴다 · 한도 0 = 옛 동작(무제한) · 한도 라벨은 계약(brains.API_LIMIT_LABEL)
  ② 가르기 — brains.api_limit_only: 이 틱의 실패가 전부 한도 때문이면 True, 다른 실패가 하나라도 섞이면 False(그 판단은 재시도에 뜻이 있다)
  ③ 한도에 닿은 판(D96) — 판단 정지를 열지 않는다(brain_pause 줄 없음 · 러너가 재시도를 권하지 않는다) · 곧바로 곱게 멈춘다
     (end 줄 없음 · exit 0) · 멈춘 판의 요약 사유가 'budget' · 이어갈 몸이 남는다
  ④ 공개 서버 경로 — /api/presets 가 한도를 내려 주고(화면이 그 값을 그대로 쓴다) 러너 환경변수로 같은 값이 간다 ·
     세션 → 키 → 이어가기로 멈춘 판이 계속된다(resume 줄의 앞 조각 사유 = budget · 이어간 판은 새 러너라 한도를 다시 0부터 센다)
  ⑤ 한도 말고 다른 이유로 실패한 판단은 옛 그대로 판단 정지를 연다(재시도 안내 · 사유 pause_timeout)
"""
import contextlib
import http.client
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch

import brains

HERE = Path(__file__).resolve().parent


def run_fixture(mode):
    """격리 러너(실 API 0콜) — 모든 판단이 한 가지 이유로 실패한다.
      budget = 한도에 닿아 전송을 못 한 실패(D96) · parse = 옛 방식의 응답 불량.
    세계 설정(크기·틱·스위치)은 부모가 준 환경 그대로 둔다 — 이어가기 지문(_world_fingerprint)이 같아야 하기 때문이다.
    두뇌 이름만 실 백엔드로 바꾼다: 더미 두뇌는 실패를 규칙 두뇌로 대신해 버려서 '판단 실패' 자체를 볼 수 없다."""
    os.environ["DUNGEON_BRAIN_BACKEND"] = "gemini_api"
    label = brains.API_LIMIT_LABEL if mode == "budget" else "타임아웃 60s"

    def call(prompt, model="haiku"):
        return "", label

    brains._call_claude = call

    def tripwire(*args, **kwargs):      # 모킹 솔기를 우회한 구현은 실제 백엔드까지 가지 못한다
        raise AssertionError("검증 중 실제 백엔드 호출 금지")

    brains._call_gemini = brains._call_cli = brains._call_anthropic = brains._call_openai = tripwire
    brains._http_post = tripwire
    import show_runner
    show_runner.main()


if __name__ == "__main__" and len(sys.argv) == 3 and sys.argv[1] == "--fixture":
    run_fixture(sys.argv[2])
    raise SystemExit(0)

# ── 여기부터는 게이트 프로세스만 — 자식 러너가 물려받는 짧은 판 설정(부모와 러너가 같은 세계를 봐야 이어가기가 된다) ──
os.environ.update(DUNGEON_GM="0", DUNGEON_TURNS="3", DUNGEON_W="40", DUNGEON_H="16", DUNGEON_DEPTHS="1",
                  DUNGEON_MONSTERS="1", DUNGEON_TRAPS="0", DUNGEON_LURKERS="0", DUNGEON_STEP_DELAY="0",
                  DUNGEON_BESTIARY_FILE="", DUNGEON_SIGHT="6", DUNGEON_TOWN_APART="1", DUNGEON_BRAIN_BACKEND="dummy")
for _k in ("DUNGEON_PARTY_FILE", "DUNGEON_STATE_DIR", "DUNGEON_RESUME", "DUNGEON_TOWN", "DUNGEON_ARCH",
           "DUNGEON_STREAM_OBS", "DUNGEON_PAUSE_LIMIT_SEC", "DUNGEON_API_CALL_LIMIT", "DUNGEON_BRAIN_FALLBACK",
           "BOTPIKDUN_DATA", "BOTPIKDUN_BRAIN", "BOTPIKDUN_MAX_RUNS", "BOTPIKDUN_START_PER_HOUR",
           "BOTPIKDUN_PAUSE_LIMIT_SEC", "BOTPIKDUN_UNWATCHED_LIMIT_SEC", "BOTPIKDUN_API_CALL_LIMIT"):
    os.environ.pop(_k, None)

import launcher                                       # noqa: E402
import run_control                                    # noqa: E402
import server                                         # noqa: E402

FIXTURE = str(HERE / "verify_api_call_limit.py")
KEY = "AIzaSyTESTKEY-0123456789abcdefghijklmnop"      # 가짜 키(형태만) — 실제로 쓰이지 않는다(서버 두뇌가 dummy)
LIMIT = 500                                           # ④ 서버가 한 판에 걸어 두는 호출 수(파트너 확정값 그대로 본다)


def records(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


class Judge:
    """번호표(쿠키) 하나를 쥔 방문자 — 공개 서버에 HTTP 로 말을 건다."""

    def __init__(self, port):
        self.port, self.cookie = port, None

    def call(self, path, body=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=90)
        headers = {"Content-Type": "application/json"}
        if self.cookie:
            headers["Cookie"] = "botpikdun_sid=" + self.cookie
        c.request("POST" if body is not None else "GET", path,
                  json.dumps(body).encode("utf-8") if body is not None else None, headers)
        r = c.getresponse()
        raw = r.read()
        for name, value in r.getheaders():
            if name.lower() == "set-cookie" and value.startswith("botpikdun_sid="):
                self.cookie = value.split("=", 1)[1].split(";", 1)[0]
        c.close()
        try:
            return r.status, json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return r.status, None


class ApiCallLimitTests(unittest.TestCase):
    """① 전송 상한 — 한 러너 프로세스가 보내는 요청 수를 한 잠금으로 함께 센다."""

    def test_concurrent_calls_share_one_budget(self):
        response = Mock(status_code=200, json=lambda: {"ok": True})
        with patch.object(brains, "API_CALL_LIMIT", 50), patch.object(brains, "_api_call_count", 0), \
                patch("requests.post", return_value=response) as post, contextlib.redirect_stderr(io.StringIO()):
            with ThreadPoolExecutor(max_workers=16) as pool:
                results = list(pool.map(lambda _: brains._http_post("https://example.invalid", {}, {}), range(100)))
            self.assertEqual(post.call_count, 50)
            self.assertEqual(sum(r[0] == 200 for r in results), 50)
            self.assertEqual(sum(r[2] == brains.API_LIMIT_LABEL for r in results), 50)
            self.assertTrue(all(c.kwargs["allow_redirects"] is False for c in post.call_args_list))

    def test_failed_attempts_also_consume_budget(self):
        with patch.object(brains, "API_CALL_LIMIT", 2), patch.object(brains, "_api_call_count", 0), \
                patch("requests.post", side_effect=RuntimeError("no network")) as post, \
                contextlib.redirect_stderr(io.StringIO()):
            for _ in range(5):
                brains._http_post("https://example.invalid", {}, {})
            self.assertEqual(post.call_count, 2)

    def test_default_has_no_limit(self):
        response = Mock(status_code=200, json=lambda: {})
        with patch.object(brains, "API_CALL_LIMIT", 0), patch("requests.post", return_value=response) as post:
            for _ in range(55):
                self.assertEqual(brains._http_post("https://example.invalid", {}, {})[0], 200)
            self.assertEqual(post.call_count, 55)

    def test_label_is_the_contract(self):
        """한도 라벨은 계약이다 — 러너가 이 문자열로 '재시도해도 같은 실패'를 알아본다. 옛 라벨 문법(호출 실패 …)도 그대로."""
        self.assertEqual(brains.API_LIMIT_LABEL, "호출 실패 ApiCallLimit")
        self.assertTrue(brains.API_LIMIT_LABEL.startswith("호출 실패 "))


class BudgetTellsTheTruthTests(unittest.TestCase):
    """② 한도 도달과 판단 정지를 가르는 자리 — 여기서 갈린 뒤에야 화면이 무엇을 말할지 정해진다."""

    def test_api_limit_only_separates_budget_from_retryable_failures(self):
        limit = {"reason": brains.API_LIMIT_LABEL, "src": "error"}
        other = {"reason": "타임아웃 60s", "src": "error"}
        self.assertTrue(brains.api_limit_only({"1": limit, "2": dict(limit)}))
        self.assertFalse(brains.api_limit_only({"1": limit, "2": other}))   # 섞였으면 재시도에 뜻이 있다
        self.assertFalse(brains.api_limit_only({"1": other}))
        self.assertFalse(brains.api_limit_only({}))                          # 실패가 없으면 한도 도달도 아니다
        self.assertFalse(brains.api_limit_only({"1": {"src": "error"}}))

    def test_budget_stop_is_a_stop_request(self):
        """멈추는 길은 사람이 누른 멈춤·D91 과 같다 — 루프 머리 스냅샷이 진실이라 이어가기가 된다."""
        self.assertTrue(issubclass(run_control.BudgetExhausted, run_control.StopRequested))


class BudgetRunnerTests(unittest.TestCase):
    """③⑤ 실제 러너 — 한도에 닿은 판과 그렇지 않은 판이 서로 다르게 멈춘다."""

    def _run(self, temp, mode, extra_env):
        state = Path(temp) / "state"
        state.mkdir()
        runner = launcher.Runner(str(HERE), str(state), str(Path(temp) / "runs"))
        env = {**os.environ, "PYTHONUTF8": "1", "DUNGEON_STATE_DIR": str(state), "DUNGEON_ACTION_MODE": "compose",
               "DUNGEON_PARTY_FILE": str(HERE / "party.json"), "DUNGEON_SEED": "7",
               "DUNGEON_SKILLS": "0", "DUNGEON_TRPG_COMBAT": "0", "DUNGEON_RANDOM_SKILL": "0", **extra_env}
        with (state / "runner.out").open("w", encoding="utf-8") as log:
            runner.proc = subprocess.Popen([sys.executable, FIXTURE, "--fixture", mode],
                                           cwd=str(HERE), env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            code = runner.proc.wait(timeout=90)
            out = (state / "runner.out").read_text(encoding="utf-8", errors="replace")
            self.assertEqual(code, 0, out)
            return state, out, runner
        finally:
            runner.stop()

    def test_call_limit_stops_the_run_without_offering_a_retry(self):
        """③ 한도에 닿은 틱은 판단 정지를 안 연다 — 눌러도 같은 실패로 끝날 버튼을 내밀지 않는다."""
        with tempfile.TemporaryDirectory(prefix="wl_budget_run_") as temp:
            state, out, runner = self._run(temp, "budget", {"DUNGEON_API_CALL_LIMIT": "4"})
            kinds = [r["kind"] for r in records(state / "stream.jsonl")]
            self.assertNotIn("brain_pause", kinds)                  # 재시도를 권하는 줄 자체가 없다
            self.assertNotIn("tick", kinds)                         # 세계는 한 틱도 안 갔다
            self.assertNotIn("end", kinds)                          # 끝난 판이 아니라 이어갈 판이다
            self.assertNotIn("판단 재시도", out)
            self.assertIn("호출 한도", out)
            self.assertIn("이어가면", out)
            resume = runner.resumable(runner.status())
            self.assertIsNotNone(resume, out)
            self.assertEqual(resume["stopped"], "budget")
            self.assertEqual(resume["turn_last"], 0)

    def test_other_failures_still_open_the_old_pause(self):
        """⑤ 한도가 아닌 실패(타임아웃)는 옛 그대로 — 판단 정지가 열리고 재시도를 권한다. 아무도 안 누르면 F1 제한 시간."""
        with tempfile.TemporaryDirectory(prefix="wl_budget_other_") as temp:
            state, out, runner = self._run(temp, "parse", {"DUNGEON_PAUSE_LIMIT_SEC": "1"})
            kinds = [r["kind"] for r in records(state / "stream.jsonl")]
            self.assertEqual(kinds.count("brain_pause"), 1)
            self.assertIn("판단 재시도", out)
            self.assertEqual(runner.resumable(runner.status())["stopped"], "pause_timeout")


class PublicBudgetTests(unittest.TestCase):
    """④ 공개 서버 경로 — 시작 화면이 예고한 값이 러너로 가고, 멈춘 판이 세션·키로 이어진다."""

    def test_public_server_announces_the_limit_and_resumes_a_stopped_run(self):
        with tempfile.TemporaryDirectory(prefix="wl_budget_public_") as temp:
            srv = server.make_public_server("127.0.0.1", 0, root=str(HERE), data_dir=temp, brain="dummy",
                                            api_call_limit=LIMIT, unwatched_limit=0)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            judge = Judge(srv.server_address[1])
            try:
                self.assertEqual(server.API_CALL_LIMIT, 500)        # 파트너 확정값은 코드 한 곳에만 있다
                status, presets = judge.call("/api/presets")
                self.assertEqual(status, 200)
                self.assertEqual(presets.get("api_call_limit"), LIMIT)   # 화면은 이 값을 그대로 쓴다(하드코딩 없음)
                ctx = srv.sessions.get(judge.cookie)

                # 한도에 닿는 판 — 러너 자리에 격리 러너를 세운다(실 API 0콜). 환경변수는 서버가 준 그대로 본다.
                captured, real_popen = {}, launcher.subprocess.Popen

                def spy(args, **kw):
                    captured.update(kw.get("env") or {})
                    launcher.subprocess.Popen = real_popen
                    return real_popen([sys.executable, FIXTURE, "--fixture", "budget"], **kw)

                launcher.subprocess.Popen = spy
                body = {"map": "normal", "mode": "classic", "action_mode": "compose", "party": "default",
                        "seed": 7, "key": KEY}
                try:
                    status, started = judge.call("/api/start", dict(body))
                finally:
                    launcher.subprocess.Popen = real_popen
                self.assertEqual(status, 200, started)
                self.assertEqual(captured.get("DUNGEON_API_CALL_LIMIT"), str(LIMIT))   # 예고한 수가 그대로 러너로

                st = self._wait_idle(judge)
                self.assertEqual(st["resume"]["stopped"], "budget", st)
                self.assertIsNone(st.get("outcome"))
                stream = Path(ctx.state_dir) / "stream.jsonl"
                self.assertNotIn("brain_pause", [r["kind"] for r in records(stream)])

                # 같은 번호표 + 같은 회사의 키로 이어가기 — 새 러너라 한도를 다시 0부터 센다
                captured2 = {}

                def spy2(args, **kw):
                    captured2.update(kw.get("env") or {})
                    launcher.subprocess.Popen = real_popen
                    return real_popen(args, **kw)

                launcher.subprocess.Popen = spy2
                try:
                    status, resumed = judge.call("/api/start", {"resume": True, "key": KEY})
                finally:
                    launcher.subprocess.Popen = real_popen
                self.assertEqual(status, 200, resumed)
                self.assertTrue(resumed.get("resumed"), resumed)
                self.assertEqual(captured2.get("DUNGEON_API_CALL_LIMIT"), str(LIMIT))
                self._wait_idle(judge)
                recs = records(stream)
                resume_lines = [r for r in recs if r["kind"] == "resume"]
                self.assertEqual(len(resume_lines), 1, [r["kind"] for r in recs])
                self.assertEqual(resume_lines[0]["stopped"], "budget")      # 앞 조각이 왜 멈췄는지 기록이 안다
                self.assertEqual(sum(r["kind"] == "run_meta" for r in recs), 1)   # 같은 판, 같은 기록 파일
                self.assertTrue([r for r in recs if r["kind"] == "tick"], [r["kind"] for r in recs])
                self.assertTrue([r for r in recs if r["kind"] == "end"], [r["kind"] for r in recs])
            finally:
                srv.shutdown()
                srv.sessions.stop_all()
                srv.server_close()

    def test_limit_zero_says_nothing_and_changes_nothing(self):
        """한도 0 인 서버는 화면에 예고할 것도 없고 러너에 거는 것도 없다 — 로컬 론처와 같은 판."""
        with tempfile.TemporaryDirectory(prefix="wl_budget_off_") as temp:
            srv = server.make_public_server("127.0.0.1", 0, root=str(HERE), data_dir=temp, brain="dummy",
                                            api_call_limit=0, unwatched_limit=0)
            try:
                self.assertEqual(srv.sessions.api_call_limit, 0)
                with io.open(os.path.join(str(HERE), "launcher.py"), encoding="utf-8") as f:
                    self.assertNotIn("api_call_limit", f.read())     # 로컬 론처는 한도를 걸지 않는다
            finally:
                srv.sessions.stop_all()
                srv.server_close()

    def _wait_idle(self, judge, sec=90):
        deadline = time.monotonic() + sec
        while time.monotonic() < deadline:
            status, st = judge.call("/api/status")
            if status == 200 and st and not st["running"]:
                return st
            time.sleep(0.3)
        self.fail("러너가 제시간에 끝나지 않았다")


if __name__ == "__main__":
    result = unittest.main(verbosity=2, exit=False).result
    if result.wasSuccessful():
        print("ALL PASS — verify_api_call_limit (전송 상한·한도 도달 가르기·곱게 멈춤·공개 서버 예고와 이어가기, 실제 API 0콜)")
    raise SystemExit(0 if result.wasSuccessful() else 1)

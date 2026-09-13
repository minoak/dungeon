# -*- coding: utf-8 -*-
"""실 API 0콜: HTTP 전송을 가로채 동시 호출·재시도가 50회 상한을 넘지 않는지 확인한다."""
import contextlib
import io
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch

import brains


class ApiCallLimitTests(unittest.TestCase):
    def test_concurrent_calls_share_one_budget(self):
        response = Mock(status_code=200, json=lambda: {"ok": True})
        with patch.object(brains, "API_CALL_LIMIT", 50), patch.object(brains, "_api_call_count", 0), \
                patch("requests.post", return_value=response) as post, contextlib.redirect_stderr(io.StringIO()):
            with ThreadPoolExecutor(max_workers=16) as pool:
                results = list(pool.map(lambda _: brains._http_post("https://example.invalid", {}, {}), range(100)))
            self.assertEqual(post.call_count, 50)
            self.assertEqual(sum(r[0] == 200 for r in results), 50)
            self.assertEqual(sum(r[2] == "호출 실패 ApiCallLimit" for r in results), 50)
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


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ApiCallLimitTests))
    if not result.wasSuccessful():
        raise SystemExit(1)
    print("ALL PASS — verify_api_call_limit (HTTP 전송 시도 상한·동시 호출·실패 포함, 실제 API 0콜)")

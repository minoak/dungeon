"""금액 경계, 예산 혼동, 대상 격리, API 실패 전파 검증."""
import unittest
from unittest.mock import Mock
from main import should_stop, stop_targets


class GuardTests(unittest.TestCase):
    def payload(self, amount):
        return dict(budgetDisplayName="botpikdun-total-50000-krw", currencyCode="KRW",
                    budgetAmount=50000, costAmount=amount)

    def test_threshold(self):
        self.assertFalse(should_stop(self.payload(49999.99)))
        self.assertTrue(should_stop(self.payload(50000)))
        self.assertTrue(should_stop(self.payload(60000)))

    def test_unrelated_and_invalid(self):
        for field, value in [("currencyCode", "USD"), ("budgetDisplayName", "other"),
                             ("budgetAmount", 300000), ("costAmount", "NaN"),
                             ("costAmount", "Infinity"), ("costAmount", None)]:
            payload = self.payload(50000)
            payload[field] = value
            self.assertFalse(should_stop(payload))
        self.assertFalse(should_stop({}))

    def test_only_named_target_in_seoul(self):
        session = Mock()
        session.get.side_effect = [Mock(status_code=404),
                                  Mock(status_code=200, json=lambda: {"status": "RUNNING"}),
                                  Mock(status_code=200, json=lambda: {"status": "TERMINATED"})]
        self.assertEqual(stop_targets(session), ["asia-northeast3-b/botpikdun"])
        session.post.assert_called_once_with(
            "https://compute.googleapis.com/compute/v1/projects/botpikdun/zones/asia-northeast3-b/instances/botpikdun/stop",
            timeout=20)

    def test_api_failure_not_reported_as_success(self):
        session = Mock()
        response = Mock(status_code=403)
        response.raise_for_status.side_effect = RuntimeError("permission denied")
        session.get.return_value = response
        with self.assertRaises(RuntimeError):
            stop_targets(session)
        session.post.assert_not_called()


if __name__ == "__main__":
    unittest.main()

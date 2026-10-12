"""Actual shadow handler bookkeeping; no catalog authority is fabricated."""
import unittest
from unittest.mock import Mock
import wakfu_server.combat_resource_loss_handler as m
from wakfu_server.combat_effect_dispatch import EffectInvocation


class Tests(unittest.TestCase):
    def handler(self):
        h = m.NativeResourceLossHandler.__new__(m.NativeResourceLossHandler)
        h.prepared = {}
        h.runner_amounts = {}
        h.allocate_uid = lambda: 123
        h.rng = lambda: 0
        h.event_lifecycle = None
        h.native_eligibility = lambda *a: True
        h._calculate = Mock(return_value=(None, 3, None, False))
        return h

    def invocation(self):
        return EffectInvocation(1, 1, 7, -7, (0, 0, 0))

    def test_rejected_preparation_consumed_without_effect(self):
        h = self.handler()
        i = h.prepare({"effect_class": 48}, {}, self.invocation())
        self.assertIn(123, h.prepared)
        self.assertFalse(h({}, {}, i))
        self.assertFalse(h.prepared)
        self.assertFalse(h.runner_amounts)
        h._calculate.assert_called_once()

    def test_unknown_uid_still_rejected(self):
        from dataclasses import replace

        h = self.handler()
        with self.assertRaisesRegex(ValueError, "Missing native prepared"):
            h({}, {}, replace(self.invocation(), native_running_uid=999))

    def test_cancel_prepared_is_idempotent(self):
        h = self.handler()
        i = h.prepare({"effect_class": 48}, {}, self.invocation())
        h.cancel_prepared(i)
        h.cancel_prepared(i)
        self.assertFalse(h.prepared)
        self.assertFalse(h.runner_amounts)

    def test_calculation_failure_releases_local_runner(self):
        h = self.handler()
        h._calculate.side_effect = ValueError("authority")
        with self.assertRaisesRegex(ValueError, "authority"):
            h.prepare({"effect_class": 48}, {}, self.invocation())
        self.assertFalse(h.prepared)
        self.assertFalse(h.runner_amounts)


if __name__ == "__main__":
    unittest.main()

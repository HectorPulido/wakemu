from dataclasses import replace
import unittest
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_runner_callbacks import runner_value_scope, notify_runner_value


class RunnerCallbackTests(unittest.TestCase):
    def setUp(self):
        self.inv = EffectInvocation(1, 1, 7, -7, (0, 0, 0), native_context_hex="0800")

    def test_zero_consumes_callback_and_equal_bytes_do_not_share_observer(self):
        seen = []
        with runner_value_scope(lambda inv, value: seen.append(value)) as first:
            observed = replace(self.inv, native_value_scope=first)
            with runner_value_scope(lambda inv, value: seen.append(-value)) as other:
                # Equal serialized contexts still represent distinct PS instances.
                notify_runner_value(replace(self.inv, native_value_scope=other), 3)
            notify_runner_value(self.inv, 100)  # Secondary event/new PS, no observer.
            notify_runner_value(observed, 0)
            notify_runner_value(observed, 8)
        self.assertEqual(seen, [-3, 0])

    def test_scope_closes_on_failure_and_rejects_escaped_identity(self):
        with self.assertRaisesRegex(RuntimeError, "rollback"):
            with runner_value_scope(lambda inv, value: None) as observer:
                escaped = replace(self.inv, native_value_scope=observer)
                raise RuntimeError("rollback")
        with self.assertRaisesRegex(ValueError, "escaped"):
            notify_runner_value(escaped, 1)
        notify_runner_value(self.inv, 1)

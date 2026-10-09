"""Native child construction releases proven null-Qf PVs without retention."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_retained_runtime import NativeRetainedRuntime


class RetainedNullManagerTests(unittest.TestCase):
    def runtime(self):
        runtime = object.__new__(NativeRetainedRuntime)
        runtime.fight = SimpleNamespace(
            state_wire_payloads={},
            phase="active",
            native_retained_records={},
            allocate_effect_uid=lambda: 92,
        )
        runtime.packets = []
        runtime.definition = lambda effect, invocation: {
            "owner_on_caster": False,
            "subscription": True,
        }
        return runtime

    def test_verified_null_qf_child_is_released_without_retention_or_notification(self):
        runtime = self.runtime()
        effect = {"effect_class": 330, "native_effect_flags": [17]}
        invocation = EffectInvocation(151184, 20, 4, 81, (0, -163, 0))
        with patch(
            "wakfu_server.combat_retained_runtime.state_manager", return_value=None
        ), patch(
            "wakfu_server.combat_retained_runtime.native_definition_timing",
            return_value={"retained": True},
        ), patch(
            "wakfu_server.combat_state_managers.registered_area_pv",
            return_value=SimpleNamespace(native_running_effect_manager=False),
        ):
            pending = runtime.begin_group(effect, {}, invocation)
            runtime.finish_group(pending)
        self.assertEqual(pending, {"native_null_qf": True, "uid": 92})
        self.assertEqual(runtime.fight.native_retained_records, {})
        self.assertEqual(runtime.packets, [])

    def test_unknown_missing_manager_still_rejects(self):
        runtime = self.runtime()
        with patch(
            "wakfu_server.combat_retained_runtime.state_manager", return_value=None
        ), patch(
            "wakfu_server.combat_retained_runtime.native_definition_timing",
            return_value={"retained": True},
        ), patch(
            "wakfu_server.combat_state_managers.registered_area_pv", return_value=None
        ):
            with self.assertRaisesRegex(
                ValueError, "Missing actual retained group manager"
            ):
                runtime.begin_group(
                    {"effect_class": 330, "native_effect_flags": [17]},
                    {},
                    EffectInvocation(151184, 20, 4, 81, (0, -163, 0)),
                )

    def test_unsubscribed_null_qf_execution_is_not_silently_released(self):
        runtime = self.runtime()
        runtime.definition = lambda effect, invocation: {
            "owner_on_caster": False,
            "subscription": False,
        }
        with patch(
            "wakfu_server.combat_retained_runtime.state_manager", return_value=None
        ), patch(
            "wakfu_server.combat_retained_runtime.native_definition_timing",
            return_value={"retained": True},
        ), patch(
            "wakfu_server.combat_state_managers.registered_area_pv",
            return_value=SimpleNamespace(native_running_effect_manager=False),
        ):
            with self.assertRaisesRegex(
                ValueError, "Missing actual retained group manager"
            ):
                runtime.begin_group(
                    {"effect_class": 330, "native_effect_flags": [17]},
                    {},
                    EffectInvocation(151184, 20, 4, 81, (0, -163, 0)),
                )

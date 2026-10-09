"""Native eWu rejects an actual area PV with null Qf after L1, before L2."""
import unittest
from random import Random
from types import SimpleNamespace
from unittest.mock import Mock, patch
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_state_handler import NativeStateHandler
from wakfu_server.combat_state_ledger import StateLedger
from wakfu_server.combat_area_authority import area_guards


class NullAreaQfStateTests(unittest.TestCase):
    def test_fresh_state_does_not_apply_or_leak_prepared_runner(self):
        fight = SimpleNamespace(
            actors={7: SimpleNamespace(id=7)},
            native_effect_areas={
                91: dict(
                    uid=91,
                    reference=111,
                    cell=(2, 3, 0),
                    native_area_contract="faY",
                    native_running_effect_manager=False,
                    native_qq_bhi=False,
                    native_qq_guard_source="Qq.constructor",
                )
            },
        )
        definitions = {
            "111": dict(type="GLYPH", native_area_properties=[], entry_masks=[10000])
        }
        handler = NativeStateHandler(
            fight,
            [],
            {},
            action_id=1,
            allocate_uid=lambda: 123,
            context=Mock(),
            execute_child=Mock(),
            rng=Random(1).random,
        )
        channels = []
        handler.event_lifecycle = SimpleNamespace(
            phase=lambda effect, invocation, **kwargs: channels.append(
                kwargs["channel"]
            )
        )
        handler.apply_reference = Mock(
            side_effect=AssertionError("Null Qf received a state")
        )
        effect = dict(effect_class=304, target_masks=[[], [], [], [], [], [], []])
        invocation = EffectInvocation(101, 1, 7, 91, (2, 3, 0))
        with patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value=definitions,
        ):
            prepared = handler.prepare(effect, dict(parameters=(1, 1, -1)), invocation)
            self.assertEqual(len(handler.prepared_runners), 1)
            result = handler(effect, dict(parameters=(1, 1, -1)), prepared)
        self.assertFalse(result)
        self.assertEqual(channels, [1])
        self.assertEqual(handler.prepared_runners, {})
        handler.apply_reference.assert_not_called()
        self.assertNotIn("state_ledger", fight.native_effect_areas[91])

    def test_area_bak_is_rechecked_after_l2_callbacks(self):
        area = dict(
            uid=91,
            reference=111,
            cell=(2, 3, 0),
            native_area_contract="faY",
            native_running_effect_manager=True,
            native_qq_bhi=False,
            native_qq_guard_source="Qq.constructor",
            state_ledger=StateLedger(91),
        )
        fight = SimpleNamespace(
            actors={7: SimpleNamespace(id=7)}, native_effect_areas={91: area}
        )
        definitions = {
            "111": dict(type="GLYPH", native_area_properties=[12], entry_masks=[])
        }
        handler = NativeStateHandler(
            fight,
            [],
            {},
            action_id=1,
            allocate_uid=lambda: 123,
            context=Mock(),
            execute_child=Mock(),
            rng=Random(1).random,
        )
        channels = []

        def phase(effect, invocation, **kwargs):
            channel = kwargs["channel"]
            channels.append(channel)
            if channel == 2:
                area["native_qq_bhi"] = True
                area["native_qq_guard_source"] = "Qq.b"

        handler.event_lifecycle = SimpleNamespace(phase=phase)
        handler.apply_reference = Mock(
            side_effect=AssertionError("Removed area passed the post-L2 baK check")
        )
        effect = dict(effect_class=304, target_masks=[[], [], [], [], [], [], []])
        invocation = EffectInvocation(101, 1, 7, 91, (2, 3, 0))
        with patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value=definitions,
        ), patch(
            "wakfu_server.combat_ordinary_death.corpse_gate_bypassed",
            return_value=False,
        ):
            prepared = handler.prepare(effect, dict(parameters=(1, 1, -1)), invocation)
            self.assertEqual(area_guards(fight, 91)["baK"], False)
            result = handler(effect, dict(parameters=(1, 1, -1)), prepared)
        self.assertFalse(result)
        self.assertEqual(channels, [1, 2])
        handler.apply_reference.assert_not_called()
        self.assertEqual(area_guards(fight, 91)["baK"], True)


if __name__ == "__main__":
    unittest.main()

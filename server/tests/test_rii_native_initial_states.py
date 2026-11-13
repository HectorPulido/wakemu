import unittest
import sys
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.achievements import rii_native_initial_states


class RiiNativeInitialStateTests(unittest.TestCase):
    def test_only_owned_native_los_contract_installs_original_states_in_order(self):
        fight = SimpleNamespace(
            actors={7: SimpleNamespace(team=0), -2: SimpleNamespace(team=1)},
            rii_los_lesson_contract={
                "owner": 7,
                "target": -2,
                "native_los_areas": True,
            },
        )
        dispatcher = SimpleNamespace(native_retention=SimpleNamespace(fight=fight))
        apply = unittest.mock.Mock()
        with patch.dict(
            sys.modules,
            {
                "wakfu_server.rift_native_gameplay": SimpleNamespace(
                    apply_native_carrier=apply
                )
            },
        ):
            self.assertTrue(rii_native_initial_states.install(dispatcher))
            self.assertEqual(
                [c.kwargs for c in apply.call_args_list],
                [
                    {"actor_id": -2, "reference": 8005, "grade": 1},
                    {"actor_id": 7, "reference": 8003, "grade": 1},
                ],
            )

    def test_ordinary_and_legacy_encounters_remain_untouched(self):
        fight = SimpleNamespace(
            actors={}, rii_los_lesson_contract={"owner": 7, "target": -2}
        )
        dispatcher = SimpleNamespace(native_retention=SimpleNamespace(fight=fight))
        apply = unittest.mock.Mock()
        with patch.dict(
            sys.modules,
            {
                "wakfu_server.rift_native_gameplay": SimpleNamespace(
                    apply_native_carrier=apply
                )
            },
        ):
            self.assertFalse(rii_native_initial_states.install(dispatcher))
            apply.assert_not_called()

    def test_invalid_participants_rejected(self):
        fight = SimpleNamespace(
            actors={7: SimpleNamespace(team=0), -2: SimpleNamespace(team=0)},
            rii_los_lesson_contract={
                "owner": 7,
                "target": -2,
                "native_los_areas": True,
            },
        )
        dispatcher = SimpleNamespace(native_retention=SimpleNamespace(fight=fight))
        with self.assertRaises(ValueError):
            rii_native_initial_states.install(dispatcher)


if __name__ == "__main__":
    unittest.main()

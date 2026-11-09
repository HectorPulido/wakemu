"""Actual constructor keeps its recurring root and finite opening root distinct."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT / "tests"),
    str(ROOT / "tools"),
]


@unittest.skipUnless(
    os.environ.get("WAKFU_NATIVE_TABLE_RUNTIME") == "1", "native catalog runtime"
)
class CrustacerebroRoundLockTests(unittest.TestCase):
    def test_actual_round_reset_rearms_only_original_unlimited_constructor(self):
        from tests.jondo_native_support_probe import build_fixture
        from native_recorded_instance_fixture import original_bootstrap_publication
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        observed = []
        original = EffectDispatcher._execute_scoped

        def observe(dispatcher, invocation, **kwargs):
            if invocation.reference in (304313, 304341, 316100):
                fight = dispatcher.native_retention.fight
                observed.append((invocation.reference, fight.native_table_turn))
            return original(dispatcher, invocation, **kwargs)

        with original_bootstrap_publication(), patch.object(
            EffectDispatcher, "_execute_scoped", observe
        ):
            case = build_fixture(5182, 218)
            self.assertTrue(
                case.fight.native_npc_initialization_receipts[-7]["initialized"]
            )
            finite_before = {
                uid: entry["execution_count"]
                for uid, entry in case.fight.native_owned_group_effects.items()
                if entry["invocation"]["reference"] == 304322
            }
            self.assertEqual(list(finite_before.values()), [1])
            for _ in range(20):
                if case.fight.native_table_turn >= 5 or case.fight.phase != "active":
                    break
                case.advance()
            self.assertGreaterEqual(case.fight.native_table_turn, 5)
            finite_after = {
                uid: entry["execution_count"]
                for uid, entry in case.fight.native_owned_group_effects.items()
                if entry["invocation"]["reference"] == 304322
            }
            self.assertEqual(
                finite_after,
                finite_before,
                "Original finite listener identity/budget must remain unchanged",
            )
        renewed = {table for reference, table in observed if reference == 304313}
        self.assertTrue({2, 3, 4, 5}.issubset(renewed), observed)
        self.assertTrue(any(reference == 316100 for reference, _ in observed), observed)
        self.assertLessEqual(
            sum(reference == 304341 for reference, _ in observed),
            1,
            "Native one-shot304322 must never become unlimited",
        )


if __name__ == "__main__":
    unittest.main()

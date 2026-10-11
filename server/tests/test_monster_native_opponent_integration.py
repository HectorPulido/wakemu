"""Native companion discovery is opt-in validation search only."""
import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_monster_validation_budget as baseline


class NativeOpponentIntegrationTests(baseline.MonsterValidationBudgetTests):
    def test_companion_lookup_only_in_recovery_search(self):
        recipe = dict(kind="native_opponent", opponent=dict(reference=4152, level=100))
        for recovery in (False, True):
            with self.subTest(recovery=recovery):
                companion = Mock(return_value=[recipe])
                pending = self.modules["monster_pending_scenarios"]
                pending.recovery_owned_state_recipes = Mock(return_value=[])
                pending.recovery_native_opponent_recipes = companion
                self.modules[
                    "wakfu_server.combat_native_spell_casting"
                ].catalog = lambda: {
                    "123": {"cast_criterion_raw": 'IsBreedId("target", 4152)'}
                }
                with patch.dict(sys.modules, self.modules), patch.object(
                    baseline.validator, "fixture", return_value=self.fake_fight()
                ):
                    baseline.validator.run_case(
                        100, 5, 123, 1, [(-7, -7)], 1, recovery_search=recovery
                    )
                self.assertEqual(companion.call_count, int(recovery))

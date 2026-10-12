"""Exercise retained PL reconstruction through actual detached scope guards."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from dataclasses import asdict
import unittest
from wakfu_server.combat_runtime_adapter import NativeActorAuthority
from wakfu_server.combat_summon_initialization import detached_summon_scope
from wakfu_server.combat_state_ledger import StateLedger, RunningState

from wakfu_server import combat_native_container as module


class OwnedConstructorTests(unittest.TestCase):
    def fixture(self):
        actor = SimpleNamespace(id=7, team=-1, state_ledger=StateLedger(7))
        authority = NativeActorAuthority(
            targeting={"dpu_id": 7, "dpr_id": 7, "bcN": -1},
            is_player=False,
            deck_spell_ids=frozenset(),
            excluded_deck_spell_ids=frozenset(),
            is_carried=False,
            breed_id=2431,
            summon_count=0,
            summon_counts_by_breed={},
            occupant_blocks=True,
            native_controller_id=7,
        )
        state = RunningState(21, 3442, 1, 7, 7, -1, "target", False, (), 0, True, None)
        fight = SimpleNamespace(
            actors={},
            owned_stat_effects={22: {"state_uid": 21}},
            native_owned_group_effects={},
            native_owned_area_effects={},
            native_owned_state_containers={21: asdict(state)},
            native_effect_areas={},
        )
        return fight, actor, authority, state

    def test_scoped_actual_constructor_resolves_without_roster_mutation(self):
        fight, actor, authority, state = self.fixture()
        with self.assertRaisesRegex(ValueError, "Invalid owned"):
            module.owned_state_container(fight, 21)
        with detached_summon_scope(fight, actor, authority):
            self.assertEqual(module.owned_state_container(fight, 21), state)
            self.assertEqual(fight.actors, {})
        with self.assertRaisesRegex(ValueError, "Invalid owned"):
            module.owned_state_container(fight, 21)

    def test_foreign_scope_unknown_caster_and_missing_child_reject(self):
        fight, actor, authority, state = self.fixture()
        foreign, _, _, _ = self.fixture()
        with detached_summon_scope(foreign, actor, authority):
            with self.assertRaisesRegex(ValueError, "Invalid owned"):
                module.owned_state_container(fight, 21)
        with detached_summon_scope(fight, actor, authority):
            fight.native_owned_state_containers[21]["caster_id"] = 999
            with self.assertRaisesRegex(ValueError, "Invalid owned"):
                module.owned_state_container(fight, 21)
            fight.native_owned_state_containers[21]["caster_id"] = 7
            fight.owned_stat_effects.clear()
            with self.assertRaisesRegex(ValueError, "Missing unique"):
                module.owned_state_container(fight, 21)

    def test_registered_caster_preserves_prior_behavior(self):
        fight, actor, authority, state = self.fixture()
        fight.actors[7] = actor
        self.assertEqual(module.owned_state_container(fight, 21), state)


if __name__ == "__main__":
    unittest.main()

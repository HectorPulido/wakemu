"""Native lifecycle assertions for operation-local reads; no actor pruning."""
import unittest
from unittest.mock import patch
from wakfu_server.combat_snapshot_actor_visibility import (
    hidden_snapshot_actor_ids as after,
)
from wakfu_server.combat_global_pv_collections import unregister_global_fighter
from wakfu_server.combat_trove_long_map import NativeTroveLongMap
from wakfu_server.combat_geometry_snapshot import source_snapshot
import test_combat_qi_death_lifecycle as qi_death_fixture


def outcome(function, fight):
    try:
        return ("value", function(fight))
    except Exception as error:
        return ("error", type(error), str(error))


class VisibilityReadViewTests(unittest.TestCase):
    def fixture(self):
        return qi_death_fixture.NativeQIDeathLifecycleTests().fight()

    def parity(self, fight):
        identities = tuple(fight.actors)
        initial = source_snapshot(fight)
        new = outcome(after, fight)
        self.assertEqual(tuple(fight.actors), identities)
        self.assertEqual(source_snapshot(fight), initial)
        return new

    def test_registered_live_and_reversible_offplay_corpse_are_preserved(self):
        fight, pc, target, _ = self.fixture()
        self.assertEqual(self.parity(fight), ("value", set()))
        fight.apply_effect_damage(pc.id, target.id, target.hp)
        self.assertEqual(self.parity(fight), ("value", set()))
        self.assertEqual(
            fight.native_global_pv_collections["fighter_status"][str(target.id)],
            "OFF_PLAY",
        )

    def test_actual_ordinary_final_death_reuses_one_validation_and_preserves_history(
        self,
    ):
        from wakfu_server.combat_ordinary_qi_retirement import (
            complete_ordinary_qi_death,
        )

        fight, pc, target, _ = self.fixture()
        fight.apply_effect_damage(pc.id, target.id, target.hp)
        self.assertTrue(complete_ordinary_qi_death(fight, target))
        self.assertEqual(self.parity(fight), ("value", {target.id}))
        original = NativeTroveLongMap.__init__
        counts = []
        for function in (after,):
            calls = []

            def counted(instance, *args, **kwargs):
                calls.append(1)
                original(instance, *args, **kwargs)

            with patch.object(NativeTroveLongMap, "__init__", counted):
                function(fight)
            counts.append(len(calls))
        self.assertEqual(counts, [1])

    def test_actual_pve_unregistration_and_retained_actor_identity(self):
        from test_combat_pve_departure import PvEDepartureTests
        from wakfu_server.combat_pve_departure import retire_pve_actor

        fight = PvEDepartureTests().fixture()
        actor = fight.actors[10]
        retire_pve_actor(fight, actor, root_actor_id=10, owner_id=1)
        actor.pve_withdrawn = True
        self.assertEqual(self.parity(fight), ("value", {10}))

    def test_actual_ordinary_and_captured_summon_retirement(self):
        from test_combat_summon_retirement import SummonRetirementTests

        for origin in ("ordinary", "captured"):
            with self.subTest(origin=origin):
                fight, owner, _, summon = SummonRetirementTests().fight(origin=origin)
                fight.apply_effect_damage(owner.id, summon.id, summon.hp)
                self.assertEqual(self.parity(fight), ("value", {summon.id}))

    def test_actual_forced_retirement_with_positive_hp(self):
        from test_combat_forced_retirement import ForcedRetirementTests

        fixture = ForcedRetirementTests()
        fight, _, target, _, retention, _, _ = fixture.fixture()
        with fight.effect_resolution():
            fixture.retire(fight, target, retention)
        self.assertGreater(target.hp, 0)
        self.assertEqual(self.parity(fight), ("value", {target.id}))

    def test_corrupt_native_map_status_and_registration_errors_match_exactly(self):
        changes = [
            lambda f: f.native_global_pv_collections["fighters"]["states"].__setitem__(
                0, "bad"
            ),
            lambda f: f.native_global_pv_collections["fighter_status"].__setitem__(
                "7", True
            ),
            lambda f: f.native_global_pv_collections["fighter_status"].pop("7"),
            lambda f: f.native_global_pv_collections["retired_fighters"].append(7),
            lambda f: f.native_global_pv_collections.__setitem__("mode", "unsupported"),
            lambda f: setattr(f, "native_ordinary_qi_retirements", []),
            lambda f: f.native_global_pv_collections["fighter_status"].__setitem__(
                "7", "OUT_OF_PLAY"
            ),
        ]
        messages = [
            "Invalid persisted native Trove topology",
            "Missing actual native fighter status",
            "Missing actual native fighter status",
            "Native fighter is both registered and retired",
            "Missing actual native global PV collection producer",
            "Invalid ordinary QI retirement ledger",
            "Unverified native snapshot fighter retirement",
        ]
        for change, message in zip(changes, messages):
            fight, *_ = self.fixture()
            change(fight)
            result = outcome(after, fight)
            self.assertEqual(result[0], "error")
            self.assertIs(result[1], ValueError)
            self.assertEqual(result[2], message)
        fight, *_ = self.fixture()
        unregister_global_fighter(fight, 7)
        fight.native_global_pv_collections["retired_fighters"].clear()
        self.assertEqual(
            outcome(after, fight),
            (
                "error",
                ValueError,
                "Missing actual native fighter registration authority",
            ),
        )

    def test_each_invocation_revalidates_corruption_and_empty_legacy_remains_legacy(
        self,
    ):
        from types import SimpleNamespace

        fight, *_ = self.fixture()
        self.assertEqual(after(fight), set())
        fight.native_global_pv_collections["fighters"]["keys"][0] = "bad"
        self.assertEqual(outcome(after, fight)[0], "error")
        self.assertEqual(after(SimpleNamespace(actors={})), set())


if __name__ == "__main__":
    unittest.main(verbosity=2)

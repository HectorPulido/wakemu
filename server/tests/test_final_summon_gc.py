"""Final native summons stop retaining inert masters; active references survive."""
from copy import deepcopy
import unittest

from test_combat_summon_retirement import SummonRetirementTests
from test_retained_gc_graph import fixture
from wakfu_server.combat_retained_gc import plan_retired_effects
from wakfu_server.combat_retained_gc_boundary import _terminal_retired_ids
from wakfu_server.combat_native_death_status import (
    initialize_fresh_bje_death_status,
    apply_native_fighter_state_transition,
)


class FinalSummonGCTests(unittest.TestCase):
    def test_native_retirement_proof_and_live_pending_master_dependencies(self):
        fight, owner, _, summon = SummonRetirementTests().fight(ko=0)
        summon.native_world_properties = frozenset()
        initialize_fresh_bje_death_status(summon)
        self.assertNotIn(summon.id, _terminal_retired_ids(fight))
        fight.apply_effect_damage(owner.id, summon.id, summon.hp)
        apply_native_fighter_state_transition(summon, 2)
        self.assertIn(summon.id, _terminal_retired_ids(fight))
        self.assertIn(summon.id, fight.actors)
        self.assertIn(summon.id, fight.native_summon_registrations)
        receipt = fight.native_summon_retirements[summon.id]
        sequence = receipt["sequence"]
        receipt["sequence"] += 1
        with self.assertRaises(ValueError):
            _terminal_retired_ids(fight)
        receipt["sequence"] = sequence
        apply_native_fighter_state_transition(summon, 1)
        self.assertNotIn(summon.id, _terminal_retired_ids(fight))
        # The planner receives only IDs certified above by the native boundary.
        snap = fixture()
        snap["actors"]["-200"]["native_master_id"] = -100
        snap["actors"]["-200"]["native_summon_source"] = {"caster_id": -100}
        before = deepcopy(snap)
        final = plan_retired_effects(snap, {-100, -200}, pending_roots=[])
        self.assertEqual(final.effect_uids, {21, 22, 31})
        self.assertTrue({10, 20, 30}.isdisjoint(final.effect_uids))
        live = plan_retired_effects(snap, {-100}, pending_roots=[])
        self.assertFalse(live.effect_uids)
        pending = plan_retired_effects(
            snap, {-100, -200}, pending_roots={"actor_id": -200}
        )
        self.assertFalse(pending.effect_uids)
        # A real carry relationship is an operative reference to the summon.
        snap["actors"]["1"]["carried_actor_id"] = -200
        carried = plan_retired_effects(snap, {-100, -200}, pending_roots=[])
        self.assertFalse(carried.effect_uids)
        snap["actors"]["1"].pop("carried_actor_id")
        self.assertEqual(snap, before)

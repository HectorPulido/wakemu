"""Receipt lookup locations are history, not retained execution roots."""
from copy import deepcopy
import unittest

from test_retained_gc_graph import fixture, wire
from wakfu_server.combat_retained_gc import plan_retired_effects
from wakfu_server.combat_retained_gc_boundary import _planner_snapshot_fields


class BirthLocatorRootTests(unittest.TestCase):
    def test_locator_history_is_omitted_but_real_pending_wire_and_active_roots_survive(
        self,
    ):
        snap = fixture()
        # Producer shape: actor UID -> (staged_receipts index, actor offset).
        # Numeric locations deliberately collide with real running UIDs.
        snap["native_rift_birth_locations"] = {"-100": (20, 21), "-200": (30, 31)}
        snap["rift_wave_state"] = {
            "staged_receipts": [
                {"next_actor_ids": [-100, -200], "next_species_refs": [5525, 5526]}
            ]
        }
        before = deepcopy(snap)
        plan = plan_retired_effects(snap, {-100, -200}, pending_roots=[])
        self.assertEqual(plan.effect_uids, {21, 22, 31})
        self.assertFalse(plan.opaque_sources)
        self.assertEqual(snap, before)
        projected = _planner_snapshot_fields(snap)
        self.assertNotIn("native_rift_birth_locations", projected)
        self.assertIs(projected["rift_wave_state"], snap["rift_wave_state"])
        self.assertEqual(
            plan_retired_effects(projected, {-100, -200}, pending_roots=[]), plan
        )
        # Real queued invocations still retain an operative owner and siblings.
        pending = plan_retired_effects(
            snap, {-100, -200}, pending_roots={"native_delayed_uid": 20}
        )
        self.assertEqual(pending.effect_uids, {31})
        # A live carrier's encoded caster reference still preserves that source.
        active = deepcopy(snap)
        active["state_wire_payloads"]["10"] = wire(10, -100, 1)
        self.assertEqual(
            plan_retired_effects(active, {-100, -200}, pending_roots=[]).effect_uids,
            {31},
        )
        # An actual active area reference is not a receipt locator either.
        active = deepcopy(snap)
        active["native_effect_areas"] = {"900": {"uid": 900, "effect_uid": 30}}
        self.assertEqual(
            plan_retired_effects(active, {-100, -200}, pending_roots=[]).effect_uids,
            {21, 22},
        )
        # No unknown extension is generally reclassified as history.
        custom = deepcopy(snap)
        custom["custom_roots"] = {"-100": (20, 21)}
        self.assertEqual(
            plan_retired_effects(custom, {-100, -200}, pending_roots=[]).effect_uids,
            {31},
        )
        self.assertEqual(snap, before)

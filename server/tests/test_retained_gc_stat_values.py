"""Numeric Actor characteristics are not effect-manager references."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from wakfu_server import combat_retained_gc as gc

from test_retained_gc_graph import fixture
from wakfu_server.combat_retained_gc import plan_retired_effects


FIELDS = (
    "effect_stats",
    "effect_minima",
    "effect_maxima",
    "effect_percentages",
    "effect_base_minima",
    "effect_base_maxima",
)


class ActorCharacteristicRootTests(unittest.TestCase):
    def plan(self, state, pending=()):
        eager = plan_retired_effects(
            state, {-100, -200}, pending_roots=pending, _reference_schemas_valid=False
        )
        demanded = plan_retired_effects(
            state, {-100, -200}, pending_roots=pending, _reference_schemas_valid=True
        )
        self.assertEqual(eager, demanded)
        return demanded

    def test_numeric_characteristic_collision_does_not_retain_dead_effects(self):
        for field in FIELDS:
            for key in (1, "1"):
                with self.subTest(field=field, key=key):
                    state = fixture()
                    state["actors"]["1"][field] = {key: -100, "2": -200}
                    before = deepcopy(state)
                    self.assertEqual(self.plan(state).effect_uids, {21, 22, 31})
                    self.assertEqual(state, before)
                    state["actors"]["1"]["target_id"] = -100
                    self.assertEqual(self.plan(state).effect_uids, {31})
                    del state["actors"]["1"]["target_id"]
                    self.assertEqual(
                        self.plan(state, {"effect_uid": 20}).effect_uids, {31}
                    )

        # Unreachable actor bodies must not acquire a new eager scalar scan.
        state = fixture()
        for row in state["actors"].values():
            row["effect_stats"] = {"1": -100}
        with patch.object(
            gc, "_actor_reference_fields", wraps=gc._actor_reference_fields
        ) as project:
            plan_retired_effects(
                state, {-100, -200}, pending_roots=[], _reference_schemas_valid=True
            )
        self.assertEqual([call.args[0]["id"] for call in project.call_args_list], [1])

    def test_nested_unknown_and_other_scalar_maps_retain_real_references(self):
        for field in FIELDS:
            state = fixture()
            state["actors"]["1"][field] = {"1": {"target_id": -100}}
            self.assertEqual(self.plan(state).effect_uids, {31})
            state["actors"]["1"][field] = {"custom": -100}
            self.assertEqual(self.plan(state).effect_uids, {31})
            del state["actors"]["1"][field]
            state["extension"] = {field: {"1": -100}}
            self.assertEqual(self.plan(state).effect_uids, {31})
        state = fixture()
        state["actors"]["1"]["selected_values"] = {"1": -100}
        self.assertEqual(self.plan(state).effect_uids, {31})

    def test_opaque_map_and_noninteger_value_keep_legacy_uncertainty(self):
        class CustomMap(dict):
            pass

        for value in (CustomMap({"1": -100}), {"1": object()}):
            state = fixture()
            state["actors"]["1"]["effect_stats"] = value
            plan = self.plan(state)
            self.assertFalse(plan.effect_uids)
            self.assertTrue(plan.opaque_sources)

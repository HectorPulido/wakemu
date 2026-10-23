"""One adapter projection shares Qf validation; later projections stay fresh."""
from copy import deepcopy
import unittest
from unittest.mock import patch

import test_combat_runtime_adapter as adapter_fixture
import test_combat_retained_cell_groups as retained_fixture
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_retained_runtime import (
    _native_retained_condition_population,
    remove_owned_group,
)


class ConditionAliasRetainedSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        adapter_fixture.ServerAdapterTests.setUpClass()

    def setUp(self):
        fixture = adapter_fixture.ServerAdapterTests()
        fixture.setUp()
        self.fight, self.adapter = fixture.preview, fixture.adapter
        source, _ = retained_fixture.RetainedCellGroupTests().fixture()
        for name in (
            "native_owned_group_effects",
            "native_retained_records",
            "native_retained_order",
            "native_retained_tracking",
        ):
            setattr(self.fight, name, deepcopy(getattr(source, name)))
        self.invocation = EffectInvocation(339526, 1, 7, -7, (1, 0, 0))

    def context(self):
        return self.adapter.condition(self.fight, {}, None, self.invocation)

    def test_distinct_actor_aliases_share_one_complete_population_validation(self):
        with patch(
            "wakfu_server.combat_retained_runtime._native_retained_condition_population",
            wraps=_native_retained_condition_population,
        ) as build:
            context = self.context()
        self.assertEqual(build.call_count, 1)
        self.assertEqual(
            context.actors["caster"].retained_effect_ids, frozenset({350552})
        )
        self.assertEqual(context.actors["target"].retained_effect_ids, frozenset())
        self.assertEqual(context.actors["caster"].retained_action_ids, frozenset({949}))

    def test_next_condition_observes_actual_group_removal_without_stale_aliases(self):
        with patch(
            "wakfu_server.combat_retained_runtime._native_retained_condition_population",
            wraps=_native_retained_condition_population,
        ) as build:
            before = self.context()
            packets = []
            remove_owned_group(self.fight, packets, action_id=3, uid=901)
            after = self.context()
        self.assertEqual(build.call_count, 2)
        self.assertEqual(
            before.actors["caster"].retained_effect_ids, frozenset({350552})
        )
        self.assertEqual(after.actors["caster"].retained_effect_ids, frozenset())
        self.assertEqual(after.actors["target"].retained_effect_ids, frozenset())
        self.assertEqual(packets[0][0], 13560)

    def test_invalid_full_graph_remains_unknown_after_an_earlier_valid_projection(self):
        self.assertEqual(
            self.context().actors["caster"].retained_effect_ids, frozenset({350552})
        )
        # The selected caster/target still exist. A forged manager anywhere in
        # the complete graph must invalidate the next population projection.
        self.fight.native_retained_records[901]["manager_id"] = 999
        after = self.context()
        self.assertIsNone(after.actors["caster"].retained_effect_ids)
        self.assertIsNone(after.actors["target"].retained_effect_ids)

import unittest
from types import SimpleNamespace
from test_combat_qi_fight import NativeQIFightLifecycleTests
from wakfu_server.combat_casting_context import resolve_criterion_cell_invocation
from wakfu_server.combat_effect_dispatch import EffectInvocation


class CriterionCellBridgeTests(unittest.TestCase):
    def test_actual_occupied_and_empty_qi_cells_preserve_execution_sources(self):
        fixture = NativeQIFightLifecycleTests()
        fight, actor, other = fixture.fixture(radii=(0, 0))
        fixture.initialize(fight)
        adapter = SimpleNamespace(
            _actor=lambda f, a: SimpleNamespace(targeting={"is_eGj": True})
        )
        trigger = {"source": "kept"}
        container = {"type": 1, "id": 7}
        for cell, expected in (
            (actor.position, actor.id),
            (other.position, other.id),
            ((1, 0, 0), None),
        ):
            invocation = EffectInvocation(
                384594,
                1,
                actor.id,
                None,
                cell,
                base_uid=8,
                native_trigger_context=trigger,
                native_retained_container=container,
                native_context_hex="00",
                native_target_cell_argument=True,
            )
            resolved = resolve_criterion_cell_invocation(adapter, fight, invocation)
            self.assertEqual(resolved.target_id, expected)
            self.assertEqual(resolved.cell, cell)
            self.assertTrue(resolved.native_target_cell_argument)
            self.assertIs(resolved.native_trigger_context, trigger)
            self.assertIs(resolved.native_retained_container, container)
            self.assertEqual(
                (resolved.base_uid, resolved.native_context_hex), (8, "00")
            )
            self.assertIsNone(invocation.target_id)

    def test_missing_occupancy_topology_is_not_assumed_empty(self):
        fixture = NativeQIFightLifecycleTests()
        fight, actor, _ = fixture.fixture(radii=(0, 0))
        fixture.initialize(fight)
        fight.native_qi_byte_topology = None
        adapter = SimpleNamespace(
            _actor=lambda f, a: SimpleNamespace(targeting={"is_eGj": True})
        )
        with self.assertRaises(ValueError):
            resolve_criterion_cell_invocation(
                adapter,
                fight,
                EffectInvocation(
                    384594,
                    1,
                    actor.id,
                    None,
                    (1, 0, 0),
                    native_target_cell_argument=True,
                ),
            )

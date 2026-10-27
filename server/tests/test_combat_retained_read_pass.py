"""A pure retained read shares geometry validation but never spans mutations."""
from dataclasses import asdict
import unittest
from unittest.mock import patch

from wakfu_server.combat_retained_runtime import (
    NativeRetainedRuntime,
    native_retained_condition_reader,
)
from wakfu_server.combat_state_ledger import StateLedger
import wakfu_server.combat_state_managers as state_managers
import test_combat_retained_query_snapshot as query_fixtures


class RetainedReadPassTests(unittest.TestCase):
    def fixture(self):
        fight = query_fixtures.RetainedQuerySnapshotTests().fight()
        fight.native_effect_areas = {
            9001: dict(
                uid=9001,
                reference=1477,
                cell=(2, 3, 4),
                native_area_contract="faY",
                native_running_effect_manager=True,
                state_ledger=StateLedger(9001),
            )
        }
        return fight

    def test_condition_population_resolves_area_once_and_next_read_sees_mutations(self):
        fight = self.fixture()
        original = state_managers.state_manager
        resolved = []

        def observe(current, identity):
            resolved.append(identity)
            return original(current, identity)

        with patch.object(state_managers, "state_manager", observe):
            reader = native_retained_condition_reader(fight)
            self.assertEqual(reader(7), ((350552, 949, 901),))
            self.assertEqual(reader(8), ())
        self.assertEqual(resolved, [9001])

        selected = fight.actors.pop(7)
        with self.assertRaisesRegex(ValueError, "Unverified native retained"):
            reader(7)
        fight.actors[7] = selected

        # The existing query owns its immutable result; a new query must
        # validate all current managers and metadata instead of reusing it.
        fight.native_retained_records[901]["manager_id"] = 999
        self.assertEqual(reader(7), ((350552, 949, 901),))
        with self.assertRaises(ValueError):
            native_retained_condition_reader(fight)(7)
        fight.native_retained_records[901]["manager_id"] = 7
        fight.native_effect_areas[9001]["cell"] = (8, 2, 0)
        self.assertEqual(
            native_retained_condition_reader(fight)(7), ((350552, 949, 901),)
        )
        self.assertEqual(original(fight, 9001).position, (8, 2, 0))
        fight.native_effect_areas[9001]["state_ledger"] = StateLedger(9002)
        with self.assertRaisesRegex(ValueError, "registered area state manager"):
            native_retained_condition_reader(fight)(7)

    def test_runtime_view_preserves_live_population_order_and_type_guards(self):
        fight = self.fixture()
        runtime = object.__new__(NativeRetainedRuntime)
        runtime.fight = fight
        initial = runtime.view()
        self.assertEqual(
            [asdict(row) for row in initial.entries],
            [fight.native_retained_records[901]],
        )
        self.assertEqual(runtime._live(), {901})
        fight.native_retained_order.append(901)
        with self.assertRaisesRegex(ValueError, "insertion order"):
            runtime.view()
        fight.native_retained_order[:] = [901]
        fight.native_retained_records[901]["uid"] = True
        with self.assertRaisesRegex(ValueError, "retained effect record"):
            runtime.view()
        fight.native_retained_records[901]["uid"] = 901
        fight.native_retained_records[901]["manager_id"] = 999
        with self.assertRaises(ValueError):
            runtime.view()
        fight.native_retained_records[901]["manager_id"] = 7
        fight.native_owned_group_effects.clear()
        self.assertEqual(runtime.view().entries, ())
        self.assertEqual(fight.native_retained_records, {})
        self.assertEqual(fight.native_retained_order, [])

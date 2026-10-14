"""A removed Qq remains authoritative while its synchronous roots execute."""
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import test_combat_effect_area_events as fixtures
from wakfu_server.combat_effect_area import remove_owned_hour_area
from wakfu_server.combat_state_managers import prune_retired_state_managers
from wakfu_server.combat_trigger_identifiers import source_identifiers


class SynchronousAreaSourceLeaseTests(unittest.TestCase):
    def fixture(self, entry=(10011,)):
        runtime, row, _ = fixtures.AreaEventTests().fixture(entry=entry)
        fight = runtime.fight
        fight.native_retired_area_managers = {}
        runtime.dispatcher.native_retention.fight = fight
        foreign = copy.deepcopy(row)
        foreign.update(uid=902, owner_id=8)
        fight.native_effect_areas[902] = foreign
        runtime.dispatcher.native_retention.synchronize = (
            lambda: prune_retired_state_managers(fight)
        )
        runtime.dispatcher.native_retention.container = lambda inv: (
            dict(container_present=True, container_type=3),
            inv.native_retained_container["id"],
        )
        return runtime, row, copy.deepcopy(foreign)

    def source(self, runtime, inv):
        with patch(
            "wakfu_server.combat_trigger_identifiers.zone_trigger_policies",
            return_value={str(inv.reference): [330, False, True]},
        ):
            result = source_identifiers(
                runtime.dispatcher.native_retention,
                dict(effect_class=330, native_effect_flags=[]),
                inv,
            )
        self.assertEqual(result["native_container"]["type"], 3)

    def test_removed_callback_survives_synchronize_then_releases_empty_qq(self):
        runtime, row, foreign = self.fixture()
        seen = []

        def execute(inv):
            runtime.dispatcher.native_retention.synchronize()
            self.assertNotIn(901, runtime.fight.native_effect_areas)
            self.assertIs(runtime.fight.native_retired_area_managers[901], row)
            self.source(runtime, inv)
            seen.append(inv.reference)

        runtime.dispatcher.execute = execute
        remove_owned_hour_area(
            runtime.fight,
            901,
            callbacks=SimpleNamespace(
                removed=lambda removed: runtime.removed(removed, target_id=8)
            ),
        )
        self.assertEqual(seen, [298554])
        self.assertEqual(runtime.fight.native_retired_area_managers, {})
        self.assertEqual(runtime.fight.native_effect_areas[902], foreign)

    def test_outer_root_continues_after_self_removal_and_nested_activation(self):
        runtime, row, foreign = self.fixture(entry=(10000,))
        runtime.definitions["1474"]["effect_ids"] = (298554, 298555)
        seen = []

        def execute(inv):
            if inv.reference == 298554 and not seen:
                seen.append(inv.reference)
                remove_owned_hour_area(runtime.fight, 901)
                runtime.dispatcher.native_retention.synchronize()
                self.assertTrue(row["executing"])
                nested = dict(runtime.definitions["1474"], effect_ids=(298556,))
                self.assertFalse(
                    runtime._activate(row, nested, runtime.fight.actors[8])
                )
                self.assertTrue(row["executing"])
            else:
                seen.append(inv.reference)
            self.source(runtime, inv)

        runtime.dispatcher.execute = execute
        runtime._activate(row, runtime.definitions["1474"], runtime.fight.actors[8])
        self.assertEqual(seen, [298554, 298555])
        self.assertFalse(row["executing"])
        self.assertEqual(runtime.fight.native_retired_area_managers, {})
        self.assertEqual(runtime.fight.native_effect_areas[902], foreign)

    def test_callback_exception_releases_lease_without_leaking_empty_manager(self):
        runtime, row, foreign = self.fixture()

        def fail(removed):
            raise ValueError("callback failed")

        with self.assertRaisesRegex(ValueError, "callback failed"):
            remove_owned_hour_area(
                runtime.fight, 901, callbacks=SimpleNamespace(removed=fail)
            )
        self.assertFalse(row["removing"])
        self.assertEqual(runtime.fight.native_retired_area_managers, {})
        self.assertEqual(runtime.fight.native_effect_areas[902], foreign)

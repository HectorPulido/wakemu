import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.wakia_bridge.wakfu_ai.bridge.jondo_capabilities import (
    removable_state_levels,
)


class DecurseAdviceTests(unittest.TestCase):
    def test_native_instance_protection_and_whitelist(self):
        def state(level, protected):
            return SimpleNamespace(reference=42, level=level, protected=protected)

        actors = [{"id": 1}, {"id": 2}, {"id": 3}]
        fight = SimpleNamespace(
            actors={
                1: SimpleNamespace(
                    state_ledger=SimpleNamespace(entries=[state(1, None)])
                ),
                2: SimpleNamespace(
                    state_ledger=SimpleNamespace(
                        entries=[state(2, True), state(3, False)]
                    )
                ),
                3: SimpleNamespace(
                    state_ledger=SimpleNamespace(entries=[state(4, True)])
                ),
            }
        )
        catalog = {"states": {"42": {"protected": True}}}
        with patch.dict(sys.modules, {"wakfu_server.combat_state_decurse": None}):
            self.assertEqual(
                removable_state_levels(fight, actors, catalog, 42), [(2, 3)]
            )
        module = SimpleNamespace(RULES={"protected_whitelist": [42]})
        with patch.dict(sys.modules, {"wakfu_server.combat_state_decurse": module}):
            self.assertEqual(
                removable_state_levels(fight, actors, catalog, 42),
                [(1, 1), (2, 2), (2, 3), (3, 4)],
            )
        self.assertEqual(removable_state_levels(fight, actors, {}, 42), [])

    def test_native_reapplication_levels_and_multiple_instances(self):
        def state(level):
            return SimpleNamespace(reference=42, level=level, protected=False)

        actor = SimpleNamespace(
            state_ledger=SimpleNamespace(entries=[state(10), state(20)])
        )
        fight = SimpleNamespace(actors={1: actor})
        actors = [{"id": 1}]
        catalog = {"states": {"42": {"protected": False}}}
        module = SimpleNamespace(
            RULES={"protected_whitelist": [], "selective_child_states": []}
        )
        with patch.dict(sys.modules, {"wakfu_server.combat_state_decurse": module}):
            self.assertEqual(removable_state_levels(fight, actors, catalog, 42, 0), [])
            self.assertEqual(removable_state_levels(fight, actors, catalog, 42, -1), [])
            self.assertEqual(
                removable_state_levels(fight, actors, catalog, 42, 7),
                [(1, 10), (1, 20)],
            )
            self.assertEqual(
                removable_state_levels(fight, actors, catalog, 42, 20),
                [(1, 10), (1, 20)],
            )
            self.assertEqual(
                removable_state_levels(fight, actors, catalog, 42, 65536), []
            )
            module.RULES["selective_child_states"].append(42)
            self.assertEqual(removable_state_levels(fight, actors, catalog, 42, 7), [])
            self.assertEqual(
                removable_state_levels(fight, actors, catalog, 42, 20),
                [(1, 10), (1, 20)],
            )
        actor.state_ledger.entries = [state(0)]
        self.assertEqual(
            removable_state_levels(fight, actors, catalog, 42, 0), [(1, 0)]
        )

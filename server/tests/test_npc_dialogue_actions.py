"""Action contracts extend NPC dialogue without bypassing native criteria."""

import unittest
from unittest.mock import patch

from wakfu_server import npc_world
from wakfu_server.achievements import npc_dialogue_actions
from test_npc_observed_dialogue import captured_row


class NativeActionContractTests(unittest.TestCase):
    def test_otomai_lore_return_contract_is_scoped_to_exact_action_and_actor(self):
        row = captured_row(-1706442046308330, 5459, 1385, -17, -4, 17, 3, 5772, 1239)
        contract = npc_dialogue_actions.resolve(row, 1239)
        self.assertEqual(contract["root"], 5763)
        self.assertEqual(contract["edges"], {(5763, 13287): 5775})
        self.assertIsNone(npc_dialogue_actions.resolve(dict(row, actor_id=-42), 1239))
        self.assertIsNone(npc_dialogue_actions.resolve(row, 1244))

    def test_multiple_actions_preserve_native_conditions_and_placement(self):
        row = captured_row(-1706442046308322, 5461, 1385, -17, -4, 17, 3, 5765, 1243)
        actor = {k: row[k] for k in ("map_id", "instance_id", "x", "y", "z")}
        actor.update(id=1, account_id=2, level=6)
        first = (5461, row["actor_id"], 1385, 0, 1243)
        second = (5461, row["actor_id"], 1385, 0, 1241)
        contracts = {
            first: {"root": 5765, "edges": {}},
            second: {"root": 5757, "edges": {}},
        }
        with patch.object(npc_dialogue_actions, "_CONTRACTS", contracts):
            for done, action, root in ((False, 1243, 5765), (True, 1241, 5757)):
                session, _ = npc_world.begin(
                    lambda: actor,
                    lambda: [row],
                    row["actor_id"],
                    action,
                    facts_provider=lambda: {10595: done},
                )
                self.assertEqual(session.node_id, root)
            with self.assertRaises(ValueError):
                npc_world.begin(
                    lambda: actor,
                    lambda: [row],
                    row["actor_id"],
                    1241,
                    facts_provider=lambda: {10595: False},
                )
            self.assertIsNone(
                npc_dialogue_actions.resolve(dict(row, actor_id=-42), 1241)
            )


if __name__ == "__main__":
    unittest.main()

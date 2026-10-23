"""Characterize portal travel missing from ordinary AI movement candidates.

Gate rows and terrain below are synthetic. These tests do not claim that a
native portal was created, paid for, or traversed by a complete combat runtime.
"""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

_HERE = Path(__file__).resolve().parent
for path in (_HERE, _HERE.parents[1]):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from test_query_search import actor
from wakfu_ai.context.native_context import NativeGraph, encode
from wakfu_ai.planning.query_search import candidates
from wakfu_server.combat_portal_travel import portal_network_pair
from wakfu_server.combat_state import Fight


ORIGIN, WALK, EXIT, ENEMY = (0, 0, 0), (1, 0, 0), (5, 0, 0), (6, 0, 0)


def gate(uid, cell):
    return dict(
        uid=uid,
        cell=cell,
        native_type_id=19,
        native_fight_affiliation=0,
        native_fight_affiliation_source="faV.j(PV).bcM",
    )


class PortalTravelCapabilityGapTests(unittest.TestCase):
    def offers(self, *, gates, spells=()):
        fight = SimpleNamespace(
            walkable=frozenset({ORIGIN, WALK, EXIT, ENEMY}),
            edges=frozenset({(ORIGIN, WALK), (EXIT, ENEMY)}),
            native_effect_areas=gates,
        )
        graph = NativeGraph(encode(dict(runtime=SimpleNamespace(fight=fight))))
        state = dict(
            key="portal-gap-root",
            actors=[
                actor(1, 1, ORIGIN, mp=1),
                actor(9, 0, ENEMY, mp=0),
            ],
        )
        return list(candidates(graph, state, dict(spells=list(spells)), 1))

    def test_affiliated_portal_pair_adds_no_nonadjacent_movement_candidate(self):
        entry, exit = gate(101, ORIGIN), gate(102, EXIT)
        self.assertEqual(portal_network_pair((entry,), (exit,)), (101, 102))
        ordinary = self.offers(gates={})
        with_network = self.offers(gates={101: entry, 102: exit})
        self.assertEqual(with_network, ordinary)
        self.assertEqual(with_network, [dict(type="move", path=[list(WALK)])])
        self.assertNotIn(dict(type="move", path=[list(EXIT)]), with_network)

    def test_owned_cast_targets_remain_eligible_across_disconnected_terrain(self):
        offers = self.offers(
            gates={101: gate(101, ORIGIN), 102: gate(102, EXIT)},
            spells=[dict(spellId=4692, level=1)],
        )
        self.assertTrue(
            any(
                action["type"] == "cast" and action["target"] == list(ENEMY)
                for action in offers
            )
        )
        # The native cast determines portal range, teleportation and ownership.
        # This is candidate eligibility, not evidence that spell 4692 succeeds.
        self.assertFalse(
            any(
                action["type"] == "move" and list(EXIT) in action["path"]
                for action in offers
            )
        )

    def test_core_walk_validation_rejects_remote_gate_even_with_injected_edge(self):
        mover = SimpleNamespace(id=1, position=ORIGIN, hp=30, physical_radius=0)
        fight = SimpleNamespace(
            actors={1: mover},
            walkable={ORIGIN, EXIT},
            edges={(ORIGIN, EXIT)},
            native_effect_areas={101: gate(101, ORIGIN), 102: gate(102, EXIT)},
        )
        # Execute the actual ordinary movement validator on minimal fixtures.
        # It rejects before requiring costs, QI providers or native catalogues.
        with self.assertRaisesRegex(ValueError, "Invalid combat movement path"):
            Fight._move_actor(fight, mover, [EXIT])
        self.assertEqual(mover.position, ORIGIN)


if __name__ == "__main__":
    unittest.main()

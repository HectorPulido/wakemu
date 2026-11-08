import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest

from wakfu_server import combat_materialized_event_history as helper


def fixture():
    rows = [dict(sequence=1, kind="turn_started", turn_id=1, actor_id=1)]
    rows += [
        dict(sequence=i, kind="state_applied", uid=i, actor_id=1) for i in range(2, 402)
    ]
    rows += [dict(sequence=402, kind="turn_started", turn_id=2, actor_id=1)]
    rows += [dict(sequence=i, kind="orientation", actor_id=1) for i in range(403, 703)]
    return SimpleNamespace(events=rows, turn_id=2, sequence=702, _resolution_depth=0)


class MaterializedEventTests(unittest.TestCase):
    def test_old_materialization_removed_current_turn_tail_sequences_preserved(self):
        fight = fixture()
        before = deepcopy(fight.events)
        self.assertEqual(helper.prune_materialized_events(fight), 400)
        self.assertEqual(fight.events, before[:1] + before[401:])
        self.assertEqual(fight.sequence, 702)
        self.assertEqual(fight.events[-256:], before[-256:])
        self.assertEqual(helper.prune_materialized_events(fight), 0)

    def test_hp_invalidation_unknown_events_and_causal_predecessor_retained(self):
        fight = fixture()
        fight.events[20] = dict(
            sequence=21, kind="characteristic_changed", stat_id=1, target_id=1
        )
        fight.events[21] = dict(
            sequence=22, kind="characteristic_changed", stat_id=2, target_id=1
        )
        fight.events[22] = dict(sequence=23, kind="unknown_future_event", target_id=1)
        fight.events[24] = dict(sequence=25, kind="death", actor_id=-1)
        old = deepcopy(fight.events)
        helper.prune_materialized_events(fight)
        for index in (20, 22, 23, 24):
            self.assertIn(old[index], fight.events)
        self.assertNotIn(old[21], fight.events)

    def test_original_death_validator_preserves_causal_adjacency(self):
        tree = ast.parse(
            Path("server/wakfu_server/combat/combat_ordinary_death.py").read_text()
        )
        nodes = [
            n
            for n in tree.body
            if isinstance(n, ast.FunctionDef)
            and n.name in ("registered_ordinary_death", "_registered_death_event")
        ]
        scope = {}
        exec(
            compile(
                ast.Module(body=nodes, type_ignores=[]), "native_death_body", "exec"
            ),
            scope,
        )
        fight = fixture()
        fight.actors = {
            1: SimpleNamespace(id=1, hp=10),
            -1: SimpleNamespace(id=-1, hp=0),
        }
        fight.events[30] = dict(
            sequence=31, kind="damage", source_id=1, target_id=-1, hp=0
        )
        fight.events[31] = dict(sequence=32, kind="death", actor_id=-1)
        self.assertTrue(scope["registered_ordinary_death"](fight, fight.actors[-1]))
        helper.prune_materialized_events(fight)
        self.assertTrue(scope["registered_ordinary_death"](fight, fight.actors[-1]))

    def test_opaque_order_missing_turn_or_inflight_does_not_mutate(self):
        for mode in ("opaque", "order", "turn", "resolution"):
            with self.subTest(mode=mode):
                fight = fixture()
                if mode == "opaque":
                    fight.events[2] = object()
                elif mode == "order":
                    fight.events[2]["sequence"] = 1
                elif mode == "turn":
                    fight.turn_id = 3
                else:
                    fight._resolution_depth = 1
                events = fight.events
                self.assertEqual(helper.prune_materialized_events(fight), 0)
                self.assertIs(fight.events, events)

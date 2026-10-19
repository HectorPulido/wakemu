"""Turn-memory authority needed by generic post-cast repositioning.

These tests establish what the existing serialized native event stream proves;
no species-specific movement policy or replacement combat assertion is used.
"""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from wakfu_ai.context.native_context import NativeGraph, encode
from wakfu_ai.planning.turn_memory import (
    attacked_this_turn,
    damaged_targets_this_turn,
)
from wakfu_ai.planning.query_search import _metrics, _movement_orders
from wakfu_ai.planning.scoring import evaluate
from wakfu_ai.planning.tactical import DEFAULT_WEIGHTS


def native_turn_memory(events, *, turn=7, position=(0, 0, 0)):
    fight = SimpleNamespace(
        turn_id=turn,
        events=deepcopy(events),
        actors={41: SimpleNamespace(position=position)},
    )
    graph = NativeGraph(encode({"runtime": SimpleNamespace(fight=fight)}))
    runtime = graph.field(graph.data["root"], "runtime")
    reference = graph.field(runtime, "fight")
    return graph, reference


class NativeHitAndRunMemoryCharacterizationTests(unittest.TestCase):
    def test_cast_event_survives_position_change_and_fresh_graph_encoding(self):
        event = dict(
            kind="npc_cast", actor_id=41, spell_id=700, target_id=92, turn_id=7
        )
        before, first = native_turn_memory([event])
        after, second = native_turn_memory([event], position=(3, 0, 0))
        self.assertEqual(before.plain(before.field(first, "events")), [event])
        self.assertEqual(after.plain(after.field(second, "events")), [event])
        self.assertEqual(after.plain(after.field(second, "turn_id")), 7)

    def test_turn_and_actor_are_present_to_distinguish_foreign_history(self):
        events = [
            dict(kind="npc_cast", actor_id=41, spell_id=700, target_id=92, turn_id=6),
            dict(kind="npc_cast", actor_id=42, spell_id=700, target_id=92, turn_id=7),
        ]
        graph, fight = native_turn_memory(events)
        self.assertEqual(graph.plain(graph.field(fight, "events")), events)
        self.assertEqual(graph.plain(graph.field(fight, "turn_id")), 7)

    def test_successful_empty_cast_event_does_not_certify_damage(self):
        event = dict(
            kind="npc_cast", actor_id=41, spell_id=700, target_id=None, turn_id=7
        )
        graph, fight = native_turn_memory([event])
        restored = graph.plain(graph.field(fight, "events"))[0]
        self.assertIsNone(restored["target_id"])
        self.assertNotIn("damage", restored)
        self.assertNotIn("outcomes", restored)

    def target_memory(self, events, *, turn=7):
        graph, fight = native_turn_memory(events, turn=turn)
        return damaged_targets_this_turn(graph, fight, 41)

    def test_damaged_target_requires_committed_positive_current_turn_damage(self):
        damage = dict(kind="damage", source_id=41, target_id=92, amount=5)
        cast = dict(kind="npc_cast", actor_id=41, turn_id=7, target_id=92)
        self.assertEqual(self.target_memory([damage, cast]), frozenset({92}))
        for events in (
            [damage],
            [dict(damage, amount=0), cast],
            [dict(damage, source_id=42), cast],
            [damage, dict(cast, actor_id=42)],
            [damage, dict(cast, turn_id=6)],
            [dict(damage, target_id=None), cast],
            [dict(damage, target_id="92"), cast],
        ):
            with self.subTest(events=events):
                self.assertEqual(self.target_memory(events), frozenset())

    def test_turn_boundary_and_foreign_cast_clear_pending_target_damage(self):
        damage = dict(kind="damage", source_id=41, target_id=92, amount=5)
        own_cast = dict(kind="npc_cast", actor_id=41, turn_id=7, target_id=92)
        foreign_cast = dict(kind="npc_cast", actor_id=42, turn_id=7, target_id=92)
        for events in (
            [damage, dict(kind="turn_started"), own_cast],
            [damage, dict(kind="turn_ended"), own_cast],
            [damage, foreign_cast, own_cast],
        ):
            with self.subTest(events=events):
                self.assertEqual(self.target_memory(events), frozenset())


class NativeHitAndRunPolicyTests(unittest.TestCase):
    def attack_events(self, *, actor=41, turn=7, damage=5):
        return [
            dict(kind="damage", source_id=actor, amount=damage),
            dict(
                kind="npc_cast",
                actor_id=actor,
                turn_id=turn,
                spell_id=700,
                target_id=92,
            ),
        ]

    def memory(self, events, **kwargs):
        graph, fight = native_turn_memory(events, **kwargs)
        return attacked_this_turn(graph, fight, 41)

    def test_committed_damaging_cast_latches_after_movement(self):
        events = self.attack_events()
        self.assertTrue(self.memory(events))
        self.assertTrue(self.memory(events, position=(3, 0, 0)))

    def test_support_empty_zero_damage_and_foreign_cast_do_not_latch(self):
        for events in (
            [dict(kind="npc_cast", actor_id=41, turn_id=7)],
            self.attack_events(damage=0),
            self.attack_events(actor=42),
            self.attack_events(turn=6),
            [dict(kind="damage", source_id=41, amount=5)],
        ):
            with self.subTest(events=events):
                self.assertFalse(self.memory(events))

    def test_turn_boundaries_reset_attack_and_pending_damage(self):
        for boundary in ("turn_started", "turn_ended"):
            self.assertFalse(self.memory(self.attack_events() + [dict(kind=boundary)]))
            self.assertFalse(
                self.memory(
                    [
                        dict(kind="damage", source_id=41, amount=5),
                        dict(kind=boundary),
                        dict(kind="npc_cast", actor_id=41, turn_id=7),
                    ]
                )
            )
        self.assertFalse(self.memory(self.attack_events(), turn=8))

    def test_other_cast_closes_pending_damage_without_erasing_committed_attack(self):
        foreign = dict(kind="npc_cast", actor_id=42, turn_id=7)
        self.assertFalse(
            self.memory(
                [
                    dict(kind="damage", source_id=41, amount=5),
                    foreign,
                    dict(kind="npc_cast", actor_id=41, turn_id=7),
                ]
            )
        )
        self.assertTrue(self.memory(self.attack_events() + [foreign]))

    def state(self, x=0, enemy_hp=30):
        def actor(identity, team, position, hp):
            return dict(
                id=identity,
                team=team,
                position=[position, 0, 0],
                hp=hp,
                max_hp=30,
                armor=0,
                ap=6,
                mp=3,
                wp=0,
            )

        return dict(actors=[actor(41, 1, x, 30), actor(92, 2, 3, enemy_hp)])

    def score(self, root, after):
        return evaluate(
            _metrics(root, 41, retreat=True),
            _metrics(after, 41, retreat=True),
            41,
            DEFAULT_WEIGHTS,
            {},
        )[0]

    def test_retreat_preference_is_bounded_and_does_not_replace_attack(self):
        root = self.state(2)
        self.assertGreater(self.score(root, self.state(0)), 0)
        self.assertEqual(_metrics(self.state(-10), 41, retreat=True)["position"], 1.5)
        self.assertGreater(
            self.score(root, self.state(2, enemy_hp=25)),
            self.score(root, self.state(-10)),
        )
        self.assertGreater(
            _metrics(self.state(2), 41)["position"],
            _metrics(self.state(0), 41)["position"],
        )

    def test_retreat_route_is_promoted_without_removing_approach_routes(self):
        state = self.state(0)
        actors = {a["id"]: a for a in state["actors"]}
        cells = [(x, 0, 0) for x in range(-3, 4)]
        edges = [(cells[i], cells[i + 1]) for i in range(len(cells) - 1)]
        edges += [(b, a) for a, b in edges]
        retreat = _movement_orders(edges, cells, actors, 41, retreat=True)
        approach = _movement_orders(edges, cells, actors, 41)
        retreat_routes = list(retreat[0])
        self.assertEqual(retreat_routes[0][-1], (-3, 0, 0))
        self.assertEqual(next(approach[0])[-1], (2, 0, 0))
        self.assertIn(((1, 0, 0), (2, 0, 0)), retreat_routes)


if __name__ == "__main__":
    unittest.main()

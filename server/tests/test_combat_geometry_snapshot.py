import copy
import json
import unittest
from types import SimpleNamespace
from wakfu_server.combat_geometry_snapshot import freeze_terrain, source_snapshot
from wakfu_server.fight_checkpoint_store import snapshot


class GeometrySnapshotTests(unittest.TestCase):
    def fight(self):
        return SimpleNamespace(
            walkable={(0, 0, 0), (1, 0, 1)},
            edges={((0, 0, 0), (1, 0, 1))},
            actors={1: SimpleNamespace(hp=10, states={"a": [1]})},
            events=[],
        )

    def test_preview_shares_only_immutable_terrain(self):
        fight = self.fight()
        freeze_terrain(fight)
        preview = copy.deepcopy(fight)
        self.assertIs(preview.walkable, fight.walkable)
        self.assertIs(preview.edges, fight.edges)
        preview.actors[1].states["a"].append(2)
        self.assertEqual(fight.actors[1].states["a"], [1])
        with self.assertRaises(AttributeError):
            fight.walkable.add((2, 0, 0))

    def test_exact_replacement_and_callback_state_guard(self):
        fight = self.fight()
        freeze_terrain(fight)
        before = source_snapshot(fight)
        fight.actors[1].hp = 9
        self.assertNotEqual(before, source_snapshot(fight))
        fight.actors[1].hp = 10
        freeze_terrain(fight)
        self.assertEqual(before, source_snapshot(fight))
        fight.edges = type(fight.edges)({((1, 0, 1), (0, 0, 0))})
        self.assertNotEqual(before, source_snapshot(fight))

    def test_mutable_fixture_mutation_stays_detectable(self):
        fight = self.fight()
        before = source_snapshot(fight)
        fight.walkable.add((2, 0, 0))
        self.assertNotEqual(before, source_snapshot(fight))

    def test_durable_checkpoint_remains_complete_identical_json(self):
        fight = self.fight()
        before = json.dumps(snapshot(fight), sort_keys=True)
        freeze_terrain(fight)
        self.assertEqual(before, json.dumps(snapshot(fight), sort_keys=True))
        self.assertEqual(len(json.loads(before)["edges"]), 1)

    def test_rejects_nested_mutable_coordinates(self):
        fight = self.fight()
        fight.walkable = [(0, [1], 0)]
        with self.assertRaises(ValueError):
            freeze_terrain(fight)


class CommitGeometryGuardTests(unittest.TestCase):
    def test_serializer_replacement_or_actor_mutation_rejects_commit(self):
        from unittest.mock import patch
        from wakfu_server.combat_spell_transaction import SpellTransaction
        from wakfu_server.combat_spell_commit import commit_spell_transaction

        for mutation in ("geometry", "actor"):
            fight = GeometrySnapshotTests().fight()
            fight.id = 9
            fight.actors[1].id = 1
            freeze_terrain(fight)
            preview = copy.deepcopy(fight)
            preview.actors[1].hp = 8
            tx = SpellTransaction(preview, {}, 0, (), (), (), source_snapshot(fight), 1)
            runtime = SimpleNamespace(
                fight=fight,
                awaiting_ack=None,
                pending=[],
                action_id=0,
                _flush=lambda: (1, b""),
            )

            def serialize(actor, current):
                if mutation == "geometry":
                    fight.walkable = type(fight.walkable)({(4, 4, 4)})
                else:
                    fight.actors[1].hp = 7
                return b""

            with patch(
                "wakfu_server.combat_spell_commit.actor_state", return_value=b""
            ):
                with self.assertRaisesRegex(ValueError, "while serializing"):
                    commit_spell_transaction(runtime, tx, stats_serializer=serialize)
            self.assertIs(runtime.fight, fight)
            self.assertEqual(runtime.action_id, 0)

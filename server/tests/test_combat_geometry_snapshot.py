import copy
import json
import struct
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


class NativeBirthGeometryCommitTests(unittest.TestCase):
    @staticmethod
    def fight_with_birth_pair():
        from wakfu_server.combat_state import Actor, Fight

        fight_id, owner_id, actor_id = 4510, 71, 72
        actors = [
            Actor(71, 0, (0, 0, 0), 100, 6, 3, 10, 1, owner_id, True),
            Actor(72, 1, (1, 0, 0), 100, 6, 3, 5, 1),
        ]
        fight = Fight(
            fight_id,
            actors,
            {(0, 0, 0), (1, 0, 0)},
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        fight.ready(owner_id)
        world = b"\x00\x01\x01" + struct.pack(">q", actor_id)
        admission = struct.pack(">iq", fight_id, actor_id)
        fight.native_rift_creation_deliveries = {
            actor_id: ((12608, world), (13091, admission))
        }
        return fight, actor_id, world, admission

    @staticmethod
    def transaction_for(fight, actor_id):
        from wakfu_server.combat_entry_executor import private_entry_preview
        from wakfu_server.combat_spell_transaction import SpellTransaction

        source, preview = private_entry_preview(fight)
        preview.actors[actor_id].hp -= 17
        return source, preview, SpellTransaction(preview, {}, 0, (), (), (), source, 1)

    def test_frozen_birth_bytes_commit_damage_and_guard_history_without_losing_legacy(
        self,
    ):
        from wakfu_server.combat_geometry_snapshot import source_snapshot
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_spell_commit import commit_spell_transaction

        fight, actor_id, world, admission = self.fight_with_birth_pair()
        source, preview, transaction = self.transaction_for(fight, actor_id)
        self.assertEqual(fight.actors[actor_id].hp, 100)
        self.assertEqual(preview.actors[actor_id].hp, 83)
        self.assertEqual(
            source["native_rift_creation_deliveries"][str(actor_id)],
            [
                {"opcode": 12608, "payload_hex": world.hex()},
                {"opcode": 13091, "payload_hex": admission.hex()},
            ],
        )

        runtime = RuntimeMessages(fight, clock=lambda: 0.0)
        packets = commit_spell_transaction(
            runtime, transaction, stats_serializer=lambda actor, current: b"stats"
        )
        self.assertIs(runtime.fight, preview)
        self.assertEqual(runtime.fight.actors[actor_id].hp, 83)
        self.assertEqual(fight.actors[actor_id].hp, 100)
        self.assertTrue(packets)

        stale, stale_actor, stale_world, stale_admission = self.fight_with_birth_pair()
        _state, _private, stale_transaction = self.transaction_for(stale, stale_actor)
        stale.native_rift_creation_deliveries[stale_actor] = (
            (12608, stale_world + b"changed"),
            (13091, stale_admission),
        )
        stale_runtime = RuntimeMessages(stale, clock=lambda: 0.0)
        with self.assertRaisesRegex(ValueError, "Combat changed after preparing"):
            commit_spell_transaction(
                stale_runtime,
                stale_transaction,
                stats_serializer=lambda actor, current: b"stats",
            )
        self.assertIs(stale_runtime.fight, stale)
        self.assertEqual(stale_runtime.action_id, 0)
        self.assertEqual(stale.actors[stale_actor].hp, 100)

        (
            legacy,
            legacy_actor,
            legacy_world,
            legacy_admission,
        ) = self.fight_with_birth_pair()
        legacy.native_rift_creation_deliveries[legacy_actor] = [
            {"opcode": 12608, "payload_hex": legacy_world.hex()},
            {"opcode": 13091, "payload_hex": legacy_admission.hex()},
        ]
        frozen_again, *_ = self.fight_with_birth_pair()
        self.assertEqual(source_snapshot(legacy), source_snapshot(frozen_again))

        (
            malformed,
            malformed_actor,
            malformed_world,
            malformed_admission,
        ) = self.fight_with_birth_pair()
        malformed.native_rift_creation_deliveries[malformed_actor] = (
            (12608, bytearray(malformed_world)),
            (13091, malformed_admission),
        )
        with self.assertRaisesRegex(ValueError, "nonserializable state"):
            source_snapshot(malformed)

        unrelated_bytes, *_ = self.fight_with_birth_pair()
        unrelated_bytes.native_unrelated_packet_bytes = world
        with self.assertRaisesRegex(ValueError, "nonserializable state"):
            source_snapshot(unrelated_bytes)

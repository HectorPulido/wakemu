import unittest
import struct
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_ready import prepare_ready


class ReadyTests(unittest.TestCase):
    def fight(self):
        cells = {(0, 0, 0), (1, 0, 0)}
        return Fight(
            7,
            [
                Actor(100, 0, (0, 0, 0), 60, 6, 3, 100, 1, 1, True),
                Actor(-200, 1, (1, 0, 0), 20, 4, 2, 10, 1),
            ],
            cells,
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )

    def run_ready(self, fight, callback):
        return prepare_ready(
            fight,
            1,
            True,
            initialize=callback,
            stats_serializer=lambda actor: b"base",
            effects_serializer=lambda: b"\0\0",
        )

    def test_failure_after_mutation_does_not_commit_readiness_or_effects(self):
        fight = self.fight()

        def fail(preview, action):
            preview.actors[100].hp = 1
            raise ValueError("unsupported mandatory innate")

        with self.assertRaises(ValueError):
            self.run_ready(fight, fail)
        self.assertEqual(
            (fight.phase, fight.ready_owners, fight.actors[100].hp),
            ("placement", set(), 60),
        )

    def test_initialization_follows_action_before_first_turn_and_duplicate_is_noop(
        self,
    ):
        fight = self.fight()
        calls = []

        def initialize(preview, action):
            calls.append(action)
            preview.native_class_initializations = {100: {"breed": 8}}
            return preview, (
                (12613, struct.pack(">iii", preview.id, action, -1) + b"innate"),
            )

        preview, messages, packets = self.run_ready(fight, initialize)
        ops = [op for op, _ in packets]
        self.assertLess(ops.index(13912), ops.index(12514))
        self.assertLess(ops.index(13912), ops.index(12873))
        self.assertEqual(
            ops[ops.index(12514) + 1 : ops.index(13477)], [12613, 13420, 12873]
        )
        self.assertEqual(
            (fight.phase, preview.phase, calls), ("placement", "active", [1])
        )
        same, no_messages, no_packets = self.run_ready(preview, initialize)
        self.assertIs(same, preview)
        self.assertIsNone(no_messages)
        self.assertEqual((no_packets, calls), ((), [1]))
        self.assertGreater(messages.action_id, 1)

    def test_readiness_can_commit_one_owner_without_starting_shared_fight(self):
        cells = {(0, 0, 0), (1, 0, 0), (2, 0, 0)}
        fight = Fight(
            9,
            [
                Actor(100, 0, (0, 0, 0), 60, 6, 3, 100, 1, 1, True),
                Actor(101, 0, (1, 0, 0), 60, 6, 3, 100, 1, 2, True),
                Actor(-200, 1, (2, 0, 0), 20, 4, 2, 10, 1),
            ],
            cells,
            {0: {(0, 0, 0), (1, 0, 0)}, 1: {(2, 0, 0)}},
        )
        candidate, messages, packets = prepare_ready(
            fight,
            1,
            True,
            initialize=lambda preview, action: self.fail(
                "class initialization waits for every controlled owner"
            ),
            stats_serializer=lambda actor: b"stats",
            effects_serializer=lambda: b"effects",
        )
        self.assertEqual((fight.phase, fight.ready_owners), ("placement", set()))
        self.assertEqual((candidate.phase, candidate.ready_owners), ("placement", {1}))
        self.assertIsNone(messages)
        self.assertEqual(packets, ())

    def test_ready_serializes_same_owner_heroes_against_the_preview_fight(self):
        from wakfu_server.combat_actor import actual_actor_stats

        cells = {(0, 0, 0), (1, 0, 0), (2, 0, 0)}
        fight = Fight(
            19,
            [
                Actor(100, 0, (0, 0, 0), 60, 6, 3, 100, 1, 1, True),
                Actor(101, 0, (1, 0, 0), 55, 6, 3, 90, 1, 1, True),
                Actor(-200, 1, (2, 0, 0), 20, 4, 2, 10, 1),
            ],
            cells,
            {0: {(0, 0, 0), (1, 0, 0)}, 1: {(2, 0, 0)}},
        )
        for actor in fight.actors.values():
            actor.native_controlled_by_ai = False
        characters = {
            actor.id: {
                "id": actor.id,
                "account_id": 1,
                "level": 1,
                "breed": 8,
                "hp": actor.hp,
                "max_hp": actor.max_hp,
                "x": actor.position[0],
                "y": actor.position[1],
                "z": actor.position[2],
                "map_id": 527,
            }
            for actor in fight.actors.values()
            if actor.controlled
        }

        def serialize(actor, state):
            if not actor.controlled:
                return b"npc"
            return actual_actor_stats(
                characters[actor.id],
                actor,
                state.id,
                wp_current=0,
                wp_maximum=0,
                fight=state,
            )

        def legacy_serializer(actor):
            if not actor.controlled:
                return b"npc"
            return actual_actor_stats(
                characters[actor.id],
                actor,
                fight.id,
                wp_current=0,
                wp_maximum=0,
                fight=fight,
            )

        candidate, messages, packets = prepare_ready(
            fight,
            1,
            True,
            initialize=lambda preview, action: (preview, ()),
            stats_serializer=legacy_serializer,
            runtime_stats_serializer=serialize,
            effects_serializer=lambda: b"\0\0",
        )

        self.assertEqual(candidate.phase, "active")
        self.assertEqual(set(candidate.order), {100, 101, -200})
        self.assertEqual(fight.phase, "placement")
        self.assertIs(messages.fight, candidate)
        self.assertTrue(any(op == 13912 for op, _ in packets))

    def test_initial_creation_delivery_accounts_for_new_actor_without_empty_snapshot(
        self,
    ):
        fight = self.fight()
        creation = (
            12613,
            struct.pack(">iii", fight.id, 1, -1) + b"actual307-descriptor",
        )

        def initialize(preview, action):
            actor = Actor(300, 0, (0, 0, 0), 15, 4, 2, 5, 1)
            preview.actors[300] = actor
            preview.native_summon_registrations = {300: {"actor_id": 300}}
            preview.native_summon_creation_deliveries = {
                300: {"opcode": creation[0], "payload_hex": creation[1].hex()}
            }
            return preview, (creation,)

        preview, _, packets = self.run_ready(fight, initialize)
        self.assertIn(300, preview.actors)
        self.assertNotIn(300, fight.actors)
        from wakfu_server.fight_checkpoint_store import _plain, snapshot

        self.assertEqual(
            _plain(preview.native_summon_creation_deliveries),
            {"300": {"opcode": creation[0], "payload_hex": creation[1].hex()}},
        )
        self.assertIn("native_summon_creation_deliveries", snapshot(preview))
        snapshots = [payload for op, payload in packets if op == 13912]
        self.assertEqual(len(snapshots), 2)
        self.assertTrue(
            all(struct.unpack_from(">q", payload, 4)[0] != 300 for payload in snapshots)
        )
        self.assertLess(
            next(index for index, row in enumerate(packets) if row[0] == 13912),
            packets.index(creation),
        )

    def test_new_actor_requires_registered_matching_creation_in_initial_outbox(self):
        for registration, recorded, outgoing in (
            (False, True, True),
            (True, False, True),
            (True, True, False),
        ):
            with self.subTest(
                registration=registration, recorded=recorded, outgoing=outgoing
            ):

                def initialize(preview, action):
                    preview.actors[300] = Actor(300, 0, (0, 0, 0), 15, 4, 2, 5, 1)
                    packet = (
                        12613,
                        struct.pack(">iii", preview.id, 1, -1)
                        + b"actual307-descriptor",
                    )
                    preview.native_summon_registrations = (
                        {300: {"actor_id": 300}} if registration else {}
                    )
                    preview.native_summon_creation_deliveries = (
                        {300: {"opcode": packet[0], "payload_hex": packet[1].hex()}}
                        if recorded
                        else {}
                    )
                    return preview, (packet,) if outgoing else ()

                with self.assertRaisesRegex(ValueError, "creation delivery"):
                    self.run_ready(self.fight(), initialize)

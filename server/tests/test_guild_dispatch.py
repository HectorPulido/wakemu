"""Offline session-bound tests for native guild request routing/publication."""
import struct
import unittest
from contextlib import contextmanager, nullcontext
from unittest.mock import patch

from wakfu_server.characters import guild_wire
from wakfu_server.characters.guild_dispatch import Guilds


def _snapshot(members=(1,), guild_id=77):
    return {
        "guild": {
            "id": guild_id,
            "level": 3,
            "blazon": 123456,
            "name": "Offline Guild",
            "description": "",
            "message": "",
            "current_points": 4,
            "total_points": 8,
            "weekly_points_limit": 7500,
            "earned_points_limit": 500,
            "last_earning_point_week": 202640,
        },
        "ranks": [{"id": 10, "name": "Leader", "permissions": 127, "position": 0}],
        "members": [
            {
                "character_id": identity,
                "account_id": identity + 100,
                "rank_id": 10,
                "points": 4,
                "xp": 1000,
                "connected": True,
                "sex": 0,
                "breed": 1,
                "save_date": 1729000000000,
                "language_mask": 0,
                "community": 1,
                "name": f"Member {identity}",
            }
            for identity in members
        ],
        "bonuses": [],
        "policy": {
            "owner_id_semantics": "account",
            "moderation_bonus_learning_factor": 0.25,
        },
    }


def _creation_body(name="Offline Guild"):
    def text(value):
        encoded = value.encode("utf-8")
        return struct.pack(">i", len(encoded)) + encoded

    return struct.pack(">q", 123456) + text(name) + text("Leader") + text("Member")


class FakeWorld:
    def __init__(self):
        self.identities = {}
        self.sent = []
        self.projections = {}
        self.send_result = True

    def live_identity(self, *, character_id):
        return self.identities.get(character_id)

    def send_to(self, character_id, generation, opcode, body):
        self.sent.append((character_id, generation, opcode, body))
        return self.send_result

    def set_guild_projection(self, character_id, generation, model, moderation_factor):
        self.projections[(character_id, generation)] = (model, moderation_factor)


class FakeStore:
    pass


class FakeChatDatabase:
    def __init__(self, policy, sender, member_rows):
        self.policy = policy
        self.sender = sender
        self.member_rows = member_rows

    def execute(self, sql, args=()):
        if "chat_channel_policy" in sql:
            return FakeQuery({"value": self.policy})
        if "SELECT c.name,p.language_mask,p.community" in sql:
            return FakeQuery(self.sender)
        return FakeQuery(rows=self.member_rows)


class FakeQuery:
    def __init__(self, row=None, rows=()):
        self.row = row
        self.rows = list(rows)

    def fetchone(self):
        return self.row

    def __iter__(self):
        return iter(self.rows)


class FakeChatStore:
    def __init__(self, db):
        self.db = db

    @contextmanager
    def connection(self):
        yield self.db

    @staticmethod
    def now():
        return 1000000


class FakeChatService:
    def __init__(self, guild_id=77):
        self.guild_id = guild_id

    def _start(self, db, account, generation, character):
        self.started = (account, generation, character)

    def _guild(self, db, character):
        return {"id": self.guild_id}


class FakeGuildService:
    def __init__(self, enabled=True, snapshots=None):
        self.is_enabled = enabled
        self.is_native_enabled = enabled
        self.snapshots = dict(snapshots or {})
        self.calls = []
        self.create_result = None
        self.invitation = None

    def enabled(self):
        return self.is_enabled

    def native_enabled(self):
        return self.is_native_enabled

    def snapshot(self, account, generation, character):
        self.calls.append(("snapshot", account, generation, character))
        return self.snapshots.get(character)

    def create(self, *args, **kwargs):
        self.calls.append(("create", args, kwargs))
        self.snapshots[args[2]] = self.create_result
        return self.create_result

    def invite(self, *args):
        self.calls.append(("invite", args))
        return self.invitation

    def remove_member(self, *args):
        self.calls.append(("remove_member", args))
        actor = args[2]
        self.snapshots.pop(args[3], None)
        self.snapshots[actor] = _snapshot((actor,))
        return self.snapshots[actor]

    def rank_create(self, *args):
        self.calls.append(("rank_create", args))
        return self.snapshots[args[2]]

    def rank_remove(self, *args):
        self.calls.append(("rank_remove", args))
        return self.snapshots[args[2]]

    def rank_edit(self, *args):
        self.calls.append(("rank_edit", args))
        return self.snapshots[args[2]]

    def rank_move(self, *args):
        self.calls.append(("rank_move", args))
        return self.snapshots[args[2]]

    def change_identity(self, *args, **kwargs):
        self.calls.append(("change_identity", args, kwargs))
        snapshot = self.snapshots[args[2]]
        field, value = args[3:5]
        snapshot["guild"][field] = value
        return snapshot


class GuildDispatchTests(unittest.TestCase):
    def setUp(self):
        self.actor = 1
        self.account = 101
        self.generation = "lease-a"
        self.world = FakeWorld()
        self.world.identities[self.actor] = (
            self.generation,
            {"account_id": self.account, "name": "Member 1"},
        )
        self.service = FakeGuildService()
        self.remote_calls = []
        self.entity = (
            b"\x16" + bytes(range(1, 32)) + guild_wire.local_section(None) + b"NATION!!"
        )
        self.dispatcher = Guilds(
            FakeStore(),
            self.world,
            lambda: self.entity,
            service=self.service,
            remote_publish=lambda character, packet: self.remote_calls.append(
                (character, packet)
            ),
        )

    def _handle_without_storage_guard(self, opcode, body, *, character=None):
        character = self.actor if character is None else character
        with patch.object(self.dispatcher, "_guard", return_value=nullcontext()):
            with patch.object(self.dispatcher, "drain_pending", return_value=0):
                return self.dispatcher.handle(
                    opcode, body, self.account, self.generation, character
                )

    def test_stale_sender_and_disabled_feature_fail_before_service_mutation(self):
        self.world.identities[self.actor] = (
            "replacement-lease",
            {"account_id": self.account, "name": "Member 1"},
        )
        with self.assertRaisesRegex(ValueError, "stale"):
            self._handle_without_storage_guard(13757, _creation_body())
        self.assertEqual([], self.service.calls)

        self.world.identities[self.actor] = (
            self.generation,
            {"account_id": self.account, "name": "Member 1"},
        )
        self.service.is_native_enabled = False
        with self.assertRaisesRegex(ValueError, "disabled"):
            self._handle_without_storage_guard(13757, _creation_body())
        self.assertEqual(
            [], [call for call in self.service.calls if call[0] != "snapshot"]
        )

    def test_management_empty_request_refreshes_snapshot_and_rejects_body(self):
        self.service.snapshots[self.actor] = _snapshot()
        self.assertTrue(self._handle_without_storage_guard(15877, b""))
        self.assertEqual(1, len(self.world.sent))
        character, generation, opcode, body = self.world.sent[0]
        self.assertEqual(
            (self.actor, self.generation, 15548), (character, generation, opcode)
        )
        self.assertEqual(self.actor, struct.unpack(">q", body[:8])[0])
        self.assertEqual(
            "Offline Guild",
            self.world.projections[(self.actor, self.generation)][0]["name"],
        )
        self.assertIs(self.world.identities[self.actor][1], self.remote_calls[-1][0])
        self.assertEqual(
            guild_wire.remote_actor_update(self.actor, 77, 123456, 3, "Offline Guild"),
            self.remote_calls[-1][1],
        )

    def test_remote_publish_callback_is_optional(self):
        self.service.snapshots[self.actor] = _snapshot()
        dispatcher = Guilds(
            FakeStore(), self.world, lambda: self.entity, service=self.service
        )
        with patch.object(dispatcher, "_guard", return_value=nullcontext()):
            with patch.object(dispatcher, "drain_pending", return_value=0):
                self.assertTrue(
                    dispatcher.refresh(self.account, self.generation, self.actor)
                )
        self.assertEqual(1, len(self.world.sent))

        self.world.sent.clear()
        with self.assertRaisesRegex(ValueError, "must be empty"):
            self._handle_without_storage_guard(15877, b"\x00")
        self.assertEqual([], self.world.sent)

    def test_creation_publishes_snapshot_before_success_ack(self):
        current = _snapshot()
        self.service.create_result = current

        self._handle_without_storage_guard(13757, _creation_body())

        self.assertEqual([15548, 1000], [entry[2] for entry in self.world.sent])
        self.assertEqual(self.actor, self.world.sent[0][0])
        self.assertEqual((self.actor, self.generation), self.world.sent[1][:2])
        self.assertEqual(
            guild_wire.creation_ack("Offline Guild")[1], self.world.sent[1][3]
        )

    def test_invitation_notice_uses_captured_target_generation(self):
        target, captured_generation = 2, "target-lease-captured"
        self.service.invitation = {
            "target_id": target,
            "target_generation": captured_generation,
            "inviter_name": "Inviter",
            "guild_name": "Offline Guild",
        }
        self.world.identities[target] = (
            "newer-target-lease",
            {"account_id": 202, "name": "Target"},
        )
        encoded_name = b"Target"
        body = bytes((len(encoded_name),)) + encoded_name

        result = self._handle_without_storage_guard(15542, body)

        self.assertEqual(self.service.invitation, result)
        self.assertEqual(1, len(self.world.sent))
        self.assertEqual((target, captured_generation, 14954), self.world.sent[0][:3])
        self.assertEqual(
            guild_wire.invitation_notice("Inviter", "Offline Guild")[1],
            self.world.sent[0][3],
        )

    def test_removed_member_receives_empty_snapshot(self):
        removed = 2
        self.world.identities[removed] = (
            "lease-b",
            {"account_id": 202, "name": "Member 2"},
        )
        self.service.snapshots = {
            self.actor: _snapshot((self.actor, removed)),
            removed: _snapshot((self.actor, removed)),
        }

        self._handle_without_storage_guard(15627, struct.pack(">q", removed))

        target_update = next(entry for entry in self.world.sent if entry[0] == removed)
        self.assertEqual((removed, "lease-b", 15548), target_update[:3])
        entity_length = struct.unpack(">H", target_update[3][8:10])[0]
        target_entity = target_update[3][10 : 10 + entity_length]
        self.assertEqual(0, struct.unpack(">H", target_entity[32:34])[0])
        self.assertEqual(b"NATION!!", target_entity[-8:])

    def test_rank_requests_route_to_the_matching_service_methods(self):
        self.service.snapshots[self.actor] = _snapshot()
        requests = (
            (15194, b"\x04Rank" + struct.pack(">q", 8), "rank_create"),
            (14088, struct.pack(">q", 10), "rank_remove"),
            (14815, struct.pack(">qq", 10, 8) + b"\x04Rank", "rank_edit"),
            (15429, struct.pack(">qh", 10, 1), "rank_move"),
        )
        for opcode, body, method in requests:
            with self.subTest(opcode=opcode):
                self.world.sent.clear()
                before = len(self.service.calls)
                self._handle_without_storage_guard(opcode, body)
                self.assertEqual(method, self.service.calls[before + 1][0])
                self.assertTrue(self.world.sent)

    def test_bonus_learn_and_activation_route_with_distinct_operation(self):
        from wakfu_server.characters import guild_economy

        self.service.snapshots[self.actor] = _snapshot()
        for opcode, expected_activation in ((15613, False), (14447, True)):
            with self.subTest(opcode=opcode), patch.object(
                guild_economy, "bonus_operation"
            ) as operation:
                self.world.sent.clear()
                self._handle_without_storage_guard(opcode, struct.pack(">i", 14))
                self.assertEqual(self.actor, operation.call_args.args[3])
                self.assertEqual(77, operation.call_args.args[4])
                self.assertEqual(14, operation.call_args.args[5])
                self.assertIs(
                    expected_activation, operation.call_args.kwargs["activate"]
                )
                self.assertTrue(
                    operation.call_args.kwargs["operation_key"].startswith(
                        "native-guild:"
                    )
                )
                self.assertEqual([15548], [entry[2] for entry in self.world.sent])

    def test_identity_change_requests_route_name_and_blazon_fields(self):
        self.service.snapshots[self.actor] = _snapshot()
        requests = (
            (
                12937,
                struct.pack(">i", len(b"New Guild")) + b"New Guild",
                "name",
                "New Guild",
            ),
            (12575, struct.pack(">q", 0x10000000007), "blazon", 0x10000000007),
        )
        for opcode, body, field, value in requests:
            with self.subTest(opcode=opcode):
                before = len(self.service.calls)
                self._handle_without_storage_guard(opcode, body)
                route = self.service.calls[before + 1]
                self.assertEqual("change_identity", route[0])
                self.assertEqual((field, value), route[1][3:5])
                self.assertTrue(route[2]["operation_key"].startswith("native-guild:"))

    def test_refresh_drains_committed_outbox_before_reading_snapshot(self):
        self.service.snapshots[self.actor] = _snapshot()
        events = []
        original_snapshot = self.service.snapshot

        def read_snapshot(*args):
            events.append("snapshot")
            return original_snapshot(*args)

        self.service.snapshot = read_snapshot
        with patch.object(self.dispatcher, "_guard", return_value=nullcontext()):
            with patch.object(
                self.dispatcher,
                "drain_pending",
                side_effect=lambda: events.append("drain") or 0,
            ):
                self.dispatcher.handle(
                    15877, b"", self.account, self.generation, self.actor
                )
        self.assertEqual(["drain", "snapshot"], events)

    def test_failed_snapshot_delivery_raises_and_suppresses_creation_ack(self):
        self.service.create_result = _snapshot()
        self.world.send_result = False

        with self.assertRaisesRegex(ValueError, "synchronization is pending"):
            self._handle_without_storage_guard(13757, _creation_body())

        self.assertNotIn(1000, [entry[2] for entry in self.world.sent])

    def test_malformed_native_requests_are_rejected_before_any_mutation(self):
        for opcode, body in (
            (15194, b"\x05\xc3"),
            (13757, struct.pack(">q", 123) + struct.pack(">i", 4) + b"x"),
            (14088, struct.pack(">q", 10) + b"trailing"),
            (14995, b"\x02"),
        ):
            with self.subTest(opcode=opcode):
                self.service.calls.clear()
                self.world.sent.clear()
                with self.assertRaises(ValueError):
                    self._handle_without_storage_guard(opcode, body)
                self.assertEqual(
                    [], [call for call in self.service.calls if call[0] != "snapshot"]
                )
                self.assertEqual([], self.world.sent)


class GuildChatDispatchTests(unittest.TestCase):
    def setUp(self):
        self.world = FakeWorld()
        self.identities = {
            1: ("sender-lease", {"account_id": 101, "name": "Héctor", "map_id": 10}),
            2: ("member-lease", {"account_id": 202, "name": "Luna", "map_id": 20}),
            3: (
                "replacement-lease",
                {"account_id": 303, "name": "Old Member", "map_id": 30},
            ),
            4: ("foreign-lease", {"account_id": 404, "name": "Visitor", "map_id": 40}),
        }
        self.world.identities = self.identities
        self.policy = {
            "maximum_bytes": 64,
            "minimum_interval_ms": 500,
            "language_mask": 1,
            "community": 2,
        }
        # These rows are the fake DB's authoritative roster membership. They
        # deliberately omit character 4, whose live presence is unrelated.
        self.member_rows = [
            {"character_id": 1, "account_id": 101, "generation": "sender-lease"},
            {"character_id": 2, "account_id": 202, "generation": "member-lease"},
            {"character_id": 3, "account_id": 303, "generation": "old-lease"},
        ]
        self.db = FakeChatDatabase(
            self.policy,
            {"name": "Héctor", "language_mask": 1, "community": 2},
            self.member_rows,
        )
        self.dispatcher = Guilds(
            FakeChatStore(self.db), self.world, lambda: b"", service=FakeChatService()
        )

    def test_guild_743_carries_sender_account_and_routes_only_current_members_across_maps(
        self,
    ):
        sent = self.dispatcher.chat(
            101, "sender-lease", 1, {"guild_id": 77, "text": "Hola ñ"}
        )

        self.assertEqual(2, sent)
        self.assertEqual(
            [(1, 743), (2, 743)], [(row[0], row[2]) for row in self.world.sent]
        )
        self.assertEqual(
            ["sender-lease", "member-lease"], [row[1] for row in self.world.sent]
        )
        self.assertNotIn(3, [row[0] for row in self.world.sent])
        self.assertNotIn(4, [row[0] for row in self.world.sent])
        _, name_end = self.world.sent[0][3][0], 1 + self.world.sent[0][3][0]
        self.assertEqual("Héctor".encode(), self.world.sent[0][3][1:name_end])
        mask, community, account, message_kind = struct.unpack_from(
            ">BBqB", self.world.sent[0][3], name_end
        )
        self.assertEqual((1, 2, 101, 0), (mask, community, account, message_kind))
        text_length = struct.unpack_from(">h", self.world.sent[0][3], name_end + 11)[0]
        self.assertEqual(
            "Hola ñ".encode(),
            self.world.sent[0][3][name_end + 13 : name_end + 13 + text_length],
        )

    def test_foreign_guild_identity_is_denied_without_delivery(self):
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.dispatcher.chat(
                101, "sender-lease", 1, {"guild_id": 78, "text": "Hola"}
            )
        self.assertEqual([], self.world.sent)

    def test_unicode_byte_limit_and_rate_limit_apply_before_delivery(self):
        self.policy["maximum_bytes"] = 4
        with patch(
            "wakfu_server.characters.guild_dispatch.time.monotonic", return_value=10.0
        ):
            self.assertEqual(
                2,
                self.dispatcher.chat(
                    101, "sender-lease", 1, {"guild_id": 77, "text": "ññ"}
                ),
            )
        previous_count = len(self.world.sent)
        with self.assertRaisesRegex(ValueError, "too long"):
            self.dispatcher.chat(
                101, "sender-lease", 1, {"guild_id": 77, "text": "ññx"}
            )
        with patch(
            "wakfu_server.characters.guild_dispatch.time.monotonic", return_value=10.25
        ):
            with self.assertRaisesRegex(ValueError, "rate limit"):
                self.dispatcher.chat(
                    101, "sender-lease", 1, {"guild_id": 77, "text": "ok"}
                )
        self.assertEqual(previous_count, len(self.world.sent))


if __name__ == "__main__":
    unittest.main()

"""Offline tests for session-bound guild chest requests and publication."""
import struct
import threading
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from wakfu_server.characters.guild_chest_dispatch import GuildChestSession


class FakeDatabase:
    def __init__(self, policy):
        self.policy = policy

    def execute(self, _sql, _args=()):
        return self

    def fetchone(self):
        return {"value": self.policy}


class FakeStore:
    def __init__(self, policy):
        self.db = FakeDatabase(policy)

    @contextmanager
    def connection(self):
        yield self.db


class FakeWorld:
    def __init__(self):
        self.identities = {}
        self.sent = []
        self.send_result = True

    def live_identity(self, *, character_id):
        return self.identities.get(character_id)

    def send_to(self, character_id, generation, opcode, body):
        self.sent.append((character_id, generation, opcode, body))
        return self.send_result


def character(identity=10, *, map_id=9, instance_id=0):
    return {
        "id": identity,
        "map_id": map_id,
        "instance_id": instance_id,
        "x": 0,
        "y": 0,
        "z": 0,
    }


def chest(guild_id=77, *, compartment=0, revision=0, items=None):
    return {
        "id": compartment,
        "guild_id": guild_id,
        "name": "Guild Chest",
        "capacity": 40,
        "revision": revision,
        "items": list(items or []),
    }


def request_context(compartments=(0, 1)):
    policy = {
        "enabled": True,
        "native_sync_enabled": True,
        "chest": {
            "enabled": True,
            "access_points": [
                {
                    "map_id": 9,
                    "object_id": 555,
                    "action_id": 12,
                    "parameter": 0,
                    "compartment_ids": list(compartments),
                }
            ],
        },
    }
    objects = [
        {"id": 555, "type": "GuildStorageBox", "map_id": 9, "x": 0, "y": 0, "z": 0}
    ]
    body = struct.pack(">qHH", 555, 12, 0)
    return policy, objects, body


def transfer_body(
    operation,
    *,
    compartment=0,
    item=900,
    reference=2504,
    quantity=3,
    container=800,
    slot=1,
    amount=35
):
    if operation in (0, 1):
        fields = struct.pack(
            ">ibqih", compartment, operation, item, reference, quantity
        )
        if operation == 1:
            fields += struct.pack(">q", container)
        return fields + struct.pack(">b", slot)
    if operation in (3, 4):
        return struct.pack(">ibq", compartment, operation, amount)
    raise ValueError("Unsupported helper operation")


class GuildChestDispatchTests(unittest.TestCase):
    def setUp(self):
        self.policy, self.objects, self.open_body = request_context()
        self.store = FakeStore(self.policy)
        self.actor = character()
        self.generation = "lease-10"
        self.account = 110
        self.view = {
            "guild_id": 77,
            "chests": [chest(77, compartment=0), chest(77, compartment=1)],
            "money": 20,
        }
        self.snapshot_calls = []

        def snapshot(
            _store,
            account,
            generation,
            identity,
            compartments,
            *,
            expected_guild_id=None
        ):
            self.snapshot_calls.append(
                (account, generation, identity, tuple(compartments), expected_guild_id)
            )
            return self.view

        self.snapshot_patch = patch(
            "wakfu_server.characters.guild_chest.snapshot", side_effect=snapshot
        )
        self.snapshot_patch.start()
        self.addCleanup(self.snapshot_patch.stop)
        self.sessions = []

    def open_session(
        self, actor=None, *, world=None, objects_for=None, blocked_now=None
    ):
        actor = actor or self.actor
        identity = actor["id"]
        session = GuildChestSession(
            self.store,
            identity + 100,
            "lease-" + str(identity),
            actor,
            self.open_body,
            self.objects,
            world=world,
            objects_for=objects_for,
            blocked_now=blocked_now,
        )
        self.sessions.append(session)
        return session

    def tearDown(self):
        for session in self.sessions:
            session.close()

    def test_withdrawal_retry_reuses_original_plan_after_chest_becomes_empty(self):
        self.view["chests"][0]["items"] = [
            {
                "slot": 0,
                "item": {"uid": 900, "reference": 2504, "quantity": 3},
                "metadata": {},
            }
        ]
        session = self.open_session()
        body = transfer_body(1)
        results = iter(({"applied": True}, {"applied": False}))
        calls = []

        def transfer(*args, **kwargs):
            calls.append((args, kwargs))
            self.view["chests"][0]["items"] = []
            self.view["chests"][0]["revision"] = 1
            return next(results)

        with patch(
            "wakfu_server.characters.guild_chest.transfer", side_effect=transfer
        ):
            first, _ = session.handle(12531, body, self.actor, self.objects)
            second, _ = session.handle(12531, body, self.actor, self.objects)

        self.assertTrue(first["applied"])
        self.assertFalse(second["applied"])
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0], calls[1])
        self.assertEqual(calls[0][0][4], 0)
        self.assertEqual(
            calls[0][0][5],
            [
                dict(
                    compartment=0,
                    uid=900,
                    reference=2504,
                    quantity=3,
                    slot=0,
                    container=800,
                    destination=1,
                )
            ],
        )
        self.assertEqual(calls[0][1]["expected_guild_id"], 77)
        self.assertEqual(self.snapshot_calls[-1][-1], 77)

    def test_money_deposit_and_withdraw_route_to_atomic_money_operation(self):
        session = self.open_session()
        calls = []

        def transfer_money(*args, **kwargs):
            calls.append((args, kwargs))
            self.view["money"] += -args[5] if kwargs["withdraw"] else args[5]
            return {"applied": True, "money": self.view["money"]}

        with patch(
            "wakfu_server.characters.guild_chest.transfer_money",
            side_effect=transfer_money,
        ):
            deposited, _ = session.handle(
                12531, transfer_body(3, amount=35), self.actor, self.objects
            )
            withdrawn, _ = session.handle(
                12531, transfer_body(4, amount=10), self.actor, self.objects
            )

        self.assertTrue(deposited["applied"])
        self.assertTrue(withdrawn["applied"])
        self.assertEqual([call[1]["withdraw"] for call in calls], [False, True])
        self.assertEqual([call[0][4:6] for call in calls], [(0, 35), (0, 10)])
        self.assertEqual([call[1]["expected_guild_id"] for call in calls], [77, 77])
        self.assertEqual(
            [call[1]["operation_key"] for call in calls][0]
            != [call[1]["operation_key"] for call in calls][1],
            True,
        )

    def test_private_or_activity_contexts_are_denied_before_backend_requests(self):
        session = self.open_session()
        body = transfer_body(3)
        for private in (
            character(instance_id=123),
            character(map_id=8),
        ):
            with self.assertRaises(ValueError):
                session.handle(12531, body, private, self.objects)
        with self.assertRaisesRegex(ValueError, "unavailable"):
            session.handle(12531, body, self.actor, self.objects, blocked=True)
        self.assertEqual(len(self.snapshot_calls), 1)

    def test_stale_lease_and_guild_switch_close_publication(self):
        world = FakeWorld()
        actor = self.actor
        world.identities[actor["id"]] = ("replacement-lease", actor)
        session = self.open_session(
            actor,
            world=world,
            objects_for=lambda _map_id: self.objects,
        )
        GuildChestSession.refresh_guild(77)
        self.assertTrue(session.closed)
        self.assertEqual(world.sent, [])

        world2 = FakeWorld()
        world2.identities[actor["id"]] = ("lease-10", actor)
        self.view = {
            "guild_id": 88,
            "chests": [chest(88, compartment=0), chest(88, compartment=1)],
            "money": 20,
        }
        switched = self.open_session(
            actor,
            world=world2,
            objects_for=lambda _map_id: self.objects,
        )
        self.view = {
            "guild_id": 99,
            "chests": [chest(99, compartment=0), chest(99, compartment=1)],
            "money": 20,
        }
        GuildChestSession.refresh_guild(88)
        self.assertTrue(switched.closed)
        self.assertEqual([entry[2] for entry in world2.sent], [14424, 14787])

    def test_publication_notifies_same_guild_watchers_only(self):
        world = FakeWorld()
        for identity, guild_id in ((10, 77), (11, 77), (12, 88)):
            actor = character(identity)
            world.identities[identity] = ("lease-" + str(identity), actor)
            self.view = {
                "guild_id": guild_id,
                "chests": [
                    chest(guild_id, compartment=0),
                    chest(guild_id, compartment=1),
                ],
                "money": 20,
            }
            self.sessions.append(
                GuildChestSession(
                    self.store,
                    identity + 100,
                    "lease-" + str(identity),
                    actor,
                    self.open_body,
                    self.objects,
                    world=world,
                    objects_for=lambda _map_id: self.objects,
                )
            )
        self.view = {
            "guild_id": 77,
            "chests": [chest(77, compartment=0), chest(77, compartment=1)],
            "money": 20,
        }
        world.sent.clear()

        GuildChestSession.refresh_guild(77)

        self.assertEqual(len(world.sent), 8)
        self.assertEqual({entry[0] for entry in world.sent}, {10, 11})
        self.assertEqual({entry[2] for entry in world.sent}, {14424, 14787, 15817})

    def test_close_clears_native_contents_and_rejects_later_requests(self):
        world = FakeWorld()
        world.identities[self.actor["id"]] = (self.generation, self.actor)
        session = self.open_session(
            self.actor,
            world=world,
            objects_for=lambda _map_id: self.objects,
        )
        session.close(clear=True)

        self.assertTrue(session.closed)
        self.assertEqual([entry[2] for entry in world.sent], [14424, 14787])
        with self.assertRaisesRegex(ValueError, "closed"):
            session.handle(12531, transfer_body(3), self.actor, self.objects)

    def test_close_waits_for_publication_then_clears_without_later_packets(self):
        world = FakeWorld()
        world.identities[self.actor["id"]] = (self.generation, self.actor)
        entered_send = threading.Event()
        release_send = threading.Event()
        close_started = threading.Event()
        close_finished = threading.Event()
        original_send = world.send_to
        first = True

        def blocked_send(character_id, generation, opcode, body):
            nonlocal first
            if first:
                first = False
                entered_send.set()
                if not release_send.wait(timeout=3):
                    raise AssertionError("Timed out waiting to resume publication")
            return original_send(character_id, generation, opcode, body)

        world.send_to = blocked_send
        session = self.open_session(
            self.actor,
            world=world,
            objects_for=lambda _map_id: self.objects,
        )
        publisher = threading.Thread(target=GuildChestSession.refresh_guild, args=(77,))
        publisher.start()
        self.assertTrue(entered_send.wait(timeout=3))

        def close_session():
            close_started.set()
            session.close(clear=True)
            close_finished.set()

        closer = threading.Thread(target=close_session)
        closer.start()
        self.assertTrue(close_started.wait(timeout=3))
        self.assertFalse(close_finished.is_set())
        release_send.set()
        publisher.join(timeout=3)
        closer.join(timeout=3)
        self.assertFalse(publisher.is_alive())
        self.assertFalse(closer.is_alive())
        self.assertTrue(close_finished.is_set())
        self.assertEqual(
            [entry[2] for entry in world.sent],
            [14424, 14787, 14787, 15817, 14424, 14787],
        )


if __name__ == "__main__":
    unittest.main()
